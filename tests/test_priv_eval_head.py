"""DESIGN B: a separate PRIVILEGED EVALUATOR HEAD beside the ordinary critic
(`agent.priv_eval_coef`, docs/proposals/privileged_critic_engine_route.md
§4.3(B)).

The head regresses the SAME value targets the critic does, on the SAME rows,
from obs || the privileged block — and it feeds NOTHING. It exists to be the
search leaf evaluator later, and to ride as arm B of the 100M monster. The
property that makes it worth building is that D18's falsifier fired on the
ADVANTAGE channel, and this head never touches that channel.

THE EMITTER AND THE TWO CONSUMERS ARE INDEPENDENT KEYS, and most of this file
exists to hold that apart:

    privileged_dim   D18 / design A — `self.critic` widens, so the block enters
                     the advantage channel. Untouched by this work.
    priv_eval_dim    design B — only `priv_eval_head` reads the block; the
                     critic stays exactly the D18-free critic.

Either makes the collector emit (`PPOAgent.privileged_block_dim`, which is what
rl/train.py hands the engine collector). A design-B lane sets the second and
leaves the first absent.

Four things are tested, in order of what would hurt most if it broke:

1. THE DEFAULT IS AN EXACT NO-OP. `priv_eval_coef=0.0` passed explicitly is
   bit-identical to not passing it: no module, no optimizer group, no metric
   key, no checkpoint rider (in-process, MLP trunk — the flag needs no encoder).
2. NO LEAKAGE, against a PLAIN control with no privileged keys at all. The
   actor's and the critic's INITIAL weights are bit-identical, and so are their
   parameters after twenty updates and every shared metric to the last float.
   That is stronger than "the gradients are disjoint": the head is constructed
   after both nets AND rewinds the global RNG stream, so the minibatch
   permutations match too. (Contrast `privileged_dim`, which re-rolls the actor
   at a fixed seed — the disclosed residue in tests/test_privileged_aux_seam.py.)
3. THE HEAD ACTUALLY LEARNS. Its loss falls and its explained variance rises
   over those twenty updates while the critic's numbers are frozen by (2).
4. THE CHECKPOINT CARRIES IT, both ways: a head-on checkpoint refuses to load
   into a head-off agent, and a head-off checkpoint still loads into a head-on
   one.

(2)-(4) need the 828 tokenizer, so they run in a subprocess with both encoder
env vars (the test_privileged_critic.py pattern).
"""

import os
import subprocess
import sys

import gymnasium as gym
import numpy as np
import pytest
import torch

from rl.agents.ppo import PPOAgent

# --- 1. the default is an exact no-op (in-process, no encoder needed) --------


def _mlp_agent(**kw):
    torch.manual_seed(0)
    return PPOAgent(
        observation_space=gym.spaces.Box(-1.0, 1.0, (3,), np.float32),
        action_space=gym.spaces.Discrete(2),
        num_envs=2, device="cpu", lr=1.0e-3, gamma=0.99, gae_lambda=0.95,
        rollout_steps=4, epochs=2, minibatches=2, clip_eps=0.2,
        entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5, hidden_sizes=[8],
        **kw,
    )


def _rows(t, num_envs=2, terminated=False):
    obs = np.full((num_envs, 3), 0.1 * t, dtype=np.float32)
    next_obs = np.full((num_envs, 3), 0.1 * (t + 1), dtype=np.float32)
    actions = np.arange(num_envs) % 2
    rewards = np.ones(num_envs, dtype=np.float32)
    term = np.full(num_envs, terminated)
    trunc = np.zeros(num_envs, dtype=bool)
    masks = np.ones((num_envs, 2), dtype=bool)
    return (obs, actions, rewards, next_obs, term, trunc, masks, masks)


def _drive(agent):
    out = []
    for t in range(4):
        out.append(agent.update(_rows(t, terminated=t == 3)))
    return out


