# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 1 of 13 (`JOURNEY.md`, the arc: gen1→gen4→gen9)
**Step 1 = gen1 retrain, batch lever** (= R2 below). SCOPE GUARD, binding: a
read inside the bar is information about the INSTRUMENT, not a licence to
queue another gen1 lever — ladder anyway (step 2), then step 3 (gen4).
**Name the JOURNEY step every work item serves; off-arc work needs a ruling.**

## Where things stand (2026-08-29 evening) — **R2'S PRE-REG IS WRITTEN AND
AWAITS RATIFICATION.** Full 2-Opus cycle ran (2 memos, 3 adjudications, 2
reviews of a frozen draft; 8 MUST-FIX applied — SESSION_LOGS 2026-08-29
evening). The pre-reg is TWO halves: `configs/showdown_sp_batch50m.yaml`
(training; one-diff = {seed, run_name, rollout_steps 3840, minibatches 120,
push_every_updates 5}; lambda HELD 0.95) + `configs/eval/ch5_r2_offsh.yaml`
(read; cells, bars, riders, usernames). Tooling committed: ch5_r2_wave.sh /
ch5_r2_preflight.sh / ch5_r2_grade.py (selftest green) / 37-test pre-reg
suite. Suite 612 passed / 17 skipped. Pure self-play; THE NOVELTY IS THE LANE.

## Results | 12M **0.71825** vs SH · ensemble 0.74633 · search@M 0.79283 (**12M**)
· **LADDER R1 (ensemble): GXE 59.6%, Glicko 1573±27, Elo 1292, n=200** ·
**LADDER R3 (search@M, s80): GXE 60.3%, Glicko 1579±25, Elo 1232, 106-94,
n=200 — STANDALONE; no R1-vs-R3 delta is a quantity (D5)** · off FP@20 greedy
0.3960/0.3430/0.2730 · C0 0.3893 · **fresh searched: 0.4390/0.4487/0.454.**
Ties=loss. **Ladders credit nothing.**

## Next actions
1. **MAINTAINER: ratify R2** — read `configs/showdown_sp_batch50m.yaml` Q10
   first: rulings owed = E1 (eyes-open: P(credit) ~6.5% pre-stated, both
   designers endorse running anyway), E2 (FP@20 anchor→primary promotion),
   E3 (checkpoint retention until D-A + forgetting rider), E4 (marked
   corrections in the verbatim migration), E5 (CLAUDE.md "5×3000" scope fix,
   suggested not made), ADJ-1/2/3 (n=3000; vs-SH split letters; clip_frac
   tripwires). Ratifying word = ratified; then archive CHAPTER5.md.
2. **MAINTAINER: launch** (>5 h training): server up + pre-launch gate chain,
   then 3 lanes seeds 66/75/83, stagger ~60 s, verify by battle PROGRESS.
   Command blocks: SESSION_LOGS 2026-08-29 evening entry / handed over at
   ratification. ~35 h wall 3-wide alone; caffeinate; clean tree.
3. After training: vs-SH finals (`--out results/ch5_r2/final_sN.json`,
   the declared home) → sha attestation commit → FP wave (T66/T75/T83,
   serial k=1) → R4S → riders. Build owed before the cross-play/forgetting
   riders run: `scripts/ch5_r2_crossplay.py`.
4. THEN curve vs credited win rate — gates LANES AND SCALE, not batch.
   Cleanup residue: `CLEANUP.md` (post-R2).

## Watch items
- **The R2 bar is honest and brutal**: at s_T = s_ctrl the treatment fleet
  MEAN must beat the control's best-ever lane by +0.042. A null is the modal
  outcome and is PRE-STATED (E1); scope guard routes every cell to step 2.
- **NEW failure mode = memory**: 2.68 GB/lane peak (R0-h gate, D-E watch);
  the box must be otherwise idle for the ~35 h.
- **SEARCH EQUALISES THE LANES** (n=3000; sd below binomial floor); beta's
  SIGN is NOT interpretable; "search inverts lane quality" barred.
- **foul-play can PANIC** (`Invalid PokemonMoveIndex: 4`); pair-flip to the
  pre-registered rerun pair is licensed edit (ii); re-run LAST.
- **R4:** `.env` holds bot2's creds; VOID (f) INVERTS on a persistent seat.
