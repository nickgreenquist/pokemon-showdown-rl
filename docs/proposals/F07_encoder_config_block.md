# F-07 proposal — an `encoder:` config block

**DRAFT, UNRULED.** Written 2026-09-02 on `audit/DOCS` @ 5d3c6b7 (main @
60c1225). Nothing in this file exists in the tree; nothing here touches the
running 100M fleet. Sources: `docs/AUDIT_ACTION_PLAN.md` §3 F-07 and F-08,
§5 item 5; `CLEANUP.md` "2026-09-01 read-only audit" (item A2).

Tags: **RULED** = a maintainer ruling; **MEASURED** = read from the tree with
its source; **PROPOSED** = this draft's suggestion, which needs a ruling.

## 1. Risk statement (F-07, restated with locations)

1. Three process env vars decide the observation layout at IMPORT time:
   `POKEMON_RL_ENCODER_V2` (`rl/envs/showdown.py:139`),
   `POKEMON_RL_ENCODER_IDS` (`:152`), `POKEMON_RL_NO_SET_PRIOR` (`:554`).
   `OBS_DIM` (`:168`) is 612 / 808 / 828 accordingly; `ENCODER_FINGERPRINT`
   (`:173-181`) records {obs_dim, encoder v1/v2, set_prior, recharge_fix,
   ids}.
2. No config that trains or evaluates a checkpoint carries these. The 100M
   wave exports them (`scripts/ch5_100m_wave.sh:29-30`); the frozen eval
   schedule tells the operator to export them (HANDOFF §2 item 1); tests
   set them per subprocess (`tests/test_encoder_v2.py:66,76`,
   `tests/test_entity_deepsets.py:247`, `tests/test_encoder_ids_tapes.py:167`,
   `tests/test_anneal_aux_group.py:36-38,56,83-94`); R0-c is "the only
   env-var'd gate" and 8 encoder-default tests fail BY DESIGN under forced
   flags (`configs/showdown_sp_100m.yaml:341-343, 368-371`).
3. Failure modes, by trunk (MEASURED in the code):
   - entity trunk: loud. `rl/networks/entity_deepsets.py:79-88` refuses
     `ID_DIM == 0` and `in_dim != OBS_DIM`; layout assert at `:105`.
   - MLP trunk, different width: loud, on the shape mismatch at
     `load_state_dict` (`rl/train.py:97-104` in `_frozen_checkpoint_pool`;
     `scripts/eval_checkpoint.py:74-80`).
   - ANY trunk, `NO_SET_PRIOR` toggled: SILENT. `OBS_DIM` is constant, the
     semantics of the opponent's move slots change (`showdown.py:550-570`),
     nothing refuses, and the eval prints a plausible wrong number. Only
     `meta.yaml`'s `encoder:` stamp (`rl/train.py:142-149`) records which
     semantics a run trained under, and NO loader reads it. This is the
     finding.
   - Resume: `rl/train.py:380-383` asserts `ckpt["config"] == asdict(cfg)`,
     which cannot see env vars — a resume under different exports continues
     the run on a different obs at constant width.
4. RULED (CLEANUP.md A2, 2026-09-01; SHELVED until the 100M readout is
   recorded): "encoder env-var default flip → assert `OBS_DIM==828`/
   fingerprint instead; pure default flip only". A2 makes v2+ids the
   default and asserts it. It does NOT make the layout a config property
   and does NOT cover `set_prior`.

## 2. Why the block EXCEEDS the ruled A2

1. A2 changes the DEFAULT of three env-var reads and adds an assert. Every
   config and checkpoint keeps loading; no schema change; no new key
   stamped; the resume drift assert is untouched. It removes the
   forgotten-export failure for v2/ids on the DEFAULT path, nothing else.
2. The block (a) adds a `Config` field (`rl/common/config.py:14-80`) —
   `asdict(cfg)` changes, so `config.yaml`, every checkpoint's
   `payload["config"]` (`rl/common/checkpoint.py:31`) and the resume drift
   assert (`rl/train.py:380`) all see a new key; (b) stamps a fingerprint
   into the checkpoint payload; (c) adds refusal logic at four loader
   sites; (d) demotes the env vars to a deprecated override. None of
   (a)-(d) is behaviour A2 ruled on. The plan's re-verified note says the
   same: "carry it as a separate proposal that needs its own maintainer
   ruling; do not fold it into A2" (plan §3 F-07).
