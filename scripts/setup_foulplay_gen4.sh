#!/usr/bin/env bash
# The exact recipe that produced the `foul-play-gen4` conda env on 2026-09-05
# (open_questions.md Q37, authorised by the maintainer that morning). Recorded,
# not meant to be re-run blindly: it creates a conda env, compiles a Rust
# extension and pre-places a pinned data file in the shared foul-play clone.
#
# WHY A SECOND ENV. poke-engine is compiled PER GENERATION (Cargo features;
# both recipes pass --no-default-features, so the crate's default set is
# irrelevant here — requirements-search.txt's "default build is GEN 4" and an
# earlier "default = []" in this header were never verified against Cargo.toml). The `foul-play` env holds the gen1 build that every gen-1
# FP number was measured with; rebuilding it for gen4 would silently retire
# the gen-1 anchor. One env per engine build; the foul-play SOURCE clone
# (../foul-play, with our gen-1 patch applied) is shared read-only, and the
# gen-1 `Fight` placeholder handling in that patch is inert in gen 4.
#
# WHY THE PRE-PLACED SET FILE. Foul Play fetches its randbats opponent model
# from pkmn.github.io on first use and caches it; a non-200 response caches
# `{}` PERMANENTLY (fp/data/sets/base.py). The file fetched 2026-09-05 is
# pinned by sha256 in docs/design_gen4/research/live/fp_gen4_set_pin.json and
# copied into the cache so the bot never fetches. Its 295 species, 39 items
# (of our 40 vocab rows — Light Clay is unreachable in both), 101 abilities
# and 181 moves are exactly the vendored pool's (59da482e); 40 species differ
# by +/-1..2 levels (a nearby upstream commit) — disclosed.
#
# HOW THE BUILD WAS VERIFIED (scripts/gen4_fp_smoke.py; the .so):
#   - maturin was invoked with `--features poke-engine/gen4 --no-default-features`
#     (pip -v log); the binary carries poke-engine's `src/genx/` module tree
#     where the gen-1 build carries `src/gen1/` (and its "used for spc" string);
#   - calculate_damage: Ghost->Steel and Dark->Steel resisted (gen 2-5 chart),
#     Explosion halves the target's Defense (gen <= 4) — see SESSION_LOGS.
set -euo pipefail

FPDIR="${FPDIR:-$(cd "$(dirname "$0")/../.." && pwd)/foul-play}"
ENV_NAME="${ENV_NAME:-foul-play-gen4}"
CONDA="${CONDA:-/opt/anaconda3/bin/conda}"
PIP="/opt/anaconda3/envs/$ENV_NAME/bin/pip"
SETS_URL="https://pkmn.github.io/randbats/data/full/gen4randombattle.json"
PIN_SHA="f742b0d9d015e0679175a46999dd06db0aeec79c820e32366d0f01f8e3f197d0"

echo "1/4 conda env $ENV_NAME (python 3.11, foul-play's)"
"$CONDA" create -y -q -n "$ENV_NAME" python=3.11

echo "2/4 foul-play's pinned requirements EXCEPT poke-engine (its line carries the gen1 build flag)"
"$PIP" install -q requests==2.33.0 websockets==14.1 python-dateutil==2.8.0

echo "3/4 poke-engine 0.0.48 compiled with the gen4 feature (needs cargo; ~1 min)"
# EXACTLY requirements-search.txt's flags: pip's wheel cache ignores
# --config-settings, so without --no-binary/--force-reinstall a re-run can
# install a cached wheel of the WRONG generation and still exit 0.
(cd "$FPDIR" && "$PIP" install -v --no-cache-dir --force-reinstall --no-binary poke-engine \
    "poke-engine==0.0.48" \
    --config-settings="build-args=--features poke-engine/gen4 --no-default-features")

echo "3b/4 verify the build (the .so discriminator; gen 1 automates the same check as FG-5)"
"/opt/anaconda3/envs/$ENV_NAME/bin/python" - << 'PYEOF'
import glob, sys
so = glob.glob("/opt/anaconda3/envs/" + sys.argv[0] if False else "/opt/anaconda3/envs/*/lib/python3.11/site-packages/poke_engine/poke_engine*.so")
so = [p for p in so if "/foul-play-gen4/" in p]
assert so, "no poke_engine .so in the gen4 env"
b = open(so[0], "rb").read()
genx, gen1, spc = b.count(b"src/genx/"), b.count(b"src/gen1/"), b.count(b"used for spc")
print(f"{so[0]}: src/genx/ {genx}, src/gen1/ {gen1}, 'used for spc' {spc}")
if not (genx >= 1 and gen1 == 0 and spc == 0):
    print("WRONG-GENERATION BUILD: expected src/genx/ >= 1, src/gen1/ == 0, 'used for spc' == 0", file=sys.stderr)
    sys.exit(3)
PYEOF

echo "4/4 pinned gen4 set file into foul-play's cache (verify the sha first)"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
curl -fsSL -o "$TMP" "$SETS_URL"
GOT="$(shasum -a 256 "$TMP" | cut -d' ' -f1)"
if [ "$GOT" != "$PIN_SHA" ]; then
    echo "UPSTREAM SET FILE CHANGED: sha $GOT != pinned $PIN_SHA — do not install; re-run the six-way comparison first" >&2
    exit 2
fi
mkdir -p "$FPDIR/fp/data/pkmn_sets_cache"
cp "$TMP" "$FPDIR/fp/data/pkmn_sets_cache/gen4randombattle.json"

echo "smoke: python scripts/gen4_fp_smoke.py --battles 5 --seat heuristics --search-time-ms 20 --port <local server port>"
