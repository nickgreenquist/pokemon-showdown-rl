"""CH3 R4 BI-5: the CLONE BLOCK of the anchor battery (arms CA / CE0 / CE3).

    python scripts/ch3_r4_anchors.py --prereg configs/eval/ch3_r4_ensemble_critic.yaml --arm CA
    python scripts/ch3_r4_anchors.py --prereg configs/eval/ch3_r4_ensemble_critic.yaml --arm CE0
    python scripts/ch3_r4_anchors.py --prereg configs/eval/ch3_r4_ensemble_critic.yaml --arm CE3
    python scripts/ch3_r4_anchors.py --prereg ... --arm CE3 --battles 4 --smoke

Arm-generic re-cut of scripts/ch3_r2_falsifier.py (which is a REGISTERED R2
instrument and is NOT modified): the falsifier hardcodes arms["SA"], the
literal output prefix "sa" and the R2 pre-reg path in its own sha stamp —
all three are parameters here, because pre-reg ANCHOR BATTERY / CLONE BLOCK
runs CE0 and CE3 from the SAME pre-reg and they would otherwise collide and
silently "resume" each other.

Arms are read from prereg["anchor_arms"] (pre-reg ANCHOR BATTERY):
  CA  greedy_h2h  s65 deterministic seat 1 vs the BC clone sampling seat 2,
      500 battles — the ERA TRIPWIRE against 0.894 +/- 0.04.
  CE0 search_h2h  s65 + depth-1 search@M, evaluator ABSENT (the R2-credited
      E0 path, bit-identical), 1000 battles in 10 chunks — THE FRESH
      COMPARATOR.
  CE3 search_h2h  same, plus the LOO 3-critic evaluator resolved
      pool-minus-self (pre-reg F5) — THE TREATMENT.

SEAT-1-ONLY DEVIATION, carried from the falsifier and re-disclosed by the
pre-reg: the search seat exists only as seat-1 machinery
(_SearchEvalAdapter), so every arm here is SAME-ORIENTATION and the ~0.20
measured seat asymmetry cancels by construction.

Chunked and resumable exactly like the falsifier / ch3_eval.py: one JSON per
chunk under results/ch3_r4_anchors/<arm lowercase>.chunkNN.json, a merged
<arm>.final.json when every chunk exists. RESOLVED AMBIGUITY: the pre-reg
gives CA no `chunks` key, so CA runs the same chunked path at the default
5 x 100 (resumable like everything else); CE0/CE3 take the pre-reg's 10.

Per-chunk evidence written for the grader (pre-reg F-GATES):
  F8/R2-5 twin  eval/win_rate == wins_from_returns EXACTLY — HARD assert
                here, as in the falsifier, not merely graded.
  F5            evaluator provenance (kind, members, member_sha256) in
                EVERY chunk JSON and in the final — mirrors
                ch3_eval._resolve_evaluator so the gate is gradeable from
                disk.
  F-C twin      leaves/ms/placeholder-skip summary per chunk; the grader
                reads |leaves_mean - 353|/353 <= 0.25 and timeouts == 0.
                NOTE, honest: rl/search has no timeout COUNTER — the
                node_cap watchdog RAISES (DO-NOT-BUILD #16), so a timeout
                manifests as a MISSING chunk file. `search/timeouts` is
                recorded 0 and the grader enforces chunk completeness.
  F11 twin      started_at / finished_at on every chunk.
Finals are stamped with the pre-reg sha256 (the ACTUAL --prereg path) and
the git sha.
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_eval import (  # noqa: E402
    _install_battle2_sentinel,
    _print_username,
    _SearchEvalAdapter,
    _sha256,
    _uninstall_battle2_sentinel,
)
from eval_checkpoint import (  # noqa: E402
    _load_showdown_agent,
    _opponent_from_checkpoint,
)

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.evaluation import _run_eval_episodes, eval_metrics  # noqa: E402
from rl.envs.make import make_env  # noqa: E402
from rl.envs.showdown import mask_desync_total  # noqa: E402

ANCHOR_DIR = "results/ch3_r4_anchors"
DEFAULT_GREEDY_CHUNKS = 5
LEAVES_EXPECTED = 353.0
LEAVES_BAND = 0.25


def _git(cmd: list[str]) -> str:
    return subprocess.run(["git", *cmd], capture_output=True, text=True).stdout.strip()


def _preflight(prereg: dict) -> None:
    """pre-reg R4-7, the anchor half: sha256 on ALL FIVE pins (the four D26
    lanes AND the clone, which lives in `checkpoints:` precisely so both
    drivers assert it), plus the encoder env vars and simulator: 4."""
    import os
    import re

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d id-suffix protocol)"
    pins = prereg["checkpoints"]
    # R5b BI-7(a): the pin count is the pre-reg's own `expected_pins`
    # (default 5 keeps R4's file exactly as it was). THE ONLY DRIVER CHANGE
    # either R5 file makes.
    expected = prereg.get("expected_pins", 5)
    assert len(pins) == expected, (
        f"preflight expects {expected} pins, got {sorted(pins)}"
    )
    for lane, spec in pins.items():
        got = _sha256(spec["path"])
        assert got == spec["sha256"], (
            f"R4-7 FAIL: {lane} checkpoint sha256 {got} != prereg {spec['sha256']}"
        )
    cfg_js = Path("showdown/config/config.js").read_text()
    m = re.search(r"^\s*simulator:\s*(\d+)", cfg_js, re.M)
    assert m and int(m.group(1)) >= 4, (
        "showdown/config/config.js: `simulator: 4` not set (see CLAUDE.md)"
    )
    print(f"preflight: R4-7 sha256 x{len(pins)} OK (clone included); simulator>=4 OK")


def _load_peer(prereg: dict, lane: str):
    """An evaluator member, built through eval_checkpoint's cross-encoder
    shim (the same seam the seat agent uses) with its pin re-asserted — F5
    requires every member file sha256 == pin."""
    spec = prereg["checkpoints"][lane]
    got = _sha256(spec["path"])
    assert got == spec["sha256"], f"F5 FAIL: member {lane} sha256 {got} != pin"
    ckpt = load_checkpoint(spec["path"])
    return _load_showdown_agent(ckpt, Config(**ckpt["config"]))


def _resolve_evaluator(prereg: dict, seat_lane: str, spec_eval, agent0):
    """pre-reg F5, mirroring ch3_eval._resolve_evaluator: `loo` resolves its
    pool HERE — the OTHER lanes' agents, this lane excluded — and the
    membership asserts fire at resolution (pool size == 3, own key absent,
    own agent excluded by IDENTITY). The returned provenance dict is written
    into every chunk JSON so the gate is gradeable from disk."""
    if not spec_eval:
        return None, None
    evaluator = dict(spec_eval)
    provenance = {"kind": evaluator["kind"]}
    if evaluator["kind"] == "loo":
        pool = [x for x in evaluator.pop("pool") if x != seat_lane]
        assert len(pool) == 3, f"F5: loo pool resolved to {pool}"
        assert seat_lane not in pool, f"F5: own lane {seat_lane} in pool"
        evaluator["agents"] = [_load_peer(prereg, x) for x in pool]
        assert all(a is not agent0 for a in evaluator["agents"]), (
            "F5: the lane's own agent object is in the ensemble"
        )
        provenance["members"] = pool
        provenance["member_sha256"] = [
            prereg["checkpoints"][x]["sha256"] for x in pool
        ]
    return evaluator, provenance


def _arm_spec(prereg: dict, arm_name: str) -> dict:
    arms = prereg["anchor_arms"]
    assert arm_name in arms, f"{arm_name} not in anchor_arms {sorted(arms)}"
    arm = arms[arm_name]
    assert arm["kind"] in ("greedy_h2h", "search_h2h"), (
        f"{arm_name}: kind {arm['kind']!r} is not a clone-block kind — FE3 "
        "(kind search_seat) runs through scripts/ch3_fp_h2h.py"
    )
    return arm


def run_arm(prereg: dict, prereg_path: str, arm_name: str,
            battles: int | None, smoke: bool, out_dir: Path) -> None:
    """One anchor arm, chunked and resumable. Same _run pattern as the R2
    falsifier's run_sa, with the arm, the output prefix and the sha-stamped
    pre-reg path all parameters."""
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES

    arm = _arm_spec(prereg, arm_name)
    is_search = arm["kind"] == "search_h2h"
    total = battles or arm["battles"]
    chunks = 1 if smoke else arm.get(
        "chunks", DEFAULT_GREEDY_CHUNKS if not is_search else 10
    )
    chunk_size = total // chunks
    assert chunk_size > 0, f"{arm_name}: {total} battles over {chunks} chunks"
    out_dir.mkdir(parents=True, exist_ok=True)

    seat_lane, opp_lane = arm["seat1"], arm["seat2"]
    seat_spec = prereg["checkpoints"][seat_lane]
    opp_spec = prereg["checkpoints"][opp_lane]
    ckpt = load_checkpoint(seat_spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)

    # seat 2 = the clone, PoolPlayer-style SAMPLING seat (the falsifier's
    # construction verbatim); seat 1 = our deterministic side.
    opponent = _opponent_from_checkpoint(opp_spec["path"], cfg.seed)
    env = make_env(cfg.env_id, cfg.seed, env_kwargs={"opponent": opponent})
    agent0 = _load_showdown_agent(ckpt, cfg)

    adapter = None
    eval_provenance = None
    agent = agent0
    if is_search:
        assert getattr(env.unwrapped, "_privileged", None) is False, (
            "SF-13: the eval env must not emit info['privileged']"
        )
        evaluator, eval_provenance = _resolve_evaluator(
            prereg, seat_lane, arm.get("evaluator"), agent0
        )
        sa = SearchAgent(
            agent0,
            DOSES[arm["dose"]],
            checkpoint_seed=int(seat_lane.lstrip("s")),
            evaluator=evaluator,
        )
        adapter = agent = _SearchEvalAdapter(sa, env)
    _print_username(env)  # R4-12 twin: realized usernames on the record

    prefix = f"{arm_name.lower()}_smoke" if smoke else arm_name.lower()
    base = cfg.eval_episodes
    desync_before = mask_desync_total()
    for k in range(chunks):
        chunk_path = out_dir / f"{prefix}.chunk{k:02d}.json"
        if chunk_path.exists():
            print(f"{chunk_path.name}: exists, skipping")
            continue
        seed_start = base + k * chunk_size
        if adapter is not None:
            adapter.begin_chunk(seed_start)
        sentinel_handle = None
        if is_search and k == 0:
            sentinel_handle = _install_battle2_sentinel(env.unwrapped._env.env)
        started_at = time.time()
        try:
            returns, outcomes, faints = _run_eval_episodes(
                agent, env, chunk_size, seed_start=seed_start
            )
        finally:
            if sentinel_handle is not None:
                _uninstall_battle2_sentinel(env.unwrapped._env.env, sentinel_handle)
                print(f"chunk {k}: battle2 sentinel armed for the whole chunk, "
                      "0 rl/search accesses (SF-13)")
        metrics = eval_metrics(returns, outcomes, faints, win_rate=True)
        desync_now = mask_desync_total()
        wins_from_returns = sum(1 for r in returns if r > 0) / len(returns)
        assert metrics["eval/win_rate"] == wins_from_returns, (
            f"F8 FAIL on {arm_name} chunk {k}: win_rate {metrics['eval/win_rate']} "
            f"!= wins_from_returns {wins_from_returns}"
        )
        report = {
            "arm": arm_name,
            "kind": arm["kind"],
            "seat1": seat_lane,
            "seat2": opp_lane,
            "chunk": k,
            "episodes": chunk_size,
            "seed_start": seed_start,
            **metrics,
            "return_mean": float(np.mean(returns)),
            "wins_from_returns": wins_from_returns,
            "ties_from_returns": sum(1 for r in returns if r == 0) / len(returns),
            "mask_desyncs_delta": desync_now - desync_before,
            "started_at": started_at,
            "finished_at": time.time(),
            "returns": returns,
        }
        if adapter is not None:
            report.update(adapter.chunk_summary())
            report["search_dose"] = arm["dose"]
            # F-C twin: no timeout counter exists (the node_cap watchdog
            # RAISES and leaves a missing chunk); recorded 0, completeness
            # graded downstream.
            report["search/timeouts"] = 0
            report["f_c_leaves_ok"] = bool(
                abs(report["search/leaves_mean"] - LEAVES_EXPECTED)
                / LEAVES_EXPECTED <= LEAVES_BAND
            )
            if eval_provenance is not None:
                report["evaluator"] = eval_provenance
        desync_before = desync_now
        chunk_path.write_text(json.dumps(report, indent=2) + "\n")
        extra = ""
        if adapter is not None:
            extra = (f" | leaves {report['search/leaves_mean']:.1f} "
                     f"({'F-C ok' if report['f_c_leaves_ok'] else 'F-C FIRES'}), "
                     f"ms {report['search/ms_mean']:.1f}, "
                     f"skips {report['search/placeholder_skips']}")
        print(f"{chunk_path.name}: win_rate {report['eval/win_rate']:.4f} "
              f"({chunk_size} battles, seed_start {seed_start}){extra}")
    if not smoke:
        _merge(prereg_path, arm_name, out_dir, chunks)
    env.close()


def _merge(prereg_path: str, arm_name: str, out_dir: Path, chunks: int) -> None:
    prefix = arm_name.lower()
    paths = [out_dir / f"{prefix}.chunk{k:02d}.json" for k in range(chunks)]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        print(f"merge: {missing} missing, no final yet")
        return
    reports = [json.loads(p.read_text()) for p in paths]
    n = sum(r["episodes"] for r in reports)
    final = {
        "arm": arm_name,
        "kind": reports[0]["kind"],
        "seat1": reports[0]["seat1"],
        "seat2": reports[0]["seat2"],
        "episodes": n,
        "chunks": chunks,
        "eval/win_rate": sum(r["eval/win_rate"] * r["episodes"] for r in reports) / n,
        "wins_from_returns": sum(
            r["wins_from_returns"] * r["episodes"] for r in reports) / n,
        "ties_from_returns": sum(
            r["ties_from_returns"] * r["episodes"] for r in reports) / n,
        "mask_desyncs": sum(r["mask_desyncs_delta"] for r in reports),
        "started_at": reports[0]["started_at"],
        "finished_at": reports[-1]["finished_at"],
        "prereg": prereg_path,
        "prereg_sha256": _sha256(prereg_path),
        "git_sha": _git(["rev-parse", "HEAD"]),
    }
    if "search/decisions" in reports[0]:
        dec = sum(r["search/decisions"] for r in reports)
        skips = sum(r["search/placeholder_skips"] for r in reports)
        searched = sum(r["search/searched_decisions"] for r in reports)
        final["search_dose"] = reports[0]["search_dose"]
        final["search/decisions"] = dec
        final["search/placeholder_skips"] = skips
        final["search/placeholder_skip_rate"] = skips / dec if dec else None
        final["search/flips"] = sum(r["search/flips"] for r in reports)
        final["search/searched_decisions"] = searched
        final["search/timeouts"] = sum(r["search/timeouts"] for r in reports)
        final["search/ms_mean"] = sum(
            r["search/ms_mean"] * r["search/searched_decisions"] for r in reports
        ) / max(searched, 1)
        final["search/leaves_mean"] = sum(
            r["search/leaves_mean"] * r["search/searched_decisions"] for r in reports
        ) / max(searched, 1)
        final["search/leaves_max"] = max(r["search/leaves_max"] for r in reports)
    if "evaluator" in reports[0]:
        final["evaluator"] = reports[0]["evaluator"]
        assert all(r.get("evaluator") == final["evaluator"] for r in reports), (
            "F5 FAIL: evaluator provenance differs across chunks"
        )
    (out_dir / f"{prefix}.final.json").write_text(json.dumps(final, indent=2) + "\n")
    print(f"{prefix}.final.json: win_rate {final['eval/win_rate']:.5f} over {n} battles")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--arm", required=True, help="CA, CE0 or CE3")
    parser.add_argument("--battles", type=int)
    parser.add_argument("--smoke", action="store_true",
                        help="single chunk, <arm>_smoke.* output, no merge")
    parser.add_argument("--out-dir", default=ANCHOR_DIR)
    parser.add_argument("--list-arms", action="store_true")
    args = parser.parse_args()
    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    if args.list_arms:
        for name, spec in prereg["anchor_arms"].items():
            print(f"{name}\t{spec['kind']}\t{spec.get('battles')}")
        return
    _preflight(prereg)
    run_arm(prereg, args.prereg, args.arm, args.battles, args.smoke,
            Path(args.out_dir))


if __name__ == "__main__":
    main()
