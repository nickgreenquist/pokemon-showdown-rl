# Handoff — written 2026-08-05, context clear after the audit/cleanup session

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

**State: everything is DONE, green, committed and pushed (through `3ceb20e`); nothing is
half-finished.** This session: DESIGN.md r6 written + three-review hardened; post-migration
cleanup executed (configs pruned, ~12.5 GB reclaimed, predecessor spine pruned, 36 predecessor
capstone log entries preserved in `SESSION_LOGS_PREDECESSOR.md`); PPO adversarially audited —
core CLEAN bit-for-bit, its one confirmed latent bug (warm-start lr override in
`load_state_dict`) FIXED with a regression test. Suite: 220 passed. No runs live. The Showdown
server may still be up on :8000 in a maintainer tab — check before starting another.

**Recommended next path, in order (agreed with the maintainer at session end):**

1. **The gate: the maintainer's review of DESIGN.md §9 (D1–D7), ~30 min.** Nothing
   implementation-shaped moves before it. Author recommendations are in place per decision
   (corpus measurement now → own chapter; Arm B 6M futility screen + 3000-battle eval
   amendment; Arm A reduced to a ~1 h smoke; no 24M run; no new benchmark yet; ladder as
   success metric; Arm C parked). The maintainer may ask to be grilled through it
   interactively instead of reading cold.
2. **One code evening, no runs:** (a) Track 1's parse-free half — sample the 109k
   `gen1randombattle` corpus, measure recency/rating/winner/set-pool coverage + the Foul Play
   format-and-latency check (bars in DESIGN §4; this decides the main line); (b) the ~1 h
   Arm A warm-start smoke from `runs/bc_p4_512_40k_s0` — exercises the just-fixed lr path and
   settles the `rl/train.py:134` guard decision (warm start = fresh run); (c) explained-variance
   + grad-norm logging (required before Arm B; the audit saw the 0.5 clip binding 16/16 on
   synthetic data — production needs the real read).
3. **First compute run: Arm B at 6M** (~2.9 h, maintainer's terminal) — terminal-cancelled
   faint shaping (DESIGN §4 form, §5 reads) vs the P5b control, 3000-battle finals, iff D2(c)
   ratifies. Commit docs BEFORE launching; launch from a clean tree.
4. **No large runs.** 24M stays rejected under the stop rule (D4c); big compute belongs to the
   corpus chapter only if Track 1's bars clear, and its first milestone is engineering, not GPU.

Open, no deadline: un-gitignore maintainer-authored `prior_work/wang_fork_diffs.md`?
