#!/usr/bin/env python
"""WHAT is the agent doing in a battle that runs to the 1000-turn cap?

    python scripts/stall_forensics.py --block gate_r5 --arm cn1
    python scripts/stall_forensics.py --block tree_r5            # every arm

The tie audit (`scripts/tie_and_stall_audit.py`) established that ~51% of ties
are turn-cap stalls and that the tie rate is a symptom of weakness. It could not
say what a stall IS. This reads the Showdown protocol out of the arm's Foul Play
log and classifies it.

WHAT IT FOUND ON THE FIRST BATTLE IT WAS POINTED AT (gate_r5/cn1, 2026-09-18):

    Foul Play was down to ONE Pokemon, Tauros, FROZEN SOLID -- `|cant|p1a:
    Tauros|frz` on 997 of 1000 turns. Gen-1 freeze is permanent without a fire
    move, so the opponent literally could not act. Our seat had a free win.

    Instead it switched 949 times, 948 of them STRICTLY ALTERNATING between
    Magneton and Abra, and played 55 moves. Turn cap -> TIE -> a NON-WIN under
    the locked protocol.

THE MECHANISM IS THE PROTOCOL'S OWN DETERMINISM. The locked eval protocol plays
argmax. The opponent is frozen, so the state stops changing; a deterministic
policy in a repeating state repeats its action, and the cycle runs until the cap.
Training SAMPLES, so this never happens there -- it is created by evaluating
deterministically, and it is invisible in any statistic that does not look at
turn counts.

NOTE the logs this reads are gitignored (results/ holds no tracked data), so this
script is the committed provenance and the finding above is its output.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MARK = "Received message from websocket: >"
CAP = 1000


def room_lines(path: Path, tag: str) -> str:
    """The protocol lines belonging to ONE battle room.

    The log interleaves rooms, and every room block starts with a `>battle-...`
    marker; any other logger line ends the block. Getting this wrong returns a
    handful of lines and a confident empty answer, which is what the first
    attempt did.
    """
    out, cur = [], False
    with path.open(errors="replace") as f:
        for line in f:
            if MARK in line:
                cur = tag in line
                continue
            if line.startswith(("DEBUG", "INFO ", "WARNING", "ERROR")):
                cur = False
                continue
            if cur:
                out.append(line)
    return "".join(out)


def classify(txt: str, seat: str) -> dict:
    """seat is 'p1' or 'p2' -- OUR side in this log."""
    foe = "p2" if seat == "p1" else "p1"
    sw = re.findall(rf"\|switch\|{seat}a: ([A-Za-z0-9'.:-]+)\|", txt)
    mv = re.findall(rf"\|move\|{seat}a: [^|]+\|([^|]+)", txt)
    foe_cant = len(re.findall(rf"\|cant\|{foe}a: [^|]+\|([a-z]+)", txt))
    foe_status = Counter(re.findall(rf"\|cant\|{foe}a: [^|]+\|([a-z]+)", txt))
    alt = sum(1 for a, b in zip(sw, sw[1:]) if a != b)
    return {
        "turns": txt.count("|turn|"),
        "our_switches": len(sw), "our_moves": len(mv),
        "alternating": alt, "alternating_frac": alt / max(len(sw) - 1, 1),
        "switch_targets": Counter(sw).most_common(4),
        "our_top_moves": Counter(mv).most_common(4),
        "foe_immobilised_turns": foe_cant,
        "foe_immobilised_by": dict(foe_status),
        "struggle": txt.lower().count("struggle"),
        "verdict": (
            "SWITCH LOOP vs an IMMOBILISED opponent -- a thrown-away win"
            if alt / max(len(sw) - 1, 1) > 0.9 and foe_cant > 0.5 * txt.count("|turn|")
            else "SWITCH LOOP" if alt / max(len(sw) - 1, 1) > 0.9
            else "long game, no simple cycle"),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", required=True, help="a directory under results/")
    ap.add_argument("--arm", help="one arm tag; default every arm in the block")
    ap.add_argument("--min-turns", type=int, default=CAP)
    ap.add_argument("--seat", default="p2", choices=("p1", "p2"),
                    help="our side in the Foul Play log (the seat ACCEPTS, so p2)")
    args = ap.parse_args()

    d = REPO / "results" / args.block
    arms = [args.arm] if args.arm else sorted(
        p.stem for p in d.glob("*.json")
        if not p.name.endswith("runner.json") and not p.name.startswith("smoke"))
    for arm in arms:
        jf = d / f"{arm}.json"
        lf = d / f"{arm}.fp.stdout"
        if not jf.exists():
            continue
        rec = json.loads(jf.read_text())
        pb = rec.get("per_battle") or []
        stalls = [b for b in pb if b.get("turns", 0) >= args.min_turns]
        if not stalls:
            continue
        print(f"\n### {args.block}/{arm}: {len(stalls)} battle(s) at >= "
              f"{args.min_turns} turns, out of {len(pb)}")
        if not lf.exists():
            print(f"  (no {lf.name} -- the log is gitignored; rerun the arm to "
                  "inspect, or point --block at a block whose log survives)")
            continue
        for b in stalls:
            txt = room_lines(lf, b["tag"])
            if not txt:
                print(f"  {b['tag']}: no protocol lines found in the log")
                continue
            c = classify(txt, args.seat)
            print(f"  {b['tag']}  outcome={b['outcome']}  turns={c['turns']}")
            print(f"    VERDICT: {c['verdict']}")
            print(f"    our switches {c['our_switches']} "
                  f"({c['alternating_frac']:.0%} strictly alternating), "
                  f"our moves {c['our_moves']}, struggle {c['struggle']}")
            print(f"    switch targets {c['switch_targets']}")
            print(f"    our top moves  {c['our_top_moves']}")
            print(f"    opponent could not act on {c['foe_immobilised_turns']} "
                  f"turns {c['foe_immobilised_by']}")


if __name__ == "__main__":
    main()
