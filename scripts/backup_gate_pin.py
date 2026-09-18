#!/usr/bin/env python
"""Write B2R's margin_delta and DRV's random threshold from phase S.

    python scripts/backup_gate_pin.py [--commit]

TWO PINS, BOTH MECHANICAL, NEITHER ALLOWED TO SEE A WIN RATE. Letting a pin
read an outcome turns a stated criterion into a choice, and at n=60 a win rate
carries se 0.065 -- larger than every effect this block is looking for.

PIN B (B2R's delta). The min-over-the-opponent backup LOWERS leaf values, so
the SAME delta lets a different number of overrides through than depth-1's. An
unmatched comparison measures how often search is BELIEVED rather than what it
believes -- the 2026-09-17 artifact that read -0.0007 as -0.053. Target is
D1O's banked realized rate (§24's CN1 at n=1500), and the realized rates of
D1O, B2O and B2R are all reported beside the delta in the readout.

PIN D (DRV's threshold). A uniform coin searches (1 - t) of decisions by
construction, so the control is matched ARITHMETICALLY from DGV's realized
search rate rather than screened for it: t = 1 - rate. Nothing is chosen.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREREG = REPO / "configs/eval/backup_gate_r5.yaml"
RES = REPO / "results/backup_gate_r5"
TARGET_OVERRIDE = 0.193          # D1O's banked rate, §24's CN1, n=1500
GRID = {"B2A": 0.03, "B2B": 0.05, "B2C": 0.08}


def _load(tag: str) -> dict:
    p = RES / f"{tag.lower()}.json"
    if not p.exists():
        sys.exit(f"REFUSE: {p} missing -- phase S incomplete")
    return json.loads(p.read_text())


def pin_b() -> tuple[float, str]:
    rows = []
    for tag, delta in sorted(GRID.items(), key=lambda kv: kv[1]):
        d = _load(tag)
        rate = d.get("search/override_rate")
        if rate is None:
            sys.exit(f"REFUSE: {tag} has no override rate")
        # THE VEHICLE MUST HAVE RUN. `opp_replies_mean` at 1.0 means the
        # minimax backup never fired whatever opp_k the config asked for, and
        # the cell says nothing about a matched delta for a vehicle that was
        # never in the arm. Same rule as the 2026-09-11 VOID probe.
        opp = d.get("depth2/opp_replies_mean")
        fired = d.get("depth2/fired_rate")
        if not opp or opp <= 1.05:
            sys.exit(f"REFUSE: {tag} depth2/opp_replies_mean={opp!r} -- the "
                     "minimax backup did not fire; the cell is VOID")
        if not fired or fired < 0.90:
            sys.exit(f"REFUSE: {tag} depth2/fired_rate={fired!r} -- no extra ply")
        rows.append((delta, tag, float(rate), abs(float(rate) - TARGET_OVERRIDE),
                     d.get("depth2/minimax_drop"), d.get("search/ms_mean")))
    for delta, tag, rate, err, drop, ms in rows:
        print(f"  B2 delta {delta:<5} {tag}: override {rate:.4f} "
              f"(|d| {err:.4f}), drop {drop}, {ms} ms")
    best = min(rows, key=lambda r: (r[3], r[0]))
    return best[0], (f"-> B2R delta {best[0]} from {best[1]} "
                     f"(override {best[2]:.4f} vs target {TARGET_OVERRIDE})")


def pin_d() -> tuple[float, str]:
    d = _load("GV")
    rate = d.get("disagree/search_rate")
    if rate is None:
        sys.exit("REFUSE: GV has no disagree/search_rate -- the gate did not "
                 "report, so it cannot be matched")
    rate = float(rate)
    if not 0.02 < rate < 0.98:
        sys.exit(f"REFUSE: GV search_rate {rate:.4f} is degenerate -- at that "
                 "rate the gated arm is greedy or ungated, not gated")
    t = round(1.0 - rate, 4)
    print(f"  GV realized search_rate {rate:.4f} -> DRV threshold {t}")
    return t, f"-> DRV threshold {t} matched to GV's search_rate {rate:.4f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    text = PREREG.read_text()
    if "PINB" not in text and "PIND" not in text:
        print("PIN already applied (no PINB/PIND left in the config)")
        return
    delta, msg_b = pin_b()
    thresh, msg_d = pin_d()
    print(msg_b)
    print(msg_d)
    out = text.replace("margin_delta: PINB", f"margin_delta: {delta}")
    out = out.replace("threshold: PIND", f"threshold: {thresh}")
    assert "PINB" not in out and "PIND" not in out, "a placeholder survived"
    PREREG.write_text(out)
    print(f"wrote {PREREG}")
    if args.commit:
        subprocess.run(["git", "add", str(PREREG)], cwd=REPO, check=True)
        subprocess.run(
            ["git", "commit", "-m",
             f"backup_gate_r5: pin B2R delta {delta} and DRV threshold {thresh} "
             f"from phase S\n\n{msg_b}\n{msg_d}\n\n"
             "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"],
            cwd=REPO, check=True)


if __name__ == "__main__":
    main()
