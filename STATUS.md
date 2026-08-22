# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-22 — **R1 PART 3 DONE: harvest 13.7k decisions,
matrix/SearchAgent landed, spike 58 ms/decision @ Dose M, FG battery run.
FG-4/5/6/7 PASS · FG-2 0.8946 vs bar 0.98 BLOCKING FAIL (causes named, 3-evening
repair clock RUNNING) · FG-2k 0.093 > 0.05 -> 2-point roll expansion REQUIRED
before R2 · FG-1 needs a maintainer ruling (engine from_string drops volatiles)**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE, not the
levers**; expert data excluded. **Recipe: entity arch + oppact aux + LR anneal =
0.3996 -> 0.5509 -> 0.6185 -> 0.71825 (D26 12M, CREDITED HEADLINE).** CH3 ratified
(depth-1 only). R0: ensemble-of-4 B1 CREDIT 0.74633 ("THESE four checkpoints");
K0-1 PASS 0.780 -> V-leaf allowed; flip anchor 0.103. R1 reads that matter: spike
58 ms/decision (all estimates beaten), successor-ranking AUC 0.816 (supports
V-leaf), oppact sh_accuracy 0.42-0.48 vs 0.436 marginal (promoted head adds
LITTLE vs SH — named confound, measured), q entropy low (MF-4 fallback inert),
Z2' truncation negligible. Three engine landmines pinned by tests (full-name
statuses; readback UPPERCASES volatiles; from_string drops volatiles).

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| R2 12M 0.5509 · R3 50M 0.5802 · D25 aux 0.6185 · placebo 0.5415 | — |
| **D26 +LR anneal 12M — B1 CREDIT, HEADLINE** (+0.0998, p 1/126) | **0.71825** |
| D29r2 50M — R-A CREDIT (named cell) / R-B FLAT · 5-lane desc 0.7181 | 0.70222 |
| D28 zero-info control — A1 (p 1/252), NOT SEALED (late dose collapse) | 0.52240 |
| CH3 R0 ensemble-of-4 — B1 CREDIT (+0.036, THESE four ckpts only) | 0.74633 |

## Next actions
1. **Maintainer rulings needed to close R1**: (a) FG-1 scope — engine
   from_string drops volatiles, so byte-identity caps at 742/800; object
   construction carries the load; (b) FG-2 repair route within the 3-evening
   clock: candidates = KO-skip recharge exclusion (secondary 0.9035),
   transformed-Ditto stratum, engine sleep-interrupt/speed-tie fidelity;
   fallback = A-sidecar (design §2) or chapter stops.
2. **Build the FG-2k 2-point roll expansion** (0.093 > 0.05 — pre-registered
   repair, ~2x leaf cost) and re-price via the spike before R2.
3. Then the R2 driver: `--search` branch on ch3_eval.py + chunk-0 raise-on-
   access sentinel (SF-13). Dose M frozen off the spike; node cap 1500 holds.
4. Push: 12 local commits — say the word.
5. Standing: §13/250M futility ruling (rec RETIRE); resume-from-checkpoint
   (24h bar); D7(a) ladder ruling only if R2 lands B1.

## Watch items
- **Spike flip rate vs recorded greedy = 0.635** — descriptive only; R2
  adjudicates whether flips WIN. Quote it nowhere as a strength claim.
- FG-2p 0.6171 < 0.95 -> placeholder stratum OUT-OF-SCOPE per pre-reg (§3 skip
  covers it); FG-6 budget FROZEN as named families incl. transform_ditto.
- D28's A1 quoted WITH "not sealed"; D29r2 R-A is a NAMED CELL; README ± are
  binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies (ch3_r1 incl. harvest+battery backed up
  to `../pokemon-showdown-rl-d25-backup-20260815/`). Seeds 66/67, 75/76,
  83/84, 93/94 held — ch3 burns none. vs-SH 0.72 is still ~40% GXE.
