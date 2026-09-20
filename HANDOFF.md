# Handoff — R6 prep, written 2026-09-20 ~23:05Z at the maintainer's request (context clear)

**Read in this order:** this file → `STATUS.md` → `docs/proposals/R6_PREP_PLAN_2026-09-19.md`
(§0 the autopsy, §2 the fleet, §3 the order, §5 the rulings, §6 state + build specs) →
`SESSION_LOGS.md` entries `2026-09-19 (evening…)` and `2026-09-20` → the Round 5 block at the
top of `docs/IDEAS_POST_100M.md`. **Do not re-derive the plan; it is ratified. Execute it.**

**Where we are in one paragraph.** LADDER R5 is LISTED (GXE 73.9 / Glicko 1697 ± 25 / Elo
1457 vs a 1354 cutoff). The post-ladder search chapter is closed (greedy tops every search
arm, RESULTS §30). On 2026-09-19 the maintainer asked for a blunt R6 prep plan; the R5 loss
autopsy (IDEAS 2.15) showed a luck-dominated format with style parity against humans, so the
plan targets the critic's SIGNAL (outcome heads, 4.11) and the optimizer's NOISE (batch/epochs,
4.12) on the W base, with the transformer and expert iteration behind R7 gates. **On 2026-09-20
the maintainer took all six rulings as recommended ("agree with all").** Everything built since
is committed and pushed (`d11f69b..39da8f8` on main); this handoff's own commit follows.

---

## 1. WHAT IS RUNNING — check this before anything else

**The exit-gate queue** (`scripts/exit_gate_queue.sh`, relaunched 2026-09-20 22:57Z from a
frozen temp copy, `caffeinate -i -w <pid>` holding idle sleep; **the lid must stay open — a
clamshell sleep is not prevented**). Phases, each skipping if its JSON exists:

| phase | what | where | expected |
|---|---|---|---|
| GAP | `scripts/action_gap.py --battles 150 --rollouts 24` (CLEANUP L9 FIXED version) | `logs/exit_gate_r5/action_gap.log`, `results/outcome_variance/action_gap.json` + `.rows.jsonl` | started 22:58Z at 1.7 s/row → minutes |
| XSM | 2-battle smoke of the 900-iteration gumbel tree through the FP seat, throwaway pair | `results/exit_gate_r5/smoke_xsm.json` | minutes |
| XGR | greedy committee, the in-session CONTROL, n=3200 off FP@20 | `results/exit_gate_r5/xgr.json`, `logs/exit_gate_r5/xgr.driver.log` | ~1.4 h at ~1.5 s/battle |
| XTG9 | gumbel tree, `iters 900`, n=3200 | `results/exit_gate_r5/xtg9.json`, `.fp.stdout` | ~22 h at ~25 s/battle |
| READOUT | the queue prints the delta, se, z and the verdict rule | `results/exit_gate_r5/READOUT.txt`, `logs/exit_gate_r5/queue.log` "QUEUE DONE" | |

