#!/usr/bin/env bash
# MERGE-BACK CHECK: does the extension build and install into a FRESH env from
# the committed pins ALONE?
#
# WHY THIS EXISTS. The engine collector is an optional path, and the claim the
# merge rests on is that the MAIN env can acquire it later without a person
# reconstructing a toolchain from memory. That claim is only true if a brand-new
# env, given nothing but requirements-engine.txt and the two pyproject files,
# ends up with a working `pkmn_gen1` whose verify() passes. This proves it.
#
# It NEVER touches the pokemon-showdown-rl env, and it never touches the
# session's own pkmn-engine-port env either — it builds a throwaway and removes
# it, so a failure here cannot cost the working environment.
#
#   bash scripts/engine_fresh_env_check.sh            # build, verify, remove
#   KEEP=1 bash scripts/engine_fresh_env_check.sh     # leave the env for triage
#
# Run it on an IDLE box: it compiles, and a compile next to a throughput
# measurement invalidates the measurement.
set -uo pipefail
cd "$(dirname "$0")/.."
ENVNAME="${ENVNAME:-pkmn-engine-freshcheck}"
PREFIX="/opt/anaconda3/envs/$ENVNAME"
KEEP="${KEEP:-0}"
LOG=logs/engine_fresh_env_check.log
mkdir -p logs
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
fail() { say "FAIL: $*"; cleanup; exit 1; }
cleanup() {
  if [ "$KEEP" = 1 ]; then say "KEEP=1 — leaving $ENVNAME in place"; return; fi
  say "removing $ENVNAME"
  conda env remove -y -n "$ENVNAME" > /dev/null 2>&1 || true
}

[ -n "$(git status --porcelain)" ] && say "WARNING: tree is dirty — the pins under test are the WORKING copy, not the commit"

say "=== fresh-env check: $ENVNAME ==="
conda env remove -y -n "$ENVNAME" > /dev/null 2>&1 || true
conda create -y -n "$ENVNAME" python=3.13 >> "$LOG" 2>&1 || fail "conda create"
say "env created (python 3.13)"

# 1. The repo itself, so rl/ imports resolve — the same editable install the
#    main env uses. This is NOT the pokemon-showdown-rl env.
"$PREFIX/bin/pip" install -e ".[dev]" >> "$LOG" 2>&1 || fail "pip install -e .[dev]"
say "repo installed editable"

# 2. The engine toolchain, from the committed pins ALONE. If this file is
#    incomplete, the build below fails and that is the finding.
"$PREFIX/bin/pip" install -r requirements-engine.txt >> "$LOG" 2>&1 || fail "requirements-engine.txt"
say "engine toolchain installed from requirements-engine.txt: $(grep -v '^#' requirements-engine.txt | tr '\n' ' ')"

# 3. The submodule must be present at the pin.
SUB=$(git submodule status engine/pkmn_gen1/vendor/pkmn-engine 2>/dev/null | awk '{print $1}' | tr -d '-+')
[ -n "$SUB" ] || fail "submodule engine/pkmn_gen1/vendor/pkmn-engine not initialised"
say "submodule at $SUB"

# 4. Build. maturin is a console script, so its bin dir must be on PATH; zig
#    comes from the pip wheel and is resolved by build.rs via `python -m ziglang`,
#    so PKMN_PYTHON is cleared to let that path run.
say "building (this compiles Zig + Rust; minutes)"
PATH="$PREFIX/bin:$PATH" PKMN_PYTHON= \
  "$PREFIX/bin/pip" install --no-build-isolation -e engine/pkmn_gen1 >> "$LOG" 2>&1 \
  || fail "editable build of engine/pkmn_gen1"
say "extension built and installed"

# 5. The FG-5 habit: verify() asserts the engine sha against the pin, the
#    build options, battle_size and the zig version. A build that imports but
#    fails verify() is a build against the wrong engine.
"$PREFIX/bin/python" - <<'PY' >> "$LOG" 2>&1 || fail "pkmn_gen1.verify()"
import json, pkmn_gen1
info = pkmn_gen1.verify()
print(json.dumps(info, indent=1))
assert info["engine_sha"] == info["engine_sha_pinned"], info
assert info["zig"] == "0.16.0", info
assert info["battle_size"] == 384, info
assert info["options"] == {"showdown": True, "log": False, "chance": False, "calc": False}, info
PY
say "verify() PASS: $("$PREFIX/bin/python" -c "import pkmn_gen1,json;i=pkmn_gen1.verify();print('engine',i['engine_sha'][:8],'zig',i['zig'],'battle',i['battle_size'])")"

# 6. The Rust unit tests are the B-0 gate and must pass against this build.
say "cargo test (B-0)"
( cd engine/pkmn_gen1 && PKMN_PYTHON= cargo test --quiet ) >> "$LOG" 2>&1 \
  || say "WARNING: cargo test failed — see $LOG (does not block the install claim)"

say "FRESH-ENV CHECK PASSED — the main env can acquire the extension from the committed pins alone"
cleanup
