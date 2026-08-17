# Handoff — written Monday 2026-08-18 ~15:30 ET, mid-run. **D29r IS RUNNING: 3 lanes,
# seeds 90-92, ~34 h left. Wednesday-morning readout. Everything else is committed.**

Read this, then `STATUS.md`. Tree clean through the last commit; **NOT pushed** (several
commits pending — the maintainer reviews and pushes, never the assistant).

---

## 1. WHAT IS RUNNING RIGHT NOW (do not disturb)

**D29r — the credited stack at 50M** (`configs/showdown_sp_stack50m.yaml`, ratified by
the maintainer launching it 2026-08-18 ~10:45 ET; the launch itself accepted the two
DESIGN2 §2 overrides flagged in the header):
- 3 lanes 3-wide alone: `showdown_sp_stack50m_s90/91/92`, entity arch + oppact aux +
  `lr_anneal_steps: 50000000`.
- Health at 15:11 Mon: all alive, 6.0M steps, warm rate 352–364 steps/s (below the
  375–395 expectation band, ABOVE the record line 330 and stop line 275 — no action
  per the letter; cost drifts ~4.5 → ~5.0 lane-days).
- **ETA: ~01:00–02:00 Wednesday.** Finish = all three at `ckpt_050000000.pt` and
  processes exited.
- **The 5-hourly health loop and the monitor DIED with the previous session** (session-
  scoped). RE-ARM on reactivation: `/loop 5h` with the lane-health prompt, checks =
  3 processes alive (`ps aux | grep -o "showdown_sp_stack50m_s9[0-9]" | sort -u`),
  latest ckpt fresh (<~30 min; rungs land every ~23 min), warm rate = Δstep/Δwall from
  ckpt mtimes (NEVER `time/steps_per_sec`, overstates 14.5%).

## 2. AT READOUT — the exact procedure (all pre-registered; do not improvise)

1. Confirm all 3 lanes at 50M, processes exited, `checkpoint.pt` final.
2. Finals, sequential, locked protocol (~4–5 min each):
   `env POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 <envpy> scripts/eval_checkpoint.py
   runs/showdown_sp_stack50m_sN/checkpoint.pt --episodes 3000 --out results/d29/final_sN.json`
   for N in 90 91 92 (mkdir results/d29 first).
3. `<envpy> scripts/d29_grade.py` — it ATTESTS both frozen comparators from disk,
   runs the hard D-A LR trace (2M/10M/26M/50M ckpts × 3 lanes, three param groups),
   applies the lane-failure rule (<3 survivors VOIDS), prints both reads' cells.
4. Verdict routing is the header's branch table VERBATIM. Key rules: R-A (vs struct50m
   0.580222) is PRIMARY; bar by realised s_T (0.6675 floor → 0.7037 at 50M-like
   spread; kill-point s_T ≥ 0.092). R-B (vs D26 0.718250) is the scale read — it may
   NOT satisfy §13(1), it MAY retire the 250M line on futility. The headline stays
   D26's 0.71825 UNLESS R-B also credits (then the 50M number leads). Falsifier-class
   = pooled < 0.6185 (composes with the cell; cannot co-fire with B1; B2∧F is a named
   cell — both sentences, neither suppressed).
5. Also record: K6/D-C/D-D in-run gates off history.csv (extract first:
   `scripts/extract_history.py <run_dir>`); aux/loss vs the pre-registered
   pool-hardening prediction (expected plateau ABOVE 0.81; diagnostic ceiling 1.40);
   the new aux/trunk_norm_delivered + aux/clip_scale columns exist in these lanes only.
6. Record everywhere in ONE commit: SESSION_LOGS entry (numbers exact), STATUS rewrite,
   README table row, RESULTS.md §10 addendum. Back up `results/d29/` to
   `../pokemon-showdown-rl-d25-backup-20260815/` (results/ is gitignored — only copy).
7. **Maintainer decisions at readout, not the assistant's:** the §13(1) wording ruling
   on a B1 ("credited STACK" vs "credited lever"); push timing.

## 3. STATE OF EVERYTHING ELSE (all committed; see SESSION_LOGS 08-16..08-18)

- **Headline: D26 CREDITED 0.71825** (4×3000, delta +0.0998 vs D25, floor bar, perm
  1/126, all gates; RESULTS.md §9). Recipe: entity arch + oppact aux + LR anneal =
  0.3996 → 0.5509 → 0.6185 → 0.71825. WHY the anneal tripled its estimate is OPEN.
- **D18 audited post-hoc: implementation CLEAN, null upheld** — do not revisit.
- **Chapter 2 (`DESIGN2.md` r2 + readout note, PROPOSED):** D30 soft-labels KILLED at
  zero lanes (Z3-3: +1–2% of head signal — cannot clear any bar); Z1-1 offline screen
  VOID (proxy≠live; D28 dose certified in-run only, 6M abort threshold 0.35 measured);
  **D28 (zero-info control, ~2.2 ld) is the queued next arm after D29r** — its build
  is specified in DESIGN2 §1 + `results/design_ch2/` memos (synthetic pointer task
  with ONE shared w_move — the per-slot version is unrepresentable by the head).
- **Patches landed:** train.py refuses 0 < lr_anneal_steps < total_steps (the 38M-
  steps-at-lr-0 trap); `_aux_gradient` returns delivered dose + clip scale.
- **Process docs (ONLY copies, gitignored):** `results/design_ch2/` — 2 design memos,
  2 chapter reviews, 2 D29r reviews, Stage-0 JSONs. Backed up 08-17/08-18 along with
  struct50m_finals and d25 (both had been MISSING from the backup).
- Ledger: chapter-1 spent (~19.7/20). D29r is on a maintainer-authorized new tranche
  (~5.0 ld realised). Seeds: 90-92 burning, 93/94 held, 70-86 reserved per DESIGN2 §5.
- Standing maintainer items: the DESIGN §8 D7(a) vs CLAUDE.md ladder-eval
  contradiction (at 0.718 the GXE question presses harder); §13 is PROPOSED with three
  preconditions; the unexplained anneal surprise is worth a mechanism look someday.

## 4. LANDMINES FROM THIS SESSION — do not rediscover

- **Handed-over commands: the maintainer must copy ONLY the command line, not the
  ``` fence lines** — pasted fences execute the command inside backtick-substitution
  and then try to run its output ("zsh: command not found: SELFTEST").
- **Long background shells get killed by the harness** — use a persistent Monitor for
  watch loops, or a cron for scheduled checks. Both are SESSION-SCOPED and die on
  context clear; re-arm after any restart.
- **wandb offline is ~750 MB/lane at 250k cadence** — disk math must include it.
- `tests/test_anneal_aux_group.py` silently SKIPS 9/10 without both encoder env vars.
- The D26-era grader lesson is now protocol: **the grader exists and self-tests BEFORE
  launch** (`scripts/d29_grade.py --selftest`); it hard-stops if the frozen comparator
  JSONs are moved or edited.
- `results/d26/finals` numbers at full precision are what the grader attests — README
  and RESULTS quote 0.71825 (exact disk 0.718250); never re-round into new documents.
