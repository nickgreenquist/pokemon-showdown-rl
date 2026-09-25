"""The mmap'd team bank (R7 plan §9 ruling 6's precondition; the 2026-09-10 max-out
finding: every lane held its own 0.53 GB copy of identical bytes).

(1) `open_bank` returns EXACTLY `read_bank`'s header and payload, verified the same
    way (sha256, length), as a read-only view over the mmap'd file.
(2) `load_bank_for_env` takes the mmap path only when the installed extension says
    it reads a buffer in place (`build_info()["bank_zero_copy"]`), and SAYS which
    it took -- an older build would extract a memoryview element by element.
(3) Under a `bank_zero_copy` build: a BatchEnv built from the mmap'd view plays
    identically to one built from bytes (same seed, same actions -> the same
    observations and the same finished episodes), and it holds the BUFFER, not a
    copy -- the mmap cannot be closed while the env lives, and can after.
(3) SKIPS until the extension is reinstalled with the change (Friday's idle box);
    after that it must PASS, not skip -- a gate in the fleet's checklist.
"""

from __future__ import annotations

import gc
import glob
import pathlib

import numpy as np
import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

import pkmn_gen1  # noqa: E402

from rl.envs.engine_bank import load_bank_for_env, open_bank, read_bank  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")), key=lambda p: pathlib.Path(p).stat().st_size)
ZERO_COPY = bool(pkmn_gen1.build_info().get("bank_zero_copy"))

pytestmark = pytest.mark.skipif(not BANKS, reason="no team bank built yet")


def test_open_bank_is_read_bank_as_a_view():
    path = pathlib.Path(BANKS[0])
    h1, p1 = read_bank(path)
    h2, p2 = open_bank(path)
    assert h1 == h2
    assert isinstance(p2, memoryview) and p2.readonly
    assert bytes(p2) == p1


def test_the_loader_keys_on_the_extensions_capability(monkeypatch):
    path = pathlib.Path(BANKS[0])
    info = dict(pkmn_gen1.build_info())
    monkeypatch.setattr(pkmn_gen1, "build_info", lambda: {**info, "bank_zero_copy": True})
    h, payload, zc = load_bank_for_env(path)
    assert zc is True and isinstance(payload, memoryview)
    monkeypatch.setattr(pkmn_gen1, "build_info", lambda: {k: v for k, v in info.items() if k != "bank_zero_copy"})
    h, payload, zc = load_bank_for_env(path)
    assert zc is False and isinstance(payload, bytes)


def _play(env, rng, steps=150):
    trace = []
    for step in range(steps):
        li, lobs, lmask, _ = env.pending("learner")
        oi, oobs, omask, _ = env.pending("opponent")
        la = [int(rng.choice(np.flatnonzero(m))) for m in lmask]
        oa = [int(rng.choice(np.flatnonzero(m))) for m in omask]
        trace.append((li.tolist(), np.asarray(lobs).tobytes()))
        env.step(li.tolist(), la, [0.0] * len(li), step, oi.tolist(), oa)
        for ep in env.drain_finished():
            trace.append(("done", int(ep["slot"]), int(ep["reward"]), int(ep["length"]), int(ep["seed"])))
    return trace


@pytest.mark.skipif(not ZERO_COPY, reason="the installed extension predates bank_zero_copy -- reinstall (Friday's idle box)")
def test_an_env_on_the_mmap_plays_like_one_on_bytes_and_holds_the_buffer():
    from rl.envs.engine_tables import build_tables

    tables, _ = build_tables()
    path = pathlib.Path(BANKS[0])
    _, raw = read_bank(path)
    _, view = open_bank(path)
    a = pkmn_gen1.BatchEnv(8, 4242, tables, raw, "p1")
    b = pkmn_gen1.BatchEnv(8, 4242, tables, view, "p1")
    assert _play(a, np.random.default_rng(3)) == _play(b, np.random.default_rng(3))
    # The env holds the EXPORT, not a copy: with every Python reference to the
    # view gone, the mapping still cannot close while the env lives.
    mm = view.obj
    del view
    gc.collect()
    with pytest.raises(BufferError):
        mm.close()
    del b
    gc.collect()
    mm.close()
