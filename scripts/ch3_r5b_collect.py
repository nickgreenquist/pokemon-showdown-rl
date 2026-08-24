"""CH3 R5b BI-1: Stage-2a self-play collection with the per-decision recorder.

    python scripts/ch3_r5b_collect.py --prereg configs/eval/ch3_r5b_exit.yaml --lane s62
    python scripts/ch3_r5b_collect.py --prereg ... --lane s62 --battles 4 --smoke

One lane per invocation (pre-reg Q4): search@M, evaluator ABSENT (E0),
seat 1 deterministic search vs THE SAME LANE's checkpoint sampling on
seat 2 — the r5a TS construction verbatim (seat1 == seat2 is intentional),
3000 battles in 10 chunks. Per SEARCHED decision the recorder persists
exactly the pre-reg whitelist and NOTHING else (F-P2):

    obs (828 f32), mask, row_ev, chosen, policy_argmax, lane, battle_id,
    decision_index

Placeholder rows (rl/search/agent.py locked-turn early return) carry no
row_ev and are EXCLUDED at the recording site; the realized skip rate is
in every chunk JSON. row_ev is stored full-width with NaN at actions the
search did not score, alongside the mask, so F-R can recompute
softmax_tau(row_ev) offline bit-for-bit.

The registered instruments are NOT modified: `_SearchEvalAdapter` is used
as-is and the recording happens in a proxy around SearchAgent.act, which
sees (obs, mask, stats, battle_index, decision_index) — everything the
whitelist needs. Chunked and resumable like scripts/ch3_r4_anchors.py: a
chunk is done iff BOTH its .json and its .npz exist; the merge writes
<lane>.final.json with per-chunk npz sha256s (F-R provenance).

Gates carried here: D-1 (t_gate_readout cell == T-PASS asserted at start,
mechanically), F-P2 (privileged-env assert + chunk-0 battle2 sentinel +
obs width 828), F-A8 (win_rate == wins_from_returns HARD assert), F-C
(leaves band recorded per chunk), F-M (ms band recorded), F-U
(_print_username on the record).
"""

import argparse
import hashlib
import json
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
from ch3_r4_anchors import _git  # noqa: E402
from eval_checkpoint import (  # noqa: E402
    _load_showdown_agent,
    _opponent_from_checkpoint,
)

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.evaluation import _run_eval_episodes, eval_metrics  # noqa: E402
from rl.envs.make import make_env  # noqa: E402
from rl.envs.showdown import mask_desync_total  # noqa: E402

COLLECT_DIR = "results/ch3_r5b/collect"
T_GATE_READOUT = "results/ch3_r5a/t_gate_readout.json"
LANES = ("s62", "s63", "s64", "s65")
BATTLES = 3000
CHUNKS = 10
DOSE = "M"
OBS_DIM = 828
LEAVES_EXPECTED = 353.0
LEAVES_BAND = 0.25
MS_BAND = (54.9, 91.5)  # F-M, recorded; outside -> STOP for diagnosis


def assert_t_gate_pass() -> None:
    """D-1: asserted mechanically at the start of every Stage-2 job."""
    readout = json.loads(Path(T_GATE_READOUT).read_text())
    assert readout["cell"] == "T-PASS", (
        f"D-1 FAIL: {T_GATE_READOUT} cell is {readout['cell']!r}, not T-PASS — "
        "no Stage-2 job may run"
    )


