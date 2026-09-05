"""Behavioral-cloning dataset: a scripted bot's own decisions, encoded
through the Gen 1 observation encoder — the data half of the
encoder-ceiling diagnostic (SESSION_LOGS_PREDECESSOR.md P4).

    python scripts/make_bc_dataset.py --battles 4000

Needs the local Showdown server running:
  cd showdown && node pokemon-showdown start --no-security

One row per decision the EXPERT faced in battles it played itself: the
OBS_DIM-wide observation (612 / 808 / 828 by encoder flag) a learner would have seen at that decision, the
legal-action mask, the expert's action index, and the battle the row came
from. Written to a gitignored data/ .npz — like the Phase-4 solver
dataset, collected data is never committed.

WHERE the rows come from is a pre-registration decision, not a default.
These are the expert's OWN visited states against `--opponent`, which is
not the state distribution an RL learner visits against the same bot.
Phase 4 measured exactly this gap and found it enormous (2026-07-29: 0.855
optimal-move agreement in-distribution against 0.44-0.62 on
differently-distributed positions), so a clone trained here answers "can
the encoder support the bot's policy on the bot's own states" — the
weakest and cleanest form of the question, and the one whose failure is
decisive.

Sanity numbers printed at the end (all cheap, all diagnostic): the
recorder's win rate against the opponent (heuristics vs heuristics should
sit near 0.5), decisions per battle, the share of decisions with only one
legal action (those are free for any clone and are reported separately by
the trainer), and the switch/move split of the expert's labels.
"""

import argparse
import asyncio
import time
from pathlib import Path

import numpy as np

from rl.collect import RecordingPlayer
from rl.envs.showdown import OPPONENT_PLAYERS


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battles", type=int, default=1000)
    parser.add_argument("--expert", default="heuristics", choices=sorted(OPPONENT_PLAYERS))
    parser.add_argument("--opponent", default="heuristics", choices=sorted(OPPONENT_PLAYERS))
    parser.add_argument(
        "--concurrency", type=int, default=16,
        help="battles in flight; 16 is measurement (b)'s plateau (2026-07-29)",
    )
    parser.add_argument("--format", default="gen1randombattle")
    parser.add_argument("--out", default=None,
                        help="default data/bc_<expert>_vs_<opponent>.npz")
    args = parser.parse_args()
    out = Path(args.out or f"data/bc_{args.expert}_vs_{args.opponent}.npz")
    out.parent.mkdir(parents=True, exist_ok=True)

    player = RecordingPlayer(
        expert=args.expert,
        battle_format=args.format,
        max_concurrent_battles=args.concurrency,
    )
    # Constructed here rather than through opponent_player: seat 2 plays its
    # own battles over the websocket, so it needs start_listening (the
    # resolver's non-listening default is for delegate seats).
    opponent = OPPONENT_PLAYERS[args.opponent](
        battle_format=args.format, max_concurrent_battles=args.concurrency
    )

    t0 = time.perf_counter()
    asyncio.run(player.battle_against(opponent, n_battles=args.battles))
    wall = time.perf_counter() - t0

    data = player.dataset()
    rows, legal = len(data["actions"]), data["masks"].sum(axis=1)
    np.savez(
        out,
        expert=args.expert,
        opponent=args.opponent,
        battle_format=args.format,
        **data,
    )
    print(f"{args.battles} battles, {rows} decisions, wall {wall:.1f}s "
          f"({rows / wall:.1f} decisions/s)")
    print(f"recorder win rate {player.n_won_battles / args.battles:.3f} "
          f"(ties count as non-wins)")
    print(f"decisions/battle {rows / args.battles:.1f}  "
          f"legal actions mean {legal.mean():.2f}  "
          f"forced (1 legal) {np.mean(legal == 1):.3f}")
    print(f"expert labels: switches {np.mean(data['actions'] < 6):.3f}  "
          f"moves {np.mean(data['actions'] >= 6):.3f}")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
