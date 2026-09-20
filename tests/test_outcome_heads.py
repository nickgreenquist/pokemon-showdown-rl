"""IDEAS 4.11 (R6 trio A), the HEADS-AND-LOSS half: `EntityDeepSetsNet(value_aux_out=3)`
on the critic, `forward_with_aux`, and `PPOAgent(aux_outcome_coef=0.1)`'s loss, seam
and metrics. The data path (`rl/envs/outcome_targets.py`, the collector's emission)
is tests/test_outcome_targets.py.

Everything touching the real trunk needs the 828-dim encoder, whose flags are read
at import, so it runs in ONE subprocess with both env vars set (the
test_ctx_layernorm pattern). Contracts pinned there:

1. DEFAULT IS AN EXACT NO-OP: no module, the critic 494,849 / actor 626,059 params,
   identical state_dict keys, and the global RNG stream untouched. The POLICY
   ignores the kwarg (trunk_kwargs are shared; the actor never grows).
2. ON: +3*384+3 params on the critic only; constructed under a rewound RNG and
   initialised from a dedicated generator, so every non-head weight AND the
   global stream after construction are bit-identical to the head-off build;
   `forward(x) == forward_with_aux(x)[0]` bitwise; the head init is reproducible.
3. PPOAgent refuses coef-without-head, head-without-coef, a negative coef, a
   non-entity trunk; the update seam refuses a batch missing/carrying targets
   against the agent's setting (naming both knobs); the sync update() refuses.
4. With both on: `loss/aux_outcome` and `aux_outcome/ev_<target>` are reported,
   finite, absent on the control, and the aux loss falls on repeated updates.
5. Checkpoints round-trip, and a head-on/head-off mismatch at load is refused
   with the lever's name (not torch's key error).
"""
import os
import subprocess
import sys

