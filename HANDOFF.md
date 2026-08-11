# Handoff — written 2026-08-11 (morning), after the 50M chapter closed

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty
stub. STATUS.md + SESSION_LOGS.md are current through the FP-guard-close entry — do
not restate them.

## State: green, PUSHED through f27bea2, nothing running

Tree clean; `origin/main == main` at f27bea2 (this handoff commit may be local —
pushing stays ask-first). Suite 267 green (NO code changed since — this was a
docs/eval/design session; rl/ untouched). Showdown server UP on :8000 (pid 74836,
`simulator: 4`). No lanes, no evals, no monitors/crons (all four session crons
deleted). Stray: one bare `caffeinate` (pid 70074, pre-existing, not ours).

## The one thing that matters

**The chapter ledger is fully settled — there are NO open measurements or pending
maintainer decisions. NEXT WORK, per ratified §12 (D18–D22 binding, 2026-08-11):**

1. **D22 PLATEAU DIAGNOSTICS first** (~one evening, mostly offline): five reads on
   the existing 50M artifacts (EV, entropy, weight-norm trajectory over ~100
   ckpts/lane, dormant/effective-rank, exploitability probe = fresh best-response vs
   frozen final). Decision rule pre-stated in §12 routes what runs next. Bonus
   question it should answer: why s35 surged (0.659) while s37 flatlined (0.509).
2. **Then D18 privileged critic** (~2–3 evenings plumbing first): cross-seat
   registry through the collection path; critic input = actor-obs ‖ opponent's
   own-side blocks (BINDING: never privileged-only — Baisero & Amato unbiasedness).
   Novelty verified 2026-08-10 ("no documented instance found" phrasing, binding).
   Its pre-reg header MUST restate the FULL §8 credit line incl. larger-of se_diff
   (2026-08-11 adjudication process fix, now in CLAUDE.md).

Ledger, for orientation only (details in STATUS/log): M1–M3 CLAIMED at 12M (0.5509);
50M CREDIT 0.5802 pooled, seed-fragility a NAMED WEAKNESS (adjudicated — header
letter governs); M4 UNCLAIMED (+0.3σ margin); anchor guard CLOSED (clone h2h 0.643,
FP 0.812-against vs 0.824 at 12M); best-ckpts pooled 0.6153 (selection caveat).

## Do NOT rediscover these (session-hot; the rest is in the logs)

- **Long-sleeping background Bash tasks get REAPED by the harness** (~10 min+; it
  happened twice). Pattern that works: `nohup ... & disown` + a cron backup check;
  delete the cron when done.
- Idle-box evals are FAST: ~3 min per 3000-battle eval, ~6.5-10 s/battle for FP
  reads. The "~1 h" folklore was contention with training lanes.
- FP harness pairing: seat listener FIRST (scripts/foulplay_vs_sh.py --seat <ckpt>),
  then FP from ../foul-play (conda foul-play): run.py --websocket-uri
  ws://localhost:8000/showdown/websocket --ps-username X --bot-mode challenge_user
  --user-to-challenge Y --pokemon-format gen1randombattle --run-count N
  --search-time-ms 100 --search-parallelism 1. Smoke 5 first, always. Usernames
  seat50m/fp50m are SPENT; use fresh ones.
- Entity ckpts need BOTH env vars at every eval (v2+ids→828); 807 refused by shim.
- Seeds: 0-13, 23-37 SPENT, 14-22 RESERVED (warmrl), 99 disposable, **38+ free**.
- Next pre-reg header wishlist (recorded in log): full credit line verbatim (above),
  val-peak-re-graded co-primary (best-ckpt gap was +0.035 pooled at 50M), n=1000
  in-training evals every 500k (~50 s each, measured).

## Open, deliberately (inherited work, none blocking)

1. Rung 0 E1-E4 measurement evening (D12b) — needs an idle box; feeds D15.
2. H&L seat accounting from metagrok — gates any 250M QUOTE, not D22/D18.
3. 250M decision itself — NOT auto-bought (seed-fragile slope); waits on D22.
4. D19 (after D18, shared plumbing), D21 singles, D20 v3 bundle post-chase.
5. RESEARCH_BRIEF.md is a dated snapshot (2026-08-10) — refresh if handed out again.
