# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 3 of 13 IN PROGRESS (`JOURNEY.md`: gen1→gen4→gen9)
Steps 1–2 DONE (batch credited, RESULTS §17; LADDER R4 discharged step 2: GXE
65.2 / Glicko-1 1618 ± 25 / Elo 1354, n=200; readouts/LADDER_R4_READOUT.md).
**Step 3 (gen4 encoder + model): groundwork MERGED + REVIEWED; the FIRST RUN
(WANG'S RECIPE on our frozen encoder, step 4 as ruled) is TRAINING — launched
agent-side under a chat waiver of rule 4 (2026-09-06) at the header's recommended
defaults. Step-3 milestone = it learns (≥ 0.60 vs SH, locked protocol); the
CHAPTER's exit is step 5: pooled 3×3000 vs-SH ≥ 0.756, ONE-SIDED (ruled; the
arithmetic gives 0.757 — RW-1). No gen4 number is a claim until the readout.**

## Where things stand (2026-09-06, ~02:00 UTC)
- **GEN-4 GROUNDWORK** (rl/envs/gen4/): layout v0.1, OBS_DIM 1,448, exact set
  prior, tracker, `ShowdownGen4-v0`; replay sha **b72dcbc7…** is a PINNED GATE.
- **BUILD ITEMS LANDED 2026-09-05 (all tested; shas in SESSION_LOGS):** BI-G4-3
  hash gate; PPO `lr_schedule: power` + `value_clip_eps`; BI-G4-2 entity trunk
  `layout: gen4` (gen-1 bit-identity pinned; actor 674,763 / critic 543,553);
  BI-G4-1 both-seat harvest (live-verified); BI-G4-4 clone-leg threading.
- **THE PRE-REG `configs/gen4_wang50m.yaml`** (+ `.prereg.yaml` sidecar, `_smoke.yaml`
  one-diff partner, `tests/test_gen4_prereg.py` 9 gates, `gen4_wang50m_wave.sh`): 2-Opus
  review APPLIED (16 MUST / 33 SHOULD across both — results/design_gen4_wang50m/), every
  finding tagged in place. Not formally ratified: launched on chat authorization at the
  RECOMMENDED DEFAULTS (RW-2/3/6 baked in; RW-1/RW-4 later ruled at the defaults, see 1).
- **Foul Play gen4 eval bot UP**; vs SH n=250: FP@20 226-24-0, FP@500 228-22-0
  (bot-vs-bot). Clone tapes 6 × 1,200 at 1.12–1.16 s/battle; a weather-forme bench
  name failed the gates on 4 of 84,046 rows — fixed cba9458, PASS. NOT PUSHED.

## Next actions
1. **FLEET: attempt 1 (03:08Z) OPS-KILLED 03:21Z** — gen-4 pool-seat mask desyncs
   tripped the gen-1 recovery cap; FIXED e37a7fc + d51fa6f (re-decide on the fresh
   request; no phantom seat-2 decisions), smoke 0 desyncs in 60k. **ATTEMPT 2 LAUNCHED
   03:40:18Z** at d51fa6f (860 passed / 2 live tests deselected; PREFLIGHT PASS), lanes
   s200/s208/s216; attempt 1 archived under `runs/aborted_20260906_0308Z/`. DISCLOSE both
   attempts + the deselects. **RW-1/RW-4 RULED at the defaults 11:30Z.** Incident 2
   (10:55Z, eval guard) FIXED 07f587d; watcher v2; all lanes rolled over by 11:32Z.
2. **MAINTAINER:** nothing owed before the readout — every RW is recorded in the
   sidecar's `ratified_decisions`; the agent babysits (watcher v2, `.rollover`).
3. **CLONE VALIDATED 2026-09-06 02:25Z:** `runs/bc_gen4_fp20_soft_s0` (FP@20 teacher,
   168,676 rows / 7,200 battles, GATES PASS; val agreement 0.433) scores **0.464 vs SH**
   (n=1000, deterministic, ties 0.022); MDT-vs-SH sanity row **0.400** (120-173-7, n=300).
   L4 is no longer PENDING; its h2h runs in the post-fleet schedule.
4. `scripts/gen4_wang50m_postfleet.sh` (FROZEN order, resume-safe; refuses while a lane
   trains) AUTO-CHAINS on FLEET DONE (a session watch; ≈ 2026-09-08 21:30Z) → author the
   five-leg readout in ONE commit. In-run gates: `scripts/gen4_wang50m_gates.py` (5M: all
   PASS, D-B 211–215 steps/s; next read 25M ≈ 09-07 12:30Z).
5. Then gen-4 levers against this baseline, each its own pre-reg — **NOT the pool
   (ruled 2026-09-06: league stays on, no ablation)**; step 6 = ONE gen-4 ladder,
   NEW pre-reg, and the maintainer wants it CONDITIONAL on a matched step-5 read.
6. **2026-09-06 rulings, docs only (fleet untouched):** JOURNEY **7.5** = switch gen-1
   training off Node onto pkmn/engine BEFORE step 8 (ONE collector for steps 8–11, gated
   on A-1); IDEAS §3 classifies every kill and indexes what re-opened (4.7 privileged
   critic, 2.8 GPU-for-update, 4.3 repriced at k=8, attention/search re-framed).

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** (read SHAPE); resumes SPLIT history: use `merge_history.py`.
- vs-SH/off-FP are NEVER ladder numbers; FP quotes carry budget + disclosures; no gen4 claim yet.
- 0.786 is Wang's NETWORK-ALONE, WEAKER number (Fig 4.1 ≈ 0.84); dose is named first.
