# GEN4_WANG50M — readout provenance

The account is `RESULTS.md` §19. This file is the provenance: what ran, from
what, with which commands, and every raw record behind a quoted number. The
data itself (`runs/`, `results/`) is gitignored.

## Identity

| | |
|---|---|
| pre-reg | `configs/gen4_wang50m.yaml` (sha256 `daa17a01…`, last touched 9918d38, 2026-09-05) |
| sidecar | `configs/gen4_wang50m.prereg.yaml` — `ratified_decisions` carries RW-1…RW-6 |
| byte pin | `tests/test_gen4_prereg.py` (9 gates) |
| launch sha | `d51fa6f` (attempt 2) |
| readout sha | `a0a8bd7` + this commit |
| journey step | 3 → 4 → 5, and step 7 (record) is this readout |
| lanes | `runs/gen4_wang50m_s200`, `_s208`, `_s216` (seeds 200/208/216; spares 224/232/240 unused) |
| freeze | OBS_DIM 1,448 / priv 703, layout v0.1; corpus `b72dcbc7…`; fixture `16eb40c7…`; sets `eacca5f3…`; Showdown `59da482e…`; vocab [301,183,41,102]; params actor 674,763 / critic 543,553 |

## Timeline (UTC)

| when | what |
|---|---|
| 2026-09-06 03:08:42 | attempt 1 launched at `8858393` |
| 2026-09-06 03:21:13 | attempt 1 OPS-KILLED (gen-4 pool-seat mask desync cap); archived `runs/aborted_20260906_0308Z/` |
| 2026-09-06 03:40:18 | **attempt 2 launched at `d51fa6f`** (860 passed, 2 live tests deselected — `logs/gen4_launch_seq.log`) |
| 2026-09-06 10:55 | incident 2: s216 died on the in-loop eval outcome guard; fixed `07f587d` |
| 2026-09-06 11:32 | all three lanes rolled onto the fix (`scripts/gen4_wang50m_watch.sh`, `.rollover`) |
| 2026-09-06 11:30 | RW-1 and RW-4 ruled in chat at the defaults |
| 2026-09-07 12:46 | 25M in-run read: all gates PASS, D-A exact at x=0.499599 |
| 2026-09-09 00:29:03 | s200 COMPLETE |
| 2026-09-09 01:08:03 | s208 COMPLETE |
| 2026-09-09 01:29:03 | s216 COMPLETE → **FLEET DONE** (≈ 69.8 h wall) |
| 2026-09-09 01:31:58 | post-fleet schedule launched BY HAND (see the ops note) |

## Resume ledger

s216 ×3, s200 ×1, s208 ×1. Merged history segments 2 / 2 / 4;
`history_merged.csv` rows 1,305,876 / 1,302,113 / 1,304,035; 2,503 update rows
each; last `_step` 50,000,000 on all three. Every resume splits the wandb
history into overlapping offline runs and loses at most one rollout of open
seat-2 rows.

## Raw records behind every quoted number

**PRIMARY (vs SH, final ckpt, 3000/lane, deterministic, ties non-wins)**

| lane | win_rate | wins_from_returns | ties | return_mean | return_std | n_eff | mask_desyncs |
|---|---|---|---|---|---|---|---|
| s200 | 0.8873333 | 0.8873333 | 0.005333 | 0.780000 | 0.621504 | 3000 | 0 |
| s208 | 0.8720000 | 0.8720000 | 0.008667 | 0.752667 | 0.651787 | 3000 | 0 |
| s216 | 0.8770000 | 0.8770000 | 0.008667 | 0.762667 | 0.640057 | 3000 | 0 |

pooled equal-weight **0.878778**; se binomial (9,000) 0.003440; se
seed-clustered (k=3, sd 0.007820) **0.004515** ← the band; `seed_start` 100 on
all three lanes, so eval battle seeds are shared across lanes and the
across-lane spread is training-seed variance, not eval noise.
n=20 pre-reads (timing probes only, never results): 0.85 / 0.90 / 0.85.

**L1 MDT h2h, 500/lane** — 0.910 / 0.890 / 0.906, pooled 0.902.
**L2 FP@20 h2h, 250/lane, samples** — 75-174-1 / 74-176-0 / 71-177-2, pooled
0.293 (220 W of 750, 3 ties as non-wins), 1.58 / 1.58 / 1.61 s/battle.
**L3 FP@500 h2h, 5 × 50/lane** — 77-172-1 / 65-185-0 / 56-194-0, pooled 0.2640 (198 W of 750); per-chunk records
in `results/gen4_wang50m/q38_pin.json`; 0 crash_forfeits (VOID threshold > 5/lane) (tally = SUM of chunk records).
**L4 clone(FP@20) h2h, 500/lane** — 0.986 / 0.988 / 0.982, pooled 0.9853.
**Q38 pin** — diff 0.029333, se_diff 0.023140 (binomial pooled), rule "pin the LOWER rung if
|p20 - p500| < 2*se_diff" -> **pin_ms 20**, later runs only (`results/gen4_wang50m/q38_pin.json`).
**S-SHAPE, 10 rungs × 3 × n=1000** — see RESULTS §19's table; pooled 0.8277 at
5M rising to 0.8800 at 50M.
**Sanity rows** (not legs): MDT vs SH 0.400 (120-173-7, n=300); clone vs SH
0.464 (n=1000, ties 0.022); FP@20 vs SH 226-24-0; FP@500 vs SH 228-22-0.