3. Ordering is itself a ruling: A2-first means the block's "unspecified"
   default inherits the flipped env default; block-first means A2
   collapses to a one-line schema-default change.

## 3. Proposed design (PROPOSED; none of it exists)

### 3.1 Schema

```yaml
encoder:            # ABSENT = today's behaviour (env vars decide; deprecated path)
  v2: true          # POKEMON_RL_ENCODER_V2
  ids: true         # POKEMON_RL_ENCODER_IDS
  set_prior: true   # NOT POKEMON_RL_NO_SET_PRIOR
  spec: gen1        # F-08 seam (§5); gen1 is the only legal value until the gen-4 chapter opens
```

- `Config.encoder: dict = field(default_factory=dict)` — the `selfplay` /
  `collector` idiom; strict keys (`rl/envs/make.py:91-110` selfplay
  precedent, `rl/train.py:450-452` collector precedent); bool values
  checked at load.
- ABSENT block = BIT-IDENTICAL to today: env vars read at import as now,
  `asdict(cfg)["encoder"] == {}`. Every existing YAML — including the
  frozen `showdown_sp_100m.yaml`, which cannot be edited — loads and
  behaves unchanged. The one-diff tests compare the raw YAML dicts
  (`yaml.safe_load` + `_flat`, `tests/test_100m_prereg.py:16-19, 24-43`;
  they never construct `Config`), so an absent block is absent on both
  sides and the key sets stay equal; `asdict(cfg)["encoder"] == {}` is
  what the Config-level round-trip (`config.yaml`, `payload["config"]`,
  the resume drift assert) sees.
- PRESENT block = the config is the source of truth.

### 3.2 Binding the block to the process (the hard part)

The layout constants (`OBS_DIM`, `MON_DIM`, `MOVE_DIM`, `ID_DIM`) are module
globals computed at import (`showdown.py:153-168`). Two ways for a config to
own them:

