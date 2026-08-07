# Handoff — written 2026-08-07, end of the pivot day

**⚠ Run the next session on FABLE 5 at HIGH effort** (`/model`, `/effort`). xhigh is not
needed — the thinking is pre-done and committed; what remains is ratification + careful
implementation. If the session is not on that setting, say so before doing anything else.

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

## State: green, committed, PUSHED, nothing running

Suite **243 passed**. Tree clean. `origin/main == main == 88bd76e` — the whole backlog is
pushed (maintainer authorized 2026-08-07; pushing remains ask-first). No training or eval
processes alive. Showdown server **UP on :8000** (`simulator: 4`) — reuse it.

Two long days produced ~15 SESSION_LOGS.md entries dated 2026-08-06/07 — **do not restate
them**. STATUS.md is current. DESIGN.md is **r7, PROPOSED, unratified**.

## The one thing that matters

**The maintainer pivoted 2026-08-07: pure from-scratch self-play in gen1randombattle is the
main chase** (novelty over strength; revocable; does not need to beat Foul Play). Everything
needed to execute is committed:

- `DESIGN.md` r7 — milestone ladder (M1 0.4400 go/no-go → M3 0.510 success claim), purity
  definition, 4 rungs, abandon criterion. **D10–D17 need maintainer ratification FIRST.**
- `prior_work/THROUGHPUT_SPEC.md` — Rung 0. Headline: SyncVectorEnv SERIALIZES all sub-envs
  (num_envs is a dead lever, <1%); ~80% of the loop is idle websocket wait; async
  Player-path collector projects 540 → ~1,400 steps/s/lane. E1–E4 (≤10 min each) first.
- `configs/showdown_sp_signal12m.yaml` — Rung 1 DRAFT (γ 0.95 + H&L 5-term zero-sum shaping;
  constants from metagrok's CODE, not the paper). Needs: `hl_shaping` env kwarg, `--no-shaping`
  on eval_checkpoint, the R0-2 antisymmetry test — then one overnight (3×12M, seeds 23/24/25).
- `configs/showdown_sp_struct12m.yaml` — Rung 2 DRAFT (entity DeepSets + per-action scorer;
  runs only after Rung 1 reads out).
- Baseline for both rungs: **0.3890 ± 0.0089** (sp12m_v2 finals, seeds 10/11/12, on disk).

## Next session, in order

1. Maintainer ratifies D10–D17 (recommendations inline in DESIGN r7).
2. If D13(a): land the MUST_RECHARGE Stage-0 fix + re-run the 12M control overnight (one
   night); else freeze v2/807 and go.
3. Implement Rung 1's three code items (spec'd to the line in its config header), run R0-2
   offline+live gates, launch 3×12M overnight. Rung 0's E1–E4 fit in the gaps.

## Do NOT rediscover these (session-hot; the rest is in the logs)

- **Something outside the session killed my background-task-launched training lanes once**
  (23:37, all three at once, silent, box stayed up; cause never identified). Long runs
  launched by Claude now use `nohup ... & disown` — the sp12m_v2 relaunch pattern. Runs in
  the maintainer's terminal are unaffected.
- Seeds claimed: 0–13 spent, **14–22 RESERVED (warmrl draft, on ice)**, 23/24/25 Rung 1,
  26/27/28 Rung 2, 29/30 smokes. Distinct across lanes AND arms.
- `runs/showdown_sp12m_v2_s1{0,1,2}_aborted1M/` are 30-min partials from the killed first
  launch — safe to delete, kept only as evidence.
- Encoder is **v2/807 via `POKEMON_RL_ENCODER_V2=1`** — process-level and forgettable; every
  run's meta.yaml stamps the fingerprint; CHECK IT per lane (R0-1 in every draft).
- Banked, on ice, zero rework to resume: FP teacher 0.8307 (n=7,200), 180k-row tapes (v1+v2
  shards `data/fp_all*`), v2 clone 0.558/0.569*, warmrl draft, P4-scale GO. These are now
  EVAL ANCHORS for the chase, not the main line.
- STATUS.md hard cap 60 lines — it drifted over twice today; count before committing.
- prior_work gained four tracked analyses (DISTILLATION_OBJECTIVES, ARCH_SCREEN_SPEC,
  HISTORY_FEATURES_DESIGN, THROUGHPUT_SPEC) + the verified H&L entry; `metagrok` is a new
  sibling clone. Read before re-deriving anything about objectives, trunks, history features,
  or the loop.

## Open, deliberately

1. D10–D17 ratification (the session's first conversation).
2. H&L scale accounting (both seats or one?) — settle from metagrok before Rung 3's budget.
3. The FP-clone protocol-grading + head-to-heads (owed if M-milestone guards ever fire, or
   if the chase is revoked and the warmrl line resumes).