def _preflight(prereg: dict, lane: str) -> None:
    """B-5/B-6 at collection time: encoder env vars, simulator: 4, pin count
    == expected_pins, and sha256 on every pin THAT IS REAL AT THIS STAGE —
    the base four and the clone. The eight distilled/placebo pins are
    placeholders until fit time (pre-reg `checkpoints:` note) and are
    asserted to still BE placeholders here, so a stale fit cannot leak in.
    """
    import os
    import re

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d id-suffix protocol)"
    pins = prereg["checkpoints"]
    expected = prereg["expected_pins"]
    assert len(pins) == expected, f"expected {expected} pins, got {len(pins)}"
    assert lane in LANES and lane in pins, f"unknown collection lane {lane!r}"
    n_real = 0
    for name, spec in pins.items():
        if name.startswith(("d6", "p6")):
            assert spec["sha256"].startswith("<"), (
                f"pin {name} must still be a placeholder at collection time — "
                "a stale fit may have leaked in"
            )
            continue
        assert not spec["sha256"].startswith("<"), (
            f"pin {name} has a placeholder sha but is not a fit-time pin"
        )
        got = _sha256(spec["path"])
        assert got == spec["sha256"], (
            f"B-5 FAIL: {name} checkpoint sha256 {got} != prereg {spec['sha256']}"
        )
        n_real += 1
    assert n_real == 5, f"collection-time preflight expects 5 real pins, got {n_real}"
    cfg_js = Path("showdown/config/config.js").read_text()
    m = re.search(r"^\s*simulator:\s*(\d+)", cfg_js, re.M)
    assert m and int(m.group(1)) >= 4, (
        "showdown/config/config.js: `simulator: 4` not set (see CLAUDE.md)"
    )
    print(f"preflight: sha256 x{n_real} OK (base four + clone); simulator>=4 OK")


class _RecordingSearchAgent:
    """Records the pre-reg whitelist per SEARCHED decision, delegating to the
    real SearchAgent. Placeholder rows carry no `search/row_ev` and are
    excluded at this site (pre-reg `placeholder_rows`). The registered
    `_SearchEvalAdapter` reads `.counters` and `.entropy_median()` off its
    agent; both are passed through."""

    def __init__(self, sa, lane: str):
        self._sa = sa
        self._lane = lane
        self.counters = sa.counters
        self.rows: list[dict] = []

    def act(self, battle, obs, mask, battle_index, decision_index):
        action, stats = self._sa.act(battle, obs, mask, battle_index, decision_index)
        if "search/row_ev" in stats:
            mask_arr = np.asarray(mask, dtype=np.uint8)
            ev = np.full(mask_arr.shape[0], np.nan, dtype=np.float32)
            for a, v in stats["search/row_ev"].items():
                ev[a] = v
            self.rows.append({
                "obs": np.asarray(obs, dtype=np.float32),
                "mask": mask_arr,
                "row_ev": ev,
                "chosen": int(stats["search/chosen"]),
                "policy_argmax": int(stats["search/policy_argmax"]),
                "battle_id": int(battle_index),
                "decision_index": int(decision_index),
            })
        return action, stats

    def entropy_median(self):
        return self._sa.entropy_median()

    def dump_chunk(self, path: Path) -> int:
        rows, self.rows = self.rows, []
        assert rows, "recorder dump with zero searched rows — collection broken"
        obs = np.stack([r["obs"] for r in rows])
        assert obs.shape[1] == OBS_DIM, (
            f"F-P2 FAIL: persisted obs width {obs.shape[1]} != {OBS_DIM}"
        )
        np.savez_compressed(
            path,
            obs=obs,
            mask=np.stack([r["mask"] for r in rows]),
            row_ev=np.stack([r["row_ev"] for r in rows]),
            chosen=np.array([r["chosen"] for r in rows], dtype=np.int32),
            policy_argmax=np.array([r["policy_argmax"] for r in rows], dtype=np.int32),
            battle_id=np.array([r["battle_id"] for r in rows], dtype=np.int32),
            decision_index=np.array([r["decision_index"] for r in rows], dtype=np.int32),
            lane=np.array(self._lane),
        )
        return len(rows)


