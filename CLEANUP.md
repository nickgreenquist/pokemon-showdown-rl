# CLEANUP.md — audit backlog

From four parallel audits on 2026-08-25 (scripts / docs / code / disk).
Everything here is **triaged but NOT done**, because each item needs either a
maintainer ruling or a change too invasive to make unattended. Items that
were safe were fixed the same day and are listed at the bottom so nobody
re-audits them.

**The fact that governs this whole file:** `results/`, `runs/` and `data/`
are ALL gitignored with **zero tracked files** (`git ls-files results | wc -l`
→ 0). So a closed rung's grader script is the *only committed provenance* for
the number it produced. "Nothing references it" is not evidence that a script
is dead. Of 69 scripts, exactly **two** are genuine delete candidates.

---

> **This file is no longer the live cleanup list.** `REPO_CLEANUP.md`
> (2026-08-28 sweep) holds the current one; read it first and reconcile
> against this file, which is kept for the items below that it does not
> restate (A2–A5, B1–B4, B6–B9).

## A. Needs a maintainer ruling

*(A1 was here. It was executed 2026-08-25 — moved to §C.)*

### A2. `rl/selfplay/elo.py` — 332 lines + 282 lines of test, imported by nothing
Bradley-Terry/Hunter-MM tournament rating fit, from the predecessor's
Connect-4 era. Zero importers in `rl/` and `scripts/`; the only one is
`tests/test_elo.py`. Not superseded-by-consolidation: `ch4_r1_grade.py` does
closed-form two-player BT, a different thing, and the ladder uses server-side
Glicko. **614 lines, the largest clean trim available.** The docstring's
Hunter/Ford degeneracy guards are the valuable part — worth moving to
`SESSION_LOGS_PREDECESSOR.md` before deleting.

### A3. Is the MinAtar / continuous-PPO spine gate still live?
`pyproject.toml:25-33` justifies keeping MinAtar, Connect 4 and continuous
PPO as "DESIGN.md's Arm C spine gate." **Arm C is PARKED** (DESIGN.md:582,
838) and DESIGN.md now carries a HISTORICAL/SPENT banner. There is **no
continuous env in the dependency set at all**, so that track cannot be run
end to end here. Combined: **56 of 529 tests (~11%)**.

Recommendation if retired: cut the continuous track (cleanest — nothing can
exercise it), keep Connect 4 regardless. Connect 4 is *not* dead weight — it
is the cheap in-process two-player fixture for `test_frozen_opponent.py`,
`test_resume.py` and `test_selfplay_pool.py` (no poke_env import). Its other
role, fixed-anchor opponents for `fixed_mix`, *is* dead (see A4).

### A4. Killed levers still carrying code
Each kill confirmed against SESSION_LOGS before listing. None should be
removed without a ruling — several have hard gates whose removal would weaken
a contract, and the comments record measurements worth keeping even if the
knob goes.

| lever | status | footprint in `rl/` |
|---|---|---|
| privileged critic (D18) | **KILLED** 2026-08-12 by its own falsifier | 66 refs across showdown.py / ppo.py / rollout.py / entity_deepsets.py / train.py |
| L2-init (D23) | letter-met, **NOT CREDITED**; 50M carry killed at zero lanes | 101 refs + a 411-line test |
| BC warmstart | **ON ICE** 2026-08-07, never came off | `bc_kl_coef`, `critic_warmup_updates`, `actor_lr_scale`, `_install_bc_anchor` |
| `selfplay.fixed_mix` | set in **zero** configs; hard-rejected for Showdown; guard says "Connect4-only" and **no Connect4 config exists** — doubly unreachable | `train.py:307-316`, `pool.py` ×5 |
| `selfplay.pfsp_power` | set in zero configs → 0.0 → the AlphaStar PFSP weighting never fires | `pool.py:115,220` |
| `TensorBoardLogger` | 43/43 configs use wandb; no test covers it | `logging.py:58` + a pinned `tensorboard` dep |
| `kernel_size`, `dueling` | predecessor Connect-4/DQN probes; PPO never passes them | `ppo.py:271`, `conv.py:30` |

### A5. Disk — costed menu (repo is 14 GB; 172 GB free, so this is hygiene)
| action | frees | risk |
|---|---:|---|
| gzip `results/ch4_r1_offsh/*.fp.stdout` | **3.52 GB** | needs a 2-line `gzip.open` fallback in `ch4_r1_grade.py:133,191` or re-grading breaks. **Do not delete** — the pre-reg reserves them |
| gzip `runs/*/history.csv` (89 files, 3.35×) | **2.16 GB** | **ONLY-COPY, never delete.** 6+ readers need the `.gz` suffix; pandas reads it transparently |
| `data/bc_p4_40k.npz` | **2.08 GB** | ruling: it backs an expert-data BC lane the charter excludes, but the clone survives as a 5.2 MB pinned checkpoint |
| 116 non-pinned `best_checkpoint.pt` | **1.29 GB** | ruling: no pre-reg pins a `best_`; the locked protocol uses the FINAL checkpoint |
| gzip `data/fp_tranche*/**.jsonl` (12.2×) | 0.61 GB | safe; only reader is `tape_to_dataset.py` |
| delete 3 aborted-1M runs + relaunch_collision | 0.14 GB | safe; unreferenced |

