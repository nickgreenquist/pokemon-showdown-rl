"""R7 B2 -- the antisymmetric critic, V(s) := 1/2 (f(view_1) - f(view_2))
(`rl/networks/entity_deepsets.py`; plan amendment box 2 item 3, runner brief §4).

Three things the brief asks for, each pinned here:
  * `V(swap(s)) == -V(s)` BITWISE (not allclose) -- the identity that cancels
    RESULTS §31's seat bias, on random inputs and on both the plain and the
    privileged form;
  * a checkpoint written by a critic WITHOUT the second view loads into the
    antisymmetric one with strict keys, and its `f` is the trained critic;
  * the actor's parameter count is untouched by the kwarg (trunk_kwargs are
    shared; the policy ignores it), so `ACTOR_PARAM_CEILING` still sees the
    pinned count.

Needs the 828 tokenizer, so it runs in a subprocess with both encoder env
vars set (tests/test_entity_deepsets.py's pattern). No engine, no server.
"""

from __future__ import annotations

import os
import subprocess
import sys

_CHILD = r"""
import numpy as np, torch
from rl.networks.entity_deepsets import EntityDeepSetsNet, ACTOR_PARAM_CEILING
from rl.envs.showdown import OBS_DIM, PRIV_DIM, privileged_block
assert OBS_DIM == 828 and PRIV_DIM == 408
torch.manual_seed(0)
KW = dict(species_vocab=152, move_vocab=166, embed_dim=64, entity_dim=128,
          ctx_sizes=[384, 384], scorer_sizes=[256], value_sizes=[1024, 1024])

def views(n, seed):
    # Random but VALID observations: the id tail must decode to table indices.
    g = np.random.default_rng(seed)
    v = g.random((n, OBS_DIM), dtype=np.float32)
    v[:, -20:] = g.integers(0, 150, (n, 20)).astype(np.float32) / 256.0
    return v

for threads in (1, 4):
    torch.set_num_threads(threads)
    for priv in (0, PRIV_DIM):
        torch.manual_seed(1)
        plain = EntityDeepSetsNet(OBS_DIM, 1, privileged_dim=priv, **KW)
        torch.manual_seed(1)
        anti = EntityDeepSetsNet(OBS_DIM, 1, privileged_dim=priv, antisymmetric=True, **KW)
        # (1) construction unchanged: same keys, same counts, same init draws.
        assert list(anti.state_dict()) == list(plain.state_dict())
        assert anti.param_count == plain.param_count
        assert all(torch.equal(a, b) for a, b in zip(anti.state_dict().values(), plain.state_dict().values()))
        # (2) a plain critic's checkpoint loads strictly, and f IS that critic.
        torch.manual_seed(2)
        trained = EntityDeepSetsNet(OBS_DIM, 1, privileged_dim=priv, **KW)
        anti.load_state_dict(trained.state_dict(), strict=True)
        anti.eval(); trained.eval()
        n = 37
        o1 = torch.from_numpy(views(n, 10)); o2 = torch.from_numpy(views(n, 11))
        if priv:
            p1 = torch.from_numpy(np.stack([privileged_block(r) for r in o2.numpy()]))
            p2 = torch.from_numpy(np.stack([privileged_block(r) for r in o1.numpy()]))
            x = torch.cat([o1, o2, p1, p2], 1); x_swap = torch.cat([o2, o1, p2, p1], 1)
            f1 = trained(torch.cat([o1, p1], 1)); f2 = trained(torch.cat([o2, p2], 1))
        else:
            x = torch.cat([o1, o2], 1); x_swap = torch.cat([o2, o1], 1)
            f1 = trained(o1); f2 = trained(o2)
        with torch.no_grad():
            v = anti(x); v_swap = anti(x_swap)
        # (3) THE IDENTITY, bitwise.
        assert torch.equal(v_swap, -v), (threads, priv, (v_swap + v).abs().max())
        nz = v != 0
        assert nz.any()
        assert torch.equal(v_swap[nz].view(torch.int32), (-v[nz]).view(torch.int32)), "bit patterns differ"
        # (4) and it is exactly 1/2 (f(view_1) - f(view_2)) of the loaded critic.
        assert torch.equal(v, 0.5 * (f1 - f2)), (threads, priv)
        # (5) a self-mirror (both views identical) values to exactly 0.
        x_same = torch.cat([o1, o1] + ([p2, p2] if priv else []), 1)
        assert torch.equal(anti(x_same), torch.zeros(n, 1))
        # (6) the wrong width is refused, never split silently.
        try:
            anti(o1)
        except ValueError as e:
            assert "antisymmetric critic expects" in str(e)
        else:
            raise AssertionError("a single view was accepted")
        # (7) forward_with_aux agrees with forward bitwise on the value.
        torch.manual_seed(3)
        anti_aux = EntityDeepSetsNet(OBS_DIM, 1, privileged_dim=priv, antisymmetric=True, value_aux_out=3, **KW)
        anti_aux.load_state_dict({**trained.state_dict(), **{k: v_ for k, v_ in anti_aux.state_dict().items() if k.startswith("aux_value_head")}})
        anti_aux.eval()
        with torch.no_grad():
            va, aux = anti_aux.forward_with_aux(x)
        assert torch.equal(va, anti_aux(x)) and aux.shape == (n, 3)

# (8) the actor ignores the kwarg: same params, same count, under the ceiling.
torch.manual_seed(4); actor = EntityDeepSetsNet(OBS_DIM, 10, **KW)
torch.manual_seed(4); actor_kw = EntityDeepSetsNet(OBS_DIM, 10, antisymmetric=True, **KW)
assert actor_kw.param_count == actor.param_count <= ACTOR_PARAM_CEILING
assert not actor_kw.antisymmetric
assert all(torch.equal(a, b) for a, b in zip(actor.state_dict().values(), actor_kw.state_dict().values()))
xa = torch.from_numpy(views(5, 20))
assert torch.equal(actor(xa), actor_kw(xa))
print("OK antisymmetric critic: identity bitwise, checkpoints load, actor untouched")
"""


def test_antisymmetric_critic_identity_and_loading():
    r = subprocess.run(
        [sys.executable, "-c", _CHILD],
        capture_output=True, text=True, timeout=600,
        env={**os.environ, "POKEMON_RL_ENCODER_V2": "1", "POKEMON_RL_ENCODER_IDS": "1"},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("OK")
