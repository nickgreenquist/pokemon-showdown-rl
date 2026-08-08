# Handoff — written 2026-08-08 (~13:45), after the Rung 1 read-out

**⚠ Run the next session on FABLE 5 at HIGH effort** (`/model`, `/effort`). The session is
an implementation build (Rung 2's entity trunk); the design thinking is done and in the
config header. If the session is not on that setting, say so before doing anything else.

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

## State: green, committed, PUSHED, nothing running

Suite **258 passed**. Tree clean; `origin/main == main` (maintainer authorized the push
2026-08-08; pushing remains ask-first). No training/eval processes. Showdown server **UP on
:8000** (pid 74836, `simulator: 4`) — reuse it. STATUS.md and SESSION_LOGS.md are current
through the Rung 1 read-out — **do not restate the 2026-08-07/08 entries**.

## The one thing that matters

**Rung 1 (SIGNAL) read out NULL 2026-08-08: pooled 0.4131 ± 0.0052 vs comparator 0.3996 ±
0.0052, z +1.84 — missed both credit-line halves. Branch (b) of its pre-registration binds:**

- **Rung 2 (STRUCTURE) runs at gamma 1.0 / NO shaping, vs the SAME 0.3996 comparator.**
  Magnitude retuning of the shaping is CLOSED (pre-registered p-hacking guard).
- Rung 2 needs CODE FIRST: entity DeepSets trunk + shared per-action scorer, param ceiling
  681k (the flat MLP's count). Full spec + post-ratification amendments (v2/808 numbers,
  3000/seed evals) in `configs/showdown_sp_struct12m.yaml`. Then the R0-4 arch smoke
  (1 lane × 1M, **seed 30**, ~35 min), then 3×12M on **seeds 26/27/28**.
- The null was CLEAN (all gates green). Mechanism notes recorded in the log entry: signal
  arm's seed spread collapsed to 0.004 (control's was 0.050 — s32 hit 0.431); S2 confirmed
  (EV easier under dense targets). Read them before designing anything.

## Next session, in order

1. Implement the Rung 2 trunk (masking contract applies — `rl/common/masking`, finite
   sentinel, value head never masked). Param-count assertion against 681k in a test.
2. R0-4 arch smoke seed 30; verify fingerprint v2/808 + battle progress per lane, as ever.
3. Launch 3×12M (maintainer terminal, v2r pattern: 3 nohup subshell lanes, 90 s stagger).
   Evals afterward are ~2 MIN each in-session (measured twice) — never budget hours.

## Do NOT rediscover these (session-hot; the rest is in the logs)

- **Encoder is FROZEN at v2/808** (`POKEMON_RL_ENCODER_V2=1`, process-level, forgettable;
  fingerprint must show `obs_dim: 808, recharge_fix: true` in EVERY lane's meta.yaml).
  0.3890/0.3800 are dead comparators (v2/807 semantics).
- Seeds: 0-13, 23-25, 29, 31-34 SPENT; 14-22 RESERVED (warmrl, on ice); **26/27/28 = Rung 2
  lanes, 30 = arch smoke**; 35+ free. Distinct across lanes AND arms (username landmine).
- Rung 2 checkpoints are UNSHAPED (branch b) — `--no-shaping` on eval is unnecessary but
  harmless; the `hl_shaping` code stays landed and gated for any future shaped arm.
- In-session watches: Monitor scripts must not contain the literal strings the maintainer's
  guard-loops pgrep for — use `rl[.]train` / `eval[_]checkpoint` bracket forms, or the two
  watchers deadlock each other (cost 20 min of confusion once).
- The maintainer-terminal guarded-eval pattern (`while pgrep ... done && evals`) exists in
  the 2026-08-07 log but is obsolete: evals are short enough to run in-session on the
  monitor's lanes-exited ping.
- STATUS.md hard cap 60 lines — it drifted over once more (caught at commit); count first.

## Open, deliberately

1. H&L scale accounting (both seats or one?) — settle from the metagrok clone BEFORE
   Rung 3's budget is priced. A 2× error is 2.5 days.
2. Rung 0 E1-E4 measurement evening (D12b) — still owed, fits any gap evening.
3. D15 (rent CPU box) and D17 (abandon) both wait on Rung 2's read: two nulls are on the
   board; if Rung 2 also nulls, the chase is one 50M scale step from the abandon criterion.
4. FP-clone protocol-grading + head-to-heads — owed only if M-milestone guards fire or the
   chase is revoked (warmrl resumes from its ratified draft, zero rework).
