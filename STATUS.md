# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-05)

**PORT VERIFICATION PASSED 8/8**; old-repo strip AUTHORIZED. History imported
(42 commits) and bootstrap commit `b696e85` pushed to
`github.com/nickgreenquist/pokemon-showdown-rl` (main tracks origin). P6 landed:
LR anneal CREDITED at 12M, and **RL beats the BC clone for the first time.**

## Results (vs SH; locked: final ckpt, 1000 battles/seed, 3 seeds pooled, ties=loss)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal | 0.4433 ± 0.0091 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH (same encoder+trunk) | 0.453–0.465 |
| SH-vs-SH mirror = ceiling for anything SH-derived | **0.489** |

P6 read: anneal credited at 12M by 0.003 over the line (z=2.16; seed-level Welch
p≈0.12 recorded as caveat; arms seed-unpaired). RL is past the clone, 0.028 under the
mirror ceiling — **P4's training-side gap is CLOSED**, undercutting DESIGN.md Arm A
(revision 5 banner). The §10 human-replay corpus is now the only lever whose ceiling
is not 0.489. Full corrected record: SESSION_LOGS.md 2026-08-05 P6 entry.

## In flight

- **`DESIGN.md` is the roadmap** but needs a revision pass against P6 before the team
  review means anything; do NOT implement its §4 as specified. Arms B/C unaffected.
- Git history import approved and unblocked (plan preserved in the 2026-08-05
  verification log entry).

## Next actions, in order

1. DESIGN.md revision pass vs P6; then the team review (phase placement of §10).
   P6_RESULTS.md stays until that pass is done.
2. Open, no deadline: whether to adapt doc-archaeologist here (survives in the old
   repo's git history); old milestone-1/2 run dirs are gone by flagged decision.

## Watch items

- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if ever re-cloned
  (+81% collection). Verified present in the copy (line 111).
- Annealed checkpoints cannot be warm-extended: a 12M anneal arm runs from scratch
  with `lr_anneal_steps: 12000000`.
- P6 arms are seed-UNPAIRED (flat s0/s1/s2, annealed s3/s4/s5) — per-seed cross-arm
  comparison is meaningless.
- poke-env 0.15.0 upstream bug: SH's setup branch is dead; report still unfiled.
- Throughput planning: 465–478 steps/s/lane end-to-end at 6-wide; ~95% collect — all
  headroom is in collect (GPU on the update buys ≤5%).
- Inherited backlog: decompose collect (`showdown_throughput.py a`) — measurement is
  stale (placeholder-encoder era); constraints in the 2026-08-04 sweep log entry.
- Old repo's milestone-1/2 run dirs (heur/maxbp/mix512/sp6m era) were NOT copied —
  judged superseded; flagged in the §5 report so deletion is a decision.
