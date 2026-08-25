"""Play the REAL Pokémon Showdown ladder (play.pokemonshowdown.com).

    python scripts/ladder.py --prereg configs/eval/ladder_r1.yaml --arm L1 --battles 20
    python scripts/ladder.py --prereg configs/eval/ladder_r1.yaml --arm L1 --battles 20 --local-smoke

Everything else in this repo talks to `localhost:8000`; this is the one path
that goes out. Read the disclosures below before running it in anger.

CREDENTIALS NEVER LIVE IN THE CONFIG. The account password is read from the
`PS_PASSWORD` env var (username from `PS_USERNAME`, or the arm's
`display_name`). CLAUDE.md's "keep secrets out of committed files" is a
standing obligation and the pre-reg is a committed file.

THE ACCOUNT MUST BE REGISTERED FIRST, BY HAND. poke-env can log in but
cannot register: open play.pokemonshowdown.com, pick the name, `/register`.
An unregistered name can still ladder, but anyone may take it and the rating
travels with whoever holds it — useless as a published result.

USERNAME LIMIT, measured against the vendored server (`server/users.ts:745`,
`sim/dex-data.ts:22`): the cap is **18 characters on the USERID**, and the
userid is the display name lowercased with every non-alphanumeric stripped.
So underscores are free in the display name but do not count against the
limit — `nick_gen1rb_rl_bot` is 18 visible characters and a 15-character
userid, while `nick_gen1randbats_rl_bot` is a 21-character userid and is
REFUSED with `|nametaken|`. `_check_username` enforces this before we
connect, because the failure mode otherwise looks like a deadlock.

WHY THE LOOP IS `ladder(1)` AND NOT `ladder(n)`: poke-env's `_ladder` queues
n games back-to-back with no seam. One battle per call gives us the seam we
need for (a) pacing between games — this is a thin ladder and a bot that
queues instantly forever is the rude version of this experiment, (b) an
append-per-battle JSONL so a crash on battle 300 costs one battle and not
300, and (c) a rating snapshot cadence. The cost is one extra round-trip per
battle, which is nothing next to a ~30-turn game.

LANDMINES INHERITED FROM THE FOUL-PLAY RUNNER (CLAUDE.md), all of which
apply harder here because the opponent is a stranger and the seat is public:
  * `|nametaken|` must abort FAST and loudly, never retry — a retry loop
    against a held username is the 3.6-hour zero-progress failure.
  * Two independent tallies must agree: poke-env's own `n_finished_battles`
    against our JSONL line count. A subtraction is not a check.
  * A wall-clock ETA is not progress. `--battles` is a request, not a
    promise; the JSONL is the truth.

ROBUSTNESS OVER STRICTNESS, and this is a deliberate DEVIATION from
`scripts/ch3_fp_h2h.py`'s seat: that seat asserts on a mask desync or a
`wait` state because a controlled eval should die rather than log a wrong
number. Here an uncaught exception forfeits a live rated game against a
human and drops the account mid-ladder, so `choose_move` falls back to
poke-env's default order and COUNTS the fallback (`decision_errors`). A run
whose `decision_errors` is non-zero is disclosed, not silently used.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import torch
import yaml

from poke_env.data import GenData
from poke_env.player import Player, SimpleHeuristicsPlayer
from poke_env.ps_client import AccountConfiguration, ServerConfiguration
from poke_env.ps_client.server_configuration import ShowdownServerConfiguration

BATTLE_FORMAT = "gen1randombattle"
LADDER_API = "https://pokemonshowdown.com/ladder/{fmt}.json"
POLICY_KINDS = ("greedy", "ensemble", "search")
USERID_MAX = 18


def _set_encoder_flags() -> None:
    """The encoder flags are read at IMPORT of rl.envs.showdown, so they must
    be set before the first rl import — which is why every runner in scripts/
    exports them (ch3_r4_fp_runner.sh:50). This entry point is run BY HAND
    across days, and a forgotten export would not fail loudly: it would build
    a different-width encoder and put a policy that is not the one we
    pre-registered in front of real opponents. `_load_showdown_agent` still
    refuses any checkpoint it cannot map exactly, so this is belt AND braces.

    Called from main(), NOT at import: importing this module must not mutate
    the process environment, or it silently reconfigures every other test in
    the same pytest process (measured — it broke 10 tests in test_zeroinfo).
    """
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")


def to_id(name: str) -> str:
    """The server's own `toID` (sim/dex-data.ts:22), reimplemented."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _check_username(display_name: str) -> str:
    uid = to_id(display_name)
    if not uid:
        raise SystemExit(f"username {display_name!r} has an empty userid")
    if len(uid) > USERID_MAX:
        raise SystemExit(
            f"username {display_name!r} -> userid {uid!r} is {len(uid)} chars; "
            f"the server refuses anything over {USERID_MAX} "
            "(server/users.ts:745). Shorten it — underscores are stripped "
            "from the userid, so they cost nothing."
        )
    return uid


