# STATUS
## JOURNEY POSITION — step 11 DONE (R5 LISTED). The post-ladder SEARCH chapter is CLOSED, and closed by a CORRECTION PASS
**THE EXIT GATE READ 09-21 22:22Z (§35, `readouts/EXIT_GATE_R5_READOUT.md`): CLEARS — XTG9 (gumbel tree, iters 900) **0.6184** vs XGR (greedy committee, control first) **0.5866**, n=3200 each, **delta +0.0319 at z +2.61** (se 0.0122); five R0 gates PASS, G2 exact on both arms; 771 ms/decision, change rate 0.110. IDEAS 4.9 (expert iteration on the tree vehicle) gets R7's first trio — a pre-reg after R6's readout, never a fleet on this number alone. ALL THREE 400k SMOKES PASS (09-21 23:08Z; `results/r6_smokes/`). **BOTH 4.12 SCREENS ARE READ AND THEY DISAGREE, WHICH IS THE POINT:** the GO keys (epochs 2 / mb 120 / lr 3.5e-4) read **FALLBACK** (00:25Z, `results/r6_batch12m/read.json`: entropy 0.48 vs W's 0.70, EV 0.49 vs 0.69, policy travel 0.72 vs 15.4 — 21× less at matched env steps), the **FALLBACK keys** (epochs 4 / mb 480 / lr 2.5e-4, optimizer steps per datum matched to W) **PASS all three checks** (01:33Z, `results/r6_batch12m/read_fallback.json`: per-update kl [0.0099, 0.0402] in band and rising like W's, last-bin entropy 0.73 / 0.69 vs W's 0.70, last-bin EV 0.66 vs 0.69, travel 2.83 vs 15.4). So the ×4 batch is only safe with the optimizer steps held — trio B is the fallback form. RULED 09-22 00:27Z (verbatim in trio A's header): THE AGENT LAUNCHES THE FLEET AND MONITORS. **The kill-and-relaunch contingency was RETIRED 09-22 11:10Z on the morning read** — trio B runs **0.94–0.96×** the maintainer-launched W fleet's 1,254 steps/s six-wide and trio A **0.78×** (the outcome head's second backward pass, arm cost not launch context; both trios share one box, so the A-vs-B spread isolates it). Maintainer verbatim: *"1.15x is not a slowdown worth changing anything"*. `docs/landmines.md` "Job lifetime, not throughput" now carries the fleet-scale measurement — do not re-raise agent-side throughput as a reason to hand a run over. RULED 09-22 00:45Z: **Ladder R6 only if the object R2 picks beats the same-session re-drawn R5 committee (E3WR) off FP@20 by a point delta ≥ +0.05** — M-R6-10 **RATIFIED 09-24 00:50Z**, maintainer: *"i want to ladder again with a real winning gain. we already hit our 'goal' of this project: reach the ladder. resources and time should be spent on step change"*. A bar for spending exposure, not for detecting improvement (~3.9 se_diff at 3000 vs 3000); disclosed cost: R5's object cleared its floor by +0.042 and listed, so +0.03..+0.05 gains go unladdered by design. Otherwise R6's finals are R7's base and the next ladder run is R7's. **R6 IS READ (QUEUE DONE 09-25 01:07:53Z; `readouts/R6_READS_READOUT.md`).** Six lanes x 200M, zero resumes, zero Node restarts; pinned 04:37Z (A 1b923a0, B 342bdf3); 14 FP@20 arms + 18 vs-SH jobs, the FP gate held 0 times, no job failed. **R1 PRIMARY (off FP@20, 9000 vs 9000 vs the same-session re-drawn R5 finals): trio B (x4 batch) +0.0216 at z 2.91 -- statistically clear, all 9 B-vs-R5 lane pairings favour B, but 0.003 under the +0.025 SIZE floor, so cell B-FLAT, uncredited; trio A (outcome heads) -0.0022 at z -0.21, A-FLAT.** vs SH agrees descriptively (B +0.0241 at z 4.35 vs R5's banked read; A -0.0023). B vs A, the one clean contrast: +0.0238 at z 2.07. C6 is common-mode, unattributable. **NO LADDER R6:** R2's object E6RF (all six R6 finals) is +0.0180 over E3WR at z 1.42, the M-R6-10 bar is +0.05. Committee gain per trio +0.033..+0.047 over its own singles (R3) -- still the largest lever; E9RF (adding the R5 W finals) -0.0080 vs E6RF. **R7's BASE (the trio headers' X-FLAT action, two bits): batch KEPT -- B is faster per datum (update 0.980x, total 0.972x W's per env step, ~1.6 se); heads DROPPED -- trio A's pre-registered instrument read NOT MOVED (turn-2-8 by-turn r^2 0.353 vs the same-run R5 W 0.317, +0.036 at z 0.44; the identical R5 critic itself moved +0.030 between runs), run from the pinned worktree with PYTHONPATH. R7's BASE RULED `b` by the maintainer ~02:10Z (621a7af): trio B's recipe, warm from trio B's finals, no heads.** Disclosed on every FP number: loop_breaker on every arm; every arm, seat and the server at nice 5 / PRI 31 via zsh BG_NICE (matched; not the E-core landmine).**
ran 09-18/19 (§25–§32); **three Opus review passes then went back over every claim and
changed sixteen of them, retracted one section in full, and found three numbers I had
invented while writing the corrections themselves.** Read §30.1's retraction box and the
§27.1 CV box before quoting anything from this week.

## THE FIVE RESULTS WORTH CARRYING FORWARD
**§30 — GREEDY BEATS EVERY SEARCH ARM, and it is a COST, not another null.** n=1000×7 off
FP@20 on the R5 committee with an in-session anchor: **GC greedy 0.6050** is the top of the
block. Ungated depth-1 **−0.052 at 2.4 se**; depth-2 **−0.076 / −0.098 at 3.4–4.4 se**.
**The block validated itself** — D1O and DUM are the SAME config on two username pairs and
read **0.5510 / 0.5530, |d| 0.0020**, so the within-session floor is a tenth of one
cross-session rung. **"Monotone in the change rate" was published and is FALSE** (0.584 at
6.4% rises to 0.587 at 9.1%); the defensible claim is the level ordering.
**§30/8.5 — the committee does NOT know WHERE to search, but SEARCHING LESS BEAT SEARCHING
MORE.** Gated on committee disagreement vs a **COIN at a matched rate: +0.0030 at 0.14 se,
selection is a null.** Gated (40%) vs ungated (93%), both replicates pooled per side:
**+0.0335 at 2.14 se**, clearing both halves of the credit line. Post-hoc pooling, credits
nothing — but the dose intuition is backwards.
**§27 + §27.1 — THE LUCK CEILING, and the critic's real deficit.** 707 positions / 22,358
rollouts: **~64% of a mid-battle outcome is IRREDUCIBLE**; ceiling **0.3630**, critic
**0.2176**. **THE GATE OPENS — the critic is NOT done.** Out-of-sample isotonic buys
**+0.0096, only ~7% of the gap: 93% is RANKING** (corrected from 12/88 — the published CV
split at the OUTCOME level while the predictor is constant within a POSITION, so every
held-out outcome had its own position in training). Worst in
the **OPENING** (r² 0.287 at turns 2–8 vs 0.727 at 23+). **Never set the training EV 0.59
against this ceiling** — a different state distribution.
**§31 — THE CRITIC IS NOT ANTISYMMETRIC: +0.059 to whichever side it is pointed at,
z 14.7**, 5× larger in the opening. **Mechanism identified:** that is its training
distribution's own mean return — league play fits it against *older, weaker* checkpoints
(+0.036 whole-run) while eval is a mirror where the truth is 0. **A TRAIN/EVAL
DISTRIBUTION SHIFT. IDEAS 4.1's claim on this evidence is WITHDRAWN** (p1/p2 are
symmetric); 4.1 keeps its sample-efficiency argument.
**§28 + §29 — two facts about our own policy form.** §28: **103 of 104 turn-cap battles
enumerated** — 100 are switch loops, **94 (91.3%)** with the opponent immobilised on ≥80%
of turns while our seat oscillates. **The mechanism is the locked protocol's own
DETERMINISM**: argmax in a state that stopped changing repeats forever; training SAMPLES.
§29: **the annealed tail trades EV for WIN RATE in 9 lanes of 9** — EV
−0.060/−0.088/−0.005, win rate +0.059/+0.062/+0.033. **DO NOT FLOOR THE LR. Third
independent measurement that EV IS NOT THE OBJECTIVE** (§21 width, §27.1 ranking, §29).

