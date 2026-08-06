# Handoff — written 2026-08-06, end of the Arm B evening

**⚠ Maintainer reminder first: run the next session on OPUS at HIGH effort** (`/model`,
`/effort`). If the session is not on that setting, say so before doing anything else.

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty stub.

## State: everything green, everything committed, nothing running, nothing queued

Suite 240 passed. Tree clean. No training processes alive. The Showdown server is still UP
on :8000 — reuse it, do not start a second one. **16 commits are unpushed** (`main` is ahead
of `origin/main`); pushing is the maintainer's call and has not been asked for.

Tonight, in one line each — full detail in the four SESSION_LOGS.md entries dated
2026-08-05/06, which are the record; do not restate them elsewhere:

- **Code evening 1** — mechanism logging (`explained_variance`, `adv_std`, `grad_norm`,
  `grad_clip_frac`), warm start settled as "a fresh run" + staged unfreeze, Arm B built,
  Track 1 measured, Foul Play priced.
- **Arm A smoke** — warm-start machinery green; handoff does not break the cloned policy.
- **D2c control re-eval** — P5b is **0.4308 ± 0.0052** at 3000 battles/seed (was 0.4433 at
  1000). Showdown eval episodes confirmed NOT reproducible; comparisons are unpaired.
- **Arm B** — **SCREENED OUT, Δ −0.0004.** Closed, not re-tuned.

## The next move is a maintainer DECISION, not code. Three are open.

1. **D8 / D9 — DESIGN §11 (search re-entry). PROPOSED, needs ratification.** Recommends a
   cheap poke-engine feasibility note, then expert iteration from Foul Play as a *teacher*
   (~6 h at 8-way for a P4-scale dataset); rejects search-in-the-training-loop on cost.
   The maintainer has said "eventually we will need some type of search," so this is live.
2. **Track 1's corpus call.** The ≥50k recent-era bar FAILS at every cutoff that buys
   today's set distribution (≥2023 = 49,693 at 28% level match; ≥2024-04 = 44,391 at 91%),
   and the corpus sizes at ~3.4× P4, not §10's projected 11–22×. Proceed on the smaller
   subset, yield to expert iteration, or run both? Numbers are in the session log.
3. **Push or not.**

## Do NOT rediscover these

- **Arm B is closed. Do not raise its coefficient** — the coefficient is not why it did
  nothing. Terminal-cancelled shaping is potential-based, so it leaves advantages exactly
  invariant, and its potential was already linear in the observation (Φ = 0.6·(obs[2] −
  obs[1])). **Generalized rule now in STATUS: any future shaping proposal must state its
  potential and show it is not already representable from the obs.**
- **Arm C stays parked permanently** — its unparking condition was "iff Arm B credits".
- **A BC-warm-started run sits at `loss/entropy` 0.063 and does not move**, failing the
  [0.2, 1.0] R0 entropy band from update 1. The band does not transfer to that regime; the
  corpus/expert-iteration chapter must choose its own `entropy_coef` BEFORE its first run,
  not waive the gate after. Critic warmup ~5 updates suffices, not the 10 the smoke used.
- **The corpus parquet is already downloaded** — `data/corpus/`, 190 MB, pinned revision,
  gitignored. Do not re-download. `scripts/corpus_survey.py --sample N` re-runs in ~12 s.
- **Background subagents died repeatedly on TLS/certificate errors** (three of three, at the
  600 s watchdog). `claude doctor` also shows a failed auto-update. Not a repo problem, but
  do not lean on parallel agents in this environment without a fallback — one wrote its
  results to disk before dying, which is the only reason its work survived.

## If the answer to (1) is "go"

The first step is the **poke-engine feasibility note** (§11 option A), which is an afternoon
and gates everything expensive: does poke-engine's gen1 build reproduce *Showdown's* gen1
mechanics closely enough to search in, what is its node throughput, and — the number nobody
in our index has ever had — **what is Foul Play's actual win rate vs SH**? Expert iteration
is capped by that number, so it should be measured before the chapter is committed to.
Note poke-engine compiles per generation (`make poke_engine GEN=gen1`); the stock wheel is
gen9. A clone sits at `$CLAUDE_JOB_DIR/tmp/foulplay` but may be gone — re-clone if so.

Also unbuilt and worth one paragraph in §11 when convenient: a BC-fit-as-architecture-screen
(ps-ppo's own method) would answer the MLP-vs-transformer question on our encoder for free
inside the expert-iteration chapter, with no RL budget.
