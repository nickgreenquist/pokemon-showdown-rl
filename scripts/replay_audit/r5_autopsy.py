"""Ladder loss autopsy: luck vs play, by opponent band, BOTH sides on the same parser.

Written 2026-09-19 for LADDER R5 (docs/proposals/R6_PREP_PLAN_2026-09-19.md §0).
Read-only over the replay directory; prints tables, writes nothing.

    python scripts/replay_audit/r5_autopsy.py --replays results/ladder/replays_r5 \
        --jsonl results/ladder/R5E.battles.jsonl --name nickgen1rbrlbot

"NET HAX" = luck events that hit the OPPONENT minus luck events that hit US, where a
luck event is: a crit taken, a freeze taken, a full-paralysis / sleep / frozen turn
(`|cant|`), a miss by that side, a confusion self-hit. Symmetric by construction, so
the human baseline comes from the same battles on the same parser (README rule).
Categories are THIS script's (forfeit / timeout / no_show / played_out by log text) and
can differ by one from the readout's; the played-out set is what the luck tables use.
"""
import argparse, re, json, pathlib, collections, statistics as st
import sys, pathlib as _pl
sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
sys.path.insert(0, str(_pl.Path(__file__).resolve().parents[2]))

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--replays", required=True); ap.add_argument("--jsonl", required=True)
ap.add_argument("--name", required=True, help="the ladder account this run played under")
args = ap.parse_args()

import _parse as P
P.US = args.name; US = P.US
from poke_env.data import GenData
MOVES = GenData.from_gen(1).moves
def norm(s): return re.sub(r"[^a-z0-9]", "", (s or "").lower())
BOOM = {"explosion", "selfdestruct"}
ROWS = [json.loads(l) for l in open(args.jsonl)]
META = {re.search(r"gen1randombattle-(\d+)", r["tag"]).group(1): r for r in ROWS}
REPL = sorted(p for p in pathlib.Path(args.replays).glob("*.html")
              if re.search(r"gen1randombattle-\d{9,}", p.name))

def analyse(path):
    us, dec, lines = P.parse(path)
    if us is None: return None
    them = "p2" if us == "p1" else "p1"
    bid = re.search(r"gen1randombattle-(\d+)", path.name).group(1)
    txt = "\n".join(lines)
    pl = {s: (n, int(r) if r else None) for s, n, r in
          re.findall(r"\|player\|(p[12])\|([^|\n]*)\|[^|\n]*\|(\d*)", txt)}
    opp_name, opp_elo = pl.get(them, ("?", None))
    w = re.search(r"\|win\|([^\n|]*)", txt)
    winner = w.group(1).strip() if w else None
    outcome = "win" if winner == US else ("loss" if winner else "tie")
    cat = "played_out"
    if re.search(r"forfeited", txt): cat = "forfeit"
    elif re.search(r"lost due to inactivity", txt): cat = "timeout"
    c = collections.Counter(); turns = 0
    for i, l in enumerate(lines):
        f = l.split("|")[1:]
        if not f: continue
        t = f[0]
        if t == "turn": turns = int(f[1]); continue
        if len(f) < 2 or f[1][:2] not in ("p1", "p2"): continue
        side = "US" if f[1][:2] == us else "THEM"
        if t == "-crit": c[("crit_taken", side)] += 1
        elif t == "-status" and len(f) > 2: c[(f"st_{f[2]}_taken", side)] += 1
        elif t == "cant" and len(f) > 2: c[(f"cant_{f[2]}", side)] += 1
        elif t == "-miss": c[("miss_by", side)] += 1
        elif t == "-damage" and "[from] confusion" in l: c[("conf_hit", side)] += 1
        elif t == "faint": c[("faints", side)] += 1
        elif t == "move" and len(f) > 2:
            c[("moves", side)] += 1
            m = MOVES.get(norm(f[2]))
            if m and m["category"] == "Status": c[("status_moves", side)] += 1
            if norm(f[2]) in BOOM: c[("boom", side)] += 1
            if norm(f[2]) == "hyperbeam":
                c[("hb", side)] += 1
                tgt = f[3] if len(f) > 3 else ""
                for mline in lines[i + 1:i + 12]:
                    g = mline.split("|")[1:]
                    if not g: continue
                    if g[0] == "turn": break
                    if g[0] == "faint" and tgt and g[1] == tgt: c[("hb_ko", side)] += 1; break
                    if g[0] == "-miss" and g[1] == f[1]: c[("hb_miss", side)] += 1; break
    for d in dec:
        side = "US" if d["side"] == us else "THEM"
        if d["kind"] == "switch": c[("switches", side)] += 1
        elif d["kind"] == "move" and d["foe"]:
            at, ft = P.types_of(d["actor"]), P.types_of(d["foe"])
            if at and ft:
                g = P.dmg(d["action"], at, ft, d.get("level", 80))
                if g:
                    c[("dmg_moves", side)] += 1
                    if g[1] == 0.0: c[("zero_dmg", side)] += 1
    if c[("moves", "THEM")] + c[("switches", "THEM")] == 0: cat = "no_show"
    def bad(side):
        return (c[("crit_taken", side)] + c[("st_frz_taken", side)] + c[("cant_par", side)]
                + c[("cant_slp", side)] + c[("cant_frz", side)] + c[("miss_by", side)]
                + c[("conf_hit", side)])
    return dict(bid=bid, opp=opp_name, opp_elo=opp_elo, outcome=outcome, cat=cat, turns=turns,
                bad_us=bad("US"), bad_them=bad("THEM"), net=bad("THEM") - bad("US"),
                our_left=6 - c[("faints", "US")], their_left=6 - c[("faints", "THEM")], c=c)

