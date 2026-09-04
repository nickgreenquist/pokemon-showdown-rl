ultracode. You are running a RESEARCH/DESIGN session for the gen4 chapter of
this project — DOCS ONLY, no code under rl/ — in an isolated worktree, while
a 100M training fleet runs on this box and a second session works audit fixes
in ../pokemon-showdown-rl-audit. Use workflows: multi-modal research sweeps,
independent design memos, adversarial synthesis. Token cost is not a
constraint; correctness and completeness are.

## HARD BARS (a ratified 100M run + its frozen eval schedule own this box)

1. NEVER touch the main tree at
   /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl — no edits,
   no checkouts, no commits there. Work ONLY in your own worktree.
2. NEVER run `pip install` into the `pokemon-showdown-rl` conda env (its
   editable install must keep pointing at the main tree).
3. NEVER touch the Showdown server / port 8000, never start battles, never
   kill or signal any existing process (rl.train lanes, ch5_100m_wave.sh,
   caffeinate, node, samplers). No evals of any checkpoint, no training, no
   benchmarks — the pre-reg peeking bar covers everything until the fleet
   AND its post-fleet eval schedule complete.
4. CPU politeness: you are a docs session — you should need almost no local
   compute. Anything unavoidable runs under nice -n 19.
5. Do not read/write runs/ or logs/ in the main tree.
6. Commit on your branch only; never push, never merge.

## SETUP

    cd /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
    git worktree add ../pokemon-showdown-rl-gen4design -b gen4-design
    cd ../pokemon-showdown-rl-gen4design
    mkdir -p docs/design_gen4

Read first, in the worktree: CLAUDE.md (binding), JOURNEY.md (gen4 is step 3;
this design work is maintainer-ruled preparation running ahead of step 2 —
say so in every doc header), prior_work/README.md IN FULL (the verified
index — read it before citing ANY external result; several popular claims
about these systems are recorded there as wrong), docs/landmines.md.
Read-only reference: ../pokemon-showdown-rl-audit — the audit branch is
building the EncoderSpec per-gen seam (its docs/AUDIT_ACTION_PLAN.md, finding
F-08). Design AGAINST that interface; if the seam isn't written yet, design
the interface you need and record it as a proposal to reconcile at merge.

## PRIOR WORK — anchor the sweep here (all indexed in prior_work/README.md)

- **Wang 2024 (MIT thesis) is THE closest prior work for gen4**: PPO +
  test-time MCTS on gen4randombattles, Elo 1756 / GXE 79.5%, ladder rank 8.
  The thesis pdf AND full fork-vs-upstream diffs of his three repos are
  vendored (wang_fork_diffs.md, 2,362 lines). Mine the diffs, not the prose:
  encoder features, action space, reward, γ=1.0/λ=0.95 at 128k steps/update
  (the index corrects the "convergent recipe" myth — his λ is OURS, not
  ps-ppo's 0.75). Note his search is test-time only.
- **Huang & Lee 2019** (gen7RB, pure PPO self-play, no search, 1677/72%) —
  the pure-self-play lane's only verified comparable; both-seat harvest and
  seat accounting are documented in the index entry.
- **pokejax** (gen4randombattle JAX engine, scratch PPO ~0.55) — weak
  baseline datapoint, but its gen4 engine choices are worth a read.
- **SimpleHeuristicsPlayer's own gen4 row**: Gen4OU 36.8%/31.6% — SH is
  weaker in gen4-adjacent formats than gen7/9; the anchor question below
  follows from this.
- The index's caveat stands: every external row is a cross-format
  extrapolation; vs-SH numbers are never ladder numbers.

## DELIVERABLES (each its own file under docs/design_gen4/, committed)

1. mechanics_delta.md — gen1→gen4 rules delta that MATTERS TO AN ENCODER
   AND POLICY: physical/special split per-move (kills the by-type rule),
   types 15→17 (Dark, Steel), items, abilities, weather, hazards
   (Stealth Rock/Spikes/Toxic Spikes), new status/volatile semantics
   (sleep/freeze mechanics changes, Substitute, Protect, U-turn momentum),
   team preview absence in randbats, anything that breaks a gen1 encoder
   assumption. Cite sources; verify against the vendored showdown/ data
   files (read-only) where possible — e.g. showdown/data/ move/species
   tables and random-battles/gen4 team pools if present.
2. pokeenv_gen4_survey.md — what the PINNED poke-env version supports for
   gen4randombattle: action space size (index says 10 through gen 5 —
   verify in singles_env.py), battle-object fields present/absent vs gen1
   (items, abilities, weather exposure), request parsing gaps, known
   issues. Read the installed source; NO live server tests — mark every
   claim that needs one as "needs live verification post-fleet".
3. encoder_requirements.md — the gen4 EncoderSpec: per-gen tables (types,
   type chart, categories, volatiles, items, abilities), vocab sizing
   (species/moves — count from the vendored gen4 data), feature blocks and
   dims, what stays shared with gen1, what is new. MUST design against the
   audit branch's F-08 EncoderSpec seam interface; gen1's 828-dim layout is
   untouchable (bit-identical constraint, OBS_DIM landmine).
4. anchors_and_eval.md — what SH is worth in gen4RB (its Gen4OU row is
   weak), what replaces/joins it (the most-damage-typed anchor from
   IDEAS_POST_100M.md §2.6 is JOURNEY's own pre-step-3 item — spec it here),
   what Foul Play equivalent exists for gen4 (Wang's MCTS? note the index's
   poke-engine gen-feature-flag landmine), and how the gen1 anchor-battery
   convention translates.
5. open_questions.md — everything needing a maintainer ruling, each with
   your recommendation and the losing argument (the 2-Opus-synthesis house
   style): e.g. gen4 as fresh net vs transfer from the gen1 final; shared
   vs per-gen action head; whether step 3 starts before/after ladder #3.
6. OPTIONAL STRETCH (only after 1–5 are committed): IDEAS_POST_100M.md §2.5
   search-depreciation write-up (free, feeds the step-2 ladder-object
   ruling) as docs/design_gen4/search_depreciation.md.

## METHOD

Run it as staged workflows: (a) parallel research sweep — one agent per
source family (Wang diffs, H&L, poke-env source, vendored showdown data,
mechanics references), each returning structured findings with citations;
(b) two independent design memos for the encoder requirements (an
evidential-validity lens and a build/ops lens), then an adversarial
synthesis that records each adjudication WITH the losing argument; (c) a
completeness critic pass — what claim is unverified, what source unread,
what gen4 mechanic unhandled — and fold its findings back in. Every doc
opens with a header naming its verification status per claim (tree-verified
/ source-verified / literature-only / needs-live-verification).

Small single-purpose commits. End state: worktree clean, branch committed,
open_questions.md current. Do not push.
