"""Gate P-2: mask parity and the §7.2 mapping table (plan §9).

Three legs, because "engine-derived mask == get_action_mask" decomposes into
three separable claims and mixing them would hide which one broke:

  A. MASK PARITY, on tape decisions. The mask is derived from the RAW
     `|request|` JSON -- what Showdown itself sent, which is exactly what the
     engine's `-Dshowdown` mode is defined to reproduce -- through §7.2's table,
     and compared to poke-env's `get_action_mask` on the parsed Battle. This
     tests the load-bearing ordering claim (switch action i <-> party index i for
     the whole battle; move action 6+j <-> stored slot j) and the SPECIAL_MOVES
     alias rule, from two independent readings of the same protocol.

  B. THE §7.2 SPLIT, on tape decisions: how often each locked situation occurs
     and what `trapped` is in each. Plan §7.2 flags this as UNCONFIRMED -- "the
     encoder's own measurement that `battle.trapped` is False on 1,262 of 1,273
     recharge/partial-trap turns is consistent with this table if most of those
     turns were Wrap victims; P-2 must confirm the split before this table is
     trusted". This leg is that confirmation.

  C. THE ENGINE HALF of the table, measured in Rust on bank battles: a hard lock
     offers exactly `Move(1)` and no switches; a semi-lock offers switches plus
     exactly one move slot. (`pkmn_gen1.mask_table_split`.)
"""

from __future__ import annotations

import json
from collections import Counter

from poke_env.battle.effect import Effect
from poke_env.environment.singles_env import SinglesEnv

# poke-env's SPECIAL_MOVES: when one of these is the only legal move-action,
# poke-env re-bases the move index onto `available_moves`, so move slot i stops
# meaning "the mon's move i" and the single legal move action is 6.
SPECIAL_MOVES = {"fight", "struggle", "recharge"}
N_ACTIONS = 10

# rl/envs/encoder_spec.py::GEN1.volatiles, in its order.
ENCODER_VOLATILES = (
    "CONFUSION",
    "FOCUS_ENERGY",
    "LEECH_SEED",
    "MUST_RECHARGE",
    "PARTIALLY_TRAPPED",
    "REFLECT",
    "SUBSTITUTE",
)


def _fainted(condition: str) -> bool:
    return condition.split(" ")[0] == "0" or "fnt" in condition


def ident_key(ident: str) -> str:
    return ident.split(": ", 1)[1] if ": " in ident else ident


def mask_from_request(req: dict, first_order: dict[str, int]) -> list[int] | None:
    """The 10-way mask §7.2 says the engine path must produce, derived from the
    request alone. `None` for a request that carries no decision.

    ORDERING, the load-bearing part. Showdown's `side.pokemon` is the CURRENT
    order and puts the active mon first, so it is re-permuted on every switch.
    poke-env's `battle.team` is NOT: it is filled from the FIRST request and
    never reordered (`abstract_battle.py:1279-1320`), which is what makes
    "switch action i means party index i" hold for a whole battle. `first_order`
    is that first-request order, and indexing by it rather than by the live
    request is the difference between a correct mask and a mask that permutes
    itself every time the active changes. Plan §7.2 asserts exactly this; here
    it is measured.
    """
    if req.get("wait"):
        return None
    side = req.get("side") or {}
    party = side.get("pokemon") or []
    if not party:
        return None
    if not first_order:
        first_order.update({ident_key(m.get("ident", "")): i for i, m in enumerate(party[:6])})

    mask = [0] * N_ACTIONS
    force_switch = bool((req.get("forceSwitch") or [False])[0])
    active_block = (req.get("active") or [None])[0]
    trapped = bool(active_block.get("trapped")) if active_block else False

    # Switch actions: action i is the mon at index i of the FIRST request's
    # order. A hard lock (`trapped`) removes every switch; a forced switch
    # removes none.
    if not trapped:
        for mon in party[:6]:
            i = first_order.get(ident_key(mon.get("ident", "")))
            if i is None or mon.get("active") or _fainted(mon.get("condition", "")):
                continue
            mask[i] = 1

    if force_switch or active_block is None:
        return mask

    offered = [m for m in (active_block.get("moves") or [])]
    usable = [m for m in offered if not m.get("disabled") and m.get("pp", 1) > 0]
    # PS sends a locked mon a ONE-entry list whose pp/disabled fields are not
    # meaningful (`[Recharge]`, `[Struggle]`, the gen-1 `[Fight]` placeholder,
    # or the locked move itself), so a single-entry list is always usable.
    if len(offered) == 1:
        usable = offered

    # The mon's stored move list -- the order poke-env's move dict is filled in
    # and therefore the order move actions index.
    active_mon = next((m for m in party if m.get("active")), None)
    stored = [str(m) for m in (active_mon or {}).get("moves", [])]

    slots = []
    for m in usable:
        mid = m.get("id", "")
        if mid in stored:
            slots.append(6 + stored.index(mid))
    if not slots and len(usable) == 1:
        # ALIAS: the only legal move is not one of the mon's stored moves (the
        # `Fight` / `Recharge` placeholder or Struggle), so poke-env re-bases it
        # onto action 6.
        slots = [6]
    for s in slots:
        if 6 <= s < N_ACTIONS:
            mask[s] = 1
    return mask