## WHAT THE REVIEW PASSES CHANGED — **read before citing anything from this week**
**Five review passes. ~25 claims changed, ONE SECTION RETRACTED, and several of the errors
were INSIDE the corrections.** The full table is in SESSION_LOGS 2026-09-19 and 2026-09-19 (cont.); the four that change what
you may cite:
- **§30.1 RETRACTED IN FULL.** It relaxed the "never difference across sessions" landmine
  on a G-test whose power at 0.02 is **0.13** (it claimed "G≈12, p≈0.02" without computing
  it). Heterogeneity sits **between days** (G 2.760 of 3.139 on 2 df). **THE LANDMINE
  STANDS**, on the honest ground that 0.02 is UNRESOLVED. Pooled greedy **0.5818 (n=6500)**
  keeps. The retraction did NOT reach `docs/landmines.md` for a day — it does now.
- **§27.1: 12%/88% → 7%/93%** (the CV split at the OUTCOME level while the predictor is
  constant within a POSITION). **"Affine beats isotonic" is WITHDRAWN — a SEED-0 artifact**:
  over 40 CV seeds +0.00055 ± 0.00128, affine ahead 24/40, the margin *half of isotonic's
  own seed-to-seed sd*. **One CV fold draw is one rung.**
- **§28's "every stall" rested on SIX battles** → 91.3%. **§31's "the sampler is exonerated"
  INVERTS its own probe** (V(s) and V(swap(s)) share a determinization, so it carries zero
  information about the sampler). **§32 withdrew the "90.9% of root visits" caveat** quoted
  all week: one smoke decision; measured `pi_top1` **0.417** vs the prior's 0.885.