def test_the_new_keys_at_zero_are_an_exact_no_op():
    absent = _mlp_agent()
    passed = _mlp_agent(priv_eval_coef=0.0, priv_eval_max_grad_norm=0.5)

    assert absent.priv_eval_head is None and passed.priv_eval_head is None
    assert absent.priv_eval_params == [] and passed.priv_eval_params == []
    assert absent._priv_eval_group == -1 and passed._priv_eval_group == -1
    # No third param group, no rider key, no metric key.
    assert len(absent.optimizer.param_groups) == len(passed.optimizer.param_groups) == 2
    assert "priv_eval_head" not in absent.state_dict()
    assert "priv_eval_head" not in passed.state_dict()

    for p, q in zip(absent.actor.parameters(), passed.actor.parameters()):
        assert torch.equal(p, q)
    for p, q in zip(absent.critic.parameters(), passed.critic.parameters()):
        assert torch.equal(p, q)

    # REBUILT BEFORE EACH DRIVE, not driven back to back. `_optimize`'s epoch
    # loop draws its minibatch permutation from the GLOBAL torch generator, so
    # running one agent's four updates leaves the stream somewhere else and the
    # second agent would shuffle differently for a reason that has nothing to do
    # with the flag. `_mlp_agent` re-seeds, so each drive starts from the same
    # state. (The same hazard is why the head's construction rewinds the stream
    # — see the subprocess test below.)
    absent = _mlp_agent()
    m_absent = _drive(absent)
    passed = _mlp_agent(priv_eval_coef=0.0, priv_eval_max_grad_norm=0.5)
    m_passed = _drive(passed)
    assert m_absent == m_passed          # every float, every update
    assert not any(k.startswith("priv_eval") for m in m_passed for k in m)
    assert not any("priv_eval" in k for m in m_passed for k in m)
    for p, q in zip(absent.actor.parameters(), passed.actor.parameters()):
        assert torch.equal(p, q)
    for p, q in zip(absent.critic.parameters(), passed.critic.parameters()):
        assert torch.equal(p, q)


def test_the_head_refuses_the_configurations_it_cannot_serve():
    with pytest.raises(ValueError, match="priv_eval_coef must be"):
        _mlp_agent(priv_eval_coef=-1.0)
    with pytest.raises(ValueError, match="priv_eval_dim must be"):
        _mlp_agent(priv_eval_dim=-1)
    # No block width at all: the head has no input.
    with pytest.raises(TypeError, match="requires a privileged block width"):
        _mlp_agent(priv_eval_coef=0.5)
    # A width with no coefficient would make the collector emit a block nothing
    # trains on — the loud-seam rule, both directions.
    with pytest.raises(ValueError, match="emit a block nothing trains on"):
        _mlp_agent(priv_eval_dim=5)
    # One block, two possible consumers: the widths cannot disagree.
    with pytest.raises(ValueError, match="ONE privileged block"):
        _mlp_agent(priv_eval_dim=5, privileged_dim=7, priv_eval_coef=0.5)
    # The MLP trunk cannot re-tokenise the block as entities. Both spellings of
    # "give the head a width" reach the same refusal.
    with pytest.raises(TypeError, match="entity_deepsets"):
        _mlp_agent(priv_eval_coef=0.5, priv_eval_dim=5)
    with pytest.raises(TypeError, match="entity_deepsets"):
        _mlp_agent(priv_eval_coef=0.5, privileged_dim=5)
    with pytest.raises(ValueError, match="priv_eval_max_grad_norm"):
        _mlp_agent(priv_eval_max_grad_norm=0.0)


def test_the_emit_flag_is_derived_from_whichever_consumer_is_on():
    """`privileged_block_dim` is what rl/train.py hands the engine collector.
    EITHER consumer turns emission on; only `privileged_dim` widens the
    critic."""
    assert _mlp_agent().privileged_block_dim == 0
    a = _mlp_agent(privileged_dim=5)                       # design A
    assert a.privileged_block_dim == 5 and a.priv_eval_dim == 0
    assert a.buffer.privs is not None
    plain = _mlp_agent()
    assert plain.buffer.privs is None


