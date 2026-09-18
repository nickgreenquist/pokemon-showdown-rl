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
# REFUSE RATHER THAN PIN A DELTA THAT DOES NOT MATCH. The grid is a guess: the
# min-over-the-opponent backup lowers leaf values by an amount nobody has
# measured, and B2A came back at 0.3702 against a 0.193 target on 2026-09-18.
# If the best cell is still this far out, the read would be a comparison at
# UNMATCHED override rates -- which is the 2026-09-17 artifact and the single
# thing this block exists to avoid. Refusing stops the queue before phase R and
# costs a screen cell; pinning anyway costs eight hours and produces a number
# that cannot be used. The screen measures the rate over ~2,000 decisions, so
# it is well determined even at n=60 -- a miss here is the GRID, not noise.
MAX_OVERRIDE_ERR = 0.05


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
    if best[3] > MAX_OVERRIDE_ERR:
        lo = min(r[2] for r in rows)
        hi = max(r[2] for r in rows)
        sys.exit(
            f"REFUSE: the grid does not reach the target. Best is {best[1]} at "
            f"delta {best[0]} with override {best[2]:.4f} against a target of "
            f"{TARGET_OVERRIDE} (|d| {best[3]:.4f} > {MAX_OVERRIDE_ERR}). The "
            f"swept range spans {lo:.4f}..{hi:.4f}.\n"
            "Phase R would compare arms that differ in HOW OFTEN the search is "
            "BELIEVED as well as in the backup -- the 2026-09-17 artifact.\n"
            "FIX: add bracketing cells to configs/eval/backup_gate_r5.yaml and "
            "this GRID, run them, and re-run the pin. The selection rule reads "
            "override rate and never a win rate, so extending the grid mid-block "
            "is legitimate (it is what the 2026-09-17 fpeval sweep did).")
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
