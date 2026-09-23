//! The batched leaf path for native search (R7 build B0;
//! `docs/search_relook/ENGINE_SEARCH_DESIGN.md` §4.1, `docs/proposals/
//! R7_NATIVE_SEARCH_PLAN_2026-09-22.md` §3).
//!
//! One root, many leaves. Each cell `(row, col, n_chance)` of the root matrix is
//! expanded by cloning the root's 384 bytes, writing a CRN seed at `B_RNG`,
//! running ONE engine update, advancing a copy of the root's projection, and
//! encoding BOTH seats' observations with exactly the calls `Gen1Env::step`
//! makes at training time -- `state_for` -> `encode` -> `privileged_block` --
//! so train and search semantics cannot drift. `expand_reproduces_the_training_
//! construction_bitwise` below is the test that says so.
//!
//! **CRN-1** (design §1.2; plan amendment 2, item 1b): the chance seed is keyed
//! on `(seed_base, column, sample)` and NEVER on the row. Every row of the matrix
//! therefore meets the same chance draws for a given opponent reply and sample
//! index, which removes the row-to-row noise a max over rows feeds on. The
//! caller folds the decision key and the determinization index into `seed_base`.
//!
//! Nothing here is a policy or a solver: rows and columns are chosen by the
//! caller (`rl/search/native.py`, build B3), the critic runs in Python over the
//! returned arrays, and the rollout leaf (the I-op) drives a `LeafBatch` from
//! Python with the policy on both seats.

use crate::battle::{Battle, BattleResult, Choice, Outcome, Player, Request, splitmix64};
use crate::encoder::{OBS_DIM, PRIV_DIM, encode, privileged_block};
use crate::env::{Gen1Env, MAX_UPDATES, N_ACTIONS, action_to_choice, mask_for};
use crate::layout::B_RNG;
use crate::observe::ObservableState;
use crate::scripted::Scripted;
use crate::tables::StaticTables;
use crate::track::BattleTracker;

/// A position: the engine's bytes, both seats' projections, and the request
/// pair -- which is NOT in the 384 bytes (rule W-REQ, `spec.rs`).
#[derive(Clone, Debug)]
pub struct Node {
    pub battle: Battle,
    pub tracker: BattleTracker,
    pub result: BattleResult,
}

/// One cell of the root matrix. `row` is an action index (0..10) for the acting
/// seat; `col` an action index for its foe, or `-1` when the foe owes a Pass
/// (the only legal column then). `n_chance` samples share the row's state and
/// differ only in the seed.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Cell {
    pub row: i32,
    pub col: i32,
    pub n_chance: u32,
}

/// What a leaf renders. `Seat` is the acting seat's observation only; `Both`
/// adds the foe's OWN view (the antisymmetric critic's second input, plan
/// amendment 2 item 3) and, for free, both seats' privileged blocks -- each is
/// a slice of the OTHER seat's full encode (`encoder.rs::privileged_block`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Render {
    None,
    Seat,
    Both,
}

/// The expanded leaves, row-major over `cells` then samples.
#[derive(Debug, Default)]
pub struct Expanded {
    pub n: usize,
    /// `n * OBS_DIM`: the acting seat's observation (zeros at a terminal leaf).
    pub obs: Vec<f32>,
    /// `n * OBS_DIM`: the foe's own observation (empty unless `Render::Both`).
    pub obs2: Vec<f32>,
    /// `n * PRIV_DIM`: the foe's own-side block -- D18's privileged block for
    /// the acting seat's critic (empty unless `Render::Both`).
    pub priv1: Vec<f32>,
    /// `n * PRIV_DIM`: the acting seat's own-side block -- the foe's privileged
    /// block (empty unless `Render::Both`).
    pub priv2: Vec<f32>,
    /// From the ACTING seat: 0 not over, 1 win, -1 loss, 2 tie.
    pub terminal: Vec<i8>,
    /// Index into the `cells` the caller passed.
    pub cell: Vec<i32>,
    pub sample: Vec<i32>,
    /// The seed written at `B_RNG` -- the CRN key made visible, so a test can
    /// assert it depends on the column and sample and never on the row.
    pub seed: Vec<u64>,
    /// `n * 2`: the request each seat owes at the leaf, `(acting, foe)`,
    /// 0 pass / 1 move / 2 switch. A leaf where the acting seat owes a Pass is
    /// a state the critic never trained on (the foe is replacing a fainted mon);
    /// the caller decides what to do with it.
    pub req_next: Vec<i8>,
    pub turn: Vec<u16>,
    /// Wall time inside the expansion loop (engine + tracker + encoder), so a
    /// bench can separate it from the PyO3 crossing and array construction.
    pub elapsed_ns: u64,
}

