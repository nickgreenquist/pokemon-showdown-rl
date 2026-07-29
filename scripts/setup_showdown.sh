#!/bin/sh
# Set up the local Pokémon Showdown server the Phase 5 capstone battles
# against (poke-env is the client; see pyproject.toml for its pin).
#
# Clones smogon/pokemon-showdown at a pinned commit into showdown/ at the
# repo root (gitignored), installs its npm deps, and writes a local config:
# the example config plus `exports.repl = false` — the REPL unix sockets
# crash with EINVAL on macOS + recent Node, and the server needs no REPL
# for local RL training.
#
# Requires Node.js (tested with v25.9.0). Start the server afterwards with:
#   cd showdown && node pokemon-showdown start --no-security
# It serves websockets on localhost:8000, poke-env's default.

set -eu

# Pinned 2026-07-29 (master HEAD at Phase 5 start).
SHOWDOWN_COMMIT=59da482eabc87245eb62313593e468e81ca537d9

cd "$(dirname "$0")/.."

if [ -e showdown ]; then
    echo "showdown/ already exists — remove it first to re-clone" >&2
    exit 1
fi

mkdir showdown
cd showdown
git init -q
git remote add origin https://github.com/smogon/pokemon-showdown.git
git fetch -q --depth 1 origin "$SHOWDOWN_COMMIT"
git checkout -q FETCH_HEAD

npm install

cp config/config-example.js config/config.js
printf '\n// Local RL training server: disable REPL sockets (EINVAL crashes on macOS/new Node)\nexports.repl = false;\n' >> config/config.js

echo "done — start with: cd showdown && node pokemon-showdown start --no-security"
