"""CH3 R2 B1 consequence (i): the SH-exploitation falsifier, search arm + grader.

    python scripts/ch3_r2_falsifier.py --prereg configs/eval/ch3_r2_falsifier.yaml
    python scripts/ch3_r2_falsifier.py --prereg configs/eval/ch3_r2_falsifier.yaml --battles 10 --smoke
    python scripts/ch3_r2_falsifier.py --prereg configs/eval/ch3_r2_falsifier.yaml --grade

Runs arm SA of the pre-reg: s65 + depth-1 search@M (the A1S configuration
verbatim — SearchAgent, DOSES["M"], checkpoint_seed 65, _SearchEvalAdapter
with rng keyed by global episode index) from seat 1 against the BC clone
sampling in seat 2 (PoolPlayer through eval_checkpoint's cross-encoder
shim). Chunked and resumable like ch3_eval.py: one JSON per chunk under
results_dir, SF-13 battle2 sentinel at chunk 0, win_rate ==
wins_from_returns asserted per chunk (F-B is HARD here, not just graded).

The GA/GB greedy arms are plain scripts/eval_checkpoint.py invocations
(the exact 2026-08-15 machinery) — this script only adds what did not
exist: search from seat 1 of a checkpoint-vs-checkpoint pairing.

--grade reads ga.json / gb.json / sa.final.json plus the pre-reg and
prints the pre-stated PRIMARY branch (P1/P2/P3, ceiling guard) and the
secondary trail — no data-dependent choices live here.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import torch
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_eval import (  # noqa: E402
    _install_battle2_sentinel,
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


def _preflight(prereg: dict) -> None:
    import os

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d id-suffix protocol)"
    for lane, spec in prereg["checkpoints"].items():
        got = _sha256(spec["path"])
        assert got == spec["sha256"], (
            f"F-A FAIL: {lane} sha256 {got} != prereg {spec['sha256']}"
        )
    print("preflight: F-A sha256 x2 OK")


def run_sa(prereg: dict, battles: int | None, smoke: bool) -> None:
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES

    from rl.train import make_agent  # noqa: F401  (imported via eval_checkpoint path)

    arm = prereg["arms"]["SA"]
    total = battles or arm["battles"]
    chunks = 1 if smoke else arm["chunks"]
    chunk_size = total // chunks
    out_dir = Path(prereg["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    s65_spec = prereg["checkpoints"][arm["seat1"]]
    clone_spec = prereg["checkpoints"][arm["seat2"]]
    ckpt = load_checkpoint(s65_spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)

    opponent = _opponent_from_checkpoint(clone_spec["path"], cfg.seed)
    env = make_env(cfg.env_id, cfg.seed, env_kwargs={"opponent": opponent})
    agent0 = _load_showdown_agent(ckpt, cfg)

    assert getattr(env.unwrapped, "_privileged", None) is False, (
        "SF-13: the eval env must not emit info['privileged']"
    )
    sa = SearchAgent(
        agent0,
        DOSES[arm["dose"]],
        checkpoint_seed=int(arm["seat1"].lstrip("s")),
    )
    adapter = _SearchEvalAdapter(sa, env)

    prefix = "sa_smoke" if smoke else "sa"
    base = cfg.eval_episodes
    desync_before = mask_desync_total()
    for k in range(chunks):
        chunk_path = out_dir / f"{prefix}.chunk{k:02d}.json"
        if chunk_path.exists():
            print(f"{chunk_path.name}: exists, skipping")
            continue
        seed_start = base + k * chunk_size
        adapter.begin_chunk(seed_start)
        sentinel_handle = None
        if k == 0:
            sentinel_handle = _install_battle2_sentinel(env.unwrapped._env.env)
        try:
            returns, outcomes, faints = _run_eval_episodes(
                adapter, env, chunk_size, seed_start=seed_start
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
            f"F-B FAIL on chunk {k}: win_rate {metrics['eval/win_rate']} != "
            f"wins_from_returns {wins_from_returns}"
        )
        report = {
            "arm": "SA",
            "chunk": k,
            "episodes": chunk_size,
            "seed_start": seed_start,
            **metrics,
            "return_mean": float(np.mean(returns)),
            "wins_from_returns": wins_from_returns,
            "ties_from_returns": sum(1 for r in returns if r == 0) / len(returns),
            "mask_desyncs_delta": desync_now - desync_before,
            "returns": returns,
            "search_dose": arm["dose"],
            **adapter.chunk_summary(),
        }
        desync_before = desync_now
        chunk_path.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{chunk_path.name}: win_rate {report['eval/win_rate']:.4f} "
              f"({chunk_size} battles, seed_start {seed_start})")
    if not smoke:
        _merge_sa(prereg, out_dir, chunks, chunk_size)
    env.close()


def _merge_sa(prereg: dict, out_dir: Path, chunks: int, chunk_size: int) -> None:
    reports = []
    for k in range(chunks):
        p = out_dir / f"sa.chunk{k:02d}.json"
        if not p.exists():
            print(f"merge: {p.name} missing, no final yet")
            return
        reports.append(json.loads(p.read_text()))
    n = sum(r["episodes"] for r in reports)
    wins = sum(r["eval/win_rate"] * r["episodes"] for r in reports)
    searched = sum(r["search/searched_decisions"] for r in reports)
    final = {
        "arm": "SA",
        "episodes": n,
        "eval/win_rate": wins / n,
        "wins_from_returns": sum(r["wins_from_returns"] * r["episodes"] for r in reports) / n,
        "ties_from_returns": sum(r["ties_from_returns"] * r["episodes"] for r in reports) / n,
        "mask_desyncs": sum(r["mask_desyncs_delta"] for r in reports),
        "search/ms_mean": sum(r["search/ms_mean"] * r["search/searched_decisions"] for r in reports) / max(searched, 1),
        "search/leaves_mean": sum(r["search/leaves_mean"] * r["search/searched_decisions"] for r in reports) / max(searched, 1),
        "search/searched_decisions": searched,
        "search/decisions": sum(r["search/decisions"] for r in reports),
        "search/placeholder_skips": sum(r["search/placeholder_skips"] for r in reports),
        "search/flips": sum(r["search/flips"] for r in reports),
        "prereg_sha256": _sha256("configs/eval/ch3_r2_falsifier.yaml"),
    }
    (out_dir / "sa.final.json").write_text(json.dumps(final, indent=2) + "\n")
    print(f"sa.final.json: win_rate {final['eval/win_rate']:.5f} over {n} battles")


def grade(prereg: dict) -> None:
    out_dir = Path(prereg["results_dir"])
    ga = json.loads((out_dir / "ga.json").read_text())
    gb = json.loads((out_dir / "gb.json").read_text())
    sa = json.loads((out_dir / "sa.final.json").read_text())

    for name, rep in (("GA", ga), ("GB", gb), ("SA", sa)):
        assert rep["eval/win_rate"] == rep["wins_from_returns"], (
            f"F-B FAIL: {name} win_rate != wins_from_returns"
        )
    n = prereg["arms"]["SA"]["battles"]
    p_sa, p_ga = sa["eval/win_rate"], ga["eval/win_rate"]
    delta = p_sa - p_ga
    se = math.sqrt(p_sa * (1 - p_sa) / n + p_ga * (1 - p_ga) / n)

    leaves = sa["search/leaves_mean"]
    f_c = abs(leaves - 353) / 353 > 0.25
    print(f"F-B PASS all three JSONs; F-C leaves_mean {leaves:.1f} "
          f"({'FIRES' if f_c else 'PASS'}); mask_desyncs "
          f"GA {ga['mask_desyncs']} GB {gb['mask_desyncs']} SA {sa['mask_desyncs']} (F-D, disclosed)")
    if f_c:
        print("VOID: F-C fired — diagnose before any branch is read")
        return

    # GB is recorded from the clone's seat; s65's B number, ties non-wins
    s65_b = 1.0 - gb["eval/win_rate"] - gb["ties_from_returns"]
    g_pooled = (ga["eval/win_rate"] + s65_b) / 2
    print(f"GA (s65 greedy, det seat) {p_ga:.4f} | GB s65-from-sampling-seat "
          f"{s65_b:.4f} | G pooled {g_pooled:.4f} "
          f"(trail {prereg['anchors']['d25_trail_vs_clone']} -> this)")
    print(f"SA (s65 search@M, det seat) {p_sa:.4f}")
    print(f"PRIMARY delta SA-GA {delta:+.4f}, se_diff {se:.4f}, 2*se {2*se:.4f} "
          f"(vs-SH delta on this lane {prereg['anchors']['s65_vs_sh_search_m'] - prereg['anchors']['s65_vs_sh_greedy']:+.4f})")

    if p_ga >= 0.90:
        if delta <= 0:
            print("BRANCH: P2 FIRES under the ceiling guard — non-positive delta")
        else:
            print("BRANCH: CEILING-LIMITED (GA >= 0.90) — descriptive only, "
                  "P1/P3 unreachable per pre-reg")
        return
    if delta >= 2 * se:
        print("BRANCH: P1 NOT-SH-SPECIFIC — the falsifier PASSES; licensed: "
              "on the s65 lane the search gain moves the non-SH anchor too")
    elif delta <= 0:
        print("BRANCH: P2 FIRES — SH-exploitation flagged; headline keeps its "
              "number, gains the mandatory caveat; goes to the maintainer")
    else:
        print("BRANCH: P3 INDETERMINATE — to the maintainer, levels quoted, "
              "no letter claimed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--battles", type=int)
    parser.add_argument("--smoke", action="store_true",
                        help="single chunk, sa_smoke.* output, no merge")
    parser.add_argument("--grade", action="store_true")
    args = parser.parse_args()
    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    if args.grade:
        grade(prereg)
        return
    _preflight(prereg)
    run_sa(prereg, args.battles, args.smoke)


if __name__ == "__main__":
    main()
