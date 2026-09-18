"""Escape a deterministic-policy limit cycle without becoming stochastic.

RESULTS §28: every turn-cap stall this project has ever produced is the same
thing -- the opponent is down to one Pokemon FROZEN SOLID (gen-1 freeze is
permanent without a fire move, so it cannot act), the state therefore stops
changing, and a deterministic policy in an unchanging state repeats its action
forever. Measured six times across three blocks and two objects, with and
without search: ~950 switches, **100% strictly alternating between exactly two
Pokemon**, against a helpless opponent, to the 1000-turn cap and a TIE -- which
the locked protocol counts as a NON-WIN. A thrown-away win.

WHY NOT JUST SAMPLE. Because the locked eval protocol names a DETERMINISTIC
policy, and sampling would change every battle rather than the broken ones. This
stays deterministic: the action is a function of the episode's history, so a
replay of the same battle plays the same moves, and it CANNOT CHANGE A SINGLE
NON-LOOPING BATTLE -- it fires only after the same (observation, action) pair has
recurred `threshold` times, which cannot happen unless the game has stopped
moving.

WHY A COUNT AND NOT A ONE-SHOT. A legitimate position can repeat once or twice
(two Pokemon trading Recover, a stalled paralysis turn). Four occurrences of the
IDENTICAL observation AND the identical chosen action is not a game state any
more; it is a fixed point.

ESCALATION. Breaking to the second-best action can land in another fixed point --
the measured loops are period-2 or period-3. The breaker therefore remembers how
many times it has already escaped THIS observation and takes the (k+1)-th best
action, so a cycle of any period unwinds in at most (legal actions) steps.

NOT WIRED ANYWHERE. It is a change to the POLICY FORM and the locked protocol
names the policy, so it needs the maintainer's ruling before a headline number
uses it (RESULTS §28). This module is the proposal, tested against the measured
signature.
"""
from __future__ import annotations

import hashlib

import numpy as np

DEFAULT_THRESHOLD = 4


def obs_key(obs: np.ndarray, decimals: int = 4) -> str:
    """A stable key for 'the same position'.

    Rounded before hashing because two float32 observations of an unchanging
    position can differ in the last bit and a raw hash would never match -- the
    breaker would then never fire and would look like it did not work.
    """
    a = np.round(np.asarray(obs, dtype=np.float64), decimals)
    return hashlib.blake2b(a.tobytes(), digest_size=16).hexdigest()


class LoopBreaker:
    """Per-battle memory of (observation, action) pairs.

    `decide` takes the policy's scores over actions and the legality mask, and
    returns the action to play. With no repetition it returns the argmax --
    bit-identical to what the greedy seat would have played.
    """

    def __init__(self, threshold: int = DEFAULT_THRESHOLD):
        assert threshold >= 2, "a threshold of 1 would fire on the first repeat"
        self.threshold = int(threshold)
        self._seen: dict[tuple[str, int], int] = {}
        self._escapes: dict[str, int] = {}
        self.counters = {
            # COUNTERS BEFORE ARMS, the standing rule: a breaker that never
            # fires and one that fires constantly must not report the same.
            "loop/decisions": 0,
            "loop/fired": 0,
            "loop/max_repeat": 0,
            "loop/distinct_states": 0,
        }

    def reset(self) -> None:
        """New battle. The memory is per-episode: two battles can legitimately
        reach the same position, and carrying the count across them would fire
        the breaker on a first visit."""
        self._seen.clear()
        self._escapes.clear()

    def decide(self, obs: np.ndarray, scores: np.ndarray, mask: np.ndarray) -> int:
        legal = np.flatnonzero(np.asarray(mask, dtype=bool))
        assert legal.size, "no legal action"
        self.counters["loop/decisions"] += 1
        order = legal[np.argsort(-np.asarray(scores, dtype=np.float64)[legal],
                                kind="stable")]
        key = obs_key(obs)
        k = self._escapes.get(key, 0)
        action = int(order[min(k, len(order) - 1)])
        seen = self._seen.get((key, action), 0) + 1
        self._seen[(key, action)] = seen
        self.counters["loop/max_repeat"] = max(self.counters["loop/max_repeat"], seen)
        self.counters["loop/distinct_states"] = len({s for s, _ in self._seen})
        if seen >= self.threshold:
            # This exact position has produced this exact action `threshold`
            # times. Escalate one rank for every future visit to this position.
            self._escapes[key] = k + 1
            self.counters["loop/fired"] += 1
        return action

    @property
    def fired_rate(self) -> float:
        d = self.counters["loop/decisions"]
        return self.counters["loop/fired"] / d if d else 0.0
