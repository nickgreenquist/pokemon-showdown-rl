#!/usr/bin/env python
"""LADDER R1 final readout — all three pre-registered obligations, in one pass.

WHY THIS WRITES MARKDOWN. `results/` is gitignored with zero tracked files, so
the JSONL and the 200+ replays live on disk and in mirrors but NEVER in git.
The same lesson `scripts/README.md` records for grader scripts applies harder
here: this script plus its committed output are the only provenance that
survives losing every copy of `results/ladder/`. Run it, commit the markdown.

The three obligations, all written result-blind during the run:
  (i)   rating trajectory rebuilt from the replays, because poke-env
        sporadically drops `battle.rating`;
  (ii)  the rematch cell WITH each cell's opponent-rating distribution,
        because rematches are rating-matched by construction and that
        confound reads exactly like the effect;
  (iii) played games vs non-games, classified from replay TEXT and behaviour
        (see ladder_classify.py for the amended rule).

JOIN TRAPS, both live: battle tags may carry a secret `-<token>` suffix, so
join on the NUMERIC id; and local-smoke replays share the real
`nickgen1rbrlbot` filename prefix, so filter by id WIDTH (real = 10 digits).
"""
import argparse, json, math, re, statistics, sys, collections
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
REAL_ID = re.compile(r"gen1randombattle-(\d{9,})")
ANY_ID = re.compile(r"gen1randombattle-(\d+)")


def load(jsonl, repdir, name):
    rows = [json.loads(l) for l in open(jsonl) if l.strip()]
    reps = {}
    for p in Path(repdir).glob("*.html"):
        m = REAL_ID.search(p.name)
        if m:
            reps[m.group(1)] = p.read_text(errors="ignore")
    for r in rows:
        r["_id"] = ANY_ID.search(r["tag"]).group(1)
        t = reps.get(r["_id"], "")
        r["_text"] = t
        # true ratings off the |player| lines — authoritative, unlike the JSONL
        pl = re.findall(r"\|player\|(p[12])\|([^|]*)\|[^|]*\|(\d+)", t)
        r["_true_rating"] = r["_true_opp"] = None
        for slot, who, elo in pl:
            if who == name:
                r["_true_rating"] = int(elo)
            else:
                r["_true_opp"] = int(elo)
    return rows, reps


# ===================== BI-4: obligations (iv) and (v) =====================
# Half-open and EXHAUSTIVE by construction, plus an explicit catch-all. R1's
# published band table summed to 194 of 200 because it was built from the
# JSONL's advisory `opponent_rating` column, which is None on six battles;
# the replays carry the true value on 200/200. So the bands here read
# `_true_opp` (from the replay `|player|` lines) and the exhaustiveness is
# ASSERTED rather than hoped for.
BANDS = [("<1100", None, 1100), ("1100-1199", 1100, 1200),
         ("1200-1299", 1200, 1300), ("1300-1399", 1300, 1400),
         (">=1400", 1400, None)]
UNKNOWN = "unrated_or_unknown"
# R1's cells, for the ONE permitted side-by-side. [1300,1400) is the only
# licensed comparison and it carries no threshold — see the pre-reg's
# `comparison_ruling.only_licensed_comparison.power_disclosure`.
# CORRECTED 2026-08-28 (BI-4): rebuilt from the replays, 200/200 asserted.
# The superseded advisory-column cells (48/43/28/47/28, sum 194) sit beside
# `bands_CORRECTED_2026_08_28` in ladder_r3.yaml; do not restore them.
R1_BANDS = {"<1100": (49, 0.694), "1100-1199": (44, 0.477),
            "1200-1299": (28, 0.464), "1300-1399": (47, 0.319),
            ">=1400": (32, 0.375)}
R1_CATS = {"forfeit": 29, "played_out": 161, "no_show": 4, "timeout_midgame": 6}


def band_of(elo):
    if elo is None:
        return UNKNOWN
    for lbl, lo, hi in BANDS:
        if (lo is None or elo >= lo) and (hi is None or elo < hi):
            return lbl
    return UNKNOWN


