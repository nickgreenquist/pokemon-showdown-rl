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
# THE P-3 GATE BANK, PINNED BY NAME. Never `sorted(glob(...))[-1]`: that chose
# `teams_a1_5000000.bin` by alphabetical accident once the A-1 bank landed,
# and P-3 on 5,000,000 pairs is a ~35 min job that used to take ~16 GB.
# Pinning is right on MERIT too, not just on cost: P-3's leg with teeth is
# the move marginals against `randbats_prior`, whose power is FLOORED by the
# prior's own 4,000 draws per species — a 100x bigger bank buys at most a
# 1.40x reduction in se while multiplying every real-but-tiny discrepancy's z
# against an unchanged Bonferroni bar. Running P-3 on the A-1 bank is not a
# stronger gate, it is a differently-calibrated one.
# WHAT THIS GIVES UP, explicitly: the per-team constraint sweep no longer
# covers the A-1 bank, so its detection floor is ~3.0e-5 per team rather than
# ~3.0e-7. Recoverable on demand — `engine_parity.py p3 --bank <the 5M bank>`
# is now a <1 GB job — so the guarantee is deferred, not destroyed.
GATE_BANK = ROOT / "data/engine/teams_59da482e_e0e0_50000.bin"
BANKS = [str(GATE_BANK)] if GATE_BANK.exists() else []


@pytest.mark.skipif(not BANKS, reason="no team bank built yet")
def test_p3_bank_matches_showdowns_generator():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts/engine_parity.py"), "p3", "--bank", str(GATE_BANK)],
        capture_output=True,
        text=True,
        timeout=1800,
        cwd=ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "[P-3] PASS" in r.stdout
