"""Play against a checkpoint yourself, in the browser.

    python scripts/play_vs_agent.py --from-user <your-name> --battles 3
    python scripts/play_vs_agent.py --from-user <your-name> --mode search --battles 1

Then open the official client pointed at the local server:

    https://play.pokemonshowdown.com/~~localhost:8000

pick the username you passed as --from-user (no password), find the bot
under its username (default: ourbestagent), and challenge it to
[Gen 1] Random Battle. The seat accepts challenges from YOUR username
only and exits after --battles.

Defaults to the D26 s65 final (the falsifier's median lane) played
GREEDY — the general-strength configuration whose gains transfer to
every anchor. --mode search adds depth-1 search@M (~65 ms/move; the
config that is stronger vs SH but measured SH-facing). Human play is
diagnostic fun, not a recorded anchor: nothing here writes to results/.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_fp_h2h import SeatPlayer, _build_agent  # noqa: E402

from poke_env.ps_client.account_configuration import AccountConfiguration  # noqa: E402

S65 = {
    "path": "runs/showdown_sp_recipe12m_s65/checkpoint.pt",
    "sha256": "09469e6a5f6c2c6bc9f6c1452955cdcde12f04d7b73e51f9e8ef2d77f8c667b7",
}


async def run(args) -> None:
    if args.checkpoint is None:
        spec = S65
    else:
        import hashlib

        h = hashlib.sha256()
        with open(args.checkpoint, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        spec = {"path": args.checkpoint, "sha256": h.hexdigest()}
    agent = _build_agent(spec)
    search_agent = None
    if args.mode == "search":
        from rl.search.agent import SearchAgent
        from rl.search.matrix import DOSES

        search_agent = SearchAgent(agent, DOSES["M"], checkpoint_seed=65)
    seat = SeatPlayer(
        agent, search_agent,
        account_configuration=AccountConfiguration(args.username, None),
    )
    print(f"'{args.username}' ({args.mode}) is waiting — challenge it from "
          f"'{args.from_user}' at https://play.pokemonshowdown.com/~~localhost:8000 "
          f"([Gen 1] Random Battle, {args.battles} battle(s))")
    await seat.accept_challenges(args.from_user, args.battles)
    print(f"done: you {seat.n_lost_battles} — {seat.n_won_battles} bot "
          f"(ties {seat.n_tied_battles})")


def main() -> None:
    import hashlib
    import os

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--from-user", required=True,
                        help="YOUR username in the browser client")
    parser.add_argument("--username", default="ourbestagent",
                        help="the bot's username to challenge")
    parser.add_argument("--battles", type=int, default=1)
    parser.add_argument("--mode", choices=["greedy", "search"], default="greedy")
    parser.add_argument("--checkpoint", help="override the default s65 final")
    args = parser.parse_args()
    for var in ("POKEMON_RL_ENCODER_V2", "POKEMON_RL_ENCODER_IDS"):
        assert os.environ.get(var) == "1", f"{var}=1 required"
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
