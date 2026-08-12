"""D23 offline gates for the L2-toward-init lever (configs/showdown_sp_l2init12m.yaml).

R0-3 lives here: l2_init_decay=0.0 must be an EXACT no-op (bit-identical
parameters after several updates, no metric keys, no checkpoint rider), and
the lever's displacement is verified DETERMINISTICALLY —
theta_after = theta_step - group_lr * lambda * (theta_step - theta0) — rather
than statistically, plus a closed-form constant-gradient case.

R0-2b (state_dict keys identical between a 0.0 and a 0.02 build, actor
param_count 626,059 unchanged) and the R0-9 init-match assertion need the
828-dim encoder, so they run in a SUBPROCESS with both encoder env vars set
(test_entity_deepsets.py's pattern).
"""

import os
import subprocess
import sys

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent, _l2_init_covered, _ln_free_blocks
from rl.common.config import Config
from rl.train import _ensure_theta0

LAMBDA = 0.02  # the config's operative coefficient
LR = 1.0e-3


def _agent(l2_init_decay=0.0, seed=0, **overrides):
    """test_ppo.py's `_agent` shape: 3-dim flat obs, 2 actions, tiny MLP."""
    kwargs = dict(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(2),
        num_envs=2,
        device="cpu",
        lr=LR,
        gamma=0.99,
        gae_lambda=0.95,
        rollout_steps=4,
        epochs=2,
        minibatches=2,
        clip_eps=0.2,
        entropy_coef=0.01,
        value_coef=0.5,
        max_grad_norm=0.5,
        hidden_sizes=[8],
        l2_init_decay=l2_init_decay,
    )
    kwargs.update(overrides)
    torch.manual_seed(seed)
    return PPOAgent(**kwargs)


def _row(t, num_envs=2, terminated=False):
    """One batched transition row as the vector loop hands it over
    (test_ppo.py::_row, duplicated so a change there cannot silently retune
    this rung's synthetic data)."""
    obs = np.full((num_envs, 3), 0.1 * t, dtype=np.float32)
    next_obs = np.full((num_envs, 3), 0.1 * (t + 1), dtype=np.float32)
    actions = np.arange(num_envs) % 2
    rewards = np.ones(num_envs, dtype=np.float32)
    term = np.full(num_envs, terminated)
    trunc = np.zeros(num_envs, dtype=bool)
    masks = np.ones((num_envs, 2), dtype=bool)
    return (obs, actions, rewards, next_obs, term, trunc, masks, masks)


def _fill(agent, base=0):
    report = {}
    for t in range(agent.buffer.horizon):
        report = agent.update(_row(base + t))
    return report


def _flat(agent):
    return torch.cat([p.detach().flatten() for p in agent.params])


# --- validation + EXACT no-op ------------------------------------------------


def test_l2_init_decay_validates():
    with pytest.raises(ValueError, match="l2_init_decay"):
        _agent(l2_init_decay=-1e-9)


def test_zero_is_an_exact_no_op():
    """Same seed, same synthetic data, three update cycles: an explicit 0.0
    and the default (kwarg absent) must end bit-identical, with no anchors
    captured, no l2init/* keys and no checkpoint rider."""
    explicit = _agent(l2_init_decay=0.0)
    default = _agent()  # kwarg never passed
    torch.manual_seed(1)
    for cycle in range(3):
        _fill(explicit, base=4 * cycle)
    torch.manual_seed(1)
    for cycle in range(3):
        _fill(default, base=4 * cycle)
    assert torch.equal(_flat(explicit), _flat(default))
    assert explicit._theta0 == [] and explicit._l2_init_groups == []
    assert explicit.l2_init_metrics() == {}
    assert "theta0_hash" not in explicit.state_dict()


def test_metrics_present_iff_decay_is_on():
    off, on = _agent(0.0), _agent(LAMBDA)
    assert off.l2_init_metrics() == {}
    metrics = on.l2_init_metrics()
    # The MLP actor IS a Sequential, so its LN-free blocks are the numbered
    # layers; the entity trunk's named blocks (species_emb, ..., slot_bias)
    # are asserted in the subprocess gate below.
    assert set(metrics) == {
        "l2init/anchor_dist_0", "l2init/anchor_dist_2",
        "l2init/anchor_dist_actor_lnfree",
    }
    # At step 0 theta IS theta0.
    assert all(value == 0.0 for value in metrics.values())
    _fill(on)
    moved = on.l2_init_metrics()
    assert moved["l2init/anchor_dist_actor_lnfree"] > 0.0