def test_priv_eval_value_refuses_an_agent_without_the_head():
    with pytest.raises(ValueError, match="priv_eval_coef = 0"):
        _mlp_agent().priv_eval_value(np.zeros((1, 3), np.float32), np.zeros((1, 5), np.float32))


# --- 2-4. the head itself (828 entity trunk, subprocess) ---------------------

_PREAMBLE = r"""
import gymnasium as gym
import numpy as np
import torch

from rl.agents.ppo import PPOAgent
from rl.envs.showdown import OBS_DIM, PRIV_DIM

assert OBS_DIM == 828 and PRIV_DIM == 408, (OBS_DIM, PRIV_DIM)

TK = dict(species_vocab=152, move_vocab=166, embed_dim=16, entity_dim=32,
          pool="max", ctx_sizes=[64], scorer_sizes=[64], value_sizes=[64])
# gae_lambda 1.0 AT gamma 1.0 ON PURPOSE: GAE then telescopes to R_t - V(s_t),
# so `flat_targets = advantages + values` is the Monte-Carlo return and does NOT
# move as the critic learns. The head's regression target is therefore fixed
# across the twenty updates and "the loss falls" means the head fit something.
# SINCE 2026-09-10 the head regresses `flat_priv_targets` -- the lam=1 return --
# at EVERY lambda, so this fixture is no longer the only setting where its
# target is the MC return. It is kept at 1.0 anyway so `flat_targets` and
# `flat_priv_targets` coincide and this file's other assertions stay readable;
# `test_the_heads_target_is_the_mc_return_at_every_lambda` is what pins the
# production setting (lam 0.95), where the two DIFFER.
KW = dict(num_envs=2, device="cpu", lr=1.0e-3, gamma=1.0, gae_lambda=1.0,
          rollout_steps=8, epochs=2, minibatches=2, clip_eps=0.2,
          entropy_coef=0.01, value_coef=0.5, max_grad_norm=0.5,
          hidden_sizes=[64, 64], trunk="entity_deepsets", trunk_kwargs=TK)


def build(**kw):
    # Re-seeded per build, so two builds leave the global stream in the SAME
    # place (the head's construction rewinds it) and the epoch loops that
    # follow draw identical minibatch permutations. NOTE: no privileged_dim —
    # design B alone, so `self.critic` is the ordinary D18-free critic.
    torch.manual_seed(0)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
        **KW, **kw,
    )


def make_batch(n_eps=6, ep_len=12, seed=5):
    g = np.random.default_rng(seed)
    n = n_eps * ep_len
    obs = (g.random((n, 828)) * 2 - 0.5).astype(np.float32)
    obs[:, 808:] = (g.integers(0, 150, (n, 20)) / 256.0).astype(np.float32)
    lengths = np.full(n_eps, ep_len, dtype=np.int64)
    rewards = np.zeros(n, dtype=np.float32)
    rewards[np.cumsum(lengths) - 1] = g.choice([-1.0, 1.0], n_eps)
    return {
        "obs": obs,
        "masks": np.ones((n, 10), dtype=bool),
        "actions": g.integers(0, 10, n).astype(np.int64),
        "rewards": rewards,
        "old_logp": np.full(n, -np.log(10.0), dtype=np.float32),
        "version": np.zeros(n, dtype=np.int64),
        "lengths": lengths,
        # The privileged block correlates with the outcome, so there is
        # something for the head to find that the plain obs does not carry.
        "privileged": (
            g.random((n, PRIV_DIM)) * 0.1
            + np.repeat(rewards[np.cumsum(lengths) - 1], ep_len)[:, None]
        ).astype(np.float32),
    }


def run(agent, batch, n=20):
    return [agent.update_episodes(batch, steps_seen=0) for _ in range(n)]
"""


