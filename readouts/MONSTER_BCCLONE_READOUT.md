# BC-clone anchor leg — the LADDER R5 committee (and its fleet), n=500/arm

Committed provenance; `results/` is gitignored. Pre-reg:
`configs/eval/monster_bcclone.yaml`. Run 2026-09-16 in one session on an idle
box, sequentially, against the same frozen clone
(`runs/bc_fp_v2r_soft_180k_s0/checkpoint.pt`, sha `5e490ade…99a0683`) the 100M
fleet's banked numbers were measured against.

```
bash scripts/monster_bcclone_queue.sh            # server up; 7 arms, ~4 min
```

**This leg completes the gen-1 anchor battery for the R5 object.** It was
PENDING since the ladder finished — not for want of a decision, but because
`scripts/ch3_r4_anchors.py` had been unrunnable since 2026-09-05 (it passed
`_opponent_from_checkpoint`'s `(player, env_id)` pair straight into `make_env`)
and had no ensemble seat at all. Both fixed in 099c440 and this commit.

## The numbers

| arm | object | win rate vs the clone | n | ties |
|---|---|---|---|---|
| **CEW** | **the R5 committee — ENS3 of the 200M W trio** | **0.9640** | 500 | 0 |
| CW104 | W lane s104, greedy | 0.9500 | 500 | 0 |
| CW112 | W lane s112, greedy | 0.9520 | 500 | 0 |
| CW120 | W lane s120, greedy | 0.9380 | 500 | 0.002 |
| **W fleet pooled** | | **0.9467** | 1500 | |
| CH104 | 100M lane s104, greedy | 0.9320 | 500 | 0 |
| CH112 | 100M lane s112, greedy | 0.9440 | 500 | 0.002 |
| CH120 | 100M lane s120, greedy | 0.9360 | 500 | 0 |
| **100M fleet pooled, THIS SESSION** | | **0.9373** | 1500 | |

Zero mask desyncs on every arm. The anchor battery's rule is that a lane value
is quoted as the PAIR {lane, fleet pooled}, so: **the committee 0.9640 (n=500);
the W fleet 0.9467 (n=1500, lanes 0.950 / 0.952 / 0.938)**.

## The reads, as pre-registered

- **A1 — the leg itself: the R5 committee beats the clone 0.9640 (n=500).**
- **A4 — committee minus its own singles: +0.0173 at 1.71 se. NULL, and a null
  here was pre-stated as EXPECTED** — at a ~0.95 ceiling this leg cannot resolve
  anything under ~2.3 points (2·se at p=0.93, n=500, is 0.0228).
- **W fleet vs the 100M fleet, same session: +0.0093 at 1.09 se — NULL.** The
  recipe that is credited in RESULTS §21 on the vs-SH and off-FP axes is
  INVISIBLE against this opponent. That is the expected shape of a ceiling
  measurement, not a contradiction: both fleets already beat a frozen imitator
  ~94% of the time, so the axis has almost no headroom left to show a difference.
- Committee vs the 100M fleet, same session: +0.0267 at 2.56 se — quoted for
  completeness, and NOT to be read as an effect: it is one arm of n=500 against
  a pooled 1500 at a ceiling, on a descriptive anchor.

## Why the same-session re-draw was worth running

The banked 100M clone numbers (2026-09-04) are **pooled 0.9233, lane s112
0.930**. Re-drawn today against the identical frozen clone they read **0.9373**
— **+0.0140 at 1.51 se** higher. Nothing about either fleet changed; that gap is
session-to-session variance on this instrument. **Had the W numbers been
differenced against the banked 0.9233 instead of a same-session re-draw, the
"gain" would have read +0.023 rather than +0.009** — two and a half times
larger, and entirely an artefact. `configs/showdown_monster200m.yaml` already
records that this leg's old 0.894 ± 0.04 tripwire is a ch3/s65-era bar and not a
cross-era one; this is that warning, measured.

## Disclosures that travel with every number above

- **A clone number is never style evidence** (CLAUDE.md's anchor battery):
  "match the policy form to the rating you compare against". This is a
  180k-step behavioural clone of 7,200 Foul Play battles collected BEFORE the
  FP@20 budget was pinned — a fixed, weak imitator. Beating it says our policy
  does not lose to a frozen imitation, and nothing else.
- **Anchors are DESCRIPTIVE and never verdict inputs.** Nothing here is a
  credit; nothing here changes RESULTS §20 or §21.
- Seat 1 is deterministic and seat 2 (the clone) SAMPLES — asymmetric by
  protocol, one orientation only, exactly as the 100M leg ran it.
- Ties are non-wins in every rate.
- n=500 at these win rates cannot resolve differences under ~2.3 points.
