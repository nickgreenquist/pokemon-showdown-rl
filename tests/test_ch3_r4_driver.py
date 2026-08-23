"""BI-1/BI-4 offline tests: F5 membership asserts + provenance shape in
_resolve_evaluator, and the evaluator-absent path staying inert (the
bit-identical-when-absent regression at the driver layer)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import ch3_eval  # noqa: E402

PREREG = {
    "checkpoints": {
        "s62": {"sha256": "a"}, "s63": {"sha256": "b"},
        "s64": {"sha256": "c"}, "s65": {"sha256": "d"},
    }
}


class _FakeAgent:
    pass


def _fake_loader(agents):
    def load(prereg, lane, env=None):
        return agents[lane], None, None
    return load


def test_absent_evaluator_is_inert():
    ev, prov = ch3_eval._resolve_evaluator(PREREG, "s62", None, None, _FakeAgent())
    assert ev is None and prov is None


def test_loo_resolves_pool_minus_self_with_provenance(monkeypatch):
    agents = {l: _FakeAgent() for l in PREREG["checkpoints"]}
    monkeypatch.setattr(ch3_eval, "_load_member", _fake_loader(agents))
    spec = {"kind": "loo", "pool": ["s62", "s63", "s64", "s65"]}
    ev, prov = ch3_eval._resolve_evaluator(PREREG, "s63", spec, None, agents["s63"])
    assert [a is agents[l] for a, l in zip(ev["agents"], ["s62", "s64", "s65"])]
    assert prov == {"kind": "loo", "members": ["s62", "s64", "s65"],
                    "member_sha256": ["a", "c", "d"]}


def test_loo_self_in_agents_fires_f5(monkeypatch):
    agents = {l: _FakeAgent() for l in PREREG["checkpoints"]}
    own = agents["s63"]
    # loader returns the OWN agent for a peer lane -> identity assert fires
    monkeypatch.setattr(
        ch3_eval, "_load_member", _fake_loader({l: own for l in agents})
    )
    spec = {"kind": "loo", "pool": ["s62", "s63", "s64", "s65"]}
    with pytest.raises(AssertionError, match="F5"):
        ch3_eval._resolve_evaluator(PREREG, "s63", spec, None, own)


def test_loo_bad_pool_size_fires_f5():
    spec = {"kind": "loo", "pool": ["s62", "s63"]}
    with pytest.raises(AssertionError, match="F5"):
        ch3_eval._resolve_evaluator(PREREG, "s63", spec, None, _FakeAgent())
