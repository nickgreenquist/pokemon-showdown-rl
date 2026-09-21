# Handoff — R6 launch night, written 2026-09-21 13:10Z at the maintainer's request (context at 70%)

**Read in this order:** this file → `STATUS.md` → the two trio headers (`configs/showdown_r6_trio_a.yaml`,
`configs/showdown_r6_trio_b.yaml`) → `configs/showdown_r6_batch12m.yaml`'s header → SESSION_LOGS entries
dated 2026-09-20 (cont.) and 2026-09-21. **Do not re-derive anything below; execute it.** The plan is
ratified (six rulings 2026-09-20); everything that could be pre-built is committed on `main` at `9a63a88`
(tree clean, nothing pushed).

## 0. THE DEADLINE

**The maintainer wants the fleet launch blocks by 21:00 EDT today = 01:00Z 2026-09-22** ("if you don't have
my commands for me by 9pm, I'll probably be asleep"). The box's local clock is EDT (UTC−4).

## 1. WHAT IS RUNNING — check first, then RE-ARM THE WATCH (the old session's monitor is gone)

The exit-gate queue (`scripts/exit_gate_queue.sh`, frozen copy, `caffeinate -i`): GAP done (RESULTS §33),
XSM done, **XGR done 00:35Z: 0.5866 (n=3200, ties 2)**, **XTG9 RUNNING** since 00:36Z at ~24.3 s/battle
(1835/3200 at 12:59Z) → **QUEUE DONE ≈ 22:10Z (18:10 EDT)**; it then prints `results/exit_gate_r5/READOUT.txt`.
```
tail -3 logs/exit_gate_r5/queue.log
```
```
grep -c Winner results/exit_gate_r5/xtg9.fp.stdout
```
Stalled = the count stops for ~10 min or the search seat's CPU time (`ps -o time= -p $(pgrep -f 'ch3_fp_h2h.py.*--arm XTG9')`
twice, 15 s apart) does not advance. **NOTHING starts on the box before QUEUE DONE** (no training lane, no
second FP block, no heavy CPU): the tree arm's opponent is wall-clock budgeted and a one-sided load bias
would push the gate toward a false clear. Re-arm a watch on `logs/exit_gate_r5/queue.log` for
`QUEUE DONE|NO FINAL|REFUSING|FAIL` (a background `until` loop or a persistent Monitor; poll every 2 min;
also fail if `pgrep -f exit_gate_queue` finds nothing).

## 2. THE RUNBOOK AT QUEUE DONE (agent; in this order; every command from the repo root)

0. Verify: queue.log shows `QUEUE DONE`; `pgrep -f 'foul-play/bin/python run.py'` empty; `git status` clean;
   `lsof -nP -iTCP:8000 -sTCP:LISTEN` shows Node; `/opt/anaconda3/envs/pkmn-engine-port/bin/python -c 'import pkmn_gen1; print(pkmn_gen1.ENCODER_C6)'` → True.
