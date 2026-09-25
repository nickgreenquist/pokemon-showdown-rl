# R6 READS READOUT -- off FP@20 primary, the Ladder R6 object, vs SH descriptive

**QUEUE DONE 2026-09-25 01:07:53Z** (`scripts/r6_reads_queue.sh`, agent-side, detached). Pre-regs
`configs/eval/r6_reads_offfp.yaml` (PRIMARY) and `configs/eval/r6_reads.yaml` (vs SH), pinned by
`scripts/monster_reads_pin.py` at 04:37:13Z -- trio A at **1b923a0**, trio B at **342bdf3** (sha256
and real step names in those commits; each touched only the two pre-regs). The raw output lives in
the gitignored `results/r6_reads_offfp/READOUT.txt` + `readout.json` and is reproduced verbatim at
the bottom, so this file is the durable copy. Journey step: 11.5 (the post-ladder improvement arc).

## Verdict, plainly

- **Trio B (W + C6 + x4 batch, fallback form) beats R5 by a statistically clear but small margin:
  +0.0216 off FP@20 at z 2.91** (pooled 9000 vs 9000; se_diff 0.0074, the larger of binomial 0.0074
  and seed-clustered 0.0050). **All 9 B-lane vs R5-lane pairings favour B.** vs SH says the same
  (+0.0241 at z 4.35 vs R5's banked read -- descriptive, cross-session). **It misses the credit
  line's +0.025 SIZE floor by 0.003, so its cell is B-FLAT and nothing is credited.** The miss is
  the size clause, not significance.
- **Trio A (W + C6 + outcome heads) is flat on every measure:** -0.0022 at z -0.21 off FP@20,
  -0.0023 at z -0.41 vs SH. Cell A-FLAT. Its update costs 1.16x W's per datum (the heads' second
  backward pass).
- **B vs A** (the one clean contrast -- identical program, same C6, only the lever differs):
  +0.0238 at z 2.07 (se_diff 0.0115, seed-clustered, driven by A's spread: 0.5483 / 0.5573 /
  0.5227).
- **No Ladder R6.** R2's object is **E6RF** (all six R6 finals; E6RF and E3BF are within 0.013, so
  the larger committee -- also the highest point estimate) at **+0.0180 over the re-drawn R5
  committee E3WR, z 1.42**. M-R6-10 (ratified 2026-09-24 00:50Z) fires only at >= +0.05. R6's
  finals become R7's base; the next ladder run is R7's.
- **The committee is still the biggest lever in the table:** +0.033 to +0.047 per trio over its own
  singles (R3), against ~+0.02 from this round's best recipe change. Adding the three R5 W finals
  to the six R6 finals does not help (E9RF - E6RF = -0.0080, z -0.63).
- **C6 is common-mode on every R6 lane and cannot be attributed** (no C6-off R6 arm; stated in both
  trio headers, uncredited). Trio A carries C6 and is flat, so C6 alone is not a large effect.

## R7's base -- the X-FLAT action, as the trio headers pre-state it

Both trio headers, verbatim: *"X-FLAT (everything else): a NULL that closes nothing; the mechanism
read decides whether R7 repeats the lever (plan section 4: a by-turn r^2 that did not move at the
finals means R7 does not repeat trio A's lever; trio B's dose is kept if its update is faster per
datum at a flat primary, dropped otherwise)."* The R7 runner encodes this as two bits: heads kept
iff trio A's mechanism MOVED, batch kept iff trio B is faster per datum; moved+faster -> `ab`,
moved only -> `a`, faster only -> `b`, neither -> `w`.

- **Trio B: FASTER -> the batch is KEPT.** Per env step over 20M-180M, from each lane's
  `history.csv` (`scripts/extract_history.py`; zero resumes, so single wandb runs):

  | per env step | W (R5, 3 lanes) | B (3 lanes) | B / W | z (3 vs 3 lanes) |
  |---|---|---|---|---|
  | update | 573.7 us | 562.2 us | **0.980x** | -1.55 |
  | collect | 224.5 us | 213.5 us | 0.951x | -- |
  | total | 798.1 us | 775.7 us | **0.972x** | -1.63 |

  Faster on the point estimate, ~1.6 se across three lanes; the header asks only "faster". Both
  fleets ran six-wide, and B's context was the heavier one (trio A's lanes, plus R7's niced G0 /
  G1 / G1b beside part of it), so the comparison does not flatter B. The rule and the result agree,
  so no maintainer line was needed.
