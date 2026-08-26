# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25 — **FIRST REAL LADDER RUN COMPLETE: 20
battles, 14-6 raw 0.700, 13-6 played 0.684 (one 1-turn win by opponent
INACTIVITY). PS Elo 1000 -> ~1340, just under the top-500 admission cutoff
of Elo ~1357; NOT LISTED, so THERE IS NO GXE YET — THE PRIMARY READ IS
UNMEASURED. A PLUMBING run, not a measurement: the stop needs n>=200 AND
rd<=40. Gates green: tallies agree 20/20, 0 decision_errors, 0 mask_desyncs,
7.6 ms/decision, 3.8 min/battle => ~12.5 h for 200. TWO BUGS FIXED AFTER the
run: the board scrape 403'd on EVERY call (urllib default UA is blocked), and
a fetch failure was indistinguishable from "not listed" — so the stopping
rule could never have fired. Also CORRECTED a same-day error of ours: the
toplist is ELO-RANKED, so there is no "GXE cutoff". Suite 531 passed.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
D26 12M = 0.71825 (CREDITED HEADLINE). R2 search@M = 0.79283 (B1 CREDIT,
SH-facing). Search is REAL and INFERENCE-ONLY (R5b B5+KILL). CH3/CH4-R1 CLOSED.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing)** | **0.79283** |
| CH4 R1 V-arms vs SH 0.71508 · our FP@20 rate 0.3487 (s_T 0.0077) | — |
| CH4 R1 hubs: FP@20 vs SH 0.82133 · FP@100 0.84000 (G6 PASS) ‡ | — |
| **LADDER R1 n=20 (PLUMBING ONLY, no GXE yet)** | **0.700** |
‡ FP's take, not ours. Never quote an anchor number as a "best".

## Next actions
1. **CONTINUE THE LADDER to n>=200** (resumable; `--battles` is a TOTAL):
   `PS_PASSWORD=$(cat ~/.ps_password) python scripts/ladder.py --prereg
   configs/eval/ladder_r1.yaml --arm L2 --battles 200`. ~12.5 h at 3.8
   min/battle; spread over evenings. It now self-terminates at rd<=40 AND
   n>=200 (it could NOT before). **L2 is PRIMARY, never swap in L3/search**:
   +0.075 vs SH but NEGATIVE off-SH (clone -0.034, FP -0.020), MU-8 z=-2.80.
2. **THREE READOUT OBLIGATIONS** (pre-registered in the config header):
   (i) rating trajectory rebuilt from `results/ladder/replays/*.html`
   (poke-env drops `battle.rating`; join on the NUMERIC id — tags may carry
   a `-<token>` suffix); (ii) the REMATCH cell WITH each cell's opponent
   ratings (rematches are rating-matched; the confound reads as the effect);
   (iii) played vs non-games, classified from replay text.
3. Off-anchor thread CLOSED. Shelved: tau-DIV, POOL-SPAN, exploiter+critic
   families. Actor ExIt KILLED. Off-SH credit line AFFORDABLE.
## Watch items
- Ladder is RESUMABLE (JSONL is truth), gated on two INDEPENDENT tallies, loops
  `ladder(1)` not `ladder(n)`. **Ladder GXE is DESCRIPTIVE, not a credit-line
  result** — no A/B, no 0.025 bar; calling it "credited" is a category error.
- **FP anchor is FP@20** (MU-2): 5.1x cheaper, strength+style equivalent, but
  marginally WEAKER (flatters us) — NAME THE BUDGET in every quote.
- **A clone h2h is NEVER style evidence**; match an anchor's policy form to its
  rating. CH4 R1 credited nothing; A1 travels with every quote.
- `scripts/score_ladder.py` is a FALSE FRIEND (Connect-4 era) — the real one is
  `scripts/ladder.py`. Runner landmines FIXED: kill-by-subshell orphaned FP ->
  |nametaken| deadlock (S1, 3.6 h); FP's normal exit misread as a crash (s64).
- `CLEANUP.md` = the audit backlog needing rulings (RESULTS.md is 2 chapters
  stale; elo.py 614 dead lines; spine gate; ~6.7 GB of compression).
- Suite GREEN **531**. results/ + the 13 sha-pinned ckpts mirrored to
  ../pokemon-showdown-rl-d25-backup-20260815/. Seeds 66/67, 75/76, 83/84, 93/94
  HELD. **"vs-SH ~40% GXE" is RETIRED — never project a ladder number.**
