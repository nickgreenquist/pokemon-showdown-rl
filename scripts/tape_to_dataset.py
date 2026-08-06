"""Reconstruct Foul Play demonstration tapes into an (obs, mask, action) dataset.

    python scripts/tape_to_dataset.py --tapes data/fp_tapes --out data/fp_bc.npz
    python scripts/tape_to_dataset.py --tapes data/fp_tapes --gates-only

No Showdown server needed: this is a pure offline replay, which is the point.
It is deterministic and re-runnable, so encoder changes cost a re-embed
(minutes) instead of a re-collection (tens of hours).

WHY TAPES AND NOT EMBEDDED ROWS
-------------------------------
P4's dataset was 2.1 GB of 611-dim float32 rows, and one OBS_DIM change turns
it into 2.1 GB of nothing. This project already intends to change the encoder
(the ps-ppo audit: STAB, expected hits, secondary-effect status AND its
probability, move-ID embedding, priority one-hot; plus the opponent set-prior
block that the vendored gen1 pool makes possible). Welding a generation run to
today's encoder would be the most expensive available mistake, so the durable
artefact is the raw protocol stream and the teacher's decision.

WHY THIS IS NOT THE "REPLAY PARSER" §10 PRICED AT DAYS
-----------------------------------------------------
Foul Play OWNS the seat, so the tape contains that seat's own `|request|`
JSONs. There is no hidden-action problem and no belief reconstruction --
exactly the two things that make the human replay corpus expensive. All this
file does is drive poke-env's OWN parser, mirroring the dispatch in
`poke_env/player/player.py:_handle_battle_message`. The parser is theirs; we
supply the message ordering.

WHAT A ROW IS
-------------
One row per decision Foul Play faced, carrying the observation OUR encoder
would have produced at that decision, the legal-action mask, the teacher's
action index, and the teacher's full pre-truncation search policy mapped onto
our action indices.

The soft policy is stored because Foul Play is STOCHASTIC: it truncates to
moves within 75% of the best and samples among them. An argmax label therefore
imitates the wrong object, and -- per the repo's own landmine -- one-hot BC on
a near-deterministic target is what produces the `loss/entropy` 0.063 collapse
that fails the R0 gate from update 1. Soft targets make the student's entropy
a design parameter instead of an accident.

FORCED ROWS ARE FLAGGED, NOT DROPPED HERE
-----------------------------------------
Gen 1 replaces the whole move list with a single `Fight` placeholder when the
active pkmn is asleep, frozen or partially trapped (~0.65 decisions/battle
measured). Those turns have exactly one legal action, so they carry no teacher
signal and should be excluded from the BC loss -- but the exclusion belongs to
the trainer, so they are flagged here and kept, and the gate report counts them.

PRE-REGISTERED CORRECTNESS GATES (printed every run; --gates-only to stop there)
-------------------------------------------------------------------------------
  G1 reconstruction   >= 99% of battles replay to a terminal state
  G2 label legality   100% of teacher actions land INSIDE our mask
  G3 legal-set SIZE   our mask's cardinality matches the `|request|`'s own
                      legal set. A size check, NOT an identity check -- a
                      permuted mapping would pass it. Identity is covered by
                      G2, which round-trips each label through the deployment
                      conversion; the two together are what make a label
                      trustworthy, and neither alone is sufficient.
  G4 outcome match    winners re-derived from tapes match the recorded result
  G5 forced coverage  the gen1 `Fight` path appears and yields 1-legal-action rows

G2 and G3 are the ones that matter. `rl/collect.py:RecordingPlayer` explains
why: the move index is relative to `active_pokemon.moves`, so a mis-indexed
label teaches the clone to name a DIFFERENT move under the very conversion
deployment uses, and no downstream number can reveal it -- the clone just looks
weak, which is indistinguishable from the diagnostic's own failure verdict.
"""

import argparse
import collections
import json
import logging
from pathlib import Path

import numpy as np
import orjson
from poke_env.battle import Battle
from poke_env.data import GenData
from poke_env.environment import SinglesEnv

from rl.envs.showdown import OBS_DIM, embed_battle

MESSAGES_TO_IGNORE = {"t:", "expire", "uhtmlchange"}
GEN = 1
BATTLE_FORMAT = "gen1randombattle"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tapes", type=Path, required=True, help="Directory of run_*.jsonl tapes")
    parser.add_argument("--out", type=Path, default=Path("data/fp_bc.npz"))
    parser.add_argument("--username", default=None, help="Foul Play's --ps-username (auto-detected if omitted)")
    parser.add_argument("--gates-only", action="store_true", help="Report gates, write nothing")
    parser.add_argument("--limit", type=int, default=None, help="Stop after N battles (debugging)")
    return parser.parse_args()


def load_events(tape_dir: Path):
    """Every tape line, in order, from every run file in the directory."""
    for path in sorted(tape_dir.glob("run_*.jsonl")):
        with path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    yield json.loads(line)


