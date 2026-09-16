#!/bin/bash
# mech200m queue -- [RWL-3]'s MECHANISM CO-PRIMARY on the nine pinned finals,
# under configs/eval/mech200m.yaml. Detached, resume-safe, rate-readable
# (CLAUDE.md rule 4). Re-execs from a FROZEN temp copy: never edit a bash
# script an instance is executing (docs/landmines.md).
#
#   nohup bash scripts/mech200m_queue.sh > logs/mech200m/queue.nohup 2>&1 &
#
# PHASES
#   COLLECT  per-lane self-play obs, 200 mirror battles each, SEQUENTIAL and
#            one lane at a time. SEQUENTIAL IS NOT A PREFERENCE: d22_collect_obs
#            derives its poke-env usernames from the checkpoint's OWN cfg.seed,
#            and the W trio and the 100M trio SHARE seeds 104/112/120 -- two of
#            those at once is rule 2's username collision, which dies as a
#            misleading TimeoutError. Skips any lane whose npz already exists,
#            so a death costs one lane.
#   SHARED   pool the six MONSTER lanes' obs into one input set (fixed shuffle,
#            20k rows) -- the cross-arm confound control named in the plan.
#   PROBE    d22_dormant_rank.py per lane, twice: once on that lane's OWN obs
#            (the D22 protocol, for within-lane trajectories) and once on the
#            shared set (for the cross-arm read). Per-lane invocation because
#            checkpoint step numbers JITTER and --steps is one list per call.
#   READOUT  scripts/mech200m_readout.py -> results/mech200m/READOUT.txt
#
# The probe is pure CPU on frozen checkpoints; only COLLECT needs the local
# Showdown server, which must already be up (the queue checks and refuses).
set -u
if [ "${QUEUE_FROZEN:-0}" != "1" ]; then
  FROZEN=$(mktemp -t mech200m_queue)
  cat "$0" > "$FROZEN"
  QUEUE_FROZEN=1 exec bash "$FROZEN" "$@"
fi
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
export POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1
export PYTHONUNBUFFERED=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
OUT=results/mech200m
LOG=logs/mech200m
mkdir -p "$LOG" "$OUT"
log() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG/queue.log"; }

# lane spec: <tag> <run_dir> <final_ckpt_step> <obs_prefix> <seed> <rungs csv>
LANES=(
  "w104 runs/showdown_monster200m_w_s104 200000000 obs_w 104 500007,12000026,50000007,100000032,150000098,200000000"
  "w112 runs/showdown_monster200m_w_s112 200000012 obs_w 112 500013,12000031,50000040,100000026,150000000,200000012"
  "w120 runs/showdown_monster200m_w_s120 200000003 obs_w 120 500024,12000011,50000026,100000013,150000017,200000003"
  "l128 runs/showdown_monster200m_l2lam_s128 200000046 obs_l 128 500021,12000018,50000031,100000024,150000005,200000046"
  "l136 runs/showdown_monster200m_l2lam_s136 200000007 obs_l 136 500039,12000022,50000010,100000023,150000045,200000007"
  "l144 runs/showdown_monster200m_l2lam_s144 200000006 obs_l 144 500000,12000020,50000000,100000024,150000034,200000006"
  "h104 runs/showdown_sp_100m_s104 100000027 obs_h 104 12000015,100000027"
  "h112 runs/showdown_sp_100m_s112 100000008 obs_h 112 12000023,100000008"
  "h120 runs/showdown_sp_100m_s120 100000080 obs_h 120 12000028,100000080"
)

prefix_for() { case "$1" in w*) echo showdown_monster200m_w_s;; l*) echo showdown_monster200m_l2lam_s;; h*) echo showdown_sp_100m_s;; esac; }

# ---------------------------------------------------------------- guards
if ! lsof -nP -iTCP:8000 -sTCP:LISTEN > /dev/null 2>&1; then
  log "REFUSING: no local Showdown server on :8000 (cd showdown && node pokemon-showdown start --no-security)"; exit 1
fi
if pgrep -f "bin/python -m rl.train" > /dev/null 2>&1; then
  log "REFUSING: an rl.train process is alive -- obs collection would collide on usernames (rule 2)"; exit 1
fi
log "guards ok: server up on :8000, no rl.train alive"

