# Handoff — R2 monitor session (written 2026-08-29, maintainer-ordered)

You are the MONITOR for the CH5 R2 batch-lever training fleet (JOURNEY
step 1). The pre-reg cycle is DONE (SESSION_LOGS 2026-08-29 evening); the
pre-reg is `configs/showdown_sp_batch50m.yaml` (training half — read its
Q6 gates and Q8 ops before anything else) + `configs/eval/ch5_r2_offsh.yaml`
(read half). STATUS.md has the arc. The Showdown server is already up on
:8000 (fresh instance, started ~13:45 EDT 2026-08-29 after killing a stale
one from 08-28). The maintainer runs Opus/high in this session and will
CHAT with you while the lanes run — answer in one or two lines until
everything is done (standing preference); full write-ups only at the end.

## FIRST MESSAGE: print the launch sequence, exactly this, in this order

Per CLAUDE.md handed-over-command rules (one command per fenced block,
`<command>`/`</command>` sentinels OUTSIDE the fence, no inline comments).
NOTE beside block 1: launching COMPLETES RATIFICATION of the pre-reg (the
D29r2 precedent), including its Q10 escalations E1-E5/ADJ-1..3.

1. Gate chain (must end green):
   `cd ~/Documents/Projects/pokemon-showdown-rl && git status --porcelain && grep -nE "^[^/]*simulator: *4" showdown/config/config.js && nc -z localhost 8000 && /opt/anaconda3/envs/pokemon-showdown-rl/bin/pytest tests/test_ch5_r2_prereg.py -q && env POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 /opt/anaconda3/envs/pokemon-showdown-rl/bin/pytest tests/test_anneal_aux_group.py -q && /opt/anaconda3/envs/pokemon-showdown-rl/bin/python scripts/ch5_r2_grade.py --selftest`
2. Lane 1:
   `cd ~/Documents/Projects/pokemon-showdown-rl && caffeinate -is env POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 WANDB_MODE=offline nohup /opt/anaconda3/envs/pokemon-showdown-rl/bin/python -m rl.train --config configs/showdown_sp_batch50m.yaml --seed 66 --run-name showdown_sp_batch50m_s66 > runs/showdown_sp_batch50m_s66.nohup.log 2>&1 &`
3. Verify lane 1 by battle PROGRESS (~60 s later, run twice, dir must grow):
   `cd ~/Documents/Projects/pokemon-showdown-rl && tail -5 runs/showdown_sp_batch50m_s66.nohup.log && ls -la runs/showdown_sp_batch50m_s66/`
4. Lane 2: same as block 2 with `--seed 75 --run-name showdown_sp_batch50m_s75`
   (and its own nohup log name). Wait ~60 s, verify as in block 3.
5. Lane 3: `--seed 83 --run-name showdown_sp_batch50m_s83`. Verify.

## MONITORING — the numbers are all in the training half's Q6; summary:

- **D-B** (from ~1M): warm dStep/dWall over >=30 min, NEVER
  `time/steps_per_sec`. Expected 385-405/lane 3-wide; RECORD <371;
  RECORD <330; STOP AND INVESTIGATE <275.
- **D-E / R0-h** (any time): per-lane RSS — RECORD >3.0 GB, STOP >4.5 GB
  or on sustained swap. This is the lever's ONE new failure mode.
  `ps -o rss=,command= -p $(pgrep -d, -f "rl.train")`
- **D-D** (at 4M, each lane): `selfplay/winrate_anchor >= 0.75`; expected
  0.90-0.96 (control read 0.9716/0.9712/0.9742). ~130 updates in.
- **K6** (before 25M): 3-lane median `loss/entropy` < 0.15 for 2
  consecutive readings -> record and STOP that check's subject per the
  gate text. **T2**: 3-lane median `loss/clip_frac` >= 0.90 x3 -> STOP.
  **T3**: median `loss/approx_kl` >= 0.5 x3, or ANY non-finite -> STOP.
  approx_kl UP TO ~30x the control's level is the EXPECTED regime (T1) —
  do not panic on it.
- Metrics: `scripts/extract_history.py runs/<run_dir>` writes history.csv
  (works mid-run); nohup logs carry stdout. Remember C-CAD: update rows
  are 1/30th the control's — bin by steps, never average raw rows.
- **NO MID-RUN CHANGES, EVER.** Every gate is record/stop-and-report.
- Lane death: `--resume runs/<run_dir>` (discards <=30,720 steps; record
  in the log + disclose later beside D-A). Spares 67/76/84 replace a lane
  ONLY pre-D-D (pre-4M), never run beside the lane they replace, never
  relaunch a dead lane on its own seat. Post-4M: lane-failure rule — dead
  is dead, report as-is.
- Box stays otherwise idle for ~35 h. NOTHING FP-related runs during
  training (wave-scoped VOID; the preflight enforces it later anyway).

## AFTER ALL LANES FINISH (agent-side, detached, resume-safe — allowed):

Follow `configs/eval/ch5_r2_offsh.yaml` Q8's BINDING ORDER: (1) vs-SH
finals via `scripts/eval_checkpoint.py runs/showdown_sp_batch50m_sN/checkpoint.pt
--episodes 3000 --out results/ch5_r2/final_sN.json`, serial; (2) the sha
ATTESTATION commit (checkpoint_attestation block — all lanes at once,
its own commit); (3) `bash scripts/ch5_r2_preflight.sh && nohup bash
scripts/ch5_r2_wave.sh ...` (T arms, serial k=1); (4) R4S (lowest
surviving seed) via `ARMS="R4S<seed>"`; (5) riders — but the cross-play/
forgetting riders need `scripts/ch5_r2_crossplay.py` BUILT first (a
registered build item). Grade with `scripts/ch5_r2_grade.py`. Do NOT
delete any intermediate checkpoint (retention obligation, E3).

On completion: fold into SESSION_LOGS + STATUS (same commit), restore
this stub. Anything ambiguous (a void, a cell dispute, X3, an amendment)
is a maintainer escalation, not a judgment call.
