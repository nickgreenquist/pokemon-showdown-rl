#!/bin/bash
# CH5 R1 wave driver (designer B BI-2 / §7.3) — STRICTLY SERIAL, k=1.
#
#   bash scripts/ch5_preflight.sh && bash scripts/ch5_r1_wave.sh
#
# G-SERIAL's ARTIFACT. Until this file existed the gate named nothing and
# was ungradeable: it asserts non-overlapping arm wall clocks, and nothing
# wrote the wave.log it would read. Every arm's start/done timestamp lands
# in $OUT/wave.log and scripts/ch5_r1_grade.py asserts they do not overlap.
#
# k=1 is not a preference. Every CH5 arm enters a comparison (A vs the
# banked 12M fleet; B vs A per lane; E3/E7 vs C0), the comparator wave
# ch4_r1_offsh ran serial k=1, and FP is TIME-BUDGETED so contention
# flatters us. A comparison across different k is VOID-K.
#
# Copied from scripts/ch4_r1_wave.sh, which already carries the resume-safe
# skip-if-complete helper. New here: the one retry for a no-JSON arm (the
# torch lazy-init SIGSEGV landmine — a lane can die before any log line),
# the per-kind STALL_POLLS, MAX_RELAUNCHES=10, NO_PROGRESS_RELAUNCHES=3,
# the ops-failure sentinels, and the wave.provenance.json stamp.
#
# bash-3.2-safe (macOS /bin/bash): no ${var,,}, no associative arrays.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO" || exit 1
PY="${PY:-/opt/anaconda3/envs/pokemon-showdown-rl/bin/python}"
PREREG="configs/eval/ch5_r1_offsh.yaml"
# G-RETAIN / artifacts.out_dir_rule: OUT MUST equal the pre-reg's
# results_dir. The runner defaults OUT to results/ch3_r4_fp_anchor, which
# would split G2's second tally (FP's stdout) from the arm JSON it has to
# be checked against.
OUT="results/ch5_r1_offsh"
WLOG="$OUT/wave.log"
export POKEMON_RL_ENCODER_V2=1
export POKEMON_RL_ENCODER_IDS=1
mkdir -p "$OUT"

wlog() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$WLOG"; }

# OUT == results_dir, asserted rather than assumed.
DECLARED_OUT="$("$PY" -c "import yaml;print(yaml.safe_load(open('$PREREG'))['results_dir'])")"
if [ "$OUT" != "$DECLARED_OUT" ]; then
    wlog "FATAL: OUT '$OUT' != prereg results_dir '$DECLARED_OUT' (artifacts.out_dir_rule)"
    exit 1
fi

wlog "WAVE START serial k=1, prereg sha $(shasum -a 256 $PREREG | cut -c1-12)"

# G8 provenance, captured BEFORE arm #1 — a stamp taken after the fact is
# not a stamp. The FP patch and the Showdown server are different
# processes and are out of the seat's reach, so this is the only place
# they are observable. A G8 break voids everything downstream of it.
"$PY" - <<'PYEOF' > "$OUT/wave.provenance.json"
import hashlib, json, subprocess, pathlib
def sh(*c, cwd=None):
    try:
        return subprocess.run(c, capture_output=True, text=True, cwd=cwd).stdout.strip()
    except Exception as e:
        return f"UNAVAILABLE: {e}"
def sha(p):
    q = pathlib.Path(p)
    return hashlib.sha256(q.read_bytes()).hexdigest() if q.exists() else "MISSING"
print(json.dumps({
  "fp_patch_sha256": sha("scripts/patches/foulplay_gen1_local.patch"),
  "foulplay_git_sha": sh("git", "rev-parse", "HEAD", cwd="../foul-play"),
  "showdown_version": json.loads(pathlib.Path("showdown/package.json").read_text()).get("version")
      if pathlib.Path("showdown/package.json").exists() else "MISSING",
  "showdown_git_sha": sh("git", "-C", "showdown", "rev-parse", "HEAD"),
  "launch_git_sha": sh("git", "rev-parse", "HEAD"),
  "prereg_sha256": sha("configs/eval/ch5_r1_offsh.yaml"),
}, indent=2))
PYEOF
wlog "provenance stamped -> $OUT/wave.provenance.json"

