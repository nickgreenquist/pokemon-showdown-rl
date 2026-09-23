# R1-E on the ENGINE backend — the write-side bridge's root-init parity (R7 B6)

Written 2026-09-23T19:50:28+00:00. Every number is read from `results/search_r1e_engine_all/r1e.json` (gitignored) written by `scripts/search_r1e_gate.py --backend engine --all --control-limit 2000 --leg-b-limit 500` at branch `r7-native-search` `dbb3071` (worktree `../pokemon-showdown-rl-r7`, env `pkmn-engine-r7`, niced beside the R6 fleet). Design: `docs/search_relook/ENGINE_SEARCH_DESIGN.md` §2–§3; the gate's own docstring says what a PASS licenses and does not.

## Verdict, by the gate's rule

**R1-E PASS** (A pass | C pass | controls all fire). Corpus: the 13,396 non-aliased harvested roots of `results/ch3_r1/harvest_s6{2,3,4,5}.pkl` (the 12M-era R1 corpus; §3.2's fresh 100M-lane harvest is still owed).

| leg | roots | read | bar |
|---|---:|---|---|
| A — observation parity, bitwise vs the live `row['obs']` | 13140 built | **13102 bit-identical (99.7%)**, 0.0029 dims/root, undeclared dims 0 | ≥ 40% bit-identical, ≤ 1.5 dims/root, no undeclared dim |
| C — mask parity vs the live `row['mask']` (the load-bearing leg) | 13140 built | **13140 exact (100.0%)** | 100% |
| refused, never built (named families, counted on both legs) | 256 | W-ACTIVESTATS 209, W-LASTMOVE 47 | the engine backend REFUSES rather than defaults |

## The one declared family on leg A

- **W-RECHARGE-STALE**: 0.0029 dims/root, 38 roots (0.29%), max |Δ| 1.00, obs-visible True, dims `own_active.volatile[MUST_RECHARGE], exactly one dim`.
  poke-env's `must_recharge` outlives the server's lock (the gate's standing finding F1). Written into the bytes as-is it made these 38 roots FORCED and aliased in the engine (our moves re-based onto the Recharge placeholder) while the live root had a full choice set — the first full-corpus run's one undeclared family, 36 dims/root on 38 roots, leg C 13,102/13,140. The bridge now writes our recharging flag only when the request corroborates it; leg C became exact on every built root, and the single dim that still differs is the live encoder writing the client's stale flag as a feature. The constructed root is the true state.

## Positive controls (n = 1,963 roots each; §3.3 + C8)

| id | status | exposed | moved | leg A dims/root base → control | leg C exact base → control | what |
|---|---|---:|---:|---|---|---|
| C1 | FIRES | 1675 | 1644 | 0.0020 → 20.8487 | 1963->1963 | swap two entries of the opponent's rev |
| C2 | FIRES | 1913 | 1486 | 0.0020 → 0.9063 | 1963->1963 | zero move_uses (re-introduce the A-1a |
| C3 | FIRES | 147 | 145 | 0.0020 → 0.0759 | 1963->1963 | sleep_observed off by one |
| C4 | FIRES | 144 | 144 | 0.0020 → 0.0711 | 1963->1968 | drop flags_before_faint |
| C5 | FIRES | 1736 | 1891 | 0.0020 → 60.0346 | 1963->1963 | THE AS-IS CONTROL: every opponent part |
| C6 | FIRES | 157 | 152 | 0.0020 → 0.1615 | 1963->1963 | flip the sign of a negative boost |
| C7 | FIRES | 1179 | 45 | 0.0020 → 0.0250 | 1963->1963 | write HP with floor instead of round |
| C8 | FIRES | 1525 | 1492 | 0.0020 → 2.2822 | 1963->471 | [beyond §3.3] revive a fainted bench m |

Every control fires. C5, the everything-revealed projection, moves 60 dims/root: R1-E measures the information boundary (`BattleTracker::from_root`), not the plumbing. C8 (a revived bench mon) is the only control leg C sees, and it drops leg C to 471/1,963.

## Refused roots

- **W-ACTIVESTATS, 209 (1.56%)**: a transformed Ditto on either side. The engine→engine resample carries Transform; the poke-env side does not yet (the design's 'hardest field, stated honestly'). Owed before the ladder path is used on a transformed root.
- **W-LASTMOVE, 47 (0.35%)**: a charging active whose live slot the harvest cannot supply (`preparing` is a bool in a snapshot; the live path has `_preparing_move`). An index of 0 is an out-of-bounds read in the engine, so the root is refused, never defaulted.

## What this licenses and what it does not

Per the gate: a PASS licenses BUILDING on the constructed root — the native operator (`rl/search/native.py`) may search a root the bridge built from a poke-env view. It is not a search number, not a claim about the transition or the leaves, not a claim about the 100M-lane state distribution (that harvest is owed), and says nothing about the families neither leg can see (W-STATS, W-LASTDMG, W-SEED, W-CONF, W-SUB, W-LS, W-ORDER, W-LASTMOVE, W-DISABLE, W-ACTIVESTATS). Leg B's one-turn agreement with the stand-in path is NOT measured on this backend (`step` returns None). Rule 6: nothing here is a win-rate read.
