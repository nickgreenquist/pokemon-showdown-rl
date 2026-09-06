#!/usr/bin/env bash
# gen4_wang50m — THE FROZEN POST-FLEET SCHEDULE (configs/gen4_wang50m.yaml,
# "POST-FLEET SCHEDULE, ORDER FROZEN"): agent-side, detached, RESUME-SAFE
# (every unit skips when its output exists), RATE-READABLE (ELAPSED per
# unit). NOTHING here runs while any lane trains — step 0 refuses.
#   1 vs-SH finals 3 x 3000 (PRIMARY; n=20 pre-read first for s/battle)
#   2 L2 FP@20 h2h 3 x 250, sequential, one FP process at a time
#   3 L1 MDT h2h 3 x 500
#   4 S-SHAPE rungs 5M..50M step 5M x 3 lanes x n=1000 (descriptive)
#   5 L3 FP@500 h2h 3 x 5 chunks x 50 (--timeout 5400; THE CHUNK IS THE
#     RESUME UNIT; the tally is the SUM of chunk records, never a subtraction)
#   6 L4 clone h2h 3 x 500 iff the clone validated (else PENDING)
#   7 Q38 pin arithmetic (pooled FP@20 vs FP@500, 2*se_diff rule) -> q38_pin.json
#   8 PRIMARY grade: scripts/gen4_wang50m_readout.py -> primary.json
#   The RESULTS addendum / README row / STATUS / SESSION_LOGS are authored
#   by hand from these files, in ONE commit (the header's rule).
# LANE-FAILURE RULE: a lane without ckpt_050000000.pt is REPORTED and
# skipped (k <= 2 -> the primary is DESCRIPTIVE ONLY, cell K); the readout
# script enforces n_eff and k.
# Launch: nohup bash scripts/gen4_wang50m_postfleet.sh > /dev/null 2>&1 < /dev/null &
# DRY=1 prints every command instead of running it.
set -u
cd "$(dirname "$0")/.."
PY=/opt/anaconda3/envs/pokemon-showdown-rl/bin/python
LOG=logs/gen4_wang50m_postfleet.log
OUT=results/gen4_wang50m
SEEDS="${SEEDS:-200 208 216}"
CLONE=runs/bc_gen4_fp20_soft_s0/checkpoint.pt
DRY="${DRY:-0}"
mkdir -p "$OUT/fp" "$OUT/sshape" logs
say() { echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
run() {  # log + run (or print under DRY)
  if [ "$DRY" = 1 ]; then say "DRY: $*" >&2; return 0; fi
  "$@"
}
final_of() { ls "runs/gen4_wang50m_s$1/ckpt_050000000.pt" 2>/dev/null; }
wr_of() { "$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['eval/win_rate'])" "$1"; }
fp_done() {  # $1 summary.json, $2 battles -> 0 if complete and clean
  [ -f "$1" ] || return 1
  "$PY" - "$1" "$2" <<'PYEOF'
import json, sys
s = json.load(open(sys.argv[1])); n = int(sys.argv[2])
ok = s.get("fp_exit_code") == 0 and not s.get("timed_out") and sum(s.get("seat_record_W_L_T", [0, 0, 0])) == n
sys.exit(0 if ok else 1)
PYEOF
}
eval_unit() {  # $1 ckpt, $2 out.json, $3.. eval_checkpoint args
  local ckpt="$1" out="$2"; shift 2
  if [ -f "$out" ]; then say "SKIP $out (exists)"; return 0; fi
  local t0; t0=$(date +%s)
  say "START $out <- $(basename "$ckpt") $*"
  if run "$PY" scripts/eval_checkpoint.py "$ckpt" "$@" --out "$out.tmp" > /dev/null 2>> "$LOG"; then
    [ "$DRY" = 1 ] || mv "$out.tmp" "$out"
    [ "$DRY" = 1 ] || say "DONE $out win_rate=$(wr_of "$out") ELAPSED=$(( $(date +%s) - t0 ))s"
  else
    say "FAILED $out (rc $?) — re-run resumes here"; return 1
  fi
}
fp_unit() {  # $1 ckpt, $2 seed, $3 battles, $4 ms, $5 tag, $6 timeout
  local ckpt="$1" seed="$2" n="$3" ms="$4" tag="$5" to="$6"
  if fp_done "$OUT/fp/$tag.summary.json" "$n"; then say "SKIP fp $tag (complete)"; return 0; fi
  local t0; t0=$(date +%s)
  say "START fp $tag: FP@${ms} x $n vs $(basename "$ckpt") seed $seed"
  if run "$PY" scripts/gen4_fp_h2h.py --checkpoint "$ckpt" --battles "$n" --search-time-ms "$ms" --port 8000 \
       --seed "$seed" --tag "$tag" --out "$OUT/fp/" --timeout "$to" > "logs/gen4_fp_$tag.log" 2>&1; then
    [ "$DRY" = 1 ] || say "DONE fp $tag: $(grep -o 'seat W-L-T=\[[0-9, ]*\]' "logs/gen4_fp_$tag.log" | tail -n 1) s/battle $(grep -o 's/battle=[0-9.]*' "logs/gen4_fp_$tag.log" | tail -n 1) ELAPSED=$(( $(date +%s) - t0 ))s"
  else
    say "FAILED fp $tag (rc $?) — the chunk is the resume unit"; return 1
  fi
}

# ---- 0. refuse while any lane trains ------------------------------------------
if pgrep -f "rl.train.*gen4_wang50m" >/dev/null || pgrep -f "rl.train --resume runs/gen4_wang50m" >/dev/null; then
  say "REFUSED: a gen4_wang50m lane is still training (nothing evaluates while any lane trains)"; exit 1
fi
grep -q "FLEET DONE" logs/gen4_wang50m_wave.log 2>/dev/null || say "WARNING: no FLEET DONE line in the wave log yet — continuing only because no lane process is alive"
LANES=""
for s in $SEEDS; do
  if [ -n "$(final_of "$s")" ]; then LANES="$LANES $s"; else say "LANE-FAILURE RULE: lane s$s has no ckpt_050000000.pt — reported, skipped"; fi
done
say "POST-FLEET START: lanes with the completion rung:$LANES"
[ -n "$LANES" ] || { say "no complete lane — nothing to evaluate"; exit 1; }

# ---- 1. vs-SH finals (PRIMARY) ---------------------------------------------------
for s in $LANES; do
  eval_unit "$(final_of "$s")" "$OUT/final_s${s}_n20.json" --episodes 20 --opponent heuristics
done
for s in $LANES; do
  eval_unit "$(final_of "$s")" "$OUT/final_s${s}.json" --episodes 3000 --opponent heuristics
done
say "STEP 1 DONE (vs-SH finals)"

# ---- 2. L2 FP@20 --------------------------------------------------------------------
for s in $LANES; do fp_unit "$(final_of "$s")" "$s" 250 20 "gen4w50m_s${s}_fp20" 3600; done
say "STEP 2 DONE (L2 FP@20)"

# ---- 3. L1 MDT ---------------------------------------------------------------------
for s in $LANES; do
  eval_unit "$(final_of "$s")" "$OUT/mdt_s${s}.json" --episodes 500 --opponent most_damage_typed
done
say "STEP 3 DONE (L1 MDT)"

# ---- 4. S-SHAPE ------------------------------------------------------------------------
for s in $LANES; do
  for m in $(seq 5 5 50); do
    ckpt="runs/gen4_wang50m_s${s}/ckpt_$(printf %09d $((m * 1000000))).pt"
    [ -f "$ckpt" ] || { say "S-SHAPE MISSING rung ${m}M for s${s} (8 | 500k: the grid literal should exist) — skipped"; continue; }
    eval_unit "$ckpt" "$OUT/sshape/s${s}_$(printf %03d "$m")M.json" --episodes 1000 --opponent heuristics
  done
done
say "STEP 4 DONE (S-SHAPE)"

# ---- 5. L3 FP@500 in chunks --------------------------------------------------------------
for s in $LANES; do
  for k in 1 2 3 4 5; do fp_unit "$(final_of "$s")" "$s" 50 500 "gen4w50m_s${s}_fp500_c${k}" 5400; done
done
say "STEP 5 DONE (L3 FP@500)"

# ---- 6. L4 clone h2h iff validated ---------------------------------------------------------
if [ -f "$CLONE" ] && [ -f "$OUT/clone_vs_sh.json" ]; then
  for s in $LANES; do
    eval_unit "$(final_of "$s")" "$OUT/clone_s${s}.json" --episodes 500 --opponent-checkpoint "$CLONE"
  done
  say "STEP 6 DONE (L4 clone h2h)"
else
  say "STEP 6: L4 reads PENDING (clone checkpoint or its vs-SH validation missing) — the README row WAITS"
fi

# ---- 7. Q38 pin --------------------------------------------------------------------------
[ "$DRY" = 1 ] || "$PY" - "$OUT" $LANES <<'PYEOF' | tee -a "$LOG"
import json, math, sys
from pathlib import Path
out = Path(sys.argv[1]); lanes = sys.argv[2:]
def pooled(tags):
    w = l = t = 0
    per = {}
    for tag in tags:
        p = out / "fp" / f"{tag}.summary.json"
        if not p.exists(): return None
        s = json.load(open(p)); W, L, T = s["seat_record_W_L_T"]; w += W; l += L; t += T; per[tag] = (W, L, T)
    n = w + l + t
    return {"W": w, "L": l, "T": t, "n": n, "p": w / n if n else float("nan"), "per_chunk": per}
r20 = pooled([f"gen4w50m_s{s}_fp20" for s in lanes])
r500 = pooled([f"gen4w50m_s{s}_fp500_c{k}" for s in lanes for k in range(1, 6)])
res = {"fp20": r20, "fp500": r500, "rule": "pin the LOWER rung if |p20 - p500| < 2*se_diff (binomial, pooled), else pin 500 and retire 20 for gen 4; governs LATER runs only"}
if r20 and r500 and r20["n"] and r500["n"]:
    se = math.sqrt(r20["p"] * (1 - r20["p"]) / r20["n"] + r500["p"] * (1 - r500["p"]) / r500["n"])
    diff = r20["p"] - r500["p"]
    res.update({"diff": diff, "se_diff": se, "pin_ms": 20 if abs(diff) < 2 * se else 500})
    print(f"Q38: FP@20 {r20['p']:.4f} (n={r20['n']}) vs FP@500 {r500['p']:.4f} (n={r500['n']}); diff {diff:+.4f}, 2*se_diff {2*se:.4f} -> PIN {res['pin_ms']} ms (later runs only; both numbers print in this readout)")
else:
    res["pin_ms"] = None; print("Q38: a rung is incomplete — no pin")
(out / "q38_pin.json").write_text(json.dumps(res, indent=1) + "\n")
PYEOF

# ---- 8. PRIMARY grade ------------------------------------------------------------------------
finals=""; for s in $LANES; do [ -f "$OUT/final_s${s}.json" ] && finals="$finals $OUT/final_s${s}.json"; done
run "$PY" scripts/gen4_wang50m_readout.py $finals --out "$OUT/primary.json" 2>&1 | tee -a "$LOG"
say "POST-FLEET DONE — author the readout (RESULTS addendum + README row + STATUS + SESSION_LOGS, ONE commit) from $OUT/"
