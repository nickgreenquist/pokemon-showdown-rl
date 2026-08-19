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

- 2026-08-05 — Arm A warm-start smoke RUN: handoff is sound; BC clones start at entropy 0.063

  runs/showdown_warmstart_smoke_s9, 200k steps / 48 updates, ~6 min, clean tree
  (git_dirty false, sha 9b031a8). All four pre-registered reads below, then the thing
  the smoke was actually worth running for.

  READ 4 (frozen-actor signature) — PASS, exactly. loss/approx_kl and loss/clip_frac are
  0.00000000 for updates 0-9 and nonzero from update 10 (0.0039 / 0.0214). The staged
  unfreeze does what it says at full scale.

  READ 1 (broken-handoff detector) — PASS. During warmup the actor cannot change, so the
  four evals inside the window measure the cloned policy itself: pooled 0.4875 (n=400,
  se 0.0250) against the clone's re-scored 0.4657 (n=1000), a +0.87 se gap. The
  BC-checkpoint -> PPO handoff does not break the policy.

  READ 3 (critic health before unfreeze) — PASS, and it OVER-provisions. loss/value
  0.446 -> 0.255 and loss/explained_variance -0.17 -> +0.42 across the warmup, but EV is
  already plateaued at ~0.38-0.42 by update 4. Ten warmup updates is roughly twice what
  this handoff needed; the chapter can use ~5 and should re-measure rather than inherit 10.

  READ 2 (no first-updates collapse) — PASS at the boundary, with a REAL transient after
  it. Banded (each rung is only n=100, se 0.05, so single rungs are not readable):
    frozen 10-40k     0.4875 (n=400)
    unfreeze 50-80k   0.4550 (n=400)   -0.033 vs frozen  (-0.92 se_diff)
    mid 90-130k       0.3820 (n=500)   -0.106            (-3.19 se_diff)
    late 140-200k     0.4757 (n=700)   -0.012            (-0.38 se_diff)
  So: no cliff at unfreeze — the first four post-unfreeze rungs are within noise — but a
  real ~0.10 sag opening ~10-20 updates LATER and fully recovered by 140k. Worth knowing
  before the chapter panics at one: the dip is not at the handoff, it is after it, and it
  comes back.

  **NOT pre-registered, and the most useful thing here: a BC-warm-started run starts at
  loss/entropy 0.063 and stays there (0.068 at 200k).** The P5b control from scratch runs
  1.69 -> 0.317 over 6M. The R0 entropy gate every arm carries is [0.2, 1.0], so a
  BC-warm-started run FAILS that gate from its first update, permanently — not because
  anything is wrong but because a cross-entropy clone of a deterministic bot is a peaked
  policy, and entropy_coef 0.01 cannot lift it. This has two consequences the corpus
  chapter must design for, and neither is in DESIGN.md: (1) the R0 entropy band does not
  transfer to the warm-started regime and needs its own value, decided before the first
  chapter run rather than waived after it; (2) the chapter's exploration story cannot be
  "PPO will re-explore" — at entropy 0.063 there is nothing to explore with, which is
  also the most likely reading of the mid-run sag (the policy is perturbed off the clone
  and has to grind back with almost no stochasticity to help it). A deliberate
  entropy_coef choice for warm starts is now a chapter prerequisite.

  Mechanism reads, recorded: loss/grad_clip_frac 0.669 warmup -> 0.745 post -> 0.938 at
  the end, i.e. this regime binds the 0.5 clip HARDER over time, the opposite of the
  from-scratch probe earlier today (1.00 -> 0.50 over the first 5 updates). grad_norm
  post-mean 0.725 against max_grad_norm 0.5. adv_std ~0.58 flat. time/steps_per_sec ~752
  solo, consistent with the ~734 baseline. eval/loss_faint_diff -1.87 -> -1.90: when this
  policy loses it is ~1.9 mons behind — the first recorded value of Arm B's secondary,
  though from a clone-like policy rather than the control recipe.

  Verdict: the warm-start machinery is GREEN and the human-BC chapter's day-one path is
  de-risked. Arm A itself stays retired (D3b). One new chapter prerequisite (the entropy
  decision) and one relaxed constant (warmup ~5, not 10).

- 2026-08-05 — D2c control re-eval DONE: P5b is 0.4308 ± 0.0052 at 3000 battles/seed

  Arm B's pre-registration requires the control re-evaluated in-repo at 3000 battles/seed
  before the comparison is read (D2c). Done now, ahead of the arm, so the control number
  is not entangled with the arm's run: 3 x 3000 battles, 88 s per seed, locked protocol
  (final rung ckpt_006000000.pt, deterministic, vs SimpleHeuristicsPlayer, ties as
  non-wins, seed_start 100).

    seed   old n=1000   new n=3000
    s0         0.4160       0.4280
    s1         0.4680       0.4320
    s2         0.4460       0.4323
    pooled  0.4433 (n=3000)   ->   0.4308 (n=9000), se 0.0091 -> 0.0052

  The shift is -0.0125 at se_diff 0.0105, i.e. -1.19 se: NOISE, not a regression, and the
  n=9000 figure is simply the better estimate. **Arm B's screen now reads against 0.4308,
  not 0.4433.** Worth noting how load-bearing D2c turned out to be: the baseline moved by
  1.4x the +0.009 futility gate purely from control sampling noise, so screening against
  the stale number could have flipped the decision on its own.

  **Showdown eval episodes are confirmed NOT reproducible, empirically.** The re-eval's
  first 1000 battles per seed do not reproduce the recorded run's per-episode returns for
  ANY seed — same checkpoint, same deterministic policy, same seed ladder. This is the
  env docstring's "episodes are server-rolled" property biting at the eval layer, and it
  makes the old and new samples INDEPENDENT rather than nested (which is why the
  comparison above uses the sum of both variances). DESIGN §8 had already reasoned to
  this conclusion and asked for the docstring fix rather than the machinery; that fix is
  now applied to rl/common/evaluation.py and scripts/eval_checkpoint.py, with the
  measurement recorded in it. Practical consequences: Showdown comparisons are UNPAIRED,
  precision is bought with battle count alone, and eval_checkpoint's skip-the-first-N
  logic is inert on Showdown (harmless — every pass draws fresh battles anyway).

  Tooling: scripts/eval_checkpoint.py now reports the ENV-supplied `eval/win_rate`
  instead of leaving every downstream analysis to count +1s by hand — which was the exact
  form the metric's spec review rejected, since it reads the reward a sign bug inverts.
  Both are emitted and they agree on all three seeds (0.4280/0.4320/0.4323), so the
  reward stream is confirmed un-inverted. The episode loop still runs ONCE: evaluate()'s
  arithmetic is factored into eval_metrics() so a caller needing raw per-episode data
  gets identical numbers without a second pass. Retires the CLAUDE.md landmine
  "eval_checkpoint.py returns raw returns only".

- 2026-08-06 — ARM B SCREENED OUT: delta -0.0004. The cancellation that made it safe made it inert.

  3 lanes x 6M, seeds 6/7/8, ~2.9 h 3-wide, all green, launched from a clean tree
  (git_dirty false). Finals per D2c: 3000 battles/seed, locked protocol, against the
  control RE-EVALUATED the same way earlier tonight.

    ARM  showdown_faint6m   0.4307 / 0.4237 / 0.4367   pooled 0.4303 (n=9000)
    CTRL showdown_r512_lra  0.4280 / 0.4320 / 0.4323   pooled 0.4308 (n=9000)
    DELTA -0.0004,  se_diff 0.0074 (binomial 0.0074 > seed-clustered 0.0040; DESIGN §5
    takes the larger),  z = -0.06

  **D2c futility screen: DO NOT ADVANCE to 12M** (needs >= +0.009). And this is not a
  can't-tell: the one-sided 90% upper bound on the true delta is **+0.0090, which does not
  reach the +0.025 credit line**. The screen was designed to be liberal precisely so it
  would not kill real levers, and this lever cleared none of it.

  R0 gates, all PASS: shaping correctness — `rollout/episode_return` stayed exactly
  {-1, 0, +1} across **639,409 episodes** in three independent runs, so the terminal
  cancellation held for the entire arm; late entropy 0.314-0.318 in [0.2, 1.0]; ties 1.57%
  <= 4%; steps/s 575-605 against the 553-600 3-wide baseline.

  FALSIFIER: does NOT fire. It required win-rate delta <= 0 (true, -0.0004) AND the
  loss-conditioned faint differential improving by > 0.5 mons; the actual change is
  **+0.017 mons** (arm -1.985 vs control -2.002). So there is no objective distortion to
  find. The agent did not learn to buy faints instead of wins — it did not learn anything
  different at all. Episode length 24.18 vs 24.22 (-0.04). `eval/loss_faint_lead_frac` is
  0.000 for BOTH arms: in not one losing battle out of ~5100 did either policy lead on
  faints, which says our losses are decisive rather than close, and is a more interesting
  fact about this agent than anything the arm was testing.

  **WHY THE NULL, and this is the part worth keeping.** The mechanism reads say the lever
  never changed the learning signal: late-window value loss +0.0013, approx_kl identical to
  four decimals (0.0008 both), clip_frac +0.0002, entropy +0.0017. Two independent reasons,
  both derivable BEFORE the run:

  1. **Terminal-cancelled shaping is potential-based, and PBS leaves the advantage function
     exactly invariant.** With r' = r + gamma*Phi(s') - Phi(s), the optimal shifted value is
     V' = V - Phi, so delta' = r' + gamma*V'(s') - V'(s) = r + gamma*V(s') - V(s) = delta.
     Every TD error is unchanged, so every GAE advantage is unchanged, so the policy
     gradient is unchanged. The safety property DESIGN §4 chose the cancellation FOR —
     policy invariance, Ng et al. — is the same property that guarantees it cannot move the
     optimum. The arm was therefore only ever testing the second-order effect: whether a
     denser reward reduces estimator variance under function approximation.
  2. **It cannot help the critic either, because the potential is already in the
     observation.** Phi = 0.1*(faints_opp - faints_self), and the encoder emits
     `vec[1] = faints_self/6` and `vec[2] = faints_opp/6` (rl/envs/showdown.py:199-200), so
     **Phi = 0.6*(obs[2] - obs[1]) exactly** — a linear function of two features the network
     already receives. Learning V and learning V - Phi are the same difficulty for this
     approximator, which is exactly what the flat value-loss comparison shows.

  **Generalizable design rule, recorded so this is not re-run in another costume: a
  potential-based shaping term whose potential is an (approximately) linear function of
  features the encoder already emits is predictably inert.** It changes no advantage and
  eases no regression. Checking that before launch costs one line of algebra and would have
  saved 2.9 h of compute here. Any future shaping proposal must state its potential and
  show it is NOT already representable from the observation.

  Corollary about ps-ppo, whose faint shaping this arm was modelled on: theirs has NO
  terminal cancellation, so it is NOT policy-invariant and does change their objective. If
  their shaping does anything, it does it by distorting the optimum — which is the
  trade-down failure mode DESIGN §4 identified and deliberately designed out. The honest
  fork is safe-and-inert versus effective-and-distorting; we picked safe, and got the null
  the theory predicts. Reopening this lever means arguing FOR the distortion, on evidence.

  Disposition: **Arm B is CLOSED, not re-tuned.** The pre-registration's amendment condition
  (README gains a measured sentence only if a PRIMARY credits) is not met — session-log
  entry only, which is this. Do NOT raise the coefficient: the coefficient is not why it did
  nothing. Arm C stays parked; its unparking condition was "iff Arm B credits", which is now
  settled as no.

- 2026-08-06 — Handoff absorbed: three items were NOT already recorded; stub restored

  Read HANDOFF.md against STATUS.md / SESSION_LOGS.md / DESIGN.md. Almost all of it was
  already in the record — Arm B's closure and the generalized shaping rule, Arm C's parking,
  the BC-warm-start entropy 0.063 prerequisite, the corpus parquet's pin, and the background-
  agent TLS deaths all exist in the 2026-08-05/06 entries and STATUS's watch list. Three gaps
  were real and are now closed:

  1. DESIGN §11 option (A) did not carry the poke-engine build cost, though the session log
     did: it compiles PER GENERATION (`make poke_engine GEN=gen1`, `--no-default-features`)
     and the stock wheel is gen9, so the feasibility note starts with a from-source build.
     §11 is written to be self-contained for reviewers, so it needed the clause.
  2. DESIGN §11 gained the paragraph the handoff flagged as unbuilt: the teacher dataset from
     (C) doubles as an **architecture screen** — same BC objective on our encoder, MLP-[512,512]
     vs transformer, compared on held-out teacher agreement, for zero RL budget. ps-ppo's own
     method; a read inside the chapter, not a separate arm.
  3. STATUS's decision list was missing "push or not" — `main` is 17 commits ahead of
     `origin/main`. Now decision 3. Track 1's block was tightened by two lines to stay under
     the 60-line cap.

  Deliberately NOT folded anywhere: the ephemeral Foul Play clone path under $CLAUDE_JOB_DIR
  (re-clone if gone) and "the Showdown server is up on :8000" — both are session facts, not
  repo state. Tree was clean going in; no runs live; nothing queued. The next move remains a
  maintainer decision (D8/D9, Track 1's bars, push), not code.

- 2026-08-06 — WHAT A vs-SH WIN RATE IS WORTH: SH is ~40% GXE in randbats; ladder eval DEFERRED

  Maintainer pushed back on the "build the ladder eval next" recommendation and asked the
  right question instead: what Elo does SH actually get, so we can map our own numbers onto
  the ladder without playing a single human. It is measured, and it was already sitting in
  `prior_work/grigsby2025_metamon.pdf` — our index had recorded only the worst row of it.

  **Metamon Table 2 + Figure 17 — PokeEnvHeuristic (= poke-env SimpleHeuristicsPlayer) vs
  humans on the public ladder:**

    format              W-L      raw WR   GXE (Fig 17 bar labels)
    Gen1OU              16-59    21.3%    21.8%
    Gen3OU              16-54    22.9%    26.7%
    Gen4OU              21-36    36.8%    31.6%
    Gen7RandomBattle    24-32    42.9%    39.7%
    Gen9RandomBattle    28-32    46.7%    41.2%

  Our index carried ONLY "Gen1OU 16W-59L (~0.21) — SH's weakest format". True, but it is an
  OU tier and it is the wrong anchor: **in random battles, where team-building is removed,
  SH is roughly twice the player it is in OU** — ~40% GXE, Glicko-1 ~1450-1500 (GXE labels
  exact; the Glicko band is read off the figure and must be quoted as approximate).

  **The conversion for our own numbers.** Ties are non-wins under the locked protocol, so
  SH-mirror parity is 0.489, not 0.500. Best RL (12M+LRA) = 0.4607; renormalizing the 1.57%
  ties out gives ~46.8% head-to-head = **~20 Elo BELOW SH**. So our best agent projects to
  ~38-40% GXE. Rule of thumb now recorded in three places: **a vs-SH win rate near 0.489
  means ~40% GXE, not "nearly solved."**

  **The randbats field, for scale:** SH 39.7/41.2% GXE; Huang & Lee 2019 (PPO self-play, NO
  search, Gen7RB) 1677 Glicko-1 / 72% GXE; ps-ppo (Gen9RB) 1725 +/- 25 / 76.7%; Wang 2024
  (PPO + test-time MCTS, Gen4RB) 1756 / 79.5%; Metamon SynRL-V2 (Gen1OU) 1761 +/- 35 / 79.9%;
  best humans 74-90%. **The floor of the published pure-policy field is 72% GXE and we are at
  ~40%.** That gap is not a shaping/LR/step-count gap — it is the size that BC-init
  (VGC-Bench: +25-30 pts at matched budget) and encoder work move.

  **DECISION (maintainer): ladder eval DEFERRED.** D7(a) stands — ladder Elo/GXE remains the
  ratified success metric — but its EXECUTION waits until an agent is clearly past SH. The
  result is now predictable from vs-SH, so it buys confirmation only, at the cost of hundreds
  of real-time battles on a human account; Metamon reports being accused of botting in chat
  at exactly this rating band. This retracts the recommendation made earlier tonight to build
  it first.

  **Also corrected: PS Elo is NOT Glicko-1.** ps-ppo's own screenshot reads Elo 2102 /
  Glicko-1 1725 for one agent, and Metamon calls PS Elo "intentionally noisy" and not
  comparable across game modes. Consequence: the corpus survey's ratings (median 1203, p90
  1415, zero above 1700) are PS **Elo** and cannot be read against any Glicko figure above.
  Quote GXE when comparing across sources.

  **Caveats, all the source's own, all carried into the index:** n is tiny (56 and 60 battles,
  ~+/-6.5pp); SH's low rating skews matchmaking toward weak opponents so raw W-L is an UPPER
  bound; Fig 17's Glicko "is possibly an overestimate" (slow convergence far below the mean);
  and **nobody has measured gen1randombattle** — every randbats row is gen4/7/9, every gen1
  row is OU. This is a cross-format extrapolation, not a measurement of our board.

  **Softens one claim made earlier tonight:** Metamon calls Foul Play "the strongest
  open-source engine today", and the #8 Gen1OU placement is a competition result under a fixed
  time budget, not a strength measurement. §11's ceiling argument rests on that placement; the
  (A) feasibility note's Foul-Play-vs-SH number therefore matters more, not less.

  Recorded in four places by design: `prior_work/README.md` (new tracked section at the top,
  where the citation rule already forces a read), `CLAUDE.md` landmines (one line, always
  loaded), `STATUS.md` (ladder-translation block under the results table), and here.

- 2026-08-06 — Foul-Play-vs-SH measurement PRE-REGISTERED and STAGED (approved); blocked on Rust

  Maintainer approved §11(A)'s teacher-strength measurement as the next direction. Built and
  staged, not run — the engine build is a prerequisite that needs a toolchain install.

  **No fork is needed, and that was worth checking rather than assuming.** Foul Play and
  poke-env's SimpleHeuristicsPlayer are both websocket CLIENTS of a Showdown server; they meet
  in the server we already run on :8000, and neither imports the other. Foul Play already ships
  the mode (`fp/config.py`): `--bot-mode challenge_user --user-to-challenge <name>
  --run-count N`, and randbats needs no team file (`team_dict = None` unless `--team-name`).

  **The one patch that IS needed is login.** `PSWebsocketClient.create` hardcodes `login_uri`
  to play.pokemonshowdown.com even for guest login, and posts for an assertion a
  `--no-security` server neither needs nor validates. poke-env short-circuits this outright
  (`ps_client.py`: `assertion = ""` when there is no password) — which is exactly why every
  training run in this repo connects fine — so the patch makes Foul Play do the same for
  localhost. Saved as `scripts/patches/foulplay_local_login.patch`, generated from the clone so
  it applies cleanly, and already applied to `../foul-play`.

  **The real gate is the engine, not the battling.** Foul Play pins `poke-engine==0.0.48` built
  `--features poke-engine/terastallization` = GEN 9. `gen1` IS a real feature flag (verified
  against poke-engine's `Cargo.toml`: `gen1`..`gen9`, `default = []`), so `make poke_engine
  GEN=gen1` is the command — a from-source Rust compile. **Rust is NOT installed on this
  machine** (`cargo`/`rustc` absent), so that install is step one and is the maintainer's.

  **Design point that reorders §11(A).** Getting this number does NOT require settling the
  mechanics-agreement question first. Foul Play plays on the real Showdown server, so the
  SERVER is the referee: any divergence between poke-engine's gen1 model and Showdown's shows
  up AS Foul Play playing worse, which the win rate already captures. The number therefore
  measures Foul-Play-as-deployed — exactly what expert iteration would distil. §11(A) splits
  into two independently useful measurements and the decision-relevant one is the cheap one;
  the agreement study is only worth paying for if the teacher survives this.

  **Asymmetric failure mode, and why it gets an explicit gate.** A wrong-generation or
  half-broken engine makes Foul Play play BADLY, biasing the primary read DOWN — the direction
  that wrongly KILLS option (C). So the pre-registration gates on build validity (smoke 5
  battles, read Foul Play's log for engine exceptions and fallback-to-random) before the 300,
  rather than treating a low number as evidence.

  **Pre-registered decision rule** (full text in the `scripts/foulplay_vs_sh.py` docstring):
  PRIMARY is Foul Play's win rate vs SH in gen1randombattle at stock budget
  (`--search-time-ms 100 --search-parallelism 1`), ties as non-wins, n=300 single lane
  (se ~0.026 at p~0.7, so the band edges sit ~4 se apart). **GO >= 0.70; MARGINAL 0.60-0.70
  (re-priced, smaller first dataset); NO < 0.60** — below which (C) does not proceed and D9(a),
  the corpus chapter on the >=2024-04 subset, becomes the main line by default. Bands are
  calibrated off the ladder translation recorded earlier tonight: SH ~40% GXE, the published
  pure-policy class ~76% GXE = ~270 Elo = ~0.82 head to head, and a clone lands BELOW its
  teacher (P4: 0.4657 against SH's 0.489 parity, ~0.023 short). A teacher under 0.60 distils
  into a student sitting roughly where our 0.4607 already is.

  Secondary reads, pre-registered so they are not fished for: measured s/decision (retires
  §11's INFERRED ~0.2), wall-clock per battle (re-prices §11(C)'s "~6 h at 8-way" for a
  P4-scale 903,090-decision dataset), tie rate, mean battle length. R0 gates: gen1 build
  verified; Foul Play's own W/L tally agrees with the SH seat's (two independent counters);
  n_finished == requested; SH accepts challenges from the Foul Play username only.

  Env rule, stated because it is the kind of thing this repo has already paid for: **Foul Play
  gets its OWN Python env.** It pulls poke-engine and its own pinned requirements; installing
  it into `pokemon-showdown-rl` would violate the exact-pins/no-ad-hoc-pip rule. Two envs, one
  server. The clone is a sibling at `../foul-play`, matching the ps-ppo precedent, and is
  recorded under "Local code checkouts" in `prior_work/README.md`.

  Suite 240 passed. Nothing has been run against a server yet; `results/` is gitignored.

- 2026-08-06 — FOUL PLAY vs SH MEASURED: 0.8467 (254-46, n=300). GO. And FP does not work in gen1.

  Maintainer was remote and lifted the >5min handover rule to unblock, so this was run in
  session end to end. Everything below is measured, not projected.

  **PRIMARY: Foul Play 254-46 vs SimpleHeuristicsPlayer in gen1randombattle, 0 ties.**

    win rate 0.8467, se 0.0208, 95% CI [0.806, 0.887]
    **7.05 se above the pre-registered 0.70 GO line** -> GO, not close to the boundary
    +297 Elo over SH

  For scale, on the same board: our best RL 0.4607, BC clone of SH 0.4657, SH-mirror parity
  0.489. The teacher is ~0.39 above our best agent. Converting via last night's ladder
  translation (SH ~40% GXE), +297 Elo puts Foul Play around **79% GXE** — the top of the
  published randbats field (Huang & Lee 72%, ps-ppo 76.7%, Wang 79.5%). That independently
  corroborates Metamon's "strongest open-source engine today" and, notably, matches the
  back-of-envelope written BEFORE the run (a ~76% GXE agent should beat SH ~0.82; measured
  0.847).

  R0 GATES, all PASS. (1) Engine built for gen1: the flag reached cargo verbatim
  (`--features poke-engine/gen1 --no-default-features`) and poke-engine's Cargo.toml has
  `default = []`, so with no defaults and only gen1 selected there is no path to a gen9 build;
  300 battles ran with 0 exceptions. NOTE a probe that did NOT work: `strings` on the compiled
  .so shows `terastallize`/`dynamax`/`steelbeam` even in the gen1 build, because move-name
  tables compile in regardless of the mechanics feature — that test discriminates nothing and
  is not evidence either way. (2) Two independent tallies agree EXACTLY: Foul Play's own
  `W: 254  L: 46` against the SH seat's 254/46. (3) 300/300 challenges resolved. (4) SH
  accepted from the Foul Play username only.

  SECONDARY READS, retiring inferred numbers:
    - **7.9 s/battle**, mean 21.97 turns. DESIGN §11 carried ~0.2 s/decision as INFERRED.
    - **Re-priced dataset generation:** a P4-scale 903,090-decision set is ~41,112 battles =
      **90.2 h single-lane, ~11.3 h at 8-way**. §11 projected "~50 h single-threaded or ~6 h
      at 8-way", so the real cost is ~1.8x the estimate. Still a weekend, not a blocker.
    - **Tie rate 0.0% over 300** (our own arms run 1.57% vs our policy). Mean length 21.97 vs
      our arms' 24.18/24.22 — Foul Play ends battles faster.

  **THE OTHER FINDING, which is arguably worth more than the number: "Foul Play supports
  gen1randombattle" was FALSE out of the box, and DESIGN §11 asserted it from source-reading.**
  Showdown has a gen-1-ONLY protocol path (`sim/pokemon.ts`: gen === 1 && !lockedMove && (frz
  || slp || partiallytrapped)) that replaces the entire move list with a single `Fight`
  placeholder. Foul Play models it nowhere and dies ~12 turns into the first battle, at TWO
  layers: `fight` is absent from moves.json so `add_move()` no-ops and the caller indexes
  `moves[-1]` on an empty list (IndexError); and once the move exists, poke-engine has no
  representable action, returns the choice `none`, and `format_decision` dies on
  `get_move("none").can_z`. **It fired 195 times across 300 battles** (~0.65/battle) — Rest,
  sleep moves, freeze, Wrap/Bind/Fire Spin. Not an edge case. Source-reading found that nothing
  REJECTS the format and mistook that for support; this is the same class of error
  prior_work/README exists to catch, except this time the unverified claim was ours.

  Three patches, in `scripts/patches/foulplay_gen1_local.patch`, applied to `../foul-play`:
  local `--no-security` login (poke-env already skips auth outright — `assertion = ""`), the
  synthetic `fight` move mirroring Foul Play's own `recharge` handling, and a forced-choice
  short-circuit submitting the placeholder unsearched. The third is faithful, not inventive:
  that turn has exactly ONE legal action, so it decides nothing Foul Play would otherwise
  choose. **Every number here is "Foul Play + our patches" and must be quoted that way.**

  CAVEATS ON THE NUMBER, stated so it is not over-read:
    - vs-SH is a PROJECTION, not a ranking (VGC-Bench Appendix C: cyclic payoff matrices).
      0.847 vs SH does not guarantee 0.847 against our RL policy or against humans.
    - DESIGN §3/D7 already warn that vs-SH past parity measures SH-EXPLOITATION. 0.847 is far
      past parity, so some of this is exploitation rather than absolute strength. For expert
      iteration what matters is narrower and IS established: its demonstrations are much better
      than SH's, which is the ceiling that capped P4.
    - Distilling a search bot loses the search. The student inherits Foul Play's move choices,
      not its ability to compute them, so the realistic ceiling is "policy that predicts Foul
      Play", below Foul Play itself. That is the standard expert-iteration bet, not a defect.
    - Nothing here touches the public ladder; the 2026-08-06 deferral stands.

  DISPOSITION: **§11(A)'s gate is passed and D8(c)/D9(c) are now evidence-backed.** The
  mechanics-agreement half of (A) was NOT run and was not needed — Foul Play plays on the real
  Showdown server, so the server is the referee and any engine/Showdown divergence shows up as
  Foul Play playing worse, which the win rate already prices in. Ratification of §11 is the
  maintainer's call and is now the only thing between here and generating the dataset.

- 2026-08-06 — Demonstration pipeline BUILT and validated; my own placeholder patch was WRONG

  Maintainer lifted the >5min rule (remote, full day available), so this was built and run in
  session. Three reviewers were spawned afterwards; their findings are a separate entry.

  **What exists now.** Foul Play instrumentation (`scripts/patches/foulplay_gen1_local.patch`,
  5 files, applied to `../foul-play`): local no-security login; the synthetic `fight` move;
  correct gen1 placeholder handling; a persistent ProcessPoolExecutor; pre-truncation policy
  capture; a switch guard on `check_speed_ranges`; and a new `fp/tape.py` event-tape writer
  gated on `FP_TAPE_DIR` so stock behaviour is unchanged when off. Plus
  `scripts/tape_to_dataset.py`, which replays tapes OFFLINE through poke-env's own parser.

  **Design decision: store TAPES, not embedded observations.** P4's dataset was 2.1 GB of
  611-dim rows that any OBS_DIM change turns into 2.1 GB of nothing, and this project intends
  to change the encoder. The durable artefact is the raw protocol stream plus the teacher's
  decision, so an encoder change costs a re-embed (minutes) not a re-collection (tens of
  hours). This is NOT §10's replay-parser problem: Foul Play owns the seat, so the tape
  carries that seat's own `|request|` JSONs -- no hidden actions, no belief reconstruction.

  **Soft targets, because the teacher is STOCHASTIC.** `select_move_from_mcts_results` builds
  a visit-share policy marginalised over determinizations, THEN truncates to moves within 75%
  of the best and `random.choices` among them. An argmax label imitates the wrong object. A
  real captured decision: `switch abra` 0.618, `sludge` 0.064, `switch venusaur` 0.063, ...
  over 9 actions, plus per-action values. The top choice at 0.62 is not a delta function, so
  argmax discards real signal. This also attacks the entropy-0.063 landmine at its root:
  that collapse is what one-hot BC on a near-deterministic target PRODUCES.

  **MY PLACEHOLDER PATCH WAS WRONG, and the 300-battle measurement was taken with it.**
  I had asserted the gen1 `Fight` turn was a forced choice with one legal action. Measured
  against a real captured request, it is not: `trapped` is False and the mask holds the
  placeholder PLUS every legal switch (verified: 3 switches + placeholder = 4 actions;
  action 1 -> `/choose switch Clefable`, 6 -> `/choose move fight`). Showdown's own source
  says so -- "actions that don't hard lock out of switching". Switching a sleeping mon out is
  ordinary gen1 play.

  **How wrong, measured:** across 50 battles the placeholder fires 0.78x/battle, and on
  **17 of 39 such turns (44%) the search elects to SWITCH OUT.** The old patch forced "stay
  in" on all of them. Two consequences:
    1. **0.8467 is a LOWER BOUND** -- Foul Play was handicapped on ~0.34 decisions/battle.
    2. Every such dataset row would have carried a systematically biased "never switch when
       asleep" label. Generating 41k battles first would have baked that in.
  Fix: restore the mon's real moves from `side.pokemon[active].moves` (the request still
  carries them, the placeholder only blanks `active[0].moves`), let the search weigh staying
  against switching, and map a stay-in result back to `/choose move 1`.

  **A latent Foul Play bug, found by it killing a run at battle 11 of 50.**
  `check_speed_ranges` (`fp/battle/inference.py:197`) indexes `all_move_json` with
  `battle.user.last_selected_move.move`, which can be the raw string "switch <species>" ->
  `KeyError: 'switchseaking'`. The sibling guard already exists further down the same file;
  it is simply missing here. Guarded. Speed inference from a turn the bot spent switching
  carries no information anyway.

  **Also caught by piloting small first:** a TIE in the 5-battle test, which my gate report
  was miscounting as a missing outcome. Ties are outcomes -- Foul Play scores them as losses,
  the locked protocol counts them as non-wins.

  **GATES, 50 battles / 1,273 decisions, after the fixes:**
    G1 reconstruction  50/50 battles terminal          100%
    G2 label legality  1273/1273 rows kept             100%   (0 unmapped, 0 outside mask)
    G3 legal-set SIZE  1273/1273                       100%   (cardinality only; G2 is identity)
    G4 outcome present 50/50 (1 tie)                   100%
  The gates earned their place: on the pre-fix run G2 flagged exactly 3 unmapped labels and
  they were exactly the 3 placeholder rows -- the pipeline caught my bad assumption on its
  own, before any bulk generation.

  **Throughput re-priced by the executor hoist: 7.9 -> 6.03 s/battle (-24%).** A P4-scale
  903,090-decision set is ~41,112 battles = **68.9 h single-lane, ~8.6 h at 8-way** (was
  90.2/11.3). Pilot win rate 0.82 at n=50 (se 0.054), consistent with the 0.8467 primary.

  NOT yet done: the bulk tranche, the BC fit, the learning curve, the encoder screen.

- 2026-08-06 — THREE REVIEWS: real defects found. Corrections to numbers, claims and gates.

  Three Opus reviewers (patches / pipeline / adversarial). Two reached the same pipeline
  defects independently, which is why I believe them. This entry SUPERSEDES the earlier
  2026-08-06 entries wherever they conflict.

  **NUMBERS I GOT WRONG, now corrected:**

  1. **"7.05 se above the 0.70 GO line" is WRONG; it is 5.54 se.** Distance from a threshold
     uses se under H0 -- sqrt(0.7*0.3/300) = 0.0265 -- not se at p-hat (0.0208). My own
     pre-registration used the right one ("se = 0.026 at p~0.7") and I then published the
     wrong one. Margin overstated by 27%. **Verdict unchanged: GO.**
  2. **The dataset arithmetic conflated TURNS with DECISIONS.** I divided 903,090 by
     `mean_turns` 21.97. Decisions exceed turns (forced switches after a faint issue a
     request without incrementing the turn). MEASURED from the pilot tape: **25.46
     decisions/battle**. So a P4-scale set is **35,471 battles, not 41,112**.
  3. **Re-priced with the persistent pool: 6.03 s/battle -> 59.4 h single-lane, ~7.4 h at
     8-way** (I had published 90.2/11.3). Note the 8-way figure assumes linear scaling and
     will not hold -- the repo has already measured collection lanes losing ~20% at 3-wide.
  4. **s/decision, the §11(A) deliverable I claimed to have retired without ever stating:
     0.237 s/decision measured**, against DESIGN's INFERRED ~0.2. The inference was good.

  **CLAIMS I OVERSTATED:**

  - **"0.8467 is a lower bound" is NOT established.** The lower-bound argument needs v1 to
    have only *restricted* options; it did more than that -- v1 returned before setting
    `last_selected_move`, so Foul Play's record of its own last move went stale for the whole
    duration of every sleep, feeding its opponent-speed inference a lie ~195 times over 300
    battles. That is an uncontrolled perturbation of unknown sign, not a handicap with a
    monotonicity guarantee. Honest statement: **a variant of Foul Play -- not stock, and not
    the bot now generating our data -- scored 0.8467.** First read on the corrected bot:
    **0.875 (35-5, n=40, se 0.052)**, directionally consistent with v1 having handicapped it
    but nowhere near conclusive. A full 300-battle re-measure is owed before any bulk run.
  - **"independently corroborates Metamon's 'strongest open-source engine'"** -- Metamon
    states that as an explicit judgement call ("based on results in old forum posts... and our
    knowledge of method details"), not a measurement. Calling our extrapolation independent
    corroboration of an opinion is the exact error prior_work/README exists to catch.
  - **"+297 Elo, ~79% GXE, top of the published field"** rests on three unmeasured bridges:
    transitivity from ONE opponent (which this project has already BANNED for its own agent
    via the cyclic-payoff caveat), cross-format (anchor is gen7/gen9 randbats; ours is gen1),
    and cross-population (humans on a ladder vs a scripted bot on localhost). The caveats were
    in the session log but STATUS.md carried the bare number, and STATUS is the only mandatory
    read. Caveated there now.
  - **A new watch item nobody had connected:** STATUS already records "poke-env 0.15.0: SH's
    setup branch is dead (upstream, unfiled)". If that bug postdates the poke-env Metamon
    laddered, **our SH is weaker than the ~40%-GXE anchor** and every vs-SH number here is
    inflated relative to it. Cheap to check; it moves the headline.

  **DEFECTS IN MY OWN FIX, found by measurement not argument:**

  - **Restoring all four moves split "stay in" into four duplicate actions.** MCTS visit
    share IS the policy, so measured on a neutral asleep position the aggregate stay-in share
    went **23% -> 66%**, and the 75%-of-best truncation then left a candidate set of moves
    only -- reproducing the very "never switch out of sleep" bias the patch existed to fix.
    Fixed: restore ONE representative move. poke-engine prices all four identically under
    slp/frz (0.244 each vs 0.484 healthy), so one action is the truer model. After the fix,
    placeholder turns fell 0.78 -> 0.10-0.25/battle, because the bot now ESCAPES those states
    instead of sitting in them.
  - **poke-engine models `partiallytrapped` with MODERN semantics** -- it deletes the switch
    options and lets the trapped mon attack at full power. Gen 1 does neither. Not fixable
    from our side, so `trap_kind` is now taped and `--drop-trap` excludes those rows.
  - **Sleep and freeze ARE handled correctly** -- status travels independently of the move
    list. My stated worry that the search would think the mon could freely act does not
    materialise there.
  - **`requirements.txt` still pinned the gen9 build.** A gen9 engine runs gen1 battles
    without ever crashing -- it just makes a far worse teacher, silently. Now pinned to gen1.
  - `BrokenProcessPool` was permanent with the persistent pool (stock self-healed per
    decision); now rebuilds and retries. Plus: fallback branch mutated the discarded deepcopy,
    `password is None` -> `not password`, and a vestigial `if True:`.
  - **A positive control I had failed to find:** the installed `.so` contains
    `src/gen1/state.rs` and "Cannot Boost spd in gen1. spa is used for spc". That is
    artefact-level proof of the gen1 build, which my retracted `strings` probe was not.

  **PIPELINE GATES REBUILT.** The old ones gave false assurance: G1 and G4 were literally the
  same measurement (`battle.finished` is set by the same two lines that set the winner); G2
  checked legality, NOT the round-trip identity its docstring claimed and which
  `rl/collect.py` actually performs; G5 counted `forced`, which the corrected patch almost
  never emits, so it would have false-FAILed forever; a FAIL printed and then wrote the npz
  and exited 0. Rewritten with six gates that gate (non-zero exit, nothing written), plus:
    - **G3 rqid alignment** -- the decision was taped against the request the reconstruction
      stands on. This converts the file's central premise into a measurement and is the single
      highest-value check; both reviewers named it independently.
    - **G2 real round-trip identity**, mirroring rl/collect.py.
    - **G4** now compares poke-env's `battle.won` against the taped winner -- catches a
      username/role mix-up, which is otherwise silent.
    - per-FILE username inference (a directory-wide guess would hand 7 of 8 lanes the wrong
      seat at the planned 8-way scale), streaming per tape file with per-battle exception
      isolation (the old version materialised the whole corpus and would not have run at
      target scale), counters for dropped policy mass and per-branch skips, and `forceSwitch`
      list-indexing / `maybeTrapped` fixes in the legal-set cross-check.

  **GATES ON THE CORRECTED 40-BATTLE TAPE: ALL PASS.** 40/40 terminal; 1015/1015 labels
  round-trip; 1015/1015 rqid aligned; 40/40 outcomes agree; 0 protocol errors; 1015/1015
  legal-set cardinality; no dropped policy mass. Placeholder 0.25/battle, trap_kind recorded.

  **STILL OPEN, deliberately:** no obs-fidelity gate (tape a battle played by our own
  RecordingPlayer and assert the replayed `embed_battle` equals the live one elementwise --
  the obs is the product and nothing yet checks it); the gen9-vs-gen1 A/B that would turn the
  engine gate into a measurement; tape provenance headers; action-slot aliasing on placeholder
  turns (action 6 resolves to the placeholder while obs move-slot 0 still describes the real
  move -- pre-existing, affects prior runs too); and `train_bc.py` reads neither `policy` nor
  `placeholder`, so soft targets change nothing until it does.

- 2026-08-06 — All four open checks CLOSED. Obs fidelity PASS; engine A/B measured; SH anchor OK.

  Follow-through on the reviewers' "you are assuming, not measuring" list. All four resolved.

  **1. OBS FIDELITY -- PASS, and it is the check that was missing.** The reconstructor gated
  labels, rqids and termination but never the OBSERVATION, which is the product;
  `apply_message` is a hand-rolled mirror of poke-env's dispatch, so any divergence yields
  wrong obs while every gate still passes. `scripts/obs_fidelity_check.py` plays real battles
  with our own `RecordingPlayer`, tapes the same seat's frames at poke-env's own entry point
  (`ps_client._handle_message`), replays offline through the IDENTICAL code path, and compares
  elementwise. **189 decisions / 8 battles: 0 obs mismatch, 0 mask mismatch, 0 key mismatch**,
  bitwise on float32 (np.array_equal, not allclose). Three of my own bugs surfaced building it:
  `battle.rqid` is a Foul Play attribute poke-env does not have; `opponent_player()` builds a
  NON-listening player that cannot battle over a server; and a stray `scripts/__init__.py` I
  had created would have changed pytest collection (removed).

  **2. ENGINE BUILD -- a real positive control, and the A/B run in both directions.** The
  compiled .so's MODULE PATHS discriminate the build; move-name tables do NOT, which is why
  the earlier `strings` probe was correctly retracted -- but for an incomplete reason: I had
  grepped move names, and module paths were available the whole time.
      gen1 build : 7x `src/gen1/`, 0x `src/genx/`, "used for spc" present
      gen9 build : 0x `src/gen1/`, 20+x `src/genx/`, no gen1 string
  **A/B: with the gen9 engine deliberately installed, Foul Play went 2-5 over 7 battles and
  then DIED** -- 6 exceptions, terminating in `pyo3_runtime.PanicException` (not even
  picklable back across the process pool) -- against ~0.85 for gen1. This CORRECTS a
  reviewer's assumption that a wrong-gen engine "never crashes, just makes a worse teacher
  silently": measured, it fails loudly. gen1 build restored and re-verified afterwards.

  **3. IS OUR SH WEAKER THAN METAMON'S ANCHOR? No.** The setup branch
  (`baselines.py`) compares `move.target == "self"` -- a STRING -- against a `Target` ENUM, so
  it is always False and **SimpleHeuristicsPlayer never uses a setup move, in any generation**
  (Swords Dance, Amnesia, Barrier, Acid Armor, Agility all qualify on every other condition
  and die there; all appear in gen1 randbats sets). But the `Target` enum landed 2024-04-11
  (poke-env 0.8.1) and `baselines.py` was never updated -- the bug is still at upstream HEAD.
  That is ~8 months BEFORE Metamon's Dec 2024-Mar 2025 window, so their SH almost certainly
  shares it and our SH is comparable to the ~40% GXE anchor rather than weaker. Residual
  caveat: Metamon ships a custom poke-env fork, so a local fix cannot be excluded.

  **4. THE CORRECTED PATCH DOES NOT DETECTABLY CHANGE THE WIN RATE -- and I over-read the
  first sample.** Earlier tonight I called a 0.875 (n=40) read "directionally consistent with
  v1 having handicapped it". Pooling properly:
      v1                 254-46  0.8467  se 0.0208
      corrected (pooled)  82-18  0.8200  se 0.0384   (40 + 60 battles)
      difference -0.0267, se_diff 0.0437, **z = -0.61 -> INDISTINGUISHABLE**
  So 0.875 was noise and I should not have read a direction into it. The corrected bot still
  clears the bar on its own: **2.62 se above the 0.70 GO line at n=100**.
  **The patch mattered for LABEL QUALITY, not for the score** -- v1 forbade switching on
  placeholder turns, and the search elects to switch on a large share of them, so v1 would
  have written a systematically wrong "never switch when asleep" label into the corpus. That
  was always the reason to fix it; the win rate was never the point.

  **GATES on the 60-battle confirmation tape (restored gen1 build): ALL PASS.** 60/60
  terminal; 1493/1493 labels round-trip; 1493/1493 rqid aligned; 60/60 outcomes agree; 0
  protocol errors; 1493/1493 legal-set cardinality; no dropped policy mass. Placeholder
  0.38/battle. Suite 240 passed.

  **STILL OPEN, stated so it does not look finished:** `scripts/train_bc.py` reads neither
  `policy` nor `placeholder`, so soft targets and trap flags change nothing until it does; and
  the action-slot aliasing on placeholder turns (action 6 resolves to the placeholder while
  the obs move-slot 0 still describes a real move) is real, PRE-EXISTING, affects prior RL/BC
  runs too, and needs a decision rather than a note.

- 2026-08-06 — THREE PATH REVIEWS. The obs-fidelity proof was ~half a proof. Encoder is the wall.

  Three Opus reviewers on "where do we stand, best next path". They converge, and two findings
  overturn the plan I was about to recommend. Everything below I verified myself.

  **THE BIGGEST FINDING WAS ALREADY ON DISK AND NOBODY PLOTTED IT.** `runs/bc_p4_*/bc_metrics.json`:
      202,584 decisions -> 0.8595 held-out agreement with SH
      405,914 decisions -> 0.8814 / 0.8808 / 0.8857
      812,848 decisions -> 0.9017 / 0.8987 / 0.9047
  **+2.1 points per doubling, log-linear, NO saturation.** Our 611-dim encoder into MLP[512,512]
  cannot exceed ~90% agreement with a DETERMINISTIC rule-based bot on 813k examples. That is
  the P4 encoder-ceiling diagnostic returning its informative verdict, and the project (me
  included) had been reading it as "the clone reproduces SH". Extrapolated, 0.95 needs ~4M
  decisions ~= 157k Foul Play battles ~= 263 h. **That road is closed.** Foul Play is a far
  harder function than SH, so more tapes buy variance reduction against a bias floor.

  **WHY: we delete the teacher's principal input.** `rl/envs/showdown.py:219` iterates
  `list(theirs.moves.values())[:4]` -- poke-env's REVEALED-moves-only dict. Foul Play does the
  opposite: it samples full opponent sets from the randbats pool weighted by consistency, and
  fills unrevealed slots. Verified in the vendored pool (`showdown/data/random-battles/gen1/
  data.json`): 146 species, ~36-42 fully determined the instant the species is revealed, 91
  with 3-of-4 certain. **The fix costs ZERO OBS_DIM** -- `_fill_move` slot 0 is currently
  `vec[o] = 1.0`, a binary "slot known" flag, and can carry P(move present) instead.

  **MY OBS-FIDELITY PROOF WAS ~55% OF A PROOF, and the reason is self-inflicted.** I ran it
  SH-expert vs SH-opponent -- after establishing THE SAME DAY that SH never uses a setup move
  (dead `Target` comparison). That run was structurally incapable of emitting `|-boost|`.
  Measured: 13 protocol tags occur in the Foul Play corpus and NEVER in that fidelity sample --
  `-boost` x67, `-curestatus` x28, `-immune` x14, `-fail` x10, `-start` x8, `-activate` x8,
  `-end` x6 -- i.e. exactly the frames driving `_fill_active`'s boosts/volatiles and
  `_fill_mon`'s status. ~32 of 611 dims were validated only in their default state, and zero
  of 221 requests were gen1 placeholders (23 of 1761 in the real corpus).
  **REDONE with a coverage gate** (`--require-coverage`, random-vs-random so setup moves fire):
  **1,967 decisions, 0 obs / 0 mask / 0 key mismatches, and all 7 fragile tags exercised**
  (-boost x149, -fail x133, -curestatus x46, -immune x37, -start x13, -activate x3, -end x1).
  The original claim was not wrong, it was under-evidenced; it is now evidenced.

  **OTHER VERIFIED DEFECTS IN MY OWN PIPELINE, all fixed this session:**
  - "non-zero exit, nothing written" was FALSE -- shards were written inside the per-file loop
    BEFORE `report()` ran, so a failing corpus left .npz files indistinguishable from good
    ones. Writes now happen only after a PASS verdict.
  - **The soft policy was UNGATED.** `policy_missing` / `policy_empty` / `policy_mass_dropped`
    / `legal_size_mismatch` were printed and not in the fail list. So if a patch revision
    stopped passing a policy, every row would get a zero vector, all six gates would PASS, and
    the entire premise of the tape design would be silently gone. They now gate.
  - **`train_bc.py` could not have loaded this corpus at all**: it reads `data["expert"]`,
    which `tape_to_dataset` never wrote (0 occurrences). Added. It also loads exactly ONE npz
    while we write one shard per tape file, and `battle_ids` restarted at 0 per file, so any
    merge would split the holdout on a fictitious battle count -- ids are now globally unique.
    The shard-merging loader is still owed.
  - **`--drop-trap` is dead code.** trap_kind across every tape on disk: {slp 22, frz 11,
    **trap 0**}. It has never excluded a row, and v1's 300-battle run logged Wrap/Bind among
    the placeholder triggers -- so either the rate is genuinely zero (implausible) or
    `"partiallytrapped" in active.volatile_statuses` is the wrong key. Untested mitigation for
    the one modelling defect we know about. NOT fixed; needs a positive test.

  **CORRECTIONS TO CLAIMS I MADE EARLIER TODAY:**
  - "argmax discards real signal" was overstated ~4x. The teacher samples from the 75%-TRUNCATED
    set, so the sampled choice differs from the pre-truncation argmax on only **10.3%** of
    decisions, and a Bayes-optimal predictor of the sampled label tops out at **0.8935
    agreement**. Soft targets are still right -- for the entropy landmine, which is the stronger
    argument -- but 0.894 is the ceiling any agreement read must be scored against, and it
    should be pre-registered before the first fit.
  - **The GO bands rest on an inapplicable prior.** They used P4's "a clone lands ~0.023 below
    its teacher". That 95% transfer came from cloning SH, whose policy is a function of exactly
    the poke-env battle object our encoder reads -- recoverable by construction. Foul Play's is
    not. Reusing the ratio is a category error.
  - **Teacher entropy MEASURED** (1,493 decisions): mean **1.092 nats**, median 1.179, top-1
    prob 0.603, mean 7.08 legal actions. So the policy is genuinely soft -- and it sits ABOVE
    the [0.2, 1.0] R0 band, meaning a well-fit student fails that gate from the OTHER side.
    The band must be re-derived from this number, not inherited.
  - The per-action `values` are taped for 1493/1493 decisions and `tape_to_dataset` reads them
    **zero** times -- a free critic warm-start target thrown away, directly relevant to the
    critic-warmup problem (5 updates of frozen-actor noise from a random critic).
  - An open item was lost to renumbering: I listed FIVE open items, then wrote "all FOUR
    closed" and substituted the SH anchor. **Tape provenance headers were dropped** and are
    still missing -- nothing in a tape records engine build, patch revision, search budget or
    poke-env version, across 8 lanes and tens of hours.

  **THE STRONGEST OBJECTION TO THE WHOLE CHAPTER, and it is not answered:** nothing in this
  repo shows RL from a BC warm start ever improving on the BC checkpoint it started from. The
  SH clone scored 0.4657; RL from that region landed 0.4607. The clone was the CEILING, not
  the floor. Foul Play raises the ceiling but the play is identical in shape. Separately, the
  student is missing INFORMATION, not just search: AlphaZero-style expert iteration puts
  student and teacher on the same information set differing only in compute, whereas here the
  ceiling is bounded by I(our obs ; teacher's action), which nobody has estimated.

  **DISPOSITION: do NOT launch bulk generation.** The next move is the encoder information fix
  (zero OBS_DIM) plus a ~500-2,000 battle tranche read against the 0.894 ceiling, with
  agreement conditioned on opponent-reveal fraction -- that last read directly estimates the
  information bound and is the chapter's falsifier. Also owed: the n=300 re-measure on the
  shipped bot, and FP vs two NON-SH opponents (our best RL checkpoint and the BC clone), both
  of which already exist and have never been played.

- 2026-08-06 — ENCODER: the opponent set prior, at ZERO OBS_DIM. The largest missing input.

  Acting on the three path reviews. This is the fix for the finding that reframed the chapter:
  our encoder showed the opponent's moves only once REVEALED, while the teacher we intend to
  distil conditions on the full randbats set distribution. BC against such a teacher regresses
  E[action | our obs] with the teacher's principal input deleted -- an IRREDUCIBLE bias that no
  amount of extra demonstration data reduces.

  **`rl/envs/randbats_prior.py` (new).** Marginal P(move in set | moves revealed so far), per
  species. NOT a heuristic: `_sample_set` reproduces Showdown's own gen1 `randomSet` move
  selection (`data/random-battles/gen1/teams.ts`) step for step -- comboMoves all-or-none on a
  50% coin flip; exactly ONE exclusiveMove, added BEFORE the essentials so a three-move combo
  can still roll one; essentials in order to the 4-move cap; remainder sampleNoReplace.
  Conditioning is rejection over 4,000 sampled sets per species, which is precisely Foul Play's
  determinization logic. Deterministic (fixed seed) so the encoder stays pure and offline
  replay stays bitwise reproducible. The set file is vendored to `rl/envs/data/` (24,970 bytes,
  sha256 85fc2743...) because `showdown/` is gitignored and re-clonable;
  `verify_against_showdown()` re-checks it, and drift matters -- Foul Play fetches sets at
  runtime from pkmn.github.io, so a mismatch would have the teacher searching movesets we do
  not encode, silently.

  **The change costs ZERO dimensions.** `_fill_move`'s slot 0 was a binary "slot known" flag;
  it now carries the probability (1.0 for our own moves and for revealed opponent moves).
  Opponent move blocks carry NO action -- the encoder docstring says they sit in reveal order --
  so unlike our own blocks they are free to be re-filled: revealed moves first, then the most
  likely unrevealed candidates. **OBS_DIM stays 611, so no checkpoint is invalidated.**

  **Also landed, same commit, also zero-dim: the action-slot ALIASING fix.** On a gen1
  placeholder turn (asleep/frozen/partially trapped) poke-env re-bases move actions onto
  `available_moves`, so slot 0 stops meaning "the mon's first move". We were filling the blocks
  with the four REAL moves and teaching a contradictory input->label mapping on ~1.5% of
  decisions. Now zeroed; the SLP/FRZ/PARTIALLY_TRAPPED bits already in `_fill_mon`/`_fill_active`
  keep the state fully described. Covers struggle and recharge by the same rule.

  **MEASURED, on the 1,493-decision corpus:**
    opponent move slots populated       3.99 / 4   (was: revealed only)
    of which CERTAIN (p >= 0.999)       3.16 / 4
    decisions with the opponent's FULL moveset known   30.7%
    decisions with NO opponent move info                0.0%   (was: every unrevealed slot)
  Sanity: tauros (one possible set) comes back all-certain; alakazam gives psychic/recover/
  thunderwave at 1.0 and splits the 4th slot 0.398/0.398/0.204; gyarados 1.0/0.673/0.668/0.666.

  **Regressions:** suite 241 passed (240 + a new placeholder-aliasing test). The obs-fidelity
  check re-run against the NEW encoder still passes bitwise -- 1,154 decisions, 0 obs / 0 mask
  / 0 key mismatches, all 7 fragile tags exercised -- so the prior did not break replay
  determinism, which was the risk of putting sampling anywhere near the encoder.
  `tests/test_showdown_env.py::test_move_block_features` was re-pinned: it asserted
  "unrevealed => all zeros", which is exactly the contract this change replaces.

  NOT yet done: the BC tranche and the agreement-vs-reveal-fraction read that estimates the
  information bound; `train_bc.py` still needs soft targets, the shard-merging loader and the
  teacher-value critic target; `--drop-trap` still has no positive test.

- 2026-08-06 — TRANCHE RUN + BC CURVE. The set prior does NOT help agreement. Negative result.

  1,200 battles collected (3 lanes x 400), reconstructed, and fitted. Everything below is
  measured. **The headline is a negative result on the encoder change I made earlier today.**

  **COLLECTION.** 3 lanes, distinct usernames, 0 errors, 1,200/1,200 battles.
    lane1 327-72 (0.8175)  lane2 338-58 (0.8450)  lane3 335-64 (0.8375)
    **POOLED 1000-194, 6 ties, n=1200 -> 0.8333, se 0.0108, 95% CI [0.812, 0.854]**
  This DISCHARGES the owed re-measure of the shipped (corrected-patch) bot, at 4x the
  pre-registered n: **10.08 se above the 0.70 GO line**, and vs v1's 0.8467 (n=300) the
  difference is -0.0133, z=-0.57 -> still indistinguishable. The patch changed labels, not
  strength, exactly as the n=100 read said.

  **THROUGHPUT AT 3-WIDE, MEASURED (nobody had run more than one lane).** 5.67-5.91 s/battle
  per lane vs 6.03 solo -- i.e. **3.02x aggregate speedup, essentially LINEAR**, unlike our own
  collection which loses ~20%/lane at 3-wide. Foul Play's search sits in its own process pool,
  so lanes barely contend. A P4-scale 35,471-battle set is **19.7 h at 3-wide** (was quoted 59 h
  solo / 7.4 h at a never-tested 8-wide). Tapes ~96 KB/battle, 115 MB for 1,200.

  **GATES AT SCALE: ALL PASS.** 1200/1200 terminal; **29,844/29,844 labels round-tripped**;
  29,844/29,844 rqid aligned; 1200/1200 outcomes agree; 0 protocol errors; 0 dropped policy
  mass; 0 missing teacher values. Placeholder 0.43/battle.

  **BC LEARNING CURVE (soft targets, by-battle rungs, best held-out free-agreement):**
      3,750 rows -> 0.3432
      7,500      -> 0.3510   (+0.008)
     15,000      -> 0.3983   (+0.047)
     30,000      -> 0.4215   (+0.023)
  **Still climbing at 30k**, ~+2.6 pts/doubling over the last two doublings, against a Bayes
  ceiling of ~0.894 for predicting this stochastic teacher's SAMPLED action. So on this read
  the branch is "more data helps", not "the encoder is the wall".

  **THE ABLATION, and it falsifies the hypothesis I acted on.** The tape design exists exactly
  so this costs a re-embed rather than a re-collection, so I re-embedded the SAME 1,200 battles
  with `POKEMON_RL_NO_SET_PRIOR=1` (revealed opponent moves only, the pre-today behaviour):
      n=15,000   with prior 0.3983   without 0.3863   delta +0.0120  (z +0.65)
      n=30,000   with prior 0.4215   without 0.4189   delta +0.0027  (z +0.21)
  **No measurable benefit.** And those z's use a binomial se that UNDERSTATES the true one,
  because val rows are correlated within a battle -- a lesson already in this repo. So the
  opponent set prior, which demonstrably supplies 3.16 certain opponent moves per decision and
  whose mechanism I verified, does not move teacher agreement at this scale.

  **The reveal-conditioned read -- the pre-registered falsifier -- does not fire either.**
  Agreement by number of opponent mons revealed, at n=30,000:
      with prior     0-1: 0.454   2-3: 0.412   4-6: 0.418
      without prior  0-1: 0.472   2-3: 0.428   4-6: 0.397
  FLAT in both conditions, and if anything HIGHER when less is revealed -- the opposite of the
  "student is bounded by missing opponent information" prediction that all three path reviewers
  converged on and that I implemented against. **On this evidence the information gap is not
  what is limiting the clone at 30k rows.**

  Honest reading of my own change: the set prior is theoretically sound, faithful to Showdown's
  generator, costs zero OBS_DIM, and is measurably inert on this metric at this scale. It may
  still matter for PLAY STRENGTH rather than move-matching (never tested), or at larger n. It
  should NOT be quoted as an improvement. Keeping it is defensible -- it is free and it removes
  a known information asymmetry with the teacher -- but the claim that it addresses the
  binding constraint is now falsified, and the reviewers' central diagnosis with it.

  **SOFT vs HARD targets at n=30,000:** agreement 0.4215 vs 0.4212 -- identical. But fitted
  policy entropy **1.449 (soft) vs 1.255 (hard)**, against a teacher entropy of 1.098. So soft
  targets buy nothing on agreement and do what they were adopted for: they anchor the student's
  entropy near the teacher's instead of driving it toward 0. That is the warm-start landmine
  (`loss/entropy` 0.063, failing the [0.2,1.0] R0 gate from update 1), and both fits land ABOVE
  that band, confirming it must be re-derived rather than inherited.

  **OPEN / NEXT:** the curve is still climbing, so a larger tranche is justified on the data
  read -- but the clone has never been scored on the thing that matters (`eval_checkpoint.py`
  vs SH under the locked protocol), and agreement is not win rate. That eval, plus the
  never-run head-to-heads (FP vs our best RL checkpoint; FP vs the BC clone of SH), are worth
  more than more rows. `--drop-trap` still has no positive test.

- 2026-08-06 — CLONE SCORED and the SH-EXPLOITATION question SETTLED. Two firsts for this repo.

  **1. THE FOUL PLAY CLONE SCORES 0.3683 vs SH (n=600), WORSE than cloning SH did.**
  `runs/bc_fp_soft_30000` under the locked protocol, `--opponent heuristics`.
  `eval/win_rate` == `wins_from_returns` to all digits, so not a reward-sign bug.

      Foul Play (the teacher)              0.8333   (n=1200)
      SH-vs-SH parity                      0.489
      BC clone of SH (P4, 813k rows)       0.4657
      best RL (12M + LR anneal)            0.4607
      **BC clone of Foul Play (30k rows)   0.3683**

  Cloning a teacher twice as strong produced an agent WEAKER than cloning the weak one. The
  explanation is consistent with the day's other numbers rather than mysterious: the SH clone
  reached 0.86-0.90 held-out agreement and scored 0.4657; this clone is at **0.42** agreement
  and scores 0.368. Imitation fidelity dominates, and 30k rows is 1/27th of P4's 813k. So this
  is NOT evidence the chapter fails -- it is evidence 30k rows is nowhere near the operating
  point -- but it is the first honest calibration between the two scales we have:
  **agreement ~0.42 -> win rate ~0.37.** The clone is currently the FLOOR, below everything we
  already have, not the ceiling the P4 clone was.

  **2. THE TEACHER IS NOT SH-EXPLOITING. §11's own trap does NOT fire.**
  Two opponents that already existed on disk and had never been played, 250 battles each,
  0 errors, via a new `--seat <checkpoint>` mode on `scripts/foulplay_vs_sh.py` (a LISTENING
  PoolPlayer; eval_checkpoint's cross-play path builds the same thing non-listening):

      Foul Play vs SimpleHeuristics     1000-194(6)   n=1200   0.8333 +/- 0.0108
      Foul Play vs our best RL 12M+LRA    219-31(0)   n=250    **0.8760** +/- 0.0208
      Foul Play vs the BC clone of SH     218-32(0)   n=250    **0.8720** +/- 0.0211

  Deltas vs the SH board: **+0.043 (z +1.82)** and **+0.039 (z +1.63)** -- i.e. Foul Play is if
  anything STRONGER against structurally different opponents, certainly not weaker. DESIGN §11
  wrote the trap before any option was chosen ("search would exploit SimpleHeuristicsPlayer
  hard and vs-SH would jump... any search work is read on the ladder, with vs-SH as board
  continuity only"), and the red-team review made it the central objection to the GO. **It is
  now answered with data rather than argument: the 0.83 is not SH-specific.**

  Incidental but worth recording: our best RL (0.4607 vs SH) and the P4 BC clone (0.4657 vs SH)
  are also indistinguishable from EACH OTHER against Foul Play (0.124 vs 0.128 from their
  side), independently corroborating STATUS's standing correction that RL is LEVEL with
  imitation rather than past it -- now measured against a third party instead of inferred from
  two vs-SH numbers.

  **WHAT THIS CHANGES.** The GO for §11(C) is now evidence-backed on the axis that mattered
  most and was weakest. What is NOT established is that distillation reaches useful strength:
  the only end-to-end datapoint is a clone at 0.368, and the repo still contains no measurement
  of RL from a BC warm start improving on its starting checkpoint. The curve is climbing
  (+2.6 pts/doubling at 30k, ceiling ~0.894), 3-wide collection is linear (19.7 h for P4
  scale), and the honest next question is whether agreement converts to win rate at a rate that
  ever clears 0.4657 -- which one more rung on the curve would answer far more cheaply than a
  full chapter.

- 2026-08-06 — DIRECTION AUDIT (evening): teacher-noise measurement, ps-ppo deep re-read,
  stack gap list. Run at maintainer request ("debug the direction"). Durable findings below;
  strategic recommendations delivered in-session and NOT ratified — nothing here changes a
  standing decision by itself.

  **1. THE TEACHER IS STOCHASTIC ENOUGH THAT THE SH-CLONE AGREEMENT BAR (0.86) CANNOT APPLY.**
  Measured on the 29,844-row tranche: Foul Play takes the argmax of its own recorded search
  policy only **0.8923** of the time; on the non-greedy 10.8%, the taken action is rank-2 in
  83% of cases with recorded mass 0.300 vs top-1 0.341 — near-tie search noise, not
  placeholder turns (placeholder rows are 1.7% of data and LESS non-greedy, 0.094). Policy
  concentration: mean top-1 prob **0.594** (median 0.553), mean entropy 1.118 nats, 41.1% of
  decisions have top-1 mass < 0.5, 22.0% have a top1−top2 gap < 0.1. Consequences: (a) top-1
  agreement of ANY state-function predictor is bounded at 0.892, so **the learning curve's
  fitted "ceiling 0.894" is this bound echoed back, not a reachable target** — the realistic
  ceiling with cross-replicate search noise is ~0.7–0.8; (b) the 30k clone's 0.4215 is
  therefore ~55–60% of its true ceiling, not 49% of the SH clone's bar — **the primary read of
  the next rung must be WIN RATE**, with `val_kl` to the soft policy as the fit metric and
  agreement demoted to a diagnostic; (c) a soft-policy clone that argmaxes E[policy] can in
  principle out-play single noisy search replicates — clone-below-teacher is not a law.

  **2. ps-ppo RE-READ (full source + git history; the load-bearing claim re-verified
  in-session).** Corrections filed in `prior_work/README.md`; headlines: the 2102-Elo system
  is the `7fb522c`-era code (15 tokens/turn, d_model 1024, 2 layers, single snapshot, NO JEPA,
  NO KV cache) and that snapshot does not even instantiate — the author's Reddit description
  is accurate for THAT system, and HEAD is a later unpublished one. Its RL phase is **pure
  mirror self-play vs the current policy** after BC-from-patched-SH — the checkpoint league
  was never runnable in any commit. `self_boost_sum` and tera-STAB **never fire** (`Move.target`
  is a `Target` enum compared against strings — verified live; same bug class as SH's dead
  setup branch), and the published agent trained with the MISALIGNED faint bonus (the
  off-by-one fix postdates the Elo screenshot) yet laddered 2102 anyway — further
  corroboration that Arm B's shaping null is unsurprising. Claimed scale: 150→250M states
  (revised upward in two minutes of commits), 2 days on an RTX 3090, 800–2048 concurrent
  battles across 10 local servers via a custom chat plugin.

  **3. ENCODER-SEMANTICS DRIFT UNDER EXISTING CHECKPOINTS (operational flag).** The set prior
  (default ON) and the placeholder aliasing fix changed observation SEMANTICS at constant
  OBS_DIM on 2026-08-06 — after every stored RL checkpoint. Re-evaluating any pre-Aug-6
  checkpoint today scores it off the distribution it trained on; nothing stamps encoder
  semantics into run meta or checkpoints. `POKEMON_RL_NO_SET_PRIOR=1` restores the prior only,
  not the aliasing fix. Note the FP-vs-our-RL head-to-heads (0.876/0.872) were played under
  the NEW semantics, so the old checkpoints' side may read slightly pessimistic. Add an
  encoder-version stamp before the next chapter's runs.

  **4. `scripts/score_ladder.py` DEFAULT-OPPONENTS DEFECT.** Its default
  `--opponents ["random", "heuristic"]` uses the Connect-4 registry names; Showdown's registry
  is `{random, max_power, heuristics}`, so the default raises. CLAUDE.md calls it "the correct
  path", but every headline number on disk came from `scripts/eval_checkpoint.py`. Fix the
  default or the doc.

  **5. VERDICT (compressed; maintainer's to ratify).** The wall is real and has a name: every
  ≥72%-GXE system in the index spent 10–60× our steps or ~1M human battles, trained on a
  non-SH signal (mirror self-play / humans / a search teacher), and most used sequence models
  — we are 0-for-3 in the RL line, and the week's +0.025-resolution rigor was aimed inside a
  recipe class whose remaining headroom is ~0.03. D8(c)/D9(c) — FP expert iteration — remains
  the right chapter (strongest measured teacher, no parsing risk, durable tapes). Amendments
  recommended: (i) read the 120k rung on win rate per finding 1; (ii) encoder work moves
  INSIDE the BC chapter now — tapes re-embed in minutes, the RL line is banked, and the
  teacher conditions on exactly what MOVE_DIM omits (no secondary-effect id/prob, no
  self-boost — gen1 Amnesia's +2/+2 is invisible — no crit/recharge class, no speed-order
  scalar; Rest/Amnesia/Reflect are near-identical 23-dim vectors); screen encoder-v2 and an
  entity-attention trunk on the SAME tranche by `val_kl`/win-rate before buying P4-scale
  data; (iii) pre-register the post-BC RL phase as mirror self-play + a KL-to-BC anchor
  (grep: no KL-anchor exists anywhere in `rl/`) rather than vs-SH — ps-ppo's laddered path
  was exactly BC-from-a-bot → mirror self-play at ~20× our steps, and our self-play nulls
  were different inits at MDE 0.14 with the pool's index-1 eviction defect live.

- 2026-08-06 — ENCODER V2 SCREENED ON THE TRANCHE: +3.1 pts agreement, GAP GROWS WITH DATA.
  Built while tranche 2 collects (maintainer authorized in-session launch; 3 lanes x 2,000
  battles toward ~180k rows, distinct usernames, gen1 engine build verified by module paths
  before launch).

  **ENCODER V2 (`POKEMON_RL_ENCODER_V2=1`, commit 838586d).** The audit's representation
  hypothesis, implemented: a 23-dim per-move EFFECT block (inflicted status + probability,
  self/foe boost sums, heal, recoil, drain, crit class, multi-hit, self-destruct, recharge,
  charge, inflicted volatiles — under v1, Rest/Amnesia/Reflect were near-identical vectors)
  plus a per-mon SPEED-EDGE scalar vs the opposing active (level-scaled, boost- and
  paralysis-aware). Feature list adapted from ps-ppo's move token (MIT), recomputed from
  poke-env gen1 data. OBS_DIM 611 -> 807; default OFF and bit-identical to v1 when unset.
  Because the tapes are the durable artefact, the screen was a RE-EMBED of the same 1,200
  battles (all six gates pass at 807 dims) — the exact workflow the set-prior ablation used.

  **THE SCREEN, same tapes, same seed, same by-battle split (paired val battles):**

      rows    v1      v2      delta
      3,750   0.3432  0.3432  +0.0000
      7,500   0.3510  0.3642  +0.0132
     15,000   0.3983  0.4089  +0.0106
     30,000   0.4215  0.4527  +0.0312   (naive z +2.45; se understated per repo lesson,
                                         but 11x the set prior's inert +0.0027 on the
                                         SAME data and metric)

  The delta GROWS with data — the signature of a representational fix the data can exploit,
  not noise: v2's last-doubling slope is +4.4 pts vs v1's +2.3. `val_kl` drops 0.840 -> 0.818.
  Contrast with the set prior (opponent-side information, inert): the binding constraint was
  what OUR OWN moves do, exactly as the stack audit predicted from Rest==Amnesia==Reflect.
  v2 is a BUNDLE (effects + speed); per-feature attribution is unmeasured — ablate only if a
  decision ever hangs on which half, per the set-prior lesson. Win rate not yet scored: that
  read comes with the 60k/120k/180k rungs when tranche 2 lands (~3.3 h at the measured
  ~6.4 s/battle/lane, linear again).

  **ALSO BUILT, all committed, suite 243 green:**
  - **Pool eviction fixed (ccae800):** span-preserving thinning replaces the index-1 delete
    that flushed pre-seeded pools (recovered predecessor bug; STATUS watch item retired).
    Anchor and newest never leave; retained push ids stay ~uniform over [0, latest];
    pool_size 1 still replaces (the naive arm). Regression test: 12 pushes into size 4 keeps
    ids {0,4,7,11}, not the old {0,9,10,11} recency window.
  - **KL-to-BC anchor (7521ed7):** `bc_kl_coef` on PPOAgent, default 0.0 = no-op.
    `begin_warm_start()` snapshots the just-loaded actor as a frozen anchor; update() adds
    bc_kl_coef * KL(pi_new || pi_anchor) per minibatch over the same stored mask (finite
    sentinel keeps illegal entries an exact 0), logged as `loss/bc_kl`; anchor persists
    through checkpoints; a scratch run with the penalty on fails loudly. This is the
    audit-recommended mechanism for the post-BC RL phase; its COEFFICIENT is unchosen and
    pre-registration of that phase is still owed.
  - **Encoder fingerprint stamped (f1cb74b):** `ENCODER_FINGERPRINT` {obs_dim, encoder
    v1/v2, set_prior} written into Showdown runs' meta.yaml and bc_metrics.json — closes the
    audit's "nothing records which obs semantics a checkpoint trained under" flag.

- 2026-08-06 (23:45) — TRANCHE 2 LANDED AND THE PROBE ANSWERED: **THE v2 FOUL-PLAY CLONE
  SCORES 0.558 vs SH — THE FIRST AGENT IN THIS REPO PAST SIMPLEHEURISTICS.**

  **COLLECTION.** 6,000/6,000 battles (3 lanes x 2,000, seeds/usernames distinct, 0 errors,
  ~5.9-6.4 s/battle/lane). FP pooled 4,981-1,019 = **0.8302** (n=6,000); with tranche 1 the
  teacher stands at **0.8307 (n=7,200)**. Reconstruction ran as ONE invocation per encoder
  over a symlinked union of both tranches' tapes — `id_base` restarts at 0 per invocation, so
  separate runs would have collided battle_ids and corrupted the by-battle holdout (checked
  before it happened, not after). **180,440 rows / 7,200 battles, ids 0-7199 unique, all six
  gates PASS under both encoders.**

  **AGREEMENT CURVE** (soft targets, seed 0, fresh split: val 18,201 decisions / 718 battles):

      rows     v1      v2
      60k    0.4375  0.4727
     120k    0.4669  0.4965
     180k    0.4860  0.5147

  Still ~+3 pts/doubling at 180k, no saturation; v2's edge stable at ~+3 pts. Against the
  measured teacher self-greedy bound of 0.892 (audit entry), 0.5147 is ~65% of the realistic
  ceiling — a different regime from yesterday's 0.42-vs-0.86 misreading.

  **WIN RATES vs SH** (n=1,000 each, final checkpoint, deterministic, ties as non-wins;
  `eval/win_rate` == `wins_from_returns` in all three; PROBE protocol — single fit seed, not
  the locked 3-seed board):

      v1 @ 180k rows   0.451 ± 0.016
      v2 @ 120k rows   0.515 ± 0.016
      v2 @ 180k rows   **0.558 ± 0.016**

  Readings: (1) v2@180k clears the ENTIRE board — SH clone 0.4657, best RL 0.4607, SH-mirror
  parity 0.489 (z ≈ +4.4 over parity). (2) **Encoder v2 is worth +0.107 win rate at 180k**
  (0.451 → 0.558, z ≈ 4.8) — ~3.5x its agreement delta; with v1, 180k rows had still not
  cleared the old clone bar. The representation was the binder, exactly as the audit argued.
  (3) Win-rate slope 120k→180k ≈ +7 pts/doubling — conversion is SUPERLINEAR in agreement
  (+2.9 agreement bought +4.3 win rate). The open question from the 30k entry ("does
  agreement convert fast enough to ever clear 0.4657") is answered: it cleared at 120k.

  **CAVEATS, owed before this becomes a headline row:** single fit seed (locked protocol
  wants 3); demonstrations are FP-vs-SH games, so the clone's state distribution is
  SH-conditioned — the TEACHER is measured non-SH-specific (0.876/0.872) but the CLONE's
  off-SH strength is not yet: run both-orientation head-to-heads (v2 clone vs SH clone / vs
  best RL / vs FP) next session.

  **IMPLICATION (maintainer's call, but the branch fired):** the pre-stated probe decision
  rule says commit P4-scale collection with the winning encoder — ~35k battles ≈ 900k rows ≈
  19.7 h at 3-wide. Naive log-linear extrapolation lands agreement ~0.58 and win rate well
  past 0.6 at P4 scale; bank the slope, not the extrapolation.

  **ALSO RUNNING:** the pre-registered self-play preview (configs/showdown_sp12m_v2.yaml,
  seeds 10/11/12, every lane's meta stamped v2/807, smoke at 573 steps/s vs the old 583
  baseline) launched at ~23:07 and owns the box overnight; R2 reads against the 0.3800
  record in the morning. Server-sharing note: the three clone evals ran during the SP lanes'
  first half hour — if any SP R0 throughput read looks marginal, exclude that window.

- 2026-08-07 (morning) — FIVE-AGENT RESEARCH SWEEP while the SP preview trains. Deliverables
  committed; findings that changed numbers or plans:

  **1. NEW BEST NUMBER: 0.569 ± 0.016 vs SH** — the 180k v2 fit's VAL-PEAK checkpoint
  (epoch 7, agreement 0.5147) had never been evaluated; the 0.558 was the OVERFIT final
  epoch (agreement 0.4949; train KL ~0.185 vs val 0.738). Carries a best-checkpoint
  selection caveat; the protocol fix is early stopping so final == best — MANDATORY for the
  900k fit (`prior_work/DISTILLATION_OBJECTIVES.md`).

  **2. THE 900k FIT'S OBJECTIVE IS SETTLED BY MEASUREMENT: soft-target BC stays.** Teacher
  advantage of the taken action computed from our own tapes: 97.1% positive, exp(0.5·A) in
  [1.000, 1.036] — Metamon-style weighted/filtered/offline-RL variants are numerically inert
  on this data (their gain came from discarding 55-85% of mixed-quality human rows). ExIt
  (NeurIPS 2017) measured soft-vs-hard = +50 ± 13 Elo at IDENTICAL agreement — our own
  soft-vs-hard agreement tie was not evidence against soft. Adopted: early stopping,
  --value-coef 0.5 (critic pretraining; zero actor coupling — donor
  runs/bc_fp_v2_soft_val_180k_s0 fitted, held-out value R^2 0.661). Gated add-on: one DAgger
  round (~100k relabels ≈ 2.2 h) iff a ~5k-decision covariate-shift diagnostic fires.

  **3. HUANG & LEE 2019 VERIFIED — the citation survives better than any ladder row** (full
  entry + archived PDF in prior_work; metagrok cloned as sibling). Pure mirror self-play,
  2-3×10⁸ decisions, ~$91. Extracted from code, absent from the paper: gamma 0.95 + 5-term
  ZERO-SUM shaping, no entropy bonus, and a per-action shared scoring head over 128-d entity
  embeddings — NOT a flat MLP. Index's guessed title was a different paper (fixed).

  **4. ARCHITECTURE SCREEN SPEC'D AND PRICED** (`prior_work/ARCH_SCREEN_SPEC.md`): 21-token
  reshape inside the network, d128/L2 pointer trunk at 0.73× MLP params, measured 34.6×
  CPU train-step cost (fits still affordable: ~18 min at 180k), decision rule pre-sketched.
  Inverts a standing note: for this trunk the UPDATE is ~55-60% of the RL loop, not collect.

  **5. HISTORY FEATURES NEED ZERO NEW STATE** (`prior_work/HISTORY_FEATURES_DESIGN.md`):
  poke-env's `_replay_data` is an always-on event log shared by both encode paths (divergence
  impossible by construction; -crit/-supereffective/-miss/cant recoverable from nowhere
  else). 22-dim suffix block spec'd with measured firing rates. AND A LIVE ENCODER BUG:
  `Effect.MUST_RECHARGE` in `_VOLATILES` is STRUCTURALLY ALWAYS 0 (v1 and v2; poke-env sets
  `mon.must_recharge`, never the Effect — 0/2,427 vs 185/2,427 measured), so recharge and
  partial-trap placeholder turns encode as all-zero move blocks with no indicator why.
  PARTIALLY_TRAPPED-as-Effect also never fires. Fix is 2 dims (bool + aliased flag),
  pre-registered as Stage-0 with the history screen — NOT hotfixed (obs semantics change).

  **6. WARM-RL PRE-REGISTRATION DRAFTED AND COMMITTED** (`configs/showdown_warmrl_v2.yaml`,
  DRAFT — not ratified): one new variable (bc_kl_coef, anchored ladder {0.03/0.10/0.30}),
  SH held out of training (first time vs-SH is admissible as a held-out primary), donor
  gates measured, F1 SH-exploitation falsifier, K1-K4 kills, seeds 14-22 claimed.

  SP preview meanwhile: R1 LEARNING GATE PASSED on all seeds (winrate_anchor 0.94-0.95 at
  ~3.7M vs the 0.75 bar); in-training rungs ~0.30-0.40 vs SH at 3.7M — hovering near the OLD
  run's FINAL (0.380) at a third of the budget. Finals ~13:00.

- 2026-08-07 (13:20) — SELF-PLAY PREVIEW READ: **NULL. Encoder v2 + the fixed pool do NOT
  unlock from-scratch self-play at 12M.** Pre-registered branch fired exactly as written.

  Finals, locked protocol (final ckpt, deterministic, ties non-wins, n=1000/seed, v2):
      s10 0.393   s11 0.377   s12 0.397   ->  POOLED 0.3890 (se 0.0089)
      OLD run (v1 + broken pool, 2026-08-01): 0.3800 ± 0.0089
      delta +0.0090, se_diff 0.0126, z +0.72  ->  NOT CREDITED (line: >=+0.025 AND >=2se)
  R0 gates all passed (fingerprints v2/807 every lane; ties ~1%; ~500-555 steps/s; one
  external kill + clean relaunch at 1.0M, cause outside the session, recorded). R1 passed
  early (winrate_anchor 0.94-0.95 by 3.7M). Entropy 1.88->~0.4, never near the 0.15 alarm.
  In-training matched-window read (6-7.3M: 0.382 vs 0.363) had suggested ~+0.02; finals say
  +0.009 — both instruments agree on "small positive, far below credit."

  **THE INSTRUCTIVE CONTRAST: the SAME encoder v2 bought +0.107 win rate in the BC chapter
  and +0.009 ± 0.013 in scratch self-play at 12M.** Representation pays when there is a
  strong signal to represent; it does not rescue a sparse-signal bootstrap at 1/20th of
  field scale. This corroborates the audit's ordering (prior first, RL second) with a
  controlled measurement rather than an argument.

  Consequence, per the pre-registration: the 50-100M pure-self-play run LOSES its cheap
  justification. If it is ever bought, the H&L-verified recipe deltas are the hypotheses to
  pre-register alongside scale: gamma 0.95 + 5-term ZERO-SUM shaping (their undocumented
  signal design), the per-action scoring head, entity embeddings — see the H&L entry in
  prior_work/README.md. The main line (P4-scale BC -> warm-started anchored RL) is
  unaffected and remains the recommendation. Bundling caveat recorded: this run changed
  encoder+pool together; the null is on the BUNDLE.

- 2026-08-07 (afternoon) — **MAINTAINER DECISION: PURE SELF-PLAY BECOMES THE MAIN CHASE.**
  Verbatim rationale: it is a more interesting project for gen1 because it has never been
  done; sitting atop already-done BC or supervised training is not as interesting; it does
  not need to match or beat Foul Play; it is the strongest subproject. "We can call it quits
  later" — the chase is explicitly revocable. Consequences: the FP/BC chapter's artifacts
  (teacher, tapes, clones at 0.558/0.569, warmrl draft) are BANKED as infrastructure and
  eval anchors, not abandoned — P4-scale collection and warmrl ratification go ON ICE rather
  than dead. DESIGN gets an r7 reorientation (drafted this session). The evidence base the
  new chapter starts from: the 12M v2+pool preview NULL (+0.009), the verified H&L recipe
  (2-3e8 decisions, gamma 0.95 + 5-term zero-sum shaping, per-action scoring head, entity
  embeddings — none of which our null run had), and the throughput math (current loop ~540
  steps/s/lane; H&L scale = ~5 days/lane; loop re-architecture is the enabler). Also
  maintainer authorized PUSH of main to origin (first push of the repo's backlog).

- 2026-08-07 (evening) — THE PIVOT'S DESIGN WORK LANDED: DESIGN r7 + Rung 0-2 artifacts, all
  committed and pushed. Three-subagent output, session-curated:

  **1. DESIGN r7 PROPOSED (D10-D17)** — full reorientation around the pure-self-play chase:
  milestone ladder (M1 0.4400 go/no-go / M2 0.489 parity / M3 0.510 success claim / M4 0.558
  stretch, all 3x3000, non-SH-anchor guard from M2 up), enforceable purity definition (no BC
  init, no teacher data, no SH in training; encoder = environment, not prior), four rungs
  cheapest-falsifiable-first, FP/BC chapter banked, D17 abandon criterion. Two corrections
  the draft caught: H&L's AGGREGATE throughput was only ~450 decisions/s (our 3-wide box
  already exceeds it — the gap is wall-clock per seed, not speed), and their 2-3e8 scale may
  count both seats (settle from metagrok before Rung 3's budget; a 2x error is 2.5 days).

  **2. RUNG 0 SPEC (`prior_work/THROUGHPUT_SPEC.md`)** — the enabler, from source:
  **SyncVectorEnv SERIALIZES all 8 sub-envs' server round-trips on the main thread; num_envs
  is a dead lever (<1%); ~80% of the loop is idle websocket wait** (steps/s = N/(N*1.85ms),
  constant in N). poke-env's PokeEnv hardcodes max_concurrent_battles=1, so the fix is an
  async collector on the plain-Player path (K=32-64 battles, batched inference via the
  rl/collect.py seam, ~950 lines) — which leaves the locked eval path UNTOUCHED by
  construction. Projects 540 -> ~1,400 steps/s/lane (H&L scale: 5.4 -> 2.1 days, all three
  seeds simultaneously). Two CRITICAL silent hazards pre-gated: the old_logp recompute
  assumption (first-epoch ratio would be exactly 1.0 and look healthy while doing stale
  vanilla PG) and the PoolPlayer one-battle latch (silent pool corruption under concurrency).
  Cut list with arithmetic: GPU inference (0.7% ceiling), Ray, AsyncVectorEnv (fork-unsafe,
  permanently), rlspawn.ts, 10 servers (we have simulator:4; 2-server contingency gated on
  E4). Decomposition experiments E1-E4 (<=10 min each) come first; G9 is a null-expected
  learning-equivalence gate at 12M vs the 0.3890 basis.

  **3. RUNG 1+2 DRAFT PRE-REGISTRATIONS** (`configs/showdown_sp_signal12m.yaml`,
  `configs/showdown_sp_struct12m.yaml`, NOT ratified): Rung 1 = gamma 0.95 + H&L's 5-term
  zero-sum event shaping with constants READ FROM METAGROK'S CODE (absent from the paper:
  faint 0.0125, fail 0.005, SE 0.0025, resisted 0.0025, immune 0.005, zero_sum), an
  ASSERTABLE antisymmetry gate (both seats' shaping sums to exactly 0.0 — poke-env scores
  both seats every step, so it is instrumentable in-process), and a `--no-shaping` eval seam
  that keeps the wins_from_returns sign-bug cross-check alive. Rung 2 = entity DeepSets +
  shared per-action scorer at a param ceiling of the MLP's 681k, with a gated
  POKEMON_RL_ENCODER_IDS suffix (807->827) for species/move ids. Sequential ladder vs 0.3890,
  one-time symmetric n-escalation, factorial explicitly refused with the power arithmetic.
  Seeds 23-30 claimed. Both drafts pre-answer the eval-leak, the wait-pump double-count, and
  the value-target-bound question at gamma 0.95 (|V| <~ 1.15, value loss +<~15%).

  Everything through this entry is pushed to origin/main.

- 2026-08-07 (late evening) — **DESIGN r7 RATIFIED. All eight decisions adopted per the
  inline recommendations** (maintainer review, structured Q&A): **D10(a)** ladder as written,
  M1 0.4400 go/no-go, **M3 0.510 is the success claim**, M2 parity the headline if M3 misses;
  **D11(a)** purity definition incl. design-time disclosure; **D12(b)** Rung-0 measurement
  evening first, Rung 1 immediately at today's loop speed; **D13(a) the MUST_RECHARGE Stage-0
  fix LANDS NOW and the 0.3890 comparator RE-BASELINES** (one extra overnight, whole chase on
  one encoder); **D14(a)** throughput measurement only, cheap wins authorized later on their
  numbers; **D15(b)** rented many-core CPU box for Rung 3 only, gated on Rung 0's
  decomposition; **D16(a)** keep the opponent pool (recorded deviation from H&L/ps-ppo pure
  mirror); **D17(a)** abandon criterion as written (below M1 after Rungs 1+2+50M, or >20
  lane-days, or >8 weeks; on abandon warmrl resumes and the negative publishes with a scale
  bound). Consequences now binding: tonight = Stage-0 fix + 3×12M control re-run on the fixed
  encoder (new comparator replaces 0.3890); Rung 1 launches the night after.

- 2026-08-07 (night) — D13a EXECUTED + RUNG 1 CODE COMPLETE, BOTH R0-2 GATES PASS. The
  ratification evening's full slate, in order. **(1) Stage-0 MUST_RECHARGE fix landed**
  (0c83339): dead Effect slot now reads `mon.must_recharge` on both actives + global
  aliased-turn flag at vec[5]; OBS_DIM v1 611→612, v2 807→**808**; fingerprint gains
  `recharge_fix: true`; live obs-fidelity PASS (215 decisions, 0 mismatches).
  **(2) Re-baseline lanes LAUNCHED** (maintainer terminal, nohup, staggered):
  `showdown_sp12m_v2r` seeds 31/32/33 from clean ce2fe2c — R0-1 verified per lane
  (v2/808 + recharge_fix, git_dirty false), battle progress verified per lane at
  540-600 steps/s. ETA ~6.2 h (~21:30); liveness monitor armed in-session (external-kill
  landmine). Pooled finals at 3×3000 become the Rung 1/2 comparator; **0.3890 is dead**.
  Smoke seed 34 spent; seeds 31-34 now claimed. **(3) Rung 1 code items all landed**
  (1062623): `hl_shaping` kwarg (metagrok constants verbatim, per-battle event cursor
  over `_replay_data`), `--no-shaping` on eval_checkpoint (+ report stamps it, R0-4),
  stub attrs per the HISTORY_FEATURES rule. **R0-2(a) OFFLINE PASS** as a permanent test
  (tests/test_hl_shaping_tapes.py): 2 tapes, >=50 battles, per-battle two-seat sums
  cancel EXACTLY (== 0.0), term-by-term hand-parse agrees, all five terms fire.
  **R0-2(b) LIVE PASS** (scripts/hl_shaping_live_smoke.py, 10 battles, seed 29):
  in-process seat-2 reward captured via calc_reward spy; s1+s2 == 0.0 exactly on every
  battle; cursor-complete vs full-log recompute <=1e-12; return identity <=1e-9. First
  live term counts (seat 1, 10 battles): faint 102, -fail 41, -supereffective 45,
  -resisted 57, -immune 8; per-battle |shaping| 0.005-0.0525 — at/below the low end of
  the predicted 0.05-0.15 band, recorded not gated. Rung 1/2 headers amended in place
  (RATIFIED banners): v2/808 everywhere, comparator = v2r pooled finals (R2 carries a
  blank to fill BEFORE launch), locked reads at 3000/seed × 3 per D10a (escalation
  clause moot). Suite 258 green. Tomorrow: v2r R0 gates + 3×3000 locked evals, fill the
  comparator, then launch Rung 1 (seeds 23/24/25).

- 2026-08-07 (22:15, autonomous overnight read) — **THE v2r RE-BASELINE IS IN: pooled
  0.3996 ± 0.0052 (n=9,000) IS THE CHASE'S COMPARATOR OF RECORD.** Per-seed
  0.3867 / 0.4310 / 0.3810 (s31/32/33, 3000 battles each, locked protocol,
  `eval/win_rate == wins_from_returns` EXACTLY on all three — the sign-bug guard holds).
  All gates green: 12M complete on every lane (final ckpt step 12,000,000), R0-1
  fingerprints v2/808+recharge_fix from clean ce2fe2c, post-3M tie rates 0.4-0.6%
  (gate 4.2%), ep len ~28 (gate 40), throughput medians 510-553 (band 537-583 -25%),
  R1 anchor 0.94-0.95 @4M, entropy floor ~0.45. Notes: (1) **s32's 0.4310 is ~3.5
  binomial-sd above its seed-mates** — real seed heterogeneity at 12M, recorded not
  gated; the pooled number is the comparator per protocol. (2) Cross-semantics delta
  vs the dead 0.3890: +0.0106, z +1.03 — within noise, exactly as the pre-registered
  secondary expected (the 2-dim Stage-0 fix alone moved nothing measurable at 12M).
  (3) **OPS FINDING: a 3,000-battle serial eval takes ~2 MINUTES, not ~1 h** — the
  eval env has no learner/wandb in the loop and the serial websocket path runs at
  full lane speed (THROUGHPUT_SPEC's own arithmetic, confirmed in anger); locked-n
  evals are effectively free, stop budgeting hours for them. Rung 1's R2 blank is
  FILLED (credit bar >= 0.4246; M1 0.4400 still above it), and the signal config
  passed a construct dry-check (Config -> env_kwargs seam -> live ShowdownSingles
  with hl_shaping 1.0). Rung 1 is GO for launch: seeds 23/24/25, one overnight.

- 2026-08-08 (13:30) — **RUNG 1 (SIGNAL) READ OUT: NULL. H&L's reward/discount design does
  NOT rescue the 12M bootstrap.** Locked finals (3×3000, --no-shaping, R0-4 exact-agree +
  no_shaping stamped on all three): s23 0.4147 / s24 0.4107 / s25 0.4140, **pooled 0.4131
  ± 0.0052 vs comparator 0.3996 ± 0.0052 → delta +0.0135, z +1.84 — misses BOTH halves of
  the credit line** (needs ≥ +0.025 and ≥ 2·se_diff = 0.0146). Below the [+0.015, +0.025)
  ambiguous band, so no escalation question even if it weren't moot. **Branch (b) of the
  pre-registration binds: report honestly, Rung 2 runs at gamma 1.0 / NO shaping against
  the SAME 0.3996 baseline; magnitude retuning stays closed.** The null is CLEAN — every
  gate green: R0-3 treatment-on (98.7% of episodes non-±1), R0-5 regime (ties ~0%, len 28),
  R0-6 throughput 516-537, R0-7/K2 value sane (EV +0.55 by 1M, zero NaNs), K1 never fired
  (entropy 0.44-0.47), R1 anchor 0.96. Secondaries: **S2 CONFIRMED** — EV end 0.575-0.656
  vs control 0.513-0.555 (dense targets make the value problem easier, as pre-stated);
  S3 entropy trace ~unchanged; **S4 no "hurry-up-and-trade" signature** (ep len 27.5-29 vs
  control 26-28, ties equal). MECHANISM NOTE, recorded not read: the signal arm's seed
  spread COLLAPSED — 0.004 across seeds vs the control's 0.050 (s32 0.431 outlier) — dense
  zero-sum shaping appears to stabilize what self-play converges to, without moving its
  mean past the bar. Also honest caveat on z +1.84: the pooled-binomial se convention
  ignores the control's measured seed heterogeneity; using between-seed variance the z
  drops to ~+0.9. Direction is positive, evidence is below every bar we pre-registered.
  Ladder state: two nulls (preview, signal) — the chase now rests on Rung 2 (STRUCTURE)
  and Rung 3 (SCALE), exactly the position D17's abandon criterion was written for.
  NEXT: implement Rung 2's entity trunk (DeepSets + per-action scorer, param ceiling
  681k, spec in configs/showdown_sp_struct12m.yaml), R0-4 arch smoke seed 30, then 3×12M
  seeds 26/27/28. Evals: in-session (~2 min each, measured again today).

- 2026-08-08 (evening) — **RUNG 2 (STRUCTURE) CODE COMPLETE — every offline gate green,
  R0-4 smoke is the only thing between here and the 3×12M launch.** Per branch (b):
  gamma 1.0, no shaping, comparator 0.3996. What landed (commit this entry rides in):
  **(1) Encoder id suffix** behind `POKEMON_RL_ENCODER_IDS=1` (default OFF, bit-identical
  unset): 20 dims appended after the v2 block — 6 own + 6 opp species dex nums (1-151),
  4 own + 4 opp move nums (1-165), each emitted id/256.0 (exact in float32), unknown/
  unrevealed → 0. Own-move ids zero on aliased turns (matching the zeroed blocks); opp-move
  ids name the move occupying the block, prior fills included. OBS_DIM 828 with both vars;
  fingerprint gains `ids`. **(2) `rl/networks/entity_deepsets.py`**: EntityTokenizer
  (ARCH_SCREEN_SPEC's 21-token reshape, offsets derived from showdown constants, asserted —
  a forgotten env var dies at construction naming the var, the R0-1 seam) + the H&L trunk:
  152/166×64 embeddings, shared per-mon/per-move subnets (in→128→128, terminal LayerNorm —
  ps-ppo's shape at the ratified width; ReLU — H&L's activation, verified in metagrok),
  DeepSets max pools, ctx 640→[384,384], ONE shared scorer 512→256→1 + 10-d slot bias over
  [ctx‖entity] pairs (switch i ↔ mon vec i, move 6+j ↔ move vec j), fully separate value
  stack. **Actor 626,059 ≤ ceiling 681,994** (the v2/808 MLP actor's exact count, verified
  live; asserted at construction, K2) — critic 494,849; both match the ratified sketch.
  **(3) PPOAgent `trunk:`/`trunk_kwargs:` seam**, default "mlp" — R0-3 proven against
  GOLDENS captured from pre-seam HEAD (9725816): param sums and forward outputs EXACT.
  K4: the entity net owns its init (Xavier + std-0.02 embeddings + 0.01-rescaled final
  scorer); `_orthogonal_init` never touches it. **(4) meta.yaml stamps exact actor/critic
  param counts** (all runs). **(5) Tests 258 → 264**: R0-2 exact counts + ceiling formula,
  R0-3 goldens, R0-5 on SIX tapes (6,000 decisions: exact round-trip, own ids all known,
  unrevealed → 0, per-slot reveal stability — the hl pair alone has only ~2,300 decisions,
  so the corpus widened to fp_tapes_all), R0-7 eval-time masking through agent.act, seam
  guards (unknown trunk / conv / continuous / missing flag all raise). **(6) Live proof**
  (seed 99 throwaway, 2,048 steps vs the :8000 server; runs/struct_integration_smoke
  kept, gitignored): fingerprint v2/828/ids ✓, params stamped ✓, 28 episodes progressed,
  in-loop eval fired, and `eval_checkpoint.py` REBUILT the entity agent from the config
  snapshot and played real battles — the finals path needs no changes. steps/s median 498
  on the 2k sample (startup-heavy; the R0-4 read stays the 1M smoke). **(7)
  `configs/showdown_sp_struct12m_smoke.yaml`** (R0-4: 1 lane × 1M, seed 30, gate ≥ 380
  steps/s, K1 shrink pre-declared and unspent). NEXT: maintainer runs the R0-4 smoke
  (~35 min); on PASS launch 3×12M seeds 26/27/28, v2r nohup pattern, BOTH env vars.

- 2026-08-08 (late evening) — **OUTSIDE ADVISORY on the self-play PPO recipe: read, verified,
  one genuinely new candidate surfaced.** Maintainer uploaded an advisory written without repo
  access; per the prior_work rule its externals were verified before anything is cited.
  VERIFIED: ps-ppo at the LADDER-ERA checkout 7fb522c (the 2102-Elo system): `gae_lambda`
  0.75 FLAT, `steps_per_update` 32,768. The advisory read HEAD (36,864 + DYNAMIC λ clamped to
  [0.55, 0.95]) — HEAD never laddered, but its Tier-1 claim survives at the checkout that did.
  Wang's numbers match our verified index (0.575@6M, LR ablation 0.55→0.80). OUR numbers it
  used are stale/wrong in ways that mostly STRENGTHEN its point: the self-play chapter runs
  rollout 128×8 = 1,024 (its "4,096" was the r512 vs-SH arm), trained ep length is ~26-28
  decisions (not ">100 turns" — its two errors cancel), and the baseline is 0.3996 (not
  0.443). Net: **~38 completed episodes per update vs Wang's ~1,600 and ps-ppo's ~1,500 — a
  ~40× terminal-signal gap per update — plus λ 0.95 (settled on Connect4's 11-step episodes)
  vs both references' 0.75. RECIPE is a candidate binder the ladder does not test.** Weak
  in-house corroboration: the control's 0.050 seed spread (s32 0.431) and Rung 1's
  spread-collapse under dense shaping both fit "noise-dominated updates". Already
  done/settled elsewhere in it: endpoint-read discipline (Rung 1 did exactly that, nulled);
  flat-MLP + rich-features control (IS the v2r comparator); move-token question (settled and
  implemented today); 80/20 snapshot pool, frozen-pool contract, anchor winrate (all in
  place). REJECTED as written: fixed bots in the training pool (breaks the pure-self-play
  chapter definition; SH must stay held out for vs-SH admissibility); replacing the LOCKED
  deterministic eval (fixed scripted opponent — sampled eval is fine as a SECONDARY only);
  "free 2×" both-seat harvest (seat 2 is ALWAYS a frozen snapshot inside SingleAgentWrapper —
  no current-vs-current games exist, rows never surface, needs behavioral-logp storage: a
  throughput lever to price for Rung 3, not free signal). DISPOSITION, maintainer to ratify:
  a pre-registered RECIPE rung — rollout toward ~16-32k steps/update (named knob!) and a λ
  0.75 arm, 12M, vs the same 0.3996 — slotted at branch (d)'s GO/NO-GO, so the cheap
  candidate is burned down BEFORE the 50M scale step is priced. Pre-registration trap noted
  now: at 12M a 32k rollout is ~366 updates total, so push_every_updates 150 would push TWO
  snapshots — pool cadence must be re-keyed in steps. Rung 2 is UNCHANGED (ratified; launches
  on R0-4 PASS); nothing from the advisory folds into it mid-flight.

- 2026-08-08 (night) — **"SHOULD WE RELAX PURE SELF-PLAY?" — landscape-review PDF read,
  key evidence verified at primary source, decision framed for the maintainer.** The
  uploaded PDF is a project-selection landscape review; despite the outside-experts
  framing it is NOT anti-pure-self-play: its verdict is "pure self-play headline + a
  matched-budget BC-initialized arm as the controlled comparison," with harsher gates than
  ours (0.8 vs SH at 50M) calibrated to a 150M budget. VERIFIED LOCALLY against
  angliss2025_vgc_bench.pdf Tables 7-11 (and our index CORRECTED — its old row mixed
  regimes): scratch PPO vs SH decays 0.785 → 0.587 → 0.514 as team diversity grows
  1 → 16 → 64 while BC-init holds 0.890 → 0.848 → 0.834; BC edge +10 → +32 pts; randbats
  is the diversity limit. That is the strongest published evidence FOR the experts'
  warning at our scale. AGAINST fatalism, also verified: H&L is a pure self-play,
  no-search, RANDOM-BATTLES success (gen7, 72% GXE) at 2-3e8 decisions = 20-45x our
  budget — the existence proof in the closest regime; gen1 is the friendliest gen for
  pure-policy (PokéAgent: Gen1OU won by pure-policy RL); and no published hard ceiling
  exists. New wrinkle: VGC-Bench's Table 7 recipe is gamma 1.0 / lambda 0.95 / ~3k
  steps-per-update — OUR side of the recipe split, softening the advisory's two-system
  convergence prior (though their scratch arm is also the one that decays). FRAMING: the
  experts are probably right that pure self-play misses M3 at 12-50M; they are unproven
  at H&L scale; and the ladder was DESIGNED to decide cheaply what to scale before paying
  for scale — the expensive fork is already gated at branch (d)/D15/D17. RECOMMENDATION
  (maintainer to ratify, nothing changed tonight): (1) run Rung 2 as ratified — it is
  built and nearly free; (2) recipe rung next if desired; (3) at the branch-(d) fork,
  decide between the 50M pure scale step and UN-ICING warmrl/BC-arm as a PARALLEL
  headline, not a replacement — the scratch-vs-BC matched-budget curve in
  gen1randombattle is itself novel (VGC-Bench did gen9 doubles; nobody has done gen1
  randbats), so the chase's novelty survives either answer. The PDF's own Option-B
  trigger (pure plateaus AND BC arm stalls) requires having run the BC arm. Resources
  named: 109k HolidayOugi gen1randombattle human replays (BC source), Metamon's open
  Gen1 checkpoints (external yardstick, "single most valuable legibility move").

- 2026-08-08 (23:45) — **R0-4 THROUGHPUT SMOKE: PASS — the entity trunk is FASTER than
  projected. GO for the 3×12M.** Seed 30, 1M steps, ~30 min wall, clean HEAD (ba81c37,
  git_dirty false). Steady-state (steps > 100k) `time/steps_per_sec` **median 552.7**
  (p10 437, p90 617, n=23,753) vs the ≥380 gate and the 430-500 projection — above even
  the MLP preview's 537 (collection dominates; the batched scorer matmuls are cheap at
  1 thread, as the FLOP arithmetic said). **S2: update share 14.0%** of collect+update
  (projection 15-20%, MLP ~5%) — affordable at 50M. R0-1 verified live: meta stamps
  obs_dim 828 / ids true / recharge_fix true, params actor 626,059 / critic 494,849.
  Health at 1M: ep len 34.5 (R0-6's ≤40 applies to main lanes after 3M), entropy
  1.746 → 0.444 (K6 floor 0.15, wide margin), EV 0.520, winrate_anchor 0.966, probe
  evals 0.55/0.50 at n=20 (noise, not a read). K1 shrink stays unspent. Lane command
  handed over: seeds 26/27/28, v2r nohup pattern, 90 s stagger, both env vars, logs in
  gitignored runs/. Overnight ETA ~6-7.5 h at 430-550 steps/s.

- 2026-08-09 (05:50, autonomous overnight read) — **RUNG 2 (STRUCTURE) READ OUT: CREDIT,
  branch (a) — THE FLAT READOUT WAS THE BINDER. Pure self-play jumped +15.1 points.**
  Locked finals (final ckpts, 3×3000, deterministic, ties as non-wins, vs SH, both env
  vars; `wins_from_returns` == `eval/win_rate` EXACTLY on all three — the reward-sign
  guard): s26 0.5633 / s27 0.5683 / s28 0.5210, **pooled 0.5509 ± 0.0052 vs comparator
  0.3996 ± 0.0052 → delta +0.1513, se_diff 0.0074, z +20.5** — six times the +0.025
  credit line, ten times 2·se_diff. Seed spread 0.047 (control's was 0.050). After the
  preview (input, null) and Rung 1 (signal, null), STRUCTURE at identical capacity
  (626,059 ≤ 681,994 params) is what unlocks the 12M bootstrap: handing the policy
  "this action targets this entity" beats making it relearn that in every weight column.
  **MILESTONE LADDER: M1 (0.4400) PASSED** — pooled AND every individual seed clear it;
  D17's below-M1 abandon arm is moot. **M2 (0.489) and M3 (0.510 — the success claim)
  are numerically cleared (worst seed 0.5210 > M3) but NOT YET CLAIMED: the mandatory
  non-SH-anchor guard (warmrl F1, DESIGN r7 §2) requires two-orientation head-to-heads
  vs the FP clone / Foul Play, 500/pair/orientation.** That work is now OWED (its
  trigger fired). Blocker recorded: one process = one encoder config, so 828-checkpoint
  vs 808/807-checkpoint cross-play needs a small per-seat obs shim — the id suffix is a
  pure suffix, so seat-2 slicing vec[:808] is exact; build the seam, don't improvise it.
  Also on the board: 0.5509 beats the best vs-SH-TRAINED MLP (0.4607) and the SH clone
  (0.4657) — an agent that has NEVER SEEN SH outscores agents trained on/against it —
  and sits 0.007 under M4's un-graded 0.558 comparator (re-grade the clone before any
  M4 talk). SECONDARY SANITY (labeled, not the guard): vs MaxBasePower n=1000 — Rung 2
  s26 0.841 vs v2r-best s32 0.749 (+9.2) — the gain generalizes to a non-SH opponent.
  GATES, all green: R0-1 fingerprints 828/ids on all lanes (git_dirty false, ba81c37);
  R0-6 ties 0.16-0.18% / ep len 30.8-31.5; R1 anchor 0.974-0.976 by 4M on 3/3; K6 never
  fired (s26 touched 0.138 but the 3-seed median held; ends 0.19-0.23); EV end
  0.376-0.587; S2 update share 13.5-13.9% (smoke-consistent; 50M-affordable). OPS: ~8.7 h
  wall at ~350 steps/s/lane 3-wide; a 50-min laptop-sleep suspended everything cleanly
  (ckpt gap 20:17→21:05, zero errors); s27's turn-1000 auto-tie marathons benign; the
  overnight Monitor died in the sleep and was re-armed (its exit-time lane count was
  buggy — lanes were verified complete by hand). CONSEQUENCES: the 50M pre-registration's
  content per branch (a) is STRUCTURE ALONE (entity trunk, gamma 1.0, no shaping) — write
  it fresh, price it with D15 (3-wide 350 steps/s → ~40 h/lane at 50M; the loop
  re-architecture is now clearly the enabler). The 2026-08-08 branch-(d) decision stack
  is MOOT (that fork assumed two nulls): the RECIPE rung is demoted to an optional
  secondary lever, and the relax-purity question is ANSWERED BY DATA at 12M — no
  relaxation needed; a BC arm is now an optional comparison, not a hedge. NEXT (maintainer
  morning): (1) guard plan — FP-clone protocol-grading + the cross-encoder shim + the
  F1 head-to-heads (M2/M3 claims hang on this); (2) S1 vs the v2r final (same shim);
  (3) the 50M structure-only pre-registration + D15; (4) push to origin (ask-first).

- 2026-08-09 (morning) — **CROSS-ENCODER EVAL SHIM BUILT + S1 HEAD-TO-HEAD RUN: Rung 2
  beats the standing best 0.612 ± 0.015 pooled — the falsifier moves, the gain is not
  SH-specific.** The shim: `PrefixSliceActor` (rl/networks/mlp.py) + a
  `_load_showdown_agent` seam in eval_checkpoint.py used by BOTH cross-play seats — a
  v2/808 checkpoint under the 828 id-suffix process is built at its native width and its
  actor input sliced, EXACT because the id block is a pure suffix; v2/807 (pre-fix,
  inserted dim) is REFUSED with a named error, never shimmed. Tests +3 (suite 267):
  wrapped-forward bitwise equality; the pure-suffix claim MEASURED across processes
  (same battle, v2/808 vs v2/828, first 808 floats byte-identical); loader shims 808 /
  passes 828 / refuses 807. **S1 (per its spec — standing best's final, both
  orientations, 500/pair/orientation, pooled):** Rung 2 s26 (median seed) vs v2r s32
  (the control's BEST lane, 0.431 vs SH): orientation A 0.628 (ties 0.004), orientation
  B 0.596 from the sampling seat (seat asymmetry visible, pooled) → **612/1000, z +7.3
  vs parity.** Falsifier reading (F1's logic): the +0.151 vs-SH jump arrives WITH a
  decisive head-to-head win over a non-SH opponent and the +9.2 MaxBasePower gain — a
  vs-SH-specific exploit would show flat anchors. FORMAL M2/M3 claim still awaits the
  NAMED anchors (maintainer to ratify sufficiency or schedule): FP clone needs a
  re-fit on v2/808 (v2/807 ckpts are un-shimmable by design), Foul Play needs the
  engine harness (no shim required — FP reads the protocol, not our encoder).

- 2026-08-09 (morning, cont.) — **F1 NAMED-ANCHOR GUARD EXECUTED: the FP clone re-fit,
  protocol-graded, and beaten head-to-head 0.657 — the M2/M3 anchors MOVE.** Steps, all
  on current code: **(1) Re-embed** of the six-tape corpus on v2/808
  (data/fp_all_v2r, tape_to_dataset one invocation): 7,200 battles / 180,440 rows, ALL
  SIX GATES PASS. **(2) Re-fit** with the banked recipe (soft, 512/512, seed 0, 20
  epochs, batch 512, lr 1e-3; ONE deviation: no --max-rows cap → all 180,440 rows vs
  the banked 180,000): val free-agreement 0.517 vs banked 0.5147 — recipe reproduced.
  **(3) Protocol-grade** (n=3,000, deterministic, ties non-wins, vs SH, v2/808 process):
  FINAL 0.5490 ± 0.0091, VAL-PEAK **0.5777 ± 0.0090** — the starred 0.558/0.569 probes
  reproduce and are SUPERSEDED; **M4's comparator is now protocol-grade at 0.5777**
  (runs/bc_fp_v2r_soft_180k_s0). **(4) The guard head-to-head** (named anchor, now
  protocol-graded; 500/pair/orientation via the shim): Rung 2 s26 vs clone FINAL —
  orientation A 0.800, orientation B 0.514 from the sampling seat → **pooled 0.657 ±
  0.015, z +10.5 vs parity.** The deterministic-vs-sampling seat asymmetry is unusually
  large here (a soft-target BC's sampled policy is far weaker than its argmax) — exactly
  why the protocol pools orientations. Note for the board: clone-final and Rung 2 are
  near-EQUAL vs SH (0.549 vs 0.551) yet 0.657 apart head-to-head — VGC-Bench's cyclic-
  payoff caveat live in our own data; single-opponent numbers are projections. **F1
  STATUS: satisfied per its letter** — two-orientation head-to-heads vs a protocol-graded
  NAMED anchor, and the anchors move (clone 0.657, v2r 0.612, MaxBasePower +9.2), so the
  vs-SH jump is NOT SH-specific. **M2 (0.489) and M3 (0.510, the success claim) are now
  guard-backed at pooled 0.5509 (worst seed 0.5210)** — maintainer's formal blessing is
  the remaining step. ALSO: Foul Play engine smoke PASS (5/5 resolved, zero engine
  exceptions; ops note — the recorded launch lacked the full URI, it is
  `--websocket-uri ws://localhost:8000/showdown/websocket`); the 250-battle FP-vs-Rung 2
  teacher-relative read is RUNNING (prior mark: FP 0.876 over our old best RL).

- 2026-08-09 (late morning) — **F1 COMPLETE: the Foul Play (engine) read is in — FP
  0.824 over Rung 2 (206-43-1, n=250, both tallies agree, 0 engine exceptions,
  7.35 s/battle).** Context that makes it a good number: FP took **0.876** off our old
  best RL and 0.872 off the SH clone — the entity trunk closed the teacher gap by ~5
  points, and our win-take against the teacher rose 0.124 → 0.172 (+39% relative). Both
  NAMED anchors are now measured (clone h2h 0.657 pooled; FP-itself 0.824-against), on
  top of v2r 0.612 and MaxBasePower +9.2: every anchor moves in Rung 2's favor, the
  vs-SH +0.151 is general strength. **The full guard package for the M2 + M3 claims is
  on the table; maintainer blessing is the only remaining step, then the 50M
  structure-only pre-registration (branch a) is unblocked.** Session artifacts:
  results/foulplay_vs_sh/fp_vs_struct.json (+ smoke_struct.json),
  runs/bc_fp_v2r_soft_180k_s0, data/fp_all_v2r, the h2h JSONs under
  runs/showdown_sp_struct12m_s26/. Seeds: none consumed (evals only).

- 2026-08-09 (afternoon, design session) — **50M PRE-REGISTRATION DRAFTED:
  `configs/showdown_sp_struct50m.yaml` — Rung 3 step 1, STRUCTURE ONLY (Rung 2 branch
  (a)), PROPOSED / DO-NOT-LAUNCH pending two maintainer actions: the formal M2/M3
  blessing sentence, then ratification.** Handoff folded first (stub restored; STATUS's
  stale "NOT pushed" corrected — origin/main is at 93342b5, later commits local). What
  the draft settles, per the handoff's open design questions: **COMPARATOR** = Rung 2's
  own pooled final 0.5509 ± 0.0052 (a 50M run must beat the 12M version of itself);
  **CREDIT BAR** ≥ 0.5759 (se_diff ~0.0074 at 3×3000 both sides, so the flat +0.025
  binds; no escalation clause — both arms already at ladder n). **M4 READ** ≥ 0.5777
  (clone VAL-PEAK, protocol-graded, the harder of the two graded numbers; note M4 >
  credit bar, so an M4 pass implies credit), with the F1-style anchor guard mandatory
  (clone h2h 500/pair/orientation pooled + FP engine 250, 12M marks to move: 0.657 /
  0.824-against). **EVAL n** = locked 3×3000. **CADENCE** = checkpoint 500k (~24 min
  at risk/lane at 350 steps/s), eval 250k ×100 eps (200 curve points; RECORDED
  DEVIATION from DESIGN §4's "every 100k" — 500 in-run evals overpay for curve shape;
  ratifying the file ratifies the deviation). **SEEDS** 35/36/37; no new throughput
  smoke (3-wide ~350 steps/s/lane is measured from the 12M lanes). **BUDGET both ways**
  per the handoff: as-is ~39.7 h/lane ≈ 40 h wall at 3-wide; post-throughput ~15 h/lane
  IF THROUGHPUT_SPEC's ~2.6× Stage-2 projection transfers (E1-E4 still owed, D12b);
  D15(b) box substitutable at ratification. **NO NEW LEVERS**, declined explicitly: LR
  anneal (never tested in-chapter), entropy_coef 0 (H&L), pure mirror (D16a keeps the
  pool). New at this horizon: a LATE-RUN COLLAPSE criterion (>0.05 below running peak
  for ≥5M on ≥2/3 lanes → record, never intervene; final read stands) since H&L
  measured forgetting in this setting. **SECONDARY THAT DECIDES 250M** pre-registered:
  the 12M→50M delta is the purchase decision; H&L seat accounting must be resolved from
  metagrok before any 250M budget is quoted (gates the quote, not this launch). D17
  accounting: +~5 lane-days, chapter total ~8 of the 20-day cap; the M1 abandon clause
  cannot fire (M1 passed at 12M). Config body verified: agent/selfplay blocks parse-
  identical to struct12m — only seed/total_steps/cadence/run_name differ. Seeds: none
  consumed (no runs). Suite untouched (267). State: server up :8000, nothing running.

- 2026-08-09 (afternoon, cont.) — **M2 + M3 FORMALLY BLESSED — THE SUCCESS CLAIM IS
  CLAIMED.** The maintainer adopted the following sentence (drafted in-session at the
  maintainer's request, issued by the maintainer 2026-08-09, "do it"), recorded
  verbatim as the citable claim of record: **"M2 and M3 — the success claim — are
  CLAIMED as of 2026-08-09: the Rung 2 entity-trunk agent, pure from-scratch self-play
  per DESIGN §5 with SH held out of training entirely, scored 0.5509 ± 0.0052 pooled
  under the locked protocol (worst seed 0.5210 — every seed individually clears M3),
  with the F1 anchor guard satisfied in full (FP-clone h2h 0.657 pooled, Foul Play
  0.824-against vs 0.876 over the old best, v2r 0.612, MaxBasePower +9.2 — every
  anchor moves, the gain is general); per our index, which records no counterexample,
  this is the first demonstrated pure self-play agent to surpass the scripted
  benchmark in gen1 random battles — a local first in a generation where it had never
  been shown, not entry into the published field."** Consequences: the README/results
  narrative may now call M3 delivered at 12M; gate 1 on
  `configs/showdown_sp_struct50m.yaml` is satisfied (header updated in this commit) —
  RATIFICATION is the only remaining gate before the 50M launch. STATUS flipped
  guard-backed → CLAIMED. Push through this commit maintainer-authorized same message.

- 2026-08-09 (afternoon, cont.) — **50M PRE-REGISTRATION RATIFIED ("ratified",
  maintainer, 2026-08-09) — AS DRAFTED, NO AMENDMENTS.** Ratification explicitly
  covers the two flagged judgment calls: the eval-cadence deviation (250k vs DESIGN
  §4's "every 100k") and the as-is local-box budget (~40 h wall at the measured 350
  steps/s/lane, 3-wide). Both gates on `configs/showdown_sp_struct50m.yaml` are now
  DONE (blessing + ratification, same day); header stamped RATIFIED / LAUNCH
  AUTHORIZED. Rung 3 step 1 is GO: seeds 35/36/37, staggered starts, caffeinate,
  R0-8 liveness (battle PROGRESS within 15 min, ≥300 steps/s warm), launch from this
  clean committed tree in the maintainer's terminal. Next session artifacts to expect:
  three run dirs `runs/showdown_sp_struct50m_s{35,36,37}`, ~100 ckpts/lane at 500k
  cadence, eval curve every 250k. Reads after finals: locked 3×3000 pooled vs the
  0.5509 comparator (credit ≥0.5759), M4 ≥0.5777 with the mandatory anchor guard,
  12M→50M slope = the 250M purchase decision. Seeds consumed this entry: none yet
  (35/36/37 committed to the lanes at launch).

- 2026-08-09 (evening) — **README staleness confirmed + rewrite scheduled.** "Results
  so far" is three chapters stale (protocol still 1000/seed pre-D2c; best-RL still
  0.4607; no self-play chapter, no FP/clone rows, no M3 claim; narrative still cites
  r6-under-review + the human-corpus line). Maintainer decision: DEFER the rewrite to
  the 50M readout (~2026-08-10 evening) and fold finals + the blessed M3 claim + the
  r7 narrative in one pass; thereafter README stays current with plan/status as a
  STANDING directive (recorded in session memory as well). 50M lanes at ~12M steps at
  the 19:11 ops check — all green, ~387 steps/s, collapse criterion not met (1/3
  lanes; early-peak cummax artifact — credited 12M lanes had the identical flat
  shape). Ops watch continues 3-hourly.

- 2026-08-09 (night) — **CANDIDATE-LEVER TRIAGE of two external advisory lists
  (maintainer-pasted), against encoder source + record. Encoder list first: most is
  ALREADY IN v2/808** (the list audited the stale 611-dim v1: revealed-flag belief
  state + set-prior move probabilities, recharge fix = OUR D13a find, preparing,
  per-mon Reflect, status_counter scalar, PP ratio, continuous HP) or REVIEWED-AND-
  DEFERRED (22-dim history block, D13: separate bundle). **Genuinely new encoder
  gaps banked for a post-chase v3 bundle: LIGHT SCREEN missing from _VOLATILES
  (Reflect present, its special twin absent — verify poke-env populates it in gen1
  first), Disable counter + which-move, Substitute remaining HP, turn-count one-hots
  vs the shared scalar, Bide/Rage/Transform/Mimic/Mist.** All frozen behind r7's
  encoder freeze (semantics change = checkpoint invalidation + comparator
  re-baseline). **Second list (frontier game-RL): two REAL new levers that DODGE the
  freeze — training-side only, purity-clean per §5, no re-baseline (eval exercises
  the actor only): (1) PRIVILEGED/ASYMMETRIC CRITIC (AlphaStar CTDE) — critic sees
  opponent's true state during self-play, policy does not; our critic is ALREADY a
  separate stack (repo contract), and turn-1 value estimation with 5/6 opponents
  unknown at γ=1.0 terminal-only is exactly the high-variance case it targets; GAE
  bootstrap caveat noted (privileged V bounds-mismatch, accepted by the big
  projects). (2) AUXILIARY OPPONENT-TEAM PREDICTION LOSS — CE over species for
  unrevealed slots, ground truth free in self-play; forces explicit belief state.
  Each is a RUNG (one lever, own pre-registration, vs the 50M winner) — NOT an
  injection; no mid-run changes. Also already-have from that list: turn/50 + fainted
  counts both sides in the global block (summed-team-HP scalar is NOT explicit —
  matters more under DeepSets max-pool than flat MLP; goes in the v3 bundle list);
  slot-permutation invariance = Rung 2's architecture itself; obs are hand-normalized
  by design (running normalizer would break frozen comparators). Novelty caveat per
  §9: "nobody did privileged critic in Pokemon" needs the adversarial index check
  before it is ever claimed. 50M lanes untouched throughout (evals/reads only).

- 2026-08-09 (night, cont.) — **CORRECTION to the triage entry above, from the
  doc-archaeologist sweep: two claims fixed.** (1) The Light Screen gap is NOT new —
  documented 2026-07-30 (predecessor log): gen1 emits `|-start|...Light Screen` and
  poke-env 0.15.0 maps it to Effect.UNKNOWN (no LIGHT_SCREEN member) — dropped rather
  than parser-forked; Reflect parses fine. So the v3-bundle item is really "parser
  fork or upstream fix + encode," not "add to _VOLATILES." (2) PARTIALLY_TRAPPED is
  in _VOLATILES but STRUCTURALLY DEAD — measured never-firing (gen1 traps surface as
  |cant|, no |-start|; HISTORY_FEATURES_DESIGN 2026-08-07); only the Stage-0 global
  aliased-turn flag covers those turns. Also confirmed by the sweep: sleep-counter
  rescale was reviewed inert (Arm-B linear rule); toxic/confusion/disable one-hots,
  Substitute HP, Bide/Rage/Transform/Mimic/Mist = genuinely absent from the record;
  Wang's 36 poke-env commits verified 2026-08-03 — both encoder-relevant fixes
  already upstream in our 0.15.0, rest moot in gen1; obs_fidelity_check's own
  coverage gaps (crit/SE/miss/cant paths) are documented. v3-bundle list stands with
  these corrections; the two freeze-dodging rungs are unaffected.

- 2026-08-09 (late night) — **DESIGN §12 DRAFTED (D18–D20, PROPOSED — ratify at the
  50M readout): the post-50M lever queue is now durable against context loss.** D18
  privileged/asymmetric critic rung (first; evidence: loss/explained_variance plateaus
  0.56–0.59 at 15M on all three live 50M lanes — the free control curve; falsifier and
  GAE caveat pre-stated in the section). D19 auxiliary opponent-team prediction rung
  (shares D18's cross-seat plumbing; sequenced after D18's read). D20 v3 encoder
  bundle incl. the parked 22-dim history block, Light Screen parser fix, real
  partial-trap fix, counters, Sub HP, team-HP aggregates — one re-baseline pays for
  all; obs_fidelity_check coverage extension is the precondition; declined items
  recorded so they do not resurface. STATUS points at §12. Lanes untouched (~15.3M,
  all green at the 22:11-class checks).

- 2026-08-09 (22:11 ops check) — **LATE-RUN COLLAPSE CRITERION MET ON ITS LETTER —
  RECORDED PER THE PRE-REGISTRATION; NO INTERVENTION, LANES RUN TO COMPLETION.** At
  ~16.0–16.3M: s35 smoothed eval 0.528 vs running peak 0.589@3.0M (gap 0.061,
  sustained ~7M steps); s36 0.485 vs 0.607@3.5M (gap 0.122, sustained ~11.8M) → 2/3
  lanes >0.05 below peak ≥5M. CALIBRATION, recorded with it: both "peaks" are
  3–3.5M cummax artifacts of an n=100 eval series (inflation ~2·se ≈ 0.04); the
  CREDITED 12M lanes showed the same early-peak-then-flat shape and still pooled
  0.5509; and s37 is at its ALL-TIME peak right now (0.604@16.2M) — a three-lane
  collapse this is not. The genuinely soft lane is s36 (0.485, low end of its band;
  entropy still 0.27). Entropy color: s35 0.14 / s37 0.13 — below the (closed) K6
  line, policy sharpening; watch, no gate. Ops: all lanes alive, ~390 steps/s, 16M
  ckpts, server up. Final read stands regardless, per the header's own clause; this
  entry is the branch-(c) evidence trail, nothing more.

- 2026-08-10 (morning) — **THIRD ADVISORY TRIAGED (maintainer-supplied survey, the
  strongest of the three — evidence-graded, cited). Two §12 amendments landed, both
  pre-ratification:** (1) **D18 UPGRADED — the GAE bias caveat is substantially
  RESOLVED**: Baisero & Amato (AAMAS 2022) prove V(actor-obs ‖ privileged) is unbiased
  incl. for bootstrapping (Thm 5.1) while privileged-ONLY V(s) is biased (Thm 4.2);
  our sketch already used the concat form, now recorded as a BINDING constraint (the
  privileged block never replaces the actor view; honest residue noted — our obs
  approximates the theorem's full history h). (2) **D21 added**: recipe/hygiene pool —
  the known rollout/λ rung plus KL early stopping, entropy scheduling (double duty:
  exploration + mixed-strategy exploitability — matches our measured seat asymmetry),
  and PFSP win-rate-prioritized pool sampling; each its own lever, no bundling.
  Advisory's negative-results list independently corroborates our declined set
  (RND/recurrence-first/resets/exotic optimizers/PopArt/reconstruction). Two-hot value
  head stays PARKED (Arm C) with the Farebrother note attached. Staleness noted: the
  advisory audits the 0.44-plateau/611-dim era and its Stage-1 hypothesis ("exceed the
  BC-clone ceiling via entity encoder") is what Rung 2 ALREADY CONFIRMED at 0.5509.
  Its rollout figures (~4k vs 37-40k) restate the 2026-08-08 recipe advisory. Lanes
  untouched (evals/doc work only).

- 2026-08-10 (night) — **EXTERNAL ADVERSARIAL PRIOR-ART SEARCH IN: BOTH NOVELTY
  CLAIMS SURVIVE (NOT REFUTED). §9's mandatory pre-writeup search is now DONE for
  both claims** (Claude-web deep-research pass, maintainer-supplied; archived with
  an UNVERIFIED-citations banner at prior_work/RESEARCH_2026-08-10_prior_art_and_
  levers.md). Scope: arXiv, ICML/NeurIPS/ICLR/AAMAS/IEEE-CoG/RLC, GitHub, Smogon,
  PokeAgent Challenge retrospective (arXiv 2603.15563) incl. participant appendix.
  **Claim A (no privileged/asymmetric critic in Pokemon RL): NOT REFUTED** — Metamon
  is shared-trunk symmetric, VGC-Bench symmetric twin nets, H&L/Wang symmetric PPO.
  **Claim B (no pure from-scratch self-play agent in gen1): NOT REFUTED** — H&L is
  gen7; Wang gen4 AND test-time MCTS; Metamon + both PokeAgent gen1 finalists are
  human-replay-bootstrapped; VGC-Bench's SP arm is gen9 doubles. **BINDING PHRASING
  RULE for all writeups: "no documented instance found," never "proven first."**
  Field calibration for the README narrative: strongest documented gen1 agents are
  Metamon-family imitation+offline-RL at ~80% GXE (SynRL-V2 79.9%, PokeAgent gen1
  champion 80.35%, TaurosEnsemble has held #1 on the human gen1OU ladder) — our lane
  is orthogonal (purity), not competitive with that number; ps-ppo's ">85% vs SH"
  claim explicitly down-weighted by the search (unverified + BC-phase). **§12
  amendments landed:** D18 novelty-check marked DONE + refs + cautionary null
  (effect size not guaranteed; never tested at γ=1.0 terminal) + start-compact
  privilege option; D19 gains the actor-side-gradient caveat (never bundles; partial
  redundancy with D18 — re-scope if D18 credits); D21 λ advice AMENDED to a sweep
  {0.95, 0.98, 1.0} (short-episode terminal-only regime reverses the low-λ argument;
  Alpha-Mini precedent) + episodes/update currency (~30 → 100–300 target) + Wang's
  controlled LR-anneal ablation noted; **NEW D22 — plateau diagnostics (Stage 0)**:
  five measurements on the existing 50M artifacts (EV, entropy, WEIGHT-NORM
  trajectory, dormant/effective-rank, exploitability proxy via fresh best-response)
  with a pre-stated decision rule routing to D18 vs regenerative-regularizer vs
  PFSP/R-NaD. Finals runner armed (results/struct50m_finals/), lanes in final steps.

- 2026-08-10 (23:11, autonomous overnight readout) — **RUNG 3 STEP 1 (50M, STRUCTURE
  ONLY) READ OUT: CREDIT PER THE RATIFIED BAR — pooled 0.5802 ± 0.0052 vs 0.5509,
  delta +0.0293, binomial z +3.99 — WITH A SEED-FRAGILITY CAVEAT THE MAINTAINER MUST
  ADJUDICATE.** All lanes completed 50M; finals on ckpt_050000000.pt each, 3×3000,
  sign cross-check exact on all six evals. **Seeds: s35 0.6593 / s36 0.5727 / s37
  0.5087 — spread 0.151, 3.2× the 12M run's 0.047.** The ratified header's explicit
  credit bar (pooled ≥ 0.5759, binomial se_diff 0.0074) is MET. BUT the repo-standing
  credit line (DESIGN §8: se_diff = larger of binomial and seed-clustered) was NOT
  restated in the header: seed-clustered se_diff ≈ 0.046 → z ≈ +0.63 — the scale
  delta is NOT seed-robust. Recorded honestly: the header's letter credits; the
  standing rule would not; maintainer adjudicates which governs the narrative.
  **M4 (≥ 0.5777): met on its letter at 0.5802, margin +0.0025 ≈ 0.3σ — NOT
  decisive; do not claim without adjudication + full guard.** ANCHOR GUARD partial:
  clone-val-peak h2h on the median seed (s36 final), 500/pair/orientation pooled =
  **0.643** (A 0.804 / B-take 0.482 — the measured seat asymmetry again), z +9.4 vs
  parity — the anchor moves, the gain is not SH-specific; ~flat vs 12M's 0.657
  (cyclic-payoff caveat stands). FP ENGINE read PENDING (needs foul-play env; morning
  task, ~15 min: smoke 5 then 250 with the full websocket URI). **BEST-CKPT
  SECONDARIES (selection caveat recorded): 0.6330 / 0.6193 / 0.5937, pooled 0.6153 —
  every lane's best ≥ 0.59 at n=3000;** s36/s37 finals sit 0.047/0.085 BELOW their
  own bests → the checkpoint-selection-policy question (2026-08-10 morning discussion)
  is LIVE: val-peak-re-graded as co-primary belongs in the next pre-registration.
  Curve note: s35 surged late (5M-mean 0.606 at 41M) and its final graded 0.659 —
  still-rising at 50M on 1/3 lanes; s37 flat-lined ~0.50 from 17M. **250M secondary
  (the purchase decision): slope +0.0293/4.2× — positive, seed-fragile; NOT
  auto-bought; feeds D22 diagnostics + seat accounting + maintainer call.** D22 is
  now doubly motivated: explaining the s35-vs-s37 divergence (weight norms, entropy,
  exploitability probe) is exactly its job. Eval-cost note for the next header:
  3000-battle evals took ~2.5-4 min each on the idle box (~25 min for all six) — the
  n=1000-in-training-eval proposal costs even less than estimated. Artifacts:
  results/struct50m_finals/ (6 finals/bests + 2 h2h JSONs + runner.log). Seeds
  consumed: none (evals only). Next: README rewritten this session per standing
  directive; §12 ratification, FP engine read, credit adjudication, push = morning.

- 2026-08-11 (morning) — **50M CREDIT ADJUDICATED (maintainer, "adopt", verbatim):
  "Adjudicated 2026-08-11: the 50M CREDIT stands per the ratified header's explicit
  bar — a pre-registration binds in both directions, and tightening the rule after
  seeing the data is as post-hoc as loosening it. The seed-fragility (spread 0.151,
  seed-clustered z +0.63) is recorded as a named weakness of the credit, not a
  footnote: the scale effect is real on the registered read but unreplicated at seed
  level. M4 is NOT claimed (+0.3σ margin, guard incomplete). Process fix, binding:
  every future pre-registration header restates the full §8 credit line verbatim,
  including the larger-of se_diff clause."** Consequences: standing best = 0.5802
  (50M s35/36/37, carried with the named weakness in every narrative use); M4 stays
  unclaimed; the process fix is codified in CLAUDE.md conventions this commit.
  Remaining morning items: FP engine read (completes the guard), §12 ratification,
  push.

- 2026-08-11 (morning, cont.) — **DESIGN §12 RATIFIED (maintainer, "ratify 12 and
  push"): D18–D22 BINDING, with the recommended sequencing — D22 plateau diagnostics
  first, then D18 privileged critic, then D19/D21 as singles; D20 post-chase.** Push
  through this commit maintainer-authorized in the same message. FP anchor-guard
  status at this entry: smoke PASS (5/5, tallies agree, 0 exceptions, seat took 3/5
  n=5); 250-battle read RUNNING (~185/250 at 07:56), folds in on landing.

- 2026-08-11 (morning, cont.) — **FP ENGINE READ IN: ANCHOR GUARD COMPLETE FOR THE
  50M READ. FP takes 0.812 off the 50M median seed (203-47, n=250, 0 ties, 250/250
  resolved, 6.46 s/battle)** vs 0.824 off the 12M agent and 0.876 off the old best —
  the engine's edge HOLDS (Δ −0.012, within n=250 noise), and our win-take rose
  0.172 → 0.188. Guard package for the 50M credit: clone-VP h2h 0.643 pooled (z +9.4
  vs parity) + FP 0.812-against — anchors hold or improve; the small vs-SH gain
  (+0.029) shows the matching signature at the anchors (no regression, no
  SH-specific jump). **M4 remains UNCLAIMED per the 2026-08-11 adjudication** — the
  guard-incomplete leg is now closed but the +0.3σ margin leg stands on its own.
  Artifacts: results/foulplay_vs_sh/{smoke_struct50m,fp_vs_struct50m}.json + logs.
  With this, every measurement attached to the 50M read is closed: finals, best-ckpt
  secondaries, clone h2h, FP engine. Chapter state: M1-M3 claimed at 12M; 50M credit
  stands (seed-fragility named); §12 ratified — NEXT WORK IS D22 THEN D18.

- 2026-08-11 (evening) — **D22 PLATEAU DIAGNOSTICS: READS 1–4 IN (offline, on the
  50M artifacts); READ 5 PRE-REGISTERED AND HANDED OVER. Provisional routing per
  the §12 rule: D18 FIRST, AS QUEUED.** Note first: the lanes' history.csv were
  stale (extracted Aug 10 19:11, truncated ~45M) — re-extracted all three to 50M.
  READ 1 (EV): flat 0.56–0.59 on all lanes from 5M through 50M (late slopes
  ±0.006/10M) — the D18 evidence line holds unchanged at 4.2× the horizon. READ 2
  (entropy): NOT collapsed — 50M levels 0.255/0.317/0.208 (s35/s36/s37); the
  ~0.13–0.16 dip near 12–16M (the 22:11 ops-check readings) RECOVERED on s35/s36.
  K6 never fired. READ 3 (weight norms, 100 ckpts/lane): monotone growth, never
  flattening — actor ×2.34–2.46, critic ×2.25–3.00 (500k→50M), species embeddings
  fastest (×5.6–6.6) — the Juliani & Ash plasticity correlate is present in ALL
  lanes including the still-improving one. READ 4 (dormant/rank, on each lane's own
  final-policy mirror obs, 5.8–7.4k decisions, results/d22/obs_s3*.npz): actor
  ctx_net.1 dormant fraction (τ=0.025) climbs 27%→84–88% on s35/s36 (s37 30–52%),
  scorer 54–74%; ctx feature srank99 collapses ~250→33–54 of 384 (actor) and →7–11
  (critic). **Flat EV + low effective rank — §12's representation/optimization
  clause — FIRES CLEANLY on all three lanes.** BONUS (s35 surge vs s37 flatline):
  s37 shows a SUSTAINED actor-side grad pathology from ~20M — pre-clip grad norm
  median 1088 over ≥30M (healthy lanes 1.4–1.7 median with a 10–14% >100 tail),
  grad_clip_frac pinned at 1.0000 from ~25M, post-clip Adam mass in actor
  species_emb/field_net where healthy lanes put it in critic/head — its critic
  STALLS (drift 5.2 over 25M→50M vs 34+ for s35/s36, norm pinned at 102.3) and its
  eval slides 0.616@16M→0.490. s35 took ONE transient spike (bin 15M, 447) and
  recovered; still rising at its 50M final (peak=final). s36 intermediate (spike at
  45M; early 0.626@3.2M peak is the known n=100 cummax artifact). The 50M read's
  seed-fragility maps onto per-lane optimization health, not luck-of-the-final.
  ROUTING (provisional; read 5 pending): representation clause fires → **D18 first,
  as queued**; plasticity clause PARTIAL (norms rise everywhere but s35's rising
  win rate confounds "flat win rate") → regenerative L2-toward-init NAMED
  next-after-D18, and it jumps the queue if D18's lanes reproduce an s37-class
  blowup; exploitability clause CANNOT fully fire (entropy half already failed) —
  read 5 quantifies the BR half as evidence weight. INFRA LANDED: frozen-checkpoint
  opponent seam (`selfplay.opponent: <path>.pt` → one-member frozen pool, learner
  never pushed; rl/train.py::_frozen_checkpoint_pool) + 2 tests (suite 269 green);
  live smoke on seed 99 trained 4096 steps vs frozen s36-50M, fingerprint clean;
  four scripts (scripts/d22_*.py); READ-5 PRE-REG configs/showdown_br50m_s38.yaml
  (fresh entity learner vs frozen s36-50M, 6M steps, seed 38; primary = pooled
  two-orientation h2h 1000/orientation, thresholds pre-stated in the header;
  launch = ratification). Side-read, noise-level (n=200): deterministic seat vs its
  own sampling twin 0.565/0.480/0.560. Artifacts: results/d22/ (binned
  trajectories, weight_norms, dormant, effective_rank, adam_grad_scale per lane).

- 2026-08-11 (night) — **D22 READ 5 IN — EXPLOITABILITY PROBE: THE 50M EQUILIBRIUM
  IS ROBUST AT THE PROBE BUDGET. D22 IS CLOSED; ROUTING FINAL: D18 FIRST, AS
  QUEUED — now unconditional.** Lane showdown_br50m_s38 (launched by maintainer =
  header ratified, 2026-08-11): fresh entity learner vs FROZEN s36-50M final, 6M
  steps, 482–503 steps/s solo, fingerprint clean (git_dirty false @ a1cd882), no
  incidents. PRIMARY (pre-stated): pooled two-orientation h2h 1000/orientation, ties
  as non-wins — **BR 0.479 (orient A, BR deterministic) / 0.474 (orient B, derived;
  s36 took 0.522) → POOLED 0.4765 ± 0.0112 < 0.55 → "equilibrium robust."** The
  exploiter's training curve confirms shape: 0.30→~0.45 in the first 1M, then
  plateau, 0.488 (sampling both sides) by 6M — a dedicated 6M attacker never
  reached parity with the frozen target. §12's exploitability clause is dead on
  BOTH halves (entropy 0.21–0.32 ≠ collapsed; BR did not win easily). With reads
  1–4, every routing signal now agrees: the plateau is a REPRESENTATION/CRITIC
  ceiling (flat EV 0.56–0.59, critic feature srank99 7–11 of 384), not an
  exploitability ceiling and not (yet) a binding plasticity ceiling → **D18
  privileged critic is next work; regenerative L2-toward-init stays named
  next-after-D18** (jumps if D18 lanes reproduce an s37-class grad blowup).
  SECONDARY, recorded as color (in-training n=100 evals, NOT locked protocol): the
  BR-trained policy scores ~0.56 vs SH (last-4 mean 0.562, max 0.64) after only 6M
  steps against ONE frozen opponent — near the 50M pooled 0.5802; dense-signal
  observation for any future curriculum thinking, no claim attached. Ops color:
  probe end-to-end (launch→verdict) ~3.6 h; h2h evals ~2 min/1000 on the idle box.
  Artifacts: runs/showdown_br50m_s38/, results/d22/br38_vs_s36_orient{A,B}.json.
  Seed 38 SPENT.

- 2026-08-11 (late night) — **D18 PLUMBING COMPLETE IN ONE SESSION (est. 2–3
  evenings): privileged critic landed end-to-end, suite 279 green, live-smoked;
  PRE-REGISTRATION DRAFTED (configs/showdown_sp_priv12m.yaml) — awaiting
  ratification, then a 3-lane overnight launch (seeds 39/40/41, ~9 h wall).**
  Three commits: (1) cedd6fb env side — `privileged_block()` slices the opponent
  seat's own-side state (6 mon blocks + active extras + 4 move blocks + 10 ids =
  408 dims) out of THAT SEAT's own embed_battle encoding — zero new fill code,
  bit-identical semantics by construction; ShowdownEnv(privileged=True) emits it
  as info["privileged"] at every decision point from battle2; live test proves the
  block carries hidden info (all 6 opponent mons populated vs <6 revealed in the
  actor's view). (2) 6d21064 collection+critic — RolloutBuffer stores per-row
  privs/next_privs (masks precedent); _vector_loop captures/rotates/reset-merges
  info["privileged"] exactly like masks and hands a 10-tuple to update() (8-tuple
  still means non-privileged); PPOAgent(privileged_dim=408): critic input =
  actor-obs ‖ priv — the actor NEVER widens (Baisero & Amato V(h,s), binding);
  env-flag/agent-flag mismatch dies at first update in both directions (tested).
  EntityDeepSetsNet(privileged_dim=): value-only (policy head refuses it), priv
  tokens through the SAME mon/move subnets + embeddings, ctx pooling 5→8 entity
  slots (+147k critic params; actor param count and R0-2 untouched). (3) live
  smoke seed 99: 4096 steps of pool self-play with the privileged critic — finite
  losses, EV 0.22 by update 4. PRE-REG HEADER carries: full §8 credit line
  VERBATIM incl. larger-of (binomial vs seed-clustered) se_diff clause (the
  2026-08-11 process fix — bar 0.5759 vs Rung 2's 0.5509 comparator); val-peak
  co-primary RECORDED-NOT-CREDIT-BEARING on n=1000 in-training evals every 500k
  (both wishlist items adopted); EV-vs-control secondary + critic-srank read;
  §12's falsifier verbatim (EV up + wr flat = kill); the +147k critic-capacity
  confound disclosed with the capacity-matched control NAMED but not run; D22
  WATCH gate (s37-class grad blowup, median >100 for 3 consecutive 1M bins →
  regenerative-L2 jumps the queue at readout, record-only). Seeds 39/40/41
  assigned here; 42+ free after launch.

- 2026-08-11 (pre-launch review) — **D18 REVIEWED BY 3 INDEPENDENT OPUS AGENTS
  (data path / critic math / theory+pre-reg) BEFORE LAUNCH: ZERO CRITICAL FINDINGS,
  ZERO CODE CHANGES — the reviewed SHAs (cedd6fb, 6d21064) launch as-is. Header
  revised instead (this commit).** Strongest verifications, all empirical: (1)
  _priv_features output BITWISE EQUAL to the reference own-side tokenization; (2)
  621 live decision points (44 through the wait pump) — zero battle2-staleness or
  cross-seat mismatches; probe of the REAL _vector_loop over adversarial episode
  interleavings — zero (obs,priv) alignment violations; (3) K3 bit-identity at
  privileged_dim=0 vs the parent commit incl. RNG stream position, both trunks; (4)
  forward hooks: critic input width ∈ {1236} only, actor ∈ {828} only, act() = 0
  critic calls; checkpoint cross-loads fail loudly both directions; gymnasium 1.3
  partial-reset placeholder semantics confirmed from source. FINDINGS FOLDED INTO
  THE HEADER (no code): (a) OPERATIVE BAR — comparator seed spread (s=0.0260)
  alone forces the larger-of bar to ≥0.5809 even at zero D18 spread, ~0.593 at
  Rung-2-like spread; 0.5759 is the binomial letter only. Powering disclosed
  (governing rule wants Δ~+0.042 at 3 seeds); RECORDING RULE pre-stated for the
  +0.025..0.042 band ("letter-met, seed-fragile, NOT credited"); 5-lane option
  (seeds 39-43, bar ~0.583, +0.8 lane-days) put to the maintainer at ratification.
  (b) FEATURE-CLASS CONFOUND, previously missed: the control critic's move subnet
  + move embeddings get ZERO gradient (value stack never consumed move tokens) —
  D18 wakes them, so effective capacity delta is ~189k not 147k, and the rung adds
  the critic's first MOVE features alongside hidden state; the capacity-matched
  control covers both (zeroed priv still flows through move_net); same-seed
  init-match for that future arm is impossible (widened critic shifts the RNG
  stream — measured). (c) srank secondary scoped: BOTH d22 scripts need post-run
  adaptation (priv-carrying tapes + privileged_dim build); unadapted harness
  raises, cannot silently mis-read. (d) co-primary selection-procedure confound
  named (24 vs 120 draws; selected on return_mean). (e) aliased seat-B turns:
  ~1-3% of rows zero priv move blocks/ids with the vec[5] cause flag outside the
  slice; disclosed, v2 named. (f) pool memory ~25.5 MB/snapshot (~510 MB/lane);
  eval-env compute-and-discard noted (time/eval_sec not like-for-like vs control).
  Closed during review: eval-with-privileged path had never fired — smoked same
  evening (3 evals, no incident). Review cost ~506k agent tokens, ~45 min.

- 2026-08-11 (night, launch record) — **D18 LAUNCHED: 5 lanes (seeds 39-43), staggered
  ~75 s apart, nohup+disown+caffeinate from the maintainer's "ratify 5 and launch"
  (agent-launched under the recorded long-job pattern; per-lane R0-8 verified at
  launch: process alive, wandb growing ~130-160 KB/30 s on every lane, git_dirty
  FALSE on all five meta.yaml @ c6e6d87, both privileged flags in every config
  snapshot; first updates completed without tripping the mismatch guard).** 5-lane
  bar arithmetic CORRECTED at ratification (the option line had applied sqrt(3/5)
  to both arms; comparator stays 3-seed): floor 0.5809 unchanged, ~0.589 at
  Rung-2-like spread — in the header at the PRIMARY block. Box is 14-core/10-perf;
  350-390 steps/s band was 3-wide, 5-wide expected lower (R0-8 record-and-continue
  covers it). Fleet monitor armed (1M milestones + exit/crash). ETA ~9-13 h.
  Readout protocol at completion: 5x3000 finals + val-peak re-grades (locked, both
  env vars) -> larger-of credit line -> recording rule if in the unclaimable band;
  d22 scripts need priv adaptation before the srank secondary.
- 2026-08-11 (~19:15, mid-run health check @ ~3.3-3.4M) — **D18 FLEET GREEN 5/5; launch
  clock corrected; overnight watch re-armed.** Launch was actually **16:03 EDT**
  (wandb dir stamps 20260811_1603xx-1607xx), not the "~23:00" in the handoff/launch
  record — at measured ~300 steps/s/lane pooled, **finals ETA ~03:30-04:30 EDT
  2026-08-12** (not 09-10h). Gates at ~3.3M: R1 anchor 0.970-0.977 all lanes (PASS);
  K6 entropy 0.26-0.38 (clear); R0-6 mean ep length 30.9-33.1 ≤ 40 (PASS; rare
  turn-1000 auto-tie stalls appear as 'bigerror' log warnings, ~tens of battles/lane,
  don't move the mean); D22-watch grad_norm median 0.88-1.0 in every 1M bin, all
  lanes (QUIET — no s37-class blowup); R0-8 steps/s s39 341 / s40 346 / **s41 270
  (under the 300 band → record-and-continue per header; above the 250 stop line)** /
  s42 305 / s43 317. EV at ~3.3M: s39 0.580, s40 0.556, **s41 0.640**, s42 0.539,
  s43 0.542 vs control plateau band 0.549-0.561 — separation clear on s39/s41,
  within-band on s40/s42/s43; more mixed than the handoff's 3M note (0.57-0.61 on
  priv lanes). In-training eval/win_rate (n=1000, not the read): 0.477-0.593.
  Ops: 13h `caffeinate -is -t 46800` started (lanes' own caffeinate exits with them
  — box must stay awake for the readout); session monitor re-armed (per-lane
  done/died/stall, fires the readout when all 5 terminate). Handoff folded, stub
  restored this commit.
- 2026-08-11 (evening, mid-run offline work) — **d22 scripts ADAPTED for the D18
  srank secondary (9c5ccc7; scoped in the priv12m header, zero rl/ changes, lanes
  untouched).** collect: `privileged` auto-detected from the ckpt config, block
  saved per decision as `priv`; rank: `--lanes/--steps/--run-prefix/--obs-prefix`,
  critic built widened from ckpt `privileged_dim`, forwarded obs ‖ priv; priv ckpt
  + priv-less npz raises loudly. VERIFIED offline: defaults reproduce the D22 read
  exactly (s35@500k actor srank99_ctx 243 / PR 1.7118, critic 252 / 2.1805 — match
  recorded CSV to 4 decimals); widened path loads the live s39@3.2M ckpt and
  probes; plain-828-into-widened still raises. Dormancy in a priv critic counts
  BOTH subnet passes (obs + priv tokens); the mon rank read keeps the first
  (observed) pass for D22 comparability — documented in the docstring. D18
  invocation uses `--out results/d18` (must not clobber results/d22 CSVs) and
  runs ONLY with the fleet down (collect derives usernames from cfg.seed — the
  same-seed collision landmine, now warned in the docstring). Readout eval driver
  staged at ~/.claude/jobs/62d4fa41/tmp/d18_readout_evals.sh (2 batches of 5
  concurrent 3000-battle evals, distinct seeds per batch).
- 2026-08-11 (late evening) — **H&L SEAT ACCOUNTING RESOLVED (the named gate on any
  250M quote, per the 50M pre-reg): their learner trains on BOTH seats of every
  battle.** Subagent deep-read of the metagrok clone + paper PDF. Proof: Algorithm 1
  "update ... using the 2m self-play matches as training data" (paper, Sec. III.B);
  simulate_worker.py:48-53 writes both seats' trajectories per battle;
  integrated_rl.py:327-329 one-seat filter requires an expt `player` key the paper's
  run config (expts/01.json — QuadCapacity, 500 iters, 7680 matches/iter) does not
  set; learner.py:130 rollup glob sweeps both files. The paper publishes battles only
  (3.84M); prior_work's "≈2-3×10⁸ decisions" was a reconstruction and is BOTH-SEAT;
  per-seat ~0.96-1.5×10⁸ (~1.15×10⁸ @ ~30 dec/seat/battle — the 25-40 band is the
  only residual uncertainty, gen7). Complications recorded: PPO epochs 6 (reuse ≠
  experience), no cross-iteration replay, errored battles re-simulated, result rows
  dropped, RL-meta +384k battles extra, both-seat batches return-balanced per battle
  (ours are not). CONVERSION: 250M ours ≈ 1.1× their learner-consumed diet / ≈ 2.2×
  their per-seat env experience; their run ≈ 19× our 12M learner-consumed, ≈ 9.6×
  per-seat. Full detail folded into prior_work/README.md (H&L entry). Also this
  evening: maintainer-authorized push landed f27bea2..b53eac3 on origin/main.
- 2026-08-11 (late evening, cont.) — **DESIGN §13 DRAFTED (PROPOSED): the 250M budget
  memo** — discharges Rung 3's metagrok budget precondition (seat accounting, above)
  and replaces its stale "5.4 days/lane" cost line with measured-rate arithmetic:
  250M×3 at 3-wide ≈ 25 lane-days (exceeds the whole D17 20-lane-day trigger; ~2.5×
  the ~9-10 remaining), solo ≈ 7 (fits, but single-seed = weak under our own 50M
  adjudication), post-throughput IF ~2.6× transfers ≈ 9.5 for 3 lanes (fits) — so
  **E1-E4 (D12b) is the gating item for any in-cap 3-lane 250M**. Open question
  surfaced for ratification: whether rented compute counts against the lane-day
  trigger. Pre-stated sequencing: no 250M pre-reg before a credited lever at 50M +
  E1-E4 measured + the cap/rent question answered. Also: CLAUDE.md landmine fixed —
  eval_checkpoint.py has reported env-supplied win_rate since 2026-08-05 (the "raw
  returns only" clause was stale).
- 2026-08-11 (night, pre-readout tooling) — **D18 grader + E4(b) width patch landed
  (f55f0a3, f4ce757).** scripts/d18_grade.py computes the pre-registered credit line
  mechanically from the readout JSONs: larger-of rule at EXACT arithmetic (the
  header's 0.5809 floor displays rounded; true clustered floor 0.58091 — the script
  credits on the rule, not the rounding), R0-4 win_rate==wins_from_returns hard-fail,
  recording-rule verbatim, branch (a)/(b)/(c) routing, co-primary recorded-only;
  verified on synthetic boundary/band/null/mismatch JSONs. showdown_throughput.py
  grew --net {tiny,mlp512,entity} per THROUGHPUT_SPEC E4(b): tiny default preserves
  historical shape reads, entity = credited Rung 2 trunk (refuses OBS_DIM != 828),
  net stamped in every header. E1-E4 remaining tooling (scripts/profile_collect.py +
  the POKEMON_RL_PROFILE block in _vector_loop) is rl/-touching and DEFERRED until
  after the readout evals run on the reviewed SHAs (3-agent review: zero code
  changes); the measurement evening still needs the idle box regardless.
- 2026-08-12 (early morning, THE D18 READOUT) — **D18 PRIVILEGED-CRITIC RUNG: NULL,
  AND KILLED BY ITS OWN PRE-STATED FALSIFIER.** All 5 lanes completed 12M clean
  (~10.6 h at 5-wide, ~300-324 steps/s warm; R0-8 recorded: s41 dipped to ~270 at
  3.3M, recovered). **PRIMARY (locked, 5×3000, both env vars, R0-4 exact-agree on
  all 10 evals): s39 0.5610 / s40 0.5477 / s41 0.4740 / s42 0.5623 / s43 0.5370 →
  pooled 0.5364, Δ −0.0145 vs comparator 0.5509.** Spread s=0.0364; clustered
  se_diff 0.0221 governs (binomial 0.0066); z = −0.65 — statistically flat, and
  |Δ| < 0.025 so not letter-negative either. **Branch (b) NULL.** CO-PRIMARY
  (val-peak re-grades, recorded-not-credit-bearing): 0.5587/0.5517/0.5200/0.6363/
  0.5523 → pooled 0.5638 (+0.0129); within-lane final→peak gap +0.0274 (selection
  n=1000 on eval/return_mean, 24 evals — its own confound block applies).
  **FALSIFIER FIRED (the epitaph): EV rose on EVERY lane** — per-2M means climb
  ~0.50 → 0.60-0.62, final-1M 0.597-0.621, clearly above the 12M control plateau
  0.549-0.561 — while win rate stayed flat: the header's verbatim kill clause
  ("critic fits information the policy cannot exploit; advantage signal degraded —
  KILL THE RUNG, do not tune around it"). The named mechanism candidate (advantage
  scale shift from a sharper V) is recorded here, not rerun. **SRANK SECONDARY
  (adapted d22 scripts, results/d18): the privileged input did NOT de-collapse the
  critic** — critic ctx srank99 at 12M: s39 14 / s40 14 / s41 25 / s42 17 / s43 7
  of 384 (50M controls: 7-11); the critic fit MORE variance (EV up) through an
  equally collapsed representation. Actor srank fell too (92/26/9/85/73 by 12M;
  s41's 9 is the blowup lane). Collapse is training-dynamics-intrinsic, not
  information starvation — regen-L2's thesis, strengthened. **D22-WATCH: s41
  reproduced an s37-class escalating grad blowup** — bin-medians 6.92 → 23.55 →
  61.97 → 1607.5 over the final 4M, worst final (0.4740 vs its 0.5200 val-peak);
  the pre-stated trigger (median >100 ×3 consecutive bins) is NOT met by letter
  (one bin >100; the 12M horizon truncated the escalation) — moot for queue order,
  branch (b) makes regen-L2 next regardless, but it is now 2-of-8 entity lanes
  with the phenomenon. K6: window closed pre-6M clean; late entropy dipped to
  0.155 (s42) / 0.172 (s41), after the window — recorded. Attribution footnote
  (confound 1): the EV rise is not separable between hidden-state and the critic's
  first move features; moot post-kill. **NEXT, per branch (b): regenerative-L2
  pre-reg (D22's named runner-up); D19 stays as-queued.** D17 accounting: +~2
  lane-days, chapter ~12-13 of 20. Artifacts: results/d18/ (10 eval JSONs + 5 obs
  tapes + dormant/effective_rank CSVs, gitignored). Grader output verbatim in
  results/d18/ via scripts/d18_grade.py; seeds 39-43 SPENT.
- 2026-08-12 (early morning, cont.) — **E1-E4 MEASUREMENT EVENING RUN AND CLOSED
  (D12b discharged; box idle post-readout; runner 0fb72eb, artifacts
  results/throughput/).** E1 (num_envs sweep 1-16, rollout×envs held at 1024, 30k
  steps each): steps/s 523-550, spread 1.05× → **FLAT — serialization CONFIRMED,
  num_envs closed as a lever forever; Stage 2 (async collector) is the whole
  answer.** Solo entity-trunk baseline ~540 steps/s. E2: reset share of collect
  0.050 — at the ignore boundary; concurrency absorbs it, no battle-creation
  pipelining needed. E3 (8k instrumented steps): embed 133 µs/decision (spec
  predicted 158), mask 8 µs, opponent 368 µs, race_get 408 µs/call → **race_get
  share of vector step 0.54 — MIDDLE BAND: the residual is ~half idle wait, half
  CPU; concurrency relief is partial, spec's §5 ceiling is cut accordingly.** E4a:
  node median **7.6% of one core** (max 15.7%) during a 1-lane run → server has
  ~10× headroom beyond the spec's own bar; one server suffices, network:1
  contingency dead. E4b (in-flight sweep, --net entity, the trustworthy-absolute
  config): 879 dec/s at K=1 → **1218 at K=8, flat to K=64 (~1240 max), knee at
  K=8; inference share 0.40 at batch-1** → the Stage-2 build target is K≈8-16
  concurrent battles/worker and batched inference has ~2× further headroom. NET
  FOR §13: a single async worker at entity width already measured **~1240 dec/s ≈
  2.3× the solo training loop** — Stage 2's ~2.6× projection survives contact at
  the shape level; 250M×3 post-Stage-2 lands ~7-8 lane-days (fits the remaining
  cap). The E1-E4 gate on the 250M quote is DISCHARGED.
- 2026-08-12 (morning, D23 DRAFTED under the new design process) — **REGENERATIVE
  L2-TOWARD-INIT pre-registration drafted, 2-agent-designed and 2-agent-reviewed
  (maintainer instruction 2026-08-12: design decisions get 2 Opus agents + reviews);
  configs/showdown_sp_l2init12m.yaml — DRAFT, NOT RATIFIED, lever NOT built.**
  DESIGN (agents: mechanism-first / read-first): DECOUPLED post-step decay toward
  θ₀ (AdamW-style), NOT a loss term — a coupled L2-init under Adam is measurably a
  dormancy-triggered soft reset (≈ the banned ReDo family; per-block λ_match spans
  ~1200×), contaminates grad_norm/clip comparability, and is eps-sensitive.
  Coverage: both nets minus LayerNorm (approximate-gauge argument; consequence
  drawn: global-norm stats ~half inert → all functional reads on LN-free blocks).
  λ = 1/(lr·N) = 0.02 closed-form (one anchor e-fold/budget; instantaneous-drift
  alternative rejected at 15× seed spread); per-step constant at other budgets.
  READ: 5 lanes, locked primary vs frozen 0.5509, larger-of credit line with bars
  precomputed; power honesty PUBLISHED IN THE HEADER (P(credit|+0.02) ≈ 0.08;
  best-case mechanism story pre-computes as NULL) → mechanism co-primary = critic
  srank de-collapse (≥40 of 384), well-powered at 12M. REVIEWS (adversarial /
  decision-quality): every core number REPRODUCED exactly (λ, N=187,488 counted
  from s26's history, all bars, power sims, D18 gaps, budget); 1 BLOCKER — the
  mechanism criteria were graded against s35-37 while R0-9 produces s26-28 curves
  (tunable-after-the-fact hole; two companion thresholds sat INSIDE the s35-37
  control range) — fixed: R0-9 freezes s26-28 numbers pre-ratification, thresholds
  as fractions of control mean, partition-complete (dead zone removed). Other
  majors fixed: falsifier scoped to "closed AT 12M for this chapter — budget
  decision, not refutation" (the old family-kill was a Type-II-driven kill
  contradicting the header's own horizon confound); VOID branch single-action
  (D19 next, stronger-λ queued behind, asymmetry vs NEGATIVE justified); revised
  D23-watch trigger honestly scoped to 12M (it retro-fires on s35/s36's RECOVERING
  50M transients — 50M carry needs a recovery clause); "θ₀ not regenerable" was
  FALSE (deterministic per (seed,config); D18's warning was cross-config) → one
  theta0.pt/run + hash, load guard scoped to training path (a shared-loader guard
  would break the locked eval); R0-2 cannot detect rider pollution → R0-2b
  state_dict-keys assert; smoke calibration replaced by deterministic identity
  unit tests (a 1.9-3.8% n=1 deviation verifies nothing); SnapshotPool θ₀
  exclusion dropped (needed a shared-class deepcopy override risking R0-3; +90
  MB/lane accepted instead); baselines labeled (500k- vs θ₀-relative had mixed);
  dormancy quoted at named threshold (tau100 0.81-0.86, 2-of-3 seeds); eps/λ-range
  numbers corrected (~6-41%, ~1200×); K6/R1 restated for T lanes; lane-failure
  rule added; R0-11 grader pre-commit (R0-4 check carried). DECISION-QUALITY
  HEADLINE (new lead question Q1): at IDENTICAL cost, 3 treatment + 2 fresh
  comparator lanes DOMINATES 5+0 (P(credit|+0.02) 0.180 vs 0.078; the comparator's
  sd rests on 3 numbers, 95% CI [0.0135,0.163]; comparator lanes are a permanent
  chapter asset for D19+) — maintainer decides 3+2 / 4+1 / 5+0. Q2: build approval
  (~1 evening). Q3: LR-anneal ordering (considered, declined by routing, maintainer
  may override). Paired-init declined; old Q4/Q5 resolved in-header. NOTHING
  LAUNCHES until ratification + build + R0-9/R0-11 complete.
- 2026-08-12 (morning, D23 RATIFIED) — **Maintainer ratified D23 (verbatim: "q1 -
  3+2 / q2 - I approve the build, use 2 opus sub agents to help / q3 - whatever you
  recommend"). Q1 = 3+2 ADOPTED (treatment 44/45/46, fresh comparator lanes 49/50 on
  struct12m verbatim at its original 100k/100 cadence; bars become formulas at
  readout over the 5-seed comparator; frozen 0.5509 stays the historical baseline).
  Q2 = build approved, 2-Opus build. Q3 = as-routed per recommendation (D23 now, LR
  anneal stays D21; anneal evidence is probe-era vs-SH-arm, and the new comparator
  lanes improve any future D21 read). Launch stays gated on build + R0-9 (control
  curves frozen into the header) + R0-11 (grader committed).**
- 2026-08-12 (mid-morning, D23 BUILT + ALL LAUNCH GATES CLEARED) — **2-Opus build
  landed (core aa8036b: l2_init_decay lever, θ₀ capture/theta0.pt+hash with
  training-scoped guard, post-step _foreach decay per group-lr, l2init/* metrics,
  14 new offline tests; periphery 34d25f0: d22 norm scripts get --lanes/--theta0
  modes with byte-identical D22 regression, d23_grade.py with 3+2 formulas). Full
  suite 292 green + R0-3 golden green in a fresh process (NOTE: pre-existing 1-ULP
  golden flake when test_ppo runs first in-process — run test_entity_deepsets.py
  alone at launch checks). R0-9 COMPLETE: control_norms.csv (s26-28 species_emb at
  12M = 5.844/5.848/6.117, mean 5.936 → frozen partition BOUND ≤4.452 / VOID
  ≥5.461; actor LN-free aggregate control 1.507-1.563; critic move blocks exactly
  DEAD ratio 1.000000 → OVERBOUND reads the ACTOR aggregate) + srank/dormancy
  (critic ctx srank99 at 12M 11/17/16 of 384, actor 72/90/45, tau100 0.510/0.534/
  0.677; s26 6M srank-1 anomaly recorded) — collect needed the server, the gate's
  "offline" label was wrong for that half. R0-10 COMPLETE: 60k smoke seed 99 — six
  l2init metrics logging, theta0.pt 4.49 MB, 517 steps/s solo vs 540 baseline.
  R0-11 COMPLETE: grader verified on six synthetic cases; honesty record shows D18
  and Rung 3 verdicts UNCHANGED under the augmented 5-seed comparator (pooled
  0.5511 vs frozen 0.5509). Header updated: gates marked cleared, R0-9 numbers
  frozen, s41 trigger fire labeled bins 8-10. READY TO LAUNCH: 3 treatment lanes
  (l2init config, seeds 44/45/46) + 2 comparator lanes (struct12m verbatim,
  original 100k/100 cadence, seeds 49/50), 5-wide, ~10.6 h wall.**
- 2026-08-12 (early afternoon, D23 LAUNCH RECORD) — **D23 LAUNCHED ("launch"): 5
  lanes up — 3 treatment (l2init cfg, seeds 44/45/46) + 2 comparator (struct12m
  verbatim, 100k/100 cadence, seeds 49/50).** s44 was launched by the maintainer
  from the handed-over command (17:00 EDT — the wandb stamps are local; a UTC
  mislabel here was corrected same day); agent launched the
  remaining four staggered 75s (s45 17:02:20, s46 17:03:35, s49 17:04:50, s50
  17:06:05 local-log clock), nohup+disown+caffeinate, all from clean tree 6e50d5c.
  R0-8 launch checks ALL GREEN: 5 python + 5 caffeinate processes; wandb binaries
  growing seconds-fresh on every lane; git_dirty FALSE on all five meta.yaml;
  l2_init_decay: 0.02 in all three treatment config snapshots, ABSENT in both
  comparator snapshots (original cadence confirmed); theta0.pt (4.49 MB) present
  on exactly the treatment lanes. Fleet monitor armed (done/died/stall per lane,
  fires the readout when all 5 terminate); 14h caffeinate up. ETA ~10.6 h at
  5-wide → finals late tonight. Readout: scripts/d23_grade.py (R0-4 hard-fail
  inside), locked evals for 3 treatment finals + val-peaks + 2 fresh comparator
  finals, mechanism reads per the ratified header (BOUND ≤ 4.452, srank ≥ 40 vs
  control 11-17, l2init/* trajectories).
- 2026-08-12 (night, MID-RUN INCIDENT + RECOVERY) — **Comparator lane s49 CRASHED at
  7.2M and was re-run as s51; treatment lanes unaffected.** Cause (exogenous infra,
  NOT config/seed/lever): at the ~7.2M in-training eval one eval battle hit the
  server's turn-1000 auto-tie and terminated without info["outcome"] → the eval
  harness's strict guard raised (`eval_win_rate is on but 1/100 eval episodes
  supplied no outcome`) and killed the lane. First firing of this mode across all
  lanes to date (~1-in-10⁴ eval battles). RELAUNCH LESSON (new landmine): a
  same-seed relaunch COLLIDES WITH THE DEAD RUN'S ZOMBIE BATTLES server-side —
  same seed → same usernames → poke-env raises `Can not reset player's battles
  while they are still running`. Server restart was not an option (4 live lanes).
  Recovery: comparator lane re-launched FRESH at **seed 51** (s51, 23:05 EDT,
  verified alive + growing) — the ratified design (2 fresh comparator lanes) is
  preserved; seed identity 49→51 recorded as the deviation. Dead artifacts kept:
  runs/showdown_sp_struct12m_s49_dead_at_7m2 (+ _relaunch_collision stub).
  CONSEQUENCES: s51 finals ~09:40 EDT 08-13 (~6h after the others, ~03:40) →
  treatment evals can run at ~04:00 but GRADING IS ONE PASS and waits for s51's
  final + eval (~10:00). Monitor re-armed on the corrected lane list (s44/45/46 +
  s50/s51); keep-awake extended to ~11:10. Seeds: 49 BURNED (dead lane), 51
  ASSIGNED. If a treatment lane hits the same eval crash, the pre-registered LANE
  FAILURE RULE applies as written (no replacement — the asymmetry vs this
  comparator re-run: comparator lanes estimate the baseline, not the treatment
  effect, and s49's death predates any treatment data it could bias).
- 2026-08-13 (mid-morning, THE D23 READOUT) — **D23 REGEN-L2: "LETTER-MET,
  SEED-FRAGILE, NOT CREDITED" (the pre-stated recording rule, verbatim) — and the
  mechanism story is strong: BOUND, gap-shrink realized, srank 2-3× control but
  short of its letter.** PRIMARY (locked, 3×3000 treatment vs 5-seed comparator,
  R0-4 exact on all 8 JSONs): treatment s44 **0.6463** / s45 0.5620 / s46 0.5607 →
  pooled 0.5897; comparator s26 0.5633 / s27 0.5683 / s28 0.5210 / s50 0.5763 /
  s51 0.4937 → pooled 0.5445; **Δ +0.0451** ≥ letter 0.025, but clustered se
  governs (treatment s=0.0491, comparator s=0.0356) → 2·se 0.0650, operative bar
  0.6095 → NOT credited. GRADER NOTE: first pass ran mis-specified at 4 comparator
  seeds (the s49→s51 swap hadn't been folded into FRESH_COMPARATOR_SEEDS; verdict
  class identical, Δ +0.0324, conservative-against-treatment; superseded same
  hour, both passes in results/d23/grade.txt history). **MAJOR CHAPTER FINDING —
  the comparator lanes did exactly what Q1 bought them for: fresh Rung 2 lanes
  landed 0.5763 and 0.4937 (range 0.083 across 5 seeds, sd 0.0356 vs the 3-seed
  estimate 0.0260) — Rung-2 12M seed variance is far larger than the frozen trio
  suggested, the operative bar at realistic spreads is ~0.61, and a 12M win-rate
  primary is effectively un-creditable at advisory-scale effects. Future 12M
  rungs must be carried by mechanism reads (as D23's design anticipated).**
  MECHANISM: manipulation check **BOUND** — species_emb ‖θ‖/‖θ₀‖ at 12M
  4.169/4.120/4.103 (median 4.120 ≤ 4.452; control 5.844-6.117; models predicted
  3.4-4.1); no OVERBOUND (actor LN-free 1.19-1.31). srank co-primary: critic ctx
  srank99 **31/53/36 of 384 vs control 11/17/16** — 2-3× de-collapse, but the
  letter (≥40 on ≥2/3) is met only by s45 → **DE-COLLAPSE NOT MET, recorded with
  values**; actor srank 141/103/87 vs control 72/90/45. CO-PRIMARY 2: within-lane
  final→peak gap **+0.0114 pooled vs D18's +0.0274** (s44 +0.0007, s45 +0.0340,
  s46 −0.0003; 2-of-3 ≈ 0) — the SHRINK prediction realized AGAINST the
  adversarial selection confound. FALSIFIER: does NOT fire (wr is letter-met, not
  FLAT per the defined partition) — the regenerative family is neither killed nor
  closed. SECONDARY 3: 0-of-3 blowups (max bin-median ratio 1.06; "consistent
  with, not evidence for, suppression"). SECONDARY 4/C3: back-half entropy s44
  0.336 EXCURSION, s45 0.334 at-the-line, s46 0.306 within (comparator s50
  0.264); credit-attribution clause moot (no credit). GATES all green: R1
  0.968-0.978 by 4M, eplen 30.7-31.9, K6 clear, R0-8 within band. HONESTY RECORD
  (grader block): augmented 5-seed comparator 0.5445 vs frozen 0.5509; D18 NULL
  unchanged; Rung 3 regrade differences are the ERA'S line (pre-larger-of), not
  the comparator — recorded verdicts stand. **s44's 0.6463 is the highest
  single-lane 12M result in repo history and exceeds the 50M pooled 0.5802 — 
  named ONLY with the recording rule's weakness attached (its arm-mates sit at
  0.561).** NEXT: not-credit → D19 as queued; a 50M regen-L2 carry (BOUND +
  gap-shrink + letter-met make a real case) requires the cap conversation —
  maintainer decisions, laid out in STATUS. Seeds 44-46/50/51 SPENT, 49 burned,
  47-48 free. Artifacts: results/d23/ (8 eval JSONs, grade.txt, control/treatment
  norms, obs tapes, rank CSVs).
- 2026-08-13 (session start, HANDOFF FOLDED) — Handoff taken and stub restored;
  nothing durable was outstanding (STATUS + the D23 readout entry already carried
  it). Verified at fold time: clean tree, **no lanes/evals/monitors running**,
  Showdown server up, 5 commits local past origin (push still unauthorized —
  now STATUS action 0). Folded into STATUS: the push item, the standing design
  process (2 Opus design agents + 2 Opus reviews per pre-reg/lever — maintainer
  2026-08-12, D23 is the template), and the s49 incident detail merged into the
  eval-auto-tie watch line. **DESIGN §12 caught up** (the handoff's deferred item):
  new QUEUE STATE block (D22 closed 08-11 → D18 read out 08-12 NULL → regen-L2
  runner-up became D23, read out 08-13; unread = D19/D20/D21), a READ-OUT stamp on
  D18 and a CLOSED stamp on D22 with its actual routing ("D18 first, unconditional"
  — representation/critic ceiling, not exploitability, not yet plasticity), and a
  D19 STATUS note: its D18-credits re-scope clause does NOT bite (D18 null), its
  plumbing dependency is satisfied, and the D23 comparator-spread finding means any
  12M D19 must be mechanism-primary, not win-rate-primary. No code touched; no
  numbers changed. Open maintainer calls unchanged: push, and D19 vs 50M regen-L2
  carry vs both (the carry needs the 20-day-cap conversation, chapter ~17/20).
- 2026-08-13 (session start, cont., THE POST-D23 DECISION) — **Maintainer took
  branch (b): the 50M REGEN-L2 CARRY**, over D19-as-queued and over both-sequenced,
  and accepted the ~5 lane-days past the 20-day cap (chapter ~17/20 — the cap
  conversation is settled by that acceptance, recorded here as the authorization).
  Rationale on the table when the call was made: regen-L2 was motivated by a 50M
  pathology (D22's weight-norm growth on the 50M lanes) but only tested at 12M;
  mechanism power is higher at 50M (larger growth, ~100 ckpts/lane); and the 12M
  win-rate channel is known-dead after the comparator-spread finding (sd 0.036 →
  operative bar ~0.61). Stated counter, and the binding design constraint that
  follows it: **Rung 3 is itself seed-fragile, so an advisory-scale delta will land
  in the recording band at 50M too — the carry's pre-reg must be MECHANISM-PRIMARY
  (norms + srank primary, win rate secondary), not a repeat of a win-rate primary
  at 2.5× the cost.** Also done this session: the 6 outstanding commits PUSHED
  (origin/main at ba4356d, maintainer authorized). NEXT: draft the carry pre-reg
  under the standing 2-Opus design process.
- 2026-08-13 (morning, THE CARRY DESIGN CYCLE — 2 Opus designers + 2 Opus reviews,
  NO LANES SPENT) — **The 50M regen-L2 carry was designed, reviewed, and comes back
  NO-GO AS SCOPED; the cycle's real output is four findings that cost zero lane-days,
  two of which bear on results already recorded.** Documents (durable, gitignored):
  results/d24_design/{carry_design_A,carry_design_B,carry_review_1,carry_review_2}.md.
  **FINDING 1 — MEASUREMENT BUG, affects the D22/D23 rank record: `srank99 = 1` is a
  silent float32 NaN sentinel, not a real rank.** Reviewer 1 flipped a true 15 to 1
  under a 1.2e-7 perturbation and identified a corrupted cell already on disk —
  `results/d22/effective_rank.csv`, s36 critic @6M reads 1, true value 19. Fix before
  any rank number is quoted again: float64 `svdvals` + a NaN hard-fail in the grader.
  Designer B independently hit the same symptom, diagnosed it as DC degeneracy and
  "fixed" it by mean-centering — **wrong cause, wrong remedy**, recorded so the
  centering change is not adopted on B's reasoning. B's 12M control reads inherited
  the bug (actor "108-110" is really 113/17/108, critic "9-14" is 9/18/25).
  **FINDING 2 — THE GEOMETRIC NULL, and it re-grades D23's own srank co-primary.**
  Interpolate a control checkpoint back toward its OWN init, theta(alpha) = theta0 +
  alpha*(theta_c - theta0), no training, pure geometry: at the alpha matching D23's
  treatment anchor distance the null alone reproduces ~50% of the headline de-collapse
  (critic 12 -> 24 vs treatment 34; actor 104 -> 127 vs 152). Reviewer 1 reproduced B's
  table independently (its critic null came out STRONGER) and extended it to 50M: at
  the treatment's predicted distance (alpha 0.3-0.5) pure geometry yields critic srank
  26-164. **Consequence: D23's actor srank margin over the null is only 1.21x and its
  critic margin ~1.5x — a de-collapse claim under a toward-init regularizer is partly
  a distance-from-init artifact, and any future rank read MUST be graded against the
  null at matched anchor distance.** D23's recorded verdict does not change (its srank
  letter was NOT met anyway), but its mechanism narrative is now weaker than logged.
  **FINDING 3 — dormancy is the null-robust plasticity statistic** (the interpolation
  moves the median control lane only 0.763 -> 0.701 across alpha 1.0 -> 0.3), and the
  matched-tau 12M restatement corrects a D23-era claim: treatment median 0.45 vs
  control 0.51 is a real -0.06, not "the lever left dormancy unchanged" (that
  comparison was tau=0.025 against tau=0.1). Actor dormancy is also where the 50M
  pathology actually lives (0.45-0.52 at 12M -> 0.85/0.76/0.39 at 50M), whereas
  **critic srank SATURATES 12M->50M (control 8/14/11 -> 10/7/9) — D23's chosen
  co-primary has no headroom left at the carry's horizon.**
  **FINDING 4 — the 50M win-rate channel is arithmetically un-creditable, verified to
  the digit by both reviewers.** Frozen comparator s35 0.65933 / s36 0.57267 / s37
  0.50867 -> pooled 0.580222, sd 0.075617; the clustered term alone is >= 0.0873 at
  ZERO treatment spread, binomial (0.0147) can never govern, so the credit bar is
  **>= 0.6675 unconditionally** — above s35's 0.6593, the best single lane in repo
  history. The bar is treatment-spread-owned: a zero-variance comparator still leaves
  0.637, and two extra comparator lanes (3.3 lane-days) move it only 0.6843 -> 0.6685.
  **WHY NO-GO (Reviewer 2, and Reviewer 1's evidence agrees):** every reachable verdict
  in both designs terminates at the same next action ("D19, or close the chapter"); the
  one branch that would redirect the project is the unreachable one. Worse, Reviewer 1
  showed **A's primaries cannot fail** — at the treatment's own predicted distance the
  geometric null clears A's letters (">11", ">=21") outright, and A's norm-growth-arrest
  read is a near-certain consequence of a 3.9-e-fold anchor pull; A also has no
  GEOMETRIC-ONLY verdict state and no capability condition, so it could return
  "MECHANISM CARRIES" on an under-trained network. **IF the carry is ever run, the
  ratified spine is B-merged** (PRIMARY = dormancy; PRIMARY 2 = rank ABOVE the null at
  matched anchor distance, keeping A's back-half-median lane statistic; capability
  floor made RELATIVE to the control's own 12M->50M delta — as written B's absolute
  floor fails on control s37; win rate descriptive with A's un-creditability table
  verbatim; seeds 52/53/54 with 47/48 named for crash replacement; A's R0-12
  frozen-comparator attestation imported). **ROADMAP DEFECT for the maintainer:** DESIGN
  §13 conditions a 250M pre-registration on "a credited lever at 50M"; under today's
  larger-of line no such lever exists (Rung 3's CREDIT was graded under the era's line
  and its recorded verdict stands, per the D23 readout), and this carry cannot create
  one at 3 lanes. §13(1) needs restating or explicitly waiving. **OPS/TOOLING, all
  pre-launch for any future rank-bearing rung:** `d22_dormant_rank.py` clobbers its own
  CSVs (no `--out-name`, unconditional writes ~L155-156) and has already destroyed the
  D23 CONTROL rank pass — results/d23/effective_rank.csv holds only seeds 44/45/46;
  neither grader exists yet; the locked protocol is 3000/seed per DESIGN §8 and
  **CLAUDE.md's "1000 battles/seed" is the stale line — fix it**; `reconstruct_theta0`
  VERIFIED working on struct50m-era configs (A had flagged this as a risk; it resolves
  positive) but needs both encoder env vars; ||theta0|| = 1.97261 for species_emb (the
  repo comment is wrong); 50M LN-free band measured 2.83-3.11. **Lane-day cost is
  UNRESOLVED between the reviewers** — R1 measured 388-398 steps/s -> 34.9-35.8 h/lane
  -> ~4.4 lane-days; R2 used 336 steps/s -> 41.3 h/lane -> ~5.6. The gap is almost
  certainly 3-wide vs 5-wide collection; resolve before any launch, and do not launch
  on the "~5.0" figure that was accepted. Repo tree untouched by all four agents
  (verified clean); no code changed this session.
- 2026-08-13 (late morning, THE ZERO-LANE WORK — measurement stack repaired and the
  GEOMETRIC NULL STUDY RUN; maintainer chose option (a)) — **Three deliverables, no
  lanes.** (1) **`d22_dormant_rank.py` HARDENED.** srank now computes in float64 with
  a deterministic Gram/`eigvalsh` fallback and a hard fail; it can no longer report
  the silent `srank99 = 1` NaN sentinel. Two distinct failure modes were measured, not
  assumed: the historical corrupt cell (s36 critic @6M) fails float32 svdvals **40/40
  and float64 0/40** — a deterministic precision failure, true value **19** — while a
  separate RARE non-deterministic LAPACK failure hit float64 once mid-sweep on an
  interpolated critic that then succeeded 60/60 in isolation, which is why the
  fallback is a different decomposition rather than a retry (it agrees with svdvals
  exactly: 19 and 21). Also: overwriting an existing dormant/effective_rank CSV is now
  REFUSED before any forward pass, with `--tag` to write alongside and `--force` to
  override — the clobber that destroyed D23's control rank pass. (2) **THE RECORD
  RE-DERIVED.** Full D22 rank pass re-run in float64: **35 of 36 cells identical, one
  corrected — s36 critic @6M, 1 -> 19** (results/d22/effective_rank_float64.csv; the
  original is kept). D18 and D23 rank CSVs scanned: **zero sentinel cells**, so the
  D23 readout's 31/53/36 are sound. **D23's destroyed control pass REGENERATED from
  the surviving tapes** (results/d23/effective_rank_control.csv): critic 12M
  **11/17/16**, actor **72/90/45** — exactly the values the D23 readout logged, so
  that entry needed no correction. (3) **THE GEOMETRIC NULL STUDY** — new
  `scripts/d24_interp_null.py` + `scripts/d24_null_match.py`, artifacts and write-up
  in results/d24_null/SUMMARY.md. Interpolating a control back toward its own theta0
  over the lever's covered params reproduces each lane's recorded `d_lnfree` to 0.000
  and its recorded srank exactly at alpha=1, then: **critic srank rises from 11/17/16
  to 185/210/182 at alpha=0.3 with NO training** (50M: 10/7/9 -> 140/121/164).
  **THE RE-GRADE OF D23, at matched anchor distance, adversarially against the most
  favourable control lane: the CRITIC de-collapse SURVIVES on all three lanes (margins
  1.35x / 2.21x / 1.64x) — it is a real effect beyond geometry. The ACTOR rise does
  NOT: margins 1.26x / 0.94x / 0.63x, i.e. two of three treatment lanes sit AT OR
  BELOW what pure interpolation reaches at the same distance** (s46's actor 87 against
  a null of 139). D23 logged "actor srank 141/103/87 vs control 72/90/45" as
  supporting color; that is a contrast at the control's OWN distance and it does not
  survive matching. **D23's recorded verdict is unchanged** (the srank letter was not
  met, and the co-primary was the critic read) — but the actor-side mechanism color is
  retired, and the critic co-primary is now on firmer ground than when it was logged.
  **CONSEQUENCE FOR ANY 50M RANK READ:** at 50M a treatment would sit near alpha
  0.3-0.5, where the null alone gives critic srank 14-164 against a control of 7-10 —
  **a naive "treatment >> control" rank read at 50M is satisfied by geometry alone**,
  which retires Designer A's PRIMARY 1 on measurement, not on argument. **DORMANCY IS
  NULL-ROBUST and is the statistic to use:** across the distances a treatment would
  occupy, interpolation moves the control's actor dormancy only 0.50->0.47 (12M) and
  0.76->0.74 (50M), while the pathology itself grows 0.45-0.52 -> 0.85/0.76/0.39. Suite
  293 green after the tooling change; tree clean; no lanes, no evals. Any future
  mechanism rung inherits: rank letters stated as a margin over the matched-distance
  null, dormancy as the primary, and the `--tag` discipline on every rank pass.
- 2026-08-13 (midday, THE SPEND-OR-STOP PAIR — 2 opposed Opus advocates, 0 lanes) —
  **Both advocates independently reject the carry; they split on D19 vs stop, and the
  exercise corrected three numbers I had wrong.** (1) **THROUGHPUT RESOLVED — the
  reviewers' 4.4-vs-5.6 lane-day disagreement was FLEET WIDTH, not measurement error.**
  Measured end-to-end (started_at -> last-ckpt mtime, cross-checked against
  history.csv): struct50m **3-wide = 387.6/389.0/398.1 steps/s** (34.9-35.8 h/lane);
  D23's **5-wide fleet 331-343**; D18's 5-wide 309-312. So a 3-wide 50M carry is
  **~5.1 lane-days** — neither reviewer's figure — and D19 needs no model at all
  because D18 was the identical fleet shape (5x12M, 5-wide, same plumbing) at
  10.69-10.79 h/lane = **2.24 lane-days, ~2.4 all-in**. My earlier "~1.5" for D19 came
  from a reviewer estimate and was wrong. Bonus, like-for-like inside one fleet: the
  regen-L2 lever costs **-3.2%** throughput (s44/45/46 mean 331.8 vs no-lever s50 342.7,
  same night, same cadence) — not Designer A's "<0.3%" nor Reviewer 2's "-4.3%".
  (2) **THE D19 CREDIT ARITHMETIC DEPENDS ON LANE COUNT, and 5 lanes changes the
  answer.** Against the 5-seed comparator (0.54452, sd 0.03558): at n_T=3 a D23-sized
  effect (+0.045) needs treatment sd <= 0.0275, tighter than EVERY 12M arm ever
  measured here (Rung-2 0.0356, D18 0.0364, D23 0.0491) — so at 3 lanes credit is
  effectively out of reach, as ADVOCATE-STOP argued. **At n_T=5 the bar is 0.5810 /
  0.5839 / 0.5898 / 0.5987 for s_T = 0.020 / 0.026 / 0.036 / 0.049** — i.e. a
  D23-sized effect with Rung-2-sized spread lands ON the line (D23's realized 0.5897 vs
  a 0.5898 bar), so D19 credits iff it beats D23 slightly. **The entire credit region
  also sits above M4 (0.558)** — a credited D19 would claim the ladder's unclaimed
  stretch milestone at 12M. (3) **THE LANE-DAY LEDGER LOOKS OVERSTATED — reconcile
  before it gates anything.** Reconstructed from all 53 surviving run dirs with usable
  timing: **393 lane-hours = 16.4 lane-days TOTAL**, of which the pre-chase
  vs-SH-trained era (r512*, faint6m*, warmstart*) is ~68 h ~ 2.8 lane-days, leaving
  **~13.5 lane-days of chase-era spend against the recorded ~17** (ADVOCATE-SPEND got
  ~12.1 on a slightly different inclusion rule). CAVEAT, stated because it cuts the
  other way: a reconstruction from surviving dirs cannot see deleted runs, so the gap
  may be ledger drift OR real spend whose dirs are gone. Either way D19 (~2.4) fits
  inside D17's 20 with room, and so would the carry on price alone — **the carry fails
  on merit, not on cost, which is the point both advocates independently reached.**
  (4) **TWO NEW HITS ON THE CARRY'S DESIGN, from ADVOCATE-SPEND:** Designer B's
  dormancy letter (3-lane median <= 0.60) is roughly a **level-0.26 test** given the
  control triple {0.839, 0.763, 0.388} — s37 alone satisfies it and P(median of 3 <=
  0.60) = 7/27 — so even the null-robust statistic needs a properly calibrated letter,
  not just a plausible threshold; and the 50M dormancy pathology is 2-of-3 and largely
  realized by 25M (s37's dormancy FALLS, 0.516 -> 0.388). (5) **ADVOCATE-STOP's
  strongest point, which stands: the ~5 lane-day overage authorized this morning was
  PURCHASE-SPECIFIC TO THE CARRY, and the carry came back NO-GO — the authorized thing
  no longer exists**, so any D19 spend needs its own authorization rather than
  inheriting that one. STOP also reads D17's compute trigger as unconditional (the
  drafter qualified the calendar trigger with "without M1" and not the compute one);
  that is a defensible reading of an ambiguous sentence and is the maintainer's to
  settle, not mine. Documents: results/d24_design/ now also holds decide_spend.md and
  decide_stop.md. No lanes, no code, tree clean.
- 2026-08-13 (midday, cont., THE LANE-DAY LEDGER AUDITED — the recorded figure was
  ~3.5 lane-days HIGH) — **Measured, from every surviving run dir with usable timing
  (started_at -> last-ckpt mtime): total 392.8 lane-hours = 16.37 lane-days, of which
  the pre-chase vs-SH-trained era (r512*, faint6m*, warmstart*) is 67.9 h = 2.83, so
  the r7 pure-self-play CHASE has cost 324.9 h = 13.54 LANE-DAYS against a recorded
  ~17.** Per-arm: struct50m 4.43 (3 lanes) · priv12m/D18 2.23 (5) · struct12m 2.18 (7,
  incl. comparators s50/s51 and the dead s49) · l2init12m/D23 1.25 (3) · sp12m_v2 0.89
  (7) · signal12m 0.82 (3) · sp12m_v2r 0.82 (4) · scratch12m 0.76 (3) · br50m probe
  0.14 (1). **WHERE THE DRIFT CAME FROM:** the ledger was incremented with round
  estimates, each high, and the running total outran even those — the Rung-3 entry
  logged "+~5, chapter ~8" against an actual 4.43, the D18 entry logged "+~2, chapter
  ~12-13" against an actual 2.23 (8 + 2 = 10, not 12-13), and D23's actual +2.2 then
  carried STATUS to ~17. **THE DELETED-DIRS CAVEAT IS DISCHARGED for the chase era:**
  every arm the logs name has a surviving run dir (v2 control, v2r, scratch, signal,
  struct12m + comparators, struct50m, br50m, priv12m, l2init12m, smokes), so the
  reconstruction is complete for r7 — the known deletions were pre-chase milestone-1/2
  dirs. **CONSEQUENCE: D17 headroom is ~6.5 lane-days, not ~3.** D19 at 5 lanes (2.24
  measured) would put the chapter at **15.8/20** — comfortably inside the trigger, no
  renegotiation, and the 50M carry (5.1) would also have fit on price alone, which
  changes nothing because it was rejected on merit. **Method note for future
  accounting: measure, do not estimate — the per-arm reconstruction above is cheap
  (one pass over runs/) and should be re-run rather than incremented.** Corrected in
  STATUS. Tree clean; no lanes.
- 2026-08-13 (afternoon, D19 DESIGN CYCLE — THE PREMISE FAILS AT ZERO LANES; DO NOT
  LAUNCH AS QUEUED) — **Two designers, working independently from DIFFERENT data
  sources, both measured that opponent-TEAM prediction is very nearly information-free
  in gen1 randbats — the format makes D19's target almost empty by construction.**
  Designer A, from 1800 teams recovered off the existing obs tapes: species marginal
  entropy **4.949 nats over 146 observed species vs uniform 4.984**; exclusion-prior
  NLL 4.942 against an oracle 4.868, so the **practical ceiling on learnable structure
  is 0.074 nats of ~4.94**, and a fitted held-out model captures 0.035 — top-1 moves
  3.09% -> 3.12%. Of that 0.074, **0.064 is exclusion** (don't re-predict an already
  revealed species), which is a mask, not a learned belief. Designer B, from 4,000
  teams drawn from the real generator: frame-level belief content **0.296 nats of
  4.921, and EXACTLY 0.000 at one revealed mon.** The two disagree on the number
  (different definitions — A's is what a model can capture beyond exclusion, B's is
  averaged over reveal states) and agree completely on the conclusion: **teams are
  independent near-uniform draws, so seeing one of the opponent's mons tells you
  essentially nothing about the rest.** The lever was imported from advisories about
  games where hidden composition is CORRELATED (DouZero+ hidden hand, agent-modeling
  aux tasks); gen1 randbats has no such structure to infer. **This is a real finding
  and it is worth recording whether or not anything else runs: an auxiliary
  opponent-team-prediction head cannot form a useful belief state in a format whose
  teams are drawn independently.** Two further zero-lane catches: (a) a plain
  `Linear(384->152)` head is 684,579 params and **BREACHES ACTOR_PARAM_CEILING
  (681,994)** — R0-2 would have hard-failed at launch; B's fix (head owned by PPOAgent,
  constructed after both nets) keeps the actor at 626,059 AND makes actor/critic init
  bit-identical to the control at the same seed, which D18 could not claim; (b)
  `loss/grad_clip_frac` is **0.90 on control lanes**, so any COUPLED aux term is a
  covert ~10-30% policy-LR cut — an aux gradient must be clipped separately (D23's
  decoupling precedent). Also recorded from Designer A: at n_C=3 every threshold letter
  has its level quantized to {0, 0.2099, 0.7901, 1} — which is exactly why the earlier
  dormancy letter came out at level 0.26 — and D18, a rung with NO actor lever, scores
  p=0.0893 on the dormancy permutation letter, i.e. that letter is not specific. **NOT
  IMPLEMENTED, NOT LAUNCHED. The maintainer authorized D19 on the queued premise; the
  premise did not survive the design cycle, so the decision goes back rather than the
  lanes going out.** Options put up: drop D19 and record the format finding; RE-TARGET
  the aux head from team composition to OPPONENT ACTION prediction (in a simultaneous-
  move game that is the belief that actually bears on the decision, ground truth is
  free in self-play, same plumbing, same 5 lanes / 2.24 lane-days) — a new lever
  needing its own cycle; or close the chapter. Documents: results/d24_design/
  d19_design_A.md, d19_design_B.md. Tree clean, no lanes, no code changed.
- 2026-08-13 (late afternoon, D25 DESIGNED AND REVIEWED — opponent ACTION prediction;
  the re-target CLEARS the information gate D19 failed, but the mechanism letter is
  unsettled and one blocking gate is running) — **The maintainer approved re-targeting
  the aux head from team composition to OPPONENT ACTION (gen1 is simultaneous-move, so
  that is the belief that bears on the decision). 2 designers + 2 reviews, 0 training
  lanes.** Documents in results/d24_design/d25_*.md. **INFORMATION GATE: CLEARED, ~15x
  D19.** Designer A collected two 300-battle mirror tapes (s26/s27 finals, ~2 min each)
  recording (seat-1 obs, seat-2 action) — the labels are NOT on disk, the existing tapes
  carry no actions — and measured realised, held-out, actor-visible structure with the
  legality/mask term subtracted FIRST: headline 0.573 nats, 39% of the loss, **largest
  exactly where D19's was zero** (0.63-0.65 at one revealed mon, 0.78-0.86 at the
  battle's first decision) against D19's 0.035 nats / 0.7% / 0.000. **Reviewer 1
  reproduced A's entire measurement table exactly, then found the headline's PRECISION
  does not hold: both lanes were read at split seed 0, and over 6 battle-level splits
  s26 is 0.5594 (sd 0.017) and s27 is 0.5059 (sd 0.057, range 0.41-0.57) — "two lanes
  agreeing to the third decimal" was a split-seed coincidence. Honest premise: 0.51-0.56
  nats.** Two corrections that go the OTHER way, both R1: collapsing 12 classes to 6
  DEFLATES by the data-processing inequality (12-class realised 0.610/0.673), so A's
  number is conservative; and **Designer B's headline "1.59-nat window, 21x" is WRONG —
  that is the raw-frame window; canonical is 1.21/1.37, and B's 1.290 "permutation
  noise" is H(raw|canonical), an ENTROPY subtracted from a MUTUAL INFORMATION.**
  Permutation is 13-24% of the window, not 72%. **THE STRUCTURAL FINDING BOTH DESIGNERS
  REACHED INDEPENDENTLY, from opposite lenses:** EntityDeepSets forms logits as
  `scorer([ctx||entity])` and ctx is max-pooled, so a linear probe on ctx **cannot
  decode even the ACTOR'S OWN action** (positive control: -0.061 nats) and a plain
  `Linear(ctx->K)` head is ill-posed for switch classes. **D19's proposed mechanism
  co-primary was therefore a null BY CONSTRUCTION — it would have read "the trunk does
  not carry the belief" when it only showed the estimator was the wrong shape.** Both
  the head and every estimator must be scorer/pointer-shaped. **BUILD CONTRACT (merged,
  verified against source by R2):** label = the 10-way int `PoolPlayer.choose_move`
  already computes pre-BattleOrder, read synchronously from pre-resolution `battle2`;
  it is TRANSITION-time info (like `info["outcome"]`) so it belongs to row t with no
  carry variable and no reset merge; anti-leak holds because the frame is derived from
  the buffered obs row's own id-suffix, so the label can only name entities the actor
  could see; no `embed_battle`/OBS_DIM change; train on B's 12-class canonical space and
  marginalise to A's oracle-validated 6 for reporting. **THREE BUGS CAUGHT BEFORE A LINE
  WAS WRITTEN:** (a) appending aux params to optimizer group 0 silently hands them the
  CRITIC's Adam moments (R2 measured it) — they need a third group; (b) A's env seam
  emits a tuple that hits gymnasium's object-array branch and hard-wires the 6-class
  space via `ident=0`; (c) the ACTOR_PARAM_CEILING dispute is settled — the assert walks
  `EntityDeepSetsNet.parameters()` ONLY, so an agent-owned head is invisible and nothing
  hard-fails (B operative), but R1 found the ceiling CONSTANT still encodes the flat MLP
  at OBS_DIM 808 while today's encoder is 828. **COST, measured not assumed: -2.1%
  throughput (the aux is update-side only and update is 13.4% of the loop), so 2.30
  lane-days training + 0.05 evals = ~2.35 -> chapter 15.9/20, inside D17. Build is ~200
  lines and ~5 evenings, NOT the "~20 lines" first estimated.** **THE OPEN QUESTION,
  and it is a launch gate:** R2's GO flips to NO-GO if the mechanism letter cannot be
  calibrated, because the rung's value concentrates in the one falsifier branch that
  rides on it; R1 found the control set is n=2 with Delta_ctx 0.034 vs 0.092 (2.7x on
  two points) and expects the drop-to-recorded-only clause to be live. **R0-12 is now
  running at zero lanes: build the five-lane control distribution (s26/27/28/50/51) and
  decide whether the permutation letter (level 12/252 = 0.0476) is calibrated AND
  reachable.** Also pending a maintainer decision BEFORE launch: the shuffled-label
  placebo arm is a further 2.24 lane-days and is what separates "an explicit opponent
  model helps" from "an auxiliary loss helps" — named-not-run leaves the claim scoped.
  Nothing built, nothing launched, tree clean.
- 2026-08-13 (evening, R0-12 CALIBRATION GATE RUN — the letter IS calibratable, but
  NOT in the form either designer wrote; D25 is GO) — **Zero training lanes; five short
  mirror collections + offline probes.** (1) **THE FIVE-LANE CONTROL DISTRIBUTION**
  (Designer A's own-tape design, 12-class, 8 battle-level splits, split-averaged):
  s26 +0.0228 / s27 +0.0274 / s28 +0.0373 / s50 +0.0162 / s51 -0.0000; **mean +0.0207,
  between-lane sd 0.0139**, 35% of that variance being split noise. **Reviewer 1's
  alarming "2.7x spread on n=2" was a single-split artefact** — the thing that made the
  whole rung look uncertain evaporates once probe numbers are split-averaged, which was
  R1's own binding correction. (2) **BUT THE PROPOSED STATISTIC IS DEAD ON
  SPECIFICITY.** Delta_ctx correlates with the lane's own total decodable gain at
  **r = +0.994 (Spearman 1.000)** and with its own policy entropy at -0.946; own-tape
  gains span 0.209 nats but collapse to 0.040 on one common tape. **The own-tape spread
  IS tape endogeneity — the very nuisance the lever moves — and its range (0.037)
  exceeds the letter's own MDE (0.025).** A rung run on Delta_ctx would have measured
  the nuisance and called it a belief state: the same failure shape as the geometric
  null, caught before launch for the third time this chapter. R1's competing worry
  (de-dormancy driving it) is CLEARED at r = -0.08. (3) **THE FIX IS REVIEWER 2'S
  MANDATED FUSION** of R0-12 with Designer B's fixed reference tape, and it was
  measured, not argued: control atoms +0.0211/+0.0144/+0.0268/+0.0171/+0.0155,
  **mean 0.0190, sd 0.0051 — 2.7x tighter** — and REPLICATED on a second reference tape
  (sd 0.0062, no home-field advantage). Neither designer alone had this; it exists only
  because the two reviews were merged. (4) **THE RATIFIABLE LETTER: Delta_ref-ctx** on
  one sha256-frozen reference tape drawn from a checkpoint in NEITHER arm; 12-class
  canonical space; **lambda FROZEN at 0.01 with no per-lane selection**; mean over 8
  battle-level splits; exact one-sided permutation (treatment higher) over 252 splits →
  **attained level 12/252 = 0.047619** (independently enumerated; min p 1/252),
  **power 0.88 at +0.010 and 1.00 at >= +0.015, MDE(80%) 0.0093 nats.** Reachability:
  the required shift is ~1.6% of the arithmetic cap and ~2% of the pool-corrected
  realised signal — **Reviewer 2's NO-GO trigger does NOT fire.** (5) **THREE MORE
  BUILD-BINDING FINDINGS:** inner-CV picks the lambda-grid floor on 100% of fits and
  TRIPLES atom noise (freeze lambda=0.01, which keeps 96% of the probe gain); 1 LBFGS
  fit in 40 diverged (needs a convergence assert, not a silent number); and two new
  capacity nulls — PCA-384 of the raw observation in the ctx slot gives **-0.058** and
  the opponent's OWN observation gives **-0.013**, so only a LEARNED ctx pays, which is
  the geometric-null test applied to this statistic and passed. (6) **The information
  band is confirmed at five lanes: 0.544 nats (L6), not A's 0.573** — R1's downward
  correction holds at n=5. NEXT: merge six documents into one pre-registered config
  header for maintainer ratification; then build (~200 lines, ~5 evenings); then the
  maintainer launches. STILL PENDING A MAINTAINER DECISION: the shuffled-label placebo
  arm (+2.24 lane-days) is what separates "an explicit opponent model helps" from "an
  auxiliary loss helps". Artifacts: results/d24_design/d25_r012_gate.md.
- 2026-08-13 (night, RATIFICATION RED TEAM — CORRECTIONS TO TODAY'S RECORD; this entry
  supersedes the earlier 08-13 entries wherever they conflict) — **An independent
  red-team pass re-derived every load-bearing conclusion of this session. The
  load-bearing links HELD; six statements did not, two of which had been reported to
  the maintainer and written into STATUS.** WHAT HELD, re-derived independently: the
  geometric null's matched-distance construction (d_lnfree IS exactly linear in alpha,
  so alpha* = d_T/d_C is exact); **the CRITIC half of the D23 re-grade, robust to every
  aggregation** (max/median/mean/min-null margins 1.35-2.07 / 2.21-3.53 / ...; per-lane
  z = +2.7/+6.6/+4.2) and to a confound the study never tested — probing all 6 nets x 6
  tapes puts the tape effect at <=5% actor, <=20% critic, nowhere near the margins; D23's
  recorded ranks reproduced exactly; the lane-day ledger reproduced to the digit (a
  wandb true-end recompute moves it +0.48 h over 53 dirs, and headroom is >=4.3 lane-days
  under every alternative method); the srank fix (Gram/eigvalsh agrees with svdvals on 12
  synthetic cases + the real cell, 0 disagreements); and the kill of Delta_ctx
  (r = +0.9940, p = 0.0006). **CORRECTION 1 — "the actor rise does NOT survive the null"
  is WRONG; the honest verdict is INCONCLUSIVE.** The margins used the MAX null over the
  three controls, which is adversarial (hence correct) when ESTABLISHING an effect but
  ANTI-CONSERVATIVE when RETIRING one. Under the MEDIAN null the actor margins are
  **1.57 / 1.18 / 0.74 — one of three below 1, not two.** Fixed in
  results/d24_null/SUMMARY.md §2, in STATUS, and in scripts/d24_null_match.py's
  docstring, which had encoded the bad rule ("a margin at or below 1.0 means the claim
  is geometry"). The critic conclusion is untouched. **CORRECTION 2 — there were TWO
  srank NaN sentinels, not one.** The 2026-08-11 entry's "s26 6M srank-1 anomaly" is
  also a sentinel: re-measured in float64 it is **25** (verified this session,
  results/d23/effective_rank_s26_6m_recheck.csv). The corrupt d22 row also had a blank
  pr_ctx (true 2.0637). **CORRECTION 3 — D25's power was overstated.** "sd 0.0051,
  power 0.88 at +0.010" is the BETTER of the two reference tapes, with sd treated as
  known and arm spreads assumed equal. Exact-permutation simulation gives **0.73** at
  the second reference's sd, **0.74** integrating sd uncertainty (df=4), and
  **0.45-0.56** if the treatment arm runs 2x the comparator's spread — which every 12M
  arm in this repo has done. **Honest pair: MDE(80%) 0.009-0.011 nats, power 0.45-0.88.**
  This is the rung's load-bearing number and the config header must carry the range, not
  the best case. **CORRECTION 4 — the specificity test that killed Delta_ctx was never
  applied to its replacement:** r(Delta_ref-ctx, the lane's own gain12) = **+0.69**. Far
  better than Delta_ctx's +0.994 and probably acceptable, but it belongs in the header as
  a disclosed limitation rather than being absent. **CORRECTION 5 — D19's stated premise
  is false in three ways, though the KILL STANDS.** gen1 randbats is NOT "independent
  near-uniform draws": showdown/data/random-battles/gen1/teams.ts:106-217 is rejection
  sampling with a species clause, a type cap of 2 and a weakness cap of 2. Belief at one
  revealed mon is **0.035 nats, not 0.000** (the zero was a model-class artefact — those
  features are identically zero at r=1). The log's "of the 0.074, 0.064 is exclusion" is
  **INVERTED**: exclusion is 0.007. Realised held-out structure is **0.347 nats
  tape-weighted, ~4x the ceiling Designer A quoted.** The lever is still correctly
  killed — 0.347 against D25's 0.544 with far worse decision-relevance — but every
  sentence of the reasoning as recorded was wrong, and D25's premise is unaffected
  because it rests on its own standalone measurement. **CORRECTION 6 — stale derived
  figures:** "39% of the loss" was derived from the retracted 0.573 and is ~37%; "~15x
  D19" is ~18x at one revealed mon but only **~1.6x tape-averaged** once D19's
  denominator is corrected per above; and SUMMARY §4's "the pathology grows 0.45-0.52 ->
  0.85/0.76/0.39" is 2-of-3 — s37 FALLS (0.516 -> 0.388). **DIAGNOSIS OF THIS SESSION'S
  FAILURE MODE, recorded so it does not repeat: uniform and mild — the summaries
  promoted the most favourable measured variant while the source documents carried the
  honest range.** Every future readout quotes the range. Red-team call: ratify D25 once
  corrections 2 and 3 land. Artifacts: results/d24_design/d25_ratify_2.md.
- 2026-08-13 (night, D25 RATIFIED at r2 on L6 — the call was delegated to me and r1 was
  REFUSED) — **Two ratification audits (defect audit + red team) plus an executed
  re-freeze gate; ten agents on this rung, zero training lanes.** r1 was NOT ratified:
  three blocking defects. **(1) THE HEAD COULD NOT BE BUILT AS SPECIFIED** — it scores
  "opponent move slots" but `entity_deepsets.py:298-302` builds `own_moves` from
  `tok["moves"][:, :4]` ONLY; the observation carries the opponent's revealed move slots
  and the trunk never tokenizes them (verified in source this session). Fix written into
  r2: the aux head applies the EXISTING `move_net`/`move_emb` to `tok["moves"][:, 4:]`,
  with the honest consequence stated — aux gradient now reaches SHARED weights, so this
  is an actor-side lever touching shared params, with five bit-identical invariants
  enumerated. **(2) THE RETIRED ADOPT-RULE WAS WORSE THAN RECORDED.** R0-L was
  CONJUNCTIVE (>= 0.05 nats at BOTH named lanes) with a pre-stated fallback to L6; it
  cleared **0 of 2 named lanes, 1 of 5**, and r1 reported the MEAN (+0.040) and deleted
  the gate — which had been Reviewer 2's ranked blocking defect. r2 restores it as
  EXECUTED/FAILED with all five numbers, executes the fallback, and refuses the
  override; the bend is described in the ledger rather than dropped. **(3) THE LETTER'S
  CONTROL DISTRIBUTION WAS COMPUTED ON s26, a COMPARATOR LANE.** The re-freeze also
  found **s35 INADMISSIBLE** as the neutral reference — it switches on 1.9% of decisions
  against the comparator arm's 6.8-9.7% (policy-side P(switch) 0.023 vs 0.072-0.181),
  and switch targets are exactly what the label space measures; the header's "same
  recipe, same horizon" justification was false (50M runs, eval_every 250k vs 100k).
  **Reference is now s36@12M (sha256 3ffee9ba...074917), s37 as replication.** **THE
  GATE'S OWN RECIPE WAS ALSO WRONG: at max_iter=300, 44 of 96 probe fits fail the
  convergence test and the control mean is inflated ~25%** (2000 and 8000 agree) — the
  first gate's numbers were never converged. **RE-FROZEN CONTROL (L6-native, s36,
  lambda 0.01, 8 splits): +0.0217/+0.0072/+0.0201/+0.0114/+0.0145, mean +0.0150, sd
  0.0060.** **HONEST OPERATING CHARACTERISTICS, the range and not the best case:** level
  12/252 = 0.047619 rising to 0.052-0.054 under 2x treatment spread (anti-conservative,
  disclosed); MDE(80%) 0.0105 equal-spread -> 0.0130 (df=4) -> 0.0169 (2x) -> **0.0207
  (both)**, worst admissible corner 0.0301; **power at +0.010 = 0.27-0.76, NOT the 0.88
  first reported.** Reviewer 1's pre-stated ~0.015 re-examination trigger **FIRES**.
  **MY RE-EXAMINATION VERDICT, recorded: ratify anyway, on one asymmetry — the aux loss
  DIRECTLY OPTIMISES the very quantity the probe measures**, unlike D23's srank which
  was an indirect side effect, so an effect well above MDE is plausible; and the header
  states plainly that a non-fire below ~0.017 nats is UNINFORMATIVE. Specificity on the
  new reference improves to **r = +0.405** (was +0.69 on s26; +0.821 on s37 — a third
  reason s36 is the pick), with the ref-tape correlation labelled a tautology.
  **RATIFIED at r2 on L6** (configs/showdown_sp_actpred12m.yaml; body diff vs struct12m
  is still seed + run_name + six lever keys, checked by parse). **TWO R0 GATES REMAIN
  OWED AND BLOCK LAUNCH, both zero-lane:** R0-13 must re-derive the LEARNED bar on L6
  inputs (0.371 is anchored on 12-class values; its 0.80 multiplier is unsourced), and
  R0-12b's four capacity nulls have not been re-run on s36. Also flagged in-header as
  the reviser's arithmetic rather than measurement: R0-8's 255/210 and the param total
  675,538. NEXT: the build (~200 lines) + tests + smoke, then the maintainer launches.

- 2026-08-13 (night, **D25 BUILT — ~230 lines, 7 files, 24 new tests, ZERO LANES**; the
  ratified pre-registration is now executable code and the two numbers it asked to
  verify at build both hold). Suite **293 -> 317 green**, tree clean, nothing running.
  **WHAT LANDED**, per the header's build order: the env seam (`_order_identity`,
  PoolPlayer's recorded choice + `clear_choice`, `opp_action`, `info["opp_choice"]`),
  buffer storage with no `next_*` twin, `forward(x, return_features=True)` +
  `_aux_features` in the trunk, a new `rl/networks/opp_action.py` (head, canonicaliser,
  masked CE), five aux hparams on `PPOAgent` with the head built LAST and its own third
  optimizer group, `_aux_gradient`'s decoupled clip, `SnapshotPool.member_id`, and
  train.py's purity seam + meta stamps. **DISCHARGED BY THE BUILD: R0-2, R0-2b, R0-2c,
  R0-3(a)+(b), R0-5(a)(b)(c)(d), R0-7, R0-9.** **STILL BLOCKING, UNCHANGED: R0-13,
  R0-12b, R0-10, R0-10b.** **BOTH VERIFY-AT-BUILD NUMBERS HOLD.** actor+aux = **675,538
  VERIFIED LIVE** from the config file itself (actor 626,059 bit-identical to control,
  critic 494,849, aux 49,479, ceiling 681,994, headroom 6,456), and the whole B7 width
  table reproduces (32/64/96/128/256 -> 16,583 / 33,031 / 49,479 / 65,927 / 131,719).
  R0-8's **255/210 verified as arithmetic against sourced inputs**: SESSION_LOGS.md:
  2567-2568 records D18's own R0-8 with **s41 at 270 and HEALTHY**, the 5-wide band is
  12e6/(10.79*3600)=308.9 to 12e6/(10.69*3600)=311.8, and at -2.5% that is ~301-304 with
  s41 -> 263, so 255 sits 3.1% below the historical healthy floor and 210 = 0.70 x 301.
  **B15 IS RESOLVED**: the YAML was "a SPEC, NOT A RUNNABLE FILE" and now constructs —
  `ShowdownEnv` takes `opp_action`, `make_agent` splats the five aux keys, both checked
  live; amended in place. **THE ONE HEADER ITEM THE FIRST PASS MISSED, and it was in §6
  rather than in the build contract: "emit the pool member id alongside `opp_choice`
  ... build item, not optional."** Without it A3 is computed from ONE actor while pool
  members' conditional entropies span 0.17-0.43, so a LEGITIMATE head reaches gap
  closure 1.08 and the "g > 1.0 is a bug" HARD FAIL fires on a correct run. Discharged
  as a SEPARATE `info["opp_member"]` key, not a fourth field — B2 pins the array at
  three and r2 widened it deliberately — carrying the pool PUSH ID (indices shift under
  eviction; a push id names the checkpoint for the run's life) and -1 for a non-member.
  **BUILD DECISIONS WHERE THE HEADER LEFT LATITUDE, recorded so they are auditable
  rather than discovered:** (1) **SWITCH legality comes from the PUBLIC FAINT COUNT and
  NOT from the revealed bench, and the two are genuinely different** — early in a battle
  the opponent has five unrevealed live mons, so the bench POOL TOKEN is all-zero while
  switching is perfectly legal; conflating them would have masked SWITCH illegal for
  most of the early game and silently deleted the class the label space exists to
  measure. (2) The live/non-active bench mask is TOKEN-side information (revealed flag,
  fainted bit, is-active bit at token offsets 0/2/3), so the pooling happens inside
  `_aux_features` rather than in the agent-owned head, which receives only the pooled
  128-d vector. (3) The learned null token is initialised at std 0.02, i.e. OFF ZERO, so
  OTHER_MOVE is not the same scorer input as an empty-bench SWITCH. (4) The aux
  optimizer group anneals with the ACTOR's schedule (inert at this rung's
  `lr_anneal_steps: 0`). **SMOKE READS, MEASURED LIVE** (4-wide self-play at the step-0
  pool member, seed 99, 512 steps, ~1.8 s; a smoke, not a lane): **label-present
  fraction 0.941** — §9 called ~6% "a guess" off our own seat's 6.4% absorbed waits and
  the opponent seat's true rate is **5.9%**, so the guess holds and the effective aux
  batch does not shrink; **aliased 0.064**, inside the tapes' 0.040-0.103;
  `aux/illegal_label_frac` and `aux/frame_collision_frac` both **exactly 0**, matching
  all five tapes; `aux/loss` 1.750 -> 1.635 against log 6 = 1.79. **The switch fraction
  reads 0.43 against the comparator's 0.068-0.097 and this is NOT a defect** — the
  labelling policy here is a RANDOM INIT picking near-uniformly over 10 actions of which
  6 are switches, where the comparator is a trained 12M policy; recorded so it is not
  read as one at launch. **DELIBERATELY NOT QUOTED as an R0-10b read:** the smoke's
  aux/policy gradient ratio (~0.02 at init) is over actor+head params post-coefficient,
  where R0-10b specifies TRUNK gradient norms at control checkpoints — it is indicative
  of nothing, and saying so is cheaper than having it quoted later. **THE TESTS**, 24 of
  them: R0-5(c)'s ORACLE IDENTITY on a synthetic tape written back out in the env's own
  `[kind, id, flags]` encoding (so the round trip exercises the real canonicaliser), with
  a companion proving the aliasing fix BUYS something — draw the aliased rows from a
  re-based frame and the identity fails UPWARD, the direction the real tapes measured at
  +0.66 nats; the ANTI-LEAK REPLAY ASSERTION over 400 random rows; R0-5(a) timing on the
  two-seat stub (pump choices discarded, wait turns yield the sentinel, `clear_choice`
  before EVERY inner step); R0-9's byte-identical `loss/grad_norm` / `grad_clip_frac`
  lever-on vs lever-off on the same batch; R0-2c's third-group graft, which is the test
  that FAILS on the group-0 append. **NEXT UNIT: the gate scripts** — the L6 probe/grader
  for R0-13 (the LEARNED bar) and R0-12b (four capacity nulls on the s36 tape, max_iter
  2000 with the asserted `||g||_2 < 1e-3`), then R0-10b offline and the R0-10 coefficient
  smoke (four arms, seed 99, ONE AT A TIME), then the maintainer launches 52-56. **OPEN
  MAINTAINER CALL, unchanged and still needed before launch: the shuffled-label placebo,
  +2.35 lane-days.**

- 2026-08-13 (night, **D25's PRE-LAUNCH GATES RUN AT ZERO LANES — three PASS, R0-10b
  FIRES**; and the sha256-frozen reference tapes were rescued from a job scratch
  directory one deletion from gone). `scripts/d25_gates.py` is committed and
  SELF-CONTAINED: the design cycle's probe machinery lives under the gitignored
  `results/`, so a gate that imported it would die with that directory — which is exactly
  what nearly happened. **THE ARTEFACT RESCUE FIRST.** The tapes §5 freezes by sha256 —
  and which R0-15 requires the grader to PRINT before any treatment number is loaded —
  were in `~/.claude/jobs/<id>/tmp/`, deleted with the job. Copied to `results/d25/` with
  all three hashes verified across the copy (s36 3ffee9ba…074917, s37 58e64af1…39483f,
  and the INADMISSIBLE s35 9388ef3e…babe484, kept because its numbers are what
  disqualify it). **Without them §5's control distribution, power table and every MDE are
  unreproducible and a re-collected tape is a DIFFERENT tape.** results/ is gitignored,
  so results/d25/ is still the only copy and its README says so at the top. **THE GRADER
  VALIDATES BEFORE IT GATES:** `verify` re-fits §5's atoms at split seeds 0 and 1 and
  matches the frozen run to **max |diff| 4.7e-05 over 10 atoms**; R0-12b's own control
  row then reproduces all five 8-split atoms (+0.0217/+0.0072/+0.0201/+0.0114/+0.0145,
  mean +0.0150) to four decimals. Splits 0 and 1 are the two LOWEST of the eight, so the
  check is per-split — a mean-vs-mean comparison looked like a systematic defect and was
  not one. Every fit in every gate passed R0-12c's `||g||_2 < 1e-3`; none dropped or
  retried. **R0-12b PASS.** On the s36 tape in L6 at max_iter 2000: PCA-384 of the raw
  observation **+0.0009**, PCA-384 of the opponent's own observation **+0.0021**,
  row-shuffled ctx **-0.0046**, iid Gaussian at the live dimension **-0.0146**, real
  trained ctx **+0.0150**. The closest null is 7x below the control. **ONE HEADER CLAIM
  DOES NOT REPRODUCE AND IS CORRECTED IN-HEADER:** "a 384-dim linear summary of the
  observation is worse than nothing" was a 12-class own-tape result (-0.058/-0.021) and
  is FALSE in the adopted space on the primary reference, where both PCA nulls are
  slightly POSITIVE. The gate's own criterion is untouched; the rhetorical force of that
  row is. **R0-13(a) PASS**, and it corrects two things. The retained push ids were
  re-derived by SIMULATING the shipped `SnapshotPool._evict_index` rather than copying a
  list, which surfaced an off-by-one: **push id 0 is the STEP-0 ANCHOR at step 0**, not
  at 0.15M — the design cycle mapped push id k to (k+1)*153,600 and that is where the
  header's "push ids spanning 0.15M-12M" came from. Oracle window **1.1505 -> 0.9783
  (85%)**, reproducing Reviewer 1's pre-stated 86% prior. And the number he explicitly
  declined to estimate, which R0-13 nonetheless required (`re-measure A1/A3/A2s`):
  **realised does NOT hold constant under pool labels — 0.544 -> 0.4485**, measured by
  resampling each row's label from its own pool mixture and refitting the L6 with-ctx
  probe. The RATIO barely moves (47.3% -> 45.8%), so the honest headline is **~46% of the
  knowable, not ~50%**. Both NO-LAUNCH thresholds clear with ~50% margin. **R0-13(b)
  DISCHARGED AND THE BAR MOVES.** The L6 `g_frozen-probe` values are
  **0.4396/0.4035/0.4681/0.3504/0.3922 -> mean 0.4108** against the 12-class 0.463, so
  the **OPERATIVE LEARNED BAR IS 0.3286, not 0.371 — an 11.4% LOOSENING**, and §6's WEAK
  band becomes [0.10, 0.3286). The header guessed it would "land in the same place" off
  A's s26 single-split L6 datum of 0.4905; **that datum was HIGH — the 8-split s26 value
  is 0.4396.** The 0.80 multiplier remains an unsourced free parameter. **R0-10b FIRES
  NO-LAUNCH, AND THE GATE ITSELF IS DEFECTIVE.** D19-B's procedure verbatim (1,024 real
  s26 rows, policy proxy = the surrogate at ratio 1 with z-scored advantages, head at
  gain 0.01), on the BUILT head, **5 head draws per stage because the head is fresh every
  lane and a one-draw ratio is a property of a seed**: raw aux/policy trunk-gradient
  ratio **0.037-0.074 (600k) / 0.020-0.047 (6M) / 0.006-0.059 (12M)**. The POLICY column
  reproduces D19-B's within ~1.5x at every stage, so the proxy is right; **D25's AUX
  trunk gradient is 4x/33x/36x SMALLER than D19's** — the OPPOSITE of the header's
  expectation that B6a's wider path would make it larger. Every coefficient in the
  pre-stated {0.05, 0.1, 0.25, 0.5} therefore lands at 0.0015-0.029 against a 0.05 floor:
  **the grid is EMPTY and R0-10b's stated action is "the rung does not launch".** **BUT
  THE BAND DOES NOT SURVIVE ITS OWN SOURCE:** [0.05, 1.5] is inherited from D19-B §6
  ("with the chosen coefficient"), and applied to D19-B's OWN table at D19-B's OWN
  recommended coefficient 0.1 it gives 0.027 (600k, OUT), 0.117 (6M, in), 0.045 (12M,
  OUT) — **it rejects the recommendation of the design that proposed it, at 2 of the 3
  gated stages. It is not a criterion the design cycle ever met.** Both facts are
  recorded and neither is smoothed over. Arithmetic only, offered as arithmetic and NOT
  as a proposal: on the mean ratios the band wants coef in **[1.7, 26]**. **NOTHING IN
  THE RATIFIED CONFIG WAS CHANGED IN RESPONSE** — the grid, the band and `aux_head_gain`
  are all pre-registered numbers and amending any of them is a maintainer call under the
  standing 2-designers-2-reviews process. **ALSO FIXED AT GATE TIME: the shipped L6 CLASS
  ORDER was inverted.** The build had SWITCH=4/OTHER_MOVE=5; §1 writes the space as
  "{ slot 0,1,2,3 | OTHER_MOVE | SWITCH }" and pins it numerically (its realised s26
  frequencies end in 7.2% and s26's measured tape switch fraction is 0.0719), and the
  design cycle's own `y12_to_y6` agrees. NOT load-bearing for the loss — the head learns
  whatever indexing it is given, which is why 17 green tests missed it — but load-bearing
  for the READOUT. Corrected and pinned by a test quoting the frequency line. The gate
  run also produced a free cross-check: **the SHIPPED canonicaliser agrees with the
  design cycle's label path on 1.0000 of 1,024 rows.** Suite **318 green**. **NEXT: the
  R0-10b adjudication is the blocker and it is the maintainer's**, then the placebo call,
  then the R0-10 smoke (four arms, seed 99, ONE AT A TIME) and the 52-56 launch.

- 2026-08-13 (night, **R0-10b ADJUDICATED: amendment A1 REFUSED by two independent Opus
  reviews; A2 measures the ratio LIVE instead** — plus a build fix no offline gate could
  have caught). Zero lanes. Suite **319 green**. **A1 PROPOSED** that R0-10b's fresh-head
  measurement is an initialisation artefact (`aux_head_gain = 0.01` scales the scorer's
  FINAL layer, so the gradient into ctx is proportional to it) and that on a FITTED head
  the ratio is 2.50/3.41/4.19, filtering the pre-stated grid to {0.05, 0.1, 0.25} rather
  than leaving it empty. **Reviewer 1 (evidential validity) REFUSED; Reviewer 2 (decision
  and risk) said RATIFY WITH CHANGES, landing on coefficient 0.1. THREE OF A1's
  LOAD-BEARING CLAIMS DID NOT SURVIVE.** (1) **The fitted construction is NOT
  DETERMINATE** — Reviewer 1 re-ran A1's own recipe, matched its held-out CE (so it IS
  the same construction), and got **1.74/1.46/1.24 against A1's 2.50/3.41/4.19**, under
  which coef 0.5 is IN BAND and the sweep would start at 0.5. A gate whose output moves
  across the whole pre-stated grid under undisclosed fit hyperparameters is not a gate.
  (2) **A1's HEADLINE WAS STATISTICALLY WRONG IN ITS OWN FAVOUR.** Its "2.31-6.56 across
  three head draws" at 12M is DENOMINATOR noise: re-measured here with the actor held
  FIXED and only the random z-scored advantage vector varying, **||g_trunk policy|| spans
  0.236-3.196 over 20 draws, 13.6x**. A1 varied the advantage seed WITH the head seed and
  then took a **mean-of-ratios, Jensen-inflated 1.3-1.5x** against ratio-of-means; it
  also dropped from the executed gate's 5 draws to 3 while the spread widened — fewer
  draws, narrower range, in the flattering direction, on the one quantity the launch
  turns on. (3) **A1's "retro-fixes D19-B's self-contradiction" RUNS THE WRONG WAY**, and
  both reviewers caught it independently: D19-B's table is fresh-head at the SAME gain
  0.01, so the fresh->fitted factor is COMMON-MODE and CANCELS — it cannot explain the
  4x/33x/36x gap, and a symmetric correction pushes D19-B's own recommendation out the
  TOP of the band. Reviewer 1 also verified the mechanism directly (scaling the head's
  final layer by 100 raises ||g_trunk aux|| 66.7-87.4x, so "~100x" is the right order)
  and then turned it on A1: **at that scale a RANDOM head sits within 1.5-2.2x of the
  FITTED head, so both constructions measure ||W_last(t)|| x residual, not coupling** —
  which is A1's own critique of the fresh number. **A2, PROPOSED AND NOT ENACTED: neither
  offline proxy gates the rung.** The ratio is measured LIVE during R0-10's smoke on the
  co-trained head against the moving trunk with the run's own advantages — shipped as
  `aux/trunk_norm` and `aux/policy_trunk_norm`, both PRE-clip, read as a RATIO OF MEANS;
  a pure diagnostic that reads `.grad` and changes no update. **It already reads 0.177 at
  coef 0.1 over the first 8k steps, inside the band.** NO pre-registered number changes,
  and on the evidence R0-10's own unmodified rule selects **0.1 — the value the ratified
  config already carries.** Reviewer 1's strict reading (fresh-head is defensible: the
  first updates are when the trunk is most plastic, and gain 0.01 was chosen in that
  frame) is recorded as a legitimate alternative under which the rung does NOT launch.
  Reviewer 2's independently-adopted findings: calibrate on INJECTION FRACTION (coef x
  ratio IS the aux gradient as a fraction of the policy's, and nothing in this repo has
  recommended an aux loss pushing the trunk as hard as the policy — which 0.25 would);
  the head's own learning is **nearly coefficient-free** because `aux_params` are their
  own Adam group, so the coefficient buys little g and all of the F5 risk; the aux clip
  binds at the top of the grid, so the band would regulate a pre-clip quantity that no
  longer describes what reaches the trunk; and condition (a) may never bind, since a head
  on frozen 600k features already reaches g ~ 0.65 against the 0.3286 bar. Budget
  arithmetic independently verified (2.35 all-in, 15.9/20, headroom ~6.5). **THE BUILD
  FIX, found by running the REAL launch entry point for the first time** (every earlier
  smoke drove the loop by hand): **SWITCH legality read "6 - 1 - faints", which assumes
  the opponent's ACTIVE IS ALIVE.** On a FORCED POST-FAINT REPLACEMENT it is not, so with
  5 fainted the one survivor sits on the BENCH and IS switchable; the old rule called
  that label illegal and dropped it at **0.12% of live decisions — a rate that would have
  HARD-FAILED R0-5(d) at read time.** No frozen tape carries such a row, so no offline
  gate could have caught it. Legality now reads the opponent active's own
  revealed/fainted/is-active bits and `canonicalise` takes the tokenizer rather than
  restating offsets; live rate back to 0.0000. C10 (whether forced replacements belong in
  the loss at all) is untouched and still open. Also fixed at gate time: **the shipped L6
  CLASS ORDER was inverted** (SWITCH=4/OTHER_MOVE=5 against §1's own frequency line,
  whose last entry 7.2% matches s26's measured 0.0719 switch rate) — not load-bearing for
  the loss, load-bearing for the readout, now pinned by a test. **NEXT: run the four
  R0-10 smoke arms (seed 99, ONE AT A TIME, ~4 min each,
  `configs/showdown_sp_actpred_smoke_c*.yaml`), read with `scripts/d25_gates.py smoke`,
  then launch 52-56.** The placebo remains an open maintainer call.

- 2026-08-14 (**R0-10 EXECUTED and D25 LAUNCHED at aux_oppact_coef = 0.1, 5 lanes, seeds
  52-56**). Four smoke arms, 100k steps each, seed 99, one at a time, ~4 min each — and
  worth recording against the CLAUDE.md landmine: agent-launched training ran at **433
  steps/s wall-clock (100k steps in 231 s)**, i.e. near-native, NOT the ~10x penalty the
  rule was written from. The rule still stands for the 11 h/lane fleet, where job
  lifetime rather than throughput is the risk. **RESULTS:** coef 0.05/0.1/0.25/0.5 gave
  live trunk ratios 0.0685/0.1137/0.3282/0.4807, `aux/loss` ends 1.5411/1.5574/1.5314/
  1.5312, entropy@100k 1.2082/1.0329/1.3680/1.2081, `aux/grad_clip_frac` 0/0/0.0052/
  0.1018. **`aux/illegal_label_frac` and `aux/frame_collision_frac` are EXACTLY 0.000000
  on all four over 400k steps of real battles** — the forced-replacement legality fix
  holds live. **THE LIVE RATIO SETTLED A2's PROXY DISPUTE: implied raw ratio ~0.96-1.37,
  between the two offline constructions and much closer to the REVIEWER's replication
  (1.24-1.74) than to A1's (2.50-4.19). A1 was the outlier; the refusal was
  well-founded** — recorded because A1 was mine. **R0-10's RULE COULD NOT DISCRIMINATE
  AND THE DEVIATION IS DISCLOSED.** (a) `aux/loss` is FLAT across a 10x coefficient range
  (spread 0.026), so g is near-identical too — the head's own learning is nearly
  coefficient-free because `aux_params` have their own Adam group, exactly as Reviewer 2
  predicted; **g ITSELF WAS NOT COMPUTED (it needs a tape per arm), so condition (a) is
  PROXIED, not evaluated, and the readout must say so.** (b) Read as written ("at matched
  steps") the control band is the comparator lanes' own first 100k — **1.1541-1.4415,
  FOUR lanes** (s51 has no history.csv) — not §7's final-1M-bin 0.212-0.284, which is
  inert against a 100k smoke; on that band the arms are **NON-MONOTONE in the
  coefficient** (0.05 in, 0.1 OUT, 0.25 in, 0.5 in), which across a 10x range is run
  noise. So "take the LARGEST satisfying both" would have selected **0.5 on a noise-driven
  condition, and it was NOT taken.** What IS monotone: injection fraction
  0.069/0.114/0.328/0.481 and `aux/grad_clip_frac`, which reaches **0.1018 at coef 0.5 —
  the aux clip binds on ~10% of minibatches, so the DECLARED coefficient stops being the
  EFFECTIVE one.** The coefficient buys nothing measurable in the aux task and
  monotonically more trunk perturbation. **0.1 taken:** injection ~11%, inside the 3-12%
  band D19-B's own recipe targeted; clip never binds; 2.3x above the band floor; and it
  is the value ratified in the config, so no pre-registered number moved. No in-rung
  re-tune — F5's no-smaller-coefficient clause stands. Config §15C carries the full
  record.

- 2026-08-14 (**D25 LAUNCH RECORD** — 5 lanes away, seeds 52-56, `aux_oppact_coef` 0.1).
  **A FIRST LAUNCH ATTEMPT FAILED SILENTLY AND IS RECORDED SO IT IS NOT REDISCOVERED:
  `setsid` DOES NOT EXIST ON macOS**, so a `setsid nohup env … &` launch printed five
  plausible pids — the subshells — while every lane died instantly. Nothing ran, no run
  dirs, nothing burned; but the pids made it look launched, which is exactly the shape of
  the "run dir exists ≠ lane trained" landmine one level further out. **The lesson
  generalises: verify a launch by battle PROGRESS, never by anything the launcher itself
  printed.** Relaunched under `screen -dmS d25_s{52..56}` (macOS has `screen`, not
  `tmux`), staggered 25 s, each `caffeinate -is`, fully detached from the agent job so the
  fleet survives it — attach with `screen -r d25_s52`. **VERIFIED LIVE at first check:**
  148k-185k steps and 3.8k-4.9k episodes per lane, **314-325 steps/s wall-clock 5-wide**
  (ETA ~10.2 h/lane, against the header's ~11.0 h estimate), R0-1 stamps correct on all
  five (`git_dirty: false`, `aux_label_space: l6`, `actor_plus_aux: 675538`), logs free of
  the startup SIGSEGV, `aux/illegal_label_frac` **0.000000 on every lane**, live trunk
  ratio 0.125-0.130 (in band, and consistent with the smoke's 0.1137 at this coefficient),
  `loss/grad_clip_frac` 0.741-0.761. **NOT an R0-8 read** — those numbers are COLD and
  include startup, where R0-8 specifies WARM wall-clock effective over a sustained >=30-min
  window after the first 1M steps; take the R0-8 read then. Also worth recording against
  CLAUDE.md's "agent-launched training measured ~10x slower": the 100k smoke arms ran at
  **433 steps/s** from the agent, i.e. near-native. The rule still stands for an 11 h
  fleet, but the binding risk there is JOB LIFETIME, not throughput — which is why the
  lanes are in detached screens rather than in the agent's process tree.

- 2026-08-14 (midday, **D25 mid-run check at 3.6M — all five lanes healthy; and a VOID-
  clause trap recorded before it can fire spuriously**). 311-315 steps/s wall 5-wide, ETA
  ~7.5 h to finals; `selfplay/winrate_anchor` **0.9685-0.9785** (R1's 0.75 gate at 4M is
  already comfortably met, and the values sit in the control range 0.955-0.975 / D23's
  0.968-0.978); `loss/entropy` 0.298-0.440, well above K6's 0.15 floor; live trunk ratio
  0.125-0.130, matching the smoke's 0.1137 at this coefficient; **`aux/illegal_label_frac`
  0.000000 on every lane across ~18M cumulative steps** — the forced-replacement legality
  fix holds at scale. **THE TRAP, recorded so the readout does not fire it: mid-run
  `loss/grad_clip_frac` reads ~0.99, and the VOID CLAUSE says a move of >0.05 from 0.90
  means "the clip path is not behaving as designed and mechanism attribution is VOID for
  that lane".** Read naively that voids all five. It is an artefact of comparing a mid-run
  value against **0.8995, which is a WHOLE-RUN 12M mean**: at matched steps the CONTROL
  lanes themselves sit at **0.9847-0.9878** over their own first 3.6M (against whole-run
  means of 0.8995-0.9517), and D25 sits at **0.9843-0.9886** — indistinguishable. **That
  is R0-9's decoupled clip holding in PRODUCTION, not a defect**: the aux term is added
  after the clip is read, so the policy's clip statistics are the control's. Compare at
  MATCHED STEPS, or void every lane including the controls. Same shape as R0-10's
  condition (b), where §7's final-1M-bin entropy band was inert against a 100k smoke —
  **this chapter's constants are mostly whole-run or end-of-run figures and several of the
  during-run gates quote them without saying so.**
- 2026-08-14 (midday, **handoff taken; 11:10 EDT lane verification**). All five D25
  lanes re-verified by battle PROGRESS after re-extracting history.csv (wandb offline —
  a stale CSV is not a stalled lane): 3.68-3.72M steps, **wall 312-327 steps/s** over
  the trailing 35 min (s52 320.6 / s53 316.0 / s54 318.4 / s55 311.7 / s56 326.6 —
  s55's logged instantaneous `time/steps_per_sec` of 42.5 is exactly the noise R0-8's
  wall-window rule exists to ignore), `selfplay/winrate_anchor` 0.9687-0.9786 (R1's
  0.75 at 4M already met on every lane), `loss/entropy` 0.350-0.466 (K6 floor 0.15 not
  approached), `aux/illegal_label_frac` 0 on all five, all `screen` sessions attached
  and detached cleanly. HANDOFF.md folded into STATUS.md and the stub restored: the
  owed-before-readout list (R0-14 grader, M4 clone re-score at 5×3000 before finals,
  C10, g-proxied disclosure, R0-16) promoted into STATUS next actions, and the
  grad_clip_frac matched-steps trap promoted to a STATUS watch item.
- 2026-08-14 (afternoon, **R0-14 DISCHARGED: the grader is written and verified;
  R0-15's attestation PASSES against the real frozen inputs**). `scripts/d25_grade.py`
  (~380 lines) + `tests/test_d25_grade.py` (20 tests), suite **319 -> 339 green**.
  What it implements, all verbatim from the config header: the credit line with the
  larger-of se clause; the recording band [0.5695, operative bar); NEGATIVE at
  0.54452 - max(0.025, 2*se); the LANE FAILURE recompute with PRIMARY VOID below 3
  survivors; R0-4's hard fail on every ingested JSON (both pools); the M4 obligations
  firing ON THE NUMBER (pooled >= 0.558) regardless of verdict; exact one-sided
  permutation letters for CO-PRIMARY B (L6 GRADED, 12-class reported-not-graded) and
  S1 (treatment LOWER) at the pre-stated levels by surviving n_T (12/252, 6/126, 2/56,
  VOID < 3), ties counted extreme (conservative). **R0-15 runs FIRST and hard-stops on
  drift**: re-reads the five comparator finals from disk (s26/27/28 =
  runs/showdown_sp_struct12m_s*/final_eval_3000.json; s50/51 =
  results/d23/comparator_s*.json), checks each against the frozen 4-dp values, derives
  0.54453/0.03561 vs frozen 0.54452/0.03558 (4-dp rounding, tol 1e-4), prints §5's
  frozen atoms in both label spaces and verifies both tape sha256s — ALL PASS on this
  machine. Verification includes HAND-DERIVED known-p cases (subset-sum counting over
  distinct integers, not the implementation checking itself): 2/252, 4/252, 2/126,
  2/56-at-level-fires, 4/56-does-not; binomial se reproduces the header's 0.005745;
  synthetic verdict cases hit CREDIT / band / FLAT / NEGATIVE / VOID and the
  clustered-governs case at D23-like spread. S1 grading correctly BLOCKS at n_C = 3
  until R0-16 lands s50/s51. Full-output rehearsal on synthetic finals under the job
  tmp dir confirmed every section fires. Inputs owed at readout: finals ->
  results/d25/final_s{52..56}.json, mech atoms -> results/d25/treatment_atoms.json
  ({"L6": {...}, "c12": {...}}, 8-split means from the post-run probe pass), dormancy
  CSV in the d22 schema. Still owed elsewhere: the atoms pipeline run itself, the M4
  clone re-score at 5x3000, R0-16, C10, and g (proxied).
- 2026-08-14 (evening, **C10 SETTLED + the atoms pipeline written; lanes COMPLETE at
  12M**). All five lanes finished 12M cleanly (~18:10-18:20 EDT; final `checkpoint.pt`
  verified at step 12,000,000 on each; anchors 0.975-0.983 at close, K6 never fired,
  `aux/illegal_label_frac` 0 throughout). **C10, settled empirically and by source:
  the §0 tapes contain ZERO forced post-faint replacement rows — 0 of 53,848 rows
  across all seven frozen tapes** (five control + s36/s37 references) have all four
  move slots illegal in `mask2` (the forced-switch signature). Cause is BY
  CONSTRUCTION, not accident: `collect_oppact.py:137-146` pairs rows on
  (battle_tag, turn) and keeps only rows **non-forced on BOTH sides**, and the live
  wait-pump reads the opponent's choice after the FIRST inner step only
  (rl/envs/showdown.py:1033-1034), so wait-window replacements never become labels.
  The LIVE loss (post legality fix) DOES include the simultaneous double-faint
  replacements at ~0.12% of labelled decisions. READOUT DISCLOSURE: every frozen-tape
  constant (A1/A3, §5 atoms, §6 g bars) is measured on a distribution that EXCLUDES
  forced replacements while the head trained on one including 0.12% of them; the
  mechanism read and manipulation check are internally consistent (both tape-based,
  same collector), and the train/measure gap is bounded by 0.12% of the aux batch.
  **`scripts/d25_atoms.py` written** (treatment Delta_ref-ctx atoms on the frozen s36
  tape, both label spaces, 8 splits, lambda 0.01, ||g|| < 1e-3 asserted; imports the
  SAME gitignored fit path that froze the controls, provenance disclosed in its
  docstring; sha-attests the tape before any fit; writes
  results/d25/treatment_atoms.json in the grader's schema + a detail file). Maintainer
  launched the locked finals chain ~18:40; C10 and the atoms script done while it ran.
- 2026-08-14 (evening, **THE D25 PRIMARY: CREDIT — pooled 0.6185, the first credited
  lever since Rung 3, and the first ever under the larger-of clause**). Maintainer ran
  the locked finals chain (~18:40-18:49 EDT, 5x3000, both encoder env vars, sequential);
  the grader ran attestation-first (R0-15 PASS, transcript in
  results/d25/grade_primary.txt) and then graded: **s52 0.6233 / s53 0.6573 / s54
  0.6063 / s55 0.6073 / s56 0.5980 -> pooled 0.6185; delta +0.0739** over the frozen
  0.54453; clustered se governs (treatment s = 0.0236, comparator s = 0.0356), 2*se =
  0.03820, **operative bar 0.58273 — cleared by +0.036, roughly the margin D23 MISSED
  by**. R0-4 exact-agree on all ten JSONs. Named per the 50M lesson: treatment spread
  is Rung-2-like (0.0236) and the credit survives it — this is NOT a seed-fragility
  band case. **s53's 0.6573 is a new single-lane record** (prior: D23 s44 0.6463);
  the POOLED 0.6185 exceeds every prior pooled result including the 50M finals
  (0.5802). D23's chapter finding ("a 12M win-rate primary is effectively
  un-creditable at advisory-scale effects") is refuted in the only honest way — by an
  effect (+0.074) that is NOT advisory-scale. **CLAIM SCOPE, pre-registered and
  binding: without the shuffled-label placebo (§12, maintainer decision OPEN), the
  licensed claim is "an auxiliary opponent-action loss helps," NOT "an explicit
  opponent model helps"; and §5's CLAIM BOUND caps the mechanism language at "the
  pooled context became more decodable," not "belief state."** M4 obligations FIRED
  ON THE NUMBER (0.6185 >= 0.558): (i) clone re-score at 5x3000 — RUNNING (both
  clone checkpoints, v2/808 process, results/d25/clone_rescore_*_p*.json; first
  attempt died on the 808-vs-828 state-dict mismatch: the 828 id-suffix process
  cannot load the v2/808 clone, and the clone's own protocol-grade precedent is the
  808 process — V2=1, IDS unset); (ii) the SH-exploitation falsifier (two-orientation
  head-to-heads vs the clone via the shim) — OWED. Mechanism co-primary atoms
  (scripts/d25_atoms.py) RUNNING on the frozen s36 tape; first read: treatment live
  ctx units ~247 (s56) vs controls 111-170 on the same tape — the lever visibly
  de-dormantifies the ctx trunk (recorded jointly per §5; the letter's own
  de-dormancy specificity read is r = -0.453 on controls, wrong sign to manufacture
  a positive, but the JOINT record must name the treatment shift).
- 2026-08-14 (evening, cont., **CO-PRIMARY B: LETTER FIRED AT MIN ATTAINABLE p =
  1/252 — IN BOTH LABEL SPACES**). `scripts/d25_atoms.py` ran on the frozen s36 tape
  (sha attested pre-fit; 8 splits; lambda 0.01; all 112 fits converged, max ||g||
  2.4e-04 vs the 1e-3 bound): **L6-native atoms s52 +0.0530 / s53 +0.0659 / s54
  +0.0505 / s55 +0.0619 / s56 +0.0568 (split sds 0.0135-0.0217) -> treatment mean
  +0.0576 vs control +0.0150.** Every treatment atom exceeds every control atom, so
  the exact permutation sits at its floor: **p = 1/252 = 0.003968 vs level 12/252 —
  FIRED** (grader transcript results/d25/grade_with_atoms.txt). 12-class secondary:
  same shape (+0.0476-0.0622, mean +0.0539, p = 1/252), letter-met, reported-not-
  graded. The shift (+0.0426 control-relative) exceeds the WORST admissible-corner
  MDE (0.0301) — this is not a marginal fire. Recorded jointly per §5: **live ctx
  units 220/257/293/271/247 vs controls 170/158/111/164/125 on the same tape** — the
  lever roughly doubles trunk liveness; the §5 de-dormancy specificity (r = -0.453 on
  controls, wrong sign) plus the four R0-12b capacity nulls are the standing answers,
  and the own-tape-gain endogeneity diagnostic still needs the own tapes (collect
  stage queued). CLAIM BOUND stands: "the pooled context became MORE DECODABLE for
  the opponent's next action" — not "belief state", not "opponent model" (that is
  the shuffled-label placebo's to license, §12, OPEN). BOTH CO-PRIMARIES HAVE NOW
  FIRED: win rate CREDIT (0.6185, bar 0.58273) + mechanism at min p. Still owed for
  the full readout: §6 g (LEARNED bar 0.3286), S1/R0-16 dormancy, M4 obligations
  (clone re-score RUNNING, SH-exploitation falsifier), the placebo decision.
- 2026-08-14 (evening, cont., **M4 OBLIGATION (i) DISCHARGED — the clone re-score does
  NOT block**). Both clone checkpoints re-scored at 5x3000 under the locked protocol
  (v2/808 process, --opponent heuristics, R0-4 exact on all ten JSONs,
  results/d25/clone_rescore_{final,best}_p{1..5}.json): **FINAL 0.5537/0.5560/0.5387/
  0.5607/0.5423 -> pooled 0.5503, sd 0.0094** (confirms the v2r protocol-grade 0.5490;
  DESIGN §2's 0.558 was the superseded n=1000 probe and the number conflict resolves
  to the re-score, as the header prescribed); **VAL-PEAK 0.5760/0.5850/0.5937/0.5837/
  0.5800 -> pooled 0.5837, sd 0.0066** (confirms 0.5777). Neither lands above D25's
  pooled 0.6185 — D25 clears even the clone's selection-biased val-peak by +0.035.
  **M4 now rests on obligation (ii) alone**: the SH-exploitation falsifier
  (two-orientation head-to-heads vs the clone, 500/pair/orientation, via the
  cross-encoder shim) + the maintainer's formal blessing. OPEN CHOICE FLAGGED for the
  maintainer: which treatment lane seats the head-to-head (M3's precedent used a
  single lane; the median-final lane s55 0.6073 is the least favorable-looking pick,
  s52/s53 the strongest). Ops note, measured tonight: the first clone chain died
  loading the v2/808 clone in the 828 process — v2/808 ckpts eval under V2=1 with IDS
  unset; the shim is for cross-play seats, not single-checkpoint evals. §6/S1/R0-16
  COLLECT STAGE LAUNCHED post-clone (own oppact tapes s52-56 at 300 eps; obs for
  s50/s51 + s52-56 at 200 eps; then both dormancy passes, control tagged
  d25_control).
- 2026-08-14 (night, **S1: LETTER FIRED at min p = 1/252; R0-16 DISCHARGED in the same
  pass**). The collect stage ran clean post-clone (~19:12-19:36 EDT: own oppact tapes
  s52-56 at 300 eps ~1.8-2.1 MB each; obs s50/s51 + s52-56 at 200 eps; both dormancy
  passes). **R0-16**: the control extends to five lanes — actor ctx_net.1 tau025 at
  12M: s26 0.4844 / s27 0.5000 / s28 0.6432 (frozen, drift-checked by the grader) +
  **s50 0.4896 / s51 0.4115** (results/d23/dormant_d25_control.csv, --tag
  d25_control). **S1**: treatment 0.3385 / 0.2474 / 0.2422 / 0.2370 / 0.2604 —
  every treatment lane BELOW every control — **exact permutation p = 1/252,
  treatment LOWER, FIRED** (results/d25/grade_s1.txt). Read WITH §7's own caveat:
  S1 is a SECONDARY with a known specificity weakness (D18, no actor lever, reached
  p = 0.0893 on the 3-lane control), though tonight's read is at n_C = 5 and the
  floor. Consistent with the §5 joint record (live units ~2x) — the lever
  de-dormantifies the actor ctx trunk, exactly the textbook
  representation-regulariser mechanism §7 named. §6 manipulation check
  (scripts/d25_manipulation.py, g on own tapes vs bar 0.3286) RUNNING.
- 2026-08-14 (night, **§6 MANIPULATION CHECK: LEARNED — median g 0.7055, 2.1x the bar,
  5/5 lanes; THE RUNG'S READOUT IS COMPLETE ON EVERY AGENT-RUNNABLE READ**).
  scripts/d25_manipulation.py on each lane's OWN tape (A1/A3 re-derived per split;
  mirror tapes, so the oracle IS the generator and g > 1.0 had no escape — max lane g
  0.7472, nowhere near it): **g@12M = 0.7472 / 0.7098 / 0.6885 / 0.6634 / 0.7055
  (s52-56), MEDIAN 0.7055 vs LEARNED bar 0.3286 — LEARNED, 5/5 consistency**, and the
  trajectory rises on every lane (3M 0.23-0.42 -> 6M 0.33-0.46 -> 12M 0.66-0.75), so
  the head was still learning at the horizon. A1 1.48-1.54, A3 0.25-0.38, NLL_head
  0.56-0.75 (results/d25/manipulation.json). **THE FALSIFIER (§8) DOES NOT FIRE — this
  is the full-success branch on all four letter-bearing reads:** PRIMARY CREDIT
  0.6185 (bar 0.58273) + CO-PRIMARY B at p = 1/252 (both spaces) + §6 LEARNED (2.1x
  bar) + S1 at p = 1/252, with M4 (i) clear (clone 0.5503/0.5837, both < 0.6185),
  C10 settled, R0-14/15/16 discharged. STILL OPEN, all maintainer-gated: the
  shuffled-label placebo (claim scope: "aux loss helps" is licensed today; "opponent
  model" needs the placebo), M4 (ii) falsifier h2h (lane choice yours) + formal M4
  blessing, and the R0-10(a) g-for-coefficient-selection disclosure stays "proxied"
  (tonight's §6 g is the manipulation check, not that). Session artifacts all under
  results/d25/ (grade_primary/with_atoms/s1.txt, treatment_atoms*.json,
  manipulation.json, clone_rescore_*, oppact_s52-56.npz, obs_s52-56.npz, dormant_d25*).
- 2026-08-15 (early, **M4 OBLIGATION (ii) DISCHARGED — the SH-exploitation falsifier
  PASSES; M4 now awaits only the maintainer's blessing**). Two-orientation
  head-to-head, s55 (median D25 final, the conservative seat) vs the v2r clone FINAL,
  500/orientation via the cross-encoder shim, ties as non-wins on both sides, R0-4
  exact on both JSONs (results/d25/h2h_s55_vs_clone_{A,B}.json): orientation A (s55
  deterministic) **0.8540**, orientation B (s55 from the sampling seat) **0.5840** ->
  **pooled 0.7190 ± 0.0142, z +15.4 vs parity**. The deterministic-vs-sampling seat
  asymmetry is large, as the protocol expects for BC-family opponents — exactly why
  it pools orientations. THE GUARD'S QUESTION ANSWERED: the anchor head-to-head
  MOVED with the vs-SH number (Rung 2: 0.5509 vs SH, 0.657 vs clone -> D25 s55:
  0.6073 vs SH, 0.719 vs clone), so the vs-SH jump is NOT SH-specific. **M4 status:
  pooled 0.6185 >= 0.558 under the locked protocol; obligation (i) clone re-score
  5x3000 discharged (0.5503 final / 0.5837 val-peak, both below); obligation (ii)
  discharged tonight. Formal claim is the maintainer's blessing away** (M2/M3
  precedent). Placebo design cycle running per the 2-Opus mandate (Designer A's memo
  in: within-allow-class permutation + a zero-lane g_allow ceiling gate; Designer B
  drafting; synthesis + reviews next).
- 2026-08-15 (early, **D25-P PLACEBO PRE-REGISTRATION DRAFTED under the 2-Opus
  process; PENDING RATIFICATION**). Maintainer ratified §12 option (1) (5-lane
  letter-bearing arm). Process ran in full: evidence brief -> 2 Opus designers with
  independent framings (A implementation-first, B inference-first) -> synthesis -> 2
  Opus reviews (R1 verification, R2 house-rules) -> all blocking findings folded ->
  configs/showdown_sp_actpred12m_placebo.yaml (header ~330 lines, DRAFT r1). Both
  designers independently converged on the scheme: uniform permutation WITHIN exact-allow
  equivalence classes, valid rows only, once per rollout, dedicated RNG generator.
  REVIEWS EARNED THEIR KEEP: R2 caught two defective HARD gates (per-update
  labelled_frac band would have failed the CREDITED treatment arm on 14-35% of
  updates — the metric drifts 0.86->0.81 over training; and the post-shuffle
  illegality gate as drafted read a PRE-shuffle metric, structurally unable to fire
  — the R0-8 inert-gate lesson twice over), the missing modal-non-null branch, and
  the illegal retro-demotion of §5's banked letter (rewritten to license-narrowing
  per the D23 "recorded verdicts stand" precedent, governed by reproduced fraction
  >= 1/3). R1 re-derived every frozen constant (corrected: clip max 0.1875 not
  0.125; trunk_norm late band [0.083, 0.098] — the draft's 0.085 ceiling excluded
  s53; chance match 0.243-0.330; global-perm illegality 0.42-0.93%), broke the
  identity-row escalation clause (cross-class swaps violate the multiset invariant
  it claims to protect — DELETED), softened the independence claim to the honest
  block-conditional form, validated s_T-frozen-at-0.02357 as an identity, and
  verified both boundary tables cell-by-cell. R0-P5 power sim RUN (200k draws,
  treatment fixed at measured): resolves +0.074 at 0.86-1.00, half-information
  +0.037 at 0.35-0.83 (range quoted), recording band modal at wide spreads
  (0.28-0.35). R0-P3 semantic diff PASSES: exactly seed/run_name/
  aux_shuffle_labels (and caught a real transcription omission, max_grad_norm,
  before commit). OPEN FOR THE MAINTAINER: ratify the header, and P11 — if R-1
  lands in the unresolvable middle, is a third arm (+1.4 lane-days, resolvable
  delta 0.0385 -> ~0.033) pre-authorised, or is 5-and-no-more the pre-commitment?
  Header assumes 5-and-no-more unless ratified otherwise. Build (flag + shuffle fn
  + R0-P1 tests + R0-P2 smokes + R0-P4 grader extension) queued behind
  ratification.
- 2026-08-15 (**D25-P BUILT AND ALL PRE-LAUNCH GATES RUN; R0-P2 PASSES WITH TWO
  DISCLOSED DISPOSITIONS; READY FOR LAUNCH**). Header RATIFIED (P11 = 5-and-no-more,
  the stated default). Build: shuffle_within_allow + marginal_nll
  (rl/networks/opp_action.py), aux_shuffle_labels flag + dedicated generator + loud
  seam + aux/loss_mb0 (rl/agents/ppo.py), meta stamp (rl/train.py); R0-P1 battery 11
  tests incl. the lag-correlation/fixed-point kills; R0-P4 grader placebo mode with
  synthetic boundary tests; suite **339 -> 354 green**. R0-P0: dose_bins.json frozen
  and REPRODUCES review R1's independent table bin-for-bin. results/d25/ BACKED UP to
  ../pokemon-showdown-rl-d25-backup-20260815/ (114 files; tapes re-attested green
  post-copy). **R0-P2 (paired seed-99 smokes, one at a time):** all hard zeros hold
  (illegal/collision/shuffle_illegal 0.000000); placebo aux/loss PINS AT ITS FLOOR
  (loss_mb0 - marginal_nll = +0.010/+0.017 across the two placebo runs, band
  [-0.05, +0.10]); labelled_frac 0.8749 in the smoke band; trunk ratio 0.0685 in
  [0.05, 1.5]; shuffle_match_frac 0.267 (predicted 0.243-0.330), identity_frac
  0.0005 (predicted 0.0002-0.0007), n_classes 2-4 (predicted 3-4). TWO ACCEPTANCE
  ITEMS DID NOT PASS AS WRITTEN, dispositions recorded: **(c) update-1 bit-identity
  is VOID-BY-PREMISE** — the Showdown server rolls fresh teams/damage every run
  regardless of seed (measured 2026-08-05, rl/common/evaluation docstring), so two
  runs NEVER share a rollout and the check cannot pass on any build; the property it
  witnessed (shuffle consumes no collection RNG) is proven at unit level
  (test_determinism_and_dedicated_stream). **(f) wall +-5% failed on the first pair
  (0.861) and passed on an A-B-A re-measure** — T1 418.3 / P1 360.2 / P2 402.9 /
  T2 412.3: the treatment itself varies 1.4% between identical runs, P1 was an
  11%-scale infra outlier, P2/T-mean = 0.970 is in band; no mechanism exists for an
  O(microseconds/rollout) shuffle to cost 14%; the binding protection at scale is
  R0-8's during-run wall gate (255/210) regardless. Both dispositions travel with
  the launch record; the maintainer's launch is their ratification. P1's entropy
  0.807 (vs T 1.290) also normalised on the re-run (P2 1.150) — batch noise at 100k,
  recorded. Smoke artifacts: runs/showdown_sp_actpred_smoke_{c010_p2,c010_p2b,
  placebo,placebo_b}. Launch: 5 lanes, seeds 57-61, staggered screens, verify by
  battle PROGRESS; grader path at readout: scripts/d25_grade.py --placebo <dir>.
- 2026-08-15 (evening, **D25-P LAUNCH RECORD — 5 lanes away, seeds 57-61**).
  Maintainer launched ~19:55 EDT (s61 relaunched minutes later on the SAME seat
  after my handed-over block carried a typo — `WANDB_MODE=OFFLINE=offline` — and
  died before creating a run dir or touching the server, so the zombie-battle
  landmine did not apply; the typo is mine, recorded). Verified by battle PROGRESS
  on all five (29.7k-34.7k steps at ~2 min, s61 7.1k at launch+~30s; ~315 steps/s
  5-wide), R0-1 stamps correct (`aux_shuffle_labels: true`, l6) on every meta.yaml,
  `git_dirty: false`. **THE PLACEBO SIGNATURE IS LIVE ON EVERY LANE: aux/loss
  1.541-1.565 pinned at aux/marginal_nll 1.514-1.539**; aux/shuffle_illegal_frac
  0.000000 x5 (the post-shuffle HARD gate); match_frac 0.236-0.298 vs the frozen
  chance band 0.243-0.330 (s61's 0.236 is a first-reading sample); identity_frac
  0.0000-0.0011 (predicted 0.0002-0.0007 scale). WATCH: R1 at 4M (arm stops <3 of
  5, branch B6), K6 before 6M, R0-8 wall (255/210), P-SHUF (per-1M-bin median of
  loss_mb0 - marginal_nll < -0.03 x3 bins), VOID clause at matched steps. ETA ~11 h.
  At the finals: locked eval 5x3000 into results/d25p/final_s{57..61}.json, then
  scripts/d25_grade.py --placebo results/d25p; atoms via d25_atoms.py (placebo
  lanes), dormancy --tag d25_placebo. OWED while lanes run: the R-4 adaptation of
  d25_manipulation.py for placebo lanes (g_P vs the 0.02 band; A0 reference
  1.773-1.780).
- 2026-08-15 (evening, **M4 CLAIMED — maintainer's formal blessing ("M4 blessing");
  THE PRE-REGISTERED LADDER IS COMPLETE, M1-M4, ALL ON PURE FROM-SCRATCH
  SELF-PLAY**). The claim rests on, all under the locked protocol: D25 pooled
  **0.6185** >= DESIGN §2's 0.558 bar (5x3000, R0-15-attested comparator);
  obligation (i) the clone re-scored at 5x3000 — final 0.5503 (sd 0.0094),
  val-peak 0.5837 (sd 0.0066), BOTH below D25's pooled, resolving the
  0.558-vs-0.5490 number conflict by re-score as the header prescribed;
  obligation (ii) the SH-exploitation falsifier — s55 vs clone 0.7190 pooled over
  two orientations (z +15.4), the anchor edge MOVING with the vs-SH number
  (0.657 at 0.5509 -> 0.719 at 0.6073), so the gain transfers off-SH. What M4
  means and does not mean: the pure self-play agent now exceeds, vs SH AND
  head-to-head, the behaviour clone of Foul Play — the strongest imitation-of-
  search anchor in the repo — while the ENGINE itself (0.8307 vs SH) remains far
  ahead; M4 is the last LADDER rung, not parity with search. Claim scope on the
  LEVER (opponent model vs aux loss) still awaits D25-P, running now — M4 is a
  WIN-RATE milestone and is not conditioned on that attribution.
- 2026-08-15 (night, **HANDOFF FOLDED; D25-P HEALTH CHECK #1 AT T+19 MIN — 5/5 GREEN,
  two during-records resolved**). Stub restored; the handoff's operational chain now
  lives in STATUS.md "Next actions" and the do-not-rediscover items below. All five
  screens (`d25p_s57`..`s61`) detached and alive; verified BY BATTLE PROGRESS after
  re-extracting history.csv on every lane (wandb offline — a stale CSV is not a stalled
  lane). At ~20:14 EDT: steps 325.9k-355.4k, `time/steps_per_sec` 341-359 per lane,
  wall projection **10.89-11.31 h to 12M** (finals ~06:45-07:15 EDT Aug 16, matching the
  ~11 h launch estimate). **THE PLACEBO SIGNATURE HOLDS AT SCALE**: `aux/loss` 1.508-
  1.584 pinned +0.0125 to +0.0152 ABOVE `aux/marginal_nll` on every lane (the head is
  at its floor and cannot beat the marginal); `aux/shuffle_illegal_frac` **0.000000 x5**
  (the HARD post-shuffle gate); `aux/shuffle_identity_frac` whole-run means 0.00044-
  0.00062, 16-23x under the 0.01 record-and-investigate line; `aux/labelled_frac`
  0.7906-0.8176, inside the during-band [0.78, 0.88] (NOT the 0.84-0.88 smoke band);
  `selfplay/winrate_anchor` 0.962-0.971 — R1's 0.75-by-4M gate is already clear 5/5,
  so branch B6 (PLACEBO-HARMS) is not in play on current evidence. `loss/entropy`
  0.519-0.807, well above K6's 0.15 floor. P-SHUF partial bin-0 medians of
  (`aux/loss_mb0` - `aux/marginal_nll`) are **+0.017 to +0.030** — the WRONG SIGN for a
  leak (the trigger is < -0.03 x3 consecutive bins); first complete bin lands at 1M.
  TWO DURING-RECORDS RESOLVED, both benign, both worth not rediscovering. (1)
  **match_frac**: the launch record flagged s61's 0.236 against "the frozen chance band
  0.243-0.330". That range is the CLOSED-FORM chance rate (sum_c p_c sum_y q^2, header
  l55/l97), a prediction from treatment-era tapes; **the GATE is that range +-0.05 =
  [0.193, 0.380]** (l153). Whole-run lane means are 0.2400/0.2420/0.2431/0.2442/0.2712
  (R0-P2 smokes: 0.2673/0.2668) — three lanes sit marginally under the closed form's
  0.243 floor and ALL FIVE clear the gate with wide room; max 0.358, never ~1.0, so the
  identity-permutation failure is excluded. Read this gate on lane MEANS, not per-update
  (per-update range 0.175-0.358; same lesson as labelled_frac, R0-P2). (2) **trunk ratio
  (R0-10b)**: the metric is `aux/trunk_norm` / `aux/policy_trunk_norm` as a RATIO OF
  MEANS (`scripts/d25_gates.py:816`; a mean-of-ratios is Jensen-inflated 1.3-1.5x — I
  inverted it once, note the direction). Provisional whole-run-so-far: **0.0447/0.0472/
  0.0563/0.0533/0.0447 — three of five BELOW the [0.05, 1.5] floor**, and below the
  placebo smoke's own 0.0685, while the treatment ran 0.125-0.130 live (smoke 0.1137).
  This is NOT a defect and must not be reported as a failed gate: R0-10b is a
  during-RECORD per 1M bin (no bin is complete at 0.35M), and the header ALREADY
  PREDICTS the direction — the named deviation from §12 (l60-67) states that no
  zero-information placebo can match gradient magnitude, because at the head's floor the
  placebo's trunk gradient is ZERO-MEAN minibatch noise while the treatment's has a
  coherent component; "magnitude is MEASURED (P3), not matched." So a decaying trunk
  ratio is the predicted placebo behaviour, not a build fault. It DOES bear on the
  readout: the arm controls for label INFORMATION, not for trunk-gradient MAGNITUDE, so
  carry the measured ratio into how **B4 and the a-fortiori clause** are read (the header
  says so explicitly) and disclose it alongside the B1 UPGRADE caveats if B1 fires.
  Nothing owed to the maintainer tonight; next reads are the R0-8 WARM wall (>=30-min
  window after 1M: record <255, STOP <210), then R1/K6, then the finals.
  ADDENDUM — the handoff's do-not-rediscover items, banked here so STATUS can point
  instead of carry. **Expected outcome shapes:** placebo win rate near 0.545 plus an
  R-1 credit = branch **B1 UPGRADE** — the licensed sentence becomes "an explicit
  opponent-action model helps" with the C3(b)/C4 caveats attached, and NEVER "belief
  state". R-1's credit boundary: placebo <= 0.5935 / 0.5871 / 0.5800 at s_P = 0 / 0.026
  / 0.036. At wide spreads the modal non-null outcome is the RECORDING BAND (B9). **A
  null R-2 alone licenses NOTHING** — that is the binding pre-statement P0. **P7 branch
  precedence:** B7 (R-4 leak / never-trained) and B6 (placebo-harms) adjudicate FIRST,
  then B1-B5/B8/B9; every branch carries its own STATUS/README obligation, discharged in
  the readout entry. **R-3 governance:** §5's banked letter NEVER loses its number or
  its verdict; the LICENSE narrows iff R-3(a) fires AND (mean_P - 0.0150)/0.0426 >= 1/3
  (the fraction governs on disagreement). **Ops:** screens survive agent jobs
  (`screen -r d25p_s57`, ctrl-a d); server on :8000; the fleet must be DOWN before any
  tape/obs collection. The R0-P2 (c) update-1 bit-identity check is VOID-BY-PREMISE (the
  server rolls fresh battles every run, measured 2026-08-05) — do not re-run it and do
  not read its failure as a build defect; wall noise at 100k-smoke scale is ~10%, and
  R0-8 is the gate that governs at 12M. C10 (tapes exclude forced replacements BY
  CONSTRUCTION, 0 of 53,848 rows; live loss included double-faints at ~0.12%) is
  disclosed at readout.
- 2026-08-15 (night, **THE OWED BUILDS LANDED WHILE THE LANES RUN: R-4 written, atoms
  parametrised**). Both were the handoff's "owed while lanes run" item; neither touches
  a running lane. (1) **`scripts/d25p_manipulation.py` — R-4, the placebo §6 check.**
  Written as a SIBLING of `d25_manipulation.py` rather than a flag on it: that script
  produced the BANKED §6 treatment letter (median g 0.7055) and has to stay reproducible
  bit-for-bit, so it is untouched and the estimator is shared by import — g_P and the
  treatment g are unit-compatible by construction, not by convention. Implements the
  header's two views of one statistic: |g_P| <= 0.02 SHUFFLE CONFIRMED / < 0.10 RESIDUAL
  / >= 0.10 LEAK / <= -0.10 DERANGEMENT (sign matters — the negative branch is
  anti-information, not a leak), and NLL_head against the floor with TRAINED-TO-FLOOR
  (|NLL_head - A1| <= 0.02, the DESIGNED outcome), NEVER-TRAINED (>= A0 - 0.05, arm
  VOID) and PARTIALLY-TRAINED (the R2-11 middle cell -> R-1 DOSE-CAVEATED, not void).
  Reads 3M/6M/12M and flags RISING |g_P| as the leak signature (R2-17). **Two places the
  pre-registration underdetermines the read, both surfaced rather than quietly resolved:**
  (i) R-4 fixes the bands but never names the ACROSS-LANE AGGREGATOR — §6's median is
  inherited and said so in the docstring and the printout, with the worst lane's |g_P|
  printed beside it so a maintainer who wants max-governs can read it without a re-run;
  (ii) the header's cells leave (A1 + 0.02, A1 + 0.05] unnamed, so a lane landing there
  prints NEAR-FLOOR (unnamed cell — disclose) instead of being folded into a neighbour.
  A0 is MEASURED per lane (mean log of the legal-class count) rather than assumed from
  the treatment tapes' 1.773-1.780; the formula was sanity-anchored against log 6 =
  1.7918, the all-six-legal ceiling the reference range sits just under. 16 tests
  (`tests/test_d25p_manipulation.py`), all green. One recorded quirk: the inclusive <=
  at the TRAINED-TO-FLOOR boundary loses to float representation (1.5 + 0.02 exceeds A1
  by 1.8e-17), so an exact-boundary lane reads NEAR-FLOOR — a disclosure, not a silent
  reclassification, and real NLL_head values do not land on the boundary. (2)
  **`d25_atoms.py` gained `--lanes` / `--run-prefix` / `--out`.** The handoff prescribed
  editing LANES, the prefix and the output path IN PLACE for the placebo run; that would
  have overwritten the defaults behind §5's banked treatment atoms
  (+0.0530/+0.0659/+0.0505/+0.0619/+0.0568). Flags instead, defaults byte-identical to
  the banked invocation (`out.stem + "_detail.json"` reproduces
  `treatment_atoms_detail.json` exactly), placebo command in the docstring. Same frozen
  s36 tape and the same sha assertion either way — only whose ctx is read changes.
  NOT DONE, and deliberately: the full suite was not re-run tonight. Five lanes are
  saturating the CPU and R0-8's WARM wall is a THROUGHPUT gate — a suite run inside that
  window would depress the number the gate reads. The D25 subset (70 tests across
  test_d25_grade / test_d25_placebo / test_d25p_manipulation / test_opp_action) is green;
  run the full suite after the wall reading is banked.
  CROSS-CHECK, RUN AND PASSED (the reason `--run-prefix` is on the R-4 CLI): pointing
  the NEW estimator at a TREATMENT lane and tape reproduces §6's banked number to the
  digit — `d25p_manipulation.py --tape-dir results/d25 --run-prefix
  showdown_sp_actpred12m_s --lanes 52` returns **g@12M = +0.7472, exactly the frozen
  s52 attestation value**, with g@3M/6M = +0.4177/+0.4585 (the rising trajectory §6
  recorded), n = 7273 at 95.7% kept, and **A0 measured 1.7785 — inside the documented
  1.773-1.780 without being told the range**, which independently confirms the
  uniform-over-legal formula. The verdict line correctly reads LEAK / BELOW-FLOOR /
  arm-VOID on that input: a treatment lane run through PLACEBO bands SHOULD look like a
  massive leak, because its labels really do carry information — so the bands are
  oriented the right way round. This is the strongest available check short of the
  placebo tapes themselves, which cannot be collected until the fleet is down.
- 2026-08-15 (night, **R0-8 WARM WALL READ AND BANKED — ALL FIVE CLEAR, and the metric
  you would reach for first is the WRONG ONE**). The gate: a >=30-min window after 1M,
  record below 255 steps/s, STOP below 210. Window opened ~20:50 EDT and closed ~21:21;
  read at 21:23 over each lane's own post-1M span (32.1-34.5 min, 596k-659k steps
  inside the window). **WALL throughput, delta_step / delta_runtime: s57 312.2, s58
  312.0, s59 313.8, s60 318.1, s61 309.5 — 5-lane median 312.2, range 309.5-318.1.
  Every lane clears the record line by >=21% and the STOP line by ~48%. R0-8 IS
  DISCHARGED**; no lane is stopped, nothing is recorded against the arm. Fleet
  throughput is flat against launch (~315 5-wide at T+2min) and against the T+19min
  projection, so the 12M ETA holds at ~10.8-11.3 h -> finals ~06:45-07:15 EDT Aug 16.
  **THE LANDMINE, measured tonight: do NOT read R0-8 off `time/steps_per_sec`.** That
  key averages 361 on the post-1M rows and would say every lane clears by 42%; the true
  wall is 312. The two are not the same population — post-1M, s57 logs
  `time/steps_per_sec` 17,166 times against 627 updates (`time/collect_sec` /
  `time/update_sec` appear once per update, `time/eval_sec` 7 times), so the key is
  emitted at a far finer granularity and its mean is not a throughput. On the 134 rows
  where both keys happen to appear its mean is 53.2, a third regime again — which is
  the tell that pairing them is meaningless. Read the gate as delta_step over
  delta_runtime and nothing else. The honest decomposition of s57's 2058 s window, which
  DOES reconcile: collect 1588 s + update 340 s = 1928 s -> 333.0 steps/s; plus eval
  42 s -> 325.9; plus 88 s (4.2%) of checkpoint/logging/pool overhead -> 311.9, the
  wall. So eval and fixed overhead cost ~6.3% of throughput, and that is the entire
  gap between the per-update rate and the gate's number.
  Suite re-run after the wall reading was banked (the reason it was deferred): **370
  passed, 0 failed, 27 s** — 354 carried plus R-4's 16. The documented flake
  (`test_full_episode_contract_against_live_server`, which fails when the whole suite
  runs with a server up) did NOT fire this time despite five lanes and the server being
  live; recorded as a data point on that flake, not as a fix.
- 2026-08-16 (morning, **D25-P FINISHED CLEAN — ALL 12M, EVERY DURING-GATE PASSES, AND
  THE PRE-STATED P3 DOSE READ FIRES: DOSE-CAVEATED ON 12/12 BINS**). Recorded BEFORE any
  placebo win rate was computed or looked at — the ordering is checkable in git history,
  and it matters, because a dose caveat discovered after seeing the outcome would be
  worth much less. **All five lanes reached exactly 12,000,000 steps and exited
  normally** (screens gone, `ckpt_012000000.pt` + final `checkpoint.pt` on every lane,
  mtimes 06:15-06:21 EDT, wall 10.34-10.44 h — slightly faster than the 10.8-11.3 h
  projection). No lane was lost; seeds 62/63 were never needed.
  **DURING-GATES, all five lanes, whole run.** HARD: `aux/shuffle_illegal_frac` == 0 on
  **all 11,718 updates x 5 lanes, zero exceptions** — the post-shuffle legality gate
  never fired once. `aux/shuffle_match_frac` lane means 0.2566/0.2819/0.2900/0.2722/
  0.2860, every one inside the [0.193, 0.380] gate, max single-update 0.4127 and never
  near 1.0 (identity permutation excluded). R1: `winrate_anchor` at 4M
  0.972-0.978 on all five, final 0.978-0.983 — **B6 does NOT fire**. K6: minimum 5-lane
  median entropy over the 5,859 pre-6M readings is 0.2460, never once below 0.15 — not
  triggered (per-lane final 0.203-0.284, per-lane min 0.093-0.172). R0-6: mean episode
  length after 3M 29.94-32.53 (<= 40) and ties 0.15-0.22% (<= 4.2%). RECORD-AND-CONTINUE:
  `aux/labelled_frac` whole-run means 0.8009-0.8110, inside [0.78, 0.88];
  `aux/shuffle_identity_frac` means 0.000500-0.000620, 16-20x under the 0.01 line.
  **P-SHUF: CLEAR on every lane and it is not close** — the per-1M-bin medians of
  (`aux/loss_mb0` - `aux/marginal_nll`) span **+0.0058 to +0.0187 across all 60
  lane-bins, always POSITIVE**, versus a trigger of < -0.03 for 3 consecutive bins;
  longest run below -0.03 is 0 on all five. The memorisation-free tracker never once
  dipped under the batch marginal in 12M steps, which is the strongest during-run
  evidence available that the shuffle held.
  **VOID clause: does not fire, and reading it naively would have voided the CREDITED
  arm.** Placebo `loss/grad_clip_frac` whole-run means 0.8812-0.9705; the treatment lanes
  s52-56 run 0.9729-0.9929. Four of five placebo lanes sit above the 0.90 figure — but so
  do ALL FIVE treatment lanes, by more. The placebo is if anything LESS clipped than the
  arm it controls, so at matched steps there is nothing to void. `aux/grad_clip_frac` is
  exactly 0.000000 on every placebo bin (the treatment's frozen table has small nonzeros
  from bin 4 on, max 0.001793) — the aux clip never binds, so P3's "the declared
  coefficient stops being the effective one" branch is clean.
  **THE HEADLINE: THE PRE-STATED DOSE READ (P3, per-1M bin, matched steps) RESOLVES TO
  DOSE-CAVEATED ON ALL TWELVE BINS.** The rule: placebo `aux/trunk_norm` >= the frozen
  bin band -> generic-aux refuted A FORTIORI; < 0.7x the band's low edge -> the null is
  DOSE-CAVEATED. Measured against `results/d25/dose_bins.json`, the placebo's bin medians
  are **0.0137-0.0173 in bin 0 falling to 0.0011-0.0022 in bin 11**, against a band that
  holds steady at 0.079-0.098 (low edge) all run. As a fraction of the 0.7x threshold
  the worst-lane value is **0.313 in bin 0 and 0.033-0.056 from bin 4 on** — one to two
  orders of magnitude short, in every bin, with no bin ambiguous and the a-fortiori
  branch unreachable even at bin 0. The trunk RATIO tells the same story from the other
  side: treatment holds 0.094-0.108 whole-run and 0.095-0.134 per bin across all 12
  bins, while the placebo starts at 0.025-0.029 in bin 0 and decays to 0.0000-0.0031 by
  bin 11 (whole-run 0.0002-0.0070; s58 is effectively zero). `aux/grad_norm` shows it at
  the head too: placebo 0.022-0.034 against a band of 0.098-0.164.
  **What this does and does not mean.** It is NOT a fault, NOT a void, and NOT a
  surprise in DIRECTION — P1's zero-mean caveat and the header's named §12 deviation
  both predicted that no zero-information placebo can match gradient magnitude
  ("magnitude is MEASURED (P3), not matched"). What is new is the MAGNITUDE: the
  shuffled-label head converges to the marginal within roughly the first 1M steps and
  thereafter injects almost nothing into the trunk. So the header's TRAINED-TO-FLOOR
  wording — "a real aux gradient was injected for 12M steps" — is only fair for the
  first bin or so; from bin 4 on the injected trunk gradient is ~3-5% of the treatment's.
  CONSEQUENCE FOR THE READOUT, binding because it is pre-stated: the a-fortiori
  refutation of "a generic aux gradient is what helps" is NOT available on this arm, and
  the dose caveat must be written into whichever branch fires. NO re-tune and NO relaunch
  (one-lever, D17); the caveat is the action. R-4 will read the same fact from the
  NLL_head side once the placebo tapes exist.
  IN-LOOP PREVIEW, read only AFTER the dose read above was committed, and NOT a result:
  the lanes' own `eval/win_rate` (n=100, `eval_opponent: heuristics` — the SAME opponent
  as the locked protocol, so it is on-scale) ends 0.58/0.50/0.57/0.63/0.60, 5-lane mean
  **~0.576**. Calibrated on the TREATMENT arm, that statistic is near-unbiased for the
  locked pooled number: treatment in-loop mean 0.6160 vs locked pooled 0.6185, bias
  +0.0025, though per-lane it swings -0.073 to +0.083 at n=100 (se ~0.05, so ~0.022 on
  the 5-lane mean). **0.576 sits just UNDER R-1's credit boundary (<= 0.5935/0.5871/
  0.5800 at s_P = 0/0.026/0.036) — inside the noise of it. The finals genuinely decide
  this; no branch may be pre-announced.** Worth flagging: 0.576 is ABOVE the ~0.545 the
  pre-registration expected for the placebo, i.e. the placebo may have moved ~+0.03 over
  the frozen comparator. If that survives the locked eval it sits in tension with the
  dose read — a lane that received 3-5% of the treatment's trunk dose from bin 4 on
  should not gain much FROM the aux gradient, so the honest candidates are comparator
  spread (5-lane sd 0.0356, se ~0.016) or the RECORDING BAND (B9), not "generic aux
  helps". Do not resolve that here; it is the readout's job.
  PROTOCOL CONFIRMED for the finals: the treatment used NO extra eval flags —
  `seed_start` is `cfg.eval_episodes` = 100 on both arms, and `--no-shaping` is a
  provable no-op (env default `hl_shaping: float = 0.0`, absent from both configs'
  env_kwargs), which the treatment finals corroborate by having `win_rate ==
  wins_from_returns` exactly (R0-4). So the placebo eval is bit-comparable with no flag
  differences at all.
- 2026-08-16 (midday, **D25-P READOUT INPUTS: R-1 CREDITS (0.5415 vs 0.6185), R-2 FLAT,
  R-4 SHUFFLE CONFIRMED — B7 does NOT fire, B6 does NOT fire, the grid lands on B1**).
  Maintainer authorised me to run the evals in-session ("sub 1h"); the whole locked set
  took **10 min**, 5 lanes sequential at ~2 min each (11:53:52-12:03:20).
  **LOCKED FINALS (5x3000 vs SH, ties=loss, final ckpt, both env vars, no extra flags):
  s57 0.5763 / s58 0.4967 / s59 0.5600 / s60 0.5473 / s61 0.5273 -> POOLED 0.5415, seed
  sd 0.0308.** R0-4 exact on all five (`win_rate == wins_from_returns` to the digit).
  Attestation PASSED before any placebo number loaded: comparator re-derived 0.54453 vs
  frozen 0.54452 (sd 0.03561 vs 0.03558), both reference tape sha256s OK.
  **R-1 (PRIMARY): CREDITS.** treatment 0.6185 vs placebo 0.5415, delta **+0.0770**;
  se_diff binomial 0.00568 vs seed-clustered 0.01735 -> the LARGER (clustered) governs,
  2*se = 0.03471, credit boundary placebo <= 0.58379. The delta is 2.2x the bar and the
  placebo is 0.042 below the boundary. **R-2: FLAT** — placebo vs frozen comparator
  delta **-0.0030** (letter bar 0.56953, operative 0.58666), the modal pre-stated
  outcome. The placebo landed essentially ON the comparator, which is the textbook shape
  for a working placebo.
  **R-4 (B7, precedence): SHUFFLE CONFIRMED.** Own 300-ep mirror tapes per lane
  (7223-7881 paired rows, 300 battles each, structurally matched to the treatment
  tapes' 7601-10160). 5-lane median g_P = **-0.0118**, inside the |g_P| <= 0.02
  CONFIRMED band; per-lane -0.0037/+0.0124/-0.0118/-0.0166/-0.0226; **RISING |g_P| on
  0/5 lanes — not the leak signature** (the trajectories mostly SHRINK: e.g. s59
  -0.0303 -> -0.0128 -> -0.0118). g_P is mildly NEGATIVE on 4 of 5, which is what an
  out-of-sample head fitted to permutation noise should do, and nowhere near the -0.10
  derangement line. VIEW 2: **4/5 TRAINED-TO-FLOOR** (NLL_head - A1 = -0.0130 to
  +0.0190) — the DESIGNED outcome; no lane NEVER-TRAINED (A0 measured 1.7703-1.7761,
  NLL_head 1.373-1.532, nowhere near it) and no lane PARTIALLY-TRAINED. **So B7 does not
  fire and the arm is not void.**
  **BOTH GAPS I FLAGGED IN THE R-4 BUILD ACTUALLY MATERIALISED — worth the flagging.**
  (i) The aggregator: the 5-lane MEDIAN reads CONFIRMED (0.0118), but the WORST lane
  (s61, |g_P| 0.0226) sits just inside RESIDUAL (0.02-0.10). **The branch is ROBUST to
  the choice — both are far below the 0.10 LEAK line, so B7 does not fire either way** —
  but if the maintainer prefers max-governs, the letter reads "RESIDUAL, disclosed,
  caveats R-1" rather than "CONFIRMED". Only the wording moves. (ii) The unnamed cell:
  s61's NLL_head - A1 = +0.0260 lands in (A1+0.02, A1+0.05], which the header never
  names; it prints NEAR-FLOOR and is disclosed rather than folded into a neighbour.
  **BRANCH: B1 UPGRADE** (R-1 credits, R-2 does not), with B7 and B6 both cleared first
  per P7 precedence. Licensed sentence: "an explicit opponent-action model helps", with
  C3(b) self-model and C4 representational-only attached IN THE SAME SENTENCE, and never
  "belief state". **THE DOSE CAVEAT IS NOW LIVE AND MUST JOIN THEM:** P3's rule attaches
  to a NULL, and R-2 is exactly that null — the placebo delivered 3-31% of the frozen
  trunk band (12/12 bins DOSE-CAVEATED), so R-2's flatness does NOT refute "a generic
  aux gradient is what helps"; that alternative is untested at matched dose, not
  eliminated. Recorded blind this morning, before any win rate was seen.
  **MY IN-LOOP PREVIEW WAS WRONG AND THE INTERVAL WAS TOO TIGHT.** I quoted ~0.576 +-
  0.022 from the n=100 in-loop metric; the locked answer is 0.5415, off by -0.035 and
  outside the band I gave. It tracked on s57/s58/s59 (0.58/0.50/0.57 vs 0.5763/0.4967/
  0.5600) but s60 and s61's last in-loop readings were high by ~0.08 (0.63/0.60 vs
  0.5473/0.5273). The treatment-arm calibration (+0.0025 bias) did not transfer.
  **Do not use the in-loop eval to preview a locked number again**, not even as a
  5-lane mean; the per-lane n=100 noise does not average out at n_lanes = 5. Still
  outstanding: R-3 (atoms) and R-5 (dormancy), inputs collecting now.
  **R-5 INPUTS COLLECTED (obs 200 eps/lane, then `d22_dormant_rank.py --tag d25_placebo`
  on the treatment's own step grid 400k/3M/6M/9M/12M — NEVER the control tag).** Placebo
  actor `ctx_net.1` tau025 at 12M: **0.4453 / 0.4297 / 0.5339 / 0.6641 / 0.7266, mean
  0.560**, against controls 0.4844/0.5000/0.6432/0.4896/0.4115 (mean 0.506) and treatment
  0.3385/0.2474/0.2422/0.2370/0.2604 (mean 0.265). **The placebo does NOT de-dormantify —
  it is slightly MORE dormant than the controls, and the treatment sits far below both.**
  Per §7's pre-stated joint reading that is the branch where **de-dormancy TRACKS THE
  INFORMATION** (still caveated: S1 is a SECONDARY, and at n = 3 a dormancy letter is a
  level-0.26 test, D18 having reached p = 0.0893 on the 3-lane control). S1's banked
  letter keeps its number either way; this is the reading that does NOT force the
  "side effect" re-narration. Effective rank is a separate, unpretty story worth
  recording: the placebo's actor ctx srank99 COLLAPSES over training (s57 227->111,
  s58 218->14, s59 228->49, s60 244->21, s61 193->11 across the five steps) while its
  dormancy stays high — a narrow, largely-dead ctx. Do not conflate the two metrics;
  R-5 reads tau025, and the STATUS watch item on "live ctx units 220-293" is a THIRD
  metric again.
- 2026-08-16 (**D25-P READOUT — BRANCH B1 UPGRADE. The claim widens from "an aux
  opponent-action loss helps" to "an EXPLICIT OPPONENT-ACTION MODEL helps", with three
  caveats bolted on. Every pre-registered read is in.**) Full grid, all inputs present,
  transcripts frozen at `results/d25p/grade_placebo.txt` and `r4_manipulation.txt`:
  **R-1 PRIMARY: CREDITS.** placebo 0.5415 vs treatment 0.6185, delta +0.0770 against a
  seed-clustered 2*se of 0.03471 (clustered 0.01735 governs over binomial 0.00568);
  boundary 0.58379, cleared by 0.042. **R-2: FLAT**, -0.0030 vs the frozen comparator.
  **R-3(a): NOT FIRED** — placebo atoms +0.0155/-0.0016/+0.0058/+0.0016/+0.0143 (mean
  **+0.0071**) are BELOW the controls' +0.0150, exact p = 239/252 = 0.948. The
  governance fraction is (0.0071 - 0.0150)/0.0426 = **-0.185 against a bar of 0.333**,
  so **the LICENSE DOES NOT NARROW** — and both governance conditions fail, not just
  one. Grader's own rider, carried verbatim: a silent (a) does NOT clear specificity
  below §5's MDE range 0.0105-0.0301. **R-3(b): FIRED at the floor**, treatment +0.0576
  vs placebo +0.0071, p = **1/252**. **R-4: SHUFFLE CONFIRMED** (median g_P -0.0118, 0/5
  rising, 4/5 TRAINED-TO-FLOOR) — **B7 does not fire**. **R-5(a): NOT FIRED** — placebo
  dormancy 0.5599 vs controls 0.5057, p = 196/252 = 0.778, i.e. the placebo is if
  anything MORE dormant; graded against all five controls only after passing
  `--s1-control results/d23/dormant_d25_control.csv` (the default CSV holds s26/s27/s28
  only, and with n_C = 3 the grader correctly REFUSES to grade — the pre-stated levels
  are enumerated against five). **R-5(b): FIRED at the floor**, treatment 0.2651 vs
  placebo 0.5599, p = **1/252**. B6 was already cleared (R1 5/5).
  **SO: B7 no, B6 no -> the R-1 x R-2 grid gives B1 UPGRADE.** The licensed sentence,
  with everything the pre-registration requires attached IN THE SAME BREATH: *an
  explicit opponent-action model helps — the labels being the agent's own mirror-self
  (C3(b): as much a self-model as an opponent model), the evidence being that the
  representation became more decodable rather than that the policy consults it (C4),
  and a generic auxiliary gradient of matched size remaining UNTESTED rather than
  refuted (the P3 dose caveat: 3-31% of the frozen trunk band, 12/12 bins).* NEVER
  "belief state". Three converging separations make this the strongest rung in the
  repo: win rate (+0.0770, clustered rule), the mechanism atom (p = 1/252) and dormancy
  (p = 1/252) all split treatment from a placebo that is otherwise identical in head,
  coefficient, cadence, label marginal and legality.
  **What the placebo actually did:** landed on the comparator (0.5415 vs 0.54452), left
  its ctx LESS decodable than the controls' (+0.0071 vs +0.0150), stayed MORE dormant
  than the controls (0.560 vs 0.506), and sat at its marginal floor throughout. It is a
  clean null on every axis, which is exactly what makes R-1 readable.
  **OBLIGATIONS DISCHARGED.** README headline rewritten (B1 requires it): the claim
  scope paragraph now states the placebo result, the licensed sentence and all three
  caveats; the results table gains the placebo row (0.5415 +- 0.0041). STATUS results
  row updated. **LEDGER RE-MEASURED, not incremented** (the 2026-08-13 audit's rule):
  sweeping every run dir with usable timing (`started_at` -> last-ckpt mtime) gives
  **497.7 lane-hours = 20.74 lane-days total, of which pre-chase 2.83, so the r7
  PURE-SELF-PLAY CHASE stands at 429.7 h = 17.91 LANE-DAYS** across 78 lanes. That
  reconciles with the audited 13.54 plus D25's 2.16 and D25-P's 2.17 (= 17.87, rounding
  aside) — the ~18.25 the handoff projected was a shade high. D25-P cost 2.17 lane-days.
  **STILL OPEN, and the honest limits of this rung:** R-6's recorded-no-letters set
  (h2h placebo-vs-treatment, S3-P entropy, S5-P reveal-stage, S7-P sensitivity, dose
  curves) was NOT run; the R-4 aggregator wording is the maintainer's call (median reads
  CONFIRMED, worst lane s61 |g_P| 0.0226 reads RESIDUAL — the branch is identical either
  way); s61's NLL_head sits in the header's unnamed near-floor cell; and vs-SH at 0.6185
  is still ~40% GXE territory, so none of this is "nearly solved".
- 2026-08-16 (**R-4 AGGREGATOR ADJUDICATED — SHUFFLE CONFIRMED, and on substance rather
  than on the median convention**). Maintainer delegated the call. Deciding it by
  "inherit §6's median" would have been an appeal to convention; the sign structure
  settles it properly. **Leakage is a POSITIVE-g_P phenomenon** — retained information
  lets the head BEAT the class marginal. Per-lane g_P@12M: s57 -0.0037, s58 **+0.0124**,
  s59 -0.0118, s60 -0.0166, s61 -0.0226. **The largest POSITIVE value is +0.0124, inside
  the 0.02 CONFIRMED band; the only lane exceeding 0.02 in magnitude (s61, -0.0226) does
  so in the NEGATIVE direction, which is not leakage at all** — it is a head fitted to
  permutation noise scoring worse than the marginal out-of-sample, and the header's
  negative branch (derangement) triggers only at <= -0.10, four times further out. So
  max-governs would have reported "RESIDUAL — possible retained information" on the
  strength of a number pointing the wrong way for that conclusion. **LETTER: SHUFFLE
  CONFIRMED**, with s61's -0.0226 disclosed in the same line. The band structure is
  two-sided by design (the script applies |g_P|), and that stays right for VOID
  screening; it is only the RESIDUAL cell whose interpretation is sign-dependent, which
  is a wrinkle the pre-registration does not name and which is now on the record.
  Nothing else moves: the branch was B1 under either reading.
- 2026-08-16 (evening, **THE HANDOFF WAS VOID — D19 WAS ALREADY DEAD, AND ITS LAST OPEN
  CHANNEL IS NOW MEASURED SHUT**). Session opened on `HANDOFF.md`'s instruction to write
  D19's pre-registration ("§12 is RATIFIED so D19 is binding, just unread"; "the right
  lever"; a 5-lane arm priced at 2.17 against a 17.91/20 ledger). **That premise is
  false. D19 ran a full 2-designer cycle on 2026-08-13, its information premise failed at
  ZERO LANES, and the maintainer re-targeted it into what became D25** — the rung that
  then credited at 0.6185 (`SESSION_LOGS.md:3067` and `:3106`; the ratified D25 header
  says it outright at `configs/showdown_sp_actpred12m.yaml:130`, "**The D19 KILL
  STANDS**"). No lanes were spent and no pre-registration was written.
  **ROOT CAUSE, and it is a documentation defect worth more than the incident.**
  `DESIGN.md` — which CLAUDE.md designates "the roadmap… read it for any substantive
  'what next' question" — was last committed **2026-08-13 07:29**, hours BEFORE that
  afternoon's kill, and had never recorded the kill, the D25 re-target, D25's credit, or
  D25-P. Its D19 entry still read "still queued, UNREAD… D19's question stands as
  written." It also **never mentioned D24 or D25 at all** (grep count: 0), i.e. the
  roadmap carried no record of the chapter's only credited lever. A session that follows
  the documented reading protocol therefore lands on a dead rung. Fixed: DESIGN §12's
  queue state now runs through D25-P, D19 carries a KILLED/RE-TARGETED status block in
  its heading and body, and CLAUDE.md records that **DESIGN's status lines are not
  self-updating and must be checked against the newest SESSION_LOGS entry.**
  **THE NEW MEASUREMENT (`results/d19_closeout/`, zero lanes, ~2 min).** The 2026-08-13
  cycle killed D19 on the GENERATOR channel (what revealed mons imply about the rest).
  Neither designer measured the BEHAVIOURAL channel — whether the opponent's PLAY leaks
  its hidden team. That is the channel a "belief state" claim would actually rest on and
  the only honest route back, so it was measured. Eight pre-D25 tapes pooled
  (s26/27/28/50/51 + the three frozen references), **52,514 rows / 2,400 battles**;
  target = the multiset of UNREVEALED opponent species; everything masked to not-yet-
  revealed species so **exclusion is free to every model and never scores as belief**;
  deliberately generous to D19 (probe reads the full 828-d observation, which upper-
  bounds any ctx head since ctx is a function of obs; lambda tuned on held-out).
  **A1 = 4.8726 nats. Generator channel beyond exclusion +0.0062; BEHAVIOURAL channel
  +0.0061; TOTAL +0.0123 sd 0.0011 — 0.25% of the target.** By reveal state the best
  phase is one revealed mon at +0.024, and that is exactly where D25's premise was
  LARGEST (0.63-0.65) — **~26x apart at D19's own best point.**
  **CONTROLS, because a null is worthless without them, and this project has been bitten
  by precisely this** (`:3131`: D19's original mechanism read "was a null BY CONSTRUCTION
  — it would have read 'the trunk does not carry the belief' when it only showed the
  estimator was the wrong shape"). Negative: our own team is contained in the label field
  0/1658 times, so the field really is the opponent's. Positive: the same probe extracts
  **+2.55 nats** with the answer planted in the input and **+3.73 nats** with the true
  team leaked as a feature (4.961 -> 1.232, near the log-k floor). It finds 3.7 nats when
  the information is there and 0.012 when it is not. lambda 0.1 stays an INTERIOR optimum
  on a grid extended to 10, so the gain is not an under-regularisation artefact.
  **HONEST LIMIT, self-corrected mid-session:** the generator number here is sample-
  limited at 2,400 battles, while a 12M-step run sees ~340k and could plausibly reach the
  record's 400,000-team figure of 0.347 nats. That does NOT rescue the rung — that channel
  is exclusion and cap saturation, "a mask effect, not a belief about which mon"
  (`configs/showdown_sp_actpred12m.yaml:131`), and 0.347 is still ~7% of a 4.95-nat
  target. The belief-bearing channel is the behavioural one and it is ~0.006. Also a
  linear probe at tape scale; a nonlinear head over 340k battles might find more, though
  PC1/PC2 show this probe class extracts 2.5-3.7 nats when the signal exists.
  **WHY IT MATTERS BEYOND D19:** ~99.75% of D19's aux CE would have been a constant fit,
  and D25-P has since measured what a shape-, count-, marginal-, coefficient- and
  cadence-matched aux gradient carrying ~zero information does to win rate — **nothing**
  (0.5415 vs 0.54452). Dose caveat attached (placebo ran at 3-31% of the treatment band,
  so it is not a matched-dose control). D19 would have bought a ~2.17-lane-day null.
  **FIVE MORE DOC DEFECTS FOUND AND FIXED OR FLAGGED** (adversarial review pass, 2 Opus
  agents, maintainer-authorised): (a) `CLAUDE.md`'s locked eval protocol said **1000
  battles/seed** against DESIGN §8's 3000 — flagged for fixing 2026-08-13 and still
  there; fixed, with 5x3000 named as the disclosed deviation it is. (b) **There is no
  DESIGN §11** — r7 retired §10-11, headers run §9 -> §12 -> §13, and DESIGN §8 itself
  calls D8/D9 (search) "UNRATIFIED and now moot" — yet `STATUS.md:40` and CLAUDE.md both
  cited "§11 (search)" as the live next lever; recorded as dangling. (c) `STATUS.md:39`
  claimed "nothing pushed" while `main == origin/main == 034ad81`, 0 ahead / 0 behind.
  (d) `README.md:126` still says D19 "is next in its queue, pending the maintainer's call
  on a 50M regen-L2 carry" — both clauses dead. (e) **A live contradiction between two
  ratified documents, left for the maintainer:** DESIGN §8's D7(a) defers ladder
  execution "until M2/M3, at which point it becomes the natural confirmation of the
  chase" — **M2/M3 are now claimed, so that trigger is satisfied** — while CLAUDE.md's
  landmine says flatly not to propose a real-ladder eval. One of them has to move.
  **NO LANES SPENT; ledger unchanged at 17.91/20. Suite 370 green, tree clean.** The
  handoff stub is restored and its durable content folded: the five D25/D25-P
  pre-registration lessons are now CLAUDE.md conventions.
- 2026-08-16 (evening, **ADVERSARIAL REVIEW LANDED: KILL NOT REFUTED, BUT MY OWN WRITE-UP
  HAD RESTORED A RETRACTED PREMISE — CORRECTED**). Reviewer 1 (Opus, tasked to refute the
  D19 kill on five axes) returned **NOT REFUTED**, and confirmed the chronology to the
  minute: DESIGN.md's "still queued, UNREAD" line was added by `ba4356d` at **07:29:23**
  and the kill landed in `6711205` at **11:41:23** — 4h12m later, after which DESIGN.md
  was untouched until today. It also closed the axis I expected to be the real risk:
  **both killed D19 designs were ALREADY set-valued and Designer A's head was ALREADY
  pointer/scorer-shaped** (`results/d24_design/d19_design_A.md:107-110`, `:130-137`), and
  the `Linear(ctx->K)` ill-posedness finding hit D19's mechanism PROBE, not its head or
  its premise — the premise was measured entirely outside the network, on generator and
  tape teams. So there is no re-shaped D19 that clears a gate the killed one failed.
  Ratification of §12 is an authorization to spend, not an obligation: the same maintainer
  who authorized D19 redirected it two days later (`:3098-3110`).
  **THREE CORRECTIONS TO MY OWN ENTRY ABOVE, ALL FOLDED IN.** (1) **I restored a sentence
  this repo formally retracted.** I wrote "teams are near-independent near-uniform draws"
  into DESIGN.md, STATUS.md and README.md; `SESSION_LOGS.md:3238` (CORRECTION 5, "D19's
  stated premise is false in three ways, though the KILL STANDS") says outright that gen-1
  randbats is NOT independent near-uniform draws — the generator is rejection sampling
  with a species clause, a type cap of 2 and a weakness cap of 2. Reviewer 1 generated
  **600,000 teams** (fixing a `battleHasDitto` provenance bug in Designer B's original
  4,000-team sample that suppressed Ditto after its first occurrence) and found **0 of
  600,000 violate either cap** — the caps bind hard, and the structure is real. **The
  correct sentence: 88-90% of D19's structure is a deterministic cap MASK, a closed-form
  function of the revealed set, leaving a genuine belief residual of 0.024-0.034 nats of
  4.955.** Model-free confirmation at one revealed mon (full 146x146 conditional, 300k
  fitting teams, held-out on 300k): **0.0341 nats, 0.69% of the loss** — reproducing the
  red team's 0.035 by an independent method and showing it is a CEILING, not a floor.
  This was the wrong reason for a right conclusion, i.e. the exact failure mode `:3252`
  diagnoses. Fixed in all three files, which now quote the retraction rather than repeat
  the error. (2) **My "+0.0123 nats / ~99.75% constant fit" was a probe-capacity result
  sold as a property of the world.** The team is constant within a battle, so the
  effective sample is **2,400 teams, not 52,514 rows** — Designer A hit the same wall at
  1,800 teams. At 300k fitting teams the generator channel is 0.20-0.33 nats. The kill
  does NOT rest on my measurement; it rests on the 0.024-0.034 residual, measured at
  generator scale. What the probe adds is that nothing in the game state rescued the
  channel at tape scale and that the estimator could find 3.7 nats when there was
  something to find. Honest constant-fit fraction ~93-95%, and the sharper number is the
  88-90% mask share. (3) **My D25-P inference was over-read** — "close to a direct
  empirical measurement of what D19 would have bought" is deleted. D25-P's placebo carried
  literally zero information; a D19 head would carry 0.20-0.33 nats of real signal. It is
  suggestive, not a measurement, and the 3-31% dose caveat sits on top.
  **NEW, AND IT CORRECTS A RATIFIED HEADER: the "~1.6x tape-averaged" multiplier at
  `:3250` and `configs/showdown_sp_actpred12m.yaml:126-129` is apples-to-oranges IN D19's
  FAVOUR.** D25's realised 0.544 is measured beyond its MASK-renormalised marginal
  (`actpred12m.yaml:855`); D19's 0.347 is gross and INCLUDES its cap mask. Matched on both
  sides it is **0.544 vs 0.024-0.034 = ~16-23x.** The red team corrected r1's inflated
  "15x" and overshot the other way. Recorded, not silently patched — D25's numbers and
  verdict are untouched and its premise never rested on the ratio.
  **RESIDUAL LEVER, AND IT IS NOT A TRAINING RUNG.** The one channel that survives is the
  cap mask, and it is genuinely not free to the trunk: per-mon type one-hots are in the
  observation but the opponent team is MAX-POOLED (`rl/networks/entity_deepsets.py:355`),
  and max-of-one-hots cannot recover type COUNTS. The fix is a summed type/weakness-count
  feature over the revealed opponent set — **which is already D20's named "summed scalars
  … matters more under DeepSets max-pool, which cannot reconstruct sums" item, at ZERO
  lanes instead of 2.17.** It is a mask, so it can never earn the belief-state claim.
  **STALE POINTERS SWEPT** (reviewer 1's exhaustive list, all fixed): two EXECUTABLE
  graders that print dead routing on re-run (`scripts/d23_grade.py:161,172-173`,
  `scripts/d18_grade.py:80-81`); `prior_work/README.md:207-209`, the sentence most likely
  to re-motivate a revival ("belief-state reconstruction is better posed here"), which
  also pointed at a `DESIGN.md` §10 that no longer exists; `RESEARCH_BRIEF.md:59-66`
  (external-facing, listed D19 AND the privileged critic as queued-next, and PFSP whose
  own D22 trigger never fired); the D23 and D18 config headers, which got ROUTING-ONLY
  addenda leaving every number and verdict untouched; DESIGN's D21 entry, which gated a
  live rung on two dead ones; and the two D19 draft pre-registrations in
  `results/d24_design/`, now stamped SUPERSEDED (they still claim seeds 52-56, spent on
  D25). Suite 370 green; ledger unchanged at 17.91/20; no lanes spent.
- 2026-08-16 (night, **D27 MATCHED-DOSE CONTROL KILLED AT ZERO LANES — AND THE REASON IS A
  BETTER RESULT THAN THE ARM WOULD HAVE BEEN**). The maintainer picked the matched-dose
  auxiliary control over D26 and asked for it launch-ready. **It cannot be built.** Two
  Opus designers, working independently from different evidence, reached the same kill by
  different routes, and both said so unprompted.
  **THE FINDING: A SHUFFLED-LABEL AUXILIARY HEAD CANNOT BE DOSED, BECAUSE IT STOPS USING
  THE TRUNK.** `OppActionHead` carries a `slot_bias` term whose documented purpose is to
  "absorb the class marginal at the optimum … the design against C3(a) (a head that fits
  P(class) and calls it a belief)" (`rl/networks/opp_action.py:126-128`). For a
  shuffled-label head **P(class) IS the entire task**, so the head routes everything into
  that bias and disconnects its input path. Measured at the weights (designer A, from the
  banked checkpoints): placebo `|slot_bias|` 0.56 -> 1.98 with final scorer weight FLAT at
  0.32 -> 0.34; treatment the exact reverse, `|W_last|` 0.48 -> 1.25 with slot_bias
  0.09-0.29. Measured at the gradients (designer B, from history.csv): the fraction of the
  aux gradient reaching the trunk collapses 0.44-0.54 (bin 0) -> **0.05-0.09 (bin 11)**
  against the treatment's 0.51-0.62. **The anti-confound device that made D25's claim
  credible is the same device that makes its placebo undosable.**
  **WHY NO COEFFICIENT FIXES IT — THREE INDEPENDENT WALLS.** (1) **It is an identity, not
  a shortfall.** Matching the trunk component needs ~58x the coefficient, which puts the
  TOTAL aux gradient at ~8.3x the treatment's; the gap is exactly the ratio of the two
  trunk fractions. **No scalar changes a fraction — including a per-update servo**, which
  kills the dose-controller option I had offered as a way out; it only picks which
  mismatch to accept. (2) **The clip is applied AFTER the coefficient**
  (`rl/agents/ppo.py:796`: `scale = min(1, aux_max_grad_norm / total)` where `total` is
  already post-coefficient), so delivered dose is capped at `clip x trunk_fraction` and
  **bins 6-11 are unreachable at ANY coefficient** under the shipped 0.5. Escaping needs
  the clip at >= 1.37-2.0 — a second lever off both D25 and D25-P. (3) **Adam is
  scale-invariant on the aux group**: `aux_params` is its own optimizer group fed only by
  the aux loss (`ppo.py:552`), so the coefficient cannot change what the head LEARNS, only
  how hard an input-ignoring head pushes.
  **A LIVE METRIC TRAP, CAUGHT BEFORE IT BIT: `aux/trunk_norm` is logged PRE-CLIP** (the
  code says so at `ppo.py:790-794`). At a raised coefficient the dose gate would have read
  in-band while a third of that was actually delivered — **D25-P's P3 dose gate, applied
  unchanged, would have certified a dose that never landed.** Harmless at coef 0.1
  (clip_frac <= 0.0018), decisive at 5.0.
  **AND THE BOUND WOULD NOT HAVE BEEN WORTH IT.** phi = the fraction of D25's +0.0739 a
  generic gradient reproduces. D27's BEST case (placebo dead flat, n_P=4, s_P=0.0308)
  bounds phi <= 41.7% under the house convention, 59.9-70.5% once T's and C's own
  seed-clustered uncertainty is propagated. **D25-P already banks phi <= 33.2% from finals
  on disk — a TIGHTER bound.** D27's best case is numerically weaker with wider scope. In
  the middle (placebo 0.575-0.581) the interval contains 100% and bounds nothing.
  **A BUDGET FACT I HAD MISSED, and it reframes the whole choice:** STATUS allocates seeds
  62-65 and ~1.74 lane-days to D26. D27 wanted the same four seeds and ~1.88.
  **17.91 + 1.74 + 1.88 = 21.53 > 20 — it was always a SUBSTITUTION, never an addition**,
  so the question was never "is D27 worth 1.88" but "is D27 worth more than D26".
  **CORRECTIONS TO THE RECORD, both found independently by both designers:** STATUS's
  "placebo ran at 3-31% of the frozen band" is wrong — that is 3-31% of the **0.7x
  THRESHOLD**; against the band itself it is **~1.2-21.9%**. And my own brief was wrong on
  calibration: 100k smokes cannot calibrate this arm, because the placebo's trunk
  disconnect only develops after ~700k (trunk fraction 0.505 at 100k vs 0.067 at bin 11),
  so a 100k smoke would have calibrated the coefficient 3.3x low.
  **WHAT THE CAVEAT NOW NEEDS, named and NOT run:** an auxiliary task with permanent
  structure and zero opponent information — predicting the agent's OWN action (labels
  already sit in the buffer as `flat_actions`, `ppo.py:862`) or regressing a fixed random
  projection of the row's own observation. Such a head never exhausts its task, never
  disconnects, and holds its dose flat at a constant coefficient, so this obstruction does
  not arise. It is a different control, needs its own pre-registration and its own ~1.75
  lane-days, and the chapter does not have them alongside D26.
  **NO LANES SPENT. Ledger unchanged at 17.91/20.** RESULTS.md §5's dose disclosure is
  rewritten from "untested, not eliminated" to "untested, AND this control cannot test it,
  and here is the measured reason". Suite 370 green. Minor build note recorded, not fixed:
  `ppo.py:762` annotates `tuple[float, float]` but `:804` returns three values.
- 2026-08-16 (night, **C4 TRANSFER PROBE — LETTER FIRED AT THE MINIMUM ATTAINABLE p, AND
  THE CONFOUND IT EXPOSED WAS FOUND AND CLEARED**). Maintainer chose "A then B": the free
  transfer diagnostic first, then the annealing arm. This is A. Zero training lanes.
  **PRE-REGISTERED FIRST, AND COMMITTED BEFORE THE TAPE EXISTED** (`4db2532`, the C4
  TRANSFER PROBE block appended to `configs/showdown_sp_actpred12m.yaml`) — letters,
  levels, both failure readings and an explicit power warning, all written before any
  number was computed.
  **THE QUESTION** is D25's own disclosed C4 (`actpred12m.yaml:1489`, "the evaluated
  opponent (SH) is not the modelled one. Transfer is untested"). D25 trains in MIRROR
  self-play, so the "opponent" its aux head predicts is a snapshot of the agent itself.
  Did the trunk learn to model AN opponent, or only ITSELF?
  **THE DESIGN: §5's machinery with exactly one change — the reference tape's opponent.**
  Same frozen s36@12M checkpoint (in neither arm), 300 battles, but playing
  `SimpleHeuristicsPlayer` instead of itself; 7,059 paired rows, 5,871 after the aliasing
  filter, sha 88e6d42f...d7e35. Same eight battle-level splits, same frozen lambda 0.01,
  same ten lanes, same exact permutation at 12/252. Collector and probe in
  `results/c4_transfer/`; the probe imports `d25_atoms`'s own fit path so this and the
  banked letter go through byte-identical fits. `d25_atoms.py` itself was NOT edited — it
  pins the frozen mirror tape by sha and asserts it, correctly, because it computes a
  banked letter.
  **RESULT: FIRED, p = 1/252 = 0.003968, THE MINIMUM ATTAINABLE, IN BOTH LABEL SPACES.**
  L6 primary: treatment s52-56 +0.0647/+0.0623/+0.0792/+0.0678/+0.0585 -> mean **+0.0665**
  against control s26/27/28/50/51 +0.0458/+0.0339/+0.0295/+0.0318/+0.0420 -> **+0.0366**.
  **Complete separation — every treatment lane above every control lane.** 12-class
  secondary agrees: +0.0700 vs +0.0386, same p. Lower-side test p = 252/252, does not
  fire. Worst ||g|| over all 176 fits 2.53e-04, inside the letter's 1e-3.
  **THE CONFOUND, FOUND BY ASKING THE OBVIOUS QUESTION AND NOT PRE-REGISTERED — MY GAP.**
  Treatment lanes carry ~1.7x more live ctx units (221-293 vs 131-169) and across the ten
  lanes **r(live units, Delta^SH) = +0.939** (Spearman +0.891), with **ZERO OVERLAP**
  between arms — so "treatment" and "more live units" are perfectly confounded in the
  pre-registered design and the permutation test cannot separate them. **§5's specificity
  argument does NOT transfer**: on the mirror tape that same correlation is -0.453, the
  WRONG sign to manufacture a positive, which is exactly what cleared de-dormancy there.
  On the SH tape the sign flips.
  **THE POST-HOC CONTROL, LABELLED AS POST-HOC, AND IT CLEARS IT.** Cut every lane to
  exactly K=131 randomly chosen live units (the minimum across lanes), zero the rest,
  refit. Three independent draws: diff **+0.0329 / +0.0296 / +0.0329, mean +0.0318, exact
  p = 1/252 on every draw** — against the unmatched +0.0299. **Capacity is not doing the
  work; if anything the matched gap is larger.**
  **LICENSED, per the pre-registration verbatim: the representation TRANSFERS to an
  opponent outside the training distribution, and the "it only models itself" reading is
  refuted. C4 IS DISCHARGED.** What it does NOT do, also per the pre-reg: it does not
  discharge C3(b) (training is still mirror self-play), does not license "belief state"
  (§5's claim bound is unchanged), does not make the head shipped (train-time only), and
  cannot touch D25's win rate, which has its own letter and its own placebo.
  **A PRE-REGISTERED PREDICTION OF MINE THAT WAS WRONG, AND INSTRUCTIVELY SO.** C4-POWER
  warned that this probe would be WEAKER than §5's because SH is scripted and
  near-deterministic, so "there is simply less for any probe to find", and that a null was
  the modal outcome. **The opposite happened: the control atoms here (+0.0366) are ~2.4x
  §5's mirror-tape control atoms (+0.0150).** I conflated LOW MARGINAL ENTROPY with LOW
  DECODABLE GAIN. A deterministic opponent has less entropy but is MORE decodable from
  state, and Delta measures the decodable part. The warning was honest and it was wrong;
  recorded so the reasoning error is not repeated.
  **Also measured, recorded not graded:** SH switches on **1.02%** of turns against a
  self-play opponent's 6.8-9.7% — a 7-9x difference that compresses the L6 label space and
  is worth knowing before any future SH-tape probe. Aliased-row fraction 16.8% vs the
  mirror tapes' 4.0-10.3%.
  Artifacts backed up alongside `results/d25/`. Suite 370 green; ledger unchanged at
  17.91/20. **NEXT: B — D26's blocking gates.**
- 2026-08-16 (night, **D26 RATIFIED BY DELEGATION; ALL PRE-LAUNCH GATES PASS; ARM READY**).
  Maintainer: "ratify whatever you think is best." **The four Q13 calls were therefore
  taken by me, not by the maintainer, and the header's status line says so explicitly so
  the record never implies otherwise.**
  **(1) RUN IT.** Not because the odds are good — P(CREDIT) is 0.23-0.39 at typical seed
  spread and the modal outcome is FLAT — but because **these lane-days have no alternative
  use**: D27 was killed at zero lanes, the chapter's account is banked in RESULTS.md, so a
  FLAT costs wall-clock and nothing else. Review 1's correction materially improved the
  picture: below the s_T ~ 0.0134 crossover the +0.025 FLOOR governs at a bar of 0.6435 —
  BELOW the anneal's own +0.0277 — where P(CREDIT) is 0.60-0.75, and six 12M arms have
  landed below that crossover. **(2) ANNEAL-ONLY; the bundle is DECLINED** — it buys +0.024
  P(CREDIT) under an honest lambda prior, nearly doubles P(NEGATIVE), needs an override of
  ratified DESIGN.md:785-787, and rests on an UNVERIFIED citation. `gae_lambda` stays 0.95.
  **(3) `lr_anneal_steps: 12000000`** — the schedule that earned both in-repo credits
  verbatim; the 15000000 floor declined ON PROCESS (a free number with no budget to
  calibrate it). **(4) "4 and no more"** — n=6 moves the resolvable delta only
  ~0.032 -> ~0.030 and the +0.025 floor is the asymptote.
  **LEFT OPEN AND EXPLICITLY NOT MINE TO TAKE:** DESIGN §8's D7(a) defers the ladder eval
  "until M2/M3" — now satisfied — while CLAUDE.md's landmine forbids it. Two ratified
  documents contradict; one must move, and that is a maintainer call.
  **GATES: ALL PASS** (`scripts/d26_gates.py` for R0-A/C/E/F/H/J, plus
  `tests/test_anneal_aux_group.py` for R0-B). The decisive one is **R0-C**: read off the
  100k smoke checkpoint's optimizer state rather than the config — **97 updates, THREE
  param groups, all at 2.4795200000e-04** against an expected 2.4795200000e-04, i.e. the
  aux group annealed with the rest and **the code path that had never executed in any run
  or test is now proven correct on a real run, at the corrected value.** R0-E: illegal and
  collision fracs 0.0, `aux/labelled_frac` 0.8686 inside the smoke-era band, all losses
  finite. R0-F reads the WRITTEN config, not the file: anneal and aux stamped, privileged
  absent, purity seam `opponent: self`, encoder v2/ids/828. R0-H re-read all five D25
  finals from disk — pooled 0.6184667, sd 0.0235815 exact, `wins_from_returns` ==
  `eval/win_rate` on every one. R0-A: exactly {seed, run_name, lr_anneal_steps} differ.
  **R0-B ALSO CAUGHT A LIVE TRAP** that would have rejected a correct anneal: R0-B's `u` is
  the PRE-increment counter while R0-C and Q3's table use the POST-increment checkpoint
  counter, so Q3's "200,000 / u=195 / 2.4586e-04" read as pre-increment is 2.45840e-04.
  Both conventions are now pinned by assertion in both directions. Two of my own drafts of
  that test failed against a CORRECT anneal because I hand-typed trailing digits the header
  never claimed; it now asserts at the 5 s.f. Q3 actually prints.
  Adds `configs/showdown_sp_recipe12m_smoke.yaml` (R0-E needs it — `rl/train.py` exposes no
  `total_steps` override) and `scripts/d26_gates.py`. Suite 371 passed, 9 skipped. Ledger
  **17.91/20 unchanged** — the smoke is 100k. **NOTHING LAUNCHED; nothing pushed.**
- 2026-08-16 (night, **D18 POST-HOC IMPLEMENTATION AUDIT: CLEAN — THE NULL STANDS ON A
  CORRECT IMPLEMENTATION, AND ITS EV SECONDARY QUANTIFIES WHY**). The maintainer asked
  whether D18's null could be an implementation artifact ("perhaps it wasn't done right?").
  First post-hoc adversarial audit of the D18 code (the 2026-08-11 3-Opus review was
  pre-launch); independent of it, every path re-read from source. **ZERO DEFECTS FOUND.**
  Verified: slice arithmetic vs the OBS layout incl. the id-tail sub-slices
  (`rl/envs/showdown.py:440-448` — `o:o+6` own species, `o+12:o+16` own moves, against
  `ID_DIM`'s "6 own + 6 opp | 4 own + 4 opp" layout at `:151`); emission after the wait
  pump at exactly the mask-emitting decision points (`:1046-1053`); collection alignment
  privs↔obs / next_privs↔next_obs with the done-row reset merge ordered AFTER the carry
  (`rl/train.py:595-628`); per-row `privs`/`next_privs` so a truncated row bootstraps the
  true final state's privileged view (`rl/buffers/rollout.py:64-75`); critic input =
  obs ‖ priv at values, next_values, AND the value loss (`rl/agents/ppo.py:896-919,1026`);
  the loud both-way env/agent mismatch seam (`:821-827`, tested both directions); actor
  never widens and `act()` calls only `self.actor` (`:691-714`); priv tokens through the
  same subnets with extras gated by the is-active bit at mon offset 2 and ids recovered
  ×256 = write-side `ID_SCALE` (`rl/networks/entity_deepsets.py:259-288`).
  **READOUT PREMISES RE-DERIVED FROM THE TAPES** (history.csv, not the log): EV last-1M
  D18 0.5972/0.6150/0.6206/0.5972/0.6040 (s39-43) vs control 0.5751/0.5572/0.5657
  (s26-28); every D18 lane above every control lane in every window tried (5-12M, 10-12M,
  11-12M) — the falsifier's premise is robust to windowing. (The recorded control band
  "0.549-0.561" reads slightly low vs my windows' 0.556-0.575; direction unchanged.)
  `loss/adv_std` last-1M: D18 0.4730-0.4788 vs control 0.4830-0.4919 — the named
  "advantage scale shift" mechanism moved the scale only −2-3%, and advantages are
  z-scored per minibatch anyway (`ppo.py:1014`), so scale per se cannot carry the effect.
  `loss/value` lower in D18 (0.213-0.229 vs 0.224-0.234); KL/clip_frac comparable.
  **THE SUBSTANTIVE FINDING — the hypothesis's magnitude was wrong, not the plumbing:**
  handed the ENTIRE hidden team, the critic gained only ~+0.045 EV against the pre-reg's
  hoped-for ~0.40 ("the ~40% unexplained terminal-return variance this lever attacks").
  Confound 1 (the priv path made the critic's move subnet live for the first time) can
  only INFLATE that, so true hidden-team content is ≤ ~0.045 of return variance — the
  rest of the unexplained variance is aleatoric (crits, rolls, 1/256 miss, full para,
  sampled opponent actions), which no privileged state can explain. Independently
  corroborated by the later D19 closeout: 88-90% of the hidden team is a deterministic
  cap mask, belief residual 0.024-0.034 nats of 4.955. Two measurements, two methods,
  same answer.
  **DESIGN-LEVEL RESIDUALS, RECORDED NOT DEFECTS:** (1) actor and critic are fully
  separate nets (`ppo.py:418-419`), so the lever's only channel is advantage quality —
  at γ=1, λ=0.95 over ~35-turn episodes the advantage is MC-heavy in the tail, and at
  λ<1 the V(h,s) bootstrap injects state-innovation noise the actor cannot condition on
  (the centralized-critic variance critique, Lyu et al.) — consistent with the small
  negative delta; a λ=1 pure-baseline variant was never run and, given ≤0.045 EV of
  content, is not worth a lane. (2) The value stack in BOTH arms never consumes our own
  active's move tokens (`entity_deepsets.py:345-359` computes `own_moves`, ctx never
  includes it) — shared across arms so it cannot explain the delta, but it is the first
  thing to fix if critic-side work is ever revisited. (3) s41 (grad-blowup lane, 0.4740)
  drags pooled; without it pooled ≈ 0.552 — still NULL, nothing changes.
  **VERDICT: the D18 null is real and informative, not an artifact. Do not re-run a
  "corrected" D18 — there is no correction to make.** The chapter's arc is coherent:
  opponent-STATE to a separate critic (D18) → nothing; opponent-ACTION into the actor's
  trunk (D25) → +0.074 credited. The injection point, not the information family, was
  the lever. Docs-only session; STATUS.md amended in this commit. Nothing launched.
- 2026-08-16 (night, **CHAPTER-2 PROPOSAL DRAFTED AND REVIEWED: `DESIGN2.md` r1, PROPOSED —
  NOT RATIFIED. D26 LAUNCHED BY THE MAINTAINER AND HEALTHY.**). D26 went up at 21:05 (4
  lanes, s62-65, ~312 steps/s median indicative, ~08:00 finish); this session ran the
  maintainer-mandated design process for the next chapter alongside it, all zero-lane.
  **PROCESS (standing, 2026-08-12): 2 independent Opus design agents** (`results/
  design_ch2/ch2_design_A.md` = information/verdict; `ch2_design_B.md` = build/cost),
  **synthesis (`DESIGN2.md` r0), then 2 independent Opus reviews** (`ch2_review_1.md` =
  evidential validity; `ch2_review_2.md` = buildability), **then r1 folding in all 26
  MUST-FIXes.** `results/` is gitignored — the four process docs are the ONLY copies and
  are not yet in the backup. Three arms, staged ask (full tranche ≈9.0 ld → ledger ≈28.6
  vs the standing 20 cap, so the ask IS a new tranche): **D28** zero-info aux control
  (the D25 dose-caveat closure; task corrected in review to a shared-readout synthetic
  pointer — the head's shared scorer makes independent per-slot readouts ~75%
  unrepresentable), **D29** D25@50M (re-opens the CLOSED 50M line; the un-creditable-bar
  finding was already banked 2026-08-13 at SESSION_LOGS:2916-2940 and Designer A
  re-derived it independently; descriptive 3v3-permutation primary; anneal-off on every
  D26 branch, pre-stated), **D30** soft-label aux (premise measured THIN at zero lanes:
  opponent L6 distribution 0.87-0.90 max-class, H(p) 0.25-0.32 nats; a 0.19-0.20
  nats/row legality leak makes the naive arm two levers; blocking offline test Z3-3 can
  kill it free). **Review catches worth their cost:** the r0 anneal-guard form would
  have rejected D26's own ratified smoke config; the r0 D29 cadence fallback was
  cadence-dirty against its own comparator in exactly the branch where it mattered; the
  r0 dose gates merged two incompatible band systems and would have failed D25 itself
  read per-bin; `d25_grade.py` at 3v3 silently prints NOT GRADED rather than crashing;
  the trunk-fraction "discrepancy" (0.51-0.62 vs 0.619-0.676) is a bin-11-vs-run-mean
  window difference, not a contradiction. **All bar arithmetic verified to <0.001 by
  review** (D29 floor 0.66754; D30 floor 0.64347; D28 boundaries reproduce the ratified
  placebo header's). Maintainer decision points are DESIGN2 §7; Stage-0 zero-lane work
  is free and listed in §6; the two small code patches (delivered-dose logging; the
  train.py interval-form anneal guard) are HELD until the D26 fleet finishes. Earlier
  same session: the D18 post-hoc audit (separate entry above) — clean, null upheld.
  STATUS.md rewritten in place (D26 running; DESIGN2 pointer). Nothing launched by the
  assistant; server untouched; **D26's D-D throughput clause may fire at the compliant
  1M warm read — thresholds remain 275/230 until then.**
- 2026-08-17 (early AM, **STAGE-0 EXECUTED AT ZERO LANES: D30 KILLED; Z1-1 VOID AS A
  SCREEN; D28's ABORT THRESHOLD CALIBRATED. DESIGN2.md -> r2.** D26 still running,
  untouched). Maintainer said "run 1 yourself" — the free offline checks. All CPU-only,
  nice'd, server untouched; scripts + JSON in `results/design_ch2/` (only copies).
  **(1) Z3-3 KILLS D30.** 13 tapes, 8 battle-level splits each, production canonicalise
  pipeline, all Z3-2 oracle-identity sanity gates PASS (reproduces ch2_design_B §1.5 to
  4 decimals). Soft-label training beats hard on held-out hard-label CE — real sign
  (12/13 tapes, 39/40 D25-lane splits, robust to 3 early-stop rules) — but only
  **-0.0078 nats pooled / -0.0155 on aux-trained tapes = 0.2-1.8% of the head's own
  learned signal** (0.73-0.86 nats), which in total bought +0.074 win rate. 1-2% more
  mechanism cannot clear a +0.025-0.049 bar. Still bundles the 0.19-0.20-nat legality
  channel; generator-dependent. `results/design_ch2/z3_3_results.json`.
  **(2) Z1-1 IS VOID AS A CALIBRATED SCREEN** — the pre-allowed honest negative. A/B
  anchor gaps offline +0.046/+0.221/+0.092/-0.204 (median +0.069 vs live ~+0.47), one
  INVERSION; offline shuffled anchor sits above the live treatment band on 3/4 tapes;
  head-scale confound persists at convergence (`ppo.py:554-561` vindicated; last-layer
  norm 5.6x spread, r=+0.53 with f). No proxy->live mapping exists; **D28's dose is
  certified IN-RUN ONLY** (200k read + 6M abort). Secondary positives: amended
  synthetic task learnable (held-out acc 0.75, CE 0.77 at tau* vs live 0.81); **tau*
  median 8.8** hits the 0.250-nat target; r0 per-slot construction collapses exactly as
  review-2 MF-1 predicted; own-action task independently corroborated dead (can't beat
  its own marginal floor on any tape). New free number: per-class OFFSETS needed to
  match D25's label marginal (unit-variance alone is near-flat). `z1_1_results.json`.
  **(3) CALIBRATIONS BANKED** (`trunk_fraction_bins.json`): trunk-fraction
  "discrepancy" RECONCILED — bin-11 0.50-0.62 (=RESULTS §5) vs run-mean 0.62-0.68
  (=ch2_design_B); same data, two windows. D25-P per-bin collapse trajectory: 0.45-0.52
  (bin 0) -> 0.07-0.14 (bins 5-6) -> 0.05-0.09 (bin 11); treatment holds 0.60-0.69 at
  6M -> **D28's 6M abort threshold = 0.35, measured not guessed**.
  **Chapter shape after Stage 0: D28 IS the chapter (2.16 ld); D29 held pending the
  maintainer's 50M/§13 ruling; D30 dead.** DESIGN2.md r2 records all of it (§0b).
  Tree committed; nothing launched; D26 lanes verified progressing throughout.
- 2026-08-17 (morning, **D26 READOUT: B1 CREDIT — POOLED 0.71825, DELTA +0.0998, THE
  HEADLINE MOVES TO D26. All gates pass.**). Fleet finished ~08:30 (4 lanes, 12M each,
  clean exits). Finals run under the locked protocol (final ckpt, 3000/seed,
  deterministic, ties as non-wins, both env vars): **s62 0.7297 / s63 0.7187 / s64
  0.7217 / s65 0.7030 -> pooled 0.71825** vs the frozen D25 comparator 0.61847 ->
  **delta +0.0998**, governing se = seed-clustered 0.0119 (s_T 0.0112 — the low-spread
  branch Q6 said would govern), operative bar = the +0.025 floor, **B1 CREDIT**; exact
  4v5 permutation 1/126 (minimum attainable; every treatment lane beats every
  comparator lane). **Gates: D-A LR trace PASS 12/12 checkpoints** (three groups, Q3
  pre-increment convention, lr ends 3.7e-08 — the anneal genuinely ran); R0-4
  exact-agree x4; K6 clean (min pre-6M entropy 0.228-0.276); R1 anchor 0.969-0.975 at
  4M all lanes. Final-1M entropy 0.286-0.318 — the anneal did NOT collapse exploration.
  **HANDOFF PREMISE FAILURE, caught by the landmine rule:** the "committed grader per
  Q6" (R0-I) did NOT exist on disk; written at readout BEFORE any final was read
  (`scripts/d26_grade.py`, reusing `d25_grade.py::se_terms/::exact_perm_p` unchanged
  per R0-I's own text; branch cuts printed in win-rate units). Finals + stdout in
  `results/d26/` (gitignored, ONLY copy; backed up to the d25 backup dir this session).
  **Honest surprise, recorded not narrated:** the measured +0.0998 is 3.6x the lever's
  own horizon-matched estimate (+0.0277) and exceeds every cell of Q6's power table.
  WHY is open — candidates (6M->12M transfer underestimate; anneal x aux interaction,
  C6's untested fifth transfer) recorded in RESULTS.md §9, not adjudicated. Docs:
  README table + se note updated; RESULTS.md §9 addendum; STATUS rewritten; DESIGN2
  r2 header noted (its 0.6185-era narrative bars are stale; D28's frozen-comparator
  caveat logic unaffected; chapter-2 decisions should be revisited against 0.7183 —
  e.g. any future 50M carry is now a question about the FULL credited stack).
  Ledger: +4 finals ~0.02 ld; D26 lanes ~1.78 ld -> **~19.7/20. The chapter budget is
  spent; chapter 2 is a new-tranche decision (DESIGN2 §7).** Suite not re-run (no
  production code changed except the new grader script). Not pushed.
- 2026-08-17 (mid-morning, **D29r PREPPED: THE CREDITED STACK AT 50M — pre-reg drafted,
  2-Opus reviewed, ALL must-fixes folded, grader committed BEFORE launch. PENDING
  ratification + tranche. Nothing launched.**). Maintainer said "prep it" after the D26
  credit flipped the 50M arithmetic (a stack that HOLDS 0.718 clears the 0.6675 floor
  the 08-13 carry cycle proved unreachable at 0.6185). Landed first, suite 372 green:
  **(1) the anneal-trap guard** — rl/train.py raises iff 0 < lr_anneal_steps <
  total_steps (interval form: permits the recipe smoke's 12M-over-100k and every lra
  config; rejects the 12M-under-50M paste that silently trains 38M steps at lr 0) +
  test; **(2) delivered-dose logging** — _aux_gradient returns (loss, total, trunk,
  delivered, scale), new keys aux/trunk_norm_delivered + aux/clip_scale, test arity
  fixed. Then `configs/showdown_sp_stack50m.yaml` (D25 recipe + lr_anneal_steps
  50000000, cadence 250k/100/500k, seeds 90-92, ~4.5 ld, ~37 h 3-wide alone) and
  `scripts/d29_grade.py` (R-A vs struct50m 0.580222/sd 0.0756/n3; R-B vs D26
  0.718250/sd 0.011177/n4 EXACT disk values, attested at every run; 3v3 + 3v4 exact
  perms with ties=non-separation; lane-failure rule implemented; five branch cells hit
  in the selftest). **Review round (2 Opus, results/design_ch2/d29_review_{1,2}.md):
  R1 verified every bar to <5e-6 and found 7 must-fixes** (worst: C-1's lr-integral
  understated 2x — 4.17x not 2.08x; the R-A table omitted the 50M regime's own spread
  row — bar 0.70370 at s_T 0.0756, kill-point 0.092, "P(credit) HIGH" re-priced at
  both regimes; the falsifier threshold was vacuous where stated and the B2-and-
  falsifier cell unnamed; the DESIGN2 §2 anneal-off override and primary/perm swap
  were unnamed — now explicit ratification-time decisions); **R2 (READY WITH FIXES)
  found R0-g protected the WRONG artifacts** — struct50m_finals (the PRIMARY
  comparator) was unlisted AND missing from the backup, as was d25/ — **backup
  repaired** (struct50m_finals, d25, d19_closeout, c4_transfer copied in); R0-c must
  carry the encoder env vars (9 silent skips without); disk is ~6.5 GB with wandb not
  4.2. All folded same morning; one-diff verified in THREE directions (6/9/6 keys,
  byte-exact); selftest + attestation + lane-failure paths all exercised green.
  **The three ratification-time calls, maintainer's:** (1) the ~4.5 ld tranche; (2)
  accept the two §2 overrides; (3) at readout only — whether a credited STACK
  satisfies §13(1)'s "credited lever" wording. Ledger unchanged (~19.7/20 spent;
  D29r is new-tranche). Launch commands in the header's OPS block, 3 lanes staggered.
- 2026-08-18 (afternoon, **D29r LANE s90 DIED AT 35.0M — MASK/ORDER RACE IN A TURN-1000
  AUTO-TIE BATTLE; 2 SURVIVORS → R-A PRIMARY HEADED FOR VOID PER THE LANE-FAILURE
  RULE**): s90 (pid gone ~13:45 Tue) crashed unhandled at step ~35,139,488; last rung
  `ckpt_035000000.pt` 13:38; wandb stream closed cleanly 13:45:03. Maintainer's
  terminal traceback (pasted into session): 13:43:25 `bigerror` "You will auto-tie if
  the battle doesn't end in 0 turns (on turn 1000)" in
  battle-gen1randombattle-33084355, then `ValueError: Invalid action 1 ... /choose
  switch Muk not in valid orders ['switch Dugtrio','switch Marowak', 4 moves]` raised
  by poke-env `singles_env.action_to_order` (strict), up through
  `SyncVectorEnv.step` → train loop dead. MECHANISM: `showdown.py:881` emits
  `info["action_mask"]` from poke-env's `get_action_mask(battle)` at obs time; strict
  order validation re-reads battle state at step time; the turn-1000 auto-tie path
  churned available_switches in between (Muk legal at mask time, gone at order time).
  The strict-raise choice is documented at `showdown.py:883` — this is the first
  observed desync in ~400M+ cumulative training steps (struct50m 3x50M + D25/D26 +
  35M here), i.e. rare race, but exposure scales with any 250M line. Lane was HEALTHY
  to the last row (no NaN/inf in final 200 rows, normal losses/returns). NOT
  restarted: the pre-reg lane-failure rule (D25's, verbatim in the header) says dies
  → reported as-is, NEVER replaced; <3 survivors VOIDS the primary (surviving finals
  individual, never pooled); the seeds-93/94 provision was pre-D-D (4M) only.
  s91/s92 unaffected, running ~397-407 steps/s on the freed cores (expectation band
  was 3-wide; 2-wide runs faster), ETA ~midnight → Wed readout stands, graded by
  `scripts/d29_grade.py` which implements the 2-survivor arithmetic. Watch re-armed
  2-hourly (survivor-aware, VOID-aware endgame); the stale 3-lane 5-hourly cron
  found still registered and deleted. OPEN (maintainer, no action taken): whether to
  harden the seam before D28/any 250M line — e.g. catch the strict ValueError at the
  `showdown.py` step boundary, log the desync, and issue a legal default order
  (truncation semantics) instead of dying at 70% of a 4.5 ld run. A fix is NOT a
  D29r matter (its arm is closed to code changes mid-run).
- 2026-08-18 (evening, **MASK-DESYNC HARDENING LANDED: the s90 crash class can no longer
  kill a run — conversion-site interception, 2-Opus reviewed, r1 retry design KILLED by
  both reviewers**): maintainer directive after s90 ("never let a single error take
  down a 50M run"). r1 (strict-flip + retry at the step boundary) was proven UNSOUND
  independently by both reviewers: PokeEnv.step flips agent*_to_move BEFORE the raising
  conversion, so a retry deadlocks silently in the timeout-less race_get — worse than
  the crash. Landed design (memo r2 + both reviews in results/design_ch2/maskfix_*):
  `ShowdownSingles.action_to_order/order_to_action` overrides + wrapped PoolPlayer
  static call route ValueError through one module-level `_recover_mask_desync` —
  WARNING + count + poke-env's own random-legal fallback; `MaskDesyncCapExceeded` on a
  2nd desync in the same battle or >3 in a rolling 100K-step window (benign race
  2.5e-9/step vs >=1e-3 systemic: six orders of margin; per-PROCESS module state so
  num_envs can't multiply the budget). Seat-2 recovery DROPS the D25 label
  (_OPP_CHOICE_NONE) — a fallback label vs the stale frame could flip the
  aux/illegal_label_frac==0 hard gates. Eval recovers on the same path;
  `mask_desyncs` now in eval_checkpoint JSON + score_ladder rows (nonzero on a locked
  number = disclosure item); no new W&B metric (locked names — maintainer call if
  wanted). REVIEW-2 CORRECTED THE MECHANISM: tied() touches no availability; the churn
  is parse_request on the LISTENER thread racing a held decision
  ([Unavailable choice]/[Invalid choice], gen-1 stall wars) — so the rate SCALES with
  long battles; that is why the cap is a rolling window, not lifetime. RESIDUALS on
  record in the memo: the finished-battle assert window (stale order_queue await makes
  naive synthesis corrupting — needs its own design round), hangs (race_get has no
  timeout — watch-loop progress checks remain the only defense), and resume (the thing
  that would have saved s90's 35M) stays OPEN. Forfeit/truncation alternatives rejected
  for cause: a forfeit scores as a LOSS (-1 into the credit-line quantity). Tests:
  tests/test_mask_desync.py (8, offline); suite 380 passed 9 skipped; env-var mode
  failures identical to HEAD via stash (8 pre-existing), zero regressions. Protects
  FUTURE launches (D28+) only — s91/s92 run pre-fix code.
- 2026-08-19 (overnight, **D29r READOUT: PRIMARY VOID BY LANE LOSS — R-A AND R-B UNREAD;
  s91 0.73267 / s92 0.75133 RECORDED INDIVIDUALLY, NEVER POOLED; HEADLINE STAYS D26
  0.71825**): s91/s92 completed 50M cleanly (exited 23:56/23:35 Tue; ~37.2 h wall,
  ~4.2 ld realised incl. s90's 1.13 to its death at 35M). Finals, locked protocol
  (final ckpt, 3000/seed, deterministic, ties non-wins, vs SH), run sequentially at
  readout: **s91 0.7326667** (2198/3000, ties 0.0080, return_mean +0.47333), **s92
  0.7513333** (2254/3000, ties 0.0097, return_mean +0.51233); R0-4 exact-agree both;
  `mask_desyncs` 0 both (first readout with the disclosure field). Grader
  (`scripts/d29_grade.py`): attest PASS on both frozen comparators, then the
  pre-registered lane-failure rule fired — 2 survivors < 3 → **PRIMARY VOID, exits
  before grading either cell**. Both individual finals exceed 0.71825 — recorded as
  OBSERVATIONS, explicitly not credits; nothing here satisfies any bar. Recorded-only
  diagnostics: D-A trace PASS 16/16 surviving rungs (2M/10M/26M/50M x s91/s92, 3 param
  groups, final lr 5.76e-9; run standalone, labeled recorded-only — the grader's own
  short-circuit is the pre-registered behavior); D-C PASS both (illegal/frame exactly
  0 everywhere, labelled 5M-bin means 0.7945-0.8133, losses finite); D-D PASS both
  (anchor 0.976 by 4M); K6 UNREADABLE as pre-registered (3-lane median, s90 dead) —
  per-lane: s91 six consecutive <0.15 entropy readings pre-25M (min 0.1251; a
  per-lane variant would have stopped it), s92 zero (min 0.1574); named, not
  adjudicated. **aux/loss prediction MISSED in the informative direction**: predicted
  plateau >0.81; measured 0.7265/0.7438 @12M FALLING to 0.6451/0.5742 final-1M —
  the offline KL proxy overstated pool hardening; ceiling 1.40 never approached.
  Delivered dose (new cols, first run): trunk_norm_delivered 0.1093/0.0982 mean,
  clip_scale 1.0000/0.9999 (clip never engaged). Recorded everywhere in this commit:
  STATUS rewrite, README row, RESULTS.md §10; results/d29/ backed up to
  ../pokemon-showdown-rl-d25-backup-20260815/; HANDOFF folded and restored to stub.
  **Maintainer decisions open:** (1) whether to re-run the 50M stack as a fresh
  pre-registered 3-lane arm (new tranche; seeds per DESIGN2 §5 — never on seat 90) or
  proceed straight to D28 (~2.2 ld, queued); (2) push timing (several commits local).
