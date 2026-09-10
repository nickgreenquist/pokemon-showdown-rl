# WANG 2024 — VERIFIED DEEP-READ OF THE SEARCH LAYER

**This is a verified deep-read**, performed 2026-09-10, read-only, against these exact local
sources and nothing else:

- `docs/prior_work/wang2024_mit_thesis_randbats_rl.pdf` — Jett Wang, *Winning at Pokémon Random
  Battles Using Reinforcement Learning*, MIT MEng thesis, February 2024. 46 pages; the PDF page
  number equals the printed page number throughout (Chapter 1 starts on both page 13). Read in
  full; Chapters 3 (Methods) and 4 (Results) and Appendix A read page-by-page as rendered images
  as well as as text.
- `docs/prior_work/wang_fork_diffs.md` — **4,213 lines as it sits on disk today**;
  `README.md`:10 calls it 2,362 lines, which no longer matches the file (minor index drift,
  recorded). Maintainer-extracted 2026-08-03, covering three `quadraticmuffin` forks:
  `pokemon-showdown` (13 commits), `poke-env` (36), `stable-baselines3` (8). Cited by line
  number in that file.
- `docs/prior_work/README.md` — our verified index (Wang source entry at :393–400, ladder table
  row at :123, action-space claim at :469–470, fork-diffs entry at :567–577).

Cross-references to our own measurements cite `docs/search_relook/S3_READOUT.md`,
`readouts/GEN4_WANG50M_READOUT.md`, `rl/search/*.py` and `configs/`.

**Citation convention.** `p.N` = thesis page N. `diff:N` = line N of `wang_fork_diffs.md`.
Where the thesis is silent I write **NOT STATED** inline and repeat it in the mandatory list at
the end. Where I reason beyond the sources I label the paragraph **INFERENCE** and show the
arithmetic.

---

## 0. The one-paragraph answer

Wang's MCTS values a leaf with **the very same PPO critic head that served as the advantage
baseline during training, unmodified — never retrained, never fine-tuned, never recalibrated,
and never trained on any state distribution other than its own self-play** (p.21, p.23, p.41;
the SB3 fork contains only timing instrumentation, diff:3993–4213). The reason this composes is
structural rather than lucky: during search he models the opponent with **that same network's
policy head** (p.26), so the states his critic is asked to value are drawn from exactly the
πθ-vs-πθ distribution it was fitted on; and he **deliberately withholds the determinized hidden
information from the value function's own input**, noting that using it would require training
a different network (p.38, §5.2.2). Both of the ways a search can drag a critic off its training
distribution are therefore closed by construction.

---

## 1. THE LEAF EVALUATOR

**What values a leaf.** Two cases, and only two (p.21, "Backup Update"):

> "A rollout ends when we encounter a terminal node or a leaf node at timestep T. At this point
> we obtain a value v for the final state s_T. If s_T is terminal, v is +1/-1/0 for a
> win/loss/tie respectively. Otherwise, we use v = V_θ(s_T), the output of the neural network's
> critic head, to estimate the value of s_T." (p.21)

So: **terminal → exact ±1/0; non-terminal leaf → the PPO critic head.** There is no hand-written
heuristic anywhere in the evaluator, and the thesis says so twice — "Self-play ensures that no
handcrafted Pokémon-specific heuristics are used to produce our neural network's value function
and policy" (p.23).

**There are no rollouts-to-termination with the policy.** He says explicitly that his variant
departs from vanilla MCTS here:

> "Vanilla MCTS plays each rollout to the end of the episode (a terminal node)… Here we discuss
> a variant where rollouts may end on either: a terminal node, as in vanilla MCTS; a leaf node,
> i.e. one which is not yet recorded in the tree. Stopping at leaf nodes is made possible because
> we have V_θ, a trained state value estimator, and provides efficiency gains because rollouts
> can end earlier." (p.20)

The default-policy / random-playout leg of classical MCTS is absent. It is AlphaZero-shaped:
policy prior in selection, critic at the leaf, no playouts. The words "playout" and "rollout
policy" never appear (verified by grep over the extracted text).

**Same critic as PPO's advantage baseline — yes, and it is the *same object*, not a copy.**

> "In our implementation, the policy and value functions learned share most of their parameters;
> we train an actor-critic network, meaning a neural network with one head to estimate the value
> of the current state (the critic), and another head to output a distribution over actions (the
> actor)." (p.20)

> "The value loss, a squared loss term used to learn a value function which forms the baseline
> for the advantage estimate" (p.20)

Appendix A.0.2 confirms one trunk, two heads: feature extractor → 3-layer MLP (hidden 256) →
actor head (2-layer MLP) and critic head (2-layer MLP → scalar) (p.41). Table A.3 gives
`value_coef 0.4375` as a tuned PPO hyperparameter (p.43) — i.e. the critic's only training
signal is PPO's own value loss.

**Was it retrained / fine-tuned / recalibrated for search? NO — and the thesis states the
counterfactual.** No section describes any post-training modification of the value head. The
words "retrain", "recalibrat*" appear nowhere in the thesis; "fine-tune" appears once, in a
speculative LLM-embedding aside (p.36). The dispositive passage is §5.2.2, listed as *future
work*:

> "After sampling opponent hidden information, we actually have moved into a regime with perfect
> information. Currently, the sampled information is only made available to the opponent so that
> it can play moves, and to the server so that it can properly simulate the rollout. If all info
> were made available to both players, higher-quality moves could be chosen for each rollout,
> improving the result of MCTS. **To complete this approach, we would also train a new neural
> network on a perfect-information version of the game.**" (p.38, emphasis mine)

Read that carefully against our S1/S3 defect. Wang identifies exactly the operation we performed
— revealing determinized opponent information to the evaluated state — states that it *would*
improve the search, and states in the same breath that doing it requires **a new network trained
on that distribution**. He did not do it. We did the first half without the second.

**Was the critic ever trained on states off the policy's own distribution? NO.** Training was
pure mirror self-play at the latest iterate, both seats harvested:

> "In each game played during training, both players used the most recent iteration of the
> policy, and both players recorded the trajectory for learning. In other words, each game
> played produced two games for the algorithm to learn from." (p.24)

No opponent pool, no league, no BC init, no SH-generated data, no offline corpus. The critic
therefore sees exactly one distribution in training: π_θ vs π_θ. And in search it is asked about
exactly that distribution, because the opponent is modelled with π_θ (§3.2.1, p.26) and our own
side selects with a π_θ-prior tree policy (p.21). **The search's leaf distribution is the
critic's training distribution.** That identity is, in my reading, the single most important
structural fact in the thesis about why his search pays.

