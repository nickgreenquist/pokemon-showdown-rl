"""Play the REAL Pokémon Showdown ladder (play.pokemonshowdown.com).

    python scripts/ladder.py --prereg configs/eval/ladder_r1.yaml --arm L1 --battles 20
    python scripts/ladder.py --prereg configs/eval/ladder_r1.yaml --arm L1 --battles 20 --local-smoke

Everything else in this repo talks to `localhost:8000`; this is the one path
that goes out. Read the disclosures below before running it in anger.

CREDENTIALS NEVER LIVE IN THE CONFIG. The account password is read from the
`PS_PASSWORD` env var. The USERNAME comes from the arm's `display_name` in
the pre-reg; `PS_USERNAME` may only CONFIRM it and the run aborts if the two
disagree (see `_resolve_display_name`) — an env var must never silently
redirect a rated run onto another account. CLAUDE.md's "keep secrets out of committed files" is a
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
# THE ENDPOINT THAT MAKES THE PRIMARY READ EXIST. See `profile_snapshot`.
PROFILE_API = "https://pokemonshowdown.com/users/{userid}.json"
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


def _get_json(url: str) -> dict:
    """One GET, returning either the parsed body or an `ok: False` marker.

    A User-Agent is REQUIRED: pokemonshowdown.com 403s urllib's default
    `Python-urllib/3.x`. Measured 2026-08-25 — curl 200, default UA 403,
    browser-ish UA 200 — after the first 20-battle run completed with EVERY
    board call silently failing.

    `ok: False` is what keeps a FETCH FAILURE from impersonating a real
    negative. The first version returned a dict with no `listed` key, and the
    stopping rule's `not snap.get("listed")` read that as a genuine "not on
    the list" — so a dead endpoint reported the reassuring, specific and
    WRONG message "not yet on the top-500 list", and the rule could never
    fire.
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": "pokemon-showdown-rl research bot"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as fh:
            return {"ok": True, "body": json.load(fh)}
    except Exception as exc:  # noqa: BLE001 — a scrape must never kill a run
        return {"ok": False, "error": repr(exc)}


def profile_snapshot(fmt: str, userid: str) -> dict:
    """OUR rating, off the USER PROFILE — the source that actually has it.

    ADDED 2026-08-27, and it fixes a two-day error that cost LADDER R1 its
    pre-registered primary read. `ladder_snapshot` below polls the TOP-500
    LEADERBOARD, which by construction contains only listed accounts; R1
    finished unlisted, so the tooling reported "GXE and Glicko are
    UNMEASURED" and `stopped_by_rule: false`. **Both were false.** The
    profile carries GXE and Glicko-1 for ANY RATED ACCOUNT, listed or not.
    Being unlisted is a statement about the BOARD, never about whether a
    rating exists. R1's numbers were on a public page the whole time.

    Verified against R1's own account 2026-08-27 —
    `https://pokemonshowdown.com/users/nickgen1rbrlbot.json` returns
    `{"ratings": {"gen1randombattle": {"elo": 1292.25, "gxe": 59.6,
      "rpr": 1573.04, "rprd": 26.57, "w": 95, "l": 105}}}` — which reproduces
    every corrected R1 number (final Elo 1292, GXE 59.6%, Glicko-1 1573+/-27,
    95-105 over 200) and shows the stopping rule was SATISFIED at rd 26.6,
    not merely un-evaluated.

    FIELD NAMES DIFFER FROM THE BOARD ROW and that is the whole trap: the
    profile spells Glicko-1 `rpr`/`rprd` where the leaderboard spells it
    `r`/`rd`. We normalise to the board's names so one stopping rule reads
    either source. `t` (ties) is absent from the profile; it stays None
    rather than being invented as 0.

    THREE OUTCOMES, kept distinct because collapsing them is the original
    bug in a new costume:
      ok=False              -> fetch failed; we know NOTHING. Never a pass.
      ok=True, rated=False  -> account reachable, no rated games in this
                               format yet. A real negative, not an error.
      ok=True, rated=True   -> the rating fields are present and usable.
    """
    url = PROFILE_API.format(userid=userid)
    got = _get_json(url)
    if not got["ok"]:
        return {"ok": False, "error": got["error"], "url": url}
    body = got["body"] or {}
    row = (body.get("ratings") or {}).get(fmt)
    out = {"ok": True, "url": url, "rated": bool(row),
           "registertime": body.get("registertime")}
    if row:
        out.update({
            "gxe": row.get("gxe"),
            "r": row.get("rpr"),      # Glicko-1 rating
            "rd": row.get("rprd"),    # Glicko-1 deviation — the stopping signal
            "elo": row.get("elo"),
            "w": row.get("w"),
            "l": row.get("l"),
            "t": row.get("t"),        # absent on the profile; stays None
        })
    return out


