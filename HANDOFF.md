# Handoff — R2 pre-reg session (written 2026-08-29, maintainer-ordered)

Task: **write and ratify R2's pre-registration** (JOURNEY step 1: gen1
retrain, batch lever). It is an irreversible artifact → full 2-Opus design
cycle (two design memos, two independent reviews, runner adjudicates).
Nothing gates it; the pre-R2 cleanup landed and pushed (SESSION_LOGS
2026-08-29). Tree is clean.

Inputs, in order:
- `STATUS.md` next-actions 1–3 — the settled parameters: **scored GREEDY**
  (r9 rescore; control = the free s80/81/82 read), **PRIMARY = strength vs
  the 0.1007 bar, BOTH sides carry the clustered term**, sigma_seed
  descriptive with the (2,2)-df disclosure, minibatch 256 / scale the
  COUNT (H&L m=7680 is an existence proof, not a target), λ = a config
  choice on the explained-variance diagnostic (`loss/explained_variance`
  is logged, ppo.py:1189), 3 new 50M lanes.
- `CHAPTER5.md` — **§3 (C1–C6 provenance), §6 (out-of-scope), §7 (five
  rulings incl. the 50M ceiling) MUST migrate into the header verbatim**;
  §8 says what the cycle should attack. Archive CHAPTER5 only with/after
  the ratified pre-reg.
- `research_reports/CONSOLIDATED.md` — the commissioned research.
- Header obligations: `journey_step: 1` + STATUS's scope guard verbatim;
  the credit line verbatim incl. the larger-of se_diff clause; the five
  D25-era pre-reg rules; anchor battery; and JOURNEY's new standing note —
  **any ladder read owes a pinned-settings FP h2h block** (budget, engine +
  poke-engine commit, n, greedy-vs-searched) named in advance.
- Pattern to copy: `configs/eval/ch5_r1_offsh.yaml` + `tests/test_ch5_prereg.py`
  (the header gets a test; protect 1292, never 1311).

Ops reminders: distinct `--seed`s across lanes; commit docs before launch;
launches are >5 h training → hand the commands to the maintainer;
`docs/landmines.md` for anything you're about to touch. Cleanup residue in
`CLEANUP.md` is post-R2 — do not reopen it.

On completion: fold into SESSION_LOGS + STATUS (same commit), restore this
stub.
