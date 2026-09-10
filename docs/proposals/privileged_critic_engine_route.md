# Privileged critic on the engine route — scoping proposal

**Status:** PROPOSAL. Not a pre-reg, not a ruling. Nothing here has run.
**Serves:** JOURNEY step 10 (the 100M monster) — specifically its likely second
arm, "the R4 recipe + a better critic", and the search relook's evaluator lever
(STATUS.md:33-40, "the monster train MUST … pick its EVALUATOR lever before
launch (seed ensemble / privileged critic / outcome-trained evaluator)").
**Off-arc?** No. It is downstream of JOURNEY 7.5 exactly as
`docs/IDEAS_POST_100M.md:764-765` places 4.7 ("step 10 territory, or step 8's
back-port; NOT gen 4").
**Written 2026-09-10, read-only session; a search-eval fleet and two other
agents were live and nothing was run.**

---

## 0. Why this is worth a block at all

Three facts settle the framing before the plumbing.

1. **The R4 recipe has never been able to run this lever.** `configs/
   showdown_sp_100m.yaml` sets `collector.mode: async`, and `rl/train.py:755-758`
   refuses `privileged_dim` on the async path outright. D18 ran on the SYNC
   vector path at `rollout_steps: 128, minibatches: 4`
   (`configs/showdown_sp_priv12m.yaml`, agent block). So "R4 recipe + privileged
   critic" is not a thing that exists on any current route — **the engine route
   is the only place it can be built.** That, not speed, is the reason this
   belongs to 7.5's exit rather than to a later chapter.

2. **The emitter is already built and tested; only the seam is missing.**
   `engine/pkmn_gen1/src/encoder.rs:54-85` defines `PRIV_DIM = 408` and
   `privileged_block()` as the same SLICE the Python takes; `env.rs:295-302`
   fills one block per learner row from a full encode of the foe's seat, read
   BEFORE the update; `pyencode.rs:342-361` exposes the `privileged` flag and
   `pyencode.rs:533-535` puts the block in the episode dict. Rust tests
   `the_privileged_block_is_the_foes_own_side_at_the_acting_state`
   (`env.rs:789-828`) and `the_privileged_block_is_empty_unless_asked_for`
   (`env.rs:830-848`) pin both halves. `docs/engine_port/NOTES.md:1468-1504` is
   the account and says in terms: "**Deliberately NOT built: the seam into PPO,
   and the lifted refusal.**"

3. **D18's own falsifier is the reason a leaf evaluator is the right consumer.**
   SESSION_LOGS.md:2647-2654: "**FALSIFIER FIRED (the epitaph): EV rose on EVERY
   lane** — per-2M means climb ~0.50 → 0.60-0.62 … while win rate stayed flat".
   A critic that *values states better* but *degrades the advantage signal* is
   the wrong object for a policy gradient and exactly the right object for a
   leaf evaluator. That asymmetry is not currently exploited anywhere and is the
   substantive design question in §4.3.

The kill was vacated 2026-09-06 (SESSION_LOGS.md:11003-11005, "**a small-run
null does not close an axis** … VACATED AS FINAL … returns as **IDEAS 4.7**");
`docs/IDEAS_POST_100M.md:740-768` carries the live hypothesis ("a both-seat
critic as a VARIANCE REDUCER at large batch and long horizon") and the standing
requirement that any run gets its own pre-reg.

---

## 1. THE SEAM, exactly

### 1.1 What PRIV_DIM is and where it is defined

| side | symbol | file:line | value |
|---|---|---|---|
| Python | `PRIV_DIM` | `rl/envs/showdown.py:470-472` | `(_PRIV_OWN_END - GLOBAL_DIM) + PRIV_ID_DIM` = **408** under `POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1` |
| Rust | `PRIV_DIM` | `engine/pkmn_gen1/src/encoder.rs:63-65` | `(PRIV_OWN_END - GLOBAL_DIM) + PRIV_ID_DIM` = **408**, `const _: () = assert!(PRIV_DIM == 408)` at `encoder.rs:74-75` (compile-time) |
| Python-visible Rust | `pkmn_gen1.PRIV_DIM` | `engine/pkmn_gen1/src/python.rs:392` | exported |
| network | `lay.priv_dim` | `rl/networks/entity_deepsets.py:358-365` | 408 at the gen-1 layout; a mismatch raises naming `PRIV_DIM` |

`privileged_dim` for this work is therefore **408**, the same value D18 used
(`configs/showdown_sp_priv12m.yaml`, `privileged_dim: 408   # THE LEVER, agent
side: critic = obs ‖ priv`).

### 1.2 Layout parity between the Node encoder and the Rust emitter — ALREADY PINNED

They do not differ. Both are the same slice of the OPPONENT seat's own 828-vector:

* Python `rl/envs/showdown.py:475-483`: `own = vec[GLOBAL_DIM:_PRIV_OWN_END]`,
  then `concatenate([own, vec[o:o+6], vec[o+12:o+16]])` with `o = OBS_DIM - ID_DIM`.
* Rust `engine/pkmn_gen1/src/encoder.rs:77-85`: `out[..own].copy_from_slice(
  &vec[GLOBAL_DIM..PRIV_OWN_END])`, then `vec[o..o+6]` and `vec[o+12..o+16]`.

Element for element identical, including the id sub-slices.

**The parity gate already exists.** `tests/test_seat_tag.py:143-160`
(`test_the_two_encoders_agree_on_the_privileged_block_width`) runs a subprocess
asserting `pkmn_gen1.PRIV_DIM == PRIV_DIM == 408` and
`pkmn_gen1.OBS_DIM == OBS_DIM == 828`. That is a **width** gate, not a **value**
gate. See §1.6 for the value gate this proposal adds.

### 1.3 The Node path's contract, which the engine path must mirror

| stage | file:line | key / name | shape |
|---|---|---|---|
| emit (reset) | `rl/train.py:1246` | `infos["privileged"]` | `(N, PRIV_DIM)` |
| emit (step) | `rl/train.py:1291` | `infos["privileged"]` → `next_privs` | `(N, PRIV_DIM)` |
| env emitter | `rl/envs/showdown.py:1427-1439` (`_emit_privileged`), called at `:1463` and `:1521` | `info["privileged"] = privileged_block(embed_battle(battle2, chart))` | `(PRIV_DIM,)` float32 |
| carry-forward | `rl/train.py:1367`, `:1394-1398` | `privs = next_privs`; done rows take `reset_infos["privileged"]` | — |
| into PPO | `rl/train.py:1298-1301` | 11-tuple `(..., privs, next_privs, opp_choice)` | — |
| loud seam | `rl/agents/ppo.py:981-987` | raises `privileged mismatch` if agent flag and env emission disagree | — |
| storage | `rl/buffers/rollout.py:67-75`, `:103-105` | `buf.privs`, `buf.next_privs`, allocated iff `priv_dim` | `(T, N, PRIV_DIM)` |
| critic input | `rl/agents/ppo.py:1030-1042` | `flat_critic_obs = cat([flat_obs, privs])`, `flat_critic_next_obs = cat([flat_next_obs, next_privs])` | `(T*N, 828+408)` |
| consumption | `rl/agents/ppo.py:1052-1053`, `:1335` | `self.critic(flat_critic_obs)` | — |
| split inside the net | `rl/networks/entity_deepsets.py:505-508` | `x, priv = x[:, :-priv_dim], x[:, -priv_dim:]` | — |

### 1.4 The engine route's seam — every site, in order

The engine route is `EngineCollector.poll()` → `_async_loop` → `EpisodeDataset`
→ `PPOAgent.update_episodes()` → `_optimize`. `rl/train.py:900` sets
`agent.buffer = None` on this route, so **`rl/buffers/rollout.py` is not on the
path at all** and needs no change.

**(a) Flag through to the Rust emitter — `rl/envs/engine_collector.py`.**
* `EngineCollector.__init__` signature, `engine_collector.py:103-115`: add
  `privileged: bool = False`; store as `self._privileged`, beside
  `self._opp_action = bool(opp_action)` at `:131`.
* `engine_collector.py:162-164`: `pkmn_gen1.BatchEnv(k, int(seed), tables,
  payload, learner_seat, int(battle_counter))` → add
  `privileged=self._privileged`. The kwarg already exists
  (`pyencode.rs:342-350`, `privileged=false` default) and is already threaded to
  `RustBatchEnv::new` at `pyencode.rs:358`.

**(b) Episode dict key — `rl/envs/engine_collector.py:369-386` (`_episode`).**
Mirror the `opp_action` block at `:384-385`:
```
if self._privileged:
    episode["privileged"] = np.asarray(raw["privileged"], dtype=np.float32)
```
`raw["privileged"]` is `(n, 408)` float32, present iff non-empty
(`pyencode.rs:533-535`), rows in learner-row order (`env.rs:299-301` appends one
block per recorded learner row, in the same loop as `ep.obs`).
**Key name is `"privileged"` — identical to the Node path's `infos` key.**

**(c) Buffer/rollout storage — `rl/buffers/episode.py`.**
* `EPISODE_KEYS` (`:35-42`) stays untouched — the block is optional.
* `OPT_KEY = "opp_choice"` (`:46`) becomes a tuple, e.g.
  `OPT_KEYS = ("opp_choice", "privileged")`, with the SAME all-or-none rule.
* `append()` (`:74-78`) — the present-on-every-episode-or-none assertion runs per
  optional key.
* `drain()` (`:89-90`) — concatenate each present optional key.
Shapes: `opp_choice` is `(n, 3)`, `privileged` is `(n, 408)`; `len()` is `n` in
both cases, so the existing length logic is unchanged.

**(d) `next_privs` at episode ends — NOT NEEDED ON THIS ROUTE, and this is the
one real divergence from the Node contract.**
`update_episodes` computes ONE critic pass and shifts V within an episode:
`rl/agents/ppo.py:1136-1138` ("ONE critic pass: within an episode V(s') is V(s)
shifted"), implemented by `_episode_boundaries` at `rl/buffers/episode.py:97-112`
— `next_values[:-1] = values[1:]` with `next_values[ends] = 0.0`. So:
* V(s_{t+1}) is the value **already computed at row t+1**, whose privileged block
  is row t+1's block — i.e. exactly the successor state's privileged view, which
  is what `next_privs` supplies on the Node path.
* The terminal bootstraps to **0** (`episode.py:107-111`), so **the final state's
  privileged view is never read**. It does not need to be emitted, stored, or
  carried.
This is not a shortcut: it is the same reason `next_obs` does not exist on this
route (`rl/buffers/episode.py:16-18`). It should be stated explicitly in the
pre-reg, because "the Node path carries next_privs and the engine path does not"
reads like a defect otherwise.

**(e) The critic's input — `rl/agents/ppo.py:1123-1190` (`update_episodes`).**
Replace the blanket refusal at `:1145-1150` with the Node path's loud seam
(`:981-987`'s exact shape):
```
privs = batch.get("privileged")
if (privs is None) == bool(self.privileged_dim):
    raise ValueError("privileged mismatch: agent privileged_dim=… but the "
                     "collector {did not emit|emitted} 'privileged' …")
```
then, mirroring `:1030-1044`:
```
flat_critic_obs = flat_obs if not self.privileged_dim else torch.cat(
    [flat_obs, torch.as_tensor(privs, dtype=torch.float32, device=self.device)], dim=-1)
```
and two one-word changes:
* `:1173` `values = self.critic(flat_obs)` → `self.critic(flat_critic_obs)`
* `:1184` `self._optimize(flat_obs, flat_actions, flat_masks, flat_obs, …)` →
  `…, flat_critic_obs, …` (the 4th positional IS `flat_critic_obs`,
  `ppo.py:1192-1206`).
`_optimize` needs **no change**: it already indexes `flat_critic_obs[idx]`
uniformly at `:1335` and never assumes it equals `flat_obs`.

**(f) The launch gate — `rl/train.py:815-834`.**
* `:821-834` refusal is replaced. Recommended (see §5.1): **derive** the
  collector flag from the agent hparam at `rl/train.py:917-926`:
  `privileged=bool(cfg.agent.get("privileged_dim"))`, adding no config key. The
  engine route has one emitter and one consumer in one process, so the two-knob
  pairing that `env_kwargs.privileged` + `agent.privileged_dim` exists for on the
  Node path has no failure mode to prevent here; the runtime seam in (e) is the
  loud check.
* `:815-820` (`env_kwargs.keys() - {"opp_action", "seat_tag"}`) is unchanged —
  no new env kwarg.
* `:835-838` (`harvest_both_seats`) stays refused. It is independently refused in
  `PPOAgent.attach_harvest` at `ppo.py:688-689`.
* `ENGINE_KEYS` at `rl/train.py:687` is unchanged. **This matters:**
  `tests/test_engine_a1_prereg.py:59-67` documents that a committed draft once
  carried `collector.privileged`, which `ENGINE_KEYS` rejects and which meant the
  config could not load at all.

**(g) Nothing else.** `rl/train.py:1246-1398` (the Node path) is untouched.
`rl/envs/showdown.py` is untouched. `rl/buffers/rollout.py` is untouched.

### 1.5 Semantics check — is the engine block the same *quantity* as the Node block?

Yes, at the acting state, and the Rust test says so by name.

* Node: `_emit_privileged` (`rl/envs/showdown.py:1427-1439`) is "called at exactly"
  the reset and step info points (`:1463`, `:1521`), off `battle2` — the true
  seat-2 battle object.
* Engine: `env.rs:295-302` runs inside `step()` **before** `battle.update()`, in
  the `lreq != Request::Pass` branch, so it is emitted once per LEARNER ROW and
  describes the state the learner's action was chosen in. The comment at
  `env.rs:284-288` states this; the test at `env.rs:789-828` rebuilds the expected
  block independently and asserts it, "so slicing our own vector, or reading the
  foe after the update, fails it" (`NOTES.md:1480-1482`).

### 1.6 The value-parity gate this proposal adds (the one that does not exist)

`tests/test_seat_tag.py:147` pins the WIDTH. Nothing pins the VALUES. Proposed:

**`test_engine_privileged_block_is_the_python_block`** — the P-1 pattern
(`scripts/engine_p1.py` compares the two encoders given identical observable
state). Concretely, in a subprocess with both encoder env vars:
1. run one engine battle with `BatchEnv(..., privileged=True)`;
2. for a sampled learner row, take the engine's `episode["privileged"][i]`;
3. independently take the engine's own foe-seat 828 vector for that state (the
   `pending("opponent")` obs at the same step is exactly it when the foe owes a
   decision) and apply the **Python** `rl.envs.showdown.privileged_block`;
4. assert bitwise equality.
This is a value gate between the Rust slice and the Python slice on the same
input vector, which is the drift `NOTES.md:1484-1489` names as "actually coming"
(JOURNEY step 8's encoder rewrite is the next step after 7.5).

---

## 2. THE GUARD at `rl/agents/ppo.py:476-481`

### 2.1 What it says

```python
if privileged_dim:
    raise TypeError(
        "aux_oppact_coef with privileged_dim: R0-1's fingerprint requires "
        "D18's plumbing ABSENT — D25 needs neither the privileged block "
        "nor its ~65 us/step seat-B re-encode"
    )
```

### 2.2 What it actually protects — read against the record

**R0-1 is an arm-scoped launch gate for the D25 12M rung, not an invariant.**
`configs/showdown_sp_actpred12m.yaml:1138-1143` verbatim:

> R0-1 FINGERPRINT: every lane's meta.yaml stamps encoder v2, recharge_fix, ids,
> obs_dim 828; PLUS **this rung's seam** — the config snapshot carries
> `agent.aux_oppact_coef > 0` AND `agent.aux_label_space == "l6"` AND
> **`agent.privileged_dim` ABSENT** AND **`env_kwargs.privileged` ABSENT**
> (D18's plumbing must not ride along; D25 needs neither). ACTION ON FAIL: the
> lane does not launch.

Its stated purpose (same file, B1 at `:234-236`) is that "D18's 408-float
privileged block is NOT used and D18's measured ~65 us/step seat-B re-encode is
NOT incurred" — a **purity and cost** clause for a one-lever rung, phrased as a
per-lane launch check. It was then hard-wired into the library as a permanent
constructor `TypeError`.

**The `~65 us/step` figure is unsourced.** Its only homes in the repo are that
same pre-reg header, twice (`configs/showdown_sp_priv12m.yaml:161-163` and
`:223-225`), where it is attributed to the seat-B re-encode duplicating work
poke-env already does. No session-log entry or artifact records how it was
measured. Treat it as an estimate, not a measurement — and note that it is a
**Node-path** quantity regardless (§3).

**The D25 mechanism claim it is entangled with — `R0-3b` — is real, and it is
about RNG, not about the aux head's inputs.** `configs/showdown_sp_actpred12m
.yaml:340-348` lists what stays bit-identical, ending:

> (iii) actor and critic INITIAL weights at a fixed seed, bit-identical to the
> aux-off control, because head construction comes last in the global RNG stream
> (R0-3b) — **D18 could not have this**.

This is true and is measurable today. `EntityDeepSetsNet.init_head`
(`rl/networks/entity_deepsets.py:395-411`) is **the net's whole init**, not just
its head, and `rl/agents/ppo.py:530-537` calls `self.actor.init_head(0.01)`
AFTER the critic has been constructed at `:514-529`. Turning on `privileged_dim`
widens the critic's `ctx_net[0]` (`entity_deepsets.py:369`, 5 → 8 entity slots),
which moves the global RNG stream, which moves the ACTOR's re-init. The pin
records it: `tests/test_entity_trunk_gen4.py:194-199`, actor param sum
**334.851** at `privileged_dim=0` vs **410.510** at `408`, with identical actor
param count 626,059.

### 2.3 Is any of it load-bearing on the engine route?

**No, for the correctness question; yes, as a disclosure.**

* **The aux head's INPUTS are structurally unreachable by `privileged_dim`.** The
  aux head reads the **actor's** features: `ppo.py:851`
  `self.actor(obs, return_features=True)`, `ppo.py:926-928`
  `canonicalise(flat_obs, flat_opp_choice, self.actor.tokenizer)`, and
  `_aux_gradient` at `ppo.py:888` takes grads over
  `(*self.actor_params, *self.aux_params)` only. The privileged block reaches the
  **critic** only: `ppo.py:1030-1042` builds `flat_critic_obs`, and the critic's
  `_priv_features` (`entity_deepsets.py:421-456`) uses the **critic's own**
  `mon_net` / `move_net` / `species_emb` / `move_emb`. Actor and critic share no
  trunk (`ppo.py:486-487`, "Separate actor and critic, no shared trunk"). **The
  two levers touch disjoint parameter sets and disjoint tensors.**
* **The engine route has no seat-B re-encode in poke-env at all** — the cost
  clause is about `rl/envs/showdown.py`'s second `embed_battle` call, which does
  not exist here (§3).
* **R0-1 belongs to a rung that finished.** D25 r2 ratified and its lanes are
  banked; the fingerprint gate is a launch check for those lanes. No live
  pre-reg asserts it. `tests/test_engine_a1_prereg.py:66-67` asserts
  `"privileged_dim" not in RAW["agent"]` for **A-1's** config, and its stated
  reason is "rl/train.py refuses D18 on the engine path" — i.e. it is asserting
  the current refusal, not an independent purity requirement. It is A-1-scoped
  and A-1 is not this arm.

### 2.4 Proposed minimal lift

**Delete the `if privileged_dim: raise TypeError(...)` block at
`rl/agents/ppo.py:476-481`** and replace it with a comment recording (i) what
R0-1 was, (ii) that it was arm-scoped, and (iii) the residue that is NOT fixed:
**a privileged critic changes the actor's initial weights at a fixed seed**
(§2.2), so `aux_oppact_coef` is no longer an exact no-op in the R0-3b sense when
`privileged_dim` is also set.

A `collector.mode == engine` conditional is worse and should be rejected: the
agent does not know its collector, the property being asserted is not about the
collector, and it would leave a second dead branch behind for whoever reads this
next.

**The residue could be removed but should not be.** Constructing the critic
after `self.actor.init_head(0.01)` would restore actor bit-identity, but it
changes the RNG stream for **`privileged_dim=0` too**, breaking the
`_GEN1_PIN` golden at `tests/test_entity_trunk_gen4.py:194-199` and every
existing recipe's init. Disclose, do not reorder.

### 2.5 The tests that pin the lift

1. **`test_aux_head_inputs_are_unchanged_by_privileged_dim`** (the direct
   answer to the guard's claim). Build two agents at the same torch seed,
   `aux_oppact_coef=0.1, trunk="entity_deepsets"`, one with `privileged_dim=0`
   and one with `408`. Load the SAME actor `state_dict` into both. Assert
   `torch.equal` on every tensor returned by
   `agent.actor(obs, return_features=True)` and on `agent.aux_head(*feats)`.
   Passing means the aux head's inputs and output are bit-identical across the
   lever — which is the property the `TypeError` asserted by refusal.
2. **`test_privileged_dim_moves_the_actor_init_and_this_is_disclosed`** — pin the
   residue rather than hide it: same seed, `privileged_dim` 0 vs 408, assert the
   actor param sums DIFFER and the actor param COUNT does not (626,059 both,
   the `_GEN1_PIN` numbers). A test that asserts a known asymmetry is how it
   stops being a surprise.
3. **Extend `_GEN1_PIN`** (`tests/test_entity_trunk_gen4.py:185-220`) with a
   third case: `privileged_dim=408, aux_oppact_coef=0.1`, capturing actor/critic
   param counts and the two forwards. It already covers `{0, 408}` without the
   aux head; the combined build is the new object.
4. **`test_update_episodes_privileged_seam_is_loud_both_ways`** — the
   `tests/test_privileged_critic.py:77-81` pattern, moved to the episode batch:
   agent with `privileged_dim` and a batch without the key raises, and vice
   versa.
5. **`test_engine_prereg_guard_still_refuses_a_half_set_pair`** — keep whatever
   `tests/test_engine_a1_prereg.py:59-67` is guarding for A-1's own config
   (A-1 does not get this lever), separate from the new capability.

---

## 3. THE COST on the engine route

### 3.1 Is the privileged block already produced in the same pass?

**No.** `env.rs:295-302` runs a **third** full projection + encode:
```rust
let fst = self.state(foe, t);
let mut fobs = vec![0.0f32; OBS_DIM];
encode(&mut fobs, t, &fst);
```
`NOTES.md:1497-1504` states it plainly and marks the plan's waiver as expired:

> **A plan claim that expires here.** Plan §12 waves through the block's cost —
> a SECOND full 828 encode per learner row, half of it discarded — on the grounds
> that "the collection loop is I/O-dominated". That is true of the server path
> and false of this one … T-1 should price it before an arm relies on it.

There is a **partial reuse** available and not taken: `poll()` already calls
`self.env.pending("opponent")` (`engine_collector.py:244`) at the same instant,
which encodes the foe's seat when the foe owes a real decision. It is returned
to Python and discarded; `step()` re-derives. This is the same class of waste
already itemised as hygiene at `NOTES.md:1974-1980` ("double encode per decision
in `env.rs:224-234`/`:273-274`"). It does not cover the mid-turn-faint case where
the foe owes only a Pass. **Recommendation: do not optimise it in this change** —
`NOTES.md:1502-1504` records the reason (a partial-encode path would break D18's
deliberate choice of a SLICE over a new fill path).

### 3.2 What the measured record bounds it at

**No measurement of the privileged block's engine-route cost exists.**
`docs/engine_port/NOTES.md` and `SPEEDUP.md` contain none — grep for
`privileged` in `docs/engine_port/` returns only `NOTES.md:1468-1504`, which is
the "recorded rather than optimised" note. **UNMEASURED.**

What the record does bound:

* `NOTES.md:1970-1972`: "The engine, the Rust encoder and the PyO3 seam together
  are **1.5% of collection at k=32 and never above 8.7%** (k=512)."
* `NOTES.md:2202`: "Collection is 34.9% of wall at k=8".
* STATUS.md:20-21: update is **65.1% of wall** on the engine route.

So the **entire Rust side** — engine stepping, both encodes, and the PyO3 seam —
is at most `8.7% × 34.9% ≈ 3.0% of wall`, and about 0.5% at k=32. A third encode
cannot cost more than that whole block. **Ceiling: ≤3.0% of wall; realistically
well under 1%.** Quote it as a bound, never as a measurement.

The `~65 us/step` from the Node path (§2.2) does **not** transfer: it is a
poke-env `embed_battle` in Python, and the Rust encoder is the one STATUS.md:57
prices at "166x faster".

### 3.3 How to measure it in 10 minutes

`scripts/engine_t1.py --leg b` is the instrument. It is COLLECTION-ONLY
(`engine_t1.py:136-143`), sweeps `K_GRID`, builds the entity trunk at the 100M
`trunk_kwargs`, and takes `steps` polls after a 20-poll warm-up
(`engine_t1.py:169-180`).

One change is needed: `leg_b` constructs `EngineCollector(learner.act_logp, pool,
seed=seed, k=k, team_bank=bank)` at `engine_t1.py:170` with no `privileged`
kwarg. Add `privileged=args.privileged` behind a new flag (default False, so the
banked leg-b numbers are untouched), then run the leg twice — off, then on —
back to back on an idle box and report the ratio per k. At the shipped
`steps=400` this is minutes per k.

Report it as **collection-only, with k and the trunk width** (CLAUDE.md's quoting
rule; `engine_t1.py:4-7`). To convert to a full-loop figure, multiply the
collection delta by collection's share of wall at that k — do not quote the
collection ratio as a training-speed ratio.

---

## 4. THE LEARNING SIDE

### 4.1 How the critic consumes it

**Concat to the critic's obs, then re-tokenised as entities inside the critic —
not a separate encoder.** This is D18's form and it is already built:

* `rl/agents/ppo.py:516-522`: with `trunk == "entity_deepsets"`, the critic is
  `EntityDeepSetsNet(obs_dim, 1, privileged_dim=privileged_dim, **trunk_kwargs)`.
* `entity_deepsets.py:505-508`: `forward` splits the tail
  `x, priv = x[:, :-priv_dim], x[:, -priv_dim:]`.
* `entity_deepsets.py:421-456` (`_priv_features`): the privileged block is
  tokenised **by the same rules and through the same `mon_net` / `move_net` /
  `species_emb` / `move_emb`** as the observed side — "the entity space is
  shared, only the pooling slots widen" (`entity_deepsets.py:352-354`). It
  returns three pooled tokens (priv mon pool, priv active, priv move pool).
* `entity_deepsets.py:369`: `ctx_in = (5 + 3) * entity_dim` — the ctx MLP widens
  from 5 to 8 slots. Critic params 494,849 → 642,305
  (`tests/test_entity_trunk_gen4.py:195-198`). The **actor is untouched**:
  626,059 either way, and `privileged_dim` on a policy head raises
  (`entity_deepsets.py:356-357`, "privileged_dim is critic-only").

`privileged_dim` should be **408**.

### 4.2 Can the value head's input be built at SEARCH time?

**Yes — the privileged block is a pure function of the opponent's team plus the
observable state, and a determinized leaf supplies both.** This is the load-
bearing question and it answers affirmatively, with three caveats that must be
disclosed.

* `sample_determinization` (`rl/search/determinize.py:153`) returns a full 6-mon
  opponent team: `moves` (exactly 4), `level`, `base_stats`, `dvs`
  (`determinize.py:55`, `EXPECTED_DVS`), `live` (the revealed poke-env mon or
  `None`), built at `:174-183` (revealed) and `:202-209` (sampled bench).
* `rl/search/bridge.py:381-401` turns that into `poke_engine.State(side_one=…,
  side_two=…)` where `side_two` is six fully-specified `EnginePokemon`
  (`_det_pokemon`, `bridge.py:198-230`), with HP/status/sleep read from the live
  mon at `:381-397`.
* `shadow_battle(state, turn)` (`rl/search/shadow_battle.py:135-170`) already
  builds **both** sides symmetrically — `side_views(state.side_one)` at `:151`
  and `side_views(state.side_two)` at `:152` — and assembles them with "Seat 1 =
  us" (`:136`). A **seat-mirrored** assembly (`active_pokemon=opp_active,
  team=opp_team, opponent_*=` our side) fed to `embed_battle` and then to
  `rl/envs/showdown.py:475-483`'s `privileged_block` yields the 408-dim block
  from seat 2's perspective, using the one true encoder. No new encoder.

**Caveat 1 — distribution shift, and it is real.** At training time the block is
the **true** seat-2 encoding (`rl/envs/showdown.py:1437-1439` off `battle2`;
`env.rs:296-298` off the real foe state). At search time it would be the
**RSD-sampled** opponent. The critic would be evaluated off-distribution unless
the search averages over determinizations — which `matrix.py:241-245` already
does (`ev_cell` → `.mean(axis=2)` over the determinization axis), so at `n_det`
4 (dose M) or 16 (dose L) the block is Monte-Carlo averaged. **This must be a
named secondary read in any pre-reg, not an assumption.**

**Caveat 2 — sampled bench is systematically "fresher".** `bridge.py:135-156`
gives unrevealed bench max PP, and `:381-397` gives them HP 1.0 / no status /
max DVs. A true privileged block would carry their real HP and status. The
critic would see a uniformly healthier opponent team than reality.

**Caveat 3 — the aliasing rule reads the whole battle object.**
`privileged_block` slices only own-side dims, but the own-move blocks it slices
were filled under `_move_slots_aliased(battle)` (`rl/envs/showdown.py:317`,
`_fill_ids` at `:371`), which consults the battle. A mirrored `shadow_battle`
derives `force_switch` and `available_moves` from our active only
(`shadow_battle.py:153-156`, `:167`); the mirrored variant must derive them from
the mirrored active or the aliasing decision is taken on the wrong seat.

### 4.3 The design question the maintainer should decide first

D18's falsifier (§0.3) says the privileged critic **improved value estimation and
did not improve (and may have degraded) the policy**. There are two distinct
products here and the proposal deliberately does not choose between them:

* **(A) One privileged critic, used for BOTH advantages and search leaves.**
  Cheapest, is IDEAS 4.7 as written, and carries D18's measured hazard into the
  policy gradient. `docs/IDEAS_POST_100M.md:757-761` already pre-commits the
  mitigation: "MECHANISM CO-PRIMARY — value-loss and EV trajectory plus critic
  srank against the control, win rate secondary … D18's falsifier restated
  verbatim … pre-committed as a NULL branch this time, never a kill."
* **(B) A privileged EVALUATOR head alongside the ordinary critic** — the
  ordinary critic keeps producing advantages (arm A's learning dynamics
  preserved bit-for-bit), and a second value head trained on the same returns
  with the privileged input is used **only** as the search leaf evaluator. This
  sidesteps D18's falsifier entirely: the thing D18 measured going wrong is the
  advantage channel, and (B) does not touch it.
  Cost: a third net, a third param group, a checkpoint rider (the `aux_head`
  precedent at `ppo.py:1471-1476`), and it is NOT what IDEAS 4.7 describes, so it
  needs its own entry.

**(A) is what this proposal scopes and prices.** (B) is named because the record
argues for it and because choosing (A) by default would be choosing it without
noticing.

### 4.4 What changes in `rl/search/` — named, not implemented

Nothing in `rl/search/` knows about `privileged` today (grep: only two
unrelated docstrings, `rl/search/harvest.py:12` and `rl/search/bridge.py:44,61`).
The seam is four functions plus two guards:

1. **`rl/search/agent.py:102-105` `SearchAgent._critic_fn(batch)`** — today
   `self._agent.critic(torch.as_tensor(batch))` on `(N, 828)`. Must receive
   `(N, 1236)` or take a second array. Same for
   **`_loo_critic_fn`** (`:107-111`).
2. **`rl/search/agent.py:113-132` `SearchAgent._decision_critic(...)`** — the
   single dispatcher for E0 / `noise` / `loo` / `oppact_uniform`. The one
   injection point; the `noisy` closure at `:127-131` wraps whatever it returns
   and needs no change.
3. **`rl/search/matrix.py:225-232`** inside `solve_decision`
   (`matrix.py:133-146`) — the only place a leaf becomes a vector
   (`embed_battle(shadow_battle(lv, turn + 1), type_chart)`). A parallel
   `leaf_priv` list is built here, and the `leaf_obs.append(None)` at `:230` for
   terminal leaves must be mirrored (terminal leaves take `_terminal_value`,
   `matrix.py:117-130`, and never reach the critic).
4. **`rl/search/shadow_battle.py:135-170` `shadow_battle`** — needs the
   seat-mirrored variant of §4.2. Both `side_views` calls already exist.

Two guards that will fire and need explicit rulings:

5. **`scripts/ch3_eval.py:322-324`** — `assert getattr(env.unwrapped,
   "_privileged", None) is False, "SF-13: the eval env must not emit
   info['privileged']"`. A determinization-sourced block does not violate SF-13's
   spirit (the point of RSD is that it uses no hidden state), but the assert is
   literal and needs a ruling, not a quiet edit.
6. **`scripts/ch3_eval.py:57-109`, `_Battle2Sentinel`** — a data descriptor that
   raises `PurityIncident` when `battle2` is read from any frame whose filename
   contains `rl/search` (`:75-86`). A determinization-sourced block never touches
   `battle2` and is safe; a "just read seat 2, it's easier" shortcut is a
   retraction-grade incident by construction. Worth naming in the pre-reg so
   nobody takes the shortcut.

**Cost at search time.** STATUS.md:57: today's stack is 5 s/decision, "55% is a
Python leaf encoder". A second `embed_battle` per leaf roughly **doubles the
dominant term** — one per expanded leaf, up to `leaf_cap` 1,296 at dose M and
5,184 at dose L (`rl/search/matrix.py:79-83`). Naively that is ~5 s → ~7.75
s/decision, which **breaches the ≤5 s per-decision cap proposed for a searched
ladder object** (STATUS.md:50). On the projected pkmn/engine search stack
(~0.17 s, STATUS.md:57) it is affordable. **Implication: the search half of this
work should wait for the Rust leaf encoder, or use a single-pass both-seat encode
(one `embed_battle` that emits actor-obs and the mirrored own-side slice
together).** The training half does not have this problem and does not have to
wait.

---

## 5. A 12M SMOKE PLAN (not a pre-reg)

Purpose: prove the seam carries real numbers and that the first update is not
training a wide critic on zeros. **Not** a verdict, not a dose, not comparable to
anything banked.

### 5.1 The config diff against `configs/engine_a1.yaml`

Exactly two lines under `agent:`, plus the horizon:

```yaml
agent:
  privileged_dim: 408          # NEW — the lever; the collector derives its own
                               # flag from this (rl/train.py:917-926)
  lr_anneal_steps: 12000000    # == total_steps (the R0-b coupling engine_a1
                               # keeps at :392-396)
total_steps: 12000000
run_name: engine_priv_smoke_s<seed>
```

`aux_oppact_coef: 0.1`, `aux_label_space: l6` and `env_kwargs.opp_action: true`
are **already** in `configs/engine_a1.yaml` (agent block; `env_kwargs` block), so
the oppact head the monster must keep (`rl/search/agent.py:68-70`) rides along
unchanged. `collector.mode: engine`, `k: 8`, `learner_seat: p1` unchanged.
`collector.team_bank` must point at a bank that exists (`engine_a1.yaml` names
`data/engine/teams_a1_5000000.bin`, annotated "DOES NOT EXIST YET"); the smoke
can use any bank meeting `min_bank_pairs`.

**No new config key.** If the maintainer prefers an explicit knob over derivation
(§1.4f), it is `collector.privileged` plus an `ENGINE_KEYS` entry at
`rl/train.py:687` plus a launch-time pairing check in the shape of
`rl/train.py:855-863` — three edits instead of zero, and
`tests/test_engine_a1_prereg.py:59-67` records that this exact key has already
broken one config. **Recommendation: derive.**

### 5.2 R0 gates that would catch a broken seam in the FIRST update

Keep every gate in `configs/engine_a1.yaml:424-450` (entropy band, `clip_frac !=
0`, the four `aux/*` gates, `eval/win_rate` in (0,1),
`collect/policy_version_lag_p99 <= 1`, `eval/no_outcome` ABSENT). Add five:

| gate | reads | why it catches the seam |
|---|---|---|
| **S-1 zeros** | the `privileged` array of the first drained batch: `abs(x).sum() > 0` and `x.std() > 0` per column-block | the exact failure both current refusals name ("the wide critic would train on zeros") |
| **S-2 shape** | `batch["privileged"].shape == (n_rows, 408)` and `n_rows == len(batch["obs"])` | a ragged or misaligned block; `pyencode.rs:311-328`'s `rows2` already refuses a non-whole row count Rust-side, this is the Python-side pair |
| **S-3 critic width** | `agent.critic.ctx_net[0].weight.shape[1] == 8 * entity_dim` (1024 at `entity_dim: 128`) and actor params == 626,059 | the actor must not have widened (`entity_deepsets.py:369`, `tests/test_entity_trunk_gen4.py:195-198`) |
| **S-4 value stats** | `loss/value` finite and `explained_variance` (`ppo.py:1236-1240`) **> the arm-A control's first-update value** at the same step | a critic reading a real 408-block should fit better immediately — this is D18's own EV signature (SESSION_LOGS.md:2652-2654) arriving at update 1 |
| **S-5 parity** | the new §1.6 value test green in the pre-flight suite | a shifted slice reaches the critic with no error anywhere (`NOTES.md:1484-1489`) |

S-1 is the one that matters. It is a two-line assertion and it is the entire
content of both refusals being lifted.

Plus the standing pre-flight: `test_aux_head_inputs_are_unchanged_by_privileged_dim`
(§2.5.1) green, and `loss/entropy`, `aux/labelled_frac`, `aux/illegal_label_frac`
identical in DISTRIBUTION to a paired non-privileged lane over the first 250k —
the aux head's inputs are provably unchanged (§2.3), so a drift there means the
lift was not minimal.

### 5.3 Runtime at k=8, width 1

From `docs/engine_port/SPEEDUP.md:27` (maxout table, evals off, idle box):
**k=8, 1 lane = 2,390 steps/s.**

`12,000,000 / 2,390 = 5,021 s = **1.40 h per lane**`, evals excluded.

Add the eval schedule: `configs/engine_a1.yaml:836-837` is `eval_every: 250000`,
`eval_episodes: 100` — 48 evals over 12M, on the server, against
`SimpleHeuristicsPlayer`. Budget those separately; the SPEEDUP row explicitly
excludes them (`SPEEDUP.md:60`).

For reference on the same table: k=256 w=1 = 3,035 steps/s → **1.10 h**; k=256
w=6 = 9,994 steps/s fleet → three seeds concurrently in ~1.9 h of wall. Under
CLAUDE.md rule 4 a 1.4 h single lane is agent-side runnable; a 3-lane fleet is
still under 2 h.

**One lane, one seed, is enough for a smoke.** If a second is run, rule 2:
distinct `--seed`s.

---

## 6. RISKS, ranked

**R1 — `privileged_dim` changes the ACTOR's initial weights at a fixed seed.**
Measured, not speculative: actor param sum 334.851 → 410.510 at the same torch
seed (`tests/test_entity_trunk_gen4.py:195-198`), because `init_head` re-inits
the whole net (`entity_deepsets.py:395-411`) and runs after the widened critic
has moved the RNG stream (`ppo.py:514-537`). **Consequence for the monster:** arm
A and arm B are NOT paired at initialisation even at the same seed. IDEAS 2.2's
seed pairing (`docs/IDEAS_POST_100M.md:756-757`, "seeds paired (2.2)") therefore
buys less than it does for other levers, and rho is already UNKNOWN
(`NOTES.md:1456-1461`). **Disclosure owed in the pre-reg. Do not "fix" it by
reordering construction — that breaks `_GEN1_PIN` for every existing recipe.**

**R2 — D18's falsifier is the mechanism risk, and it fires on the ADVANTAGE
channel.** "EV rose on EVERY lane … while win rate stayed flat"
(SESSION_LOGS.md:2652-2654); the epitaph was "critic fits information the policy
cannot exploit; advantage signal degraded". Design (A) in §4.3 carries this
straight into the monster's second arm. Mitigations are pre-registered in IDEAS
4.7 (mechanism co-primary, falsifier restated, NULL branch not kill); design (B)
avoids it structurally. **This is a maintainer decision, not an implementation
detail.**

**R3 — the search half needs the Rust leaf encoder before it is affordable.**
A second `embed_battle` per leaf roughly doubles 55% of a 5 s/decision stack
(STATUS.md:56-57; `matrix.py:225-227`, `leaf_cap` 1,296/5,184 at
`matrix.py:79-83`), i.e. ~7.75 s/decision — over the ≤5 s cap proposed for a
searched ladder object (STATUS.md:50). **The training seam and the search seam
should be separate blocks, and the search seam should wait.**

**R4 — train/inference distribution shift on the block itself.** Training: the
TRUE seat-2 encoding. Search: an RSD-sampled team with fresher HP/status/PP
(§4.2, caveats 1-2). Averaged over `n_det` at doses M/L
(`matrix.py:241-245`), but not eliminated. A named secondary read.

**R5 — checkpoint contract: the CRITIC's `state_dict` changes; the ACTOR's does
not.** Critic params 494,849 → 642,305 (`tests/test_entity_trunk_gen4.py:195-198`)
and `ctx_net.0.weight` changes shape, so a privileged checkpoint's `critic` will
NOT load into a non-privileged agent (`ppo.py:1499`
`self.critic.load_state_dict(state["critic"])`, a hard shape error — loud, which
is correct). Every eval site rebuilds from the run's own config via `make_agent`
(`rl/train.py:59-79`, splats every `cfg.agent` key;
`scripts/eval_checkpoint.py:73-74`, `:95-96`, `:195-196`), so they are fine.
`rl/train.py:82-108` `_frozen_checkpoint_pool` likewise rebuilds from
`ckpt["config"]`. **`OBS_DIM` is UNCHANGED at 828** — this is not the
"changing OBS_DIM invalidates every checkpoint" landmine.

**R6 — `_GEN1_PIN` and the bit-exact trunk pin.** `tests/test_entity_trunk_gen4
.py:185-230` already pins `privileged_dim ∈ {0, 408}` bit-exactly for gen 1 —
this is an ASSET, not an obstacle: the privileged critic's forward is already
golden. The change to guard is that the combined build (`privileged_dim=408` AND
`aux_oppact_coef=0.1`) is a NEW object with no golden; §2.5.3 adds one. Note the
adjacent constraint: the scorer factorization is REVERTED and blocked by this
same bit-exact pin (STATUS.md:28-29, `NOTES.md:2016-2021`) — this proposal does
not touch it.

**R7 — `rl/networks/entity_deepsets.py` reach.** The privileged path touches
`__init__` (`:303`, `:347-369`), `init_head` (`:395-411`, whole-net), `forward`
(`:505-508`, `:532-533`) and `_priv_features` (`:421-456`). It shares the
`mon_net` / `move_net` / embedding tables **within the critic**, so the critic's
entity space is now trained on both observed and privileged tokens — that is
D18's deliberate design (`:352-354`) and it means the critic's representation is
not comparable to the control's even where the block is absent. Not a defect;
a disclosure for any critic-srank or dormancy read
(`scripts/d22_dormant_rank.py` hooks `scorer.1` on the ACTOR, so it is
unaffected).

**R8 — `harvest_both_seats` stays refused, in two places.**
`ppo.py:688-689` and `rl/train.py:835-838`. Seat 2's privileged block would be
seat 1's own side and is not collected. Leave both refusals in place; the
engine route makes seat-2 harvest cheap (`NOTES.md`/plan §8.4) and that is a
separate pre-reg.

**R9 — A-1's grading is untouched but its guard test is adjacent.**
`tests/test_engine_a1_prereg.py:66-67` asserts `privileged_dim` absent from
A-1's config. A-1 does not get this lever and that assertion should stay; only
its stated REASON ("rl/train.py refuses D18 on the engine path") becomes stale
and should be reworded to "A-1 is a one-lever parity gate". **Nothing 100M+ runs
on the engine before 7.5 exits** (STATUS.md:43-44) — this proposal is
build-and-smoke work inside 7.5, not a launch.

---

## Estimated effort

**2 evening blocks for the training seam** (§1, §2, §5): ~1 block to write the
six edits and five tests, ~1 block to run the 12M smoke and the leg-b cost
measurement and write the readout.

**A further 2-3 blocks for the search seam** (§4.4), and it should not start
until the Rust leaf encoder lands (R3) — the four functions are small, but
`shadow_battle`'s mirrored variant plus the two `ch3_eval.py` purity rulings are
the real cost.

Edits in the training seam, for sizing: `rl/envs/engine_collector.py` (3 sites),
`rl/buffers/episode.py` (3 sites), `rl/agents/ppo.py` (2 sites: the guard at
`:476-481`, `update_episodes` at `:1145-1190`), `rl/train.py` (2 sites:
`:821-834`, `:917-926`). No change to `rl/buffers/rollout.py`,
`rl/envs/showdown.py`, `rl/networks/entity_deepsets.py`, or the Rust crate.

## Decisions needed from the maintainer

1. **Design (A) or (B)** — one privileged critic driving both advantages and
   search leaves (IDEAS 4.7 as written, carries D18's falsifier), or a separate
   privileged evaluator head leaving the advantage channel untouched (§4.3).
   Everything downstream depends on this and it is the only question that
   changes the shape of the work.
2. **Lift the `ppo.py:476-481` guard outright?** The proposal argues yes, with a
   comment recording R0-1's arm scope and the R1 residue (§2.4). The alternative
   — leave it and gate on the collector — is argued against.
3. **Derive the collector flag from `agent.privileged_dim`, or add
   `collector.privileged`?** Proposal: derive (§1.4f, §5.1). An explicit key is
   three more edits and has broken a config once
   (`tests/test_engine_a1_prereg.py:59-67`).
4. **Does the seam ship inside JOURNEY 7.5, or wait for 7.5's exit?**
   STATUS.md:43-44 says nothing 100M+ runs on the engine before 7.5 exits; a 12M
   smoke is not a 100M run, but it is a capability change to the collector A-1 is
   being graded on. A ruling avoids an argument later.
5. **`scripts/ch3_eval.py:322-324` (SF-13) and the `battle2` sentinel** — does a
   determinization-sourced privileged block satisfy SF-13? Needed before any
   search work, not before the training seam (§4.4.5-6).
6. **Whether the block's engine-route cost must be measured before the arm
   launches.** `NOTES.md:1500-1502` says T-1 should price it; §3.3 is a
   ~10-minute measurement. Cheap enough that the answer is probably yes.
