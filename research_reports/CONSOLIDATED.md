# CONSOLIDATED — one report from the four, cross-checked against the repo

Written 2026-08-29, in-session (single assistant, repo access; not deep
research). Sources: the four reports in this directory — 2× Claude deep
research, 2× Gemini deep research, commissioned on Q1 (convergence), Q2
(alternatives), and for the full-scope pair Q3 (hidden state), Q4
(variance), Q5 (search). **The standing rule of this directory applies to
this file too:** nothing below enters a pre-registration, config header,
or README row until verified against the actual paper or code. What this
file adds over the four is the cross-check against repo facts, which the
research models did not have.

**Serves JOURNEY step 1** (gen1 retrain, batch lever): it is the
requested research consolidation feeding R2's pre-reg cycle. It queues no
new gen1 lever.

## Verdict in four lines

1. The four agree the convergence worry (Q1) is theoretically real and
   invisible to self-play win rate — but **this repo already ran the test
   they all rank highest** (a best-response exploitability probe, D22
   Read 5, 2026-08-11) and it read **robust at probe budget**.
2. Their most-recommended agent-side change (past-checkpoint opponent
   pool) **is already production here**, at OpenAI Five's exact 80/20 mix.
3. **Nothing in the four changes R2's design.** The batch lever, the
   strength primary vs the 0.1007 bar, and the greedy scoring all stand.
   The reports contribute two free descriptive riders and a step-8 ledger.
4. The ranking disagreement the README asks to resolve dissolves on repo
   facts: Claude's #1 (paired/CRN evaluation) does not touch the binding
   variance term for a large-delta lever, and Gemini's #1 (EMAgnet+VRPO)
   is uncited and blocked by this directory's own verification rule.

---

## 1. Where the four agree, and how each claim fares against the repo

**(a) Independent symmetric PPO self-play in a 2p0s game has no
last-iterate convergence guarantee; cycling is invisible to
win-rate-vs-self.** All four, with a consistent citation base
(Mertikopoulos–Papadimitriou–Piliouras SODA 2018; Bailey–Piliouras EC
2018; Daskalakis–Foster–Golowich NeurIPS 2020 two-timescale necessity).
The cited papers are real and the theory is standard. **All four also
concede the magnitude is uncharacterized for our exact class**
(simultaneous + hidden + heavy chance): every positive equilibrium result
lives in alternating-turn or low-chance games. Verdict: real risk,
unmeasured size, and the repo's one direct measurement (§3a below) came
back reassuring.

**(b) A fixed entropy bonus is not a convergence fix; a KL-to-reference
(proximal) term is.** The Claude Q1/Q2 report makes the sharp version:
the entropy bonus defines a regularized game but does not give
last-iterate convergence to its equilibrium — that needs KL(π‖π_ref)
against a periodically-refreshed reference (MMD, Sokota et al. ICLR 2023,
arXiv:2206.05825; R-NaD, Perolat et al. ICML 2021). Gemini agrees via its
EMAgnet/NashPG framing. Our recipe is `entropy_coef 0.01`, fixed, no
reference term — so this is a genuine untested candidate. It is a few
lines, purity-preserving (the reference is our own past self), and both
Claude reports rank it the highest-EV *algorithmic* change. **Step-8
ledger, not R2** (§5).

