# Handoff — written 2026-08-11 (late night), D18 lanes RUNNING

Read this, fold anything durable into STATUS.md / SESSION_LOGS.md, restore the empty
stub. STATUS.md + SESSION_LOGS.md are current through the D18 launch-record entry.

## State: green, committed through 9f932c9 (LOCAL — push not authorized), 5 LANES LIVE

**D18 privileged-critic rung is RATIFIED (5 lanes) and RUNNING**: seeds 39-43,
launched ~23:00 2026-08-11 via nohup+disown+caffeinate (maintainer-authorized
agent launch, "ratify 5 and launch"), detached — they survive any session end.
~300 steps/s/lane at 5-wide → finals land ~09:00-10:00 2026-08-12. Suite 279
green. Server up on :8000 (simulator: 4). Runs: runs/showdown_sp_priv12m_s{39..43}
(logs runs/priv_s*.nohup.log). Check liveness: `pgrep -f 'rl[.]train.*priv12m'`
(expect 5) + newest ckpt_*.pt mtime per run dir. Launch checks all passed
(git_dirty false @ c6e6d87, both priv flags in every config snapshot, mismatch
guard silent). A session monitor was watching the fleet — it DIED with that
session; re-arm one if desired (1M-milestone pattern in the session log) or just
check ckpt files.

## The one thing that matters: THE D18 READOUT (when lanes finish)

Config header = the contract: configs/showdown_sp_priv12m.yaml (RATIFIED, revised
per the 3-agent review — read it before grading). Protocol:

1. Per lane: locked eval of FINAL checkpoint.pt, 3000 battles, BOTH env vars
   (scripts/score_ladder.py is the honest path; eval_checkpoint.py works too).
   Idle-box ~3 min each. Then the same for each lane's best_checkpoint.pt
   (val-peak CO-PRIMARY, recorded-not-credit-bearing).
2. CREDIT (larger-of rule, verbatim in header): pooled Δ vs 0.5509 ≥ +0.025 AND
   ≥ 2·se_diff, se_diff = LARGER of pooled-binomial (0.0066 at 5v3 lanes) and
   seed-clustered (comparator term 0.0150 is a FLOOR → bar ≥ 0.5809; ~0.589 at
   Rung-2-like spread). Letter-met-but-unclaimable band → pre-stated recording
   rule: "letter-met, seed-fragile, NOT credited."
3. FALSIFIER (live — see below): EV up but wr flat/negative → KILL the rung.
4. Secondaries: EV trajectory vs control curves; D22-watch (per-lane grad_norm
   median per 1M bin — s37-class = median >100 for 3 consecutive bins →
   regenerative-L2 jumps queue); srank read needs BOTH d22 scripts adapted first
   (priv-carrying tapes + privileged_dim build — scoped in header, post-run).
5. Docs: log entry + STATUS rewrite + README per readme-stays-current memory.

## Early signal (3M, recorded in log): EV separation IS present

Priv lanes EV 0.57-0.61 vs matched control 0.549-0.561 (+0.02-0.04) at 3M.
Entropy 0.30-0.41, grad norms ~0.9, R1 anchor gate passing (0.977). The
falsifier is therefore genuinely armed: EV separation without wr separation at
12M = kill, per the header's own clause.

## Do NOT rediscover

- The 3-agent review verdict (session log): ZERO code changes — do not "fix" the
  reviewed SHAs. Known-and-accepted: control critic's move subnet is dead weight
  (D18 wakes it — feature-class confound, disclosed); ~1-3% aliased seat-B rows;
  eval env computes-and-discards the block (time/eval_sec not comparable).
- Same-seed init-match across privileged_dim is IMPOSSIBLE (RNG stream shifts);
  seed-match at arm level only.
- Entity ckpts need BOTH env vars at every eval; priv ckpts additionally carry
  privileged_dim in their config snapshot (make_agent rebuilds correctly).
- Long background Bash gets REAPED (~10min+); nohup+disown works (in use NOW).
- Seeds: 0-13, 23-43 SPENT/assigned, 14-22 RESERVED, 99 disposable, 44+ free.

## Open, deliberately

1. Push: everything local through 9f932c9 — ask-first, maintainer decides.
2. After readout: credit → 50M-scale decision + D19 re-scope; null → regenerative
   L2 next (D22's named runner-up). 250M decision waits on this + seat accounting.
3. Rung 0 E1-E4 measurement evening (D12b) — still owed, needs idle box.
4. d22 script adaptation for the srank secondary (cheap, offline, post-readout).
