"""PROOF that `/timer on` reaches the server on the TRAINING env path.

The handoff's standing order for THE ORPHANED-ROOM DEADLOCK fix was "VERIFY,
do not assume ... a short live run plus an assertion on the constructed
player, not a code read". This is that. It

  1. builds the REAL training env through `make_env` (no test doubles),
  2. asserts both `_EnvPlayer` seats carry `_start_timer_on_battle_start`,
  3. RECORDS every outgoing websocket message and proves a `/timer on` was
     sent, per battle, by BOTH seats -- the wire, not the flag, and
  4. runs a CONTROL env with the knob False and proves ZERO `/timer on`, so
     the recorder cannot be reporting a message it invented.

Needs a live local Showdown server. Usage:

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/ch5_timer_smoke.py --battles 6
"""

import argparse
import json

import numpy as np

from rl.envs.make import make_env


def _instrument(env):
    """Wrap both seats' ps_client message funnels: `send_message` for what WE
    put on the wire, `_handle_message` for what the SERVER says back. The
    second one is the half that matters -- it proves the server ACTED on
    `/timer on` rather than merely that we sent it."""
    sent = []
    received = []
    inner = env.unwrapped._env.env  # ActionMask -> ShowdownEnv -> SingleAgentWrapper
    for seat in ("agent1", "agent2"):
        player = getattr(inner, seat)
        client = player.ps_client

        def make_send(seat=seat, original=client.send_message):
            async def recording(message, room="", message_2=None):
                sent.append({"seat": seat, "message": message, "room": room})
                return await original(message, room, message_2)
            return recording

        def make_recv(seat=seat, original=client._handle_message):
            async def recording(message):
                if "|inactive|" in message:
                    for line in message.split("\n"):
                        if line.startswith("|inactive|"):
                            received.append({"seat": seat, "line": line})
                return await original(message)
            return recording

        client.send_message = make_send()
        client._handle_message = make_recv()
    return inner, sent, received


def _play(env, battles):
    """Play `battles` episodes with a legal-random policy (the policy is
    irrelevant here; what matters is that real battles start and finish)."""
    rng = np.random.default_rng(0)
    finished = 0
    for i in range(battles):
        obs, info = env.reset(seed=1000 + i)
        done = False
        while not done:
            mask = info["action_mask"]
            legal = np.flatnonzero(mask)
            obs, reward, term, trunc, info = env.step(int(rng.choice(legal)))
            done = term or trunc
        finished += 1
    return finished


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--battles", type=int, default=6)
    args = ap.parse_args()

    report = {}
    for label, flag in (("treatment", True), ("control", False)):
        env = make_env(
            "Showdown-v0",
            seed=7 if flag else 8,
            env_kwargs={
                "opponent": "heuristics",
                "start_timer_on_battle_start": flag,
            },
        )
        inner, sent, received = _instrument(env)
        seats = {s: getattr(inner, s) for s in ("agent1", "agent2")}
        flags = {s: p._start_timer_on_battle_start for s, p in seats.items()}
        finished = _play(env, args.battles)
        timers = [m for m in sent if m["message"] == "/timer on"]
        rooms = sorted({m["room"] for m in timers})
        per_seat = {s: sum(1 for m in timers if m["seat"] == s) for s in seats}
        acked = [m for m in received if "Battle timer is ON" in m["line"]]
        report[label] = {
            "constructed_flag": flags,
            "battles_finished": finished,
            "timer_on_sent": len(timers),
            "timer_on_per_seat": per_seat,
            "distinct_rooms_timed": len(rooms),
            "total_messages_sent": len(sent),
            "server_timer_on_acks": len(acked),
            "server_ack_example": acked[0]["line"] if acked else None,
            "inactive_lines_seen": len(received),
            "usernames": {s: p.username for s, p in seats.items()},
        }
        env.close()

    t, c = report["treatment"], report["control"]
    assert all(t["constructed_flag"].values()), "the kwarg did not reach the seats"
    assert not any(c["constructed_flag"].values()), "control seats got the flag"
    assert t["battles_finished"] == args.battles, "treatment battles did not finish"
    assert c["battles_finished"] == args.battles, "control battles did not finish"
    # One `/timer on` per seat per battle: the send sits in poke-env's
    # `_create_battle` (player.py:230), which runs once per room per seat.
    assert t["timer_on_sent"] == 2 * args.battles, t["timer_on_sent"]
    assert t["distinct_rooms_timed"] == args.battles, t["distinct_rooms_timed"]
    assert set(t["timer_on_per_seat"].values()) == {args.battles}, t["timer_on_per_seat"]
    assert c["timer_on_sent"] == 0, "control sent /timer on"
    # The server's own answer, seen by both seats: `|inactive|Battle timer is
    # ON ...` is broadcast to the room, so each of the N battles produces one
    # line per seat.
    assert t["server_timer_on_acks"] == 2 * args.battles, t["server_timer_on_acks"]
    assert c["server_timer_on_acks"] == 0, "control saw a timer-on broadcast"

    print(json.dumps(report, indent=2))
    print(f"\nPASS: /timer on is on the wire on the training path "
          f"({t['timer_on_sent']} sends over {args.battles} battles, one per "
          f"seat per battle) and the SERVER acknowledged it "
          f"({t['server_timer_on_acks']} broadcasts). Control: 0 and 0.")


if __name__ == "__main__":
    main()
