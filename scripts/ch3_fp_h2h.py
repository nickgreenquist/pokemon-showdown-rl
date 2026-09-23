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
A `search_seat` arm may also declare `leaf_encoding: det_blind` (2026-09-10,
docs/search_relook/DET_BLIND.md); absent = the as-is leaf encoding, and the
realized value lands in the report as `search_leaf_encoding` either way.
It may likewise declare `margin_delta: <float>` (2026-09-10,
docs/search_relook/MARGIN_SELECTOR.md) — the margin-gated selector; absent =
the hard argmax every banked FS/FE arm ran, and the realized value lands in
the report as `search_margin_delta` (null when off) either way.
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
#   * native_seat (R7 G2, plan §6; 2026-09-23) -- the L-OP on a live battle
#     (`rl/search/lop.py::NativeLOp`): B belief-sampled worlds built through
#     B6's write-side bridge into pkmn_gen1 roots, `native.solve` on each with
#     the committee's critic at the leaves and the committee's prior on that
#     world's foe view, PIMC over the worlds, the gated soft best response.
#     Carries `seat:` (provenance and the decision-RNG seed) and
#     `ensemble_members:` (the committee, the seat among them) like a searched
#     committee, and a `lop:` block whose keys are NativeLOp's signature
#     (`lop_from`) with the solve dials under `solve:` (`native.dials_from`).
#     Its GREEDY action is EnsembleAgent's over the same members, so against an
#     `ensemble_seat` arm over those members the comparison isolates the
#     search. RUNS IN AN ENGINE ENV (pkmn-engine-r7: pkmn_gen1 + poke-env,
#     no poke_engine) -- `PY=` on the runner -- and never imports SearchAgent.
ARM_KINDS = ("greedy_seat", "search_seat", "sampled_seat", "fp_vs_clone",
             "ensemble_seat", "native_seat")


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
        # F5 pool size: R4's 4-lane default (peers == 3) unless the pre-reg
        # declares `loo_pool_expected` (S3, 2026-09-10 — three 100M lanes).
        expected = int(evaluator.pop("loo_pool_expected", 3))
        pool = [x for x in evaluator.pop("pool") if x != seat_lane]
        assert len(pool) == expected, (
            f"F5: loo pool resolved to {pool} (expected {expected} peers)"
        )
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
        # per-decision probe stats, keyed by their own name; see choose_move
        self.probe: dict[str, list[float]] = {}
        self.leaves: list[int] = []
        # EVERY decision's seat-side wall time, whatever the arm kind (2026-09-23,
        # the G2 reviews): JOURNEY 14 wants decisions/sec for BOTH arms, and an
        # arm's own wall clock is mostly Foul Play's think time and the server.
        self.decision_ms: list[float] = []
        self.concurrent_decisions = 0
        # ARM-LEVEL decision total. `_decision_index` RESETS every battle, so it
        # cannot be the denominator of an arm-level rate -- see below.
        self._decisions_total = 0

    def choose_move(self, battle):
        from rl.envs.showdown import SinglesEnv, _recover_mask_desync, embed_battle

        assert not battle.wait, "wait state reached the seat player"
        live = sum(1 for b in self.battles.values() if not b.finished)
        if live > self.max_concurrent_live:
            self.max_concurrent_live = live
        # COUNT the decisions taken while more than one battle was live, not
        # just the MAX (added 2026-09-17). `max_concurrent_live_battles` is a
        # max over the whole arm, so ONE transient at ONE battle seam -- poke-env
        # creating the next battle object before the previous one's `finished`
        # flag lands -- sets it to 2 for a 3000-battle arm and is indistinguish-
        # able from genuinely parallel play, which would invalidate the arm.
        # Three of the banked monster-read arms carry a 2, including E3WF, the
        # number that PICKED THE LADDER OBJECT; inferring "transient" from
        # compute-share arithmetic worked but should not have been necessary.
        if live > 1:
            self.concurrent_decisions += 1
        if battle.battle_tag != self._battle_tag:
            self._battle_tag = battle.battle_tag
            self._battle_index += 1
            self._decision_index = 0
            self.tag_index[battle.battle_tag] = self._battle_index
            if hasattr(self._agent, "reset_episode"):
                self._agent.reset_episode()  # the loop breaker's memory is per battle
        t_dec = time.perf_counter()
        obs = embed_battle(battle, self._type_chart)
        mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
        if self._sa is not None:
            t0 = time.perf_counter()
            try:
                action, stats = self._sa.act(
                    battle, obs, mask, self._battle_index, self._decision_index
                )
            except Exception as exc:
                # R7 G2: the native L-op's OperatorMismatch means the arm is not the
                # operator G1 measured. poke-env would swallow the exception in its
                # message task and the battle would forfeit on the timer as an
                # ORDINARY LOSS; exiting the process makes it a death the runner sees.
                if type(exc).__name__ == "OperatorMismatch":
                    import os, sys, traceback
                    traceback.print_exc()
                    print("FATAL: OperatorMismatch -- the seat exits; the arm is VOID", file=sys.stderr, flush=True)
                    os._exit(70)
                raise
            if "search/leaves" in stats:
                self.ms.append((time.perf_counter() - t0) * 1e3)
                self.leaves.append(int(stats["search/leaves"]))
                # PER-DECISION PROBE STATS, and this path never carried them.
                # scripts/ch3_eval.py has aggregated depth2/ tree/ census/ bcts/
                # heuristic/ keys since 2026-09-16; THIS collector only ever kept
                # ms and leaves, so every tree/* diagnostic ever produced off
                # Foul Play was discarded -- including IDEAS 4.9's expert
                # falsifier, which burned a 45-minute screen on 2026-09-19
                # reporting nothing. Same defect class, third occurrence: a dial
                # reaches the WRITER and not the COLLECTOR.
                for k, v in stats.items():
                    if (k.split("/")[0] in ("depth2", "tree", "census", "bcts",
                                            "heuristic", "disagree")
                            and isinstance(v, (int, float))):
                        self.probe.setdefault(k, []).append(float(v))
        else:
            action = self._agent.act(obs, mask, deterministic=self._det)
        self.decision_ms.append((time.perf_counter() - t_dec) * 1e3)
        self._decision_index += 1
        self._decisions_total += 1
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
    # RESULTS §28 / R6 prep plan ruling #1: the eval-time loop breaker, behind
    # the arm's own key so every banked arm is byte-for-byte what it was. The
    # wrapper delegates `members`/`decisions`/`actor`, so the dim probe and the
    # ensemble counters below see through it.
    loop_breaker = bool(arm.get("loop_breaker"))
    if loop_breaker:
        assert arm["kind"] in ("greedy_seat", "ensemble_seat"), (
            f"{arm_name}: loop_breaker applies to the greedy and ensemble seats only")
        from rl.common.loop_breaker import LoopBreakingPolicy

        agent = LoopBreakingPolicy(agent, threshold=int(arm.get("loop_breaker_threshold", 4)))
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
    searched_ensemble = None
    if arm["kind"] == "native_seat":
        from rl.envs.engine_tables import build_tables
        from rl.search.ensemble import EnsembleAgent
        from rl.search.lop import NativeLOp, lop_from

        members = list(arm["ensemble_members"])
        assert len(members) == len(set(members)), (
            f"{arm_name}: duplicate member in {members} -- a repeated member "
            "silently reweights the log-prob pool")
        assert not seat_lane_defaulted and seat_lane in members, (
            f"{arm_name}: native_seat needs an explicit `seat:` among {members}")
        ens = EnsembleAgent([agent if x == seat_lane else _build_agent(prereg["checkpoints"][x]) for x in members])
        for m in ens.members:
            m.actor.eval(); m.critic.eval()
        tables, tables_fp = build_tables()
        search_agent = NativeLOp(ens, tables, **lop_from(arm.get("lop")))
        agent = ens
        # The width stamp over the COMMITTEE (every member's input width), not the
        # single seat lane the generic stamp above saw (the G2 code review).
        native_dim = _native_dim(agent)
        searched_ensemble = {
            "members": members,
            "member_sha256": [prereg["checkpoints"][x]["sha256"] for x in members],
            "member_steps": [prereg["checkpoints"][x].get("step") for x in members],
            "tables_fingerprint": tables_fp,
        }
    elif arm["kind"] == "search_seat":
        from rl.search.agent import SearchAgent, lane_seed
        from rl.search.matrix import DOSES

        evaluator, eval_provenance = _resolve_evaluator(
            prereg, seat_lane, arm.get("evaluator"), agent
        )
        # `ensemble_members` (2026-09-11): the SEARCHED object becomes the
        # committee -- log-pooled prior, mean opponent model, mean critic at
        # the leaves -- through EnsembleSearchAdapter, the same wiring
        # scripts/ch3_eval.py uses. It is deliberately NOT spelled `lanes`:
        # `lanes` is asserted absent on every non-ensemble_seat kind above,
        # and that assert exists because a `lanes` key on the wrong kind
        # silently rates one lane. A distinct key cannot be confused for it.
        #
        # WHY OFF-FP AT ALL: vs-SH is saturated (we sit 0.82-0.84 against a
        # bot the bare policy already beats 78% of the time), and the two
        # objects share all three checkpoints, so that comparison is mostly
        # measuring their shared component. Off Foul Play we sit near 0.50,
        # where a selector has room -- and the gate is MEASURED to be worth
        # 3x more there: +0.042 vs SH against +0.129 off-FP.
        if arm.get("ensemble_members"):
            from rl.search.ensemble_search import EnsembleSearchAdapter

            members = list(arm["ensemble_members"])
            assert len(members) == len(set(members)), (
                f"{arm_name}: duplicate member in {members} -- a repeated "
                "member silently reweights the log-prob pool"
            )
            assert seat_lane in members, (
                f"{arm_name}: seat {seat_lane} must be one of {members}; the "
                "seat lane is what seeds the decision RNG and pins the sha"
            )
            agent = EnsembleSearchAdapter(
                [agent if x == seat_lane else _build_agent(prereg["checkpoints"][x])
                 for x in members]
            )
            # PROVENANCE, not decoration. Without these the report of a
            # 3-member searched committee is byte-indistinguishable from a
            # single-lane searched arm -- the exact class of defect the
            # seat_lane_defaulted stamp and the MA-10 budget note exist for.
            searched_ensemble = {
                "members": members,
                "member_sha256": [prereg["checkpoints"][x]["sha256"] for x in members],
                "member_steps": [prereg["checkpoints"][x].get("step") for x in members],
            }
        # `leaf_encoding` (optional, 2026-09-10 — docs/search_relook/DET_BLIND.md):
        # absent = the as-is leaf encoding every banked FS/FE arm ran.
        # `margin_delta` (optional, 2026-09-10 — MARGIN_SELECTOR.md): absent =
        # the hard argmax (matrix.py D4) every banked FS/FE arm ran. Both
        # realized values are stamped into the report below either way.
        search_agent = SearchAgent(
            agent, DOSES[arm["dose"]],
            checkpoint_seed=lane_seed(seat_lane),
            evaluator=evaluator,
            leaf_encoding=arm.get("leaf_encoding"),
            margin_delta=arm.get("margin_delta"),
            # `depth2` (optional, wired 2026-09-16 for JOURNEY 11.5): a dict
            # {our_k, cap, plies} turns on matrix.py's SELECTIVE extra ply.
            # Absent = the depth-1 matrix every banked FP arm ran. The
            # realized dict AND the fired-counters are stamped into the report
            # below either way -- an unfired extra ply must never again be
            # indistinguishable from an ineffective one.
            depth2=arm.get("depth2"),
            # `disagree` (optional, wired 2026-09-18 for IDEAS 8.5): a dict
            # {metric, threshold} spends the search budget only on the
            # decisions the committee is split on. Absent = search every
            # decision, which is what every banked arm did.
            disagree=arm.get("disagree"),
            # `calibration` (optional, wired 2026-09-19 for IDEAS 2.13): a path
            # to a luck-ceiling rows JSONL, or an inline {xs, ys} fit. Absent =
            # the raw critic, which is what every banked arm ran.
            calibration=arm.get("calibration"),
            # `tree` (optional, wired 2026-09-16 alongside depth2): swaps the
            # depth-1 matrix for rl/search/tree.py -- decoupled UCT with OUR
            # policy as the PUCT prior and OUR critic at the leaves, mean
            # simulation depth ~3. It was already wired in ch3_eval.py (vs SH)
            # and missing here, so the one vehicle
            # docs/search_relook/DEPTH_IS_THE_UNTESTED_AXIS.md calls "the actual
            # target" had never been runnable on the axis where a selector has
            # leverage -- the SAME plumbing gap that kept depth2 off this path.
            # Wiring it costs nothing and does not run it: an MCTS arm needs its
            # own pre-reg, and configs/eval/depth2_r5.yaml deliberately does NOT
            # test this vehicle.
            tree=arm.get("tree"),
            # ...and the other two vehicles ch3_eval.py already forwards and
            # this caller dropped: `mcts` (poke_engine's OWN MCTS on our
            # determinized roots -- the reference marker, no learned policy in
            # the loop) and `bcts`. Same defect, found by the same test.
            mcts=arm.get("mcts"),
            bcts=arm.get("bcts"),
            heuristic=arm.get("heuristic"),
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
        "loop_breaker": loop_breaker,
        # None on a single-lane arm; the members + shas on a searched committee.
        "searched_ensemble": searched_ensemble,
        "seat_native_dim": native_dim,
        "declared_search_time_ms": arm.get("search_time_ms"),
        # 2026-08-27: proves the deadlock fix did not buy concurrency. The
        # queue has slack 2 so a duplicate battle-init cannot block, but play
        # must remain strictly serial; if this is ever > 1 the arm is NOT
        # commensurable with the k=1 comparator wave and must be re-run.
        "max_concurrent_live_battles": seat.max_concurrent_live,
        # the MAX above answers "did it ever happen"; these answer "how much"
        "concurrent_decisions": seat.concurrent_decisions,
        # WRONG UNTIL 2026-09-19. The numerator accumulates across the ARM while
        # `_decision_index` RESETS at every battle boundary, so this divided an
        # arm-level count by the LAST BATTLE's decision count. Four of the seven
        # non-zero banked values exceed 1.0 -- impossible for a fraction of
        # decisions -- and `scripts/depth2_r5_readout.py` hard-VOIDs any arm
        # above 0.01, so the counter written to settle "was the concurrency a
        # transient?" would have false-VOIDed every arm it was meant to clear
        # (hd1 reads 4.0851 against a true 0.00195, a factor of 2100).
        # BANKED VALUES BEFORE THIS DATE ARE NOT RATES; recompute as
        # concurrent_decisions / (search/decisions) where that field exists.
        "concurrent_decision_rate": (
            seat.concurrent_decisions / max(seat._decisions_total, 1)),
        "concurrent_decisions_denominator": seat._decisions_total,
    }
    # THE SEAT'S OWN PACE, every arm kind (JOURNEY 14: decisions/sec for BOTH
    # arms). `seat/*` is our own compute per decision; `arm/decisions_per_wall_sec`
    # is dominated by Foul Play's think time and the server, labelled as such.
    dms = np.array(seat.decision_ms) if seat.decision_ms else np.array([0.0])
    report.update({
        "seat/decision_ms_mean": float(dms.mean()),
        "seat/decision_ms_p50": float(np.percentile(dms, 50)),
        "seat/decision_ms_p99": float(np.percentile(dms, 99)),
        "seat/decisions_per_sec": (1000.0 / float(dms.mean())) if dms.mean() > 0 else None,
        "arm/decisions_per_wall_sec": (seat._decisions_total / elapsed) if elapsed > 0 else None,
    })
    # WHICH `rl` THIS PROCESS RAN (the G2 design review): two envs import two
    # different trees, and a launch sha of the CWD would not say which.
    import pathlib
    import rl as _rl
    _rl_root = pathlib.Path(_rl.__file__).resolve().parents[1]
    report["rl_package"] = str(pathlib.Path(_rl.__file__).resolve().parent)
    try:
        import subprocess as _sp
        report["rl_git_sha"] = _sp.run(["git", "-C", str(_rl_root), "rev-parse", "HEAD"], capture_output=True,
                                       text=True, check=True).stdout.strip()
        report["rl_git_dirty"] = bool(_sp.run(["git", "-C", str(_rl_root), "status", "--porcelain", "--untracked-files=no"],
                                              capture_output=True, text=True, check=True).stdout.strip())
    except (OSError, _sp.CalledProcessError):
        report["rl_git_sha"] = None
    if arm["kind"] == "native_seat":
        # The L-op's own counters: the override rate beside every win rate (the
        # landmine), the refusal families, the dose, decisions/sec (JOURNEY 14's
        # exit condition names it in every quote).
        ms = np.array(seat.ms) if seat.ms else np.array([0.0])
        report.update(search_agent.report())
        report.update({
            "search/ms_mean": float(ms.mean()),
            "search/ms_p99": float(np.percentile(ms, 99)),
            "search/searched_decisions": len(seat.ms),
        })
    elif search_agent is not None:
        ms = np.array(seat.ms) if seat.ms else np.array([0.0])
        lv = np.array(seat.leaves) if seat.leaves else np.array([0])
        dec = search_agent.counters["search/decisions"]
        # IDEAS 8.5: a decision the DISAGREEMENT GATE declined is not searched
        # either, and it is not a placeholder skip. Folding it in here is not
        # cosmetic -- every rate below divides by `dec - skips`, so a gated arm
        # would otherwise report `depth2/fired_rate` and `override_rate` against
        # a denominator that counts decisions the search never saw, and a
        # perfectly healthy gated arm would read VOID.
        skips = (search_agent.counters["search/placeholder_skips"]
                 + (search_agent.counters["disagree/eligible"]
                    - search_agent.counters["disagree/searched"]))
        overrides = search_agent.counters["search/overrides"]
        report.update({
            # THE DOSE, stamped 2026-09-17. It never was, so a claim like
            # "dose is matched and it is M" -- which is the entire basis of the
            # JOURNEY 11.5 comparison -- was UNVERIFIABLE from the artifact.
            # ch3_eval.py has stamped it since R2; this path did not, and the
            # R0 gate that reads it therefore passed silently on absence. The
            # leaves count is the indirect check and it is right beside it.
            "search_dose": arm["dose"],
            "search_leaf_encoding": search_agent.leaf_encoding or "as_is",
            "search_margin_delta": search_agent.margin_delta,
            "search/ms_mean": float(ms.mean()),
            "search/leaves_mean": float(lv.mean()),
            "search/searched_decisions": len(seat.ms),
            "search/decisions": dec,
            "search/placeholder_skips": skips,
            "search/flips": search_agent.counters["search/flips"],
            "search/overrides": overrides,
            # null with the gate off — see scripts/ch3_eval.py::_merge
            "search/override_rate": (
                overrides / max(dec - skips, 1)
                if search_agent.margin_delta is not None else None
            ),
        })
        # DEPTH PROVENANCE. `search_depth2` is the realized dial (null = the
        # depth-1 matrix). The three counters below are what make an arm
        # gradeable: `depth2/fired_rate` near 0 means the extra ply NEVER RAN
        # and the arm is VOID, whatever its win rate says. 2026-09-11's D2
        # probe is the precedent and the reason this is stamped rather than
        # inferred.
        d2 = search_agent._depth2
        report["search_depth2"] = d2
        # IDEAS 8.5 PROVENANCE. `search_disagree` is the realized dial; the
        # rate beside it is what makes a gated arm gradeable. A search_rate of
        # 1.0 is a UNIFORM-DOSE arm wearing a gated label and a 0.0 is greedy,
        # and neither is distinguishable from the win rate alone.
        report["search_disagree"] = search_agent._disagree
        # THE PROBE STATS, averaged over the decisions that produced them. Their
        # absence is what made IDEAS 4.9's falsifier unreadable off Foul Play.
        for k, vals in sorted(seat.probe.items()):
            if vals:
                report[k] = float(sum(vals) / len(vals))
        report["probe/decisions_with_stats"] = (
            len(next(iter(seat.probe.values()))) if seat.probe else 0)
        # IDEAS 2.13 PROVENANCE. `calib/leaves` at 0 means the dial never
        # touched a leaf whatever the config asked for, and `calib/mean_shift`
        # says how far it moved them -- an arm where both are ~0 is a RAW-critic
        # arm wearing a calibrated label.
        cal = search_agent._calibration
        report["search_calibration"] = (
            None if cal is None else {"knots": len(cal.xs), **cal.fit_meta})
        if cal is not None:
            leaves = search_agent.counters["calib/leaves"]
            report["calib/leaves"] = leaves
            report["calib/mean_shift"] = (
                search_agent.counters["calib/shift_sum"] / max(leaves, 1))
        if search_agent._disagree is not None:
            elig = search_agent.counters["disagree/eligible"]
            srch = search_agent.counters["disagree/searched"]
            report.update({
                "disagree/eligible": elig,
                "disagree/searched": srch,
                "disagree/search_rate": srch / max(elig, 1),
                "disagree/score_mean":
                    search_agent.counters["disagree/score_sum"] / max(elig, 1),
                "disagree/score_mean_searched": (
                    search_agent.counters["disagree/score_sum_searched"]
                    / srch if srch else None),
            })
        report["search_tree"] = search_agent._tree
        report["search_mcts"] = search_agent._mcts
        report["search_bcts"] = search_agent._bcts
        report["search_heuristic"] = search_agent._heuristic
        if search_agent._heuristic is not None:
            hd = search_agent.counters["heuristic/decisions"]
            report["heuristic/decisions"] = hd
            report["heuristic/fired_rate"] = hd / max(dec - skips, 1)
            report["heuristic/leaves_per_decision"] = (
                search_agent.counters["heuristic/leaves_scored"] / max(hd, 1))
        if d2 is not None:
            searched = max(dec - skips, 1)
            report.update({
                "depth2/decisions_with_ply": search_agent.counters["depth2/decisions_with_ply"],
                "depth2/fired_rate": search_agent.counters["depth2/decisions_with_ply"] / searched,
                "depth2/grandchildren_total": search_agent.counters["depth2/grandchildren"],
                "depth2/grandchildren_per_decision": (
                    search_agent.counters["depth2/grandchildren"] / searched),
                "depth2/leaves_deepened_total": search_agent.counters["depth2/leaves_deepened"],
                "depth2/mean_shift": (
                    search_agent.counters["depth2/shift_sum"]
                    / max(search_agent.counters["depth2/decisions_with_ply"], 1)),
                # IDEAS 2.10. `opp_replies_mean` is the REALIZED branch factor
                # on the opponent's side -- 1.0 means the minimax back-up never
                # fired whatever `opp_k` the config asked for -- and
                # `minimax_drop` is how much the min over its answers moved the
                # backed-up value. A number from an arm where both are ~0 is a
                # depth-1 number wearing a depth-2 label.
                "depth2/opp_replies_mean": (
                    search_agent.counters["depth2/opp_replies_sum"]
                    / max(search_agent.counters["depth2/decisions_with_ply"], 1)),
                "depth2/minimax_drop": (
                    search_agent.counters["depth2/drop_sum"]
                    / max(search_agent.counters["depth2/decisions_with_ply"], 1)),
                "depth2/leaves_unexpanded_total":
                    search_agent.counters["depth2/leaves_unexpanded"],
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
    if loop_breaker:
        report.update(agent.counters)   # loop/decisions, fired, fired_rate, ...
    return report


def _git_sha() -> str:
    import subprocess
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                              text=True).stdout.strip()
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:
        return ""


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

    # `launch_git_sha` DID NOT MEAN WHAT ITS NAME SAYS until 2026-09-18: it was
    # read AFTER the battles, so it recorded the tree state when the arm
    # FINISHED, and SESSION_LOGS 2026-09-0x documents the opposite belief ("the
    # seat stamps launch_git_sha per arm at ITS start"). Caught when the tree
    # block's TV arm -- launched 10:45Z -- came back stamped with a commit made
    # at 11:40Z. It is now read HERE, before a single battle, and the finish-time
    # value is kept beside it so an arm that spans a commit is visible rather
    # than merely mis-labelled. ARMS WRITTEN BEFORE THIS CHANGE CARRY A
    # FINISH-TIME VALUE UNDER THE LAUNCH NAME (docs/CLEANUP.md L5).
    launch_sha = _git_sha()

    result = asyncio.run(run(prereg, args.arm, battles, tag))

    # CH4 R1 G8: era/provenance stamp — launch sha, the pre-reg's content
    # hash (the thresholds cannot drift between launch and grading without
    # a trace), encoder state, process obs width.
    import hashlib

    from rl.envs.showdown import OBS_DIM
    result["launch_git_sha"] = launch_sha
    result["finish_git_sha"] = _git_sha()
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