- **Option 1 — config-sets-flags (minimal).** `train.main()` loads the
  config BEFORE any `rl.envs.showdown` import (true today: `rl/train.py`
  imports it only deferred, `:87, :147, :323`; `rl.envs.make` registers the
  env lazily, `rl/envs/make.py:149-153`). A new `apply_encoder_block(cfg)`
  runs right after `load_config` (`rl/train.py:967, 971`): if
  `rl.envs.showdown` is already in `sys.modules`, REFUSE (an import-order
  fault, never a silent mismatch); else set `os.environ` from the block;
  if an env var is already set and DISAGREES with the block, REFUSE ("the
  deprecated override must equal the config"). Every later import sees the
  config's flags. One top-level import on the eval path must move:
  `scripts/eval_checkpoint.py:46` (`mask_desync_total`) binds the flags
  before `ckpt["config"]` is readable — deferring it makes the loader
  config-first too. `rl/envs/showdown_async.py:61` also imports at top but is
  itself imported after the config on the training path (`rl/train.py:514`,
  inside `_async_loop`). `rl/collect.py:34` and `rl/search/matrix.py:49`
  likewise import at top, but they are NOT on the training path at all:
  nothing under `rl/` imports `rl.collect` (only
  `scripts/make_bc_dataset.py:40`, `scripts/obs_fidelity_check.py:49`,
  `scripts/showdown_throughput.py:83`, `tests/test_collect.py:19`), and
  `rl.search.matrix` is reached only from `rl/search/agent.py:37` and from
  scripts (`scripts/ladder.py:388`,
  `scripts/play_vs_agent.py:89`, the `ch3_*` family, `tests/test_ch3_*`) —
  so `rl/train.py:514` does not cover them, and each of THOSE entry points
  needs its own config-first handling (the `eval_checkpoint.py` treatment) if
  it is ever to be driven by the block. Until then they would keep the env-var
  exports as their only source, which §3.5's deprecated-override rule permits.
- **Option 2 — object, with F-08.** The flags become fields of an
  `EncoderSpec` instance selected by the block; env, tokenizer and
  fingerprint take the spec; the module globals remain as the gen-1 default
  spec's attributes for backward compatibility. Larger; it is what F-08
  needs anyway (§5).
- PROPOSED: Option 1 now — it makes the SCHEMA and the REFUSAL contract real
  with a small diff; Option 2 arrives with F-08 and keeps the schema. Under
  Option 1 the env var stays the process-level truth, so the tests'
  subprocess pattern stays valid.

### 3.3 Stamp

- `save_checkpoint` (`rl/common/checkpoint.py:15-40`) gains
  `payload["encoder"] = dict(ENCODER_FINGERPRINT) | {"spec": ...}` for
  Showdown configs (`cfg.env_id.startswith("Showdown")`, the
  `_write_run_metadata` idiom at `rl/train.py:142`). Spine checkpoints
  unchanged. Readers `.get()` it (the `extras` precedent,
  `checkpoint.py:25-28`).
- `meta.yaml` keeps its stamp (`rl/train.py:147-149`) as the per-RUN
  record; the payload stamp is the per-FILE record (a checkpoint copied
  out of its run dir keeps its fingerprint).

### 3.4 Refusal sites (checkpoint fingerprint vs process fingerprint; refuse on any differing key)

`make_agent` (`rl/train.py:45`) builds against the process `OBS_DIM` and
loads nothing; the comparison belongs to every site that then calls
`load_state_dict` on a checkpoint:

1. `scripts/eval_checkpoint.py` — the standard path (`:174-175`,
   `make_agent` + `load_state_dict`, where `NO_SET_PRIOR` is silent today)
   and the cross-play path (`_load_showdown_agent`, `:51-92`). The 808→828
   `PrefixSliceActor` shim stays legal: `ids` is the ONE key allowed to
   differ, in the one direction the shim already permits (`:74`), so
   `tests/test_eval_shim.py` keeps passing.
2. `rl/train.py:_frozen_checkpoint_pool` (`:68-106`) — the training-side
   frozen opponent; refuses only on shape today.
3. `rl/train.py` warm start `init_from` (`:359`) — loads weights with no
   encoder check at all today.
4. `rl/train.py` resume (`:379-383`) — add the fingerprint to the drift
   assert; `SnapshotPool.load_state_dict` (`rl/selfplay/pool.py:221-238`)
   rebuilds members through `make_agent` at the process `OBS_DIM` and would
   otherwise fail on shape only.
5. Message shape: print both fingerprints and the config/export lines that
   reconcile them (the `eval_checkpoint.py:75-80` wording).

### 3.5 Deprecation of the env vars

Kept as an override that MUST equal the block when both are present (refuse
otherwise); the truth when the block is absent (today); one deprecation line
per process when they are the only source. Removal is a later, separate
ruling — after A2, and after the wave/eval scripts and the tests have moved
to the block.

## 4. Migration for existing checkpoints and run dirs

1. Payload without `encoder` (every checkpoint on disk today): fall back to
   the sibling `meta.yaml`'s `encoder:` — present on every Showdown run dir
   since f1cb74b, 2026-08-06 (`SESSION_LOGS.md:1673-1675`), `ids` since
   Rung 2 (`configs/showdown_sp_struct12m.yaml:152`). `meta.yaml` is read
   from the checkpoint's parent dir, which the ~200 rungs x 3 lanes of the
   100M fleet satisfy in place.
2. Neither payload nor `meta.yaml` (pre-2026-08-06 checkpoints; a checkpoint
   copied out of its dir): fall back to today's width inference
   (`eval_checkpoint.py:69-80`) and WARN that `set_prior` is unverifiable.
   Never refuse what loads today — that would strand the archive.
3. `meta.yaml` is the LAUNCH stamp: a run resumed under different exports
   would carry a stale fingerprint. Under §3.4 item 4 that can no longer
   happen; for the archive it is disclosed, not fixable (no fleet has been
   resumed under changed exports; the R2 resumes ran the same wave-script
   exports).
4. **The resume drift assert with a new `Config` field — the bit-identity
   hazard of the whole proposal.** `load_config(run/config.yaml)` on an OLD
   run dir yields `encoder == {}` and `asdict(cfg)` carries the key;
   `ckpt["config"]` written by old code lacks it. The assert
   (`rl/train.py:380`) MUST compare with the key defaulted
   (`ckpt["config"].get("encoder", {})`), or every existing run dir —
   including the 100M lanes — becomes un-resumable on the new code. First
   regression test to write; `tests/test_resume.py:164-171` is the drift
   test to extend.
5. Wave/eval scripts: the `ch5_100m_wave.sh:29-30` exports stay valid under
   the deprecated-override rule (they equal the block); new pre-regs carry
   the block and drop the exports.

## 5. Interaction with F-08's `EncoderSpec` (PLANNED, NOT landed)

1. F-08 (plan §3 F-08, §5 item 5): the gen-1 tables — 15 types,
   type-determined physical/special, no items/abilities/weather, gen-1
   volatiles (`showdown.py:81-168`, per the plan) — go behind an
   `EncoderSpec` chosen by format; the 828-dim gen-1 encoding stays
   bit-identical under regression tapes; the action space stays 10 through
   gen 5 (poke-env `get_action_space_size`), so the spec is the gen-4
   blocker and the action-space derivation a gen-9 need.
2. STATUS at this draft: the `EncoderSpec` seam is being built in a sibling
   worktree on the `audit-fixes` branch family. At this draft's base (all
   audit branches at 5d3c6b7) no `EncoderSpec` exists in the tree
   (`grep -rln EncoderSpec` hits only `docs/AUDIT_ACTION_PLAN.md` and this
   file — no code). Nothing here describes landed code.
