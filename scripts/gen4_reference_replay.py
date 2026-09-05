#!/usr/bin/env python
"""Replay every local gen-4 tape through `embed_battle_gen4` and record the
reference hash — the instrument behind encoder_requirements.md §13's
"Reference replay" paragraph, and the precursor of the pinned hash gate
(ruled build item 3: it lands the moment a pre-reg freezes the layout).

    python scripts/gen4_reference_replay.py [--tapes data/gen4_tapes] [--out FILE.json]

Rule (the gen-1 gate's, tests/test_encoder_spec.py): sha256 over
`vec.tobytes()` per decision, in tape order, one BattleTracker per
(seat, room). Tapes whose name ends `_gen1` are skipped (t7 is a gen-1
control). Prints decisions, NaN / out-of-Box / poisoned counts, µs/decision
and the sha; it never asserts — the gate does that once frozen.
"""
import argparse, hashlib, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from poke_env.data import GenData  # noqa: E402

from rl.envs.gen4.encoder import embed_battle_gen4  # noqa: E402
from rl.envs.gen4.spec import LAYOUT  # noqa: E402
from rl.envs.gen4.tape import replay_tape  # noqa: E402
from rl.envs.gen4.tracker import BattleTracker  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tapes", default="data/gen4_tapes")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    tapes = sorted(p for p in Path(args.tapes).glob("*.jsonl") if not p.stem.endswith("_gen1"))
    if not tapes:
        print(f"no tapes under {args.tapes}"); return 1
    tc = GenData.from_gen(4).type_chart
    h = hashlib.sha256()
    n = nan = oob = 0
    per_tape = {}
    t_enc = 0.0
    for tape in tapes:
        trackers = {}
        before = n

        def on_decision(battle, request, seat):
            nonlocal n, nan, oob, t_enc
            tr = trackers.setdefault((seat, battle.battle_tag), BattleTracker())
            t0 = time.perf_counter()
            vec = embed_battle_gen4(battle, tc, tr)
            t_enc += time.perf_counter() - t0
            assert vec.shape == (LAYOUT.obs_dim,) and vec.dtype == np.float32
            nan += int(np.isnan(vec).any())
            oob += int(vec.min() < -1.0 or vec.max() > 4.0)
            h.update(vec.tobytes())
            n += 1

        r = replay_tape(tape, on_decision)
        per_tape[tape.name] = {"decisions": n - before, "poisoned": r.get("poisoned"), "errors": r.get("errors")}
        print(f"{tape.name}: {n - before} decisions, poisoned={r.get('poisoned')}, errors={bool(r.get('errors'))}", flush=True)
    out = {
        "tapes": [t.name for t in tapes], "decisions": n, "nan": nan, "out_of_box": oob,
        "poisoned": sum(v["poisoned"] or 0 for v in per_tape.values()),
        "us_per_decision": round(1e6 * t_enc / max(n, 1), 1), "obs_dim": LAYOUT.obs_dim,
        "sha256": h.hexdigest(), "per_tape": per_tape,
    }
    print(json.dumps({k: v for k, v in out.items() if k != "per_tape"}, indent=1))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
