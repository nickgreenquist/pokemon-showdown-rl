"""Aggregate damage efficiency, and whether errors track losses.

EFFICIENCY = chosen move's expected damage / best available expected damage,
over our own decisions, restricted to states where the comparison is fair:
  - the mon has NO boosts up (Amnesia changes the special/physical calculus)
  - we are comparing within the same damage category (A/D ratio cancels)
  - only moves the generator ALWAYS gives, or that were revealed that battle
Computed identically for the human on the other side of the same battles.
"""
import re, json, collections, statistics
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))
import _parse as P

BOOSTM = {"amnesia","swordsdance","agility","barrier","acidarmor","growth",
          "harden","meditate","sharpen","withdraw","defensecurl","focusenergy"}

def run():
    eff = {"US": [], "THEM": []}
    per_battle = {}
    for path in P.replays():
        us, dec, _ = P.parse(path)
        if us is None: continue
        bid = re.search(r"gen1randombattle-(\d+)", path.name).group(1)
        boosts = collections.Counter()
        rec = collections.defaultdict(list)
        for d in dec:
            if d["kind"] != "move": continue
            side = "US" if d["side"] == us else "THEM"
            if P.norm(d["action"]) in BOOSTM:
                boosts[(d["side"], d["actor"])] += 1; continue
            if boosts[(d["side"], d["actor"])] or not d["foe"]: continue
            at, ft = P.types_of(d["actor"]), P.types_of(d["foe"])
            if not at or not ft: continue
            g = P.dmg(d["action"], at, ft, d["level"])
            if not g: continue
            always, _ = P.guaranteed_moves(d["actor"])
            revealed = {P.norm(z["action"]) for z in dec
                        if z["side"] == d["side"] and z["kind"] == "move"
                        and z["actor"] == d["actor"]}
            best = g[0]
            for mv in (set(always) | revealed):
                a = P.dmg(mv, at, ft, d["level"])
                if a and a[2] == g[2] and a[0] > best:   # same category only
                    best = a[0]
            if best > 0:
                eff[side].append(g[0] / best); rec[side].append(g[0] / best)
        per_battle[bid] = {s: (statistics.mean(v) if v else None)
                           for s, v in rec.items()}
    return eff, per_battle

eff, per_battle = run()
print("DAMAGE EFFICIENCY  (chosen expected damage / best available, same "
      "category, no boosts up)\n")
for s in ("US", "THEM"):
    v = eff[s]
    print(f"  {s:<6} n={len(v):>5}   mean {statistics.mean(v):.3f}"
          f"   median {statistics.median(v):.3f}"
          f"   at 1.00 {sum(1 for x in v if x > 0.999)/len(v):.1%}"
          f"   below 0.5 {sum(1 for x in v if x < 0.5)/len(v):.1%}")

out = json.load(open("results/ladder/L2.report.json")) if False else None
rows = [json.loads(l) for l in open("results/ladder/L2.battles.jsonl")]
res = {re.search(r"gen1randombattle-(\d+)", r["tag"]).group(1): r["outcome"]
       for r in rows}
w = [per_battle[b]["US"] for b in per_battle
     if res.get(b) == "win" and per_battle[b].get("US")]
l = [per_battle[b]["US"] for b in per_battle
     if res.get(b) == "loss" and per_battle[b].get("US")]
print(f"\n  our efficiency in battles we WON  (n={len(w)}): "
      f"{statistics.mean(w):.3f}")
print(f"  our efficiency in battles we LOST (n={len(l)}): "
      f"{statistics.mean(l):.3f}")
print(f"  difference: {statistics.mean(w)-statistics.mean(l):+.3f}")