**Value scale.** Reward is terminal-only, `r ∈ {−1, 0, 1}` with 0 for every non-terminal turn
*and for ties* (p.23), and `gamma = 0.9999` (Table A.3, p.43). So V_θ is an essentially
undiscounted expected-outcome estimate in [−1, +1] — dimensionally identical to the ±1/0 terminal
backup it is mixed with in the same `Q` running mean. There is no scale mismatch to reconcile.
(Ours is the same shape: `gamma: 1.0`, terminal-only ±1 — `configs/showdown_sp_batch50m.yaml`
:836. This closes off "value-scale mismatch" as a candidate explanation for our sign.)

---

## 2. THE TREE

**Variant: a PUCT-family tree policy with the policy as prior — but not AlphaZero's PUCT, and he
says so.** The selection rule (p.21):

> a_t = argmax_a ( Q[s_t, a] + α · U(s_t, a) ),  where  U(s, a) = P[s, a]^β · √(M[s]) / (N[s, a] + 1)

with `P[s,a] = π_θ(a | s)` and, in his own footnote 3 (p.21):

> "The tree policy used is similar to that used in AlphaZero [21], except that α is a constant
> instead of a function of M[s] and β is introduced."

The words "UCT" and "PUCT" never appear in the thesis. This is PUCT-shaped: policy prior in the
numerator, visit count in the denominator, √(parent visits) scaling. The novel dial is
**β ∈ [0,1]**, an exponent on the prior that "dictates … how much to trust the neural network
policy" (p.21). **The numeric values of α and β are NOT STATED anywhere in the thesis** — Table
A.3 (p.43) lists PPO hyperparameters only, and no MCTS hyperparameter appears in it.

**Backup: running mean, no max, no minimax.** `Q[s,a] ← (N·Q + v)/(N+1)`, `N += 1`, `M += 1`
(p.21–22). Every value in the tree is an average over the rollouts that passed through it.

**Final action selection: MAX VISIT COUNT, not max Q — and the reason given is variance.**

> "a* = max_{a∈A} N(s_0, a) … It is intuitive to choose the action with the largest Q value
> instead, but less-visited actions may have higher variance in their Q estimates." (p.22)

This is a *robust* selector. An action whose Q looks best on a handful of noisy leaf evaluations
cannot win unless the tree policy also chose to spend visits on it, and the tree policy is
anchored to the policy prior through `P[s,a]^β`. The search cannot stray far from π_θ without
paying for it in visits. **This is a regularization mechanism our depth-1 matrix does not have**
(see §8, H2).

Selection at the root is deterministic; mixing is explicitly *future work* (§5.2.1, p.38).

