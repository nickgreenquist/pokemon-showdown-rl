"""Snapshot pool: the historical-opponent side of self-play (Phase 4 chunk 2).

Two objects. `AgentOpponent` wraps a frozen copy of a training agent's nets
behind the `Opponent` protocol; `SnapshotPool` holds a population of them and
IS an `Opponent` itself, which is the whole wiring trick — `rl/train.py`
passes the pool through the same `env_kwargs` seam a name like "heuristic"
travels, and one pool object is shared by every sub-env because caller kwargs
are never deep-copied (see `rl/envs/make.py`).

Where the copy happens is the load-bearing decision: `agent.state_dict()`
ALIASES the live training tensors (probe-confirmed, SESSION_LOGS_PREDECESSOR.md), so a pool of
state_dicts would hold references into the learner and every "frozen"
opponent would silently track it — the Phase-3 log_alpha rebind failure
class. `AgentOpponent.__init__` therefore deep-copies at construction, where
it cannot be forgotten by a call site — and it copies the ACTOR and CRITIC
ONLY (F-01, 2026-09-02). Until then it deep-copied the whole agent, which at
the batch recipe dragged the learner's `RolloutBuffer` (obs + next_obs at
(3840, 8, 828) float32 = 2 x 3840 x 8 x 828 x 4 B = 203.5 MB) and the Adam
moments (1.17 M params x 2 x 4 B = 9.4 MB) into EVERY member: ~4.1 GB of
dead pages per lane at pool_size 20 on the sync path, and again on every
async `--resume` (which rebuilds all members through `agent_factory`). The
old "~2/3 of the ~1 MB per snapshot is dead optimizer state — accepted
waste" was a Connect-4-era figure, 200x short of the batch-recipe truth;
that is the 5.87 GB solo-lane D-E landmine's mechanism. A member now costs
its weights (~4.5 MB at the batch recipe — `pool.pt`'s 90 MB over 20
members was already exactly that).

Two distinct swap boundaries, enforced by WHERE things are called rather
than by state in here:

- which member plays is drawn per EPISODE — `select()` runs at env reset;
- new snapshots enter the pool only at a ROLLOUT boundary — `push()` is
  called from `rl/train.py` right after the `update()` that drained the
  buffer, so within a rollout the env is a *stochastic* env with a fixed
  opponent distribution, not a non-stationary one. That is what PPO's
  importance ratios actually require.

Retention on overflow is SPAN-PRESERVING THINNING (fixed 2026-08-06; the
ported rule deleted index 1 every time, which flushed a pre-seeded pool
within pool_size pushes and degenerated retention to anchor + recency
window — the recovered predecessor record measured exactly that). A plain
recency deque was the only pool-span design with a published ablation
against it (Bansal et al., ICLR 2018 — "training against the latest
opponent leads to worst performance"), so on overflow the pool evicts the
member whose push-time neighbors are closest together — the one whose
removal costs the least span coverage — never the step-0 anchor and never
the newest. Retained push ids stay ~uniform over [0, latest], so the
pool's span grows with training instead of trailing it. The exception is
`pool_size: 1` — the naive arm, a <=push-cadence-lagged copy of the
learner, which is what the self-play literature means by naive self-play —
where push must REPLACE, because keeping the oldest would pin the naive
arm to its random init forever.
"""

import copy

import numpy as np
import torch

from rl.common.masking import masked_logits
from rl.selfplay.opponents import Opponent


class _MemberNets:
    """What a member keeps of the agent it was snapshotted from: the two nets
    and the device. That is the whole `.agent.actor / .agent.critic /
    .agent.device` surface `move()`, `freeze()`, the pool's state_dict
    round-trip and the tests read. `__slots__` makes the surface the
    contract: nothing else — not a `RolloutBuffer`, not an optimizer — can
    ride along on a member by accident, which is exactly what the pre-F-01
    whole-agent deepcopy let happen (module docstring)."""

    __slots__ = ("actor", "critic", "device")

    def __init__(self, actor, critic, device):
        self.actor = actor
        self.critic = critic
        self.device = device


