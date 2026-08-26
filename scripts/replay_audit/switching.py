"""Switching, KO conversion, and boost-aware re-checks.

The boost correction matters: an earlier pass flagged 53 decisions as
"attacked into a resist with a better option", and the largest cluster
(Slowpoke vs Poliwrath, 11x) turned out to be a textbook Amnesia sweep --
Thunder Wave, Amnesia x3, then Surf to a near-KO. Gen 1 Amnesia raises
Special for BOTH attack and defence, so a 0.5x Surf from a +6 Slowpoke beats
an unboosted neutral move by a lot. Any check that ignores boosts will call
correct play an error, so boost state is tracked and reported here.
"""
import re, collections
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))
import _parse as P

BOOSTM = {"amnesia","swordsdance","agility","barrier","acidarmor","growth",
          "harden","meditate","sharpen","withdraw","defensecurl","doubleteam",
          "focusenergy"}

sw_into_se, churn, ko_giveup, boosted_att = [], [], [], []
tally = collections.Counter()
switch_streaks = collections.Counter()

for path in P.replays():
    us, dec, lines = P.parse(path)
    if us is None: continue
    bid = re.search(r"gen1randombattle-(\d+)", path.name).group(1)[-4:]
    boosts = collections.Counter()          # (side,actor) -> n boost moves used
    last_kind = {}
    streak = collections.Counter()
    for i, d in enumerate(dec):
        side = "US" if d["side"] == us else "THEM"
        tally[(side, d["kind"])] += 1
        if d["kind"] == "switch":
            streak[d["side"]] += 1
            switch_streaks[(side, min(streak[d["side"]], 4))] += 1
            # did the mon we brought in eat a super-effective hit next?
            for nxt in dec[i+1:i+3]:
                if nxt["kind"] == "move" and nxt["side"] != d["side"] \
                   and nxt["foe"] == d["actor"]:
                    at, ft = P.types_of(nxt["actor"]), P.types_of(d["actor"])
                    if not at or not ft: break
                    g = P.dmg(nxt["action"], at, ft, nxt.get("level", 80))
                    if g and g[1] >= 2.0:
                        sw_into_se.append((side, f"b{bid} t{d['turn']} "
                            f"switched in {d['actor']} -> ate {nxt['action']} "
                            f"x{g[1]:g} from {nxt['actor']}"))
                    break
        else:
            streak[d["side"]] = 0
            if P.norm(d["action"]) in BOOSTM:
                boosts[(d["side"], d["actor"])] += 1
            # gave up a near-KO by switching is handled above; here: attacked
            # while already boosted, which is the CORRECT pattern -- counted so
            # the "attacked into a resist" number can be read net of it
            if boosts[(d["side"], d["actor"])] >= 2:
                boosted_att.append((side, d["actor"]))
        last_kind[d["side"]] = d["kind"]

    # switching away from a foe that was nearly dead
    for i, d in enumerate(dec):
        if d["kind"] != "switch" or d["side"] != us: continue
        prev = [z for z in dec[:i] if z["side"] == us and z["kind"] == "move"]
        if not prev: continue
        p_ = prev[-1]
        if p_["foe_hp"] is not None and 0 < p_["foe_hp"] <= 25:
            ko_giveup.append(f"b{bid} t{d['turn']} switched to {d['actor']} "
                             f"with {p_['foe']} at {p_['foe_hp']:.0f}%")

mv_us, mv_th = tally[("US","move")], tally[("THEM","move")]
sw_us, sw_th = tally[("US","switch")], tally[("THEM","switch")]
tot_us, tot_th = mv_us+sw_us, mv_th+sw_th
print(f"{'':<40}{'US':>12}{'THEM':>12}")
print(f"  {'total decisions':<38}{tot_us:>12}{tot_th:>12}")
print(f"  {'switch rate':<38}{sw_us/tot_us:>11.1%}{sw_th/tot_th:>12.1%}")
u = [x for s,x in sw_into_se if s=="US"]; t = [x for s,x in sw_into_se if s=="THEM"]
print(f"  {'switched into a >=2x hit':<38}{len(u):>12}{len(t):>12}")
print(f"  {'  as a share of switches':<38}{len(u)/max(sw_us,1):>11.1%}{len(t)/max(sw_th,1):>12.1%}")
print(f"\n  consecutive-switch runs (US / THEM):")
for k in (1,2,3,4):
    print(f"    run of {k}{'+' if k==4 else ' '}: "
          f"{switch_streaks[('US',k)]:>4} / {switch_streaks[('THEM',k)]:>4}")
print(f"\n  we switched away while the foe was <=25%: {len(ko_giveup)}")
for x in ko_giveup[:10]: print(f"    {x}")
ba = collections.Counter(a for s,a in boosted_att if s=="US")
print(f"\n  our attacks made while that mon had >=2 boosts up: "
      f"{sum(1 for s,_ in boosted_att if s=='US')}")
for k,v in ba.most_common(8): print(f"    {v:>3}x  {k}")
print(f"\n  examples, switched into a super-effective hit (ours):")
for x in u[:12]: print(f"    {x}")