**SIMULTANEOUS MOVES: NOT STATED as a design problem, and the deployed treatment is a
single-agent approximation.** The thesis acknowledges simultaneity twice as a fact of the game
("on most turns both players choose their actions simultaneously", p.13; "sometimes they are
simultaneous, or one player makes two decisions in a row", p.25) but **never names it as a search
problem and never describes a joint-action or matrix treatment**. The words "decoupled", "Nash",
"simultaneous-move game", "matrix game" do not appear. "equilibrium" appears exactly once, in
§5.2.3 as a *conjecture about future work* (p.39).

What the deployed system does, from §3.2.1 (p.26):

> "During MCTS, we model the opponent's decisions using the trained neural network policy. This
> has the benefit of simplicity, but weakens the agent's performance against players who play
> differently from the neural network."

**INFERENCE (well supported):** the tree branches over *our* actions only; the opponent's action
is sampled from π_θ and folded into the environment transition, together with the simulator's
RNG. Support: (i) the statistics are `Q[s,a]`, `N[s,a]`, `M[s]`, `P[s,a] = π_θ(a|s)` — one action
index, not a pair (p.21); (ii) the tree policy argmaxes over a single `a` (p.21); (iii) the final
decision is `argmax_a N(s_0, a)` over one action space (p.22); (iv) the rollouts are stepped
through the real Showdown battle stream, which will not advance a turn until both sides have
submitted a choice, and the opponent's is supplied by π_θ. So the game is treated as a **POMDP
with a fixed opponent policy baked into the transition kernel** — a best-response search, not an
equilibrium search. He effectively concedes this in §4.2:

> "we believe the winrate of the full agent with MCTS vs NN to be somewhat 'inflated'. Recall
> that during MCTS, we assume our opponent plays according to the NN policy, and search for the
> best response. Then, because in essence the MCTS always knows exactly what the NN will do, its
> winrate when playing against NN is higher than when playing against humans of equivalent
> strength to NN." (p.32)

Note that he applies this caveat **only to the MCTS+NN vs NN cell (.809)** — not to the .908 vs
SimpleHeuristics. Against SH the opponent model is wrong, and search still gained 12 points.

**STOCHASTICITY: handled by Monte Carlo sampling through the real simulator, with a fresh RNG
per rollout.** The thesis states the principle — "MCTS deals naturally with the stochasticity of
Pokémon by taking an expectation over rollouts" (p.23) — and the fork shows the mechanism. Every
rollout restore calls `this.battle!.resetRNG(null)` (diff:702) immediately before re-rolling the
opponent team (diff:703). There are no chance nodes, no damage-roll enumeration, no explicit
expectimax layer. Damage rolls, accuracy, crits, secondary effects and speed ties are all
realized by Showdown's own PRNG and averaged into `Q` over ~1000–2000 rollouts.

He also relies on this to excuse the leader-collision risk in parallel search:

> "It is possible that given similar initial trees, each worker traverses the tree in a similar
> way, inflating the visit count of certain actions. This effect is mitigated, however, by the
> stochasticity of the environment: even if workers select the same action, it is likely that
> they will receive different outcomes from the environment… Empirically, we find this not to be
> a major issue: the most-visited action nearly always has the highest estimated value." (p.27)

**DEPTH REACHED IN PRACTICE: NOT STATED.** The thesis gives only two size figures — `R` between
1000 and 2000 rollouts per decision, and 2,000–15,000 nodes stored at any time (p.27–28) — and
never an average or maximum ply depth, never a tree-depth histogram.

**INFERENCE on depth (weak, shown for what it is worth):** 20 workers × 10 s = 200
worker-seconds for 1000–2000 rollouts is 100–200 worker-ms per rollout, and each rollout begins
with a full `>load` (JSON deserialization of the entire `Battle` plus a constrained team
regeneration — diff:695–703). That restore is plausibly the dominant cost, which would leave
rollouts *shallow* — a handful of plies. I cannot pin this from the sources and it is not a
claim; the honest statement is that **the thesis does not let you compute the depth**, and any
"his search was deep, ours is depth-1" story must be argued from the node counts and the
persistence rule below rather than from a stated depth.

**The tree PERSISTS ACROSS DECISIONS within a game — an effective-budget multiplier the
per-decision rollout count understates.** "Throughout the game, we keep track of the following
statistics as dictionaries" (p.21), and the only pruning rule is monotone in fainted count:

> "During a gen4randombattle game, the total number of fainted Pokémon never decreases. This
> means once the game reaches f1 fainted Pokémon, we can remove all states s′ from the tree where
> F[s′] < f1. **Other than this, no states are removed from the tree until the end of the game,
> because states could potentially be re-visited in later rollouts.**" (p.28)

So statistics accumulate across the ~25 decisions of a game between faints. The root of decision
*t+1* is frequently already in the tree carrying visits from decision *t*'s search.

**BRANCHING FACTOR with the 494-way action space: ≤ 9, exactly like everyone else.** This is the
key correction on item 7. From §3's POMDP definition (p.23):

> "a ∈ A = {0, 1, …, 494}: The first 199 actions correspond to moves, while the latter 295 actions
> correspond to switching to another Pokémon. **On any given turn, up to 9 actions are valid (up
> to 4 moves and up to 5 possible switches); the rest get masked out.**"

Masking is a hard −inf on the logits before the softmax (§3.1.3, p.25). The 494 is the width of
the *output layer*, not the search branching factor. His own game-tree estimate uses 6 options
per player per turn (p.15). Search branching is therefore ≤9 for him and ≤9 for us — identical.

---

## 3. DETERMINIZATION / IMPERFECT INFORMATION

**Sampling law: one full determinization per rollout, at the root, re-drawn every rollout.**

> "We address this by sampling one possibility for all unknown opponent information **at the
> start of each MCTS trajectory**. This is possible because we have access to the exact procedure
> by which Pokémon Showdown generates randombattles teams." (p.26)

"Trajectory" = rollout (the thesis uses "rollout" and "trajectory" interchangeably from p.20
onward). The fork confirms the granularity: the state is captured **once per decision** by
`>getstate` (diff:509–511, chat command at diff:454–462) and restored **once per rollout** by
`>load`, and the reroll is inside the load handler:

```
case 'load':                                        (diff:667)
  ...
  this.battle = Battle.fromJSON(jsonState);         (diff:695)
  this.battle.restart(send);
  for (const side of this.battle!.sides) this.battle!.undoChoice(side.id);
  this.battle!.resetRNG(null);                      (diff:702)
  this.battle!.rerollTeam(sideid as SideID, checkpointSets);   (diff:703)
  this.battle!.makeRequest();
```

`room-battle.ts` routes the reroll to the *other* seat — literally commented
`// reroll the side that didn't send the load` (diff:554–556). So each of the 1000–2000 rollouts
per decision gets **an independently drawn opponent team and an independently seeded PRNG**. This
is textbook root-level Perfect-Information Monte Carlo / determinized UCT, at a determinization
count of 1000–2000 per decision.

**What `>getstate` / `>load` actually are.** Two new chat commands (`/getstate`, `/load`, with
`/save` aliased to `/getstate` — diff:454–470) that expose Showdown's existing battle
serialization over the protocol. `Battle.emitState` sends `sideupdate` + `|state|<JSON>` to the
requesting side (diff:744–748) using stock `State.serializeBattle`; `/load` (diff:466–470 → diff:525–562) takes
`<sets>|-|<requests>` from the client, rebuilds the battle from JSON, and re-rolls the opponent
side. **Serialization itself is upstream Showdown; the fork's contribution is the protocol
surface, the reroll, and the request/rqid bookkeeping** (diff:525–562; the block at diff:529–540
rebuilds `this.rqid` from
the per-player request ids so the restored battle accepts choices).

**What "constrained team regeneration" does.** `rerollTeam` (diff:757–815) calls
`teamGenerator.randomTeamFromPartial(checkpointSets, 6)` — note the hard-coded 6: **the
determinized opponent team is always a full six**, and an alternative that grew the team
incrementally is present but commented out (diff:768). Then:

- Revealed Pokémon: the *existing* `Pokemon` object is kept and only its set is swapped, via
  `replaceSet` (diff:839–886) — item, ability and move slots are replaced while HP, status,
  boosts, volatiles and forme are preserved (`// replaceSet does not modify forme`, diff:785).
  This is careful and correct: the battle state of a revealed mon survives re-determinization.
- Unrevealed Pokémon: replaced wholesale with new `Pokemon` objects (diff:790–796).
- `side.pokemonLeft` is recomputed with the comment `// newly hallucinated pokemon will not be
  fainted` (diff:808–811), so the determinized team's alive count matches reality.

**Does it condition on revealed information? Yes, and the conditioning set is explicit.**
`SetCriteria` (diff:717–723) is `{species, moves[], ability?, item?, isLead}`. `battle-stream.ts`
parses exactly these from the client's `/load` payload (diff:668–690). `randomConstrainedSet`
(diff:69–107) then does **rejection sampling against those constraints**: reroll until the
generated set's item matches, ability matches, and every revealed move is present. The thesis
describes the same procedure:

> "For unknown Pokémon, the server generates a new Pokémon and its set… For known Pokémon, the
> server attempts to generate a valid set consistent with the known traits of the Pokémon. It
> does this through rejection sampling: generating random sets until one satisfies the constraints
> formed by known traits." (p.26–27)

Including `isLead` is a genuinely careful detail — randbats set selection is lead-dependent.
**NOT conditioned on:** revealed level, revealed stats, or observed PP.

**Team-level structure is preserved.** `randomTeamFromPartial` (diff:253–…) pre-seeds the stock
generator's counters — tier count, per-type count, per-type weakness count, type-combination
count, `baseFormes` — from the revealed mons, then runs the stock rejection loop for the unknown
slots with all the usual caps (species clause, ≤2/tier, ≤2/type, ≤3 weak to a type, ≤1 per type
combo, the Zoroark-last-slot rule) (diff:326–380). `teamDetails` (hail/rain/sand/sun/spikes/
stealthRock/toxicSpikes/rapidSpin/screens) is likewise pre-populated from the revealed mons
(diff:311–320). This is structurally the same construction our `rl/search/determinize.py`
implements for gen 1 against the gen-1 generator's caps — so **determinization quality is not an
obvious axis of difference between the two systems; determinization COUNT is (4 or 16 vs
1000–2000).**

**The force-fallback, and a thesis/code discrepancy.** Thesis (p.27):

> "If after **10 attempts** we do not generate any valid sets, we 'force' the known information to
> be in the set, randomly filling in unknown information with no regard for compatibility."

The released code disagrees on the number: `randomConstrainedSet(criteria, teamDetails,
attempts = 100)` (diff:69–72), and the only in-repo caller passes **500** (diff:306–310). The
`force` flag is passed on the final attempt (diff:79) and simply writes the known ability/item in
directly. There is also a later fallback: if no *set archetype* is compatible with the revealed
moves at all, all archetypes are re-allowed (commit `8b2bb8e08`, diff:1459–1470). **The number
"10" in the thesis is not the number in the code**; the MCTS driver that would settle it is not
in any of the three released forks.

**Is there a belief model? NO.** The word "belief" does not appear in the thesis. There is no
learned opponent-team predictor, no posterior over sets beyond the generator's own prior
restricted by rejection. The determinizer is the *unmodified game generator conditioned on
observations* — which in randbats is the exact posterior over teams given the observed
constraints, up to the sequential-vs-final-team-counter approximation. (Our
`rl/search/determinize.py` header makes the identical point and the identical approximation.)

**A determinization-consistency fix worth naming.** Commits `8d43265ae` / `13d8c26a1`
(diff:1621–1770) make hallucinated moves respect the *live* battle's restrictions: a
newly-invented move slot is marked `disabled` if the mon is choice-locked onto a different move,
Encore'd onto a different move, or Taunted and the invented move is a Status move. Without this,
re-determinization can hand the opponent legal access to a move the live battle has locked out.
This is a real class of determinization bug and he fixed it three weeks before submission.

**What the determinized information is and is NOT shown to.** From §5.2.2 (p.38, quoted in full
in §1): the sampled information goes **to the opponent model** (so π_θ can pick moves from the
seat that owns that team — an on-distribution view for that seat) and **to the server** (so it
can simulate). It does **not** go to the searching agent's own state encoding. His own network's
input during rollouts is its normal partial-information view.

---

## 4. BUDGET

| quantity | value | source |
|---|---|---|
| ladder time control | timer starts at 150 s per player, **+10 s replenished per decision**; timer hitting 0 is an instant loss | p.24 |
| thinking time allowed per move | **10 seconds** | p.24 |
| rollouts per decision, R | **1000–2000**, "depending on the length of each rollout and size of the game tree" | p.27 |
| search parallelism | **20 workers** + an aggregator process; workers sync every **10 rollouts** | p.27 |
| tree size held | 2,000–15,000 nodes | p.28 |
| determinizations per decision | = R (one per rollout) | p.26 + diff:702–703 |
| GPU inference share | not the bottleneck — "the speed of each rollout is bottlenecked by the environment stepping, not GPU inference" | p.27 |
| training compute (for scale) | 150M steps ≈ 3M battles, 4 days, one A6000 48G + 80 CPU workers | p.24 |

**What 0.908 costs per decision.** 10 s wall-clock × 20 workers ≈ **200 worker-seconds per
decision**, spent almost entirely inside the Node.js Showdown simulator, producing 1000–2000
independent determinized rollouts. He is bounded by the ladder's own clock, not by hardware:
"Speed is of great importance in the search process because of the 10 second time constraint"
(p.27).

**Against ours (S3_READOUT.md):** dose M is **62.3 ms/decision and 277.4 leaves/decision**, one
process. Wall-clock ratio ≈ **160×**; CPU-seconds ratio ≈ **3,200×**; determinizations 4 vs
1000–2000 ≈ **250–500×**. Dose L (n_det 16, leaf_cap 5184) is 244.6 ms and 1083 leaves — still
~40× short in wall-clock and ~60× short in determinizations. **We have never run search at a
budget within two orders of magnitude of his.**

---

## 5. THE MEASUREMENT — what 0.786 and 0.908 actually are

**The table** (Table 4.1, p.30) is a four-player round-robin; row beats column:

|  | MCTS + NN | NN | Heuristic | Random |
|---|---|---|---|---|
| MCTS + NN | — | .809 | **.908** | .996 |
| NN | .191 | — | **.786** | 1. |
| Heuristic | .088 | .206 | — | .992 |
| Random | .004 | 0. | .007 | — |

Caption: "Some head-to-head winrates don't add up to 1, because of ties." (p.30)

- **n: NOT STATED.** The thesis gives no sample size for any cell of Table 4.1. §3.1.2's n=200 is
  a *different* measurement (see below).
- **Opponent:** poke-env's `SimpleHeuristicsPlayer` (p.24, ref [22]) — **but a patched one.** The
  poke-env fork modifies `baselines.py` twice (diff:3800–3822): Curse is excluded from the
  damaging-move argmax, and SH is barred from switching against Arena Trap / Shadow Tag. The
  commit log adds `1799235 Ignore Curse "???" type in HeuristicPlayer`, `e806b20 opp_remaining_mons
  bug in HeuristicsPlayer`, `11fb65b/547674a SimpleHeuristicPlayer should respect maybe_trapped`
  (diff:3419–3445). Both surviving patches make SH *strictly better* (they remove wasted/invalid
  choices). **Our numbers are against stock poke-env `SimpleHeuristicsPlayer`** (`rl/envs/
  showdown.py`:56,68 imports it directly, no subclass). The opponents are not identical objects.
- **Ties:** excluded from both sides' rates, not counted as losses. From the row/column sums:
  MCTS+NN vs Heuristic .908 + .088 = .996 → 0.4% ties; NN vs Heuristic .786 + .206 = .992 → 0.8%
  ties; MCTS+NN vs NN .809 + .191 = 1.000 → no ties. **Our locked protocol counts ties as
  non-wins.** At 0.4–0.8% this is immaterial either way, but the convention differs.
- **Checkpoint: NOT STATED.** The thesis never says which checkpoint produced Table 4.1, never
  says "final checkpoint", and never says whether the ladder object (§4.3) is the same checkpoint.
  The two rows .786 and .908 sit in the same table and share the "NN" label, so the same network
  is the natural reading — but it is a reading, not a statement.
- **Policy form: NOT STATED.** Whether the "NN" row plays argmax or samples from π_θ is never
  said. This matters: our 0.78867 is greedy by the locked protocol.
- **Error bars: none, anywhere.** No confidence interval or standard error appears on any winrate
  in the thesis (grep: no "confidence interval", no "±" on a winrate; the only "error bars"
  mention is a definition of Glicko-1 on p.32).

**Is 0.908 the n=200 validation metric? NO — they are different measurements.** §3.1.2 (p.24):

> "During training, the neural network was validated every 20,000 steps. The sole validation
> metric was the agent's winrate over **200 games** against SimpleHeuristicsPlayer."

That is the *training-time* curve of Figure 4.1, and it measures the **network alone** — MCTS is
never in the training loop ("MCTS is not used to train the neural network. Instead, the neural
network is trained via PPO, then MCTS is used purely at inference time as a policy improvement
operator", p.23). At 10 s/decision, running the full MCTS agent every 20,000 steps for 200 games
would be impossible. **So .908 is from Table 4.1 at an unstated n, not from §3.1.2's n=200.**

**Resolving Table 4.1's .786 against Figure 4.1's ~.85 — the thesis does not let you, and there
are in fact THREE numbers, not two.**

1. Prose, p.29: "After 150M total steps (4 days) of training, we reach slightly more than that,
   roughly **85%**."
2. Figure 4.1 itself, read from the rendered page: the smoothed line plateaus and ends at
   **≈0.82–0.83**, with the raw band spanning roughly 0.78–0.88. The prose's "roughly 85%"
   already sits above its own figure.
3. Table 4.1, p.30: **.786**.

The thesis makes no attempt to reconcile them and provides none of the information that would.
Candidate explanations, **all unstated**: Figure 4.1's points are n=200 (binomial se ≈ 0.028, so
one point at 0.85 vs 0.786 is ~2.3 se — the *curve level* of ~0.82 is the fairer comparison and
is still ~1.3 se above); the validation runs may use a sampled policy while Table 4.1 uses argmax
or vice versa; Table 4.1 may use a different checkpoint; ties may be handled differently. **My
verdict: unresolvable from the thesis.** The defensible statement of Wang's network-alone strength
vs SH is "somewhere in 0.786–0.85, with no error bar and no stated n", and any comparison against
our 0.78867 ± (seed-clustered) should carry that band.

**The ladder measurement** (§4.3, p.32): username `ihtfp_abra`, **n = 200 games**, average
**1615 Elo** — and the footnote matters: "average taken after game 100, to exclude the period
where it was climbing" (p.32 fn.1). The headline figures are a **PEAK**:

> "peaking at rank 8 (1693 Elo, 1756 ± 28 Glicko-1, 79.5% GXE)" (p.32)

Figure 4.3 shows the Elo trace starting at 1000, climbing to ~1600 by game 100, then oscillating
1550–1700 with a single spike to ~1700 near game 180; the plotted rank-1 line is 1763. **Only the
MCTS+NN agent was ever laddered. There is no ladder number for the network alone.**

---

## 6. WHAT HE REPORTS ABOUT SEARCH FAILING OR HURTING

This is thin, and the thinness is itself the finding. **§5 is titled "Future Work and Discussion",
not "Negative Results"**, and its one experimental negative is about the *network*, not the search.

**(a) The one experimental negative result in the thesis is §5.1.3, and it is not about search.**
The "recursive"/hierarchical idea — train (π_k, v_k) for k-Pokémon teams and bootstrap π_2 from
v_1 — was tried and failed:

> "We attempted such a setup, but saw **no significant improvements** over simply training a 6v6
> from scratch, in either training efficiency or strength of the trained agent." (p.37)

His own diagnosis is an out-of-distribution argument that reads like a prophecy of our S1 defect:

> "States which arise after one Pokémon has fainted on each team in a 2v2 may be **out-of-
> distribution** compared to the states which π_1 trained on. For example, it may be the case that
> our Pikachu is poisoned even though the opponent's Slaking doesn't know any moves which cause
> poisoning… but π_1 would never have encountered the current state." (p.37)

**(b) The self-inflation caveat on the MCTS-vs-NN cell** (p.32, quoted in §2 above). He discounts
.809 because the opponent model is exactly the opponent. He does **not** extend the caveat to
.908 vs SH.

**(c) A concrete case where the search made a materially bad move — the only one in the thesis.**
§4.4, expert `arolakiv`, turn 2 (p.33–34, Figure 4.4): with Kecleon against Rampardos, the bot
feared Superpower (37.4% of Rampardos sets) and switched to Venomoth, which was immediately KO'd
by Stone Edge because *all* Rampardos carry a strong Rock move. His attribution is the opponent
model, not the evaluator or the determinizer:

> "This suboptimal behavior could be explained by the fact that during MCTS, the bot strongly
> assumes that the opponent plays according to π_θ… It is conceivable that the neural net never
> chooses a Rock-type attack on that turn against Kecleon, so **the search was not aware of the
> potential for the switched-in Venomoth to get instantly knocked out**." (p.33–34)

Note what this failure *is*: the search's opponent model assigned ~zero probability to the
opponent's actual best move, so the search's expectation over opponent actions was
**systematically optimistic about switching in**. Flag this — the same failure shape is written
into our own `rl/search/matrix.py` docstring for a different reason (uniform switch targets ⇒
"the search is systematically OPTIMISTIC about our staying in").

**(d) A dismissed parallelism risk** (p.27): correlated workers could inflate visit counts;
dismissed empirically ("the most-visited action nearly always has the highest estimated value")
with no number attached.

**(e) An acknowledged suboptimality of the decision rule** (§5.2.1, p.38): deterministic
max-visit selection is wrong where the optimal strategy mixes, "with one action just barely
edging out the other."

**What is NOT there:** no ablation of any kind on the search. **No sensitivity study on R.** No
sweep or even stated value of α or β. No comparison of critic-leaf vs full-rollout backup. No
determinization-count study. **No case anywhere in which the network alone beat the search.**
Table 4.1's MCTS+NN row dominates the NN row in all three shared columns and that is the entire
evidence base for "search helps".

---

## 7. ACTION SPACE AND GENERATION

**His action space:** 494 identity actions — 199 move identities + 295 switch-target identities —
masked to ≤9 legal per turn (p.23). Hard −inf masking before the softmax, masks re-applied in the
gradient update (§3.1.3, p.25). **Ours:** 10-way positional on gen 1 (4 moves + 6 switch slots),
masked through `rl/common/masking` with a finite −1e8 sentinel.

**Does the thesis argue the action space made search necessary or effective? NO — the thesis
makes no argument about the action space at all** beyond defining it and noting the masking. The
words justifying the *format* choice (gen 4) are about mechanics richness and ladder activity
(p.13–14), not about action-space size. Gen 4 is in fact chosen partly *because* it has a
**smaller** action space than later gens: "Generation 4 excludes mechanics from later generations
such as mega-evolving and Terastallization which essentially double the action space of the game
until they are used" (p.14).

**Is our index's claim at README:469–470 supportable?** The claim is: *"the strongest pure
policies are positional; Wang's 494-way identity space is the outlier and his headline needed
MCTS."*

- **"the outlier": SUPPORTED.** 494-way identity is the only identity action space among the
  strong randbats agents in our index (ps-ppo 14 positional, Metamon 9/13 positional, ours 10
  positional).
- **"his headline needed MCTS": NOT SUPPORTABLE AS A CAUSAL CLAIM, and the causal direction it
  implies is not in the thesis.** Two problems. First, the network alone was **never laddered**,
  so there is no measurement of what the headline would have been without MCTS — the claim is
  untestable from the source. Second, if the implied mechanism is "the identity space cost him
  network strength, and MCTS repaired it", the thesis contains no support: his network alone
  reaches 0.786–0.85 vs SH, which is in the same band as positional agents at comparable budgets,
  and the search branching factor is ≤9 regardless of output width (§2 above).
- **What IS defensible:** *the only object Wang ever laddered was MCTS+NN; the thesis contains no
  ladder measurement of his network alone, and no ablation isolating the contribution of the
  action space.* I recommend the index be narrowed to that.

---

# WHY OUR RESULT MIGHT DIFFER — hypotheses, ranked, each with the evidence that would settle it

Framing. The base rates are almost identical — his network alone .786 vs SH (p.30), our 100M
object 0.78867 vs SH (S3_READOUT A0) — and the search deltas have opposite signs: **+0.122 for
him, −0.0681 for us** (S3_READOUT P-M, 3/3 lanes negative, clustered se_diff 0.01944). In loss
terms he removes 57% of the network's losses; we add 32%. Ranked by how much of that gap I think
each hypothesis can carry, and by whether we can actually settle it.

### H1 — BUDGET AND DEPTH: his search does 250–3000× more work, and depth-1 makes the critic the only thing that can move a decision. **Rank 1.**

At depth 1 with a terminal-only critic, the search's score for an action is
`E_q[V_θ(one joint turn later)]`. The simulator contributes exactly one turn of exact mechanics;
everything else is the critic. Wang's rollouts push the leaf many plies out and re-sample the
determinization 1000–2000 times, so the *simulator* supplies most of the discrimination and the
critic only breaks near-ties. Numbers: 200 worker-seconds vs 0.0623 s; 1000–2000 determinizations
vs 4; 1000–2000 rollouts vs 277 leaves; plus his cross-decision statistic reuse (p.28).

*What would settle it in our repo.* (i) The n_det axis: S3L (n_det 16, leaf_cap 5184) exists and
is PARTIAL at 4/10 chunks on s112 — **finishing S3L is the cheapest single datapoint on this
hypothesis** and it is already pre-registered (`configs/eval/search_s3_100m.yaml`, arm S3L, read
P-L, sign-only, one lane). Note the honest prior: at 4/10 chunks it reads 0.72333 vs S3M's
0.74767 on that lane, i.e. *not* rescuing. (ii) Depth ≥2 **does not exist in code** (STATUS watch
item; `docs/search_relook/ENGINE_SEARCH_DESIGN.md` is the open design). Until depth exists,
"search doesn't work on gen 1" is a claim about depth-1 only, and the thesis gives no evidence at
depth 1 in either direction. (iii) STATUS already owes a per-decision cap for a searched ladder
object (≤5 s) — his is 10 s × 20 workers. **We have never tested search at a budget he would
recognize.**

### H2 — SELECTION RULE: his search is policy-anchored and variance-averse; ours is a hard argmax over few, noisy cells. **Rank 2 — the highest-value cheap test.**

Three mechanisms in his selector have no analogue in ours:
1. **The policy prior is inside the selection rule**, `U ∝ P[s,a]^β` with β ∈ [0,1] tunable
   (p.21). In our `rl/search/matrix.py` the policy prior appears only as tie-break D3, after the
   matrix score.
2. **The decision is max *visit count*, not max value**, and he says the reason is variance:
   "less-visited actions may have higher variance in their Q estimates" (p.22). We take D4, a hard
   argmax over the renormalized matrix score.
3. **Q is a running mean over ~1000+ samples per action.** Ours spreads 277 leaves over ≤9 of our
   actions × 6 opponent classes × 4 determinizations — single-digit leaves per cell. A hard argmax
   over single-digit-sample means is precisely the max-bias / optimizer's-curse regime.

The smoking gun is already in our own readout: **S3M flips the policy's argmax on 72.8% of
decisions** (S3_READOUT, `flip rate` 0.7277). A search that overrides a 0.789 policy on nearly
three-quarters of its decisions and lands at 0.721 is not adding information — it is adding noise
with authority. Wang's construction structurally cannot flip at that rate: an action the policy
dislikes must first *earn visits* against `P[s,a]^β`.

*What would settle it.* Cheap, offline, no new training: re-score the existing S3M decision logs
under alternative selectors and measure the flip rate as a function of the selector. Concretely
(a) a margin rule — take the search action only when the matrix margin exceeds a multiple of the
leaf-value spread, else the policy argmax; (b) a prior-blended score `score + α·log π_θ`; (c) a
visit-count analogue (allocate the leaf budget by the prior and select by allocation). All three
are edits to `matrix.py` D3/D4 and `agent.py`, need no retraining, and the flip rate is already
instrumented. **If a margin rule at flip-rate ~10–20% recovers the greedy number and beats it, H2
is the answer and H3 is not needed.**

### H3 — OPPONENT MODEL: his is the same network, unbiased and consistent; ours is a coarse classifier with a *known directional bias*. **Rank 3.**

Wang's tree is internally consistent: the value being estimated is "value of π_θ against π_θ",
the opponent in the rollouts *is* π_θ, and the critic was fitted on exactly that. Ours: the
oppact head's 6-class posterior, with `OTHER_MOVE` dropped and renormalized, and `SWITCH`
collapsed to a **uniform draw over legal bench targets** — and our own `matrix.py` docstring names
the consequence: *"uniform averages over bad switch-ins, so the search is systematically
OPTIMISTIC about our staying in (design §9)."* A systematically optimistic opponent model is a
mechanism by which more search makes a policy strictly worse: every extra leaf sharpens a biased
estimate.

Wang's Kecleon/Venomoth failure (p.33–34) is the same failure *shape* from the opposite cause —
an opponent model that under-weights the opponent's real best reply makes switching look safe.
His error is unbiased-ish noise (π_θ plays sensible moves); ours has a named sign.

*What would settle it.* S3 already has the ablation hook: `agent.py` exposes
`{"kind": "oppact_uniform"}`. But the sharper test is the switch-target law — replace the uniform
bench draw with (i) the opponent's *best* bench target under the determinization (pessimistic
bound) and (ii) the opponent policy's own switch distribution if one is available. If the sign of
P-M moves materially between optimistic and pessimistic switch targets, the opponent model is
carrying the result. This is a `matrix.py` change plus a rerun at dose M; no training.