# --- the deterministic lever tests -------------------------------------------


def test_decay_displacement_is_exactly_group_lr_times_lambda():
    """R0-3's deterministic criterion: with the optimizer step suppressed
    (zero task gradient), the ONLY motion is the anchor pull, and it must
    equal group_lr * lambda * (theta - theta0) elementwise."""
    agent = _agent(LAMBDA)
    # Displace the weights off theta0 so the pull has something to act on.
    with torch.no_grad():
        for param in agent.params:
            param.add_(torch.full_like(param, 0.25))
    before = [p.detach().clone() for p in agent.params]
    agent._apply_l2_init_decay()
    anchors = dict(zip((id(p) for p in agent.params), [None] * len(agent.params)))
    assert len(anchors) == len(agent.params)  # params are distinct tensors
    covered = {id(p): a for _, params, ancs, _ in agent._l2_init_groups
               for p, a in zip(params, ancs)}
    lrs = {id(p): group["lr"] for group, params, _, _ in agent._l2_init_groups
           for p in params}
    for param, prior in zip(agent.params, before):
        anchor = covered.get(id(param))
        if anchor is None:  # not covered (LayerNorm / frozen): must not move
            assert torch.equal(param.detach(), prior)
            continue
        expected = prior - lrs[id(param)] * LAMBDA * (prior - anchor)
        assert torch.allclose(param.detach(), expected, atol=1e-6, rtol=0.0)


def test_constant_gradient_closed_form_displacement():
    """A synthetic CONSTANT gradient through the real optimizer, one step:
    Adam's first step is exactly -lr * sign(g) (bias-corrected m/sqrt(v) = 1
    up to eps), and the decay then subtracts lr * lambda * (theta_step -
    theta0). Both terms are checked against the closed form, which pins the
    ORDER (decay after the step, on the post-step weights)."""
    agent = _agent(LAMBDA)
    theta0 = {id(p): a for _, params, ancs, _ in agent._l2_init_groups
              for p, a in zip(params, ancs)}
    start = [p.detach().clone() for p in agent.params]
    for param in agent.params:
        param.grad = torch.ones_like(param)
    agent.optimizer.step()
    stepped = [p.detach().clone() for p in agent.params]
    agent._apply_l2_init_decay()
    for param, prior, post_step in zip(agent.params, start, stepped):
        # Adam's very first step on a constant positive gradient.
        assert torch.allclose(post_step, prior - LR, atol=1e-6, rtol=0.0)
        anchor = theta0[id(param)]
        expected = post_step - LR * LAMBDA * (post_step - anchor)
        assert torch.allclose(param.detach(), expected, atol=1e-6, rtol=0.0)


def test_decay_uses_the_groups_current_lr():
    """The pull rides each param group's CURRENT lr, so it composes with
    actor_lr_scale and with the anneal instead of hardcoding base_lr."""
    agent = _agent(LAMBDA, actor_lr_scale=0.25)
    with torch.no_grad():
        for param in agent.params:
            param.add_(1.0)
    before = [p.detach().clone() for p in agent.params]
    agent.optimizer.param_groups[1]["lr"] = 0.5 * LR  # a half-annealed critic lr
    agent._apply_l2_init_decay()
    scales = {"actor": 0.25 * LR, "critic": 0.5 * LR}
    n_actor = len(agent.actor_params)
    for i, (param, prior) in enumerate(zip(agent.params, before)):
        lr = scales["actor" if i < n_actor else "critic"]
        anchor = prior - 1.0  # theta0 is exactly one below the displaced value
        assert torch.allclose(
            param.detach(), prior - lr * LAMBDA * (prior - anchor), atol=1e-9, rtol=0.0
        )


def test_grad_norm_and_clip_frac_are_untouched_by_the_lever():
    """Decoupled, not a loss term: the clip sees the task gradient alone.
    Read on the FIRST grad step (epochs=1, minibatches=1), the only one whose
    weights are identical between the two builds — from the second step on the
    lever has legitimately moved the parameters, so the curves diverge through
    the DATA, never through the clip pathway."""
    off = _agent(0.0, epochs=1, minibatches=1)
    on = _agent(LAMBDA, epochs=1, minibatches=1)
    torch.manual_seed(2)
    off_report = _fill(off)
    torch.manual_seed(2)
    on_report = _fill(on)
    for key in ("loss/grad_norm", "loss/clip_frac", "loss/grad_clip_frac",
                "loss/policy", "loss/value", "loss/entropy"):
        assert on_report[key] == off_report[key], key
    assert not torch.equal(_flat(on), _flat(off))  # the lever did land


