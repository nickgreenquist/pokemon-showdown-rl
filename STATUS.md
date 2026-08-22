# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-22 — **R1 PART 3 + EXPANSION DONE: harvest 13.7k
decisions; matrix/SearchAgent/2-point-roll-expansion landed; FG battery:
FG-1/4/5/6/7 PASS (FG-1 re-scoped per ruling: volatile-free byte-identity
100%) · FG-2k residual 0.0928 -> 0.0082 post-expansion (Dose M re-priced 73.2
ms/decision) · FG-2 0.9057 vs bar 0.98 still BLOCKING — DV lead run to ground
(max-DV now EVIDENCE-BASED: 94.85% of realized stats exactly max; sampling and
expected-8 both measured worse); next repair: Ditto transform, ~2 evenings**)
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
1. **FG-2 deeper repair, ~2 evenings left**: top fixable = TRANSFORMED DITTO
   (poke-env exposes copied base stats; bridge uses them but the det level/
   stat path and shadow static-dex path diverge); then turn-order edges
   (speed ties; slept-mon-still-explodes is engine-internal — may end as a
   named residual). Fallback stays: A-sidecar (design §2) or chapter stops.
   FG-1 CLOSED (ruled re-scope, PASS).
2. ~~Roll expansion~~ DONE (rl/search/expansion.py; residual 0.0082; spike
   re-priced 73.2 ms/dec; flip rate 0.635 -> 0.51). Next build: the R2 driver
   (`--search` on ch3_eval.py + chunk-0 sentinel, SF-13) once FG-2 is ruled.
3. Push: 4 local commits — say the word.
5. Standing: §13/250M futility ruling (rec RETIRE); resume-from-checkpoint
   (24h bar); D7(a) ladder ruling only if R2 lands B1.

## Watch items
- **Spike flip rate vs recorded greedy = 0.51 (post-expansion)** — descriptive
  only; R2 adjudicates whether flips WIN. Quote it nowhere as a strength claim.
- The part-3d 'engine keeps MUSTRECHARGE after KO' claim was WRONG (engine
  implements KO-skip itself); corrected in the 08-22 evening log entry.
- FG-2p 0.6171 < 0.95 -> placeholder stratum OUT-OF-SCOPE per pre-reg (§3 skip
  covers it); FG-6 budget FROZEN as named families incl. transform_ditto.
- D28's A1 quoted WITH "not sealed"; D29r2 R-A is a NAMED CELL; README ± are
  binomial except ‡; never read throughput off `time/steps_per_sec`.
- `results/` dirs are the ONLY copies (ch3_r1 incl. harvest+battery backed up
  to `../pokemon-showdown-rl-d25-backup-20260815/`). Seeds 66/67, 75/76,
  83/84, 93/94 held — ch3 burns none. vs-SH 0.72 is still ~40% GXE.
