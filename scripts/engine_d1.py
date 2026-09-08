#!/usr/bin/env python
"""Gate D-1 — engine vs server dynamics (docs/PKMN_ENGINE_RUST_PLAN.md §9).

The question D-1 answers is the ONE thing the offline gates cannot: does the
engine PLAY THE SAME GAME our Showdown server plays? B-0..P-2 proved the
projection, the encoder and the mask agree with poke-env given a state; they say
nothing about whether the engine reaches the same states. The engine's
`-Dshowdown` mode targets a PATCHED PS at `@pkmn/sim 0.9.31` and our server is
PS 0.11.11 (`59da482e`), so a gen-1 mechanic could differ.

METHOD. The same SCRIPTED policy on both seats, so nothing about a learned
policy enters, and both legs draw teams from the SAME team bank -- built by our
Showdown, so the team distribution is common by construction and only the
SIMULATOR differs. Two matchups (plan §9): `max_power` vs `max_power` and
`random` vs `random`.

BANDS (plan §9, restated verbatim so this file is self-contained):
    P1 win rate   |delta| < 0.02    (se ~ 0.007 at n=10,000)
    tie rate      |delta| < 0.005
    mean turns    |delta| < 5%
Secondary, descriptive: turn percentiles, faints per game, the fraction of
games containing a sleep and a freeze. A failure is NOT tuned away -- it is
localised with the engine's `debug-log` build before any training.

RUNNING IT. Three legs, run separately:

    python scripts/engine_d1.py --leg engine --bank data/engine/teams_*.bin
    python scripts/engine_d1.py --leg server --bank data/engine/teams_*.bin
    python scripts/engine_d1.py --leg compare

The SERVER leg needs a Showdown server and the engine leg is a measurement, so
NEITHER may run beside a training fleet -- both refuse to start if one is up
(`--force` overrides, and stamps `contended: true` into the output so the
number can never be quoted as clean). Each leg writes JSON to `--out`; the
compare leg reads both and applies the bands.

Resume-safe: each leg appends completed CHUNKS, so a death costs one chunk.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import time

import numpy as np

MATCHUPS = [("max_power", "max_power"), ("random", "random")]
BANDS = {"p1_win_rate": 0.02, "tie_rate": 0.005, "mean_turns_rel": 0.05}
DEFAULT_N = 10_000
CHUNK = 500


# --- the guard --------------------------------------------------------------


def fleet_is_running() -> list[str]:
    """Any `rl.train` lane or Showdown server we did not start. A measurement
    taken beside three training lanes is invalid by this repo's own rules
    (CLAUDE.md: a throughput window that straddles other work invents records),
    and the server leg would additionally collide with a lane's seat."""
    found = []
    for pattern, what in (
        ("[p]ython -m rl.train", "a training lane"),
        ("[n]ode pokemon-showdown", "a Showdown server"),
    ):
        r = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            found.append(f"{what} ({len(r.stdout.split())} process(es))")
    return found


def check_box(leg: str, force: bool, gate: str = "D-1") -> bool:
    """Returns whether the box was contended. Refuses unless --force."""
    busy = fleet_is_running()
    if leg == "server":
        # The server leg NEEDS a server, so a running one is only a problem if
        # a training fleet is using it.
        busy = [b for b in busy if "training lane" in b]
    if not busy:
        return False
    msg = f"{gate} is a measurement and the box is busy: " + "; ".join(busy)
    if not force:
        raise SystemExit(
            msg + "\nRun it when the box is idle, or pass --force to record a "
            "CONTENDED number (which is not quotable)."
        )
    print(f"WARNING: {msg} — recording contended: true", file=sys.stderr)
    return True


# --- the engine leg ---------------------------------------------------------


def engine_leg(bank: pathlib.Path, n: int, seed: int) -> dict:
    import pkmn_gen1

    from rl.envs.engine_bank import read_bank
    from rl.envs.engine_tables import build_tables

    tables, fp = build_tables()
    header, payload = read_bank(bank)
    out = {}
    for p1, p2 in MATCHUPS:
        # k=1: `scripted_series` runs its own battle loop and reads only the
        # lane seed, tables and bank from the BatchEnv.
        env = pkmn_gen1.BatchEnv(1, seed, tables, payload, "p1")
        rows = {k: [] for k in ("outcome", "turns", "faints_p1", "faints_p2",
                                "any_sleep", "any_freeze")}
        done = 0
        t0 = time.perf_counter()
        while done < n:
            chunk = env.scripted_series(min(CHUNK, n - done), p1, p2)
            for k in rows:
                rows[k].append(np.asarray(chunk[k]))
            done += len(chunk["turns"])
            print(f"  {p1} vs {p2}: {done}/{n}", file=sys.stderr)
        out[f"{p1}_vs_{p2}"] = _summarise(
            {k: np.concatenate(v) for k, v in rows.items()}
        )
        out[f"{p1}_vs_{p2}"]["wall_seconds"] = time.perf_counter() - t0
    return {
        "leg": "engine",
        "n": n,
        "seed": seed,
        "bank_sha256": header["sha256"],
        "ps_commit": header["ps_commit"],
        "engine_sha": pkmn_gen1.build_info()["engine_sha"],
        "tables_fingerprint": fp,
        "matchups": out,
    }


# --- the server leg ---------------------------------------------------------


