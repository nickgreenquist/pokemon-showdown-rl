# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25 — **LADDER R1 IS OPEN AND RESUMABLE AT n=20
OF 200.** First real run: 14-6 raw 0.700, 13-6 played 0.684 (one 1-turn win by
opponent INACTIVITY). PS Elo 1000 -> ~1340 vs a top-500 admission cutoff of
Elo ~1357; NOT LISTED, so THERE IS NO GXE YET — THE PRIMARY READ IS UNMEASURED.
A PLUMBING run, not a measurement: the stop needs n>=200 AND rd<=40. Gates
green: tallies agree 20/20, 0 decision_errors, 0 mask_desyncs, 7.6 ms/decision.
Both same-day board-scrape bugs are FIXED and **VERIFIED LIVE**: pull ok,
cutoff Elo **1357.2**, unlisted. Suite 531; L2 ckpt sha256 re-verified.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
D26 12M = 0.71825 (CREDITED HEADLINE). R2 search@M = 0.79283 (B1 CREDIT,
SH-facing), REAL and INFERENCE-ONLY (R5b B5+KILL). CH3/CH4-R1 CLOSED.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing)** | **0.79283** |
| CH4 R1 V-arms 0.71508 · our FP@20 0.3487 · hubs FP@20 0.82133 / @100 0.84000 ‡ | — |
| **LADDER R1 n=20 (PLUMBING ONLY, no GXE yet)** | **0.700** |
‡ FP's take, not ours. Never quote an anchor number as a "best".

## Next actions
1. **CONTINUE THE LADDER to n>=200** (resumable; `--battles` is a TOTAL):
   `PS_PASSWORD=$(cat ~/.ps_password) python scripts/ladder.py --prereg
   configs/eval/ladder_r1.yaml --arm L2 --battles 200`. ~9-11.5 h for the
   remaining 180, over evenings. **THROUGHPUT IS NOT OURS TO TUNE:** 229
   s/battle mean (median 184) = 8.0 s/turn set by the HUMAN opponent vs our
   7.6 ms decision (~0.1%); peak hours shorten the QUEUE only. **k=1 is
   ratified and concurrency is the ONLY real lever — do NOT raise it**, least
   of all mid-run (it splits one measurement across two protocols, and
   matchmaking pairs k in-flight battles on one stale rating). **L2 is PRIMARY,
   never L3/search**: +0.075 vs SH, NEGATIVE off-SH (clone -0.034, FP -0.020).
2. **THREE READOUT OBLIGATIONS** (pre-registered in the config header):
   (i) rating trajectory from `results/ladder/replays/*.html` (poke-env drops
   `battle.rating`; join on the NUMERIC id — tags may carry a `-<token>`
   suffix, and **local smokes share the `nickgen1rbrlbot` prefix, so filter by
   id WIDTH: real = 10-digit, smoke = 8-digit `408873xx`**); (ii) the REMATCH
   cell WITH each cell's opponent ratings (rating-matched by construction — the
   confound reads as the effect); (iii) played vs non-games, from replay TEXT.
3. Off-anchor thread CLOSED; off-SH credit line AFFORDABLE. Shelved: tau-DIV,
   POOL-SPAN, exploiter+critic. Actor ExIt KILLED.
## Watch items
- Ladder is RESUMABLE (JSONL is truth), gated on two INDEPENDENT tallies.
  **Ladder GXE is DESCRIPTIVE, never credit-line** — no A/B, no 0.025 bar.
- **THE BOARD MOVES — re-pull before quoting.** Lowest-listed GXE went 58.8 ->
  **76.4 in ONE DAY**, Elo cutoff held ~1357. ELO-ranked: no "GXE cutoff".
- **FP anchor is FP@20** (MU-2): 5.1x cheaper, strength+style equivalent, but
  marginally WEAKER (flatters us) — NAME THE BUDGET in every quote. **A clone
  h2h is NEVER style evidence**; match an anchor's policy form to its rating.
- `scripts/score_ladder.py` is a FALSE FRIEND (Connect-4 era); the real one is
  `scripts/ladder.py`. FP runner landmines FIXED (S1 orphan/|nametaken|; s64).
- `CLEANUP.md` = the audit backlog needing rulings (RESULTS.md 2 chapters stale;
  elo.py 614 dead lines; spine gate; ~6.7 GB of compression).
- results/ + the 13 sha-pinned ckpts mirrored to ../pokemon-showdown-rl-d25-
  backup-20260815/; seeds 66/67, 75/76, 83/84, 93/94 HELD. **"vs-SH ~40% GXE"
  is RETIRED — never project a ladder number.**