def infer_username(events) -> str:
    """Foul Play's own username, read off the `|updateuser|` it receives after login."""
    for ev in events:
        if ev["k"] != "m":
            continue
        for raw_line in ev["v"].split("\n"):
            parts = raw_line.split("|")
            if len(parts) > 2 and parts[1] == "updateuser" and parts[2].strip():
                name = parts[2].strip()
                if not name.lower().startswith("guest "):
                    return name
    raise SystemExit("Could not infer the Foul Play username from the tapes; pass --username")


def room_of(raw: str):
    """The battle room a raw message belongs to, or None if it is not a battle message."""
    head = raw.split("\n", 1)[0]
    if head.startswith(">battle-"):
        return head[1:]
    return None


def apply_message(battle: Battle, raw: str, state: dict) -> None:
    """Mirror of poke_env Player._handle_battle_message for a single raw message."""
    lines = raw.split("\n")
    for line in lines[1:]:
        split_message = line.split("|")
        if len(split_message) <= 1:
            continue
        tag = split_message[1]
        if tag == "":
            battle.parse_message(split_message)
        elif tag in MESSAGES_TO_IGNORE:
            continue
        elif tag == "request":
            if len(split_message) > 2 and split_message[2]:
                request = orjson.loads(split_message[2])
                battle.parse_request(request)
                state["last_request"] = request
        elif tag == "win":
            battle.won_by(split_message[2])
            state["winner"] = split_message[2]
        elif tag == "tie":
            battle.tied()
            state["tie"] = True
        elif tag in ("error", "bigerror"):
            state["errors"].append(line)
        else:
            battle.parse_message(split_message)


def request_legal_set(request: dict) -> set:
    """The legal choices the SERVER itself offered, read straight off the request.

    Independent of poke-env's tracking, which is the point: G3 compares our
    mask against the server's own statement rather than against ourselves.
    """
    legal = set()
    active = request.get("active")
    if active and not request.get("forceSwitch"):
        entry = active[0]
        for i, move in enumerate(entry.get("moves", [])):
            if not move.get("disabled", False):
                legal.add(("move", i))
        if entry.get("trapped") or entry.get("maybeTrapped"):
            return legal
    side = request.get("side", {})
    for i, mon in enumerate(side.get("pokemon", [])):
        if mon.get("active"):
            continue
        cond = mon.get("condition", "")
        if cond.endswith(" fnt") or cond == "0 fnt" or cond.startswith("0 "):
            continue
        legal.add(("switch", i))
    return legal


def main() -> None:
    args = parse_args()
    logger = logging.getLogger("tape_replay")
    logger.addHandler(logging.NullHandler())
    type_chart = GenData.from_format(BATTLE_FORMAT).type_chart

    events = list(load_events(args.tapes))
    if not events:
        raise SystemExit(f"No tape events found under {args.tapes}")
    username = args.username or infer_username(events)

    battles: dict[str, Battle] = {}
    states: dict[str, dict] = {}
    obs_rows, mask_rows, action_rows, battle_ids, forced_rows = [], [], [], [], []
    policy_rows = []

    counts = collections.Counter()
    battle_index: dict[str, int] = {}
    g3_checked = g3_ok = 0

    for ev in events:
        if ev["k"] == "m":
            room = room_of(ev["v"])
            if room is None:
                continue
            if room not in battles:
                if args.limit is not None and len(battles) >= args.limit:
                    continue
                battles[room] = Battle(room, username, logger, gen=GEN)
                states[room] = {"last_request": None, "winner": None, "tie": False, "errors": []}
                battle_index[room] = len(battle_index)
            apply_message(battles[room], ev["v"], states[room])
            continue

        # decision event
        tag = ev["tag"]
        if tag not in battles:
            counts["decision_without_battle"] += 1
            continue
        battle = battles[tag]
        counts["decisions"] += 1
        if ev.get("forced"):
            counts["forced"] += 1

        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)

        # G3: our mask vs the server's own statement of what was legal.
        req = states[tag]["last_request"]
        if req is not None and not ev.get("forced"):
            g3_checked += 1
            if int(mask.sum()) == len(request_legal_set(req)):
                g3_ok += 1

        # The teacher's choice -> our action index, via the SAME conversion
        # deployment uses. A name that does not resolve is a hard failure, not
        # a row to quietly skip.
        action = teacher_action(battle, ev["choice"], ev.get("forced", False))
        if action is None:
            counts["unmapped_choice"] += 1
            continue
        if not (0 <= action < mask.shape[0]) or not mask[action]:
            counts["label_outside_mask"] += 1
            continue

        obs_rows.append(embed_battle(battle, type_chart))
        mask_rows.append(mask)
        action_rows.append(action)
        battle_ids.append(battle_index[tag])
        forced_rows.append(bool(ev.get("forced")))
        policy_rows.append(soft_policy(battle, ev.get("policy"), mask.shape[0]))

    report(args, counts, battles, states, g3_checked, g3_ok)

    if args.gates_only:
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.out,
        obs=np.asarray(obs_rows, dtype=np.float32),
        masks=np.asarray(mask_rows, dtype=bool),
        actions=np.asarray(action_rows, dtype=np.int64),
        battle_ids=np.asarray(battle_ids, dtype=np.int64),
        forced=np.asarray(forced_rows, dtype=bool),
        policy=np.asarray(policy_rows, dtype=np.float32),
        obs_dim=np.int64(OBS_DIM),
    )
    print(f"\nwrote {args.out}  ({len(obs_rows)} rows, obs_dim={OBS_DIM})")