def classify_request(req: dict) -> tuple[str, bool]:
    """The §7.2 row this decision sits in, read off the WIRE.

    Plan §7.2's table is a claim about what Showdown sends, so it is classified
    from the request rather than from poke-env's parsed state: PS's answer is the
    thing the engine's `-Dshowdown` mode is defined to reproduce. Returns
    `(row, trapped)`.
    """
    if (req.get("forceSwitch") or [False])[0]:
        return "force_switch", False
    block = (req.get("active") or [None])[0]
    if block is None:
        return "no_active", False
    trapped = bool(block.get("trapped"))
    offered = block.get("moves") or []
    if len(offered) != 1:
        return "normal", trapped
    only = offered[0].get("id", "")
    if only == "recharge":
        return "recharge", trapped
    if only == "struggle":
        return "struggle", trapped
    if only in SPECIAL_MOVES:  # the gen-1 `fight` placeholder
        return "placeholder", trapped
    # A single REAL move. With `trapped` it is a hard lock (Thrash / two-turn
    # charge / Rage). Without it, plan §7.2 expects a SEMI-lock (Bide or a
    # Wrap/Bind/Clamp/Fire Spin user) -- but a one-move SET (Ditto knows only
    # Transform) looks identical from the request, so the two are separated by
    # the size of the mon's stored move list.
    if trapped:
        return "hard_lock", True
    party = (req.get("side") or {}).get("pokemon") or []
    active_mon = next((m for m in party if m.get("active")), None)
    if active_mon is not None and len(active_mon.get("moves") or []) <= 1:
        return "one_move_set", False
    return "semi_lock", False


def classify_state(battle) -> str:
    """A secondary reading, from poke-env's parsed state, so the placeholder row
    can be split into its causes (asleep / frozen / Wrap victim)."""
    ours = battle.active_pokemon
    if ours is None:
        return "no_active"
    eff = {e.name for e in ours.effects}
    theirs = battle.opponent_active_pokemon
    foe_eff = {e.name for e in theirs.effects} if theirs is not None else set()
    tags = []
    if ours.must_recharge:
        tags.append("recharge")
    if "BIDE" in eff:
        tags.append("bide")
    # poke-env puts PARTIALLY_TRAPPED on the VICTIM, so the USER is identified by
    # the FOE carrying it.
    if "PARTIALLY_TRAPPED" in eff:
        tags.append("trapped_victim")
    if "PARTIALLY_TRAPPED" in foe_eff:
        tags.append("trapping_user")
    if ours.preparing:
        tags.append("charging")
    if "LOCKED_MOVE" in eff:
        tags.append("locked_move")
    if ours.status is not None:
        if ours.status.name == "SLP":
            tags.append("asleep")
        elif ours.status.name == "FRZ":
            tags.append("frozen")
    return "+".join(tags) if tags else "none"


def check_decision(
    battle, req: dict, report: Counter, failures: list, room: str, first_order: dict[str, int]
) -> None:
    want = mask_from_request(req, first_order)
    if want is None:
        report["skipped_wait"] += 1
        return
    got = SinglesEnv.get_action_mask(battle)
    if len(got) != N_ACTIONS:
        failures.append(f"{room}: poke-env mask is {len(got)} wide, expected {N_ACTIONS}")
        return

    kind, req_trapped = classify_request(req)
    report["decisions"] += 1
    report[f"kind:{kind}"] += 1
    # The table's `trapped` column, both readings: what PS sent and what
    # poke-env concluded. Plan §7.2 flags the second as unconfirmed.
    report[f"reqtrap:{kind}:{int(req_trapped)}"] += 1
    report[f"pokeenvtrap:{kind}:{int(bool(battle.trapped))}"] += 1
    if kind in ("placeholder", "hard_lock", "semi_lock", "recharge", "struggle"):
        report[f"cause:{kind}:{classify_state(battle)}"] += 1

    # Census of the SEVEN volatile slots the encoder actually has
    # (encoder_spec.GEN1.volatiles). A slot that never fires in 100k decisions is
    # a structurally dead feature, which is exactly what the D13a MUST_RECHARGE
    # fix was about -- so it is counted rather than assumed.
    for who, mon in (("own", battle.active_pokemon), ("opp", battle.opponent_active_pokemon)):
        if mon is None:
            continue
        names = {e.name for e in mon.effects}
        for eff in ENCODER_VOLATILES:
            live = bool(mon.must_recharge) if eff == "MUST_RECHARGE" else eff in names
            if live:
                report[f"vol:{who}:{eff}"] += 1
        report[f"vol:{who}:_decisions"] += 1

    if want != got:
        report["mismatched"] += 1
        report[f"mismatch:{kind}"] += 1
        transformed = (battle.active_pokemon is not None and battle.active_pokemon.transformed)
        if transformed:
            report["mismatch_family:transform"] += 1
        else:
            report["mismatch_family:undeclared"] += 1
        msg = json.dumps(
            {
                "room": room,
                "turn": int(battle.turn),
                "kind": kind,
                "transformed": bool(transformed),
                "engine_mask": want,
                "pokeenv_mask": got,
                "trapped": bool(battle.trapped),
                "available_moves": [m.id for m in battle.available_moves],
                "stored": [m.id for m in list(battle.active_pokemon.moves.values())[:4]]
                if battle.active_pokemon
                else [],
                "switches": [m.species for m in battle.available_switches],
            }
        )
        if len(failures) < 25:
            failures.append(msg)
