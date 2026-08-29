# Handoff — repo cleanup session (2026-08-29, maintainer-ordered)

Task: clean and organize the repo BEFORE R2 launches. Maintainer-ordered,
so the off-arc ruling requirement is satisfied. JOURNEY position unchanged
(step 1; R2's pre-reg is the next arc work — do NOT write it this session).

Read `REPO_CLEANUP.md` (live list, 2026-08-28) then `CLEANUP.md` (older;
only A2–A5, B1–B4, B6–B9 still live). Reconcile the two into ONE ledger as
you work. Line numbers in both have drifted — re-verify every quote before
acting on it.

**FIRST ACTION — get the outstanding rulings in one message to the
maintainer:** (a) delete `rl/selfplay/elo.py` + test (614 lines, zero
importers)? (b) retire the MinAtar/continuous-PPO spine (~11% of suite;
Connect 4 STAYS — live test fixture)? (c) strip killed-lever code
(priv-critic, L2-init, BC warmstart, fixed_mix, TensorBoardLogger…) or
leave the knobs? (d) delete `data/bc_p4_40k.npz` (2.08 GB) and the 116
non-pinned `best_checkpoint.pt` (1.29 GB)? — compression-only (~6.7 GB)
needs no ruling; (e) `docs/archive/` + `readouts/` restructure and the
CLAUDE.md diet (REPO_CLEANUP §D/§D2)?

Boundaries:
- **CHAPTER5.md is NOT deletable.** Its §3/§6/§7 must first migrate into
  R2's pre-reg header, which does not exist yet. Archive/delete with or
  after R2, never before.
- Honor both do-not-re-litigate lists (REPO_CLEANUP items 16–17 +
  "Verified clean" block; CLEANUP §C). "Nothing greps it" is not evidence
  a script is dead — two deletions were already retracted on exactly that.
- The ⏸ wave constraint has EXPIRED (RS81/RS82 landed 2026-08-29), so
  items 1 and 8 are safe now. Item 1 edits a live pre-reg AND its test —
  one commit, dated CORRECTED notes, test updated to protect the
  corrected values, not the retraction.

Newer than the sweep: `RESEARCH_BRIEF.md` is already deleted (f981032);
`research_reports/` (4 reports + `CONSOLIDATED.md`) now exists — include
it in root-inventory/archive decisions.

Success metric is §D2's: "tokens before useful work" goes DOWN. Small
single-purpose commits as items land; end green; ask before pushing.
On completion: fold durable findings into SESSION_LOGS.md (+ STATUS.md
pointer), restore this file to its empty stub.