_ISOLATION_CHILD = _PREAMBLE + r"""
batch = make_batch()
# THE CONTROL IS A PLAIN RUN — no privileged keys at all, so its batch carries
# no block either. That is the comparison that matters: not "design B against
# design A", but "design B against the recipe as it ships".
plain = {k: v for k, v in batch.items() if k != "privileged"}

off = build()                                   # NO privileged keys at all
m_off = run(off, plain)
on = build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
m_on = run(on, batch)

# --- structure --------------------------------------------------------------
assert off.priv_eval_head is None and on.priv_eval_head is not None
assert off.privileged_block_dim == 0 and on.privileged_block_dim == PRIV_DIM
assert len(off.optimizer.param_groups) == 2
assert len(on.optimizer.param_groups) == 3 and on._priv_eval_group == 2
# DESIGN A IS OFF. The critic that produces advantages is the ordinary one:
# same privileged_dim 0, same 5-slot ctx, same parameter count as the control's.
assert on.privileged_dim == 0
assert on.critic.privileged_dim == 0
assert on.critic.ctx_net[0].weight.shape[1] == 5 * 32 == off.critic.ctx_net[0].weight.shape[1]
assert on.critic.param_count == off.critic.param_count
# ...while the HEAD is the wide one.
assert on.priv_eval_head.privileged_dim == PRIV_DIM
assert on.priv_eval_head.ctx_net[0].weight.shape[1] == 8 * 32
assert on.priv_eval_head.param_count > on.critic.param_count
# The head is NOT in the union clip_grad_norm_ reads, or it would move
# loss/grad_norm.
pe = {id(p) for p in on.priv_eval_params}
assert pe and not (pe & {id(p) for p in on.params})
assert not (pe & {id(p) for p in on.critic.parameters()}), "the head IS the critic"
assert not (pe & {id(p) for p in on.actor.parameters()})

# --- 2. NO LEAKAGE ----------------------------------------------------------
# INIT first: the head is constructed AFTER the actor and the critic and rewinds
# the global RNG stream, so both nets' initial weights are bit-identical to the
# control's. (Contrast privileged_dim, which re-rolls the actor — the disclosed
# residue in tests/test_privileged_aux_seam.py.)
i_off, i_on = build(), build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
for name, a, b in (("actor", i_off.actor, i_on.actor), ("critic", i_off.critic, i_on.critic)):
    sa = a.state_dict(); sb = b.state_dict()
    assert set(sa) == set(sb), name
    for k in sa:
        assert torch.equal(sa[k], sb[k]), ("init", name, k)
# ...and then after twenty updates on the same rows.
for name, a, b in (("actor", off.actor, on.actor), ("critic", off.critic, on.critic)):
    for (k, p), (_, q) in zip(a.state_dict().items(), b.state_dict().items()):
        assert torch.equal(p, q), (name, k)
assert len(m_off) == len(m_on) == 20
for i, (a, b) in enumerate(zip(m_off, m_on)):
    assert set(b) - set(a) == {
        "loss/priv_eval_value",
        "priv_eval/explained_variance",
        # Added 2026-09-10 with the MC-target fix. `explained_variance_mc` is
        # the VERDICT read (head vs the outcome it now regresses); `critic_ev_mc`
        # scores the ordinary critic on that same target in the same pass, and
        # `ev_mc_advantage` is their difference. The GAE-target EV above stays a
        # diagnostic because it scores the head against ~53% its own opponent.
        "priv_eval/explained_variance_mc",
        "priv_eval/critic_ev_mc",
        "priv_eval/ev_mc_advantage",
    }, (i, set(b) - set(a))
    assert not set(a) - set(b), (i, set(a) - set(b))
    for k in a:
        assert a[k] == b[k], (i, k, a[k], b[k])

# --- 3. THE HEAD LEARNS -----------------------------------------------------
first, last = m_on[0], m_on[-1]
assert last["loss/priv_eval_value"] < first["loss/priv_eval_value"], (
    first["loss/priv_eval_value"], last["loss/priv_eval_value"])
assert last["priv_eval/explained_variance"] > first["priv_eval/explained_variance"], (
    first["priv_eval/explained_variance"], last["priv_eval/explained_variance"])
assert np.isfinite(last["loss/priv_eval_value"])
# ...and its weights are the ones that moved.
fresh = build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
moved = sum(
    1 for p, q in zip(fresh.priv_eval_head.parameters(), on.priv_eval_head.parameters())
    if not torch.equal(p, q)
)
assert moved > 0, "the head took no step"
# Same seed, same init: the rewind makes the head reproducible too.
again = build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
for p, q in zip(fresh.priv_eval_head.parameters(), again.priv_eval_head.parameters()):
    assert torch.equal(p, q)

# --- the public evaluator entry point ---------------------------------------
v = on.priv_eval_value(batch["obs"][:4], batch["privileged"][:4])
assert v.shape == (4,) and np.isfinite(v).all()
with torch.no_grad():
    ref = on.priv_eval_head(torch.cat([
        torch.as_tensor(batch["obs"][:4]), torch.as_tensor(batch["privileged"][:4])
    ], dim=-1)).reshape(-1).numpy()
assert np.array_equal(v, ref)
# A single row is accepted (a search leaf is one state).
assert on.priv_eval_value(batch["obs"][0], batch["privileged"][0]).shape == (1,)
try:
    on.priv_eval_value(batch["obs"][:4], batch["privileged"][:4, :-1])
    raise SystemExit("a short block was accepted")
except ValueError as e:
    assert "408" in str(e), e

print("OK", first["loss/priv_eval_value"], last["loss/priv_eval_value"],
      first["priv_eval/explained_variance"], last["priv_eval/explained_variance"])
"""


