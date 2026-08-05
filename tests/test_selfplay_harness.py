"""Harness wiring for self-play: env_kwargs, make_eval_env, eval/win_rate,
the Config fields, and the checkpoint ladder.

Everything here defaults OFF, so the other half of each test is that Phases
0-3 are untouched: `selfplay` empty means `{}` env kwargs, `eval_win_rate`
False means the metric is never emitted, `checkpoint_every` 0 means no ladder.
"""

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.evaluation import evaluate
from rl.envs.make import make_eval_env, make_env, make_vec_env, selfplay_env_kwargs
from rl.selfplay.opponents import Opponent, RandomOpponent
from rl.train import make_agent, train

CONNECT4_AGENT = {
    "algo": "ppo",
    "hidden_sizes": [16],
    "lr": 2.5e-4,
    "gamma": 1.0,
    "gae_lambda": 0.95,
    "rollout_steps": 16,
    "epochs": 1,
    "minibatches": 2,
    "clip_eps": 0.2,
    "entropy_coef": 0.01,
    "value_coef": 0.5,
    "max_grad_norm": 0.5,
}


def connect4_config(**overrides):
    base = dict(
        env_id="Connect4-v0",
        seed=0,
        total_steps=256,
        eval_every=128,
        eval_episodes=4,
        run_name="test_c4",
        logger="tensorboard",
        num_envs=4,
        selfplay={"opponent": "random", "eval_opponent": "heuristic"},
        eval_win_rate=True,
        agent=dict(CONNECT4_AGENT),
    )
    base.update(overrides)
    return Config(**base)


# ------------------------------------------------------------- env_kwargs

def test_caller_env_kwargs_share_one_object_across_sub_envs():
    """Load-bearing for chunk 2: ONE pool object must be visible to all N
    sub-envs. gymnasium deep-copies the kwargs stored on a registered spec
    but not the caller's, so the pool must be passed at make time — and
    registering it would silently hand each sub-env a private copy, which
    is the counterfactual asserted below."""
    shared = RandomOpponent()
    vec = make_vec_env("Connect4-v0", 0, 4, env_kwargs={"opponent": shared})
    assert all(env.unwrapped.opponent_source is shared for env in vec.envs)

    gym.register(
        id="Connect4RegisteredKwargs-v0",
        entry_point="rl.envs.connect4:Connect4Env",
        kwargs={"opponent": shared},
    )
    copies = [gym.make("Connect4RegisteredKwargs-v0") for _ in range(4)]
    assert not any(env.unwrapped.opponent_source is shared for env in copies), (
        "gymnasium stopped deep-copying registered kwargs; chunk 2's pool "
        "sharing rests on this distinction"
    )


def test_connect4_registers_and_keeps_the_mask_contract():
    env = make_env("Connect4-v0", seed=0)
    obs, info = env.reset(seed=0)
    assert obs.shape == (2, 6, 7)
    # The ActionMask wrapper must pass the env's OWN mask through, not
    # overwrite it with all-True.
    assert "action_mask" in info
    env = make_env("Connect4-v0", seed=0, env_kwargs={"opponent": "heuristic"})
    from rl.selfplay.opponents import HeuristicOpponent

    assert isinstance(env.unwrapped.opponent_source, HeuristicOpponent)


def test_env_kwargs_default_to_nothing_for_every_other_config():
    cfg = Config(
        env_id="CartPole-v1", seed=0, total_steps=1, eval_every=1,
        eval_episodes=1, run_name="x", agent={"algo": "random"},
    )
    assert selfplay_env_kwargs(cfg, "opponent") == {}
    assert selfplay_env_kwargs(cfg, "eval_opponent") == {}
    make_eval_env(cfg).close()  # constructs exactly as before


def test_eval_env_uses_the_eval_opponent_not_the_training_one():
    from rl.selfplay.opponents import HeuristicOpponent

    cfg = connect4_config()
    assert selfplay_env_kwargs(cfg, "opponent") == {"opponent": "random"}
    env = make_eval_env(cfg)
    assert isinstance(env.unwrapped.opponent_source, HeuristicOpponent)


def test_missing_opponent_key_raises():
    cfg = connect4_config(selfplay={"opponent": "random"})
    with pytest.raises(ValueError, match="eval_opponent"):
        selfplay_env_kwargs(cfg, "eval_opponent")


# ----------------------------------------------------------- Config fields

