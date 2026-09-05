# Review brief — configs/gen4_wang50m.yaml (the first gen-4 pre-registration)

You are reviewing a FROZEN DRAFT of a pre-registration header for a training
run. Ratification is the maintainer's; you advise. Write findings as a numbered
list, each tagged MUST-FIX or SHOULD-FIX, each with: the line(s) or key, what is
wrong, the concrete fix (text or number), and — for arithmetic — your own
re-derivation. Do NOT propose a different design; the maintainer's rulings are
settled (below). Do flag anything the draft claims that the code or the docs
contradict.

## Settled rulings (do not relitigate)
HANDOFF.md §1 items 1–11 (read them), docs/design_gen4/open_questions.md §0.5,
JOURNEY.md steps 3–5. In short: first gen-4 run = Wang's Table A.3 recipe + his
LR schedule, mirror self-play latest-vs-latest, both seats harvested, NO pool,
on the frozen encoder layout v0.1 (as built, unreachable dims kept), 50M per
seat as a disclosed fraction of his ≈ 75M; milestone ≥ 0.60 vs SH (locked
protocol); chapter exit step 5: pooled 3×3000 ≥ 0.756 one-sided; the five-leg
battery per CLAUDE.md; FP budget pinned by a one-time 20/500 ladder; the clone
built alongside; > 5 h → hand-over launch. The credit line and the five pre-reg
rules (CLAUDE.md "Conventions") bind.

## The files under review
- configs/gen4_wang50m.yaml (the header + the training config)
- configs/gen4_wang50m.prereg.yaml (the machine-readable sidecar)
- configs/gen4_wang50m_smoke.yaml (the one-diff partner)
- tests/test_gen4_prereg.py (the consistency gates)
- scripts/gen4_wang50m_wave.sh (the launch/watch script)

## The code the header makes claims about (verify, don't trust)
- rl/agents/ppo.py: `lr_schedule` / `lr_power_a` / `lr_power_b` (the anneal
  branch in `_optimize`), `value_clip_eps` (the minibatch loop), `attach_harvest`
  and the union batch in `update()`; tests/test_wang_recipe.py.
- rl/selfplay/harvest.py, rl/selfplay/pool.py (`move_logp`), rl/envs/showdown.py
  `PoolPlayer` (the harvest hooks), rl/envs/gen4/env.py; tests/test_harvest.py.
- rl/networks/entity_deepsets.py (`TrunkLayout`, `resolve_layout`);
  tests/test_entity_trunk_gen4.py.
- rl/train.py (the `harvest_both_seats` seam, the anneal guard, `_vector_loop`'s
  step / checkpoint / eval arithmetic).
- rl/envs/gen4/spec.py (LAYOUT), rl/envs/gen4/vocab.py + data/gen4_vocab.json.
- scripts/eval_checkpoint.py, scripts/gen4_fp_h2h.py, scripts/tape_to_dataset.py,
  scripts/train_bc.py (the post-run instruments the schedule names).
- The pattern files: configs/showdown_sp_100m.yaml (the last ratified training
  header) and configs/eval/ladder_r4.yaml (build items / barred_language form).
- docs/prior_work/README.md (Wang entry) and the thesis text if you need it:
  docs/prior_work/wang2024_mit_thesis_randbats_rl.pdf (pdftotext is on the box).

## Smoke provenance
The R0-e readings in the header come from a 3-update run of
configs/gen4_wang50m_smoke.yaml on 2026-09-05 (scratch cwd, the test suite
running beside it). Treat every rate as a lower bound; do not ask for more
smoke.
