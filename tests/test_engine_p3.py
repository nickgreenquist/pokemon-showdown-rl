"""Gate P-3 as a test (docs/PKMN_ENGINE_RUST_PLAN.md §9).

Needs a team bank, which is gitignored and built by
`scripts/engine_team_bank.py` from the vendored Showdown checkout. Skips loudly
where either is absent. The bank build loads only `showdown/dist/sim`: no server
is started and no socket is opened.
"""

from __future__ import annotations

import glob
import pathlib
import subprocess
import sys

import pytest

pytest.importorskip("pkmn_gen1", reason="build engine/pkmn_gen1 first")

ROOT = pathlib.Path(__file__).resolve().parents[1]
BANKS = sorted(glob.glob(str(ROOT / "data/engine/teams_*.bin")))


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_p3_bank_matches_showdowns_generator():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/engine_parity.py"), "p3", "--bank", BANKS[-1]],
        capture_output=True,
        text=True,
        timeout=1800,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[P-3] PASS" in r.stdout
