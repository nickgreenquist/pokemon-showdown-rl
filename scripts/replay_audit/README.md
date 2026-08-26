# `scripts/replay_audit/` — overnight audit of the ladder replays

Built 2026-08-25 in answer to "audit the replays, find any patterns."
Read-only: nothing here touches the agent, the encoder or a running ladder.

    python scripts/replay_audit/issues.py       # 10 issue classes, both sides
    python scripts/replay_audit/zero_damage.py  # 0x moves, by certainty
    python scripts/replay_audit/switching.py    # switch quality, boost tracking
    python scripts/replay_audit/efficiency.py   # damage efficiency + win/loss
    python scripts/replay_audit/variance.py     # crits, status, luck by outcome

**Every check runs on BOTH sides of the same battles.** A rate without the
human baseline from the same parser, carrying the same bugs, is not
interpretable — and in this audit the baseline is what overturned the
headline: we pick the highest-damage move MORE often than our opponents do.

Two false positives are pinned here because they cost real time:

  1. `_parse.moveset_dist` enumerates Showdown's own `randomSet` rather than
     reasoning about the JSON. `moves` is not filler — it is sampleNoReplace
     over the REMAINING slots, so when `len(moves) + 1 exclusive` fills the
     4-move cap every entry is taken with probability 1. That is why Raichu
     ALWAYS has Surf and Electabuzz ALWAYS has Psychic, which is what makes
     their 0x Electric moves indefensible rather than forced.
  2. Boosts are tracked. An early pass flagged 54 decisions as "attacked into
     a resist"; its biggest cluster (Slowpoke vs Poliwrath, 11x) was a correct
     Amnesia sweep. Gen 1 Amnesia raises Special for attack AND defence, so a
     0.5x Surf from a boosted Slowpoke beats an unboosted neutral move.
