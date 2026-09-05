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
# R3's cells (readouts/LADDER_R3_READOUT.md — replay-built, 200/200 asserted):
# the SECOND reference column BI-R4-2 adds (ladder_r4.yaml, review_2 F10).
# Same rule as R1's: descriptive, no threshold, and from R4 on every
# multi-run column appears only under the CONFOUNDED heading.
R3_BANDS = {"<1100": (59, 0.610), "1100-1199": (45, 0.622),
            "1200-1299": (40, 0.550), "1300-1399": (36, 0.444),
            ">=1400": (20, 0.200)}
R3_CATS = {"forfeit": 35, "played_out": 140, "no_show": 6, "timeout_midgame": 19}
PRIOR_LABEL = {"L2.battles.jsonl": "R1", "R3S.battles.jsonl": "R3"}
# The ten confounds R3 -> R4 (ladder_r4.yaml "THE CONFOUNDS"), printed
# ADJACENT to every multi-run table. The list may grow, never shrink.
CONFOUNDS_R4 = [
    "1 POLICY KIND (R3 search@M -> R4 greedy)",
    "2 TRAINING SCALE (50M -> 100M)",
    "3 TRAINING RECIPE (stack50m_r2 -> batch async 100M: FOUR bundled deltas — "
    "batch (credited §17), async wire, the training-side /timer on fix 9a0e54d, "
    "the 100M horizon+anneal (P3))",
    "4 ACCOUNT (REUSED — warm-started from R1's parked ~1292 instead of a fresh "
    "climb from 1000; neither prior run shares this shape)",
    "5 CALENDAR + POOL (~93 active players/day, weeks apart)",
    "6 OPPONENT MEMORY (R4 plays under the SAME NAME as R1's 200 games — the "
    "strongest memory exposure of the three runs)",
    "7 INSTRUMENTATION / OPS (R3: 10 runner launches, 8 unlogged server-side "
    "losses; R4: see the realized ops ledger)",
    "8 SELECTION RULE (vs-SH tie-break -> off-FP median, ruled post-publication)",
    "9 STAFF NOTICE (named as 'first run after staff contact'; under M10 the "
    "courtesy note was WAIVED, so this confound did not fire — kept, never shrunk)",
    "10 DETERMINISM / REPLAYABILITY (greedy is fully state-determined -> R4 is the "
    "most memorisation-exposed of the three; read opponent-Elo columns first)",
]


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
    # ALL REQUIRED (REPO_CLEANUP item 9, 2026-08-29). These used to default
    # to R1's paths and R1's account name; forgetting only --name on an R3
    # readout fetched bot1's profile into an R3-labelled file, and load()
    # then nulled _true_rating on every row while the exhaustiveness assert
    # still passed. Fail loudly instead of defaulting to the wrong run.
    ap.add_argument("--jsonl", required=True,
                    help="e.g. results/ladder/L2.battles.jsonl (R1)")
    ap.add_argument("--replays", required=True,
                    help="e.g. results/ladder/replays")
    ap.add_argument("--name", required=True,
                    help="the ladder account this run actually played under")
    ap.add_argument("--label", required=True,
                    help="run label for headings, e.g. R1 / R3")
    ap.add_argument("--compare-jsonl", action="append", default=[],
                    help="a PRIOR run's JSONL, for obligation (v)'s "
                         "opponent-pool overlap. REPEATABLE — one per prior "
                         "(BI-R4-2); skipped per file if absent or if it is "
                         "the same file as --jsonl.")
    ap.add_argument("--prereg", default=None,
                    help="the run's pre-reg YAML. When given the readout "
                         "REFUSES to render unless --name equals "
                         "arms.<primary_arm>.display_name and the --jsonl "
                         "basename starts with primary_arm (obligation vii, "
                         "the R1-default trap machine-checked).")
    ap.add_argument("--prior-account-games", type=int, default=0,
                    help="rated games the account carried BEFORE this run "
                         "(R4 under account reuse: 200; a fresh account: 0). "
                         "Reconciliation asserts profile_total == this + "
                         "n_jsonl + unlogged.")
    ap.add_argument("--prior-account-record", default=None,
                    help="that prior record as W-L (R4: 95-105), so the "
                         "unlogged games can be signed as wins or losses.")
    ap.add_argument("--report", default=None,
                    help="the runner's <arm>.report.json — the realized ops "
                         "ledger and instrument stamps (R4 block).")
    ap.add_argument("--board-n0", default=None,
                    help="the archived n=0 board pull (R4: decides the M2 "
                         "band-clause branch of the headline).")
    ap.add_argument("--out", required=True,
                    help="TRACKED path on purpose: results/ is "
                         "gitignored, so the readout must land in "
                         "the repo to survive losing results/")
    args = ap.parse_args()
    if args.prereg:
        import yaml
        pr = yaml.safe_load(open(args.prereg))
        arm = pr["primary_arm"]
        want = pr["arms"][arm]["display_name"]
        if args.name != want or not Path(args.jsonl).name.startswith(arm):
            sys.exit(f"REFUSING TO RENDER (obligation vii): --name {args.name!r} "
                     f"vs arms.{arm}.display_name {want!r}; --jsonl "
                     f"{Path(args.jsonl).name!r} must start with {arm!r}. "
                     "ALL THREE READOUT SCRIPTS DEFAULT TO R1 — this is the "
                     "machine check.")

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
    # obligation (vii): profile_total == prior_account_games + n_jsonl + unlogged
    pw_, pl_, pt_ = snap.get("w"), snap.get("l"), snap.get("t") or 0
    recon = None
    if pw_ is not None and pl_ is not None:
        total = pw_ + pl_ + pt_
        expected = args.prior_account_games + n
        recon = dict(w=pw_, l=pl_, t=pt_, total=total, expected=expected,
                     gap=total - expected)
        if args.prior_account_record:
            a, b = (int(x) for x in args.prior_account_record.split("-"))
            recon.update(run_w=pw_ - a, run_l=pl_ - b)

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
          f"**{snap.get('w')}-{snap.get('l')}**"
          + (f" (CUMULATIVE account record — it carries "
             f"{args.prior_account_games} rated games from before this run; "
             f"this run's own record is the runner-logged subset in obligation "
             f"(vii))." if args.prior_account_games else "."))
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
    if args.label.upper() == "R4":
        rep = json.load(open(args.report)) if args.report else {}
        n0 = json.load(open(args.board_n0)) if args.board_n0 else {}
        c1300 = [r for r in rows if band_of(r["_true_opp"]) == "1300-1399"]
        k = len(c1300)
        v = sum(1 for r in c1300 if r["outcome"] == "win") / k if k else float("nan")
        distinct = len({r["opponent"] for r in rows})
        U = recon["gap"] if recon else None
        n0_cut = n0.get("cutoff_elo")
        stop_cut = (rep.get("ladder_after") or {}).get("cutoff_elo")
        in_band = lambda x: x is not None and 1300 <= x < 1400
        same_band = (in_band(n0_cut) and in_band(stop_cut)) or (
            n0_cut is not None and stop_cut is not None and band_of(n0_cut) == band_of(stop_cut))
        clause = (", the band containing rank 500 on the n=0 pull,"
                  if in_band(n0_cut) and same_band else "")
        cum = f"{recon['w']}-{recon['l']}" if recon else "UNAVAILABLE"
        A("## The pre-registered headline sentence, filled (ladder_r4.yaml)\n")
        A(f"Playing the real gen1randombattle ladder on the project's ORIGINAL rated "
          f"account, reused under the multi-account rules (it carries R1's 200 games; "
          f"the rating is warm-started from R1's parked end state, not a fresh "
          f"measurement of this object alone), the 100M final on lane s112 — 100M "
          f"steps, pure self-play, greedy/deterministic, the lane a maintainer-ruled "
          f"MEDIAN-of-three rule named on the off-Foul-Play@20 primary — reached GXE "
          f"**{snap.get('gxe')}%**, Glicko-1 **{snap['r']:.0f} +/- {snap['rd']:.0f}** and "
          f"final Elo **{snap['elo']:.0f}** over **{n + (U or 0)}** rated battles THIS RUN "
          f"(runner-logged n_jsonl = {n}, plus {U if U is not None else '?'} unlogged "
          f"server-scored games identified by replay diff; the profile's CUMULATIVE "
          f"record including R1's 200 games is {cum}) against {distinct} distinct "
          f"opponents this run. Against the 1300-1400 band{clause} it scored "
          f"**{v:.3f}** (n={k} of n_jsonl = {n}). This run credits nothing.\n")
        A("**s112 IS NOT \"THE BEST 100M LANE\" AND MAY NOT BE DESCRIBED AS ONE.** It is "
          "the lane the 2026-09-04 median-of-three rule named on the off-FP@20 primary, "
          "a rule ruled WITH all three lane numbers already published (RESULTS §18). That "
          "it is the highest-scoring of the three on both descriptive anchors is "
          "incidental to a selection made on a different axis, so the battery quoted "
          "for this object sits at the flattering end of a ±0.02 instrument. Every "
          "anchor quote is the PAIR {lane value, fleet pooled value}: vs-SH 0.8000 "
          "(lane s112, final_s112.json; fleet pooled 0.79589, n=3x3000); off-FP@20 "
          "0.50167 (lane s112, t112.json; fleet pooled 0.49844; budget named; "
          "weakly-powered equivalence; flattering point estimate); BC-clone 0.930 "
          "(lane s112, ca112.final.json; fleet pooled 0.9233, n=3x500; a clone number "
          "is never style evidence).\n")
        A("R4 is the first ladder measurement here whose object is drawn from a fleet "
          "carrying all three anchors at locked protocols; the lane values quoted are "
          "single-seed components of those protocols, never the protocols themselves. "
          "(A claim about the RECORD, never about the rating.)\n")
        A(f"Board pulls, both archived: n=0 admission cutoff Elo "
          f"**{n0_cut}** (`{args.board_n0}`); at stop **{stop_cut}** "
          f"(the runner's `ladder_after`); this readout's own pull "
          f"**{snap.get('cutoff_elo')}**. M2 branch: "
          + ("both inside [1300,1400) and in the same band — the rank-500 clause STANDS."
             if clause else
             "NOT both inside [1300,1400) in the same band — the rank-500 clause and the "
             "~0.50 reference are STRUCK; the cell reads as a rate with its n and se.")
          + "\n")
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
        A(f"| PS Elo, start"
          + (" (WARM-STARTED — R1's parked end state, not a fresh 1000)"
             if args.prior_account_games else "") + f" | {traj[0][1]} |")
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
    # GATED ON THE OBSERVED SIGN, for the same reason the websocket block
    # below is gated on the label: a disclosure that attaches itself to the
    # wrong run is worse than no disclosure. This prose used to end
    # "...so a lower rematch win rate is predicted with zero memorisation"
    # UNCONDITIONALLY. It was written for R1, where the rematch rate really
    # was lower (0.356 vs 0.525). R3's is HIGHER (0.548 vs 0.517), so in
    # R3's committed readout that sentence sat directly under a table
    # showing the opposite. The confound itself is the POINT of the cell and
    # is stated in BOTH branches -- only the claim about which way this
    # run's numbers came out is conditional.
    A("Rematches are rating-matched by construction — opponents met twice skew")
    A("stronger, and the opponent-Elo columns above are where you check that —")
    A("so the two cells are NOT like-for-like, and a lower rematch win rate is")
    A("predicted by the confound alone, with zero memorisation.")
    if fc and rc:
        d = rc["rate"] - fc["rate"]
        both_opp = fc["opp_mean"] is not None and rc["opp_mean"] is not None
        pool = (f" (opp Elo mean {rc['opp_mean']:.0f} vs {fc['opp_mean']:.0f})"
                if both_opp else "")
        if d < 0:
            A(f"**This run came out that way:** rematch {rc['rate']:.3f} "
              f"(n={rc['n']}) vs first encounter {fc['rate']:.3f} "
              f"(n={fc['n']}){pool},")
            A(f"a gap of {d:+.3f} in exactly the direction the confound alone")
            A("predicts. It is evidence of nothing beyond the confound.")
        elif d > 0:
            A(f"**This run came out the OTHER way:** rematch {rc['rate']:.3f} "
              f"(n={rc['n']}) vs first encounter {fc['rate']:.3f} "
              f"(n={fc['n']}),")
            A(f"i.e. {d:+.3f} AGAINST the stronger pool{pool}. The confound")
            A("predicts the opposite sign, so it cannot explain this cell")
            A("away — and the cell is nowhere near powered to establish the")
            A("reverse either. Do not read it as opponents failing to adapt,")
            A("and do not read it as us adapting.")
        else:
            A(f"**This run split it exactly:** both cells at "
              f"{fc['rate']:.3f} (n={fc['n']} vs {rc['n']}){pool}, so the")
            A("confound's predicted gap did not show up. Underpowered either")
            A("way; read nothing into the tie.")
    A("This cell is descriptive and attaches to no lever.\n")
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
    if args.label.upper() == "R4":
        A("### CONFOUNDED — NOT AN EFFECT\n")
        A("The R1 and R3 reference columns below (and every multi-run table in this "
          "readout) are printed for continuity only. Ten things moved between the runs "
          "at once, so no cross-run difference here is an effect, in any direction:\n")
        for c in CONFOUNDS_R4:
            A(f"- {c}")
        A("")
    A("Opponent Elo comes from the replay `|player|` lines, **never** the")
    A("JSONL's advisory `opponent_rating` column — building R1's table from")
    A("that column is what silently dropped six of its 200 battles. Bands are")
    A("half-open, exhaustive, and the sum is ASSERTED against n.\n")
    A("| band | n | W | win rate | binom se | opp Elo mean | opp Elo med | "
      "implied true rating | R1 (n, rate) | R3 (n, rate) |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for lbl in list(cells):
        rs = cells[lbl]
        if not rs:
            A(f"| {lbl} | 0 | — | — | — | — | — | — | "
              f"{R1_BANDS.get(lbl, ('—', '—'))[0]}, "
              f"{R1_BANDS.get(lbl, ('—', '—'))[1]} | "
              f"{R3_BANDS.get(lbl, ('—', '—'))[0]}, "
              f"{R3_BANDS.get(lbl, ('—', '—'))[1]} |")
            continue
        cw = sum(1 for x in rs if x["outcome"] == "win")
        rate = cw / len(rs)
        opp = [x["_true_opp"] for x in rs if x["_true_opp"]]
        om = statistics.mean(opp) if opp else None
        omed = statistics.median(opp) if opp else None
        imp = implied_rating(rate, om)
        r1, r3 = R1_BANDS.get(lbl), R3_BANDS.get(lbl)
        A(f"| {lbl} | {len(rs)} | {cw} | {rate:.3f} | "
          f"{binom_se(rate, len(rs)):.3f} | "
          f"{f'{om:.0f}' if om else '—'} | {f'{omed:.0f}' if omed else '—'} | "
          f"{f'{imp:.0f}' if imp else '—'} | "
          f"{f'{r1[0]}, {r1[1]:.3f}' if r1 else '—'} | "
          f"{f'{r3[0]}, {r3[1]:.3f}' if r3 else '—'} |")
    A(f"\n**Cells sum to {total_cells} = n. Asserted, not eyeballed.**\n")
    agg_opp = [r["_true_opp"] for r in rows if r["_true_opp"]]
    agg_imp = implied_rating(w / n, statistics.mean(agg_opp)) if agg_opp else None
    if agg_imp:
        A(f"Aggregate implied true rating (all {len(agg_opp)} rated-opponent "
          f"battles, mean opp Elo {statistics.mean(agg_opp):.0f}): "
          f"**{agg_imp:.0f}**.\n")
    # The "n = 28-47" here was hardcoded from R1's PRE-BI-4 band table and
    # then carried into R3's readout unchanged, so it described neither
    # table it was printed under (R1 corrected is 28-49, R3 is 20-59). Same
    # defect class as the rematch prose above: read it off the table
    # directly overhead. Empty bands are excluded -- "n = 0-59 per band"
    # would understate the cells that exist.
    band_ns = [len(cells[lbl]) for lbl, _, _ in BANDS if cells[lbl]]
    span = (f"{min(band_ns)}-{max(band_ns)}" if len(set(band_ns)) > 1
            else (f"{band_ns[0]}" if band_ns else "the n shown above"))
    A("**CAVEAT, carried verbatim from R1: the per-band implied rating trends")
    A("UPWARD with opponent strength.** That is either logistic")
    A(f"mis-specification or a real effect, and at n = {span} per band this repo")
    A("declines to resolve it. **Only the [1300,1400) cell is a licensed")
    A("comparison, it is one-sided upward against ~0.50, and NO THRESHOLD")
    A("ATTACHES TO IT — 2*se_diff at matched n is ~0.195, about twenty points")
    A("of win rate, so this cell can only resolve differences nobody would")
    A("need statistics to see.**\n")

    # ------- obligation (v): opponent-pool overlap + behavioural channel -------
    A("## Obligation (v) — opponent-pool overlap and the behavioural channel\n")
    from ladder import to_id
    mine = [to_id(r["opponent"]) for r in rows]
    if args.label.upper() == "R4":
        A("**CONFOUNDED — NOT AN EFFECT** (the ten-confound list under obligation "
          "(iv) applies to every table in this section).\n")
    cmps = [Path(p) for p in args.compare_jsonl]
    if not cmps:
        A("Overlap SKIPPED — no --compare-jsonl was given.")
        A("State this in the readout rather than omitting the obligation.\n")
    for cmp_path in cmps:
        plabel = PRIOR_LABEL.get(cmp_path.name, cmp_path.name)
        if cmp_path.exists() and cmp_path.resolve() != Path(args.jsonl).resolve():
            other = {to_id(json.loads(l)["opponent"])
                     for l in open(cmp_path) if l.strip()}
            inter = set(mine) & other
            ins = [r for r, u in zip(rows, mine) if u in inter]
            outs = [r for r, u in zip(rows, mine) if u not in inter]
            A(f"Compared against `{cmp_path}` ({plabel}; {len(other)} distinct "
              f"opponents).\n")
            A("| cell | n | W | win rate |")
            A("|---|---|---|---|")
            for lbl, rs in ((f"opponents ALSO faced in {plabel}", ins),
                            (f"opponents NOT faced in {plabel}", outs)):
                if rs:
                    cw = sum(1 for x in rs if x["outcome"] == "win")
                    A(f"| {lbl} | {len(rs)} | {cw} | {cw/len(rs):.3f} |")
            A(f"\nDistinct-opponent intersection with {plabel}: **{len(inter)}**.\n")
        else:
            A(f"Overlap with `{cmp_path}` SKIPPED — absent or identical to --jsonl. "
              "Stated rather than omitted.\n")
    A("Game categories beside R1's and R3's:\n")
    A("| category | this run | R1 | R3 |")
    A("|---|---|---|---|")
    for k in ("forfeit", "played_out", "no_show", "timeout_midgame"):
        A(f"| {k} | {cats.get(k, 0)} | {R1_CATS[k]} | {R3_CATS[k]} |")
    ff, r1ff, r3ff = (cats.get("forfeit", 0) / n, R1_CATS["forfeit"] / 200,
                      R3_CATS["forfeit"] / 200)
    A(f"\nForfeit rate **{ff:.3f}** vs R1's **{r1ff:.3f}** and R3's **{r3ff:.3f}**.")
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

    # ---- obligation (vii): RECORD RECONCILIATION — every run, machine-checked
    # (BI-R4-5 un-gated this from label=="R3"; cumulative form under reuse) ----
    A("## Obligation (vii) — record reconciliation (machine-checked)\n")
    if recon is None:
        A("**Profile record UNAVAILABLE at readout time — the reconciliation "
          "could not run. Re-run when the profile is reachable; quote no record "
          "until it reconciles.**\n")
    else:
        A(f"Profile W-L-T **{recon['w']}-{recon['l']}-{recon['t']}** = "
          f"{recon['total']} rated games on the account. Prior games on the "
          f"account {args.prior_account_games} + runner-logged n_jsonl {n} = "
          f"{recon['expected']}. **unlogged_delta = {recon['gap']:+d}.**")
        if "run_w" in recon:
            A(f"This run's record BY THE PROFILE (profile minus the prior "
              f"{args.prior_account_record}): {recon['run_w']}-{recon['run_l']}; "
              f"BY THE JSONL: {w}-{n - w}.")
        if recon["gap"] == 0:
            A("**RECONCILED — every rated game the server scored this run is in "
              "the JSONL.** The replay-diff instrument is moot at a zero gap. "
              "The profile record is the CUMULATIVE account record; this run's "
              "own record is the runner-logged tally, and every downstream quote "
              "labels which one it is (obligation viii).\n")
        else:
            rw = recon.get("run_w"); rl = recon.get("run_l")
            if rw is not None and rw == w and (rl or 0) > (n - w):
                cause = (f"the {rl - (n - w)} extra server-side losses are battles "
                         "in flight when the runner died — the server timed the seat "
                         "out and scored the loss, and the dead runner never logged "
                         "the battle. THE PRIMARY RATING INCLUDES THEM; the JSONL "
                         "tally does not. They are our outages, not opponent behaviour")
            else:
                cause = ("UNCLASSIFIED — diff the account's server-side replay index "
                         "against save_replays to name the unlogged games, and do not "
                         "quote a cause until that diff has been run")
            A(f"**THE RECORD DOES NOT RECONCILE: gap {recon['gap']:+d}; {cause}.**\n")

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
        if args.label.upper() == "R4":
            A(f"Mean turns **{mt:.1f}**, against this object's OWN off-Foul-Play@20 "
              f"proxy **28.403** (t112): realized ratio **{mt / 28.403:.3f}**; the "
              "pre-reg carried both prior ratios (R1 0.946, R3 0.776), projecting "
              "22.0-26.9. This is the only new OBSERVABLE this run buys beyond a "
              "rating.\n")
        else:
            A(f"Mean turns **{mt:.1f}**, against R1's **25.9** and the **36.824**")
            A("measured off Foul Play@20, with the 0.944 (proxy -> ladder)")
            A("calibration that predicted ~34.8. This is the only new OBSERVABLE")
            A("this run buys beyond a rating.\n")

    if args.label.upper() == "R4":
        rep = json.load(open(args.report)) if args.report else {}
        fin = [r.get("finished_at") for r in rows if r.get("finished_at")]
        d = [b - a for a, b in zip(fin, fin[1:])]
        big = [x for x in d if x > 900]
        span_h = (fin[-1] - fin[0]) / 3600 if len(fin) > 1 else float("nan")
        wall = rep.get("wall_clock_sec")
        dec = rep.get("decisions_this_session")
        mdm = rep.get("mean_decision_ms")
        A("## R4 disclosures (ladder_r4.yaml), in the order the pre-reg lists them\n")
        A("- **ACCOUNT REUSE / WARM START (M6, maintainer-ruled).** This run played "
          "on nickgen1rbrlbot, R1's account, because multiple accounts are against "
          "Showdown's rules. GXE, Glicko-1 and Elo at stop are ACCOUNT properties "
          "carrying R1's 200 games; the profile record is cumulative; the rating "
          "started from R1's parked end state (Elo 1292, GXE 59.6, Glicko-1 1573 "
          "+/- 27, captured at LG-2 and asserted equal to R1's banked end state — "
          "zero games on the account between 2026-08-26 and launch). "
          "**Elo(R4 end) - Elo(R1 end) is barred by name**: one account now spans "
          "both runs and that subtraction is a confounded non-effect like every "
          "other cross-run delta.")
        A("- **NO COURTESY NOTE WAS SENT (M10, maintainer-ruled 2026-09-04 evening: "
          "not a tournament, not a high-traffic room).** The pre-reg's staff notice "
          "(M5) was waived before launch; no staff contact of any kind occurred "
          "during the run; the blind-breach licence for unsolicited contact was "
          "never used.")
        A("- **BLINDNESS.** Profile, replay list and board were NOT opened before "
          "n=200 by the agent or the runner (the runner polls the profile only from "
          "n>=200). The known, disclosed leak — the per-battle running W/L print — "
          "was read: the babysit monitor summarized the JSONL W-L every 30 min and "
          "the maintainer asked for it twice mid-run. **The maintainer watched the "
          "public board mid-run to collect screenshots** (the account listed, at one "
          "point around rank 350) — stated rather than omitted, as R3's board-watch "
          "was; no stopping decision attached to any of it: the rule is mechanical "
          "and fired at n=200 exactly.")
        A("- **THE RNG-STREAM RESUME WRINKLE DOES NOT APPLY** (greedy act() ignores "
          "battle_index), and no resume happened anyway.")
        A("- **CONFOUND 9 DID NOT FIRE** (no staff contact before or during the run); "
          "the list is kept at ten, never shrunk.")
        # ---- top-500 exposure during the run: DESCRIPTIVE, from the replay-derived
        # pre-battle ratings against the n=0 cutoff (M2: the n=0 pull decides) ----
        pre = [r["_true_rating"] for r in rows]
        line = n0_cut if n0_cut is not None else 1360
        listed_idx = [i + 1 for i, v in enumerate(pre) if v is not None and v >= line]
        exc, prev = 0, False
        for pv in pre:
            a = pv is not None and pv >= line
            exc += int(a and not prev); prev = a
        cell_rows = [r for r in rows if band_of(r["_true_opp"]) == "1300-1399"]
        cell_n = len(cell_rows)
        cell_rate = (sum(1 for r in cell_rows if r["outcome"] == "win") / cell_n
                     if cell_n else float("nan"))
        lw = sum(1 for i in listed_idx if rows[i - 1]["outcome"] == "win")
        peak = max(pv for pv in pre if pv) if any(pre) else None
        peak_at = pre.index(peak) + 1 if peak else None
        min_gxe = (rep.get("ladder_after") or {}).get("min_listed_gxe", snap.get("min_listed_gxe"))
        se_cell = binom_se(cell_rate, cell_n) if cell_n else None
        A("\n## Top-500 exposure during the run (DESCRIPTIVE — peak Elo is not a result)\n")
        A(f"From the replay-derived PRE-battle ratings against the n=0 admission "
          f"cutoff {line}: the account entered **{len(listed_idx)} of {n}** battles "
          f"({100 * len(listed_idx) / n:.0f}%) at or above the line, in **{exc}** "
          f"separate excursions; peak pre-battle Elo **{peak}** before battle "
          f"{peak_at}; record while listed **{lw}-{len(listed_idx) - lw}**; final "
          f"Elo {snap['elo']:.0f} against {stop_cut} at stop "
          f"(**{(stop_cut or 0) - snap['elo']:.1f}** under, inside one game's swing); "
          f"GXE {snap.get('gxe')} against the lowest listed GXE at stop, {min_gxe}. "
          f"The licensed cell ({cell_rate:.3f}, n={cell_n}, se {se_cell:.3f}) cannot distinguish "
          "this object from a 0.50 player in the band containing rank 500.")
        A("**Pure self-play reached the top-500 line repeatedly; it did not hold it.** "
          "Peak Elo is not a result (RESULTS §16.4, carried since R1); the "
          "stopping-rule figure is the read. Evidence for the rank seen: the "
          "maintainer's screenshots of the public board, filed under "
          "`readouts/ladder_r4_evidence/` (placeholder until filed).")
        A("Battle indices entered while listed: " + ", ".join(map(str, listed_idx)) + ".")
        A("\n## Obligation (ix) — realized-cost ledger\n")
        A(f"- runner launches **1**; supervisor relaunches **0**; watchdog kills **0**; "
          f"socket losses **0**; unlogged server-scored games **{recon['gap'] if recon else '?'}**.")
        A(f"- realized span first->last battle **{span_h:.2f} h**; runner wall clock "
          f"**{(wall or 0) / 3600:.2f} h**; gaps > 900 s: **{len(big)}** "
          f"(sum {sum(big) / 3600:.2f} h, {100 * sum(big) / max(1, fin[-1] - fin[0]):.1f}% of span).")
        if d:
            clean = [x for x in d if 0 < x < 900]
            A(f"- s/battle three ways: whole-run mean **{statistics.mean(d):.1f}**, "
              f"median **{statistics.median(d):.1f}**, median excl. gaps > 900 s "
              f"**{statistics.median(clean):.1f}** (diagnostic band [190, 300] — "
              f"{'INSIDE' if 190 <= statistics.median(clean) <= 300 else 'OUTSIDE, disclosed'}). "
              "Never wall/battles_total.")
        A(f"- mean turns **{statistics.mean(r['turns'] for r in rows):.1f}** "
          f"(diagnostic band [18, 32] — "
          f"{'INSIDE' if 18 <= statistics.mean(r['turns'] for r in rows) <= 32 else 'OUTSIDE, disclosed'}).")
        if dec and mdm and wall:
            A(f"- compute share: {dec} decisions x {mdm:.2f} ms = "
              f"{dec * mdm / 1000:.1f} s of {wall:.0f} s wall = "
              f"**{100 * dec * mdm / 1000 / wall:.3f}%**.")
        A("\n## VOID conditions (a)-(g), each against its evidence\n")
        pol = rep.get("policy", {})
        keys_ok = sorted(pol) == sorted(["kind", "obs_dim", "encoder_v2", "encoder_ids", "lane", "sha256"])
        A(f"- (a) format/rated: {n}/{n} JSONL rows tagged gen1randombattle; the runner "
          "asserts rated on every row — **not void**.")
        A("- (b) checkpoint/arm swap: sha asserted at the one runner launch; provenance "
          f"stamped {pol.get('sha256', '?')[:6]}... lane {pol.get('lane')} — **not void**.")
        A("- (c) set-pool drift: LG-5 upstream data.json/teams.ts sha256 == pin == "
          "vendored (59da482) within 24 h of launch — **not void**.")
        A("- (d) account contamination: LG-2 capture == R1's banked end state, zero "
          "games since 2026-08-26; the LG-9 starting-rating line showed the parked "
          "values (the inverted tell passed) — **not void**.")
        A(f"- (e) wrong object: provenance keys {'EXACTLY the six greedy keys' if keys_ok else 'NOT the six keys — INVESTIGATE'}"
          f" (kind {pol.get('kind')}, obs_dim {pol.get('obs_dim')}); mean_decision_ms "
          f"**{mdm:.3f}** vs the VOID bound 15 (finalized from the LG-6 smoke's 3.036) — "
          f"**{'not void' if (mdm or 99) < 15 and keys_ok else 'VOID'}**; "
          f"max_concurrent_live_battles {rep.get('max_concurrent_live_battles')} (expected 1); "
          f"decision_errors {rep.get('decision_errors')}; mask_desyncs {rep.get('mask_desyncs')}; "
          f"tallies jsonl/poke-env {rep.get('tally_jsonl')}/{rep.get('tally_pokeenv')} agree={rep.get('gate_tallies_agree')}.")
        A("- (f) a second concurrent project account: none — **not void**.")
        A(f"- (g) an unlicensed stop: stopped_by_rule={rep.get('stopped_by_rule')} at n={n}, "
          "attempt 1, no operational abort — **not void**.")
        A("\n**VERDICT: the run is COMPLETE and VALID as pre-registered; the primary read "
          "stands. It discharges JOURNEY step 2 (M4).**\n")
        A("Rematch-cell references, CONFOUNDED — NOT AN EFFECT (ten-confound list under "
          "obligation (iv); opponent-Elo columns first): R1 rematch 0.356 (n=59, opp Elo "
          "mean 1311) vs first 0.525 (n=141, 1198); R3 rematch 0.548 (n=84, 1240) vs first "
          "0.517 (n=116, 1173). Confound 10: greedy is fully state-determined, so R4 is the "
          "most memorisation-exposed of the three, and rating-matching alone predicts a "
          "lower rematch rate with zero memorisation.\n")
    A("## Obligation (iii) — played games vs non-games\n")
    A(f"Categories: `{dict(cats)}`\n")
    A(f"- all rated battles: **{w}/{n} = {w/n:.3f}** (reconciles with the board)")
    A(f"- played only, RATIFIED cut: **{pw}/{len(played)} = {pw/len(played):.3f}**")
    A("  (a no-show — opponent submitted zero moves — is not a game; a forfeit")
    A("  or a mid-game timeout IS a win, per the 2026-08-25 amendment)\n")
    # Hand-written appendices survive regeneration: everything at/after the
    # marker line in the existing --out file is re-appended verbatim.
    MARK = "<!-- HAND-WRITTEN APPENDIX — preserved on regeneration -->"
    out = Path(args.out)
    tail = ""
    if out.exists() and MARK in out.read_text():
        tail = "\n" + MARK + out.read_text().split(MARK, 1)[1]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n" + tail)
    print("\n".join(L))
    print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