_CHECKPOINT_CHILD = _PREAMBLE + r"""
batch = make_batch()

on = build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
run(on, batch, n=3)
state = on.state_dict()
assert "priv_eval_head" in state
# The two nets every eval site loads keep exactly a control checkpoint's keys —
# and, because design A is off, exactly its SHAPES too, so a design-B
# checkpoint's `critic` loads into a plain agent unchanged.
assert set(state["actor"]) == set(build().actor.state_dict())
build().critic.load_state_dict(state["critic"])

# Round trip into a fresh head-on agent: the head comes back exactly.
back = build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
back.load_state_dict(state)
for (k, p), (_, q) in zip(on.priv_eval_head.state_dict().items(),
                          back.priv_eval_head.state_dict().items()):
    assert torch.equal(p, q), k
assert np.array_equal(
    on.priv_eval_value(batch["obs"][:8], batch["privileged"][:8]),
    back.priv_eval_value(batch["obs"][:8], batch["privileged"][:8]),
)
# ...and the Adam moments grafted onto our own groups, head included.
assert len(back.optimizer.state_dict()["state"]) == len(on.optimizer.state_dict()["state"])

# A head-carrying checkpoint must NOT load silently into an agent without one:
# the search evaluator would be a fresh random net and nothing would say so.
plain = build()
try:
    plain.load_state_dict(state)
    raise SystemExit("a design-B checkpoint loaded into a head-less agent")
except ValueError as e:
    assert "priv_eval_coef = 0" in str(e), e

# The reverse is legitimate — a warm start from a control run leaves the head
# at its init — and a pre-2026-09-10 checkpoint has no such key at all.
off = build()
run(off, {k: v for k, v in batch.items() if k != "privileged"}, n=3)
control = off.state_dict()
assert "priv_eval_head" not in control
warm = build(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
init = [p.detach().clone() for p in warm.priv_eval_head.parameters()]
warm.load_state_dict(control)
for p, q in zip(init, warm.priv_eval_head.parameters()):
    assert torch.equal(p, q), "the warm start moved the head"
for (k, p), (_, q) in zip(off.critic.state_dict().items(), warm.critic.state_dict().items()):
    assert torch.equal(p, q), k
# It still trains from there.
m = warm.update_episodes(batch, steps_seen=0)
assert np.isfinite(m["loss/priv_eval_value"])
print("OK")
"""