- **THE CORRECTIONS THEMSELVES NEEDED CORRECTING SIX TIMES** — a KL lifted from a GOLDEN
  TEST FIXTURE, an uncomputed median G *inside the paragraph charging that a number was
  never computed*, a test asserting a SOURCE STRING (so it survived commenting the code
  out), and a denominator wrong at six sites. **Both lessons are in `docs/landmines.md` and
  CLAUDE.md** — STATUS is rewritten in place and cannot hold them.
- **NINE defect-class fixes, all ONE shape — a dial or counter that runs and reports
  nothing, or the wrong thing.** Structural repair: `ch3_eval` DERIVES its forwarded dials
  from `SearchAgent`'s signature and **hard-fails on an unknown pre-reg key**.

## Next actions
1. **R6 PREP — DONE 09-20/21: the action gap banked (§33), 4.11's heads + loss BUILT (unsmoked), the C6 RUST
   PORT LANDED (P-1 zero mismatches, flag on: ruling 2 met, C6 rides R6), the R6 trio configs DRAFTED with the launcher's C6 export, and R7's ARCHITECTURE GATE READ: the attention screen DOES NOT CLEAR (§34: +0.0179 at 6.52×, flat reveal profile = generic capacity; no R7 attention trio).** NEXT, after QUEUE DONE: the 4.12 screen, the 400k smokes (`scripts/r6_smokes.sh` → `scripts/r6_smoke_check.py`, every expectation derived), the exit-gate readout (`scripts/exit_gate_readout.py`, computed from disk), the screen read (`scripts/r6_batch12m_read.py`), the fleet (maintainer launches); the post-fleet reads are BUILT (`scripts/r6_reads_queue.sh`, `configs/eval/r6_reads*.yaml`); then the split-schedule ladder ONLY IF the reads show an R6 committee ≥ +0.05 off FP@20 over the re-drawn R5 committee (RULED in principle 09-22: "if we dont see offline gains: why ladder"; threshold to confirm — M-R6-10 in the DRAFT `docs/proposals/ladder_r6.draft.yaml`, M-R6-1..10 owed); below it the R6 finals are R7's base and R7 ladders.
2. **The search chapter is closed for now: §30 is a measured COST, not a null.** The next
   search idea must argue against the override regression (−0.48 win rate per unit override
   fraction, r −0.875, leave-one-out stable), not merely propose another vehicle.
