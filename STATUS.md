# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25 — **LADDER READINESS ASSESSED. Verdict:
the BUILD is cheap (~an evening) and the 2026-08-23 deferral is SATISFIED,
but do NOT let it out yet — what is missing is a PRE-REG, not code. The
board was measured for the first time: gen1RB top-500 = GXE 93.5 best /
75.0 list-median / 58.8 cutoff, Glicko 2022/1712/1568, 93 players active in
24 h. HANDOFF's "real ladder play is new construction" was OVERPRICED:
poke-env 0.15.0 ships ShowdownServerConfiguration + native Player.ladder(),
SeatPlayer (scripts/ch3_fp_h2h.py) is already server-agnostic, battle.rating
is native, GXE is an unauthenticated GET, and search@M at 65-75 ms/decision
is nowhere near the timer. CH4 R1 stays CLOSED; no headline moved.**)
**Pure from-scratch self-play in gen1randombattle; THE NOVELTY IS THE LANE.**
D26 12M = 0.71825 (CREDITED HEADLINE). R2 search@M = 0.79283 (B1 CREDIT,
SH-facing). Search is REAL and INFERENCE-ONLY (R5b B5+KILL). CH3/CH4-R1 CLOSED.

## Results (vs SH; ties=loss; locked = final ckpt)
| result | win rate |
|---|---|
| D26 12M HEADLINE 0.71825 · R0 ensemble 0.74633 · D29r2 50M 0.70222 | — |
| **CH3 R2 search@M — B1 CREDIT, BEST (caveat: SH-facing)** | **0.79283** |
| CH4 R1 V-arms in-session vs SH (era pin PASS) | 0.71508 |
| CH4 R1 our FP@20 rate, 4 lanes x 3000 (mean; s_T 0.0077) | 0.3487 |
| CH4 R1 hubs: FP@20 vs SH 0.82133 · FP@100 vs SH 0.84000 (G6 PASS) | ‡ |
‡ FP's take, not ours. Never quote an anchor number as a "best".

## Next actions
1. **LADDER: the answer is "build it, don't launch it."** Five open
   decisions, all the maintainer's, none technical — (a) no pre-reg exists
   and no gen1RB peer row exists, so what the number MEANS is undefined;
   (b) which policy ships (search@M is our best but its increment measured
   NON-TRANSFERRING at z = -2.80) and in which FORM (deterministic vs
   sampling, now that repeat opponents are certain); (c) ladder accounting
   (timer losses/DCs/ties, stopping rule, one account or per-seed alts);
   (d) public exposure + etiquette (PS rules do NOT ban bots; Metamon's own
   repo says they turned "a lot more cautious about laddering"); (e) a
   one-diff check that the live gen1 sets still match vendored 59da482.
2. Off-anchor thread stays CLOSED. Shelved, NOT re-opened: tau-DIV, POOL-SPAN,
   exploiter family, critic family. Actor ExIt stays KILLED. Off-SH credit line
   is AFFORDABLE (0.025 floor, 4 lanes) if a future lever wants one.
## Watch items
- **Ladder build items already FREE** (do not re-price): auth, ladder(), rating
  capture, GXE scrape, latency. NOT built: the runner, day-spanning
  resumability, a results file.
- **CH4 R1 credited nothing**; Amendment A1 (result-blind) travels with every quote.
- **FP anchor is now FP@20** (CLAUDE.md, MU-2): 5.1x cheaper, strength AND style
  equivalent, but marginally WEAKER (flatters us) — NAME THE BUDGET every quote.
- **A clone h2h is NEVER style evidence**; match an anchor's policy form to the
  rating it compares against (~26 pts = the "clone intransitivity").
- `scripts/score_ladder.py` is a FALSE FRIEND (Connect-4-era checkpoint-rung
  scorer). Old P2 rider SUPERSEDED (MU-8): non-transfer z = -2.80.
- Runner landmines FIXED: kill-by-subshell orphaned FP -> |nametaken| deadlock
  (S1, 3.6 h); FP's normal exit misread as a crash (s64).
- Suite GREEN 495 passed (last run 2026-08-25). Tree clean, **fully pushed**
  (the old "commits after 60d73fc unpushed" line was stale). results/ mirrored to
  ../pokemon-showdown-rl-d25-backup-20260815/. Seeds 66/67, 75/76, 83/84, 93/94
  HELD. **The "vs-SH ~40% GXE" rule of thumb is RETIRED — do not project a ladder
  number; see prior_work/README.md's conversion note + new measured-board section.**