Check it:
```
tail -5 logs/exit_gate_r5/queue.log
```
```
grep -c Winner results/exit_gate_r5/xtg9.fp.stdout
```
Stalled means the `Winner` count stops moving for ~10 min or the seat's CPU time
(`ps -o time= -p <pid>` twice, 15 s apart) does not advance — never a wall-clock ETA
(CLAUDE.md landmines). **If an FP arm dies mid-run its username pair is poisoned for hours:
add a rerun pair to `configs/eval/exit_gate_r5.yaml` (e.g. `xgtg9r2seat/xgtg9r2bot`, prefix-free
against the inventory — the queue's own check will tell you) before relaunching**; the config
has no `rerun_pairs` block yet. Relaunch is the same command with GO already present:
```
nohup bash scripts/exit_gate_queue.sh >> logs/exit_gate_r5/queue.nohup 2>&1 &
```
**No training lane and no second FP block while this runs** (a wall-clock-budgeted FP@20
opponent is weakened by contention, unevenly across arms — the §30-class contamination). The
4.12 screen and the fleet wait for "QUEUE DONE". The Showdown server was up at 23:01Z;
`showdown/config/config.js` `simulator: 4` was NOT re-checked this session (rule 5).

**Also on disk, done:**
- `results/outcome_variance/action_gap.json` (the FIXED action-gap run, 23:03Z 09-20): **134 positions, `top1_is_played_frac` 1.00 (valid)**, top-1 worse than top-2 in 35.1% of positions, mean loss when wrong 0.181, **ceiling on a top-2 swap 0.0317 of win rate** (per-position rollout noise on the gap ~0.204, so single gaps are unresolved; the WINNER'S-CURSE caveat in the script's docstring applies — noise alone inflates this). Read it against the +0.02..0.05 the search blocks chase: it sits AT the credit floor, so it is neither a mechanism kill nor a licence; bank it as item 1 says, with that framing.
- `results/wavg_r5/READOUT.txt` (IDEAS 2.12 — finals 0.6013 vs averages
0.5813, n=3000 each, −0.020 at 1.58 se, UNRESOLVED; the finals stay the members).

## 2. THE SIX RULINGS (maintainer, 2026-09-20, "agree with all") — recorded in STATUS, plan §5, IDEAS, CLEANUP

1. **Loop breaker ON for the R6 ladder object.** Wired 09-19 behind `loop_breaker: true` on
   greedy/ensemble arms in `scripts/ch3_fp_h2h.py`, `scripts/ladder.py`, `scripts/ch3_eval.py`
   (`rl/common/loop_breaker.py::LoopBreakingPolicy`; `loop/*` counters in every report). It is a
   POLICY-FORM change: every R6 number that carries it says so.
2. **C6 rides R6 only if the Rust encoder port lands before the fleet**; else R6 is c6-off and
   C6 moves to R7. The engine collector REFUSES `POKEMON_RL_ENCODER_C6=1` until then.
3. **Fleet shape:** 6 lanes × 200M, W base (`l2_init_decay 0.02`, critic `value_sizes
   [1024,1024]`, k=8 engine collector), trio A = outcome heads (4.11), trio B = batch ×4 /
   epochs 2 (4.12). No width, no 300M, no LR floor, no λ change, no search on the object.
4. **R6 ladder under the split schedule** (CLEANUP L1): four sessions, different hours and days,
   its own stopping rule, in the R6 ladder pre-reg.
5. **IDEAS 2.13 leaf recalibration stays OFF.**
6. **Both R7 gates run now:** the exit-gate queue (above) and the attention BC screen (build
   item 4 below). IDEAS 4.9's fleet waits on the gate's verdict; 8.6's re-run is subsumed.

## 3. GET TO WORK — in this order

**0. Health + concurrency check (every session).** `git status` must be clean and
`ps -axo pid,etime,command | grep -i claude` must show no OTHER live session editing this tree
— on 09-19 two sessions were committing concurrently and this one waited for a clean tree.
Suite: run it in a BARE process (no encoder env vars exported into pytest; 6 tests in
`tests/test_showdown_env.py` build v1 fakes). Baseline 1240 passed / 87 skipped in
`pokemon-showdown-rl`; the engine tests need the `pkmn-engine-port` env
(`/opt/anaconda3/envs/pkmn-engine-port/bin/pytest tests/test_engine_collector.py`).

**1. Bank the two gate reads as they land** (the action gap in minutes, the tree gate in ~a day).
Every block gets a committed readout because `results/` is gitignored:
- `readouts/ACTION_GAP_R5_READOUT.md` — from `results/outcome_variance/action_gap.json` and the
  log. **Validity gate first:** `top1_is_played_frac` must be ~1.0 (a1 equals the action the
  committee played), else the run is invalid. Then the number: `ceiling_win_rate` =
  P(top-1 worse than top-2) × E|ΔQ| / 2 — compare it to the effects the search blocks chase
  (+0.02..0.05) and to the per-position rollout noise the script prints. A ceiling BELOW them is
  a MEASURED MECHANISM CEILING on gated search (rule 6's one permitted kill); ABOVE them says
  the prize is real and the nulls were about our constructions. Scope: a bound over the TOP
  TWO only. Write a RESULTS addendum (hacking run, credits nothing), update CLEANUP L9 (run),
  IDEAS 8.1/8.2 pointers, STATUS.
- `readouts/EXIT_GATE_R5_READOUT.md` — `results/exit_gate_r5/READOUT.txt` carries the verdict
  rule from `configs/eval/exit_gate_r5.yaml` (`decision_rule`): clears at ≥ +0.025 AND ≥
  2·se_diff → IDEAS 4.9 gets R7's first trio (a pre-reg then); otherwise 4.9 is closed on this
  object for R7 by a measured bound on the operator (not a small-run null). Report
  `search/ms_mean`, `tree/kl_pi_prior`, `tree/pi_top1`, `tree/argmax_moved`, `search/overrode`
  beside the win rates; both FP@20 disclosures travel; never difference against a banked
  number (the control XGR is the only comparator). RESULTS addendum, IDEAS 4.9 + 8.6 rows,
  STATUS. R0 gates are listed in the config; `G_BUDGET_REALIZED` needs ms/decision within ~2×
  of 766.6.

**2. The C6 Rust port** (ruling 2; ~half a day + the parity re-gate; work in the
`pkmn-engine-port` env only, never install into `pokemon-showdown-rl` — rule 1).
`engine/pkmn_gen1/src/encoder.rs::fill_move` (line ~185 writes `base_power/100`): add the same
seven-id table as `rl/envs/showdown.py::_c6_fixed_damage` — Seismic Toss / Night Shade 1.15,
Counter 1.0, Dragon Rage 0.56, Sonic Boom 0.26, Psywave 0.85, Super Fang 2.2 × the foe's
current HP fraction (0.5 when the foe is unknown) — and for those ids leave the type-multiplier
slot at 0 for an immunity and 1.0 otherwise; behind a flag the Python env var can drive (or a
build feature); expose `pkmn_gen1.ENCODER_C6 = True` so `rl/envs/engine_collector.py::
_check_engine_c6` passes; `pip install -e` the extension in the port env (the importable module
only changes on install — the stale-extension trap); re-run the A-1 parity harness under the
flag so Python and Rust agree bitwise on those slots (the harness's declared families);
`tests/test_encoder_c6.py` pins the Python side, `tests/test_encoder_spec.py` pins the
v2+ids+c6 hash `40646b06…`. The launcher (`scripts/monster_fleet.sh`) must EXPORT
`POKEMON_RL_ENCODER_C6=1` for the fleet lanes only once this lands.

**3. IDEAS 4.11 — the heads and the loss** (trio A; the DATA PATH is built:
`rl/envs/outcome_targets.py`, `collector.outcome_targets: true` emits `(n, 3)` rows,
`OPT_KEYS` in `rl/buffers/episode.py`, `tests/test_outcome_targets.py`). Spec, verbatim from plan
§6: `EntityDeepSetsNet(value_aux_out: int = 0)` adds `self.aux_value_head = nn.Linear(ctx_in,
value_aux_out)` on the CRITIC only (`is_policy` asserts 0; `value_sizes` is the precedent for a
critic-only kwarg shared through `trunk_kwargs`) plus `forward_with_aux(x) -> (value, aux)`;
`forward` unchanged so search leaves and evals are untouched and old checkpoints load.
`PPOAgent(aux_outcome_coef: float = 0.0)`: in `update_episodes` a loud seam
`(batch.get("outcome_targets") is None) == (coef > 0)` → error naming both the collector flag
and the hparam (the `opp_choice` precedent at `rl/agents/ppo.py` ~1453); loss `coef *
mse(aux, targets)` on the critic's minibatch pass (gradients through the critic trunk — the
point); metrics from the update: `loss/aux_outcome`, `aux_outcome/ev_survivors_own`,
`ev_survivors_opp`, `ev_hp_margin` (1 − var(resid)/var(target)). Config keys:
`agent.aux_outcome_coef: 0.1`, `agent.trunk_kwargs.value_aux_out: 3`,
`collector.outcome_targets: true`. Tests: the seam, the actor param count pinned unchanged
(`ACTOR_PARAM_CEILING` untouched), a coef-0/aux-0 golden (state_dict identical), shapes, and
one 400k smoke through the launcher with `aux_outcome/*` visible in `history.csv` before any
trio launches. Mechanism co-primary for the fleet: the by-turn r² against the rollout oracle
(`scripts/critic_calibration.py` on an `outcome_variance` run) must lift the turn-2–8 bucket.

**4. The attention BC screen** (R7's architecture gate; offline, CPU-light; can overlap the
queue if `nice`d — it is not wall-clock budgeted). `docs/prior_work/ARCH_SCREEN_SPEC.md` is the
spec: build `rl/networks/entity_attention.py` (21-token reshape inside the net, d_model 128,
2 layers, 4 heads, pre-LN, pointer head, actor ~496k params — below the 681,994 ceiling),
a `--trunk attention` option in the BC trainer, then 3 fit seeds × {entity_deepsets,
attention} on the gen-1 FP@20 tapes (`data/fp_tapes*`; the banked clone runs are `runs/bc_fp_*`),
paired, cluster-bootstrapped by battle; plus the throughput re-bench against TODAY'S trunk
(the 34.6× figure was vs the flat MLP). Clears at ≥ +0.02 agreement with the CI excluding 0 and
≤ 3× throughput loss → R7's second trio under a lifted `ACTOR_PARAM_CEILING` (a K2
structure-rung artifact). **Purity: only the architecture choice transfers; no weights fitted
on FP tapes enter a learner.**

**5. The 4.12 screen RUN** (after "QUEUE DONE"; never beside an FP arm):
```
ALLOW_ANNEAL_OVER_HORIZON=1 bash scripts/monster_fleet.sh configs/showdown_r6_batch12m.yaml 12000000 204 212
```
~2.6 h per lane two-wide. Read (mechanism only, never a win rate): `approx_kl`, `clip_frac`,
entropy, `explained_variance`, `adv_std`, `time/update_sec` at matched steps against the W
lanes' own first 12M (`runs/showdown_monster200m_w_s*/history.csv`; the schedule is matched by
construction). GO for trio B if kl ∈ [0.005, 0.06], entropy still falling, EV within 0.05 of the
W lanes at 12M; else the pre-stated fallback (epochs 4, minibatches 480, lr 2.5e-4) — both in
the config header. Do NOT set the C6 flag for the screen.

