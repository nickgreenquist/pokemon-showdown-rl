# LLMs in the Loop for Reinforcement Learning — Technical Report

*Revised 2026-08-05. Companion to `CROSS_FEATURES_AND_ARCHITECTURE.md`, which is now the **primary** path; this document covers optional LLM-assisted techniques, all of which are deferred behind it.*

## Revision note — what changed and why

The first draft ranked **frozen LLM embeddings of species/move descriptions** as recommendation #1. **That ranking was wrong and is retracted.** Two objections surfaced in review:

1. **A frozen embedding is a constant per move.** The same vector represents Blizzard whether Lapras uses it (STAB) or Tauros does (no STAB), and whether the target is Exeggutor (2×) or Lapras (0.5×). By construction it cannot encode STAB or type effectiveness — the two properties most likely to be the binding constraint. It does not reduce the composition burden; it adds ~32–64 dense dimensions the flat MLP must *still* multiply against distant type blocks.
2. **The precedents use attention, not concatenation.** EMMA (ICML 2021) and ATLA (CoRL 2022), the two real frozen-embedding results, inject them through entity-conditioned attention — the mechanism that makes a context-free vector usable in context. Bare concatenation into a flat MLP is a different and weaker proposition, and it is untested anywhere.

Both objections point the same way: **explicit cross features and crossing machinery come first.** LLM embeddings become interesting *after* an attention trunk exists, as a source of semantic residue (the quirks nobody thought to enumerate) rather than as a fix for composition.

A third consideration specific to this project: Gen 1 has ~165 moves, no abilities and no items. The embedding's selling point — "you don't have to enumerate every quirk" — is worth much more in Gen 9 (900+ moves, abilities, items) than in a vocabulary small enough to hand-featurize in an afternoon.

The taxonomy (§1–2) and evidence assessment (§5) below stand as originally researched. Only the recommendations changed.

---

## Scope

This report covers **LLMs helping an RL agent** — LLM-in-the-loop for RL. The reverse direction (RL used to train LLMs: RLHF, RLVR, GRPO, DPO) is a separate and much larger field, and is out of scope.

Two things easily conflated in the Pokémon literature:
- **LLM-as-agent** — the LLM *is* the policy (PokéLLMon, PokéChamp). Not this project.
- **LLM-assisted RL** — the trained neural policy remains the decision-maker; the LLM contributes features, rewards, curriculum, or analysis. This is the target.

Evidence grades: **[PR]** peer-reviewed · **[PP]** preprint · **[BLOG/REPO]** blog or personal repo.

---

## 1. Taxonomy

### 1.1 LLM as action prior
- **Yan et al., Efficient RL with LLM Priors** [PR, ICLR 2025], arXiv:2410.07927. LLM as prior action distribution via variational inference; DQN-Prior, CQL-Prior, GFlan-Prior. Reports >90% sample reduction in offline settings on ALFWorld/Overcooked. Code: github.com/yanxue7/RL-LLM-Prior.
  **Blocked for this project:** per-decision querying over a *textual* action space, benchmarked on action spaces of size ~8–50.
- **LAMARL** [PP], arXiv:2506.01538 — LLM-generated prior regularizes MADDPG.
- **Cache-Efficient Posterior Sampling** [PP], arXiv:2505.07274 — caches LLM outputs across similar states to confront the latency problem directly.

### 1.2 LLM for exploration guidance
- **LLM-Explorer** [PP], arXiv:2505.15293. Samples action-reward trajectories, prompts an LLM to summarize learning status, emits an updated exploration distribution **every K episodes**. Reports up to 37.27% average improvement on Atari/MuJoCo. Code: github.com/tsinghua-fib-lab/LLM-Explorer. **The periodic-call archetype — the one exploration method whose call placement is compatible with a fast loop.**
- **ELLM** [PR, ICML 2023], arXiv:2302.06692 — LLM suggests goals from a text state description; evaluated in Crafter. Needs a state→text captioner. Gains degrade in novel worlds (Mars benchmark, arXiv:2410.08126).
- **LLM-augmented observations** [PP], arXiv:2510.08779 — recommendations injected into the observation so the agent learns when to ignore them.