def board_snapshot(fmt: str, userid: str) -> dict:
    """Our row off the PUBLIC top-500 leaderboard. Unauthenticated GET.

    THIS IS NOT THE SOURCE OF OUR RATING — `profile_snapshot` is. What only
    the board can tell us is whether we are LISTED and where the admission
    line sits, and both are descriptive. Absent from the list is NOT an
    error: admission is an ELO threshold (~1357 on 2026-08-25), so an
    unlisted run is the normal case for this project.
    """
    url = LADDER_API.format(fmt=fmt)
    got = _get_json(url)
    if not got["ok"]:
        return {"ok": False, "error": got["error"], "url": url}
    board = got["body"] or {}
    rows = board.get("toplist", [])
    mine = next((r for r in rows if r.get("userid") == userid), None)
    out = {"ok": True, "url": url, "listed": mine is not None,
           "toplist_size": len(rows)}
    if rows:
        # The toplist is ELO-RANKED (verified 2026-08-25: elo is monotone
        # descending, gxe and glicko are not). So admission is an ELO
        # threshold; the minimum GXE on the list is just whoever has the
        # lowest GXE among those admitted and is NOT a cutoff.
        out["cutoff_elo"] = rows[-1].get("elo")
        out["min_listed_gxe"] = rows[-1].get("gxe")
    if mine:
        out.update(
            {k: mine.get(k) for k in ("gxe", "r", "rd", "elo", "w", "l", "t")}
        )
    return out


def _resolve_display_name(arm: dict, arm_name: str) -> str:
    """The PRE-REGISTERED name wins. `PS_USERNAME` may confirm it, never
    silently replace it.

    THE BUG THIS CLOSES, added 2026-08-27 after both design reviewers flagged
    it independently. The line used to be:

        display_name = os.environ.get("PS_USERNAME") or arm["display_name"]

    so an env var SILENTLY OVERRODE the config. A stale
    `PS_USERNAME=<previous run's account>` left in a shell, a `.env`, or a
    shell profile would quietly ladder the new arm on the OLD account —
    burning rated games on it and contaminating a published rating that
    cannot be re-measured. The only symptom was one line of startup output.

    THE FIX IS THE ONE THAT MAKES SIMPLE, SIMILAR NAMES SAFE. The alternative
    on offer was a naming convention — pick names far apart in edit distance
    so a mix-up is visible. That is not a mechanism, it is a habit, and it
    fails exactly when someone is tired. Making the config authoritative means
    `run2` / `run3` style names are fine forever: the runner cannot be pointed
    somewhere the pre-registration did not name.

    RESOLUTION ORDER:
      * `PS_USERNAME` unset            -> use the arm's `display_name`.
      * `PS_USERNAME` matches (by USERID, so punctuation and case are free)
                                       -> use it, and say so.
      * `PS_USERNAME` disagrees        -> **SystemExit.** Never the env var.
    Comparison is on `to_id`, not on the raw string, because PS authenticates
    on the userid: `nick_gen1rb_rl_bot2` and `nickgen1rbrlbot2` are the SAME
    account and disagreeing about punctuation is not an error worth aborting
    a 16-hour run over.
    """
    declared = arm.get("display_name")
    if not declared:
        raise SystemExit(f"arm {arm_name!r} declares no display_name")
    env_name = os.environ.get("PS_USERNAME")
    if not env_name:
        return declared
    if to_id(env_name) == to_id(declared):
        if env_name != declared:
            print(f"  PS_USERNAME {env_name!r} confirms arm's "
                  f"{declared!r} (same userid {to_id(declared)!r})")
        return declared
    raise SystemExit(
        f"PS_USERNAME={env_name!r} (userid {to_id(env_name)!r}) DISAGREES with "
        f"arm {arm_name!r}'s pre-registered display_name {declared!r} (userid "
        f"{to_id(declared)!r}).\n"
        "REFUSING TO RUN. The pre-registration names the account; an "
        "environment variable does not get to redirect it silently — that is "
        "how a run lands on the wrong account and contaminates a rating that "
        "cannot be re-measured.\n"
        "Fix whichever is wrong: unset/correct PS_USERNAME, or change the "
        "arm's display_name in the pre-reg (and re-ratify it)."
    )


