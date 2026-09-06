# review_1.md — REVIEWER 1: evidential validity and arithmetic

Target: frozen draft `results/design_gen4_wang50m/gen4_wang50m.draft.yaml` (sha1 e0b25365,
byte-identical to `configs/gen4_wang50m.yaml`), sidecar `configs/gen4_wang50m.prereg.yaml`, smoke,
`tests/test_gen4_prereg.py`. Verified against `rl/agents/ppo.py`, `rl/train.py`,
`rl/selfplay/harvest.py`, `scripts/eval_checkpoint.py`, `scripts/gen4_fp_h2h.py`,
`scripts/gen4_wang50m_wave.sh`, the thesis text (`pdftotext -layout`, Table A.1/A.2/A.3,
§3.1, §3.1.4, §3.1.2, §4.1, §4.2, Table 4.1), `docs/design_gen4/anchors_and_eval.md` §5/§6,
`docs/prior_work/README.md`, `../stable-baselines3/stable_baselines3/ppo/ppo.py`,
`configs/showdown_sp_100m.yaml`. `pytest tests/test_gen4_prereg.py tests/test_wang_recipe.py`
= 14 passed.

**What checked out and needs no change** (so the fixes below are not read as a verdict on the
arithmetic as a whole): `lr 5.8884e-5 = 10^-4.23` (10^0.77 = 5.88844, rel err 7e-6); every
Table A.3 value matches the PDF exactly (lr, 7 epochs, γ .9999, λ .754, clip .0829, clip_vf
.0184, ent .0588, vf .4375, grad-norm .5430, n_steps 78·512 "78 is # workers", batch 1024,
features 896 / hidden 256), and §3.1.4 is literally `10^-4.23 / (8x+1)^1.5`, x = progress in
[0,1]; 8×2496 = 19,968, 2×19,968 = 39,936 = 78·512; `floor(5e7/19,968) = 2,504`, last update at
**49,999,872**, trailing 128 steps; `8 | 50,000,000` and `8 | 500,000`, so `_vector_loop`'s
`step` lands on every grid literal and `ckpt_{step:09d}.pt` gives exactly **100 rungs**, the 50M
rung written inside the last loop body; 200 in-loop evals, se 0.05 at n=100; pushes 2,504 + the
step-0 push (`train.py:611`); `sqrt(.7·.3/9000) = 0.004830`; `sqrt(.786·.214/200) = 0.0290017`
and `0.786 − 0.0290 = 0.7570`; 5e7/290 = 47.9 h, /0.7 = 68.4 h; L3 250×26.6 s = 1.85 h/lane,
5.54 h for three; L2 750×1.18 s = 14.8 min; `train.py:414` really does refuse
`lr_anneal_steps < total_steps`. **SB3's `clip_range_vf` claim is CORRECT**: `ppo.py:239-243` is
`values_pred = old_values + clamp(values − old_values, ±clip_range_vf)` then
`F.mse_loss(returns, values_pred)`, no `max` against an unclipped loss — identical to
`rl/agents/ppo.py:1336-1343`. The five-leg battery matches CLAUDE.md's gen-4 list leg for leg;
every gate's metric key exists (`harvest/{rows_this_update,seat1_rows,version_lag_max,
rows_dropped,discarded,episodes}`, `loss/{entropy,clip_frac,approx_kl}`, `eval/win_rate`,
`time/realized_steps_per_sec`); the M/S5/K partition has no unnamed cell; the aggregator is named
once; `most_damage_typed` resolves for gen 4 via `opponent_player_gen4 → sd.opponent_player`;
`gen4_fp_h2h.py` takes the four flags the header names; the wave script's 60 s stagger,
`ps -o time=` CPU-delta check and 3-retry bound are as described.

---

## MUST-FIX

**1. D-A's closed form is off by one update; the gate as written STOPS every lane.**
Line: `D-A ... with u the number of completed updates at that rung, x = (u × 19,968) / 5e7,
lr == 5.8884e-5 × (8x + 1)^-1.5 to 1e-12 relative`.
`_optimize` applies the schedule from `steps_seen = self.updates * horizon * num_envs`
(`ppo.py:1116`) and increments `self.updates` **at the end** of `_optimize` (`ppo.py:1436`).
So during the k-th update `self.updates == k−1`, and a checkpoint whose stored `updates` field
is `u` carries the lr applied from `steps_seen = (u−1) × 19,968`. The header's own parenthetical
("applied at the START of update u+1 from steps_seen = u × 19,968") states the mechanism
correctly and then contradicts the formula. Re-derivation (rung / u = floor(S/19,968) /
header lr / actual lr / relative error): 5M / 250 / 2.440911e-05 / 2.447429e-05 / **−0.266%**;
25M / 1252 / 5.266761e-06 / 5.271813e-06 / **−0.096%**; 50M / 2504 / 2.180896e-06 /
2.182058e-06 / **−0.053%**. Against a `1e-12` tolerance all three fail → "STOP that lane" on
all three lanes at the first D-A reading (~3 h in). The ratified 100M header got this right for
its async path ("the async loop anneals update u at f(step_{u−1})"), so this is a regression, not
a new convention. **Fix:** replace with `x = ((u − 1) × 19,968) / 5e7, where u is the
checkpoint's own `updates` field (`ppo.py:1467`; the optimizer's param_groups, including lr,
ride in `state["optimizer"]`, `ppo.py:1466`)`.

**2. R0-f: the minibatch count is 40, not "exactly 39", and the grad-step figure is wrong.**
Lines: `minibatches 39 over the UNION: floor(rows/39) ≈ 1,024 ± ~30` and
`grad steps ≈ 2,504 × 7 × 39 ≈ 683,592 (... the minibatch count is exactly 39 per epoch ...)`.
`_optimize` sets `minibatch_size = B // 39` and `_minibatch_slices` returns
`range(0, B, minibatch_size)` clamped — so with `B = 39·mbs + r`, `r = B mod 39 ∈ [0,38]`,
there are **40** slices whenever `r ≠ 0` (probability ~38/39 per update). Verified live:
`B=39,936 → 39 slices`; `B=39,654 → mbs 1016, 40 slices, tail 30 rows`; `B=40,087 → mbs 1027,
40 slices, tail 34`. Under `minibatch_tail: keep` (the config's default) the floor is 2, so the
tail slice **takes a full Adam step at the 1,024-row lr, z-scored over ≤38 rows** — ~2.5% of all
gradient steps, an order more than the 0.8% the F-04 audit recorded at `minibatches: 120`.
Expected grad steps = 2,504 × 7 × (39 + 37/39) ≈ **700,200**, not 683,592.
**Fix:** "39 full minibatches plus a trailing slice of `B mod 39` rows (0–38) that trains under
`minibatch_tail: keep` (F-04 default, ruled) — 40 slices per epoch on ~38/39 of updates; grad
steps ≈ 2,504 × 7 × 39.95 ≈ 700,200." Add to **D-IMPL**: Wang's 39,936 / 1,024 divides exactly,
so SB3 saw **no** partial minibatch; ours takes ~17,500 full-lr steps on ≤38-row slices.

**3. "0.786 (Table 4.1, his full agent)" is factually wrong — it is the network ALONE.**
Lines: the step-5 verbatim quote and `S5-MATCHED "matched Wang's 0.786"`.
Table 4.1 (thesis p. 30): row **NN** vs column **Heuristic** = `.786`; row **MCTS + NN** vs
Heuristic = `.908`. `anchors_and_eval.md` §6 has it right ("network alone 0.786"). JOURNEY.md:60
carries the error and the header quotes it verbatim (correctly — it must). **Fix:** keep the
quote and add a bracketed note in the [R1-1] style: "[R1-x] CORRECTION: Table 4.1's 0.786 is
his NETWORK ALONE (`MCTS + NN` vs Heuristic is 0.908). The network-alone row is the right
comparator — we do not search — so the threshold is unaffected, but 'his full agent' is wrong
and must not propagate to the readout." And make S5-MATCHED read "matched Wang's
**network-alone** 0.786".

**4. The se's provenance is wrong, and n = 200 is arithmetically impossible for that cell.**
Lines: `0.786 minus one standard error of his 200-game number (0.029)`; sidecar
`wang_se: 0.0290`. The thesis's 200 games is §3.1.2's **in-training validation** metric ("the
neural network was validated every 20,000 steps. The sole validation metric was the agent's
winrate over 200 games"). §4.2 / Table 4.1 state **no n at all**. And a winrate at n=200 must
lie on the 1/200 grid: `0.786 × 200 = 157.2` — not an integer, so Table 4.1's cell cannot be an
n=200 number. Every Table 4.1 entry *is* consistent with **n = 1000**: `.786/.206` + 8 ties =
1000, `.809/.191` + 0 = 1000, `.908/.088` + 4 = 1000, `.996/.004`, `.007/.992` + 1. (n = 500
fails on `.809 × 500 = 404.5`.) At n = 1000, `se = sqrt(.786·.214/1000) = 0.012969` and the
one-se floor is **0.7730**, not 0.756/0.757. **Fix:** carry 0.756 AS RULED (I do not reopen the
ruling), but replace the derivation sentence with: "0.029 is one se of his §3.1.2 **validation**
n = 200; Table 4.1's n is unstated in the thesis, and its digit grid is inconsistent with 200
(0.786·200 = 157.2) while every cell is consistent with n = 1000, where one se is 0.0130 and the
floor would be 0.773." Add this to **RW-1** as a third option so the maintainer decides against
the real evidence.

**5. The failure branch pre-commits to DOSE while the cited evidence points away from it.**
Lines: `M-NO ... D-DOSE (named first)`; `S5-SHORT ... NAMES DOSE FIRST ("at 2/3 of his per-seat
dose")`. Thesis §4.1: "the neural network made most of its progress within the first **40M**
steps (1 day) ... quickly reaching **80%** winrate against SimpleHeuristicsPlayer"; and
`anchors_and_eval.md` §6's digitization: "**0.786 at 30M**, endpoint ≈ 0.836, peak ≈ 0.849 near
120M". His steps are TOTAL (both seats): 30–40M total = **15–20M per seat = 30–40% of our
planned 50M per seat**. So his own curve crosses 0.786 at well under half our dose, and a
dose-first sentence is an excuse the evidence contradicts. The ruling (name dose first) stands —
but naming it *alone* first is not honest. **Fix:** keep the ordering and append, in the same
sentence: "— noting that his Figure 4.1 reaches 0.786 at ≈30M of his 150M TOTAL steps (≈15M per
seat, ≈30% of ours) and §4.1 reports ~80% by 40M total, so dose is named first as ruled but is
NOT the cause his own curve supports; D-ENC and D-NET are." Also fix the second cause-list in
M-NO, which omits the value clip (see SHOULD-FIX 15).

**6. `n_eff` is never defined — ruling 10 requires it.** HANDOFF §1.10: "future pre-regs define
n_eff explicitly." The draft defines it for neither the primary (3,000/lane) nor L2/L3.
`eval_checkpoint.py` reports `episodes`, `wins_from_returns`, `ties_from_returns` and
`mask_desyncs` but has no crash accounting; `gen4_fp_h2h.py` has no `crash_forfeits` at all,
while the gen-1 convention (`scripts/ch3_r4_fp_runner.sh:10`) is
`n_eff = seat_finished − crash_forfeits` with wins reduced by the same count.
**Fix:** add a `N_EFF` block: (a) primary — n_eff = battles with an env-supplied
`info["outcome"]`; a lane's eval that dies mid-way is **re-run from zero**, never merged, and
`n_eff = 3000` on every lane or the lane's primary is PENDING; (b) L2/L3 — n_eff =
`seat_finished − crash_forfeits`, `crash_forfeits` = relaunches per ruling 10 (recorded, not
acted on), a leg VOIDS above 5 relaunches; (c) `mask_desyncs` disclosed beside every number.
Mirror the block in the sidecar.

**7. D-B's band is centred on a number the header itself says the fleet will miss.**
Lines: `Expected ≈ 290 steps/s ± 15% -> [245, 335] PROVISIONAL (the solo smoke's ... rate; 3-wide
is UNKNOWN and the gen-1 sync precedent lost ~30% at fleet width ...)`; `RECORD < 0.85× expected`.
0.7 × 290 = **203 steps/s**, below the band's floor, so every lane RECORDs a breach by
construction from the first window and the babysitter cannot separate the known width effect
from a real fault. (The wall-clock plan already uses the 30% loss: 68 h.) **Fix:** state two
references — solo 290 (the smoke) and **fleet-width expected ≈ 203, band [173, 234] PROVISIONAL**
— with `RECORD < 0.85 × 203 = 173`, `STOP-AND-INVESTIGATE < 0.5 × 203 = 102 sustained 2 windows`,
re-based from the fleet's first conforming windows and disclosed.

**8. K6 is not decidable: a fleet statistic cannot select a lane.** Line: `K6 loss/entropy:
3-lane median < 0.15 for 2 consecutive readings BEFORE 25M -> STOP that lane`. Which lane? (The
wording is inherited verbatim from the ratified 100M header, so it is not a new error — but there
it sat beside a control fleet whose realized minima were known, and here there is none.)
**Fix:** either "**each lane's own** `loss/entropy` < 0.15 for 2 consecutive readings before 25M
-> STOP that lane", or keep the median and make the action "STOP ALL, disclose". T3 has the same
ambiguity ("-> STOP") and needs the same word.

**9. Two required §6 disclosures are missing.** `anchors_and_eval.md` §6 lists, verbatim, as
travelling with the comparison: (a) "SB3's PPO **implementation** (his 13 hyperparameters are
Bayesian-tuned on a 3v3 surrogate, not SB3 defaults — JOURNEY's 'with its defaults' is wrong)";
(b) "that our exit bar is **his weaker number**". The draft's D-IMPL names only "he ran SB3
(MaskablePPO)" and the header nowhere mentions Figure 4.1's ≈0.836 endpoint / ≈0.849 peak or the
unreconciled pair. (a) is load-bearing beyond bookkeeping: thesis A.0.3 says the recipe was tuned
by Bayesian optimization on **3v3 battles** against **his** encoder, action space and network — so
"Wang's recipe as he ran it" on our trunk is a recipe transplant, not a controlled reproduction.
**Fix:** extend D-IMPL with the 3v3-surrogate sentence, and add to the step-5 block: "0.786 is
his WEAKER published number; Figure 4.1 digitizes to ≈0.836 endpoint and ≈0.849 peak near 120M,
unreconciled from the text (`prior_work/README.md`, `anchors_and_eval.md` §6). The exit bar is
deliberately the lower one; a pooled read between 0.756 and 0.836 is 'matched' under this
pre-reg and must not be quoted as reproducing his curve."

---

## SHOULD-FIX

10. **The lr floor is never reached.** `lr_schedule power ... floor lr0/27 at x = 1` and the M-NO
cause "the LR floor (lr0/27 at x = 1)". Max applied x = 2,503×19,968/5e7 = **0.99959808**, so
`(8x+1)^1.5 = 26.9855` and the realized minimum lr is **2.182058e-06 = lr0/26.986**, not
lr0/27 = 2.180889e-06. Say "floor lr0/27 asymptotically; the run's realized minimum is
lr0/26.99 = 2.1821e-6 at the last update".

11. **The 0.0044 se has no p** (`one pooled-3×3000 se ≈ 0.0044`): `sqrt(p(1−p)/9000)` = 0.004323
at p = 0.786, 0.004527 at p = 0.756. Write "≈ 0.0043–0.0045 (p 0.786 → 0.756)". The PLANNING SE
line correctly names p = 0.70.

12. **290 vs the smoke's own readings.** 320/275/296 tile the run, so the whole-run rate is the
harmonic mean **295.9**, not 290 — use 296, or say "290 = 296 rounded down as a lower bound".
Also 290 ± 15% = [246.5, 333.5]; the stated [245, 335] is ±15.5%, so say "rounded outward".

13. **Rung file size.** `100/lane × ~19 MB` — 19.2 MB is `checkpoint.pt`, which alone carries the
pool member (`_save_latest` passes `pool.state_dict()`; `save_checkpoint` does not). A rung is
actor+critic+2 Adam moments = 1,218,316 params × 12 B ≈ **14.6 MB** → ≈1.46 GB/lane. R0-h's 6 GB
is conservative either way; just don't call 19 MB the rung size.

14. **R0-2's stated diagnosis cannot be what a 0.0 reading means.** `loss/clip_frac > 0.0 on every
update (exactly 0.0 = recorded old_logp / recompute not wired) KILL LANE`. Seat-1 `old_logp` is
recomputed so epoch 1's ratio is exactly 1, but 6 further epochs move the policy and seat-2's
`old_logp` is the member's — a bit-exact 0.0 across 7×40 minibatches means a **frozen actor,
zero lr, or a broken ratio**, not a recording choice. Reword.

15. **The value clip makes the critic UPDATE-limited, and D-DOSE does not say so.** All 7 epochs
clip against the same `flat_old_values` (computed once per update, `ppo.py:1075`) and `clamp`
passes no gradient once saturated, so a row's prediction can move at most **0.0184** per update
on a target in [−1, 1]: 0 → 0.9 needs ≥ 49 updates ≈ 978k steps. Our 2,504 updates vs his
150M/39,936 = **3,756** means the 2/3 dose is also 2/3 of the critic's clipped-increment budget.
Add one line to D-DOSE and put "the value clip's per-update ceiling (0.0184; 2,504 vs his 3,756
updates)" into the M-NO cause list.

16. **`harvest/empty` is never gated or reported.** `harvest.py:83` counts battles whose seat-2
side never decided. R0-3/H1 gate `rows_dropped`, `discarded`, `version_lag_max` but not `empty`.
Add "`harvest/empty` RECORD; investigate above 1% of `harvest/episodes`".

17. **The eval s/battle is from ~20-decision losing battles.** `the smoke's eval ran 10 battles
in 0.47 s -> ≈ 0.05 s/battle -> ≈ 3 min/lane`. The smoke's collect was 2.0–2.6 ms per env-step,
so 0.047 s/battle implies ≈20 decisions — a policy at `win_rate 0.1` conceding fast. The final
checkpoint's battles will run 40–70 decisions (the smoke's own seat-1 mean is 62.9), so budget
**8–10 min/lane** for 3×3000 and **≈1.25 h** for S-SHAPE's 30,000 battles. The "≈ 8 h" total
still holds; the per-item figures do not. The header's "re-read at n = 20 first" hedge stays.

18. **The standing sign-inversion cross-check is not a gate here.** CLAUDE.md: "`eval/win_rate`
is env-supplied outcome, never return-sign; `wins_from_returns` exists only as the cross-check and
the two must agree." Nothing is shaped, so on this run the two must agree **exactly**. Add to the
PRIMARY read: "`win_rate == wins_from_returns` exactly on every primary and every leg, and
`mask_desyncs` disclosed beside each number."

19. **Q38's pin rule is an equivalence-by-failure-to-reject with unstated power.** At n = 250/lane
pooled to 750 per rung, `2·se_diff = 2·sqrt(2p(1−p)/750) ≈ 0.052` at p ≈ 0.5 — so "the budgets are
equivalent at our n" means "not distinguishable at ±5 points", the same weakness the standing
FP@20 disclosure names. State the number in the pin rule.

20. **The FP set-file drift rides L2 only.** "FP's pinned set file drifts ±1–2 levels on 40
species" is a property of the file, so it applies to **L3** identically. The sidecar's
`disclosures` list (8 D-items) also omits all three FP disclosures — add them, or mark them
leg-local.

21. **The sidecar's `battery` has four legs, not five.** L5 (vs-SH per lane + tie rate) is absent,
so "the five-leg battery" is not machine-checkable and `tests/test_gen4_prereg.py` asserts only
`L1..L4`. Add `L5: {leg: vs_sh_per_lane, n_per_lane: 3000, note: "primary axis, descriptive use"}`
and extend the test's leg loop.

22. **"flat"/"plateau" barred outright while the header permits "not distinguishable from flat".**
Reword the sidecar entries to `'"flat"/"plateau" as an unqualified description of the S-SHAPE
curve (the permitted forms are enumerated in the header)'`. Related test defect:
`test_gen4_prereg.py:147-150` ends every branch in `or True`, so that loop can never fail — drop
the `or True` and assert what is meant. Same file, line 75: the dose assertion
`total_steps*2/3 <= 2*per_seat_dose/3 + 1` is `33,333,333 ≤ 50,000,001`, always true and unrelated
to the dose; line 76 is the real check — delete 75.

23. **Cell K has no route.** `at k <= 2 ... the primary is DESCRIPTIVE ONLY and neither branch
fires (cell K)` — but step 3's milestone is then undecided and nothing says what happens. The
100M header routes every cell explicitly. Add: "cell K routes to a MAINTAINER RULING (re-run the
dead lane on a spare seed, or accept a k=2 descriptive readout); the README row WAITS either way."