### H4 — GENERATION: one turn of lookahead is worth much less in gen 1 than a multi-turn tree is in gen 4. **Rank 4 — testable with assets we already own.**

Gen 4 randbats is, by his own description, a **stalling** metagame — hazards, status, recovery,
weather, items, abilities — where value accrues over many turns and "both metagames intuitively
require strategizing over a long time horizon" (p.14); his own average game is 25 turns (p.15).
Gen 1 has no items, no abilities, no hazards, a compressed status set, and much of the decision is
damage-race arithmetic a good critic already encodes at the root. The marginal information in one
extra ply is correspondingly small.

*What would settle it.* **We own both sides of this comparison.** `rl/envs/gen4/`
(`ShowdownGen4-v0`) and a finished gen-4 object at 0.8788 vs SH
(`readouts/GEN4_WANG50M_READOUT.md`). Running the *same* depth-1 search stack on the gen-4 object
at dose M turns "generation" from a story into a measurement: same code, same dose, same protocol,
different generation. If depth-1 search is positive on gen 4 and negative on gen 1, H4 is real and
H1/H2 are secondary. **This is the single most informative experiment on this list that does not
require new search code.** (It does require the gen-4 determinizer and bridge; scope that before
committing.)

### H5 — LEAF-STATE DISTRIBUTION: he keeps the critic on-distribution by construction; we broke it, fixed it, and it was worth nothing. **Rank 5 — largely settled, and the settlement is a finding.**

