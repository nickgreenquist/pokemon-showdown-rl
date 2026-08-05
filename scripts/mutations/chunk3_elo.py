"""Chunk-3 mutation spec: Bradley-Terry harness (rl/selfplay/elo.py).

Run through the harness from the repo root:

    python scripts/mutate.py scripts/mutations/chunk3_elo.py

Separate from chunk3_solver.py so each battery reruns only the tests its
targets can break. If a control is ever reported caught, the harness is
measuring noise — see scripts/mutate.py's docstring.

`old` strings must match the current source exactly and uniquely; a
refactor that breaks one shows up as BAD-PATTERN, which is a prompt to
update the spec, not to delete the mutation.
"""

TESTS = ["tests/test_elo.py"]

ELO = "rl/selfplay/elo.py"

MUTATIONS = [
    ("draws-not-half-a-win", ELO,
     "        S[i, j] += first_wins + 0.5 * draws",
     "        S[i, j] += first_wins"),
    ("ford-check-dropped", ELO,
     "    if not ford_connected(S):\n        raise ValueError",
     "    if False:\n        raise ValueError"),
    ("ceiling-players-never-dropped", ELO,
     "            if scored[k] == 0 or conceded[k] == 0",
     "            if scored[k] == 0"),
    ("drop-does-not-cascade", ELO,
     """        if not drop:
            return kept, floored, ceilinged
        for i, bucket in drop:
            bucket.append(players[i])
            kept.remove(i)""",
     """        for i, bucket in drop:
            bucket.append(players[i])
            kept.remove(i)
        return kept, floored, ceilinged"""),
    ("anchor-guard-dropped", ELO,
     "    if anchor not in (players[i] for i in kept):",
     "    if False:"),
    ("bootstrap-does-not-resample", ELO,
     "            pair: tuple(rng.multinomial(sum(cell), np.asarray(cell) / sum(cell)))",
     "            pair: cell"),
    ("bootstrap-failures-uncounted", ELO,
     "        except ValueError:\n            failed += 1\n            continue",
     "        except ValueError:\n            continue"),
    # -------------------------------------------------------- intransitivity
    ("cycle-needs-only-two-aligned-edges", ELO,
     "                if (sign[i, j] == sign[j, k] == sign[k, i] != 0):",
     "                if (sign[i, j] == sign[j, k] != 0):"),
    ("tied-edges-complete-cycles", ELO,
     "                if (sign[i, j] == sign[j, k] == sign[k, i] != 0):",
     "                if (sign[i, j] == sign[j, k] == sign[k, i]):"),
    # ------------------------------------------------- equivalence CONTROLS
    # MM is scale-invariant and ratings are anchor-relative: any per-
    # iteration rescaling constant gives identical rating differences.
    ("C1-normalize-by-arithmetic-mean", ELO,
     "        p /= np.exp(np.log(p).mean())  # rescale only: MM is scale-invariant",
     "        p /= p.mean()  # rescale only: MM is scale-invariant"),
    # Strong connectivity holds from every start node or from none.
    ("C2-reachability-from-last-node", ELO,
     "        seen = {0}\n        frontier = [0]",
     "        seen = {n - 1}\n        frontier = [n - 1]"),
]