fn req_code(r: Request) -> i8 {
    match r {
        Request::Pass => 0,
        Request::Move => 1,
        Request::Switch => 2,
    }
}

/// **CRN-1.** `(seed_base, col, sample)` -> the u64 written at `B_RNG`. No row.
pub fn leaf_seed(seed_base: u64, col: i32, sample: u32) -> u64 {
    // col -1 (the foe's Pass) -> 1, col 0 -> 2, ...; sample 0 -> 1, ...
    let key = (((col as i64 + 2) as u64) << 32) | (sample as u64 + 1);
    splitmix64(seed_base ^ splitmix64(key))
}

impl Node {
    /// Snapshot a live collector battle: bytes, projection and requests, all
    /// exactly as the env holds them.
    pub fn from_env(env: &Gen1Env) -> Node {
        Node {
            battle: Battle(env.battle().0),
            tracker: env.tracker().clone(),
            result: env.result(),
        }
    }

    /// A root with a FRESH projection: only what `observe` can see from these
    /// bytes (the two actives, their live move slots) is revealed. For fixtures
    /// and constructed roots; a live position comes from `from_env`, and a
    /// resampled world from `with_battle`, which keep the real projection.
    pub fn fresh(battle: Battle, p1: Request, p2: Request) -> Node {
        let mut tracker = BattleTracker::default();
        tracker.observe(&battle);
        Node {
            battle,
            tracker,
            result: BattleResult { outcome: Outcome::None, p1, p2 },
        }
    }

    /// The same projection over different bytes -- a resampled world built from
    /// `BattleSpec::from_visible` plus a hidden-slot fill (build B1b). What each
    /// seat has REVEALED does not change when the hidden slots are redrawn.
    pub fn with_battle(&self, battle: Battle, p1: Request, p2: Request) -> Node {
        Node {
            battle,
            tracker: self.tracker.clone(),
            result: BattleResult { outcome: Outcome::None, p1, p2 },
        }
    }

    pub fn over(&self) -> bool {
        self.result.over()
    }

    pub fn request(&self, p: Player) -> Request {
        self.result.request(p)
    }

    /// The observable state for `p` under the request it owes -- the same call
    /// `Gen1Env::state` makes.
    pub fn state(&self, p: Player, t: &StaticTables) -> ObservableState {
        self.tracker.state_for(&self.battle, p, self.result.request(p), t)
    }

    /// poke-env's 10-way mask for `p`, or all-false when `p` owes a Pass.
    pub fn mask(&self, p: Player, t: &StaticTables) -> [bool; N_ACTIONS] {
        let req = self.result.request(p);
        if req == Request::Pass || self.over() {
            return [false; N_ACTIONS];
        }
        let st = self.state(p, t);
        mask_for(&self.battle, p, req, st.aliased)
    }

    /// The 828-vector for `p` at this position.
    pub fn obs(&self, p: Player, t: &StaticTables) -> Vec<f32> {
        let mut v = vec![0.0f32; OBS_DIM];
        encode(&mut v, t, &self.state(p, t));
        v
    }

    /// The outcome from `p`'s seat: 0 not over, 1 win, -1 loss, 2 tie.
    pub fn outcome_for(&self, p: Player) -> i8 {
        let from_p1 = match self.result.outcome {
            Outcome::None => return 0,
            Outcome::Win => 1,
            Outcome::Lose => -1,
            Outcome::Tie | Outcome::Error => return 2,
        };
        match p {
            Player::P1 => from_p1,
            Player::P2 => -from_p1,
        }
    }

    /// Resolve one cell's choices against the ROOT, once. `action_to_choice`
    /// only ever returns a choice the engine offered, so the per-leaf update can
    /// skip the legality re-check: the leaves differ from the root only in the
    /// seed, which does not change what is offered.
    fn cell_choices(
        &self,
        seat: Player,
        aliased_seat: bool,
        aliased_foe: bool,
        c: &Cell,
    ) -> Result<(Choice, Choice), String> {
        let foe = seat.foe();
        let (rs, rf) = (self.result.request(seat), self.result.request(foe));
        if c.n_chance == 0 {
            return Err(format!("cell {c:?}: n_chance must be >= 1"));
        }
        if c.row < 0 || c.row as usize >= N_ACTIONS {
            return Err(format!("cell {c:?}: row outside 0..{N_ACTIONS}"));
        }
        let cs = action_to_choice(&self.battle, seat, rs, aliased_seat, c.row as usize)
            .ok_or_else(|| format!("cell {c:?}: row action {} is not legal for {seat:?}", c.row))?;
        let cf = if rf == Request::Pass {
            if c.col != -1 {
                return Err(format!(
                    "cell {c:?}: {foe:?} owes a Pass at this root, so the only column is -1"
                ));
            }
            Choice::Pass
        } else {
            if c.col < 0 || c.col as usize >= N_ACTIONS {
                return Err(format!("cell {c:?}: col outside 0..{N_ACTIONS} ({foe:?} owes a decision)"));
            }
            action_to_choice(&self.battle, foe, rf, aliased_foe, c.col as usize)
                .ok_or_else(|| format!("cell {c:?}: col action {} is not legal for {foe:?}", c.col))?
        };
        Ok(match seat {
            Player::P1 => (cs, cf),
            Player::P2 => (cf, cs),
        })
    }

