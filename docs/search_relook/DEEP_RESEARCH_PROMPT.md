# Deep-research prompt — value functions for test-time search over a PPO policy

Paste everything below the line into Claude web's deep research mode.

---

I need a literature-grounded answer to one question: **how do you obtain a value
function good enough for test-time search, when your policy was trained with PPO
in pure self-play?** I have a concrete, measured anomaly to explain, and I want
prior art, not speculation.

## My situation, with numbers

I train an agent to play Pokémon Showdown **Gen 1 random battles** (battle phase
only, no team building) with PPO in **pure self-play** — no human replays, no
expert demonstrations, no distillation from a stronger bot, ever. That purity
constraint is a hard requirement of the project, not a preference.

The trained policy is decent: **0.789 win rate vs the benchmark rule-based
opponent** (`SimpleHeuristicsPlayer` in poke-env), measured over 3 seeds x 3000
battles, deterministic/greedy action selection, ties counted as non-wins.

I then added **inference-time search**: depth-1 expectimax over the same
checkpoint's PPO value head. For each of my legal actions, crossed with a
distribution over the opponent's likely actions, I sample 4 determinizations of
the opponent's hidden team, roll the game engine forward one turn, and score the
resulting leaves with the critic. About 300 leaves and ~62 ms per decision.

**It made the agent worse: 0.721 vs 0.789, a delta of −0.068, negative on all
three seeds.** Against a strong search-based opponent (an expectiminimax bot
with a hand-written evaluation) the same comparison is 0.396 searched vs 0.502
greedy. Increasing the search budget 4x makes it slightly worse still, not
better.

I found and fixed one real defect along the way: my leaf encoder was showing the
critic the *determinized* opponent bench as if it were revealed, which is
out-of-distribution for a critic trained only on the real partially-observed
encoding. That bias was large — the leaf values shifted by +0.050 on average
with a standard deviation of 0.125, against decision margins (top action minus
second action) of about 0.028, i.e. the artefact was 4.5x the size of the
decisions being made. **Fixing it changed the win rate by −0.009, i.e. nothing.**

So the encoding was not the binding constraint. My hypothesis is that the
**PPO critic itself is the wrong object to search over**: PPO trains V(s) as a
variance-reducing baseline for advantage estimation, on states the current
policy actually visits, with a bootstrapped target. Search needs accurate
*absolute* values on *hypothetical* states the policy would never have reached,
including states that are one bad move away from disaster. Those are different
objectives and I have never trained for the second one.

## The anomaly I most want explained

Jett Wang's 2024 MIT MEng thesis ("Winning at Pokémon Random Battles Using
Reinforcement Learning") trains PPO in self-play on **Gen 4** random battles and
adds **test-time MCTS**. He reports the network alone at **0.786** vs the same
`SimpleHeuristicsPlayer` benchmark — essentially the same base strength as mine
— and the **full MCTS + network agent at 0.908**. Search bought him roughly
**+12 points** and his ladder rank.

Two systems, near-identical base strength against the same benchmark opponent
class, and search helps one by +12 points while costing the other 7. I want to
know why. Candidate explanations I can think of, and I want the literature's
view on each: leaf-evaluator quality and how it was trained; MCTS with a policy
prior versus one-ply expectimax; simulation budget; generation and episode
length; action-space design; determinization quality for the hidden information;
or a measurement difference that makes the two numbers less comparable than they
look.

## What I want from you

**1. The core question: training a value function FOR search, not for PPO.**
What does the literature actually say and do here? I am looking for concrete,
implementable techniques with citations, ideally with reported effect sizes:

- Training a separate value head or network on **Monte-Carlo returns to
  termination** rather than TD/GAE bootstrapped targets — how much does this
  matter in practice, and who has measured it?
- Training the evaluator on a **broader state distribution** than the policy's
  own: states reached by perturbed/random/exploratory actions, resampled
  states, or states drawn from search trees. What is this called in the
  literature and what are the standard recipes?
- The AlphaZero family's approach: value trained on **final game outcomes** from
  self-play, jointly with a policy prior, and why that yields something
  searchable when a PPO critic may not.
- **Value equivalence** and MuZero-style learned models: the argument that a
  value function should be trained to be *useful for planning* rather than
  accurate per se.
- Calibration and the **overestimation/optimism** problem when a search argmaxes
  over a noisy value function (the "optimizer's curse" / maximization bias);
  what corrections exist (ensembles, quantile/distributional critics,
  pessimism, uncertainty penalties) and which have been shown to help *search*
  specifically rather than just off-policy learning.
- The known failure mode where **more search makes a policy worse** because the
  evaluator is miscalibrated — I would like the canonical references and any
  quantitative characterizations of when search helps versus hurts as a function
  of evaluator quality. There is work on "the more you search the worse you get"
  in imperfect-information and in noisy-evaluator settings; find it.
- Whether **fine-tuning an existing PPO critic** (rather than training a new
  evaluator from scratch) is a studied thing, and what it costs.

**2. Search in imperfect-information, simultaneous-move, stochastic games.**
Pokémon is all three at once: both players commit simultaneously, damage/accuracy
/crits are stochastic, and the opponent's team is hidden. What is the right
family of algorithms — decoupled/simultaneous-move UCT, counterfactual regret and
its search-time variants, ReBeL, Player of Games, information-set MCTS,
determinized (perfect-information Monte Carlo) search — and, critically, **what
is known about the failure modes of naive determinization** (strategy fusion,
non-locality)? I am currently doing determinized one-ply search, which is the
textbook case where those pathologies bite, and I want to know whether that
alone could explain a negative result of this size.

**3. Wang's thesis specifically, and comparable Pokémon RL systems.**
Read the thesis if you can reach it (MIT DSpace, handle 1721.1/153888) and tell
me exactly what his MCTS uses as its leaf evaluator, which MCTS variant it is,
how he handles simultaneous moves and stochasticity, how he determinizes the
hidden team, his simulation budget per move, and how the 0.786 and 0.908 numbers
were measured (n, opponent, ties, same checkpoint or not). Also look at other
Pokémon-battling agents that use search on top of a learned policy and say
whether any of them report the same negative result I have, or the conditions
under which search paid off.

**4. A ranked, actionable answer.** Given a pure-self-play constraint (no expert
data of any kind into the learner), rank the interventions most likely to turn a
negative search result into a positive one, with the evidence behind each and
the rough cost. I care about what to build next, in order.

## Ground rules

- **Distinguish what is verified in source code or a paper's own tables from
  what is claimed in an abstract, a blog post, or a README.** Several
  widely-repeated claims in this specific literature do not survive contact with
  the code, so tell me which of your sources you actually checked and how.
- Cite everything, with page/section/table numbers where the number came from.
- Where the literature genuinely does not answer a question, say so plainly
  rather than filling the gap.
- Prefer results with measured effect sizes over qualitative advice.
- Assume deep familiarity with PPO, GAE, MCTS, and RL generally; skip the
  tutorials and get to the specifics, the trade-offs, and the numbers.
