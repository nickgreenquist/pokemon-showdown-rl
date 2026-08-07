# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-07 — PIVOT RATIFIED)

**Pure from-scratch self-play in gen1randombattle is the main chase** (novelty over
strength; revocable per D17). **DESIGN r7 RATIFIED 2026-08-07 — D10a/D11a/D12b/D13a/D14a/
D15b/D16a/D17a all binding.** FP/BC chapter BANKED (eval anchors + fallback): teacher 0.8307
(n=7,200), tapes 180k rows, v2 clone 0.558/0.569*, warmrl on ice. Pushed through 288a347.

## Results (vs SH; ties=loss; locked = final ckpt, 3 seeds, n=3000/seed per D2c.
## *Starred rows are probe reads: 1 fit seed and/or n=1000.)

| result | win rate |
|---|---|
| PPO 12M flat / **+LR anneal — best vs-SH-trained RL** | 0.4330 / **0.4607** |
| **Scratch self-play 12M: v1+broken pool / v2+fixed pool** | **0.3800 / 0.3890** (null, z +0.7) |
| BC clone of SH (P4, 813k rows) | **0.4657** |
| SH-vs-SH mirror = parity; caps imitators only | **0.489** (0.486 at n=40k) |
| Foul Play (+patch) — teacher; banked anchor | **0.8307** (n=7,200)* |
| BC-of-FP v2 180k: final / val-peak — banked anchor | 0.558 / **0.569*** |

**MILESTONE LADDER (r7 §2, RATIFIED):** M1 ≥0.4400 (go/no-go) · M2 ≥0.489 parity ·
M3 ≥0.510 past SH (**the success claim, D10a**) · M4 ≥0.558 stretch. All at 3×3000,
non-SH-anchor guard from M2 up. vs-SH ADMISSIBLE (SH held out of training entirely).

## Next actions, in order

1. **TONIGHT (D13a): MUST_RECHARGE Stage-0 fix + 3×12M control re-run** on the fixed
   encoder (v2/808), seeds 31/32/33 — the new comparator REPLACES 0.3890. Then locked eval
   3×3000.
2. **Rung 1 (SIGNAL) the night after:** control config verbatim + gamma 0.95 + H&L 5-term
   zero-sum shaping (constants from metagrok's code); seeds 23/24/25; pre-reg
   `configs/showdown_sp_signal12m.yaml`. Code items: `hl_shaping` kwarg, `--no-shaping`
   eval seam, R0-2 antisymmetry gate. Rung 2 draft: `showdown_sp_struct12m.yaml` (26/27/28).
3. **Rung 0 measurement evening (E1-E4, ≤10 min each, D12b/D14a):** decompose the loop at
   [512,512] per `prior_work/THROUGHPUT_SPEC.md`; cheap wins authorized on their numbers.
4. ON ICE, zero rework: warmrl (seeds 14-22 reserved), P4-scale GO (19.7 h), §11 D8/D9.
   D17 abandon criterion armed: below M1 after Rungs 1+2+50M, or >20 lane-days, or >8 wks.

## Watch items

- Seeds: 0/1/2 lra, 3/4/5 lra12m, 6/7/8 ArmB, 9 smoke, 10-13 SP preview+smoke, 14-22
  RESERVED (warmrl), 23+ = the chase. Distinct across lanes AND arms (username landmine).
  Showdown evals are UNPAIRED and non-reproducible — buy precision with battles.
- `showdown/config/config.js` `simulator: 4` — gitignored; re-set if re-cloned (+81%).
- **Encoder freezes at v2/808 once the Stage-0 fix lands (D13a):** dead MUST_RECHARGE slot
  → live `mon.must_recharge` bool (both actives) + global move-slots-aliased flag at vec[5].
  OBS_DIM 807→808 (v1 611→612) — invalidates all pre-fix checkpoints for re-eval; the
  fingerprint stamp is the guard, CHECK IT per lane (R0-1). 0.3890 is DEAD as a comparator
  once the re-baseline reads out.
- **Rung 1 shaping is NOT Arm B:** non-cancelled, zero-sum, 5-term, gamma 0.95, mirror play
  — Arm B's null (cancelled potential-based single term vs SH) does not transfer. Its R0
  gate: both seats' shaping sums to exactly 0 per event; shaping/terminal mass ratio logged.
- BC-warm-start landmines (on ice with warmrl): loss/entropy 0.063 from update 1; critic
  warmup 5 at rollout 512; grad clip binds harder on warm starts (0.67→0.94).
- `score_ladder.py` default `--opponents` raises on Showdown (use `eval_checkpoint.py`). H&L
  scale accounting (both seats?) unresolved — settle from metagrok before Rung 3's budget.
