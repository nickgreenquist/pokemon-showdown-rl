"""Measure Foul Play's win rate against SimpleHeuristicsPlayer — the SH seat.

    python scripts/foulplay_vs_sh.py --opponent foulplaybot --battles 300
    python scripts/foulplay_vs_sh.py --opponent foulplaybot --battles 5 --tag smoke

This script owns the SH side only. Foul Play runs as a SEPARATE process, in a
SEPARATE environment, and the two meet in the local Showdown server — neither
imports the other. See "How to run it" at the bottom of this docstring.

=============================================================================
PRE-REGISTRATION — written before the first battle, per the repo convention
=============================================================================

WHY THIS MEASUREMENT EXISTS

DESIGN.md §11 proposes (C): expert iteration with Foul Play as the teacher —
generate demonstrations offline, distil by BC, RL from there. §11 states its
own ceiling honestly: (C) is bounded by Foul Play's strength, "which nobody in
our index has measured." That is the one number option (A) exists to buy, and
it should be bought before a chapter-sized commitment.

The stakes are set by P4. A behavioural clone lands BELOW its teacher: cloning
SH produced 0.4657 against an SH-vs-SH parity mark of 0.489 — roughly 0.023
short. Our best RL policy is 0.4607, i.e. level with that clone and ~20 Elo
below SH itself. So a teacher only modestly stronger than SH distils into a
student that lands roughly where we already are, and the chapter buys nothing.
Meanwhile the published pure-policy randbats field starts at 72% GXE against
SH's ~40% (see the ladder-translation section at the top of prior_work/README).
Expert iteration is worth a chapter only if the teacher is a big step up.

PRIMARY READ, with the decision rule fixed in advance

  Foul Play's win rate vs SimpleHeuristicsPlayer in gen1randombattle, on our
  own server, at Foul Play's stock search budget (--search-time-ms 100,
  --search-parallelism 1). Ties count as non-wins, matching the locked eval
  protocol; ties are ALSO reported separately.

  >= 0.70  GO. Clearly stronger teacher; §11 (C) stands as the recommended
           main line and D8(c) is well-founded.
  0.60-0.70  MARGINAL. (C) only with a re-priced, deliberately smaller first
           dataset, and the D9 ordering re-argued — a student landing ~0.03
           under a 0.65 teacher is a real gain over 0.4607 but not a large one.
  < 0.60   NO. The teacher does not clear the bar. (C) does not proceed on
           this evidence; D8 falls back to (a)/(b) and D9(a) — the corpus
           chapter on the >=2024-04 subset — becomes the main line by default.

  Calibration for the bands, so they are not arbitrary: SH sits at ~40% GXE on
  the gen7/gen9 randbats ladders (Metamon Table 2). An agent in the published
  pure-policy class (~76% GXE) is ~270 Elo above that, which is ~0.82 head to
  head. A teacher that cannot manage 0.60 against SH is nowhere near that class
  and cannot lift a student past the SH-imitation ceiling P4 already hit.

SAMPLE SIZE

  300 battles, single lane. At p ~ 0.7 that is se = 0.026, so the 0.60/0.70
  band edges sit ~4 se apart — enough to place the result in a band, which is
  all the decision needs. This is the "reduced pre-registered protocol" §11(A)
  and D5 both anticipated; it is NOT the locked 3-seed/3000-battle protocol,
  because this is a scouting measurement of a third-party bot, not an arm.

R0 SANITY GATES — if any fails, the number is void, not merely noisy

  (1) THE ENGINE IS ACTUALLY BUILT FOR GEN 1. Foul Play ships pinned to
      poke-engine==0.0.48 built with `--features poke-engine/terastallization`,
      i.e. GEN 9. It must be rebuilt with `make poke_engine GEN=gen1`. This
      gate is the reason the whole measurement can go wrong in the dangerous
      direction: a wrong-generation or half-broken engine makes Foul Play play
      BADLY, which biases the primary read DOWN — and down is the direction
      that kills (C). An asymmetric failure mode gets an explicit gate rather
      than a shrug. Run --battles 5 --tag smoke first and read Foul Play's log
      for engine exceptions, "could not" warnings, or fallback-to-random
      behaviour before spending the 300.
  (2) TWO INDEPENDENT TALLIES AGREE. Foul Play prints its own "W: n L: n" line
      each battle. This script counts from the SH seat. The two are independent
      counters of the same battles and must agree, or something is joining the
      battles that should not be.
  (3) EVERY CHALLENGE RESOLVED. n_finished == --battles. A hung or refused
      challenge silently shortens the sample.
  (4) NO THIRD PARTY. The SH seat accepts challenges from the Foul Play
      username ONLY, so a stray poke-env process cannot contaminate the count.

SECONDARY READS — pre-registered so they are not fished for afterwards

  (a) Measured seconds/decision for Foul Play. DESIGN §11 currently carries
      ~0.2 s/decision as INFERRED, never measured; this retires that.
  (b) Wall-clock per battle, which prices (C) properly: §11's "~6 h at 8-way
      for a P4-scale dataset" rests on the inferred number and on P4's 903,090
      decisions. Both get restated from measurement.
  (c) Tie rate. Our own arms run 1.57% ties; a much higher rate against a
      search bot would say something about how gen1 randbats ends.
  (d) Mean battle length, for the same dataset arithmetic.

WHAT THIS MEASUREMENT DOES *NOT* SETTLE

  Not the mechanics-agreement question. §11(A) also asks whether poke-engine's
  gen1 build reproduces Showdown's gen1 closely enough to search in. This run
  does not answer that and does not need to: Foul Play plays on the real
  Showdown server, so the SERVER is the referee. Any divergence between the
  engine's model and Showdown's shows up AS Foul Play playing worse, which the
  win rate already captures. The number measures Foul-Play-as-deployed, which
  is exactly what expert iteration would distil. The agreement study is only
  worth paying for if this number says the teacher is worth building on.

  Not a ladder claim of any kind. Nothing here touches the public ladder; per
  the 2026-08-06 decision, ladder execution waits until an agent is past SH.

HOW TO RUN IT (two environments, one server — never one env)

  Foul Play pulls poke-engine and its own pinned requirements. It does NOT go
  in the pokemon-showdown-rl env: the repo's dependency rule is exact pins via
  pyproject.toml with no ad-hoc pip installs, and CLAUDE.md already records
  what sharing an env across projects costs. Foul Play gets its own env; this
  script runs from ours; both point at the local server on :8000.

  Foul Play also needs the local-login patch in scripts/patches/ — it posts to
  play.pokemonshowdown.com for an assertion even in guest mode, which a
  --no-security server neither needs nor validates. poke-env skips auth
  outright when there is no password (ps_client.py: assertion = ""), and the
  patch makes Foul Play do the same. Full command sequence is in the
  2026-08-06 SESSION_LOGS.md entry.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from poke_env.player import SimpleHeuristicsPlayer
from poke_env.ps_client.account_configuration import AccountConfiguration

BATTLE_FORMAT = "gen1randombattle"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--opponent",
        required=True,
        help="Foul Play's --ps-username. Challenges from anyone else are ignored.",
    )
    parser.add_argument(
        "--battles",
        type=int,
        default=300,
        help="Challenges to accept. 300 is the pre-registered primary; use 5 for the smoke.",
    )
    parser.add_argument(
        "--username",
        default="shanchor",
        help="Username for the SH seat. Must not collide with a seeded poke-env lane.",
    )
    parser.add_argument(
        "--tag",
        default="primary",
        help="Label for the output file, e.g. 'smoke' or 'primary'.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("results/foulplay_vs_sh"),
        help="Where the JSON result lands.",
    )
    return parser.parse_args()


async def run(args: argparse.Namespace) -> dict:
    # No password: poke-env then skips the assertion request entirely, which is
    # what the local --no-security server expects. Same path every training run
    # already takes.
    sh = SimpleHeuristicsPlayer(
        account_configuration=AccountConfiguration(args.username, None),
        battle_format=BATTLE_FORMAT,
        max_concurrent_battles=1,
    )

    print(f"SH seat '{args.username}' waiting for {args.battles} challenges from '{args.opponent}'")
    started = time.monotonic()
    await sh.accept_challenges(args.opponent, args.battles)
    elapsed = time.monotonic() - started

    finished = sh.n_finished_battles
    # Ties are non-wins in the locked protocol, and are also reported on their own
    # so the primary read can be recomputed under either convention.
    sh_wins = sh.n_won_battles
    ties = sh.n_tied_battles
    fp_wins = sh.n_lost_battles

    turns = [b.turn for b in sh.battles.values() if b.finished]

    return {
        "tag": args.tag,
        "battle_format": BATTLE_FORMAT,
        "opponent_username": args.opponent,
        "sh_username": args.username,
        "battles_requested": args.battles,
        "battles_finished": finished,
        "foulplay_wins": fp_wins,
        "sh_wins": sh_wins,
        "ties": ties,
        # PRIMARY: ties as non-wins for Foul Play, matching the locked protocol.
        "foulplay_win_rate": (fp_wins / finished) if finished else None,
        # Secondary framing: ties excluded, for comparison with sources that drop them.
        "foulplay_win_rate_excl_ties": (
            fp_wins / (finished - ties) if finished - ties > 0 else None
        ),
        "tie_rate": (ties / finished) if finished else None,
        "mean_turns": (sum(turns) / len(turns)) if turns else None,
        "wall_clock_sec": round(elapsed, 1),
        "sec_per_battle": round(elapsed / finished, 2) if finished else None,
        # R0 gate (3). Also lets the reader see a short sample for what it is.
        "gate_all_challenges_resolved": finished == args.battles,
    }


def main() -> None:
    args = parse_args()
    result = asyncio.run(run(args))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"{args.tag}.json"
    out.write_text(json.dumps(result, indent=2) + "\n")

    print(json.dumps(result, indent=2))
    print(f"\nwrote {out}")

    rate = result["foulplay_win_rate"]
    if not result["gate_all_challenges_resolved"]:
        print(
            "\nR0 GATE (3) FAILED: "
            f"{result['battles_finished']}/{args.battles} battles finished. "
            "The number is void — do not read it."
        )
    elif rate is not None:
        band = "GO (>=0.70)" if rate >= 0.70 else ("MARGINAL (0.60-0.70)" if rate >= 0.60 else "NO (<0.60)")
        print(f"\nPRIMARY: Foul Play {rate:.4f} vs SH  ->  {band}")
        print("Cross-check this against Foul Play's own 'W: / L:' tally before believing it.")


if __name__ == "__main__":
    main()
