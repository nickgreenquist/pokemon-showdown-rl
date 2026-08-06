"""Reconstruct Foul Play demonstration tapes into an (obs, mask, action) dataset.

    python scripts/tape_to_dataset.py --tapes data/fp_tapes --out data/fp_bc
    python scripts/tape_to_dataset.py --tapes data/fp_tapes --gates-only

No Showdown server needed: a pure offline replay, deterministic and
re-runnable, so an encoder change costs a re-embed (minutes) rather than a
re-collection (tens of hours). That is the whole reason the durable artefact is
the raw protocol stream and not embedded rows: P4's dataset was 2.1 GB of
611-dim float32, and one OBS_DIM change turns it into 2.1 GB of nothing.

This is NOT §10's replay parser. Foul Play owns the seat, so the tape carries
that seat's own `|request|` JSONs: no hidden actions, no belief reconstruction.
This file only drives poke-env's OWN parser, mirroring player.py's dispatch.

WHAT A ROW IS
-------------
One row per decision: our encoder's observation at that decision, the legal
mask, the teacher's action index, its full pre-truncation search policy mapped
onto our action indices, and flags for the gen1 placeholder turns.

Soft targets are stored because Foul Play is STOCHASTIC (it truncates to moves
within 75% of the best, then samples). One-hot BC on a near-deterministic
target is exactly what produces the `loss/entropy` 0.063 collapse recorded as a
landmine, so soft targets make student entropy a design parameter.

THE GEN1 PLACEHOLDER, AND WHY THOSE ROWS ARE MARKED
---------------------------------------------------
In gen1 only, when the active pkmn is asleep, frozen or partially trapped,
Showdown replaces the move list with a single `Fight` placeholder. Such a turn
is NOT a forced choice: `trapped` is False and every legal switch remains
(measured). Two consequences:

  * Our action space cannot express WHICH move the teacher nominated, only
    "stay in" (poke-env maps a lone special move to slot 6). Every real-move
    entry in the teacher's policy is therefore summed onto that slot. That is
    correct -- it is P(stay in) -- but it must be understood, not discovered.
  * poke-engine's gen1 build honours sleep and freeze but models
    `partiallytrapped` with MODERN semantics: it deletes the switch options and
    lets the trapped mon attack at full power. Trap rows are searched in the
    wrong game, so `trap_kind` is carried and `--drop-trap` excludes them.

GATES -- a FAIL exits non-zero and the corpus is not treated as usable
----------------------------------------------------------------------
  G1 reconstruction  every battle replays to a terminal state
  G2 label identity  every label round-trips through the DEPLOYMENT conversion
                     (`action_to_order(action) == the teacher's order`) and
                     lands inside the mask. Legality alone is NOT enough: the
                     move index is relative to `active_pokemon.moves`, so a
                     mis-indexed label teaches the clone to name a DIFFERENT
                     move under the very conversion deployment uses, and no
                     downstream number could reveal it -- the clone would just
                     look weak. This mirrors rl/collect.py's assertion.
  G3 rqid alignment  the request the decision was taped against IS the request
                     the reconstruction stands on. Converts this file's central
                     premise -- that replaying in order reproduces the state the
                     teacher saw -- from an argument into a measurement.
  G4 outcome agrees  poke-env's `battle.won` matches the winner named in the
                     tape. Independent of G1, and it catches a username/role
                     mix-up, which is otherwise completely silent.
  G5 placeholder     placeholder turns are seen and accounted for.
  G6 clean protocol  no `|error|` frames and no replay exceptions. A rejected
                     choice would otherwise be taped and become a label.
"""

import argparse
import collections
import json
import logging
import sys
from pathlib import Path

import numpy as np
import orjson
from poke_env.battle import Battle
from poke_env.data import GenData
from poke_env.environment import SinglesEnv
from poke_env.player import SingleBattleOrder

from rl.envs.showdown import OBS_DIM, embed_battle

