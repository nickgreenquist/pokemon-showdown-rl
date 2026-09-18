#!/usr/bin/env python
"""How much of a gen-1 random battle is decided by LUCK rather than by play?

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/outcome_variance.py --battles 60 --dets 4 --rollouts 8

THE QUESTION, and why it bounds everything else. RESULTS §21 measured that our
critic's `explained_variance` is pinned at ~0.59 no matter how much capacity it
gets: 2.67x the width and 126x the first-layer rank bought ZERO extra EV. §22
and §23 then measured that search buys nothing at depth 2 with EITHER our critic
or Foul Play's heuristic. Both results have the same possible explanation, and
nobody has checked it: **0.59 may simply BE the ceiling.**

Gen-1 random battles carry enormous outcome noise -- critical hits, paralysis
full-stops, freeze, sleep turns, damage rolls, speed ties -- and none of it is
knowable from a position. If a large fraction of the outcome variance is
irreducible, then a critic that explains 0.59 is DONE, no leaf evaluator can be
much better, and every remaining lever belongs on the policy rather than on the
value function or the search.

WHAT IS MEASURED, and against WHOSE information. The relevant ceiling is not
"given the true state" but "given what OUR CRITIC SEES", because that is the
function whose EV we are trying to explain. Our critic reads an observation of
an imperfect-information game, so its irreducible variance has two sources:

    (1) CHANCE  -- the engine's own branch distribution, and
    (2) HIDDEN INFORMATION -- the opponent's unrevealed team and moves.

So each measured position is held at OUR OBSERVATION, and BOTH are varied: `k`
determinizations consistent with that observation (the same RSD sampler the
search uses), `m` rollouts each under the SAME deterministic policy on both
seats. Everything that then differs is noise the critic could not have known.

    Var_within  = E_obs[ Var(outcome | obs) ]        the irreducible part
    Var_total   = Var_obs,rollouts(outcome)          what a critic must explain
    EV_ceiling  = 1 - Var_within / Var_total

And the critic's OWN explained variance is computed on the SAME positions, so
"0.59 against a ceiling of X" is apples to apples rather than a comparison
across two different samples.

COST, AND WHY IT IS SHAPED THIS WAY. Fixed policy on both seats, so a rollout
is ~30 engine steps and ~60 policy forwards. Positions come from real self-play
battles played by the same object, sampled across the whole battle rather than
at a fixed turn. Each position is MEASURED AS IT IS REACHED and its row is
appended to a JSONL immediately, so the job is resume-safe (a death costs one
position, `--rows` picks up where it stopped) and its progress is readable as a
RATE rather than as a wall-clock guess -- CLAUDE.md rule 4's three conditions
for running long analysis agent-side.

WHAT THIS IS NOT. It is not a claim about the ladder, and it is not a win rate.
It is a property of the FORMAT measured through our own encoder and policy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent))

REPO = Path(__file__).resolve().parents[1]


def _terminal(state) -> float | None:
    from rl.search.matrix import _terminal_value
    return _terminal_value(state)


def _swap(state):
    """The same position from side two's point of view.

    Needed because a rollout has to be SELF-PLAY: a weak scripted opponent
    would push outcomes toward one side, collapse their spread and inflate the
    measured ceiling. With the same committee on both seats the game sits near
    even and the spread being measured is the format's, not the opponent's.
    """
    from poke_engine import State

    return State(
        side_one=state.side_two, side_two=state.side_one,
        weather=state.weather, weather_turns_remaining=state.weather_turns_remaining,
        terrain=state.terrain, terrain_turns_remaining=state.terrain_turns_remaining,
        trick_room=state.trick_room,
        trick_room_turns_remaining=state.trick_room_turns_remaining,
    )


def _shadow_mask(sb) -> np.ndarray:
    """The 10-slot action mask for a SHADOW battle.

    `poke_env.SinglesEnv.get_action_mask` cannot be used: a shadow battle is a
    SimpleNamespace shaped for `embed_battle`, not a poke-env Battle, and that
    function reaches for `pokemon.base_species`. The mask is therefore built
    here against EXACTLY the ordering `matrix.our_action_str` decodes --
    switches are `list(team.values())[i]`, moves are
    `list(active_pokemon.moves.keys())[j-6]` -- because a mask that disagrees
    with the decoder silently plays a different move than the one scored.
    """
    mask = np.zeros(10, dtype=bool)
    team = list(sb.team.values())
    active = sb.active_pokemon
    for i, mon in enumerate(team[:6]):
        if mon is not active and not mon.fainted:
            mask[i] = True
    if not sb.force_switch and active is not None:
        for j, mv in enumerate(list(active.moves.values())[:4]):
            if getattr(mv, "current_pp", 0) > 0:
                mask[6 + j] = True
    return mask


def _choose(state, agent, type_chart, turn):
    """The committee's action for SIDE ONE of `state`, as an engine action string."""
    from rl.envs.showdown import embed_battle
    from rl.search.matrix import our_action_str
    from rl.search.shadow_battle import shadow_battle

    sb = shadow_battle(state, turn)
    mask = _shadow_mask(sb)
    if not mask.any():
        return None, None
    obs = embed_battle(sb, type_chart)
    a = agent.act(obs, mask, deterministic=True)
    try:
        return our_action_str(sb, int(a)), obs
    except (IndexError, KeyError, AttributeError):
        return None, obs


