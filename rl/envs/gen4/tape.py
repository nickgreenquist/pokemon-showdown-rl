"""Replayable protocol tapes for gen-4 bring-up.

A tape is a JSONL file, one line per websocket batch a seat received:

    {"seat": "<username>", "room": "battle-gen4randombattle-12",
     "batch": [["", "init", "battle"], ["", "title", ...], ...]}

`batch` is exactly the `split_messages` list poke-env's
`Player._handle_battle_message` receives (poke_env/player/player.py), so
`replay_tape` can rebuild a `Battle` per (seat, room) and drive it through
poke-env's OWN `parse_request` / `parse_message` — the same code path a live
player runs — and call back at every decision point with the battle object
and the request. That is what lets an encoder be exercised offline on real
gen-4 states with no server, and what the gen-4 tape hash gate will pin.

PURITY: tapes are bring-up instruments and eval evidence — they are NEVER
training data, and no training path imports this module (the pure self-play
lane admits no expert or replay data; RESULTS §1). Recorded by
scripts/gen4_smoke.py (the design_gen4 [live] checks). The
protocol tallies below are the instrument for the docs' [live] claims:
every count is a plain grep over the tape, so a reader can re-run it.
"""

from __future__ import annotations

import gzip
import json
import logging


class TapeWriter:
    """List-shaped sink that streams each batch to disk as it arrives.

    The recorders used to accumulate every batch in a Python list and write
    once at the end — a 300-battle tape is ~60 MB of JSON held live, and a
    death at 90 % lost the whole arm (CLAUDE.md rule 4(ii): a death costs one
    unit of work). `append` writes one line and flushes; `len()` still works.
    """

    def __init__(self, path):
        from pathlib import Path
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("w")
        self._n = 0

    def append(self, ev) -> None:
        self._fh.write(json.dumps(ev) + "\n")
        self._fh.flush()
        self._n += 1

    def __len__(self) -> int:
        return self._n

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterator

# poke-env's own ignore list (Player._handle_battle_message) — a replay
# must skip what the live handler skips.
MESSAGES_TO_IGNORE = {"t:", "expire", "uhtmlchange"}

_LOGGER = logging.getLogger("gen4_tape_replay")
_LOGGER.addHandler(logging.NullHandler())


def iter_tape(path: Path | str) -> Iterator[dict]:
    """One event per line; `.gz` tapes (the committed test fixture) open
    transparently."""
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def apply_batch(battle, batch: list[list[str]], strict: bool = False) -> dict | None:
    """Feed one batch through poke-env's parser exactly as Player does.
    Returns the request dict if the batch carried one (a decision point),
    else None. Mirrors poke_env/player/player.py::_handle_battle_message
    minus the network side (no orders are sent)."""
    request = None
    for sm in batch[1:]:
        if not sm:
            continue
        if len(sm) == 1:
            continue
        tag = sm[1]
        if tag == "":
            battle.parse_message(sm)
        elif tag in MESSAGES_TO_IGNORE:
            continue
        elif tag == "request":
            if len(sm) > 2 and sm[2]:
                request = json.loads(sm[2])
                battle.parse_request(request, strict)
        elif tag == "win":
            battle.won_by(sm[2])
        elif tag == "tie":
            battle.tied()
        elif tag in ("error", "bigerror"):
            continue
        else:
            battle.parse_message(sm)
    return request


def replay_tape(
    path: Path | str,
    on_decision: Callable[[object, dict, str], None] | None = None,
    gen: int = 4,
    seats: set[str] | None = None,
    strict: bool = False,
) -> dict:
    """Rebuild every (seat, room) battle on the tape and replay it.

    `on_decision(battle, request, seat)` fires after each batch that carried
    a request — the state a live player would encode and act on. A batch
    that raises inside poke-env poisons that battle's later decisions (they
    are skipped, and counted), never the replay.

    Returns {"decisions": n, "battles": n, "poisoned": n, "errors": Counter}.
    """
    from poke_env.battle import Battle

    battles: dict[tuple[str, str], object] = {}
    poisoned: set[tuple[str, str]] = set()
    errors: Counter = Counter()
    decisions = 0
    for ev in iter_tape(path):
        seat, room, batch = ev["seat"], ev["room"], ev["batch"]
        if seats is not None and seat not in seats:
            continue
        key = (seat, room)
        if key in poisoned:
            continue
        battle = battles.get(key)
        if battle is None:
            battle = Battle(room, seat, _LOGGER, gen=gen)
            battles[key] = battle
        try:
            request = apply_batch(battle, batch, strict=strict)
        except Exception as exc:  # noqa: BLE001 — the replay must survive a parse bug
            poisoned.add(key)
            errors[f"{type(exc).__name__}: {str(exc)[:100]}"] += 1
            continue
        if request is not None and not request.get("wait"):
            decisions += 1
            if on_decision is not None:
                on_decision(battle, request, seat)
    return {
        "decisions": decisions,
        "battles": len(battles),
        "poisoned": len(poisoned),
        "errors": errors,
    }


# --- protocol tallies (the [live] instrument) ------------------------------


