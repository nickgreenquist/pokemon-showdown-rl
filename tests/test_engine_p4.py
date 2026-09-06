"""Gate P-4 as a test (docs/PKMN_ENGINE_RUST_PLAN.md §9).

Runs `scripts/engine_parity.py p4` against the local Foul-Play tapes. The tapes
are gitignored collection artifacts, so this skips loudly where they are absent.
No server, no poke-env client -- it reads recorded `|request|` JSON only.
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


@pytest.mark.skipif(not tape_paths(), reason="local FP tapes absent")
def test_p4_stats_match_the_request_exactly():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/engine_parity.py"), "p4"],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[P-4] PASS" in r.stdout
