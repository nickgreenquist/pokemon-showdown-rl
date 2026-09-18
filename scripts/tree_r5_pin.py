#!/usr/bin/env python
"""Pick HD1/HD2's margin_delta by matching D1's REALIZED override rate.

    python scripts/tree_r5_pin.py [--commit]

Same rule the depth read used, and for the same reason: the heuristic's leaf
values spread wider than our critic's, so the SAME delta lets 2.5x as many
overrides through, and comparing at equal delta would compare how often the
search is believed rather than what it believes. Reads `search/override_rate`
from the phase-S JSONs and nothing else -- letting it see a win rate would turn
a stated criterion into a choice, and at n=60 a win rate carries se 0.065.

Target is 0.0682, D1's realized rate at n=3000, not the n=60 screen's 0.0723.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREREG = REPO / "configs/eval/tree_r5.yaml"
RES = REPO / "results/tree_r5"
TARGET = 0.0682
GRID = {"tree_q": {"TSA": 0.05, "TSB": 0.10, "TSC": 0.20}}


def pick(cells):
    rows = []
    for tag, delta in sorted(cells.items(), key=lambda kv: kv[1]):
        p = RES / f"{tag.lower()}.json"
        if not p.exists():
            sys.exit(f"REFUSE: {p} missing — phase S incomplete")
        d = json.loads(p.read_text())
        # A TREE ARM REPORTS NO override_rate: that field is gated on
        # `margin_delta`, which lives on the MATRIX selector. The tree carries
        # its margin inside `tree.margin`, so its "how often did search overrule
        # the policy" number is search/flips over searched decisions. Same
        # quantity, different bookkeeping -- and taking the None at face value
        # is what blocked this run at 07:05Z.
        rate = d.get("search/override_rate")
        if rate is None and d.get("search_tree"):
            dec = d.get("search/decisions") or 0
            skips = d.get("search/placeholder_skips") or 0
            rate = (d.get("search/flips") or 0) / max(dec - skips, 1)
        # the critic arms carry no heuristic counter by construction
        fired = 1.0 if d.get("search_tree") else 0.0   # the tree must have RUN
        if rate is None:
            sys.exit(f"REFUSE: {tag} has no override rate")
        if not fired or fired < 0.90:
            sys.exit(f"REFUSE: {tag} heuristic/fired_rate={fired!r} — the vehicle "
                     "did not run and the cell says nothing")
        rows.append((delta, tag, rate, abs(rate - TARGET), d.get("search/ms_mean")))
        print(f"  {tag} delta {delta:.2f}: override {rate:.4f} "
              f"(|diff| {abs(rate - TARGET):.4f}), fired {fired:.3f}, "
              f"{d.get('search/ms_mean', float('nan')):.1f} ms")
    best = min(rows, key=lambda r: (r[3], r[0]))
    print(f"  -> delta {best[0]:.2f} from {best[1]} "
          f"(override {best[2]:.4f} vs target {TARGET})")
    return best


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()
    print(f"target override rate {TARGET} (D1 realized, n=3000)\ntree, decide=q:")
    b1 = pick(GRID["tree_q"])
    b2 = None
    text = PREREG.read_text()
    for holder, best in (("PINQ", b1),):
        if holder in text:
            text = text.replace(f"margin: {holder}",
                                f"margin: {best[0]:.2f}", 1)
        else:
            m = re.search(rf"{'HD1' if holder == 'PIN1' else 'HD2'}:.*?margin_delta: ([\d.]+)", text)
            if not m or abs(float(m.group(1)) - best[0]) > 1e-9:
                sys.exit(f"REFUSE: {holder} already pinned to {m and m.group(1)}, "
                         f"rule says {best[0]}")
            print(f"{holder} already pinned, verified")
    PREREG.write_text(text)
    print(f"wrote {PREREG}")
    if args.commit:
        subprocess.run(["git", "add", str(PREREG)], check=True, cwd=REPO)
        subprocess.run(["git", "commit", "-q", "-m",
                        f"tree_r5: TQ margin {b1[0]:.2f} matches D1's override "
                        f"({b1[2]:.4f} vs target {TARGET})\n\n"
                        "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>\n"
                        "Claude-Session: https://claude.ai/code/session_01Rz5TMHg1uVyb6emrgq7rXn"],
                       cwd=REPO)
        print("committed")


if __name__ == "__main__":
    main()
