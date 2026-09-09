"""Gates P-1 and P-2 as tests (docs/PKMN_ENGINE_RUST_PLAN.md §9).

Both replay the local Foul-Play tapes offline -- no server, no poke-env client.
They skip loudly where the tapes or the built extension are absent. The default
targets here are the gate minimum (>= 5,000 decisions); the recorded gate runs
used 100,000 (see docs/engine_port/NOTES.md).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from engine_tapes import tape_paths  # noqa: E402


def _run(gate: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/engine_parity.py"), gate, *extra],
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=ROOT,
    )


@pytest.mark.skipif(not tape_paths(), reason="local FP tapes absent")
def test_p1_encoder_parity_is_bitwise():
    r = _run("p1", "--target", "6000")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[P-1] PASS" in r.stdout


@pytest.mark.skipif(not tape_paths(), reason="local FP tapes absent")
def test_p2_mask_parity_and_the_mapping_table():
    r = _run("p2", "--target", "6000", "--engine-battles", "2000")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[P-2] PASS" in r.stdout
