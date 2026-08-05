# SESSION LOGS

Dated entries, append-only. Index: `grep -n '^- 20' SESSION_LOGS.md`, then Read the
entry by offset — never a broad keyword grep.

- 2026-08-05 — Old repo's cleanup VERIFIED; dedicated conda env `pokemon-showdown-rl` created

  Final sweep of deep-rl-from-scratch after its close-out push (6 commits, tip
  `aa033dd`, clean tree): code grep for showdown/poke_env across .py/.toml/.yaml/.sh —
  zero hits; every retained md doc (README, PLAN, PLAN_ARCHIVE, SESSION_LOGS, STATUS,
  CLAUDE) — zero 'showdown' mentions. Their cleanup claim is TRUE and goes further
  than their own removal manifest recommended: the Phase-5 narrative was scrubbed from
  the working docs, so **the old repo's capstone log entries / Phase 5 spec now exist
  only in its git history** (pushed, so durable — `git show <pre-strip>:SESSION_LOGS.md`
  there if primary sources are ever needed). Their README carries no forwarding link
  to this repo. Nothing in their six final commits contained capstone material we
  lacked. Their close-out also confirmed the shared-env hazard from their side: two
  repos both shipping a top-level `rl` package must not share an env (first `.pth`
  alphabetically wins, silent wrong-tree imports — measured).

  Env migration (maintainer removed `deep-rl` with `conda env remove`): created
  `/opt/anaconda3/envs/pokemon-showdown-rl` (Python 3.13), `pip install -e ".[dev]"`
  from pinned pyproject. Verified: `import rl` resolves here from a neutral cwd;
  torch 2.13.0 and poke_env import; offline suite `288 passed, 8 warnings`. CLAUDE.md
  env section updated (name, recreate line, one-env-per-repo warning); the only other
  deep-rl mentions in live docs are provenance naming, left alone.

