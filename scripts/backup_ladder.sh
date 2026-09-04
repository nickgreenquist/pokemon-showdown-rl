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
# writes readouts/LADDER_R1_READOUT.md to a TRACKED path, so even losing all three
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
# The tarball takes results/ladder WHOLESALE, so it already covers every run
# under that root. The name is no longer run-specific for the same reason.
tar czf "$ARCHIVE/ladder_$STAMP.tar.gz" -C "$REPO/results" ladder

# R3 BI-3. The COPYING always covered R3 -- rsync and tar both take
# results/ladder wholesale, which is exactly why ladder_r3.yaml puts R3 under
# R1's root instead of taking its own. The VERIFICATION did not: the counts
# below were hardcoded to L2.battles.jsonl and replays/, so R3's files were
# being mirrored and archived while the "OK - mirror matches live" line said
# nothing whatsoever about them. An unverified backup is not a checked backup.
# Each run is (jsonl, replay dir); a missing one is skipped, not an error,
# because this script runs after R1 sessions too.
RUNS=("L2:replays" "R3S:replays_r3" "R4G:replays_r4")   # BI-R4-1 (ladder_r4): without this the OK line says nothing about R4
fail=0
for entry in "${RUNS[@]}"; do
  arm="${entry%%:*}"
  repdir="${entry##*:}"
  [ -f "$SRC/$arm.battles.jsonl" ] || { echo "$arm: not present, skipped"; continue; }
  rows=$(wc -l < "$SRC/$arm.battles.jsonl" | tr -d ' ')
  mrows=$(wc -l < "$MIRROR/$arm.battles.jsonl" | tr -d ' ')
  reps=$(find "$SRC/$repdir" -name '*.html' 2>/dev/null | wc -l | tr -d ' ')
  mreps=$(find "$MIRROR/$repdir" -name '*.html' 2>/dev/null | wc -l | tr -d ' ')
  echo "$arm live   : $rows rows, $reps replays"
  echo "$arm mirror : $mrows rows, $mreps replays"
  if [ "$rows" = "$mrows" ] && [ "$reps" = "$mreps" ]; then
    echo "$arm OK - mirror matches live"
  else
    echo "$arm MISMATCH - do not trust the mirror"
    fail=1
  fi
done
echo "archive: $ARCHIVE/ladder_$STAMP.tar.gz"
[ "$fail" = 0 ] || exit 1
