<!-- PROVENANCE: Claude-web deep-research output, received 2026-08-10 (maintainer-
supplied). UNVERIFIED: citations and quotes have NOT been independently checked
against sources by this repo — treat as leads and search coverage, not evidence.
The prior-art NOT-REFUTED verdicts are recorded in SESSION_LOGS 2026-08-10 with
their scope; prior_work/README.md remains the verified index. -->

# State-of-the-Art RL Techniques for a Pure Self-Play Gen 1 Pokémon Agent — Technical Assessment & Adversarial Prior-Art Verification

## TL;DR
- **Both novelty claims survive adversarial search.** No Pokémon RL work found (Metamon, VGC-Bench, Wang 2024, Huang & Lee 2019, PokéChamp, PokéLLMon, or any PokéAgent Challenge entrant) uses an **asymmetric/privileged critic**; and no **pure from-scratch self-play** agent has been demonstrated for **Gen 1 Showdown** — every strong Gen 1 agent is human-replay-bootstrapped. Residual uncertainty is "not published/open-sourced," not "provably never done."
- **The scale-plateau is the real problem, and the highest-value levers are update-time-only.** In priority order for value-per-hour: (1) a **privileged/history-state critic** (your queued item — theoretically strongest, and genuinely novel here); (2) **plasticity diagnostics + regenerative regularization**, the one plasticity family shown to help in *on-policy* PPO; (3) an **auxiliary opponent-team prediction head**; (4) rollout/batch scaling; (5) λ tuning. All compatible with on-policy PPO, masked `Discrete(10)`, and CPU inference.
- **Several fashionable techniques are near-no-ops or non-transferable here** and should be deprioritized: symlog/two-hot value transforms (your returns are already bounded ±1), most off-policy plasticity resets, distributional critics, RND/ICM intrinsic motivation, and novel optimizers (Muon/SOAP), which have no replicated control-RL evidence.

---

## Summary Table — Techniques Ranked by Expected Value-per-Implementation-Hour (this project)

| # | Technique | Cost location | Encoder re-baseline? | Impl. difficulty | Evidence strength | Purity-compatible? | Expected effect |
|---|-----------|---------------|----------------------|------------------|-------------------|--------------------|-----------------|
| 1 | **Plateau diagnostics (Stage 0)** | Offline/update | No | Low | Peer-reviewed (on-policy) | Yes | Prerequisite; redirects all other work |
| 2 | **Privileged history-state critic V(h,s)** | Update-time only | No (critic-only) | Medium | Peer-reviewed + theory (not in Pokémon) | Yes (self-play GT) | Medium–large |
| 3 | **Rollout/batch increase (→100–300 eps/update)** | Collection-time | No | Low | Peer-reviewed + theory | Yes | Medium |
| 4 | **Regenerative (L2-toward-init) regularizer** | Update-time only | No | Low | Peer-reviewed on-policy (ProcGen) | Yes | Small–medium |
| 5 | **LR annealing** | Update-time only | No | Low | 1 controlled ablation (Wang, Gen 4) | Yes | Medium (per Wang) |
| 6 | **GAE λ sweep {0.95,0.98,1.0}** | Update-time only | No | Low | Analogy + theory | Yes | Small |
| 7 | **KL early-stopping / value-clip on-off** | Update-time only | No | Low | Peer-reviewed (mixed) | Yes | Small |
| 8 | **PFSP win-rate-prioritized opponent sampling** | Update-time only | No | Low–med | Peer-reviewed (AlphaStar, GPU-scale) | Yes | Small–medium |
| 9 | **Auxiliary opponent-team prediction head** | Update-time (drop head at inference) | Maybe (if reshapes trunk) | Medium | Peer-reviewed (competitive games) | Yes (self-play GT) | Small–medium |
| 10 | **SimBa components (RSNorm+residual+post-LN)** | Cheap at inference | **Yes** (RSNorm) | Medium | Peer-reviewed w/ ablations (control) | Yes | Unknown; possibly breaks scale-NULL |
| 11 | **Entropy-coef scheduling** | Update-time only | No | Low | Moderate | Yes | Small (watch exploitability) |
| 12 | **R-NaD-style dynamics regularizer** | Update-time | No | High | Peer-reviewed (Science, DeepNash) | Yes | Potentially large; big change |
| — | Symlog/two-hot/return-norm/PopArt | Update-time | Some | Low | Peer-reviewed **against** here | Yes | ~Zero (bounded returns) |
| — | Distributional/C51 critic in PPO | Update-time | No | Medium | Thin in PPO | Yes | ~Zero–small |
| — | ReDo / hard resets / primacy-bias resets | Update-time | No | Medium | Peer-reviewed **against** on-policy | Yes | Negative risk |
| — | RND/ICM intrinsic motivation | Inference + update | No | Medium | Non-transfer (dense signal already) | Yes | ~Zero |
| — | Muon/SOAP/Shampoo/PSGD-Kron | Update-time | No | Medium | No control-RL replication | Yes | Unknown/negative risk |
| — | Attention entity trunk | **Inference (34.6×)** | Yes | High | — | Yes | Rejected on throughput |