### 1.3 LLM as reward designer
- **Eureka** [PR, ICLR 2024], arXiv:2310.12931. GPT-4 writes reward **code**, evolutionary refinement from training statistics. Outperforms human experts on 83% of 29 environments. LLM call is offline/between-runs.
- **Text2Reward** [PR, ICLR 2024], arXiv:2309.11489. Dense reward code from a Pythonic env representation; used with **PPO and SAC**. Matches or beats expert-written rewards on 13/17 manipulation tasks. **Most directly relevant — targets PPO and produces auditable code.**
- **Kwon et al.** [PR, ICLR 2023] — LLM outputs scalar rewards from a behavior description.

### 1.4 LLM as reward model / critique evaluator
"LLM-as-a-Judge" as reward signal. Thin evidence in games specifically; most instances are in the out-of-scope direction. **Weak.**

### 1.5 LLM latent representations as features
- **LESR** [PR, ICML 2024], arXiv:2407.13237. **Correction:** LESR does *not* use frozen embeddings — the LLM generates state-representation **code** plus intrinsic reward code. +29% on MuJoCo. Do not cite as embedding evidence.
- **EMMA / Messenger** [PR, ICML 2021], arXiv:2101.07393. Frozen BERT-base entity descriptions via **entity-conditioned attention**; 40% higher win rate on zero-shot generalization — but the authors note hardest-stage win rate stays at 10%. Code: github.com/ahjwang/messenger-emma.
- **ATLA** [PR, CoRL 2022], arXiv:2206.13074. Frozen BERT-base → 768-d fixed vectors conditioning a meta-RL policy. Cleanest "embed a description → feed to policy" example found.
- **Werewolf RL**, arXiv:2310.18940 — frozen `text-embedding-ada-002` as input to a self-attention RL policy.
- **NetHack Learning Environment**, arXiv:2006.13760 — notably learns glyph embeddings **from scratch**; frozen-LLM-embedding-as-feature is not standard practice even in a rich named-entity game.
- **Gap:** no head-to-head ablation isolating frozen-LLM-embedding vs. randomly-initialized-learned-embedding, all else equal, in any game. None in Pokémon.

### 1.6 LLM planner + RL controller
- **SayCan** [PR, CoRL 2022], arXiv:2204.01691. LLM proposes skills, learned value functions ground them (`p(useful) × p(feasible)`). Per-decision calls; fine at robot timescales.

### 1.7 LLM as shield / veto
Classical shielding — **Alshiekh et al. 2018** [PR, AAAI], arXiv:1708.08611; Probabilistic Logic Shields, arXiv:2303.03226 — uses *formal logic*, not LLMs. **No mature LLM-based shield literature exists.** An LLM veto layer is a folk technique, not an evidenced one.

### 1.8 LLM as world model
Surveys catalog LLM-as-rollout and dynamics learners (arXiv:2404.00282); arXiv:2411.08794 is a sobering counterweight. **Irrelevant here** — you have the exact simulator.

### 1.9 LLM as curriculum / opponent designer
OMNI, OMNI-EPIC, CurricuLLM (arXiv:2409.18382). Periodic/offline placement, compatible in principle, marginal over an existing checkpoint pool.

### 1.10 LLM for offline trajectory analysis
Sparse formal literature, but **directly mirrors Wang's §4.4**, which used three expert players to diagnose losing games. Entirely offline.

### 1.11 LLM-assisted BC / demonstration generation
Adjacent to the existing BC clone. In Pokémon the richer resource is the ~109k human `gen1randombattle` replays.

---

## 2. Game-specific work

**Minecraft.** Voyager (arXiv:2305.16291) — GPT-4 writes reusable code skills, automatic curriculum, self-verification; 3.3× more unique items, 15.3× faster tech-tree milestones. **Not an RL hybrid** — LLM-as-agent with a code skill library. DEPS, Plan4MC, JARVIS-1 are planner relatives.

**Crafter / NetHack / Procgen.** ELLM in Crafter. NetHack LLM agents still underperform an extensive heuristic bot — a caution about long-horizon roguelikes.

**Imperfect-information games (closest structural match).** CICERO, Hanabi, DeepNash, Libratus/Pluribus are **RL + search + game theory**; language models appear in CICERO for *dialogue*, not as the policy core. Confirms the structural analogy, offers no ready recipe.

