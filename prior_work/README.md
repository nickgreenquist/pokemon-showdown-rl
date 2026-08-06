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
  §11's proposed architecture screen.
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

**The conversion, worked for our own numbers.** Ties are non-wins under the locked protocol,
so SH-mirror parity is **0.489, not 0.500**. Best RL (12M+LRA) = 0.4607; renormalizing the
1.57% ties out gives ~46.8% head-to-head, i.e. **≈ −20 Elo vs SH**. So our best agent projects
to **~38–40% GXE**, a couple of points under SH. The rule of thumb: *a vs-SH win rate near the
0.489 parity mark means ~40% GXE, not "nearly solved."*

Where that sits in the published randbats field:

| agent | format | Glicko-1 | GXE |
|---|---|---|---|
| **ours (12M+LRA), projected** | gen1RB | ~1400–1450 | **~38–40%** |
| poke-env SH | Gen7RB / Gen9RB | ~1450–1500 | 39.7% / 41.2% |
| Huang & Lee 2019 — PPO self-play, **no search** | Gen7RB | 1677 | 72% |
| ps-ppo — transformer PPO | Gen9RB | 1725 ± 25 | 76.7% |
| Wang 2024 — PPO + test-time MCTS | Gen4RB | 1756 | 79.5% |
| Metamon SynRL-V2 — offline RL on human data | Gen1OU | 1761 ± 35 | 79.9% |
| best human players | — | — | 74–90% |

**Consequences, and the reason this is filed at the top of the index:**

1. **SH parity is not the finish line — it is ~40% GXE.** The floor of the published
   pure-policy randbats field is 72%. That gap is not a shaping/LR/step-count gap; it is the
   size that BC-init (VGC-Bench: +25–30 pts at matched budget) and encoder work move.
2. **A ladder eval is now PREDICTABLE from vs-SH, so it buys confirmation only.** Maintainer
   decision 2026-08-06: D7(a) stands (ladder Elo/GXE remains the ratified success metric) but
   its EXECUTION is deferred until an agent is clearly past SH. Metamon reports being accused
   of botting in chat at exactly this rating band.
3. **PS Elo ≠ Glicko-1.** ps-ppo's own screenshot is Elo 2102 / Glicko-1 1725 for one agent,
   and Metamon calls PS Elo "intentionally noisy" and not comparable across game modes. Our
   corpus survey's ratings (median 1203, p90 1415) are PS **Elo** and cannot be read against
   any Glicko row above. Quote GXE when comparing across sources.

**Four caveats, all stated by the source itself:** n is tiny (56 and 60 battles → ±6.5pp);
SH's low rating skews matchmaking toward weak opponents, so **raw W–L is an upper bound**;
Fig 17's Glicko "is possibly an overestimate" (slow convergence far below the mean); and
**nobody has measured gen1randombattle** — every randbats row above is gen4/7/9 and every
gen1 row is OU, so this is a cross-format extrapolation, not a measurement of our board.

## Local code checkouts — READ THESE DIRECTLY

Full source for the closest comparable system is on this machine, OUTSIDE the repo tree.
Any agent working on encoder, action-space, reward-shaping, self-play or PPO-hyperparameter
questions should read it rather than reason from the summaries below — the summaries are
lossy by construction and the code has repeatedly contradicted the project's own README.

- **`/Users/nickgreenquist/Documents/Projects/foul-play`** — full clone of
  https://github.com/pmariglia/foul-play at `25c976f` (the same commit DESIGN §11 audited).
  The teacher candidate for §11 option (C). Read `fp/config.py` for the CLI surface
  (`--bot-mode challenge_user`, `--user-to-challenge`, `--run-count`, `--search-time-ms`
  default 100, `--search-parallelism` default 1) and `Makefile` for the engine rebuild.
  **It is pinned to `poke-engine==0.0.48` built `--features poke-engine/terastallization`,
  i.e. GEN 9** — `gen1` is a real feature flag (verified against poke-engine's `Cargo.toml`:
  `gen1`..`gen9`, `default = []`), so gen1 work needs `make poke_engine GEN=gen1`, a Rust
  toolchain, and a from-source compile. **It carries our local-login patch applied**
  (`scripts/patches/foulplay_local_login.patch` in the main repo); re-apply it after any pull.
  Gets its own Python env — never the `pokemon-showdown-rl` one.
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
  **Structural advantage for us:** randbats sets come from a fixed, public, enumerable pool
  (`showdown/data/random-battles/gen1/teams.ts`, already vendored), so belief-state reconstruction
  is better posed here than in the OU formats Metamon targets.
  Full analysis, costs and the open phase-placement question: `DESIGN.md` §10.

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
  Best apples-to-apples anchor: scratch transformer PPO at 5M steps = 0.48 vs
  SimpleHeuristics; BC-initialized variants 0.62–0.78 (+25–30 pts at matched budget — the
  best-evidenced lever anywhere). Cyclic payoff matrices (Appendix C) — a single SH
  winrate is a projection, not a ranking.
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
  today" — relevant to §11's ceiling argument, which rests on a competition placement instead.
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

Referenced but not archived: Huang & Lee 2019 (~1677 Glicko-1, Gen 7 randbats — already a
PLAN.md anchor); PokéChamp / PokeLLMon (LLM agents, no SH numbers); rlmon (results tables
arithmetically impossible — do not cite).