MESSAGES_TO_IGNORE = {"t:", "expire", "uhtmlchange"}
GEN = 1
BATTLE_FORMAT = "gen1randombattle"
LOGGER = logging.getLogger("tape_replay")
LOGGER.addHandler(logging.NullHandler())


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--tapes", type=Path, required=True)
    p.add_argument("--out", type=Path, default=Path("data/fp_bc"),
                   help="Output prefix; one .npz shard per tape file.")
    p.add_argument("--gates-only", action="store_true")
    p.add_argument("--drop-trap", action="store_true",
                   help="Exclude partial-trap rows (poke-engine models them wrong).")
    return p.parse_args()


def iter_events(path):
    """Stream one tape file -- the corpus will not fit in RAM at target scale."""
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def room_of(raw):
    head = raw.split("\n", 1)[0]
    return head[1:] if head.startswith(">battle-") else None


def infer_username(path):
    """Per FILE, not per directory. One tape file is one Foul Play process, and
    collection is planned 8-way with distinct usernames (a standing landmine).
    A directory-wide guess would hand 7 of 8 lanes the wrong seat, silently
    inverting `battle.won`."""
    for ev in iter_events(path):
        if ev["k"] != "m":
            continue
        for line in ev["v"].split("\n"):
            parts = line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser" and parts[2].strip():
                name = parts[2].strip()
                if not name.lower().startswith("guest "):
                    return name
    return None


def apply_message(battle, raw, state):
    """Mirror of poke_env Player._handle_battle_message for one raw frame."""
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
                req = orjson.loads(sm[2])
                battle.parse_request(req)
                state["request"] = req
        elif tag == "win":
            battle.won_by(sm[2])
            state["winner"] = sm[2]
        elif tag == "tie":
            battle.tied()
            state["tie"] = True
        elif tag in ("error", "bigerror"):
            state["errors"].append(line)
        else:
            battle.parse_message(sm)


def request_legal_set(request):
    """The choices the SERVER offered, as an independent cardinality check."""
    legal = set()
    fs = request.get("forceSwitch", [False])
    # forceSwitch is a LIST; `[False]` is truthy, so it must be indexed.
    force_switch = bool(fs[0]) if isinstance(fs, list) and fs else bool(fs)
    active = request.get("active")
    trapped = False
    if active and not force_switch:
        entry = active[0]
        for i, mv in enumerate(entry.get("moves", [])):
            if not mv.get("disabled", False):
                legal.add(("move", i))
        # Only `trapped` blocks switching; `maybeTrapped` does NOT -- poke-env
        # sets _trapped from `trapped` alone and keeps switches available.
        trapped = bool(entry.get("trapped"))
    if not trapped:
        for i, mon in enumerate(request.get("side", {}).get("pokemon", [])):
            if mon.get("active") or mon.get("condition", "").endswith(" fnt"):
                continue
            legal.add(("switch", i))
    return legal


def teacher_order(battle, choice, placeholder):
    """Foul Play's choice as a poke-env order, plus which branch resolved it.

    The branch is returned so skips can be attributed: a systematic switch-only
    or move-only skip would bias the corpus in a specific direction.
    """
    if choice.startswith("switch "):
        target = choice.split("switch ", 1)[1].strip()
        for mon in battle.available_switches:
            if mon.species == target or mon.base_species == target:
                return SingleBattleOrder(mon), "switch"
        return None, "switch"

    for mv in battle.available_moves:
        if mv.id == choice:
            return SingleBattleOrder(mv), "move"

    if placeholder:
        # Our action space cannot express which move was nominated; the only
        # move-shaped action is the placeholder slot, meaning "stay in", which
        # is the decision actually being demonstrated.
        for mv in battle.available_moves:
            if mv.id == "fight":
                return SingleBattleOrder(mv), "placeholder"
    return None, "move"