def test_new_config_fields_default_off_and_are_not_shared():
    a = Config(env_id="CartPole-v1", seed=0, total_steps=1, eval_every=1,
               eval_episodes=1, run_name="a", agent={"algo": "random"})
    b = Config(env_id="CartPole-v1", seed=0, total_steps=1, eval_every=1,
               eval_episodes=1, run_name="b", agent={"algo": "random"})
    assert a.selfplay == {} and a.eval_win_rate is False and a.checkpoint_every == 0
    # field(default_factory=dict), not a shared mutable default.
    a.selfplay["x"] = 1
    assert b.selfplay == {}


# --------------------------------------------------------- eval/win_rate

class _FixedOutcomeEnv(gym.Env):
    """One-step env with a scripted outcome per episode."""

    def __init__(self, outcomes):
        self.action_space = gym.spaces.Discrete(2)
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (2,), np.float32)
        self.outcomes = outcomes
        self.i = -1

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.i += 1
        return np.zeros(2, np.float32), {"action_mask": np.ones(2, dtype=bool)}

    def step(self, action):
        outcome = self.outcomes[self.i % len(self.outcomes)]
        return (np.zeros(2, np.float32), float(outcome), True, False,
                {"action_mask": np.ones(2, dtype=bool), "outcome": outcome})


class _ConstantAgent:
    def act(self, obs, action_mask=None, deterministic=False):
        return 0


def test_win_rate_counts_wins_and_ignores_draws():
    env = _FixedOutcomeEnv([1, 1, 0, -1])  # 2 wins, 1 draw, 1 loss
    metrics = evaluate(_ConstantAgent(), env, episodes=4, win_rate=True)
    assert metrics["eval/win_rate"] == pytest.approx(0.5)
    assert metrics["eval/return_mean"] == pytest.approx(0.25)


def test_win_rate_survives_a_flipped_reward_sign():
    """The catch that paid for the spec review. `return > 0` reads the very
    reward a sign bug inverts, so it reports 1.000 under an inversion and
    passes its own detector at the ceiling. Reading info["outcome"] breaks
    the circularity."""

    class Flipped(gym.Wrapper):
        def step(self, action):
            obs, reward, term, trunc, info = self.env.step(action)
            return obs, -reward, term, trunc, info

    outcomes = [1, -1, -1, -1]  # a policy that wins 25% of its games
    clean = evaluate(_ConstantAgent(), _FixedOutcomeEnv(outcomes), 4, win_rate=True)
    flipped = evaluate(_ConstantAgent(), Flipped(_FixedOutcomeEnv(outcomes)), 4, win_rate=True)

    assert clean["eval/win_rate"] == pytest.approx(0.25)
    assert flipped["eval/win_rate"] == pytest.approx(0.25), "outcome must not follow the reward"
    # The return DOES flip — which is exactly what the rejected definition
    # would have read, turning a 25% policy into a reported 75%.
    assert clean["eval/return_mean"] == pytest.approx(-0.5)
    assert flipped["eval/return_mean"] == pytest.approx(0.5)


def test_win_rate_refuses_to_guess_when_the_env_supplies_no_outcome():
    """Scoring a missing outcome as a non-win would report a plausible wrong
    number, which is the whole failure mode this metric exists to avoid."""
    env = make_env("CartPole-v1", seed=0)

    class Greedy:
        def act(self, obs, action_mask=None, deterministic=False):
            return 0

    with pytest.raises(ValueError, match="no info"):
        evaluate(Greedy(), env, episodes=2, win_rate=True)


def test_win_rate_is_absent_unless_requested():
    env = _FixedOutcomeEnv([1])
    assert "eval/win_rate" not in evaluate(_ConstantAgent(), env, 2)


# ------------------------------------------------------- normalize guard

@pytest.mark.parametrize("flag", ["normalize_obs", "normalize_reward"])
def test_selfplay_with_normalizers_raises(tmp_path, monkeypatch, flag):
    """The normalizers wrap the VECTOR env while the opponent lives inside a
    sub-env beneath them, so the learner would act on z-scores while every
    frozen snapshot still acts on raw bools — the pool un-frozen by the back
    door, with no crash and no metric that looks wrong."""
    monkeypatch.chdir(tmp_path)
    cfg = connect4_config(**{flag: True})
    with pytest.raises(ValueError, match="selfplay is incompatible"):
        train(cfg)


# ----------------------------------------------------- checkpoint ladder