**6. The R6 fleet yaml + smokes.** Derive two configs from `configs/showdown_monster200m_w.yaml`
(the [RWL] header is inherited history; write a NEW header — the fleet's finals feed the
ladder, so it gets the full pre-reg treatment: `journey_step` named — R6 repeats JOURNEY 10/11
under the maintainer's 2026-09-20 ratification of the plan, say so — arms, R0 gates, the credit
line verbatim with the larger-of clause, the mechanism co-primaries from plan §2, the floor =
the R5 W finals re-drawn IN SESSION off FP@20, the object rule = best committee off FP@20 under
a pre-stated tie band, ENS3-A/ENS3-B/ENS6/ENS9). Trio A: `aux_outcome_coef 0.1`,
`value_aux_out 3`, `collector.outcome_targets: true`, seeds e.g. 304/312/320. Trio B: the
4.12 keys the screen confirmed, seeds 328/336/344. Distinct `seat_tag`s. C6 flag only if item 2
landed. Smokes: 400k per config through the launcher, param counts stamped (actor 626,059
unchanged), `aux_outcome/*` and `l2init/*` rising, the resume test (kill one lane, watchdog
resumes it), then launch (over 5 h → the maintainer launches; rule 4). ~50 h.

**7. Post-fleet:** the `monster_reads_offfp.yaml` pattern (same-session re-draw of the R5 W
finals as the floor, fresh prefix-free usernames), vs-SH locked protocol, the BC-clone leg, the
mechanism co-primaries, README row; then the R6 ladder pre-reg (`configs/eval/ladder_r5.yaml`
is the template) with the split schedule (CLEANUP L1) and `loop_breaker: true`, both disclosed
in every quote.

