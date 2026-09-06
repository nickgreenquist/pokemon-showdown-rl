#!/usr/bin/env python
"""Gate driver for the pkmn/engine collector port (docs/PKMN_ENGINE_RUST_PLAN.md §9).

Subcommands, in gate order:

    b1   10,000 random-policy battles, engine-only. No server, no encoder.
    p4   §5.5 stats vs the |request| `stats` + `maxhp` on the Foul-Play tapes.
    p3   team-bank constraints and species marginals.
    p1   828-float encoder parity against poke-env, replayed from the tapes.
    p2   mask parity against poke-env's `get_action_mask`.

D-1 (dynamics smoke), T-1 (throughput) and A-1 (acceptance) are NOT here: they
need the Showdown server and/or an idle box, and are out of scope while a
training fleet is running (docs/engine_port_session_brief.md §3).

Borrowed: pkmn/engine (https://github.com/pkmn/engine), MIT,
(c) 2021-2024 pkmn contributors, vendored at the pinned commit.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pkmn_gen1


def _print_kv(d: dict, indent: str = "  ") -> None:
    width = max(len(k) for k in d)
    for k, v in d.items():
        if isinstance(v, float):
            print(f"{indent}{k:<{width}}  {v:.6g}")
        else:
            print(f"{indent}{k:<{width}}  {v}")


def cmd_b1(args: argparse.Namespace) -> int:
    """B-1: no panic, no `Error` outcome, outcomes in {Win, Lose, Tie}, turns <= 1000.

    `smoke_random_battles` raises on every one of those, so reaching the report
    IS the pass; mean turns and tie rate are recorded as descriptive numbers.
    """
    info = pkmn_gen1.verify()
    print(f"engine {info['engine_sha'][:12]}  zig {info['zig']}  options {info['options']}")

    ok = True
    for block, label in ((True, "blocked (engine's own fuzz config)"), (False, "all 164 moves")):
        t0 = time.perf_counter()
        s = pkmn_gen1.smoke_random_battles(args.n, args.seed, block)
        dt = time.perf_counter() - t0
        print(f"\n[B-1] {args.n} random-policy battles -- movesets: {label}")
        assert s["battles"] == args.n
        assert s["p1_wins"] + s["p2_wins"] + s["ties"] == args.n, "an outcome escaped {W,L,T}"
        if s["max_turns"] > 1000:
            print(f"  FAIL: max_turns {s['max_turns']} > 1000")
            ok = False
        _print_kv(
            {
                "p1_wins": s["p1_wins"],
                "p2_wins": s["p2_wins"],
                "ties": s["ties"],
                "  of which turn-1000/EBC": s["long_ties"],
                "tie_rate": s["tie_rate"],
                "p1_win_rate": s["p1_win_rate"],
                "mean_turns": s["mean_turns"],
                "min/max turns": f"{s['min_turns']} / {s['max_turns']}",
                "mean_updates/battle": s["mean_updates"],
                "learner decisions": s["decisions"],
                "  forced (1 choice)": s["forced_decisions"],
                "switch requests": s["switch_requests"],
                "wall seconds": dt,
                "battles/s (NOT a T-1 number)": args.n / dt if dt else float("inf"),
            }
        )
        if args.json:
            print(json.dumps({"block": block, **s}))

    print(
        "\n  battles/s above is INCIDENTAL: it includes team generation and the\n"
        "  wrapper's per-update legality check, it is a random policy with no\n"
        "  encoder, and it was measured next to other load. It is not a T-1\n"
        "  number and must not be quoted as one."
    )
    print(f"\n[B-1] {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def cmd_p4(args: argparse.Namespace) -> int:
    """P-4: exact, 100%, over >= 1,000 own-side mons."""
    from collections import Counter

    import engine_p4
    from engine_tapes import tape_paths

    paths = tape_paths(pathlib.Path(args.tapes_root) if args.tapes_root else None)
    if not paths:
        print("no tapes found -- pass --tapes-root", file=sys.stderr)
        return 2

    report: Counter = Counter()
    failures: list[str] = []
    seen: set = set()
    read = 0
    for path in paths:
        engine_p4.check_tape(path, report, failures, seen)
        read += 1
        print(
            f"  {path.name}: {len(seen)} distinct own-side mons, "
            f"{report['mismatched']} mismatched",
            flush=True,
        )
        # The gate counts DISTINCT mons: a mon reappears in every request of its
        # battle, and 7,200 repeats of 240 sets is not 7,200 sets.
        if len(seen) >= args.min_distinct and report["pp_checked"] >= args.min_mons:
            break

    print(f"[P-4] tapes read: {read} of {len(paths)}")
    _print_kv(
        {
            "own-side mons checked": report["mons_checked"],
            "  distinct (room, mon)": len(seen),
            "  with a max-HP reading": report["hp_checked"],
            "  mismatched": report["mismatched"],
            "skipped: transformed": report["skipped_transformed"],
            "skipped: fainted (no maxhp)": report["skipped_hp_fainted"],
            "skipped: no stats block": report["skipped_no_stats"],
            "engine records built": report["records_built"],
            "max-PP slots checked": report["pp_checked"],
            "  max-PP mismatched": report["pp_mismatched"],
            "  max-PP skipped: transformed": report["pp_skipped_transformed"],
        }
    )
    for f in failures[:25]:
        print(f"  MISMATCH {f}")

    reasons = []
    if report["mismatched"]:
        reasons.append(f"{report['mismatched']} stat mismatches")
    if report["pp_mismatched"]:
        reasons.append(f"{report['pp_mismatched']} max-PP mismatches")
    if failures:
        reasons.append(f"{len(failures)} reported failures")
    if len(seen) < args.min_distinct:
        reasons.append(f"only {len(seen)} distinct mons < --min-distinct {args.min_distinct}")
    if report["pp_checked"] < args.min_mons:
        reasons.append(f"only {report['pp_checked']} PP slots < --min-mons {args.min_mons}")
    if reasons:
        print(f"\n[P-4] FAIL: {'; '.join(reasons)}")
        return 1
    print("\n[P-4] PASS")
    return 0


def cmd_p3(args: argparse.Namespace) -> int:
    """P-3: the bank is Showdown's generator, not a guess."""
    from collections import Counter

    import engine_p3
    import engine_team_bank as bank

    path = pathlib.Path(args.bank)
    if not path.exists():
        print(f"no bank at {path} -- build one with scripts/engine_team_bank.py", file=sys.stderr)
        return 2

    header, payload = bank.read_bank(path)   # verifies the payload sha256
    print(f"[P-3] bank {path.name}")
    _print_kv(
        {
            "ps_commit": header["ps_commit"],
            "engine_sha": header["engine_sha"],
            "pairs": header["pairs"],
            "payload sha256": header["sha256"][:16] + "...",
        }
    )
    if not header["ps_commit"].startswith(args.ps_commit):
        print(f"  FAIL: PS commit is not {args.ps_commit}")
        return 1

    report: Counter = Counter()
    failures: list[str] = []
    t0 = time.perf_counter()
    stats = engine_p3.analyse(bank.iter_pairs(payload), report, failures)
    dt = time.perf_counter() - t0

    mm = stats["move_marginals"]
    _print_kv(
        {
            "pairs checked": report["pairs"],
            "teams checked": report["teams"],
            "mons checked": report["mons"],
            "constraint violations": len(failures),
            "pairs with a Ditto": report["pairs_with_ditto"],
            "  pairs with TWO Dittos": report["pairs_with_two_dittos"],
            "  Ditto in team 1 / team 2": f"{stats['ditto_teams_first']} / {stats['ditto_teams_second']}",
            "distinct species drawn": stats["distinct_species"],
            "species chi2 (even vs odd pairs)": stats["species_halves_chi2"],
            "  dof": stats["species_halves_dof"],
            "  p": stats["species_halves_p"],
            "move-marginal cells (stochastic)": mm["cells"],
            "  deterministic cells agreeing": mm["deterministic_cells_agreeing"],
            "  species covered": mm["species"],
            "  max |z| vs the prior": mm["max_abs_z"],
            "  Bonferroni |z| threshold": mm["bonferroni_threshold"],
            "  cells over threshold": mm["cells_over_threshold"],
            "wall seconds": dt,
        }
    )
    if stats["levels_multi_valued"]:
        print(f"  species with >1 level in the bank: {stats['levels_multi_valued']}")
    if mm["moves_in_bank_not_in_prior"]:
        print(f"  moves in the bank the prior never draws: {mm['moves_in_bank_not_in_prior']}")
    for w in mm["worst"][:5]:
        print(
            f"  worst cell: {w['species']}/{w['move']} bank={w['p_bank']:.4f} "
            f"prior={w['p_prior']:.4f} z={w['z']:+.2f}"
        )
    for f in failures[:20]:
        print(f"  VIOLATION {f}")

    rt = engine_p3.round_trip_battles(bank.iter_pairs(payload), args.round_trip, 0x9E3779B9)
    print(
        f"  round trip: {rt['battles']} bank battles played through the engine "
        f"({rt['win']}W/{rt['lose']}L/{rt['tie']}T, mean {rt['mean_turns']:.1f} turns)"
    )

    reasons = []
    if rt["battles"] != args.round_trip:
        reasons.append("round-trip battles did not all complete")
    if failures:
        reasons.append(f"{len(failures)} constraint violations")
    if report["pairs_with_two_dittos"]:
        reasons.append(f"{report['pairs_with_two_dittos']} pairs with two Dittos")
    if stats["levels_multi_valued"]:
        reasons.append("a species appeared at more than one level")
    if mm["moves_in_bank_not_in_prior"]:
        reasons.append("the bank draws moves the prior never does")
    if report["teams"] < args.min_teams:
        reasons.append(f"only {report['teams']} teams < --min-teams {args.min_teams}")
    if mm["cells_over_threshold"] > args.max_outlier_cells:
        reasons.append(
            f"{mm['cells_over_threshold']} move-marginal cells past the Bonferroni "
            f"threshold (allowed {args.max_outlier_cells})"
        )
    if stats["species_halves_p"] < 0.001:
        reasons.append(f"species halves disagree (p={stats['species_halves_p']:.2g})")
    if reasons:
        print(f"\n[P-3] FAIL: {'; '.join(reasons)}")
        return 1
    print("\n[P-3] PASS")
    return 0


