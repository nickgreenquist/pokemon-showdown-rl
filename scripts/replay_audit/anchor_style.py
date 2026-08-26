"""Profile the OPPONENT's play style in a set of replays, using the same
metrics the ladder audit ran over the human field. The question: which anchor
actually resembles the humans we meet on the ladder?"""
import sys, re, pathlib, collections
sys.path.insert(0,'scripts/replay_audit'); sys.path.insert(0,'.')
import _parse as P
from poke_env.data import GenData
M=GenData.from_gen(1).moves
BOOSTM={"amnesia","swordsdance","agility","barrier","acidarmor","growth","harden",
        "meditate","sharpen","withdraw","defensecurl","focusenergy"}

def profile(paths, target_is=None, label=""):
    """target_is: player NAME to profile, or None = profile whoever is NOT us."""
    mv=dmg=zero=dom=hb=boom=switch=forced=setup=status=0
    turns=[]; chains=collections.Counter(); seen_b=0
    for p in paths:
        txt=p.read_text(errors="ignore")
        slots=dict(re.findall(r"\|player\|(p[12])\|([^|]*)\|", txt))
        if target_is:
            tgt=next((s for s,n in slots.items() if n==target_is), None)
        else:
            tgt=next((s for s,n in slots.items() if n!="nickgen1rbrlbot"), None)
        if tgt is None: continue
        seen_b+=1
        lines=[l for l in txt.split("\n") if l.startswith("|")]
        active=None; foe=None; other="p2" if tgt=="p1" else "p1"
        known=collections.defaultdict(set); run=0
        for l in lines:
            f=l.split("|")[1:]
            if not f: continue
            if f[0]=="turn": turns.append(int(f[1]))
            if f[0] in ("switch","drag") and len(f)>1:
                sp=f[1].split(": ",1)[-1]
                if f[1][:2]==tgt:
                    active=sp
                    if f[0]=="switch": switch+=1
                else: foe=sp
            if f[0]=="move" and len(f)>2 and f[1][:2]==tgt:
                sp=f[1].split(": ",1)[-1]; name=f[2]; mv+=1
                known[sp].add(name)
                n=P.norm(name); m=M.get(n)
                if m and m["category"]=="Status": status+=1
                if n in BOOSTM:
                    run+=1; chains[min(run,4)]+=1
                else: run=0
                if n=="hyperbeam": hb+=1
                if n in ("explosion","selfdestruct"): boom+=1
                at,ft=P.types_of(active or ""), P.types_of(foe or "")
                if at and ft:
                    g=P.dmg(name,at,ft,80)
                    if g:
                        dmg+=1
                        if g[1]==0.0: zero+=1
                        best=None
                        for alt in known[sp]:
                            if P.norm(alt)==n: continue
                            aa=P.dmg(alt,at,ft,80)
                            if aa and (best is None or aa[0]>best): best=aa[0]
                        if best and best>max(g[0],1e-9)*2: dom+=1
    tot=mv+switch
    f=lambda x,d: (x/d if d else 0)
    return dict(label=label, battles=seen_b, decisions=tot,
                switch_rate=f(switch,tot), zero_rate=f(zero,dmg),
                dominated=f(dom,dmg), hyperbeam=f(hb,dmg), boom=f(boom,dmg),
                status_share=f(status,mv), chain3=chains[3]+chains[4],
                mean_turns=(max(turns) if turns else 0))

if __name__ == "__main__":
    T=pathlib.Path("/Users/nickgreenquist/.claude/jobs/62d4fa41/tmp")
    lad=[p for p in pathlib.Path("results/ladder/replays").glob("*.html")
         if re.search(r"gen1randombattle-\d{9,}", p.name)]
    rows=[profile(lad, None, "HUMANS (ladder, n=200)"),
          profile(sorted(T.glob("tapes_sh/*.html")), None, "SimpleHeuristics"),
          profile(sorted(T.glob("tapes_clone/*.html")), None, "BC clone of Foul Play")]
    print(f"{'opponent':<26}{'decis':>7}{'switch%':>9}{'0x%':>7}{'domin%':>8}"
          f"{'hyperbm%':>10}{'boom%':>7}{'status%':>9}{'chain3+':>9}")
    for r in rows:
        print(f"  {r['label']:<24}{r['decisions']:>7}{r['switch_rate']:>8.1%}"
              f"{r['zero_rate']:>7.1%}{r['dominated']:>8.1%}{r['hyperbeam']:>10.1%}"
              f"{r['boom']:>7.1%}{r['status_share']:>9.1%}{r['chain3']:>9}")
    print("\nDISTANCE FROM THE HUMAN FIELD (sum of |anchor - human| over the rates):")
    h=rows[0]
    keys=["switch_rate","zero_rate","dominated","hyperbeam","boom","status_share"]
    for r in rows[1:]:
        d=sum(abs(r[k]-h[k]) for k in keys)
        per=", ".join(f"{k}:{abs(r[k]-h[k]):+.3f}" for k in keys)
        print(f"  {r['label']:<24} total {d:.3f}   ({per})")