## Gate table (all PASS, all three lanes)

| gate | s200 | s208 | s216 |
|---|---|---|---|
| R0-1 entropy ≤250k (1.3–2.1) | 1.757–1.810 | 1.773–1.813 | 1.770–1.821 |
| R0-2 clip_frac == 0 | 0/2503 | 0/2503 | 0/2503 |
| R0-3 harvest ratio (0.7–1.3) | 0.901–1.059 | 0.967–1.032 | 0.959–1.043 |
| R0-4 first eval win_rate @250k | 0.310 | 0.320 | 0.470 |
| R0-6 non-finite loss/* | 0 | 0 | 0 |
| H1 rung buckets breached | 0/100 | 0/100 | 0/100 |
| K6 entropy min (floor 0.15) | 0.740 | 0.747 | 0.748 |
| T2 clip_frac max (STOP ≥0.90 ×3) | 0.175 | 0.177 | 0.189 |
| T3 approx_kl max (STOP ≥0.5 ×3) | 0.0023 | 0.0022 | 0.0023 |
| D-B median steps/s (expected **203**) | 202 | 198 | 197 |
| D-B conforming windows | 133/134 | 134/136 | 134/136 |
| D-C in-loop evals (NOT ACTIONABLE) | 200 | 200 | 200 |
| D-D selfplay/winrate_latest | 0.500 | 0.500 | 0.499 |

**D-A**, the (u−1) form, EXACT to 1e-12 relative on all three lanes, actor ==
critic: 5M u=250 x=0.099441 lr 2.447429e-05; 25M u=1252 x=0.499599 lr
5.271813e-06; 50M u=2504 x=0.999598 lr 2.182058e-06. Realized minimum lr0/26.99.

**R0-5 caveat.** It PASSes, but the post-hoc read measures the first rung
against the LAST launch line — a RESUME after the 11:32Z rollover — so it
prints negative minutes (−420 / −431 / −407). R0-5 was satisfied at attempt-2
launch, not by this read.

## Ops note — the auto-chain deadlock, found at FLEET DONE

The session watcher that was to auto-chain the schedule would have refused
forever: its own command line contains the literal strings `python -m rl.train`
and `gen4_wang50m`, so BOTH its own guard and
`scripts/gen4_wang50m_postfleet.sh`'s step-0 check
(`pgrep -f "rl.train.*gen4_wang50m"`) matched THE WATCHER ITSELF. The watcher
was stopped and the schedule launched directly at 01:31:58Z after verifying
`pgrep -f "bin/python -m rl.train"` == 0 and all three `ckpt_050000000.pt`
present at 14,318,259 bytes each. **Fix for any future guard: anchor the
pattern on the interpreter path (`bin/python -m rl.train`), never on a bare
module name a watcher may also mention.**

## Exact commands

```
# training (per lane, attempt 2)
python -m rl.train --config configs/gen4_wang50m.yaml --seed <200|208|216> \
    --run-name gen4_wang50m_s<seed>
# resumes
python -m rl.train --resume runs/gen4_wang50m_s<seed>
# the frozen post-fleet schedule (order is frozen in the script's header)
nohup bash scripts/gen4_wang50m_postfleet.sh > /dev/null 2>&1 < /dev/null &
# histories (resumes split them; this is the only correct input)
python scripts/merge_history.py runs/gen4_wang50m_s<seed>
# gates, per lane
python scripts/gen4_wang50m_gates.py runs/gen4_wang50m_s<seed> \
    --history runs/gen4_wang50m_s<seed>/history_merged.csv \
    --da-checkpoint runs/gen4_wang50m_s<seed>/ckpt_050000000.pt
# the primary sentence is printed, never composed by hand
python scripts/gen4_wang50m_readout.py results/gen4_wang50m/final_s*.json \
    --out results/gen4_wang50m/primary.json
```

## Rendered summary

A one-page rendering of this readout (verdict, the number line against Wang's
three published figures, the S-SHAPE curve, the gate chips, the disclosures and
the next steps) is published as a private artifact:
<https://claude.ai/code/artifact/c63edab6-0119-41f3-899a-030d06e5c389>. It is a
VIEW, never the source: every number there is transcribed from
`results/gen4_wang50m/` and this file is canonical on any conflict. The page's source
is committed beside this file as `readouts/gen4_wang50m_readout.html`, so the artifact
is reproducible from a clone; it is published without the `<!doctype>`/`<head>`
wrapper, which the Artifact host supplies. Editing it and republishing to the SAME
URL keeps the link — publishing a different file path would create a second artifact.

## What this readout may not be used for

vs-SH is not a ladder number, in either direction. No lever is credited. The
gen-4 ladder is banked and unrun, so nothing here speaks to gen-4 ladder
strength. `pool_size: 1` was Wang-match fidelity only and is not evidence
about league play. Anchors are descriptive and never verdict inputs.