Compression-only (no deletions): **~6.7 GB**, taking the repo to ~7.2 GB.

**The comedy waste, named:** `results/ch4_r1_offsh/l62.fp.stdout` is 674.8 MB
/ 4.9M lines. The grader reads **3,000 `Winner:` lines** out of it. Across 13
tapes: 3.72 GB of poke-env DEBUG logging carrying 24.9 MB of signal, and it
compresses 18.2×.

---

## B. Safe but not yet done

### B1. Reproducibility holes pointing into gitignored space
- `d25_atoms.py` imports `rev1_check` / `gate_r012` from
  `results/d25/scripts/` — **gitignored and untracked**. `d25_gates.py`
  deliberately re-implemented those rather than import them, for exactly this
  reason; `d25_atoms.py` never got that treatment. Fix: vendor the two
  modules into `scripts/`, or whitelist that directory in `.gitignore`.
- `tests/test_opp_action.py` names `scripts/gate_r012.py`;
  `rl/networks/zeroinfo.py` names `scripts/z1_1.py`. Neither is in
  `scripts/`; both live under gitignored `results/`. A fresh clone resolves
  neither.

### B2. `selfplay.*` config silently accepts unknown keys
Top-level keys are strict (`Config(**raw)` raises on a typo); `agent.*` and
`env_kwargs.*` are strict by accident (they land in a constructor).
**`selfplay.*` is strict nowhere** — every read is `cfg.selfplay.get(...)`,
and `train.py:301` checks only for *missing* required keys, never extra ones.
So `pfsp_power` typo'd as `pfsp_pow` loads clean, trains a full 12M-step run
with flat opponent sampling, and produces **no error and no metric that looks
wrong**. Both affected knobs are unset today, so this is prophylactic — but
it is the one place a silent-wrong-run can still originate. Fix: an
unknown-key assertion in `selfplay_env_kwargs` (`rl/envs/make.py:109-120`),
where the reserved-key check already lives.

### B3. The encode/mask/convert trio is duplicated 8× with divergent policy
Sites: `rl/collect.py:81,133`, `rl/envs/showdown.py:999`,
`scripts/ch3_fp_h2h.py:154`, `scripts/ladder.py:253`,
`scripts/tape_to_dataset.py:314`, `scripts/showdown_throughput.py:127`,
`scripts/obs_fidelity_check.py:211`. The copying is not the finding — the
**divergent desync policy** is: strict-raise in `collect.py`, counted-recover
in `showdown.py`/`ch3_fp_h2h.py`, default-move in `ladder.py`. (The
ladder half was fixed 2026-08-25 to feed the shared counter.) Proposed:
one `decide(battle, type_chart, act_fn, *, on_desync)` helper with the policy
as an explicit argument, so the three intentional differences stay visible
instead of accidental.

### B4. Three scripts bypass the masking contract
`d25_atoms.py:88`, `d25_gates.py:52`, `d25_manipulation.py:52` hand-roll the
`-1e8` sentinel instead of going through `rl/common/masking.masked_logits`,
which CLAUDE.md mandates. `rl/common/masking.py` itself is clean — no change
proposed there.

### B5. Doc staleness (lower value than A1)
- `DESIGN2.md:3-6` still says "PROPOSED... NOT RATIFIED. Nothing launched" —
  but D28/D29r/D29r2 all launched, ran, and were credited or killed. It is
  also **invisible to CLAUDE.md's read protocol** despite being cited by
  production code (`ppo.py:522`, `zeroinfo.py:1`) and three configs.
- `RESULTS.md` and `RESEARCH_BRIEF.md` are absent from CLAUDE.md's Docs
  section entirely.
- `RESEARCH_BRIEF.md` is orphaned, self-declared "not a living doc", and its
  headline speculation was later falsified. Delete candidate.
- `DESIGN.md:32` promises deletion-on-migration; its 2026-08-25 banner
  promises permanent retention. Banner wins (newer); reconcile in one line.
- CLAUDE.md calls DESIGN §13 "PROPOSED"; DESIGN.md:844 says **RETIRED**.
- `SESSION_LOGS.md` (6700 lines, 185 entries) has only a flat grep index. A
  chapter-boundary lookup near the top would be an *addition*, not an edit,
  so it does not violate append-only.

