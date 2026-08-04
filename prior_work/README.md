# prior_work — external sources for the Phase 5 capstone

Local archive of the papers and project write-ups that informed Phase 5 design, collected
during the 2026-08-03 prior-work verification dig (full findings: the "prior-work
verification" entry in `SESSION_LOGS.md`). Everything here except this index and the
briefing is **gitignored** (third-party copyright + repo size); the files live on disk
only, so re-download from the URLs below if one goes missing.

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
  Offline RL on ~1M human battles. Measured SimpleHeuristics vs the human ladder: Gen1OU
  16W–59L (~0.21) — SH's weakest format. Its `PokeEnvHeuristic` IS poke-env's
  SimpleHeuristicsPlayer. Paper's naive latest-checkpoint self-play arm underdelivered;
  post-paper, large diverse agent-vs-agent datasets became the main driver.
- `karten2026_pokeagent_challenge.pdf` — Karten, Grigsby et al., *PokéAgent Challenge*
  (arXiv 2603.15563), NeurIPS 2025 competition report.
  https://arxiv.org/abs/2603.15563 · https://pokeagent.github.io
  Gen1OU won by pure-policy RL (#1 and #2); the MCTS agent (Foul Play) won Gen9OU but
  placed only #8 in Gen1OU — the pure-policy handicap is smallest in early gens. Finalist
  levers: Kron optimizer, AID activation (plasticity loss).
- `ps-ppo/` — README + ladder screenshot from https://github.com/Nebraskinator/ps-ppo
  (cloned and code-verified 2026-08-03). Pure-policy transformer (14.5M params), Gen 9
  randbats, Elo 2102 / GXE 76.7% / Glicko-1 1725±25 (screenshot) — real but confounded
  (BC-from-SH init + faint shaping + arch, no ablation); the "Wang MLP ~1100 Elo" README
  claim has no code support. Transferable: BC-fit-to-the-heuristic as an architecture
  screen; the poke-env SimpleHeuristicsPlayer `_stat_estimation` +1-boost bug (patched in
  their `worker.py`). Action space is **14 = 4 move + 6 switch + 4 tera-move — positional**,
  the same family as ours, which is the load-bearing fact when the action-space question is
  re-opened (see the 2026-08-04 entry).
  Announcement thread: https://www.reddit.com/r/reinforcementlearning/comments/1rgvnbw/pokemon_showdown_ai_elo_1900/
  (r/reinforcementlearning, title "Pokemon Showdown AI ELO 1900"). **UNREAD — reddit.com is
  unfetchable from the Claude Code sandbox (both `www.` and `old.`), so nothing from the post
  body or comments has been verified and none of it informs any claim in this repo.** Attribution
  to the ps-ppo author is inferred from the matching ">1900 ELO" figure, not confirmed. Worth a
  manual read: announcement threads often carry author replies on hyperparameters, failures and
  negative results that never reach the README — exactly the ablation detail ps-ppo lacks.
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
