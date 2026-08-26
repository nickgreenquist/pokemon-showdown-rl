# prior_work — external sources for the Phase 5 capstone

Local archive of the papers and project write-ups that informed Phase 5 design, collected
during the 2026-08-03 prior-work verification dig (full findings: the "prior-work
verification" entry in `SESSION_LOGS.md`).

**Tracking rule (settled 2026-08-05):** this directory is gitignored by default —
third-party copyright, plus repo size. A file is whitelisted iff its CONTENT is ours: this
index, and the analyses listed directly below. A file we *generated* but whose content is
someone else's stays ignored, which is why `wang_fork_diffs.md` is not tracked (2,362 lines
of another author's source diffs under a thin layer of our commentary) — that closes the
standing "un-gitignore it?" question with a no. Everything ignored lives on disk only, so
re-download from the URLs below if one goes missing.

## Our own analyses — TRACKED, and the only files here guaranteed to exist

- **`PHASE5_PRIOR_WORK_BRIEFING.md`** — the Phase 5 briefing distilled from the sources below.
- **`CROSS_FEATURES_AND_ARCHITECTURE.md`** — implementation spec for the encoder/architecture
  question, and per its own header **the primary path** of the two. A four-rung ladder from
  hand-composed cross features (rung 0) through a pointer/shared-slot scoring head, explicit
  crossing (two-tower dot product / DCN), to entity attention over Pokémon tokens (rung 3),
  with per-move and per-Pokémon feature formulas, an experimental design and a
  pre-registration sketch. **Caveat carried from its own Provenance section: written in a
  session with NO repo access, so every formula must be verified against `baselines.py` and
  the Gen 1 damage formula before implementing — where it contradicts this repo's own audit,
  the audit wins.** Bears directly on DESIGN §7's parked STAB and boosts-one-hot items and on
  DESIGN's (retired) architecture-screen proposal — r7 removed §10-11; see §8.
- **`DISTILLATION_OBJECTIVES.md`** (2026-08-07) — verified survey + in-repo measurements on
  the BC objective for the Foul-Play chapter. Verdict: soft-target CE stays; every
  weighted/filtered/offline-RL variant is measurably inert on our tapes (teacher advantage
  97.1% positive); adopt early stopping + value-coef critic pretraining; DAgger is the one
  gated add-on. Key citation: ExIt's soft-vs-hard = +50 Elo at identical agreement.
- **`ARCH_SCREEN_SPEC.md`** (2026-08-07) — implementable entity-attention-vs-MLP BC screen:
  21-token reshape inside the network (no encoder change), d128/L2 pointer-head trunk sized
  below the MLP's params, measured 34.6× CPU train-step cost, decision rule, and a 23-item
  audit of CROSS_FEATURES_AND_ARCHITECTURE.md (which it supersedes on conflicts).
- **`HISTORY_FEATURES_DESIGN.md`** (2026-08-07) — Stage-1 history block (22 dims) derived
  entirely from poke-env's always-on `_replay_data` event log (provably path-divergence-free);
  plus a live encoder bug: the MUST_RECHARGE volatile flag is structurally always 0 (v1 AND
  v2), and recharge/partial-trap placeholder turns are indistinguishable all-zero move blocks.
- **`THROUGHPUT_SPEC.md`** (2026-08-07) — Rung-0 engineering spec for the collection loop.
  Headline: SyncVectorEnv serializes all sub-env round-trips (num_envs is a dead lever, <1%);
  ~80% of the loop is idle websocket wait; Stage-2 async collector on the Player path projects
  540 → ~1,400 steps/s/lane with gates G1–G9 and decomposition experiments E1–E4 first.
- **`LLM_IN_RL_REPORT.md`** — LLM-in-the-loop *for* RL (not RL for LLMs, and not
  LLM-as-agent). Taxonomy plus graded evidence. Its own revision note **retracts** the first
  draft's headline recommendation: frozen LLM embeddings of species/move text are a constant
  per move, so they cannot encode STAB or type effectiveness — the two properties most likely
  to bind — and the real precedents (EMMA, ATLA) inject embeddings through entity-conditioned
  attention rather than concatenation into a flat MLP. Conclusion: everything in the
  cross-features doc ranks above everything in this one, and Gen 1's ~165 moves with no items
  or abilities shrinks the prize further. Deferred, not scheduled.

## What a vs-SH win rate is worth in ladder terms — TRACKED, derived 2026-08-06

**Read this before proposing a ladder eval, or before treating vs-SH parity as "done."**
Source facts are Metamon's (Table 2 + Figure 17, see its entry below); the conversion is ours.

SH's own measured record against humans, by format — note that the ONE number this index
previously carried (Gen1OU, ~0.21) is SH's *worst* row and comes from an OU tier, not randbats:

| format | SH W–L vs humans | raw WR | GXE (Fig 17 labels) |
|---|---|---|---|
| Gen1**OU** | 16–59 | 21.3% | 21.8% |
| Gen3OU | 16–54 | 22.9% | 26.7% |
| Gen4OU | 21–36 | 36.8% | 31.6% |
| **Gen7RandomBattle** | 24–32 | **42.9%** | **39.7%** |
| **Gen9RandomBattle** | 28–32 | **46.7%** | **41.2%** |

**In random battles — our format family — SH is roughly twice the player it is in OU**
(team-building removed), landing at **~40% GXE, Glicko-1 ≈ 1450–1500**. The GXE figures are
exact bar labels; the Glicko band is read off the figure and should be quoted as approximate.

**The conversion — REWRITTEN 2026-08-25; the old version was three chapters stale and
would have mis-calibrated the ladder run.** Ties are non-wins under the locked protocol, so
SH-mirror parity is **0.489, not 0.500**.

- **SUPERSEDED (kept so the old number is recognisable):** the 12M+LRA era scored **0.4607**
  vs SH ⇒ ≈ −20 Elo ⇒ a projection of ~38–40% GXE. **That agent is long gone.**
- **CURRENT:** the credited headline is **0.71825** vs SH (D26 12M, 4 lanes × 3000), i.e.
  **≈ +163 Elo vs SH**. Add inference-time search and it is 0.79283 (SH-facing caveat).

**Do NOT convert that to a GXE projection, in either direction.** Two opposing biases, both
measured in this project, make the extrapolation untrustworthy:

1. *Upward-bias caution (the repo's own standing rule):* past parity, a vs-SH number
   increasingly measures **SH-exploitation** rather than strength — SH is one fixed scripted
   opponent and every number here comes from it.
2. *Downward-bias caution (new, CH4 R1, 2026-08-25):* off-anchor strength is **not** a
   separate axis. Against Foul Play, our take is exactly what Bradley–Terry predicts from
   vs-SH strength (residual +0.005 ± 0.013), so there is no hidden off-distribution deficit
   that a ladder would suddenly expose either.

**The rule of thumb that replaces the old one:** *a vs-SH number near 0.489 means ~40% GXE;
a vs-SH number far above it means the conversion has run out of road and only a ladder read
settles it.* That is now the single largest unmeasured quantity in the project — and the
argument for running the ladder rather than estimating it.

Where that sits in the published randbats field:

| agent | format | Glicko-1 | GXE |
|---|---|---|---|
| ~~ours (12M+LRA), projected~~ **SUPERSEDED, 0.4607 era** | gen1RB | ~1400–1450 | ~38–40% |
| **ours (D26 12M, 0.71825 vs SH)** | gen1RB | **UNMEASURED** | **UNMEASURED — see the conversion note above; do not project** |
| poke-env SH | Gen7RB / Gen9RB | ~1450–1500 | 39.7% / 41.2% |
| Huang & Lee 2019 — PPO self-play, **no search** (VERIFIED, see entry) | Gen7RB | 1677 (n=300) | 72%* |
| ps-ppo — transformer PPO | Gen9RB | 1725 ± 25 | 76.7% |
| Wang 2024 — PPO + test-time MCTS | Gen4RB | 1756 | 79.5% |
| Metamon SynRL-V2 — offline RL on human data | Gen1OU | 1761 ± 35 | 79.9% |
| best human players | — | — | 74–90% |

**Consequences, and the reason this is filed at the top of the index:**

1. **SH parity is not the finish line — it is ~40% GXE.** The floor of the published
   pure-policy randbats field is 72%. ~~That gap is not a shaping/LR/step-count gap; it is the
   size that BC-init and encoder work move.~~ **CORRECTED 2026-08-25 — that second sentence is
   contradicted by this project's own ledger and was actively misleading.** From 0.4607 the
   agent reached 0.71825 with NO BC-init and NO encoder change: entity structure at *reduced*
   parameter count (+0.1513), an opponent-action auxiliary loss (+0.0739), and **an LR anneal
   (+0.0998) — a schedule change, exactly the class this sentence dismissed.** Whatever remains
   of the gap, "shaping/LR/step-count cannot move it" is false.
2. **A ladder eval was deferred until an agent was clearly past SH. IT NOW IS**
   (0.71825, ≈ +163 Elo vs SH), and the 2026-08-23 ruling deferring execution until the models
   were exhausted against the SH and Foul Play anchors is **satisfied as of CH4 R1
   (2026-08-25)**. ~~It buys confirmation only~~ — **CORRECTED: it is no longer predictable
   from vs-SH** (see the conversion note above; the extrapolation has run out of road in both
   directions). Metamon reports being accused of botting in chat at this rating band.
3. **PS Elo ≠ Glicko-1.** ps-ppo's own screenshot is Elo 2102 / Glicko-1 1725 for one agent,
   and Metamon calls PS Elo "intentionally noisy" and not comparable across game modes. Our
   corpus survey's ratings (median 1203, p90 1415) are PS **Elo** and cannot be read against
   any Glicko row above. Quote GXE when comparing across sources.

**Four caveats, all stated by the source itself:** n is tiny (56 and 60 battles → ±6.5pp);
SH's low rating skews matchmaking toward weak opponents, so **raw W–L is an upper bound**;
Fig 17's Glicko "is possibly an overestimate" (slow convergence far below the mean); and
**nobody has measured gen1randombattle** — every randbats row above is gen4/7/9 and every
gen1 row is OU, so this is a cross-format extrapolation, not a measurement of our board.

### THE BOARD ITSELF — measured 2026-08-25, first time in this project

The fourth caveat above said "nobody has measured gen1randombattle." Half of that is now
fixed: no *agent* has been measured on it, but **the board is public and free to read** —
an unauthenticated GET on `https://pokemonshowdown.com/ladder/gen1randombattle.json`
returns the top-500 list with GXE, Glicko-1 (`r`/`rd`) and Elo per player. Pulled
2026-08-25 (fetch it again before quoting; it moves):

| gen1randombattle **top-500 list** | GXE | Glicko-1 | Elo |
|---|---|---|---|
| best | **93.5** | 2022 | 1667 |
| p90 | 82.3 | 1794 | 1510 |
| median **of the list** | **75.0** | 1712 | 1427 |
| 500th (lowest listed) | 58.8 | 1568 | 1358 |

**Read the row labels literally: this is the top-500 leaderboard, NOT the ladder-wide
distribution** — ladder-wide median GXE is ~50 by construction, so "median 75.0" means
median *among listed players*, and it is not a percentile of the playerbase.

**CORRECTION 2026-08-25 (same day, after the first ladder run):** an earlier version of
this table called the 500th row "the cutoff to be listed at all" for GXE and Glicko. That
is WRONG. **The toplist is ELO-RANKED** — verified against the live board: `elo` is
monotone descending down all 500 rows, `gxe` and `glicko` are not. So admission is an
**Elo threshold (≈1357)**, and the lowest GXE on the list is merely whoever happens to
hold it, not a boundary. The bottom ten listed players span GXE 66–76 while the list
minimum is 58.8. Quote the Elo cutoff; never quote a "GXE cutoff".

Two things it reframes:

1. **The published field is mid-toplist here, not the ceiling.** Huang & Lee's 72% (gen7RB)
   and ps-ppo's 76.7% (gen9RB) straddle this list's median of 75.0. The gen1RB ceiling is
   93.5. Cross-format still, so this is calibration, not a comparison — but the field's
   numbers are not a wall.
2. **The ladder is alive but THIN.** Activity by `last_played`: **93 players in the last
   24 h**, 173 in 7 d, 277 in 30 d; the median listed player has 386 games. Queueing will
   work, but over a few hundred games **repeat opponents are certain**, and a repeat human
   opponent is a kind of adversary no anchor in this project has ever tested — vs-SH is
   3000 iid battles against a script that cannot adapt. Whether a deterministic policy is
   memorisable over repeats is UNMEASURED here.

## Local code checkouts — READ THESE DIRECTLY

Full source for the closest comparable system is on this machine, OUTSIDE the repo tree.
Any agent working on encoder, action-space, reward-shaping, self-play or PPO-hyperparameter
questions should read it rather than reason from the summaries below — the summaries are
lossy by construction and the code has repeatedly contradicted the project's own README.

- **`/Users/nickgreenquist/Documents/Projects/foul-play`** — full clone of
  https://github.com/pmariglia/foul-play at `25c976f` (the same commit the retired DESIGN §10-11 audited; see §8).
  The teacher candidate for the retired §11 option (C). Read `fp/config.py` for the CLI surface
  (`--bot-mode challenge_user`, `--user-to-challenge`, `--run-count`, `--search-time-ms`
  default 100, `--search-parallelism` default 1) and `Makefile` for the engine rebuild.
  **It is pinned to `poke-engine==0.0.48` built `--features poke-engine/terastallization`,
  i.e. GEN 9** — `gen1` is a real feature flag (verified against poke-engine's `Cargo.toml`:
  `gen1`..`gen9`, `default = []`), so gen1 work needs `make poke_engine GEN=gen1`, a Rust
  toolchain, and a from-source compile (verified 2026-08-06: builds clean in ~9 s).
  Gets its own Python env — never the `pokemon-showdown-rl` one.

  **HOW TO PROVE THE ENGINE IS THE GEN1 BUILD (measured 2026-08-06, both directions).** The
  compiled extension's MODULE PATHS are a binary discriminator; move-name tables are NOT (they
  are shared across builds, which is why an earlier `strings`-on-move-names probe was correctly
  retracted as inconclusive). On the .so at
  `<env>/lib/python3.11/site-packages/poke_engine/poke_engine.cpython-311-darwin.so`:

  | build | `src/gen1/` | `src/genx/` | `"used for spc"` |
  |---|---|---|---|
  | `--features poke-engine/gen1` | **7** | 0 | 1 |
  | `--features poke-engine/terastallization` (gen9) | **0** | 20+ | 0 |

  **And the A/B was run.** With the gen9 engine deliberately installed, Foul Play vs SH in
  gen1randombattle went **2-5 over 7 battles and then died** with 6 exceptions, terminating in
  `pyo3_runtime.PanicException` (which cannot even be pickled back across the process pool),
  against **~0.85 for the gen1 build**. So a wrong-generation engine is NOT the silent
  degradation it was assumed to be — it panics loudly, and where it does play it is far
  weaker. Both halves of "a wrong build would bias the teacher DOWN" are now measured rather
  than inferred.

  **CORRECTION, measured 2026-08-06 by RUNNING it — "Foul Play supports gen1randombattle" is
  not true out of the box.** The retired DESIGN §10-11 recorded that support as MEASURED FROM SOURCE (generic
  format parsing, a registered GEN1 mechanics entry, gen1 protocol handling, a live gen1 set
  file). Source-reading was right that nothing *rejects* the format, and wrong that the format
  works: Foul Play crashes out of a gen1 battle within ~12 turns of the first one. Showdown has
  a **gen-1-ONLY** protocol path (`sim/pokemon.ts`: `if (this.battle.gen === 1 && !lockedMove
  && (['frz','slp'].includes(this.status) || partiallytrapped))`) that replaces the entire move
  list with a single `Fight` placeholder when the active pkmn is asleep, frozen or partially
  trapped. Foul Play models it nowhere: `fight` is absent from `moves.json`, so `add_move()`
  silently no-ops and the caller indexes `moves[-1]` on an empty list (`IndexError`); and even
  once the move exists, poke-engine has no representable action for that state, returns the
  choice `none`, and `format_decision` dies on `get_move("none").can_z`. In gen1 randbats this
  fires constantly — Rest, Sleep Powder, Hypnosis, Sing, Lovely Kiss, Blizzard/Ice Beam freeze,
  Wrap/Bind/Fire Spin — not as an edge case. **This is the strongest available evidence that
  nobody has run Foul Play in gen1 randbats seriously**, which is worth weighing against
  Metamon's "strongest open-source engine today" when pricing the retired §11 option (C).

  **Our patches are in `scripts/patches/foulplay_gen1_local.patch`** (7 files, applied to the
  clone; re-apply after any pull): local `--no-security` login; the synthetic `fight` move;
  correct placeholder handling; a persistent process pool; pre-truncation policy capture; a
  switch guard on a latent upstream `KeyError`; the gen1 engine pin; and a tape writer.
  **CORRECTED 2026-08-06:** an earlier version treated the placeholder turn as a forced choice
  with one legal action. It is not — `trapped` is False and every switch remains legal, and
  the search elects to switch on a large share of them. Any number measured here is **"Foul
  Play + our patches"**, and 0.8467 specifically was measured with the EARLIER, handicapped
  version, so it is not a number for stock Foul Play nor for the bot generating our data.
- **`/Users/nickgreenquist/Documents/Projects/ps-ppo`** — full clone of
  https://github.com/Nebraskinator/ps-ppo (49 commits, MIT-licensed as of a later commit).
  ~4.6k lines of Python. Machine-local and never committed here; re-clone from the URL if
  missing. Entry points: `config.py` (every hyperparameter), `obs_moves.py` /
  `obs_pokemon.py` / `obs_global.py` / `obs_transitions.py` (the observation, which is the
  part most worth reading), `ppo_core.py` (model + PPO), `worker.py` (BC data generation,
  poke-env bridge), `learner.py`. Deleted-but-recoverable: `eval.py`,
  `eval_policy_improvement.py` (`git show 7fb522c^:eval.py`).
  **Read the ps-ppo entry under Sources before citing anything from it** — several of its
  public claims do not survive contact with the code.

  **ARCHITECTURE + SIZE, MEASURED FROM SOURCE 2026-08-25** (arithmetic re-derived from the
  layer definitions, not read off a claim): genuine transformer — pre-norm self-attention
  (fused QKV) × `n_layers` plus a cross-attention `FlexReadout`. **Two very different
  configurations exist in the repo and the difference matters, so always name the commit:**
  *HEAD* is `d_model 512 / 3 layers / 8 heads` = **14.49M params (12.9M at inference; the
  JEPA predictor is train-only)**; the *Elo-2102 ladder screenshot* commit `1b13ae0` is
  `d_model 1024 / 2 layers` = **≥37.9M excluding embeddings and subnets**. A third,
  `7fb522c^` (= `9259a1c`), is `model_dim 256 / 4 layers`. **So "the published ps-ppo agent"
  is ~38M+, not 14.5M** — an earlier phrasing in this index that said "d_model 1024, 2
  layers" without a commit was ambiguous across all three. Also note `ff_expansion: 4.0` in
  `config.py` is **DEAD at HEAD** — `FlexEncoderLayer` is constructed without it, so the real
  feed-forward is 2.0 (d_ff 1024).

  **OUR SIZE, for the side-by-side** (measured the same day): actor **626,059**, critic
  494,849, aux head 49,479 = **1,170,387 total; no attention anywhere** (DeepSets max-pool +
  one shared pointer scorer). The correct comparable is NOT ps-ppo/Metamon but **Huang & Lee
  2019 at 1.33M, also attention-free, also pure self-play randbats, no search — which reached
  72% GXE. We are at 88% of its parameter count.** Metamon's 15M floor was chosen to stop
  underfitting ~1M human battles and does not transfer to a lane with no imitation data.
  **Standing caution before anyone proposes "scale up":** in THIS project every
  capacity-shaped lever read null (privileged critic −0.0145; 12M→50M scale −0.016; ~88% of
  D26 critic rank idle), while the largest credited win came from adding structure at
  *reduced* parameter count. Attention here is **untested, not refuted** — it was killed
  pre-launch on a 34.6× CPU train-step microbenchmark (DESIGN.md §4 Rung 2, lines 337-340), never trained.
  The sharper architectural gap vs both large systems is **temporal context** (ps-ppo 64–256
  turns, Metamon 200; we are single-snapshot Markov), not pooling-vs-attention.

## Datasets

- **`HolidayOugi/pokemon-showdown-replays`** (HuggingFace) — public Showdown replays via the
  Showdown API. 33,154,470 rows / 69.8 GB parquet, upload dates 2005–2026, counts current to
  2026-06-20. Schema `id, format, players, log, uploadtime, views, formatid, rating`.
  **`gen1randombattle` = 109,147 replays** (verified against the dataset's own per-format table
  2026-08-04; more than Gen 1 OU's 102,574) — plausibly 10–20M state-action pairs counting both
  perspectives, vs P4's 903,090 SH decisions. **The only known route to human demonstrations in
  our exact format**, and human demos are NOT bounded by the 0.489 SH-imitation ceiling that caps
  every SH-clone approach. Filter to the format; do not pull 69.8 GB.
  Known problems, all verified: **`rating` is mostly null** (no skill filter — a clone learns the
  mean uploader, not the strong players); **no license is stated** (this repo may go public —
  handle like the Pons benchmark data: local, gitignored, never committed); voluntary-upload
  selection bias; and spectator logs hide each player's private view, so reconstruction is
  required and some actions are unrecoverable.
  **Metamon's parser is NOT a shortcut** — it does not support random battles (Gens 1–4 OU +
  Gen 9 OU only), it replaced poke-env's message parsing with its own so it cannot feed our
  `embed_battle`, and its action space (13, or a 9-choice `MinimalActionSpace` for Gens 1–4) orders
  moves and switches **alphabetically** where ours uses poke-env insertion order with 6 switch
  slots — a re-sort plus a hole, where an off-by-one silently mislabels every row. Its Gen-1
  mechanics parsing is still the right thing to fork.
  **Structural advantage for us — NOW MEASURED, AND MUCH SMALLER THAN THIS SENTENCE
  IMPLIED (2026-08-16).** randbats sets come from a fixed, public, enumerable pool
  (`showdown/data/random-battles/gen1/teams.ts`, already vendored), which does make
  belief-state reconstruction better POSED here than in the OU formats Metamon targets.
  It does not make it worth learning: the pool is ~146 species at 4.955 nats, the
  generator's type/weakness caps of 2 supply real structure, but **88-90% of it is a
  deterministic cap MASK and the genuine belief residual is 0.024-0.034 nats** — which is
  why D19 was killed at zero lanes and re-targeted into D25 (opponent ACTION prediction,
  which credited). Do not read this paragraph as motivating a team-prediction rung; see
  `DESIGN.md` §12's D19 block and `results/d19_closeout/`.
  (`DESIGN.md` §10 no longer exists — r7 retired §10-11.)

## Sources

- `wang2024_mit_thesis_randbats_rl.pdf` — Jett Wang, *Winning at Pokémon Random Battles
  Using Reinforcement Learning*, MIT MEng thesis, Feb 2024.
  https://dspace.mit.edu/handle/1721.1/153888
  The closest prior work: PPO + MCTS on gen4randombattles, rank 8 on the ladder. Pure
  network 0.786 vs SimpleHeuristics (Table 4.1; Fig 4.1 says ~0.85 — unreconciled), ~0.575
  at 6M steps (our budget). The only controlled LR-annealing ablation in this literature
  (constant 0.55 → annealed 0.80, §3.1.4). No opponent pool. Curriculum negative result
  (§5.1.3). Hyperparameters in Table A.3.
- `angliss2025_vgc_bench.pdf` — Angliss et al., *VGC-Bench* (arXiv 2506.10326), 2025.
  https://arxiv.org/abs/2506.10326 · code https://github.com/cameronangliss/vgc-bench
  Best apples-to-apples anchor — CORRECTED 2026-08-08 against the paper's own Tables
  8/10/11 (the previous "0.48 / 0.62–0.78" row mixed regimes): vs SimpleHeuristics at
  ~5M steps, scratch SP/FP/DO win 0.771–0.804 at 1 team, decaying to 0.510–0.518 at 64
  teams; BC-initialized 0.822–0.909 at 1 team, HOLDING 0.801–0.834 at 64 teams; BC alone
  0.449–0.489. The BC edge GROWS with team diversity (+10 pts → +32 pts) — and randbats
  is the diversity limit. Their recipe (Table 7): gamma 1.0, lambda 0.95, ~3k
  steps/update — OUR gamma/lambda, not Wang/ps-ppo's 0.75, so the "convergent recipe"
  prior has a third system on the other side. Cyclic payoff matrices (Appendix C) — a
  single SH winrate is a projection, not a ranking.
- `grigsby2025_metamon.pdf` — Grigsby et al., *Metamon* (arXiv 2504.04395), RLC 2025.
  https://arxiv.org/abs/2504.04395 · code https://github.com/UT-Austin-RPL/metamon
  Offline RL on ~1M human battles. Its `PokeEnvHeuristic` IS poke-env's SimpleHeuristicsPlayer,
  and **Table 2 + Figure 17 are the measured SH-vs-humans ladder record for FIVE formats** —
  the basis of the vs-SH → ladder conversion filed at the top of this index. Read that section
  rather than the Gen1OU number alone: this entry used to carry only Gen1OU 16W–59L (~0.21),
  which is SH's *worst* row and an OU tier, while the randbats rows (Gen7RB 24–32, Gen9RB
  28–32, GXE 39.7%/41.2%) are the ones that apply to our format. Paper's naive
  latest-checkpoint self-play arm underdelivered; post-paper, large diverse agent-vs-agent
  datasets became the main driver. Appendix A.1/A.2 also carry the randbats ladder anchors
  (Huang & Lee 1677/72%, Wang 1756/79.5%) and call Foul Play "the strongest open-source engine
  today" — relevant to the retired §11's ceiling argument, which rests on a competition placement instead.