def _not_yet(name: str):
    def run(args: argparse.Namespace) -> int:
        print(f"[{name}] not implemented yet", file=sys.stderr)
        return 2

    return run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="gate", required=True)

    b1 = sub.add_parser("b1", help="loop smoke: N random-policy battles, engine-only")
    b1.add_argument("-n", type=int, default=10_000)
    b1.add_argument("--seed", type=int, default=0xB1B1_B1B1)
    b1.add_argument("--json", action="store_true")
    b1.set_defaults(func=cmd_b1)

    p4 = sub.add_parser("p4", help="stats vs the |request| stats on the tapes")
    p4.add_argument("--tapes-root", default=None)
    p4.add_argument("--min-mons", type=int, default=1000)
    p4.add_argument("--min-distinct", type=int, default=1000)
    p4.set_defaults(func=cmd_p4)

    p3 = sub.add_parser("p3", help="team-bank constraints and species marginals")
    p3.add_argument("--bank", default="data/engine/teams_59da482e_e0e0_50000.bin")
    p3.add_argument("--ps-commit", default="59da482e")
    p3.add_argument("--min-teams", type=int, default=100_000)
    p3.add_argument("--max-outlier-cells", type=int, default=0)
    p3.add_argument("--round-trip", type=int, default=500)
    p3.set_defaults(func=cmd_p3)

    for gate, helptext in (
        ("p1", "828-float encoder parity"),
        ("p2", "mask parity"),
    ):
        p = sub.add_parser(gate, help=helptext)
        p.set_defaults(func=_not_yet(gate.upper()))

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
