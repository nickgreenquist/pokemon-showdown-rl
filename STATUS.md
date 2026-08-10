# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-09 — M2/M3 CLAIMED; 50M RATIFIED — LAUNCH IS NEXT)

**Pure from-scratch self-play in gen1randombattle is the main chase** (novelty over
strength; r7 RATIFIED; encoder frozen v2/808 + gated id suffix 828 for entity trunks).
**RUNG 2 (STRUCTURE) CREDITED 2026-08-09, branch (a): s26 0.5633 / s27 0.5683 / s28
0.5210, pooled 0.5509 ± 0.0052 (3×3000) vs 0.3996 ± 0.0052 → delta +0.1513, z +20.5.
THE FLAT READOUT WAS THE BINDER** (matched params 626,059 ≤ 681,994; every gate green).
**M1 PASSED. M2 + M3 (the success claim) FORMALLY CLAIMED 2026-08-09** — blessing issued
by the maintainer, recorded verbatim in SESSION_LOGS; F1 guard in full (clone h2h 0.657
± 0.015 pooled; FP-itself 0.824-against vs 0.876 over old best — teacher gap closed ~5
pts; v2r 0.612; MaxBP +9.2). README/results may now call M3 delivered at 12M. Suite 267
green. Pushed through the blessing commit 2026-08-09 (authorized); push stays ask-first.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed per D2c; *probe: 1 seed/n=1000)

| result | win rate |
|---|---|
| PPO 12M flat / +LR anneal — best vs-SH-trained RL | 0.4330 / 0.4607 |
| Self-play 12M control on v2/808 — Rung 2's comparator | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL, branch (b) | 0.4131 ± 0.0052 (z +1.84) |
| **Rung 2 STRUCTURE (entity DeepSets ptr) — CREDIT (a)** | **0.5509 ± 0.0052** (z +20.5) |
| BC clone of SH (P4, 813k rows) | 0.4657 |
| SH-vs-SH mirror = parity; caps imitators only | 0.489 (0.486 at n=40k) |
| FP-clone v2r graded 3000: final / **val-peak = M4 bar** | 0.5490 / **0.5777 ± 0.0090** |
| Foul Play (+patch) teacher* / takes off Rung 2 (n=250) | 0.8307* / 0.824-against |

**MILESTONE LADDER (r7 §2):** M1 ≥0.4400 **PASSED** · M2 ≥0.489 / M3 ≥0.510 (**success
claim**) **CLAIMED 2026-08-09** · M4 ≥0.5777 stretch (now protocol-grade).

## Next actions, in order

1. **LAUNCH the 50M lanes** — `configs/showdown_sp_struct50m.yaml` RATIFIED 2026-08-09
   as drafted (Rung 3 step 1: structure only, γ1.0, no shaping; comparator 0.5509,
   credit bar ≥0.5759, M4 ≥0.5777 + anchor guard; ~40 h wall at 350 steps/s/lane).
   Seeds 35/36/37, maintainer's terminal, staggered, caffeinate, verify per R0-8
   (battle PROGRESS within 15 min, ≥300 steps/s warm), from a clean committed tree.
2. After finals: locked eval 3×3000 + anchor guard (clone h2h pooled, FP engine 250);
   branch per header — (a) credit → M4 read + 250M decision; (b)/(c) per file.
3. Rung 0 E1-E4 measurement evening still owed (D12b) — feeds D15; needs an IDLE box
   (before launch or after readout, never alongside the lanes).
4. README rewrite DEFERRED to the 50M readout (fold finals + M3 claim + r7 narrative;
   README stays current thereafter — standing directive). **DESIGN §12 D18–D20
   PROPOSED 2026-08-09** (post-50M levers: privileged critic first, aux opponent-
   prediction, v3 encoder bundle) — ratify at readout. H&L seat accounting before
   any 250M budget. ON ICE: warmrl (14-22), §11 D8/D9.

## Watch items

- Seeds: 0-13, 23-37 SPENT (35/36/37 = 50M lanes), 14-22 RESERVED (warmrl), 99
  disposable; 38+ free. Distinct across lanes AND arms.
- **Entity ckpts need BOTH env vars at every eval** (v2 + ids → 828; forgotten var dies
  loudly — designed seam). Cross-encoder play needs the shim (808 ok; 807 refused).
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- 3-wide throughput ~350 steps/s/lane (solo smoke 552) — budget with the measured
  number. `score_ladder.py --opponents` raises on Showdown (use eval_checkpoint.py).
  Sleep suspends lanes harmlessly but kills Monitors — TaskStop zombie; caffeinate.
