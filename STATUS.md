# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-05)

Bootstrap complete; P6 landed (anneal CREDITED at 12M). **DESIGN.md r6 done and
awaiting team review of §9 D1–D7 — that review gates all implementation.**
Post-migration cleanup EXECUTED in full: predecessor's 36 capstone log entries
preserved (`SESSION_LOGS_PREDECESSOR.md`), ~12.5 GB reclaimed (runs/ 12→1.0 GB,
data/ 3.6→2.1 GB; finals + eval JSONs + history.csv all retained), predecessor
spine PRUNED (ALGOS = {random, ppo}; Connect-4 survives only as the self-play
tests' two-player fixture; suite 318 → 219 green). sp6m self-play record
recovered (D6 satisfied: NOT CREDITED at matched init+budget, Δ=−0.023,
MDE≈0.14). Standing correction: RL is LEVEL with the BC clone (0.4607 vs
0.4530/0.4657), not past it; the pre-registered 0.47 mark was unmet.

## Results (vs SH; locked: final ckpt, 1000 battles/seed, 3 seeds pooled, ties=loss)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal | 0.4433 ± 0.0091 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |

## Next actions, in order

1. **Team review of DESIGN.md §9 (D1–D7).** Author recs: corpus measurement now
   (D1 c→d), Arm B 6M futility screen + 3000-battle eval amendment (D2c), Arm A →
   ~1 h smoke (D3b), no 24M run (D4c), no new benchmark yet (D5c), closures (D6 —
   recovery done), ladder as success metric (D7a). Arm C parked (3-atom return).
2. If D1(c) ratifies: Track 1 parse-free afternoon (six checks; provisional bars
   in DESIGN §4).
3. Small, open, no deadline: un-gitignore maintainer-authored
   `prior_work/wang_fork_diffs.md`? Optional `pip install -e ".[dev]"` refresh to
   sync the env with the pruned pyproject (tests pass either way).

## Watch items

- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned
  (+81% collection). Verified present (line 111).
- Annealed checkpoints cannot be warm-extended; warm start needs the
  `rl/train.py:134` guard fix (decided at the Arm A smoke).
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix
  before any future self-play rung (recovered bug).
- P6 arms seed-UNPAIRED; per-seed cross-arm comparison meaningless. Username-salt
  fix would enable pairing (DESIGN §8) — though P3 measured pairing buys ~nothing.
- Value explained-variance NOT logged — add before Arm B launches (DESIGN §5).
- poke-env 0.15.0: SH's setup branch is dead (upstream bug, report unfiled).
- Throughput planning: 465–478 steps/s/lane end-to-end at 6-wide; ~95% collect.
- Run-dir `meta.yaml` git_shas are old-repo SHAs, unresolvable here — run
  provenance lives in SESSION_LOGS narrative only.
- If Connect-4 should be fully gone (it is now only the self-play test fixture),
  the cost is a two-player dummy env + rewriting 49 self-play tests.
