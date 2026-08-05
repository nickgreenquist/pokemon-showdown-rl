# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-05)

Bootstrap complete; P6 landed (anneal CREDITED at 12M). **DESIGN.md r6 done and
awaiting team review of §9 D1–D7** — that review gates all implementation.
**Post-migration audit + cleanup done**: 61 dead configs deleted, README brought
current, doc-archaeologist agent adapted here, and the old repo's `showdown_sp6m`
self-play record RECOVERED into SESSION_LOGS (D6 amendment satisfied: self-play NOT
CREDITED at matched init+budget, Δ=−0.023, MDE≈0.14 caveat). Standing correction:
RL is LEVEL with the BC clone (0.4607 vs 0.4530/0.4657), not past it; 0.47 unmet.

## Results (vs SH; locked: final ckpt, 1000 battles/seed, 3 seeds pooled, ties=loss)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal | 0.4433 ± 0.0091 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |

## Open maintainer decisions

1. **Team review of DESIGN.md §9 (D1–D7).** Author recs: corpus measurement now
   (D1 c→d), Arm B 6M futility screen + 3000-battle eval amendment (D2c), Arm A →
   ~1 h smoke (D3b), no 24M run (D4c), no new benchmark yet (D5c), closures (D6,
   recovery already done), ladder as success metric (D7a). Arm C parked.
2. **Preservation:** predecessor's 36 capstone log entries + Phase-5 write-ups exist
   ONLY at old-repo git `5d6a604` (one rm -rf from gone). Commit an extracted archive
   here / git-bundle the old repo / accept risk. Also: un-gitignore maintainer-authored
   `prior_work/wang_fork_diffs.md`?
3. **runs/data reclaim, ~13 GB** (gitignored, irreversible; list + keep-set in the
   2026-08-05 audit log entry): intermediates 9.34 GB, wandb 2.27 GB (history.csv
   verified), migration smokes 69 MB, regenerable npz 1.5 GB.
4. **Predecessor spine prune** (DQN/SAC/connect4/mujoco code, tests, deps, figure
   scripts, assets — pyproject already says "prune together"). Note: MinAtar/CartPole
   code must survive for Arm C's spine gate; q_learning.py is unreachable already.

## Watch items

- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned
  (+81% collection). Verified present (line 111).
- Annealed checkpoints cannot be warm-extended; warm start needs the `rl/train.py:134`
  guard fix (decided at the Arm A smoke).
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix
  before any future self-play rung (recovered bug, 2026-08-05 entry).
- P6 arms seed-UNPAIRED; per-seed cross-arm comparison meaningless. Username-salt fix
  would enable pairing (DESIGN §8) — though P3 measured pairing buys ~nothing.
- Value explained-variance NOT logged — add before Arm B launches (DESIGN §5).
- poke-env 0.15.0: SH's setup branch is dead (upstream bug, report unfiled).
- Throughput planning: 465–478 steps/s/lane end-to-end at 6-wide; ~95% collect.
- `runs/showdown_scratch12m_s*` is the 12M pure SELF-PLAY arm (finals 0.3800), not
  "12M flat 0.417" — the 2026-08-04 rescue-list label is wrong (corrected in log).