**Text games.** ALFWorld, TextWorld, Jericho — action space is already language. Least transferable to a fixed Discrete(10) vector setting.

**Pokémon.**
- **PokéLLMon** [PR], arXiv:2402.01118 — LLM agent, 48.57% Gen8 random ladder, 56% vs. invited humans. No trained RL policy.
- **PokéChamp** [PR, ICML 2025 spotlight], arXiv:2503.04094 — LLM-powered minimax; 76% vs. the best LLM bot, 84% vs. the strongest rule-based bot, projected Elo 1300–1500. No LLM training, not a trained-NN hybrid. Note a substantial fraction of its ladder games were lost to turn timeouts — read ladder figures alongside head-to-head numbers.
- **Metamon** [PR, RLC 2025], arXiv:2504.04395 — offline RL + transformers on reconstructed human replays, Gens 1–4. **The strongest trained-policy Pokémon work, and it uses no LLM in the policy.**
- **VGC-Bench**, arXiv:2506.10326 — LLM is a *separate baseline agent*, not fused into the RL policy. Also the source of the strongest lever in this whole literature: BC-initialized variants at 0.62–0.78 vs. scratch PPO at 0.48, **at matched 5M budget**.
- **Wang 2024 MIT MEng thesis** — PPO + MCTS, rank 8 gen4randombattles. §5.1.1 proposes LLM embeddings of attributes as **untested future work**; §4.4 used three human experts for failure analysis.
- **Zhang, Parashar & Saha 2023** [BLOG/REPO — non-peer-reviewed student project, author labels the code "bad"] — LLM-shaped intrinsic rewards for PPO/DQN in Pokémon Showdown. Most on-point, least trustworthy.

**Determination:** no peer-reviewed or robust open-source work fuses a trained neural RL policy with an LLM component for Pokémon Showdown. Genuinely close to unexplored — with the standard caveat that "unexplored" sometimes means "tried privately and didn't work."

---

## 3. Feasibility under this project's constraints

The loop is ~95% collect and inference-bound; the update is ~5%. An LLM call at ~0.5–2 s against an ~83 µs forward pass is a 6,000–24,000× mismatch. **Viable placements are Offline (once), Periodic (every N updates), or Eval-time only.** The compute budget has since been lifted (GPU / CPU fleet available), which changes what training runs are affordable but **does not change the per-call latency ratio** — this constraint survives the hardware change.

| Technique | Call placement | Impl. cost | API $ | Perturbs loop? | Verdict |
|---|---|---|---|---|---|
| Offline replay/failure analyst | Eval-time | 2–4 days | $10–50/batch | No | **Recommended** |
| Potential-based reward shaping, LLM-drafted as code | Offline/periodic | 3–6 days | $20–150 | No | Conditional |
| Frozen embeddings of move/species text | Offline (once) | 1–3 days | <$5 | No | **Deferred — see revision note** |
| Periodic exploration adjuster | Periodic | 4–8 days | $30–120 | Minimal | Only if plateau is exploratory |
| Curriculum / opponent designer | Periodic | 4–8 days | $20–80 | No | Marginal over existing pool |
| Action prior (Yan et al.) | Per-decision | 5–10 days | High | **Yes** | Rejected — latency + non-text actions |
| Runtime veto / shield | Per-decision | 2–5 days | High | **Yes** | Rejected for training; eval-only at best |
| Planner + controller (SayCan) | Per-decision | High | High | **Yes** | Rejected — no skill hierarchy |
| World model | n/a | — | — | — | Rejected — simulator exists |

---

## 4. Recommendations (revised)

**Everything in `CROSS_FEATURES_AND_ARCHITECTURE.md` ranks above everything here.** The plateau is most likely compositional, and no LLM technique addresses composition. Within the LLM options:

### #1 — LLM as offline replay / failure-mode analyst
Feed batches of **losing** games as structured turn logs; ask for recurring failure patterns. Mirrors Wang's three human experts. Addresses the project's actual gap: win rate says *that* it plateaus, never *why*.
**Data flow:** dump N lost episodes → format as text → LLM → ranked failure hypotheses → convert the top 2–3 into features (feeds the cross-features work) or reward terms.
**Success criterion:** ≥2 of the top-5 identified failure modes, once addressed, each measurably reduce that failure's frequency on a held-out eval set.
**Risk:** the LLM will produce fluent, Pokémon-sounding rationalizations. Verify every claim against replay data before acting.

