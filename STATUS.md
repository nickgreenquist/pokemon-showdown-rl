# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 7.5 (the engine port), IN FLIGHT and P0; steps 1–7 DONE
**THE GEN-4 CHAPTER IS CLOSED (2026-09-09):** step 3 MET (M-YES), step 5's exit MET
(S5-MATCHED), step 6's ladder BANKED NOT RUN, step 7 is RESULTS §19. Steps 1–2 banked
(LADDER R4: GXE 65.2 / Glicko-1 1618 ± 25 / Elo 1354, n=200).
**Everything from here is gen 1.**

## The gen-4 result (2026-09-09; RESULTS §19, readouts/GEN4_WANG50M_READOUT.md)
- **vs SH, locked protocol, 3×3000, greedy: pooled 0.8788.** Band reads the
  seed-clustered 0.00452, not the binomial 0.00344; +0.1228 over the floor = 27.2×.
  **ONE RUNG IS WORTH ±0.02.** **M-YES** and **S5-MATCHED**; **CREDITS NOTHING** —
  "matched" carries D-DOSE (2/3), D-IMPL, D-NET, D-ACT, D-ENC, D-COLL, D-SH, D-TIE.
- **Anchors** (descriptive, never verdict inputs): MDT 0.902 · FP@20 0.293 (budget named;
  weakly powered; flatters us) · FP@500 0.264 · clone(FP@20) 0.985. Every gate PASS ×3.

## JOURNEY 7.5 — the engine port (2026-09-10; full account docs/engine_port/NOTES.md)
- **A/B SPEEDUP 4.035x** (width 1, k=256 vs concurrency 8; ABBA, sd 0.0086); **2.984x
  matched** (collector alone); **3.553x at width 3**. 2.62x cross-day is RETIRED. The Node
  path is ~85% batch-1 forwards, so much of this is INFERENCE BATCHING — quote the
  PIPELINE's speedup, never the engine's.
- **THE PROFILE INVERTED:** update 25.0% of wall on Node -> **65.1% on the engine**, so
  further collector work is capped at **1.54x**. Account: docs/engine_port/SPEEDUP.md.
- **MAX-OUT:** today k=8 w=3 = 4,861 steps/s fleet; **k=256 w=6 = 9,994 = 2.06x** on
  11.3 GB of 24; best per-lane k=256 w=1 = 3,035 = 1.87x. **A lane is a SEED — width buys
  seeds/hour, never a shorter run.** 100M×3 seeds: 13.2 h at k=256 vs 48 h on Node.
- **Learner levers are COMPLEMENTS:** threads and minibatches each NEGATIVE alone, **1.51x
  crossed**; `torch.compile` 0.82x, dead. Both need a pre-reg. Scorer `ctx` factorization
  REVERTED — correct to 3e-07 but a bit-exact forward pin forbids it; needs a ruling.
- **A-1: NO VERDICT, by instruction.** Descriptive per-seed at n=12,000: s66 0.6640,
  s75 0.6925, s83 0.6555. `ratified_decisions` empty; RW-1..RW-10 all owed.

## Next actions
1. **Rule on RW-1..RW-10** (`configs/engine_a1.prereg.yaml`) — nothing about A-1 can be
   graded until the band is ruled; `scripts/engine_a1_grade.py` refuses by design.
2. **Apply the two FREE wins** — scorer `ctx` factorization (staged, tested) and an
   mmap'd team bank. Neither changes learning; both were held back only so the A/B and
   the max-out sweep would not span two builds.
3. **Anything that changes LEARNING needs its own pre-reg**: k 8→256 (staleness), the
   threads×minibatches pair (trajectory). Width 3→6 does NOT — it is free, and it is
   fleet throughput only.
4. **IDEAS after 7.5:** §4 ranked 4.1 → 4.5 → 4.3 → 4.7 → 4.2 → 4.4; §2.9's remaining
   bit-identical update wins and §5's shared trunk (19.5% of the epoch loop). SB3
   migration is CLOSED (§3 + docs/CLEANUP.md).

## Watch items
- **SUITE GREEN: 939 passed / 19 skipped, 2 min** (`-m "not live_server"`, ch3 ignored;
  port env). **No single env runs it all** — the main env lacks `pkmn_gen1`, and
  seaborn/scipy/matplotlib are undeclared. Needs a ruling.
- **The live-server "flake" was an ORDERING BUG** — poke-env draws seat names from global
  `random`, pinned by `set_seed()` first. Fixed + bounded in `tests/conftest.py`.
- **vs-SH is NEVER a ladder number**; the gen-4 ladder is banked and unrun. No projection.
- Resumes SPLIT wandb history — always `merge_history.py`, then `history_merged.csv`.
- **A pgrep guard must anchor on `bin/python`**, or it matches its own command line.
- 0.786 is Wang's NETWORK-ALONE, WEAKER cell (Fig 4.1 ≈ 0.836/0.849); dose is named first.
- **Never edit a bash script an instance is executing** — bash reads by byte offset and
  resumes into garbage. The queue re-execs from a frozen copy for this reason.
