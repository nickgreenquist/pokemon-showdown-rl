# Handoff — written 2026-08-21 ~19:15 ET at the maintainer's request (context
# clear). **NOTHING IS RUNNING. Chapter 2 is COMPLETE and fully read out.
# Everything is committed AND PUSHED (`main` == `origin/main` at `5d7ebe0`).**

Read this, then `STATUS.md`. Fold anything durable into STATUS/SESSION_LOGS and
restore the empty stub.

## 1. STATE — five readouts landed in this session (08-17 → 08-21), all recorded

- **Headline: D26 CREDITED 0.71825** (unchanged). Recipe: entity arch + oppact
  aux + LR anneal.
- **D29r**: VOID by lane loss (s90 died at 35M — poke-env mask/valid-orders
  listener race); s91 0.73267 / s92 0.75133 individual, never pooled.
- **Mask-desync hardening LANDED** (9ac445d, 2-Opus reviewed): that crash class
  is dead; residuals (assert window, hangs, RESUME) in
  results/design_ch2/mask_desync_fix_memo.md. Maintainer's standing bar (memory:
  run-loss-tolerance): never lose 24+ h to one error; resume-from-checkpoint is
  the OPEN item that fully meets it.
- **D29r2** (re-run, s80-82, zero incidents): **R-A CREDIT** 0.70222 (NAMED CELL
  — no strict separation, sentence travels) / **R-B FLAT** (scale adds nothing);
  pre-declared 5-lane descriptive **0.71813 ± 0.02236** = the 12M number. The
  50M question is ANSWERED: transfers, saturates.
- **D28** (zero-info dose control, s70-74, built+frozen+2-Opus-reviewed and read
  out inside 24 h): **A1 — control 0.52240 does NOT reproduce D25** (+0.09607,
  perm 1/252, strict separation) x S-b, manipulation g 0.979 LEARNED. **NOT
  SEALED**: Delta_2 = -0.022 (< 0) and r_late 0.12 (< 0.70; per-bin q collapsed
  0.12/0.68/0.01 in bins 9-11 — a learned task stops dosing). **Caveat
  DOWNGRADED, not closed**; quote A1 only with "not sealed" + the per-bin table.
  STRUCTURAL FINDING (RESULTS §12): a control easy enough to dose is easy enough
  to learn — the seal may be unreachable for any learnable stationary task.

## 2. WHAT'S NEXT (all maintainer decisions; nothing queued)

1. **Chapter-3 direction.** Chapter-2 lines are spent (dose caveat downgraded
   with measured obstacle; 50M saturated; D27/D30 dead). Recorded candidates:
   (a) the D26 anneal surprise mechanism (+0.0998 was 3.6x its estimate — an
   unexplained lever-interaction worth understanding before inventing new
   levers); (b) the search line (DESIGN §8 D8/D9, unratified — training-compute
   saturation is exactly what re-opens inference-compute); (c) the §13/250M
   ruling (R-B FLAT + the 5-lane descriptive argue RETIRE on futility — my
   recommendation on record). Any of these = a fresh 2-Opus design round
   (memory: design-decisions-two-opus).
2. **Standing contradictions/items**: DESIGN §8 D7(a) vs CLAUDE.md ladder-eval
   (at a stable ~0.72 the GXE question is as answerable as it will ever be);
   resume-from-checkpoint (design on request); §13(1) wording ruling only
   matters if 250M stays alive.

## 3. OPS STATE

- No lanes running; server up on :8000 (simulator 4, since Aug 6). No crons, no
  monitors (all session-scoped and deleted/dead — re-arm nothing until a launch).
- Seeds: 70-74, 80-82, 90-92 burned; 75/76, 83/84, 93/94 held; 66/67 held; 68
  used for the D28 smoke (dead run dir, ignorable). Ledger: chapter-2 realised
  ~11 ld (D29r 4.2 + D29r2 4.6 + D28 2.2).
- **Backups**: every results/* only-copy incl. d28, d29r2, design_ch2 (memos,
  reviews x6, z1_2_frozen.json, dose bins) is in
  ../pokemon-showdown-rl-d25-backup-20260815/.
- Suite: 384 passed / 17 skipped at 5d7ebe0 (7 zeroinfo tests run via their
  subprocess re-runner; the anneal-test env-var skip landmine is unchanged).

## 4. LANDMINES THIS SESSION ADDED (beyond CLAUDE.md's list)

- **Watch crons are SESSION-SCOPED** — they died with every context clear;
  re-arm after restart when lanes are running (this cost nothing this time
  because the maintainer handed back promptly).
- **Grader attestation catches transcribed constants** — D28's R1 per-seed
  values were wrong from memory and attest() caught them; never trust doc-quoted
  per-seed numbers, always re-derive from the finals JSONs.
- **A 40k smoke's dose/entropy stats are NOT band-comparable to 1M-bin
  medians** (two false alarms avoided: labelled_frac 0.849 and F-HIGH — both
  fine at bin scale). Compare same-window-to-same-window (D25's own first-40k).
- **poke-env `echo ===` zsh glob landmine still bites in compound commands**;
  quote or use "SEP".
- **`results/design_ch2/scripts/z1_2.py` + z1_2_frozen.json are the frozen D28
  task definition** — rl/networks/zeroinfo.py asserts module==JSON in tests;
  never edit one without the other.