3. **The live lever is the CRITIC, and §27/§27.1/§31 say what is wrong with it**: 93% of
   the gap is RANKING, worst in the opening, and the train/eval shift is measured at +0.059.
   `docs/IDEAS_POST_100M.md` Round 4 is re-ranked around that. **4.9 is the top §4 item; its 2.11 gate OPENED and its exit gate CLEARED (§35) — R7's first trio. R7 RATIFIED 09-22 (JOURNEY 14 opened early):
   `docs/proposals/R7_NATIVE_SEARCH_PLAN_2026-09-22.md`, frozen at amendment box 3 until G0 reads. R7 B0–B3, B1, B1b (resample + fusion pass) and **B5 (learner seams, `bc24570`)** BUILT 09-23 on branch `r7-native-search` (worktree `../pokemon-showdown-rl-r7`, fresh env `pkmn-engine-r7`; all tests green; ruling 7 defaulted to 5 lanes). **G0 ran niced beside the fleet 09-23 00:38Z–16:15Z** (500/500 positions, rows `results/r7_g0/rollout_q.rows.jsonl`; a-trio lanes ~5% under their pre-G0 bands, disclosed in SESSION_LOGS 01:35Z). The merge to main and the B0 bench (pass line 3.6 ms p99 six-wide) WAIT for the idle box after the R6 reads queue (Fri 09-25 ~05:00 EDT) — a running block imports the working tree. **RULED 09-23 11:40Z: R7 IS THE KITCHEN SINK** — the ExIt fleet's base is the stacked recipe (SESSION_LOGS 11:40Z), searched vs coef-0 control on it; arch-class levers lap after. **B4 BUILT 11:47Z** (`311c3b5`, `bb25203`: the child-process collector with the T-op inside, weights shipped per update, backpressure, the loop runs and resumes it). **G0 READ 16:30Z (`readouts/R7_G0_READOUT.md`): the kill does NOT fire — split-sample depth-1 ceiling +0.0236 ± 0.0028 win-rate (upper95 +0.0292), zero-gap null −0.0003; fusion bound ≈ 0 (P3 intact); the dial sweep sets the T-op at k 4 / S 2 / τ 0.05 / gate 0.01 (10% override, 17% of the ceiling, no cell negative); the simultaneous-move root-rule read: greedy is exploitable by −0.052 at the oracle level and regret matching halves it, but at the critic level every rule is within noise — the EVALUATOR is the binding constraint. AMENDMENT BOX 4 written. **G1 READ 21:24Z (`readouts/R7_G1_READOUT.md`): the gated L-op beats its own greedy by +0.0504 ± 0.0050 win-rate in the engine mirror (n 10,000, 10.1 se) at 9.6% override — the operator's BEST case (the true world + the foe's exact prior). Writing it found box 4 item 4's fusion pass ran at τ 1.0, where the operator barely moves: re-read at the working dials (`scripts/rollout_q_belief.py`) the choice depends on the hidden world ~9× more and the peek is unresolved per decision, but the fusion cost stays under §10's floor (upper95 +0.0008/decision) — the T-op stays B = 1 (AMENDMENT BOX 5). G1b (belief arms, B = 8, paired on battle seed with re-runs that reproduce G1's rows) READ 09-24 02:24Z (below).** **B6's gate R1-E PASSES on the full corpus (19:55Z, `readouts/R1E_ENGINE_READOUT.md`: 99.7% of built roots bitwise, mask parity exact, 256 refused by family); `rollout_q/2` and the `root_rule` dial landed (`8f30bb4`).** **The evaluator read (22:35Z, box 5 item 7): fine-tuning the critic on G0's 500 positions fits them (in-sample Spearman +0.497 → +0.663) and transfers nothing (out of fold +0.004 ± 0.006) — G0's rows are too few; the fleet does not wait on an evaluator step.** Two design corrections (box 5 items 5–6): B2 out of the fleet's base (the T-op's leaf is the learner's own critic, so it would peek at every leaf), the control never plays. **G2 BUILT (branch `54c2f40`; pre-reg `configs/eval/r7_g2.yaml`, RATIFIED 09-24 00:20Z, runs after the fleet); the warm start's θ0 path pre-built (`7014f11`); the B0 bench reads its pass line at the fleet's form (`f640049`).** **G2 reviewed twice (DRAFT r2 `666b660`: the bridge had handed the foe our whole team — fixed; the worlds now sample the foe active's moves). The mmap'd team bank — ruling 6's precondition — BUILT (`7c6cb40`, install Friday). R-E2 RULED YES and LANDED (`38f7736`: the scorer factorization, ~26% of the epoch loop, `_GEN1_PIN` re-baselined; no other golden moves). RULED 00:20Z (box 6): the fleet starts WARM from the base trio's R6 finals, paired by final, +100M; width 3+3 if B0 passes six-wide (else 3+2); G2 RATIFIED, runs AFTER the fleet (smoke Friday). THE FLEET PRE-REG r3 IS A GENERATOR** (`scripts/derive_r7_fleet.py`, branch `068ccaf`; AMENDMENT BOX 7): two Opus reviews + two verification passes + two focused passes, every verified finding fixed -- the LR rule could never have read the LR (approx_kl carries KL(pi'||pi_theta) on searched rows; now split by the search mask, nine smokes incl. a beta-0 comparator), the shakedown's resume could never have run at base b (checkpoint.pt every 4 updates; length now derived), read (vi) had no instrument (`scripts/r7_mechanism_reads.py`, reproduces G0 exactly), power stated (P(X-POS) 0.49/0.72/0.88 at +0.025/.030/.035), X-GAIN added and X-FLAT routed on the mechanism reads. **BOX 7 RULED 09-25 ~01:05Z (maintainer, as recommended): X-FLAT's routing as written; n 6000 PER LANE; beta·KL inside the shared clip. R6 READ (QUEUE DONE 01:07:53Z): base `ab` or `b` (trio B faster per datum -> batch kept by its own rule; trio A's heads on its instrument), no Ladder R6 (E6RF +0.0180 < +0.05). R7 MERGED 01:43:52Z (`9d6a1f8`), both engine envs rebuilt; B0 VERDICT (the quiet-box re-run 03:52Z, verdict-bearing by the pre-run ruling): FAIL -- six-wide p99 7.460 ms vs 3.6 (the noisy first run 7.531; mean 1.76-2.15 ms, at the plan's 1.8; the tail is the critic forward, structural) -> the fleet is 3 + 2 by R-F2 (`readouts/R7_B0_BENCH.md`). BASE RULED `b` 02:10Z (maintainer): trio B's recipe, warm from trio B's finals, no heads; the nine LR-smoke configs committed. NEXT: `scripts/r7_smokes.sh lr b` (~3 h; fp-speedup's calibration done 03:50Z) -> `--stage fleet --b0 FAIL` -> shakedown.** **G1b READ 02:24Z (box 5 item 8): the belief L-op beats its own greedy +0.0553 ± 0.0070 in the mirror; belief minus true, paired on 4,993 battles, +0.0022 ± 0.0079 -- the peek is worth nothing measurable at the battle level; G2 (after the fleet) is the live test.** Friday's order is box 7's: R6 readout -> the a7 session's FP probe (~45 min; `../pokemon-showdown-rl-fpprobe/results/fp_parallel_probe/STATUS` releases the box) -> merge -> reinstall BOTH engine envs + the suite (the mmap test and `test_r7_mechanism_reads.py` PASS, not skip) -> B0 `--widths 5 6` at nice 0 -> the base -> `--stage lr-smokes` -> `scripts/r7_smokes.sh lr <base>` -> `--stage fleet` -> `scripts/r7_smokes.sh shakedown` -> G2's smoke -> the maintainer launches (`scripts/r7_fleet_launch.sh`). Launch from bash: zsh's BG_NICE nices `cmd &` +5.**
4. **THE SIX R6 RULINGS ARE TAKEN (maintainer, 2026-09-20, "agree with all"):** loop breaker ON
   for the ladder object; C6 in R6 only if the Rust port lands first; fleet = W base, trio A
   outcome heads, trio B batch/epochs; R6 ladder under the split schedule; 2.13 stays OFF; the
   two R7 gates run now (the exit-gate queue was relaunched 09-20). Also: 4.9's fleet waits on
   that gate; 8.6's re-run is subsumed by it. **The LR-anneal floor: DO NOT floor it (§29).**
5. **THE ACTION GAP IS MEASURED (RESULTS §33, `readouts/ACTION_GAP_R5_READOUT.md`): a perfect
   top-2 swap is worth 0.032 naive [0.022, 0.043] / 0.024 deconvolved of win rate per decision —
   AT the credit floor, NEITHER a mechanism kill NOR a licence.** Noise alone would print 0.029;
   true gaps have sd ≈ 0.16 outcome units, ordered right ~59% of the time. The exit gate CLEARED (§35: +0.0319 at +2.61 se).

## Watch items
- **A SMALL-RUN NULL IS NOT EVIDENCE ABOUT A LEVER** (CLAUDE.md rule 6). §30's selection
  null is quoted as *"+0.003 at 0.022 se"*, never as a kill: it does not exclude a
  credit-sized effect. **§30's ungated arms ARE a kill-shaped result** because they measure
  a COST at 2.4–4.4 se, which is the distinction rule 6 turns on.
- **SEEDS DO NOT PAIR BATTLES**; replicates are the instrument. **Never difference across
  sessions without an in-block anchor** (§30.1 retraction).
- **PRE-REG IS FOR LADDER RUNS AND HEADLINE CLAIMS ONLY** (2026-09-17) — hacking needs
  none, and the anti-self-deception rules do not relax: **counters to disk, matched
  comparisons, same-session anchors.** All three were violated at least once this week and
  each violation was caught only by a second pass.
