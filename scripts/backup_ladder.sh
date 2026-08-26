#!/usr/bin/env bash
# Back up the ladder artifacts. Run after any ladder session.
#
# WHY THIS EXISTS. `results/` is gitignored with ZERO tracked files, so the
# ladder JSONL and its 200+ replays are NOT in git and never will be. A rated
# ladder game is also unrepeatable — you cannot re-play it — so losing these
# files loses the measurement permanently, unlike a training run which can be
# re-run. Three copies is the standing arrangement:
#
#   1. results/ladder/                      the live working copy
#   2. ../pokemon-showdown-rl-d25-backup-20260815/ladder/   rsync mirror
#   3. ~/pokemon-showdown-rl-ladder-archive/               dated tarballs
#
# The NUMBERS survive separately from the files: `scripts/ladder_readout.py`
# writes LADDER_R1_READOUT.md to a TRACKED path, so even losing all three
# copies leaves the readout in git. That is the same rule scripts/README.md
# records for grader scripts.
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/results/ladder"
MIRROR="$REPO/../pokemon-showdown-rl-d25-backup-20260815/ladder"
ARCHIVE="$HOME/pokemon-showdown-rl-ladder-archive"

[ -d "$SRC" ] || { echo "no $SRC — nothing to back up"; exit 1; }
mkdir -p "$MIRROR" "$ARCHIVE"
rsync -a "$SRC/" "$MIRROR/"
STAMP="$(date +%Y%m%d_%H%M)"
tar czf "$ARCHIVE/ladder_r1_$STAMP.tar.gz" -C "$REPO/results" ladder

rows=$(wc -l < "$SRC/L2.battles.jsonl" | tr -d ' ')
reps=$(find "$SRC/replays" -name '*.html' | wc -l | tr -d ' ')
mrows=$(wc -l < "$MIRROR/L2.battles.jsonl" | tr -d ' ')
mreps=$(find "$MIRROR/replays" -name '*.html' | wc -l | tr -d ' ')
echo "live   : $rows rows, $reps replays"
echo "mirror : $mrows rows, $mreps replays"
echo "archive: $ARCHIVE/ladder_r1_$STAMP.tar.gz"
[ "$rows" = "$mrows" ] && [ "$reps" = "$mreps" ] \
  && echo "OK - mirror matches live" \
  || { echo "MISMATCH - do not trust the mirror"; exit 1; }
