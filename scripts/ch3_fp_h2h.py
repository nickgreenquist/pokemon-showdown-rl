"""CH3 R2 B1 consequence (ii): our seat for the h2h vs Foul Play.

    python scripts/ch3_fp_h2h.py --prereg configs/eval/ch3_r2_fp_h2h.yaml --arm FG
    python scripts/ch3_fp_h2h.py --prereg configs/eval/ch3_r2_fp_h2h.yaml --arm FS --battles 5 --tag smoke

Owns OUR side only (the foulplay_vs_sh.py division of labor): a LISTENING
poke-env player that accepts challenges from the pre-registered Foul Play
username and drives the s65 checkpoint — deterministically (arm FG), or
through depth-1 search@M (arm FS: SearchAgent on the seat's OWN battle
object; the _SearchEvalAdapter seam without the gym env, since here the
player owns the battle poke-env parses for it). Foul Play runs as a
separate process in its own env exactly as foulplay_vs_sh.py documents.

DEVIATION from the historical --seat PoolPlayer numbers, disclosed in the
pre-reg: this seat is DETERMINISTIC (locked protocol + the R2-credited
configuration), where the 2026-08 -against marks sampled. The FG/FS delta
is seat-matched, so the deviation cancels in the primary read.

CH3 R4 BI-5 additions (additive only; with no `evaluator` key on the arm
every path here behaves exactly as it did for FG/FS):
  * `assert arm["kind"] in ARM_KINDS` — any other string used to run the
    GREEDY seat silently (pre-reg ANCHOR BATTERY / FP BLOCK, review 2
    blocker 2);
  * an `evaluator` key (kind loo) resolves pool-minus-seat-lane with the F5
    membership asserts and is passed to SearchAgent, its provenance written
    into the output JSON — this is what arm FE3 of
    configs/eval/ch3_r4_fp_anchor.yaml runs;
  * the seat lane is `arm.get("seat", "s65")`, so arms that name no seat
    (FG/FS) resolve to exactly the s65 checkpoint and checkpoint_seed 65
    they always did.
The crash-forfeit auto-relaunch loop lives in scripts/ch3_r4_fp_runner.sh.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import numpy as np
import torch
import yaml

from poke_env.data import GenData
from poke_env.player import Player
from poke_env.ps_client.account_configuration import AccountConfiguration

BATTLE_FORMAT = "gen1randombattle"
# CH4 R1 BI-2b/BI-3 (pre-reg configs/eval/ch4_r1_offsh_instrument.yaml):
#   sampled_seat — the checkpoint seat samples instead of argmaxing, rng
#     pinned by the arm's seat_rng_seed (a DISCLOSED locked-protocol
#     deviation; the point of arm S1);
#   fp_vs_clone — the seat is the 808-dim FP behaviour clone, loadable in
#     this 828-dim process ONLY through the eval_checkpoint shim (review 1
#     BL-2 proved load_state_dict RuntimeErrors without it); clone_policy
#     selects sampling (form-matched to the banked pooled comparator) or
#     deterministic (C1b, recorded-only).
#   * ensemble_seat (CH5 R1) — the 4-lane EnsembleAgent that actually played
#     LADDER R1. It carries `lanes: [...]` instead of `seat:`, and the two
#     keys are MUTUALLY EXCLUSIVE and asserted: `ladder.py`'s POLICY_KINDS
#     ("greedy"/"ensemble"/"search") is a SEPARATE namespace, so an arm
#     copied across from a ladder pre-reg must not half-resolve here.
#     Construction is byte-equivalent to ladder.py's: same sha assert, same
#     load_checkpoint/Config/_load_showdown_agent, same lane ORDER — the
#     whole point of the arm is that it rates the object that laddered.
ARM_KINDS = ("greedy_seat", "search_seat", "sampled_seat", "fp_vs_clone",
             "ensemble_seat")


def _build_agent(spec: dict):
    """sha-assert then load THROUGH THE SHIM (eval_checkpoint's
    _load_showdown_agent): an 828 lane loads natively; the 808 clone gets
    PrefixSliceActor — bit-for-bit its own encoding. Returns the agent
    (unchanged contract); the realized input width is read off the actor
    at the call site via _native_dim() for the G8 stamp."""
    import hashlib
    import sys

    sys.path.insert(0, str(Path(__file__).parent))
    from eval_checkpoint import _load_showdown_agent

    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config

    h = hashlib.sha256()
    with open(spec["path"], "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    assert h.hexdigest() == spec["sha256"], f"F-A FAIL: sha256 mismatch on {spec['path']}"

    ckpt = load_checkpoint(spec["path"])
    cfg = Config(**ckpt["config"])
    torch.set_num_threads(1)
    return _load_showdown_agent(ckpt, cfg)


def _native_dim(agent) -> int:
    """Realized input width of a loaded agent: the shim's slice width when
    a cross-encoder checkpoint was wrapped, else the process OBS_DIM.

    An EnsembleAgent has no `.actor`, so before CH5 it would have fallen
    through to OBS_DIM and stamped 828 even over a wrapped 808 member. It
    now recurses and asserts the members agree — a mixed-width ensemble is
    a real possibility here (the clone is 808) and must not stamp silently."""
    from rl.envs.showdown import OBS_DIM
    members = getattr(agent, "members", None)
    if members is not None:
        dims = {_native_dim(m) for m in members}
        assert len(dims) == 1, (
            f"ensemble members disagree on input width: {sorted(dims)} — "
            "the G8 stamp would be a fiction"
        )
        return dims.pop()
    native = getattr(getattr(agent, "actor", None), "in_dim", None)
    return int(native) if native is not None else OBS_DIM


def _resolve_evaluator(prereg: dict, seat_lane: str, spec_eval, agent0):
    """CH3 R4 BI-5: the evaluator plumb-through for the FE3 anchor (pre-reg
    ANCHOR BATTERY / FP BLOCK), mirroring ch3_eval._resolve_evaluator. `loo`
    resolves POOL MINUS THE SEAT LANE here and the F5 membership asserts fire
    at resolution — pool size == 3, own key absent, own agent excluded by
    IDENTITY, every member file sha256 == pin. The provenance dict goes into
    the output JSON so the gate is gradeable from disk. Returns (None, None)
    when the arm carries no `evaluator` key, which leaves the FG/FS code path
    exactly as it was."""
    if not spec_eval:
        return None, None
    evaluator = dict(spec_eval)
    provenance = {"kind": evaluator["kind"]}
    if evaluator["kind"] == "loo":
        pool = [x for x in evaluator.pop("pool") if x != seat_lane]
        assert len(pool) == 3, f"F5: loo pool resolved to {pool}"
        assert seat_lane not in pool, f"F5: own lane {seat_lane} in pool"
        evaluator["agents"] = [
            _build_agent(prereg["checkpoints"][x]) for x in pool
        ]
        assert all(a is not agent0 for a in evaluator["agents"]), (
            "F5: the lane's own agent object is in the ensemble"
        )
        provenance["members"] = pool
        provenance["member_sha256"] = [
            prereg["checkpoints"][x]["sha256"] for x in pool
        ]
    return evaluator, provenance


class SeatPlayer(Player):
    """Deterministic (or search-driven) listening seat. Encode/mask/convert
    trio per PoolPlayer.choose_move; the search path feeds SearchAgent the
    seat's own battle object with rng keyed by (checkpoint_seed,
    battle_index, turn, decision_index) exactly as the R2 eval driver."""

    def __init__(self, agent, search_agent=None, deterministic=True, **kwargs):
        # 2026-08-27, DEADLOCK FIX, and the reason is in poke-env, not here.
        # `max_concurrent_battles` becomes the maxsize of Player's
        # `_battle_count_queue`. In `player.py` the battle-init path does
        # `await self._battle_count_queue.put(None)` at line 221 BEFORE the
        # `if battle_tag in self._battles` check at line 222 that would undo
        # it. So a DUPLICATE `|init|battle` for a room already known, while a
        # battle is live, blocks on a FULL queue **forever** -- and that
        # `await` is inside the single message-handling coroutine, so ALL
        # message processing stops. The seat then sits at 0.0% CPU with
        # foul-play's clock running down, which reads as "slow", not "hung".
        # Measured cost: b81 hung at 639 then 611, b82 at 57 then 699, while
        # b80 survived at 1000. Search arms are the exposed ones because they
        # play 32-47% longer battles (36.8 mean turns vs 25-28 for greedy and
        # ensemble), so they reach the turn-1000 auto-tie -- and the room
        # churn around it -- far more often.
        # maxsize 2 gives the spurious put somewhere to go; it is released
        # again one line later. It does NOT license concurrent play: foul-play
        # challenges strictly serially under --run-count, so exactly one
        # battle is ever live. That is ASSERTED rather than assumed --
        # `max_concurrent_live_battles` is tracked below and stamped into the
        # arm JSON, so "concurrency stayed 1" is checkable at grade time.
        # 2026-08-31, THE ORPHANED-ROOM DEADLOCK (docs/landmines.md). The
        # note above diagnosed the SPURIOUS PUT; the wedge that killed R4S66
        # twice was a different and larger one -- LEAKED ROOMS. poke-env
        # returns a slot only on `|win|`/`|tie|` (player.py:311), and a
        # turn-1000 auto-tie makes both sides Struggle (move index 4), which
        # panics foul-play's Rust engine and leaves a room we still hold.
        # Showdown never ends that room on its own: `nextRequest`/`nextTick`/
        # `checkActivity` all return early on `!this.timerRequesters.size`
        # (showdown/server/room-battle.ts:320/345/410), so with no timer
        # requester a dead opponent never times out. MEASURED: both R4S66
        # attempts wedged at EXACTLY 4 orphans against this 2-slot queue,
        # against 0 orphans in 9,000 greedy battles -- search arms reach turn
        # 1000, greedy ones do not.
        # `start_timer_on_battle_start` attacks the cause (the room now
        # resolves by timeout). maxsize 8 is pure slack behind it: 4 orphans
        # < 8 would have carried BOTH attempts to completion. Neither
        # licenses concurrent play -- foul-play challenges strictly serially
        # under --run-count -- and that stays ASSERTED, not assumed, by
        # `max_concurrent_live_battles` in the arm JSON.
        super().__init__(
            battle_format=BATTLE_FORMAT,
            max_concurrent_battles=8,
            start_timer_on_battle_start=True,
            **kwargs,
        )
        self.max_concurrent_live = 0
        self._agent = agent
        self._sa = search_agent
        self._det = deterministic
        self._type_chart = GenData.from_format(BATTLE_FORMAT).type_chart
        self._battle_tag: str | None = None
        self._battle_index = -1
        self._decision_index = 0
        self.tag_index: dict[str, int] = {}  # CH4 R1 BI-7: per-battle records
        self.ms: list[float] = []
        self.leaves: list[int] = []

    def choose_move(self, battle):
        from rl.envs.showdown import SinglesEnv, _recover_mask_desync, embed_battle

        assert not battle.wait, "wait state reached the seat player"
        live = sum(1 for b in self.battles.values() if not b.finished)
        if live > self.max_concurrent_live:
            self.max_concurrent_live = live
        if battle.battle_tag != self._battle_tag:
            self._battle_tag = battle.battle_tag
            self._battle_index += 1
            self._decision_index = 0
            self.tag_index[battle.battle_tag] = self._battle_index
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        if self._sa is not None:
            t0 = time.perf_counter()
            action, stats = self._sa.act(
                battle, obs, mask, self._battle_index, self._decision_index
            )
            if "search/leaves" in stats:
                self.ms.append((time.perf_counter() - t0) * 1e3)
                self.leaves.append(int(stats["search/leaves"]))
        else:
            action = self._agent.act(obs, mask, deterministic=self._det)
        self._decision_index += 1
        try:
            order = SinglesEnv.action_to_order(np.int64(action), battle)
        except ValueError as exc:
            return _recover_mask_desync(battle, exc)
        return order


async def run(prereg: dict, arm_name: str, battles: int, tag: str) -> dict:
    from rl.envs.showdown import mask_desync_total

    arm = prereg["arms"][arm_name]
    # CH3 R4 BI-5 (review 2 blocker 2): an unrecognised kind used to run the
    # GREEDY seat SILENTLY. It now fails loudly.
    assert arm["kind"] in ARM_KINDS, (
        f"{arm_name}: kind {arm['kind']!r} not in {ARM_KINDS} — an unknown "
        "kind must not silently run the greedy seat"
    )
    # CH5 R1: `seat` and `lanes` are mutually exclusive, and BOTH directions
    # are asserted. `seat` defaults to "s65", so an ensemble arm that forgot
    # its lanes would otherwise have quietly rated ONE lane — the same silent
    # -fallback class BI-5 closed for unknown kinds.
    ensemble_lanes = None
    seat_lane_defaulted = False
    if arm["kind"] == "ensemble_seat":
        from rl.search.ensemble import EnsembleAgent

        assert "seat" not in arm, (
            f"{arm_name}: ensemble_seat takes `lanes`, not `seat` — a `seat` "
            "key here would silently rate a single lane"
        )
        ensemble_lanes = list(arm["lanes"])
        assert ensemble_lanes, f"{arm_name}: ensemble needs at least one lane"
        assert len(ensemble_lanes) == len(set(ensemble_lanes)), (
            f"{arm_name}: duplicate lane in {ensemble_lanes} — a repeated "
            "member silently reweights the log-prob mean"
        )
        seat_lane = None
        agent = EnsembleAgent(
            [_build_agent(prereg["checkpoints"][x]) for x in ensemble_lanes]
        )
    else:
        assert "lanes" not in arm, (
            f"{arm_name}: `lanes` is ensemble_seat-only; kind {arm['kind']!r} "
            "would ignore it and rate a single lane"
        )
        # CH5 R1 review BL-2: this default is a live footgun. An arm that
        # omits `seat` silently runs s65, and if s65 happens to be pinned in
        # that pre-reg the sha assert PASSES — so three "50M" arms could all
        # be one 12M lane and the JSONs would be indistinguishable from
        # correct ones. The default CANNOT simply be removed: four banked
        # arms depend on it (ch3_r2_fp_h2h FG/FS, fp_budget_ladder
        # FP20/FP500) and their pre-regs must stay runnable. So it stays,
        # and becomes SELF-DESCRIBING instead — `seat_lane_defaulted` is
        # stamped into every report and a pre-reg gates on it being False.
        seat_lane_defaulted = "seat" not in arm
        seat_lane = arm.get("seat", "s65")
        agent = _build_agent(prereg["checkpoints"][seat_lane])
    native_dim = _native_dim(agent)
    # CH4 R1 BI-3: a sampling seat (S1's whole point; C1's form-matching to
    # the banked pooled-orientation clone comparator) draws from torch's
    # RNG, so the arm must pin seat_rng_seed or it is irreproducible.
    deterministic = True
    if arm["kind"] == "sampled_seat" or (
        arm["kind"] == "fp_vs_clone" and arm.get("clone_policy") == "sampling"
    ):
        deterministic = False
        seed = int(arm["seat_rng_seed"])
        torch.manual_seed(seed)
        np.random.seed(seed)
    search_agent = None
    eval_provenance = None
    if arm["kind"] == "search_seat":
        from rl.search.agent import SearchAgent
        from rl.search.matrix import DOSES

        evaluator, eval_provenance = _resolve_evaluator(
            prereg, seat_lane, arm.get("evaluator"), agent
        )
        search_agent = SearchAgent(
            agent, DOSES[arm["dose"]],
            checkpoint_seed=int(seat_lane.lstrip("s")),
            evaluator=evaluator,
        )
    seat = SeatPlayer(
        agent,
        search_agent,
        deterministic=deterministic,
        account_configuration=AccountConfiguration(arm["seat_username"], None),
    )
    print(f"seat '{arm['seat_username']}' ({arm['kind']}) waiting for {battles} "
          f"challenges from '{arm['fp_username']}'")
    started = time.monotonic()
    await seat.accept_challenges(arm["fp_username"], battles)
    elapsed = time.monotonic() - started

    finished = seat.n_finished_battles
    our_wins = seat.n_won_battles
    ties = seat.n_tied_battles
    fp_wins = seat.n_lost_battles
    turns = [b.turn for b in seat.battles.values() if b.finished]

    report = {
        "tag": tag,
        "arm": arm_name,
        "battle_format": BATTLE_FORMAT,
        "seat_username": arm["seat_username"],
        "fp_username": arm["fp_username"],
        "battles_requested": battles,
        "battles_finished": finished,
        "our_wins": our_wins,
        "foulplay_wins": fp_wins,
        "ties": ties,
        "our_win_rate": (our_wins / finished) if finished else None,
        "foulplay_win_rate": (fp_wins / finished) if finished else None,
        "tie_rate": (ties / finished) if finished else None,
        "mean_turns": (sum(turns) / len(turns)) if turns else None,
        "wall_clock_sec": round(elapsed, 1),
        "sec_per_battle": round(elapsed / finished, 2) if finished else None,
        "mask_desyncs": mask_desync_total(),
        "gate_all_challenges_resolved": finished == battles,
        # CH4 R1 BI-7: per-battle records — the S0 slice, the tape<->JSON
        # join, and the crash-forfeit interaction are all defined on these.
        "per_battle": sorted(
            (
                {
                    "index": seat.tag_index.get(t, -1),
                    "tag": t,
                    "outcome": ("win" if b.won else "loss") if b.won is not None else "tie",
                    "turns": b.turn,
                }
                for t, b in seat.battles.items()
                if b.finished
            ),
            key=lambda r: r["index"],
        ),
        # CH4 R1 G8 stamps.
        "seat_policy": "sampled" if not deterministic else "deterministic",
        "seat_rng_seed": arm.get("seat_rng_seed"),
        "seat_lane": seat_lane,
        "seat_lane_defaulted": seat_lane_defaulted,
        "seat_native_dim": native_dim,
        "declared_search_time_ms": arm.get("search_time_ms"),
        # 2026-08-27: proves the deadlock fix did not buy concurrency. The
        # queue has slack 2 so a duplicate battle-init cannot block, but play
        # must remain strictly serial; if this is ever > 1 the arm is NOT
        # commensurable with the k=1 comparator wave and must be re-run.
        "max_concurrent_live_battles": seat.max_concurrent_live,
    }
    if search_agent is not None:
        ms = np.array(seat.ms) if seat.ms else np.array([0.0])
        lv = np.array(seat.leaves) if seat.leaves else np.array([0])
        report.update({
            "search/ms_mean": float(ms.mean()),
            "search/leaves_mean": float(lv.mean()),
            "search/searched_decisions": len(seat.ms),
            "search/decisions": search_agent.counters["search/decisions"],
            "search/placeholder_skips": search_agent.counters["search/placeholder_skips"],
            "search/flips": search_agent.counters["search/flips"],
        })
    if eval_provenance is not None:
        report["evaluator"] = eval_provenance   # F5, gradeable from disk
        report["seat_lane"] = seat_lane
    if ensemble_lanes is not None:
        # Provenance in the SAME shape ladder.py stamps, so an FP number and
        # a ladder number for "L2" are checkably the same object.
        report["seat_lanes"] = ensemble_lanes
        report["seat_sha256"] = [
            prereg["checkpoints"][x]["sha256"] for x in ensemble_lanes
        ]
        report["ensemble/decisions"] = agent.decisions
        report["ensemble/flips"] = agent.flips
        report["ensemble/flip_rate"] = (
            agent.flips / agent.decisions if agent.decisions else None
        )
    return report


def main() -> None:
    import os

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", required=True)
    parser.add_argument("--arm", required=True,
                        help="an arm name defined in the pre-reg's arms block")
    parser.add_argument("--battles", type=int)
    parser.add_argument("--tag")
    args = parser.parse_args()

    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required (828-d id-suffix protocol)"

    with open(args.prereg) as f:
        prereg = yaml.safe_load(f)
    battles = args.battles or prereg["arms"][args.arm]["battles"]
    tag = args.tag or args.arm.lower()

    result = asyncio.run(run(prereg, args.arm, battles, tag))

    # CH4 R1 G8: era/provenance stamp — launch sha, the pre-reg's content
    # hash (the thresholds cannot drift between launch and grading without
    # a trace), encoder state, process obs width.
    import hashlib
    import subprocess

    from rl.envs.showdown import OBS_DIM
    result["launch_git_sha"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    result["prereg_path"] = args.prereg
    result["prereg_sha256"] = hashlib.sha256(Path(args.prereg).read_bytes()).hexdigest()
    result["encoder_env"] = {
        v: os.environ.get(v)
        for v in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS")
    }
    result["process_obs_dim"] = OBS_DIM

    out_dir = Path(prereg["results_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{tag}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "returns"}, indent=2))
    print(f"\nwrote {out}")
    if not result["gate_all_challenges_resolved"]:
        print("\nG3 FAILED: not every challenge resolved — the number is VOID.")
    print("G2: cross-check against Foul Play's own W/L tally before believing it.")


if __name__ == "__main__":
    main()
