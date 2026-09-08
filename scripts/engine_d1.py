#!/usr/bin/env python
"""Gate D-1 — engine vs server dynamics (docs/PKMN_ENGINE_RUST_PLAN.md §9).

The question D-1 answers is the ONE thing the offline gates cannot: does the
engine PLAY THE SAME GAME our Showdown server plays? B-0..P-2 proved the
projection, the encoder and the mask agree with poke-env given a state; they say
nothing about whether the engine reaches the same states. The engine's
`-Dshowdown` mode targets a PATCHED PS at `@pkmn/sim 0.9.31` and our server is
PS 0.11.11 (`59da482e`), so a gen-1 mechanic could differ.

METHOD. The same SCRIPTED policy on both seats, so nothing about a learned
policy enters. Two matchups (plan §9): `max_power` vs `max_power` and `random`
vs `random`.

TEAMS ARE DRAWN INDEPENDENTLY ON EACH LEG, not fed in common. An earlier draft
of this file proposed feeding the bank's pairs to the server through
`gen1customgame` so both legs played identical teams. The plan's own band
arithmetic rules that out: "se ~ 0.007 at n=10,000" is the se of a DIFFERENCE OF
TWO INDEPENDENT PROPORTIONS (sqrt(2 x 0.25/10000) = 0.00707), not a paired one,
so §9 already intends independent draws -- and the common-team scheme would have
changed the FORMAT to buy pairing the gate never asked for. Both legs therefore
play `gen1randombattle` team distributions from the same generator: the engine
reads the bank, which `scripts/engine_team_bank.py` generated with our own
Showdown at `59da482e`, and the server draws live from that same checkout. The
generator is common; only the SIMULATOR differs, which is the comparison.

Disclosed rather than fixed: the engine leg samples 10,000 battles from a
50,000-pair bank, so a few pairs recur (each with a fresh battle seed), while
the server draws fresh every battle. Same distribution, different finite-sample
structure; far below the bands.

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


class _DynamicsProbe:
    """Mixin over a poke-env `Player` that records what D-1 compares, WITH THE
    ENGINE LEG's OWN SEMANTICS.

    Sleep/freeze is "did it happen at any point", not "is it present at the
    end". The engine leg scans every party member at every decision point AND
    once after the final update (`scripted.rs::scan_status`); this scans both
    teams at every `choose_move` and once when the battle finishes. Getting
    this wrong in either direction invents a mechanic difference: an
    end-state-only read would miss a mon slept and then KO'd, which the engine
    leg sees.

    Coverage matches despite `opponent_team` holding only REVEALED mons: a mon
    can only be slept or frozen while active, and an active mon is revealed.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sleep_tags: set[str] = set()
        self.freeze_tags: set[str] = set()

    def choose_move(self, battle):
        self._scan(battle)
        return super().choose_move(battle)

    def _scan(self, battle) -> None:
        for mon in list(battle.team.values()) + list(battle.opponent_team.values()):
            status = getattr(mon, "status", None)
            name = getattr(status, "name", None)
            if name == "SLP":
                self.sleep_tags.add(battle.battle_tag)
            elif name == "FRZ":
                self.freeze_tags.add(battle.battle_tag)

    def scan_finished(self) -> None:
        """The post-final-update pass, mirroring the engine leg's."""
        for battle in self.battles.values():
            if battle.finished:
                self._scan(battle)


def _probe_player(key: str, username: str, seed: int, concurrency: int):
    """A registry opponent with the probe mixed in.

    The POKE-ENV ORIGINALS, never the in-engine ports: D-1 asks whether the two
    SIMULATORS agree, so running our port against itself would prove nothing.
    `/timer on` and an explicit distinct username are both mandatory (CLAUDE.md
    landmines: without a timer requester an abandoned room never ends and the
    leg wedges forever; poke-env derives usernames from globally-seeded
    `random`, so two processes on one box collide).
    """
    import inspect

    from poke_env.ps_client.account_configuration import AccountConfiguration

    from rl.envs.showdown import OPPONENT_PLAYERS

    base = OPPONENT_PLAYERS[key]
    cls = type(f"Probed{base.__name__}", (_DynamicsProbe, base), {})
    kwargs = dict(
        battle_format="gen1randombattle",
        account_configuration=AccountConfiguration(username, None),
        max_concurrent_battles=concurrency,
        start_timer_on_battle_start=True,
    )
    if "seed" in inspect.signature(base.__init__).parameters:
        kwargs["seed"] = seed
    return cls(**kwargs)


