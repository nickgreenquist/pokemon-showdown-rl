"""BI-G4-4 — the clone leg's format threading (scripts/make_bc_dataset.py,
scripts/tape_to_dataset.py, scripts/train_bc.py, scripts/eval_checkpoint.py)
and the gen-4 recorder (rl/envs/gen4/env.py::Gen4RecordingPlayer). Offline:
the teacher-id normalisation measured on the first gen-4 Foul Play tape,
the recorder's encode on a fixture battle, train_bc's encoder dispatch off a
dataset's `gen` stamp, and eval_checkpoint's gen-4 loader on a checkpoint
written by the real save path. The live chain (tape -> gates -> clone ->
eval) ran 2026-09-05 on a 3-battle FP@20 tape: 53/53 rows, GATES PASS.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
from poke_env.data import GenData

from rl.common.checkpoint import load_checkpoint, save_checkpoint
from rl.common.config import Config
from rl.envs.gen4.encoder import embed_battle_gen4
from rl.envs.gen4.env import Gen4RecordingPlayer, fake_spaces_gen4
from rl.envs.gen4.tape import replay_tape
from rl.envs.gen4.tracker import BattleTracker
from rl.train import make_agent

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
_FIXTURE = _ROOT / "tests/fixtures/gen4_tape_t0_2battles.jsonl.gz"


def test_teacher_move_id_strips_fp_power_suffixes_only():
    from tape_to_dataset import teacher_move_id

    assert teacher_move_id("hiddenpowerfighting70") == "hiddenpowerfighting"
    assert teacher_move_id("hiddenpowerflying70") == "hiddenpowerflying"
    assert teacher_move_id("return102") == "return"
    assert teacher_move_id("frustration102") == "frustration"
    assert teacher_move_id("hiddenpower") == "hiddenpower"
    assert teacher_move_id("shadowball") == "shadowball"
    assert teacher_move_id("Ice Beam") == "icebeam"
    assert teacher_move_id("uturn") == "uturn"          # no digit suffix, untouched
    assert teacher_move_id("v-create") == "vcreate"


def test_gen4_recording_player_encodes_through_the_tracker():
    player = Gen4RecordingPlayer(expert="heuristics", start_listening=False)
    assert player._trackers == {}
    tc = GenData.from_gen(4).type_chart
    trackers, n = {}, 0

    def on_decision(battle, request, seat):
        nonlocal n
        # The battle object mutates as the replay continues, so both encodes
        # happen HERE, at the same state: the recorder's (its own per-tag
        # tracker) against a reference tracker replaying the same log.
        key = (seat, battle.battle_tag)
        want = embed_battle_gen4(battle, tc, trackers.setdefault(key, BattleTracker()))
        obs = player._encode(battle)
        assert obs.shape == (1448,) and obs.dtype == np.float32
        assert np.array_equal(obs, want)
        assert np.array_equal(player._encode(battle), obs)  # idempotent per decision
        n += 1

    replay_tape(_FIXTURE, on_decision)
    assert n == 130
    # One tracker per battle TAG (the two seats of a room share a tag).
    assert len(player._trackers) == 2


def test_train_bc_dispatches_on_the_gen_stamp():
    from train_bc import _encoder_for

    g1 = _encoder_for({"obs": np.zeros((1, 612))})  # no stamp: gen 1
    assert g1["gen"] == 1 and g1["env_id"] == "Showdown-v0" and len(g1["reveal_offsets"]) == 6
    g4 = _encoder_for({"gen": np.int64(4)})
    assert g4["gen"] == 4 and g4["env_id"] == "ShowdownGen4-v0" and g4["obs_dim"] == 1448
    assert g4["fingerprint"]["layout"] == "v0.1"
    # The revealed flag of opponent mon i sits at opp_mons_off + i * 62.
    from rl.envs.gen4.spec import LAYOUT

    assert g4["reveal_offsets"] == [LAYOUT.opp_mons_off + i * 62 for i in range(6)]


def test_eval_checkpoint_loads_a_gen4_checkpoint_and_pairs_a_gen4_opponent(tmp_path):
    from eval_checkpoint import _load_showdown_agent, _opponent_from_checkpoint

    cfg = Config(
        env_id="ShowdownGen4-v0", seed=0, total_steps=0, eval_every=0, eval_episodes=100,
        run_name="g4", logger="tensorboard", eval_win_rate=True,
        selfplay={"opponent": "heuristics", "eval_opponent": "heuristics"},
        agent={"algo": "ppo", "hidden_sizes": [8], "lr": 1e-3, "gamma": 1.0, "gae_lambda": 0.95,
               "rollout_steps": 4, "epochs": 1, "minibatches": 1, "clip_eps": 0.2,
               "entropy_coef": 0.01, "value_coef": 0.5, "max_grad_norm": 0.5},
    )
    obs_space, act_space = fake_spaces_gen4()
    torch.manual_seed(0)
    agent = make_agent(cfg, SimpleNamespace(observation_space=obs_space, action_space=act_space))
    path = tmp_path / "ckpt.pt"
    save_checkpoint(path, agent, 0, cfg)
    ckpt = load_checkpoint(path)
    loaded = _load_showdown_agent(ckpt, Config(**ckpt["config"]))
    for a, b in zip(agent.actor.parameters(), loaded.actor.parameters()):
        assert torch.equal(a, b)
    assert loaded.actor[0].in_features == 1448
    player, env_id = _opponent_from_checkpoint(str(path), seed=3)
    assert env_id == "ShowdownGen4-v0" and player.format == "gen4randombattle"
    assert type(player).__name__ == "Gen4PoolPlayer"