B = [b for b in (analyse(p) for p in REPL) if b]
print(f"parsed {len(B)} replays; jsonl rows {len(ROWS)}; outcome agrees with jsonl on "
      f"{sum(1 for b in B if META.get(b['bid'], {}).get('outcome') == b['outcome'])}/{len(B)}")
print("categories (this script's classifier):", dict(collections.Counter(b["cat"] for b in B)))
def band(e):
    if e is None: return "unrated"
    return "<1200" if e < 1200 else "1200-1299" if e < 1300 else "1300-1399" if e < 1400 else ">=1400"
def wr(xs): return sum(1 for b in xs if b["outcome"] == "win") / len(xs) if xs else float("nan")
def mean(xs): return st.mean(xs) if xs else float("nan")
print("\n== ALL RATED BATTLES by opponent band (win = all; win_p = played-out only) ==")
print(f"{'band':<11}{'n':>4}{'win':>7}{'played':>8}{'win_p':>7}{'net hax W':>11}{'net hax L':>11}")
for bd in ["<1200", "1200-1299", "1300-1399", ">=1400"]:
    xs = [b for b in B if band(b["opp_elo"]) == bd]; po = [b for b in xs if b["cat"] == "played_out"]
    print(f"{bd:<11}{len(xs):>4}{wr(xs):>7.3f}{len(po):>8}{wr(po):>7.3f}"
          f"{mean([b['net'] for b in po if b['outcome']=='win']):>11.2f}"
          f"{mean([b['net'] for b in po if b['outcome']=='loss']):>11.2f}")
PO = [b for b in B if b["cat"] == "played_out"]
W = [b for b in PO if b["outcome"] == "win"]; L = [b for b in PO if b["outcome"] == "loss"]
print(f"\n== LUCK vs OUTCOME, played-out only (n={len(PO)}: {len(W)} W / {len(L)} L) ==")
print(f"net hax (+ = luck favoured us): mean in wins {mean([b['net'] for b in W]):+.2f}, in losses {mean([b['net'] for b in L]):+.2f}")
for lo, hi, lbl in [(-99, -3, "net <= -3 (luck against us)"), (-2, -1, "net -2..-1"), (0, 0, "net = 0"),
                    (1, 2, "net +1..+2"), (3, 99, "net >= +3 (luck for us)")]:
    xs = [b for b in PO if lo <= b["net"] <= hi]
    print(f"  {lbl:<30} n={len(xs):>3}  win={wr(xs):.3f}")