def _server_rows(a, b) -> dict:
    """Per-battle rows from P1's seat, in `_summarise`'s shape.

    `a` is P1 by construction: `battle_against` has `a` issue the challenges, and
    the challenger is p1 on the server — the same seat the engine leg scores
    from (`learner_seat: p1`).
    """
    from rl.envs.showdown import battle_outcome

    a.scan_finished()
    b.scan_finished()
    sleep = a.sleep_tags | b.sleep_tags
    freeze = a.freeze_tags | b.freeze_tags
    rows = {k: [] for k in ("outcome", "turns", "faints_p1", "faints_p2",
                            "any_sleep", "any_freeze")}
    for tag, battle in a.battles.items():
        if not battle.finished:
            continue
        # The repo's own convention (`rl/envs/showdown.py::battle_outcome`),
        # not a local reading of `battle.won`: +1 won, -1 lost, 0 tie, with the
        # tie falling through both flags. Ties are non-wins everywhere here.
        rows["outcome"].append(battle_outcome(battle))
        rows["turns"].append(battle.turn)
        rows["faints_p1"].append(sum(m.fainted for m in battle.team.values()))
        rows["faints_p2"].append(sum(m.fainted for m in battle.opponent_team.values()))
        rows["any_sleep"].append(tag in sleep)
        rows["any_freeze"].append(tag in freeze)
    return {k: np.asarray(v) for k, v in rows.items()}


def server_leg(bank: pathlib.Path, n: int, seed: int, concurrency: int = 8) -> dict:
    """The same policies on the real simulator.

    NEVER RUN. Written 2026-09-08 while a fleet owned the box, so every line
    below is UNVERIFIED against a live server: treat the first run as a
    bring-up, not as the gate, and read the sanity lines it prints before
    trusting a single number.

    Chunked and resume-safe (CLAUDE.md rule 4): each chunk's rows are appended
    to `<out>/server_partial.json`, so a death costs one chunk and progress is
    readable as a RATE against the engine leg's own s/battle.
    """
    import asyncio

    from rl.envs.engine_bank import read_bank

    header, _payload = read_bank(bank)  # provenance only; the server draws its own
    out = {}
    for p1, p2 in MATCHUPS:
        rows = {k: [] for k in ("outcome", "turns", "faints_p1", "faints_p2",
                                "any_sleep", "any_freeze")}
        done = 0
        t0 = time.perf_counter()
        while done < n:
            want = min(CHUNK, n - done)
            # A FRESH PAIR OF SEATS PER CHUNK. A killed arm's username pair is
            # poisoned for hours (the Foul-Play runner incidents), and a fresh
            # pair per chunk means a resume never reuses one.
            tag = f"d1{done // CHUNK}"
            a = _probe_player(p1, f"{tag}a{seed}", seed, concurrency)
            b = _probe_player(p2, f"{tag}b{seed}", seed + 1, concurrency)
            asyncio.run(a.battle_against(b, n_battles=want))
            chunk = _server_rows(a, b)
            got = len(chunk["turns"])
            if got != want:
                raise SystemExit(
                    f"{p1} vs {p2}: asked for {want} battles, {got} finished — "
                    "a room was abandoned; do not average over a short chunk"
                )
            for k in rows:
                rows[k].append(chunk[k])
            done += got
            print(f"  {p1} vs {p2}: {done}/{n} "
                  f"({(time.perf_counter() - t0) / done:.2f} s/battle)",
                  file=sys.stderr)
        out[f"{p1}_vs_{p2}"] = _summarise(
            {k: np.concatenate(v) for k, v in rows.items()}
        )
        out[f"{p1}_vs_{p2}"]["wall_seconds"] = time.perf_counter() - t0
    return {
        "leg": "server",
        "n": n,
        "seed": seed,
        "bank_sha256": header["sha256"],
        "ps_commit": header["ps_commit"],
        "battle_format": "gen1randombattle",
        "unverified": "this leg has never been run; treat the first run as bring-up",
        "matchups": out,
    }


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