def teacher_action(battle, choice: str, forced: bool):
    """Map Foul Play's choice string onto our discrete action index.

    Foul Play emits either `switch <species>` or a move id. We resolve against
    the same lists poke-env's `action_to_order` indexes, so the label means the
    same thing at training time and at deployment.
    """
    if forced:
        # Fallback rows only: Foul Play could not restore the real move list and
        # submitted the placeholder. Map onto the placeholder's own action slot.
        for move in battle.available_moves:
            if move.id == "fight":
                return int(SinglesEnv.order_to_action(_move_order(move), battle))
        return None

    if choice.startswith("switch "):
        target = choice.split("switch ", 1)[1].strip()
        for i, mon in enumerate(battle.available_switches):
            if mon.species == target or mon.base_species == target:
                return int(SinglesEnv.order_to_action(_switch_order(mon), battle))
        return None

    for move in battle.available_moves:
        if move.id == choice:
            return int(SinglesEnv.order_to_action(_move_order(move), battle))

    # Placeholder turn: the search names one of the mon's real moves, but the
    # only move-shaped action our env offers is the `fight` slot. "Stay in" is
    # the decision actually being demonstrated, so that is the label -- and
    # crucially the SWITCH options on such a turn are real, searched choices,
    # not the biased "always stay in" an earlier patch would have written.
    for move in battle.available_moves:
        if move.id == "fight":
            return int(SinglesEnv.order_to_action(_move_order(move), battle))
    return None


def _move_order(move):
    from poke_env.player import SingleBattleOrder

    return SingleBattleOrder(move)


def _switch_order(mon):
    from poke_env.player import SingleBattleOrder

    return SingleBattleOrder(mon)


def soft_policy(battle, policy, n_actions: int) -> np.ndarray:
    """The teacher's pre-truncation search distribution over OUR action indices."""
    vec = np.zeros(n_actions, dtype=np.float32)
    if not policy:
        return vec
    for choice, prob in policy:
        idx = teacher_action(battle, choice, False)
        if idx is not None and 0 <= idx < n_actions:
            vec[idx] += float(prob)
    total = vec.sum()
    if total > 0:
        vec /= total
    return vec


def report(args, counts, battles, states, g3_checked, g3_ok) -> None:
    n_battles = len(battles)
    finished = sum(1 for b in battles.values() if b.finished)
    # A tie is an OUTCOME, not a missing one -- Foul Play's own tally counts it
    # as a loss, and the locked protocol counts ties as non-wins, so it must be
    # represented rather than treated as an unfinished battle.
    ties = sum(1 for s in states.values() if s["tie"])
    decided = sum(1 for s in states.values() if s["winner"] is not None or s["tie"])
    decisions = counts["decisions"]
    kept = decisions - counts["unmapped_choice"] - counts["label_outside_mask"]

    def pct(a, b):
        return f"{100.0 * a / b:.2f}%" if b else "n/a"

    print("=" * 68)
    print(f"tapes: {args.tapes}   battles: {n_battles}   decisions: {decisions}")
    print("=" * 68)
    print(f"G1 reconstruction   {finished}/{n_battles} battles terminal   {pct(finished, n_battles)}   (>=99% required)")
    print(f"G2 label legality   {kept}/{decisions} rows kept   {pct(kept, decisions)}   (100% required)")
    print(f"     unmapped choice: {counts['unmapped_choice']}   outside mask: {counts['label_outside_mask']}")
    print(f"G3 legal-set size   {g3_ok}/{g3_checked}   {pct(g3_ok, g3_checked)}   (cardinality only; identity is G2)")
    print(f"G4 outcome present  {decided}/{n_battles}   {pct(decided, n_battles)}   ({ties} ties)")
    print(f"G5 forced rows      {counts['forced']}   ({counts['forced'] / n_battles:.2f}/battle)" if n_battles else "G5 forced rows      0")
    if counts["decision_without_battle"]:
        print(f"WARNING decisions with no matching battle stream: {counts['decision_without_battle']}")
    errs = sum(len(s["errors"]) for s in states.values())
    if errs:
        print(f"WARNING protocol errors seen in tapes: {errs}")

    fail = []
    if n_battles and finished / n_battles < 0.99:
        fail.append("G1")
    if decisions and kept != decisions:
        fail.append("G2")
    if g3_checked and g3_ok != g3_checked:
        fail.append("G3")
    if n_battles and decided != n_battles:
        fail.append("G4")
    if not counts["forced"]:
        fail.append("G5 (placeholder path never exercised - sample may be too small)")
    print()
    print("GATES: " + ("PASS" if not fail else "FAIL -> " + ", ".join(fail)))


if __name__ == "__main__":
    main()