class AgentOpponent(Opponent):
    """A frozen agent snapshot playing as an env opponent.

    Samples from the policy rather than argmaxing: a deterministic opponent
    collapses an eval or tournament set to a couple of distinct games (the
    `eval/return_std > 0` failure), and stochastic play on both sides is the
    locked tournament protocol. The draw comes from this opponent's OWN
    `torch.Generator`, never the global torch stream — the learner's
    collection also samples from the global stream, so sharing it would let
    the number of learner steps between opponent moves change every seeded
    opponent decision, and a chunk-3 tournament matchup could never be
    replayed in isolation.

    `move()` runs its own forward instead of calling `agent.act()`: act()
    samples via `Categorical.sample()`, which only draws from the global
    stream.
    """

    def __init__(self, agent, seed: int = 0):
        # Deep-copy the NETS, never the agent: the copy is what makes the
        # snapshot frozen (state_dict aliases the learner — module docstring),
        # but copying the agent also cloned its RolloutBuffer and Adam
        # moments, ~215 MB of dead memory per member at the batch recipe
        # (F-01). A member plays from its actor; the critic rides only so
        # state_dict() restores exactly what push() froze. One deepcopy call
        # over the pair keeps any module the two nets might share shared in
        # the copy too, as the whole-agent copy did (today they share none).
        actor, critic = copy.deepcopy((agent.actor, agent.critic))
        self.agent = _MemberNets(actor=actor, critic=critic, device=agent.device)
        self.generator = torch.Generator().manual_seed(seed)

    def freeze(self) -> None:
        for net in (self.agent.actor, self.agent.critic):
            net.eval()
            for param in net.parameters():
                param.requires_grad_(False)

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        obs_t = torch.as_tensor(obs, dtype=torch.float32, device=self.agent.device).unsqueeze(0)
        mask_t = torch.as_tensor(mask, dtype=torch.bool, device=self.agent.device)
        with torch.no_grad():
            probs = torch.softmax(masked_logits(self.agent.actor(obs_t), mask_t), dim=-1)
        return int(torch.multinomial(probs, 1, generator=self.generator).item())


