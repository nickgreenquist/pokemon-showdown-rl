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

## D19 is closed — do not re-queue it (`results/d19_closeout/`)
Killed 2026-08-13, **re-targeted into D25**; `actpred12m.yaml:130` = "The D19 KILL STANDS."
**Say why correctly — CORRECTION 5 (`SESSION_LOGS.md:3238`) retracted "independent
near-uniform draws" as FALSE**; the type/weakness caps bind on 0 of 600k teams. Right
sentence: **88-90% is a cap MASK; the belief residual is 0.024-0.034 nats of 4.955** vs
D25's 0.544 beyond mask+marginal — **~16-23x, not the "~1.6x" at `:3250`**.

## Next actions
1. **D26, the final arm — 4 lanes, 12M, seeds 62-65, ~1.74 lane-days -> 19.65/20. FITS.**
   **CORRECTION: n=5 is NOT "the only shape the credit machinery is enumerated for" and n=4
   does NOT "re-open every level"** — `d25_grade.py:94` has `{5:(12,252), 4:(6,126),
   3:(2,56)}` and **6/126 = 12/252 = 0.047619, identical**; n=4 costs only min-p.
2. **THE CALL IS GENUINELY CLOSE.** Required delta to credit **+0.032 to +0.053** (pooled
   0.650-0.672), but the anneal's horizon-matched effect is **+0.0277 at 12M**
   (`SESSION_LOGS.md:170`, "direction replicates, magnitude does not", Welch p~0.12) — NOT
   DESIGN.md:101's +0.051, the 6M number. **The bar exceeds the lever's own best measured
   effect.** P(CREDIT) 0.23-0.44; modal outcome FLAT/letter-met 0.61-0.75.
3. **BOTH DESIGNERS RECOMMEND ANNEAL-ONLY over the anneal+λ bundle.** Bundling buys ~2
   points of P(CREDIT) under an honest λ prior, nearly doubles P(NEGATIVE), and **requires
   overriding ratified `DESIGN.md:786`**, which names these two levers and forbids this
   exact bundle. λ=1.0 has zero in-repo execution and an UNVERIFIED citation.
4. **Blocking build gate:** `ppo.py:999` (anneal × aux-head, param group 2) has **never
   executed** — no run, no test; `tests/test_ppo.py:494` unpacks 2 groups and would raise.
5. **Zero-lane either way:** the C4 transfer probe (`actpred12m.yaml:1489`); **R-6**.
6. **Maintainer:** DESIGN §8 D7(a) defers the ladder eval "until M2/M3" — now satisfied —
   while CLAUDE.md's landmine forbids it. Two ratified docs contradict; one must move.

## Watch items
- **THE DOSE CAVEAT IS PART OF THE CLAIM.** Placebo `aux/trunk_norm` ran at 3-31% of the
  frozen band, so R-2's flatness does NOT refute "a generic aux gradient of matched size
  would help" — untested, not eliminated.
- **README error bars are BINOMIAL; the seed-clustered se governs**, 2.66x larger.
- **Three ctx metrics, do not conflate:** tau025 dormancy, srank99, live ctx units. (R-5,
  if ever re-run, needs `--s1-control results/d23/dormant_d25_control.csv` for n_C=5.)
- **Never read R0-8 off `time/steps_per_sec`** (361 vs wall 312) — use Δstep/Δruntime;
  **in-loop `eval/win_rate` (n=100) does NOT preview a locked number** (0.576 vs 0.5415).
- **`results/d25/`, `d25p/`, `d19_closeout/` are the ONLY copies** of the frozen tapes and
  grade artifacts; all three backed up at `../pokemon-showdown-rl-d25-backup-20260815/`.
- **No DESIGN §11**; all pushed; **LEDGER 17.91/20** (78 dirs, 429.7 h, measured twice).
  Seeds 62-65 = D26, 66/67 held, 68+ free.
- vs-SH 0.6185 is still ~40% GXE — not "nearly solved."
