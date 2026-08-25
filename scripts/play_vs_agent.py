"""Play against a checkpoint yourself, in the browser.

    python scripts/play_vs_agent.py --from-user <your-name> --arm L2
    python scripts/play_vs_agent.py --from-user <your-name> --battles 3
    python scripts/play_vs_agent.py --from-user <your-name> --mode search --battles 1

**`--arm` is the one you want when sanity-checking the ladder.** It builds
the policy through `ladder._build_policy` and plays it through
`ladder.LadderPlayer` — the exact objects the live ladder run uses, with
`accept_challenges` swapped in for `ladder()`. Anything else tests a cousin
of the laddering agent rather than the agent itself, which for L2 matters:
`--mode greedy` is ONE lane, the ladder primary is a FOUR-lane ensemble.

This runs against the LOCAL server, so it neither touches the laddering
account nor interrupts a live run.

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

from poke_env.ps_client.account_configuration import AccountConfiguration  # noqa: E402

S65 = {
    "path": "runs/showdown_sp_recipe12m_s65/checkpoint.pt",
    "sha256": "09469e6a5f6c2c6bc9f6c1452955cdcde12f04d7b73e51f9e8ef2d77f8c667b7",
}


async def run_arm(args) -> None:
    """The ladder's own policy, challenged instead of queued."""
    import yaml

    import ladder

    prereg = yaml.safe_load(open(args.prereg))
    arm_name = args.arm if args.arm != "PRIMARY" else prereg["primary_arm"]
    act_fn, prov = ladder._build_policy(prereg, prereg["arms"][arm_name])
    seat = ladder.LadderPlayer(
        act_fn,
        account_configuration=AccountConfiguration(args.username, None),
    )
    lanes = prov.get("lanes") or prov.get("lane")
    print(f"'{args.username}' = ladder arm {arm_name} ({prov['kind']}, "
          f"lanes {lanes}) — challenge it from '{args.from_user}' at "
          f"https://play.pokemonshowdown.com/~~localhost:8000 "
          f"([Gen 1] Random Battle, {args.battles} battle(s))")
    await seat.accept_challenges(args.from_user, args.battles)
    print(f"done: you {seat.n_lost_battles} — {seat.n_won_battles} bot "
          f"(ties {seat.n_tied_battles}); decision_errors "
          f"{seat.decision_errors}")


async def run(args) -> None:
    from ch3_fp_h2h import SeatPlayer, _build_agent

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
    parser.add_argument("--arm", nargs="?", const="PRIMARY",
                        help="play a ladder pre-reg arm (L1/L2/L3, or bare "
                             "--arm for the pre-reg's primary_arm). This is "
                             "the option that tests what actually ladders.")
    parser.add_argument("--prereg", default="configs/eval/ladder_r1.yaml")
    args = parser.parse_args()
    # Set rather than assert (ladder.py does the same, and for the same
    # reason): this is a by-hand entry point, and a forgotten export would
    # not fail loudly — it would build a different-width encoder and quietly
    # play something other than the agent under test.
    os.environ.setdefault("POKEMON_RL_ENCODER_V2", "1")
    os.environ.setdefault("POKEMON_RL_ENCODER_IDS", "1")
    asyncio.run(run_arm(args) if args.arm else run(args))


if __name__ == "__main__":
    main()