# ---------------------------------------------------------------- COLLECT
for spec in "${LANES[@]}"; do
  set -- $spec; tag=$1; rd=$2; step=$3; opfx=$4; seed=$5
  npz="$OUT/${opfx}${seed}.npz"
  if [ -f "$npz" ]; then log "COLLECT $tag SKIP ($npz exists)"; continue; fi
  ck=$(printf "%s/ckpt_%09d.pt" "$rd" "$step")
  [ -f "$ck" ] || { log "COLLECT $tag FAILED: $ck missing"; continue; }
  log "COLLECT $tag: $ck -> $npz (200 mirror battles)"
  "$PY" scripts/d22_collect_obs.py "$ck" --episodes 200 --out "$npz" \
      >> "$LOG/collect_$tag.log" 2>&1
  if [ -f "$npz" ]; then log "COLLECT $tag DONE: $(tail -1 "$LOG/collect_$tag.log")";
  else log "COLLECT $tag NO NPZ -- see $LOG/collect_$tag.log"; fi
  sleep 10   # let Showdown reap the rooms before the next seat connects
done
log "COLLECT PHASE DONE"

# ---------------------------------------------------------------- SHARED
if [ -f "$OUT/obs_shared.npz" ]; then
  log "SHARED SKIP (obs_shared.npz exists)"
else
  log "SHARED: pooling the six monster lanes' obs (fixed shuffle 20260916, 20000 rows)"
  "$PY" - <<'PYEOF' >> "$LOG/shared.log" 2>&1
import numpy as np
from pathlib import Path
out = Path("results/mech200m")
files = [out / f"obs_{a}{s}.npz" for a, seeds in (("w", (104, 112, 120)), ("l", (128, 136, 144)))
         for s in seeds]
missing = [f for f in files if not f.exists()]
assert not missing, f"missing obs for the shared pass: {missing}"
obs = np.concatenate([np.load(f)["obs"] for f in files])
masks = np.concatenate([np.load(f)["masks"] for f in files])
rng = np.random.default_rng(20260916)
idx = rng.permutation(len(obs))[:20000]
idx.sort()
np.savez_compressed(out / "obs_shared.npz", obs=obs[idx], masks=masks[idx],
                    outcomes=np.zeros(1, dtype=np.int8),
                    checkpoint="POOLED: " + ", ".join(f.name for f in files))
print(f"pooled {len(obs)} rows from {len(files)} lanes -> 20000 shared rows")
PYEOF
  log "SHARED: $(tail -1 "$LOG/shared.log")"
fi

# ---------------------------------------------------------------- PROBE
for spec in "${LANES[@]}"; do
  set -- $spec; tag=$1; rd=$2; step=$3; opfx=$4; seed=$5; rungs=$6
  pfx=$(prefix_for "$tag")
  if [ -f "$OUT/effective_rank_${tag}.csv" ]; then log "PROBE $tag SKIP (own-obs csv exists)";
  else
    log "PROBE $tag (own obs, rungs $rungs)"
    "$PY" scripts/d22_dormant_rank.py --lanes "$seed" --steps "$rungs" --layer-ranks \
      --run-prefix "$pfx" --obs-prefix "$opfx" --out "$OUT" --tag "$tag" \
      >> "$LOG/probe_$tag.log" 2>&1 || log "PROBE $tag FAILED -- see $LOG/probe_$tag.log"
  fi
  if [ -f "$OUT/effective_rank_${tag}_shared.csv" ]; then log "PROBE $tag SKIP (shared-obs csv exists)";
  else
    log "PROBE $tag (SHARED obs, rungs $rungs)"
    "$PY" scripts/d22_dormant_rank.py --lanes "$seed" --steps "$rungs" --layer-ranks \
      --run-prefix "$pfx" --obs-file "$OUT/obs_shared.npz" --out "$OUT" --tag "${tag}_shared" \
      >> "$LOG/probe_${tag}_shared.log" 2>&1 || log "PROBE $tag SHARED FAILED -- see $LOG/probe_${tag}_shared.log"
  fi
done
log "PROBE PHASE DONE"

# ---------------------------------------------------------------- READOUT
"$PY" scripts/mech200m_readout.py > "$OUT/READOUT.txt" 2>&1
log "READOUT written to $OUT/READOUT.txt"
log "QUEUE DONE"
