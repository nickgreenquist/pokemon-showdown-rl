# Handoff — written 2026-08-09 (~late morning), after the F1 guard completed

**⚠ Run the next session on FABLE 5 at HIGH effort** (`/model`, `/effort`). The session is
a DESIGN session: draft the 50M structure-only pre-registration for ratification. If the
session is not on that setting, say so before doing anything else.

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

## State: green, committed, PUSHED through 93342b5, nothing running

Suite **267 green**. Tree clean; `origin/main == main` at 93342b5 (maintainer authorized
that push 2026-08-09; pushing stays ask-first — a handoff commit after it may be local).
No training/eval/FP processes. Showdown server UP on :8000 (pid 74836, `simulator: 4`).
STATUS.md + SESSION_LOGS.md are current through the F1-complete entry — do not restate.

## The one thing that matters

**Rung 2 (STRUCTURE) CREDITED 2026-08-09: pooled 0.5509 ± 0.0052 vs 0.3996, z +20.5 —
the flat readout was the binder. F1 guard COMPLETE on every anchor (clone h2h 0.657
pooled; FP-itself 0.824-against vs 0.876 historically; v2r 0.612; MaxBP +9.2).**

- **M2/M3 blessing:** maintainer reacted "results look great" to the package but has NOT
  issued a formal blessing sentence — get it explicitly and record it before the 50M
  header cites M3 as claimed.
- **NEXT TASK: draft `configs/showdown_sp_struct50m.yaml` pre-registration** (branch (a):
  entity trunk, gamma 1.0, NO shaping, 3 seeds, fresh seeds from 35+). Template: the
  Rung 2 header (`configs/showdown_sp_struct12m.yaml`) + its SEQUEL section. Design
  questions the draft must settle: comparator (natural: Rung 2's 0.5509 pooled — a 50M
  run must beat the 12M version of itself, credit line per repo standard), the M4 read
  (clone now protocol-graded at 0.5777, gap −0.027), eval n, checkpoint cadence at 50M,
  and R0 gates carried forward (fingerprint 828/ids, param ceiling unchanged, R0-6, K6).
- **Budget reality, measured:** 3-wide lanes run ~350 steps/s/lane (NOT the solo smoke's
  552) → 50M ≈ 40 h/lane, ~40 h wall at 3-wide. That is the D15 decision (rent a CPU box
  / loop re-architecture): Rung 0 E1-E4 (THROUGHPUT_SPEC, D12b) is still owed and feeds
  it. The pre-registration should state the budget both ways (as-is vs post-throughput).

## Do NOT rediscover these (session-hot; the rest is in the logs)

- Entity checkpoints need BOTH env vars at eval (`POKEMON_RL_ENCODER_V2=1
  POKEMON_RL_ENCODER_IDS=1`); a forgotten var dies loudly at trunk construction (by
  design). v2/808 MLP checkpoints cross-play via the shim (automatic in
  eval_checkpoint); v2/807 are refused — no exact map exists.
- Foul Play launches need the FULL URI `--websocket-uri ws://localhost:8000/showdown/websocket`
  (the 2026-08-06 log's sequence omitted it); env `foul-play` (conda), patch already
  applied in `../foul-play`'s working tree; smoke 5 battles first, always.
- Deterministic-vs-sampling seat asymmetry in h2h can be huge (0.800/0.514 vs the BC
  clone) — never read one orientation alone; pool per protocol.
- Laptop sleep suspends lanes+server harmlessly BUT kills session Monitors while the
  harness still lists them as running — TaskStop the zombie and re-arm. `caffeinate -is`
  offered for the 50M lanes.
- Monitor/watch scripts must not contain the literal strings the maintainer's guard
  loops pgrep for — bracket forms (`rl[.]train`).
- Seeds: 0-13, 23-34 SPENT, 14-22 RESERVED (warmrl), 99 disposable; **35+ free — the 50M
  lanes draw from there**, distinct across lanes AND arms.
- STATUS.md hard cap 60 — it drifted twice this session (61); count BEFORE committing.

## Open, deliberately

1. M2/M3 formal blessing sentence (above) — then the README/results narrative can call
   M3 the success claim delivered at 12M.
2. H&L scale accounting (both seats or one?) — settle from the metagrok clone BEFORE the
   50M budget is priced as "H&L-comparable" anywhere.
3. Rung 0 E1-E4 measurement evening (D12b) — feeds D15; fits any gap evening.
4. Recipe rung (rollout/λ) demoted to optional secondary post-credit; VGC-Bench is a
   third reference on OUR side of the λ split (README corrected 2026-08-09).
5. BC arm / relax-purity: answered by data at 12M (no); optional comparison chapter only.
