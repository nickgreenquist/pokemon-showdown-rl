# IDEAS_POST_100M — audited candidate levers (2026-09-01)

Source: `~/Downloads/pokemon_rl_ideas.md` (a 2026-09-01 env-less code audit),
re-audited this session against the code, the committed record, and
`prior_work/README.md`; verified claims are cited in place and the source
doc's errors are corrected in §7. **Not a pre-registration.** Every fleet
item here needs its own pre-reg header (credit line restated verbatim,
`journey_step` named) before anything launches.

**Sequencing floor (binding):** nothing below runs before FLEET DONE → the
frozen eval schedule → grade → record (HANDOFF §§1–3; the peeking bar covers
*any* checkpoint eval until the last lane ends). After the record lands,
**JOURNEY step 2 (ladder #3) is next on every branch** (HANDOFF §4.4);
fleet-scale retrains below are **step 8** work unless the maintainer pulls
one forward the way the 100M was.

---

## 1. The constraint that orders everything

σ_seed ≈ 0.0617 at k=3 (SESSION_LOGS 2026-08-28: R1-A bar 0.0717 =
2·σ_seed/√3; s_50(off-FP) 0.0617 ≈ vs-SH 0.0630). Realized unpaired bars run
0.065 (D23) – 0.0718 (R2) – 0.1007 (r9-corrected two-fleet form). D23's
finding generalizes: **an advisory-scale effect (+0.02..0.05) lands in the
recording band at k=3 unpaired** — only R2-sized effects (+0.137) credit.
Hence the tier order: instrument first, free reads second, fleets last and
only for levers that could plausibly clear ~0.07 — or that pre-commit a
mechanism-primary design (the D23/carry lesson, SESSION_LOGS 2026-08-13).

The 100M grade re-ranks §4: if S-SHAPE is still rising at 100M (quote it
with the mandatory anneal sentence), "more steps" competes with every lever
and the standing fewer-bigger-runs order favors it; if it is bending, the
per-step levers below rise. Write the §4 pre-reg *after* the grade.

## 2. Tier 0 — instrument work and free reads (no fleet; after the frozen schedule completes)

**2.1 Re-measure eval overdispersion — RUN IT (~20 min agent-side).**
The ±0.02 landmine (docs/landmines.md:55) compares a **range** of 3 draws
(0.76467/0.78467/0.78333, spread 0.0200) to a binomial **se** (0.0077).
Expected range of 3 normal draws is 1.69σ = 0.0130 (sd 0.0068), so the
observed spread is ~1σ high — ordinary. On the matching statistic: sample sd
0.0112 = 1.45× binomial, 2 df, p ≈ 0.12 — unresolved. Run 5 more n=3000
passes of the same `runs/showdown_sp_batch50m_s83/ckpt_050000000.pt` (8
total, 7 df); `scripts/ch5_scale_shape_report.py:78-83` already prints the
spread check. If eval is binomial-clean, the rule over-buys battles when
read as a 1σ width; if 1.45× holds, the landmine is measured and stays.
Either way "pool 3 seeds, read shape" survives. Output: a numbers-backed
proposal to the maintainer to re-word the landmine — not an edit.

**2.2 Seed-sharing run tag — BUILD IT (few lines + a test).**
Every training A/B to date is unpaired for a mechanical reason, not a
statistical one: usernames derive from the seed
(`rl/envs/showdown_async.py:214,219` — `as2s{seed}a/b`; the sync path
derives at construction, `showdown.py:641`), so same-seed arms collide
(landmine rule 2; the R2 seed-guard "legal owner" bookkeeping exists because
of this). Add a run tag to the username and arms can share seeds: shared
init (when shapes match) + shared early episode stream. Honest expectations:
CH3 R4's paired-clustered se of 0.0080 (RESULTS.md:693) shows what *full*
pairing buys, but that was same-checkpoint eval pairing — training-seed
pairing cancels only what stays correlated through chaotic decorrelation, ρ
unknown. It is weakly dominant (ρ≈0 ⇒ no worse than unpaired), costs almost
nothing, and it is the only cheap attack on §1. Build before any §4 fleet;
measure and report ρ on first use. Extend the seed-guard test to tags.

**2.3 Critic own-move routing — offline read ONLY (hours, no fleet).**
Verified in code: `rl/networks/entity_deepsets.py:345-349` computes
`own_moves`; `ctx_parts` (:353-359) is field + both team pools + both
actives; the critic head reads ctx alone — no PP, no disabled, no own-move
detail (it also pays the `move_net` FLOPs and discards them). D18's closeout
named exactly these lines as "the first thing to fix if critic-side work is
ever revisited" (SESSION_LOGS 2026-08-16, :4580). Two honesty notes: the
opp-move-token exclusion is a *ratified* design (docstring :27-31, threat
info routes via mon matchup features), and D18's +0.045-EV cap is about
*hidden* info — own-move routing is a different quantity, mostly bounded by
species-stereotyped movesets instead. Spec: collect ~50k mirror decisions
with the 100M final (collection-only), regress critic-A (ctx as-is) vs
critic-B (ctx + own-move pool, 5→6 · entity_dim, critic-only change) on the
same (obs → ±1) targets; read held-out EV + Brier resolution (CH3 R0's Z1
decomposition: reliability 0.0117 = calibrated, resolution 0.0594 vs
uncertainty 0.2050 = the deficit is resolution). Fleet arm only if the
offline read shows a real resolution gain — then it is §4/step-8 work.

**2.4 P3 draw-frequency covariate — OPTIONAL (~20 min).**
P3 is predecessor-era (2026-08-03, heur_512 data): CV R² 0.0375 (p<0.005,
n=3000/146 species); coefficients read as strength, not rarity (Electabuzz
+0.098, Mewtwo +0.072, Abra/Alakazam +0.07; Tangela/Parasect/Grimer ≈
−0.07), and at ~120 appearances/species the per-species se (~0.045) can
manufacture the pattern. Re-run on fresh eval JSONs with draw frequency as a
covariate (count draws from the vendored
`showdown/data/random-battles/gen1/teams.ts` pool). No lever exists either
way — teams are server-rolled — this is bookkeeping hygiene.
`scripts/p3_team_luck.py` is do-not-relitigate-protected: extend, don't edit.

**2.5 Search-depreciation write-up — DO IT (mostly free; JOURNEY's own
pre-step-3 item).** The points exist: 12M per-lane search deltas
+0.051/+0.104/+0.148 (monotone in lane weakness), 50M batch-lane R4S66
search@20 **0.38067 vs greedy 0.4740 (~10 se — search hurts)**, and the
100M primary adds the endpoint. Formalize the curve, feed the step-2
ladder-object ruling (greedy leads on today's evidence, HANDOFF §4.4) and
pre-frame JOURNEY 11.5. No training.

**2.6 most-damage-typed anchor — BUILD BEFORE STEP 3 (one afternoon;
JOURNEY's own item).** The only anchor whose strength doesn't drift across
generations; H&L report 0.829 against it in gen7. Sibling of
MaxBasePowerPlayer with type awareness.

## 3. Ruled out / answered — do not re-propose

- **KO / status / HP-differential potential shaping.** Inert by algebra:
  Φ = 0.6·(obs[2]−obs[1]) exactly (SESSION_LOGS :803), linear in emitted
  features. Measured null: Δ −0.0004, se 0.0074 (z −0.06) over 9,000
  battles; the 639,409-episode figure is the *invariance gate* (returns
  stayed {−1,0,+1}), not the null read. Standing rule binds: state your
  potential and show it is not already obs-representable.
- **Chaining runs off finished checkpoints.** lr_anneal ends at ≈0 (the
  pre-reg cycle barred own-run 50M rungs at "507.8× lr"); re-heating *is*
  the N-ANNEAL confound the 100M header names as the leading alternative;
  dormancy makes a collapsed representation a bad restart point.
- **Survivor bonus on a win.** The docstring argument at
  `rl/envs/showdown.py:740-745` is the ruling: uncancelled shaping spans
  ±1.6 and a sweeping 48%-win policy outscores a trading 50%-win one; in
  gen1, sacrificing a mon to absorb sleep is correct play. (Citation note:
  this lives in code, not in a named record entry.)
- **Paired eval via server battle seed — ANSWERED 2026-09-01, feasible,
  small prize, don't build now.** `RoomBattleOptions.seed` exists
  (`showdown/server/room-battle.ts:490`, passed at :575); only the wire path
  from the challenge command is missing (patch precedent: the timer knob;
  ps-ppo's rlspawn.ts). But CRN shares only the team draw + pre-divergence
  rolls, and the team-luck share of outcome variance is small (P3 R² 0.0375
  lower-bound). It cannot touch σ_seed. Revisit only if 2.1 finds real
  overdispersion traceable to team draws. Patch would live in
  `scripts/patches/` (server is gitignored).
- **Width/capacity scaling.** The ledger argues directly against: the
  biggest credited win came at *reduced* params (626,059 actor under the
  681,994 K2 ceiling, +0.1513); H&L reached 72% GXE at 1.33M; measured
  idleness (D22: dormant 27→84–88% on s35/s36, critic ctx srank99 7–11/384;
  search-era lanes ~47/384). CNN is a category error (`rl/networks/conv.py`
  is MinAtar's DQN net).

## 4. Tier 1 — training levers (each its own pre-reg; step 8 unless pulled forward; 50M async recipe, ~1 day/fleet at 574 steps/s/lane)

Ranked. Build 2.2 first — at k=3 unpaired, only an R2-sized effect credits
(§1), so every arm below should either pair seeds or pre-commit a
mechanism co-primary (D23 lesson).

**4.1 Both-seat harvest — the repo's licensed A2 (CHAPTER5 §3, licensed
2026-08-26; do not confuse with CLEANUP.md's audit item "A2"). STRONGEST.**
Seat 2's trajectory is discarded (`showdown.py:1208`,
`discard_seat2_obs=True`); in the async collector the opponent is a
listening Player that already encodes its own obs to move. Harvest = ~2×
episodes/update (~959 → ~1,700 at the 80% rule below) at zero extra
simulation and — unlike R2 — **without** reducing update count. Precedent is
as strong as this lane has: H&L, the only verified pure-self-play randbats
success, consumes both seats (Algorithm 1's "2m matches"; verified to the
line in prior_work/README.md), with exactly return-balanced batches — one
winner + one loser per battle — which matters at γ=1 terminal-only. The
recorded blocker (2026-08-08 advisory: "seat 2 is ALWAYS a frozen snapshot
... needs behavioral-logp storage") has a clean answer: harvest only rows
where the drawn opponent is the *latest* snapshot (latest_prob 0.8,
push_every_updates 5 — `pool.py:185-192`), store that snapshot's own logp as
behaviour logp; ≤5-update staleness is the same order as seat 1's own
within-collection staleness, which PPO's ratio already absorbs. Drop the 20%
historical rows. Honesty: returns are exactly anticorrelated within a battle
and gradients cluster by battle → effective n < 2×; H&L is existence proof,
never a target (their m=7680 is self-described as "completely arbitrary").
Cost: logp capture in `pool.py:83-88` `move()`, a seat-2 episode builder,
reward mirroring, D-C-style gates (illegal/collision exactly 0 on seat-2
rows), a discard-rate metric, tests — then a fleet.

**4.2 gae_lambda 0.75 — RUN IT, with corrected evidence.** λ=0.95 is
universal (39 configs) and was explicitly HELD at R2's GO/NO-GO
(`showdown_sp_batch50m.yaml:208`, "Q4"); the 2026-08-08 advisory verified
ps-ppo's ladder-era checkout `7fb522c` (the 2102-Elo system) at λ 0.75 FLAT
+ steps_per_update 32,768; the λ arm was slotted at branch (d), mooted when
structure credited, re-homed into D21, and swept 2026-08-16 — never run.
Pro-mechanism: D18 says the outcome residual is largely aleatoric (entire
hidden team worth +0.045 EV) and the value head is calibrated (Z1
reliability 0.0117) — λ<1 filters luck the actor can't condition on.
**Corrections the source doc needs:** (i) the external field is split, not
convergent — ps-ppo 0.75 and Wang 0.754 sit against **VGC-Bench at γ1.0/λ0.95
(our exact values)** and H&L at λ0.9/γ0.95; (ii) every λ<0.95 system pairs
it with dense-ish reward (ps-ppo faint ±0.1; H&L 5-term) — at our pure
terminal ±1, γ=1, ep len ~32, λ=0.75 gives actions >8 steps from the end
almost no direct outcome signal (0.75¹⁰ ≈ 0.06): the terminal reaches them
only through the value chain, and the value target itself becomes more
bootstrapped (`ppo.py:944`, targets = advantages + values) — two-sided,
given the critic is the diagnosed weak component (D22); (iii) R2's 30,720-
step updates already bought a large slice of the same aleatoric-noise
averaging — the advisory priced λ when updates were ~34 episodes, so the
marginal prize is smaller now (the source doc applies exactly this discount
to shaping but not to λ). Design: one arm, λ=0.75 verbatim, batch50m_async
recipe, 3 seeds (paired via 2.2 if landed; else the async acceptance fleet
66/75/83 is the free control), early kill-watch on value EV / entropy,
manipulation check on loss/adv_std (λ moves it mechanically — the
recipe12m header shows the gate pattern). A null closes the axis cheaply; a
negative with a slow-value signature names λ+faint-shaping (ps-ppo's actual
pair) as the follow-up pre-reg — never a bundle (recipe12m header, factorial
hazard).

**4.3 Regenerative-L2 at 50M — NEW (the source doc missed it).**
D23 (12M): "LETTER-MET, SEED-FRAGILE, NOT CREDITED" — Δ +0.0451 ≥ the
0.025 letter with bar 0.065; mechanism strong (norm BOUND held, critic
srank99 31/53/36 vs control 11/17/16, final→peak gap shrink realized);
falsifier did not fire — "the regenerative family is neither killed nor
closed." The lever is BUILT (`l2_init_decay`, θ₀ capture, metrics, 14
tests; −3.2% throughput). The 50M carry was designed and came back **NO-GO
AS SCOPED** (2026-08-13) — but what changed since: chapter budget reset,
1.53× async speedup, and the carry's own design guidance stands
(mechanism-primary: norms + srank primary, win rate secondary). Conditions
to revisit: 100M S-SHAPE bending (plateau pressure) or dormancy/srank
reading collapsed on the 100M finals (probe is cheap, D22 instruments
exist — with the D24 float64-svdvals fix; srank99=1 is a NaN sentinel).
PokéAgent finalists' plasticity levers (Kron, AID) are the same family;
this repo's own lever has local evidence and zero build cost.

**4.4 H&L 5-term shaping on the entity trunk — LAST, gated.** Factual base
verified: `hl_shaping` non-zero in exactly three runs on disk (signal12m
s23/24/25), all `trunk: mlp`, and the +0.0135 n.s. read was a γ0.95+5-term
*bundle* (the repo's own header calls it "never tested on the entity
trunk"). But: R2 bought the variance half, 4 of 5 terms reward play we
already dominate the replay field on (domin% 0.6 vs humans' 2.7 — ladder-R1
replay audit, not a clone number), the aleatoric ceiling caps the
credit-assignment half, and the "~1 in 4" price is an agent-authored
licensed estimate, not a maintainer ruling. Run only if 4.1–4.3 null or
S-SHAPE says more-steps is dead. Shaping ALONE at γ=1 (no bundle, no anneal
variant — on an inert term annealing anneals nothing, per the source doc
itself). Zero code; one overnight at 12M is NOT readable (D23's comparator
finding) — this too is a 50M-recipe question now.

## 5. Tier 2 — architecture (step 8 at the earliest; most of it folds into step 3)

- **Attention re-benchmark — DO (minutes-to-an-hour, no training).** The
  34.6× kill was a CPU train-step microbenchmark vs the flat [512,512] MLP
  (2026-08-07, pre-entity-production); "attention-vs-entity_deepsets has
  NEVER been measured" (CHAPTER5:207). Re-run ARCH_SCREEN_SPEC's step
  against the current trunk; an honest ratio either re-opens or re-closes
  the rung with a live number.
- **DCN / two-tower explicit crossing — PARK for step 8.** The unbuilt
  middle rung (CROSS_FEATURES ladder). Only with a mechanism-read design;
  12M win-rate primaries are dead (§1).
- **Temporal context — FOLD INTO STEP 3, harder than the source doc says.**
  Both *validated* comparables are single-snapshot: the 2102-Elo ps-ppo is
  the `7fb522c`-era system (KV-cache/temporal is HEAD-only, no logs or
  checkpoints anywhere in its history), and H&L is single-snapshot +
  lastmove. It changes OBS_DIM — invalidating every checkpoint including
  the 100M finals right when step 2 needs them. The gen4 encoder rewrite
  (JOURNEY step 3, Wang's one-hot duration counters,
  prior_work/HISTORY_FEATURES_DESIGN.md) is where Markovianity gets
  redesigned for free.
- **Width — SKIP** (§3, last bullet).

## 6. Ops hygiene (from the 2026-09-01 auto-mode review; sequenced)

Safe now (server-side, touches nothing on this box): **GitHub branch
protection on `main`** — block force-push and deletion; maintainer's click.

After FLEET DONE + frozen schedule + grade are recorded:
- gitleaks (or equivalent) pre-commit hook — live secrets are the ladder
  bot credentials and the W&B key. Not while the babysitter session is
  mid-schedule (a failing hook derails its commits).
- Permission config: soft-block `git clean` / `git reset --hard` (in this
  repo `git clean -fdx` deletes the *gitignored* `showdown/` server AND all
  of `runs/` in one shot — worse than any `rm`), plus ladder-launch and
  `git push` soft blocks; allow-list read-only inspection (`git status/
  diff/log`, `pytest`, `ps`, `extract_history`) so the prompts that matter
  still get read.
- `runs/`-outside-tree symlink migration: decide only after E2's rung
  retention window closes (~600 rungs must stay until S-SHAPE, S-ANNEAL,
  D-A are committed) and after checking resume metadata for embedded paths.
- `npm ci --ignore-scripts` as the habit for any `showdown/` reinstall
  (then re-set `simulator: 4` — standing landmine).
- CLEANUP.md shelf unshelves at the readout per its own terms (audit items
  A2–A5); B3 (decide()-helper refactor) became legal when R2 landed but
  waits until the frozen eval paths are done being load-bearing.

## 7. Corrections to the source doc (so nobody re-imports them)

1. R2: 1,024→30,720 steps/update, ~34→**~959** episodes/update (not
   ~1,100); biggest credit *of CH5* (project-wide biggest is +0.1513,
   entity structure).
2. R2 was not the advisory's continuation — its batch size was
   independently recalibrated against H&L (CHAPTER5:264-269). The λ half:
   advisory → branch (d) mooted → D21 → swept 2026-08-16.
3. "Reliability 0.0117" is CH3 R0's Murphy decomposition of the *search*
   value head vs SH (Brier 0.1567 = 0.0117 + resolution 0.0594 /
   uncertainty 0.2050) — not a fleet-R0 read.
4. Omitted: VGC-Bench runs γ1.0/λ0.95 (prior_work:407-411) — the
   "convergent 0.75" prior has a third system on the other side; and
   steps_per_update 32,768 / λ0.75-flat belong to commit `7fb522c` (HEAD:
   36,864, plus an undocumented dynamic-λ 0.55–0.95).
5. "Unpaired se terms 0.024–0.049" — not found as recorded; the honest
   unpaired comparators are the seed-clustered bars 0.065 / 0.0718 / 0.1007.
6. The 639,409 episodes were the shaping-invariance *gate*; the null was a
   separate 9,000-battle read (Δ −0.0004, z −0.06).
7. "~27-decision domain": self-play measures 26–32 by era (R2: 32.047);
   27.2 is decisions *vs SH* (CH3 R0).
8. P3 is predecessor-era (2026-08-03, heur_512 data), not 100M-cycle;
   coefficients also include Abra/Alakazam +0.07.
9. srank99 "7–11 of 384" is the D22 s35–37 probe; search-era headline lanes
   read ~47/384; any future rank quote needs the D24 float64 fix.
10. The ±1.6 / 48-vs-50 trade-down argument lives in the
    `showdown.py:728-757` docstring (Arm-B rationale), not a named record
    ruling — conclusion unchanged.
11. "~1 in 4" for shaping is an agent-authored licensed estimate
    (CHAPTER5 §3b), not maintainer-priced.
12. Missing entirely: the built, letter-met, uncredited regenerative-L2
    family (§4.3) — arguably better-evidenced than the shaping retry it
    ranks above.