print(f"losses with even-or-better luck ('unforced'): {sum(1 for b in L if b['net'] >= 0)}/{len(L)}")
print(f"wins with even-or-worse luck ('earned'):      {sum(1 for b in W if b['net'] <= 0)}/{len(W)}")
print("\n== MARGIN: opponent mons left when we LOST (played out):",
      dict(sorted(collections.Counter(b["their_left"] for b in L).items())))
print("== MARGIN: our mons left when we WON (played out):",
      dict(sorted(collections.Counter(b["our_left"] for b in W).items())))
for tl in sorted(set(b["their_left"] for b in L)):
    xs = [b for b in L if b["their_left"] == tl]
    print(f"  their_left={tl}: n={len(xs)}, mean net hax {mean([b['net'] for b in xs]):+.2f}, unforced {sum(1 for b in xs if b['net'] >= 0)}")
def style(xs, side):
    g = lambda k: sum(b["c"][(k, side)] for b in xs)
    mv, sw, dm = g("moves"), g("switches"), g("dmg_moves")
    cant = g("cant_par") + g("cant_slp") + g("cant_frz")
    hb, ko = g("hb"), g("hb_ko")
    return (f"switch {sw/(mv+sw):.3f}  status {g('status_moves')/mv:.3f}  boom/100mv {100*g('boom')/mv:.1f}  "
            f"HB/100mv {100*hb/mv:.1f} (KO {ko/hb if hb else float('nan'):.2f}, miss {g('hb_miss')}, uses {hb})  "
            f"0x-dmg {g('zero_dmg')/dm:.3f}  cant/battle {cant/len(xs):.2f}  frz/battle {g('st_frz_taken')/len(xs):.2f}  "
            f"crit_taken/battle {g('crit_taken')/len(xs):.2f}")
print("\n== HYPER BEAM and 0x-damage over ALL parsed battles (n=%d) ==" % len(B))
for side in ("US", "THEM"):
    g = lambda k: sum(b["c"][(k, side)] for b in B)
    print(f"   {side:<5} HB uses {g('hb'):>3}  KO {g('hb_ko'):>3} ({g('hb_ko')/g('hb'):.2f})  missed {g('hb_miss'):>2}  "
          f"recharge turns {g('cant_recharge'):>3}   0x-damage {g('zero_dmg')}/{g('dmg_moves')} = {g('zero_dmg')/g('dmg_moves'):.3f}")
print("\n== STYLE, both sides, played-out ==")
for lbl, xs in [("all played-out", PO), (">=1400 played-out", [b for b in PO if band(b["opp_elo"]) == ">=1400"]),
                ("<1300 played-out", [b for b in PO if band(b["opp_elo"]) in ("<1200", "1200-1299")])]:
    print(f"{lbl} (n={len(xs)})"); print("   US  ", style(xs, "US")); print("   THEM", style(xs, "THEM"))
print("\n== EVERY LOSS vs >=1400 (played out): opp elo | turns | net (us-bad/them-bad) | their mons left | switches us v them | events ==")
for b in sorted([b for b in L if band(b["opp_elo"]) == ">=1400"], key=lambda b: -b["opp_elo"]):
    c = b["c"]; notes = []
    for k, lbl in [("crit_taken", "crit"), ("st_frz_taken", "frz"), ("cant_par", "fullpara"), ("cant_slp", "slpturn"),
                   ("miss_by", "miss"), ("conf_hit", "confhit")]:
        u, t = c[(k, "US")], c[(k, "THEM")]
        if u or t: notes.append(f"{lbl} {u}v{t}")
    print(f"  {b['opp_elo']:>5} | {b['turns']:>3} | {b['net']:+d} ({b['bad_us']}/{b['bad_them']}) | {b['their_left']} | "
          f"sw {c[('switches','US')]}v{c[('switches','THEM')]} | {', '.join(notes)}")