Wang closes both off-distribution channels: the leaf state is a π_θ-vs-π_θ state, and the
determinized hidden information is withheld from the searching agent's own encoding (p.38,
§5.2.2 — "to complete this approach, we would also train a new neural network"). We opened the
second channel: S1 measured a **+0.0497 value bias at 4.5× the decision margin** from encoding
determinized opponent info the critic never saw. `det_blind` closed it (S3B), and
**P-B = −0.0088, NEG** (S3_READOUT). So on our system this channel was real and non-binding.

*What is still open.* The *other* half of the distribution question, which det_blind does not
touch: our critic is trained in self-play but the S3 leaves are one turn from **SH-generated**
game states, not self-play states. Wang never faces this because his rollout opponent is π_θ
regardless of whom he is playing. Test: measure the critic's calibration (predicted vs realized
outcome) on leaves reached from SH-vs-us states versus self-play states, using the existing
harvest machinery (`rl/search/harvest.py`, `scripts/ch3_harvest.py`). A calibration gap between
the two state populations would say the evaluator is mis-scaled exactly where the search consumes
it. Note this is *different* from the A1E ensemble arm, which changes the evaluator's variance,
not its distribution.

### H6 — HIS NETWORK WAS WEAKER IN A WAY THE SH NUMBER HIDES, so search had headroom ours does not. **Rank 6 — suggestive, and there is a real number behind it.**

