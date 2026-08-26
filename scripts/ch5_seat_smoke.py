"""CH5 — does a `ch3_fp_h2h.py` SEAT actually complete battles? No FP needed.

`ch5_seat_equiv.py` proves a seat DECIDES like the path it is standing in
for. It cannot prove the seat can PLAY: `choose_move`, the mask/order
conversion, the desync-recovery branch and every report field are
untouched by an offline identity check.

This runs `ch3_fp_h2h.run()` VERBATIM with a local `SimpleHeuristicsPlayer`
standing in for Foul Play, so it needs only the local Showdown server and
the ONLY thing under test is our seat. Use it whenever a new arm kind is
registered, BEFORE spending a Foul Play arm on it.

    python scripts/ch5_seat_smoke.py --kind ensemble_seat --battles 6
    python scripts/ch5_seat_smoke.py --kind search_seat --seat s62 --dose M

WIN RATES FROM THIS SCRIPT ARE NOT RESULTS. n is a handful of battles and
the opponent is SH, not FP. It answers "does the seat work", nothing else.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import yaml  # noqa: E402
from poke_env.player import SimpleHeuristicsPlayer  # noqa: E402
from poke_env.ps_client.account_configuration import AccountConfiguration  # noqa: E402

import ch3_fp_h2h as fp  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--kind", default="ensemble_seat")
ap.add_argument("--battles", type=int, default=6)
ap.add_argument("--seat", help="lane, for single-seat kinds")
ap.add_argument("--dose", help="search dose, for search_seat")
ap.add_argument("--prereg", default="configs/eval/ladder_r1.yaml",
                help="source of the checkpoint pins and (for ensembles) the lanes")
ap.add_argument("--lanes-from-arm", default="L2")
# Distinct usernames per invocation: same-name lanes collide on the server
# and the loser dies with a misleading timeout (the repo's seeding landmine).
ap.add_argument("--suffix", default="a")
args = ap.parse_args()

N = args.battles
SEAT, CHAL = f"ch5smk{args.suffix}seat", f"ch5smk{args.suffix}sh"

ladder = yaml.safe_load(Path(args.prereg).read_text())
arm = {"kind": args.kind, "battles": N,
       "seat_username": SEAT, "fp_username": CHAL}
if args.kind == "ensemble_seat":
    arm["lanes"] = ladder["arms"][args.lanes_from_arm]["lanes"]
else:
    arm["seat"] = args.seat or "s62"
    if args.dose:
        arm["dose"] = args.dose
prereg = {
    "checkpoints": ladder["checkpoints"],
    "results_dir": str(ROOT / "results" / "ch5_seat_smoke"),
    "arms": {"SMOKE": arm},
}

async def challenger():
    sh = SimpleHeuristicsPlayer(
        battle_format="gen1randombattle",
        max_concurrent_battles=1,
        account_configuration=AccountConfiguration(CHAL, None),
    )
    await asyncio.sleep(6)          # let the seat register and start listening
    await sh.send_challenges(SEAT, n_challenges=N)

async def main():
    t0 = time.monotonic()
    seat_task = asyncio.create_task(fp.run(prereg, "SMOKE", N, f"smoke_{args.kind}"))
    chal_task = asyncio.create_task(challenger())
    report, _ = await asyncio.gather(seat_task, chal_task)
    keep = [k for k in (
        "battles_requested", "battles_finished", "our_wins", "foulplay_wins",
        "ties", "mean_turns", "sec_per_battle", "mask_desyncs",
        "gate_all_challenges_resolved", "seat_policy", "seat_lane",
        "seat_lanes", "seat_native_dim", "ensemble/decisions",
        "ensemble/flips", "ensemble/flip_rate", "search/ms_mean",
        "search/leaves_mean", "search/decisions", "search/flips",
    ) if k in report]
    print("\n=== SEAT SMOKE REPORT (win rate is NOT a result) ===")
    print(json.dumps({k: report.get(k) for k in keep}, indent=1))
    print(f"per_battle rows: {len(report['per_battle'])}  "
          f"first: {report['per_battle'][0] if report['per_battle'] else None}")
    print(f"wall {time.monotonic()-t0:.1f}s")
    ok = (report["battles_finished"] == N
          and report["gate_all_challenges_resolved"]
          and report["mask_desyncs"] == 0)
    if args.kind == "ensemble_seat":
        ok = ok and bool(report.get("seat_lanes")) and report.get("ensemble/decisions", 0) > 0
    print("\nSEAT SMOKE", "PASS" if ok else "FAIL")
    if not ok:
        sys.exit(1)

asyncio.run(main())
