# The expert-iteration gate — is the gumbel tree at 900 iterations a policy-improvement operator on the R5 committee?

**STATUS: PENDING — XTG9 (the tree arm) is running; this file carries everything that is
already fixed and is FILLED when `results/exit_gate_r5/READOUT.txt` lands. Nothing below is
a verdict until the "VERDICT" section is written.**

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

## Results (FILLED AT READOUT from `results/exit_gate_r5/READOUT.txt` and the two JSONs)

| arm | win rate | n | ties | search/ms_mean | tree/kl_pi_prior | tree/pi_top1 | tree/argmax_moved | search/overrode |
|---|---|---|---|---|---|---|---|---|
| XGR (greedy control) | 0.5866 | 3200 | 2 | — | — | — | — | — |
| XTG9 (tree@900) | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING | PENDING |

delta (XTG9 − XGR): PENDING; se_diff (unpaired two-proportion, 3200 vs 3200 ≈ 0.0124 at
p≈0.58): PENDING; z: PENDING.

## VERDICT

PENDING.

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
- After 01:12Z: test runs of a few seconds each (≤ 40 tests), nothing else.
Box: 14 cores; load average 2–4 throughout; the FP process runs at normal priority. The
contamination is one-sided (heavier beside the control than beside the tree arm, and within
the tree arm's first 30 min only) and small; it is disclosed, not corrected for.
