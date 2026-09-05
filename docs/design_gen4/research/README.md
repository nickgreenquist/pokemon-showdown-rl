# docs/design_gen4/research — the raw research behind the five design docs

**Status: EVIDENCE, NOT AUTHORITY.** These are the research notes the five
docs in `docs/design_gen4/` were distilled from (2026-09-04, gen4-design
worktree, docs-only). Where a note and a doc disagree, **the doc wins**; two
known errors in the notes were corrected in the docs and are listed below.
Nothing here is a pre-registration, a measurement, or a verdict input. Kept
because the docs deliberately compressed implementer-grade detail (per-ability
and per-item tables, the generator's sampling rules, the 54-row seam-assumption
table, poke-env field-by-field semantics) that step 3 would otherwise re-derive.

Every claim in a note carries one of the four tags defined in `HEADER_TEMPLATE.md`
(tree-verified / source-verified / literature-only / needs-live-verification)
and a `file:line` or page citation. Repo line numbers are `main@2738025`
(the snapshot the agents read); `showdown/` numbers are the vendored
pokemon-showdown 0.11.11 @ 59da482; `poke_env/` is the pinned 0.15.0.

## The notes (one per source family; the four the brief named that never landed are listed after)

| note | source family | feeds |
|---|---|---|
| `showdown_gen4_mechanics.md` | vendored `showdown/data/mods/gen4/*`, base data, `sim/`, gen1 mod — the rules delta with the inherit chain traced | `mechanics_delta.md` |
| `showdown_gen4_pool.md` | `random-battles/gen4/{sets.json,teams.ts}` + the gen5 base — exact counts, sampling rules, EV/IV/HP rules, vocab sizes | `mechanics_delta.md` §5/§14, `encoder_requirements.md` §3.4–3.5 |
| `showdown_gen4_abilities_items.md` | the 101-ability / 40-item universes, gen4 semantics, reveal model, the 12+5 class taxonomy | `mechanics_delta.md` §11, `encoder_requirements.md` §3 |
| `pokeenv_battle_state.md` | poke-env 0.15.0 `battle/*` field by field for gen4 | `pokeenv_gen4_survey.md` §3–5 |
| `pokeenv_env_layer.md` | poke-env env/action/player layer; `SimpleHeuristicsPlayer` end to end | `pokeenv_gen4_survey.md` §1–2/§7, `anchors_and_eval.md` §1 |
| `wang_pokeenv_fork.md` | Wang's poke-env fork diffed against 0.15.0 (30 changes: 15 upstreamed, 1 partial, 9 absent) | `pokeenv_gen4_survey.md` §6 |
| `our_encoder_seam_inventory.md` | the landed `EncoderSpec` seam and every gen1 assumption still outside it (A1–A54); the test contract; a GEN4 proposal | `encoder_requirements.md` |
| `wang_thesis.md` | Wang 2024 read in full: Tables A.1–A.3, Fig 4.1 digitized, MCTS, the γ/λ discrepancy resolved | `encoder_requirements.md` §5, `anchors_and_eval.md` §6 |
| `huang_lee_metagrok.md` | H&L 2019 + the metagrok clone: observation as the code builds it, the most-damage-typed bot verbatim, recipe facts | `encoder_requirements.md` §5, `anchors_and_eval.md` §2 |
| `project_record.md` | the repo's own record: Wang verification entries, the anchor-battery convention verbatim, the search-depreciation data set with provenance (incl. the IDEAS §2.5 "12M" error), standing rulings, the 2-Opus house style | `anchors_and_eval.md`, `open_questions.md` |

| `wang_showdown_fork.md` | Wang's pokemon-showdown fork, `wang_fork_diffs.md` §1 (2026-09-05, Opus agent, gen4-build): `>getstate`/`>load` is a full perfect-information dump; the determinizer's exact constraints; the fork samples the SAME curated role-table generator family we vendor; only `/offertie`'s turn-100 gate changes a rule | `encoder_requirements.md` §3.5, `open_questions.md` Q12 / D1, `anchors_and_eval.md` §6 |
| `psppo_metamon_obs.md` | ps-ppo's obs_*.py in full + Metamon's tokenisation appendix (2026-09-05): items / abilities / stat ranges / counters / weather / sentinels, and the comparison table against our proposal | `encoder_requirements.md` §5, `open_questions.md` Q11 / Q13 / Q29 / Q43 / D2 |
| `foulplay_pokejax_audit.md` | foul-play's search core, request parsing and hidden-state bookkeeping for gen 4; the Struggle panic re-diagnosed; the upstream set-file schema; pokejax's bug list as an audit checklist (2026-09-05) | `anchors_and_eval.md` §3, `encoder_requirements.md` §9, `open_questions.md` Q37 / D3 |
| `critic_pass.md` | the completeness-critic pass (2026-09-05): 131 citations checked, 111 verified, 20 wrong or drifted (corrected inline in the docs), cross-doc inconsistencies, completeness gaps, the 23-row live checklist | all five docs |

**Still not produced:** the literature cross-check (Bulbapedia / Smogon vs the
vendored sim; deferral D4) and `search_depreciation.md` (D5).

