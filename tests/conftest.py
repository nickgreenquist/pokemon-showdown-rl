"""Suite-wide fixtures. Currently: keeping the live-server tests from wedging.

WHY THIS EXISTS. On 2026-09-10 the suite HUNG — not failed, hung — whenever a
Showdown server was up, and it did so at zero CPU with no error anywhere. The
cause is a chain of three things, none of which is a bug on its own:

  1. The live tests get DETERMINISTIC poke-env usernames. Six of the nine reach
     `AccountConfiguration.generate(..., rand=True)`, which draws from the
     GLOBAL `random` module — and `rl/common/seeding.py`'s `set_seed` has
     already pinned that module by the time these tests run, because
     `test_l2_init` and `test_resume` sort earlier and call it. Run one of
     these files ALONE and `random` is OS-seeded, the names are fresh, and it
     passes. That is precisely the "passes alone, fails in the suite" signature
     CLAUDE.md records as a known flake — it was never a flake, it was an
     ordering dependency.
  2. A leftover registration from a killed run makes that name collide, which
     CLAUDE.md's landmine list calls a pair "poisoned for hours".
  3. poke-env raises `nametaken` on its private daemon loop, where nothing on
     the main thread ever sees it — and the main thread is parked on
     `battle_queue.get()` with NO TIMEOUT. So a collision becomes an
     indefinite hang rather than an error.

`random.seed()` below removes (1). The watchdog removes the consequence of (3),
which matters more: a suite that fails is diagnosable, a suite that hangs at
zero CPU consumed hours here before anyone realised it was not merely slow.
Same instrument, same reasoning as the per-battle watchdog `scripts/engine_d1.py`
already carries for the same failure shape.
"""

from __future__ import annotations

import random
import signal

import pytest

LIVE_TEST_BUDGET_S = 300.0


@pytest.fixture(autouse=True)
def _live_server_watchdog(request):
    """Bound every `live_server` test, and hand it an unpinned RNG."""
    if request.node.get_closest_marker("live_server") is None:
        yield
        return

    # Undo whatever set_seed() an earlier test left in the global `random`.
    # poke-env derives seat names from it, so a pinned stream means every suite
    # run asks for the same usernames.
    random.seed()

    def _blow(_signum, _frame):
        raise TimeoutError(
            f"{request.node.name} exceeded {LIVE_TEST_BUDGET_S:.0f}s. A poke-env "
            "handshake that never completes looks exactly like this: both sides "
            "alive at ZERO CPU, no exception anywhere, because `nametaken` is "
            "raised on a daemon loop the main thread never checks. Check that "
            "nothing else holds these usernames — a killed run poisons its pair "
            "for hours."
        )

    old = signal.signal(signal.SIGALRM, _blow)
    signal.setitimer(signal.ITIMER_REAL, LIVE_TEST_BUDGET_S)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, old)
