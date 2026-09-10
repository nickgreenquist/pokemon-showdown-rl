#!/usr/bin/env bash
# Progress as a RATE per job (chunks done, min/chunk) against R3's clean-box
# references: A0 ~5-8, M ~18, L ~55 min/chunk. A wall-clock ETA is not
# progress; a job alive at zero CPU is a stall (ps -o time= twice, 15 s).
REPO=/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl
cd "$REPO" || exit 1
RES=results/search_s3_100m
echo "job            chunks  first_chunk_utc      last_chunk_utc       min/chunk  last_wr  ms/dec"
for j in a0_s104 a0_s112 a0_s120 s3l_s112 s3m_s104 s3m_s112 s3m_s120 a1e_s104 a1e_s112 a1e_s120; do
  python3 - "$j" "$RES" <<'PY'
import glob, json, os, sys, datetime as dt
j, res = sys.argv[1], sys.argv[2]
fs = sorted(glob.glob(f"{res}/{j}.chunk*.json"))
fin = os.path.exists(f"{res}/{j}.final.json")
if not fs:
    print(f"{j:<14} {'0/10':>6}  {'-':<20} {'-':<20} {'-':>9}  {'-':>7}  -"); sys.exit()
ts = [os.path.getmtime(f) for f in fs]
first, last = dt.datetime.utcfromtimestamp(ts[0]), dt.datetime.utcfromtimestamp(ts[-1])
rate = (ts[-1]-ts[0])/60/(len(fs)-1) if len(fs) > 1 else float('nan')
d = json.load(open(fs[-1]))
ms = d.get("search/ms_mean"); ms = f"{ms:.0f}" if ms else "-"
print(f"{j:<14} {str(len(fs))+'/10'+('*' if fin else ''):>6}  {first:%Y-%m-%d %H:%M}    {last:%Y-%m-%d %H:%M}    {rate:9.1f}  {d.get('eval/win_rate', float('nan')):7.4f}  {ms}")
PY
done
echo "--- off-FP leg (F3M112): completed battles from FP's own log"
grep -c "Winner:" results/search_s3_100m_offfp/f3m112.fp.stdout 2>/dev/null || echo 0
ls results/search_s3_100m_offfp/*.NO_PROGRESS results/search_s3_100m_offfp/*.TOO_MANY_CRASHES results/search_s3_100m_offfp/*.USERNAME_DEADLOCK 2>/dev/null
echo "--- live eval processes (bin/python anchored)"
pgrep -fl 'bin/python scripts/ch3_eval.py|bin/python scripts/ch3_fp_h2h.py' | sed -E 's/ \/opt.*ch3_/ ch3_/' 
