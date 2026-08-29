# Reinforcement Learning in Stochastic, Simultaneous-Move, Imperfect-Information Games: A Methodological Review

## 1. Introduction

The engineering of autonomous agents for highly complex, multi-agent environments requires a precise alignment between the fundamental mathematical properties of the environment and the theoretical guarantees of the chosen reinforcement learning algorithm. The environment under consideration—Pokémon Showdown Generation 1 random battles—represents a unique and uniquely hostile intersection of game-theoretic properties. It is a two-player zero-sum (2p0s) game characterized simultaneously by imperfect information (hidden team compositions, progressive revelation of movesets and items), simultaneous moves (a "double lock-in" mechanism where neither player possesses knowledge of the opponent's current-turn commitment), and exceptionally high stochasticity (accuracy rolls, critical hits, variable damage ranges, and speed ties).

This specific trifecta invalidates the foundational assumptions of algorithms designed for standard benchmark environments. Deterministic, perfect-information environments like Chess and Go rely on the existence of a definitive Markov Decision Process (MDP) and alternating-turn game trees. Games like Poker incorporate high stochasticity (card draws) and imperfect information, but largely execute over sequential, alternating-turn structures where counterfactual reasoning can be cleanly mapped to distinct decision nodes. Environments like Stratego feature imperfect information and simultaneous deployment phases, but the core combat mechanics resolve deterministically. A simultaneous-move, highly stochastic, imperfect-information environment creates an astronomical state distribution where two identical policies can yield wildly divergent outcomes, and where the transition dynamics are entirely dependent on the unobserved, concurrent action of the adversary.

The deployment of Independent Proximal Policy Optimization (IPPO) from a random initialization via pure mirror self-play—constrained to a 50 million environment-step budget on a CPU—presents severe diagnostic challenges. The observed phenomenon, wherein final win rates across independently seeded training runs vary drastically and mask the efficacy of hyperparameter or architectural levers (creating a detection threshold noise floor near a 0.10 win rate variance), is a recognized pathology in multi-agent reinforcement learning.

This report provides an exhaustive literature review and methodological analysis of this phenomenon. It explores the theoretical limits of IPPO in 2p0s simultaneous-move imperfect-information games, establishes a rigorous empirical framework for detecting policy cycling using existing training artifacts, and systematically evaluates alternative game-theoretic algorithms. The alternatives are ranked strictly by their empirical evidence in games matching these specific properties, their reliance on inference-time search, and the engineering reality of porting them to an existing, from-scratch PPO codebase.

## 2. Theoretical Evaluation of Independent PPO in Markov Games

The central inquiry is whether Independent PPO is mathematically sound for a 2p0s simultaneous-move imperfect-information game, or if it is inherently predisposed to cycle between mutually exploitable policies without converging to a Nash Equilibrium. The theoretical literature definitively confirms the latter: unregularized independent policy gradient methods in zero-sum self-play are highly vulnerable to cyclical dynamics, non-transitive limit cycles, and severe gradient variance.

### 2.1 Non-Stationarity and the Absence of Average-Iterate Guarantees

In a single-agent environment, PPO optimizes a surrogate objective function under the assumption that the underlying environment dynamics—the transition probabilities and reward functions—are stationary. PPO is a last-iterate algorithm, meaning its theoretical design assumes the final policy is the optimal policy.

In multi-agent self-play, this assumption collapses entirely. The environment is properly modeled not as an MDP, but as a Markov Game (or Stochastic Game). As the agent's policy updates, the opponent's policy (whether a direct mirror or a historical checkpoint) also updates. This renders the state-transition probabilities highly non-stationary from the perspective of either individual player. Because the environment's transition function depends on the joint action $\mathbf{a} = (a_1, a_2)$, the gradient steps taken by Player 1 are actively undermined by the gradient steps taken by Player 2.

In 2p0s games, the definitive solution concept is the Nash Equilibrium (NE)—a joint policy profile where neither player can improve their expected payoff by unilaterally deviating. In games with imperfect information, the Nash Equilibrium heavily relies on mixed (stochastic) strategies to obfuscate intent and manage hidden information. However, independent best-response dynamics—which policy gradient methods inherently approximate by moving in the direction of steepest expected reward—frequently fail to locate these mixed equilibria. Instead of converging, the learning dynamics in unregularized continuous zero-sum games often result in orbits or "vortices" around the Nash Equilibrium.

This dynamic is particularly aggressive in games featuring intransitive mechanics (e.g., Rock-Paper-Scissors). Pokémon Showdown is fundamentally built upon intransitive type matchups and counter-strategies. When IPPO discovers a highly effective strategy (e.g., a specific sweeping archetype), it over-optimizes for it. The self-play opponent subsequently discovers the exact counter to that strategy, prompting the agent to discard the original strategy entirely to counter the counter. This creates a perpetual cycle. Therefore, the variance observed in final win rates across independently seeded runs is not merely environmental noise; it is a manifestation of the policies terminating at different, arbitrary coordinates along a non-transitive limit cycle. The final models are highly specialized to defeat the specific sequence of self-play opponents they most recently encountered, rendering them brittle, unbalanced, and mutually exploitable.

### 2.2 The Variance of Generalized Advantage Estimation (GAE) in Stochastic Self-Play

Beyond macro-level game-theoretic cycling, IPPO suffers from a severe micro-level algorithmic flaw when applied to highly stochastic, simultaneous-move games: the variance introduced by Generalized Advantage Estimation (GAE).

GAE is designed to balance bias and variance by aggregating multi-step temporal-difference (TD) residuals along sampled trajectories. In deterministic environments, a chosen action reliably leads to a predictable future state, keeping the variance of the GAE calculation manageable. However, recent research identifies GAE as a critical bottleneck in stochastic self-play reinforcement learning.

In a simultaneous-move, highly stochastic environment, the state transition $P(s' \vert{} s, a_1, a_2)$ is subject to immense variance. The future states and rewards are heavily dependent not only on the agent's sampled stochastic action but also on the opponent's sampled stochastic action, compounded by the environment's intrinsic randomness (damage rolls, critical hits). Because equilibrium policies in imperfect-information games are inherently stochastic, GAE inherits massive randomness from the future actions sampled in the multi-step trace.

This multi-step backup becomes overwhelmed by noise. Research indicates that this variance persists and actively destabilizes learning even if the state-value critic network is perfectly accurate. The sampled trajectory is merely one of millions of highly divergent potential paths. Consequently, the advantage estimates driving the PPO actor updates are highly volatile. This high variance degrades the policy update, forces the clipping mechanism to constantly engage under false premises, and severely destabilizes the learning process, directly contributing to the wide dispersion of final win rates across random seeds.

## 3. Empirical Detection of Policy Cycling and Intransitivity

Detecting policy cycling without access to an exact exploitability calculation is a fundamental challenge. Exact exploitability requires computing a perfect Best Response against the agent's policy across the entire game tree. In a game with the state-space size of Pokémon Showdown, this is computationally impossible. However, the failure mode can be definitively diagnosed using the existing training artifacts: the final checkpoints of the independently seeded runs.

### 3.1 Constructing Head-to-Head Payoff Matrices

To determine if the variance in win rates is due to cyclical best-response dynamics rather than uniform convergence to different local optima, an empirical payoff matrix must be constructed via a comprehensive cross-play tournament.

Assuming the existence of $N$ final policies generated from $N$ different random seeds (e.g., $N=10$), a round-robin tournament must be executed where every policy plays every other policy. Given the stated noise threshold of 0.10, achieving statistical significance requires driving the standard error of the win rate strictly below this threshold. The standard error for a binomial proportion is $\sqrt{p(1-p)/m}$, where $p$ is the true win rate and $m$ is the number of matches. To confidently resolve win rate differences of 0.02–0.05, $m$ must be sufficiently large. For instance, at $p=0.5$, reducing the standard error to 0.01 requires $m = 2,500$ matches per pairing.

The resulting $N \times N$ matrix represents the empirical expected value of playing policy $i$ against policy $j$. If IPPO is converging to a stable, robust approximation of a Nash Equilibrium, the win rates in this cross-play matrix should be near 50% across all pairings (accounting for the inherent stochasticity of the randomized teams).

Conversely, if the algorithm is trapped in a limit cycle, the matrix will reveal severe intransitivities. For example, Policy A may defeat Policy B with a 65% win rate, Policy B may defeat Policy C with a 60% win rate, but Policy C defeats Policy A with a 70% win rate. The presence of these stark, cyclical exploitability loops within the cross-play matrix is the definitive empirical signature of unregularized policy gradient cycling.

### 3.2 Advanced Evaluation via Alpha-Rank

To formalize and quantify the severity of the cycling observed in the head-to-head matrix, the literature strongly recommends the application of Alpha-Rank. Alpha-Rank is a principled evolutionary dynamics methodology designed specifically for large-scale multi-agent evaluation where computing exact Nash Equilibria is intractable.

Alpha-Rank operates directly on the empirical $N \times N$ payoff matrix generated in the previous step. It constructs a Markov transition matrix over the pure strategies (the $N$ seeded policies). The algorithm models a population of agents transitioning between these strategies based on their relative fitness (win rates). It computes the stationary distribution of a random walk over this matrix.

If the ranking-intensity parameter $\alpha$ is chosen to be large, Alpha-Rank maps exactly to the dynamical solution concept of Markov-Conley chains (MCCs). Unlike a static Nash Equilibrium, MCCs capture the full dynamical system, identifying fixed points, recurrent sets, and limit cycles.

If the policies have converged to a robust equilibrium, Alpha-Rank will assign the vast majority of the probability mass (the stationary distribution) to a single policy or a tight cluster of highly similar policies (a single sink component). If the policies are cycling, Alpha-Rank will reveal a highly distributed probability mass across multiple policies that form an intransitive loop (a recurrent set). Implementing Alpha-Rank requires only the empirical payoff matrix and can be executed trivially using existing open-source Python libraries such as OpenSpiel, requiring no additional environment interactions or neural network inference.

## 4. Evaluation of Alternative Algorithms

Addressing the theoretical shortcomings of IPPO requires adopting algorithms specifically engineered for equilibrium finding in imperfect-information games. The following alternatives are evaluated and ranked strictly by a composite metric of two critical factors:

- **Empirical Evidence:** Demonstrated success in games featuring the specific combination of simultaneous moves, hidden information, and high chance. The evaluation explicitly distinguishes between games that possess these properties versus games where algorithms are theoretically assumed to transfer (e.g., sequential poker variants or deterministic-combat board games).
- **Architectural Cost and Reality of Porting:** The engineering viability of porting the algorithm to an existing, from-scratch PPO codebase operating via pure self-play, strictly constrained to a single developer and a 50 million step budget on a CPU.

### 4.1 Regularized Policy Gradient Variants (EMAgnet, NashPG, VRPO)

**Ranking: 1 (Highest Evidence, Lowest Architectural Cost)**

Recent breakthroughs in MARL have demonstrated that the architecture of PPO does not need to be abandoned. The theoretical literature establishes that generic policy gradient methods, when augmented with appropriate mathematical regularization and variance reduction, can match or exceed specialized game-theoretic approaches like Counterfactual Regret Minimization or Neural Replicator Dynamics. This category represents the most realistic path forward, requiring only surgical modifications to the existing loss functions and advantage estimators.

#### 4.1.1 EMAgnet (Parameter-Space EMA Regularization)

- **Demonstrated In:** FootsiesGym (Simultaneous moves, imperfect information, high state-space) and Control Biased RPS (Intransitive, large spaces of strictly dominated strategies).
- **Performance vs. Baselines:** Outperformed standard PPO and uniform-regularized PPO (entropy bonuses) by preventing the policy from wasting probability mass on strictly dominated strategies, achieving significantly lower exploitability.
- **Inference Search Required:** No. Model-free execution.
- **Architectural Portability:** Extremely High.

EMAgnet introduces a profound yet computationally trivial modification to PPO. Standard regularization techniques typically force the policy toward a uniform distribution (via an entropy bonus) to ensure exploration and prevent premature convergence. However, in games like Pokémon Showdown with large strategy spaces where most options are strictly suboptimal (e.g., using a stat-lowering move against an immune opponent), the uniform target wastes the regularization budget on irrelevant strategies.

EMAgnet instead regularizes the current policy toward an Exponential Moving Average (EMA) of its own past network weights. Mathematically, the PPO objective is augmented with a Kullback-Leibler (KL) divergence penalty:

$\mathcal{L}_{\text{EMAgnet}}(\theta) = \mathcal{L}_{\text{PPO}}(\theta) + \lambda_{\text{KL}} \mathbb{E}_{z \sim \mathcal{T}}[D_{\text{KL}}(\pi_{\theta_{\text{mag}}}(\cdot \vert{} z) \vert{}  \vert{} \pi_\theta(\cdot \vert{} z))]$

where $\theta_{\text{mag}}$ represents the EMA of the policy parameters. After each standard PPO optimization step, the magnet parameters are softly updated: $\theta_{\text{mag}} \leftarrow (1-\tau)\theta_{\text{mag}} + \tau\theta$.

This adaptive "magnet" trails behind the current policy. As the agent learns to avoid strictly dominated strategies, the EMA magnet gradually stops regularizing toward those mistakes. Conversely, it retains a smoothed memory of viable strategies discovered during self-play cycling, acting as an anchor that prevents catastrophic forgetting and dampens cyclical orbits. Porting this requires merely initializing a duplicate of the policy network, configuring the EMA update rule, and adding a KL penalty to the existing PPO actor loss. It is perfectly suited for a single developer operating under strict computational constraints.

#### 4.1.2 VRPO (Variance-Reduced Policy Optimization / Q-Boosting)

- **Demonstrated In:** Dou Dizhu (Highly stochastic, imperfect information, though mostly sequential) and Heads-Up No-Limit Texas Hold'em.
- **Performance vs. Baselines:** Outperformed state-of-the-art baselines like PerfectDou; heavily stabilized self-play by eliminating advantage variance.
- **Inference Search Required:** No.
- **Architectural Portability:** High.

VRPO directly addresses the GAE variance crisis discussed in Section 2.2. While EMAgnet solves macro-level cycling, VRPO solves the micro-level gradient instability caused by high stochasticity. It introduces "Q-boosting," which replaces the standard GAE multi-step backup with a multi-step Expected SARSA($\lambda$) trace computed from a centralized Q-critic.

Instead of calculating advantages by bootstrapping through single, highly stochastic sampled next-actions, Q-boosting takes the mathematical expectation over the policy's action probabilities at each backup step. By integrating out the action-sampling noise analytically, the variance of the advantage estimator plummets. This allows the PPO clipping objective to function effectively, relying on stable advantage signals rather than noise-induced spikes.

Porting this to an existing codebase requires modifying the PPO critic head. Instead of predicting a single State-Value $V(s)$, the DeepSets encoder must output an Action-Value $Q(s, a)$ for every legal action. The advantage calculation function must then be rewritten to implement the Expected SARSA($\lambda$) trace. The underlying PPO actor architecture, clipping mechanism, and self-play loop remain entirely unchanged. Combining VRPO's advantage estimator with EMAgnet's regularization yields a theoretically optimal setup for this specific game class.

#### 4.1.3 Nash Policy Gradient (NashPG)

- **Demonstrated In:** Dark Hex 3x3, Leduc Poker, Battleship (Simultaneous deployment, hidden information, but deterministic transitions).
- **Performance vs. Baselines:** Achieved comparable or lower exploitability than R-NaD and Neural Fictitious Self-Play on large-scale domains.
- **Inference Search Required:** No.
- **Architectural Portability:** High.

NashPG builds upon the theoretical foundation of Magnetic Mirror Descent (MMD) but operationalizes it natively within a sample-based policy gradient framework. It utilizes an iterative multi-round regularization procedure. The algorithm maintains a "reference policy." During an inner loop, standard PPO updates are executed, but the objective is regularized by the KL divergence between the current policy and the fixed reference policy. Once the inner loop converges (or after a set number of steps), an outer loop updates the reference policy to match the current policy, and the process repeats.

This strictly monotonic refinement mathematically forces last-iterate convergence to a Nash Equilibrium without requiring the global uniqueness assumptions that hamstring standard IPPO. The engineering cost is marginally higher than EMAgnet due to the requirement of orchestrating distinct outer and inner training loops, but the core PPO update remains intact. While highly effective, EMAgnet's continuous parameter-space EMA is arguably simpler to implement and tune than NashPG's discrete inner/outer loop orchestration.

### 4.2 Policy Space Response Oracles (PSRO)

**Ranking: 2 (High Evidence, Moderate-to-High Architectural Cost)**

- **Demonstrated In:** Leduc Poker, Stratego variants, and various OpenSpiel meta-games. (Handles imperfect information natively, though mostly demonstrated in games with lower stochasticity than Pokémon).
- **Performance vs. Baselines:** State-of-the-art for approximating Nash Equilibria in large 2p0s games by generating strategically diverse populations.
- **Inference Search Required:** No.
- **Architectural Portability:** Moderate to High effort, significantly strains compute budget.

PSRO is a meta-algorithm that generalizes the Double Oracle algorithm to deep reinforcement learning. Rather than training a single policy in continuous self-play, PSRO maintains a persistent population of policies. In each epoch, it constructs an empirical meta-game matrix (identical to the diagnostic tool in Section 3) representing the win rates of all policies against each other. It then calculates the exact Nash Equilibrium of this meta-game, resulting in a target probability distribution over the existing population. A new "Best Response" policy is then trained via RL (e.g., using the existing PPO implementation) to defeat this specific distribution of opponents. Once trained, this new policy is added to the population, and the cycle repeats.

PSRO handles simultaneous moves and imperfect information natively because it abstracts the environment away, relying purely on the empirical terminal outcomes of the games to build its meta-matrix. The primary advantage is that the existing PPO algorithm can be utilized as the Best Response oracle with zero modifications to its internal math.

The cost lies entirely in infrastructure and computational overhead. PSRO requires orchestrating an expanding population of distinct neural networks, periodically halting to calculate meta-game equilibria, and launching new PPO training sessions against a frozen, mixed ensemble of opponents. Given a strict 50 million environment-step budget on a CPU, PSRO is highly likely to fail. Each Best Response iteration requires substantial step counts to converge against the meta-distribution. With only 50M steps, PSRO may only complete a handful of epochs, generating a population too small to capture the strategic diversity of Pokémon Showdown.

### 4.3 Regularized Nash Dynamics (R-NaD) / DeepNash

**Ranking: 3 (High Evidence, Extremely High Architectural Cost)**

- **Demonstrated In:** Stratego Classic (Simultaneous deployment phase, hidden piece identities, immense state space $10^{535}$, but strictly deterministic combat mechanics).
- **Performance vs. Baselines:** Achieved human-expert level; convincingly defeated all prior state-of-the-art bots on the Gravon platform.
- **Inference Search Required:** No (Model-free self-play).
- **Architectural Portability:** Complete Rewrite Required.

DeepNash represents a landmark achievement in solving imperfect-information games without reliance on inference-time search algorithms. Its underlying algorithm, R-NaD, actively prevents cycling by fundamentally modifying the dynamical system underpinning the multi-agent learning approach.

R-NaD guarantees convergence to an approximate Nash Equilibrium by utilizing a sophisticated reward transformation process. It modifies the environment's base reward function by injecting a penalty based on the divergence from a regularization policy, interpolating smoothly between iterative regularization steps over time.

Crucially, R-NaD abandons PPO and standard policy gradients entirely. It employs Neural Replicator Dynamics (NeuRD), which applies replicator dynamics—a concept from evolutionary game theory—to the policy update, effectively bypassing the gradient step through the softmax function. Furthermore, to evaluate the Q-function in a multi-agent setting, R-NaD utilizes a heavily customized two-player adaptation of the v-trace estimator, requiring complex off-policy corrections.

While the evidence for R-NaD's efficacy in simultaneous-move, hidden-information games is unimpeachable, the architectural cost of porting it is prohibitive. The existing PPO loss, GAE advantage estimator, and standard advantage-based training loop must be discarded. The implementation of NeuRD, two-player v-trace, and dynamic reward transformations requires writing a fundamentally new algorithmic core. Furthermore, recent benchmarking explicitly demonstrates that properly regularized PPO (e.g., EMAgnet, NashPG) matches or exceeds R-NaD's performance on imperfect-information benchmarks while requiring vastly simpler mechanics.

### 4.4 Neural Fictitious Self-Play (NFSP)

**Ranking: 4 (Moderate Evidence, Incompatible Architectural Cost)**

- **Demonstrated In:** Leduc Hold'em, Limit Texas Hold'em, Mini-RTS (Sequential/Alternating moves, imperfect information, stochastic card draws).
- **Performance vs. Baselines:** Approached Nash Equilibrium where standard RL diverged, though largely superseded by modern methods.
- **Inference Search Required:** No.
- **Architectural Portability:** Complete Rewrite Required.

NFSP approximates the classic game-theoretic algorithm of fictitious play using deep neural networks. It resolves the cycling issue by forcing the agent to maintain two distinct memories and policies: a Best Response policy and an Average Strategy network. The Best Response policy is trained via Deep Q-Networks (DQN) from a standard experience replay buffer. The Average Strategy network is trained via supervised learning (classification) on a massive reservoir buffer containing the historical actions of the Best Response policy. During actual play, the agent mixes between executing the Best Response and the Average Strategy.

While NFSP resolves cycling by ensuring average-iterate convergence, it poses insurmountable integration issues for the specified setup. First, NFSP relies on DQN, an off-policy value-based method. DQN scales exceptionally poorly to environments with large, combinatorial, or simultaneous action spaces compared to continuous policy gradient methods. Second, the requirement to maintain and sample from a massive reservoir buffer of historical states and actions is highly memory intensive. Porting this to a PPO codebase is effectively impossible; it requires abandoning the on-policy actor-critic paradigm entirely in favor of off-policy Q-learning combined with supervised classification.

### 4.5 Deep Counterfactual Regret Minimization (Deep CFR) / DREAM

**Ranking: 5 (Zero Evidence for Simultaneous Moves, Incompatible Architectural Cost)**

- **Demonstrated In:** Poker variants (Strictly sequential, alternating-turn, imperfect information).
- **Performance vs. Baselines:** State-of-the-art for alternating-turn poker games.
- **Inference Search Required:** Frequently relies on resolving/subgame solving at inference, though fully model-free variants (DREAM) exist.
- **Architectural Portability:** Fundamentally Incompatible.

Counterfactual Regret Minimization (CFR) and its deep neural variants (Deep CFR, DREAM) operate by calculating the regret of not taking counterfactual actions across the nodes of a game tree. While theoretically flawless for converging to Nash Equilibria, they are heavily optimized for sequential, alternating-turn games where the game tree can be explicitly traversed and counterfactual states calculated.

In a true simultaneous-move game with extreme stochasticity like Pokémon Showdown, standard CFR breaks down. To apply CFR to simultaneous moves, the simultaneous nodes must be mathematically transformed into sequential nodes with fictitious hidden information (e.g., Player 1 moves, then Player 2 moves without seeing Player 1's move). In an environment with massive action spaces and stochastic transitions, this sequentialization results in an explosive expansion of an already intractable state space.

Furthermore, algorithms like Deep CFR require training separate neural networks for each player and each iteration, alongside massive memory buffers for regret matching. DREAM attempts to make this model-free with advantage baselines, but the fundamental architecture relies on regret matching rather than policy gradients. The architectural chasm between PPO and Deep CFR is absolute; adopting CFR principles would necessitate abandoning the current codebase, the state representation, and the fundamental approach to policy generation.

### 4.6 Summary Matrix of Algorithmic Alternatives

| Algorithm | Handles Simultaneous + Imperfect + Stochastic? | Replaces PPO / Portability Cost? | Requires Inference Search? | Primary Mechanism for Stability |
|---|---|---|---|---|
| EMAgnet | Yes (Tested in highly complex 2p0s) | No / Very Low Cost | No | KL Regularization to Parameter EMA |
| VRPO | Yes (Tested in highly stochastic IIGs) | No / Low Cost | No | Q-Boosting (Expected SARSA traces) |
| NashPG | Yes (Tested in 2p0s IIGs) | No / Low Cost | No | Iterative Reference Policy Refinement |
| PSRO | Yes (Meta-game solver) | No / Mod-High Cost | No | Empirical Meta-Game Equilibrium |
| R-NaD | Yes (Tested on Stratego) | Yes / Complete Rewrite | No | Neural Replicator Dynamics & Reward Transforms |
| NFSP | Marginal (Designed for sequential) | Yes / Complete Rewrite | No | Supervised Average Policy via Reservoir |
| Deep CFR | No (Designed for sequential trees) | Yes / Complete Rewrite | Often | Counterfactual Regret Matching |

## 5. Synthesis and Recommendations

The instability and 0.10 win-rate variance observed across independently seeded PPO runs in the Pokémon Showdown environment are not indicative of a software bug or improper hyperparameter tuning. Rather, they represent a fundamental mathematical limitation of Independent PPO when deployed in zero-sum, imperfect-information Markov Games. The algorithm is trapped in cyclical best-response dynamics, navigating endless intransitive loops without a theoretical mechanism to anchor it to a Nash Equilibrium. Furthermore, the reliance on Generalized Advantage Estimation (GAE) in a highly stochastic environment is injecting fatal variance into the policy updates, blinding the actor network to true strategic improvements.

To empirically confirm this diagnosis using existing artifacts, the generation of an empirical cross-play matrix among the varied seeds is required. Applying Alpha-Rank to this matrix will mathematically map the cyclical basins of attraction, proving the existence of non-transitive limit cycles.

To resolve the algorithmic failure without discarding the existing DeepSets PPO architecture, abandoning the pure self-play requirement, or exceeding the strict 50 million CPU step budget, the integration of regularized policy gradient methods is strongly recommended.

Specifically, EMAgnet provides the most elegant and architecturally viable solution to macro-level cycling, requiring only the tracking of an exponential moving average of policy weights and the addition of a KL divergence penalty to the PPO loss. Combining this with the VRPO (Q-boosting) advantage estimator to neutralize micro-level action-sampling noise presents a mathematically rigorous, empirically proven, and highly realistic path forward. This hybrid approach retains the speed and simplicity of the current PPO codebase while augmenting it with the theoretical guarantees necessary to stabilize self-play and achieve convergence in a highly stochastic, simultaneous-move environment.