def run_lane(prereg: dict, prereg_path: str, lane: str,
             battles: int | None, smoke: bool, out_dir: Path) -> None:
    from rl.search.agent import SearchAgent
    from rl.search.matrix import DOSES

    total = battles or BATTLES
    chunks = 1 if smoke else CHUNKS
    chunk_size = total // chunks
    assert chunk_size > 0
    out_dir.mkdir(parents=True, exist_ok=True)

    spec = prereg["checkpoints"][lane]
    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(cfg.torch_threads)

    # seat 2 = the SAME lane's checkpoint, sampling (r5a TS verbatim);
    # seat 1 = deterministic search@M, evaluator ABSENT (E0).
    opponent = _opponent_from_checkpoint(spec["path"], cfg.seed)
    env = make_env(cfg.env_id, cfg.seed, env_kwargs={"opponent": opponent})
    assert getattr(env.unwrapped, "_privileged", None) is False, (
        "F-P2/SF-13: the collection env must not emit info['privileged']"
    )
    agent0 = _load_showdown_agent(ckpt, cfg)
    sa = SearchAgent(agent0, DOSES[DOSE], checkpoint_seed=int(lane.lstrip("s")),
                     evaluator=None)
    recorder = _RecordingSearchAgent(sa, lane)
    adapter = _SearchEvalAdapter(recorder, env)
    _print_username(env)  # F-U: realized usernames on the record

    prefix = f"{lane}_smoke" if smoke else lane
    base = cfg.eval_episodes
    desync_before = mask_desync_total()
    for k in range(chunks):
        chunk_json = out_dir / f"{prefix}.chunk{k:02d}.json"
        chunk_npz = out_dir / f"{prefix}.chunk{k:02d}.npz"
        if chunk_json.exists() and chunk_npz.exists():
            print(f"{chunk_json.name}: exists (json+npz), skipping")
            continue
        recorder.rows = []
        seed_start = base + k * chunk_size
        adapter.begin_chunk(seed_start)
        sentinel_handle = None
        if k == 0:
            sentinel_handle = _install_battle2_sentinel(env.unwrapped._env.env)
        started_at = time.time()
        try:
            returns, outcomes, faints = _run_eval_episodes(
                adapter, env, chunk_size, seed_start=seed_start
            )
        finally:
            if sentinel_handle is not None:
                _uninstall_battle2_sentinel(env.unwrapped._env.env, sentinel_handle)
                print(f"chunk {k}: battle2 sentinel armed for the whole chunk, "
                      "0 rl/search accesses (F-P2/SF-13)")
        n_rows = recorder.dump_chunk(chunk_npz)
        metrics = eval_metrics(returns, outcomes, faints, win_rate=True)
        desync_now = mask_desync_total()
        wins_from_returns = sum(1 for r in returns if r > 0) / len(returns)
        assert metrics["eval/win_rate"] == wins_from_returns, (
            f"F-A8 FAIL on {lane} chunk {k}: win_rate {metrics['eval/win_rate']} "
            f"!= wins_from_returns {wins_from_returns}"
        )
        report = {
            "arm": f"COLLECT_{lane.upper()}",
            "kind": "collect_search_h2h",
            "seat1": lane,
            "seat2": lane,
            "chunk": k,
            "episodes": chunk_size,
            "seed_start": seed_start,
            **metrics,
            "return_mean": float(np.mean(returns)),
            "wins_from_returns": wins_from_returns,
            "ties_from_returns": sum(1 for r in returns if r == 0) / len(returns),
            "mask_desyncs_delta": desync_now - desync_before,
            "recorded_rows": n_rows,
            "npz_sha256": _sha256(str(chunk_npz)),
            "started_at": started_at,
            "finished_at": time.time(),
            "returns": returns,
            **adapter.chunk_summary(),
            "search_dose": DOSE,
            "search/timeouts": 0,  # no counter exists; the watchdog RAISES
        }
        report["f_c_leaves_ok"] = bool(
            abs(report["search/leaves_mean"] - LEAVES_EXPECTED) / LEAVES_EXPECTED
            <= LEAVES_BAND
        )
        report["f_m_ms_ok"] = bool(
            MS_BAND[0] <= report["search/ms_mean"] <= MS_BAND[1]
        )
        desync_before = desync_now
        chunk_json.write_text(json.dumps(report, indent=2) + "\n")
        print(f"{chunk_json.name}: win_rate {report['eval/win_rate']:.4f} | "
              f"rows {n_rows}, leaves {report['search/leaves_mean']:.1f} "
              f"({'F-C ok' if report['f_c_leaves_ok'] else 'F-C FIRES'}), "
              f"ms {report['search/ms_mean']:.1f} "
              f"({'F-M ok' if report['f_m_ms_ok'] else 'F-M FIRES'}), "
              f"skips {report['search/placeholder_skips']}")
    if not smoke:
        _merge(prereg_path, lane, out_dir, chunks)
    env.close()