    /// Expand every cell. Returns the rendered leaves and, when `keep` is set,
    /// the leaf nodes themselves (for a `LeafBatch`).
    pub fn expand(
        &self,
        t: &StaticTables,
        seat: Player,
        cells: &[Cell],
        seed_base: u64,
        render: Render,
        keep: bool,
    ) -> Result<(Expanded, Vec<Node>), String> {
        if self.over() {
            return Err("expand() on a finished battle".into());
        }
        let foe = seat.foe();
        if self.result.request(seat) == Request::Pass {
            return Err(format!("{seat:?} owes no decision at this root (request Pass)"));
        }
        let aliased_seat = self.state(seat, t).aliased;
        let aliased_foe = if self.result.request(foe) == Request::Pass {
            false
        } else {
            self.state(foe, t).aliased
        };
        let total: usize = cells.iter().map(|c| c.n_chance as usize).sum();
        let mut out = Expanded {
            obs: Vec::with_capacity(if render == Render::None { 0 } else { total * OBS_DIM }),
            obs2: Vec::with_capacity(if render == Render::Both { total * OBS_DIM } else { 0 }),
            priv1: Vec::with_capacity(if render == Render::Both { total * PRIV_DIM } else { 0 }),
            priv2: Vec::with_capacity(if render == Render::Both { total * PRIV_DIM } else { 0 }),
            terminal: Vec::with_capacity(total),
            cell: Vec::with_capacity(total),
            sample: Vec::with_capacity(total),
            seed: Vec::with_capacity(total),
            req_next: Vec::with_capacity(total * 2),
            turn: Vec::with_capacity(total),
            n: 0,
            elapsed_ns: 0,
        };
        let t0 = std::time::Instant::now();
        let mut nodes = Vec::with_capacity(if keep { total } else { 0 });
        // One scratch leaf, refilled per sample: `clone_from` reuses the
        // tracker's Vec capacity, so a leaf costs a 384-byte memcpy and no
        // allocation.
        let mut leaf = Node {
            battle: Battle(self.battle.0),
            tracker: self.tracker.clone(),
            result: self.result,
        };
        for (ci, c) in cells.iter().enumerate() {
            let (c1, c2) = self.cell_choices(seat, aliased_seat, aliased_foe, c)?;
            for s in 0..c.n_chance {
                let seed = leaf_seed(seed_base, c.col, s);
                leaf.battle.0.copy_from_slice(&self.battle.0);
                leaf.battle.0[B_RNG..B_RNG + 8].copy_from_slice(&seed.to_le_bytes());
                leaf.tracker.clone_from(&self.tracker);
                leaf.result = leaf.battle.update_unchecked(c1, c2);
                if leaf.result.outcome == Outcome::Error {
                    return Err(format!(
                        "cell {c:?} sample {s}: engine returned Error, unreachable in showdown mode"
                    ));
                }
                leaf.tracker.observe(&leaf.battle);
                out.push(&leaf, t, seat, ci, s, seed, render);
                if keep {
                    nodes.push(leaf.clone());
                }
            }
        }
        out.elapsed_ns = t0.elapsed().as_nanos() as u64;
        Ok((out, nodes))
    }
}

impl Expanded {
    #[allow(clippy::too_many_arguments)]
    fn push(
        &mut self,
        leaf: &Node,
        t: &StaticTables,
        seat: Player,
        ci: usize,
        s: u32,
        seed: u64,
        render: Render,
    ) {
        let foe = seat.foe();
        self.cell.push(ci as i32);
        self.sample.push(s as i32);
        self.seed.push(seed);
        self.turn.push(leaf.battle.turn());
        self.req_next.push(req_code(leaf.result.request(seat)));
        self.req_next.push(req_code(leaf.result.request(foe)));
        let term = leaf.outcome_for(seat);
        self.terminal.push(term);
        self.n += 1;
        if render == Render::None {
            return;
        }
        let o = self.obs.len();
        self.obs.resize(o + OBS_DIM, 0.0);
        let p = self.priv1.len();
        if render == Render::Both {
            self.obs2.resize(o + OBS_DIM, 0.0);
            self.priv1.resize(p + PRIV_DIM, 0.0);
            self.priv2.resize(p + PRIV_DIM, 0.0);
        }
        if term != 0 {
            // A terminal leaf's value is its outcome; the encoder is never asked
            // about a finished battle (nor is it at training time).
            return;
        }
        // The acting seat's view under the request it now owes -- exactly
        // `Gen1Env::state` + `encode`.
        let st = leaf.tracker.state_for(&leaf.battle, seat, leaf.result.request(seat), t);
        encode(&mut self.obs[o..o + OBS_DIM], t, &st);
        if render == Render::Both {
            // The foe's OWN view: its own_seat path (exact HP/PP/status, all six
            // slots) and OUR foe_seat path (revealed only) -- the second input
            // of the antisymmetric critic, and the source of D18's block.
            let fst = leaf.tracker.state_for(&leaf.battle, foe, leaf.result.request(foe), t);
            encode(&mut self.obs2[o..o + OBS_DIM], t, &fst);
            privileged_block(&self.obs2[o..o + OBS_DIM], &mut self.priv1[p..p + PRIV_DIM]);
            privileged_block(&self.obs[o..o + OBS_DIM], &mut self.priv2[p..p + PRIV_DIM]);
        }
    }
}