class SnapshotPool(Opponent):
    """A population of `AgentOpponent` snapshots, itself an `Opponent`.

    `select()` is the 80/20 draw (OpenAI Five's split): `latest_prob` on the
    newest member, else uniform over the rest — the uniform historical draw
    is ours, not theirs (they weighted by quality scores over an unbounded
    pool). It draws from the RNG the env hands in, which is the env's own
    per-episode stream — the pinned draw order (flip, select, opponent
    moves) is unchanged, the select slot just consumes draws now.

    The two chunk-4 probe levers (`pfsp_power`, `fixed_mix`) were REMOVED
    2026-08-29 (CLEANUP A4, maintainer-ruled): both sat at their inert
    defaults in every config ever run — fixed_mix was additionally
    hard-rejected for Showdown and its Connect4 path had no config — so
    select() here IS the pre-lever draw, byte-identical on the seeded
    stream (the compatibility contract test_selfplay_pool pins). `report()`
    and the per-member stats STAY: they feed the live selfplay/* metrics.

    The pool must be non-empty before the first env reset: `rl/train.py`
    pushes the step-0 snapshot before entering the loop, and `select()` on
    an empty pool raises rather than papering over a broken push order.
    """

    def __init__(self, pool_size: int, latest_prob: float):
        if pool_size < 1:
            raise ValueError(f"pool_size must be >= 1, got {pool_size}")
        if not 0.0 <= latest_prob <= 1.0:
            raise ValueError(f"latest_prob must be a probability, got {latest_prob}")
        self.pool_size = pool_size
        self.latest_prob = latest_prob
        self.members: list[AgentOpponent] = []
        # Per-member [learner score sum, games] fed by report(); read by the
        # train loop's selfplay/winrate_anchor / winrate_latest metrics.
        self.stats: list[list[float]] = []
        self.pushes = 0  # lifetime count; also seeds each member's generator
        self.push_ids: list[int] = []  # per-member push counter, for retention

    def __len__(self) -> int:
        return len(self.members)

    def push(self, agent) -> None:
        """Snapshot `agent` into the pool. The install point, so freezing
        happens here — a snapshot cannot enter the pool trainable."""
        member = AgentOpponent(agent, seed=self.pushes)
        member.freeze()
        self.members.append(member)
        self.stats.append([0.0, 0])
        self.push_ids.append(self.pushes)
        self.pushes += 1
        if len(self.members) > self.pool_size:
            evict = self._evict_index()
            del self.members[evict]
            del self.stats[evict]
            del self.push_ids[evict]

    def _evict_index(self) -> int:
        """Span-preserving thinning (module docstring). Never the step-0
        anchor, never the newest; among the rest, evict the member whose
        push-time neighbors are closest together — ties go to the oldest.
        At pool_size 1 (the naive arm) the sole member is replaced, because
        protecting the oldest would pin that arm to its random init."""
        if self.pool_size == 1:
            return 0
        ids = self.push_ids
        return min(range(1, len(ids) - 1), key=lambda i: (ids[i + 1] - ids[i - 1], i))

    def member_id(self, played: Opponent) -> int:
        """The push id of the member that played, or -1 for one evicted
        mid-episode. Identity match, same rule as `report`.

        Push ids and not list indices: indices shift under eviction, while a
        push id names the checkpoint that generated a decision for the run's
        whole life. D25 §6 needs exactly that — the manipulation check's oracle
        floor A3 must be evaluated on the member that actually produced each
        label, not on one arbitrary actor. Under a real pool (latest_prob 0.8,
        per-member E[H] spanning 0.17-0.43) a legitimate head otherwise reaches
        a gap closure of 1.08 and the "g > 1.0 is a bug" hard fail fires on a
        correct run."""
        for member, push_id in zip(self.members, self.push_ids):
            if member is played:
                return push_id
        return -1

    def report(self, played: Opponent, outcome: int) -> None:
        """Accumulate the learner's result vs the member that played.
        Identity match on purpose: a member evicted while its last episode
        was in flight is silently not a member and should not move any
        count."""
        for member, stat in zip(self.members, self.stats):
            if member is played:
                stat[0] += (outcome + 1) / 2  # learner score: win 1, draw 0.5
                stat[1] += 1
                return

    def select(self, rng: np.random.Generator) -> Opponent:
        if not self.members:
            raise IndexError("empty pool: push a snapshot before the first reset")
        if len(self.members) == 1:
            return self.members[0]
        if rng.random() < self.latest_prob:
            return self.members[-1]
        return self.members[int(rng.integers(len(self.members) - 1))]

    def move(self, obs: np.ndarray, mask: np.ndarray, rng: np.random.Generator) -> int:
        raise TypeError("the pool never plays; select() returns the member that does")

    def state_dict(self) -> dict:
        """Everything a resumed run needs to reconstruct THIS pool exactly:
        member networks (actor + critic — a member's play reads only the
        actor, the critic rides so a member restores to what push() froze),
        per-member torch generator STATE (not just its seed: draws already
        consumed must not replay), per-member stats, push ids, lifetime
        counter. The learner's own weights are the checkpoint's job, not
        the pool's."""
        return {
            "pool_size": self.pool_size,
            "latest_prob": self.latest_prob,
            "pushes": self.pushes,
            "push_ids": list(self.push_ids),
            "stats": [list(s) for s in self.stats],
            "members": [
                {
                    "actor": m.agent.actor.state_dict(),
                    "critic": m.agent.critic.state_dict(),
                    "generator": m.generator.get_state(),
                }
                for m in self.members
            ],
        }

    def load_state_dict(self, state: dict, agent_factory) -> None:
        """Rebuild members via `agent_factory` (a zero-arg callable returning
        a freshly constructed learner-shaped agent). Each member keeps only
        the factory agent's nets (`AgentOpponent.__init__`); the transient
        agent itself — its untouched RolloutBuffer, its empty optimizer — is
        dropped on the spot, so a resume costs weights, not ~205 MB per
        member. Restores membership, stats and generator streams.
        Checkpoints written before 2026-08-29 carry pfsp_power/fixed_mix
        keys (both always 0.0, levers removed); they are simply not read."""
        for key in ("pool_size", "latest_prob"):
            got, want = getattr(self, key), state[key]
            assert got == want, (
                f"pool {key} mismatch on resume: constructed {got}, "
                f"checkpoint {want} — the pool config must come from the "
                "run's own config.yaml"
            )
        self.members, self.stats = [], []
        self.push_ids = list(state["push_ids"])
        self.pushes = state["pushes"]
        for mstate, push_id in zip(state["members"], self.push_ids):
            member = AgentOpponent(agent_factory(), seed=push_id)
            member.agent.actor.load_state_dict(mstate["actor"])
            member.agent.critic.load_state_dict(mstate["critic"])
            member.generator.set_state(mstate["generator"])
            member.freeze()
            self.members.append(member)
        self.stats = [list(s) for s in state["stats"]]

    def freeze(self) -> None:
        """No-op on purpose: members are frozen one by one at push(), which
        is their install point. The env still calls this when the pool is
        installed — the contract is that every installer calls freeze()."""
