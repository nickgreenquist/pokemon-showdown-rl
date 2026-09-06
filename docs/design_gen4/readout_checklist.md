# gen4_wang50m readout — the lines the ONE commit must carry

Assembled 2026-09-06 (agent, overnight) from `configs/gen4_wang50m.yaml`,
CLAUDE.md and the standing rulings, so the readout is a fill-in against a
list, not a recall exercise. NOT a pre-reg; the header governs on conflict.
Inputs land in `results/gen4_wang50m/` via `scripts/gen4_wang50m_postfleet.sh`;
the PRIMARY sentence is printed by `scripts/gen4_wang50m_readout.py`
(`primary.json`), never composed by hand.

## Where it lands (one commit)
- RESULTS.md **§19 Addendum, <date> — gen-4 first run (JOURNEY step 3→4):
  Wang's recipe on our frozen encoder layout v0.1** — the account.
- README row (WAITS for every leg: vs-SH primary + L1 MDT 500 + L2 FP@20 +
  L3 FP@500 + L4 BC-clone 500; a missing leg = the row waits, never drops).
- STATUS.md rewritten (≤ 60 lines); SESSION_LOGS.md entry; `readouts/` file.

## The verdict block (read off the header, never decided after)
- [ ] PRIMARY: pooled 3 × 3000 vs SimpleHeuristics, final `ckpt_050000000.pt`,
      deterministic, ties as non-wins, equal-weight mean over lanes at equal
      n; per-lane values printed; n_eff == 3000 per lane; `eval/win_rate` ==
      `wins_from_returns` per lane (the reward-sign guard).
- [ ] Step-3 MILESTONE: ≥ 0.60 → M-YES / M-NO (it learns / it does not).
- [ ] Step-5 read: ≥ 0.756 ONE-SIDED → S5-MATCHED / S5-SHORT. On S5-SHORT
      **DOSE is named first** (50M per seat vs Wang's ≈ 75M; 2/3), then the
      SB3 confound, then the encoder/impl deviations.
- [ ] se provenance: binomial AND seed-clustered both printed; which one the
      band reads; ONE RUNG IS WORTH ±0.02.
- [ ] k = 3 lanes for a branch; k ≤ 2 → CELL K, descriptive only.
- [ ] **THIS RUN CREDITS NOTHING** (verbatim) — no lever, no credit line
      applied; "matched" is the only permitted strength word.
- [ ] RW-1 (threshold) and RW-4 (FP@500 scope) rulings RECORDED in the
      sidecar's `ratified_decisions` BEFORE this commit; the run started on
      a chat authorization at the recommended defaults (RW-2/3/6 baked in;
      rule 4 waived once) — say so in the addendum's first paragraph.

## Disclosures that ride the headline (each a sentence, adjacent)
- [ ] D-NET our entity trunk, not his 256/896 MLP; D-ACT our action space;
      D-ENC layout v0.1 vs his Tables A.1/A.2; D-IMPL our PPO vs SB3 (the
      residual gap partly measures SB3's implementation against ours);
      D-COLL lockstep sync vs his per-worker buffers; D-SH the SH version /
      poke-env pin; D-TIE ties as non-wins (his tie handling unknown — the
      tie rate printed); D-DOSE 2/3 of his per-seat dose.
- [ ] HIS CURVE: 0.786 is Table 4.1's NETWORK-ALONE number (MCTS+NN 0.908;
      Fig 4.1 ≈ 0.836/0.849 reads higher); his curve crossed 0.786 at ≈ 30%
      of our per-seat dose; n = 200 is §3.1.2's validation metric, Table
      4.1's digits imply n = 1000.
- [ ] Both-seat harvest: ≈ 100M rows from 50M seat-1 steps (2/3 of his
      150M); seat-2 rows carry the member's own log-prob; version_lag_max
      band; any RESUME lost ≤ one rollout of open seat-2 rows (per resume).
- [ ] `/timer on` on every seat (the orphaned-room deadlock fix,
      2026-08-31) — the RESULTS disclosure line OWED since then lands HERE.
- [ ] R0-k2: the bare suite's status at launch (green / green with the two
      documented live tests deselected — `logs/gen4_launch_seq.log`).
- [ ] D-B: realized whole-lane dStep/dWall per lane; the PROVISIONAL band
      [173, 234] re-based from the fleet's first conforming windows;
      NON-CONFORMING windows named (the clone chain ended before launch —
      say so if true); "progress is a rate, never an ETA".
- [ ] D-A anneal liveness at 5M / 25M / 50M, both groups, the (u − 1) form.
- [ ] Every gate table: R0-1..6, H1, K6, T2, T3 (PROVISIONAL bands re-based
      at 5M, the violation disclosed), D-C not actionable, D-D ~0.5 by
      construction, D-E/D-F box-level, stalls / resumes / retries per lane.
- [ ] vs-SH numbers are NOT ladder numbers; no projection either way.

## The descriptive legs (never verdict inputs; per lane AND pooled)
- [ ] L1 MDT h2h 500/lane + the MDT-vs-SH sanity row (300, `a_record`).
- [ ] L2 FP@20 h2h 250/lane — the seat SAMPLES (named); budget in every
      quote; the two standing disclosures: the equivalence test is weakly
      powered, the point estimate flatters us; FP's set file drifts ±1–2
      levels on 40 species.
- [ ] L3 FP@500 h2h 5 × 50/lane — tally = SUM of chunk records; same three
      disclosures; both budgets quoted until Q38 pins; the pin governs LATER
      runs only (`q38_pin.json`, the 2·se_diff rule ≈ ±5 points at 3 × 250).
- [ ] L4 BC-clone h2h 500/lane — teacher budget FP@20 named; the clone's own
      vs-SH n = 1000 quoted beside it; "a clone number is never style
      evidence"; the clone is an anchor, never training data (purity).
- [ ] S-SHAPE 10 rungs × 3 × 1000: the CURVE only; "flat"/"plateau" BARRED;
      MANDATORY SENTENCE: sub-50M rungs sit on the 50M power anneal and are
      not comparable to a finished run at the same step.
- [ ] Sanity rows (not legs): FP@20 vs SH 226-24-0, FP@500 vs SH 228-22-0
      (n = 250, bot-vs-bot, 2026-09-05); random / MaxBasePower if printed.

## README row wording (pattern)
`| **gen 4 — first run: Wang's recipe on our encoder (50M/seat × 3), greedy** | 0.xxxx | M-YES/NO · S5-…; MDT h2h 0.xx · FP@20 h2h 0.xx · FP@500 h2h 0.xx · clone(FP@20) h2h 0.xx |`
— a gen-4 table of its own (never a row in the gen-1 ladder), the two FP
disclosures footnoted, "credits nothing" in the caption.