# RESUME-SAFE: an arm whose JSON exists AND resolved every challenge is
# COMPLETE and is skipped, so the wave can be re-invoked freely. A partial
# arm re-runs WHOLE — there is no mid-arm resume and none is claimed.
complete() {
    f="$OUT/$1.json"
    [ -f "$f" ] || return 1
    "$PY" - "$f" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
ok = d.get("gate_all_challenges_resolved", True) and (
    d.get("battles_finished", d.get("episodes", 0)) > 0)
sys.exit(0 if ok else 1)
PYEOF
}

# STALL_POLLS by arm kind (designer B §5.4, at 10 s/poll): 30 (5 min) for
# greedy/ensemble, 60 (10 min) for search. B set search's 60 because search
# was "3x slower"; the 100-battle calibration put it at 2.68 s/battle
# marginal against greedy's 1.485 — 1.8x, not 3x — so 60 is now MORE
# conservative than B intended. Kept: with MAX_RELAUNCHES cut to 10, a
# false-positive stall kill is 3x more expensive than it was under CH4's 30.
stall_polls_for() {
    case "$1" in
        B*) echo 60 ;;
        *)  echo 30 ;;
    esac
}

# wave_plan.order. E7 (CE7) runs LAST: it is the widest and most expensive
# roster, so an evening that runs short stops before it and loses nothing —
# every arm is individually resumable and the wave is skip-if-complete.
ARMS="${ARMS:-C0 A80 A81 A82 B80 B81 B82 CE3 CE7}"

for arm in $ARMS; do
    tag="$(echo "$arm" | tr 'A-Z' 'a-z')"
    if complete "$tag"; then wlog "$arm SKIP (already complete)"; continue; fi
    sp="$(stall_polls_for "$arm")"
    attempt=1
    while [ "$attempt" -le 2 ]; do
        wlog "$arm start (attempt $attempt, STALL_POLLS=$sp)"
        PREREG="$PREREG" ARM="$arm" TAG="$tag" OUT="$OUT" \
            STALL_POLLS="$sp" MAX_RELAUNCHES=10 NO_PROGRESS_RELAUNCHES=3 \
            bash scripts/ch3_r4_fp_runner.sh >> "$OUT/$tag.driver.log" 2>&1
        rc=$?
        # OPS FAILURES are re-run, never graded (designer B §6). They are
        # FILES the runner writes, so the grader sees them without
        # inference, and it REFUSES to grade a tag carrying one.
        if [ -f "$OUT/$tag.NO_PROGRESS" ]; then
            wlog "$arm OPS FAILURE (NO_PROGRESS) rc=$rc -- re-run under a FRESH username pair; NOT graded"
            break
        fi
        if [ -f "$OUT/$tag.USERNAME_DEADLOCK" ]; then
            wlog "$arm OPS FAILURE (USERNAME_DEADLOCK) rc=$rc -- re-run under a FRESH username pair; NOT graded"
            break
        fi
        if [ -f "$OUT/$tag.TOO_MANY_CRASHES" ]; then
            wlog "$arm VOID (TOO_MANY_CRASHES) rc=$rc -- continuing"
            break
        fi
        # B §7.3: a lane can die at startup with SIGSEGV in torch lazy
        # static init, BEFORE any log line or run dir. No JSON at all is
        # that shape, and it earns exactly one retry.
        if [ ! -f "$OUT/$tag.json" ] && [ "$attempt" -eq 1 ]; then
            wlog "$arm produced NO JSON rc=$rc -- retrying once (torch lazy-init SIGSEGV landmine)"
            attempt=2
            sleep 30
            continue
        fi
        wlog "$arm done rc=$rc"
        break
    done
done

wlog "WAVE COMPLETE"
wlog "G2 OWED on every arm: scripts/ch5_r1_grade.py before any number is quoted."