def ladder_snapshot(fmt: str, userid: str) -> dict:
    """Our row off the PUBLIC top-500 leaderboard. Unauthenticated GET; no
    login needed, and it is the only source of GXE (the battle stream carries
    Elo only). Absent from the list is NOT an error — the 500th place cutoff
    was GXE 58.8 on 2026-08-25, so an early run is legitimately unlisted."""
    url = LADDER_API.format(fmt=fmt)
    try:
        with urllib.request.urlopen(url, timeout=20) as fh:
            board = json.load(fh)
    except Exception as exc:  # noqa: BLE001 — a scrape must never kill a run
        return {"error": repr(exc), "url": url}
    rows = board.get("toplist", [])
    mine = next((r for r in rows if r.get("userid") == userid), None)
    out = {"url": url, "listed": mine is not None, "toplist_size": len(rows)}
    if rows:
        out["cutoff_gxe"] = rows[-1].get("gxe")
    if mine:
        out.update(
            {k: mine.get(k) for k in ("gxe", "r", "rd", "elo", "w", "l", "t")}
        )
    return out


def _build_policy(prereg: dict, arm: dict):
    """Returns (act_fn, provenance). Every kind exposes the SAME call —
    act(battle, obs, mask, battle_index, decision_index) -> int — so the
    policy choice is genuinely a config line and the runner never branches
    on it again."""
    sys.path.insert(0, str(Path(__file__).parent))
    from eval_checkpoint import _load_showdown_agent

    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config

    import hashlib

    def _load(lane: str):
        spec = prereg["checkpoints"][lane]
        h = hashlib.sha256()
        with open(spec["path"], "rb") as fh:
            for block in iter(lambda: fh.read(1 << 20), b""):
                h.update(block)
        got = h.hexdigest()
        assert got == spec["sha256"], (
            f"sha256 mismatch on {spec['path']}: {got} != {spec['sha256']}"
        )
        ckpt = load_checkpoint(spec["path"])
        cfg = Config(**ckpt["config"])
        torch.set_num_threads(1)
        return _load_showdown_agent(ckpt, cfg)

    from rl.envs.showdown import OBS_DIM

    kind = arm["kind"]
    assert kind in POLICY_KINDS, f"kind {kind!r} not in {POLICY_KINDS}"
    prov = {
        "kind": kind,
        "obs_dim": int(OBS_DIM),
        "encoder_v2": os.environ.get("POKEMON_RL_ENCODER_V2"),
        "encoder_ids": os.environ.get("POKEMON_RL_ENCODER_IDS"),
    }

    if kind == "greedy":
        lane = arm["lane"]
        agent = _load(lane)
        prov["lane"] = lane
        prov["sha256"] = prereg["checkpoints"][lane]["sha256"]

        def act(battle, obs, mask, bi, di):
            return agent.act(obs, mask, deterministic=True)

    elif kind == "ensemble":
        from rl.search.ensemble import EnsembleAgent

        lanes = list(arm["lanes"])
        members = [_load(x) for x in lanes]
        agent = EnsembleAgent(members)
        prov["lanes"] = lanes
        prov["sha256"] = [prereg["checkpoints"][x]["sha256"] for x in lanes]

        def act(battle, obs, mask, bi, di):
            return agent.act(obs, mask, deterministic=True)

    else:  # search
        from rl.search.agent import SearchAgent
        from rl.search.matrix import DOSES

        lane = arm["lane"]
        agent = _load(lane)
        evaluator = None
        if arm.get("evaluator_lanes"):
            from rl.search.ensemble import EnsembleAgent

            ev_lanes = list(arm["evaluator_lanes"])
            assert lane not in ev_lanes, f"own lane {lane} in the evaluator"
            evaluator = {"agents": [_load(x) for x in ev_lanes]}
            prov["evaluator_lanes"] = ev_lanes
        sa = SearchAgent(
            agent,
            DOSES[arm["dose"]],
            checkpoint_seed=int(lane.lstrip("s")),
            evaluator=evaluator,
        )
        prov.update({"lane": lane, "dose": arm["dose"],
                     "sha256": prereg["checkpoints"][lane]["sha256"]})

        def act(battle, obs, mask, bi, di):
            action, _stats = sa.act(battle, obs, mask, bi, di)
            return action

    return act, prov