def server_leg(bank: pathlib.Path, n: int, seed: int) -> dict:
    """The same battles on the real simulator.

    NOT IMPLEMENTED YET, on purpose: it needs a Showdown server, and this file
    was written while a fleet owned the box. What it must do is written out
    here so the implementation is a mechanical step and not a design one.

    1. Feed the SAME team pairs. `rl/envs/engine_bank.iter_pairs` unpacks a
       bank entry into two six-mon sets; each becomes a poke-env `teampreview`-
       free custom team through `Player(team=...)` in the `gen1customgame`
       format -- NOT `gen1randombattle`, whose server-side generator would draw
       its own teams and destroy the common-team property this gate rests on.
    2. Play `p1` vs `p2` from `OPPONENT_PLAYERS` (the poke-env originals, not
       the ports: comparing our port against itself would prove nothing).
    3. Record per battle: outcome from P1's seat, `battle.turn`, both sides'
       faint counts, and whether any `|-status|...|slp` / `|frz` line appeared.
       `save_replays` or a tape gives the last one without new plumbing.
    4. Emit exactly the `_summarise` shape below, so `--leg compare` is common.

    Two traps the implementation must respect, both from CLAUDE.md:
      * every connecting seat sends `/timer on`, or an abandoned room never
        ends and the leg wedges forever;
      * concurrent seats need distinct usernames -- poke-env derives them from
        globally-seeded `random`, so a second D-1 process on one box collides.
    """
    raise SystemExit(
        "the server leg is not implemented (see this function's docstring for "
        "the four steps and the two traps); it needs a Showdown server, which "
        "the engine-port session was forbidden to start"
    )


# --- shared -----------------------------------------------------------------


def _summarise(rows: dict) -> dict:
    outcome = np.asarray(rows["outcome"], dtype=np.int64)
    turns = np.asarray(rows["turns"], dtype=np.float64)
    n = len(outcome)
    return {
        "battles": n,
        "p1_win_rate": float((outcome > 0).mean()),
        "p2_win_rate": float((outcome < 0).mean()),
        "tie_rate": float((outcome == 0).mean()),
        "mean_turns": float(turns.mean()),
        "turns_p10": float(np.percentile(turns, 10)),
        "turns_p50": float(np.percentile(turns, 50)),
        "turns_p90": float(np.percentile(turns, 90)),
        "turns_max": float(turns.max()),
        "mean_faints_p1": float(np.mean(rows["faints_p1"])),
        "mean_faints_p2": float(np.mean(rows["faints_p2"])),
        "sleep_fraction": float(np.mean(rows["any_sleep"])),
        "freeze_fraction": float(np.mean(rows["any_freeze"])),
        # The binomial se on the primary read, for the band's own arithmetic.
        "p1_win_rate_se": float(np.sqrt(0.25 / max(n, 1))),
    }


def compare(engine: dict, server: dict) -> dict:
    """The verdict. Every band is two-sided and reads the ABSOLUTE delta; the
    signed delta is reported alongside and stays in the record forever."""
    report = {"bands": BANDS, "matchups": {}, "pass": True}
    for key in engine["matchups"]:
        e, s = engine["matchups"][key], server["matchups"].get(key)
        if s is None:
            report["matchups"][key] = {"status": "MISSING on the server leg"}
            report["pass"] = False
            continue
        d_win = e["p1_win_rate"] - s["p1_win_rate"]
        d_tie = e["tie_rate"] - s["tie_rate"]
        d_turns = (e["mean_turns"] - s["mean_turns"]) / max(s["mean_turns"], 1e-9)
        checks = {
            "p1_win_rate": (d_win, abs(d_win) < BANDS["p1_win_rate"]),
            "tie_rate": (d_tie, abs(d_tie) < BANDS["tie_rate"]),
            "mean_turns_rel": (d_turns, abs(d_turns) < BANDS["mean_turns_rel"]),
        }
        report["matchups"][key] = {
            "engine": e,
            "server": s,
            "deltas": {k: v for k, (v, _) in checks.items()},
            "pass": {k: ok for k, (_, ok) in checks.items()},
            # Descriptive only; no band, reported because a mechanic difference
            # shows here first even when the primaries pass.
            "descriptive_deltas": {
                k: e[k] - s[k]
                for k in ("mean_faints_p1", "mean_faints_p2",
                          "sleep_fraction", "freeze_fraction",
                          "turns_p50", "turns_p90")
            },
        }
        report["pass"] &= all(ok for _, ok in checks.values())
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--leg", required=True, choices=("engine", "server", "compare"))
    ap.add_argument("--bank", type=pathlib.Path)
    ap.add_argument("--n", type=int, default=DEFAULT_N)
    ap.add_argument("--seed", type=int, default=20260907)
    ap.add_argument("--out", type=pathlib.Path, default=pathlib.Path("results/d1"))
    ap.add_argument("--force", action="store_true",
                    help="record a CONTENDED number rather than refusing")
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    if args.leg == "compare":
        engine = json.loads((args.out / "engine.json").read_text())
        server = json.loads((args.out / "server.json").read_text())
        report = compare(engine, server)
        (args.out / "compare.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report["matchups"], indent=2)[:4000])
        print("D-1", "PASS" if report["pass"] else "FAIL")
        return 0 if report["pass"] else 1

    if args.bank is None:
        raise SystemExit("--bank is required for a data leg")
    contended = check_box(args.leg, args.force)
    fn = engine_leg if args.leg == "engine" else server_leg
    result = fn(args.bank, args.n, args.seed)
    result["contended"] = contended
    result["started_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    (args.out / f"{args.leg}.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result["matchups"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