def test_ladder_writes_by_threshold_crossing_not_modulo(tmp_path, monkeypatch):
    """num_envs 4 with checkpoint_every 250: `step` advances in fours and
    lands on 250's multiples only at 500 and 1000, so `step % every == 0`
    writes 2 rungs where 4 were asked for."""
    monkeypatch.chdir(tmp_path)
    register_masked_dummy()
    cfg = Config(
        env_id="MaskedDummy-v0", seed=0, total_steps=1000, eval_every=1000,
        eval_episodes=1, run_name="ladder", logger="tensorboard", num_envs=4,
        checkpoint_every=250,
        agent={**CONNECT4_AGENT, "rollout_steps": 8, "gamma": 0.99},
    )
    train(cfg)
    rungs = sorted(p.name for p in (tmp_path / "runs" / "ladder").glob("ckpt_*.pt"))
    assert rungs == [
        "ckpt_000000252.pt",  # first step >= 250
        "ckpt_000000500.pt",
        "ckpt_000000752.pt",
        "ckpt_000001000.pt",
    ], rungs


def test_ladder_is_off_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    register_masked_dummy()
    cfg = Config(
        env_id="MaskedDummy-v0", seed=0, total_steps=200, eval_every=200,
        eval_episodes=1, run_name="noladder", logger="tensorboard", num_envs=4,
        agent={**CONNECT4_AGENT, "rollout_steps": 8, "gamma": 0.99},
    )
    train(cfg)
    assert list((tmp_path / "runs" / "noladder").glob("ckpt_*.pt")) == []


def register_masked_dummy():
    from tests.envs.masked_dummy import register

    register()


class _CheckpointOpponent(Opponent):
    """Adapter proving a ladder rung is consumable as a frozen opponent.

    Deliberately test-local: chunk 2 ships the real `AgentOpponent`, and the
    point here is only that chunk 1 did not pick a checkpoint FORMAT that
    chunk 3's tournament cannot load.
    """

    def __init__(self, agent):
        self.agent = agent

    def freeze(self):
        for net in (self.agent.actor, self.agent.critic):
            net.eval()
            for param in net.parameters():
                param.requires_grad_(False)

    def move(self, obs, mask, rng):
        return int(self.agent.act(obs, mask, deterministic=True))


def test_ladder_rung_round_trips_into_a_frozen_opponent(tmp_path, monkeypatch):
    """Acceptance is the round trip, not the file: a rung must load into a
    playable, frozen opponent using nothing but the checkpoint itself."""
    monkeypatch.chdir(tmp_path)
    cfg = connect4_config(total_steps=256, checkpoint_every=128, run_name="rt")
    train(cfg)
    rungs = sorted((tmp_path / "runs" / "rt").glob("ckpt_*.pt"))
    assert rungs, "no ladder rungs written"

    ckpt = load_checkpoint(rungs[0])
    restored_cfg = Config(**ckpt["config"])
    assert ckpt["step"] == int(rungs[0].stem.split("_")[1])
    # Built from the checkpoint alone, through the normal factory.
    env = make_eval_env(restored_cfg)
    agent = make_agent(restored_cfg, env)
    agent.load_state_dict(ckpt["agent"])

    opponent = _CheckpointOpponent(agent)
    opponent.freeze()
    assert not agent.actor.training and not agent.critic.training
    assert all(not p.requires_grad for p in agent.actor.parameters())

    # And it actually plays: the env raises on any illegal column.
    from rl.envs.connect4 import Connect4Env

    game = Connect4Env(opponent=opponent)
    rng = np.random.default_rng(0)
    for episode in range(5):
        obs, info = game.reset(seed=episode)
        done = False
        while not done:
            legal = np.flatnonzero(info["action_mask"])
            obs, _, done, _, info = game.step(int(rng.choice(legal)))

    # Weights survived the round trip bit-for-bit.
    fresh = make_agent(restored_cfg, env)
    fresh.load_state_dict(ckpt["agent"])
    for a, b in zip(agent.actor.parameters(), fresh.actor.parameters()):
        assert torch.equal(a, b)


# ------------------------------------------------------------ end to end

class _RecordingLogger:
    def __init__(self):
        self.records = []

    def log(self, metrics, step):
        self.records.append((step, dict(metrics)))

    def close(self):
        pass


def _record_metrics(monkeypatch):
    """Capture everything the train loop logs. Asserting on `evaluate()`
    alone is not enough: the metric can be computed correctly and simply
    never threaded into the call, which a mutation dropping
    `win_rate=cfg.eval_win_rate` proved was invisible."""
    logger = _RecordingLogger()
    monkeypatch.setattr("rl.train.make_logger", lambda cfg: logger)
    return logger