def soft_policy(battle, policy, n_actions, placeholder, counts):
    vec = np.zeros(n_actions, dtype=np.float32)
    if not policy:
        counts["policy_missing"] += 1
        return vec
    dropped = 0.0
    for choice, prob in policy:
        order, _ = teacher_order(battle, choice, placeholder)
        if order is None:
            dropped += float(prob)
            continue
        idx = int(SinglesEnv.order_to_action(order, battle))
        if 0 <= idx < n_actions:
            vec[idx] += float(prob)  # placeholder turns SUM onto the stay-in slot
        else:
            dropped += float(prob)
    if dropped > 0.01:
        counts["policy_mass_dropped"] += 1
    total = vec.sum()
    if total > 0:
        vec /= total
    else:
        counts["policy_empty"] += 1
    return vec


def process_file(path, type_chart, counts, drop_trap):
    username = infer_username(path)
    if username is None:
        counts["no_username"] += 1
        return None

    battles, states, index_of = {}, {}, {}
    rows = collections.defaultdict(list)

    for ev in iter_events(path):
        if ev["k"] == "m":
            room = room_of(ev["v"])
            if room is None:
                continue
            if room not in battles:
                battles[room] = Battle(room, username, LOGGER, gen=GEN)
                states[room] = {"request": None, "winner": None, "tie": False, "errors": []}
                index_of[room] = len(index_of)
            try:
                apply_message(battles[room], ev["v"], states[room])
            except Exception as exc:  # one bad tag must not abort the corpus
                counts["battle_exceptions"] += 1
                states[room]["errors"].append(f"replay exception: {exc!r}")
            continue

        tag = ev["tag"]
        if tag not in battles:
            counts["decision_without_battle"] += 1
            continue
        battle, state = battles[tag], states[tag]
        counts["decisions"] += 1

        placeholder = bool(ev.get("placeholder"))
        trap = ev.get("trap_kind")
        if placeholder:
            counts["placeholder"] += 1

        req = state["request"]
        if req is None or req.get("rqid") != ev.get("rqid"):
            counts["rqid_mismatch"] += 1
            continue
        counts["rqid_ok"] += 1

        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        if len(request_legal_set(req)) == int(mask.sum()):
            counts["legal_size_ok"] += 1
        else:
            counts["legal_size_mismatch"] += 1

        order, kind = teacher_order(battle, ev["choice"], placeholder)
        if order is None:
            counts["unresolved_" + kind] += 1
            continue
        action = int(SinglesEnv.order_to_action(order, battle))
        if not (0 <= action < mask.shape[0]) or not mask[action]:
            counts["outside_mask"] += 1
            continue
        if str(SinglesEnv.action_to_order(np.int64(action), battle)) != str(order):
            counts["roundtrip_mismatch"] += 1
            continue
        counts["kept"] += 1

        if drop_trap and trap == "trap":
            counts["dropped_trap"] += 1
            continue

        rows["obs"].append(embed_battle(battle, type_chart))
        rows["masks"].append(mask)
        rows["actions"].append(action)
        rows["battle_ids"].append(index_of[tag])
        rows["policy"].append(soft_policy(battle, ev.get("policy"), mask.shape[0], placeholder, counts))
        rows["placeholder"].append(placeholder)
        rows["trap_kind"].append(trap or "")

    for room, b in battles.items():
        st = states[room]
        counts["battles"] += 1
        if b.finished:
            counts["terminal"] += 1
        if st["tie"]:
            counts["outcome_ok"] += 1
        elif st["winner"] is not None and b.won == (st["winner"] == username):
            counts["outcome_ok"] += 1
        else:
            counts["outcome_mismatch"] += 1
        counts["protocol_errors"] += len(st["errors"])
    return rows


