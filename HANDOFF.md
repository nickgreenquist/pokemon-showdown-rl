# Handoff — written 2026-08-16 night. **NOTHING IS RUNNING. D26 is ratified and ready to launch.**

Read this, then `STATUS.md`. Everything below is committed and PUSHED (`main` == `origin/main`
at `c0add37`, suite 371 passed / 9 skipped, tree clean, server up on :8000).

---

# 1. FOR THE MAINTAINER — the whole roadmap in one page

## Already done

| DESIGN.md item | outcome |
|---|---|
| §2 milestone ladder M1–M4 | **all four CLAIMED** |
| §4 Rung 0 — throughput | done |
| §4 Rung 1 — reward shaping | ran, **NULL** |
| §4 Rung 2 — entity architecture | ran, **+0.151** ← the big one |
| §4 Rung 3 — scale 12M→50M | ran, +0.029 |
| §12 D22 — plateau diagnostics | closed: representation/critic ceiling |
| §12 D18 — privileged critic | ran, **NULL**, falsifier fired |
| §12 D19 — opponent-team prediction | **KILLED at zero lanes**, re-targeted → D25 |
| D23 — regenerative L2 (out-of-queue) | ran, letter-met, **NOT credited** |
| D25 — opponent-**action** aux head | ran, **CREDITED 0.6185** ← the other one |
| D25-P — shuffled-label placebo | ran, flat (0.5415) → the *information* did it |
| C4 transfer probe | ran 2026-08-16, **FIRED**, C4 discharged |
| D27 — matched-dose control | **KILLED at zero lanes** (undosable) |

## What was tried and failed

- **Reward shaping** (Rung 1) — nothing.
- **Better inputs** (encoder v2 + pool fix) — +0.009, nothing.
- **Privileged critic** (D18) — critic got better, agent didn't. Killed by its own falsifier.
- **Regenerative L2** (D23) — met the letter, failed the seed-robustness bar.
- **Predicting the opponent's hidden team** (D19) — killed before spending compute: 88–90% of
  what's inferable is a deterministic cap mask, not a belief.
- **Matched-dose control** (D27) — killed before spending compute: a shuffled-label head
  routes everything into its bias term and disconnects from the trunk, so it *cannot* be
  dosed at any coefficient.
- **Scale** (Rung 3) — +0.029 for 4.17× compute. Real but small, and diagnosed: the ceiling
  is representational, not experience.

## What moved the needle — only two things

1. **Architecture (Rung 2): 0.3996 → 0.5509, +0.151.** Entity embeddings + DeepSets pooling +
   a per-action scorer, at *identical* parameter count. Score "this move against this
   opponent" instead of learning slot-indexed preferences.
2. **The opponent-action auxiliary head (D25): → 0.6185, +0.074.** Predict which action the
   opponent is choosing this turn; labels are free in self-play. Controlled by a placebo, and
   as of today the representation is shown to **transfer** to an opponent it never trained on.

Everything else nulled. The pattern: **structure beat signal, inputs, and scale.**

## What's left to try

- **D26 — LR annealing** (a §12/D21 item). Ratified, gated, ready. ~1.74 lane-days. The last
  thing that fits the budget.
- **D21 leftovers** — GAE λ sweep, KL early stopping, entropy scheduling, rollout sizing. Each
  is its own arm; none fits alongside D26. *PFSP is effectively dead* — D22's trigger for it
  never fired.
- **D20 — v3 encoder bundle.** Post-chase by design. Changing OBS_DIM invalidates every
  checkpoint, so the control alone costs a full arm before any treatment.
- **§13 — 250M scale.** Blocked by its own precondition: it requires a credited lever *at 50M*
  and none exists.
- **A structured zero-information aux control** — the honest way to close the last caveat on
  D25 (predict the agent's *own* action, or regress a random projection of its own obs). Needs
  its own pre-registration and ~1.75 lane-days the chapter doesn't have.

**Budget: 17.91 of 20 lane-days spent. D26 takes it to ~19.65. After that the chase is over.**

---

# 2. FOR THE NEXT SESSION — state and next actions

## Where things stand
`RESULTS.md` is the chapter's written account (self-contained; it is DESIGN.md's successor,
since DESIGN.md is deleted by its own lifecycle rule once migrated). `STATUS.md` is current
state. **DESIGN.md is NOT self-updating — verify its status lines against the newest
SESSION_LOGS entry before acting on anything in it.** A stale D19 entry cost a whole session
on 2026-08-16.