---

## Part 1 — Adversarial Prior-Art Verification

### What was searched
arXiv; ICML/NeurIPS/ICLR/AAMAS/IEEE CoG/RLC proceedings; GitHub (metagrok, ps-ppo, VGC-Bench, PokeChamp, metamon); Smogon forums; the NeurIPS 2025 PokéAgent Challenge paper (arXiv 2603.15563) including its full participant-methodology appendix; Hugging Face model cards; and the Metamon/VGC-Bench/Wang-thesis/Huang-&-Lee primary papers. Specifically examined: Metamon, VGC-Bench, PokéChamp, PokéLLMon, Jett Wang's MIT thesis, Huang & Lee 2019, metagrok, Nebraskinator/ps-ppo, and the PokéAgent Gen 1 OU champion and finalist writeups.

### Claim A — "No asymmetric/privileged critic has been used in any Pokémon RL work." → **NOT REFUTED.**
No Pokémon RL system uses a value function conditioned on the opponent's hidden information while the actor sees only legal observations. What each actually uses:
- **Metamon** (built on AMAGO): a **symmetric, shared-trunk actor-critic** on reconstructed *first-person* observations — "a single Transformer trajectory encoder … used as the inputs to small feed-forward actor and critic networks," "one forward pass of one Transformer model with two output heads." Hidden information is *inferred into the observation*, never given privileged to a critic.
- **VGC-Bench**: an actor-critic "**without parameter sharing, though they share the same network architecture**," with both nets embedding all 12 Pokémon (6 ego + 6 opponent) via the same Transformer encoder — a symmetric input, not a privileged critic.
- **Huang & Lee 2019** and **Wang 2024**: standard symmetric PPO actor-critics; no opponent-hidden-info value function.

The entire asymmetric/privileged-critic literature (Pinto et al. 2018; Baisero & Amato 2022; Lyu et al. 2023; Cai et al. NeurIPS 2024; the 2025 "informed" variant) is robotics/sim-to-real/theory — **none in Pokémon.** A privileged critic conditioned on the opponent's hidden team appears **genuinely undone** in this domain.

