#!/usr/bin/env python
"""Head-to-head between two REGISTRY opponents on the local Showdown server.

    python scripts/anchor_h2h.py --a most_damage_typed --b max_power --battles 300

WHY. A new scripted anchor needs a placement before it anchors anything:
most-damage-typed must beat MaxBasePower (it is MaxBasePower plus a type
chart) and lose to SimpleHeuristics (the index calls it "far weaker than
SH"). These are SANITY numbers — bot-vs-bot, descriptive, never a protocol
number and never a verdict input. Needs the local server up
(`cd showdown && node pokemon-showdown start --no-security`).

Every seat sends /timer on (the orphaned-room deadlock, docs/landmines.md).
Usernames are explicit and distinct so two runs never collide (landmine 2).
"""
import argparse, asyncio, inspect, json, math, statistics, time
from pathlib import Path

from poke_env.ps_client.account_configuration import AccountConfiguration

from rl.envs.showdown import OPPONENT_PLAYERS

FMT = "gen1randombattle"


def build(key: str, username: str, seed: int, concurrency: int):
    cls = OPPONENT_PLAYERS[key]
    kwargs = dict(battle_format=FMT,
                  account_configuration=AccountConfiguration(username, None),
                  max_concurrent_battles=concurrency,
                  start_timer_on_battle_start=True)
    if "seed" in inspect.signature(cls.__init__).parameters:
        kwargs["seed"] = seed
    return cls(**kwargs)


async def run(args):
    a = build(args.a, f"h2h{args.a.replace('_', '')[:7]}{args.seed}", args.seed, args.concurrency)
    b = build(args.b, f"h2h{args.b.replace('_', '')[:7]}{args.seed + 1}", args.seed + 1, args.concurrency)
    t0 = time.monotonic()
    await a.battle_against(b, n_battles=args.battles)
    dt = time.monotonic() - t0
    n = a.n_finished_battles
    w, t, l = a.n_won_battles, a.n_tied_battles, a.n_lost_battles
    rate = w / n if n else float("nan")  # ties are non-wins
    se = math.sqrt(rate * (1 - rate) / n) if n else float("nan")
    turns = [bt.turn for bt in a.battles.values() if bt.finished]
    out = dict(a=args.a, b=args.b, battles=n, a_wins=w, ties=t, a_losses=l,
               a_win_rate=rate, binom_se=se, mean_turns=statistics.mean(turns) if turns else None,
               seed=args.seed, seconds=dt, sanity_only=True)
    print(f"{args.a} vs {args.b}: {w}-{l}-{t} over {n} -> A wins {rate:.3f} ± {se:.3f}, "
          f"mean turns {out['mean_turns']:.1f}, {dt:.0f} s")
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(out, indent=2))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--a", required=True, choices=sorted(OPPONENT_PLAYERS))
    ap.add_argument("--b", required=True, choices=sorted(OPPONENT_PLAYERS))
    ap.add_argument("--battles", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out", default=None)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
