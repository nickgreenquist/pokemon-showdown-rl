# docs/research_reports

AI deep-research reports commissioned for this project. **Not `docs/prior_work/`** —
that index holds *verified* external material, read before citing any external
result. These are raw model output: useful for orientation and for finding
papers worth reading, and **not evidence until checked against source.**

Standing rule, and it has already been earned three times over on the H&L
entry in `docs/prior_work/README.md`: a claim in one of these files may not enter a
pre-registration, a config header, or a README row until someone has verified
it against the actual paper or code. Round numbers with no citation
("12–25% win rate", "62.3% in Tron") are the ones to check first.

| file | source | scope | formatting |
|---|---|---|---|
| `RL_RESEARCH_REPORT_CLAUDE.md` | Claude, deep research | all five questions | as pasted |
| `RL_RESEARCH_REPORT_GEMINI.md` | Gemini, deep research | all five questions | rebuilt 2026-08-28 (pasted as one line; text verified unchanged) |
| `RL_RESEARCH_REPORT_Q1_Q2_ONLY_CLAUDE.md` | Claude, deep research | Q1–Q2 (convergence, alternatives) | as pasted |
| `RL_RESEARCH_REPORT_Q1_Q2_ONLY_GEMINI.md` | Gemini, deep research | Q1–Q2 (convergence, alternatives) | rebuilt 2026-08-28 (pasted as one line; text verified unchanged) |
| `CONSOLIDATED.md` | in-session assistant, 2026-08-29 | the four above, cross-checked against repo facts | authored here |

**They disagree, and the disagreement is the interesting part.** Claude ranks
the measurement fix first (paired/CRN evaluation across training seeds) and
puts algorithm replacement last. Gemini's Q1/Q2 report ranks EMAgnet + VRPO
first and does not rank the measurement fix at all. Both agree independent PPO
self-play in a 2p0s game has no last-iterate convergence guarantee, and both
flag that Stratego — R-NaD's evidence base — has zero chance nodes. ~~Resolve
the ranking before spending on either.~~ **RESOLVED 2026-08-29 in
`CONSOLIDATED.md` §2: neither #1 drives R2.** Paired evaluation does not touch
the binding variance term for a large-delta lever (a batch change decorrelates
paired trajectories — the Claude report's own caveat), and EMAgnet/VRPO are
uncited and blocked by the standing rule above. The durable output is the
diagnostic riders and the step-8 candidate ledger in `CONSOLIDATED.md` §§4–5 —
and the finding that two of the four's headline recommendations (BR
exploitability probe, past-checkpoint opponent pool) were already done here
before the reports were commissioned.
