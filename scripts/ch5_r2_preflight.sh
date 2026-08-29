#!/bin/bash
# CH5 R2 pre-flight — COPY of scripts/ch5_preflight.sh with two deltas:
# the prereg_sha256 echo points at R2's pre-reg, and a NO-CO-SCHEDULED-
# TRAINING check R1 never needed (R2's checkpoints come from lanes that
# may still be running; FP is time-budgeted and a training lane inflates
# its effective search budget — wave-scoped VOID). Run IMMEDIATELY before
# scripts/ch5_r2_wave.sh. Exits non-zero on anything that would make the
# wave unquotable.
#
# Two checks beyond B's list, both from CLAUDE.md's landmines and both
# flagged as additions: the `simulator: 4` check (the config is gitignored
# and silently resets on a re-clone; it is worth +81% collection
# throughput) and the G0 clean-tree check, which belongs in the same five
# seconds — launches stamp git_dirty and one untracked .md flips it.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"; cd "$REPO" || exit 1
rc=0

pkill -9 -f "run.py .*--ps-username ch5" 2>/dev/null && echo "swept orphan ch5 foul-play"

if pgrep -f "scripts/ch3_fp_h2h.py" >/dev/null; then
    echo "FAIL: a ch3_fp_h2h.py seat is already running"; rc=1
fi
if pgrep -f "rl\.train" >/dev/null; then
    echo "FAIL: a training lane is running -- FP is time-budgeted; a training lane inflates its effective search budget (wave-scoped VOID)"; rc=1
fi
if ! nc -z localhost 8000 2>/dev/null; then
    echo "FAIL: no Showdown server on :8000 (cd showdown && node pokemon-showdown start --no-security)"; rc=1
fi
if ! grep -qE "^[^/]*simulator: *4" showdown/config/config.js 2>/dev/null; then
    echo "FAIL: showdown/config/config.js is missing simulator: 4 (+81% throughput; the file is gitignored and resets on re-clone)"; rc=1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "FAIL (G0): tree is dirty -- launches stamp git_dirty, and one untracked .md flips it"; rc=1
fi

# r2_review_2 SF-3: refuse to LAUNCH a wave against un-attested pins.
# (The failure downstream is loud and burns no pair, but it costs the
# arm's single no-JSON retry; the grader already refuses to grade.)
if grep -q "status: PENDING" configs/eval/ch5_r2_offsh.yaml; then
    echo "FAIL: checkpoint_attestation.status is PENDING -- run the attestation commit first (checkpoint_attestation flow)"; rc=1
fi

echo "launch_git_sha $(git rev-parse HEAD)"
echo "prereg_sha256  $(shasum -a 256 configs/eval/ch5_r2_offsh.yaml | cut -d' ' -f1)"
exit $rc
