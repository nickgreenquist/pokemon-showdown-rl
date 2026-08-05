"""Chunk-4 mutation spec: the forgetting measures in rl/selfplay/elo.py.

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/chunk4_forgetting.py

The AlphaStar proxy is the campaign's PRIMARY forgetting number and the
regression-rate null band is what keeps the secondary from misreading a
never-learns run as the worst forgetter — each mutation here is a way one
of those headline numbers goes quietly wrong: a min silently averaged, a
draw dropped from the pooled score, a tie counted as regression, the
monotone rearrangement (the null's entire content) skipped.

`old` strings must match the current source exactly and uniquely; a
refactor that breaks one shows up as BAD-PATTERN, which is a prompt to
update the spec, not to delete the mutation.
"""

TESTS = ["tests/test_elo.py"]

ELO = "rl/selfplay/elo.py"

MUTATIONS = [
    ("proxy-min-becomes-mean", ELO,
     "        min(_pooled_winrate(counts, rungs[i], rungs[j]) for j in range(i))",
     "        float(np.mean([_pooled_winrate(counts, rungs[i], rungs[j]) for j in range(i)]))"),
    ("pooled-winrate-drops-draws", ELO,
     "    return (a_wins + b_losses + 0.5 * (draws_ab + draws_ba)) / games",
     "    return (a_wins + b_losses) / games"),
    ("regression-counts-ties", ELO,
     "        _pooled_winrate(counts, rungs[i], rungs[j]) < 0.5 for i, j in pairs",
     "        _pooled_winrate(counts, rungs[i], rungs[j]) <= 0.5 for i, j in pairs"),
    ("null-band-skips-the-rearrangement", ELO,
     "    elo = np.sort(np.array([ratings[r] for r in rungs]))",
     "    elo = np.array([ratings[r] for r in rungs])"),
    # ------------------------------------------------ equivalence CONTROLS
    ("C1-proxy-mean-by-hand", ELO,
     "    return float(np.mean(mins)), mins",
     "    return sum(mins) / len(mins), mins"),
    ("C2-proxy-min-over-a-list", ELO,
     "        min(_pooled_winrate(counts, rungs[i], rungs[j]) for j in range(i))",
     "        min([_pooled_winrate(counts, rungs[i], rungs[j]) for j in range(i)])"),
]