- **Trio A: NOT MOVED -> the heads are DROPPED.** The pre-registered mechanism co-primary (turn-2-8
  by-turn r^2 against the rollout oracle must LIFT above the R5 W finals' 0.287 on positions drawn the
  same way in the same run) ran 01:43-02:01Z on 2026-09-25, both sides in parallel from the PINNED
  worktree `../pokemon-showdown-rl-r6pin` (25bad2c; `rl/` and the instrument's scripts identical to
  the R6 launch commit 907adc6), `PYTHONPATH` set to it and verified per process (the analysis env's
  editable install otherwise imports main's `rl/`, and the R7 merge landed on main 45 s after launch).
  Trio A with C6 on, the R5 W finals with C6 off. Draw = the 09-18 run's (its rows hold ep 0-799 ->
  `--battles 800`; dets 4 x rollouts 8, max-stop 36, seed 20260917). A 688 positions, W 687.
  `critic_calibration.py --compare` (B - A = trio A minus R5 W; se unpaired), verbatim:

  ```
  BY-TURN r^2: A = r5W_finals   B = trioA_finals
       turns   n_a    r2_a   n_b    r2_b      B-A      se      z
         2-8   168   0.317   167   0.353   +0.036   0.082   0.44
        9-15   165   0.572   166   0.487   -0.085   0.077  -1.10
       16-22   184   0.582   186   0.591   +0.009   0.073   0.12
        23-+   170   0.629   169   0.644   +0.015   0.074   0.21
    se is UNPAIRED (the two runs sample different positions); a bucket's z is descriptive.
  ```

  **The pre-registered bucket: +0.036 at z 0.44 -- not distinguishable from zero.** The header's words
  split two ways, stated rather than resolved silently: read LITERALLY, trio A's 0.353 is above the
  quoted 0.287, which gives `ab`; read with error bars against the same-run comparator -- which is
  what `critic_calibration.py`'s own header says this co-primary is for ("read with error bars instead
  of by eye") -- it is no lift, and the instrument's own re-draw noise is the same size: the IDENTICAL
  R5 W critic read 0.287 on 09-18 and 0.317 here, +0.030 with nothing changed. The 9-15 bucket fell
  (-0.085, z -1.10). Both runners recommended `b` (the heads also cost 1.16x W's update per datum).
- **R7's BASE: `b`, RULED by the maintainer at ~02:10Z** (in the r7-runner's session; recorded in
  621a7af and SESSION_LOGS 2026-09-25 02:11Z) -- trio B's recipe (W + C6 + the x4 batch, fallback
  form), warm from trio B's finals, no outcome heads. The nine 2M LR-smoke configs derive from it
  (621a7af; donor f1 = PIN-b's b328, sha f09063696cda...).

## Disclosures

- Both FP@20 disclosures, on every number above: the equivalence test is weakly powered, and the
  point estimate flatters us. Budget named: 20 ms per decision.
- **Every FP arm ran with `loop_breaker: true`** (ruling #1), the R5 re-draws included, which is why
  the R5 floor is re-drawn in this session and never quoted from the bank.
- **Every FP arm, seat, and the Showdown server ran at nice 5 / PRI 31**, inherited through zsh's
  `BG_NICE` from the agent's launching shell (SESSION_LOGS 2026-09-24 01:55Z). Matched across all
  arms; plain nice keeps the P-cores (the lanes at nice 5 ran at the W fleet's speed); background
  QoS (PRI 4) is what clamps to the efficiency cores.
- **The FP gate held 0 times** (the queue logs zero `HOLD` lines): no process at >= 50% of a core
  over a 20 s CPU-time delta and no foreign-env python was on the box at any arm boundary. No arm
  or job failed (zero `NO JSON` / `NO FINAL` lines).
- The queue was relaunched five times while in WAIT (six WAIT lines in its log: the 09-22 launch plus five) to pick up gate and caffeinate changes (it
  re-execs from a frozen temp copy); every relaunch happened with nothing past WAIT in its log. The
  queue held its own `caffeinate -i -s -w` for the unattended phases.
- vs-SH S1/S2 compare against R5's **banked** vs-SH reads (a different session) -- descriptive only;
  vs SH is the saturated axis and never the verdict.
- E9RF is a **mixed** C6-on/C6-off committee (`POKEMON_RL_ENCODER_C6_ALLOW_MISMATCH=1`), disclosed as
  such.
- The six R6 lanes: all 200M, **zero resumes, zero Node restarts** (both watchdogs' exit lines).
  R7's niced instruments (G0, G1, G1b) ran beside the TRAINING fleet only -- never beside an FP arm.

## The raw readout, verbatim (`results/r6_reads_offfp/READOUT.txt`)

```
R6 READS -- off FP@20 PRIMARY (credit line) + object pick; vs SH descriptive
Disclosures on every FP@20 number: the equivalence test is weakly powered, and the
point estimate flatters us. Budget: FP@20 = search_time_ms 20 per decision. Every
off-FP arm runs with loop_breaker: true (ruling #1) -- a policy-form change vs every
banked number, which is why the R5 floor is RE-DRAWN below and never quoted.

OFF FP@20 singles (n=3000 each):
  trio A finals: 0.5483 (n=3000) / 0.5573 (n=3000) / 0.5227 (n=3000)
  trio B finals: 0.5617 (n=3000) / 0.5617 (n=3000) / 0.5763 (n=3000)
  R5 W re-draw: 0.5447 (n=3000) / 0.5437 (n=3000) / 0.5467 (n=3000)
  pooled: A 0.5428 (n=9000) | B 0.5666 (n=9000) | W re-draw 0.5450 (n=9000)
OFF FP@20 committees (n=3000 each):
  E3AF 0.5753 (n=3000) | E3BF 0.6080 (n=3000) | E6RF 0.6097 (n=3000) | E9RF 0.6017 (n=3000) (MIXED c6) | floor E3WR 0.5917 (n=3000)

R1 THE PRIMARY, per trio (credit line verbatim; boundary = NOT met):
  trio A (outcome heads, IDEAS 4.11): delta -0.0022  se_binomial 0.0074  se_clustered 0.0104  -> se_diff 0.0104  z -0.21  CELL A-FLAT
  trio B (batch/epochs, IDEAS 4.12): delta +0.0216  se_binomial 0.0074  se_clustered 0.0050  -> se_diff 0.0074  z 2.91  CELL B-FLAT
  C6 is common-mode on every R6 lane and confounded with each lever by construction; uncredited.

R2 THE LADDER OBJECT: highest candidate; top two within 0.013 -> the larger committee;
   none reaches E3WR - 0.013 -> the R5 committee stays the object.
  LADDER OBJECT = E6RF (highest point estimate)
  E3AF - E3WR: -0.0163 at -1.28 se_diff (se 0.0127)
  E3BF - E3WR: +0.0163 at 1.29 se_diff (se 0.0126)
  E6RF - E3WR: +0.0180 at 1.42 se_diff (se 0.0126)
  E9RF - E3WR: +0.0100 at 0.79 se_diff (se 0.0127)

R3 COMMITTEE GAIN PER TRIO (3000 vs 9000; the R5 W trio read +0.0417 over its floor):
  E3AF - mean(GA): +0.0326 at 3.12 se_diff (se 0.0104)
  E3BF - mean(GB): +0.0414 at 4.01 se_diff (se 0.0103)
  E3WR - mean(GW re-draw)  [same session]: +0.0467 at 4.49 se_diff (se 0.0104)

R4 MEMBERS:
  E9RF - E6RF  (do the c6-off W finals still add? MIXED object): -0.0080 at -0.63 se_diff (se 0.0126)
  E6RF - better ENS3: +0.0017 at 0.13 se_diff (se 0.0126)

vs SH, LOCKED form (no loop breaker), 3000/lane x 3 or 3 batches x 3000:
  GA: 0.8193 (n=9000)  [ga_a304 0.80933, ga_a312 0.82667, ga_a320 0.82200]
  GB: 0.8458 (n=9000)  [gb_b328 0.84700, gb_b336 0.83600, gb_b344 0.85433]
  E3A: 0.8457 (n=9000)  [e3a_b0 0.85367, e3a_b1 0.84133, e3a_b2 0.84200]
  E3B: 0.8670 (n=9000)  [e3b_b0 0.87133, e3b_b1 0.86567, e3b_b2 0.86400]
  E6R: 0.8640 (n=9000)  [e6r_b0 0.85567, e6r_b1 0.87033, e6r_b2 0.86600]
  E9R: 0.8616 (n=9000)  [e9r_b0 0.85133, e9r_b1 0.87300, e9r_b2 0.86033]
  R5 GW (banked): 0.8217 (n=9000)  [gw_w104 0.82133, gw_w112 0.82167, gw_w120 0.82200]
  R5 E3W (banked): 0.8386 (n=9000)  [e3w_b0 0.82833, e3w_b1 0.84900, e3w_b2 0.83833]
S1 (descriptive; vs SH is the saturated axis):
  GA - R5 GW(banked): -0.0023 at -0.41 se_diff (se 0.0057)
  GB - R5 GW(banked): +0.0241 at 4.35 se_diff (se 0.0055)
  GA - 100M A0 0.78867: +0.0307 at 5.19 se_diff (se 0.0059)
  GB - 100M A0 0.78867: +0.0571 at 9.94 se_diff (se 0.0057)
S2:
  E3A - R5 E3W(banked): +0.0071 at 1.31 se_diff (se 0.0054)
  E3B - R5 E3W(banked): +0.0284 at 5.39 se_diff (se 0.0053)
  E6R - R5 E3W(banked): +0.0254 at 4.80 se_diff (se 0.0053)
  E9R - R5 E3W(banked): +0.0230 at 4.32 se_diff (se 0.0053)
S3 committee gain per trio:
  E3A - GA: +0.0263 at 4.73 se_diff (se 0.0056)
  E3B - GB: +0.0212 at 4.06 se_diff (se 0.0052)

Credit line (verbatim, CLAUDE.md): a lever is credited iff pooled delta >= +0.025 AND
>= 2*se_diff, where se_diff is the LARGER of the pooled-binomial se_diff and the
seed-clustered se_diff, the latter computed from the per-seed finals at read time.
R1 is the only credit read; every other number here is descriptive.
-> results/r6_reads_offfp/readout.json
```
