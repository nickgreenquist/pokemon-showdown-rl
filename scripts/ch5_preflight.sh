#!/bin/bash
# CH5 R1 BI-6 pre-flight (designer B §5.2c / §10 BI-6). Run IMMEDIATELY
# before scripts/ch5_r1_wave.sh. Exits non-zero on anything that would make
# the wave unquotable.
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
if ! nc -z localhost 8000 2>/dev/null; then
    echo "FAIL: no Showdown server on :8000 (cd showdown && node pokemon-showdown start --no-security)"; rc=1
fi
if ! grep -qE "^[^/]*simulator: *4" showdown/config/config.js 2>/dev/null; then
    echo "FAIL: showdown/config/config.js is missing simulator: 4 (+81% throughput; the file is gitignored and resets on re-clone)"; rc=1
fi
if [ -n "$(git status --porcelain)" ]; then
    echo "FAIL (G0): tree is dirty -- launches stamp git_dirty, and one untracked .md flips it"; rc=1
fi

echo "launch_git_sha $(git rev-parse HEAD)"
echo "prereg_sha256  $(shasum -a 256 configs/eval/ch5_r1_offsh.yaml | cut -d' ' -f1)"
exit $rc
