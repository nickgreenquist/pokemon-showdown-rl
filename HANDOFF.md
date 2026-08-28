# Handoff — RS80 LANDED, CH5 R1 CLOSED, R3 PRE-REG IS A DRAFT AWAITING SIX
# RULINGS. Written 2026-08-28 ~01:05Z, immediately before a Mac restart.

**NOTHING IS RUNNING.** The wave is `WAVE COMPLETE`, every process is gone,
the tree is clean and pushed. The Showdown server was left up; it dies with
the restart and just needs relaunching (`cd showdown && node pokemon-showdown
start --no-security`) before anything touches the env.

## 1. What landed while you were away

**RS80, the mandatory fresh re-score, is IN and CLEAN.** CH5 R1 is now
complete end to end: **ten graded arms, ZERO VOIDS**, G2 exact on every one,
G-SERIAL clean across 18 username pairs.

- **PUBLISHABLE: search@M on s80, off Foul Play@20, n=3000 -> `0.4390`**
  (1317-1671-12). 2.43 h, 2.92 s/battle, mean_turns 37.015, mask_desyncs 0.
- **The selection score was 0.4470 at n=1000. The fresh re-score is 0.4390 —
  the WINNER'S-CURSE direction. Publishing 0.4470 would have overstated the
  object; Q6 earned its place and the log records that it did.**
- **vs the incumbent C0/L2 0.3893: +0.0497, 3.9 binomial se. DESCRIPTIVE —
  R1 CREDITS NOTHING.** It is the pre-registered `r3_deployment_rule`
  comparison and it clears the +0.025 replacement threshold on a FRESH score.
  **The R3 deployment object stands: search@M on lane s80.**
- **CEILING, and it travels with the number forever:** licenses search as an
  R3 DEPLOYMENT CANDIDATE and nothing else; does NOT reverse MU-8
  (z = -2.80); is not a vs-SH number; **never set beside the 12M cell
  (0.79283)**. NAME THE BUDGET — this is FP@20.

Grade artifact: `results/ch5_r1_offsh/grade.json`. Re-run any time with
`python scripts/ch5_r1_grade.py --out results/ch5_r1_offsh/grade.json`.

## 2. Two live defects fixed in the ladder runner (both were going to bite R3)

**(a) `ladder.py` read the rating off the TOP-500 LEADERBOARD, which by
construction lists only ranked accounts.** R1 finished unlisted, so
`stopping_rule_met` answered "not yet on the top-500 list" on every poll and
the report says `stopped_by_rule: false` — **while R1 was sitting at rd 26.6 /
n 200, i.e. the rule was SATISFIED.** Two tests PINNED the wrong behaviour, so
a green suite was defending the bug. It now reads
`https://pokemonshowdown.com/users/<userid>.json`, verified live against R1's
own account (elo 1292.25, gxe 59.6, rpr 1573.04, rprd 26.57, w95/l105).
Same class of error fixed in the readout generator, which still emitted the
PRE-BATTLE "Elo 1311" as the final rating.

**(b) `PS_USERNAME` silently overrode the pre-registered account name.** A
stale export would have laddered R3 on R1's account and permanently
contaminated the only published ladder rating we have. **The pre-reg is
authoritative now** — `PS_USERNAME` may only CONFIRM it and the run aborts on
disagreement, compared on the userid so punctuation and case are free. This is
what makes ordinary `...bot2`-style names safe, per your ruling that a naming
convention is a habit and not a mechanism. Six tests pin it; 54 pass.

## 3. R3 IS READY EXCEPT FOR SIX RULINGS — `configs/eval/ladder_r3.yaml`

Written under the standing 2-Opus cycle (validity framing + ops framing,
synthesised, every load-bearing claim re-verified against source). It is a
**DRAFT and must not be launched.** `open_decisions:` at the foot of the file:

