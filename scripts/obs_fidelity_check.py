"""Prove that OFFLINE tape replay reproduces LIVE observations, exactly.

    python scripts/obs_fidelity_check.py --battles 10

Needs the local Showdown server running.

WHY THIS EXISTS
---------------
`scripts/tape_to_dataset.py` reconstructs training rows by replaying a taped
protocol stream through poke-env's parser offline. Its gates (G1-G6) check that
labels round-trip, that rqids align, that battles terminate. **None of them
check the observation** -- and the observation is the product. `apply_message`
is a hand-rolled mirror of `poke_env/player/player.py`'s dispatch; any
divergence, however small, yields rows whose obs differ from what a live agent
would have seen, and EVERY existing gate still passes. A behavioural clone
trained on such rows would simply look weak, which is indistinguishable from
the diagnostic's own failure verdict.

So this script closes the loop the only way that actually settles it: play real
battles with our own `RecordingPlayer`, capture the live (obs, mask, action) at
each decision AND the raw inbound frames from the same seat, then replay the
frames offline through the same code `tape_to_dataset` uses and compare
**elementwise**.

WHAT IT ASSERTS
---------------
For every decision, on the same battle and the same rqid:
  * obs identical (bitwise on float32 -- not allclose; the replay is
    deterministic and should be exact, so any drift is a real defect)
  * action mask identical
  * the expert's action index identical

A single mismatch fails the run and prints the first differing feature index,
because "which feature drifted" is the whole diagnostic.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np
from poke_env.battle import Battle
from poke_env.data import GenData
from poke_env.environment import SinglesEnv
from poke_env.ps_client import ps_client as ps_client_module

from rl.collect import RecordingPlayer
from rl.envs.showdown import embed_battle

import logging

BATTLE_FORMAT = "gen1randombattle"
LOGGER = logging.getLogger("fidelity")
LOGGER.addHandler(logging.NullHandler())


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--battles", type=int, default=10)
    p.add_argument("--opponent", default="heuristics")
    p.add_argument("--expert", default="heuristics")
    p.add_argument("--username", default="fidelityrec")
    p.add_argument("--tape", type=Path, default=Path("data/fidelity/tape.jsonl"))
    return p.parse_args()


class TapingRecordingPlayer(RecordingPlayer):
    """RecordingPlayer that also tapes the raw frames its own seat receives.

    The tape is written from inside `_handle_message`, i.e. the same entry point
    poke-env itself parses from, so the offline replay is fed byte-identical
    input. A decision marker is appended in `choose_move` AFTER the parent has
    recorded its live row, which puts the marker at exactly the same position in
    the stream that `tape_to_dataset` will encounter it.
    """

    def __init__(self, *args, tape_path: Path, **kwargs):
        super().__init__(*args, **kwargs)
        tape_path.parent.mkdir(parents=True, exist_ok=True)
        self._tape = tape_path.open("w", buffering=1)
        self.live = []  # (battle_tag, rqid, obs, mask, action)

        # Player HOLDS a PSClient rather than inheriting one, so the hook goes
        # on the client instance. Taping here -- the same entry point poke-env
        # parses from -- guarantees the offline replay is fed byte-identical
        # input rather than something reconstructed a layer up.
        inner = self.ps_client._handle_message

        async def taping_handle_message(message: str):
            if not self._tape.closed:
                self._tape.write(json.dumps({"k": "m", "v": message}) + "\n")
            await inner(message)

        self.ps_client._handle_message = taping_handle_message

    def choose_move(self, battle):
        before = len(self.obs)
        order = super().choose_move(battle)
        if len(self.obs) > before:  # parent kept a row for this decision
            rqid = (battle.last_request or {}).get("rqid")
            self.live.append(
                (battle.battle_tag, rqid, self.obs[-1], self.masks[-1], self.actions[-1])
            )
            self._tape.write(
                json.dumps({"k": "d", "tag": battle.battle_tag, "rqid": rqid}) + "\n"
            )
        return order

    def close_tape(self):
        self._tape.close()


async def collect(args):
    """Play the battles, returning the live rows and the tape path."""
    player = TapingRecordingPlayer(
        args.expert,
        battle_format=BATTLE_FORMAT,
        tape_path=args.tape,
        max_concurrent_battles=1,
    )
    # NOT rl.envs.showdown.opponent_player: that builds a NON-listening player
    # (start_listening=False) because in training the opponent's choose_move is
    # called directly on the second seat's battle object and it never needs its
    # own connection. Here the two seats really do meet over the server, so the
    # opponent must own a websocket.
    from rl.envs.showdown import OPPONENT_PLAYERS

    opp = OPPONENT_PLAYERS[args.opponent](
        battle_format=BATTLE_FORMAT, max_concurrent_battles=1
    )
    await player.battle_against(opp, n_battles=args.battles)
    # battle_against returns when the battles are decided, but message-handling
    # tasks are still in flight; without a drain the last decision can be
    # appended to `live` after the tape is closed, which looks like a fidelity
    # failure and is not one.
    await asyncio.sleep(3)
    player.close_tape()
    return list(player.live), player.username


def replay(tape_path, username):
    """Offline replay -- deliberately the SAME logic tape_to_dataset uses."""
    # Loaded by path: `scripts/` is deliberately not a package (adding an
    # __init__.py would change pytest collection), and sys.path[0] is the
    # script's own directory when run as `python scripts/...`.
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "tape_to_dataset", Path(__file__).with_name("tape_to_dataset.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    apply_message, room_of = mod.apply_message, mod.room_of

    type_chart = GenData.from_format(BATTLE_FORMAT).type_chart
    battles, states = {}, {}
    out = []
    with tape_path.open() as fh:
        for line in fh:
            ev = json.loads(line)
            if ev["k"] == "m":
                room = room_of(ev["v"])
                if room is None:
                    continue
                if room not in battles:
                    battles[room] = Battle(room, username, LOGGER, gen=1)
                    states[room] = {"request": None, "winner": None, "tie": False, "errors": []}
                apply_message(battles[room], ev["v"], states[room])
                continue
            tag = ev["tag"]
            if tag not in battles:
                continue
            b = battles[tag]
            out.append(
                (
                    tag,
                    ev["rqid"],
                    embed_battle(b, type_chart),
                    np.array(SinglesEnv.get_action_mask(b), dtype=bool),
                )
            )
    return out


def main():
    args = parse_args()
    print(f"Playing {args.battles} battles as '{args.username}' (expert={args.expert})...")
    live, username = asyncio.run(collect(args))
    print(f"live decisions recorded: {len(live)}  (seat username: {username!r})")

    # The replay MUST use the username poke-env actually registered: it drives
    # `_player_role`, and a wrong one silently mislabels every seat-relative
    # feature in the observation.
    offline = replay(args.tape, username)
    print(f"offline decisions replayed: {len(offline)}")

    if len(live) != len(offline):
        print(f"\nFAIL: decision COUNT differs -- live {len(live)} vs offline {len(offline)}.")
        sys.exit(1)

    obs_bad = mask_bad = key_bad = 0
    first = None
    for (ltag, lrqid, lobs, lmask, _), (otag, orqid, oobs, omask) in zip(live, offline):
        if ltag != otag or lrqid != orqid:
            key_bad += 1
            continue
        if not np.array_equal(lobs, oobs):
            obs_bad += 1
            if first is None:
                idx = int(np.flatnonzero(lobs != oobs)[0])
                first = (ltag, lrqid, idx, float(lobs[idx]), float(oobs[idx]))
        if not np.array_equal(lmask, omask):
            mask_bad += 1

    n = len(live)
    print("=" * 66)
    print(f"decisions compared : {n}")
    print(f"battle/rqid mismatch: {key_bad}")
    print(f"observation mismatch: {obs_bad}")
    print(f"mask mismatch       : {mask_bad}")
    print("=" * 66)
    if first:
        tag, rqid, idx, lv, ov = first
        print(f"first obs divergence: {tag} rqid={rqid} feature[{idx}] live={lv} offline={ov}")
    ok = not (obs_bad or mask_bad or key_bad) and n > 0
    print("\nOBS FIDELITY: " + ("PASS — offline replay reproduces live observations exactly"
                               if ok else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
