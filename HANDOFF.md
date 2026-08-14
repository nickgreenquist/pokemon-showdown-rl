# Handoff — written 2026-08-14 11:05 EDT. **D25 IS RUNNING. 5 LANES LIVE.**

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty
stub. STATUS.md and SESSION_LOGS.md are CURRENT through the launch record; this file
carries only what the next session needs to *do*.

## State: 5 lanes training, healthy, ~7.5 h remaining

`origin/main` = `ec86d71`, pushed, tree clean, suite **319 green**.

D25 launched 2026-08-14 ~00:10 EDT at `aux_oppact_coef: 0.1`, seeds **52-56**, in five
DETACHED `screen` sessions — `screen -r d25_s52` (…s56), `ctrl-a d` to detach,
`screen -ls` to list. They are independent of any agent job and survive it.

At 3.6M steps (11:04 EDT), all five: 311-315 steps/s wall, ETA **~7.5 h → finals ~18:30
EDT**, `selfplay/winrate_anchor` **0.9685-0.9785**, `loss/entropy` 0.298-0.440,
`aux/illegal_label_frac` **0.000000**, live trunk ratio 0.125-0.130.

## Do this, in order

1. **VERIFY LANES BY BATTLE PROGRESS, never by run-dir existence or by what a launcher
   printed.** `python scripts/extract_history.py runs/showdown_sp_actpred12m_s52` then
   read `_step` / `rollout/episode_return`. wandb is OFFLINE, so `history.csv` only
   refreshes when you re-extract — a stale CSV is not a stalled lane.
2. **R1 at 4M (already essentially met):** `winrate_anchor` >= 0.75. A lane below it is
   STOPPED under the LANE FAILURE RULE; **fewer than 3 of 5 clearing STOPS THE ARM and
   records F5 NEGATIVE** with the coefficient named. No re-tune, no relaunch (D17 +
   one-lever).
3. **K6:** 5-lane MEDIAN `loss/entropy` < 0.15 for 5 consecutive readings before 6M ->
   stop that lane. Currently 0.298-0.440, falling as expected.
4. **R0-8, WARM:** wall-clock effective steps/s over a sustained >= 30-min window AFTER
   the first 1M steps. Record-and-continue below **255**, STOP below **210**. NOT the
   logged `time/steps_per_sec`, against which any 2xx threshold is inert. Currently
   311-315 and fine.
5. **If a lane dies to an eval auto-tie crash, relaunch on a FRESH seed (47-48 are
   held), never the same seat** — a same-seed relaunch hits zombie battles (s49 -> s51).
6. **At the finals, run the locked eval:** final checkpoint, deterministic, ties as
   non-wins, vs `SimpleHeuristicsPlayer`, **3000 battles/seed x 5 seeds pooled**, BOTH
   encoder env vars at every eval.

## Owed before the readout — none of it needs a lane

- **R0-14, THE GRADER: NOT WRITTEN.** One script implementing the credit line VERBATIM
  (pooled delta >= +0.025 AND >= 2*se_diff, se_diff the **LARGER of** pooled-binomial and
  seed-clustered), the recording band, the lane-failure recompute, R0-4's hard fail, and
  the exact permutation p for CO-PRIMARY B in BOTH label spaces and for S1, at the
  pre-stated level for whatever n_T survives (5 -> 12/252, 4 -> 6/126, 3 -> 2/56, VOID
  below 3). Comparator is FROZEN: 0.5633/0.5683/0.5210/0.5763/0.4937 -> **0.54452, sd
  0.03558**; realistic operative bar **0.584-0.599**. R0-15 requires it to print those
  five numbers and the tape sha256 BEFORE any treatment number is loaded.
- **g, for R0-10 condition (a) — PROXIED, NEVER COMPUTED.** The smoke read `aux/loss`
  (flat across a 10x coefficient range), not g. Closing it needs a tape per smoke arm
  plus the probe. Say "proxied" at readout, or close it.
- **R0-16:** S1's dormancy control extended to s50/s51 at 12M, tau 0.025,
  `--tag d25_control`. Blocking for the S1 letter only.
- **THE M4 CLONE RE-SCORE, at 5x3000** — do it BEFORE the finals land, so the M4 branch
  is not adjudicated under the pressure of a live result. The obligations fire on the
  NUMBER (pooled >= 0.558), not on a verdict, so a FLAT result can trigger them.
- **C10:** whether the §0 tapes included forced post-faint replacements is UNDETERMINED
  in every source and must be settled before the readout. The build now handles their
  LEGALITY correctly; whether they belong in the loss is the open question.

## Open maintainer decision

**The shuffled-label placebo arm, +2.35 lane-days** (chapter -> ~18.2/20). It is the
difference between "an explicit opponent model helps" and "an auxiliary loss helps".
Needed before the READOUT, not before the run. Currently NAMED-NOT-RUN and the header
scopes the claim accordingly.

## Do NOT rediscover

- **`grad_clip_frac` ~0.99 mid-run is NORMAL and is NOT a VOID trigger.** The VOID
  clause's 0.90 is a WHOLE-RUN mean; at 3.6M the CONTROL lanes themselves sit at
  **0.9847-0.9878** and D25 sits at **0.9843-0.9886** — indistinguishable, which is
  R0-9 holding in production. Compare at MATCHED STEPS or you will void every lane,
  controls included.
- **`setsid` does not exist on macOS.** It printed five plausible pids for five
  instantly-dead lanes. Verify a launch by battle progress, never by the launcher's
  output. Use `screen -dmS`.
- **The LEARNED bar is 0.3286, not 0.371** (R0-13(b), L6 re-derivation). WEAK is
  [0.10, 0.3286); VOID below 0.10.
- **L6 class order is `{slot0..3, OTHER_MOVE=4, SWITCH=5}`** — pinned by a test against
  §1's own frequency line. A readout that maps class 4 to SWITCH is mis-attributing.
- **Quote the RANGE, not the best measured variant.** MDE(80%) **0.0105-0.0301**, power
  at +0.010 **0.27-0.76**; a non-fire below ~0.017 nats is UNINFORMATIVE. Rank reads:
  MAX null to ESTABLISH, MEDIAN to RETIRE.
- **`results/d25/` is the ONLY COPY of the sha256-frozen reference tapes** (gitignored).
  Losing it makes §5's control distribution, power table and every MDE unreproducible.
  `python scripts/d25_gates.py verify` attests them.
- Realised information under pool labels is **0.4485, not 0.544** — ~46% of the knowable,
  not ~50%. The window is 0.9783.
