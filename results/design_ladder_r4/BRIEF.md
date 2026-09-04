# BRIEF — LADDER R4 (gen1 ladder #3, JOURNEY step 2) — 2026-09-04

Shared evidence brief for the standing 2-Opus design cycle. Two independent
memos from this brief under different framings (A: MEASUREMENT VALIDITY,
B: OPERATIONS/COST), then synthesis, draft, two adversarial reviews.
Designers are given settled rulings and OPEN questions, never a preferred
design (CHAPTER5 §8's lesson). Ratification is the maintainer's.

## The step (verbatim, JOURNEY.md step 2)
"Gen1 ladder #3 — record. Happens regardless of what step 1's offline read
says. This is the capture of where the object stands on the format the
novelty claim lives on, before the encoder rewrite. Exit condition: the run
itself — not a rating, not top-500." Top-500 chasing is explicitly named a
trap. A mediocre run does not mean the story failed.

## SETTLED — maintainer-ruled 2026-09-04, not up for redesign
- THE OBJECT: the 100M final, played GREEDY (deterministic), single lane
  chosen by the pre-committed MEDIAN-BY-PRIMARY-AXIS rule over the three
  100M finals' off-FP@20 rates (0.48633/0.50167/0.50733) -> lane s112,
  runs/showdown_sp_100m_s112/ckpt_100000008.pt, sha256 2ec16fbf85a9046d...
  (full sha in configs/eval/ch5_100m_offfp.yaml). Median was chosen over
  best-of-3 exactly to avoid selection-on-noise on a ±0.02 instrument.
- GREEDY over search: R4S66 measured search@20 HURTING the batch recipe
  (0.38067 vs greedy 0.4740, ~10 se). search@M on the 100M lane itself was
  NEVER measured; the ruling stands on today's evidence and says only that.
- 100M context: cell P3 (delta +0.02389 vs floor 0.025, NOT credited);
  ladder deployment is a strongest-agent selection question, not a credit
  claim. RESULTS.md §18 is the account.

## FACTS ON DISK (verify anything load-bearing yourselves)
- Anchor battery for THIS EXACT object all EXISTS (unlike R3's D4 gap):
  vs-SH s112 final 0.8000 (fleet pooled 0.79589); off-FP@20 t112 0.50167
  (pooled 0.49844; budget + two standing disclosures travel); BC-clone
  ca112 0.930 (pooled 0.9233). All n=3000 (clone 500), locked protocols,
  published in RESULTS §18.
- Infra: scripts/ladder.py supports kind=greedy natively (POLICY_KINDS);
  BI-5 (max_concurrent_live_battles stamped in artifact) and BI-6
  (max_concurrent 2 deadlock fix) landed pre-R3; supervisor + watchdog
  (scripts/ladder_supervise.sh, ladder_watchdog.sh) self-healed R3 through
  real websocket outages (10 runner launches). Instruments:
  ladder_classify.py / ladder_readout.py / ladder_move_audit.py /
  backup_ladder.sh; tests/test_ladder.py carries the ratification-marker
  machinery (BI-2: markers present in draft, ABSENT once ratified).
- R3 realized: ~17 h for n=200 WITH search@M (~2.7 s/move thinking).
  GREEDY inference is ~ms; wall clock is matchmaking-dominated (board
  ~93 active players/day). R1's cheap-inference ensemble reached 176
  battles overnight unattended.
- References for licensed cells: R1 CORRECTED bands (2026-08-28:
  [1300,1400) = 0.319, n=47; aggregate implied true Elo 1214) and R3's
  readout (GXE 60.3%, Glicko-1 1579±25, Elo 1232, 106-94 over n=200;
  bands in readouts/LADDER_R3_READOUT.md). RECONCILE item open: R3 STATUS
  said 106-94 (n=200) vs readout 106-102 (208) — R3's fix was building the
  table from replays with an exhaustiveness assert; carry that.
- Local Showdown server is NOT involved (run is vs play.pokemonshowdown.com,
  fresh rated account). Box is otherwise free; no training runs concurrent.

## CARRIED RULINGS THAT BIND R4 (from ladder_r3.yaml ratified_decisions —
read that file IN FULL; it is the template that can fire)
- D2's PRE-COMMITTED TRIGGER, verbatim: "A THIRD RATED ACCOUNT — any
  ladder run after R3 — REQUIRES A COURTESY NOTE TO PS STAFF BEFORE
  LAUNCH." R4 IS account #3. The note's text, recipient and mechanics are
  a design item; sending it is the maintainer's act.
- D5's comparison framework: standalone descriptive; NO cross-run delta
  quoted as an effect in either direction; the Glicko-RD bar REFUSED (the
  three reasons are in the file); [1300,1400) is the only licensed
  comparison cell, no threshold attaches, its power is derisory and said
  so; headline sentence is a fixed template quoted with n, policy kind,
  board position. "THIS RUN CREDITS NOTHING" travels.
- Purity note: playing humans is purity-legal; ladder replays NEVER become
  training data.
- Stopping rule precedent: rd <= 40 AND n >= 200, runner exits on the rule
  (G-BLIND licensed stops); D1 precedent: ONE continuous unattended run is
  ruled admissible (R1 and R3 both ran overnight unattended).
- vs-SH/off-FP are NEVER ladder numbers, in either direction; the ~40% GXE
  conversion is RETIRED. The profile carries GXE/Glicko for ANY rated
  account; the leaderboard JSON only for listed ones; JSONL `rating` is
  PRE-battle.

## OPEN QUESTIONS (design these; recommend, don't decide)
1. n / stopping rule for R4: carry rd<=40 AND n>=200, or change (why)?
2. Does Q6's "re-score fresh before publishing" apply to the median lane?
   (The selection statistic IS the published, pre-registered primary at
   n=3000 — median, not max. Argue it either way; name what is quotable.)
3. Courtesy note: text, recipient (PS staff channel), timing, what it
   discloses (research bot, rate, account name), failure mode if ignored.
4. Account: naming (R1/R3 precedent is linked names — opponent-memory
   confound #6 in R3's seven), fresh vs linked, who registers it.
5. Licensed cells and references: carry [1300,1400) with R1-corrected +
   R3 cells as side-by-side references (never subtracted)? Any new cell?
6. Readout/record mechanics: replay-built tables with exhaustiveness
   assert (the R3 106-102 lesson); README/STATUS/RESULTS update plan
   (anchor battery already complete — R3's D4 gap does not recur).
7. Ops: greedy-specific stall/deadlock watch (no search workers this
   time); wall-clock projection for greedy; disconnect handling; what the
   supervisor does differently, if anything.
8. Amendment licensing: what may move post-ratification (R3's licensed-
   edit precedent), and the barred-language list.

## Deliverables
mem_A.md (measurement validity) and mem_B.md (operations/cost) in
results/design_ladder_r4/. Every load-bearing claim cites its source file;
disagreements with this brief are stated, not smoothed.
