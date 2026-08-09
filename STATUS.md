# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-09 — RUNG 2 CREDIT)

**Pure from-scratch self-play in gen1randombattle is the main chase** (novelty over
strength; r7 RATIFIED; encoder frozen v2/808 + gated id suffix 828 for entity trunks).
**RUNG 2 (STRUCTURE) READ OUT 2026-08-09: CREDIT, branch (a) — s26 0.5633 / s27 0.5683 /
s28 0.5210, pooled 0.5509 ± 0.0052 (3×3000) vs 0.3996 ± 0.0052 → delta +0.1513, z +20.5.
THE FLAT READOUT WAS THE BINDER** (input null, signal null, structure credits at matched
params 626,059 ≤ 681,994). Every gate green (R0-1/6, R1, K6, sign-guard exact). **M1
PASSED (every seed). M2/M3 numerically cleared — worst seed 0.5210 > 0.510 — but claims
PEND the mandatory non-SH-anchor guard (F1 head-to-heads).** Beats best vs-SH-trained
(0.4607) and SH clone (0.4657); never saw SH in training. Suite 264 green. NOT pushed.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed per D2c; *probe: 1 seed/n=1000)

| result | win rate |
|---|---|
| PPO 12M flat / +LR anneal — best vs-SH-trained RL | 0.4330 / 0.4607 |
| Self-play 12M control on v2/808 — COMPARATOR (3×3000) | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL, branch (b) | 0.4131 ± 0.0052 (z +1.84) |
| **Rung 2 STRUCTURE (entity DeepSets ptr) — CREDIT (a)** | **0.5509 ± 0.0052** (z +20.5) |
| BC clone of SH (P4, 813k rows) | 0.4657 |
| SH-vs-SH mirror = parity; caps imitators only | 0.489 (0.486 at n=40k) |
| Foul Play (+patch) — teacher / BC-of-FP v2 val-peak | 0.8307* / 0.569* |
| Rung 2 s26 vs MaxBasePower (v2r-best s32: 0.749*) | 0.841* — gain generalizes |

**MILESTONE LADDER (r7 §2):** M1 ≥0.4400 **PASSED** · M2 ≥0.489 / M3 ≥0.510 (**success
claim**) numerically cleared, AWAIT F1 guard · M4 ≥0.558 stretch (re-grade clone first).

## Next actions, in order

1. **M2/M3 GUARD (now owed — trigger fired):** build the cross-encoder eval shim (one
   process = one encoder; seat-2 slices vec[:808], exact by pure-suffix design), then
   F1 two-orientation head-to-heads 500/pair/orientation vs FP clone (protocol-grade it
   first) and/or Foul Play. S1 vs v2r final rides the same shim.
2. **50M pre-registration, STRUCTURE ONLY** per branch (a): entity trunk, γ1.0, no
   shaping, 3 seeds, own config header. Price with D15 (3-wide ~350 steps/s → ~40 h/lane
   at 50M; loop re-architecture is the named enabler — now clearly worth it).
3. Push to origin (ask-first). Rung 0 E1-E4 measurement evening still owed (D12b).
4. SUPERSEDED by the credit: the 2026-08-08 branch-(d) stack is moot — RECIPE rung is
   now an optional secondary lever; relax-purity is answered (no). BC arm = optional
   comparison chapter, not a hedge. ON ICE unchanged: warmrl (14-22), §11 D8/D9.

## Watch items

- Seeds: 0-13, 23-34 SPENT (26/27/28 Rung 2, 30 arch smoke), 14-22 RESERVED (warmrl),
  99 disposable integration smoke; 35+ free. Distinct across lanes AND arms.
- **Entity checkpoints need BOTH env vars at every eval** (v2 + ids → 828); a forgotten
  var dies loudly at trunk construction (tokenizer assert) — that's the designed seam.
- **Cross-encoder cross-play is blocked without the shim** — 828 vs 808/807 checkpoints
  cannot share a process today; FP-clone ckpts are v2/807 (pre-recharge-fix) on top.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- `score_ladder.py --opponents` raises on Showdown (use `eval_checkpoint.py`). H&L seat
  accounting unresolved — settle from metagrok before any Rung-3-scale budget.
- 3-wide lane throughput is ~350 steps/s/lane (not the solo smoke's 552) — budget with
  the measured number.