- **D1 SCHEDULE — the big one. R3 IS NOT ONE NIGHT.** 200 battles projects to
  **16-19 h** plus a +1-2 h auto-tie tail. Recommendation: two sessions of
  ~100 with explicit `--battles` targets (it is a CUMULATIVE target across
  resumes). Alternative if you want one night: declare an n>=150 floor
  RESULT-BLIND, before the first battle.
- **D2 ETIQUETTE** — is a second, sequential account inside R1's "multiple
  accounts" line? Draft ruling: yes, and the second and last time without a
  courtesy note to PS staff.
- **D3 CONCURRENCY** — `ladder.py` is still `max_concurrent_battles=1` while
  the FP seat went to 2 on 2026-08-27 to close a poke-env deadlock whose own
  fix comment names SEARCH as the exposed policy (it hung b81 at 639 then 611,
  b82 at 57 then 699). On a rated ladder that hang forfeits a live game
  against a human. Recommend raising to 2. **Flagged rather than done
  silently, because the etiquette argument cites the literal "max_concurrent
  1".** UNMEASURED on the ladder path — reasoning from mechanism.
- **D4 ANCHORS** — R3's object will have ONE of three. Recommend buying the
  other two (~2.7 h), sequenced AROUND the ladder, never beside it.
- **D5 COMPARISON RULING** — R3 is STANDALONE DESCRIPTIVE; no R1-vs-R3 delta
  may be quoted as an effect. The 76-Glicko-point bar is REFUSED with reasons.
  Cost: "+N Elo from search" is not available at any n this design can buy.
- **D6 SEARCH REVERSAL** — R3 deploys the arm `ladder_r1.yaml` argued against
  and you accepted the argument against. On the record as a decision.

**Already done for R3:** account `nickgen1rbrlbot2` registered (zero rated
games), `.env` written 0600 and gitignored, checkpoint sha verified, the arm
BUILDS (obs_dim 828, dose M), VOID (c) set-pool pin re-verified against
upstream master (0 commits since we vendored).

## 4. Numbers that were WRONG in this repo and are now corrected

- **"R1 ran 217 s/battle" is wrong.** It divides a session-scoped
  `wall_clock_sec` (43464.6 s, covering 180 battles) by a cumulative
  `battles_total` (200). True rate off the JSONL `finished_at` deltas is
  **246.5**. Never divide those two fields.
- **R1's band table sums to 194 of 200.** The six missing battles are exactly
  the six where the JSONL `opponent_rating` is None — the table was built from
  the ADVISORY column instead of the replays, which carry 200/200.
- **Auto-tie counts, from each arm's own tallies:** search 4/5/8 per 1000,
  greedy 1/0/0. RS80 re-confirms at n=3000: 12 ties, 0.4%.

## 5. What is next, in order

1. **Rule on D1-D6**, then launch R3 per the file's own launch gates (LG-1 is
   already satisfied: RS80 landed clean).
2. **R2 retrain — COMMITTED, NOT CONDITIONAL.** The batch-lever ruling is
   still owed: the R1-A branch table routes to **C2 (more lanes, first-class)**
   while batch is an assistant **§3b A4** addition that competes but may not
   displace a C-item without your explicit call. Recommended shape is in the
   previous handoff and unchanged: drop the scale question for the chapter
   (permitted verbatim), spend R2 on batch at ~1,000 episodes/update, 3 new
   50M lanes, banked s80/s81/s82 as a free control.
3. **Scale only after checking sigma_seed shrank below 0.0617.** If it did
   not, scale is still unmeasurable at k=3 and you would be buying an answer
   you cannot read. Decide before buying, not at readout.
4. `CLEANUP.md` rulings.

## 6. Do not

- Quote 0.4470. It is a selection score (Q6).
- Set RS80's 0.4390 beside the 12M search cell 0.79283, or read it as vs-SH.
- Run the readout scripts bare — all three default to R1's paths AND R1's
  account name and will emit a normal-looking readout OF R1.
- Launch R3 before D1-D6 are ruled.
