#!/usr/bin/env python
"""Apply RULE R1 of configs/eval/depth2_r5.yaml — mechanically, from disk.

    python scripts/depth2_r5_pin.py [--commit]

The rule, restated from the pre-reg so this file can be audited alone:

    the depth-1 arm is FIXED at margin_delta 0.10; the depth-2 PRIMARY arm's
    delta is the grid point whose PHASE-S OVERRIDE RATE is closest in absolute
    value to S1A's; ties break toward the SMALLER delta; and if two depth-2
    cells are within 0.005 of each other AND both within 0.01 of S1A, the
    smaller delta wins.

IT READS `search/override_rate` AND NOTHING ELSE. The phase-S win rates are on
disk in the same JSONs and are not opened here — at n=60 a win rate carries
se 0.065, and letting the rule see one would turn a pre-stated criterion into
a choice. This is the same construction rule R1 of monster_reads_offfp.yaml
used to pick the ladder object, for the same reason.

REFUSES to pin unless every phase-S cell is on disk and every one of them
passes the pre-reg's R0 gates that apply to a screen cell (the extra ply must
have FIRED on the depth-2 cells — 2026-09-11's VOID probe is why). Writes the
chosen delta over the `FILL_FROM_RULE_R1` placeholder as a TEXT substitution,
leaving every other byte of the pre-reg untouched (a YAML round-trip would
destroy its comments, which are the pre-registration).
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREREG = REPO / "configs/eval/depth2_r5.yaml"
RES = REPO / "results/depth2_r5"
PLACEHOLDER = "FILL_FROM_RULE_R1"
D1_CELL = "S1A"
D2_CELLS = {"S2A": 0.10, "S2B": 0.20, "S2C": 0.35, "S2D": 0.50}
FIRED_MIN = 0.90


def cell(tag: str) -> dict:
    p = RES / f"{tag.lower()}.json"
    if not p.exists():
        sys.exit(f"REFUSE: {p} is missing — phase S is not complete")
    return json.loads(p.read_text())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    d1 = cell(D1_CELL)
    d1_rate = d1.get("search/override_rate")
    if d1_rate is None:
        sys.exit(f"REFUSE: {D1_CELL} has no search/override_rate (gate off?)")
    print(f"{D1_CELL} (depth 1, delta 0.10): override_rate {d1_rate:.4f}, "
          f"{d1.get('search/ms_mean', float('nan')):.1f} ms/decision")

    rows = []
    for tag, delta in sorted(D2_CELLS.items(), key=lambda kv: kv[1]):
        c = cell(tag)
        rate = c.get("search/override_rate")
        fired = c.get("depth2/fired_rate")
        if rate is None:
            sys.exit(f"REFUSE: {tag} has no search/override_rate")
        if fired is None or fired < FIRED_MIN:
            sys.exit(
                f"REFUSE: {tag} has depth2/fired_rate {fired!r} < {FIRED_MIN} — "
                "the extra ply did not fire and the cell is VOID (R0 gate "
                "G_FIRED; 2026-09-11's D2 probe printed a win rate having "
                "produced zero grandchildren)"
            )
        rows.append((delta, tag, rate, abs(rate - d1_rate), c))
        print(f"{tag} (depth 2, delta {delta:.2f}): override_rate {rate:.4f} "
              f"(|diff| {abs(rate - d1_rate):.4f}), fired {fired:.3f}, "
              f"{c.get('search/ms_mean', float('nan')):.1f} ms/decision")

    best = min(rows, key=lambda r: (r[3], r[0]))     # distance, then smaller delta
    near = [r for r in rows if abs(r[3] - best[3]) <= 0.005 and r[3] <= 0.01]
    if len(near) > 1:
        chosen = min(near, key=lambda r: r[0])
        print(f"\nTIE CLAUSE FIRES: {[r[1] for r in near]} are within 0.005 of "
              f"each other and 0.01 of {D1_CELL}; the SMALLER delta wins.")
    else:
        chosen = best
    delta, tag = chosen[0], chosen[1]
    print(f"\nRULE R1 -> D2M takes margin_delta {delta:.2f} (from {tag}, "
          f"override {chosen[2]:.4f} vs {D1_CELL}'s {d1_rate:.4f})")

    text = PREREG.read_text()
    if PLACEHOLDER not in text:
        m = re.search(r"^\s*margin_delta: ([\d.]+)\s+# pinned by rule R1", text, re.M)
        if not m:
            sys.exit("REFUSE: the pre-reg has neither the placeholder nor a pin")
        if abs(float(m.group(1)) - delta) > 1e-9:
            sys.exit(f"REFUSE: already pinned to {m.group(1)}, rule says {delta}")
        print("already pinned, verified")
        return
    text = text.replace(
        f"margin_delta: {PLACEHOLDER}      # written by scripts/depth2_r5_pin.py",
        f"margin_delta: {delta:.2f}   # pinned by rule R1 from {tag} "
        f"(override {chosen[2]:.4f} vs {D1_CELL} {d1_rate:.4f})", 1)
    assert PLACEHOLDER not in text, "substitution missed"
    PREREG.write_text(text)
    print(f"wrote {PREREG}")

    if args.commit:
        subprocess.run(["git", "add", str(PREREG)], check=True, cwd=REPO)
        msg = (f"depth2_r5: rule R1 pins D2M at margin_delta {delta:.2f} "
               f"(matched override rate)\n\n"
               f"Mechanical, by scripts/depth2_r5_pin.py, reading "
               f"search/override_rate and nothing else from the phase-S JSONs:\n"
               f"  {D1_CELL} depth 1 delta 0.10 -> {d1_rate:.4f}\n"
               + "".join(f"  {r[1]} depth 2 delta {r[0]:.2f} -> {r[2]:.4f} "
                         f"(|diff| {r[3]:.4f})\n" for r in rows)
               + f"\nChosen: {tag}. Every depth-2 cell passed G_FIRED.\n\n"
               "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n"
               "Claude-Session: https://claude.ai/code/session_01Rz5TMHg1uVyb6emrgq7rXn")
        r = subprocess.run(["git", "commit", "-q", "-m", msg],
                           capture_output=True, text=True, cwd=REPO)
        print(r.stdout.strip() or r.stderr.strip() or "committed")


if __name__ == "__main__":
    main()