def implied_rating(rate, opp_elo):
    """Invert Elo's expected-score curve: E = 1/(1+10^((opp-me)/400)).

    Undefined at a 0.000 or 1.000 cell (the inverse diverges), which is a
    real limitation of the estimator and not a missing number -- reported as
    `--` rather than clipped, because clipping would invent a bound.
    """
    if opp_elo is None or not (0 < rate < 1):
        return None
    return opp_elo - 400 * math.log10(1 / rate - 1)


def binom_se(rate, n):
    return math.sqrt(rate * (1 - rate) / n) if n else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jsonl", default="results/ladder/L2.battles.jsonl")
    ap.add_argument("--replays", default="results/ladder/replays")
    ap.add_argument("--name", default="nickgen1rbrlbot")
    ap.add_argument("--label", default="R1",
                    help="run label for headings, e.g. R3")
    ap.add_argument("--compare-jsonl", default="results/ladder/L2.battles.jsonl",
                    help="the OTHER run's JSONL, for obligation (v)'s "
                         "opponent-pool overlap. Skipped if absent or if it "
                         "is the same file as --jsonl.")
    ap.add_argument("--out", default="LADDER_R1_READOUT.md",
                    help="TRACKED path on purpose: results/ is "
                         "gitignored, so the readout must land in "
                         "the repo to survive losing results/")
    args = ap.parse_args()

    import ladder_classify as lc
    from ladder import ladder_snapshot

    rows, reps = load(args.jsonl, args.replays, args.name)
    n = len(rows)
    w = sum(1 for r in rows if r["outcome"] == "win")

    # (iii) played vs non-games, using the RATIFIED instrument
    for r in rows:
        r["_cat"] = lc.classify(r["_text"], args.name) if r["_text"] else "NO_REPLAY"
    cats = collections.Counter(r["_cat"] for r in rows)
    played = [r for r in rows if r["_cat"] != "no_show"]
    pw = sum(1 for r in played if r["outcome"] == "win")

    # (i) rating trajectory
    have_jsonl = sum(1 for r in rows if r.get("rating"))
    have_true = sum(1 for r in rows if r["_true_rating"])
    traj = [(r["index"], r["_true_rating"] or r.get("rating")) for r in rows]
    traj = [(i, v) for i, v in traj if v]

    # (ii) rematch cell
    seen, first, re_ = set(), [], []
    for r in rows:
        (re_ if r["opponent"] in seen else first).append(r)
        seen.add(r["opponent"])

    def cell(rs):
        if not rs:
            return None
        wr = sum(1 for x in rs if x["outcome"] == "win") / len(rs)
        opp = [x["_true_opp"] or x.get("opponent_rating") for x in rs]
        opp = [o for o in opp if o]
        return dict(n=len(rs), w=sum(1 for x in rs if x["outcome"] == "win"),
                    rate=wr, turns=statistics.mean(x["turns"] for x in rs),
                    opp_mean=statistics.mean(opp) if opp else None,
                    opp_med=statistics.median(opp) if opp else None,
                    opp_n=len(opp))
    fc, rc = cell(first), cell(re_)
    snap = ladder_snapshot("gen1randombattle", args.name)

    L = []
    A = L.append
    A(f"# LADDER {args.label} — final readout (n = {n})\n")
    A("Generated by `scripts/ladder_readout.py`. **This file is the committed")
    A("provenance for these numbers** — `results/ladder/` is gitignored, so the")
    A("JSONL and the replays are not in git and exist only on disk and in")
    A("mirrors. Everything below is reproducible by re-running that script")
    A("against those artifacts.\n")
    A("## Status of the primary read\n")
    A(f"- Profile reachable: **{snap.get('profile_ok')}**")
    A(f"- Board reachable: **{snap.get('board_ok')}**")
    A(f"- Listed on the top-500: **{snap.get('listed')}**")
    A(f"- Top-500 admission cutoff: Elo **{snap.get('cutoff_elo')}**")
    # CORRECTED 2026-08-26, and the GENERATOR was fixed 2026-08-27. This
    # block used to branch on `listed` from the TOP-500 LEADERBOARD and emit
    # "GXE AND GLICKO ARE UNMEASURED. Showdown publishes them only for
    # listed accounts. The pre-registered primary read therefore does not
    # exist for this run." **That is false.** The leaderboard JSON contains
    # only listed accounts, but the USER PROFILE
    # (https://pokemonshowdown.com/users/<userid>.json) carries GXE and
    # Glicko-1 for ANY rated account. LADDER R1 was declared unmeasurable on
    # that branch and its numbers were on the profile the whole time
    # (GXE 59.6%, Glicko-1 1573 +/- 27, Elo 1292). Being unlisted is a
    # statement about the TOP-500 BOARD, never about whether a rating exists.
    # `ladder.ladder_snapshot` now reads both sources, so the branch below
    # keys on whether a RATING exists rather than on where it is ranked.
    if snap.get("rd") is not None:
        A(f"\n**PRIMARY READ (server-computed, via "
          f"{snap.get('rating_source')}):** GXE **{snap.get('gxe')}%**, "
          f"Glicko-1 **{snap['r']:.0f} +/- {snap['rd']:.0f}**, "
          f"Elo **{snap['elo']:.0f}**, record "
          f"**{snap.get('w')}-{snap.get('l')}**.")
        A("Quoted WITH n, WITH the policy kind and WITH the board position,")
        A("exactly as pre-registered. DESCRIPTIVE — the ladder credits no")
        A("lever, and being unlisted is a fact about the board, not about")
        A("whether this rating exists.\n")
        rule = {"glicko_rd_max": 40, "min_battles": 200}
        met = (snap["rd"] <= rule["glicko_rd_max"]) and (n >= rule["min_battles"])
        A(f"- Stopping rule (`rd <= 40 AND n >= 200`): "
          f"**{'SATISFIED' if met else 'NOT satisfied'}** "
          f"at rd {snap['rd']:.1f}, n {n}.")
        A("  (R1's `L2.report.json` says `stopped_by_rule: false`. That is an")
        A("  ARTIFACT of the runner reading rd off the leaderboard it was not")
        A("  on — not a statement that the rule failed. Fixed 2026-08-27.)\n")
    elif snap.get("profile_ok") and snap.get("rated") is False:
        A("\n**NO RATING YET** — the profile is reachable and reports no")
        A("rated games in this format. A real negative, not a missing read.\n")
    else:
        A("\n**PRIMARY READ UNAVAILABLE — ENDPOINT FAILURE, NOT ABSENCE.**")
        A(f"profile_ok={snap.get('profile_ok')} "
          f"({snap.get('profile_error')}); "
          f"board_ok={snap.get('board_ok')} ({snap.get('board_error')}).")
        A("Do NOT read this as 'we have no rating' — that inversion is")
        A("exactly what cost R1 two days.\n")
    A("## Headline (all DESCRIPTIVE — the ladder credits no lever)\n")
    A("| | |")
    A("|---|---|")
    A(f"| rated battles | {n} |")
    A(f"| record | {w}–{n-w} (**{w/n:.3f}**) |")
    A(f"| played-only (ratified cut, excludes no-shows) | {pw}/{len(played)} "
      f"(**{pw/len(played):.3f}**) |")
    # EVERY VALUE IN `traj` IS A **PRE-BATTLE** RATING — verified on 195/195
    # consecutive pairs of the R1 run (sign(rating[i+1]-rating[i]) matches
    # outcome[i] 100% of the time). So `traj[-1]` is the rating going INTO
    # the last battle, not the rating after it. This generator used to label
    # it "PS Elo, final" and that is the origin of the "Elo 1311" this repo
    # quoted for two days; the true final was 1292, one loss later. The
    # PROFILE is authoritative for the final value and is used when present.
    if traj:
        if snap.get("elo") is not None:
            A(f"| PS Elo, final (profile, authoritative) | "
              f"**{snap['elo']:.0f}** |")
            A(f"| PS Elo, last PRE-battle value | {traj[-1][1]} |")
        else:
            A(f"| PS Elo, last PRE-battle value (profile unreachable — "
              f"NOT the final) | **{traj[-1][1]}** |")
        A(f"| PS Elo, highest observed (pre-battle) | "
          f"{max(v for _, v in traj)} |")
        A(f"| PS Elo, start | {traj[0][1]} |")
    A(f"| distinct opponents | {len({r['opponent'] for r in rows})} |")
    A(f"| mean turns | {statistics.mean(r['turns'] for r in rows):.1f} |")
    A("\n## Obligation (i) — rating trajectory from the replays\n")
    A(f"poke-env recorded a rating on **{have_jsonl}/{n}** battles; the replays")
    A(f"carry the server's true value on **{have_true}/{n}**. The replays are")
    A("authoritative and the JSONL column is advisory, exactly as pre-registered.\n")
    if traj:
        step = max(1, len(traj) // 20)
        A("PRE-battle Elo by battle index (every "
          f"{step}): " + " → ".join(str(v) for i, v in traj[::step]) + "\n")
        A("Every value above is the rating going INTO that battle. The final")
        A("rating is one battle later and comes from the profile, not here.\n")
    A("## Obligation (ii) — the rematch cell\n")
    A("| cell | n | W | win rate | mean turns | opp Elo mean | opp Elo median |")
    A("|---|---|---|---|---|---|---|")
    for lbl, c in (("first encounter", fc), ("rematch (2nd+)", rc)):
        if c:
            A(f"| {lbl} | {c['n']} | {c['w']} | {c['rate']:.3f} | "
              f"{c['turns']:.1f} | "
              f"{c['opp_mean']:.0f} | {c['opp_med']:.0f} |" if c["opp_mean"]
              else f"| {lbl} | {c['n']} | {c['w']} | {c['rate']:.3f} | "
                   f"{c['turns']:.1f} | — | — |")
    A("\n**Read the opponent-rating columns before the win-rate columns.**")
    A("Rematches are rating-matched by construction — opponents met twice skew")
    A("stronger — so a lower rematch win rate is predicted with zero")
    A("memorisation. This cell is descriptive and attaches to no lever.\n")
    # ---------------- obligation (iv): THE BAND TABLE ----------------
    cells = collections.OrderedDict((lbl, []) for lbl, _, _ in BANDS)
    cells[UNKNOWN] = []
    for r in rows:
        cells[band_of(r["_true_opp"])].append(r)
    total_cells = sum(len(v) for v in cells.values())
    assert total_cells == n, (
        f"band table is not exhaustive: cells sum to {total_cells} but there "
        f"are {n} rated battles. This is exactly how R1's table lost six "
        f"battles; the pre-reg requires the assertion, so FIX IT rather than "
        f"publishing a table that does not reconcile."
    )
    A("## Obligation (iv) — the band table (BI-4)\n")
    A("Opponent Elo comes from the replay `|player|` lines, **never** the")
    A("JSONL's advisory `opponent_rating` column — building R1's table from")
    A("that column is what silently dropped six of its 200 battles. Bands are")
    A("half-open, exhaustive, and the sum is ASSERTED against n.\n")
    A("| band | n | W | win rate | binom se | opp Elo mean | opp Elo med | "
      "implied true rating | R1 (n, rate) |")
    A("|---|---|---|---|---|---|---|---|---|")
    for lbl in list(cells):
        rs = cells[lbl]
        if not rs:
            A(f"| {lbl} | 0 | — | — | — | — | — | — | "
              f"{R1_BANDS.get(lbl, ('—', '—'))[0]}, "
              f"{R1_BANDS.get(lbl, ('—', '—'))[1]} |")
            continue
        cw = sum(1 for x in rs if x["outcome"] == "win")
        rate = cw / len(rs)
        opp = [x["_true_opp"] for x in rs if x["_true_opp"]]
        om = statistics.mean(opp) if opp else None
        omed = statistics.median(opp) if opp else None
        imp = implied_rating(rate, om)
        r1 = R1_BANDS.get(lbl)
        A(f"| {lbl} | {len(rs)} | {cw} | {rate:.3f} | "
          f"{binom_se(rate, len(rs)):.3f} | "
          f"{f'{om:.0f}' if om else '—'} | {f'{omed:.0f}' if omed else '—'} | "
          f"{f'{imp:.0f}' if imp else '—'} | "
          f"{f'{r1[0]}, {r1[1]:.3f}' if r1 else '—'} |")
    A(f"\n**Cells sum to {total_cells} = n. Asserted, not eyeballed.**\n")
    agg_opp = [r["_true_opp"] for r in rows if r["_true_opp"]]
    agg_imp = implied_rating(w / n, statistics.mean(agg_opp)) if agg_opp else None
    if agg_imp:
        A(f"Aggregate implied true rating (all {len(agg_opp)} rated-opponent "
          f"battles, mean opp Elo {statistics.mean(agg_opp):.0f}): "
          f"**{agg_imp:.0f}**.\n")
    A("**CAVEAT, carried verbatim from R1: the per-band implied rating trends")
    A("UPWARD with opponent strength.** That is either logistic")
    A("mis-specification or a real effect, and at n = 28-47 per band this repo")
    A("declines to resolve it. **Only the [1300,1400) cell is a licensed")
    A("comparison, it is one-sided upward against ~0.50, and NO THRESHOLD")
    A("ATTACHES TO IT — 2*se_diff at matched n is ~0.195, about twenty points")
    A("of win rate, so this cell can only resolve differences nobody would")
    A("need statistics to see.**\n")

    # ------- obligation (v): opponent-pool overlap + behavioural channel -------
    A("## Obligation (v) — opponent-pool overlap and the behavioural channel\n")
    from ladder import to_id
    mine = [to_id(r["opponent"]) for r in rows]
    cmp_path = Path(args.compare_jsonl)
    if cmp_path.exists() and cmp_path.resolve() != Path(args.jsonl).resolve():
        other = {to_id(json.loads(l)["opponent"])
                 for l in open(cmp_path) if l.strip()}
        inter = set(mine) & other
        ins = [r for r, u in zip(rows, mine) if u in inter]
        outs = [r for r, u in zip(rows, mine) if u not in inter]
        A(f"Compared against `{cmp_path}` ({len(other)} distinct opponents).\n")
        A("| cell | n | W | win rate |")
        A("|---|---|---|---|")
        for lbl, rs in (("opponents ALSO faced in the other run", ins),
                        ("opponents faced only in this run", outs)):
            if rs:
                cw = sum(1 for x in rs if x["outcome"] == "win")
                A(f"| {lbl} | {len(rs)} | {cw} | {cw/len(rs):.3f} |")
        A(f"\nDistinct-opponent intersection: **{len(inter)}**.\n")
    else:
        A(f"Overlap SKIPPED — `{cmp_path}` is absent or identical to --jsonl.")
        A("State this in the readout rather than omitting the obligation.\n")
    A("Game categories beside R1's:\n")
    A("| category | this run | R1 |")
    A("|---|---|---|")
    for k in ("forfeit", "played_out", "no_show", "timeout_midgame"):
        A(f"| {k} | {cats.get(k, 0)} | {R1_CATS[k]} |")
    ff, r1ff = cats.get("forfeit", 0) / n, R1_CATS["forfeit"] / 200
    A(f"\nForfeit rate **{ff:.3f}** vs R1's **{r1ff:.3f}**.")
    A("**If these differ materially that is a candidate explanation for a")
    A("rating difference having NOTHING to do with the object**, and it is")
    A("named here in advance so it cannot be discovered later as a convenient")
    A("excuse. Descriptive; attaches to no lever.\n")
    # GATED ON THE LABEL, not on the presence of a timeout. The first version
    # keyed on `"timeout_midgame" in cats`, which is true of R1 as well -- so
    # an R1 readout claimed R1 had suffered websocket disconnections, which is
    # false and would have been published as provenance. A disclosure that
    # attaches itself to the wrong run is worse than no disclosure.
    if args.label.upper() == "R3":
        A("**R3 DISCLOSURE, and it does not apply to R1: real websocket")
        A("disconnections occurred during this run — 10 runner launches across")
        A("2 supervisor generations (attempt numbering restarts at 04:01), 8")
        A("SIGKILL terminations of a socket-less runner (7 recorded by the")
        A("watchdog) at n = 16, 72 (x3), 126, 138, 178 (x2), plus the battle-10")
        A("crash that predates the supervisor — all healed unattended. So a")
        A("`timeout_midgame` here may be OUR socket dying rather than a human")
        A("abandoning. That is a DIFFERENT thing from R1's six and the two")
        A("must not be pooled silently.**\n")
        pw_, pl_ = snap.get("w"), snap.get("l")
        if pw_ is not None and pl_ is not None and (pw_, pl_) != (w, n - w):
            wins_note = ("wins match exactly" if pw_ == w else
                         "WINS DO NOT MATCH — investigate before quoting")
            A(f"**Where the record differs: the profile says {pw_}-{pl_} "
              f"({pw_ + pl_} rated games); this JSONL says {w}-{n - w} "
              f"({n}). The {wins_note}; the {pl_ - (n - w)} extra "
              "server-side losses are battles in flight when our socket "
              "died — the server timed the seat out and scored the loss, "
              "and the dead runner never logged the battle. THE PRIMARY "
              "RATING INCLUDES THEM; the 200-battle tally does not. They "
              "are our outages, not opponent behaviour.**\n")
        A("**R3 DISCLOSURE, blind breach: a crash-resume printed the live")
        A("rating into the run log at battle 10. It does not void the read --")
        A("the stopping rule is mechanical and cannot fire before n=200 -- but")
        A("it happened and is stated here rather than omitted.**\n")
        A("**R3 DISCLOSURE, blind breach 2: the maintainer watched battle 200")
        A("live on the public board — a Hitmonchan Counter-vs-Counter mirror")
        A("that ended when the opponent forfeited. n=199 was already complete")
        A("and the stopping rule is mechanical, so no stopping decision could")
        A("attach to it; stated rather than omitted.**\n")
        A("R3's object (search@M on s80) has **ONE of three anchors: FP@20")
        A("only** — no vs-SH at the locked protocol and no BC-clone h2h")
        A("exists for search on any 50M lane (pre-reg `anchor_battery`).\n")
        A("Both accounts share a stem, so opponents can link them; 141 humans")
        A("had already played 200 games against a bot from this project before")
        A("this run started.\n")

    # ------------- obligation (vi): s/battle, computed correctly -------------
    fin = [r.get("finished_at") for r in rows if r.get("finished_at")]
    if len(fin) > 1:
        d = [b - a for a, b in zip(fin, fin[1:])]
        clean = [x for x in d if 0 < x < 900]
        A("## Obligation (vi) — seconds per battle\n")
        A(f"- whole-run mean of `finished_at` deltas: **{statistics.mean(d):.1f}** s")
        A(f"- MEDIAN (robust to outage gaps): **{statistics.median(d):.1f}** s")
        A(f"- median excluding gaps > 900 s (n={len(clean)} of {len(d)}): "
          f"**{statistics.median(clean):.1f}** s" if clean else "")
        A("\n**Never `wall_clock_sec / battles_total`** — those have different")
        A("scopes (session vs cumulative) and that division is the origin of")
        A("the wrong '217 s/battle' this repo quoted for R1. The true R1 value")
        A("is 246.5.\n")
        mt = statistics.mean(r["turns"] for r in rows)
        A(f"Mean turns **{mt:.1f}**, against R1's **25.9** and the **36.824**")
        A("measured off Foul Play@20, with the 0.944 (proxy -> ladder)")
        A("calibration that predicted ~34.8. This is the only new OBSERVABLE")
        A("this run buys beyond a rating.\n")

    A("## Obligation (iii) — played games vs non-games\n")
    A(f"Categories: `{dict(cats)}`\n")
    A(f"- all rated battles: **{w}/{n} = {w/n:.3f}** (reconciles with the board)")
    A(f"- played only, RATIFIED cut: **{pw}/{len(played)} = {pw/len(played):.3f}**")
    A("  (a no-show — opponent submitted zero moves — is not a game; a forfeit")
    A("  or a mid-game timeout IS a win, per the 2026-08-25 amendment)\n")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("\n".join(L) + "\n")
    print("\n".join(L))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