The comparison our index has never drawn: **in the same generation, against the same benchmark
class, our gen-4 network alone scores 0.8788 at 50M steps (locked protocol, 3×3000, greedy) while
Wang's gen-4 network alone scores 0.786–0.85 at 150M steps.** Three times the steps, a lower
number. If that survives the comparability caveats, his +12 points from MCTS is partly "search
rescuing a weaker network" — the loss headroom above 0.786 is 21.4 points and he took 12 of them;
above our 0.78867 in gen 1, the headroom is the same size but the *reachable* part of it may not
be.

*Comparability caveats that must travel with this, and they are not small.* His SH is **patched**
(diff:3800–3822, and three SH commits in the log) and the patches make SH better; ours is stock.
Different poke-env versions. His n is unstated and unbounded; ours is 9,000 with a seed-clustered
band. His policy form (argmax vs sampled) is unstated; ours is greedy.

*What would settle it.* Nothing in our repo settles Wang's side — his checkpoint is not released
(only replays: `github.com/quadraticmuffin/pkmn-thesis-replays`, p.35). What our repo *can* do is
remove the SH-version confound in one direction: run our gen-4 object against an SH patched the
same two ways (Curse exclusion, trap-aware switching) and report both. That converts an
uncontrolled comparison into a bounded one.