## 4. LANDMINES LEARNED THIS SESSION (all recorded in the log; carry them)

- **The engine training path uses the RUST encoder.** A Python encoder flag never reaches
  `raw["obs"]`; a lane launched with `POKEMON_RL_ENCODER_C6=1` would have stamped `c6=True` in
  `meta.yaml` while training c6-off. `_check_engine_c6` refuses it. Any future encoder change
  has TWO implementations to port and the A-1 parity harness to re-run.
- **A skip guard on file EXISTENCE skipped a real run.** A pre-fix `action_gap.json` made the
  queue skip the fixed run, and its rows file would have been resumed from. Guards must check a
  version marker; the invalid artifacts live in `results/outcome_variance/invalid_pre_L9/`.
- **Run the suite bare.** Exporting `POKEMON_RL_ENCODER_V2/IDS` into pytest fails six
  `test_showdown_env.py` tests that build v1 fakes. `--timeout` is not installed; the conftest
  bounds live tests itself.
- **Two sessions in one tree.** Check for another live Claude process and a dirty tree before
  editing; wait for its push rather than committing over it.
- **CPU beside an FP arm contaminates unevenly.** Two niced 90-s suite runs and the encoder
  gates ran beside the wavg CONTROL arm (disclosed). Keep heavy jobs off the box while an FP arm
  runs; the queues refuse to START beside one but nothing stops a job started later.
