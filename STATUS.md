# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 7.5 (the engine port), IN FLIGHT and P0; steps 1–7 DONE
**THE GEN-4 CHAPTER IS CLOSED (2026-09-09):** step 3 MET (M-YES), step 5's exit MET
(S5-MATCHED), step 6's ladder BANKED NOT RUN, step 7 is RESULTS §19. Steps 1–2 banked
(LADDER R4: GXE 65.2 / Glicko-1 1618 ± 25 / Elo 1354, n=200).
**Everything from here is gen 1.**

## The gen-4 result (2026-09-09; RESULTS §19, readouts/GEN4_WANG50M_READOUT.md)
- **PRIMARY vs SH, locked protocol, 3×3000, greedy: pooled 0.8788.** se binomial 0.00344,
  seed-clustered 0.00452 — **the band reads 0.00452**; +0.1228 over the floor = 27.2×.
  **ONE RUNG IS WORTH ±0.02.**
- **M-YES** (≥ 0.60) and **S5-MATCHED** (≥ 0.756). **CREDITS NOTHING** — "matched" is the
  only permitted strength word and carries D-DOSE (2/3), D-IMPL, D-NET, D-ACT, D-ENC,
  D-COLL, D-SH, D-TIE in the same sentence.
- **Anchors** (descriptive, never verdict inputs): MDT 0.902 · FP@20 0.293 (budget named;
  weakly powered; flatters us) · FP@500 0.264 · clone(FP@20) 0.985. **Every gate PASS ×3**;
  S-SHAPE climbs through 25M then spans 0.017 — one rung is ±0.02. Detail: RESULTS §19.

## JOURNEY 7.5 — the engine port (2026-09-10; full account docs/engine_port/NOTES.md)
- **A/B SPEEDUP 4.035x** — same box, same hour, ABBA, 1M/arm, width 1, engine k=256 vs
  async concurrency 8. Per-pair 4.041/4.028, sd 0.0086 (node 21.8 min/run, engine 5.4).
  **The 2.62x cross-day figure is RETIRED.** Big caveat that travels with it: the Node
  path does batch-1 forwards for ~85% of its ceiling, so much of this is INFERENCE
  BATCHING, not the Rust engine. Quote it as the PIPELINE's speedup.
- **THE PROFILE INVERTED:** update is 25.0% of wall on Node, **65.1% on the engine**
  (3 lanes each side, both 3-wide). Further collector work is capped at **1.54x**.
- **MAX-OUT** (idle, k x width): today's k=8 w=3 = 4,861 steps/s fleet; **k=256 w=6 =
  9,994 = 2.06x** on 11.3 GB of 24. Best per-lane k=256 w=1 = 3,035 = 1.87x. **A lane is
  a SEED — width buys seeds/hour, never a shorter run.**
- **Learner levers are COMPLEMENTS:** threads and minibatches are each NEGATIVE alone,
  **1.51x crossed** (7.73 → 5.11 s update). `torch.compile` 0.82x, dead.
- **Free wins, not yet applied:** scorer `ctx` factorization (~26% of the epoch loop,
  verified 3e-07) and an mmap'd team bank (0.53 GB/lane duplicated today).
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
- **vs-SH is NEVER a ladder number**; the gen-4 ladder is banked and unrun. No projection.
- Resumes SPLIT wandb history — always `merge_history.py`, then `history_merged.csv`.
- **A pgrep guard must anchor on `bin/python`, not a bare module name:** the FLEET DONE
  auto-chain matched its OWN command line and would have refused the schedule forever.
- 0.786 is Wang's NETWORK-ALONE, WEAKER cell (Fig 4.1 ≈ 0.836/0.849); dose is named first.
- **Never edit a bash script an instance is executing** — bash reads by byte offset and
  resumes into garbage. The queue re-execs from a frozen copy for this reason.
