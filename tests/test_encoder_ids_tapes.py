"""R0-5 of configs/showdown_sp_struct12m.yaml — embedding-id sanity on REAL
recorded gen1randombattle protocol (offline, on tapes).

Replays the same two Foul-Play collection tapes test_hl_shaping_tapes.py
uses, through poke-env's own parser (scripts/tape_to_dataset.py's replay,
inlined lean), and at every rqid-aligned decision encodes the battle with
the id suffix ON and asserts:

  - every id value round-trips EXACTLY (encode -> x*256 is already integral
    -> id), for >= 5000 decisions;
  - own-team species ids are all known (a 0 would mean a dex-mapping hole);
  - unrevealed opponent slots encode id 0, revealed ones their dex number;
  - a revealed opponent mon's id is STABLE across consecutive decisions of
    the same battle (reveal order is append-only, so slot i keeps its mon).

The encoder flags are read at import, so the replay runs in a subprocess
with both env vars set. Tapes are local collection artifacts (gitignored);
the test skips loudly where they are absent — R0-5 must run and pass on the
training box before the Rung 2 launch.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# The hl-shaping pair alone carries only ~2,300 decisions; the >= 5000 gate
# needs the wider collection corpus (fp_tapes_all is the 6-lane P4 set).
TAPES = [
    Path("data/fp_tapes2/run_92564.jsonl"),
    Path("data/fp_tapes/run_90336.jsonl"),
    Path("data/fp_tapes3/run_98827.jsonl"),
    Path("data/fp_tapes_all/run_4106.jsonl"),
    Path("data/fp_tapes_all/run_4115.jsonl"),
    Path("data/fp_tapes_all/run_4121.jsonl"),
]

_CHILD = r"""
import json
import logging
import sys

import numpy as np
from poke_env.battle import Battle
from poke_env.data import GenData

from rl.envs.showdown import ID_DIM, OBS_DIM, embed_battle, _species_id

assert OBS_DIM == 828 and ID_DIM == 20, (OBS_DIM, ID_DIM)

MESSAGES_TO_IGNORE = {"t:", "expire", "uhtmlchange"}
LOGGER = logging.getLogger("tape_replay")
LOGGER.addHandler(logging.NullHandler())
TYPE_CHART = GenData.from_gen(1).type_chart
TARGET = 6000  # stop early once the >= 5000 gate has margin


def iter_events(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def infer_username(path):
    for ev in iter_events(path):
        if ev["k"] != "m":
            continue
        for line in ev["v"].split("\n"):
            parts = line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser" and parts[2].strip():
                name = parts[2].strip()
                if not name.lower().startswith("guest "):
                    return name
    return None


def apply_message(battle, raw, state):
    for line in raw.split("\n")[1:]:
        sm = line.split("|")
        if len(sm) <= 1:
            continue
        tag = sm[1]
        if tag == "":
            battle.parse_message(sm)
        elif tag in MESSAGES_TO_IGNORE:
            continue
        elif tag == "request":
            if len(sm) > 2 and sm[2]:
                req = json.loads(sm[2])
                battle.parse_request(req)
                state["request"] = req
        elif tag == "win":
            battle.won_by(sm[2])
        elif tag == "tie":
            battle.tied()
        elif tag in ("error", "bigerror"):
            continue
        else:
            battle.parse_message(sm)


decisions = 0
for path in sys.argv[1:]:
    username = infer_username(path)
    assert username, path
    battles, states, seen_opp = {}, {}, {}
    for ev in iter_events(path):
        if decisions >= TARGET:
            break
        if ev["k"] == "m":
            head = ev["v"].split("\n", 1)[0]
            if not head.startswith(">battle-"):
                continue
            room = head[1:]
            if room not in battles:
                battles[room] = Battle(room, username, LOGGER, gen=1)
                states[room] = {"request": None}
                seen_opp[room] = [0] * 6
            try:
                apply_message(battles[room], ev["v"], states[room])
            except Exception:
                states[room]["request"] = None  # poisoned: skip its decisions
            continue
        room = ev["tag"]
        if room not in battles:
            continue
        req = states[room]["request"]
        if req is None or req.get("rqid") != ev.get("rqid"):
            continue
        battle = battles[room]
        vec = embed_battle(battle, TYPE_CHART)
        block = vec[OBS_DIM - ID_DIM :].astype(np.float64) * 256.0
        assert (block == np.round(block)).all(), block  # exact, not a tolerance
        ids = np.round(block).astype(int)
        team = list(battle.team.values())[:6]
        assert ids[:6].tolist() == [_species_id(m.species) for m in team]
        assert all(i > 0 for i in ids[:6]), ids[:6]
        opp = list(battle.opponent_team.values())[:6]
        assert ids[6:12].tolist() == (
            [_species_id(m.species) for m in opp] + [0] * (6 - len(opp))
        )
        prev = seen_opp[room]
        for i, v in enumerate(ids[6:12]):
            if prev[i]:
                assert v == prev[i], (room, i, prev[i], v)  # slot stability
            elif v:
                prev[i] = int(v)
        assert (0 <= ids[12:]).all() and (ids[12:] <= 165).all()
        decisions += 1

assert decisions >= 5000, f"only {decisions} decisions checked"
print(f"OK {decisions}")
"""


@pytest.mark.skipif(
    not all(t.exists() for t in TAPES),
    reason="local FP tapes absent — R0-5 must run on the training box",
)
def test_r05_id_block_round_trips_on_recorded_battles():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, *[str(t) for t in TAPES]],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().startswith("OK")
