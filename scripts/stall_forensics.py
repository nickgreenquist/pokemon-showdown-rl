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


def room_lines(path: Path, tags) -> dict[str, str]:
    """The protocol lines belonging to EACH of `tags`, in ONE pass.

    The log interleaves rooms, and every room block starts with a `>battle-...`
    marker; any other logger line ends the block. Getting this wrong returns a
    handful of lines and a confident empty answer, which is what the first
    attempt did.

    ONE PASS, not one per tag: these logs run 200-900 MB and an arm can hold
    fifteen stalls, so re-reading per battle turned a ten-minute sweep into an
    afternoon. That is why the first version only ever looked at one arm -- and
    a claim about "every stall" then rested on six of them.
    """
    want = set(tags)
    out: dict[str, list[str]] = {t: [] for t in want}
    cur = None
    with path.open(errors="replace") as f:
        for line in f:
            if MARK in line:
                cur = next((t for t in want if t in line), None)
                continue
            if line.startswith(("DEBUG", "INFO ", "WARNING", "ERROR")):
                cur = None
                continue
            if cur is not None:
                out[cur].append(line)
    return {t: "".join(v) for t, v in out.items()}


def classify(txt: str, seat: str) -> dict:
    """seat is 'p1' or 'p2' -- OUR side in this log."""
    foe = "p2" if seat == "p1" else "p1"
    sw = re.findall(rf"\|switch\|{seat}a: ([A-Za-z0-9'.:-]+)\|", txt)
    mv = re.findall(rf"\|move\|{seat}a: [^|]+\|([^|]+)", txt)
    foe_cant = len(re.findall(rf"\|cant\|{foe}a: [^|]+\|([a-z]+)", txt))
    foe_status = Counter(re.findall(rf"\|cant\|{foe}a: [^|]+\|([a-z]+)", txt))
    alt = sum(1 for a, b in zip(sw, sw[1:]) if a != b)
    turns = txt.count("|turn|")
    acts = len(sw) + len(mv)
    # THE CLASSIFIER IS DELIBERATELY CONSERVATIVE, because the claim it supports
    # is about EVERY stall and the first version's categories were too coarse to
    # carry one. Three things are separated that it used to conflate:
    #   * a room whose protocol we did not fully capture -- an arm that was
    #     relaunched mid-battle leaves a partial room, and a battle with 1000
    #     turns and 10 recorded actions is a LOG artifact, not a policy one;
    #   * a loop against an opponent that CAN act -- a real game, however ugly;
    #   * the bug: the opponent is immobilised for most of the battle and we
    #     still do not finish it. Whether our side alternates between two slots
    #     or hammers one is not the point; NOT WINNING against something that
    #     cannot act is.
    incomplete = acts < 0.25 * max(turns, 1)
    foe_frac = foe_cant / max(turns, 1)
    if incomplete:
        verdict = "INCOMPLETE LOG -- too few recorded actions to classify"
    elif foe_frac >= 0.80:
        verdict = "FOE IMMOBILISED AND WE DID NOT FINISH -- a thrown-away win"
    elif alt / max(len(sw) - 1, 1) > 0.9 and len(sw) > 100:
        verdict = "SWITCH LOOP against an opponent that COULD act"
    else:
        verdict = "long game, no simple cycle"
    return {
        "turns": turns,
        "our_switches": len(sw), "our_moves": len(mv),
        "alternating": alt, "alternating_frac": alt / max(len(sw) - 1, 1),
        "switch_frac": len(sw) / max(acts, 1),
        "foe_immobilised_frac": foe_frac,
        "switch_targets": Counter(sw).most_common(4),
        "our_top_moves": Counter(mv).most_common(4),
        "foe_immobilised_turns": foe_cant,
        "foe_immobilised_by": dict(foe_status),
        "struggle": txt.lower().count("struggle"),
        "verdict": verdict,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--block", required=True, help="a directory under results/")
    ap.add_argument("--arm", help="one arm tag; default every arm in the block")
    ap.add_argument("--min-turns", type=int, default=CAP)
    ap.add_argument("--seat", default="p2", choices=("p1", "p2"),
                    help="our side in the Foul Play log (the seat ACCEPTS, so p2)")
    ap.add_argument("--summary", action="store_true",
                    help="one line per arm plus a verdict tally -- the form that "
                         "supports (or refutes) a claim about EVERY stall")
    args = ap.parse_args()
    tally: Counter = Counter()

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
        rooms = room_lines(lf, [b["tag"] for b in stalls])
        for b in stalls:
            txt = rooms.get(b["tag"], "")
            if not txt:
                print(f"  {b['tag']}: no protocol lines found in the log")
                continue
            c = classify(txt, args.seat)
            tally[c["verdict"]] += 1
            if args.summary:
                print(f"  {b['tag'][-8:]}  {c['verdict']:<52} "
                      f"sw {c['our_switches']:>4} ({c['switch_frac']:>4.0%} of acts) "
                      f"alt {c['alternating_frac']:>5.0%} foe-stuck {c['foe_immobilised_frac']:>5.0%}")
                continue
            print(f"  {b['tag']}  outcome={b['outcome']}  turns={c['turns']}")
            print(f"    VERDICT: {c['verdict']}")
            print(f"    our switches {c['our_switches']} "
                  f"({c['alternating_frac']:.0%} strictly alternating), "
                  f"our moves {c['our_moves']}, struggle {c['struggle']}")
            print(f"    switch targets {c['switch_targets']}")
            print(f"    our top moves  {c['our_top_moves']}")
            print(f"    opponent could not act on {c['foe_immobilised_turns']} "
                  f"turns {c['foe_immobilised_by']}")

    if tally:
        total = sum(tally.values())
        print(f"\n{'=' * 78}\nVERDICT TALLY over {total} stalls examined\n{'=' * 78}")
        for v, n in tally.most_common():
            print(f"  {n:>4}  ({n / total:>5.1%})  {v}")
        print("\n  A claim about EVERY stall needs this denominator, not a sample.")


if __name__ == "__main__":
    main()
