# Bootstrap brief — pkmn/engine collector port, in a worktree, WHILE A FLEET IS RUNNING

**For a parallel Claude Code session.** Written 2026-09-06 by the babysitter
session. The spec you are implementing is `docs/PKMN_ENGINE_RUST_PLAN.md`; this
file is only the operating envelope — what you may touch, what you must not,
where to stop, and how to hand back.

**Read first, in this order:** `CLAUDE.md` (binding), this file,
`docs/PKMN_ENGINE_RUST_PLAN.md` §0 verdict → §1 pins → §3 C API → §5 wrapper →
§7 invariants → §9 gates, and the concurrency / env sections of
`docs/landmines.md`. Do **not** read `STATUS.md` or `HANDOFF.md` as a to-do
list: the work they describe belongs to another session.

---

## 0. The situation you are working next to

A three-lane training fleet (`runs/gen4_wang50m_s200`, `_s208`, `_s216`) is
running on this box and will be until **≈ 2026-09-08 22:00Z**, followed by an
automatic ~8 h evaluation schedule (until ≈ 2026-09-09 06:00Z). It is the
project's first gen-4 result and it is not reproducible cheaply — a fleet is
~65 h of wall time. A separate session owns it, owns `main`, and will write the
readout from it.

Live pieces you must leave alone: three `python -m rl.train` processes, one
`node pokemon-showdown` server with 4 simulator workers on the default port, a
detached watcher (`scripts/gen4_wang50m_watch.sh`) under `caffeinate`, and four
session monitors. Headroom as of writing: ~5.1 of 14 cores in use, ~11 GB
free+inactive of 24 GB, lanes at 212–215 steps/s.

**Your prime directive: the fleet's numbers must be indistinguishable from what
they would have been if you had never run.**

---

## 1. Hard prohibitions (each of these can destroy the run)

1. **Never install into, modify, or activate the `pokemon-showdown-rl` conda
   env.** The lanes resume into it after any death; a half-resolved dependency
   there kills them at import. You get your own env (§2). This mirrors the
   existing `foul-play-gen4` precedent: one env per engine build.
   **This OVERRIDES CLAUDE.md's rule 1 ("Activate the `pokemon-showdown-rl`
   conda env") and the `pip install -e ".[dev]"` line under "Development
   environment", for this session only** — those are written for a session that
   owns the box, and you do not. CLAUDE.md is otherwise binding. The env rule
   behind rule 1 still holds in its real form: one env per repo, never `base`,
   never shared — yours is `pkmn-engine-port` (§2). If you have already
   activated the fleet's env, that alone is harmless; `conda deactivate` and do
   not install, and say so in your handoff.
2. **Never start a Showdown server, and never let anything connect to the
   running one.** poke-env derives usernames from a globally-seeded `random`, so
   a stray connection collides with a lane's seat and the lane dies with a
   misleading `TimeoutError`. Concretely: no `node pokemon-showdown start`, no
   `poke_env` client code, no `pytest tests/` (the suite contains live-server
   tests), no `scripts/` that open a battle. If you believe you need a server,
   STOP and ask the maintainer.
3. **Never write to `runs/`, `logs/`, `wandb/`, `results/`, or `data/` in the
   main tree.** Read them if you must, by absolute path, read-only.
4. **Never run `git clean`, `git reset --hard`, or `git checkout` in the main
   tree.** `git clean -fdx` there would delete the gitignored `showdown/` server
   *and* all of `runs/` — worse than any `rm`.
5. **Never commit to `main` and never push anything.** You work on the branch
   `pkmn-engine-port` in your own worktree. `main` belongs to the babysitter
   session, which is committing to it while you work.
