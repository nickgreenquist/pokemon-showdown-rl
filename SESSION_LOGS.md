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
