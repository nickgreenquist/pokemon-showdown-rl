# The expert-iteration gate — is the gumbel tree at 900 iterations a policy-improvement operator on the R5 committee?

**STATUS: READ 2026-09-21T22:22Z — CLEARS. XTG9 0.6184 vs XGR 0.5866 (n=3200 each), delta +0.0319, se_diff 0.0122, z +2.61; every R0 gate PASS, G2 agrees exactly on both arms. Every number below is computed by `scripts/exit_gate_readout.py` from the arm JSONs, the Foul-Play stdouts and the runner logs (`results/exit_gate_r5/readout.json`). Credits nothing: a gate on an operator; it licenses a PRE-REG for IDEAS 4.9 as R7's first trio, not a fleet.**

`configs/eval/exit_gate_r5.yaml`, `scripts/exit_gate_queue.sh` (relaunched 2026-09-20
22:57Z from a frozen copy at `39da8f8`, `caffeinate -i` held). Phases: GAP (the action gap,
RESULTS §33) → XSM (a 2-battle smoke of the tree through the FP seat) → XGR (the greedy
committee, the in-session CONTROL, n=3200) → XTG9 (the gumbel tree, `iters 900`, n=3200) →
the queue's own readout. R7's first gate (R6 prep plan §4); decides IDEAS 4.9 (expert
iteration) for R7. Off FP@20 — both disclosures travel with every number: the equivalence
test is weakly powered, and the point estimate flatters us. **Credits nothing** (a gate on
an OPERATOR, not a lever credit).

## The rule, verbatim from the config