6. **Never edit these files** (they are the readout's, or they are pinned):
   `STATUS.md`, `SESSION_LOGS.md`, `RESULTS.md`, `README.md`, `readouts/*`,
   `JOURNEY.md`, `docs/IDEAS_POST_100M.md`, `docs/design_gen4/*`,
   `configs/gen4_wang50m*.yaml` (byte-pinned by `tests/test_gen4_prereg.py`).
   Anything you want to say about the port goes in
   `docs/engine_port/NOTES.md` **on your branch**.
7. **Never kill a process** you did not start, and never touch `caffeinate`.
   If the fleet looks wrong, report it — do not intervene.
8. **No throughput measurement.** Gates **T-1** (throughput), **D-1** (dynamics
   smoke, needs a server) and **A-1** (acceptance fleet) are OUT OF SCOPE while
   the fleet runs. Numbers taken next to three training lanes are invalid by
   this repo's own rules and would have to be thrown away.

## 2. Setup (run these in order, from the main repo root)

```
git worktree add /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl-engine -b pkmn-engine-port main
```

```
conda create -y -n pkmn-engine-port python=3.13
```

Then, from the **worktree** directory, install the repo editable into the new
env (never the fleet's env):

```
/opt/anaconda3/envs/pkmn-engine-port/bin/pip install -e ".[dev]"
```

Toolchain: `cargo`/`rustc` 1.97.1 are already on the box; `zig` and `maturin`
are not. Install `ziglang==0.16.0` and `maturin` into **your** env only, and pin
both in `engine/pkmn_gen1/pyproject.toml` (repo rule: exact pins).

Vendor `pkmn/engine` at the pinned commit
`9b88fd6c5467f703c38951d5b2e8a660314d410b` (plan §1.1) inside the worktree, and
name it in the README and in code comments (repo rule: name anything borrowed).

Data you need is gitignored, so the worktree does not have it. Read it from the
main tree by **absolute path**, never by writing through a symlink:
- tapes for parity gates: `/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/data/fp_tapes*/run_*.jsonl`
- team data for the teams gate: `/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown/data/random-battles/gen1/`

Resource discipline: `cargo build -j2` and `zig build -j2`, nothing wider, and
run every build and test **under background QoS** so the lanes keep priority:

```
taskpolicy -b cargo build -j2
```

This is not theoretical. MEASURED 2026-09-06: light doc-and-git work from
another session on this box moved lane rates 216 → 190–206 steps/s, a 5–12%
dip, recovering as soon as it stopped. A compile will cost more. The band's
RECORD line is 180, so an unthrottled build can push a lane's window out of
conformance and put a disclosure into someone else's readout.

Check `vm_stat` before anything heavy; keep your own footprint under ~2 GB.
Before and after any build, confirm you did no harm:

```
tail -3 /Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/logs/gen4_wang50m_wave.log
```

Lane rate must stay ≥ 180 steps/s and lanes must keep reporting `alive`. If a
build drops either, stop building and say so.

## 3. Scope: the six gates you may run, and where you stop

From plan §9, in order. Nothing downstream of a failed gate runs.

- **B-0 build** — `pkmn_gen1.verify()`, the engine's own Zig suite once at the
  pin, plus Rust tests for `layout.json` offsets and the two showdown-mode
  overrides, `Choice`/`Result` bit tests (`0x11`, `0x16`, `0x50`), name-map
  identity for 151 species / 165 moves against poke-env, base stats/types, max-PP.
- **B-1 loop smoke** — 10,000 random-policy battles **engine-only, no server**;
  every update legal by construction, outcomes in {Win, Lose, Tie}, never
  `Error`, turns ≤ 1000.
- **P-4 stats** — our §5.5 stats equal the `|request|` `stats` + `maxhp` for
  ≥ 1,000 own-side mons on the tapes. Exact, 100%.
- **P-3 teams** — per-team constraints on 100k draws; species marginals against
  `rl/envs/randbats_prior.py` (χ², n=100k).
- **P-1 encoder parity** — replay ≥ 5,000 tape decisions through poke-env
  (harness shape: `tests/test_encoder_ids_tapes.py`), rebuild the engine-side
  observable state, compare **828 floats bitwise** outside the declared
  families; report each family's count, total budget ≤ 1% of decisions.
  `OBS_DIM = 828` under `POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1`.
- **P-2 mask parity** — engine-derived mask equals `get_action_mask` per
  decision, 100% outside the Transform family; report the recharge / Wrap /
  locked-turn split against §7.2's table.

**STOP after P-2.** Do not attempt D-1, T-1 or A-1. Write the handoff (§5).

The two invariants everything is graded against (plan §7): the observation is a
function of what poke-env could observe from the protocol, never of the engine's
hidden state; and the 10-way action space, mask and block/slot orderings are
poke-env's, bit-for-bit where the information exists.

## 4. Time-box (a maintainer condition, not a suggestion)

P-1 and P-2 are where this project either lands in 16 evening blocks or balloons
to 40. Before you start P-1, write your block budget into
`docs/engine_port/NOTES.md`. Log hours against it. When you reach the budget,
**stop and write up what is blocking** rather than grinding — an honest "P-1 is
stuck on the Transform family, here is the evidence" is worth more than another
ten blocks of silent effort.

If an undeclared mismatch appears in P-1, it is a bug, not a family. Fix it or
declare it with a written reason (plan §9).

## 4b. Agents: no ultracode, read-only subagents only

**Do not run a workflow / ultracode fan-out for this.** Three reasons:

1. A fan-out means several agents compiling at once, and CPU contention is
   exactly what §2 forbids — light doc work from another session already moved
   lane rates 12% today.
2. The gates are strictly sequential; nothing downstream of a failed gate runs,
   so there is little to parallelise in the first place.
3. Bitwise parity across 828 fields against poke-env's information boundary
   needs ONE coherent mental model. Parallel agents each holding a partial model
   produce an inconsistent encoder, and the cost surfaces as debugging later.

**Do** use read-only subagents for bounded extraction that produces documents,
not code — `layout.json` offsets plus the two showdown-mode overrides; the
poke-env action-order / mask table §7.2 needs; an 828-field checklist derived
from `rl/envs/encoder_spec.py` and `rl/envs/showdown.py`; a catalogue of the tape
corpus. And one adversarial reviewer at the end, asking whether the parity
harness actually compares what it claims to compare.

**Every agent is model `opus`** (standing maintainer rule — Fable fan-outs
burned the usage limit twice). Keep the count small; each one costs tokens the
maintainer is watching.

## 5. Handing back

- Small, single-purpose commits on `pkmn-engine-port`. Never push.
- `docs/engine_port/NOTES.md` on the branch is your log: every gate, its exact
  numbers (family counts, χ² values, mismatch counts), hours spent, and every
  decision you made that the plan did not already make for you.
- Final report: which gates PASS with numbers, what is left, the block budget
  versus actual, and anything the plan got wrong (the plan expects to be
  corrected in place — say so rather than working around it).
- Do not delete the worktree, and do not merge to `main`. The maintainer or the
  babysitter session does that after the readout lands.
