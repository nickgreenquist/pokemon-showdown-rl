# Handoff — written 2026-08-05, first context clear of this repo

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

**State: bootstrap is COMPLETE and fully verified — nothing is half-done.** Port verification
passed 8/8 with measured reproductions; the old repo is stripped, archived, and verified clean;
git history (42 commits + bootstrap `b696e85`) is pushed; the repo runs standalone in the new
`pokemon-showdown-rl` conda env (fresh-env suite: 288 passed, after the old repo and old env
were already gone). STATUS.md is current and is your real entry point.

**Next action, singular: the DESIGN.md revision pass against the P6 numbers.** P6 broke Arm A's
premise (RL 0.4607 > clone 0.453; SH ceiling 0.489 leaves +0.028) — see DESIGN.md's Revision 5
banner and P6_RESULTS.md (mind its correction banner; the log entry wins on mechanism). The
revision pass must resolve §10's phase placement (the 109k human-replay corpus — the only lever
not capped at 0.489) before the team review means anything. Do not implement any arm before
that review concludes.

Two small open maintainer decisions, no deadline: adapt the old repo's doc-archaeologist agent
here (old repo git history has it); old milestone-1/2 run dirs are gone by flagged decision.

Nothing else is in flight. No runs are live. The Showdown server may still be up in a
maintainer terminal tab from verification — check :8000 before starting another.
