# Handoff — written 2026-08-25 (night), for a fresh-context session

The project just **played its first real Pokémon Showdown ladder games**. Tree
is clean, suite is green (531 passed), nothing is mid-flight, nothing is
broken. Fold this file back to its empty stub on pickup (`# Handoff` + the
"(empty — write here only when the maintainer asks for a handoff)" line).

## Read order

1. `STATUS.md` (authoritative, 60-line cap).
2. **The newest SESSION_LOGS entry** — "FIRST REAL POKEMON SHOWDOWN LADDER
   RUN". It carries everything STATUS could not hold. Index with
   `grep -n '^- 20' SESSION_LOGS.md`, read by offset.
3. **`configs/eval/ladder_r1.yaml` — read the whole header.** It is the
   ratified pre-reg and it is where the live decisions live: the policy
   choice and why search was argued down, the etiquette findings, four VOID
   conditions, and **three READOUT OBLIGATIONS written result-blind**.
4. `CLEANUP.md` — the audit backlog, if you are asked to do cleanup.
5. **Do NOT read `DESIGN.md` for "what next"** — it carries a HISTORICAL/SPENT
   banner.

## The one-line state

**14–6 over 20 ladder battles (0.700 raw, 0.684 on games actually played).
PS Elo 1000 → ~1340, about 17 short of the top-500 admission cutoff (~1357).
NOT listed, so THERE IS NO GXE YET — the primary read is UNMEASURED.** This
was a plumbing run. The pre-registered stop needs **n ≥ 200 AND rd ≤ 40**.

## The next task

Continue the same run. `--battles` is a TOTAL across resumes, so this picks up
at 21 and stops itself when the rule is met:

```
PS_PASSWORD=$(cat ~/.ps_password) python scripts/ladder.py --prereg configs/eval/ladder_r1.yaml --arm L2 --battles 200
```

~12.5 h at 3.8 min/battle, so it spans evenings. Kill and re-run freely — the
JSONL is the truth and resume is per-battle.

## Things that will bite you

- **Do NOT swap in L3/search because it is "our best".** It is best *vs SH*
  (0.79283) and NEGATIVE on both off-SH opponents we have measured (clone
  −0.034, FP@100 −0.020), with MU-8's transfer test at **z = −2.80**. The
  ladder is off-SH. This was argued and ratified; the reasoning is in the
  pre-reg header so it is not re-litigated.
- **Do NOT raise `max_concurrent_battles` above 1.** Matchmaking pairs by
  rating, so k in-flight battles are all matched against the same stale
  rating. CH4 R1 pre-registered a G7 concurrency gate that ended up moot at
  k=1, so nothing here has ever shown k>1 is neutral. Changing k mid-run is
  the worst option — it splits one measurement across two protocols.
- **Do NOT quote 0.700 as a ladder result.** n=20, and the primary read is
  GXE, which does not exist until we are listed.
- **`scripts/score_ladder.py` is a FALSE FRIEND** (Connect-4-era
  checkpoint-rung scorer). The real ones are `scripts/ladder.py` (ladder) and
  `scripts/eval_checkpoint.py` (locked vs-SH protocol).
- **Never quote a "GXE cutoff".** The toplist is ELO-RANKED (verified: elo
  monotone descending, gxe/glicko not). Admission is Elo ~1357.
- **`results/`, `runs/` and `data/` are gitignored with ZERO tracked files.**
  A closed rung's grader script is the only committed provenance for its
  number. "Nothing references it" does not mean dead. See `scripts/README.md`.

## Three readout obligations — all pre-registered, all still owed

Written result-blind during the run, which is why they are trustworthy. Do not
quietly re-scope them at readout:

1. **Rating trajectory from the replays.** poke-env sporadically drops
   `battle.rating` (1 of 20). `results/ladder/replays/*.html` carries both
   players' true ratings. **Join on the NUMERIC battle id** — some tags carry
   a secret `-<token>` suffix that silently breaks a `rsplit("-")`.
2. **The rematch cell.** First encounter vs 2nd+ meeting. At n=20 it read
   14–3 vs 0–2 — **noise, and no conclusion was drawn.** Report each cell's
   opponent-rating distribution alongside: rematches are rating-matched by
   construction, so that confound reads exactly like the effect.
3. **Played games vs non-games.** Classify from replay text ("lost due to
   inactivity", forfeits), never from turn count. Report the raw rate both
   ways. ~6% so far.

## Open, needing a maintainer ruling (all in CLEANUP.md)

Highest value first: **`RESULTS.md` is two chapters behind the README that
calls it canonical** — it ends at D28 and never mentions search or 0.79283.
Then `rl/selfplay/elo.py` (614 lines incl. its test, imported by nothing
else); whether the MinAtar/continuous spine gate is still live (56 of 531
tests, and no continuous env exists in the deps); the killed-lever
footprints; and ~6.7 GB reclaimable by compression alone.

## Artifacts

- Committed through `8b642d7`; **nothing pushed — ask first.**
- `results/ladder/L2.battles.jsonl` (20 rows), `L2.report.json`,
  `results/ladder/replays/` — gitignored, and the only copy.
- The 13 sha-pinned checkpoints are now mirrored to
  `../pokemon-showdown-rl-d25-backup-20260815/_runs_sacred/` and verified
  sha-equal. Before tonight they existed in exactly one place.
- Training seeds 66/67, 75/76, 83/84, 93/94 remain HELD; the ladder burns none.
