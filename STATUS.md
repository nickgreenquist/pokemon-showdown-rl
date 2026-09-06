# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## JOURNEY POSITION — step 3 of 13 IN PROGRESS (`JOURNEY.md`: gen1→gen4→gen9)
Steps 1–2 DONE (batch credited, RESULTS §17; LADDER R4 discharged step 2: GXE
65.2 / Glicko-1 1618 ± 25 / Elo 1354, n=200; readouts/LADDER_R4_READOUT.md).
**Step 3 (gen4 encoder + model): groundwork MERGED + REVIEWED; the FIRST RUN's
build items are LANDED and its pre-reg is DRAFTED AND REVIEWED, AWAITING
RATIFICATION (2026-09-05 late). First run = WANG'S RECIPE on our frozen
encoder (step 4, ruled); step-3 milestone = it learns (≥ 0.60 vs SH, locked
protocol); the CHAPTER's exit is step 5: pooled 3×3000 vs-SH ≥ 0.756,
ONE-SIDED (ruled; the arithmetic gives 0.757 — RW-1). No gen4 model trained.**

## Where things stand (2026-09-05, late)
- **GEN-4 GROUNDWORK** (rl/envs/gen4/): layout v0.1, OBS_DIM 1,448, exact set
  prior, tracker, `ShowdownGen4-v0`; replay sha **b72dcbc7…** is a PINNED GATE.
- **BUILD ITEMS LANDED 2026-09-05 (six commits, all tested):** BI-G4-3 hash gate
  (3a5df5b); PPO `lr_schedule: power` + `value_clip_eps` (526f839, Wang's
  §3.1.4 / SB3 clip_range_vf); BI-G4-2 entity trunk `layout: gen4` (ec39268,
  gen-1 bit-identity pinned; actor 674,763 / critic 543,553); BI-G4-1 both-seat
  harvest `selfplay.harvest_both_seats` (66746dc, live-verified gen 1 + gen 4);
  BI-G4-4 clone-leg threading (8afa069; the FP-tape → dataset → clone → eval
  chain ran end to end at gen 4 via `FP_TAPE_DIR`).
- **THE PRE-REG `configs/gen4_wang50m.yaml`** (+ `.prereg.yaml` sidecar,
  `_smoke.yaml` one-diff partner, `tests/test_gen4_prereg.py` 9 gates,
  `scripts/gen4_wang50m_wave.sh`): 2-Opus review APPLIED (review_1 9 MUST / 17
  SHOULD; review_2 7 MUST / 16 SHOULD — results/design_gen4_wang50m/), every
  finding tagged in place. **NOT RATIFIED; do not launch from it.** Smoke (3
  updates, no number quoted): ~290 seat-1 steps/s solo, harvest ratio 0.99–1.01.
- **Foul Play gen4 eval bot UP**; vs SH n=250: FP@20 226-24-0, FP@500 228-22-0
  (bot-vs-bot, descriptive). Suite 856 passed / 16 skipped (known live flake
  deselected; a live-test stall cleared with a FRESH server, pid 92980). NOT PUSHED.

## Next actions
1. **MAINTAINER: ratify `configs/gen4_wang50m.yaml`** — rulings RW-1..RW-6 at its
   foot (RW-1 threshold 0.756 as ruled / 0.757 / 0.773 at Table 4.1's implied
   n=1000; RW-2 trunk widths ours; RW-3 update size = total rows ≈ 39,936; RW-4
   FP@500 on all lanes, chunked; RW-5 hand-over launch; RW-6 minibatch tail keep
   vs fold). Record in the sidecar's `ratified_decisions`, flip both STATUS lines.
2. **MAINTAINER: launch** (> 5 h): bare `pytest tests/` green (R0-k2), restart the
   server fresh, close other apps (R0-i ≥ 8 GB), clean tree, then
   `nohup caffeinate -dims bash scripts/gen4_wang50m_wave.sh > /dev/null 2>&1 < /dev/null &`
   Seeds 200/208/216; plan 2–3 days; no encoder env vars; agent babysits.
3. Alongside (agent): the gen-4 BC clone — 7,200 FP@20-vs-SH tapes in 1,200-battle
   chunks (`scripts/gen4_clone_tapes.sh`, `FP_TAPE_DIR`, detached) →
   `tape_to_dataset.py --gen 4` → `train_bc.py --target soft` → validate vs SH.
4. After the fleet: the FROZEN post-fleet schedule in the header (vs-SH 3×3000 →
   FP@20 → MDT → S-SHAPE → FP@500 chunks → clone h2h → Q38 pin → five-leg readout;
   RESULTS + README row + STATUS + SESSION_LOGS in ONE commit).
5. Then our gen-1 machinery as LEVERS against this baseline (pool / league
   first), each its own pre-reg; step 6 = ONE gen-4 ladder run under a NEW pre-reg.

## Watch items
- **ONE vs-SH RUNG IS WORTH ±0.02** (read SHAPE); **RESUME SPLITS HISTORY** and
  LOSES the open seat-2 harvested rows (disclosed).
- vs-SH/off-FP are NEVER ladder numbers; FP quotes carry budget + the disclosures.
- Every gen4 number so far is a smoke or bot-vs-bot placement; none is a claim.
- 0.786 is Wang's NETWORK-ALONE and WEAKER number (Fig 4.1 ≈ 0.836/0.849); dose
  is named first as ruled, but his curve crossed 0.786 at ≈ 30% of our per-seat dose.