**Live evidence (`live/`, 2026-09-04/05):** the protocol-tally summaries of the
eight local tape runs (`scripts/gen4_smoke.py`; the tapes themselves are
gitignored under `data/gen4_tapes/`) and the generator sample
(`scripts/gen4_sample_generator.js`, 100,000 teams). Each doc's final section cites them; `rl/envs/gen4/tape.py::protocol_stats` is the code that produced every count, so a reader can re-run it on a new tape. The `fp*` / `h2h*` summaries are the Foul Play gen-4 runs (`scripts/gen4_fp_smoke.py`, `scripts/gen4_fp_h2h.py`); `fp_gen4_set_pin.json` pins Foul Play's opponent-model file.

## Known errors in the notes, corrected in the docs

0. `critic_pass.md` §1 lists 20 wrong or drifted citations across the five docs
   (line numbers, three counts, the sleep range and wake law, Sleep Clause vs
   Rest); all are corrected inline in the docs with a `critic_pass.md` citation.
   `wang_thesis.md:580-593` ("the generator he measured is not the generator we
   would run") overstates the difference: `wang_showdown_fork.md` §4 shows the
   same generator family; what differs is the ability source and the table
   contents at 2023 vs 59da482e.

1. `showdown_gen4_mechanics.md` §7 says gen5's `onSwitchIn` sleep reset "applies to
   gen4". It does not: gen4's `slp` entry has no `inherit: true`, so it replaces the
   parent entry entirely (`showdown/sim/dex.ts:676-695`); foul-play's GEN4 table
   agrees. Corrected in `mechanics_delta.md` §6 (commit b7b7bd0).
2. `our_encoder_seam_inventory.md` §4.6 says "262 distinct dex numbers"; the pool's
   295 species map onto **267** (its own §4.2 collapse table is consistent with 267).
3. `pokeenv_battle_state.md` §1.1 estimates the item vocabulary at "≈26"; the
   exhaustive extraction in `showdown_gen4_abilities_items.md` §2.2 is **40**
   (17 species-forced + 23 by rule).
4. `pokeenv_battle_state.md` §1.5 reads the sleep counter as "correctly tracked";
   `wang_pokeenv_fork.md` #10 shows it double-bumps on a Sleep Talk turn
   (`abstract_battle.py:726-741` calls `moved()` twice). The docs carry the fork
   note's reading, pending a parse-only replay test.

## `probes/` — the scripts behind the counts (ours; outputs are small derived data)

`_gen4pool_probe.js` / `.out.json`, `_gen4pool_sample.js` / `.out.json`, `gen4dump.js`
(the gen4 dex/format dump the pool note cites; its 645 KB output is NOT tracked —
re-run under `nice -n 19 node` against the vendored `showdown/`), `gen4_moves_merge.js`
and `tc_diff.js` (the merged gen4 move table and the gen1-vs-gen4 type-chart delta;
read `showdown/dist/data/**/*.js` — the compiled data — so spot-check the `.ts`
before a pre-reg quotes a number from them), `_gen4_vocab.py` / `.out.json`,
`ab_item_parse.py` with `_ab_facts.txt` / `_it_facts.txt` / `_ab_names.json` /
`_item_names.json` / `_ability_ids.txt` / `_item_ids.txt` (the abilities note's
extraction), `_effect_strings.txt` (185 literal effect strings greppable from the
sim, the coverage lower bound), `_fig41_probe.py` / `_fig41_read.py` (the Figure 4.1
digitization), `extract_block.sh`.

## Not tracked, and how to regenerate

- pdftotext dumps of the Wang, H&L and Metamon PDFs and page images (third-party
  content; `pdftotext -layout docs/prior_work/<pdf>`, PDFs are gitignored under
  `docs/prior_work/`).
- `_gen4_dexdump.json` (645 KB of Showdown data): `nice -n 19 node probes/gen4dump.js`.
- `_base_abilities_pool.txt` / `_base_items_pool.txt` (Showdown data extracts).
- `psppo_1b13ae0/`: `git -C ../ps-ppo show 1b13ae0:<file>` for the obs files.
- The main-tree snapshot the agents read (`git archive main@2738025`).

## `sweep_scripts/` — the agent prompts (provenance of the notes)

`sweep1_fable_14wide.js` (2026-09-02/03, two runs: 0/14 and 0/14 — every agent
died at the session usage limit; 14 in flight at once) and `sweep3_opus_waves.js`
(2026-09-04, `model: 'opus'`, three sequential waves of five: 10/14 notes landed
before the next limit; the reconcile critic and follow-ups never ran). The four
2026-09-05 notes were one wave of four Opus agents launched by hand from the
`gen4-build` session (prompts in SESSION_LOGS 2026-09-05), while the orchestrator
built the encoder — all four landed. The exact
task text each note answers is the `T[...]` entry in the script; the PREAMBLE is the
hard-bar and tagging contract every agent worked under. The lesson is recorded in
the maintainer's memory (fan out in waves of ≤ 5).

`GEN4_DESIGN_PROMPT.md` is the maintainer's brief (precedent:
`docs/archive/AUDIT_WORKTREE_PROMPT.md`). `DOC_CONVENTIONS.md` and
`HEADER_TEMPLATE.md` are the writing rules the five docs follow — reuse them for
any doc added to this directory.