def main():
    args = parse_args()
    type_chart = GenData.from_format(BATTLE_FORMAT).type_chart
    counts = collections.Counter()
    tapes = sorted(args.tapes.glob("run_*.jsonl"))
    if not tapes:
        raise SystemExit("No run_*.jsonl under " + str(args.tapes))

    shards = []
    for path in tapes:
        rows = process_file(path, type_chart, counts, args.drop_trap)
        if rows and rows["obs"] and not args.gates_only:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            shard = args.out.parent / (args.out.name + "_" + path.stem + ".npz")
            np.savez_compressed(
                shard,
                obs=np.asarray(rows["obs"], dtype=np.float32),
                masks=np.asarray(rows["masks"], dtype=bool),
                actions=np.asarray(rows["actions"], dtype=np.int64),
                battle_ids=np.asarray(rows["battle_ids"], dtype=np.int64),
                policy=np.asarray(rows["policy"], dtype=np.float32),
                placeholder=np.asarray(rows["placeholder"], dtype=bool),
                trap_kind=np.asarray(rows["trap_kind"]),
                obs_dim=np.int64(OBS_DIM),
            )
            shards.append((shard, len(rows["obs"])))

    ok = report(counts, args)
    if not ok:
        print("\nGates FAILED -- this corpus is not usable as-is.")
        for shard, _ in shards:
            print("  (shard written for inspection: " + str(shard) + ")")
        sys.exit(1)
    for shard, n in shards:
        print("wrote " + str(shard) + "  (" + str(n) + " rows)")


def report(counts, args):
    d, b = counts["decisions"], counts["battles"]

    def pct(a, n):
        return "%.2f%%" % (100.0 * a / n) if n else "n/a"

    print("=" * 70)
    print("battles: %d   decisions: %d   rows kept: %d" % (b, d, counts["kept"]))
    print("=" * 70)
    print("G1 reconstruction  %d/%d terminal        %s" % (counts["terminal"], b, pct(counts["terminal"], b)))
    print("G2 label identity  %d/%d round-tripped   %s" % (counts["kept"], d, pct(counts["kept"], d)))
    print("     unresolved move %d  unresolved switch %d  outside mask %d  roundtrip mismatch %d"
          % (counts["unresolved_move"], counts["unresolved_switch"],
             counts["outside_mask"], counts["roundtrip_mismatch"]))
    print("G3 rqid alignment  %d/%d                %s" % (counts["rqid_ok"], d, pct(counts["rqid_ok"], d)))
    print("G4 outcome agrees  %d/%d                %s" % (counts["outcome_ok"], b, pct(counts["outcome_ok"], b)))
    print("G5 placeholder     %d turns (%.2f/battle)" % (counts["placeholder"], counts["placeholder"] / b if b else 0))
    print("G6 clean protocol  errors %d   replay exceptions %d" % (counts["protocol_errors"], counts["battle_exceptions"]))
    print("   legal-set size  %d ok / %d mismatch (cardinality cross-check)"
          % (counts["legal_size_ok"], counts["legal_size_mismatch"]))
    print("   soft policy     missing %d  mass-dropped %d  empty %d"
          % (counts["policy_missing"], counts["policy_mass_dropped"], counts["policy_empty"]))
    if args.drop_trap:
        print("   dropped trap rows %d" % counts["dropped_trap"])

    fail = []
    if b and counts["terminal"] != b:
        fail.append("G1")
    if d and counts["kept"] != d:
        fail.append("G2")
    if d and counts["rqid_ok"] != d:
        fail.append("G3")
    if b and counts["outcome_ok"] != b:
        fail.append("G4")
    if b and counts["placeholder"] == 0:
        fail.append("G5(no placeholder turns seen; sample may be small)")
    if counts["protocol_errors"] or counts["battle_exceptions"]:
        fail.append("G6")
    if counts["no_username"]:
        fail.append("username-inference")
    print()
    print("GATES: " + ("PASS" if not fail else "FAIL -> " + ", ".join(fail)))
    return not fail


if __name__ == "__main__":
    main()