## The one live action: launch D26, or don't
`configs/showdown_sp_recipe12m.yaml` is **RATIFIED BY DELEGATION** (the maintainer said
"ratify whatever you think is best"; the four Q13 calls were taken by the assistant and the
header says so). **All pre-launch gates pass** — `scripts/d26_gates.py` (R0-A/C/E/F/H/J) and
`tests/test_anneal_aux_group.py` (R0-B). Re-run both before launching; they are cheap.

Launch commands are in the header's Q12 — four lanes, seeds 62–65, one per detached shell,
staggered ~60 s. **Verify each lane by battle PROGRESS, never by the run directory existing.**
~10.4 h wall. Runs go in the maintainer's terminal.

**Honest expectation, pre-stated:** required delta is +0.025 to +0.053 and the lever's own
horizon-matched effect is +0.0277. P(CREDIT) 0.23–0.39 at typical seed spread, 0.60–0.75 if
seed spread lands low. **The modal outcome is FLAT, and a FLAT licenses nothing** — its
interval would not even exclude +0.0277. That is written into Q6 so it cannot be re-narrated
at readout.

## At readout
Grade with the committed grader per Q6; the headline moves to D26 **only on B1 (credit)** —
on every other branch D25 stays the headline and D26 is reported beside it. That rule was
corrected after review: the draft version was a one-way ratchet that would have overturned
the D23 precedent.

## If D26 is NOT run
The chapter closes at 17.91/20. `RESULTS.md` needs no further work. That is a legitimate and
defensible ending — "we stopped because the remaining levers were below what the budget could
resolve" reads better than spending the last of it on a pre-registered long shot.

## Open, and NOT the assistant's to decide
**DESIGN §8's D7(a) defers the ladder eval "until M2/M3" — now satisfied — while CLAUDE.md's
landmine forbids proposing one. Two ratified documents contradict; one must move.**

---

# 3. LANDMINES FROM THIS SESSION — do not rediscover

- **Verify a handoff's premise before executing it.** The last one sent a session at D19,
  which had been dead for three days.
- **`aux/trunk_norm` is logged PRE-clip** (`ppo.py:790`), and the clip is applied POST-
  coefficient (`:796`). A dose gate reading the logged value would certify a dose never
  delivered.
- **Two counter conventions, same letter.** R0-B's `u` is PRE-increment; R0-C and Q3's table
  use the POST-increment checkpoint counter. Mixing them rejects a correct anneal. Both are
  now pinned by assertion.
- **Don't hand-type precise constants.** Two drafts of R0-B failed against a *correct* anneal
  because I typed digits the header never claimed. Assert at the precision actually printed.
- **`rl.envs.showdown` freezes `ID_DIM` from the process env at IMPORT.** Setting the encoder
  flags at construction is too late; use the subprocess pattern
  (`tests/test_privileged_block.py:69`).
- **A null needs a positive control.** The D19 closeout is only credible because the same
  probe extracts +3.73 nats when the answer is planted.
- **Check the obvious confound before believing a letter.** The C4 probe fired at p=1/252, and
  live-unit count correlated with the statistic at r=+0.94 with zero overlap between arms. It
  survived a capacity-matched refit — but it might not have.
- **`results/` is gitignored.** `d25/`, `d25p/`, `d19_closeout/`, `c4_transfer/` are the ONLY
  copies; all are backed up at `../pokemon-showdown-rl-d25-backup-20260815/`.
- **`time/steps_per_sec` is not throughput** (361 logged vs a 312 wall) and **in-loop
  `eval/win_rate` (n=100) does not preview a locked number** (0.576 vs a locked 0.5415).
- **vs-SH 0.6185 is still ~40% GXE.** Nothing here is "nearly solved."
