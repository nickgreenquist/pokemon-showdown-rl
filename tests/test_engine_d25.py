"""D25 opponent-action labels from the engine collector, through the REAL
canonicaliser (`rl.networks.opp_action.canonicalise`).

The label seam is `(kind, id, flags)` where `id` names an ENTITY — `_move_id` /
`_species_id`, the encoder's own tables — never a slot. Nothing downstream
asserts that: `canonicalise` matches the id against the row's own opponent-move
id suffix, and an id that names nothing simply lands in OTHER_MOVE. So the test
is a DISTRIBUTION test against a control that reproduces the failure exactly
(ids replaced by slot-shaped small integers), not a per-row assertion.

No server: `BatchEnv` is engine-only. Skips loudly without the built extension
or a team bank.
"""

from __future__ import annotations

import glob
import os
import pathlib
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")))

_CHILD = r"""
import json, pathlib, sys
sys.path.insert(0, "scripts")
import numpy as np
import torch
import pkmn_gen1
import engine_team_bank as bank
from rl.envs.engine_tables import build_tables
from rl.networks.entity_deepsets import EntityTokenizer
from rl.networks.opp_action import canonicalise, OTHER_MOVE, SWITCH

tables, _fp = build_tables()
_header, payload = bank.read_bank(pathlib.Path(sys.argv[1]))
K = 48
env = pkmn_gen1.BatchEnv(K, 909, tables, payload, "p1")
rng = np.random.default_rng(3)

episodes = []
for step in range(20000):
    acts = {}
    for who in ("learner", "opponent"):
        idx, _obs, mask, _m = env.pending(who)
        acts[who] = (idx, np.array([rng.choice(np.flatnonzero(m)) for m in mask], dtype=np.int64))
    li, la = acts["learner"]
    oi, oa = acts["opponent"]
    env.step(li.tolist(), la.tolist(), [0.0] * len(li), 0, oi.tolist(), oa.tolist())
    episodes.extend(env.drain_finished())
    if len(episodes) >= 400:
        break

obs = torch.from_numpy(np.concatenate([e["obs"] for e in episodes]))
choice = torch.from_numpy(np.concatenate([e["opp_choice"] for e in episodes])).long()
assert obs.shape[0] == choice.shape[0] and obs.shape[1] == 828

tok = EntityTokenizer(828, species_vocab=152, move_vocab=166, layout="gen1")
target, allow, valid, stats = canonicalise(obs, choice, tok)

# The CONTROL is the bug this test exists for: emit the choice's data field.
# Move slots are 1..4 and order slots 1..6, so every id lands in 1..=6 and the
# canonicaliser matches almost nothing.
ctl = choice.clone()
is_move = ctl[:, 0] == 1
ctl[is_move, 1] = torch.from_numpy(rng.integers(1, 5, int(is_move.sum())))
is_switch = ctl[:, 0] == 0
ctl[is_switch, 1] = torch.from_numpy(rng.integers(1, 7, int(is_switch.sum())))
c_target, _ca, c_valid, c_stats = canonicalise(obs, ctl, tok)

def slotted(t, v):
    v = v & (t < OTHER_MOVE)
    return float(v.sum()) / max(float((t != SWITCH).sum()), 1.0)

out = {
    "rows": int(obs.shape[0]),
    "present": stats["aux/label_present_frac"],
    "labelled": stats["aux/labelled_frac"],
    "aliased": stats["aux/aliased_frac"],
    "illegal": stats["aux/illegal_label_frac"],
    "collision": stats["aux/frame_collision_frac"],
    "switch": stats["aux/switch_frac"],
    "slotted": slotted(target, valid),
    "ctl_slotted": slotted(c_target, c_valid),
}
print(json.dumps(out))
"""


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_d25_labels_canonicalise_the_way_the_reference_env_intends():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD, BANKS[-1]],
        capture_output=True,
        text=True,
        timeout=1800,
        cwd=ROOT,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    import json

    s = json.loads(r.stdout.strip().splitlines()[-1])
    print(s)

    assert s["rows"] > 5000, s

    # An illegal label would put the target on a -1e8 logit and produce a ~1e8
    # CE term. The reference measures 0.0000 on all five tapes; so must we.
    assert s["illegal"] == 0.0, s
    # `canonicalise` asserts internally that no aliased row is valid; these two
    # say the aliased path is EXERCISED, not merely absent. The reference's
    # measured band across five tapes is 4.0%-10.3% of present rows.
    assert 0.01 < s["aliased"] < 0.20, s
    # Wait turns get the sentinel, so PRESENT is strictly below 1.
    assert 0.80 < s["present"] < 1.0, s
    assert s["labelled"] > 0.70, s
    assert s["collision"] < 0.02, s

    # THE DISCRIMINATOR. A move label that names a real move usually matches one
    # of the four opponent slots the row itself carries; a slot-shaped label
    # almost never does, and lands in OTHER_MOVE instead.
    assert s["slotted"] > 0.50, s
    assert s["ctl_slotted"] < 0.10, s
    assert s["slotted"] > 5 * s["ctl_slotted"], s