- 2026-08-05 — Git history imported: the capstone lineage is now this repo's `main`

  Executed the approved plan. Cloned the old repo (222 commits) into the scratchpad;
  `filter-branch` keep-list = rl/ scripts/ tests/ configs/ assets/ prior_work/
  pyproject.toml .gitignore DESIGN_P7.md with --prune-empty; squashed baseline commit
  built from the parent of the first capstone commit (old `0ef4775` "Phase 5 env
  plumbing", 2026-07-29); grafted and baked. Result: **baseline + 41 capstone-era
  commits = 42** (49 of the 90 capstone-era commits touched only dropped doc paths and
  pruned away); tip `f8ca9b6` = old `57a93e5` ("P6 COMPLETE"). Fidelity verified:
  kept paths of the filtered tip are byte-identical to old HEAD `61752d4` (empty diff).
  Fetched into this repo as `main`, index reset to HEAD; the working tree now carries
  exactly the bootstrap diff (pyproject rewrite, DESIGN_P7.md → DESIGN.md with
  revisions, logging.py WANDB_PROJECT fix, six new docs) — bootstrap commit lands when
  asked. Old-repo commit hashes resolve only in the archive; hashes are strict from
  here on.

- 2026-08-05 — PORT VERIFICATION PASSED (8/8, measured) — old-repo strip AUTHORIZED

  All eight MIGRATION.md checks reproduced their recorded numbers; MIGRATION.md,
  start.md and PORT_VERIFICATION_HANDOFF.md deleted per their own lifecycle rules.
  Measured results:

  1. Provenance: `rl.__file__` → this repo from a neutral cwd, re-verified at the end.
     Gotcha for the record: the new dist name does not displace the old editable
     install — required an explicit `pip uninstall deep-rl-from-scratch` after
     `pip install -e ".[dev]"`.
  2. Independence: zero functional old-repo references (only the exempt pyproject
     provenance comment). Re-verified at the end.
  3. Offline suite: exactly `288 passed, 8 warnings` (needs the server up — two
     server-gated tests in test_collect.py; first run without it: 286 + 2 skipped).
  4. Full suite: `318 passed, 8 warnings`, zero failures; known flake did not fire.
  5. BC val agreement, recomputed from checkpoints over the reconstructed battle-level
     split: 0.901660 / 0.898744 / 0.904674 — bit-identical to recorded; val rows
     90242 / 89955 / 89797 match.
  6. Live smoke (runs/migration_smoke, 4k steps): clean connect/train/eval/exit, all
     seven locked metric keys in history.csv.
  7. Throughput (runs/migration_tput, 150k steps, single lane, maintainer terminal):
     median 733.8 steps/s over last 90% (bar >659 — `simulator: 4` operative);
     collect/update split 94.7/5.3.
  8. Ported clone finals via score_ladder (1000 battles/seed, maintainer terminal):
     0.460 / 0.455 / 0.482, pooled 1397/3000 = 0.4657 vs recorded 0.4530 (~1σ);
     every band condition met. JSONs: runs/bc_p4_512_40k_s*/migration_check8.json.

  Flagged decision for the strip (not a blocker): the old repo's milestone-1/2 run
  dirs (showdown_heur*, showdown_maxbp, showdown_mix512, showdown_sp6m, shakeouts,
  tput probes) were NOT copied — judged superseded (numbers live in the old repo's
  retained docs). Their deletion is a maintainer decision, not an accident. Also open:
  whether to adapt the old repo's doc-archaeologist agent here.

  GIT HISTORY IMPORT PLAN (approved 2026-08-05; preserved from MIGRATION.md before its
  deletion): import the capstone's commit lineage as this repo's root. Shape:
  path-filter to the ported files (rl/, scripts/, tests/, configs/, pyproject.toml,
  .gitignore, DESIGN_P7.md) AND cut at capstone start (~2026-07-25), one squashed
  baseline commit ("harness as inherited at capstone start"), genuine capstone-era
  commits on top, bootstrap committed above that (when asked). Mechanics: clone the
  old repo into the scratchpad, filter the CLONE (old repo untouched — its .git keeps
  full history even after the working-tree strip), fetch the filtered branch here as
  `main`, `git reset --mixed` so the tree diff vs imported HEAD is the bootstrap.
  Accepted: hashes rewrite once at import, strict thereafter; no history-wide
  personal-details audit (rule relaxed 2026-08-05).

- 2026-08-04 — Repo bootstrapped from deep-rl-from-scratch

  Copied per start.md §2 while the old repo's 6-lane P6 run was live (old repo treated
  as read-only; file reads only): `rl/`, `scripts/`, `tests/`, `configs/`, `prior_work/`,
  `assets/`, `DESIGN_P7.md`, `.gitignore`, `runs/bc_p4_512_40k_s{0,1,2}`, `data/`
  (3.6GB), `showdown/` (286M, `simulator: 4` verified at `config/config.js:111`).
  Excluded `__pycache__`/`.pytest_cache`/`.DS_Store`. Old repo's markdown docs NOT
  copied by design — their durable content is distilled into this repo's CLAUDE.md /
  STATUS.md / README.md.

  Rewrote `pyproject.toml` (name `pokemon-showdown-rl`; pins unchanged — spine code and
  tests still import gymnasium/minatar/mujoco/open_spiel; deps prune with the spine).
  Wrote CLAUDE.md (charter, environment, landmines, conventions), STATUS.md (60-line
  cap), README.md. Per start.md's later edit: the design doc is the roadmap; STATUS.md
  points at it instead of restating it.

  Renamed `DESIGN_P7.md` → `DESIGN.md` (maintainer call: fresh repo, no old-repo phase
  names). Inside the doc: proposal arms P7a/b/c → Arms A/B/C; P4/P5/P5b/P6 kept — they
  name the predecessor's measured experiments (a naming note says so). Also fixed
  now-stale old-repo references: "no RL libraries by hard rule" in §1, the PLAN.md
  lifecycle line, the §10 Metamon governance paragraph (rule retired here; provenance +
  pinning is what binds), and the absolute ps-ppo path (now `../ps-ppo`). Revision 4
  note in the doc records this; no measured number or claim changed.

  start.md gained §8b (port verification, 7 checks with recorded numbers to reproduce).
  Ran check 1's diagnostic early: `import rl` from this root resolves here only via cwd
  shadowing — the env's editable install is still `__editable__.deep_rl_from_scratch`
  pointing at the old repo. Fix (`pip install -e ".[dev]"`) is pip and therefore waits
  for the all-clear; it should also wait for the old repo's P6 finals, which import
  `rl` and would otherwise resolve to this repo's copy mid-run. Checks 2–7 pending.

  Created MIGRATION.md (maintainer call): carries §8b's seven checks + recorded numbers,
  the preconditions (P6 done → old repo's finals done → editable swap), the copy
  inventory, and a result field per check — so start.md can be deleted without losing
  the verification protocol. It gates DESIGN.md work and is itself deleted when all
  checks pass. Referenced from STATUS.md next-actions and CLAUDE.md docs list.

  Added independence check to MIGRATION.md (maintainer call: zero functional references
  to the old repo — code must live here; provenance naming in comments/docs stays, the
  charter requires it). Ran it: one functional hit, fixed — `rl/common/logging.py`
  `WANDB_PROJECT` "deep-rl-from-scratch" → "pokemon-showdown-rl". No old-repo paths in
  copied runs/ artifacts or anywhere else in code. Note: W&B runs now land under the
  new project name; old-repo W&B history stays under the old one.

- 2026-08-04 — Final sweep of the old repo (maintainer request): gaps found and closed

  Verified: rl/, scripts/, tests/, configs/, prior_work/, assets/ all match the source
  file-by-file (pycache/.DS_Store excluded); showdown/.git came across (pin provenance);
  old HANDOFF.md is the empty stub (nothing mid-handoff).

  Rescued (~6.3GB; all finished, live P6 dirs untouched — start.md §0 says the old
  session will strip the capstone from the old repo, so result-backing checkpoints were
  at risk): showdown_r512_lra_s{0,1,2} (P5b best RL 0.4433), showdown_r512_s{0,1,2}
  (P5 control 0.3923), showdown_scratch12m_s{0,1,2} (12M flat 0.417), bc_p4_512_s{0,1,2}
  + bc_p4_512_sub10k (P4 scaling arms). All diffed file-by-file post-copy: match.

  Knowledge from old STATUS.md not previously carried over (now in STATUS.md watch):
  annealed checkpoints cannot be warm-extended — a 12M anneal arm runs from scratch with
  lr_anneal_steps: 12000000; poke-env 0.15.0 SH setup-branch upstream bug, report
  unfiled; inherited backlog — decompose collect via `scripts/showdown_throughput.py a`
  (last ran 2026-07-30 on the 10-dim placeholder encoder, pre-611-dim; an encode timer
  must NOT go in shared code — `embed_battle` is inside `ShowdownSingles`, and a
  `hasattr` branch in `rl/train.py` is what the masking contract bans). Also noted:
  P5b per-seed 0.416/0.468/0.446 — s0 is the recurring weak seed; watch seed spread.

  Left in the old repo by decision (recorded in MIGRATION.md): all pre-migration md
  docs/history, top-level wandb/ and logs/, live P6 dirs, and
  .claude/agents/doc-archaeologist.md — flagging for the maintainer whether to adapt it
  here (its protocol targets the old repo's PLAN_ARCHIVE/SESSION_LOGS).

- 2026-08-05 — P6 COMPLETE and CREDITED (from the old repo; recorded here as the durable copy)

  Distilled from the old repo's final SESSION_LOGS entry (written at close-out from run
  artifacts) — which CORRECTS two mechanism claims in P6_RESULTS.md; where they differ,
  this entry and the old log win.

  Design: flat vs annealed LR at 12M on r512, 3 seeds/arm, 6-wide; arms seed-UNPAIRED
  by necessity (flat s0/s1/s2, annealed s3/s4/s5 — the collision landmine). Annealed =
  linear 2.5e-4 → 0 over 12M, from scratch. 6/6 lanes completed (425,265–431,269 rows,
  62 ckpts each); R0 gates passed on all six.

  Finals (locked protocol): flat 0.425/0.424/0.450 → pooled 0.4330; annealed
  0.449/0.451/0.482 → pooled **0.4607**. Delta +0.0277, z = 2.16 → **CREDITED, clearing
  the line by 0.003** where the 6M read cleared by double. Direction replicates,
  magnitude does not. Recorded caveat, not re-litigation: seed-level Welch t ≈ 2.03,
  p ≈ 0.12; both arms carried by one strong seed. Per-seed cross-arm comparison is
  meaningless (unpaired); the pooled test never assumed pairing.

  What it moves: first RL result past the BC clone (0.453); 0.028 under the 0.489
  mirror ceiling; P4's training-side gap is CLOSED. Flat 6M→12M = +0.0407, so raw
  budget bought as much as the anneal; annealed 6M→12M only +0.017. Undercuts DESIGN.md
  Arms A premise — revision 5 banner merged there from the old repo's revision 4.

  Mechanism (corrected vs P6_RESULTS.md): approx_kl second-half flat 0.00554 vs
  annealed 0.00167 — 3.3× (NOT "halved"); annealed decays monotonically by quarter
  (0.00468/0.00367/0.00233/0.00101) vs trendless flat. clip_frac 0.0569 vs 0.0206
  (2.8×), newly recorded. Entropy DID separate — clean 3-vs-3 rank split (annealed
  0.2541–0.2746 below flat 0.2773–0.2817) — but only ~6.5%; the pre-registered tell
  (entropy collapse) did not occur. Loop split held 94.8/5.2 over the full 12M.

  Artifacts now here: runs/showdown_r512_12m_s{0,1,2}, runs/showdown_r512_lra12m_s{3,4,5}
  (rsynced, row counts verified vs source), runs/p6_finals_logs/ (the six gitignored
  finals_*.log the numbers are sourced from — they were on the old repo's deletion
  list). P6 is done; it never needs re-running.

- 2026-08-05 — Two maintainer decisions: history import approved; public-repo rule relaxed

  Git history: import the capstone's commit lineage from the old repo as this repo's
  root — path-filtered to the ported files + cut at capstone start (2026-07-25) with a
  squashed baseline commit, capstone-era commits on top, bootstrap commit above that.
  Run only after the old session commits P6 finals + result. Hash rewrite accepted for
  the import ("fine for the history import, we can be strict going forward"). Full plan
  in MIGRATION.md.

  Public-repo strictness relaxed: the "no personal details in committed files — may go
  public" obligation drops to "keep secrets out"; local paths etc. are fine. Updated in
  CLAUDE.md (charter), DESIGN.md §10 (license caveat reworded; not committing unlicensed
  data still stands). MIGRATION.md check 2's `/Users/` grep stays — it guards old-repo
  independence, not privacy.

  Not done yet, blocked on the P6 run finishing (~02:00–02:30): `pytest tests/`,
  deleting `start.md`, first commit. P6's result arrives via separate handover.

- 2026-08-05 — DESIGN.md revision 6: rewritten vs P6, hardened by three review passes

  The handoff's singular next action. Full rewrite of DESIGN.md against the P6 numbers,
  then three independent Opus review passes (experimental design / strategy+priorities /
  adversarial fact-check) whose accepted findings were folded in. P6_RESULTS.md deleted
  as pre-flagged (durable record: the P6 entry above + DESIGN r6). HANDOFF.md stub
  restored. Docs only — no code changed, no runs launched.

  CORRECTION (wins over the P6 entry's phrasing above): "first RL result past the BC
  clone" was overstated. Port check 8 re-scored the same clone checkpoints in-repo at
  0.460/0.455/0.482 → pooled 0.4657 (vs 0.4530 recorded, ~1σ); RL's 0.4607 sits between
  the clone's two same-protocol measurements, and P6's own pre-registered "past the
  teacher" amendment mark (pooled ≥ 0.47, configs/showdown_r512_12m.yaml) was not
  reached. Correct claim: LEVEL with the clone. P6's PRIMARY (anneal credited vs flat)
  is untouched by this.

  Substantive design changes from review, all argued in DESIGN r6:
  - Arm B redesigned: terminal cancellation added (faint potential zeroed at terminal;
    without it the shaping telescopes to ±0.6 against the ±1 outcome and the trade-down
    failure mode is IN the objective, not a risk); shaping-correctness R0 gate; mechanism
    reads pre-registered (value explained-variance must be added to logging first);
    loss-conditioned secondaries with a falsifier.
  - Arm C PARKED: under terminal-only ±1 at gamma=1.0 the return support is {-1,0,+1} —
    a 51-bin categorical head has nothing to model. Unpark iff Arm B credits or dense
    signal arrives; if unparked, TOST equivalence gate + specified distributional target;
    note CartPole/MinAtar baseline run dirs were never ported.
  - Arm A retired to a ~1 h single-seed warm-start smoke from runs/bc_p4_512_40k_s0
    (guard fix + critic-only warmup + step-0 win-rate handoff check) — de-risks the
    human-BC chapter's day-one path for ~1/6 the cost of the arm.
  - Credit line now names its se estimator (larger of pooled-binomial / seed-clustered;
    P6 cleared by 0.003 or 0.0003 depending on the choice — ambiguity closed). Proposed
    amendment: finals at 3000 battles/seed for arm AND control (variance decomposition:
    ~88% of arm-mean variance is battle noise; se_diff 0.0137 → 0.0088 for eval-only
    cost); 6M futility screen at +0.009 with the full credit line applied only at 12M.
  - D4 (24M scaling run) statistical rationale corrected: the annealed 6→12M marginal
    (+0.0174 ± 0.0129, z=1.35) is inside noise and confounded by schedule shape;
    rejection rests on the stop rule and the SH-exploitation argument alone.
  - Track 1 re-scoped into a parse-free afternoon (recency cutoff, rating nullity,
    winner extraction, teams.ts coverage, Foul Play support + measured latency) and a
    parser-slice half (clean-parse fraction, action=-1 share, RecordingPlayer golden-path
    round-trip test); provisional go/no-go bars stated for the review to adjust.
  - §10 risks added: era drift, MNAR bias of hidden-action rows (they correlate with
    switch decisions — the exact skill the corpus is bought for), scale honesty (25–50 GB
    embedded at corpus scale; current BC loader is load-all-into-RAM; raw storage is
    deferred cost, not zero cost), HF revision pin, clone evaluation plan.
  - New D7: ladder performance as the ratified success metric + defined end state; GPU
    rental gated on a measured embed/parse throughput split; the unlicensed corpus does
    not leave the local box without an explicit decision.
  - D6 amended: recover the old repo's showdown_sp6m self-play numbers into these logs
    before deferring the post-parity opponent question (the old repo dir is still on
    disk with full .git; run dirs were deliberately not ported).

  Fact fixes vs the pre-review r6 draft, from the fact-check pass: costs requalified
  (2.9 h is 3-wide; 12M is ~6.5 h), episode length ~25 (measured 24.2–24.6, not ~27),
  approx_kl figures re-labeled as cross-arm second-half means with the monotone
  by-quarter decay restored, Wang 0.786 provenance hedged (no step count in our index;
  Fig 4.1 ~0.85 unreconciled), Foul Play "well above SH" downgraded to
  placement-inferred, the poke-env SH setup-branch bug disclosed next to the board,
  the stop rule's README amendment condition restored, corpus selection-bias and
  governance-relaxation notes restored, and self-containment restorations (VGC-Bench
  quote, Metamon action-space specifics, pokejax obs-bridge precedent, clone
  free-agreement numbers, ps-ppo commit hash 17e0955).

- 2026-08-05 — Post-migration audit + cleanup; sp6m self-play record RECOVERED (D6 amendment done)

  Three-Opus-subagent audit (configs/references, runs+staleness, old-repo recovery),
  findings applied. Suite re-run after changes (see verdict at entry end).

  CLEANUP APPLIED (all git-reversible):
  - 61 dead configs deleted: the 56-file predecessor spine (cartpole non-PPO, connect4,
    frozenlake, lunarlander, mujoco, pendulum, all minatar DQN + PPO lr-sweep variants)
    plus 5 non-science probes (showdown_probe_100k, r512_tput, scratch_shakeout,
    sp_probe, sp_shakeout). Verified first: NO test, script, or module reads configs/
    (no glob, no default path; rl/train.py --config is required=True) — deletion cannot
    turn the suite red. Kept 18: 6 roadmap (cartpole_ppo + 5 minatar PPO — Arm C spine
    gate), 8 live/control showdown, 4 milestone provenance (maxbp, heuristics_ppo,
    heur_6m, mix_512 — their numbers now recorded below).
  - README results section brought current: P6 rows added, "clone beating every RL
    result" claim replaced with the level-with correction, +0.051 qualified as the 6M
    figure, roadmap pointer updated.
  - scripts/train_bc.py --data default fixed (pointed at nonexistent
    bc_heuristics_vs_heuristics.npz; now data/bc_p4_40k.npz, the file backing the live
    clone). scripts/train_supervised.py comment repointed (connect4_pool.yaml deleted).
  - DESIGN.md §8 paired-eval line upgraded from "unmeasured here" to the recovered P3
    measurement; D6 marked recovery-done with the recovered verdict inline.
  - doc-archaeologist agent ADAPTED here (.claude/agents/doc-archaeologist.md), from
    the old repo's 793f9bf, repointed at this repo's docs — closes one of the two open
    maintainer decisions.

  CORRECTION (of the 2026-08-04 sweep entry's rescue list): showdown_scratch12m_s{0,1,2}
  is NOT "12M flat 0.417". It is the 12M PURE SELF-PLAY arm (config on disk:
  selfplay.opponent: self, pool_size 20, rollout_steps 128); its on-disk finals pool to
  0.3800 ± 0.0089 (0.369/0.398/0.373). The 0.417 figure belongs to showdown_heur_512
  (12M vs fixed SH, pre-P5 recipe, pooled 0.4170 across s0/s1/s2 per the old repo's
  2026-08-02 replication) — whose run dirs were NOT ported.

  RECOVERED — showdown_sp6m (milestone-3 run 1), from deep-rl-from-scratch
  SESSION_LOGS.md@5d6a604 (full SHA 5d6a604f9bc129512cfd556418ea678874fe52fe):
  - Design: warm-started snapshot-pool self-play (pool 20, latest_prob 0.8,
    push_every_updates 150 ≈ half-run span) vs matched control showdown_cont6m (same
    0.408 12M parent ckpt, same 6M budget, fixed-SH opponent) — training distribution
    the single variable; 3 seeds each, ~3 h/arm 3-wide at ~553 steps/s.
  - Result 2026-08-01: SELF-PLAY NOT CREDITED. Locked finals SP 0.408 ± 0.018
    (436/375/414) vs CT 0.432 ± 0.018 (421/446/428); Δ = −0.023 inside the ±0.025
    floor (z ≈ −1.8). Cross-play SP-vs-CT 3008/6000 = 0.501; SP-vs-parent 3030/6000 =
    0.5050 ± 0.0065 — 6M of self-play moved the policy ±1.3 points from its own parent.
    All health gates green (ties 1.1–2.4%, ep len ~26.7, entropy 0.384–0.391, no
    forgetting — H&L §V-C never fired).
  - The control's +0.024 is specialization, not strength: CT-vs-parent head-to-head
    3059/6000 = 0.5098.
  - Caveats that must travel with the number: the 3-seed paired design resolves only
    MDE ≈ 0.14 at the recipe level (a null about THIS init and budget, not the recipe
    class); the pool was measured strength-homogeneous (winrate_latest 0.4986–0.5013),
    killing latest_prob/PFSP retuning at this rung by measurement; SP seed spread 0.061
    vs CT 0.013; and a +0.018 ± 0.0065 deterministic-vs-sampling SEAT BIAS makes any
    single-orientation cross-play read wrong by ~2 points (both-orientation averaging
    cancels it).
  - Companion: showdown_scratch12m (above) reached 0.4837 ± 0.0065 head-to-head vs the
    equal-budget fixed-bot policy — a genuine generalist approaching the plateau from
    below; the plateau, not the training distribution, binds. Also recovered: the
    entropy-collapse of Connect 4 did NOT reproduce (server-rolled teams are the
    Tesauro dice).
  - LIVE BUG recovered with it: rl/selfplay/pool.py evicts index 1 on overflow,
    flushing pre-seeded pools by ~push 19 of 39 — fix before any future self-play rung.

  RECOVERED — milestone one-liners (same source; backs the 4 kept milestone configs):
  maxbp 2M placeholder-encoder 0.663 ± 0.029 vs MaxBasePower (milestone 1 PASSED; same
  policy vs SH 0.262); heur 2M [64,64] 0.292 ± 0.028 (still climbing at wall); heur_6m
  0.358 ± 0.015 (budget lever "credited, exhausted"); heur_512 12M [512,512] 0.408 ±
  0.030 s0 ("CAPACITY WAS BINDING"), replicated s1 0.411 / s2 0.432 → pooled 0.4170 ±
  0.0090; mix512 (70/20/10 opponent mix, 6M×3) 0.356 ± 0.017 NOT CREDITED. Also: the
  [512,512] band extrapolation "+0.153/+0.103/+0.061/+0.027/+0.016 (ratio ≈0.65) →
  asymptote ≈0.42" — the source of "the 0.42 asymptote"; and the turn/50 encoder clock
  saturates at 50 (dead vs heuristics, load-bearing under long self-play games).

  RECOVERED — where the load-bearing written records live (all @5d6a604, old repo):
  P4 bucket analysis (forced-switch 0.866 / voluntary-switch 0.556 / all-status 1.000 /
  multi-hit 2.1%) and data-scaling (+0.021/doubling, ratio 0.78 = fresh-common-ground
  0.0271→0.0212 read — NOT the bc_metrics.json val-agreement deltas, which give ~0.83);
  2,769 decisions/s (also in DESIGN_P7@import); P3 team-draw R² = 0.0375 lower bound +
  paired-episode correlation ≤ 0.04 over 21 run-pairs ("no analysis plan may rely on
  it"); mirror b = 0.489 n=20k / 0.486 n=40k.

  ⚠ PRESERVATION DECISION NEEDED (maintainer): the predecessor's 36 capstone session-log
  entries, README Phase-5 write-up, and PLAN.md Phase-5 spec exist ONLY at old-repo git
  5d6a604 — this repo's imported history was path-filtered to code/configs/DESIGN_P7/
  prior_work and contains none of it. The old repo's own removal doc (CAPSTONE_REMOVAL
  §4) argued against deleting that narrative. One rm -rf from gone. Options: commit an
  extracted archive here (e.g. prior_work/predecessor_capstone_logs.md, un-gitignored),
  git bundle the old repo, or accept the risk. Related: prior_work/wang_fork_diffs.md is
  maintainer-AUTHORED analysis but sits under the prior_work/* gitignore — consider a
  !negation.

  RUNS/DATA RECLAIM (audited, ~12.5 GB runs + 3.6 GB data; awaiting sign-off — gitignored,
  irreversible): 75% of runs/ is intermediate ckpt_*.pt (9.34 GB, ~30× the finals per
  lane), 18% wandb/ (2.27 GB — history.csv row counts verified against the logged
  425,265–431,269 this session, so wandb is safely redundant). Candidates: intermediates
  9.34 GB + wandb 2.27 GB + migration smokes 69 MB + data/bc_p4_main.npz+sub10k 1.5 GB
  (regenerable; agreement numbers frozen in bc_metrics.json). DO NOT DELETE:
  p6_finals_logs (sole evidence for 0.4607/0.4330), bc_p4_512_* family incl. sub10k
  (36 MB — sole on-disk source of the +0.021/doubling ladder),
  showdown_scratch12m_s*/xplay_*.json, every final_eval/migration_check8/bc_metrics
  JSON. Provenance note: all run-dir meta.yaml git_shas are old-repo SHAs, unresolvable
  here — provenance runs through SESSION_LOGS narrative only.

- 2026-08-05 — Cleanup executed: predecessor logs preserved, ~12.5 GB reclaimed, spine PRUNED

  All three maintainer approvals from the audit executed same evening.

  PRESERVED: SESSION_LOGS_PREDECESSOR.md committed (commit 918aef0) — the 36 capstone
  entries extracted whole from deep-rl-from-scratch@5d6a604 (titles identified via the
  strip commit 0c3b972's deletion patch, entries taken byte-for-byte from the pre-strip
  file), plus the predecessor README "Results — Phase 5" section and PLAN.md Phase-5
  spec as appendices. CLAUDE.md Docs and doc-archaeologist repointed at it. The
  one-rm-rf-from-gone risk is closed.

  RECLAIMED (~12.5 GB): runs/ 12 GB → 1.0 GB, data/ 3.6 GB → 2.1 GB. Deleted: 696
  intermediate ckpt_*.pt + 9 mid-run 6M ckpts inside 12M lanes, all 17 wandb/ dirs
  (history.csv row counts verified against the logged 425,265–431,269 first),
  migration_smoke + migration_tput, data/bc_p4_main.npz + bc_p4_sub10k.npz
  (regenerable; agreement numbers frozen in bc_metrics.json), and the Connect-4 Pons
  data (solver_dataset.npz, Test_L*). Every lane retains its final numbered ckpt,
  checkpoint.pt, best_checkpoint.pt, config/meta/history.csv, and every eval JSON;
  p6_finals_logs and the bc_p4_512_* family untouched. data/bc_p4_40k.npz kept (backs
  the live 0.4657 clone and the Track-1 warm-start smoke).

  SPINE PRUNED (maintainer: "we don't need anything not related to capstone"):
  - Deleted algorithms: dqn.py, sac.py, q_learning.py, reinforce.py (+ replay buffer,
    polyak — SAC/DQN-only). ALGOS is now {random, ppo}; the QLearningAgent special
    branch removed from train.py.
  - Deleted the Connect-4 STUDY: solver.py, the alpha-beta opponents + play_game
    (opponents.py trimmed to Opponent/Random/Heuristic/make_opponent — pool.py's fixed
    anchors), tests test_solver/test_connect4_oracle (open_spiel oracle + the retired
    no-RL-libraries import ban), scripts (pons_benchmark, pons_agent_metrics,
    make_solver_dataset, value_mse_probe, coverage_probe, forgetting, tournament,
    train_supervised, mutate + mutations/), the 4 figure scripts, 8 predecessor asset
    figures (showdown_milestone3.png stays).
  - KEPT AS TEST FIXTURE, deliberately: rl/envs/connect4.py + test_connect4.py + the
    trimmed opponents.py. The self-play harness tests (49 tests backing the ported
    rl/selfplay/* that D6 keeps live) use Connect4Env as their two-player fixture;
    removing it means rewriting them. README records the framing the maintainer chose:
    the Connect-4 self-play study was the sanity check preparing this project.
    Flag: if the maintainer wants it fully gone, the cost is a two-player dummy env +
    test rewrite.
  - KEPT deliberately: normalize.py + its test (frozen_obs_env is imported by four
    live showdown scripts); continuous-PPO support + test_ppo_continuous (module-level
    prune only — no interior surgery on the live PPO); conv.py (ppo.py imports it;
    Arm C MinAtar gate); RandomAgent (ALGOS floor + scalar-loop coverage).
  - Test edits: masking's DQN section removed (contract coverage for the live algo
    stays), minatar conv-DQN smoke removed (conv-PPO smoke stays), run_capture +
    normalize-guard switched to random/PPO vehicles, scalar-split timer test removed
    (vector split — the capstone path — still tested), _VecRandomAgent restored after
    an over-cut.
  - pyproject: gymnasium[classic-control,toy-text,box2d,mujoco] → [classic-control];
    mujoco and open_spiel pins dropped; minatar stays. Installed env still carries the
    old packages until a `pip install -e ".[dev]"` refresh — harmless, optional.
  - README provenance paragraph rewritten with the maintainer's framing.

  Suite: 318 → 219 passed, zero failures — the delta is exactly the pruned spine's
  tests. Still open (unchanged): team review of DESIGN.md §9; wang_fork_diffs.md
  gitignore negation question.

- 2026-08-05 — PPO CORRECTNESS AUDIT: core CLEAN (bit-for-bit), one confirmed LATENT bug

  Motivated by the library-vs-ours question (ps-ppo turns out to be a custom PPO too;
  Wang is the one who used SB3). Method: one Opus subagent did an adversarial
  line-by-line audit of the learner core (ppo.py, rollout.py, masking.py) with
  runnable numerical repros; the main session independently audited the integration
  seams (vector loop, showdown env semantics, eval path, checkpointing) and
  re-verified the subagent's confirmed bug live before accepting it.

  CORE VERDICT: CLEAN. Strongest evidence: an independent re-implementation of the
  entire update from the PPO spec reproduced PPOAgent.update BIT-FOR-BIT (max |dparam|
  = 0.0 across all 12 tensors) at production settings. Verified item by item: GAE vs
  brute-force lambda-sum over 1500 randomized rollouts incl. gamma=1.0 (0 mismatches;
  termination cuts bootstrap, truncation keeps it); ratio contract (old_logp
  recomputed under STORED masks before any grad step — epoch-0 ratio exactly 1.0; all
  shapes (B,), no broadcast bugs); masked entropy GRADIENT exactly 0 on illegal logits
  (the unmasked form would leak 0.2255); per-minibatch advantage normalization after
  slicing, targets from unnormalized advantages; losses/optimizer (0.5*MSE value loss
  = SB3 convention); randperm-without-replacement epochs, old_logp/targets fixed
  pre-epoch; LR anneal arithmetic exact (CleanRL's schedule; 12M config consumes
  99.94% of it, floor clamped). Vector-loop wiring spot-checked end-to-end: stored
  obs/mask/action identical to what act() consumed/returned, 160/160 rows.

  INTEGRATION VERDICT (main session): CLEAN. The two nastiest seams are explicitly
  engineered away with rationale in-code: showdown.py:486 remaps every finished
  battle to terminated=True (poke-env reports forfeits/ties/timer as truncated,
  which would stack a bootstrap on a decided game's terminal reward at gamma=1);
  autoreset genuinely disabled with manual partial resets AFTER the terminal row
  reaches the buffer, reset-mask merge on done rows only; wait-states absorbed
  inside env.step (no phantom rows; reward accumulates across the pump); eval is
  fixed-seed deterministic masked argmax with outcome from battle.won/lost and a
  hard error on missing outcomes; checkpoints write-then-rename.

  CONFIRMED BUG (latent — no completed run affected, verified): PPOAgent.
  load_state_dict (ppo.py:493) restores the CHECKPOINT's optimizer hyperparameters,
  including lr, and a constant-lr config never rewrites lr after construction
  (anneal branch gated on lr_anneal_steps). Live repro: warm-start from an
  annealed-to-the-floor checkpoint (saved lr 1.44e-07) into a fresh lr=2.5e-4
  config -> trains at 1.44e-07 forever, silently. Both historical init_from configs
  (sp6m/cont6m) loaded a constant-lr checkpoint at identical lr, so nothing to date
  is corrupted — but P6's annealed checkpoints ARM the hazard on exactly the Arm A
  warm-start smoke path, and the train.py:134 guard does not fire (it checks the
  new config's lr_anneal_steps, not the checkpoint's saved lr). Fix (one line —
  re-assert base_lr after optimizer load, plus a regression test) is bundled into
  the Arm A warm-start-semantics decision (DESIGN D3/§4); not applied unilaterally.

  Low severity, recorded: (1) size-1 trailing minibatch NaNs the net when
  batch % (batch//minibatches) == 1 — impossible at production 4096/4, fails LOUDLY
  if ever hit; a construction-time divisibility assert is the cheap guard. (2)
  approx_kl/clip_frac are averaged over all 16 grad steps, damping the read ~1.5x
  vs CleanRL's last-minibatch convention — relative comparisons (P6's mechanism
  reads) survive; absolute bands are judged against a damped statistic. (3) No
  explained-variance or grad-norm logging — already a pre-Arm-B task in DESIGN §5;
  the audit measured (synthetic data) the 0.5 grad clip binding on 16/16 steps with
  the critic carrying ~93% of the norm, which production logging should check.
  (4) Coverage gaps -> five one-line test specs recorded by the audit: lr-after-load
  invariant, GAE property test vs brute force, vector-wiring bitwise test, minibatch
  divisibility guard, entropy-gradient masking test.

  Bottom line: the learner is not the risk the library question worried it was —
  keep ours stands on evidence now, not just argument. The one real hazard sits
  exactly where DESIGN already scheduled work (the warm-start smoke), one line away.

- 2026-08-05 — Warm-start lr bug FIXED (maintainer-approved, same evening as the audit)

  ppo.py load_state_dict now re-asserts the constructing config's base_lr after the
  optimizer load; regression test test_load_state_dict_keeps_the_configs_lr added
  (donor at the anneal floor 1.44e-7, recipient keeps its config lr, updates counter
  still restores). Live repro re-run against the fix: recipient stays at 2.5e-4.
  Annealed resumes unaffected (update() recomputes lr from the counter). Suite: 220
  passed. The audit entry above stands except its "not applied" line — applied here.

- 2026-08-05 — DESIGN r6 RATIFIED (maintainer review): D1–D7 adopted as recommended

  "Consider it human reviewed; the design is set, coding work starts." Decisions now
  binding, per §9's recommendations: D1 (c)→(d) corpus measurement now, chapter
  presumptive; D2 (c) Arm B 6M futility screen (advance ≥ +0.009) → 12M credit, with
  the 3000-battle/seed eval amendment for arm AND re-evaluated control; D3 (b) Arm A
  retired to the ~1 h warm-start smoke; D4 (c) no 24M run under the stop rule; D5 (c)
  no new benchmark yet (Foul Play checks ride inside Track 1); D6 both closures (MCTS
  downgrade formal; post-parity opponent question deferred to the corpus chapter —
  sp6m recovery already done); D7 (a) ladder performance is the ratified success
  metric, GPU rental gated on measured embed/parse throughput, the unlicensed corpus
  never leaves the local box. Arm C stays parked. DESIGN.md status flipped to
  RATIFIED; its pre-registrations migrate into config headers as arms are built, then
  the file is deleted per lifecycle. Maintainer's session setting for the coding
  work: Opus, high effort.

- 2026-08-05 — CODE EVENING 1: Track 1 measured, warm-start settled, Arm B built

  First session after ratification. Everything in HANDOFF.md item 1 landed, plus Arm B's
  code and config. Suite: 236 passed offline, +3 live-server (239). No runs launched.

  **1c — mechanism logging (rl/agents/ppo.py).** Added `loss/explained_variance` and
  `loss/adv_std` (batch-level, computed once per update on the PRE-update critic and the
  pre-normalization advantages) and `loss/grad_norm` + `loss/grad_clip_frac` (per grad
  step). EV uses the identity that the GAE residual IS the advantage, so it costs no
  second forward pass; a zero-variance batch reports 0.0 rather than a NaN that would
  poison the logger's history. Metric-namespace addition, recorded: these four join
  `loss/*`, and `eval/loss_faint_diff` + `eval/loss_faint_lead_frac` join `eval/*` (below).

  **PRODUCTION GRAD-CLIP READ (the audit's open question, answered).** Control recipe
  (showdown_r512_lra), production batch 4096, first 5 updates: grad_clip_frac
  1.00 / 0.875 / 0.625 / 0.75 / 0.50 with grad_norm 3.30 → 0.47. So the 0.5 clip does NOT
  bind 16/16 in production the way the audit's synthetic probe suggested — it binds hard
  at init and relaxes within ~20k steps. Caveat, stated: 5 updates is 0.34% of a 6M run,
  early-training only; steady state comes from Arm B's own curves. Same probe: EV starts
  strongly NEGATIVE (−2.72 → −1.22), i.e. the critic is worse than the batch mean for the
  first 20k steps — expected at gamma 1.0 with terminal-only reward, never measured here
  before, and the baseline Arm B's EV is read against.

  **1b — warm start settled as "a warm start is a FRESH run" (rl/train.py:124 guard
  DELETED).** New `Agent.begin_warm_start()`; PPO's rewinds the update counter and re-arms
  the warmup. Weights and Adam moments survive — they ARE the warm start. `init_from` +
  `lr_anneal_steps` is now legal and the anneal covers the new run's budget instead of
  resuming the donor's finished schedule at lr ~0. Staged unfreeze implemented:
  `critic_warmup_updates` (a TRUE freeze via requires_grad, so Adam skips the params —
  zeroing grads would let existing moments keep walking the weights) and `actor_lr_scale`
  on a new actor/critic param-group split.
    Two compatibility hazards found and closed while building it: (1) the param-group
  split would have made torch refuse every stored P4/P5/P6 checkpoint (they carry ONE
  group) — load_state_dict now grafts the moments onto OUR groups, exact because the
  flattened param order (actor then critic) is unchanged; verified live against the BC
  clone and both annealed 6M/12M finals. (2) At scale 1.0 the split had to be bit-for-bit
  a no-op on existing recipes — regression-tested against a hand-built single-group Adam.

  **Arm B — terminal-cancelled faint shaping (rl/envs/showdown.py).** Potential-based:
  Phi = 0.1*(faints_opp − faints_self), Phi(terminal) := 0, per-step reward Phi(s') − Phi(s).
  Written as a DIFFERENCED STATE POTENTIAL, never as faint-event attribution — the known
  trap in this exact lever (ps-ppo 17e0955) is an attribution off-by-one, and a difference
  has no attribution step to be off by one in. Keyed by the battle OBJECT: the two seats
  share a battle_tag, so any tag-derived key would fuse their faint counts (caught by a
  test, not by reasoning). New `Config.env_kwargs`, applied identically to the training env
  and every eval site, and forbidden from carrying opponent keys.
    R0 SHAPING GATE, both forms green: unit (scripted faint sequence sums to exactly the
  terminal ±1) and live (3 real battles, per-episode shaped return == info["outcome"],
  with an assertion that intermediate faint rewards actually fired). Stronger still, an
  8192-step real training run with shaping on produced 283 episodes whose returns were
  exactly {−1, +1} — the cancellation holds end-to-end through wait-absorption.

  **Arm A smoke validated end-to-end at small scale** (configs/showdown_warmstart_smoke.yaml,
  8192-step version, real BC checkpoint + anneal): approx_kl and clip_frac EXACTLY 0.00000
  for updates 0-1 then nonzero from update 2 — the actor froze and unfroze on schedule —
  and EV climbed −0.31 → +0.52. The full ~200k-step smoke is the maintainer's to run.

  **Configs written, both with pre-registration headers per the DESIGN-to-config migration:**
  `showdown_faint6m.yaml` (Arm B, seeds 6/7/8, 6M screen at +0.009 vs the re-evaluated P5b
  control, 3000-battle finals, mechanism + falsifier reads) and `showdown_warmstart_smoke.yaml`
  (seed 9, reads RECORDED not gated). Seeds 6-9 are free of 0/1/2 (lra) and 3/4/5 (lra12m).

  **TRACK 1 (parse-free half) — MEASURED, and it moves the corpus chapter's premise.**
  scripts/corpus_survey.py, one pinned 199,704,915-byte parquet (revision
  bc76388c2119f8a5694adf643c640610b157ee1c, sha256 44ca123d...), full pass in ~12 s.
  109,147 rows, 0 duplicate ids, formatid homogeneous. Numbers:
    (1) Upload years 2015-2026. Cutoffs: ≥2018 = 82,141; ≥2023 = 49,693; ≥2024 = 48,159;
        ≥2025 = 25,911.
    (2) `rating` is NOT mostly null in this format — 69,749/109,147 = 63.9% present.
        §10's "verified mostly-null" does not hold for gen1randombattle and should be
        corrected. But the population is weak: median 1203, p90 1415, 23,441 above 1300,
        1,358 above 1500, ZERO above 1700. In-log per-player Elo (from `|player|`) is
        recoverable for 2019-2026, median 1306. So a skill signal exists and is usable
        for reweighting; a strong-player tail essentially does not.
    (3) Decisions: mean 55.5/battle both sides, 6,059,959 TOTAL across all 109k.
        §10's "plausibly 10-20M state-action pairs" is 2-3x TOO HIGH. Calibrated against
        the literal `|choice|` lines old logs carry (21,521 battles), the |move|+|switch|
        heuristic undercounts by 13.1% (it misses turns spent asleep/frozen/recharging,
        which log `|cant|`), giving ~6.97M calibrated for the full corpus and ~3.06M for
        ≥2024. Against P4's 903,090 SH decisions that is ~3.4x, not the 11-22x §10 claims.
    (4) Winner extractability 108,794/109,147 = 99.68% matched to the `players` field;
        failures are ties and a handful of 2015 unmatched. Also measured: ~26% of battles
        end in a forfeit and ~7% in an inactivity timeout.
    (5) SET-POOL COVERAGE, and this is the finding that sets the cutoff. Species and move
        pools are near-static across the recent era (species-in-pool 100% from 2023,
        (species,move) legality 99.3-99.9%). What MOVES is the LEVEL table, and it moves
        in steps, mid-year — so the survey resolves 2023+ monthly. Level match jumps
        0.276 → 0.910 at 2024-04 and 0.918 → 0.999 at 2026-01. Battles from each boundary:
        ≥2024-04 = 44,391; ≥2026-01 = 6,105.
    **BAR VERDICT: the ≥50k recent-era bar FAILS at every cutoff that buys today's set
    distribution.** ≥2023 clears 49,693 (99.4% of the bar) but at only 28% level match —
    a different generator. ≥2024-04 is the honest "sets look like today's" subset at
    44,391. This is a real decision for the maintainer, not a formality: the bar as
    written says no, and the sizing (≈3x P4, not 10-20x) says the chapter is a smaller
    lever than §10 assumed. Recorded, NOT decided unilaterally.
    Also found, and it cuts the other way: **2015-2018 logs carry literal `|choice|` lines
    with BOTH players' submitted actions in the player's own encoding** (`|choice|move
    drillpeck|switch 3`). For those 21,521 battles the hidden-action problem (§10's
    `action = -1` rows, Track 1 check 8) essentially does not exist — but they are exactly
    the era with the worst set drift. Cheap labels and clean distribution are in different
    halves of the corpus.

  **Track 1 check (6) — Foul Play, answered from source (INFERRED, not measured;** clone
  25c976f05cbf2880eaa579afd6db1dcb2c3b57c6, 2026-07-19). gen1randombattle IS supported:
  format parsing is generic (`_GEN_REGEX gen([1-9]0?)` + "random" → RANDOM_BATTLE), Gen-1
  mechanics are explicitly implemented (fp/generations.py GEN1 registered at line 125;
  gen1 partial-trapping, stat-modification glitches, burn/paralysis nullify volatiles in
  fp/battle/protocol.py; gen1_pokedex_mods.json), and the randbats set source
  https://pkmn.github.io/randbats/data/full/gen1randombattle.json exists (HTTP 200,
  28,151 bytes). **Seconds-per-decision is a DIAL, not an emergent property**:
  `--search-time-ms` (default 100) feeds straight into `monte_carlo_tree_search(state,
  search_time_ms, threads)`, and random-battle mode searches parallelism×2 sampled battles
  (×4 shallow early), so stock wall clock is ~0.2 s/decision, scaling linearly with the
  flag. That reprices D5 hard: the locked protocol's ~81k decisions is ~4.5 h at stock
  settings, NOT the "hundreds of hours" §10 assumed from Wang's ~10 s/move MCTS. The real
  blocker is different — **poke-engine is compiled per generation** (`make poke_engine
  GEN=gen1`, `--no-default-features`), the pinned build is gen9/terastallization, and one
  install serves exactly one generation. Unmeasured and still open: Foul Play's STRENGTH
  at a 100 ms budget, which is what would make it a meaningful anchor.

  Process note: three background agents were used for the parallelizable measurement work
  and all three died on TLS/API errors mid-flight (harness watchdog, 600 s no-progress).
  The corpus one had written its results to disk first, so its numbers survived and were
  re-derived and re-verified here; Foul Play was redone inline. Not a repo problem.