### #2 — Potential-based reward shaping, LLM-drafted as auditable code
Eureka/Text2Reward methodology, **constrained to potential-based form** `F = γΦ(s') − Φ(s)` so the optimal policy is provably unchanged. Let the LLM draft `Φ` (HP differential, status advantage, expected-damage margin) as Python you review and unit-test.
**Success criterion:** reaches the control's win rate in ≥30% fewer environment steps, with no lower final plateau.
**Note:** the reward-shaping fork is independently live — Wang used sparse ±1 only at 150M; ps-ppo used ±0.1 symmetric faint shaping at 250M. Two strong systems, opposite choices. Any shaping arm should be pre-registered on its own merits, not adopted because an LLM drafted it.

### #3 — Frozen embeddings of move/species descriptions *(deferred)*
Revisit **only after** an attention trunk exists, and scope it as *semantic residue* — the Gen 1 quirks nobody enumerated — not as a composition fix. If run: PCA to 32–64 dims, concatenate into slot-aligned positions, and include an **equal-width random-vector control**. That control is non-negotiable; it separates "the semantics helped" from "more input width helped," and it is the single most important methodological point in this report.

### #4 — Periodic exploration adjustment *(conditional)*
LLM-Explorer pattern, off the critical path. Only if the cross-features and architecture arms show the plateau is exploratory rather than representational. Current evidence points the other way: the agent sits at ~0.443 while a BC clone of the heuristic sits at ~0.453, which reads as *the agent has learned the heuristic and stalled* — a representational ceiling, not an exploration failure.

**Not recommended in any form for the training loop:** action priors, planners, shields, world models.

---

## 5. Evidence quality

- **Strongest (peer-reviewed, ablated, code released):** Eureka, Text2Reward, ELLM, EMMA, ATLA, SayCan, Yan et al., LESR. In-domain: Metamon (RLC 2025), PokéChamp (ICML 2025).
- **Confounded bundles:** Voyager mixes curriculum + skill library + self-verification. ps-ppo's >1900 Elo changed architecture, BC pretraining, faint shaping, distributional value, JEPA, temporal context and 250M steps simultaneously — "attention internalizes the game tree" is an attribution, not a measurement, and there are no ablations.
- **Preprints, verify before citing:** LLM-Explorer, LAMARL, Cache-Efficient Posterior Sampling, LaGO (arXiv:2606.24669 — future-dated index), RWML.
- **Weak / anecdote:** the Zhang/Parashar/Saha Pokémon reward-shaping project.
- **The honest caveat:** the specific thing originally recommended — frozen LLM embeddings as fixed RL input features in Pokémon, cleanly ablated — has never been published. The nearest evidence uses frozen embeddings *with attention*, not bare concatenation into a flat MLP. Expected effect size is genuinely uncertain, which is why it moved from #1 to deferred.

---

## References

Yan et al. arXiv:2410.07927 · LLM-Explorer arXiv:2505.15293 · ELLM arXiv:2302.06692 · arXiv:2510.08779 · Eureka arXiv:2310.12931 · Text2Reward arXiv:2309.11489 · LESR arXiv:2407.13237 · EMMA arXiv:2101.07393 · ATLA arXiv:2206.13074 · LaGO arXiv:2606.24669 *(unverified)* · SayCan arXiv:2204.01691 · Alshiekh arXiv:1708.08611 · Probabilistic Logic Shields arXiv:2303.03226 · Voyager arXiv:2305.16291 · PokéLLMon arXiv:2402.01118 · PokéChamp arXiv:2503.04094 · Metamon arXiv:2504.04395 · VGC-Bench arXiv:2506.10326 · Wang thesis dspace.mit.edu/handle/1721.1/153888 · LAMARL arXiv:2506.01538 · CurricuLLM arXiv:2409.18382 · Survey arXiv:2404.00282 · RL/LLM Taxonomy arXiv:2402.01874 · NLE arXiv:2006.13760 · Werewolf arXiv:2310.18940