class LadderPlayer(Player):
    """One seat, playing strangers. See the module docstring on why this is
    forgiving where the Chapter-3 seat is strict."""

    def __init__(self, act_fn, **kwargs):
        super().__init__(
            battle_format=BATTLE_FORMAT, max_concurrent_battles=1, **kwargs
        )
        self._act = act_fn
        self._type_chart = GenData.from_format(BATTLE_FORMAT).type_chart
        self._battle_tag = None
        self._battle_index = -1
        self._decision_index = 0
        self.decision_errors = 0
        self.decision_ms: list[float] = []

    def _fallback(self, exc) -> object:
        self.decision_errors += 1
        print(f"  ! decision fallback ({type(exc).__name__}: {exc})",
              flush=True)
        return self.choose_default_move()

    def choose_move(self, battle):
        from rl.envs.showdown import (
            SinglesEnv,
            _recover_mask_desync,
            embed_battle,
        )

        if battle.battle_tag != self._battle_tag:
            self._battle_tag = battle.battle_tag
            self._battle_index += 1
            self._decision_index = 0
        t0 = time.perf_counter()
        try:
            obs = embed_battle(battle, self._type_chart)
            mask = np.array(SinglesEnv.get_action_mask(battle), dtype=bool)
            action = self._act(
                battle, obs, mask, self._battle_index, self._decision_index
            )
        except Exception as exc:  # noqa: BLE001 — never forfeit a live game
            order = self._fallback(exc)
        else:
            try:
                order = SinglesEnv.action_to_order(np.int64(action), battle)
            except ValueError as exc:
                # A mask desync, and it goes through the SAME recovery every
                # other seat uses so it lands in `mask_desync_total()`. Left
                # to the generic fallback it would be counted only in this
                # object's private tally and would be INVISIBLE to the
                # counter every locked number in this project discloses.
                try:
                    order = _recover_mask_desync(battle, exc)
                except Exception as inner:  # noqa: BLE001
                    # Second desync in one battle: the shared recovery is
                    # capped and RAISES, which is right for an eval that
                    # should die rather than log a wrong number, and wrong
                    # here — raising forfeits a live rated game.
                    order = self._fallback(inner)
            except Exception as exc:  # noqa: BLE001
                order = self._fallback(exc)
        self._decision_index += 1
        self.decision_ms.append((time.perf_counter() - t0) * 1e3)
        return order


def summarize(out_path: Path) -> dict:
    """W/L/T off the JSONL — the file is the truth, here and on resume."""
    rows = [json.loads(line) for line in open(out_path) if line.strip()] \
        if out_path.exists() else []
    wins = sum(1 for r in rows if r["outcome"] == "win")
    ties = sum(1 for r in rows if r["outcome"] == "tie")
    return {
        "battles_total": len(rows),
        "wins": wins,
        "ties": ties,
        "losses": len(rows) - wins - ties,
        # Ties are NON-WINS, as everywhere else in this project (the locked
        # protocol). The ladder itself scores a tie as neither, so this
        # number is ours and is not what GXE reflects — quote both.
        "raw_win_rate": (wins / len(rows)) if rows else None,
    }


def stopping_rule_met(cfg: dict, n: int, snap: dict) -> tuple[bool, str]:
    """The pre-registered stop: Glicko rd <= 40 AND n >= 200.

    This lived only as prose in the pre-reg header until 2026-08-25, i.e. it
    was a human instruction that a tired operator could overrun or undershoot
    by hundreds of public battles. It is code now. Both halves must hold:
    the rd bound is the real signal (rating is path-dependent, so a raw n is
    not evidence of convergence) and the n floor stops a lucky early streak
    from ending the run at rd 39 on 40 games.

    Being UNLISTED is not a pass — an unlisted account has no published rd at
    all, so we cannot know it converged. Keep playing.
    """
    rule = cfg.get("stopping_rule") or {}
    rd_max = rule.get("glicko_rd_max")
    n_min = rule.get("min_battles")
    if rd_max is None or n_min is None:
        return False, "no stopping rule configured"
    if n < n_min:
        return False, f"n {n} < {n_min}"
    if not snap.get("listed"):
        return False, f"n {n} >= {n_min} but not yet on the top-500 list"
    rd = snap.get("rd")
    if rd is None:
        return False, f"n {n} >= {n_min} but no rd on the board row"
    if rd > rd_max:
        return False, f"n {n} >= {n_min}, rd {rd:.1f} > {rd_max}"
    return True, f"n {n} >= {n_min} AND rd {rd:.1f} <= {rd_max}"