def _from_cause(sm: list[str]) -> str | None:
    """The `[from] xxx` annotation of a message, if any."""
    for field in sm[2:]:
        if field.startswith("[from]"):
            return field[6:].strip()
    return None


def protocol_stats(path: Path | str) -> dict:
    """Greppable counts over ONE seat's view per room (the first seat seen
    for a room), plus per-seat request/error counts. Everything here is a
    literal count of protocol lines — the check behind a docs [live] tag."""
    first_seat: dict[str, str] = {}
    tags: Counter = Counter()
    from_causes: Counter = Counter()      # (tag, [from] cause)
    effects: Counter = Counter()          # -start / -end / -singleturn / -activate names
    side_conds: Counter = Counter()       # -sidestart names
    weather: Counter = Counter()          # (weather, cause/upkeep)
    cant: Counter = Counter()             # cant reasons
    status: Counter = Counter()
    field_counts: Counter = Counter()     # (tag, len(sm)) — the -item 6-field check
    errors: Counter = Counter()           # per-seat |error| kinds
    requests: Counter = Counter()         # request shape keys
    request_move_ids: Counter = Counter()
    request_move_names: Counter = Counter()
    active_keys: Counter = Counter()
    pokemon_keys: Counter = Counter()
    turns: dict[str, int] = defaultdict(int)
    outcomes: Counter = Counter()
    per_battle_max_turn: dict[str, int] = {}
    for ev in iter_tape(path):
        seat, room, batch = ev["seat"], ev["room"], ev["batch"]
        owner = first_seat.setdefault(room, seat)
        for sm in batch[1:]:
            if len(sm) < 2:
                continue
            tag = sm[1]
            if tag == "request":
                if len(sm) > 2 and sm[2]:
                    req = json.loads(sm[2])
                    shape = tuple(sorted(k for k in req if k not in ("rqid", "side")))
                    requests[str(shape)] += 1
                    if "active" in req:
                        for act in req["active"]:
                            for k in act:
                                active_keys[k] += 1
                            for mv in act.get("moves", []):
                                request_move_ids[mv.get("id", "?")] += 1
                                request_move_names[mv.get("move", "?")] += 1
                    for mon in req.get("side", {}).get("pokemon", []):
                        for k in mon:
                            pokemon_keys[k] += 1
                continue
            if tag == "error":
                kind = sm[2].split("]")[0] + "]" if len(sm) > 2 and sm[2].startswith("[") else sm[2][:40] if len(sm) > 2 else "?"
                errors[f"{seat}|{kind}"] += 1
                continue
            if seat != owner:
                continue  # count game events once per room
            tags[tag] += 1
            field_counts[f"{tag}|{len(sm)}"] += 1
            cause = _from_cause(sm)
            if cause is not None:
                from_causes[f"{tag}|{cause}"] += 1
            if tag in ("-start", "-end", "-singleturn", "-singlemove", "-activate", "-block", "-fieldstart", "-fieldend", "-fieldactivate"):
                effects[f"{tag}|{sm[3] if len(sm) > 3 else '?'}"] += 1
            elif tag in ("-sidestart", "-sideend"):
                side_conds[f"{tag}|{sm[3] if len(sm) > 3 else '?'}"] += 1
            elif tag == "-weather":
                w = sm[2] if len(sm) > 2 else "?"
                extra = "upkeep" if any(f == "[upkeep]" for f in sm[3:]) else (cause or "set")
                weather[f"{w}|{extra}"] += 1
            elif tag == "cant":
                cant[sm[3] if len(sm) > 3 else "?"] += 1
            elif tag == "-status":
                status[sm[3] if len(sm) > 3 else "?"] += 1
            elif tag == "turn":
                t = int(sm[2])
                per_battle_max_turn[room] = max(per_battle_max_turn.get(room, 0), t)
            elif tag == "win":
                outcomes["win"] += 1
            elif tag == "tie":
                outcomes["tie"] += 1
    max_turns = sorted(per_battle_max_turn.values())
    return {
        "rooms": len(first_seat),
        "outcomes": dict(outcomes),
        "turns": {
            "n": len(max_turns),
            "mean": (sum(max_turns) / len(max_turns)) if max_turns else None,
            "median": (max_turns[len(max_turns) // 2]) if max_turns else None,
            "max": max_turns[-1] if max_turns else None,
            "min": max_turns[0] if max_turns else None,
        },
        "tags": dict(tags.most_common()),
        "from_causes": dict(from_causes.most_common()),
        "effects": dict(effects.most_common()),
        "side_conditions": dict(side_conds.most_common()),
        "weather": dict(weather.most_common()),
        "cant": dict(cant.most_common()),
        "status": dict(status.most_common()),
        "field_counts": dict(sorted(field_counts.items())),
        "errors": dict(errors.most_common()),
        "request_shapes": dict(requests.most_common()),
        "request_active_keys": dict(active_keys.most_common()),
        "request_pokemon_keys": dict(pokemon_keys.most_common()),
        "request_move_ids": dict(request_move_ids.most_common()),
        "request_move_names_nonplain": {
            k: v for k, v in request_move_names.most_common()
            if any(ch.isdigit() for ch in k)
        },
    }
