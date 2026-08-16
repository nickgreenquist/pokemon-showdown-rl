# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-16 — **D19 CLOSED; D26 DESIGNED, AWAITING RATIFICATION**)
**Pure from-scratch self-play in gen1randombattle is the chase. The NOVELTY IS THE LANE,
not the levers** — proven technique inside it is fine (DESIGN §5:390); expert-data
bootstrapping is what's excluded. **D25 CREDITED 0.6185; its placebo lands dead on the
comparator (0.5415), so the INFORMATION did the work; M1-M4 all claimed.** Licensed: *an
explicit opponent-action model helps*, **and it TRANSFERS to an opponent never trained
against (C4 discharged 2026-08-16)** — C3(b) and the dose caveat remain; **NEVER "belief
state"**. 50M CLOSED; D18 NULL; D23 not-credited; D19 KILLED. `RESULTS.md` = the account.

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25-P placebo — FLAT** Δ -0.0030; R-1 T-vs-P Δ **+0.0770** CREDITS | **0.5415** |

## D19 is closed (`results/d19_closeout/`; full account in RESULTS.md)
Killed 2026-08-13, re-targeted into D25. **CORRECTION 5 (`SESSION_LOGS.md:3238`) retracted
"independent near-uniform draws" as FALSE**: 88-90% is a cap MASK, belief residual
0.024-0.034 nats of 4.955.

## Next actions
0. **D27 (matched-dose control) IS DEAD** — zero lanes, mechanism in `RESULTS.md` §5. Do
   not re-propose a rescaled shuffled-label placebo. D26+D27 = 21.53 > 20: always a swap.
1. **C4 TRANSFER PROBE: RUN, FIRED, C4 DISCHARGED** (`results/c4_transfer/`, zero lanes).
   D25 ctx decodes SH +0.0665 vs controls' +0.0366, exact p = 1/252 both label spaces, on
   an opponent no lane trained against. De-dormancy confound (r=+0.94, no arm overlap)
   CLEARED by a post-hoc capacity-matched refit at K=131 (+0.0318, p=1/252 x3). C3(b) NOT
   discharged.
2. **D26 (LR anneal) — 4 lanes, 12M, seeds 62-65, ~1.74 lane-days -> 19.65/20. FITS.**
   Header ratifiable at `configs/showdown_sp_recipe12m.yaml`; R0-A passes (exactly
   {seed, run_name, lr_anneal_steps} differ). **Maintainer chose to run it.**
3. **R0-B STILL OWED, BLOCKING BEFORE LAUNCH:** `ppo.py:999` (anneal x aux-head, group 2)
   has **never executed** — no config pairs a live aux head with a live anneal, no test
   combines them. The gate must drive a REAL `update()` (aux agent + `opp_choice` in the
   batch) per `tests/test_ppo.py::_lr_after_fill`; a formula-only test was drafted and
   discarded as fake cover. Then R0-C/E/F/G/H/I/J.
4. **s_T DECIDES D26.** Required delta **+0.025 to +0.053**: below the s_T~0.0134 crossover
   the +0.025 FLOOR governs (bar 0.6435, BELOW the lever's own effect); in the D18/D23/D25
   range the bar is 0.650-0.672, ABOVE it. The anneal is **+0.0277 at 12M**, not
   DESIGN.md:101's +0.051 (6M). **P(CREDIT) 0.23-0.39 typical, 0.60-0.75 if s_T low.**
   ANNEAL-ONLY, not the anneal+lambda bundle (both designers; bundling needs a
   `DESIGN.md:786` override and doubles P(NEGATIVE)).
5. **Maintainer:** DESIGN §8 D7(a) defers the ladder eval "until M2/M3" (now satisfied)
   while CLAUDE.md forbids it. Two ratified docs contradict; one must move.

## Watch items
- **THE DOSE CAVEAT: "untested, AND this control cannot test it".** A shuffled head cannot
  be dosed — it routes the marginal into `slot_bias` and disconnects its trunk path
  (fraction 0.44-0.54 -> 0.05-0.09 vs treatment 0.51-0.62), so matching the trunk needs
  ~58x coef = ~8.3x total. No scalar changes a fraction. `RESULTS.md` §5.
- **README error bars are BINOMIAL; the seed-clustered se governs**, 2.66x larger.
- **Never read R0-8 off `time/steps_per_sec`** (361 vs wall 312) — use Δstep/Δruntime;
  **in-loop `eval/win_rate` (n=100) does NOT preview a locked number** (0.576 vs 0.5415).
- **`results/d25/`, `d25p/`, `d19_closeout/`, `c4_transfer/` are the ONLY copies** of the
  tapes and grade artifacts; all backed up at `../pokemon-showdown-rl-d25-backup-20260815/`.
- **No DESIGN §11**; all pushed; **LEDGER 17.91/20** (78 dirs, 429.7 h, measured twice).
  Seeds 62-65 = D26, 66/67 held, 68+ free. vs-SH 0.6185 is still ~40% GXE.