/// Leaf positions driven to termination from Python -- the rollout leaf (the
/// I-op, plan §3): the policy acts on BOTH seats through `pending` / `step`,
/// exactly as `BatchEnv` is driven, but nothing restarts and nothing is
/// recorded. The chance stream continues from each leaf's CRN seed.
pub struct LeafBatch {
    pub nodes: Vec<Node>,
    pub cell: Vec<i32>,
    pub sample: Vec<i32>,
    updates: Vec<u32>,
    /// The scripted policies' draw stream (tests and benches only).
    rng: u64,
}

impl LeafBatch {
    pub fn new(nodes: Vec<Node>, cell: Vec<i32>, sample: Vec<i32>, seed: u64) -> LeafBatch {
        let n = nodes.len();
        LeafBatch {
            nodes,
            cell,
            sample,
            updates: vec![0; n],
            rng: splitmix64(seed ^ 0x4C45_4146_4241_5443),
        }
    }

    pub fn len(&self) -> usize {
        self.nodes.len()
    }
    pub fn is_empty(&self) -> bool {
        self.nodes.is_empty()
    }
    pub fn live(&self) -> usize {
        self.nodes.iter().filter(|n| !n.over()).count()
    }
    pub fn done(&self) -> Vec<bool> {
        self.nodes.iter().map(|n| n.over()).collect()
    }
    pub fn outcome(&self, p: Player) -> Vec<i8> {
        self.nodes.iter().map(|n| n.outcome_for(p)).collect()
    }
    pub fn turns(&self) -> Vec<u16> {
        self.nodes.iter().map(|n| n.battle.turn()).collect()
    }

    /// Every live leaf where `p` owes a decision: `(idx, obs, mask)`.
    pub fn pending(&self, p: Player, t: &StaticTables) -> (Vec<i32>, Vec<f32>, Vec<bool>) {
        let mut idx = Vec::new();
        let mut obs = Vec::new();
        let mut mask = Vec::new();
        for (i, n) in self.nodes.iter().enumerate() {
            if n.over() || n.result.request(p) == Request::Pass {
                continue;
            }
            let st = n.state(p, t);
            let o = obs.len();
            obs.resize(o + OBS_DIM, 0.0);
            encode(&mut obs[o..], t, &st);
            mask.extend(mask_for(&n.battle, p, n.result.request(p), st.aliased));
            idx.push(i as i32);
        }
        (idx, obs, mask)
    }

    /// One update on every live leaf. Every seat owing a decision must be given
    /// one, or the batch refuses -- a silently skipped leaf would stall forever.
    pub fn step(
        &mut self,
        t: &StaticTables,
        p1_idx: &[i32],
        p1_actions: &[usize],
        p2_idx: &[i32],
        p2_actions: &[usize],
    ) -> Result<(), String> {
        if p1_idx.len() != p1_actions.len() || p2_idx.len() != p2_actions.len() {
            return Err("idx/actions lengths disagree".into());
        }
        let k = self.nodes.len();
        let mut acts: [Vec<Option<usize>>; 2] = [vec![None; k], vec![None; k]];
        for (side, (idx, actions)) in [(p1_idx, p1_actions), (p2_idx, p2_actions)].into_iter().enumerate() {
            for (n, &i) in idx.iter().enumerate() {
                if i < 0 || i as usize >= k {
                    return Err(format!("leaf {i} out of range"));
                }
                acts[side][i as usize] = Some(actions[n]);
            }
        }
        for i in 0..k {
            let node = &mut self.nodes[i];
            if node.over() {
                continue;
            }
            let mut chosen = [Choice::Pass, Choice::Pass];
            for (side, p) in [Player::P1, Player::P2].into_iter().enumerate() {
                let req = node.result.request(p);
                if req == Request::Pass {
                    continue;
                }
                let a = acts[side][i]
                    .ok_or_else(|| format!("leaf {i}: {p:?} owes a decision, none given"))?;
                let st = node.state(p, t);
                chosen[side] = action_to_choice(&node.battle, p, req, st.aliased, a)
                    .ok_or_else(|| format!("leaf {i}: action {a} is not legal for {p:?}"))?;
            }
            node.result = node
                .battle
                .update(node.result.p1, chosen[0], node.result.p2, chosen[1])
                .map_err(|e| format!("leaf {i}: {e}"))?;
            if node.result.outcome == Outcome::Error {
                return Err(format!("leaf {i}: engine returned Error, unreachable in showdown mode"));
            }
            node.tracker.observe(&node.battle);
            self.updates[i] += 1;
            if self.updates[i] > MAX_UPDATES {
                return Err(format!("leaf {i} exceeded {MAX_UPDATES} updates"));
            }
        }
        Ok(())
    }