### H7 — MEASUREMENT: some of the gap is that his numbers are softer than ours. **Rank 7 — cannot explain the sign, but it should widen every band we draw around his figures.**

Table 4.1 has **no n, no error bars, no stated checkpoint, no stated policy form**; his
network-alone figure is somewhere in 0.786–0.85 by his own three mutually inconsistent
presentations; ties are excluded rather than counted as non-wins; the ladder headline is a
**peak**, not an average (the average after game 100 was 1615 Elo). Our own landmine — one vs-SH
rung at n=3000 is worth ±0.02, not the binomial ±0.008 — applies with more force to a number
with no n at all. **This cannot flip a sign**: our P-M is −0.0681 with 3/3 lanes negative at
n=9,000 per arm, and no plausible measurement slack in his table turns his +0.122 into a
negative. But it does mean "he got +12, we got −7" is a comparison of a hard number against a
soft one.

*What would settle it.* Nothing — the information is not in the thesis and the code is not
released. The correct response is to widen the band we quote for his figures and to stop treating
.786 as a point estimate.

### Not on this list, and why

- **Determinization quality.** His and ours are the same construction — the stock generator's
  team-level caps and counters, pre-seeded from revealed mons, with rejection sampling on revealed
  traits (diff:253–380 vs `rl/search/determinize.py`). Count differs (H1); method does not.
- **Value scale / discounting.** Both are terminal-only ±1 with γ ≈ 1 (his 0.9999, p.43; ours 1.0)
  and both mix critic values with ±1 terminal backups on the same scale. Nothing to explain here.
- **Action-space width.** Both search over ≤9 legal actions per turn (p.23). The 494 is an output
  width, not a branching factor.
- **Chance handling as a source of *sign*.** He Monte-Carlos the real PRNG; we take the engine's
  average-damage branch plus a pre-registered 2-point roll expansion at KO boundaries
  (`rl/search/expansion.py`). Ours is lower-variance with a known Jensen-gap bias, which is a real
  difference — but `expansion.py` exists precisely because that gap was measured and repaired, so
  it belongs under H2's variance/bias framing rather than as its own hypothesis.

---

# NOT STATED IN THE THESIS — the mandatory list

Every item below was searched for in the full text and is absent. These are the reproduction
blockers and the places where any claim about Wang's search must say "unknown".

**Search hyperparameters and behaviour**
1. **The values of α and β** — the two constants governing exploration and how much the search
   trusts the policy prior (p.21). Table A.3 (p.43) contains PPO hyperparameters only.
2. **The achieved search depth**, average or maximum, at any point in a game.
3. **Any sensitivity of strength to R** (the rollout count). R is reported as an outcome of the
   time budget, never as a swept variable.
4. **Any search ablation at all** — no critic-leaf vs full-playout comparison, no
   determinization-count study, no opponent-model ablation, no α/β sweep.
5. **The state key used for the Q/N/M dictionaries** — in particular whether it includes the
   determinized hidden information. *(This matters: `a* = argmax_a N(s_0,a)` is only meaningful if
   the root key is determinization-independent, so that visits accumulate across the 1000–2000
   determinizations. The thesis never says.)*
6. **How the search handles our-side force-switch turns** (post-faint replacements, where the
   opponent does not act simultaneously).
