"""Local gen4randombattle smoke + tape recorder — the design_gen4 [live] checks.

Plays N battles on the LOCAL Showdown server (ws://localhost:8000,
`--no-security`) between two stock poke-env players, records every raw
battle message BOTH seats receive as a replayable tape
(rl/envs/gen4/tape.py), tallies the protocol facts docs/design_gen4/* mark
[live], and captures poke-env's UNKNOWN-string warnings. Nothing here
trains, evaluates a checkpoint, or imports the gen-1 encoder.

    python scripts/gen4_smoke.py --battles 20 --player random --opponent heuristics --tag rnd_vs_sh

Outputs (under --out, default data/gen4_tapes/, gitignored):
    <tag>.jsonl          the tape (both seats)
    <tag>.summary.json   protocol tallies + decision-time facts + warnings

Rule 2 of CLAUDE.md: usernames are derived here explicitly (not from the
global `random` stream), unique per process, so two smokes never collide.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import json
import logging
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from poke_env.player import (  # noqa: E402
    MaxBasePowerPlayer,
    Player,
    RandomPlayer,
    SimpleHeuristicsPlayer,
)
from poke_env.ps_client import AccountConfiguration, LocalhostServerConfiguration  # noqa: E402

from rl.envs.gen4.tape import protocol_stats  # noqa: E402
from rl.envs.most_damage_typed import MostDamageTypedPlayer  # noqa: E402

PLAYERS = {
    "random": RandomPlayer,
    "max_power": MaxBasePowerPlayer,
    "heuristics": SimpleHeuristicsPlayer,
    "most_damage_typed": MostDamageTypedPlayer,
}


class _WarningTally(logging.Handler):
    """Every WARNING+ record poke-env emits, histogrammed by message."""

    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.counts: Counter = Counter()

    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001
            msg = str(record.msg)
        self.counts[f"{record.name}|{msg[:160]}"] += 1


class TapeMixin:
    """Records every batch this seat receives, and decision-time facts."""

    def __init__(self, *args, tape: list, stats: Counter, **kwargs):
        super().__init__(*args, **kwargs)
        self._tape = tape
        self._stats = stats

    async def _handle_battle_message(self, split_messages):
        self._tape.append(
            {"seat": self.username, "room": split_messages[0][0], "batch": split_messages}
        )
        try:
            await super()._handle_battle_message(split_messages)
        except Exception as exc:  # noqa: BLE001 — count, then let poke-env's handler see it
            self._stats[f"handler_exception|{type(exc).__name__}: {str(exc)[:120]}"] += 1
            raise

    def choose_move(self, battle):
        s = self._stats
        s["decisions"] += 1
        req = battle._last_request or {}
        if battle.maybe_trapped:
            s["maybe_trapped"] += 1
            if not battle.trapped:
                s["maybe_trapped_and_not_trapped"] += 1
        if battle.trapped:
            s["trapped"] += 1
        if battle.force_switch:
            s["force_switch"] += 1
            s["force_switch_request_has_active"] += "active" in req
            s["force_switch_with_available_moves"] += bool(battle.available_moves)
        if battle.active_pokemon is not None:
            mon = battle.active_pokemon
            if mon.item == "":
                s["own_active_item_empty_string"] += 1
            elif mon.item is None:
                s["own_active_item_None"] += 1
            if mon.ability is None:
                s["own_active_ability_None"] += 1
            if mon.status is not None and mon.status.name == "SLP":
                s[f"slp_counter|{mon.status_counter}"] += 1
            if mon.status is not None and mon.status.name == "TOX":
                s[f"tox_counter|{mon.status_counter}"] += 1
        opp = battle.opponent_active_pokemon
        if opp is not None:
            s[f"opp_item|{'unknown' if opp.item == 'unknown_item' else 'None' if opp.item is None else 'known'}"] += 1
            s[f"opp_ability|{'None' if opp.ability is None else 'known'}"] += 1
            s[f"opp_n_possible_abilities|{len(opp.possible_abilities)}"] += 1
            if opp.stats and any(v is not None for v in opp.stats.values()):
                s["opp_stats_present"] += 1
        if battle.weather:
            for w, t in battle.weather.items():
                s[f"weather_stamp_age|{w.name}|{battle.turn - t}"] += 1
        return super().choose_move(battle)


def _make(cls_name: str, username: str, tape: list, stats: Counter, fmt: str, concurrent: int, strict: bool):
    base = PLAYERS[cls_name]
    cls = type(f"Tape{base.__name__}", (TapeMixin, base), {})
    kwargs = dict(
        account_configuration=AccountConfiguration(username, None),
        battle_format=fmt,
        server_configuration=LocalhostServerConfiguration,
        max_concurrent_battles=concurrent,
        start_timer_on_battle_start=True,  # landmine: every seat sends /timer on
        log_level=logging.WARNING,
        tape=tape,
        stats=stats,
    )
    params = inspect.signature(Player.__init__).parameters
    if strict:
        assert "strict_battle_tracking" in params, "poke-env has no strict_battle_tracking kwarg"
        kwargs["strict_battle_tracking"] = True
    return cls(**kwargs)


async def _run(args) -> dict:
    tape: list = []
    stats_a: Counter = Counter()
    stats_b: Counter = Counter()
    pid = os.getpid() % 10000
    name_a = f"g4{args.tag[:5]}a{pid}"[:18]
    name_b = f"g4{args.tag[:5]}b{pid}"[:18]
    p_a = _make(args.player, name_a, tape, stats_a, args.format, args.concurrent, args.strict)
    p_b = _make(args.opponent, name_b, tape, stats_b, args.format, args.concurrent, args.strict)
    t0 = time.time()
    await p_a.battle_against(p_b, n_battles=args.battles)
    wall = time.time() - t0
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tape_path = out / f"{args.tag}.jsonl"
    with tape_path.open("w") as fh:
        for ev in tape:
            fh.write(json.dumps(ev) + "\n")
    summary = {
        "format": args.format,
        "player": args.player,
        "opponent": args.opponent,
        "battles": args.battles,
        "seats": {"a": name_a, "b": name_b},
        "wall_s": round(wall, 1),
        "s_per_battle": round(wall / max(args.battles, 1), 2),
        "a_record": [p_a.n_won_battles, p_a.n_lost_battles, p_a.n_tied_battles],
        "decision_facts_a": dict(stats_a.most_common()),
        "decision_facts_b": dict(stats_b.most_common()),
        "tape": str(tape_path),
        "tape_lines": len(tape),
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--battles", type=int, default=10)
    ap.add_argument("--player", choices=sorted(PLAYERS), default="random")
    ap.add_argument("--opponent", choices=sorted(PLAYERS), default="heuristics")
    ap.add_argument("--format", default="gen4randombattle")
    ap.add_argument("--concurrent", type=int, default=1)
    ap.add_argument("--strict", action="store_true", help="poke-env strict_battle_tracking=True")
    ap.add_argument("--tag", default="smoke")
    ap.add_argument("--out", default="data/gen4_tapes")
    args = ap.parse_args()

    tally = _WarningTally()
    logging.getLogger("poke-env").addHandler(tally)
    logging.getLogger().addHandler(tally)  # per-username player loggers propagate here
    logging.getLogger().setLevel(logging.WARNING)

    summary = asyncio.run(_run(args))
    summary["warnings"] = dict(tally.counts.most_common())
    summary["protocol"] = protocol_stats(summary["tape"])
    with open(Path(args.out) / f"{args.tag}.summary.json", "w") as fh:
        json.dump(summary, fh, indent=1, default=str)
    p = summary["protocol"]
    print(f"battles={args.battles} wall={summary['wall_s']}s s/battle={summary['s_per_battle']} "
          f"record(a)={summary['a_record']} rooms={p['rooms']} outcomes={p['outcomes']} turns={p['turns']}")
    print("errors:", p["errors"])
    print("request shapes:", p["request_shapes"])
    print("active keys:", p["request_active_keys"])
    print("pokemon keys:", p["request_pokemon_keys"])
    print("decision facts a:", summary["decision_facts_a"])
    print("decision facts b:", summary["decision_facts_b"])
    print("warnings:", summary["warnings"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
