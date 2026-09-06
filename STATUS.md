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
- **THE PRE-REG `configs/gen4_wang50m.yaml`** (+ `.prereg.yaml` sidecar,
  `_smoke.yaml` one-diff partner, `tests/test_gen4_prereg.py` 9 gates,
  `scripts/gen4_wang50m_wave.sh`): 2-Opus review APPLIED (review_1 9 MUST / 17
  SHOULD; review_2 7 MUST / 16 SHOULD — results/design_gen4_wang50m/), every
  finding tagged in place. **Not formally ratified: launched on the maintainer's
  chat authorization at the RECOMMENDED DEFAULTS — RW-2/RW-3/RW-6 are thereby
  baked into the run; RW-1 and RW-4 are readout-side and STILL OWED.** Smoke:
  ~290 seat-1 steps/s solo, harvest ratio 0.99–1.01 (no number quoted).
- **Foul Play gen4 eval bot UP**; vs SH n=250: FP@20 226-24-0, FP@500 228-22-0
  (bot-vs-bot). Clone tapes 6 × 1,200 at 1.12–1.16 s/battle; a weather-forme bench
  name failed the gates on 4 of 84,046 rows — fixed cba9458, PASS. NOT PUSHED.

## Next actions
1. **FLEET: attempt 1 (03:08Z) OPS-KILLED 03:21Z** — gen-4 pool-seat mask desyncs
   (~3e-5/step; U-turn / Baton Pass / choice-lock traffic) tripped the gen-1 recovery
   cap (3 per 100k). FIXED e37a7fc + d51fa6f (re-decide on the fresh request; no
   phantom seat-2 decisions); smoke 0 desyncs in 60k. **ATTEMPT 2 LAUNCHED 03:40:18Z**
   at d51fa6f (R0-k2 860 passed / 2 live tests deselected; server pid 11553; PREFLIGHT
   PASS): lanes s200/s208/s216 pids 11668/11795/11905. Attempt 1 is archived under
   `runs/aborted_20260906_0308Z/`. DISCLOSE both attempts and the deselects.
   **RW-1 (0.756) and RW-4 (FP@500 on all lanes) RULED at the defaults 11:30Z (chat).**
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
5. Then our gen-1 machinery as LEVERS against this baseline (pool / league
   first), each its own pre-reg; step 6 = ONE gen-4 ladder run under a NEW pre-reg.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** (read SHAPE); **RESUME SPLITS HISTORY**, loses open seat-2 rows.
- vs-SH/off-FP are NEVER ladder numbers; FP quotes carry budget + the disclosures;
  every gen4 number so far is a smoke, a clone or a bot-vs-bot placement — no claim.
- 0.786 is Wang's NETWORK-ALONE, WEAKER number (Fig 4.1 ≈ 0.84); dose is named first.