def test_win_rate_reaches_the_logger_when_enabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = _record_metrics(monkeypatch)
    train(connect4_config(run_name="wr_on"))
    keys = {key for _, metrics in logger.records for key in metrics}
    assert "eval/win_rate" in keys
    rates = [m["eval/win_rate"] for _, m in logger.records if "eval/win_rate" in m]
    assert rates and all(0.0 <= rate <= 1.0 for rate in rates)


def test_win_rate_is_absent_from_the_log_when_disabled(tmp_path, monkeypatch):
    """The no-op half: every pre-Phase-4 run logs exactly what it used to."""
    monkeypatch.chdir(tmp_path)
    logger = _record_metrics(monkeypatch)
    train(connect4_config(run_name="wr_off", eval_win_rate=False))
    keys = {key for _, metrics in logger.records for key in metrics}
    assert "eval/win_rate" not in keys
    assert "eval/return_mean" in keys


def _pool_selfplay(**overrides):
    base = {"opponent": "self", "eval_opponent": "heuristic",
            "pool_size": 4, "push_every_updates": 2, "latest_prob": 0.8}
    base.update(overrides)
    return base


def test_pool_mode_trains_end_to_end_and_the_pool_grows(tmp_path, monkeypatch):
    """The chunk-2 wiring, observed from the log: the step-0 push before the
    loop, then one push per push_every_updates rollouts. 256 steps at
    4 envs x 16 rollout_steps = 4 updates (steps 64/128/192/256), so
    push_every 2 lands pushes at 128 and 256."""
    monkeypatch.chdir(tmp_path)
    logger = _record_metrics(monkeypatch)
    train(connect4_config(run_name="pool", selfplay=_pool_selfplay()))
    sizes = [(step, m["selfplay/pool_size"])
             for step, m in logger.records if "selfplay/pool_size" in m]
    assert sizes == [(0, 1), (128, 2), (256, 3)]
    # Eval still runs against the fixed anchor and reports the metric of
    # record — under self-play the pool would score ~50% by construction.
    keys = {key for _, metrics in logger.records for key in metrics}
    assert "eval/win_rate" in keys


def test_pool_metric_is_absent_for_fixed_opponent_configs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    logger = _record_metrics(monkeypatch)
    train(connect4_config(run_name="fixed"))
    keys = {key for _, metrics in logger.records for key in metrics}
    assert "selfplay/pool_size" not in keys


def test_pool_mode_requires_the_pool_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = connect4_config(
        selfplay={"opponent": "self", "eval_opponent": "heuristic", "pool_size": 4}
    )
    with pytest.raises(ValueError, match="latest_prob"):
        train(cfg)


def test_pool_mode_needs_a_vectorized_algorithm(tmp_path, monkeypatch):
    """Snapshots push at rollout boundaries; the scalar loop has none, and
    silently accepting would train against the frozen step-0 snapshot
    forever while looking like self-play."""
    monkeypatch.chdir(tmp_path)
    cfg = connect4_config(agent={"algo": "random"}, selfplay=_pool_selfplay())
    with pytest.raises(ValueError, match="vectorized"):
        train(cfg)


def test_eval_opponent_self_raises_loudly(tmp_path, monkeypatch):
    """Only the TRAINING opponent string is replaced with the pool object.
    `eval_opponent: self` reaches make_opponent unreplaced and dies there —
    the guard that keeps eval pinned to a fixed external anchor."""
    monkeypatch.chdir(tmp_path)
    cfg = connect4_config(selfplay=_pool_selfplay(eval_opponent="self"))
    with pytest.raises(ValueError, match="unknown opponent"):
        train(cfg)


def test_connect4_trains_end_to_end_with_win_rate(tmp_path, monkeypatch):
    """PPO through the real vector loop on Connect 4: conv net selected by obs
    rank with no config key, varying masks, the opponent inside each sub-env,
    and eval scored against the fixed anchor. The env raises on any illegal
    column, so completing is most of the assertion."""
    monkeypatch.chdir(tmp_path)
    cfg = connect4_config()
    train(cfg)
    ckpt = load_checkpoint(tmp_path / "runs" / "test_c4" / "checkpoint.pt")
    assert ckpt["step"] == 256
    # The conv trunk was selected from the rank-3 observation, not a config key.
    assert any(key.startswith("trunk.0") for key in ckpt["agent"]["actor"])