def _merge(prereg_path: str, lane: str, out_dir: Path, chunks: int) -> None:
    paths = [(out_dir / f"{lane}.chunk{k:02d}.json",
              out_dir / f"{lane}.chunk{k:02d}.npz") for k in range(chunks)]
    missing = [p.name for pair in paths for p in pair if not p.exists()]
    if missing:
        print(f"merge: {missing} missing, no final yet")
        return
    reports = [json.loads(j.read_text()) for j, _ in paths]
    for r, (_, npz) in zip(reports, paths):
        got = _sha256(str(npz))
        assert got == r["npz_sha256"], (
            f"F-R FAIL: {npz.name} sha256 {got} != chunk record {r['npz_sha256']}"
        )
    n = sum(r["episodes"] for r in reports)
    dec = sum(r["search/decisions"] for r in reports)
    skips = sum(r["search/placeholder_skips"] for r in reports)
    searched = sum(r["search/searched_decisions"] for r in reports)
    final = {
        "arm": f"COLLECT_{lane.upper()}",
        "kind": "collect_search_h2h",
        "seat1": lane,
        "seat2": lane,
        "episodes": n,
        "chunks": chunks,
        "eval/win_rate": sum(r["eval/win_rate"] * r["episodes"] for r in reports) / n,
        "wins_from_returns": sum(
            r["wins_from_returns"] * r["episodes"] for r in reports) / n,
        "mask_desyncs": sum(r["mask_desyncs_delta"] for r in reports),
        "recorded_rows": sum(r["recorded_rows"] for r in reports),
        "rows_per_battle": sum(r["recorded_rows"] for r in reports) / n,
        "search_dose": DOSE,
        "search/decisions": dec,
        "search/placeholder_skips": skips,
        "search/placeholder_skip_rate": skips / dec if dec else None,
        "search/searched_decisions": searched,
        "search/flips": sum(r["search/flips"] for r in reports),
        "search/timeouts": sum(r["search/timeouts"] for r in reports),
        "search/ms_mean": sum(
            r["search/ms_mean"] * r["search/searched_decisions"] for r in reports
        ) / max(searched, 1),
        "search/leaves_mean": sum(
            r["search/leaves_mean"] * r["search/searched_decisions"] for r in reports
        ) / max(searched, 1),
        "npz_sha256": {f"{lane}.chunk{k:02d}.npz": r["npz_sha256"]
                       for k, r in enumerate(reports)},
        "started_at": reports[0]["started_at"],
        "finished_at": reports[-1]["finished_at"],
        "prereg": prereg_path,
        "prereg_sha256": _sha256(prereg_path),
        "git_sha": _git(["rev-parse", "HEAD"]),
    }
    (out_dir / f"{lane}.final.json").write_text(json.dumps(final, indent=2) + "\n")
    print(f"{lane}.final.json: win_rate {final['eval/win_rate']:.5f}, "
          f"{final['recorded_rows']} rows over {n} battles "
          f"({final['rows_per_battle']:.1f}/battle)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--lane", required=True, choices=LANES)
    parser.add_argument("--battles", type=int)
    parser.add_argument("--smoke", action="store_true",
                        help="single chunk, <lane>_smoke.* output, no merge")
    parser.add_argument("--out-dir", default=COLLECT_DIR)
    args = parser.parse_args()
    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    assert_t_gate_pass()
    _preflight(prereg, args.lane)
    run_lane(prereg, args.prereg, args.lane, args.battles, args.smoke,
             Path(args.out_dir))


if __name__ == "__main__":
    main()
