"""END-TO-END proof that `/timer on` RESOLVES an orphaned room.

`ch5_timer_smoke.py` proves the message reaches the server. This proves the
message FIXES THE BUG, which is the claim the maintainer is being asked to
rule on. It reproduces THE ORPHANED-ROOM DEADLOCK (docs/landmines.md) in
miniature -- a live battle whose opponent vanishes mid-game, exactly as
foul-play's Rust engine vanishes when a turn-1000 auto-tie makes both sides
Struggle -- and measures whether our seat's room ever ends.

    treatment (start_timer_on_battle_start=True):  room must END
    control   (start_timer_on_battle_start=False): room must NOT end

The control is what has been running in every arm to date. Expect it to sit
at the cap, which is the whole incident in one line.

Challenge battles get STARTING_TIME_CHALLENGE=300 plus a
DISCONNECTION_BANK_TIME=300 bank (showdown/server/room-battle.ts:47/52), so
the treatment should resolve in roughly five minutes, not instantly. That
number is itself the ops answer to "how long does one orphan cost us".

    python scripts/ch5_orphan_demo.py            # both arms, ~13 min
    python scripts/ch5_orphan_demo.py --arm treatment
"""

import argparse
import asyncio
import json
import os
import time

from poke_env.player import SimpleHeuristicsPlayer
from poke_env.ps_client import AccountConfiguration

FORMAT = "gen1randombattle"


async def _any_battle(player, timeout=90.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if player.battles:
            return next(iter(player.battles.values()))
        await asyncio.sleep(0.05)
    raise TimeoutError("no battle appeared")


def _mute(player):
    """Stop `player` ever answering a battle request.

    The disconnect alone is not enough to reproduce the incident on this box:
    a local heuristics-vs-heuristics battle runs END TO END IN ~40 ms, so by
    the time any external watcher reacts to `|init|` the game is already over
    (measured: the first two versions of this script disconnected at turns 21
    and 18, of a finished battle). Muting the opponent first freezes the room
    at turn 1, which is the state a panicked foul-play process leaves behind;
    dropping its socket afterwards makes it an ORPHAN rather than a slow
    player.
    """
    async def deaf(*args, **kwargs):
        return

    player._handle_battle_request = deaf


async def run_arm(label: str, flag: bool, cap: float, poll: float,
                  settle: float = 3.0) -> dict:
    tag = f"{os.getpid() % 100000}{label[:2]}"
    victim = SimpleHeuristicsPlayer(
        account_configuration=AccountConfiguration(f"orphvic{tag}", None),
        battle_format=FORMAT,
        max_concurrent_battles=1,
        start_timer_on_battle_start=flag,
    )
    ghost = SimpleHeuristicsPlayer(
        account_configuration=AccountConfiguration(f"orphgho{tag}", None),
        battle_format=FORMAT,
        max_concurrent_battles=1,
    )
    _mute(ghost)
    # `battle_against`, not raw send/accept_challenges: poke-env runs every
    # player on its own background POKE_LOOP, and only the wrapped entry
    # points marshal across it (`handle_threaded_coroutines`). Awaiting
    # `send_challenges` from this loop touches primitives that live on
    # another one and the handshake silently never completes -- which is
    # exactly how the first version of this script failed.
    playing = asyncio.create_task(ghost.battle_against(victim, n_battles=1))

    battle = await _any_battle(victim)
    # The room is now open and frozen at turn 1 with the opponent mute. Drop
    # its socket: from here the room is an ORPHAN, exactly as after the Rust
    # panic, and nothing but the server can ever end it.
    await asyncio.sleep(settle)
    turn_at_kill = battle.turn
    await ghost.ps_client.stop_listening()
    t0 = time.time()
    while not battle.finished and time.time() - t0 < cap:
        await asyncio.sleep(poll)
    elapsed = time.time() - t0

    playing.cancel()
    await asyncio.gather(playing, return_exceptions=True)
    # The slot is the thing that actually deadlocks a lane: poke-env returns
    # it only on |win|/|tie| (player.py:311), so report it directly.
    slots_held = victim._battle_count_queue.qsize()
    try:
        await victim.ps_client.stop_listening()
    except Exception:
        pass

    return {
        "arm": label,
        "start_timer_on_battle_start": flag,
        "turn_at_disconnect": turn_at_kill,
        "room_resolved": bool(battle.finished),
        "seconds_to_resolve": round(elapsed, 1) if battle.finished else None,
        "seconds_waited": round(elapsed, 1),
        "cap_seconds": cap,
        "queue_slots_still_held": slots_held,
        "max_concurrent_battles": 1,
        "battle_tag": battle.battle_tag,
    }


async def main_async(args):
    arms = [("treatment", True), ("control", False)]
    if args.arm != "both":
        arms = [a for a in arms if a[0] == args.arm]
    out = []
    for label, flag in arms:
        print(f"[{time.strftime('%H:%M:%S')}] {label}: "
              f"start_timer_on_battle_start={flag}", flush=True)
        result = await run_arm(label, flag, args.cap, args.poll, args.settle)
        print(json.dumps(result, indent=2), flush=True)
        out.append(result)
    print("\n=== ORPHANED-ROOM DEMO ===", flush=True)
    for r in out:
        verdict = (f"RESOLVED after {r['seconds_to_resolve']}s"
                   if r["room_resolved"]
                   else f"STILL OPEN after {r['seconds_waited']}s (the bug)")
        print(f"  {r['arm']:10s} timer={r['start_timer_on_battle_start']!s:5s} "
              f"{verdict}; slots held {r['queue_slots_still_held']}/1",
              flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", choices=["both", "treatment", "control"], default="both")
    ap.add_argument("--cap", type=float, default=420.0,
                    help="seconds to wait for the room to end (300s bank + slack)")
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--settle", type=float, default=3.0,
                    help="seconds the room stays open before the opponent vanishes")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
