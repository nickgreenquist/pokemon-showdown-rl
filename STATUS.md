# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-13 — D23 READ OUT: letter-met, NOT credited; nothing running)

**Pure from-scratch self-play in gen1randombattle is the chase** (novelty over strength;
r7; encoder frozen v2/808+ids=828). 50M chapter CLOSED (0.5802 CREDIT, seed-fragile);
D18 priv-critic NULL, falsifier-killed. **D23 REGEN-L2 (λ=0.02 toward-init, 3 treatment
+ 2 fresh comparator lanes): Δ +0.0451 (0.5897 vs 5-seed comparator 0.5445) —
"letter-met, seed-fragile, NOT credited" per the pre-stated rule (clustered 2·se 0.0650;
spread 0.0491, s44 0.6463 vs arm-mates 0.561). MECHANISM: BOUND (species_emb ×4.10-4.17
vs control ×5.8-6.1); final→peak gap SHRANK (+0.0114 vs D18 +0.0274 — realized against
the adversarial confound); srank 2-3× control (31/53/36 vs 11-17) but de-collapse letter
NOT met (≥40 on ≥2/3); falsifier NOT fired — family neither killed nor closed.** MAJOR
FINDING: fresh comparator lanes (0.5763, 0.4937) put true Rung-2 12M seed sd at ≈0.036
(3-seed said 0.026) → 12M win-rate primaries are un-creditable; mechanism carries rungs.

## Results (vs SH; ties=loss; locked = final ckpt, 3×3000/seed; *probe/†1000-seed era)

| result | win rate |
|---|---|
| PPO 12M flat / +LR anneal — best vs-SH-TRAINED RL | 0.4330† / 0.4607† |
| Self-play 12M control (v2/808, flat MLP) | 0.3996 ± 0.0052 |
| Rung 1 SIGNAL (γ0.95 + H&L shaping) — NULL | 0.4131 ± 0.0052 |
| Rung 2 STRUCTURE 12M (entity DeepSets ptr) — CREDIT | 0.5509 ± 0.0052 |
| Rung 2 comparator refresh (5 seeds, 2026-08-13) | 0.5445, sd 0.0356 |
| **Rung 3 50M finals — CREDIT (seed-fragile, see log)** | **0.5802 ± 0.0052** |
| D18 priv-critic 12M — NULL, falsifier-killed | 0.5364 ± 0.0066 |
| D23 regen-L2 12M — letter-met, NOT credited (s44 0.6463!) | 0.5897 ± 0.0066 |
| BC-of-FP clone graded final / val-peak = M4 bar | 0.5490 / 0.5777 ± 0.0090 |
| SH mirror parity 0.489 · FP engine 0.812-against* | clone h2h 0.643 pooled |

**LADDER:** M1/M2/**M3 CLAIMED at 12M** · M4: letter-met at 50M, NOT claimed.

## Next actions, in order (maintainer decisions at the top)

0. **DECIDED 2026-08-13: branch (b), the 50M REGEN-L2 CARRY** (maintainer, over D19
   and over both-sequenced; ~5 lane-days accepted past the 20-day cap, chapter
   ~17/20). NEXT STEP: pre-registration under the 2-Opus design process, **written
   mechanism-primary** — weight norms + srank at 50M (where D22 diagnosed the
   pathology and D23 only tested at 12M) as PRIMARY, win rate SECONDARY, since 50M
   is seed-fragile too and an advisory-scale delta will land in the recording band
   again. Then a cap/lane-day accounting line, then launch by the maintainer.
   D19 deferred behind it (unread; DESIGN §12 carries its status note). Push DONE.
2. Post-chase bundle: comparator-spread finding + D23 mechanism story (README and
   DESIGN §12 queue state are current through the readout).
3. 250M: per §13 — needs a credited 50M lever + the cap/rent answer (E1-E4 cleared).

## Watch items

- Seeds: 0-13, 23-46, 50-51 SPENT; **49 BURNED**; 14-22 RESERVED; 99 disposable;
  **47-48, 52+ free.**
- Entity ckpts need BOTH env vars; D23 treatment ckpts eval fine on the plain path
  (theta0 never needed at eval; theta0.pt lives in each run dir).
- Eval auto-tie crash (~1-in-10⁴ eval battles) can kill a lane (killed s49 at 7.2M →
  re-run s51); same-seed relaunch hits zombie battles — relaunch FRESH seed (log 08-12).
- Artifacts: results/d23/ (gitignored) — grade.txt, 8 eval JSONs, norms, ranks.
- Suite 293 green (R0-3 golden needs its own pytest process — 1-ULP flake, log).
- Design process (standing, maintainer 2026-08-12): pre-regs/lever designs get 2
  Opus design agents + 2 Opus reviews before ratification — D23 is the template.
