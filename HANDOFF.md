# Handoff — written 2026-08-13 (night), D25 RATIFIED and pushed, NOTHING RUNNING

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty
stub. STATUS.md + SESSION_LOGS.md are CURRENT through the D25 ratification entry — this
file carries only what the next session needs to *do*.

## State: green, clean tree, pushed, NOTHING RUNNING

`origin/main` = `ae19035`. Suite 293 green. No lanes, no evals, no monitors. Zero
training lanes were spent this entire session. Showdown server may still be up on :8000.

## What happened (one paragraph)

The 50M regen-L2 carry was designed, reviewed, and REJECTED on merit by six agents. The
rank tooling was found buggy (a float32 NaN sentinel recording `srank99=1`) and fixed;
two corrupt cells were re-derived. A geometric-null study was built and run
(`results/d24_null/`), re-grading D23: its critic de-collapse SURVIVES, its actor read
is INCONCLUSIVE. The lane-day ledger was audited: the chase has cost **13.54**, not the
recorded ~17. D19 (opponent TEAM prediction) was killed pre-build on measured
information content, re-targeted to opponent ACTION prediction as **D25**, designed,
reviewed, gated, audited twice, refused at r1, corrected, and **RATIFIED at r2**.

## THE NEXT UNIT OF WORK: build D25 (~200 lines, ~5 evenings, zero lanes)

**The contract is `configs/showdown_sp_actpred12m.yaml`** — 1,236 lines, ratified, and
it is the spec. Do not re-derive it; the ten agent documents behind it are in
`results/d24_design/` (gitignored) if you need provenance.

Build order, from the header:

1. **Label path.** `PoolPlayer.choose_move` (`rl/envs/showdown.py`) already computes the
   10-way int pre-`BattleOrder`; `SingleAgentWrapper.step` calls it synchronously from
   pre-resolution `battle2`. Emit `np.array([kind, id], int32)` — NOT a tuple (a tuple
   hits gymnasium's object-array branch). Transition-time info: belongs to row *t*, no
   carry variable, no reset merge. The frame MUST derive from the buffered obs row's own
   id-suffix so the label can only name entities the actor could see.
2. **Head.** Pointer scorer over `[ctx ‖ opp_entity_i]`, width 96, **owned by the agent,
   not the actor** (keeps `actor.state_dict()` unchanged so every eval script runs
   unmodified). **The opponent move tokens DO NOT EXIST** — `entity_deepsets.py:298-302`
   builds `own_moves` from `tok["moves"][:, :4]` only. Apply the EXISTING
   `move_net`/`move_emb` to `tok["moves"][:, 4:]` / `tok["move_ids"][:, 4:]`. This puts
   aux gradient into shared weights; the header enumerates the five invariants that must
   stay bit-identical.
3. **Optimizer.** Aux params in their OWN third group, appended last. Appending to group
   0 silently hands them the critic's Adam moments (measured, not theorized). Clip the
   aux gradient SEPARATELY — control `loss/grad_clip_frac` is 0.90, so a coupled term is
   a covert 10-30% policy-LR cut.
4. **Label space is L6** (six classes), not 12. The 12-class variant is a recorded free
   secondary only. Drop aliased (sleep/recharge) rows.
5. **Tests** the header names, incl. the oracle-CE identity test and an LBFGS
   convergence assert (1 fit in 40 diverged silently).

## Blocking before the maintainer launches (both zero-lane)

1. **R0-13 must re-derive the LEARNED bar on L6 inputs.** The 0.371 in §8 is anchored on
   12-class `g_frozen-probe` values because no five-lane L6 values exist anywhere, and
   its 0.80 multiplier is unsourced (a reviewer's example, not a measurement).
2. **R0-12b's four capacity nulls have NOT been re-run on the s36 reference tape.**

Also verify at build, flagged in-header as the reviser's arithmetic rather than quoted
measurement: R0-8's thresholds 255/210, and the param total 675,538.

## Open maintainer decision, needed BEFORE launch

**The shuffled-label placebo arm: +2.24 lane-days** (chapter 15.9 -> ~18.1 of 20). It is
the difference between claiming "an explicit opponent model helps" and "an auxiliary
loss helps". Currently NAMED-NOT-RUN and the header scopes the claim accordingly.

## Do NOT rediscover

- **Quote the RANGE, not the best measured variant.** This session's one systematic
  error, caught by a red team: several summaries promoted the most favourable variant
  while the source documents carried the honest range. D25's power is **0.27-0.76** at
  +0.010, MDE(80%) **0.0105-0.0207** — not the 0.88 first reported.
- **Rank reads: MAX null to ESTABLISH an effect, MEDIAN null to RETIRE one.** They are
  not interchangeable; the docstring in `scripts/d24_null_match.py` now explains it.
- srank must be float64 with the Gram/eigvalsh fallback; `--tag` every rank pass
  (`d22_dormant_rank.py` used to clobber its own CSVs and destroyed D23's control pass).
- Letters at n=3 quantize to {0, 0.21, 0.79, 1}. Calibrate every letter's level before
  proposing it — one earlier proposal was accidentally level-0.26.
- A linear probe on `ctx` cannot decode even the actor's OWN action (logits are
  `scorer([ctx‖entity])`, ctx is max-pooled). Heads and estimators must be scorer-shaped.
- Seeds: 0-13, 23-46, 50-51 SPENT; 49 BURNED; 14-22 RESERVED; 99 disposable; 47-48 and
  57+ free. **D25 takes 52-56.**
- D19's kill STANDS but its recorded reasoning was wrong in three ways (gen1 randbats is
  rejection sampling with species/type/weakness caps, not independent draws) — see the
  red-team entry in SESSION_LOGS.