7. **Whether the parallel workers' trees share nodes across determinizations**, and what the
   aggregator does on key collisions.
8. **The MCTS driver's source.** None of the three released forks contains the search: the
   pokemon-showdown fork provides the `>getstate`/`>load` protocol surface and the constrained
   regenerator; the poke-env fork provides state-tracking fixes and message-timing repairs (no
   `|state|`/`|load|` handling); the SB3 fork is timing instrumentation only (diff:3993–4213). The
   driver that ties them together is not published.

**Measurement**
9. **n for Table 4.1** — no sample size for any cell, including .786 and .908.
10. **Which checkpoint Table 4.1 used**, and whether the ladder agent (§4.3) is the same
    checkpoint.
11. **Whether the "NN" row plays argmax or samples** from π_θ.
12. **Any error bar, confidence interval or seed count** on any winrate in the thesis.
13. **Any reconciliation of the three network-alone numbers** — prose "roughly 85%" (p.29),
    Figure 4.1's ≈0.82–0.83 plateau, and Table 4.1's .786.
14. **A ladder result for the network alone.** Only MCTS+NN was laddered.
15. **The poke-env version** used, and the fact that `SimpleHeuristicsPlayer` was patched — the
    thesis cites poke-env [22] as if it were stock; the patches are visible only in the fork
    (diff:3800–3822).
16. **A stable ladder estimate.** 1756 Glicko-1 / 79.5% GXE / 1693 Elo are the **peak at rank 8**;
    the run's own average after game 100 was 1615 Elo, n=200 total (p.32).

**Design rationale**
17. **Any argument that the 494-way action space made search necessary or effective.** The thesis
    makes no action-space argument beyond defining it and masking it.
18. **Any treatment of simultaneous moves as a search problem.** No decoupled-UCT, no matrix game,
    no equilibrium solve; "equilibrium" appears once, in future work (§5.2.3, p.39).
19. **Any belief model.** The word does not appear; the determinizer is the game's own generator
    conditioned on observations.
20. **A discrepancy the thesis does not flag:** p.27 says the constrained set generator "forces"
    after **10 attempts**; the released code's default is **100** (diff:69–72) and its only
    in-repo caller passes **500** (diff:306–310).

---

## Appendix — the facts most likely to be quoted, with citations

| fact | value | cite |
|---|---|---|
| leaf evaluator | PPO critic head V_θ, unmodified; ±1/0 at terminals | p.21 |
| critic retrained/recalibrated for search | no; perfect-info variant explicitly requires "a new neural network" (future work) | p.38 |
| determinized info shown to own network | **no** — only to the opponent model and the server | p.38 |
| opponent model in search | the same network's policy π_θ | p.26 |
| tree policy | Q + α·P[s,a]^β·√M[s]/(N[s,a]+1); AlphaZero-like, α constant, β new | p.21 |
| backup | running mean; terminal ±1/0, else V_θ | p.21 |
| root decision rule | argmax visit count (variance argument) | p.22 |
| determinization | one per rollout, root-level, rejection-sampled on revealed species/moves/item/ability/isLead | p.26–27; diff:69–107, 253–380, 695–703 |
| rollouts per decision | 1000–2000 | p.27 |
| search parallelism | 20 workers, sync every 10 rollouts | p.27 |
| per-move budget | 10 s (timer: 150 s + 10 s/decision) | p.24 |
| tree nodes held | 2,000–15,000; pruned only by fainted count; persists across decisions | p.27–28 |
| action space | 494 identity actions, masked to ≤9 legal | p.23 |
| training | 150M steps ≈ 3M battles, 4 days, A6000 + 80 CPU workers; mirror self-play, both seats | p.24 |
| reward / γ | terminal-only ±1, ties 0; γ = 0.9999 | p.23, p.43 |
| network alone vs SH | .786 (Table 4.1) / "roughly 85%" (prose) / ≈0.82–0.83 (Fig 4.1) | p.29–30 |
| MCTS+NN vs SH | .908 | p.30 |
| MCTS+NN vs NN | .809, self-described as "inflated" | p.30, p.32 |
| ladder | n=200, avg 1615 Elo after game 100, **peak** rank 8 / 1693 Elo / 1756 ± 28 Glicko-1 / 79.5% GXE | p.32 |
| experts' self-estimated long-run winrate vs the bot | "50 or 60", 50, "slightly over 50" | p.34 |
| LR annealing | constant → stuck ~55%; annealed → 80%; decay constants hand-chosen, not tuned | p.25 |
| network negative result | recursive/hierarchical k-mon bootstrapping: "no significant improvements" | p.37 |

## Corrections owed to `docs/prior_work/README.md`

1. **:123 (ladder table).** "Wang 2024 … 1756 / 79.5%" are **peak** values at rank 8, n=200, with
   the first ~100 games being the climb; the run's own average after game 100 was **1615 Elo**.
   Our own R1/R3/R4 rows quote **final** Elo. The table currently compares his peak against our
   finals.
2. **:397–398.** "Fig 4.1 says ~0.85" is the *prose's* number; the figure itself plateaus at
   ≈0.82–0.83. There are three inconsistent presentations, not two, and the thesis reconciles
   none of them. Table 4.1's n is **not stated at all** — that belongs in the entry.
3. **:398–399.** "The only controlled LR-annealing ablation in this literature" overstates it:
   two points, no n, no seeds, no error bars, and the decay constants "were chosen after a few
   manual runs, rather than tuned" (p.25). It is a two-point anecdote, not a controlled ablation.
4. **:399.** "Curriculum negative result (§5.1.3)" mislabels it. §5.1.3 is *"Recursive" Learning*
   — hierarchical bootstrapping of (π_k, v_k) across team sizes. There is no opponent curriculum
   in the thesis.
5. **:400.** "Hyperparameters in Table A.3" should add: **Table A.3 contains no MCTS
   hyperparameters** — α, β and R appear only in prose or not at all.
6. **:469–470.** "his headline needed MCTS" is not supportable from the thesis: the network alone
   was never laddered, so there is no counterfactual. Narrow it to *"the only object Wang ever
   laddered was MCTS+NN."* The "494-way identity space is the outlier" half stands.
7. **New, and it is the reason this file exists.** The Wang entry should carry the leaf-evaluator
   line: *same PPO critic, unmodified, and the determinized hidden information is deliberately
   withheld from his own network's input — §5.2.2 says using it would require training a new
   network.*
8. **New comparability disclosure.** Wang's SimpleHeuristicsPlayer is **patched** (Curse excluded
   from the damaging-move argmax; no switching into Arena Trap / Shadow Tag — diff:3800–3822, plus
   `maybe_trapped` and `opp_remaining_mons` commits). Ours is stock. This is the same class of
   caveat the index already carries for ps-ppo's patched SH.
