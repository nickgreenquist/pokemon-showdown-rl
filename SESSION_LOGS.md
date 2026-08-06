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
