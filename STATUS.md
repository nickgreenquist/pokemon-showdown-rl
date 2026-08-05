# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-05)

**DESIGN.md r6 is RATIFIED** (maintainer review; §9 recommendations D1–D7 adopted as
written — binding list in the ratification log entry). **Coding work starts: no
review gates remain.** Repo is clean and audited: post-migration cleanup executed
(~12.5 GB reclaimed, spine pruned, predecessor logs preserved in
`SESSION_LOGS_PREDECESSOR.md`), PPO audited CLEAN bit-for-bit with its one latent
bug (warm-start lr override) fixed + regression-tested. Suite: 220 passed.
Standing correction: RL is LEVEL with the BC clone (0.4607 vs 0.4530/0.4657), not
past it. Maintainer's session setting for coding work: **Opus, high effort**.

## Results (vs SH; locked: final ckpt, 1000 battles/seed, 3 seeds pooled, ties=loss)

| result | win rate |
|---|---|
| PPO 6M flat ("r512") | 0.3923 ± 0.0089 |
| PPO 6M + LR anneal | 0.4433 ± 0.0091 |
| PPO 12M flat | 0.4330 (0.425/0.424/0.450) |
| **PPO 12M + LR anneal — best RL** | **0.4607** (0.449/0.451/0.482) |
| BC clone of SH | 0.4530 recorded / **0.4657 re-scored in-repo** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |

(D2c amendment, ratified: future finals move to 3000 battles/seed, arm + control.)

## Next actions, in order (detail: HANDOFF.md this turn, then DESIGN §4/§5)

1. Code evening: Track 1 parse-free corpus measurement (+ lock its bars); Arm A
   warm-start smoke (~1 h; settle the train.py:134 guard as "fresh run"); add
   explained-variance + grad-norm logging (pre-Arm-B requirement).
2. Arm B at 6M (3-wide, ~2.9 h, maintainer terminal): terminal-cancelled faint
   shaping; pre-registration moves into its config header before launch; futility
   gate ≥ +0.009 to advance to 12M; 3000-battle finals incl. re-evaluated control.
3. Corpus chapter iff Track 1 bars clear (engineering first, GPU later per D7).
   No 24M run (D4c). Arm C parked. Open, no deadline: un-gitignore
   `prior_work/wang_fork_diffs.md`?

## Watch items

- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned
  (+81% collection). Verified present (line 111).
- PPO audit 2026-08-05: core CLEAN; lr-override bug FIXED. The train.py:134 guard
  decision (warm start = fresh run) is settled at the Arm A smoke.
- `rl/selfplay/pool.py` evicts index 1 on overflow — breaks pre-seeded pools; fix
  before any future self-play rung (recovered bug).
- P6 arms seed-UNPAIRED; per-seed cross-arm comparison meaningless. Username-salt
  fix would enable pairing (DESIGN §8) — though P3 measured pairing buys ~nothing.
- Value explained-variance NOT logged yet — lands in next-action 1c, before Arm B.
- poke-env 0.15.0: SH's setup branch is dead (upstream bug, report unfiled).
- Concurrency (ported + verified): solo ~734 steps/s; 3-wide ≈ −20%/lane
  (~553–600); 6-wide 465–506/lane; ~95% collect. Collect DECOMPOSITION is stale
  (placeholder-encoder era) — only matters if optimizing collect.
- Run-dir `meta.yaml` git_shas are old-repo SHAs — provenance via SESSION_LOGS.
- Corpus (D7): stays on the local box; pin the HF revision before any download.
