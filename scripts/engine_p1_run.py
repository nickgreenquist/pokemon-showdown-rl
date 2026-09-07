"""P-1 replay driver. Runs as a SUBPROCESS because the encoder flags are read at
import (`POKEMON_RL_ENCODER_V2` / `POKEMON_RL_ENCODER_IDS`), exactly as
`tests/test_encoder_ids_tapes.py` does.

Prints a JSON report on stdout.
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from collections import Counter

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import numpy as np
from poke_env.battle import Battle
from poke_env.data import GenData

from rl.envs.showdown import ID_DIM, OBS_DIM, embed_battle

assert OBS_DIM == 828 and ID_DIM == 20, (OBS_DIM, ID_DIM)

import engine_p1  # noqa: E402
import engine_p2  # noqa: E402
from engine_tapes import iter_events, tape_paths  # noqa: E402
from rl.envs.engine_tables import build_tables  # noqa: E402

import pkmn_gen1  # noqa: E402

# A stale editable install is invisible otherwise: `cargo build` refreshes
# target/, the importable extension only changes on `pip install -e`.
STATE_SCHEMA = 2
if getattr(pkmn_gen1, "__state_schema__", 0) != STATE_SCHEMA:
    raise SystemExit(
        f"pkmn_gen1 state schema is {getattr(pkmn_gen1, '__state_schema__', 0)}, "
        f"this harness writes {STATE_SCHEMA} -- rebuild with:\n"
        "  pip install --no-build-isolation -e engine/pkmn_gen1"
    )

MESSAGES_TO_IGNORE = {"t:", "expire", "uhtmlchange"}
LOGGER = logging.getLogger("tape_replay")
LOGGER.addHandler(logging.NullHandler())
LOGGER.setLevel(logging.CRITICAL)
TYPE_CHART = GenData.from_gen(1).type_chart


def infer_username(path):
    for ev in iter_events(path):
        if ev.get("k") != "m":
            continue
        for line in ev["v"].split("\n"):
            parts = line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser" and parts[2].strip():
                name = parts[2].strip()
                if not name.lower().startswith("guest "):
                    return name
    return None


def apply_message(battle, raw, state):
    for line in raw.split("\n")[1:]:
        sm = line.split("|")
        if len(sm) <= 1:
            continue
        tag = sm[1]
        if tag == "":
            battle.parse_message(sm)
        elif tag in MESSAGES_TO_IGNORE:
            continue
        elif tag == "request":
            if len(sm) > 2 and sm[2]:
                req = json.loads(sm[2])
                battle.parse_request(req)
                state["request"] = req
        elif tag == "win":
            battle.won_by(sm[2])
        elif tag == "tie":
            battle.tied()
        elif tag in ("error", "bigerror"):
            continue
        else:
            battle.parse_message(sm)


def mutate_reference(which: str) -> None:
    """Corrupt one rule in `rl.envs.showdown` ONLY (never in the Rust path or in
    `engine_p1.py`), so a gate that cannot see the corruption is proved blind.

    The rules chosen are the two an adversarial review showed were previously
    shared with the harness and therefore unfalsifiable.
    """
    import rl.envs.showdown as sd

    if which == "alias":
        sd._move_slots_aliased = lambda battle, spec=None: False
    elif which == "opp_order":
        original = sd._opponent_move_slots
        sd._opponent_move_slots = lambda theirs: list(reversed(original(theirs)))
    elif which == "prior":
        original = sd._opponent_move_slots
        sd._opponent_move_slots = lambda theirs: [(m, 0.5) for m, _ in original(theirs)]


def exposure(battle) -> list[str]:
    """Which declared families this decision is EXPOSED to, whether or not it
    mismatches. Without this the family counts are zero by construction."""
    out = []
    ours = battle.active_pokemon
    theirs = battle.opponent_active_pokemon
    if (ours is not None and ours.transformed) or (theirs is not None and theirs.transformed):
        out.append("transform")
    for mon in (ours, theirs):
        if mon is not None and any(m.id == "struggle" for m in mon.moves.values()):
            out.append("struggle_slot")
            break
    for mon in (ours, theirs):
        if mon is not None and any(m.id == "mirrormove" for m in mon.moves.values()):
            out.append("mirror_move")
            break
    return out


def classify(battle, idxs) -> str:
    """Which declared non-parity family (plan §7.1.1 / §7.2), if any, a
    mismatching decision belongs to. 'undeclared' is a BUG, not a family."""
    ours = battle.active_pokemon
    theirs = battle.opponent_active_pokemon
    fields = {engine_p1.describe_index(i).split(".", 1)[0] for i in idxs}
    if (ours is not None and ours.transformed) or (theirs is not None and theirs.transformed):
        return "transform"
    if any(f.startswith("opp_move") for f in fields) and theirs is not None:
        if any(m.id == "struggle" for m in theirs.moves.values()):
            return "struggle_slot"
    if any(f.startswith("own_move") for f in fields) and ours is not None:
        if any(m.id == "struggle" for m in ours.moves.values()):
            return "struggle_slot"
    return "undeclared"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=6000)
    ap.add_argument("--tapes-root", default=None)
    ap.add_argument("--max-examples", type=int, default=12)
    ap.add_argument("--gate", choices=("p1", "p2"), default="p1")
    ap.add_argument(
        "--mutate",
        choices=("none", "alias", "opp_order", "prior"),
        default="none",
        help="POSITIVE CONTROL: corrupt one per-decision rule in the REFERENCE "
        "encoder only. A gate that still reports 0 mismatches is blind to that "
        "rule -- which is how the first version of this harness was caught.",
    )
    args = ap.parse_args()
    if args.mutate != "none":
        mutate_reference(args.mutate)

    tables, fingerprint = build_tables()
    assert tables.obs_dim == OBS_DIM

    paths = tape_paths(pathlib.Path(args.tapes_root) if args.tapes_root else None)
    decisions = 0
    mismatched = 0
    families: Counter = Counter()
    families_seen: Counter = Counter()
    field_counts: Counter = Counter()
    examples: list[dict] = []
    tapes_read = 0
    p2_report: Counter = Counter()
    p2_failures: list[str] = []
    # The FIRST request's party order per room -- poke-env's team dict order.
    p2_orders: dict[str, dict[str, int]] = {}

    for path in paths:
        if decisions >= args.target:
            break
        username = infer_username(path)
        if not username:
            continue
        tapes_read += 1
        battles, states = {}, {}
        for ev in iter_events(path):
            if decisions >= args.target:
                break
            if ev["k"] == "m":
                head = ev["v"].split("\n", 1)[0]
                if not head.startswith(">battle-"):
                    continue
                room = head[1:]
                if room not in battles:
                    battles[room] = Battle(room, username, LOGGER, gen=1)
                    states[room] = {"request": None}
                try:
                    apply_message(battles[room], ev["v"], states[room])
                except Exception:
                    states[room]["request"] = None  # poisoned: skip its decisions
                continue
            room = ev["tag"]
            if room not in battles:
                continue
            req = states[room]["request"]
            if req is None or req.get("rqid") != ev.get("rqid"):
                continue
            battle = battles[room]

            if args.gate == "p2":
                engine_p2.check_decision(
                    battle, req, p2_report, p2_failures, room,
                    p2_orders.setdefault(room, {}),
                )
                decisions += 1
                continue

            # Family EXPOSURE, counted on EVERY decision -- not only on
            # mismatching ones, where a zero would be true by construction.
            for fam in exposure(battle):
                families_seen[fam] += 1

            ref = embed_battle(battle, TYPE_CHART)
            state = engine_p1.state_from_battle(battle, req)
            ours = np.asarray(tables.encode(state))
            idxs = engine_p1.compare(ref, ours)
            decisions += 1
            if idxs:
                mismatched += 1
                fam = classify(battle, idxs)
                families[fam] += 1
                for i in idxs:
                    field_counts[engine_p1.describe_index(i)] += 1
                if len(examples) < args.max_examples:
                    examples.append(
                        {
                            "room": room,
                            "turn": int(battle.turn),
                            "family": fam,
                            "n_fields": len(idxs),
                            "fields": [
                                {
                                    "field": engine_p1.describe_index(i),
                                    "ref": float(ref[i]),
                                    "ours": float(ours[i]),
                                }
                                for i in idxs[:8]
                            ],
                        }
                    )

    if args.gate == "p2":
        print(
            json.dumps(
                {
                    "tapes_read": tapes_read,
                    "decisions": decisions,
                    "report": dict(p2_report),
                    "failures": p2_failures,
                }
            )
        )
        return 0

    print(
        json.dumps(
            {
                "tapes_read": tapes_read,
                "decisions": decisions,
                "mismatched_decisions": mismatched,
                "families": dict(families),
                "family_exposure": dict(families_seen),
                "top_fields": field_counts.most_common(20),
                "examples": examples,
                "tables_fingerprint": fingerprint,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
