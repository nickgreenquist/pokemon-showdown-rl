"""Foul Play (gen-4 engine build) vs a stock poke-env seat on a LOCAL server —
the anchors_and_eval.md §3 smoke, recorded as a tape.

Two environments, one server, exactly as scripts/foulplay_vs_sh.py documents:
Foul Play runs from its OWN conda env (here `foul-play-gen4`, poke-engine
0.0.48 built with `--features poke-engine/gen4`) as a subprocess in
`challenge_user` mode; our seat is a LISTENING poke-env player (SH by
default, or random / max_power / most_damage_typed) that accepts its
challenges, wrapped in the tape recorder so every message it sees is
replayable. Foul Play's stdout goes to a log we grep afterwards for the
things that matter: Rust panics, "More than 4 moves on pokemon" (the
engine-bridge index hole), tracebacks, `Unavailable choice`, and which set
file it loaded.

    python scripts/gen4_fp_smoke.py --battles 5 --search-time-ms 20 --port 8001

Nothing here is a protocol number: n is tiny and the seat is a scripted bot.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import signal
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poke_env.ps_client import AccountConfiguration, ServerConfiguration  # noqa: E402

from rl.envs.gen4.tape import TapeWriter, protocol_stats  # noqa: E402
from scripts.gen4_smoke import PLAYERS, TapeMixin, _WarningTally  # noqa: E402

FP_DIR = Path(os.environ.get("FPDIR", Path(__file__).resolve().parents[2] / "foul-play"))
FP_PY = Path(os.environ.get("FPPY", "/opt/anaconda3/envs/foul-play-gen4/bin/python"))

_GREPS = {
    "panic": re.compile(r"panicked|PanicException|Invalid PokemonMoveIndex"),
    "more_than_4_moves": re.compile(r"More than 4 moves on pokemon"),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "unavailable_choice": re.compile(r"Unavailable choice"),
    "invalid_choice": re.compile(r"Invalid choice"),
    "loaded_from_cache": re.compile(r"Loaded from cache: (\S+)"),
    "downloaded": re.compile(r"Downloaded and cached from remote"),
    "regenerator": re.compile(r"regenerator", re.I),
    "error_line": re.compile(r"^ERROR", re.M),
}


def _launch_fp(cmd: list[str], log_fh) -> subprocess.Popen:
    """Foul Play in its OWN process group, so a stop reaches its search workers."""
    return subprocess.Popen(cmd, cwd=str(FP_DIR), stdout=log_fh, stderr=subprocess.STDOUT,
                            start_new_session=True)


def _stop_fp(fp: subprocess.Popen, grace_s: float = 60.0) -> None:
    """Reap Foul Play AND its `--search-parallelism` workers (scripts/ch3_r4_fp_runner.sh
    :177-195 exists because killing only the parent orphaned live workers that kept
    the room and poisoned the username pair for hours). The whole process group gets
    SIGTERM, then SIGKILL; the parent is waited so fp.returncode is the signal."""
    try:
        fp.wait(timeout=grace_s)
        return
    except subprocess.TimeoutExpired:
        pass
    for sig, wait_s in ((signal.SIGTERM, 15.0), (signal.SIGKILL, 15.0)):
        try:
            os.killpg(fp.pid, sig)
        except ProcessLookupError:
            break
        try:
            fp.wait(timeout=wait_s)
            break
        except subprocess.TimeoutExpired:
            continue


async def _progress(seat, t0: float, total: int, every_s: float = 60.0) -> None:
    """One line a minute — the RATE a babysitter reads (CLAUDE.md rule 4(iii))."""
    while True:
        await asyncio.sleep(every_s)
        n = seat.n_finished_battles
        el = time.time() - t0
        print(f"progress: {n}/{total} battles, W-L-T {seat.n_won_battles}-{seat.n_lost_battles}-"
              f"{seat.n_tied_battles}, {el / max(n, 1):.1f} s/battle, {el / 60:.0f} min", flush=True)


def _server(port: int) -> ServerConfiguration:
    return ServerConfiguration(
        f"ws://localhost:{port}/showdown/websocket",
        "https://play.pokemonshowdown.com/action.php?",
    )


async def _run(args) -> dict:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tape_path = out / f"{args.tag}.jsonl"
    tape = TapeWriter(tape_path)  # streamed per batch, never buffered in RAM
    stats: Counter = Counter()
    pid = os.getpid() % 10000
    seat_name = f"g4fp{args.tag[:4]}s{pid}"[:18]
    fp_name = f"g4fp{args.tag[:4]}f{pid}"[:18]
    base = PLAYERS[args.seat]
    cls = type(f"Tape{base.__name__}", (TapeMixin, base), {})
    seat = cls(
        account_configuration=AccountConfiguration(seat_name, None),
        battle_format=args.format,
        server_configuration=_server(args.port),
        max_concurrent_battles=1,
        start_timer_on_battle_start=True,  # every seat that plays foul-play sends /timer on
        log_level=logging.WARNING,
        tape=tape,
        stats=stats,
    )
    fp_log = out / f"{args.tag}.foulplay.log"
    cmd = [
        str(FP_PY), "run.py",
        "--websocket-uri", f"ws://localhost:{args.port}/showdown/websocket",
        "--ps-username", fp_name,
        "--bot-mode", "challenge_user",
        "--user-to-challenge", seat_name,
        "--pokemon-format", args.format,
        "--search-time-ms", str(args.search_time_ms),
        "--search-parallelism", str(args.search_parallelism),
        "--run-count", str(args.battles),
        "--log-level", args.fp_log_level,
    ]
    t0 = time.time()
    # give the seat a moment to log in before the challenge arrives
    accept = asyncio.create_task(seat.accept_challenges(fp_name, args.battles))
    await asyncio.sleep(3.0)
    timed_out = False
    ticker = asyncio.create_task(_progress(seat, t0, args.battles))
    with fp_log.open("w") as fh:
        fp = _launch_fp(cmd, fh)
        try:
            await asyncio.wait_for(accept, timeout=args.timeout)
        except asyncio.TimeoutError:
            timed_out = True  # the seat stops accepting; the tape and summary below still land
        finally:
            ticker.cancel()
            _stop_fp(fp)
    wall = time.time() - t0
    tape.close()
    text = fp_log.read_text(errors="replace")
    greps = {k: len(p.findall(text)) for k, p in _GREPS.items()}
    m = _GREPS["loaded_from_cache"].search(text)
    return {
        "format": args.format,
        "seat": args.seat,
        "search_time_ms": args.search_time_ms,
        "search_parallelism": args.search_parallelism,
        "battles": args.battles,
        "fp_env_python": str(FP_PY),
        "fp_dir": str(FP_DIR),
        "fp_exit_code": fp.returncode,
        "timed_out": timed_out,
        "wall_s": round(wall, 1),
        "s_per_battle": round(wall / max(args.battles, 1), 2),
        "seat_record": [seat.n_won_battles, seat.n_lost_battles, seat.n_tied_battles],
        "fp_log": str(fp_log),
        "fp_log_greps": greps,
        "fp_sets_loaded_from": m.group(1) if m else None,
        "decision_facts_seat": dict(stats.most_common()),
        "tape": str(tape_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--battles", type=int, default=5)
    ap.add_argument("--seat", choices=sorted(PLAYERS), default="heuristics")
    ap.add_argument("--format", default="gen4randombattle")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--search-time-ms", type=int, default=20)
    ap.add_argument("--search-parallelism", type=int, default=1)
    ap.add_argument("--fp-log-level", default="INFO")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--tag", default="fp_smoke")
    ap.add_argument("--out", default="data/gen4_fp")
    args = ap.parse_args()
    tally = _WarningTally()
    logging.getLogger("poke-env").addHandler(tally)
    logging.getLogger().addHandler(tally)
    logging.getLogger().setLevel(logging.WARNING)
    summary = asyncio.run(_run(args))
    summary["poke_env_warnings"] = dict(tally.counts.most_common())
    summary["protocol"] = protocol_stats(summary["tape"])
    with open(Path(args.out) / f"{args.tag}.summary.json", "w") as fh:
        json.dump(summary, fh, indent=1, default=str)
    p = summary["protocol"]
    print(f"FP@{args.search_time_ms} vs {args.seat}: battles={args.battles} fp_exit={summary['fp_exit_code']} "
          f"wall={summary['wall_s']}s s/battle={summary['s_per_battle']} seat_record(W-L-T)={summary['seat_record']} "
          f"outcomes={p['outcomes']} turns={p['turns']}")
    print("fp log greps:", summary["fp_log_greps"], "| sets from:", summary["fp_sets_loaded_from"])
    print("seat errors:", p["errors"], "| poke-env warnings:", summary["poke_env_warnings"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
