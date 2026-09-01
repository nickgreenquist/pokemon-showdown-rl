# Handoff — the timer fix, then two probes (written 2026-08-31, maintainer-ordered)

Run **Opus / high**. Work the four items **in this order**. Read `STATUS.md`
first, then this. R2 is CLOSED and CREDITED (cell P1) — nothing here can change
that verdict, and no item below is credit-seeking.

**Standing:** the maintainer ruled items 2 and 3 are IN-ARC step-1 work
(choosing which object to ladder R3 with), so no JOURNEY amendment is owed.
Answer in one or two lines while things run; full write-up at the end.

The box is IDLE. Showdown server on :8000 may need restarting
(`cd showdown && node pokemon-showdown start --no-security`); `simulator: 4`
must be at `showdown/config/config.js` line ~111 (gitignored — re-set after any
re-clone). Commit docs before launching anything; launch from a clean tree.

---

## 1. THE TIMER FIX — highest value, do it first

**Read `docs/landmines.md` → "THE ORPHANED-ROOM DEADLOCK" before touching
anything.** One-paragraph version: a turn-1000 auto-tie makes both sides
Struggle (move index 4), foul-play's Rust engine panics, the dead opponent
leaves a room we still hold, `start_timer_on_battle_start` defaults False so no
`/timer on` is sent and the room NEVER resolves, poke-env frees a queue slot
only on `|win|`/`|tie|`, leaked rooms fill `_battle_count_queue`, and the next
battle blocks forever at `player.py:221`. This cost R2 **190,776 + 170,680
re-run steps, a 5.2 h freeze, and two dead R4S66 attempts**.

**The change:** `start_timer_on_battle_start=True` at
`scripts/ch3_fp_h2h.py:176` (SeatPlayer), `scripts/ladder.py:465`
(LadderPlayer), and — the one that matters most — through
`ShowdownSingles(...)` via `**kwargs` into PokeEnv. Secondary, seats only:
`max_concurrent_battles` 2 → 8 (pure slack; 4 orphans < 8 would have carried
both R4S66 attempts to completion). Also fix `ch3_r4_fp_runner.sh`: `log_bytes()`
(:122-126) reads the FP log ONLY, so a wedged SEAT gets blamed on foul-play and
would have credited us 4 PHANTOM FORFEITS on a graded arm; and the
`pid is gone` branch (:241-244) sets FP_DEAD without calling `kill_fp`, so
search-worker children are never reaped there.

**VERIFY, do not assume.** The training path is the one with no slack
(`poke_env/environment/env.py` hardcodes `max_concurrent_battles=1` as a
LITERAL at 273/292/355/375). Prove the kwarg actually reaches PokeEnv — a
short live run plus an assertion on the constructed player, not a code read.

**RULING OWED BEFORE THIS SHIPS:** `/timer on` is a **wire-visible protocol
change** — it alters what the server does in every battle thereafter. The
maintainer must rule on comparability against banked arms. My read is that it
is inert for a bot answering in <3 s (ops, not a claim), but it is not mine to
decide. Ask, with your smoke-test evidence in hand.

**Then, OPTIONAL:** re-run R4S66 (`ARMS="R4S66" bash scripts/ch5_r2_wave.sh`
after `scripts/ch5_r2_preflight.sh`). ~2.4 h. It answers whether search still
stacks on a batch lane — a real input to the ladder choice — but it **ROUTES
NOTHING** and cannot touch the verdict. Its pair is already flipped (commit
956b909); do NOT flip again. Unfixed it will fail a third time identically.

## 2. SCALE-SHAPE READ — minutes, do it before MPS

Does 50M → 100M plausibly pay? D29r2's R-B FLAT tested the OLD recipe; the
BATCH recipe's scaling is **UNMEASURED** at any point but 50M.

**USE s83'S RUNGS. Not s66, not s75** — those two were resumed and their
histories cross a seam where checkpoint step and training history disagree.
s83 is the only clean lane. The E3 retention obligation kept all 69 rungs
(`runs/showdown_sp_batch50m_s83/ckpt_0*.pt`, every 500k).

Evaluate ~20M / 30M / 40M / 50M vs SH (`scripts/eval_checkpoint.py <ckpt>
--episodes N --out ...`; n=1000 is a fine SHAPE read, say so when quoting).
Report whether the curve is still climbing at 50M or already flat.

**DESCRIPTIVE ONLY — no bar, no comparator, credits nothing.** Do not project
a 100M number. **STOP AT "read the curve and report."** A 100M run is
credit-seeking and needs its own PRE-REGISTRATION (arms, bar, credit line
verbatim, journey step) through the full 2-Opus cycle — that decision is the
maintainer's, informed by your read. Do not queue it.

## 3. MPS BENCHMARK — report and propose only

"CPU only for the RL loop; MPS is flaky here" (`CLAUDE.md:71`,
`rl/common/config.py:21`, `docs/archive/DESIGN.md:548`) is **NEVER MEASURED** —
no session-log entry, no benchmark, and NO `docs/landmines.md` narrative,
unlike every other rule in CLAUDE.md. DESIGN.md calls it "a repo convention".

Re-testing is newly motivated: the batch lever moved us from ~1k to
**30,720-step batches at `[512,512]`**, the regime that favours a GPU.

- Measure **`time/update_sec`** at REAL width and REAL batch. MPS can only help
  the learner; **collection is Node-bound and cannot benefit**, so any headline
  "N× faster" that includes collection is wrong by construction.
- **Do NOT use `scripts/showdown_throughput.py`** — collection-only, ~7×
  overstated, and hardcoded `[64,64]`.
- Check numerics: the `-1e8` mask sentinel is a harness contract; `-inf`
  behaviour differs across backends. Assert MPS and CPU agree.

**REPORT AND PROPOSE ONLY. The maintainer rules on the CLAUDE.md change** —
it is a standing rule every session reads. Do not edit it yourself.

## 4. THEN STOP

Fold into SESSION_LOGS + STATUS in the same commit, restore this stub. Do NOT
start a 100M run, do NOT ladder, do NOT build `scripts/ch5_r2_crossplay.py`
(still unbuilt; it blocks riders R3c/R1i/R1ii and the README row via the anchor
battery's BC-clone half). Anything ambiguous is a maintainer escalation.

**Watch for the stall signature everywhere:** process ALIVE, **zero CPU**,
stale output, no crash. `pgrep` NEVER catches it. Confirm in 15 s with
`ps -o time= -p <pid>` twice — identical CPU time means stalled.