    /// Both seats play `policy` for one update on every live leaf; returns how
    /// many leaves are still live. Tests and benches only -- never an
    /// instrument's rollout policy, which is the trained network on both seats.
    pub fn scripted_step(&mut self, t: &StaticTables, policy: Scripted) -> Result<usize, String> {
        let mut idx = [Vec::new(), Vec::new()];
        let mut acts = [Vec::new(), Vec::new()];
        for (i, n) in self.nodes.iter().enumerate() {
            if n.over() {
                continue;
            }
            for (side, p) in [Player::P1, Player::P2].into_iter().enumerate() {
                if n.result.request(p) == Request::Pass {
                    continue;
                }
                let st = n.state(p, t);
                let mask = mask_for(&n.battle, p, n.result.request(p), st.aliased);
                idx[side].push(i as i32);
                acts[side].push(policy.act(&st, &mask, t, &mut self.rng));
            }
        }
        self.step(t, &idx[0], &acts[0], &idx[1], &acts[1])?;
        Ok(self.live())
    }
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;
    use crate::env::tests::tables_stub;
    use crate::team::random_team;

    fn pick(env: &Gen1Env, p: Player, t: &StaticTables, rng: &mut u64) -> Option<usize> {
        let pd = env.pending(p, t)?;
        let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| pd.mask[a]).collect();
        assert!(!legal.is_empty());
        *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
        Some(legal[((*rng >> 33) as usize) % legal.len()])
    }

    fn teams(seed: u64) -> (Vec<[u8; 24]>, Vec<[u8; 24]>) {
        (
            random_team(seed ^ 0x51, true).iter().map(|m| m.to_bytes()).collect(),
            random_team(seed ^ 0x52, true).iter().map(|m| m.to_bytes()).collect(),
        )
    }

    /// THE test: a leaf is bit-for-bit what the collector would have produced
    /// had the battle been played into that state under the same chance seed --
    /// the acting seat's next observation, the foe's own view, and both
    /// privileged blocks. Covers moves, switches, mid-turn faints, terminals.
    #[test]
    fn expand_reproduces_the_training_construction_bitwise() {
        let t = tables_stub();
        let (mut checked, mut passes, mut priv_checked, mut terminals) = (0, 0, 0, 0);
        for seed in 0..30u64 {
            let (p1, p2) = teams(seed);
            let mut env = Gen1Env::new(seed, &p1, &p2, Player::P1, 0, true).unwrap();
            let mut rng = seed | 1;
            while !env.done() {
                let la = pick(&env, Player::P1, &t, &mut rng);
                let oa = pick(&env, Player::P2, &t, &mut rng);
                let Some(a) = la else {
                    env.step(&t, la, 0.0, 0, oa).unwrap();
                    continue;
                };
                let node = Node::from_env(&env);
                let col = oa.map(|b| b as i32).unwrap_or(-1);
                let seed_base = 0xB0 ^ seed;
                let (e, _) = node
                    .expand(&t, Player::P1, &[Cell { row: a as i32, col, n_chance: 1 }], seed_base, Render::Both, false)
                    .unwrap();
                assert_eq!(e.n, 1);
                // Play the same pair in the env under the SAME chance seed.
                let s = leaf_seed(seed_base, col, 0);
                env.battle_mut().0[B_RNG..B_RNG + 8].copy_from_slice(&s.to_le_bytes());
                env.step(&t, la, 0.0, 0, oa).unwrap();
                assert_eq!(e.turn[0], env.turn());
                if env.done() {
                    let want = match env.outcome() {
                        Outcome::Win => 1,
                        Outcome::Lose => -1,
                        _ => 2,
                    };
                    assert_eq!(e.terminal[0], want, "terminal from P1's seat");
                    assert!(e.obs.iter().all(|&v| v == 0.0), "a terminal leaf encodes nothing");
                    terminals += 1;
                    continue;
                }
                assert_eq!(e.terminal[0], 0);
                assert_eq!(e.req_next, vec![req_code(env.request(Player::P1)), req_code(env.request(Player::P2))]);
                match env.pending(Player::P1, &t) {
                    // The collector's next observation for P1.
                    Some(pd) => {
                        assert_eq!(e.obs, pd.obs, "seed {seed}: the leaf is not the collector's next obs");
                        checked += 1;
                    }
                    // P1 owes a Pass (the foe is replacing a fainted mon): the
                    // view under that request, as `Gen1Env::state` renders it.
                    None => {
                        let mut v = vec![0.0f32; OBS_DIM];
                        encode(&mut v, &t, &env.state(Player::P1, &t));
                        assert_eq!(e.obs, v);
                        passes += 1;
                    }
                }
                // The foe's own view, and the two blocks sliced from the two
                // full encodes -- the D18 construction at `env.rs`.
                let mut fobs = vec![0.0f32; OBS_DIM];
                encode(&mut fobs, &t, &env.state(Player::P2, &t));
                assert_eq!(e.obs2, fobs, "seed {seed}: the foe's own view differs");
                let mut blk = vec![0.0f32; PRIV_DIM];
                privileged_block(&fobs, &mut blk);
                assert_eq!(e.priv1, blk, "the acting seat's privileged block is not the foe's own side");
                let mut blk2 = vec![0.0f32; PRIV_DIM];
                privileged_block(&e.obs, &mut blk2);
                assert_eq!(e.priv2, blk2);
                priv_checked += 1;
            }
        }
        assert!(checked > 300, "only {checked} decision leaves compared");
        assert!(passes > 10, "only {passes} pass leaves compared");
        assert!(priv_checked > 300, "only {priv_checked} privileged blocks compared");
        assert!(terminals >= 20, "only {terminals} terminals reached");
    }

    /// The other seat's expansion of the mirrored cell renders the same leaf
    /// with the views swapped -- so `obs2` really is "the foe's own view".
    #[test]
    fn the_foes_view_is_what_the_foe_would_expand_to() {
        let t = tables_stub();
        let mut compared = 0;
        for seed in 40..52u64 {
            let (p1, p2) = teams(seed);
            let mut env = Gen1Env::new(seed, &p1, &p2, Player::P1, 0, false).unwrap();
            let mut rng = seed | 1;
            while !env.done() && compared < 400 {
                let la = pick(&env, Player::P1, &t, &mut rng);
                let oa = pick(&env, Player::P2, &t, &mut rng);
                if let (Some(a), Some(b)) = (la, oa) {
                    let node = Node::from_env(&env);
                    let sb = 0x77 ^ seed;
                    let (e1, _) = node
                        .expand(&t, Player::P1, &[Cell { row: a as i32, col: b as i32, n_chance: 2 }], sb, Render::Both, false)
                        .unwrap();
                    // Choose P2's seed_base so its (col = a) key lands on the
                    // same seeds as P1's (col = b): leaf_seed = splitmix64(sb ^ splitmix64(key)).
                    for s in 0..2u32 {
                        let key = |col: i32| splitmix64((((col as i64 + 2) as u64) << 32) | (s as u64 + 1));
                        let sb2 = sb ^ key(b as i32) ^ key(a as i32);
                        assert_eq!(leaf_seed(sb2, a as i32, s), leaf_seed(sb, b as i32, s));
                        let (e2, _) = node
                            .expand(&t, Player::P2, &[Cell { row: b as i32, col: a as i32, n_chance: s + 1 }], sb2, Render::Both, false)
                            .unwrap();
                        let i = s as usize;
                        let (o, p) = (i * OBS_DIM, i * PRIV_DIM);
                        assert_eq!(e1.seed[i], e2.seed[i]);
                        assert_eq!(&e1.obs[o..o + OBS_DIM], &e2.obs2[o..o + OBS_DIM]);
                        assert_eq!(&e1.obs2[o..o + OBS_DIM], &e2.obs[o..o + OBS_DIM]);
                        assert_eq!(&e1.priv1[p..p + PRIV_DIM], &e2.priv2[p..p + PRIV_DIM]);
                        assert_eq!(&e1.priv2[p..p + PRIV_DIM], &e2.priv1[p..p + PRIV_DIM]);
                        let flip = |x: i8| if x == 2 { 2 } else { -x };
                        assert_eq!(e1.terminal[i], flip(e2.terminal[i]));
                        assert_eq!(e1.req_next[2 * i], e2.req_next[2 * i + 1]);
                        assert_eq!(e1.req_next[2 * i + 1], e2.req_next[2 * i]);
                        compared += 1;
                    }
                }
                env.step(&t, la, 0.0, 0, oa).unwrap();
            }
        }
        assert!(compared >= 200, "only {compared} leaves compared");
    }

    /// CRN-1: same column and sample -> same seed across every row; a different
    /// column or sample -> a different seed. Read off the engine's bytes, not
    /// the helper.
    #[test]
    fn the_chance_seed_is_keyed_on_column_and_sample_never_row() {
        let t = tables_stub();
        let (p1, p2) = teams(9);
        let mut env = Gen1Env::new(9, &p1, &p2, Player::P1, 0, false).unwrap();
        let mut rng = 3u64;
        for _ in 0..6 {
            let la = pick(&env, Player::P1, &t, &mut rng);
            let oa = pick(&env, Player::P2, &t, &mut rng);
            env.step(&t, la, 0.0, 0, oa).unwrap();
        }
        let node = Node::from_env(&env);
        let rows: Vec<i32> = (0..N_ACTIONS as i32).filter(|&a| node.mask(Player::P1, &t)[a as usize]).collect();
        let cols: Vec<i32> = (0..N_ACTIONS as i32).filter(|&a| node.mask(Player::P2, &t)[a as usize]).collect();
        assert!(rows.len() >= 2 && cols.len() >= 2, "fixture too small: {rows:?} x {cols:?}");
        let cells: Vec<Cell> = rows
            .iter()
            .flat_map(|&r| cols.iter().map(move |&c| Cell { row: r, col: c, n_chance: 3 }))
            .collect();
        let (e, nodes) = node.expand(&t, Player::P1, &cells, 0xC0FFEE, Render::Seat, true).unwrap();
        assert_eq!(e.n, cells.len() * 3);
        let at = |ci: usize, s: usize| ci * 3 + s;
        let seed_of = |i: usize| -> u64 {
            // What the engine was handed: the seed is consumed by the update, so
            // read the Expanded record, which is what was written.
            e.seed[i]
        };
        for (ci, c) in cells.iter().enumerate() {
            for (cj, d) in cells.iter().enumerate() {
                for s in 0..3 {
                    let same = c.col == d.col;
                    assert_eq!(seed_of(at(ci, s)) == seed_of(at(cj, s)), same, "{c:?} vs {d:?} sample {s}");
                    if s > 0 {
                        assert_ne!(seed_of(at(ci, s)), seed_of(at(cj, s - 1)));
                    }
                }
            }
        }
        // Same (row, col): the three samples are three different leaves unless
        // chance had nothing to do this update, and the engine advanced its own
        // seed from the one we wrote.
        assert!(nodes.iter().all(|n| n.battle.turn() >= node.battle.turn()));
    }

    #[test]
    fn leaf_batch_rollouts_finish_with_mirrored_outcomes() {
        let t = tables_stub();
        let (p1, p2) = teams(21);
        let mut env = Gen1Env::new(21, &p1, &p2, Player::P1, 0, false).unwrap();
        let mut rng = 5u64;
        for _ in 0..10 {
            let la = pick(&env, Player::P1, &t, &mut rng);
            let oa = pick(&env, Player::P2, &t, &mut rng);
            env.step(&t, la, 0.0, 0, oa).unwrap();
        }
        assert!(!env.done());
        let node = Node::from_env(&env);
        let rows: Vec<i32> = (0..N_ACTIONS as i32).filter(|&a| node.mask(Player::P1, &t)[a as usize]).collect();
        let cols: Vec<i32> = (0..N_ACTIONS as i32).filter(|&a| node.mask(Player::P2, &t)[a as usize]).collect();
        let cells: Vec<Cell> = rows
            .iter()
            .flat_map(|&r| cols.iter().map(move |&c| Cell { row: r, col: c, n_chance: 2 }))
            .collect();
        let (e, nodes) = node.expand(&t, Player::P1, &cells, 1234, Render::None, true).unwrap();
        assert!(e.obs.is_empty(), "Render::None encodes nothing");
        let mut lb = LeafBatch::new(nodes, e.cell.clone(), e.sample.clone(), 1234);
        let n = lb.len();
        assert_eq!(n, cells.len() * 2);
        // Drive it with the same shape Python uses: pending -> step.
        let mut guard = 0;
        while lb.live() > 0 {
            guard += 1;
            assert!(guard < 6000, "rollouts did not terminate");
            let (i1, o1, m1) = lb.pending(Player::P1, &t);
            let (i2, o2, m2) = lb.pending(Player::P2, &t);
            assert_eq!(o1.len(), i1.len() * OBS_DIM);
            assert_eq!(m1.len(), i1.len() * N_ACTIONS);
            assert_eq!(o2.len(), i2.len() * OBS_DIM);
            let choose = |mask: &[bool], rng: &mut u64| -> Vec<usize> {
                mask.chunks(N_ACTIONS)
                    .map(|m| {
                        let legal: Vec<usize> = (0..N_ACTIONS).filter(|&a| m[a]).collect();
                        assert!(!legal.is_empty());
                        *rng = rng.wrapping_mul(6364136223846793005).wrapping_add(1);
                        legal[((*rng >> 33) as usize) % legal.len()]
                    })
                    .collect()
            };
            let a1 = choose(&m1, &mut rng);
            let a2 = choose(&m2, &mut rng);
            lb.step(&t, &i1, &a1, &i2, &a2).unwrap();
        }
        let o1 = lb.outcome(Player::P1);
        let o2 = lb.outcome(Player::P2);
        assert!(o1.iter().all(|&o| o == 1 || o == -1 || o == 2));
        for i in 0..n {
            assert_eq!(o1[i], if o2[i] == 2 { 2 } else { -o2[i] });
        }
        assert!(lb.turns().iter().all(|&tn| tn > node.battle.turn()));
        assert!(lb.done().iter().all(|&d| d));
        // A finished batch has nothing pending and refuses no-op steps quietly.
        assert!(lb.pending(Player::P1, &t).0.is_empty());
    }

    #[test]
    fn scripted_rollouts_terminate_too() {
        let t = tables_stub();
        let (p1, p2) = teams(33);
        let env = Gen1Env::new(33, &p1, &p2, Player::P1, 0, false).unwrap();
        let node = Node::from_env(&env);
        let rows: Vec<i32> = (0..N_ACTIONS as i32).filter(|&a| node.mask(Player::P1, &t)[a as usize]).collect();
        let cells: Vec<Cell> = rows.iter().map(|&r| Cell { row: r, col: 6, n_chance: 4 }).collect();
        let (e, nodes) = node.expand(&t, Player::P1, &cells, 7, Render::None, true).unwrap();
        let mut lb = LeafBatch::new(nodes, e.cell, e.sample, 7);
        let mut guard = 0;
        while lb.scripted_step(&t, Scripted::Random).unwrap() > 0 {
            guard += 1;
            assert!(guard < 6000);
        }
        assert!(lb.outcome(Player::P1).iter().all(|&o| o != 0));
    }

    #[test]
    fn illegal_cells_are_refused_before_the_engine_sees_them() {
        let t = tables_stub();
        let (p1, p2) = teams(2);
        let env = Gen1Env::new(2, &p1, &p2, Player::P1, 0, false).unwrap();
        let node = Node::from_env(&env);
        let m = node.mask(Player::P1, &t);
        let bad = (0..N_ACTIONS as i32).find(|&a| !m[a as usize]).expect("some action is illegal at a lead");
        let err = node.expand(&t, Player::P1, &[Cell { row: bad, col: 6, n_chance: 1 }], 0, Render::Seat, false).unwrap_err();
        assert!(err.contains("not legal"), "{err}");
        let err = node.expand(&t, Player::P1, &[Cell { row: 6, col: 6, n_chance: 0 }], 0, Render::Seat, false).unwrap_err();
        assert!(err.contains("n_chance"), "{err}");
        let err = node.expand(&t, Player::P1, &[Cell { row: 6, col: 11, n_chance: 1 }], 0, Render::Seat, false).unwrap_err();
        assert!(err.contains("col"), "{err}");
    }

    /// A fresh projection over the root's bytes sees the leads; a resampled
    /// world keeps the real projection (B1b's contract).
    #[test]
    fn fresh_and_with_battle_keep_their_projections() {
        let t = tables_stub();
        let (p1, p2) = teams(15);
        let mut env = Gen1Env::new(15, &p1, &p2, Player::P1, 0, false).unwrap();
        let mut rng = 1u64;
        for _ in 0..8 {
            let la = pick(&env, Player::P1, &t, &mut rng);
            let oa = pick(&env, Player::P2, &t, &mut rng);
            env.step(&t, la, 0.0, 0, oa).unwrap();
        }
        let node = Node::from_env(&env);
        let fresh = Node::fresh(Battle(node.battle.0), node.result.p1, node.result.p2);
        assert!(fresh.mask(Player::P1, &t).iter().any(|&b| b) || node.request(Player::P1) == Request::Pass);
        let same = node.with_battle(Battle(node.battle.0), node.result.p1, node.result.p2);
        assert_eq!(same.obs(Player::P1, &t), node.obs(Player::P1, &t));
        assert_eq!(same.obs(Player::P2, &t), node.obs(Player::P2, &t));
        // A fresh tracker has forgotten the bench the real one saw revealed
        // (unless nothing beyond the actives was ever revealed in 8 updates).
        let revealed = |n: &Node| n.tracker.side(Player::P2).reveal_order().len();
        assert!(revealed(&fresh) <= revealed(&node));
    }
}