- `karten2026_pokeagent_challenge.pdf` — Karten, Grigsby et al., *PokéAgent Challenge*
  (arXiv 2603.15563), NeurIPS 2025 competition report.
  https://arxiv.org/abs/2603.15563 · https://pokeagent.github.io
  Gen1OU won by pure-policy RL (#1 and #2); the MCTS agent (Foul Play) won Gen9OU but
  placed only #8 in Gen1OU — the pure-policy handicap is smallest in early gens. Finalist
  levers: Kron optimizer, AID activation (plasticity loss).
- `ps-ppo/` — README + ladder screenshot from https://github.com/Nebraskinator/ps-ppo.
  **Full source clone lives at `/Users/nickgreenquist/Documents/Projects/ps-ppo` — read it
  directly (see "Local code checkouts" above).** Pure-policy transformer, Gen 9 randbats,
  by u/Nebraskinator. Also archived here: `Pokemon Showdown AI (ELO 1900+) _ r_reinforcementlearning.pdf`,
  the announcement thread
  (https://www.reddit.com/r/reinforcementlearning/comments/1rgvnbw/pokemon_showdown_ai_elo_1900/ —
  reddit.com is unfetchable from the Claude Code sandbox, so this saved PDF is the only readable
  copy). Code read in full 2026-08-04; earlier entries rested on the README alone.

  **THE TRANSFERABLE FINDING — their move token is the encoder fix this project derived
  independently.** `obs_moves.py` encodes, per move slot: `stab_flag` (`move.type in
  [type_1, type_2, (+tera)]`), `expected_hits`, `self_boost_sum` (`sum(move.boosts.values())`
  gated on `target in ("self","allAlly")` — SH's setup rule, same gate), `status_raw` +
  `status_prob` (secondary-effect status AND its `chance`), a move-ID embedding, type /
  category / target one-hots, a 13-bin priority one-hot, `is_available`, and
  `owner_raw`/`slot_raw` positional identity so empty slots still carry coordinates. Every
  field the 2026-08-04 `baselines.py` audit found missing from our `_fill_move` is here, plus
  secondary-effect probability, which that audit had filed under "beating SH needs this."
  Independent convergence: we inferred it from reading SH's source, they arrived at it
  empirically. `obs_pokemon.py` is worth reading too — notably `stats_int` = 5 stats ×
  (min, est, max), an explicit belief range over hidden EVs/IVs, and boosts as 7 × 13 one-hot
  rather than a scalar.

  **They precompute NO type effectiveness.** Zero hits for `matchup` / `damage_multiplier` /
  `type_chart` / `effectiveness` across the tree — raw types both sides, attention learns the
  chart. **We are the exact inverse: we precompute cross-entity effectiveness (`_fill_move[+4]`,
  `_fill_mon[+30]/[+31]`) and omit STAB, which they precompute.** A flat MLP arguably needs the
  composed terms MORE, not less, so this is an argument for adding STAB, not for dropping ours.

  **Verified architecture at HEAD** (instantiated the model, 2026-08-04): **14,490,657 params** —
  embeddings 140,960 · subnets 4,321,088 · transformer 6,309,888 · JEPA 1,581,568 · readout
  2,103,808 · pi 7,182 · v 26,163. `d_model` 512, `n_layers` 3, `n_heads` 8, `act_dim` 14,
  value 51 bins over [−1.5, 1.5]. **The author's "~55M params" on Reddit is wrong; 14.5M is
  correct.** (An earlier guess here that embedding tables closed the gap is also wrong —
  they are only 141k.)

  **Action space: 14, positional** — `act_dim: int = 14  # 4 moves + 4 tera moves + 6 switches`
  (`config.py`), README §Action Mask gives indices 0–3 move, 4–9 switch, 10–13 tera+move. Same
  family as ours. With Metamon's 9 (4 move + 5 switch) this is the evidence that closed the
  action-space question on 2026-08-04: the strongest pure policies are positional; Wang's
  494-way identity space is the outlier and his headline needed MCTS.

  **HEAD IS NOT THE PUBLISHED SYSTEM.** None of the following appears in the README or the
  Reddit thread: a **JEPA auxiliary objective** (default `mode="ppo_with_jepa"`, `jepa_coef`
  1.0, EMA tau 0.99, 1.58M dedicated params); **dynamic GAE lambda** (`use_dynamic_lambda`,
  range 0.55–0.95); and **temporal context** (`kv_cache_len` 64, `batch_seq_len` 256, plus a
  373-line `obs_transitions.py`) — which flatly contradicts the author's Reddit statement that
  "the agent uses a single snapshot... it does not model the non-Markovian aspects of gameplay."
  He also states `d_model` 1024 (code: 512) and value support [−1.6, 1.6] (code: [−1.5, 1.5]).
  Any claim sourced from the README or thread describes an EARLIER system than the code.

  **Results — what survives verification.** The ladder Elo is real: `eval.py` (deleted at
  `7fb522c`, recover with `git show 7fb522c^:eval.py`) plays the public Showdown ladder via
  `ShowdownServerConfiguration` + `player.ladder(n)` with a username and password. Screenshot
  shows gen9randombattle Elo 2102 / GXE 76.7% / Glicko-1 1725 ± 25; the thread says "peaked at
  ~1900 ELO (top 25%)" and puts engine-search Foul Play above 2300.
  **The ">85% vs SimpleHeuristicsPlayer" figure must NOT be used.** No script in all 49 commits
  ever evaluated against SH — `eval.py` ladders against humans only. This is stronger than the
  2026-08-03 finding of "no eval script at HEAD": no such evaluation ever existed in code, so
  the number is not comparable to any win rate in this repo.
  **The "Wang MLP replication plateaued ~1100 ELO" claim likewise has no code support** — no MLP
  model exists anywhere in the history (`PokeNet` survives only in a stale `config.py`
  docstring). Treat as anecdote. Same status for the author's Reddit claim that "an MLP, even
  with dedicated subnets, was unable to perfectly mimic the bot; the transformer architecture
  was strictly required" — interesting, converges with our own encoder audit, but unquantified
  and untraceable. It is a hypothesis for our BC-clone diagnostic to test, not a result.

  **Confirmed as published:** reward `terminal_win/loss ±1.0`, `faint_self −0.1`,
  `faint_opp +0.1`; BC-from-SH via `SyncBridgePlayer(SimpleHeuristicsPlayer)` (`worker.py:200`)
  with the poke-env `_stat_estimation` +1-boost bug patched at `worker.py:76` (so their SH
  numbers are vs a PATCHED bot — comparability caveat); BC-fit-to-the-heuristic as an
  architecture screen ("configurations that failed to imitate perfectly were discarded").

  **Other hyperparameters** (`config.py`, all at HEAD): `gamma` 0.999, `gae_lambda` 0.75,
  `clip_coef` 0.1, `ent_coef` 0.02, `vf_coef` 0.5, `update_epochs` 2, `minibatch_size` 768,
  `grad_accum_steps` 4, `target_kl` 0.02, `steps_per_update` 36864, `lr` 3e-4,
  `weight_decay` 1e-2, `max_grad_norm` 0.5, `clip_vloss` False; rollout
  `target_concurrent_battles` 800, `rooms_per_pair` 32.

  **TWO DEFECTS — do not copy blind.** (1) The per-zone LR multipliers previously extracted
  here as transferable (backbone 0.5× / actor 1.0× / critic 2.0×) are **dead code at HEAD**:
  `LearnerConfig.__post_init__` keys its multiplier dict on
  `imitation/warmup/ppo/warmup_with_actor_reset`, but the default `mode` is `"ppo_with_jepa"`,
  which is not a key, so `.get(..., (1.0, 1.0, 1.0))` returns the neutral default and the
  multipliers never fire. (2) `lr_hold_steps: 500_000` exceeds `lr_total_steps: 1_00_000`
  (100k, written oddly) — hold longer than the whole schedule. Both corroborate a commenter's
  report of definition/usage mismatches. **Treat the repo as a design reference, not a recipe**;
  the author says as much in the thread ("not intended to be a package that you can simply
  download and run"; files were deliberately withheld).

  **CORRECTIONS 2026-08-06 (direction audit: full-source re-read + git-history walk; the
  load-bearing claim re-verified in-session).** (1) **`self_boost_sum` and the tera-STAB
  branch NEVER fire**: `Move.target` returns a `Target` enum on poke-env 0.15 and
  `obs_moves.py` compares it against `("self", "allAlly")` — verified live:
  `Move("swordsdance", gen=9).target` is `<Target.SELF: 15>`, membership False. The
  "SH's setup rule, same gate" sentence above is wrong in the flattering direction — their
  laddered agent had NO working setup-move or tera-STAB feature (same bug class as SH's own
  dead setup branch). (2) **The 2102-Elo agent is the `7fb522c`-era system** — 15 tokens/turn,
  d_model 1024, 2 layers, single snapshot, no JEPA, no KV cache, gamma 0.9999, lr 1e-4,
  clip 0.2, 2048 concurrent battles — and the author's Reddit statements (d_model 1024,
  support ±1.6, "single snapshot") describe THAT system accurately; only HEAD contradicts
  them, so "HEAD IS NOT THE PUBLISHED SYSTEM" above stands but the contradiction runs the
  other way. That snapshot does not instantiate (two hard errors at `config.py:257` and
  `ppo_core.py:203`), so **no committed revision reproduces the Elo**. (3) **The RL phase is
  pure MIRROR self-play vs the current policy** — both seats route to one weight set; the
  checkpoint league was never runnable in any commit (`policy_router.py` exists in no
  commit; HEAD deleted the mechanism). (4) **The published agent trained with a MISALIGNED
  faint bonus** — the off-by-one fix (`17e0955`, 2026-04-20) postdates the Elo screenshot
  (2026-02-27) — and laddered 2102 anyway; corroborates our Arm B null. (5) HEAD PPO
  plumbing is partly dead: `grad_accum_steps` never reaches the update (true batch 768),
  `target_kl` is inert under the default `ppo_with_jepa` mode, value-head decode support is
  [−1.6, 1.6] against an encode support of [−1.5, 1.5] (a 1.0667× scale error), and the LR
  "anneal" is a 27× single-step cliff caused by the `1_00_000` typo. (6) Claimed scale went
  ">150M" → ">250M states" in two minutes of commits; no logs or checkpoints exist anywhere
  in history. Infrastructure worth copying regardless: the `rlspawn.ts` server chat plugin
  (autospawn/reconcile/rescue battles), 10 local servers on one box, the action mask fed in
  as an observation feature, and integer embedding banks initialized sinusoidally.
- `pokejax/` — analyses, eval summary, and training log from
  https://github.com/JerJer2465/pokejax (gen4randombattle JAX engine). Scratch PPO ~0.55
  vs SH (n=20) at ~378M steps. Most useful part: their diagnosed obs-bridge bug list
  (stale `available_moves` 1–2 turns after switches — 15.9% of turns; PP never
  decrementing locally; sleep-turn off-by-one) — our bridge is audited against it.
- `elitefurretai_RL.md` — RL engineering doc from
  https://github.com/caymansimpson/EliteFurretAI (VGC doubles, in progress). Showdown
  throughput facts (one server process = one core; server-per-worker; centralized batched
  inference), opponent-pool curriculum with 1000-battle EWMA graduation windows.
- `saketatreya_pokemon-rl.md` — *Solving Pokémon as a POMDP*,
  https://github.com/saketatreya/inhumansystems (`writings/pokemon-rl.md`), Gen 9
  randbats. 70/30 past-checkpoint/random opponent mix vs forgetting; curriculum-over-
  heuristics reported as only "a slight benefit".
- `ivison2021_pokerl.html` — Hamish Ivison, *Reinforcement Learning with Pokemon*, 2021.
  https://ivison.id.au/2021/08/02/pokerl.html
  DQN floor datapoint: 0.47 vs MaxBasePower (weaker than SH) at 1M moves, gen8 randbats.
- `PHASE5_PRIOR_WORK_BRIEFING.md` — the maintainer's own advisory from a no-repo-access
  research session (2026-08-03), verified and corrected by the log entry above. Committed.
- `wang_fork_diffs.md` — full fork-vs-upstream diffs of Wang's three GitHub repos
  (`quadraticmuffin`: pokemon-showdown, poke-env, stable-baselines3), maintainer-extracted
  2026-08-03. The thesis's missing infrastructure layer: `>getstate`/`>load` stream commands +
  constrained team regen (the MCTS determinization — serialization itself is upstream Showdown),
  36 poke-env state-tracking fixes (encoder-relevant ones upstreamed by 0.15.0), SB3
  instrumentation only. Read + verified against our tree in the 2026-08-03 log entries.

- `huang_lee_2019_selfplay_pokemon.pdf` — Huang & Lee, *A Self-Play Policy Optimization
  Approach to Battling Pokémon*, IEEE CoG 2019. **VERIFIED 2026-08-07 (subagent deep-read;
  the citation survives contact BETTER than any other ladder row).** NOTE: the title this
  index previously guessed ("Competitive Deep RL over a Pokémon Battling Simulator") is a
  DIFFERENT paper (Simões et al. 2020) — do not chase it. Code: `yuzeh/metagrok` (MIT),
  **cloned as a sibling at `/Users/nickgreenquist/Documents/Projects/metagrok`**; the
  committed config reproduces the paper's 1,327,618 params exactly and the released
  checkpoint loads. The recipe: **pure mirror self-play from random init** (both seats the
  same object, no pool, no BC init, no curriculum), **3.84M battles (500 iters × 7680),
  6 days, ~$91 on GCP** — a 10⁸-scale statement; also financially trivial. **SEAT
  ACCOUNTING RESOLVED 2026-08-11 (subagent deep-read, gates any 250M quote): their PPO
  learner consumes BOTH seats' trajectories from every battle.** Paper Algorithm 1 is
  explicit ("update the neural network parameters using the **2m** self-play matches as
  training data"); code agrees (simulate_worker.py:48-53 writes p1+p2 trajectories per
  battle; integrated_rl.py:327-329 filters to one seat only if the expt config sets
  `player`, which the paper's run config expts/01.json does not; learner.py:130 sweeps
  both files into the rollup). The paper publishes NO decision count — this index's old
  "≈2-3×10⁸ decisions" was a reconstruction and is a BOTH-SEAT number; per-seat their
  run is ~0.96-1.5×10⁸ decisions (~1.15×10⁸ at ~30 decisions/seat/battle, the residual
  uncertainty being that 25-40 band, gen7). PPO epochs 6 (each transition reused 6× in
  SGD — data diet, not extra experience; no cross-iteration replay,
  updater_buffer_length_iters 1); errored battles re-simulated, not half-counted;
  terminal result rows dropped from training data; RL-meta adds a further 384k battles
  on top of the headline run. Structural note: their both-seat batches are exactly
  return-balanced per battle (one winner + one loser trajectory) — our one-seat-vs-pool
  batches are not. **CONVERSION LINE for the 250M decision: a 250M-step run in our
  currency ≈ 1.1× their learner-consumed diet (~2.3×10⁸) and ≈ 2.2× their per-seat env
  experience (~1.15×10⁸); their run ≈ 19× our 12M in learner-consumed terms, ≈ 9.6×
  per-seat.** Architecture is NOT a flat MLP: 128-d entity
  embeddings (species/moves/items/abilities), shared per-Pokémon net, DeepSets max-pool over
  the team, and a SHARED PER-ACTION SCORING HEAD ([trunk ‖ move_emb ‖ switch_target_emb] →
  shared MLP → scalar) — rung 1-2 of the architecture ladder, uncontested by ps-ppo (flat
  readout). Zero precomputed type chart (now 2 of 2 published ≥70% pure-policy agents).
  Undocumented in the paper, extracted from code: **gamma 0.95** + a **5-term ZERO-SUM
  shaping** (faint 0.0125, fail 0.005, supereffective 0.0025, resisted 0.0025, immune 0.005,
  all antisymmetric — unfarmable in mirror self-play), **no entropy bonus**, no grad clip,
  constant lr 2e-4. The 1677 Glicko is real (peer-reviewed, ladder script released) but
  n=300, one run, one fresh account, no error bar (±2.6pp binomial), possibly sampled rather
  than greedy (then a lower bound); "72% GXE" is 1677 pushed through Showdown's GXE formula
  (verified: 71.94%), NOT an independent measurement — quoting both is quoting one number
  twice. **PER-UPDATE BATCH SIZE — ADDED 2026-08-26, and it re-targets a number this
  repo already carries.** Verified against the committed run config
  (`expts/01.json` in the local metagrok clone), not the paper:
  `num_iters 500`, `simulate_args.num_matches 7680`, `updater_args
  {vbatch_size 8192, num_epochs 6, clip_param 0.1, opt_lr 2e-4,
  weight_decay 2e-6}`, `reward_args {gamma 0.95, lam 0.9}`.
  Both seats are harvested (see SEAT ACCOUNTING above), so **one H&L update
  consumes 7,680 matches = 15,360 episodes.** Ours consumes rollout 128 x 8
  envs = 1,024 steps ~= **34 episodes** at ~30 decisions/episode: a **~450x
  gap in terminal signal per update**, and the regimes are inverted — they
  take 500 enormous updates, we take ~11.7k (12M) / ~48.8k (50M) tiny ones.
  **WHY THIS MATTERS MORE THAN THE ~40x ALREADY LOGGED (2026-08-08):** that
  figure and the resulting **"~30 -> 100-300 episodes/update" target** were
  calibrated against **Wang (~1,600) and ps-ppo (~1,500)**. This index
  separately argues those are NOT our comparable — H&L is, being the only
  pure-self-play randbats success on record and our own lane. **Against the
  right comparable the recorded target is 50-150x too low, and the gap is
  ~450x rather than ~40x.** Total experience is the SMALLER gap (3.84M
  matches vs ~830k battles at 50M steps, ~4.6x), and cost is not the
  binder at all (6 days, ~$91 on GCP). **This is a config change, not a
  compute story** — and it is UNTESTED here, so it is a candidate, not a
  finding. **CAUTION, and it is why this went in the index rather than
  straight into a chapter: raising episodes/update at fixed total steps
  buys fewer, better gradients — it trades update COUNT for update
  QUALITY, and nothing here has measured which side binds.** Two
  confounds travel with any H&L comparison and must not be copied
  piecemeal: their `gamma 0.95` + 5-term dense shaping are COUPLED (we run
  gamma 1.0, sparse, and our own shaping arm read NULL), and their batches
  are exactly return-balanced per battle (one winner + one loser) while
  our one-seat-vs-pool batches are not.
  **PROVENANCE: an external expert review (2026-08-26) raised the
  per-update framing; the numbers above were re-verified here before
  being believed, and three of its claims did NOT survive that check** —
  it described the shaping as two terms with `supereffective` POSITIVE
  (the config has five terms and `supereffective: -0.0025`, `resisted:
  +0.0025`), it missed `gamma 0.95` / `lam 0.9` entirely, and it quoted a
  "~104 Glicko gap" that **cannot exist**: our ladder run was never
  listed, so we have no Glicko and no GXE (see the ladder landmine). The
  per-update finding stands on its own; those three do not.

  Their bot table does NOT transfer: 0.829 is vs a max-damage-typed bot far weaker
  than SH, and their 0.612 is vs the 2019 ancestor of foul-play, pre-Rust. Negative results:
  randbats self-play never learned multi-turn setup (Trick Room 0.12-0.15), and 50 iters of
  fine-tuning on fixed teams collapsed randbats play to 15.4% vs its own parent
  (catastrophic forgetting).

Referenced but not archived: PokéChamp / PokeLLMon (LLM agents, no SH numbers); rlmon
(results tables arithmetically impossible — do not cite).