# --- coverage predicate ------------------------------------------------------


def test_coverage_excludes_layernorm_includes_bare_parameters():
    from torch import nn

    net = nn.Module()
    net.block = nn.Sequential(nn.Linear(3, 4), nn.LayerNorm(4))
    net.norm = nn.LayerNorm(3)
    net.slot_bias = nn.Parameter(torch.zeros(5))
    names = [name for name, _ in _l2_init_covered(net)]
    assert names == ["slot_bias", "block.0.weight", "block.0.bias"]
    # LN-free blocks: the bare parameter, never the LN-terminated stack.
    assert _ln_free_blocks(net) == ["slot_bias"]


def test_frozen_params_are_skipped():
    """critic_warmup_updates freezes the actor with requires_grad=False — a
    TRUE freeze, so the anchor pull must not walk it either."""
    agent = _agent(LAMBDA, critic_warmup_updates=5)
    assert all(not p.requires_grad for p in agent.actor_params)
    # Frozen at capture: excluded from the covered set outright.
    assert all(name.startswith("critic.") for name in agent._theta0_names)
    assert agent._l2_init_blocks == []
    with torch.no_grad():
        for param in agent.params:
            param.add_(1.0)
    before = [p.detach().clone() for p in agent.actor_params]
    agent._apply_l2_init_decay()
    for param, prior in zip(agent.actor_params, before):
        assert torch.equal(param.detach(), prior)


# --- persistence: the rider, the file, the guards ----------------------------


def test_state_dict_rider_and_eval_side_load():
    """The digest rides in state_dict; a 0.0 agent (the eval-side rebuild's
    shape when the config is edited, and every pre-D23 loader) must load a
    checkpoint carrying it without crashing."""
    on = _agent(LAMBDA)
    state = on.state_dict()
    assert state["theta0_hash"] == on.theta0_hash()
    plain = _agent(0.0)
    plain.load_state_dict(state)  # rider ignored, not fatal
    assert torch.equal(_flat(plain), _flat(on))
    # And the same checkpoint loads into a lever-on agent whose own init
    # differs (the eval path never touches theta0).
    other = _agent(LAMBDA, seed=7)
    assert other.theta0_hash() != on.theta0_hash()
    other.load_state_dict(state)


def test_theta0_hash_is_deterministic_for_a_fixed_seed():
    assert _agent(LAMBDA, seed=44).theta0_hash() == _agent(LAMBDA, seed=44).theta0_hash()
    assert _agent(LAMBDA, seed=44).theta0_hash() != _agent(LAMBDA, seed=45).theta0_hash()


def _cfg(tmp_path, **overrides):
    return Config(
        env_id="CartPole-v1", seed=44, total_steps=16, eval_every=8,
        eval_episodes=1, run_name=tmp_path.name, **overrides,
    )


def test_training_path_writes_theta0_once_and_guards_resumes(tmp_path):
    agent = _agent(LAMBDA, seed=44)
    cfg = _cfg(tmp_path)
    _ensure_theta0(agent, tmp_path, cfg)
    path = tmp_path / "theta0.pt"
    assert path.exists()
    payload = torch.load(path, weights_only=False)
    assert payload["theta0_hash"] == agent.theta0_hash()
    assert len(payload["theta0"]) == len(agent._theta0_names)
    written = path.stat().st_mtime_ns

    # Same (seed, config) reconstruction: hash matches, file untouched.
    _ensure_theta0(_agent(LAMBDA, seed=44), tmp_path, cfg)
    assert path.stat().st_mtime_ns == written

    # A different init against the same run dir is a different experiment.
    with pytest.raises(ValueError, match="different initialization"):
        _ensure_theta0(_agent(LAMBDA, seed=45), tmp_path, cfg)

    # Anchors deleted under a run that already has checkpoints: raise rather
    # than silently re-anchor to a fresh init.
    path.unlink()
    (tmp_path / "checkpoint.pt").write_bytes(b"")
    with pytest.raises(FileNotFoundError, match="theta0.pt"):
        _ensure_theta0(_agent(LAMBDA, seed=44), tmp_path, cfg)