1. **Launch the 4.12 screen** (2 lanes × 12M, ~2.6 h; ratified as agent-run, plan §3 item 8):
   ```
   ALLOW_ANNEAL_OVER_HORIZON=1 bash scripts/monster_fleet.sh configs/showdown_r6_batch12m.yaml 12000000 204 212
   ```
   Run dirs `runs/showdown_r6_batch12m_s204` / `_s212` (the launcher names dirs `runs/<config basename>_s<seed>`
   and overrides the config's `run_name`). Note the launch time.
2. **Smoke A beside the screen** (disclose the window in the screen read; only `time/*` is affected):
   ```
   bash scripts/monster_fleet.sh configs/showdown_r6_trio_a_smoke400k.yaml 400000 904
   ```
   → `runs/showdown_r6_trio_a_smoke400k_s904`. PASS = reaches 400k; `meta.yaml` has `encoder.c6: true`,
   `aux_outcome_coef: 0.1`, `params.actor: 626059`, `params.critic_aux_outcome: 3075`; after `ckpt_000200*.pt`
   exists, **the RESUME test**: kill the lane's `rl.train` (`pgrep -f 'run-name showdown_r6_trio_a_smoke400k_s904'`),
   watch `runs/train_watchdog.log` for `RESUMED ... c6=1`, let it finish; then
   `python scripts/extract_history.py runs/showdown_r6_trio_a_smoke400k_s904` and confirm `aux_outcome/ev_*`,
   `loss/aux_outcome` and `l2init/*` present and moving in `history.csv`.
3. **Smoke B (GO keys)** then **smoke B-fallback**, one at a time (~5 min each; check `encoder.c6: true`, `l2init/*`):
   ```
   bash scripts/monster_fleet.sh configs/showdown_r6_trio_b_smoke400k.yaml 400000 912
   ```
   ```
   bash scripts/monster_fleet.sh configs/showdown_r6_trio_b_fallback_smoke400k.yaml 400000 920
   ```
4. **Meanwhile, bank the exit gate:** fill `readouts/EXIT_GATE_R5_READOUT.md` (skeleton committed; the rule,
   R0 gates and the contamination ledger are already in it) from `results/exit_gate_r5/READOUT.txt` +
   `xtg9.json`; RESULTS §35 addendum; IDEAS 4.9 + 8.6 rows; STATUS; log. The verdict rule: clears at
   ≥ +0.025 AND ≥ 2·se_diff (XTG9 − XGR, 3200 vs 3200) → 4.9 gets R7's first trio; otherwise 4.9 is closed on
   this object for R7 by a measured bound on the operator (never "a null"). Report `search/ms_mean`,
   `tree/kl_pi_prior`, `tree/pi_top1`, `tree/argmax_moved`, `search/overrode` beside the win rates; both
   FP@20 disclosures travel; `G_BUDGET_REALIZED` needs ms/decision within ~2× of 766.6. Commit.
5. **When both screen lanes are DONE** (`runs/train_watchdog.log`): 
   ```
   /opt/anaconda3/envs/pokemon-showdown-rl/bin/python scripts/r6_batch12m_read.py --json-out results/r6_batch12m/read.json
   ```
   prints GO or FALLBACK (the rule is operationalized in the script and the config header; the W lane s104
   passes it against s112/s120). Record the verdict and the three smoke results in BOTH trio headers' STATUS
   line; if FALLBACK, trio B launches from `configs/showdown_r6_trio_b_fallback.yaml` **with
   `TAG=showdown_r6_trio_b`** so its run dirs stay `runs/showdown_r6_trio_b_s*` (the pins and the reads queue
   expect those). Commit; the launcher refuses a dirty tree.
6. **Post the launch blocks** (§3). If the screen runs late, post trio A's block as soon as smoke A passed
   (~19:00 EDT) and trio B's when the verdict lands. A smoke failure → diagnose, do NOT hand over that trio.

## 3. THE MAINTAINER'S LAUNCH BLOCKS (one command per block, no comments; wrap in <command> sentinels)

Box prep (password; once): `sudo pmset -c sleep 0 disksleep 0`; System Settings → Software Update →
automatic updates OFF; lid OPEN; quit VS Code and Chrome.
Trio A: `bash scripts/monster_fleet.sh configs/showdown_r6_trio_a.yaml 200000000 304 312 320`
Trio B, ~2 min later, ONE of:
  GO: `bash scripts/monster_fleet.sh configs/showdown_r6_trio_b.yaml 200000000 328 336 344`
  FALLBACK: `TAG=showdown_r6_trio_b bash scripts/monster_fleet.sh configs/showdown_r6_trio_b_fallback.yaml 200000000 328 336 344`
Watch: `tail -f runs/train_watchdog.log`. ~48–50 h six-wide. The launcher preflights everything (clean tree,
Node, simulator 4, encoder flags + the C6 marker + the extension, anneal == horizon, distinct seeds).

**Open questions put to the maintainer (unanswered as of this handoff):** (i) if the verdict lands after 21:00
EDT, may the agent launch trio B itself (a one-off rule-4 authorization), or does it wait for the morning?
(ii) launch trio A early (~19:00 EDT) or both together?

## 4. AFTER THE FLEET (all built; nothing to write)

`scripts/r6_reads_queue.sh` (waits for all six `DONE` lines, pins via `scripts/monster_reads_pin.py --trio a|b`,
runs `configs/eval/r6_reads_offfp.yaml` then `configs/eval/r6_reads.yaml`, then `scripts/r6_reads_readout.py`):
```
nohup bash scripts/r6_reads_queue.sh > logs/r6_reads/queue.nohup 2>&1 &
```
(arm it once the fleet is running; it holds until DONE; ~22 h of arms). Then the BC-clone leg (500) and trio A's
mechanism read (`scripts/outcome_variance.py` on the A finals → `scripts/critic_calibration.py --label ...`
and `--compare` against the R5 W finals' calibration JSON; the 2–8 bucket must lift above 0.287), RESULTS/README
rows, then finalize `docs/proposals/ladder_r6.draft.yaml` (M-R6-1 from the reads readout's rule R2; M-R6-2..7
recommended defaults) → `git mv` to `configs/eval/ladder_r6.yaml` at ratification; the split schedule = four
supervisor launches with cumulative targets 50/100/150/200 on different days.

## 5. LANDMINES LEARNED 2026-09-21 (also in the log; carry them)

- **The launcher names run dirs from the CONFIG BASENAME + seed and overrides `run_name`**; a differently-named
  config (the fallback) needs `TAG=` to land in the expected dirs. Every pin/queue/header was aligned to this.
- **A pre-stated mechanism criterion must pass its own REFERENCE**: "entropy still falling" as a monotone
  test failed the W lanes themselves (their entropy plateaus ~0.70 from 2M); operationalized before the screen
  ran and recorded in the config header.
- **A chunked CSV scan must stop on the UNFILTERED max step** (a one-chunk test hides the bug).
- **The attention screen's fits ran beside the exit-gate arms** (ledger in the readout skeleton); nothing else
  may run beside XTG9 now.
- **`pip install -e` of the engine extension needs the port env's bin on PATH** (maturin by name); the importable
  module changes only on install.

## 6. NUMBERS TO CARRY (each traced)

- XGR 0.5866 (n=3200, ties 2; `results/exit_gate_r5/xgr.json`). XSM smoke: ms 844.3, KL 1.8847, pi_top1 0.734,
  argmax_moved 0.176 (`smoke_xsm.json`).
- Action gap: naive 0.0317 [0.0220, 0.0426], deconvolved 0.0241, noise-only 0.0290 (RESULTS §33).
- Attention screen: Δagreement +0.0179 [+0.0143, +0.0214], 6.52× throughput, flat reveal profile (RESULTS §34).
- C6 port: P-1 30,000 decisions zero mismatches flag on; 20,000 off. Suite bare 1258/87/0 at `2d20cf7`.
- W lanes' first 12M (the screen's reference): kl 0.03–0.046, entropy 1.34 → 0.70, EV 0.49 → 0.69.

## 7. Safe to trust / needs care

- **Trust:** every readout in `readouts/`, the trio configs' diff sets (tests), the reads pre-regs (tests), the
  screen read on its reference.
- **Care:** the exit-gate delta until XTG9 finished in this session with no relaunch; trio B's keys until the
  screen's verdict is recorded; the smokes have NOT run yet (nothing under `runs/showdown_r6_*` exists).
