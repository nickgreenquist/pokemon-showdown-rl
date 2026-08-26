"""Profile OUR OWN side of the 200 rated ladder replays against the human
field, on the metrics `anchor_style.py` uses for the scripted anchors.

Why this exists as its own grader script: every style number this project
owned compared an ANCHOR to humans (which proxy resembles the ladder field).
Nobody had ever put US in that table. The answer changes the diagnosis --
see the 2026-08-26 SESSION_LOGS entry.

Second section is a BIAS CHECK on the `dominated` metric, which compares a
damaging move against the alternatives that mon has ALREADY REVEALED in the
same replay. A side that reveals fewer distinct moves gets fewer chances to
be flagged, so the raw rate is reported alongside the rate CONDITIONED on
actually having a known damaging alternative.

    python scripts/replay_audit/our_style.py
"""
import sys, re, pathlib, collections

sys.path.insert(0, "scripts/replay_audit")
sys.path.insert(0, ".")
import _parse as P
from anchor_style import profile

OURS = {"nickgen1rbrlbot", "nick_gen1rb_rl_bot"}
REPLAYS = pathlib.Path("results/ladder/replays")
# 9+ digits = a real ladder battle id; the 8-digit ones are local-server tapes.
LADDER_RE = re.compile(r"gen1randombattle-\d{9,}")
METRICS = ["switch_rate", "zero_rate", "dominated", "hyperbeam", "boom", "status_share"]


def seats(path):
    return dict(re.findall(r"\|player\|(p[12])\|([^|]*)\|", path.read_text(errors="ignore")))


def dominated_detail(paths, mine: bool):
    """Exposure-normalized version of anchor_style's `dominated`."""
    revealed = collections.defaultdict(set)
    n_dmg = n_with_alt = n_flagged = 0
    for path in paths:
        text = path.read_text(errors="ignore")
        slots = dict(re.findall(r"\|player\|(p[12])\|([^|]*)\|", text))
        tgt = next((s for s, n in slots.items() if (n in OURS) == mine), None)
        if tgt is None:
            continue
        known = collections.defaultdict(set)
        active = foe = None
        for line in text.split("\n"):
            if not line.startswith("|"):
                continue
            f = line.split("|")[1:]
            if not f:
                continue
            if f[0] in ("switch", "drag") and len(f) > 1:
                species = f[1].split(": ", 1)[-1]
                if f[1][:2] == tgt:
                    active = species
                else:
                    foe = species
            if f[0] == "move" and len(f) > 2 and f[1][:2] == tgt:
                species, name = f[1].split(": ", 1)[-1], f[2]
                at, ft = P.types_of(active or ""), P.types_of(foe or "")
                got = P.dmg(name, at, ft, 80) if (at and ft) else None
                if got:
                    n_dmg += 1
                    alts = [a for a in known[species] if P.norm(a) != P.norm(name)]
                    dmg_alts = [a for a in alts if P.dmg(a, at, ft, 80)]
                    if dmg_alts:
                        n_with_alt += 1
                    best = max((P.dmg(a, at, ft, 80)[0] for a in dmg_alts), default=None)
                    if best and best > max(got[0], 1e-9) * 2:
                        n_flagged += 1
                known[species].add(name)
        for species, moves in known.items():
            revealed[(path.name, species)] |= moves
    counts = [len(v) for v in revealed.values()]
    return dict(
        dmg_moves=n_dmg, with_alt=n_with_alt, flagged=n_flagged,
        rate_all=n_flagged / n_dmg if n_dmg else 0.0,
        rate_given_alt=n_flagged / n_with_alt if n_with_alt else 0.0,
        revealed_per_mon=sum(counts) / len(counts) if counts else 0.0,
    )


def main():
    ladder = [p for p in REPLAYS.glob("*.html") if LADDER_RE.search(p.name)]
    handles = {n for p in ladder for n in seats(p).values() if n in OURS}
    print(f"{len(ladder)} rated ladder replays; our handle(s): {sorted(handles)}\n")

    us = profile(ladder, sorted(handles)[0], "US (L2 ensemble)")
    # target_is=None is anchor_style's own "whoever is not us" resolution, so
    # this row is bit-identical to the HUMANS row that script prints.
    them = profile(ladder, None, "HUMANS (same 200)")

    print(f"{'side':<26}{'batt':>6}{'decis':>7}{'switch%':>9}{'0x%':>7}"
          f"{'domin%':>8}{'hyperbm%':>10}{'boom%':>7}{'status%':>9}")
    for r in (us, them):
        print(f"  {r['label']:<24}{r['battles']:>6}{r['decisions']:>7}"
              f"{r['switch_rate']:>8.1%}{r['zero_rate']:>7.1%}{r['dominated']:>8.1%}"
              f"{r['hyperbeam']:>10.1%}{r['boom']:>7.1%}{r['status_share']:>9.1%}")
    gap = sum(abs(us[k] - them[k]) for k in METRICS)
    print("\nper-metric delta (us - humans):")
    for k in METRICS:
        print(f"  {k:<16}{us[k]:>8.1%}{them[k]:>9.1%}{us[k]-them[k]:>+9.3f}")
    print(f"  TOTAL |delta| {gap:.3f}   (anchor_style: SH 0.095, FP clone 0.124)")

    print("\nBIAS CHECK on `dominated` -- is the gap an artifact of reveal count?")
    for label, mine in (("US", True), ("HUMANS", False)):
        d = dominated_detail(ladder, mine)
        print(f"  {label:<8} dmg-moves {d['dmg_moves']:>5}  had-a-known-dmg-alt "
              f"{d['with_alt']:>5} ({d['with_alt']/d['dmg_moves']:.1%})  "
              f"flagged {d['flagged']:>4}  rate/all {d['rate_all']:.2%}  "
              f"rate|alt {d['rate_given_alt']:.2%}  "
              f"distinct moves revealed/mon {d['revealed_per_mon']:.2f}")


if __name__ == "__main__":
    main()
