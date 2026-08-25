# STATUS

Hard cap: 60 lines. Rewritten in place; newest SESSION_LOGS.md entry wins on conflict.

## Where things stand (2026-08-25 — **LADDER BUILT AND SMOKED; NOT LAUNCHED.
`scripts/ladder.py` + `configs/eval/ladder_r1.yaml` (DRAFT) + 24 offline
gates; suite 519 passed. All three arms smoked end-to-end on the local server
(ensemble 3.3 ms/decision, greedy 1.7, search@M 71.7). VOID (c) PASSES —
vendored gen1 randbats files BYTE-IDENTICAL to upstream master, 0 commits
since. Board measured first time: gen1RB top-500 = GXE 93.5 / 75.0 median /
58.8 cutoff, 93 active in 24 h. PRE-REG **RATIFIED** — PRIMARY = L2 ensemble
(the maintainer's L3/search lean was argued down on off-SH evidence), ONE arm,
stop at rd<=40 AND n>=200. ONE STEP LEFT: REGISTER THE ACCOUNT BY HAND.**)
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
1. **LADDER — RATIFIED, one manual step from launch.** PRIMARY = **L2, the
   4-lane ensemble** (0.74633 vs SH, +0.036 R0-credited; not a post-hoc lane
   pick; UNMEASURED off-SH — disclose that). **L3/search was argued down and
   MUST NOT be quietly substituted**: +0.075 vs SH but NEGATIVE on both
   off-SH opponents (clone -0.034, FP@100 -0.020), MU-8 transfer z = -2.80,
   and ~40% longer battles. One arm; A/B deferred (needs its own pre-reg
   naming a primary). Stop at **Glicko rd <= 40 AND n >= 200**.
2. **REGISTER `nick_gen1rb_rl_bot` BY HAND** (poke-env cannot); then
   `export PS_PASSWORD=...` and launch. `nick_gen1randbats_rl_bot` is a
   21-char USERID and the server REFUSES it — the cap is 18 on the userid
   (underscores are stripped, so they cost nothing).
3. Off-anchor thread stays CLOSED. Shelved: tau-DIV, POOL-SPAN, exploiter and
   critic families. Actor ExIt stays KILLED. Off-SH credit line AFFORDABLE.
## Watch items
- Ladder run is RESUMABLE (JSONL is truth), gated on two INDEPENDENT tallies,
  and loops `ladder(1)` not `ladder(n)` (pacing + per-battle resume).
- **Ladder GXE is DESCRIPTIVE, not a credit-line result** — no A/B, no 0.025
  bar. Calling it "credited" would be a category error.
- **FP anchor is now FP@20** (CLAUDE.md, MU-2): 5.1x cheaper, strength AND style
  equivalent, but marginally WEAKER (flatters us) — NAME THE BUDGET every quote.
- **A clone h2h is NEVER style evidence**; match an anchor's policy form to the
  rating it compares against. CH4 R1 credited nothing; A1 travels with quotes.
- `scripts/score_ladder.py` is a FALSE FRIEND (Connect-4-era checkpoint-rung
  scorer) — the real one is `scripts/ladder.py`. MU-8 non-transfer z = -2.80.
- Runner landmines FIXED: kill-by-subshell orphaned FP -> |nametaken| deadlock
  (S1, 3.6 h); FP's normal exit misread as a crash (s64). ladder.py aborts on
  |nametaken| rather than retrying, for the same reason.
- Suite GREEN **519 passed** (495 baseline + 24 ladder). results/ mirrored to
  ../pokemon-showdown-rl-d25-backup-20260815/. Seeds 66/67, 75/76, 83/84, 93/94
  HELD. **The "vs-SH ~40% GXE" rule of thumb is RETIRED — do not project a ladder
  number; see prior_work/README.md's conversion note + new measured-board section.**
