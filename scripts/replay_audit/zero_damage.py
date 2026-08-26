"""Refined 0x analysis: was a better move CERTAIN, LIKELY, or genuinely absent?
And the question that supersedes it -- should it have switched instead?"""
import re, collections
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))
import _parse as P

def best_alt(actor, foe_types, level, used, revealed):
    """-> (certain_best, prob_best) where certain_best only uses moves the
    generator ALWAYS gives, plus anything actually revealed this battle."""
    always, maybe = P.guaranteed_moves(actor)
    _, pdist = P.moveset_dist(actor)
    certain = set(always) | {P.norm(m) for m in revealed}
    cb = pb = None
    for mv in set(pdist) | certain:
        if mv == P.norm(used): continue
        d = P.dmg(mv, P.types_of(actor), foe_types, level)
        if not d: continue
        if mv in certain and (cb is None or d[0] > cb[0]): cb = (d[0], mv, 1.0)
        if pb is None or d[0] > pb[0]: pb = (d[0], mv, pdist.get(mv, 1.0))
    return cb, pb

rows, stuck = [], []
for path in P.replays():
    us, dec, _ = P.parse(path)
    if us is None: continue
    bid = re.search(r"gen1randombattle-(\d+)", path.name).group(1)[-4:]
    for d in dec:
        if d["side"] != us or d["kind"] != "move" or not d["foe"]: continue
        at, ft = P.types_of(d["actor"]), P.types_of(d["foe"])
        if not at or not ft: continue
        g = P.dmg(d["action"], at, ft, d["level"])
        revealed = {z["action"] for z in dec
                    if z["side"] == us and z["kind"] == "move" and z["actor"] == d["actor"]}
        if g and g[1] == 0.0:
            cb, pb = best_alt(d["actor"], ft, d["level"], d["action"], revealed)
            rows.append((bid, d["turn"], d["actor"], d["foe"], d["action"], cb, pb))
        # separately: was EVERY guaranteed damaging move <=0.5x here?
        always, _ = P.guaranteed_moves(d["actor"])
        pool = set(always) | {P.norm(m) for m in revealed}
        eff = [P.dmg(m, at, ft, d["level"]) for m in pool]
        eff = [e for e in eff if e]
        if eff and max(e[1] for e in eff) <= 0.5 and d["hp"] > 30:
            stuck.append((bid, d["turn"], d["actor"], d["foe"], d["action"],
                          max(e[1] for e in eff), d["hp"]))

print("=== every 0x move we played, by whether a better one was CERTAIN ===\n")
cert = prob = none = 0
for bid, t, a, f, mv, cb, pb in rows:
    if cb and cb[0] > 5:
        cert += 1
        print(f"  INDEFENSIBLE  b{bid} t{t:>2} {a:<11} vs {f:<11} used {mv}")
        print(f"                 had {cb[1]} (~{cb[0]:.0f} dmg) with probability 1.0")
    elif pb and pb[0] > 5:
        prob += 1
        print(f"  PROBABLE      b{bid} t{t:>2} {a:<11} vs {f:<11} used {mv}")
        print(f"                 {pb[1]} (~{pb[0]:.0f}) present with p={pb[2]:.2f}"
              f"  -> ~{1-pb[2]:.0%} chance it had no damaging option")
    else:
        none += 1
        print(f"  NO OPTION     b{bid} t{t:>2} {a:<11} vs {f:<11} used {mv}"
              f"   (every possible move is 0x here -- the error is STAYING IN)")
print(f"\n  indefensible {cert}   probabilistic {prob}   no-move-existed {none}")

print(f"\n\n=== decisions where our BEST guaranteed move was <=0.5x and we "
      f"attacked anyway (hp>30%): {len(stuck)} ===")
by_mon = collections.Counter(f"{a} vs {f}" for _, _, a, f, _, _, _ in stuck)
for k, v in by_mon.most_common(14):
    print(f"    {v:>2}x  {k}")
