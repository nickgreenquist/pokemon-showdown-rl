#!/usr/bin/env python
"""LADDER R1 readout obligation (iii): separate played games from non-games.

WHY THIS IS A SCRIPT AND NOT A GREP
-----------------------------------
The pre-reg told us to classify from replay TEXT rather than turn count, and
that instruction was right about turn counts and WRONG about text. Measured at
n=26 on real data:

  * SEVEN of our wins are `|-message|<them> forfeited.` at 19-33 turns. A
    concession from a losing position is the normal way a Pokemon game ends.
    Stripping them as "non-games" cost 18 points of descriptive win rate.
  * `lost due to inactivity` is the SAME STRING for a turn-1 no-show (battle
    16, opponent made 0 moves) and for a turn-32 abandonment (battle 25,
    `cogslife`, 21 moves and 9 switches before timing out). So the marker
    text cannot separate a rage-quit from someone who never arrived.

MAINTAINER RULING, 2026-08-25 at n=26: a mid-game timeout or disconnect IS a
win, and `played only` should not be strict — the official Elo/GXE is the real
number regardless, so the descriptive cut has no reason to be conservative.

THE INSTRUMENT: did the opponent ever submit a MOVE. Zero moves = they never
played = not a game. Everything else is a game, however it ended. This is
behavioural, reads straight out of the replay, and honours the pre-reg's own
"not a turn-count threshold" constraint better than its own grep did.

  Count MOVES, not switches. The lead send-out is a server-generated
  `|switch|` present on BOTH sides of every battle, so a switch count of 1
  means nothing happened. Battle 16 shows 1 switch / 0 moves for each player.
"""
import argparse
import json
import pathlib
import re
import sys

# Real ladder ids are 10-digit; local-smoke ids are 8-digit (408873xx). The
# filename prefix does NOT separate them any more — two smokes were saved
# after the display name was changed to the registered one.
REAL_ID = re.compile(r"gen1randombattle-(\d{9,})")
ANY_ID = re.compile(r"gen1randombattle-(\d+)")


def load_replays(replay_dir: pathlib.Path) -> dict[str, str]:
    out = {}
    for p in replay_dir.glob("*.html"):
        m = REAL_ID.search(p.name)
        if m:
            out[m.group(1)] = p.read_text(errors="ignore")
    return out


def opponent_moved(text: str, our_name: str) -> bool | None:
    """True/False, or None when the seat cannot be determined.

    WE MUST BE IN THE BATTLE. Taking "the slot that is not us" without first
    confirming one slot IS us would, on a battle we never played (a renamed
    account, a PS_USERNAME override, a stray replay in the directory), pick
    some arbitrary player as "the opponent" and return a confident, wrong
    answer. That is this repo's standing failure mode — a well-formed answer
    is worse than a crash — and the 403 bug of the same day was exactly it.
    """
    slots = dict(re.findall(r"\|player\|(p[12])\|([^|]*)\|", text))
    if our_name not in slots.values():
        return None
    theirs = next((s for s, n in slots.items() if n != our_name), None)
    if theirs is None:
        return None
    return bool(re.search(rf"\|move\|{theirs}a", text))


def classify(text: str, our_name: str) -> str:
    moved = opponent_moved(text, our_name)
    if moved is False:
        return "no_show"
    if "lost due to inactivity" in text:
        return "timeout_midgame"
    if "forfeited" in text:
        return "forfeit"
    return "played_out"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", default="results/ladder/L2.battles.jsonl")
    ap.add_argument("--replays", default="results/ladder/replays")
    ap.add_argument("--name", default="nickgen1rbrlbot")
    ap.add_argument("--json", action="store_true", help="machine-readable only")
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.jsonl) if l.strip()]
    reps = load_replays(pathlib.Path(args.replays))

    missing, cats = [], {}
    for r in rows:
        bid = ANY_ID.search(r["tag"]).group(1)
        text = reps.get(bid)
        if text is None:
            missing.append(bid)
            r["_cat"] = "NO_REPLAY"
        else:
            r["_cat"] = classify(text, args.name)
        cats[r["_cat"]] = cats.get(r["_cat"], 0) + 1

    def rate(sel):
        s = [r for r in rows if sel(r)]
        w = sum(1 for r in s if r["outcome"] == "win")
        return w, len(s), (w / len(s) if s else float("nan"))

    all_r = rate(lambda r: True)
    # RATIFIED cut: only a no-show is not a game.
    rat = rate(lambda r: r["_cat"] != "no_show")
    # The PRE-REGISTERED cut, still reported because it was written
    # result-blind. Superseded on 2026-08-25, never deleted.
    prereg = rate(lambda r: r["_cat"] == "played_out")

    report = {
        "n": len(rows),
        "categories": cats,
        "missing_replays": missing,
        "all_rated": {"w": all_r[0], "n": all_r[1], "rate": round(all_r[2], 4)},
        "ratified_played_only": {"w": rat[0], "n": rat[1],
                                 "rate": round(rat[2], 4)},
        "prereg_played_only_SUPERSEDED": {"w": prereg[0], "n": prereg[1],
                                          "rate": round(prereg[2], 4)},
    }
    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"n = {len(rows)}   categories: {cats}")
    if missing:
        print(f"  !! {len(missing)} battles have NO replay: {missing}")
    print(f"\n  all rated battles           {all_r[0]:>3}/{all_r[1]:<3} = "
          f"{all_r[2]:.3f}   (reconciles with the board)")
    print(f"  played-only  RATIFIED       {rat[0]:>3}/{rat[1]:<3} = "
          f"{rat[2]:.3f}   (excludes no-shows only)")
    print(f"  played-only  pre-reg        {prereg[0]:>3}/{prereg[1]:<3} = "
          f"{prereg[2]:.3f}   SUPERSEDED 2026-08-25, reported for the record")
    print("\nGXE/Glicko are server-computed over ALL rated battles and are "
          "untouched by this cut.")
    if missing:
        sys.exit(1)


if __name__ == "__main__":
    main()
