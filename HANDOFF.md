# Handoff — written 2026-08-13 (mid-morning), post-D23-readout, nothing running

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty
stub. STATUS.md + SESSION_LOGS.md are CURRENT through the D23 readout entry — this
file carries only the pending items.

## State: green, clean tree, NOTHING RUNNING

Suite 293 green (R0-3 golden file needs its own pytest process — 1-ULP flake,
logged). No lanes, no monitors, no evals in flight. Server still up on :8000. Two
stray `caffeinate -t` timers will expire on their own. Old dead-run dirs
(`runs/showdown_sp_struct12m_s49_dead_at_7m2`, `_relaunch_collision`) kept as
incident artifacts, gitignored.

## Pending, in order

1. **PUSH: 4 commits local past origin** (bc0394b readout + README fixes + grader
   seed-list fix + norms print guard). Ask-first rule — maintainer says push.
2. **THE DECISION (STATUS action 1)**: after D23's "letter-met, seed-fragile, NOT
   credited" — (a) D19 as queued, (b) 50M regen-L2 carry (BOUND + gap-shrink +
   letter-met is a real case; ~5 lane-days vs ~3 left under the 20-day cap → cap
   conversation), or (c) both sequenced. The comparator-spread finding (true Rung-2
   12M seed sd ~0.036) means any future 12M rung should be mechanism-primary by
   design — factor that into (a) vs (b).
3. Process rule now standing (memory + log): design decisions get 2 Opus design
   agents + 2 Opus reviews before ratification. D23's full cycle is the template
   (SESSION_LOGS 2026-08-12 entries).
4. Small deferred items: DESIGN.md §12 status lines don't yet say D18/D23 are read
   out (lifecycle says headers carry the contracts; update §12's two lever entries
   whenever DESIGN is next touched). d23_grade.py's frozen-vs-augmented block is
   the citable comparator-migration record.

## Do NOT rediscover

- Eval auto-tie crash (~1-in-10⁴ eval battles) can kill a lane mid-run; a SAME-SEED
  relaunch then collides with the dead run's zombie battles server-side ("Can not
  reset player's battles") — relaunch on a FRESH seed (s49→s51 incident, logged).
- Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED; 14-22 RESERVED; 99 disposable;
  47-48 and 52+ free.
- D23 treatment ckpts eval on the plain path (theta0 never needed at eval);
  theta0.pt lives once per run dir, hash-stamped in checkpoints.
- results/d23/ has everything the readout used: grade.txt (both grader passes),
  8 eval JSONs, control_norms.csv + treatment_norms.csv, obs tapes, rank CSVs.