- primary: XTG9 minus XGR, off FP@20, n=3200 per arm, same session, control first
- clears: delta >= +0.025 AND >= 2*se_diff -> the gumbel tree at 900 iterations IS a policy-improvement operator on this object; IDEAS 4.9 gets R7's first trio on the tree vehicle (a pre-reg then, with a mechanism co-primary that is not EV).
- does_not_clear: otherwise -> at the strongest affordable budget the expert is not measurably better than the student (a +0.025 improvement is excluded at 2 se), so there is no expert to iterate on; 4.9 is closed on THIS object for R7 -- a measured bound on the operator, not a small-run null (rule 6). It reopens only with a different expert (a different vehicle or budget), never by re-running this one.
- also recorded: search/ms_mean (the price), tree/kl_pi_prior, tree/pi_top1, tree/argmax_moved (the expert's shape), the realized change rate (search/overrode)
- comparator (the same tree config's screen, RESULTS §32, n=40 — not a win-rate read): ms/decision 766.6, argmax_moved 0.159, pi_top1 0.773.

## R0 gates (each checked at readout; the evidence line quoted)

- `G_EXPERT_REPORTED` — XTG9 reports tree/kl_pi_prior, tree/pi_top1, tree/argmax_moved and search/ms_mean; absent means the counters did not survive the seat path and the read says nothing
- `G_BUDGET_REALIZED` — search/ms_mean on XTG9 is within ~2x of the screen's 766.6 ms; far below means the iters knob did not reach the tree
- `G_CONTROL_FIRST` — XGR's json predates XTG9's (CLEANUP L6)
- `G_SESSION` — no difference against any banked number; the delta is XTG9 - XGR only
- `G_TIES` — ties are non-wins and are reported beside n

## What has landed

- XGR greedy control: **0.5866** (n=3200, ties 2); finished 2026-09-21 00:35Z. Beside the banked greedy reads (0.5765 n=4500; 0.6050 in §30's block; 0.5818
  pooled n=6500) it sits inside the cross-session spread; it is the ONLY comparator for XTG9
  (never difference against a banked number).
- XSM smoke (2 battles, throwaway pair, 2026-09-20 23:04–23:06Z): {"battles_requested": 2, "battles_finished": 2, "our_wins": 0, "foulplay_wins": 2, "our_win_rate": 0.0, "foulplay_win_rate": 1.0, "declared_search_time_ms": 20, "max_concurrent_live_battles": 1, "search/ms_mean": 844.3347255632814, "tree/argmax_moved": 0.17647058823529413, "tree/kl_pi_prior": 1.8847149622092354, "tree/pi_top1": 0.7341666666666667}.
  Its ms/decision is the first `G_BUDGET_REALIZED` witness (766.6 × ~2 is the bound).
- XTG9 launched 2026-09-21 00:36Z; 12 battles by 00:42Z and 1,574 by 11:12Z (~24 s/battle,
  the search seat holding ~a full core) → expected to finish ~22:30Z 2026-09-21.
- XTG9 finished 2026-09-21T22:22Z: **0.6184** (n=3200, ties 0); 21.8 h at 24.48 s/battle, mean turns 29.4; `relaunches 0`, `crash_forfeits 0` (`xtg9.runner.json`); the FP exit was the normal end of the run.

## Results (computed by `scripts/exit_gate_readout.py` at readout; `results/exit_gate_r5/readout.json`)

| arm | win rate | n | ties | search/ms_mean | tree/kl_pi_prior | tree/pi_top1 | tree/argmax_moved | search/overrode |
|---|---|---|---|---|---|---|---|---|
| XGR (greedy control) | 0.5866 | 3200 | 2 | — | — | — | — | — |
| XTG9 (tree@900) | 0.6184 | 3200 | 0 | 771.4 | 1.6688 | 0.762 | 0.176 | 0.1098 (11007/100217) |

delta (XTG9 − XGR): **+0.0319**; se_diff (unpaired two-proportion, 3200 vs 3200): 0.0122; z: +2.61. Rule: delta >= +0.025 AND >= 2·se_diff (2·se_diff = 0.0245) → MET.
Realized change rate (docs/landmines.md: `search/override_rate` is `None` by construction on a tree arm): flips/(decisions − placeholder_skips) = 11007/100217 = 0.1098; overrides on the same denominator = 0.1098; decisions 106497, skips 6280.

R0 gates (evidence from the JSONs and the runner logs):
- `G_EXPERT_REPORTED` — **PASS**: {"missing": [], "values": {"tree/kl_pi_prior": 1.6688240338622429, "tree/pi_top1": 0.7623653046740342, "tree/argmax_moved": 0.17552468822873366, "search/ms_mean": 771.3904358728741}}
- `G_BUDGET_REALIZED` — **PASS**: {"ms_mean": 771.3904358728741, "comparator_ms": 766.6, "ratio": 1.0062489380027055, "note": ""}
- `G_CONTROL_FIRST` — **PASS**: {"control_started": "2026-09-20T23:06:52Z", "tree_started": "2026-09-21T00:36:09Z", "control_json_mtime_before_tree": true}
- `G_SESSION` — **PASS**: {"prereg_sha256_equal": true, "note": "the delta is XTG9 - XGR only; no banked number enters"}
- `G_TIES` — **PASS**: {"ties": {"XGR": 2, "XTG9": 0}, "note": "our_win_rate = our_wins / battles_finished on both arms (ties are non-wins)"}

G2 (two tallies agreeing, never a subtraction — the seat's JSON against Foul Play's own `Winner:` lines):
- XGR: **AGREE** seat [1877, 1877], bot [1321, 1321], ties [2, 2], FP total 3200 vs battles_finished 3200
- XTG9: **AGREE** seat [1979, 1979], bot [1221, 1221], ties [0, 0], FP total 3200 vs battles_finished 3200

Launch shas: control `e6cc5ddedda9f9f99f6beb967bc502b86dd8fd21`, tree `5dd27dfcac5368f0cc98f6606f69dfe9509e240a` — the block SPANS COMMITS (each arm imports the working tree at its launch); diff under rl/ and the seat script:
```
rl/agents/ppo.py               | 141 ++++++++++++++++++++++++++++++++++++++++-
 rl/envs/engine_collector.py    |  22 +++++--
 rl/envs/engine_tables.py       |  20 +++++-
 rl/networks/entity_deepsets.py |  65 ++++++++++++++++++-
 rl/train.py                    |  33 ++++++++++
 5 files changed, 269 insertions(+), 12 deletions(-)
```

Verdict under the pre-reg's rule, verbatim:
- **CLEARS** — delta >= +0.025 AND >= 2*se_diff -> the gumbel tree at 900 iterations IS a policy-improvement operator on this object; IDEAS 4.9 gets R7's first trio on the tree vehicle (a pre-reg then, with a mechanism co-primary that is not EV).

Disclosures: FP@20's equivalence test is weakly powered and its point estimate flatters us; binomial se governs (one arm per cell); never differenced against a banked number.

## VERDICT

**CLEARS.** +0.0319 meets both legs of the pre-stated rule (≥ +0.025; ≥ 2·se_diff = 0.0245); z +2.61.
The verdict text, verbatim from the pre-reg: *delta >= +0.025 AND >= 2*se_diff -> the gumbel tree at 900 iterations IS a policy-improvement operator on this object; IDEAS 4.9 gets R7's first trio on the tree vehicle (a pre-reg then, with a mechanism co-primary that is not EV).*

What it says: at the strongest affordable budget (`iters 900`, 771 ms/decision, 1.01× the n=40 screen's
766.6) the gumbel tree, deciding from its own visit distribution with the R5 committee as prior and evaluator, is
measurably better than the committee it searches — the first search result in this project above greedy at 2 se
(§26's +0.021 was 0.96 se; §30's ungated matrix arms were COSTS). The tree changed 11.0% of searched decisions
(11007/100217; ~3.4 per battle of ~29 turns); §30's override regression on the D5-gated matrix
search (−0.48 win rate per unit change fraction) would predict -0.053 at this rate, and the tree reads the
opposite sign — the VEHICLE changed, not the dose (a mechanism remark, not a measurement of §30's arms).

What it does not say: nothing about the ladder object (ruling #3 stands — R6's object is greedy with the loop
breaker); nothing about a smaller budget (8.6's 100 / 300 rungs are unmeasured at this n); nothing across sessions
(one rung is ±0.02; this block is one session, control first, within-session floor 0.0020). It licenses IDEAS 4.9's
PRE-REG for R7's first trio — a mechanism co-primary that is not EV (§21), the dose as a sampled fraction of
decisions (4.9 item iii: the expert costs ~771 ms against a ~10 ms greedy decision), and its own re-drawn control.

## What may NOT be said (fixed before the number)

- A "does not clear" is a MEASURED BOUND on THIS operator at THIS budget on THIS object
  (rule 6's permitted kill shape), not a statement about search in general and not about
  a different expert; it reopens only with a different vehicle or budget.
- XTG9's number is never differenced against a banked greedy number; XGR is the comparator.
- The tree's shape statistics (`tree/*`) describe the expert; they are not the verdict.
- One rung is worth ±0.02 across sessions (CLAUDE.md); this block is ONE session, control
  first, and its within-session floor is the D1O/DUM replicate spread (0.0020, §30).

## Contamination ledger (what ran beside each arm, all `nice -n 19`; owed by CLAUDE.md)

Beside XGR (2026-09-20 23:07Z – 2026-09-21 00:35Z):
- 23:43Z–23:48Z: three pytest runs (13 + 173 + 96 tests, ~45 s total, one process).
- 23:53Z: the attention screen's dataset build (six FP tapes re-embedded through poke-env,
  ~1 min, one process).
- 23:54Z–23:58Z: the C6 port's `cargo test --lib` (22 s) and `pip install -e` rebuild (32 s),
  two build jobs under `taskpolicy -b`; then P-1 parity ×3 (~25 s), the port tests (8 s), the
  collector suite (28 s).
- 00:08Z–00:35Z: the attention screen's fits, ONE at a time, single-threaded: entity_s0
  (00:08–00:12), attention_s0 (00:13–00:28), entity_s1 (00:28–00:30), attention_s1 (00:30→).
- 00:10Z–00:12Z: the full bare suite (1250 tests, ~100 s, one process).
Beside XTG9 (2026-09-21 00:36Z →):
- 00:36Z–01:05Z: the remaining fits, single-threaded: attention_s1 (→00:46), entity_s2
  (00:46–00:48), attention_s2 (00:48–01:04); the throughput bench (~1 min at 01:05Z) and the
  readout script.
- 01:10Z–01:12Z: the full bare suite on the merged main (1258 tests, 105 s, one process).
- After 01:12Z: test runs of a few seconds each (≤ 40 tests) through 14:00Z; 14:31Z–14:50Z six new tests in
  four runs and one ~2 s `grep` over `xgr.fp.stdout`; ~18:20Z–18:45Z two read-only Opus review agents (single-file
  pytest runs of 6 + 7 + 2 + 7 tests, `python -c` layout probes); 20:13Z the full bare suite (1279 tests, 106 s,
  one process); 20:14Z–20:17Z a few single-file test runs. Nothing else; no training lane beside either arm.
Box: 14 cores; load average 2–4 throughout; the FP process runs at normal priority. The
contamination is one-sided (heavier beside the control than beside the tree arm) and small; it is
disclosed, not corrected for. Launch shas: the two arms launched from different commits (the table
above prints the diff under `rl/` and the seat script): the 4.11 heads and the C6 port landed between
them; neither touches `rl/search/`, both arms ran c6-OFF (`encoder_env`), and a head-off build's forward
is bit-identical by test (`tests/test_outcome_heads.py`), so the seat's program was the same search on the
same network.