def rollout(state, agent, type_chart, rng, turn0: int, max_turns: int = 120) -> float:
    """Play `state` to the end, SAME deterministic committee on both seats.

    The only thing that varies between calls on one state is `rng`, which
    resolves the engine's chance branches; varying the determinization on top
    of that adds the hidden-information half. Everything else is held.
    """
    from poke_engine import generate_instructions

    turn = turn0
    for _ in range(max_turns):
        tv = _terminal(state)
        if tv is not None:
            return tv
        ours, _ = _choose(state, agent, type_chart, turn)
        theirs, _ = _choose(_swap(state), agent, type_chart, turn)
        if ours is None or theirs is None:
            return float("nan")          # unplayable: dropped, never counted as a draw
        try:
            branches = generate_instructions(state, ours, theirs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            return float("nan")
        if not branches:
            return float("nan")
        p = np.array([b.percentage for b in branches], dtype=np.float64)
        if p.sum() <= 0:
            return float("nan")
        state = state.apply_instructions(
            branches[int(rng.choice(len(branches), p=p / p.sum()))])
        turn += 1
    return float("nan")                   # hit the cap: dropped, not scored 0


def load_rows(path) -> tuple[list[dict], set[int]]:
    """Rows already on disk, and the positions they cover.

    A row is one line of JSON appended the moment its position was measured,
    so the LAST line of a killed run can be a partial write. That line is
    dropped rather than allowed to raise -- a resume that crashes on its own
    crash log is not resume-safe (CLAUDE.md rule 4 (ii)).
    """
    from pathlib import Path as _P

    p = _P(path)
    if not p.exists():
        return [], set()
    rows = []
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue                      # torn final line from a kill
        if "ep" in r:
            rows.append(r)
    return rows, {int(r["ep"]) for r in rows}


def _critic_value(agent, obs) -> float:
    """The committee's value for an observation: the MEAN over members.

    `EnsembleAgent` pools the members' POLICIES in log-prob space and exposes no
    value, so the critic side has to be averaged here explicitly rather than
    silently taken from member zero.
    """
    import torch

    members = getattr(agent, "members", [agent])
    with torch.no_grad():
        t = torch.as_tensor(np.asarray(obs, dtype=np.float32)[None])
        return float(np.mean([float(m.critic(t).reshape(-1)[0]) for m in members]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoints", nargs="+", default=[
        "runs/showdown_monster200m_w_s104/ckpt_200000000.pt",
        "runs/showdown_monster200m_w_s112/ckpt_200000012.pt",
        "runs/showdown_monster200m_w_s120/ckpt_200000003.pt"])
    ap.add_argument("--battles", type=int, default=60, help="source battles = positions")
    ap.add_argument("--dets", type=int, default=4, help="determinizations per position")
    ap.add_argument("--rollouts", type=int, default=8, help="rollouts per determinization")
    ap.add_argument("--seed", type=int, default=20260917)
    ap.add_argument("--out", default="results/outcome_variance/variance.json")
    # RESUME SAFETY (CLAUDE.md rule 4 (ii)): every position's row is appended
    # here the moment it is measured, and a restart skips the positions the
    # file already holds. A death costs ONE position, not the whole job. The
    # default sits beside --out so the two travel together.
    ap.add_argument("--rows", default=None,
                    help="JSONL of per-position rows; defaults to <out>.rows.jsonl")
    args = ap.parse_args()
    rows_path = Path(args.rows) if args.rows else Path(str(args.out) + ".rows.jsonl")

    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    from poke_env.data import GenData

    from eval_checkpoint import _load_showdown_agent, _opponent_from_checkpoint
    from rl.common.checkpoint import load_checkpoint
    from rl.common.config import Config
    from rl.common.evaluation import EVAL_SEED_OFFSET
    from rl.envs.make import make_env
    from rl.search.bridge import BridgeCounters, battle_to_state
    from rl.search.determinize import sample_determinization
    from rl.search.ensemble import EnsembleAgent

    type_chart = GenData.from_format("gen1randombattle").type_chart
    members = []
    for path in args.checkpoints:
        c = load_checkpoint(path)
        members.append(_load_showdown_agent(c, Config(**c["config"])))
    agent = EnsembleAgent(members) if len(members) > 1 else members[0]
    print(f"object: committee of {len(members)}", flush=True)

    c0 = load_checkpoint(args.checkpoints[0])
    cfg0 = Config(**c0["config"])
    opponent, _ = _opponent_from_checkpoint(args.checkpoints[0], cfg0.seed)
    env = make_env(cfg0.env_id, cfg0.seed, env_kwargs={"opponent": opponent})
    counters = BridgeCounters()
    rows_path.parent.mkdir(parents=True, exist_ok=True)
    rows, done_eps = load_rows(rows_path)
    if rows:
        print(f"RESUME: {len(rows)} positions already measured in {rows_path}",
              flush=True)

    # ---- one position, then its rollouts, then the next ------------------
    # INTERLEAVED on purpose. Collecting every position first and measuring
    # afterwards is the same arithmetic but it is not RESUME-SAFE: the job only
    # produces its first row after the whole collection phase, so a death at
    # 90% costs everything. Measuring each position as it is reached means a
    # death costs one position and the rate is readable from the file.
    #
    # Each position also gets its OWN rng, derived from (seed, ep), so a
    # resumed run reproduces the positions it skipped and the ones it has yet
    # to do -- a single shared stream would make the resumed half a different
    # experiment from the first.
    t_start = time.time()
    for ep in range(args.battles):
        if ep in done_eps:
            continue
        rng = np.random.default_rng([args.seed, ep])
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + 90000 + ep)
        mask = info.get("action_mask")
        stop_at = int(rng.integers(2, 14))     # mid-battle, before most are decided
        done, step, found = False, 0, None
        while not done and step < 500:
            # env.unwrapped (ShowdownEnv) -> _env (SingleAgentWrapper) -> env
            # (ShowdownSingles) -> battle1. Checked against the live object
            # rather than guessed; one level short silently yields None and the
            # run reports "0 usable positions" with no other symptom.
            inner = getattr(getattr(env.unwrapped, "_env", None), "env", None)
            battle = getattr(inner, "battle1", None) if inner is not None else None
            if step >= stop_at and battle is not None and not battle.finished:
                dets = [sample_determinization(battle, rng) for _ in range(args.dets)]
                try:
                    states = [battle_to_state(battle, d, counters) for d in dets]
                except (KeyboardInterrupt, SystemExit):
                    raise
                except BaseException:
                    break
                found = (states, int(battle.turn), np.asarray(obs, dtype=np.float32))
                break
            obs, _, term, trunc, info = env.step(
                agent.act(obs, mask, deterministic=True))
            mask, done, step = info.get("action_mask"), term or trunc, step + 1
        if found is None:
            continue
        states, turn, pos_obs = found
        v = _critic_value(agent, pos_obs)
        outs = []
        for st in states:
            for _ in range(args.rollouts):
                o = rollout(st, agent, type_chart, rng, turn)
                if not np.isnan(o):
                    outs.append(o)
        if len(outs) < 4:
            continue
        outs = np.asarray(outs, dtype=np.float64)
        row = {"ep": ep, "turn": turn, "mean": float(outs.mean()),
               "var": float(outs.var()), "n": int(outs.size), "critic": v,
               "outcomes": outs.tolist()}
        rows.append(row)
        with rows_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        el = time.time() - t_start
        print(f"ep {ep + 1}/{args.battles}: {len(rows)} rows, "
              f"turn {turn}, n {outs.size}, mean {outs.mean():+.3f}, "
              f"{el / max(len(rows), 1):.1f} s/row", flush=True)
    env.close()
    print(f"{len(rows)} usable positions", flush=True)

    all_out, all_pred = [], []
    for r in rows:
        all_out.extend(r["outcomes"])
        all_pred.extend([r["critic"]] * len(r["outcomes"]))
    m = np.array([r["mean"] for r in rows])
    w = np.array([r["var"] for r in rows])
    ao, ap_ = np.asarray(all_out), np.asarray(all_pred)
    var_within = float(w.mean())
    var_between = float(m.var())
    var_total = float(ao.var())
    ceiling = var_between / var_total if var_total > 0 else float("nan")
    ev_critic = (1.0 - float(((ao - ap_) ** 2).mean()) / var_total
                 if var_total > 0 else float("nan"))

    summary = {
        "positions": len(rows), "rollouts_total": int(ao.size),
        "dets": args.dets, "rollouts_per_det": args.rollouts,
        "mean_outcome": float(ao.mean()),
        "var_within_obs": var_within, "var_between_obs": var_between,
        "var_total": var_total,
        "ev_ceiling": ceiling, "critic_ev_here": ev_critic,
        "critic_headroom": ceiling - ev_critic,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"summary": summary,
         "rows": [{k: v for k, v in r.items() if k != "outcomes"} for r in rows]},
        indent=2))
    print("\n" + "=" * 72)
    print(f"{len(rows)} positions x {args.dets}x{args.rollouts} rollouts "
          f"= {ao.size} outcomes; mean outcome {ao.mean():+.4f}")
    print(f"  Var WITHIN an observation (chance + hidden info) : {var_within:.4f}")
    print(f"  Var BETWEEN observations (what play controls)    : {var_between:.4f}")
    print(f"  EV CEILING for ANY critic reading our obs        : {ceiling:.4f}")
    print(f"  our critic's EV on these same positions          : {ev_critic:.4f}")
    print(f"  headroom                                         : {ceiling - ev_critic:+.4f}")
    print("=" * 72)
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