**(c) Full algorithm replacement is rejected by all four.** Deep
CFR/DREAM/ESCHER (wrong paradigm, traversal assumptions, zero
simultaneous-move evidence), NFSP (DQN-shaped rewrite), full R-NaD
(weeks-scale rewrite; both flag that Stratego has **zero chance nodes**,
so DeepNash's transfer to us is assumed, not demonstrated), full
PSRO/league (compute shape wrong for one CPU box). Matches the repo's
standing scope; nothing to do.

**(d) Cycling detection should use artifacts we already have:**
cross-play matrices across seeds and checkpoints (intransitivity, JPC),
"loses to its own ancestor" forgetting reads, entropy/KL drift traces,
checkpoint-mixture-vs-last-iterate. All cheap, eval-only, purity-safe.
Partially planned already (cross-play is STATUS next-action 4). §4 names
the two worth adding to R2 as descriptive riders.

**(e) No published agent has reached a strong level in any Showdown
format via pure self-play from scratch.** The Claude Q1/Q2 report's §4 is
the best-sourced survey in the four and is one-directional: every strong
agent used human data, search, or an LLM prior. **This confirms the
novelty thesis is intact.** One definitional flag: it notes H&L is "not
documented as strictly pure-from-scratch" because of shaping/curriculum —
our purity lane excludes *expert data*, not shaping (A1 is literally
H&L's shaping), so H&L remains our comparable; say "no human data" rather
than "pure" when quoting externally.

**(f) Deterministic argmax at a simultaneous-move node is exploitable in
principle; the sound form is a mixed-strategy stage-game solve (LP /
regret matching), sampled.** Both full reports, consistent SM-MCTS
citation base (Lanctot et al. 2013; Bošanský et al. 2016). Applies to our
deployed depth-1 expectation search. Not actionable now: n=200 anonymous
ladder opponents do not adapt to us, and R2 is scored greedy. **Step-11
note** (the greedy-vs-searched deployment decision), §5.

**(g) OpenAI Five is the existence proof for the lane's recipe class.**
PPO self-play with 80/20 past-self sampling worked in a
simultaneous-move, hidden-info, mild-chance game — at ~45,000 years of
self-play. The recipe class is not doomed; scale is the gap. Useful
framing for the write-up, no action.

---

## 2. The ranking disagreement, resolved

The README notes: Claude ranks the measurement fix first and algorithm
replacement last; Gemini's Q1/Q2 report ranks EMAgnet+VRPO first and does
not rank the measurement fix. (The *full* Gemini report also ranks paired
evaluation first, so it is 3-of-4 for instrument-first; the Q1/Q2 Gemini
is the outlier.)

**Neither #1 should drive R2, for repo-specific reasons the research
models could not see:**

- **Claude's #1 (paired/CRN evaluation) does not touch R2's binding
  term.** The R2 bar (0.1007 at k=3) is set by cross-seed policy variance
  (σ_seed 0.0617), not eval noise — the n=3000 binomial floor is 0.00906,
  ~7× below it. Eval-side CRN/team-swap attacks the small term.
  Paired *training* seeds (the Sharma theorem) attack the right term, but
  only when the paired runs stay correlated — and the Claude report's own
  caveat kills it here: "interventions that reroute the whole training
  trajectory may decorrelate the paired runs." A ~30× episodes/update
  change reroutes the trajectory from the first update; expect paired
  ρ ≈ 0 and no gain. Also mechanical: our seed drives Showdown usernames
  (CLAUDE.md rule 2), and server-side battle RNG is not client-paired in
  our harness. The repo already derived the instrument wall independently
  and more precisely (k≥24 for the +0.025 floor; F(2,2) crit 19.0 needs a
  4.4× σ cut to detect). **The measurement-first stance is correct in
  general and already internalized here; the specific fix they propose
  does not rescue the current comparison.** Where it *does* apply: a
  future small-delta lever (e.g. the KL term at fixed batch) is exactly
  the case paired training seeds are built for — carry it in the step-8
  ledger.
- **Gemini's #1 (EMAgnet + VRPO) is blocked by this directory's own
  rule.** EMAgnet, GARIP, VRPO/"Q-boosting", NashPG and "RHyVE" carry no
  arXiv IDs anywhere in either Gemini report; GARIP and RHyVE match
  nothing we can place in the literature at all. The *idea* under EMAgnet
  (KL toward an EMA/snapshot of self) is the same idea as MMD/R-NaD and
  survives on the Claude reports' verifiable citations — adopt the idea
  from the verified lineage, not the unverifiable one. VRPO's target (GAE
  variance under stochasticity) is real as a mechanism, and note the
  batch lever R2 is already buying attacks the same quantity (averaging
  the update over ~30× more episodes); a bespoke expected-SARSA critic is
  not needed to test it.

---

## 3. What the reports recommend that this repo has already done

The research models had the brief, not the repo. Four of their headline
recommendations are already banked:

- **(a) Exploitability / best-response probe — their single
  most-recommended new instrument — RAN 2026-08-11** (D22 Read 5,
  `configs/showdown_br50m_s38.yaml`, SESSION_LOGS 2026-08-11 night). A
  fresh 6M-step entity learner vs the frozen struct50m s36 final: pooled
  two-orientation **0.4765 ± 0.0112** — below the pre-stated 0.55 line,
  "equilibrium robust at probe budget"; the attacker plateaued by ~1M and
  never reached parity. Pre-stated one-sidedness stands: a weak exploiter
  does not *prove* inexploitability (6M budget, one seed), and the target
  was the struct-era policy (0.5802 vs SH), two recipe generations behind
  the current object. But the reports' implicit "your recipe is probably
  badly exploitable" prior has one direct in-repo measurement against it.
  End-to-end cost was ~3.6 h — re-running it against the current best
  object is cheap and is the right step-8 gate (§5).
- **(b) Past-checkpoint opponent pool — production since the D-series.**
  `rl/selfplay/pool.py`: snapshot pool, `pool_size 20`,
  `latest_prob 0.8`, push every 150 updates, anchor + uniform-reservoir
  retention chosen against a published ablation. That is OpenAI Five's
  80/20 mix. Claude's #2 agent-side change is done; the only remaining
  delta is *prioritized* sampling (PFSP weighting), which is only
  motivated if cross-play shows forgetting.
- **(c) State-only privileged critic warning — theory matches our
  measurement.** Baisero & Amato 2022 / Lyu et al. 2022: state-only
  asymmetric critics bias the policy gradient and can hurt. The repo
  measured the privileged critic at **−0.0145** (C3 ledger). The reports
  supply the mechanism for a result we already have; if the idea is ever
  revisited, the sound form conditions the critic on ⟨history, state⟩
  jointly, not state alone.
- **(d) Belief-adjacent auxiliary head — partially done.** The credited
  D29r2 stack carries the opponent-action aux head. The reports' variant
  (predict hidden team/moves/HP) is a different target with, by their own
  admission, no clean effect size anywhere in the literature.
- Smaller overlaps: per-seed finals with a clustered-se credit line
  (stricter than the rliable-style reporting they urge); entropy traces
  already logged (`loss/*`); cross-play already queued as an R2
  descriptive.

**One analytic correction to all four:** they equate our seed-to-seed
spread with cycling/JPC. That is a hypothesis, not a finding. Our σ_seed
is measured against a *fixed scripted third party* (SH), which is not the
JPC signature (JPC is an off-diagonal drop in cross-play). And search@M
nearly equalizes the lanes (searched sd 0.0076, below the binomial
floor), which fits "lanes differ in value-head quality" at least as well
as "lanes sit at different phases of a cycle." The R2 cross-play
descriptive is exactly the discriminating read — one more reason to keep
it.

---

## 4. Application to JOURNEY steps 1–2: what changes (almost nothing)

**R2's design is untouched.** Lever = batch (episodes/update), one
change; primary = strength vs the 0.1007 bar with both sides carrying the
clustered term; scored greedy per the r9 rescore; control = s80/81/82.
Nothing in the four reports argues against the batch lever, and nothing
in them outranks it under the 50M ceiling and the scope guard.

Two descriptive riders proposed for the R2 pre-reg — both go through
R2's own 2-Opus cycle, both named descriptive, never verdict inputs:

1. **Sharpen the already-planned cross-play descriptive with two named
   reads:** (i) off-diagonal treatment-vs-control drop (the JPC read);
   (ii) within-lane late-vs-ancestor using checkpoints already saved (the
   forgetting read). Same battles as the planned cross-play; the reports
   contribute the *names of the failure signatures*, so the readout can
   say "cycling-consistent" or not instead of just reporting a matrix.
2. **Free log-side traces, zero battles:** per-lane entropy trajectory
   (already logged) and checkpoint-to-checkpoint policy drift. Batch is
   *expected* to change update dynamics; these are the cheapest record of
   how.

Explicitly **not** proposed for R2: KL-to-reference (a second lever —
contaminates the single-lever read), paired training seeds (ρ ≈ 0 under a
batch change, §2), eval-protocol changes (breaks comparability with every
banked arm; the locked protocol stands), checkpoint-mixture probes
(worthwhile but not free; step-8 material).

**Step 2 (ladder #3): nothing changes.** Exit condition is the run.

---

## 5. The durable ledger — candidates for later steps, with verification owed

Ordered; each names its verification debt. None is licensed by this file.

1. **Re-run the BR exploitability probe against the current best object**
   (12M ensemble or 50M s80, post-R2 winner). ~3.6 h e2e measured, probe
   infra exists (`_frozen_checkpoint_pool`), pre-reg pattern exists
   (br50m header). It is the instrument that decides whether item 2 is
   needed at all, and the honest "did the special sauce reduce
   exploitability" measure for step 8/9. Verification owed: none — in-repo.
2. **KL-to-reference regularizer (MMD-style; EMA or periodic-snapshot
   anchor).** Few lines on the PPO loss, purity-safe, the
   theoretically-correct fix if (and only if) item 1 or the R2 cross-play
   shows real exploitability/cycling. Natural home: JOURNEY step 8.
   Verification owed: read Sokota et al. 2023 (arXiv:2206.05825) and
   Perolat et al. 2021 before the pre-reg; ignore the EMAgnet/GARIP
   citations unless someone locates them.
3. **A2 both-seat harvest** — already licensed 2026-08-26, subordinate.
   The Gemini GAE-variance framing and H&L's return-balanced batches both
   support it; it remains the natural dose-matched companion/placebo for
   batch follow-ups.
4. **Pool prioritization (PFSP weighting)** — only if the forgetting read
   (§4.1.ii) fires. Verification owed: AlphaStar league mechanics against
   the Nature paper.
5. **Temporal context at the gen4 encoder rewrite (step 3).** The
   reports' recurrence recommendation (Ni et al. 2022, real citation)
   converges with A3, which the 2026-08-25 architecture review already
   named the sharper structural gap. Sequencing insight: A3 inherits
   C6's checkpoint-invalidation problem in gen1, but **step 3 pays the
   invalidation anyway** — the gen4 encoder rewrite is the free moment to
   add turn-history context.
6. **Paired training seeds for small-delta levers** (Sharma-style) — the
   right tool once a lever does *not* reroute the trajectory (e.g. the KL
   term at fixed batch). Verification owed: arXiv:2512.24145 exists and
   says what the report says; also whether our harness can actually pair
   env randomness (server-side RNG — likely needs work; scope it then).
7. **Mixed-strategy root solve at inference** (LP/regret-matching over
   the depth-1 joint-action matrix, sample instead of argmax) — a step-11
   deployment-form candidate, only if the laddered object is searched.

**Rejected outright** (concurring with 3–4 of 4 reports, plus repo
facts): Deep CFR/DREAM/ESCHER, NFSP, full R-NaD rewrite, full
PSRO/league, antithetic sampling (unproven for terminal win rate, and our
env RNG is server-side), state-only privileged critic (measured −0.0145,
theory now explains it).

---

## 6. Claims that must not be cited until verified

Per the directory's standing rule; the round-numbers-first heuristic.

- **Gemini full report:** recurrent-vs-static "12–25% win rate" gain;
  DUCT "62.3% in Tron"; SUCT "51.4–54.3%"; depth-1 "10–15%" and depth-2
  "4–8%" win-rate gains; ρ "routinely exceeds 0.85–0.95". All uncited.
  Treat as fabricated until sourced.
- **Gemini Q1/Q2 report:** EMAgnet, GARIP, VRPO/Q-boosting, NashPG,
  "Deterministic Exploitation Attractor" — no IDs anywhere; GARIP and
  RHyVE (full report) match nothing we can place. The claim "regularized
  PPO matches or exceeds R-NaD on benchmarks" is load-bearing for its #1
  ranking and is unverifiable as cited.
- **Claude reports:** citation IDs are largely real and known
  (Mertikopoulos 1709.02738, MMD 2206.05825, DeepNash 2206.15378, PSRO
  1711.00832, NFSP 1603.01121, Deep CFR 1811.00164, Timbers 2004.09677,
  Henderson 1709.06560, rliable 2108.13264, Ni 2110.05038, OpenAI Five
  1912.06680, DORA 2110.02924, ESCHER 2206.04122, DREAM 2006.10410,
  AdaStop 2306.10882). Content still unverified against source per the
  rule. Spot-check before use: Sharma 2512.24145 (both Claude reports'
  #1 lean on it), the DFG arXiv ID (2101.04233), the OpenSpiel R-NaD
  Liar's Poker cite (2511.03724), and the PokéAgent report ID
  (2603.15563). Metamon quotes (GXE 74–90% human ceiling; SynRL-V2
  Gen1OU 79.9%/#31) should be checked against the local copy indexed in
  `prior_work/README.md` before entering any doc — that index is the
  authority, not these reports.
