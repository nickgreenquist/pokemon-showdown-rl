"""Overnight replay audit. Every check runs on BOTH sides of the same battles:
a rate without the human baseline from the same parser is not interpretable.
"""
import re, collections, json
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))
import _parse as P
from poke_env.data import GenData

G = GenData.from_gen(1); MOVES = G.moves
def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())

HEAL = {"recover", "softboiled", "rest"}
BOOST = {"swordsdance", "agility", "amnesia", "barrier", "acidarmor",
         "doubleteam", "growth", "harden", "meditate", "sharpen", "withdraw",
         "defensecurl", "focusenergy"}
STATUS_INFLICT = {"thunderwave": "par", "toxic": "tox", "sleeppowder": "slp",
                  "hypnosis": "slp", "spore": "slp", "lovelykiss": "slp",
                  "sing": "slp", "poisonpowder": "psn", "stunspore": "par",
                  "glare": "par", "confuseray": None, "supersonic": None,
                  "willowisp": "brn", "poisongas": "psn"}
BOOM = {"explosion", "selfdestruct"}

def run():
    issues = collections.defaultdict(list)     # name -> [(side, detail)]
    tally  = collections.Counter()             # (side, kind) -> n
    per_species = collections.Counter()
    battles = 0

    for path in P.replays():
        us, dec, lines = P.parse(path)
        if us is None: continue
        battles += 1
        bid = re.search(r"gen1randombattle-(\d+)", path.name).group(1)[-4:]
        prev_zero = {}                          # (side,actor) -> last 0-dmg move
        for k, d in enumerate(dec):
            side = "US" if d["side"] == us else "THEM"
            tally[(side, d["kind"])] += 1
            if d["kind"] != "move" or not d["foe"]:
                continue
            mv = norm(d["action"])
            at, ft = P.types_of(d["actor"]), P.types_of(d["foe"])
            if not at or not ft: continue
            got = P.dmg(d["action"], at, ft, d["level"])
            m = MOVES.get(mv)
            ctx = f"b{bid} t{d['turn']:>2} {d['actor']} vs {d['foe']}"

            # ---- damaging-move checks
            if got:
                e, mult, _ = got
                tally[(side, "damaging")] += 1
                if mult == 0.0:
                    issues["A_zero_multiplier"].append((side, f"{ctx}: {d['action']} x0"))
                    if side == "US": per_species[d["actor"]] += 1
                # best known/guaranteed alternative
                ess, exc = P.guaranteed_moves(d["actor"])
                pool = set(ess) | {norm(x) for x in
                                   [z["action"] for z in dec
                                    if z["kind"] == "move" and z["actor"] == d["actor"]
                                    and z["side"] == d["side"]]}
                best = None
                for alt in pool:
                    if alt == mv: continue
                    a = P.dmg(alt, at, ft, d["level"])
                    if a and (best is None or a[0] > best[0]): best = (a[0], alt)
                if best and best[0] > max(e, 1e-9) * 2.0:
                    src = "guaranteed" if best[1] in ess else "revealed"
                    issues["B_dominated_move"].append(
                        (side, f"{ctx}: {d['action']} ~{e:.0f} vs {best[1]} "
                               f"~{best[0]:.0f} ({best[0]/max(e,1e-9):.1f}x, {src})"))
                if mv == "hyperbeam" and d["foe_hp"] and d["foe_hp"] > 40:
                    issues["J_hyperbeam_unlikely_ko"].append(
                        (side, f"{ctx}: foe at {d['foe_hp']:.0f}% -> recharge"))
                if mv in BOOM:
                    issues["K_explosion"].append(
                        (side, f"{ctx}: at {d['hp']:.0f}% hp, foe {d['foe_hp']:.0f}%"))
                if prev_zero.get((d["side"], d["actor"])) == mv:
                    issues["L_repeated_a_zero_move"].append((side, f"{ctx}: {d['action']} again"))
                prev_zero[(d["side"], d["actor"])] = mv if mult == 0.0 else None

            # ---- status / utility checks
            if m and m["category"] == "Status":
                tally[(side, "status_move")] += 1
                want = STATUS_INFLICT.get(mv, "MISS")
                if want != "MISS" and d["foe_status"]:
                    issues["C_status_onto_already_statused"].append(
                        (side, f"{ctx}: {d['action']} but foe already {d['foe_status']}"))
                if want and want != "MISS":
                    imm = P.dmg(d["action"], at, ft, d["level"])
                    mt = m["type"].upper()
                    from poke_env.battle.pokemon_type import PokemonType as T
                    mult = getattr(T, mt).damage_multiplier(*ft, type_chart=P.TC)
                    if mult == 0.0:
                        issues["D_status_move_type_immune"].append(
                            (side, f"{ctx}: {d['action']} ({mt}) vs immune type"))
                if mv in HEAL and d["hp"] > 85:
                    issues["E_heal_at_high_hp"].append(
                        (side, f"{ctx}: {d['action']} at {d['hp']:.0f}% hp"))
                if mv in BOOST and d["hp"] < 25:
                    issues["F_boost_at_low_hp"].append(
                        (side, f"{ctx}: {d['action']} at {d['hp']:.0f}% hp"))
                if mv == "substitute" and "Substitute" in d["self_vol"]:
                    issues["G_substitute_while_sub_up"].append((side, ctx))
                if want and want != "MISS" and d["foe_hp"] is not None and d["foe_hp"] < 20:
                    issues["H_status_onto_dying_foe"].append(
                        (side, f"{ctx}: {d['action']} at foe {d['foe_hp']:.0f}% hp"))

    print(f"battles parsed: {battles}\n")
    print(f"{'':<34}{'US':>16}{'THEM (human)':>18}")
    for lbl, key in [("move decisions", "move"), ("  of those, damaging", "damaging"),
                     ("  of those, status", "status_move"), ("switches", "switch")]:
        print(f"  {lbl:<32}{tally[('US',key)]:>16}{tally[('THEM',key)]:>18}")
    dm_us, dm_th = tally[("US","damaging")], tally[("THEM","damaging")]
    mv_us, mv_th = tally[("US","move")], tally[("THEM","move")]
    print(f"\n{'ISSUE':<34}{'US':>10}{'rate':>9}{'THEM':>8}{'rate':>9}   ratio")
    for name in sorted(issues):
        u = [x for s, x in issues[name] if s == "US"]
        t = [x for s, x in issues[name] if s == "THEM"]
        base_u, base_t = (dm_us, dm_th) if name[0] in "ABJKL" else (mv_us, mv_th)
        ru, rt = len(u)/max(base_u,1), len(t)/max(base_t,1)
        r = f"{ru/rt:.1f}x" if rt > 0 else ("--" if ru == 0 else "inf")
        print(f"  {name:<32}{len(u):>10}{ru:>8.2%}{len(t):>8}{rt:>8.2%}{r:>8}")
    json.dump({k: v for k, v in issues.items()}, open("audit_raw.json","w"), indent=1)
    return issues

if __name__ == "__main__":
    issues = run()
    print("\n\n================ OUR ISSUES, IN FULL ================")
    for name in sorted(issues):
        u = [x for s, x in issues[name] if s == "US"]
        if not u: continue
        print(f"\n--- {name}  ({len(u)})")
        for x in u[:14]: print(f"    {x}")
        if len(u) > 14: print(f"    ... and {len(u)-14} more")