3. Fit: the block's `spec` key SELECTS the spec; `v2`, `ids`, `set_prior`
   are gen-1 spec parameters. Under Option 2 the fingerprint becomes
   `spec.fingerprint()`, `OBS_DIM` becomes `spec.obs_dim`, and the refusal
   sites compare spec fingerprints. The block should land with `spec: gen1`
   as its ONLY legal value, so F-08 adds VALUES, never fields.
4. Sequencing (PROPOSED): F-07 block (Option 1) → F-08 spec (Option 2,
   same schema) → A2 becomes "the gen1 spec's default flags are v2+ids" —
   or A2 first, if the maintainer prefers the ruled item to land as ruled.
   JOURNEY step 3 ("gen4 encoder + model", `JOURNEY.md:37-40`) is where the
   spec is needed; the block is needed the first time a checkpoint is
   evaluated on a box whose exports were forgotten, which is any day.

## 6. Bit-identity and test contract (what an implementation must prove)

1. Absent block → `OBS_DIM`, `ENCODER_FINGERPRINT`, every encoded vector,
   and every `asdict(cfg)` except the new empty key are bit-identical.
   Pins: the R0-3 goldens (`tests/test_entity_deepsets.py:55`), the tape
   gate (`tests/test_encoder_ids_tapes.py:164`, data-gated),
   `tests/test_100m_prereg.py` — all unchanged.
2. Present block equal to the exports → same. Present block unequal to the
   exports → a refusal, not a run.
3. Loader refusals: one test per §3.4 site, each with a fingerprint that
   differs ONLY in `set_prior` (the silent case today).
4. Old-payload resume (§4 item 4): a checkpoint saved without `encoder`
   resumes under the new code.

## 7. What needs a maintainer ruling (explicit list)

1. Whether an `encoder:` block is wanted at all, given A2 is ruled and
   shelved — or whether A2 as ruled suffices for the gen-1 chapter and the
   block waits for the gen-4 chapter with F-08.
2. Ordering: block before A2, A2 before block, or A2 subsumed by the
   block's default.
3. Option 1 (config-sets-flags now) vs Option 2 only (wait for the
   `EncoderSpec` and do it once).
4. Env-var deprecation: keep-as-override-that-must-agree (proposed), or hard
   removal once the block lands (breaks `ch5_100m_wave.sh`, the frozen
   HANDOFF §2 incantation, and the tests' subprocess pattern).
5. Refusal vs warning per loader site — in particular whether `init_from`
   (a warm start, by design a fresh run) refuses or warns, and whether the
   808→828 shim stays the single legal exception.
6. Migration for checkpoints with neither payload nor `meta.yaml`
   fingerprint: warn-and-load (proposed) or refuse.
7. Whether the payload stamp counts as a checkpoint-format change owed a
   disclosure line in the next pre-reg header (it changes no existing
   file's loading; it changes the bytes of every new one).
8. Timing: A2's shelf condition is "until the 100M readout is recorded";
   whether the block inherits it, or may be built (not merged) beforehand.
