# Handoff — written 2026-08-05. THE DESIGN IS SET; CODING WORK STARTS NOW.

**⚠ Maintainer reminder, before anything else: run this session on OPUS at HIGH effort**
(`/model`). If the session isn't on that setting, say so first thing.

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

**State: everything green, committed, pushed; nothing half-done.** DESIGN.md r6 is **RATIFIED**
(maintainer review 2026-08-05; §9's recommendations D1–D7 adopted as written — see the
ratification log entry for the binding list). PPO audited clean bit-for-bit, its one latent
bug (warm-start lr override) fixed + regression-tested. Suite: 220 passed. No runs live; the
Showdown server may still be up on :8000 in a maintainer tab — check before starting another.

**The work, in order — no further review gates:**

1. **Code evening (this session):**
   a. **Track 1 parse-free half** (DESIGN §4): sample the 109k `gen1randombattle` HF corpus —
      recency/uploadtime distribution, `rating` nullity, winner extractability, log-length,
      `teams.ts` set-pool coverage, Foul Play format support + measured s/decision. Finalize
      the pre-registration bars (provisional ones in §4) — worth maintainer eyeballs before
      locking. Pin the HF revision. This decides whether the corpus chapter is the main line.
   b. **Arm A warm-start smoke** (~1 h, DESIGN §4 "Retired"): single seed, ~100–200k steps
      from `runs/bc_p4_512_40k_s0` — settle the `rl/train.py:134` guard as "a warm start is a
      fresh run" (the lr-override half is already fixed in ppo.py); record step-0 win rate ≈
      clone's, no first-updates collapse under critic-only warmup.
   c. **Explained-variance + grad-norm logging** (required before Arm B; DESIGN §5). The audit
      saw the 0.5 clip binding 16/16 on synthetic data — get the production read.
2. **Arm B at 6M** (first compute run, after 1c): terminal-cancelled faint shaping exactly per
   DESIGN §4/§5 — move its pre-registration into the config header (the
   `showdown_r512_lra.yaml` pattern) before launch. 3 seeds = 3-wide (~2.9 h, ~553–600
   steps/s/lane, distinct `--seed` per lane), maintainer's terminal, commit docs BEFORE
   launching from a clean tree. Finals at 3000 battles/seed for arm AND the re-evaluated P5b
   control; futility gate: advance to 12M iff pooled delta ≥ +0.009.
3. **No large runs.** 24M stays rejected (D4c); corpus-chapter compute waits on Track 1's bars,
   and that chapter's first milestone is engineering, not GPU.

As arms get built, migrate their pre-registrations from DESIGN.md into config headers
(lifecycle: DESIGN.md is deleted once fully migrated). Open, no deadline: un-gitignore
maintainer-authored `prior_work/wang_fork_diffs.md`?
