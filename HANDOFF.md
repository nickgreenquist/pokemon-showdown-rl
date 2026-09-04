# Handoff — LADDER R4: run the pre-launch gates, launch (maintainer's hands), babysit, read out, record
Written 2026-09-04, maintainer-ordered ("resume the sequence"). Read STATUS.md,
then this, then **`configs/eval/ladder_r4.yaml` IN FULL — it is the RATIFIED
governing document** (2026-09-04, rulings M1-M10 in its ratified_decisions foot).

## 0. WHERE THINGS STAND
- 100M run: DONE, graded **P3** (non-resolving), fully recorded (RESULTS §18,
  README row, SESSION_LOGS 2026-09-04). Nothing left there.
- **LADDER R4: RATIFIED, HOLD LIFTED 2026-09-04 evening** (audit-fixes merged
  and closed; gen4-design PAUSED by the maintainer, not a blocker — do not
  touch that worktree). **LG-1 WAIVED (M10)** — launch whenever the gates
  below pass.
- The object: 100M final, lane s112, ckpt_100000008.pt (sha in the pre-reg),
  GREEDY. Account: **REUSE nickgen1rbrlbot** (M6, maintainer-ruled — multi-
  account rules; R1's account, parked since 2026-08-26). This run plays ~200
  RATED games vs humans on play.pokemonshowdown.com, overnight, 12-16 h.
- Anchor quotes for this object are PAIRED (lane + fleet pooled), rule named:
  off-FP@20 0.50167 / pooled 0.49844; vs-SH 0.8000 / 0.79589; clone 0.930 /
  0.9233. s112 is NOT "the best lane" — the median rule named it.

## 1. WHEN THE HOLD LIFTS — pre-launch gates, IN ORDER (pre-reg LG-1..9)
1. **LG-1 WAIVED** — RULED 2026-09-04 evening (pre-reg M10): no courtesy
   note (not a tournament, not a high-traffic room); the note file is
   deleted. Nothing to send, nothing to stamp. The readout discloses that no
   staff notice was sent. Unsolicited staff contact still carries the
   pre-reg's blind-breach licence and the stop-at-boundary rule.
2. **LG-2 parked-profile capture** — pull
   pokemonshowdown.com/users/nickgen1rbrlbot.json; assert it equals R1's
   banked end state (GXE 59.6, Glicko-1 1573, Elo 1292, n=200 games); rd will
   have GROWN with inactivity — record as found. ANY games since 2026-08-26 =
   VOID (d), stop and report. Save the pull into the readout dir.
3. **LG-3 .env** — MAINTAINER updates BOTH `PS_USERNAME=nickgen1rbrlbot` AND
   `PS_PASSWORD` (currently bot2's; smoke can't check the password — first
   verified at live login). Launch shell must also export
   `POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1` (.env lacks them;
   supervisor exports nothing; bare = loud OBS_DIM 612 death that burns
   relaunches).
4. **LG-4** `pytest tests/test_ladder.py` green (77 passed as of ratification).
5. **LG-5** set-pool upstream re-check within 24 h of launch (pin block in the
   pre-reg; fetch both files from smogon master, hash, compare).
6. **LG-6 local smoke** — needs the LOCAL server UP (it is old, pid 68702
   from 2026-09-01 — restart it fresh for the smoke):
   `python scripts/ladder.py --prereg configs/eval/ladder_r4.yaml --arm R4G
   --local-smoke --battles 2` style (see ladder.py). Assert: kind=greedy,
   lane=s112, the sha (BI-R4-7 now PRINTS sha+obs_dim at startup), obs_dim
   828, NO dose key, and the stamped mean_decision_ms — **FINALIZE the VOID
   (e) threshold from it** (provisional band [1,20); licensed pre-launch edit,
   commit with one-line reason).
7. **LG-7** clean tree, docs committed, **LOCAL SERVER STOPPED**, nothing else
   heavy on the box (a live rated game has a timer).
8. **LG-8** build items: BI-R4-1/3/7 LANDED at ratification. BI-R4-2/5/6 are
   OWED AT READOUT with named fallbacks (ruled, M9) — nothing to do now.
9. **LG-9 LAUNCH — MAINTAINER AT THE TERMINAL (~90 s)**, reading startup
   lines: kind=greedy, userid character-by-character, printed sha/obs_dim, and
   the starting-rating line MUST SHOW R1's parked values — an EMPTY "none
   yet" rating means WRONG ACCOUNT (the tell is INVERTED under reuse).

Launch (two blocks, his zsh, from the repo root; battles target 200):
    cd <repo> && source .env && export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 && nohup scripts/ladder_supervise.sh R4G 200 configs/eval/ladder_r4.yaml >> results/ladder/R4G.supervisor.log 2>&1 < /dev/null &
    nohup scripts/ladder_watchdog.sh R4G 900 >> results/ladder/R4G.watchdog.log 2>&1 < /dev/null &

## 2. BABYSIT (yours; 12-16 h, budget 17, hard ceiling ~22)
- NEVER kill anything mid-battle (forfeits a live rated game). The watchdog
  kills ONLY on socket absence; trust it. Supervisor relaunches; a death
  costs <=1 battle (JSONL is the truth; --battles is cumulative).
- Watch: `results/ladder/R4G.run.log`, supervisor/watchdog logs, JSONL line
  count. Rate read: median s/battle vs refs (R1 230.0 / R3 218.0; band
  [190,300] on median-excl-gaps; bands are DIAGNOSTIC except decision-ms).
- BLIND until n=200: no profile, replay list or board opens. The pre-reg has
  the licensed stops (four), the staff-contact breach licence, the
  profile-unreachable 3-step procedure, and the rule-unmet-at-200 → TARGET
  300 relaunch path. Read them from the pre-reg, not from memory.
- Run `scripts/backup_ladder.sh` ONCE mid-run and once at end.
- Moderator contact => stop at next battle boundary, do not argue.

## 3. READOUT AND RECORD (yours)
- Land BI-R4-2/5/6 (or execute their named fallbacks, saying so): readout
  two-prior support; un-gate the reconciliation block from label=="R3";
  the committed-docs W-L grep test.
- **ALL THREE READOUT SCRIPTS DEFAULT TO R1 — pass every flag, always.**
- Reconciliation is CUMULATIVE: profile total == R1's 200 + R4 jsonl +
  unlogged (replay-diff names them). R4's OWN record comes from the JSONL,
  never the profile; the profile record (incl. R1) is quoted as cumulative.
- Write readouts/LADDER_R4_READOUT.md (headline sentence is FIXED in the
  pre-reg — includes the reuse/warm-start disclosure and the s112-not-best
  sentence adjacent); RESULTS §16.5 (+16.3 re-scoped to three runs); README
  row in the SAME commit; STATUS rewrite + SESSION_LOGS entry (same commit).
  Barred-language list is a YAML key in the pre-reg — respect it verbatim;
  NO cross-run delta is an effect; Elo(R4)-Elo(R1) is barred BY NAME.
- E2 exemption: ckpt_100000008.pt is FROZEN until this readout lands.

## 4. AFTER — next arc work (STATUS carries it)
Step 2 discharges with the run (M4: even VOID/INCOMPLETE discharges it).
Then step 3 (gen4) — audit branch merged; gen4-design PAUSED (maintainer
resumes it at will; its branch has no commits yet — rebase onto main first);
standing rulings (MPS wording, pool.py:88, crash_forfeit) still open.

## 5. Rules that cost hours (unchanged)
conda env pokemon-showdown-rl, never base; commit docs before launching;
one command per fenced block for the maintainer, `<command>` sentinels;
zsh vs bash; never push without asking; SESSION_LOGS 2026-09-04 entries
carry this cycle's full narrative if anything here reads ambiguous.