### Claim B — "No pure from-scratch self-play RL agent has been demonstrated for Gen 1 Showdown." → **NOT REFUTED.**
- **Huang & Lee (2019)** did pure from-scratch self-play PPO (no tree search, no human data) — but achieved "**1677 Glicko-1 and 72% GXE on the Gen7RandomBattle** Pokémon Showdown ladder" (Metamon, arXiv 2504.04395, App. A.2). **Gen 7, not Gen 1.**
- **Wang (2024)** "augments PPO with **MCTS at test-time** and achieve a 1756 Glicko-1 and 79.5% GXE on the Gen4RandomBattle ladder," [arxiv](https://arxiv.org/pdf/2504.04395) peaking at rank 8 (1693 Elo) on the official gen4randombattles ladder (Wang MEng thesis). Test-time search **disqualifies** it, and it is **Gen 4**.
- **Metamon** and both PokéAgent **Gen 1 finalists** bootstrap from **human replays** (see below) — explicitly not from-scratch.
- **VGC-Bench** includes a from-scratch self-play (SP) agent, but for VGC **doubles** (Gen 9-era), and its strongest results come from BC-initialized variants.
- **DeepNash** (Stratego) is from-scratch self-play but not Pokémon (correctly out of scope).

**No Gen 1 pure-from-scratch self-play result is documented in the accessible literature.**

### Calibration — strongest documented Gen 1 agent, and adjacent-generation methods
The **Metamon Gen1OU-specialist family** is the strongest documented Gen 1 line:
- **SynRL-V2** "settles at a **Gen1OU GXE of 79.9% (Glicko-1 1761 ± 35)** after more than 100 battles" (Metamon paper, footnote 4). It is the basis of most PokéAgent qualifying submissions.
- Later Metamon baselines: **Kadabra3 ≈80% GXE**, **Kakuna ≈82% GXE** (Gen1OU); **TaurosEnsemble** has held **#1 on the human Gen1OU ladder**. [GitHub](https://github.com/UT-Austin-RPL/metamon)
- The **PokéAgent Gen 1 OU champion "PA-Agent"** reached a "GXE in Gen 1 OU qualifying [of] **80.35%**," built on Metamon offline RL, "**bootstrapping from human replays … then refining via 6 rounds of inter-model battle data, gradually reducing human data proportion from 100% to 10%**." The **Gen 1 finalist "4thLesson"** fine-tunes Metamon's pretrained SyntheticRL-V2, [arXiv](https://arxiv.org/html/2603.15563v1) swapping AdamW→**Kron (PSGD-Kron)** and Leaky ReLU→**AID**, adding ~1.1–1.2M self-play replays generated against 19 baseline models. PA-Agent beat 4thLesson 50–28 in the final.

**Every strong Gen 1 agent uses imitation + offline RL, never from-scratch self-play.** Adjacent generations: **Gen 4** best is PPO+test-time-MCTS (Wang); **Gen 9** strongest is **Foul Play** (root-parallelized MCTS with Decoupled-UCT, >80% GXE Gen9OU, PokéAgent Gen 9 champion).

**Bottom line:** your intended contribution — a *pure from-scratch self-play* Gen 1 agent with an *asymmetric privileged critic* — is doubly novel against the documented record. State it as "no documented instance found," not "proven first," because private/unpublished code cannot be ruled out.

---

## Part 2 — Techniques Assessed Against the Repo State

The binding constraints — on-policy PPO, sparse terminal ±1 at γ=1.0, ~25–35-decision episodes, CPU-inference-bound, one-lever pre-registration, frozen encoder mid-chapter — eliminate most fashionable techniques and privilege a small set of **update-time-only** interventions.

### 1. Asymmetric / privileged critics and CTDE — *highest expected value, and novel here*
**What it is.** Condition the critic on privileged state (here: the opponent's true hidden team/sets, free in self-play) while the actor sees only legal observations. Introduced as Asymmetric Actor-Critic for image-based robotics (Pinto et al., RSS 2018). [arxiv](https://arxiv.org/pdf/2603.04531)

**The subtlety that matters for your GAE use.** Baisero & Amato (AAMAS 2022, "Unbiased Asymmetric RL under Partial Observability," arXiv 2105.11674) prove a pure state-value critic **V(s)** is *biased* for a history-dependent policy — the state alone is inadequate and V^π(s) is not well-defined for history policies under partial observability. Their fix: a **history-state value V(h,s)** feeding the critic *both* the actor's observation/history *and* the privileged signal, which "resolves all the theoretical and practical issues with state values" [IFAAMAS](https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p2917.pdf) and preserves the policy-gradient theorem with **no bias**. This is decisive for you because **you bootstrap with GAE** — a biased V propagates into advantage targets, not just into a baseline. Lyu et al. (JAIR 2023, arXiv 2408.14597) confirm history-state values are unbiased estimators of history values. [arxiv](https://arxiv.org/pdf/2408.14597) The 2025 "informed asymmetric actor-critic" (arXiv 2509.26000, ICML 2026 poster) generalizes to arbitrary privileged signals and shows carefully selected *partial* privilege can match full-state critics.

**How much privilege, and parameter sharing.** Give the critic **the actor's observation PLUS the privilege (V(h,s)), never privilege-only.** Start compact (opponent species identities + move sets) per the "informed" criterion. On sharing: your value head is **already a separate [384,384] stack with no shared trunk** — ideal. Feed privilege only to that separate critic; sharing a trunk would leak hidden info into the actor, which is exactly what invalidates the design.

**Cautionary evidence.** "Guided Actor-Critic" (OpenReview) found asymmetric SAC "does not outperform standard SAC as significantly … in memory-based settings," because a privileged *value* function gives only indirect supervision via the RL objective. So the effect is real but not guaranteed large; it is largest when hidden info strongly determines returns — true in Gen 1, where the opponent's hidden team is the dominant outcome-variance source at turn 1 (no team preview).

**Feasibility.** Critic is discarded at inference → **zero inference cost** (perfect for CPU). Compatible with on-policy PPO, masked `Discrete(10)`, self-play, sparse terminal ±1. Touches the **separate critic only**, not the frozen 828-dim actor encoder; the ID/embedding machinery already exists. **Effect: medium–large on value-fit and sample efficiency; medium confidence.** Grade: peer-reviewed with theory + ablations, but **never tested in Pokémon or at γ=1.0 terminal reward** — treat as extrapolation.

### 3. Why scale stops paying — *the central problem; diagnostics are a prerequisite lever*
Your 50M run reading ~0.55 (vs 0.5509 at 12M) is the crux. Distinguish ceilings with concrete diagnostics:
- **Representational vs optimization:** track **value explained variance** and **feature effective rank**. Flat explained variance + low effective rank → capacity/optimization.
- **Plasticity (most likely under self-play drift):** Juliani & Ash (NeurIPS 2024, arXiv 2405.19153) — the single most relevant paper — show plasticity loss is **pervasive under domain shift in on-policy PPO** and **correlates with growing parameter norms**. Self-play drift *is* continual domain shift. Measure **dormant-neuron fraction** and **weight-norm trajectory**; climbing norms + flat win-rate ⇒ plasticity ceiling.
- **Self-play equilibrium / mixed-strategy:** track **policy-entropy trajectory** and an **exploitability proxy** (win-rate of a freshly-trained best-response vs your frozen final checkpoint). Near a cyclic equilibrium, more steps cannot help.
- **Critical batch size:** McCandlish et al. (2018, arXiv 1812.06162) — if the gradient noise scale exceeds your 1024-step batch, you are noise-dominated and more steps at fixed batch yield diminishing returns (see §4).

**This is a measurement exercise first.** Pre-register these five metrics on the *existing* 50M run before spending more compute. Offline analysis, zero inference cost, no encoder change.

### 13. Plasticity loss — *does it transfer? Partly, and direction matters*
Most plasticity evidence is high-replay-ratio off-policy. **Juliani & Ash (2024) studied on-policy PPO directly** and found: plasticity loss is real under non-stationarity; "a number of methods developed to resolve it in other settings **fail, sometimes even performing worse than applying no intervention at all**"; but "a class of **'regenerative' methods are able to consistently mitigate plasticity loss … including in gridworld tasks and more challenging environments like Montezuma's Revenge and ProcGen**." The survey (arXiv 2411.04832) adds that regenerative regularization "avoids forgetting and works well in on-policy settings."

**Actionable:** **Do NOT** import ReDo / dormant-neuron hard resets / primacy-bias resets (validated off-policy; flagged unreliable-to-harmful on-policy). **Do try a regenerative (L2-toward-init) regularizer** — a clean, one-line, update-time-only, pre-registerable lever that directly targets the parameter-norm-growth mechanism they identified. **Effect: small–medium; medium confidence** (peer-reviewed, on-policy, ablated — but on ProcGen/Montezuma, not self-play).

### 2. Auxiliary losses — *opponent-team prediction is the right one; most others aren't*
UNREAL reward/pixel-control, SPR, BYOL-Explore are dense-reward/pixel/off-policy results that don't obviously transfer. But **agent/opponent modeling as an auxiliary task** has direct support: "Agent Modeling as Auxiliary Task for Deep RL" (arXiv 1907.09597) shows predicting opponent policy helps in cooperative *and* competitive settings; DouZero+ (arXiv 2204.02558) adds a hidden-hand-card prediction head; ROA-Star adds opponent modeling + a scouting reward to AlphaStar. **Your queued opponent-team prediction head is well-motivated and label-free in self-play.** Nuance: the prediction *head* is inference-free if dropped, but its gradient flows into the shared trunk — an **actor-side change** that could interact with your frozen-encoder discipline (if it reshapes the trunk, it needs a re-baseline). Also note the head and a privileged critic (§1) are complementary but partially redundant (the critic *uses* hidden info; the head *learns to infer* it) — pre-register separately. **Effect: small–medium; medium confidence.**

### 4. Rollout/batch sizing and epochs — *you are plausibly under-batched*
Comparable Pokémon systems use ~37,000–40,000 steps/update; you use 1024 (≈30–40 episodes). Under **sparse terminal reward, episodes-per-update is the relevant currency** (one bit per episode), and ~30 episodes/update is a small, high-variance gradient. McCandlish et al. predict near-linear parallelization of progress *below* the critical batch size; MAPPO (Yu et al. 2022, arXiv 2103.01955) shows "a sufficiently large batch-size is required to achieve the best final performance"; Hilton et al. (2022, arXiv 2110.00641) give batch-size-invariance so you can scale while preserving PPO behavior. **Raise rollout size to lift episodes/update from ~30 toward ~100–300, holding epochs at 4.** This is collection-time cost, not inference-per-step cost — fits your throughput profile if parallelized. **Effect: medium; medium-high confidence** you are noise-dominated given sparse terminal reward. Update-time, no encoder change, single knob.

### 5. GAE λ and γ under sparse terminal reward + short episodes
With a single terminal ±1 and **short (~25–35-step) episodes**, γ=1.0 is defensible. **λ is worth a pre-registered sweep**: under pure terminal reward the Monte-Carlo return (λ→1.0) is *unbiased*, and short episodes bound its variance — weakening the usual low-λ argument. The Alpha-Mini minichess study (arXiv 2112.13666) found **λ=1.0 optimal precisely because "episodes are short" [arxiv](https://arxiv.org/pdf/2112.13666) and full rollouts give unbiased advantage**. Two comparable Pokémon systems use λ≈0.75, biasing toward the (initially poor) critic. **Sweep λ ∈ {0.95, 0.98, 1.0}.** If your critic is the bottleneck (§3), higher λ should help. **Effect: small; medium confidence.** Update-time, single knob.

### 6. Learning-rate schedules
Wang's Gen 4 thesis reports the only controlled LR-annealing ablation in this literature: **constant ~0.55 vs annealed ~0.80 validation win rate**, schedule `10^-4.23/(8x+1)^1.5` — a large effect. General on-policy practice (Memory Gym / recurrent PPO) linearly decays LR and entropy. **Your constant 2.5e-4 is a recorded deviation** and a cheap, high-value lever. **Effect: medium (per Wang); medium confidence** (single thesis, Gen 4, but a controlled ablation). Caveat: on a 50M run, decaying LR could help escape *or* prematurely freeze the plateau — test on fixed budget.

### 7. Self-play methodology — *your pool is reasonable; equilibrium vs league is the deeper question*
AlphaStar's league (PFSP win-rate-weighted opponents + main/league exploiters) targets **non-transitivity and cycling** — the exact risk in simultaneous-move Gen 1. Your **20-checkpoint pool at 80/20** is a sensible middle ground and better than pure mirror self-play for avoiding the "believes it's playing itself" overfit. But note **both published pure-self-play successes (Huang & Lee; DeepNash) used no pool** — pure mirror self-play with a principled dynamics fix. DeepNash's **R-NaD (Regularised Nash Dynamics)** (Perolat et al., Science 2022, arXiv 2206.15378) converges to an approximate Nash *instead of cycling around it*, model-free, no search [arXiv](https://arxiv.org/abs/2206.15378) — the single most relevant self-play result for a from-scratch imperfect-information zero-sum game. **Two levers:** (a) **PFSP win-rate-prioritized sampling** (your queued item — replaces uniform pool draw with win-rate weighting; cheap, update-time); (b) longer-term, an **R-NaD-style dynamics/reward regularizer** if your exploitability proxy shows the plateau is an equilibrium artifact. **Effect: PFSP small–medium; R-NaD potentially large but a major change.** Grade: Nature/Science, GPU-scale, different games.

### 8. Exploration and mixed strategies
Nash policies in simultaneous-move games are generally **mixed**, so **entropy regularization doubles as exploitability control**. Your 0.01 coef is standard; **entropy scheduling** (queued) is worth testing, but decaying entropy too fast can *increase* exploitability — measure the exploitability proxy (§3) alongside. **Intrinsic motivation (RND/ICM) is not worth it:** it targets sparse-reward *exploration* in single-agent long-horizon tasks; your trajectory-level signal is dense (every 25–35 steps) and self-play already provides an automatic curriculum. **Deprioritize RND/ICM** (high confidence).

### 9. Architecture that doesn't cost inference — *SimBa components are the best low-risk bet*
**SimBa (ICLR 2025, arXiv 2410.09754)** is the most relevant architecture result: "(i) an observation normalization layer that standardizes inputs with running statistics, (ii) a residual feedforward block to provide a linear pathway from the input to output, and (iii) a layer normalization to control feature magnitudes," [OpenReview](https://openreview.net/forum?id=jXLiDKsuDo) and it improves "various deep RL algorithms — **including off-policy, on-policy, and unsupervised methods**." These are cheap at inference and could plausibly break your scale-NULL by letting the entity trunk use more parameters productively. **But RSNorm changes input statistics** → interacts with your frozen hand-normalized encoder and needs a **re-baseline**; residual+post-LN inside the MLP trunk are actor-side changes that also invalidate comparators. So batch these into your next re-baseline, not drop-in. **DeepSets vs attention:** you made the right CPU call (attention = 34.6× the MLP step). Max-pool DeepSets is sufficient when interaction structure is low-order; attention is genuinely required mainly when pairwise entity interactions dominate — which in Gen 1 (no items/abilities, simple type interactions) they largely don't. **Keep DeepSets.** Grade: peer-reviewed with broad ablations incl. on-policy, but continuous-control benchmarks, not discrete self-play.

### 10. Normalization — *mostly no-ops for you; say so explicitly*
With **bounded ±1 returns at γ=1.0**, most normalization tricks are near-no-ops. Definitive evidence: "Reward Scale Robustness for PPO via DreamerV3 Tricks" (NeurIPS 2023, PPO-v3, arXiv 2310.17805) — symlog, two-hot, PopArt-style value normalization, and return normalization **help only when returns are NOT already normalized/clipped, and slightly HARM when they are.** [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2023/file/04f61ec02d1b3a025a59d978269ce437-Paper-Conference.pdf) Your returns are already bounded ⇒ **symlog, two-hot, return normalization, PopArt are predicted near-no-ops or mild negatives.** The one that can still matter is **advantage normalization** — but the Memory Gym finding that the crucial fix in one env was *not* normalizing advantages means treat batch-vs-minibatch advantage normalization as a small pre-registerable knob, not a guaranteed win. Observation normalization is subsumed by SimBa's RSNorm (§9). **Effect: near-zero; high confidence. Do not spend hours here.**

### 11. Distributional critics
Categorical/C51 or two-hot value heads in PPO: PPO-v3 already covers two-hot (near-no-op with bounded returns). The theoretical appeal (value-fit stability under self-play non-stationarity) is real but unproven in on-policy PPO with bounded rewards. **Low priority; the privileged critic (§1) attacks value-fit quality more directly.** Grade: thin in PPO specifically.

### 12. PPO implementation details
The "37 Implementation Details of PPO" (Huang et al., ICLR Blog) and "Implementation Matters" (Engstrom et al.) establish that code-level details often matter more than the algorithm. Testable here: **(a) value clipping** (evidence genuinely mixed — cheap on/off test given your separate unmasked value head); **(b) KL-based early stopping vs fixed 4 epochs** (can prevent destructive updates under self-play non-stationarity — clean update-time lever). **PPG** (phasic policy gradient) suits your separate value head but is a larger change. **Effect: small each; high confidence they're safe to test.** Update-time, no encoder change.

### 14. Optimizers beyond Adam — *no replicated control-RL evidence; skip*
**Muon, SOAP, Shampoo, PSGD-Kron** have strong supervised/LLM-pretraining evidence but **no replicated RL-control evidence.** Muon's authors flagged RL transfer as open; NeMo-RL reports only "minor improvements" post-training; [arXiv](https://arxiv.org/html/2607.16169v1) Fan et al. (2026, arXiv 2605.19282) document **spectral failures of Muon in RLVR** (low-SNR gradients destabilize whitening). [arXiv](https://arxiv.org/html/2605.19282) The **PokéAgent Gen 1 finalist "4thLesson" used PSGD-Kron** on the Metamon framework — the only Pokémon-adjacent optimizer swap on record — but bundled with an activation change and offline fine-tuning, isolating nothing. **Stay on Adam.** An optimizer swap is high-variance, poorly supported, and cuts against your "unverified claims weigh heavily" prior. Grade: no control-RL replication.

### 15. 2024–2026 findings a practitioner shouldn't ignore
- **SimBa/SimbaV2** (§9): best "scale-the-network" recipe; SimbaV2 adds hyperspherical normalization.
- **Juliani & Ash on-policy plasticity** (§3, §13): the direction-of-effect reversal (off-policy fixes backfire on-policy) is the single most important negative result for you.
- **PPO-v3 / DreamerV3-tricks-on-PPO** (§10): "normalization is a no-op when returns are bounded" saves wasted experiments.
- **Optimizer replication caution** (§14): don't cargo-cult Muon from LLM-land.

---

## Techniques That Do Not Transfer, Are Already Done, or Are Poorly Supported
- **Already done well — don't re-propose:** the entity/DeepSets trunk (credited +0.151); pointer-style shared scorer; separate unmasked value head; belief-state P(move) prior in the observation; 20-checkpoint self-play pool; masked `Discrete(10)`; single-torch-thread CPU loop; rejecting the attention trunk (34.6× step).
- **Non-transferable to your regime:** RND/ICM intrinsic motivation (dense trajectory signal already; single-agent long-horizon result); off-policy/high-replay plasticity resets (ReDo, primacy-bias resets — Juliani & Ash show they can underperform *no intervention* on-policy); recurrence/large attention (CPU inference-bound); off-policy/high-replay-ratio algorithms generally.
- **Near-no-ops with bounded ±1 returns (γ=1.0):** symlog, two-hot value transform, return normalization, PopArt, distributional/C51 critics — PPO-v3 shows these help only with *unnormalized* returns and can *harm* when returns are already bounded.
- **Poorly supported / cargo-cult risk:** Muon/SOAP/Shampoo/PSGD-Kron in RL (no replicated control-RL evidence; documented RLVR failures); the **Nebraskinator/ps-ppo** personal-repo claim of ">85% vs SimpleHeuristics, >1900 Elo, highest documented pure-neural policy" — unverified, no peer review, no ablation, **and preceded by a behavior-cloning/imitation phase** (so not pure-from-scratch and not a valid target).

---

## Recommendations (staged, one lever per pre-registered experiment)

**Stage 0 — Diagnose the plateau first (no new training).** On the existing 50M run, log/plot: value explained-variance, policy-entropy trajectory, weight-norm trajectory, dormant-neuron fraction, effective rank, and an exploitability proxy (best-response vs the frozen final checkpoint). *Decision rule:* rising weight norm + flat win-rate → plasticity ceiling (→Stage 2); flat explained variance + low effective rank → representational/optimization ceiling (→Stage 1/architecture); best-response wins easily + entropy collapsed → exploitability/equilibrium ceiling (→Stage 3).

**Stage 1 — Cheapest update-time levers, in order.** (1) **Privileged history-state critic V(h,s)** feeding the *separate* value head the opponent's hidden team (highest expected value, novel, zero inference cost); (2) **rollout/batch increase** to ~100–300 episodes/update; (3) **GAE λ sweep {0.95,0.98,1.0}**; (4) **LR annealing** per Wang's schedule shape; (5) **KL early-stopping** and **value-clip on/off**. Each individually pre-registerable with its own credit line.

**Stage 2 — If plasticity ceiling.** Add a **regenerative (L2-toward-init) regularizer** — the one plasticity family Juliani & Ash validate on-policy. Explicitly do NOT add ReDo/hard resets.

**Stage 3 — If equilibrium/exploitability ceiling.** Add **PFSP win-rate-prioritized opponent sampling** first (cheap); if cycling persists, prototype an **R-NaD-style dynamics regularizer** (larger change; the principled fix for cycling in imperfect-information zero-sum self-play).

**Stage 4 — Batched into the next re-baseline (encoder-touching).** **SimBa components** (RSNorm + residual + post-LN); **auxiliary opponent-team prediction head**; richer belief/history features (the audited encoder gaps: sleep/toxic one-hots, last-turn events, Substitute HP, PP binning). Land these together as a new baseline, not piecemeal.

**Benchmarks that change the plan:** if Stage-0 shows weight-norm growth, jump Stage 2 ahead of Stage 1. If the batch increase (1.2) moves the SH readout past ~0.57 with z>3, prioritize further batch scaling over architecture. If the privileged critic improves value explained-variance but not win-rate, the bottleneck is the actor/exploration, not the critic — pivot to Stage 3.

---

## Caveats
- **Evidence grading is uneven.** Privileged-critic theory (Baisero & Amato; Lyu et al.) is peer-reviewed with proofs but **never tested in Pokémon or at γ=1.0 terminal reward** — effect sizes are extrapolation. SimBa and Juliani-Ash are peer-reviewed with ablations but on continuous control / ProcGen, not self-play games. Wang's LR ablation is a single MEng thesis (Gen 4). PPO-v3 normalization results are peer-reviewed and directly on-point.
- **Personal-repo claims are explicitly down-weighted** — see the Nebraskinator/ps-ppo entry above.
- **Part 1 residual uncertainty is "not published," not "never done."** Private codebases, unpublished competition entries, and deleted repos cannot be ruled out. The claims are robustly unrefuted across arXiv, ICML/NeurIPS/ICLR/AAMAS/IEEE CoG/RLC, GitHub, Smogon, and the PokéAgent Challenge writeups — state them as "no documented instance found," not "proven first."
- **PokéAgent Challenge figures are self-reported** by participant teams and reproduced "largely verbatim" in the retrospective (arXiv 2603.15563); GXE numbers carry the authors' caveats (multi-account rating deflation; Gen 1 called a Metamon performance "outlier").
- **The purity constraint holds against all Part-2 recommendations:** none require imitation, human data, teacher/distilled data, scripted training opponents, or inference-time search. The privileged critic uses only self-play ground truth (weights remain a function of random init + self-play + environment). Scripted/distilled agents remain evaluation anchors only.

---

## References
- Pinto et al. (2018), "Asymmetric Actor Critic for Image-Based Robot Learning," RSS. https://roboticsproceedings.org/rss14/p08.html
- Baisero & Amato (2022), "Unbiased Asymmetric RL under Partial Observability," AAMAS. https://arxiv.org/abs/2105.11674
- Lyu, Baisero, Xiao, Daley, Amato (2023), "On Centralized Critics in Multi-Agent RL," JAIR. https://arxiv.org/pdf/2408.14597
- "Informed Asymmetric Actor-Critic," ICML 2026 / arXiv 2509.26000. https://arxiv.org/pdf/2509.26000
- Cai et al. (2024), "Provable Partially Observable RL with Privileged Information," NeurIPS.
- Juliani & Ash (2024), "A Study of Plasticity Loss in On-Policy Deep RL," NeurIPS. https://arxiv.org/abs/2405.19153
- "Plasticity Loss in Deep RL: A Survey" (2024). https://arxiv.org/abs/2411.04832
- Lee et al. (2025), "SimBa: Simplicity Bias for Scaling Up Parameters in Deep RL," ICLR. https://arxiv.org/abs/2410.09754
- "Reward Scale Robustness for PPO via DreamerV3 Tricks" (2023), NeurIPS. https://arxiv.org/pdf/2310.17805
- McCandlish et al. (2018), "An Empirical Model of Large-Batch Training." https://arxiv.org/pdf/1812.06162
- Hilton et al. (2022), "Batch size-invariance for policy optimization," NeurIPS. https://arxiv.org/pdf/2110.00641
- Yu et al. (2022), "The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games." https://arxiv.org/pdf/2103.01955
- Huang, Dossa, et al. (2022), "The 37 Implementation Details of PPO," ICLR Blog Track.
- Engstrom et al. (2020), "Implementation Matters in Deep Policy Gradients."
- Vinyals et al. (2019), "Grandmaster level in StarCraft II," Nature (AlphaStar/PFSP/league). https://storage.googleapis.com/deepmind-media/research/alphastar/AlphaStar_unformatted.pdf
- Perolat et al. (2022), "Mastering the Game of Stratego with Model-Free Multiagent RL" (DeepNash/R-NaD), Science. https://arxiv.org/abs/2206.15378
- "Agent Modeling as Auxiliary Task for Deep RL" (2019). https://arxiv.org/pdf/1907.09597
- "DouZero+: Improving DouDizhu AI by Opponent Modeling" (2022). https://arxiv.org/pdf/2204.02558
- "Alpha-Mini: Minichess Agent with Deep RL" (2021). https://arxiv.org/pdf/2112.13666
- Grigsby et al. (2025), "Human-Level Competitive Pokémon via Scalable Offline RL with Transformers" (Metamon), RLC. https://arxiv.org/abs/2504.04395
- Angliss et al. (2025), "VGC-Bench," arXiv 2506.10326. https://arxiv.org/abs/2506.10326
- Wang, J. (2024), "Winning at Pokémon Random Battles Using Reinforcement Learning," MIT MEng thesis. https://dspace.mit.edu/bitstream/handle/1721.1/153888/wang-jett-meng-eecs-2024-thesis.pdf
- Huang & Lee (2019), "A Self-Play Policy Optimization Approach to Battling Pokémon," IEEE CoG. https://ieee-cog.org/2019/papers/paper_175.pdf
- Karten et al. (2025), "PokéChamp: an Expert-level Minimax Language Agent," ICML. https://arxiv.org/abs/2503.04094
- "The PokeAgent Challenge: Competitive and Long-Context Learning at Scale," arXiv 2603.15563. https://arxiv.org/html/2603.15563v1
- Fan et al. (2026), "Rethinking Muon Beyond Pretraining," arXiv 2605.19282. https://arxiv.org/html/2605.19282