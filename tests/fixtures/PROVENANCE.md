# tests/fixtures — provenance

Frozen baselines that tests compare against. Nothing here is imported by `rl/`
and nothing here is ever edited: a file in this directory that no longer
matches its recorded hash is a failing test, not a file to update.

## `ppo_pre_f04.py.txt`

`rl/agents/ppo.py` exactly as of commit
`5d3c6b7c841c008b0e70e916e3d8242ef3166bb5` — the commit BEFORE the F-04
minibatch-tail wire (`650a8e6`, which added `PPOAgent(minibatch_tail=...)` with
default `keep`). 72,626 bytes, sha256
`307ad4a140f8fff08f2c619fdd326cbf915d9ad2dfd6c2111fc5b3acf02be1b7`.

Written once with:

    git show 5d3c6b7c841c008b0e70e916e3d8242ef3166bb5:rl/agents/ppo.py \
      > tests/fixtures/ppo_pre_f04.py.txt

**Why a vendored copy rather than `git show` at test time.**
`tests/test_ppo_episodes.py::test_minibatch_tail_keep_is_bit_identical_to_the_
pre_f04_agent` execs this source into a throwaway module and RUNS the
pre-change agent beside today's, which is the only weight-level evidence that
`minibatch_tail="keep"` is bit-for-bit the old loop — the claim "no run's
numerics move" rests on it. Reading the blob from the object store instead made
that pin silently droppable: after a squash-merge or rebase the commit is gc'd,
an abbreviated sha stops resolving once it stops being unique, and a run from a
non-git export has no store at all — each of which turned the pin into a skip
that blended into the suite's other documented skips. Vendored, it survives any
merge strategy.

The `.py.txt` extension keeps pytest and the linters from collecting it as a
module. It lives here and not in `tests/data/` because `.gitignore` ignores
every `data/` directory (the F-21 landmine: a file that exists only in one
working tree is not a baseline).

`tests/test_ppo_episodes.py::test_pre_f04_baseline_is_present_and_pinned` keeps
it honest — the hash above, the absence of F-04's helper and kwarg, and, when
the object store still has the commit, byte-identity with the blob itself.