_LAUNCH_CHILD = r"""
import sys

from rl.common.config import Config
from rl.envs.showdown import PRIV_DIM
from rl.train import _async_collector_mode

assert PRIV_DIM == 408

def cfg(**agent):
    return Config(
        env_id="Showdown-v0", seed=0, total_steps=1000, eval_every=500,
        eval_episodes=10, run_name="t",
        collector={"mode": "engine", "k": 8, "team_bank": sys.argv[1]},
        env_kwargs={"opp_action": True},
        selfplay={"opponent": "self", "eval_opponent": "heuristics"},
        agent={"algo": "ppo", "aux_oppact_coef": 0.1, **agent},
    )

# THE LIFTED REFUSAL: the engine route used to reject agent.privileged_dim
# outright. It now accepts EITHER consumer of the block at the encoder's width —
# design A, design B, or both.
assert _async_collector_mode(cfg(privileged_dim=408), vectorized=True) == "engine"
assert _async_collector_mode(
    cfg(priv_eval_dim=408, priv_eval_coef=0.5, trunk="entity_deepsets"),
    vectorized=True,
) == "engine"
assert _async_collector_mode(
    cfg(privileged_dim=408, priv_eval_coef=0.5, trunk="entity_deepsets"),
    vectorized=True,
) == "engine"
# ...and refuses any other width, because a shifted slice reaches the critic
# with no error anywhere downstream.
for bad in (7, 398, 409):
    try:
        _async_collector_mode(cfg(privileged_dim=bad), vectorized=True)
        raise SystemExit(f"privileged_dim {bad} was accepted")
    except ValueError as e:
        assert "PRIV_DIM" in str(e), e
    try:
        _async_collector_mode(
            cfg(priv_eval_dim=bad, priv_eval_coef=0.5, trunk="entity_deepsets"),
            vectorized=True,
        )
        raise SystemExit(f"priv_eval_dim {bad} was accepted")
    except ValueError as e:
        assert "PRIV_DIM" in str(e), e
# The SERVER-backed async collector still refuses both: it has no seat-2 battle
# object to emit the block from.
def async_cfg(**agent):
    c = cfg(**agent)
    c.collector = {"mode": "async", "concurrency": 8}
    c.env_kwargs = {"opp_action": True}
    return c
for over in (dict(privileged_dim=408), dict(priv_eval_dim=408, priv_eval_coef=0.5)):
    try:
        _async_collector_mode(async_cfg(**over), vectorized=True)
        raise SystemExit(f"async accepted {over}")
    except ValueError as e:
        assert "privileged" in str(e), e
# And there is still NO collector.privileged key (ENGINE_KEYS is unchanged —
# the flag is derived from the AGENT'S OWN NEED).
from rl.train import ENGINE_KEYS
assert "privileged" not in ENGINE_KEYS, ENGINE_KEYS
import inspect, rl.train
src = inspect.getsource(rl.train._async_loop)
assert 'privileged=bool(getattr(agent, "privileged_block_dim", 0))' in src, (
    "the engine collector's privileged flag is not derived from the agent"
)
print("OK")
"""