### B6. Nine stale comments (five fixed, four left)
Left: `checkpoint.py:1` "Phase 0 stub... optimizer state joins when the first
gradient-based agent lands" (it landed); `ppo.py:86-88` MuJoCo/SAC references
(neither exists — pruned with the spine); `ppo.py:66` "DQN-vs-PPO headline"
(no DQN; `ALGOS` is `{random, ppo}`); `wrappers.py:36` "into the replay
buffer" (no replay buffer exists); `buffers/base.py:2` justifies the ABC by
DQN/SAC, leaving a single-implementer abstraction.

### B7. Two genuine delete candidates in `scripts/`
`play_vs_agent.py` (87 lines) and `record.py` (128 lines, the sole reason
`imageio` is pinned). **Note:** `play_vs_agent.py` was flagged as dead by the
audit and then immediately became useful — it is now the way to play the
ladder policy by hand (`--arm`). Left in deliberately. Judge `record.py` on
its own.

### B8. `d29_grade.py` vs `d29r2_grade.py` — the one true duplicate
191 of 197 lines identical; differs by a seed tuple and two paths. **Do not
just delete one** — `RESULTS.md:409` cites `d29_grade.py` by path as the
attestation record for the D29r VOID verdict, a published negative result.
Either parameterise with `--seeds`/`--results` and keep a thin shim, or keep
both with a cross-reference.

---

## B9. poke-env sporadically drops the battle rating (found live, n=5)
`battle.rating` / `battle.opponent_rating` came back `None` for battle 5
while the saved replay shows the server sent 1184 / 1111. Not seat-dependent
(three of the four successes were also p2) — a race in the `|player|` parse.
No impact on the primary read (server-computed GXE), and fully recoverable
from `results/ladder/replays/*.html`. Left unpatched deliberately: changing
`ladder.py` mid-measurement would mix code versions across a resume. Fix
after the run, or accept the replays as the source of truth.

Join replays to JSONL rows on the NUMERIC battle id — some tags carry a
secret suffix (`battle-gen1randombattle-<id>-<token>`), which silently breaks
a `rsplit("-")` join.

---

## C. Done 2026-08-25 (do not re-audit)

- **A1 (was "the highest-value doc item outstanding"): `RESULTS.md` was two
  chapters behind — EXECUTED 2026-08-25, verified closed 2026-08-28.**
  `RESULTS.md` now carries `## 13` (Chapter 3 / search, closed), `## 14`
  (Chapter 4 R1 / off-anchor) and `## 15` (the full vs-SH table + chapter
  narrative), in the `## 9`–`## 12` addendum pattern A1 proposed; §15 carries
  **0.79283**, whose absence was A1's headline complaint. A1's own citation
  is now dangling: `README.md:8` no longer says "start there" — the README
  opens on the ladder result and points at `RESULTS.md` from `:123`, `:170`
  and the where-written-down table at `:243`. **Not a successor item** — the
  live list is `REPO_CLEANUP.md`, whose item 10 (RESULTS has no ladder
  chapter; wants a §16) is the next thing in this area.
- **README told readers to evaluate with `score_ladder.py`** — the Connect-4
  false friend, not the locked protocol. Now points at `eval_checkpoint.py`
  and `ladder.py`.
- **CLAUDE.md still said "do not propose the ladder"** — the deferral CH4 R1
  satisfied and the maintainer has since ratified. The D19 dead-lever failure
  mode, one file from repeating.
- Attention ruling mis-cited as "§7 / ~line 313" in three files (it is §4
  Rung 2, lines 337-340); five dangling "DESIGN §11" pointers qualified;
  CLAUDE.md's "288 passed" (stale by 240).
- **CH4 R1's four instruments had zero references repo-wide** despite
  producing the whole chapter readout — named in an `instruments:` block with
  a test asserting the paths exist.
- `scripts/README.md` written: script → chapter → banked output, leading with
  the trap that **`ch3_*` is not all Chapter 3** (`ch3_r4_fp_runner.sh`,
  `foulplay_vs_sh.py` and the FP patch are live anchor machinery).
- **`verify_against_showdown()` had zero callers** — a public set-pool
  verifier that never ran. Wired into the suite.
- 24 dangling `PLAN.md` citations (predecessor file, absent here) repointed
  to `SESSION_LOGS_PREDECESSOR.md`, every measurement preserved.
- `test_connect4.py` claimed a fuzz-oracle complement that no longer exists —
  a false coverage claim, corrected.
- `logging.py` said "reuse exactly" over a list missing 5 of the 10 locked
  metric names.
- `train.py`'s "611-dim" obs measurement date-stamped (production is 828).
- Two pre-launch ladder bugs: mask desyncs were invisible to
  `mask_desync_total()`, and the pre-registered stopping rule was prose no
  code read.
- **The backup contained zero `.pt` files** — the 13 sha-pinned checkpoints
  behind every pre-registered result existed in exactly one place on one
  disk. All 13 copied and verified sha-equal to their config pins; 322
  unmirrored `results/` files re-synced.
- Caches swept; three unreferenced FP logs gzipped (302 MB → 26 MB).
