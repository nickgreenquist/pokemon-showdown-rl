# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-16 — **D19 CLOSED; D26 DESIGNED, AWAITING RATIFICATION**)
**Pure from-scratch self-play in gen1randombattle is the chase. The NOVELTY IS THE LANE,
not the levers** — proven technique inside it is fine (DESIGN §5:390); expert-data
bootstrapping is what's excluded. **D25 CREDITED 0.6185; its placebo lands dead on the
comparator (0.5415), so the INFORMATION did the work; M1-M4 all claimed.** Licensed: *an
explicit opponent-action model helps*, with C3(b)/C4/dose caveats — **NEVER "belief
state"**. 50M CLOSED; D18 NULL; D23 not-credited; D19 KILLED. `RESULTS.md` = the account.

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25-P placebo — FLAT** Δ -0.0030; R-1 T-vs-P Δ **+0.0770** CREDITS | **0.5415** |

## D19 is closed — do not re-queue it (`results/d19_closeout/`; full account in RESULTS.md)
Killed 2026-08-13, re-targeted into D25. **Say why correctly — CORRECTION 5
(`SESSION_LOGS.md:3238`) retracted "independent near-uniform draws" as FALSE.** Right
sentence: 88-90% of the structure is a cap MASK; belief residual 0.024-0.034 nats of 4.955.

## Next actions
0. **D27 (matched-dose control) IS DEAD — zero lanes, mechanism in `RESULTS.md` §5. Do not
   re-propose a rescaled shuffled-label placebo.** D26+D27 = 21.53 > 20: always a swap.
1. **D26, the final arm — 4 lanes, 12M, seeds 62-65, ~1.74 lane-days -> 19.65/20. FITS.**
   **CORRECTION: n=5 is NOT "the only shape the credit machinery is enumerated for" and n=4
   does NOT "re-open every level"** — `d25_grade.py:94` has `{5:(12,252), 4:(6,126),
   3:(2,56)}` and **6/126 = 12/252 = 0.047619, identical**; n=4 costs only min-p.
2. **THE CALL IS CLOSE AND s_T DECIDES IT.** Required delta **+0.025 to +0.053**: below the
   s_T~0.0134 crossover the +0.025 FLOOR governs (bar 0.6435, BELOW the lever's own effect);
   in the D18/D23/D25 range the bar is 0.650-0.672, ABOVE it. The anneal is **+0.0277 at
   12M** (`SESSION_LOGS.md:170`), not DESIGN.md:101's +0.051 (the 6M number). **P(CREDIT)
   0.23-0.39 typical, 0.60-0.75 if s_T lands low**; six 12M arms came in below 0.0236.
3. **ANNEAL-ONLY, not the anneal+λ bundle** (both designers): bundling buys ~2 points of
   P(CREDIT), doubles P(NEGATIVE), and needs an override of ratified `DESIGN.md:786`.
4. **Blocking build gate:** `ppo.py:999` (anneal × aux-head, group 2) has **never executed**
   — no config pairs a live aux head with a live anneal, and no test combines them.
5. **Zero-lane either way:** the C4 transfer probe; **R-6**.
6. **Maintainer:** DESIGN §8 D7(a) defers the ladder eval "until M2/M3" (now satisfied)
   while CLAUDE.md forbids it. Two ratified docs contradict; one must move.

## Watch items
- **THE DOSE CAVEAT: now "untested, AND this control cannot test it".** Placebo trunk
  dose was ~1.2-21.9% of the frozen band (the "3-31%" recorded earlier was against the
  0.7x THRESHOLD, not the band — both designers flagged it independently). **A shuffled
  head cannot be dosed**: it routes the marginal into `slot_bias` and disconnects its
  trunk path (fraction 0.44-0.54 -> 0.05-0.09 vs treatment 0.51-0.62), so matching the
  trunk needs ~58x coef = ~8.3x total. No scalar changes a fraction. See `RESULTS.md` §5.
- **README error bars are BINOMIAL; the seed-clustered se governs**, 2.66x larger.
- **Three ctx metrics, do not conflate:** tau025 dormancy, srank99, live ctx units.
- **Never read R0-8 off `time/steps_per_sec`** (361 vs wall 312) — use Δstep/Δruntime;
  **in-loop `eval/win_rate` (n=100) does NOT preview a locked number** (0.576 vs 0.5415).
- **`results/d25/`, `d25p/`, `d19_closeout/` are the ONLY copies** of the frozen tapes and
  grade artifacts; all three backed up at `../pokemon-showdown-rl-d25-backup-20260815/`.
- **No DESIGN §11**; all pushed; **LEDGER 17.91/20** (78 dirs, 429.7 h, measured twice).
  Seeds 62-65 = D26, 66/67 held, 68+ free.
- vs-SH 0.6185 is still ~40% GXE — not "nearly solved."