- **The lid.** `caffeinate -i` prevents idle sleep only; a closed lid ends the block.

## 5. NUMBERS TO CARRY (each traced)

- Autopsy (`scripts/replay_audit/r5_autopsy.py` over `results/ladder/replays_r5`): played-out
  win 0.19 at net luck ≤ −3 (n=52), 0.67 at 0 (12), 0.83 at ≥ +3 (40); unforced losses 18/72;
  ≥1400 opponents 0.353 (n=34); style parity (switch 0.259 vs 0.287, status 0.216 vs 0.242,
  Hyper Beam KO 0.48 vs 0.50 over all 200).
- IDEAS 2.12: 0.6013 vs 0.5813, −0.0200 at 1.58 se, UNRESOLVED (`results/wavg_r5/READOUT.txt`).
- C6 hash gate: v2+ids+c6 `40646b06…`; flag-off 828 re-verified `0be192a8…`.
- Commits this cycle: `6078f4f` plan + autopsy, `cd20c14` IDEAS Round 5, `317f845` HANDOFF stub,
  `14a4fdf` wavg_r5, `bb45abd` action_gap L9, `000c9b8` exit_gate_r5, `d13972c` C6,
  `e826adc` loop breaker, `22cfad6` 4.11 data path + engine C6 seam, `76a9194` 4.12 config +
  launcher opt-in, `39da8f8` rulings taken; suite bare 1240 / 87 / 0.

## 6. Safe to trust / needs care

- **Trust:** everything in `readouts/`, the R5 ladder figures, plan §0's autopsy table, the
  suite, the six rulings as recorded.
- **Care:** the action-gap number until its `top1_is_played_frac` self-check reads ~1.0; the
  exit-gate delta until XGR and XTG9 both finished in ONE session with no relaunch on a poisoned
  pair; any C6 claim about the ENGINE path until the port lands; the 4.12 screen's LR until the
  screen itself sets it.
