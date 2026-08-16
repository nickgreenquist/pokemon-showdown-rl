# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-16 — **D19 CLOSED; NOTHING RUNNING; ONE OPEN CALL**)
**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). **D25 CREDITED 0.6185; D25-P's placebo lands dead on
the comparator (0.5415), so the INFORMATION did the work; M1-M4 all claimed.** Licensed
sentence: *an explicit opponent-action model helps* — with C3(b) self-model, C4
representational-only and the P3 dose caveat in the same breath. **NEVER "belief state".**
50M CLOSED; D18 NULL; D23 not-credited; **D19 KILLED at zero lanes**.

## Results (vs SH; ties=loss; locked = final ckpt; 5×3000 from D23 on)
| result | win rate |
|---|---|
| Rung 2 12M 0.5509 · Rung 3 50M 0.5802 · D18 0.5364 · D23 0.5897 · clone 0.5503 | — |
| **D25 oppact-aux 12M — CREDIT** (bar 0.58273) · **M1-M4 CLAIMED** | **0.6185** |
| **D25-P placebo — FLAT**, Δ -0.0030; R-1 T-vs-P Δ **+0.0770** CREDITS | **0.5415** |

## D19 is closed — do not re-queue it (`results/d19_closeout/`, zero lanes)
Killed 2026-08-13 at zero lanes (teams are near-independent near-uniform draws) and
**re-targeted into D25**; `showdown_sp_actpred12m.yaml:130` = "The D19 KILL STANDS." The
one unmeasured channel — whether the opponent's PLAY leaks its team — is now measured
shut: **+0.0061 nats of a 4.873-nat target; +0.0123 total (0.25%)**, best phase +0.024 vs
D25's 0.63-0.65 there; controls (planted answer +2.55, leaked team +3.73) make it an
information verdict, not a wrong-shaped estimator. **A session was sent here on 2026-08-16
because `DESIGN.md` was 3 days stale and recorded D24/D25 zero times — DESIGN is NOT
self-updating; check it against SESSION_LOGS.**

## Next actions — **ONE OPEN MAINTAINER CALL; everything else is zero-lane**
1. **THE CALL: spend the last ~2.09 lane-days, or close the chapter?** Chase is at
   **17.91/20**. A 5-lane 12M arm — the only shape the credit machinery is enumerated for
   (levels at 1/252) — costs ~2.17 and **no longer fits**; 4 lanes ≈ 1.74 fits but re-opens
   every pre-registered level. Budget and method ran out together. D17's 20-day line is an
   **abandon-on-failure trigger, not a budget**: its payload is "write it up as a measured
   negative", with no branch for "on success, buy more".
2. **If spending:** a **matched-dose aux control**, closing the one live alternative to
   D25's claim (watch item 1). Needs its own design cycle — a shuffled label floors out,
   so matching dose needs a different target, not a config edit.
3. **Zero-lane, worth doing either way:** the **C4 opponent-transfer probe** — does the
   trunk model *an opponent* or only itself? `actpred12m.yaml:1489` says transfer is
   UNTESTED; reuses `d25_atoms.py`. Then **R-6**, and a README rewrite.
4. **Needs the maintainer:** DESIGN §8's D7(a) defers ladder execution "until M2/M3" —
   **now satisfied** — while CLAUDE.md's landmine forbids it. Two ratified docs contradict.

## Watch items
- **THE DOSE CAVEAT IS PART OF THE CLAIM.** Placebo `aux/trunk_norm` ran at 3-31% of the
  frozen band (12/12 bins), so R-2's flatness does NOT refute "a generic aux gradient of
  matched size would help" — untested, not eliminated.
- **R-5 needs `--s1-control results/d23/dormant_d25_control.csv`** for n_C=5 (default is
  s26/27/28 only). **Three ctx metrics, do not conflate:** R-5 reads tau025; srank99
  collapses on the placebo (s58 218→14) while dormancy stays high; live ctx units is a 3rd.
- **Never read R0-8 off `time/steps_per_sec`** (361 vs wall 312) — use Δstep/Δruntime; and
  **in-loop `eval/win_rate` (n=100) does NOT preview a locked number** (0.576 vs 0.5415).
- **`results/d25/`, `d25p/`, `d19_closeout/` are the ONLY copies** of the frozen tapes and
  grade artifacts; all three backed up at `../pokemon-showdown-rl-d25-backup-20260815/`.
- **No DESIGN §11** (r7 retired §10-11; §8 calls search "moot"); everything IS pushed;
  **LEDGER 17.91/20**, re-measured 2026-08-16 twice (78 dirs, 429.7 h). vs-SH 0.6185 is
  still ~40% GXE — not "nearly solved." Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED;
  14-22 RESERVED; 47-48 held; 52-56 = D25; 57-61 = D25-P (SPENT); 62+ free.