def test_theta0_guard_is_a_no_op_when_the_lever_is_off(tmp_path):
    """The EVAL path builds agents and loads checkpoints without ever seeing
    a run dir; the guard must never fire off the lever."""
    _ensure_theta0(_agent(0.0), tmp_path, _cfg(tmp_path))
    assert not (tmp_path / "theta0.pt").exists()


# --- R0-2b / R0-9 on the real 828-dim entity trunk (subprocess) --------------

_CHILD = r"""
import gymnasium as gym
import numpy as np
import torch

from rl.agents.ppo import PPOAgent
from rl.envs.showdown import OBS_DIM
from rl.common.seeding import set_seed

assert OBS_DIM == 828, OBS_DIM
TRUNK_KWARGS = dict(
    species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
    pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384],
)
KWARGS = dict(
    num_envs=8, device="cpu", lr=2.5e-4, gamma=1.0, gae_lambda=0.95,
    rollout_steps=128, epochs=4, minibatches=4, clip_eps=0.2,
    entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
    hidden_sizes=[512, 512], trunk="entity_deepsets", trunk_kwargs=TRUNK_KWARGS,
)


def build(l2_init_decay):
    set_seed(44)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
        l2_init_decay=l2_init_decay, **KWARGS,
    )


off, on = build(0.0), build(0.02)

# --- R0-2b: state_dict KEYS bit-identical, param counts unchanged -----------
assert list(off.actor.state_dict()) == list(on.actor.state_dict())
assert list(off.critic.state_dict()) == list(on.critic.state_dict())
assert set(off.state_dict()) | {"theta0_hash"} == set(on.state_dict())
assert on.actor.param_count == sum(p.numel() for p in on.actor.parameters()) == 626_059
assert on.critic.param_count == 494_849, on.critic.param_count
# theta0 is a plain list: nothing registered as a parameter or a buffer.
assert not any("theta0" in k for k in on.actor.state_dict())
assert list(on.actor.buffers()) == list(off.actor.buffers())

# --- R0-9 INIT-MATCH: same seed, with and without the lever -> identical ----
for a, b in ((off.actor, on.actor), (off.critic, on.critic)):
    for (ka, va), (kb, vb) in zip(a.state_dict().items(), b.state_dict().items()):
        assert ka == kb and torch.equal(va, vb), ka

# --- coverage on the real trunk ---------------------------------------------
covered = set(on._theta0_names)
ln_params = {
    f"{prefix}.{name}"
    for prefix, net in (("actor", on.actor), ("critic", on.critic))
    for module_name, module in net.named_modules()
    if isinstance(module, torch.nn.LayerNorm)
    for name, _ in ((f"{module_name}.{p}", q) for p, q in module.named_parameters(recurse=False))
}
allp = {
    f"{prefix}.{name}"
    for prefix, net in (("actor", on.actor), ("critic", on.critic))
    for name, _ in net.named_parameters()
}
assert covered == allp - ln_params, sorted(allp - ln_params - covered)
assert ln_params and not (covered & ln_params)
assert "actor.slot_bias" in covered            # bare Parameter, covered
assert "critic.head.weight" in covered
assert any(n.startswith("actor.mon_net.") for n in covered)   # LN-free params of an LN block

# --- the l2init/* namespace on the real actor -------------------------------
keys = set(on.l2_init_metrics())
assert keys == {
    "l2init/anchor_dist_species_emb", "l2init/anchor_dist_move_emb",
    "l2init/anchor_dist_ctx_net", "l2init/anchor_dist_scorer",
    "l2init/anchor_dist_slot_bias", "l2init/anchor_dist_actor_lnfree",
}, sorted(keys)
assert all(v == 0.0 for v in on.l2_init_metrics().values())
with torch.no_grad():
    on.actor.species_emb.weight.add_(1.0)
m = on.l2_init_metrics()
assert abs(m["l2init/anchor_dist_species_emb"] - (152 * 64) ** 0.5) < 1e-3, m
assert abs(m["l2init/anchor_dist_actor_lnfree"] - (152 * 64) ** 0.5) < 1e-3, m
assert not off.l2_init_metrics()
print("OK")
"""


def test_entity_trunk_gates_r02b_init_match_and_metric_namespace():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