def _run(child: str, *args: str, timeout: int = 900) -> str:
    result = subprocess.run(
        [sys.executable, "-c", child, *args],
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
        capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_the_head_trains_without_touching_the_actor_or_the_critic():
    out = _run(_ISOLATION_CHILD)
    print(out.strip().splitlines()[-1])
    assert out.strip().splitlines()[-1].startswith("OK")


def test_the_checkpoint_carries_the_head_and_survives_a_control_checkpoint():
    assert _run(_CHECKPOINT_CHILD).strip().splitlines()[-1] == "OK"


def test_the_engine_launch_gate_accepts_the_block_at_the_encoder_width(tmp_path):
    bank = tmp_path / "teams.bin"
    bank.write_bytes(b"")
    assert _run(_LAUNCH_CHILD, str(bank)).strip().splitlines()[-1] == "OK"


# The defect this pins (found in review 2026-09-10, fixed the same day): the
# head used to regress `flat_targets`, the GAE(lambda) target. At gamma 1 with
# a terminal-only reward that decomposes EXACTLY as
#     target_t = lam^(N-1-t) * z + (1 - lam) * sum_k lam^(k-1) V(s_t+k)
# so at the PRODUCTION lam of 0.95 about 53% of the head's target mass was the
# ORDINARY critic's own output (82% of it at the first decision) -- the network
# the privileged head exists to beat. It survived because the only test of the
# head's learning ran at lam 1.0, where the GAE target already IS the MC return:
# the tested path was not the production path. Both assertions below fail on the
# pre-fix code.
_MC_TARGET_CHILD = _PREAMBLE + r"""
batch = make_batch()


def build_lam(lam, **kw):
    torch.manual_seed(0)
    kws = dict(KW, gae_lambda=lam)
    return PPOAgent(
        gym.spaces.Box(-1.0, 4.0, (828,), np.float32), gym.spaces.Discrete(10),
        **kws, **kw,
    )


def capture(agent):
    # Every target the head is actually handed, minibatch by minibatch.
    seen = []
    inner = agent._priv_eval_gradient

    def spy(priv_obs, targets):
        seen.append(targets.detach().clone())
        return inner(priv_obs, targets)

    agent._priv_eval_gradient = spy
    agent.update_episodes(batch, steps_seen=0)
    return seen


HEAD = dict(priv_eval_dim=PRIV_DIM, priv_eval_coef=0.5)
t95 = capture(build_lam(0.95, **HEAD))     # production
t100 = capture(build_lam(1.0, **HEAD))     # the old fixture's setting
assert len(t95) == len(t100) > 0, (len(t95), len(t100))

# 1. THE TARGET DOES NOT MOVE WITH gae_lambda. The critic's advantages still do
#    -- only the head's target is pinned to the outcome.
for i, (a, b) in enumerate(zip(t95, t100)):
    assert torch.equal(a, b), ("the head's target moved with gae_lambda", i)

# 2. AND IT IS THE GAME'S OUTCOME. gamma is 1 and the reward is terminal-only,
#    so the MC return of every row in an episode is that episode's own z.
#    Pre-fix these were a continuous smear of bootstrapped critic values.
#    Magnitude, not equality: lam=1 reaches z by TELESCOPING the float32 scan,
#    so the critic's values cancel to ~1.2e-7 rather than to zero bits.
for i, a in enumerate(t95):
    assert torch.allclose(a.abs(), torch.ones_like(a), atol=1e-5), (
        i, float(a.abs().min()), float(a.abs().max()))

# 3. The GAE(0.95) target the head USED to get is materially different, so (1)
#    and (2) are not vacuous on this fixture.
probe = build_lam(0.95, **HEAD)
obs_t = torch.as_tensor(batch["obs"], dtype=torch.float32)
with torch.no_grad():
    v = probe.critic(obs_t).squeeze(-1)
from rl.buffers.episode import episode_gae
gae95 = torch.as_tensor(
    episode_gae(batch["rewards"], v.numpy(), batch["lengths"], 1.0, 0.95)) + v
mc = torch.as_tensor(
    episode_gae(batch["rewards"], v.numpy(), batch["lengths"], 1.0, 1.0)) + v
assert (gae95 - mc).abs().mean().item() > 1e-3, (gae95 - mc).abs().mean().item()
z = np.repeat(batch["rewards"][np.cumsum(batch["lengths"]) - 1], batch["lengths"])
assert np.allclose(mc.numpy(), z, atol=1e-5), np.abs(mc.numpy() - z).max()

# 4. The verdict metric exists and scores head against critic on that target.
m = build_lam(0.95, **HEAD).update_episodes(batch, steps_seen=0)
for k in ("priv_eval/explained_variance_mc", "priv_eval/critic_ev_mc",
          "priv_eval/ev_mc_advantage"):
    assert k in m, (k, sorted(m))
assert abs((m["priv_eval/explained_variance_mc"] - m["priv_eval/critic_ev_mc"])
           - m["priv_eval/ev_mc_advantage"]) < 1e-6
print("OK")
"""


def test_the_heads_target_is_the_mc_return_at_every_lambda():
    assert _run(_MC_TARGET_CHILD).strip().splitlines()[-1] == "OK"