def _record(battle, index: int) -> dict:
    return {
        "index": index,
        "tag": battle.battle_tag,
        "opponent": battle.opponent_username,
        "outcome": ("win" if battle.won else "loss")
        if battle.won is not None
        else "tie",
        "turns": battle.turn,
        "rating": battle.rating,
        "opponent_rating": battle.opponent_rating,
        "finished_at": int(time.time()),
    }


async def run(prereg: dict, arm_name: str, battles: int, out_path: Path,
              local_smoke: bool) -> dict:
    from rl.envs.showdown import mask_desync_total

    arm = prereg["arms"][arm_name]
    pacing = prereg.get("pacing", {})
    display_name = os.environ.get("PS_USERNAME") or arm["display_name"]
    userid = _check_username(display_name)
    password = os.environ.get("PS_PASSWORD")

    if local_smoke:
        server = ServerConfiguration(
            "ws://localhost:8000/showdown/websocket",
            "https://play.pokemonshowdown.com/action.php?",
        )
        password = None
        print("LOCAL SMOKE: localhost:8000, no auth, NOT the real ladder")
    else:
        server = ShowdownServerConfiguration
        if not password:
            raise SystemExit(
                "PS_PASSWORD is unset. The real ladder needs a REGISTERED "
                "account; export PS_PASSWORD (and PS_USERNAME if it differs "
                "from the arm's display_name) before running without "
                "--local-smoke."
            )

    # Resume: the JSONL is the truth, not a counter we keep in our heads.
    done = []
    if out_path.exists():
        with open(out_path) as fh:
            done = [json.loads(line) for line in fh if line.strip()]
        print(f"resuming: {len(done)} battles already in {out_path}")
    remaining = battles - len(done)
    hard_cap = int(prereg.get("max_battles_total", 10_000))
    if len(done) + remaining > hard_cap:
        remaining = max(0, hard_cap - len(done))
        print(f"hard cap {hard_cap} clamps this session to {remaining}")
    if remaining <= 0:
        # A no-op is not a gate failure. There is nothing to cross-check when
        # no battle was played, so say so explicitly rather than returning a
        # short dict that main() would read as a missing gate.
        print("nothing to do — target already reached")
        report = {"arm": arm_name, "noop": True, "local_smoke": local_smoke,
                  "tally_jsonl": len(done), "tally_pokeenv": len(done),
                  "gate_tallies_agree": True}
        report.update(summarize(out_path))
        return report

    act_fn, provenance = _build_policy(prereg, arm)
    player = LadderPlayer(
        act_fn,
        account_configuration=AccountConfiguration(display_name, password),
        server_configuration=server,
        start_timer_on_battle_start=bool(pacing.get("start_timer", True)),
        save_replays=str(prereg["save_replays"]) if prereg.get("save_replays")
        else False,
    )

    before = ladder_snapshot(BATTLE_FORMAT, userid) if not local_smoke else {}
    print(f"seat '{display_name}' (userid {userid}) kind={provenance['kind']} "
          f"-> {remaining} battles")
    if before.get("listed"):
        print(f"  starting board position: GXE {before['gxe']} "
              f"Glicko {before['r']:.0f} Elo {before['elo']:.0f}")

    # LOCAL SMOKE ONLY: a ladder queue with one player in it never matches,
    # so the smoke would hang forever and look exactly like a deadlock. Put a
    # second player in the queue and the two find each other — which makes
    # this a real end-to-end exercise of the ladder path (search_ladder_game,
    # match, play, |win|), not just an import check.
    smoke_opponent = None
    if local_smoke:
        smoke_opponent = SimpleHeuristicsPlayer(
            battle_format=BATTLE_FORMAT,
            max_concurrent_battles=1,
            server_configuration=server,
            account_configuration=AccountConfiguration(
                f"smokeopp{os.getpid() % 100000}", None
            ),
        )
        print(f"  smoke opponent '{smoke_opponent.username}' joins the queue")

    sleep_s = float(pacing.get("sleep_between_battles_sec", 5.0))
    seen = {r["tag"] for r in done}
    records = list(done)
    _rule = prereg.get("stopping_rule") or {}
    rule_n_min = int(_rule.get("min_battles", 10 ** 9))
    poll_every = int(pacing.get("board_poll_every_battles", 10))
    stopped_by_rule = False
    started = time.monotonic()
    fh = open(out_path, "a")
    try:
        for i in range(remaining):
            try:
                if smoke_opponent is not None:
                    await asyncio.gather(
                        player.ladder(1), smoke_opponent.ladder(1)
                    )
                else:
                    await player.ladder(1)
            except Exception as exc:  # noqa: BLE001
                msg = repr(exc)
                if "nametaken" in msg.lower():
                    raise SystemExit(
                        f"|nametaken| on {display_name!r} — another process "
                        "holds this username, or it is registered to a "
                        "password we did not send. ABORTING rather than "
                        "retrying (CLAUDE.md: the retry loop is the 3.6-hour "
                        "zero-progress failure)."
                    ) from exc
                print(f"  ! ladder() raised {msg}; stopping this session",
                      flush=True)
                break
            for tag, battle in player.battles.items():
                if battle.finished and tag not in seen:
                    seen.add(tag)
                    rec = _record(battle, len(records))
                    records.append(rec)
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    # Count from OUR records, never from player.battles: on a
                    # resumed session the earlier tags belong to a previous
                    # process and are simply not in this player's dict. Reading
                    # them there is a KeyError on the first battle of day two —
                    # measured, not hypothesised.
                    n = len(records)
                    wins = sum(1 for r in records if r["outcome"] == "win")
                    print(f"  [{n}] {rec['outcome']:5s} vs "
                          f"{rec['opponent']} ({rec['turns']} turns) "
                          f"— running {wins}/{n} = {wins / n:.3f}",
                          flush=True)
            # Evaluate the pre-registered stop. The board is polled every
            # `poll_every` battles once past the n floor, not every battle:
            # this is someone else's server and the rd we are waiting on
            # moves on the scale of tens of games, not one.
            if not local_smoke and len(records) >= rule_n_min:
                if (len(records) - rule_n_min) % poll_every == 0:
                    snap = ladder_snapshot(BATTLE_FORMAT, userid)
                    met, why = stopping_rule_met(prereg, len(records), snap)
                    print(f"  stopping rule: {why}", flush=True)
                    if met:
                        print("  STOPPING RULE MET — ending the run as "
                              "pre-registered.", flush=True)
                        stopped_by_rule = True
                        break
            if i < remaining - 1 and sleep_s:
                await asyncio.sleep(sleep_s)
    finally:
        fh.close()

    elapsed = time.monotonic() - started
    # Two INDEPENDENT tallies, per the Foul-Play G2 lesson. poke-env counts
    # for itself; we count our own file. A subtraction would not be a check.
    jsonl_n = sum(1 for _ in open(out_path))
    pokeenv_n = player.n_finished_battles + len(done)
    after = ladder_snapshot(BATTLE_FORMAT, userid) if not local_smoke else {}

    report = {
        "arm": arm_name,
        "battle_format": BATTLE_FORMAT,
        "display_name": display_name,
        "userid": userid,
        "policy": provenance,
        "battles_this_session": len(records) - len(done),
        "battles_total": jsonl_n,
        "tally_jsonl": jsonl_n,
        "tally_pokeenv": pokeenv_n,
        "gate_tallies_agree": jsonl_n == pokeenv_n,
        "decision_errors": player.decision_errors,
        "mask_desyncs": mask_desync_total(),
        "stopped_by_rule": stopped_by_rule,
        "stopping_rule": prereg.get("stopping_rule"),
        "mean_decision_ms": (
            float(np.mean(player.decision_ms)) if player.decision_ms else None
        ),
        "wall_clock_sec": round(elapsed, 1),
        "ladder_before": before,
        "ladder_after": after,
        "local_smoke": local_smoke,
    }
    report.update(summarize(out_path))
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--prereg", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--battles", type=int, required=True,
                    help="TOTAL target across resumes, not a per-session count")
    ap.add_argument("--out-dir", default="results/ladder")
    ap.add_argument("--local-smoke", action="store_true",
                    help="point at localhost:8000 and skip auth — proves the "
                         "plumbing without touching the real ladder")
    args = ap.parse_args()
    _set_encoder_flags()

    prereg = yaml.safe_load(open(args.prereg))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".smoke" if args.local_smoke else ""
    jsonl = out_dir / f"{args.arm}{suffix}.battles.jsonl"

    report = asyncio.run(run(prereg, args.arm, args.battles, jsonl,
                             args.local_smoke))
    report_path = out_dir / f"{args.arm}{suffix}.report.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"\nbattles -> {jsonl}\nreport  -> {report_path}")
    if report.get("stopped_by_rule"):
        print("\nSTOPPING RULE MET — this run is complete as pre-registered. "
              "Do not add battles to it.")
    if not report.get("gate_tallies_agree"):
        print("\nGATE FAILED: the two tallies disagree — do not use these "
              "numbers until it is explained.")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
