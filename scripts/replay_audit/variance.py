"""If move choice isn't deciding our games, what is? Gen 1 is famously
variance-heavy -- crits, freeze, full paralysis, and sleep all swing games
independently of policy. Quantify who got what, and split by outcome."""
import re, json, collections, statistics
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))
import _parse as P

rows = [json.loads(l) for l in open("results/ladder/L2.battles.jsonl")]
meta = {re.search(r"gen1randombattle-(\d+)", r["tag"]).group(1): r for r in rows}

agg = collections.defaultdict(lambda: collections.Counter())
per_battle = {}
for path in P.replays():
    us, dec, lines = P.parse(path)
    if us is None: continue
    bid = re.search(r"gen1randombattle-(\d+)", path.name).group(1)
    them = "p2" if us == "p1" else "p1"
    c = collections.Counter()
    for l in lines:
        f = l.split("|")[1:]
        if not f: continue
        t = f[0]
        if len(f) < 2: continue
        side = f[1][:2] if f[1][:2] in ("p1", "p2") else None
        who = None if side is None else ("US" if side == us else "THEM")
        if t == "-crit" and who:                    # crit landed ON who
            c[("crit_taken", who)] += 1
        if t == "-status" and who and len(f) > 2:
            c[(f"status_{f[2]}_taken", who)] += 1
        if t == "cant" and who and len(f) > 2:      # fully para / asleep / frozen
            c[(f"cant_{f[2]}", who)] += 1
        if t == "faint" and who:
            c[("faints", who)] += 1
        if t == "-miss" and who:
            c[("missed_us_attacking", who)] += 1
    per_battle[bid] = c
    for k, v in c.items(): agg[k[0]][k[1]] += v

print("EVENT TOTALS across all parsed battles  (\"taken\" = happened TO that side)\n")
print(f"  {'event':<26}{'US':>8}{'THEM':>8}   ratio")
for k in sorted(agg):
    u, t = agg[k]["US"], agg[k]["THEM"]
    r = f"{u/t:.2f}" if t else "--"
    print(f"  {k:<26}{u:>8}{t:>8}{r:>8}")

def split(key, sub):
    w = [per_battle[b][(key, sub)] for b in per_battle
         if meta.get(b, {}).get("outcome") == "win"]
    l = [per_battle[b][(key, sub)] for b in per_battle
         if meta.get(b, {}).get("outcome") == "loss"]
    if not w or not l: return None
    return statistics.mean(w), statistics.mean(l)

print("\n\nPER-BATTLE MEANS, split by our result:\n")
print(f"  {'':<34}{'in WINS':>10}{'in LOSSES':>12}")
for key, sub, lbl in [("crit_taken","US","crits we took"),
                      ("crit_taken","THEM","crits we landed"),
                      ("cant_par","US","turns we lost to paralysis"),
                      ("cant_par","THEM","turns they lost to paralysis"),
                      ("cant_slp","US","turns we lost to sleep"),
                      ("cant_slp","THEM","turns they lost to sleep"),
                      ("status_frz_taken","US","times we were frozen"),
                      ("status_frz_taken","THEM","times we froze them"),
                      ("faints","US","our mons fainted"),
                      ("faints","THEM","their mons fainted")]:
    s = split(key, sub)
    if s: print(f"  {lbl:<34}{s[0]:>10.2f}{s[1]:>12.2f}")

opp_w = [meta[b]["opponent_rating"] for b in per_battle
         if meta.get(b, {}).get("outcome") == "win" and meta[b].get("opponent_rating")]
opp_l = [meta[b]["opponent_rating"] for b in per_battle
         if meta.get(b, {}).get("outcome") == "loss" and meta[b].get("opponent_rating")]
print(f"\n  {'opponent Elo':<34}{statistics.mean(opp_w):>10.0f}{statistics.mean(opp_l):>12.0f}"
      f"   (n={len(opp_w)}/{len(opp_l)})")
