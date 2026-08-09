# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-09 — 50M PRE-REGISTRATION DRAFTED, AWAITS RATIFICATION)

**Pure from-scratch self-play in gen1randombattle is the main chase** (novelty over
strength; r7 RATIFIED; encoder frozen v2/808 + gated id suffix 828 for entity trunks).
**RUNG 2 (STRUCTURE) CREDITED 2026-08-09, branch (a): s26 0.5633 / s27 0.5683 / s28
0.5210, pooled 0.5509 ± 0.0052 (3×3000) vs 0.3996 ± 0.0052 → delta +0.1513, z +20.5.
THE FLAT READOUT WAS THE BINDER** (matched params 626,059 ≤ 681,994; every gate green).
**M1 PASSED. M2/M3 GUARD-BACKED (F1 complete): clone h2h 0.657 ± 0.015 pooled; FP-itself
0.824-against (vs 0.876 over old best — teacher gap closed ~5 pts); v2r 0.612; MaxBP
+9.2. Formal blessing sentence NOT yet issued** ("results look great" is a reaction, not
the blessing) — get it and record it before M3 is cited as claimed. Suite 267 green.
Pushed through 93342b5; commits after it (handoff, 50M draft) are LOCAL — push ask-first.

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
claim**) guard-backed, AWAIT BLESSING · M4 ≥0.5777 stretch (now protocol-grade).

## Next actions, in order

1. **Maintainer: formal M2/M3 blessing sentence** — record it in SESSION_LOGS.
2. **Maintainer: ratify `configs/showdown_sp_struct50m.yaml`** (drafted 2026-08-09,
   PROPOSED, do-not-launch). Rung 3 step 1: structure only, γ1.0, no shaping, seeds
   35/36/37, comparator 0.5509, credit bar ≥0.5759, M4 read ≥0.5777 + anchor guard,
   ckpt 500k / eval 250k (deviation from §4's 100k recorded), ~40 h wall as-is at the
   measured 350 steps/s/lane 3-wide (~15 h/lane IF Rung 0's ~2.6× projection holds).
3. Push to origin (ask-first). Rung 0 E1-E4 measurement evening still owed (D12b) —
   feeds D15 (rent-a-box vs local) and the post-throughput budget line.
4. Settle H&L seat accounting from metagrok BEFORE any 250M budget is set (gates the
   250M quote, not the 50M launch). ON ICE unchanged: warmrl (14-22), §11 D8/D9.

## Watch items

- Seeds: 0-13, 23-34 SPENT, 14-22 RESERVED (warmrl), 99 disposable; 35/36/37 assigned
  to the 50M lanes (draft); 38+ free. Distinct across lanes AND arms.
- **Entity checkpoints need BOTH env vars at every eval** (v2 + ids → 828); a forgotten
  var dies loudly at trunk construction — designed seam.
- **Cross-encoder cross-play needs the shim** (828 vs 808 ok; v2/807 refused, no map).
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- 3-wide lane throughput is ~350 steps/s/lane (not the solo smoke's 552) — budget with
  the measured number. `score_ladder.py --opponents` raises on Showdown (use
  eval_checkpoint.py). Laptop sleep suspends lanes harmlessly but kills session
  Monitors — TaskStop the zombie, re-arm; `caffeinate -is` for the 50M lanes.
