# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-05)

Bootstrap complete (port verification 8/8; history pushed). P6 landed: LR anneal
CREDITED at 12M. **DESIGN.md revision 6 is DONE** — rewritten against P6, hardened by
three independent Opus review passes (experimental design / strategy / fact-check),
open forks turned into the decision list §9 D1–D7. **Correction recorded: RL is LEVEL
with the BC clone, not past it** — port check 8 re-scored the clone at pooled 0.4657
(vs 0.4530 recorded, ~1σ), and P6's pre-registered "past the teacher" mark (pooled
≥ 0.47) was not reached.

## Results (vs SH; locked: final ckpt, 1000 battles/seed, 3 seeds pooled, ties=loss)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal | 0.4433 ± 0.0091 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |

## In flight

- **Team review of DESIGN.md §9 (D1–D7) is the next gate.** Do not implement any arm
  before it concludes. Author recs: corpus measurement now (D1 c→d), Arm B at 6M with
  futility screen + 3000-battle eval amendment (D2c), Arm A retired to a ~1 h smoke
  (D3b), no 24M run (D4c), no new benchmark yet (D5c), closures + sp6m recovery (D6),
  ladder as success metric (D7a). Arm C parked (3-atom return; nothing to model).

## Next actions, in order

1. Maintainer reads DESIGN.md §9; team review settles D1–D7.
2. If D1(c) ratifies: Track 1 parse-free afternoon (six checks; provisional bars in §4).
3. Open, no deadline: adapt doc-archaeologist from the old repo's git history; recover
   sp6m self-play numbers from the old repo's retained docs (D6 amendment).

## Watch items

- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if ever re-cloned
  (+81% collection). Verified present (line 111).
- Annealed checkpoints cannot be warm-extended; any warm start needs the
  `rl/train.py:134` guard fix first (design decision taken at the Arm A smoke).
- P6 arms are seed-UNPAIRED (flat s0/s1/s2, annealed s3/s4/s5) — per-seed cross-arm
  comparison is meaningless. Username-salt harness fix would enable pairing (DESIGN §8).
- Value explained-variance is NOT logged — must be added before Arm B launches (§5).
- poke-env 0.15.0: SH's setup branch is dead (upstream bug, report unfiled) — every
  vs-SH number is against this build.
- Throughput planning: 465–478 steps/s/lane end-to-end at 6-wide; ~95% collect — all
  headroom is in collect. Inherited backlog: decompose collect (measurement stale).
- P6_RESULTS.md deleted 2026-08-05 as pre-flagged (durable record: SESSION_LOGS P6
  entry + DESIGN r6). Old milestone-1/2 run dirs remain gone by flagged decision.