def ladder_snapshot(fmt: str, userid: str) -> dict:
    """Both sources, merged, with the PROFILE authoritative for our rating.

    Order matters: the board row is written first so that when we are listed
    the two agree, then the profile overwrites — the profile is the account's
    own record and exists in every case, while the board row exists only
    while we hold a top-500 slot. `listed` and `cutoff_elo` still come from
    the board, because only the board knows them.

    `ok` means "at least one source answered", so a single dead endpoint
    does not blind the run. The per-source flags `board_ok` / `profile_ok`
    are what a reader should check before trusting any individual field.
    """
    board = board_snapshot(fmt, userid)
    prof = profile_snapshot(fmt, userid)

    out = {"ok": bool(board.get("ok") or prof.get("ok")),
           "board_ok": bool(board.get("ok")),
           "profile_ok": bool(prof.get("ok"))}
    if board.get("ok"):
        out.update({k: v for k, v in board.items() if k != "ok"})
    else:
        out["board_error"] = board.get("error")
        out["listed"] = None
    if prof.get("ok"):
        out["profile_url"] = prof.get("url")
        out["rated"] = prof.get("rated")
        # Only real values overwrite the board row — an unrated profile must
        # not blank out a board row we successfully read.
        for k in ("gxe", "r", "rd", "elo", "w", "l", "t"):
            if prof.get(k) is not None:
                out[k] = prof[k]
        out["rating_source"] = "profile" if prof.get("rated") else None
    else:
        out["profile_error"] = prof.get("error")
    if out.get("rating_source") is None and board.get("listed"):
        out["rating_source"] = "leaderboard"
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

    SUPERSEDED 2026-08-27, and the superseded text is kept because the error
    was reasoned, not careless. This function used to read:

        "Being UNLISTED is not a pass — an unlisted account has no published
         rd at all, so we cannot know it converged. Keep playing."

    **The premise is false.** An unlisted account HAS a published rd; it is
    on the USER PROFILE (`profile_snapshot`), not on the top-500 leaderboard
    this function was handed. LADDER R1 therefore ran to its n floor and
    reported `stopped_by_rule: false` while sitting at **rd 26.6, n 200** —
    the rule had been satisfied and nothing could see it. The `listed` gate
    is REMOVED. What the rule needs is an rd from a source that answered,
    and `listed` is descriptive from here on.
    """
    rule = cfg.get("stopping_rule") or {}
    rd_max = rule.get("glicko_rd_max")
    n_min = rule.get("min_battles")
    if rd_max is None or n_min is None:
        return False, "no stopping rule configured"
    if n < n_min:
        return False, f"n {n} < {n_min}"
    if not snap.get("ok"):
        err = snap.get("error") or snap.get("profile_error") or snap.get("board_error")
        return False, (f"BOTH ENDPOINTS UNREACHABLE ({err}) — cannot "
                       "evaluate the stopping rule. This is NOT 'unrated'.")
    rd = snap.get("rd")
    if rd is None:
        # Distinguish the two ways rd can be missing, because they call for
        # opposite responses: an unrated account keeps playing, a dead
        # profile endpoint is an ops problem the operator must see.
        if snap.get("profile_ok") and snap.get("rated") is False:
            return False, (f"n {n} >= {n_min} but the account has no rated "
                           "games in this format yet")
        if not snap.get("profile_ok"):
            return False, (f"n {n} >= {n_min} but the PROFILE is unreachable "
                           f"({snap.get('profile_error')}) and the board row "
                           "carries no rd — cannot evaluate the rule")
        return False, f"n {n} >= {n_min} but no rd from either source"
    if rd > rd_max:
        return False, f"n {n} >= {n_min}, rd {rd:.1f} > {rd_max}"
    src_name = snap.get("rating_source") or "unknown source"
    return True, f"n {n} >= {n_min} AND rd {rd:.1f} <= {rd_max} (via {src_name})"


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
    display_name = _resolve_display_name(arm, arm_name)
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
    # Print whenever a rating EXISTS — gating this on `listed` is the same
    # leaderboard-vs-profile error that cost R1 its primary read.
    if before.get("rd") is not None:
        print(f"  starting rating ({before.get('rating_source')}): "
              f"GXE {before.get('gxe')} "
              f"Glicko-1 {before['r']:.0f} +/- {before['rd']:.0f} "
              f"Elo {before.get('elo'):.0f} "
              f"[listed={before.get('listed')}]")
    elif before.get("profile_ok") and before.get("rated") is False:
        print("  starting rating: none yet — account has no rated games in "
              f"{BATTLE_FORMAT}")

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