24. **Aggregator wording for the legs and S-SHAPE.** The primary's aggregator is declared "binding
everywhere", which formally covers "reported per lane AND pooled" and S-SHAPE's "pooled per rung" —
but say it in those two lines. Also note that at equal n per lane the equal-weight mean **is** the
pooled-over-battles proportion, so recording both is a tautology unless a lane's n_eff differs
(see MUST-FIX 6) — which is exactly when it stops being one. And S5-SHORT's "states the gap in se
units" must name which se (the larger of the two printed).

25. **`harvest/*` is outside CLAUDE.md's locked metric-name list** ("plus `loss/*` and
`selfplay/*`"), yet nine gate readings key off it. Add the namespace to CLAUDE.md's Conventions in
the same commit (housekeeping, no ruling needed).

26. **Distinct seeds if any leg goes concurrent.** L3's 5.5 h is the sequential total and
`gen4_fp_h2h.py --seed` defaults to 0; if the three lanes ever run in parallel, landmine 2 applies
(poke-env derives seat names from globally-seeded `random`). Say "sequential, one FP process" or
pin per-lane `--seed`.

---

## VERDICT

**Ratifiable after the nine MUST-FIXes.** The recipe transcription is exact against Table A.3 and
§3.1.4, the freeze is pinned by real hashes, the update-size and rung arithmetic are right to the
step, the SB3 `clip_range_vf` claim survives a read of SB3's source, the outcome partition has no
unnamed cell and the battery matches CLAUDE.md's gen-4 list leg for leg. Six of the nine fixes are
text; two are numbers that will otherwise fire spurious STOPs (D-A's off-by-one, guaranteed at
1e-12; D-B's band, guaranteed at fleet width); one is an obligation the maintainer already ruled
(n_eff). What worries me most is **MUST-FIX 5**, the pre-committed dose-first attribution — the
only finding whose absence would be invisible in the finished readout: every number would be
right, the sentence would be the one the pre-reg promised, and the reader would come away
believing 2/3 dose was the leading explanation of a short result when Wang's own Figure 4.1
crosses 0.786 at roughly 30% of our planned per-seat dose and §4.1 reports ~80% by 40M total
steps. The honest candidates at that point are D-ENC (our scalar counters against his one-hot
durations — the one choice `open_questions.md` marks unsupported) and D-NET, and the header orders
them last. D-A bites first, but it bites loudly at the 5M rung and costs an hour; this one would
survive into RESULTS.