_CHILD = r"""
import gymnasium as gym
import numpy as np
import torch

from rl.agents.ppo import PPOAgent
from rl.envs.outcome_targets import TARGET_NAMES
from rl.envs.showdown import OBS_DIM
from rl.networks.entity_deepsets import ACTOR_PARAM_CEILING, EntityDeepSetsNet

assert OBS_DIM == 828, OBS_DIM
torch.set_num_threads(1)
KW = dict(species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
          pool="max", ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[384, 384])
HEAD = 3 * 384 + 3

# 1. default is an exact no-op
torch.manual_seed(0); c0 = EntityDeepSetsNet(828, 1, **KW); r0 = torch.rand(1)
torch.manual_seed(0); c_off = EntityDeepSetsNet(828, 1, value_aux_out=0, **KW); r_off = torch.rand(1)
assert c0.param_count == c_off.param_count == 494_849, (c0.param_count, c_off.param_count)
assert list(c0.state_dict()) == list(c_off.state_dict())
assert c0.aux_value_head is None and c0.value_aux_out == 0
assert torch.equal(r0, r_off)
a3 = EntityDeepSetsNet(828, 10, value_aux_out=3, **KW)
assert a3.param_count == 626_059 <= ACTOR_PARAM_CEILING, a3.param_count
assert a3.aux_value_head is None and a3.value_aux_out == 0, "the policy must ignore the kwarg"

# 2. on: the head, the rewound stream, the shared context pass
torch.manual_seed(0); c3 = EntityDeepSetsNet(828, 1, value_aux_out=3, **KW); r3 = torch.rand(1)
assert c3.param_count == 494_849 + HEAD, c3.param_count
assert torch.equal(r3, r0), "the head's construction moved the global RNG stream"
assert set(c3.state_dict()) - set(c0.state_dict()) == {"aux_value_head.weight", "aux_value_head.bias"}
for k, v in c0.state_dict().items():
    assert torch.equal(v, c3.state_dict()[k]), k
torch.manual_seed(1); c0.init_head(1.0); i0 = torch.rand(1)
torch.manual_seed(1); c3.init_head(1.0); i3 = torch.rand(1)
assert torch.equal(i0, i3), "init_head's head draws leaked into the global stream"
for k, v in c0.state_dict().items():
    assert torch.equal(v, c3.state_dict()[k]), k
assert c3.aux_value_head.weight.abs().sum() > 0 and torch.all(c3.aux_value_head.bias == 0)
torch.manual_seed(1); c3b = EntityDeepSetsNet(828, 1, value_aux_out=3, **KW); c3b.init_head(1.0)
assert torch.equal(c3.aux_value_head.weight, c3b.aux_value_head.weight), "head init not reproducible per seed"
x = torch.rand(4, 828)
with torch.no_grad():
    v, aux = c3.forward_with_aux(x)
    assert v.shape == (4, 1) and aux.shape == (4, 3), (v.shape, aux.shape)
    assert torch.equal(c3(x), v) and torch.equal(c0(x), v)
    assert torch.isfinite(aux).all()
for net, why in ((a3, "policy"), (c0, "headless critic")):
    try:
        net.forward_with_aux(x); raise SystemExit(f"{why} accepted forward_with_aux")
    except ValueError:
        pass
try:
    EntityDeepSetsNet(828, 1, value_aux_out=-1, **KW); raise SystemExit("negative value_aux_out accepted")
except ValueError:
    pass

# 3. PPOAgent seams
def agent(seed=0, **over):
    torch.manual_seed(seed)
    kw = dict(observation_space=gym.spaces.Box(-1.0, 4.0, (828,), np.float32),
              action_space=gym.spaces.Discrete(10), num_envs=1, device="cpu", lr=1e-3,
              gamma=1.0, gae_lambda=0.95, rollout_steps=64, epochs=2, minibatches=2,
              clip_eps=0.2, entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
              hidden_sizes=[512, 512], trunk="entity_deepsets", trunk_kwargs=dict(KW))
    kw.update(over)
    return PPOAgent(**kw)
ON = dict(aux_outcome_coef=0.1, trunk_kwargs={**KW, "value_aux_out": 3})
for bad in (dict(aux_outcome_coef=0.1), dict(trunk_kwargs={**KW, "value_aux_out": 3}),
            dict(aux_outcome_coef=-0.1)):
    try:
        agent(**bad); raise SystemExit(f"accepted {bad}")
    except ValueError as e:
        assert "outcome" in str(e) or ">= 0" in str(e), str(e)
try:
    agent(aux_outcome_coef=0.1, trunk="mlp", trunk_kwargs={"value_aux_out": 3})
    raise SystemExit("mlp trunk accepted the lever")
except ValueError as e:
    assert "entity_deepsets" in str(e), str(e)
plain = agent(); on = agent(**ON)
assert on.critic.param_count == plain.critic.param_count + HEAD
assert on.actor.param_count == plain.actor.param_count == 626_059
for net in ("actor", "critic"):
    for k, v in getattr(plain, net).state_dict().items():
        assert torch.equal(v, getattr(on, net).state_dict()[k]), (net, k)
torch.manual_seed(0); agent(); s_plain = torch.rand(1)
torch.manual_seed(0); agent(**ON); s_on = torch.rand(1)
assert torch.equal(s_plain, s_on), "the lever moved the post-construction RNG stream"

# 4. the update seam, the metrics, the learning
def episodes(lengths, seed=0, targets=True):
    rng = np.random.default_rng(seed); total = int(sum(lengths))
    obs = rng.random((total, 828), dtype=np.float32)
    masks = np.ones((total, 10), dtype=np.bool_); masks[:, 0] = rng.random(total) > 0.5
    actions = np.array([rng.choice(np.flatnonzero(m)) for m in masks], dtype=np.int64)
    rewards = np.zeros(total, dtype=np.float32); ends = np.cumsum(lengths) - 1
    outcomes = rng.choice([-1.0, 1.0], size=len(lengths)); rewards[ends] = outcomes
    b = {"obs": obs, "masks": masks, "actions": actions, "rewards": rewards,
         "old_logp": np.zeros(total, np.float32), "version": np.zeros(total, np.int64),
         "lengths": np.asarray(lengths, np.int64)}
    if targets:
        rows = [np.tile(rng.random(3).astype(np.float32) * (1.0 if o > 0 else -1.0), (L, 1))
                for L, o in zip(lengths, outcomes)]
        b["outcome_targets"] = np.concatenate(rows).astype(np.float32)
    return b
def with_logp(ag, b):
    with torch.no_grad():
        b["old_logp"] = ag._logp_entropy(torch.as_tensor(b["obs"]), torch.as_tensor(b["actions"]),
                                         torch.as_tensor(b["masks"]))[0].numpy().astype(np.float32)
    return b
lengths = [6, 5, 7, 4, 6, 4]
try:
    on.update_episodes(with_logp(on, episodes(lengths, targets=False)), steps_seen=0)
    raise SystemExit("head-on agent accepted a batch without targets")
except ValueError as e:
    assert "collector.outcome_targets" in str(e) and "aux_outcome_coef" in str(e), str(e)
try:
    plain.update_episodes(with_logp(plain, episodes(lengths, targets=True)), steps_seen=0)
    raise SystemExit("head-off agent accepted targets")
except ValueError as e:
    assert "aux_outcome_coef" in str(e), str(e)
b = with_logp(on, episodes(lengths))
m = on.update_episodes(b, steps_seen=0)
want = {"loss/aux_outcome"} | {f"aux_outcome/ev_{n}" for n in TARGET_NAMES}
assert want <= set(m), sorted(m)
assert all(np.isfinite(m[k]) for k in want), {k: m[k] for k in want}
control = plain.update_episodes(with_logp(plain, episodes(lengths, targets=False)), steps_seen=0)
assert set(control).isdisjoint(want), sorted(set(control) & want)
first = m["loss/aux_outcome"]
for _ in range(8):
    last = on.update_episodes(b, steps_seen=0)["loss/aux_outcome"]
assert last < first, (first, last)
bad_w = dict(b); bad_w["outcome_targets"] = b["outcome_targets"][:, :2]
try:
    on.update_episodes(bad_w, steps_seen=0); raise SystemExit("a 2-wide target block was accepted")
except ValueError as e:
    assert "value_aux_out" in str(e), str(e)

# 5. the sync path refuses; checkpoints round-trip; mismatches are named
try:
    on.update(None); raise SystemExit("update() accepted the lever")
except ValueError as e:
    assert "update_episodes" in str(e), str(e)
sd = on.state_dict()
assert "aux_value_head.weight" in sd["critic"]
fresh = agent(seed=5, **ON); fresh.load_state_dict(sd)
assert torch.equal(fresh.critic.aux_value_head.weight, on.critic.aux_value_head.weight)
try:
    agent(seed=6).load_state_dict(sd); raise SystemExit("head-on ckpt loaded into a head-off agent")
except ValueError as e:
    assert "outcome-head mismatch" in str(e), str(e)
try:
    fresh.load_state_dict(plain.state_dict()); raise SystemExit("head-off ckpt loaded into a head-on agent")
except ValueError as e:
    assert "outcome-head mismatch" in str(e), str(e)
print("OK")
"""


def test_outcome_heads_default_noop_gated_on_seams_and_learning():
    result = subprocess.run(
        [sys.executable, "-c", _CHILD],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, result.stderr[-4000:]
    assert result.stdout.strip().endswith("OK"), result.stdout[-2000:]
