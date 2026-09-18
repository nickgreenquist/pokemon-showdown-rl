#!/usr/bin/env python
"""Does a REAL tree over our critic beat greedy? off FP@20, R5 committee.

The bar is GREEDY (pooled 0.5765, n=4500 over three blocks), not the depth-1
matrix -- every search configuration measured so far is level with or below it.
"""
import json, math
from pathlib import Path
import yaml

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "results/tree_r5"
PR = yaml.safe_load(open(REPO / "configs/eval/tree_r5.yaml"))
C = PR["comparators"]


def g(t):
    p = RES / f"{t.lower()}.json"
    return json.loads(p.read_text()) if p.exists() else None


def flip_rate(d):
    """How often did the search overrule the policy?

    A TREE ARM REPORTS NO `search/override_rate`: that field is gated on
    `margin_delta`, which belongs to the MATRIX selector, while the tree carries
    its margin in `tree.margin`. Same quantity, different bookkeeping -- and
    taking the None at face value is what blocked the 07:05Z pin for four hours.
    """
    r = d.get("search/override_rate")
    if r is not None:
        return float(r)
    dec = d.get("search/decisions") or 0
    skips = d.get("search/placeholder_skips") or 0
    return (d.get("search/flips") or 0) / max(dec - skips, 1)


def code_provenance(data):
    """Did every arm in this block run the SAME CODE?

    Each arm is a fresh process that imports the WORKING TREE, so a block
    launched before an edit and finished after one is comparing two programs.
    `launch_git_sha` has been stamped into every arm's JSON since CH4 R1's G8
    block and nothing has ever read it (docs/CLEANUP.md L5). This reads it. It
    does not refuse -- whether a spanning block is VOID is a maintainer ruling
    -- but a reader is told rather than having to think of the question.

    THE FIELD WAS MIS-NAMED UNTIL 2026-09-18: it was read AFTER the battles, so
    older arms carry the tree state at COMPLETION under the launch name. An arm
    with no `finish_git_sha` is one of those and is labelled as such, because
    comparing a finish sha against a launch sha proves nothing either way.
    """
    rows = {t: d for t, d in data.items() if d}
    if not rows:
        return
    print("\n## Code provenance\n")
    distinct, legacy = set(), []
    for t, d in rows.items():
        start, end = d.get("launch_git_sha"), d.get("finish_git_sha")
        if end is None:
            # Written before 2026-09-18: `launch_git_sha` was read AFTER the
            # battles, so it is the FINISH state under the launch name. Say so
            # rather than silently comparing it against a real launch sha.
            legacy.append(t)
            print(f"  {t:4s} {(start or 'UNSTAMPED')[:12]}  (FINISH-time sha, "
                  f"mis-named: this arm predates the fix)")
        else:
            span = "" if start == end else f" -> {end[:12]} SPANNED A COMMIT MID-ARM"
            print(f"  {t:4s} {(start or 'UNSTAMPED')[:12]}{span}")
        if start:
            distinct.add(start)
    if len(distinct) > 1:
        print(f"\n  THIS BLOCK SPANS {len(distinct)} COMMITS. Every arm is a fresh")
        print("  process importing the working tree, so the arms ran different")
        print("  programs. Say what the diff touched before differencing them.")
    elif not legacy:
        print("\n  One commit across every arm.")
    if legacy:
        print(f"\n  {len(legacy)} arm(s) carry a FINISH-time sha under the launch")
        print("  name, so this block's shas are not directly comparable to each")
        print("  other. Read the commit LOG against the arm's wall-clock window.")


def cmp(lab, pa, na, pb, nb):
    se = math.sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb)
    print(f"  {lab:46s} {pa:.4f} - {pb:.4f} = {pa - pb:+.4f} at {abs(pa - pb) / se:.2f} se")


def main():
    print("=" * 78)
    print("A REAL TREE OVER OUR CRITIC -- decoupled UCT, our policy as the PUCT")
    print("prior, our critic at the leaves. off FP@20, R5 committee, batch 16.")
    print("Both FP@20 disclosures travel. THE BAR IS GREEDY, not the matrix.")
    print("=" * 78)
    print("\n## Sweep (TQ margin toward D1's 6.8% override; n=60, win rate NOT read)\n")
    for a in PR["phases"]["S"]:
        d = g(a)
        if not d:
            print(f"  {a} PENDING"); continue
        t = PR["arms"][a]["tree"]
        print(f"  {a} margin {t['margin']:<5.2f} override {flip_rate(d):.4f} "
              f"ms {(d.get('search/ms_mean') or float('nan')):.1f}")

    print("\n## The read\n")
    arms = [("TV", "visits (FP's own rule)"), ("TG", "gumbel (Danihelka)"),
            ("TQ", "q + matched margin"), ("TGR", "GREEDY anchor, this block")]
    data = {a: g(a) for a, _ in arms}
    for a, lab in arms:
        d = data[a]
        if not d:
            print(f"  {a:4s} {lab:26s} PENDING"); continue
        print(f"  {a:4s} {lab:26s} {d['our_win_rate']:.4f} n={d['battles_finished']:<5d} "
              f"ms {(d.get('search/ms_mean') or 0):.1f} "
              f"flips {flip_rate(d):.4f}")

    code_provenance(data)
    anchor = data["TGR"]
    print("\n## Against greedy\n")
    if anchor:
        for a, lab in arms[:3]:
            if data[a]:
                cmp(f"{a} - greedy (same block)", data[a]["our_win_rate"],
                    data[a]["battles_finished"], anchor["our_win_rate"],
                    anchor["battles_finished"])
        cmp("greedy this block - greedy pooled (3 blocks)",
            anchor["our_win_rate"], anchor["battles_finished"],
            C["greedy_pooled"]["rate"], C["greedy_pooled"]["n"])
    else:
        print("  PENDING (the anchor is the bar; nothing is read without it)")

    print("\n## Against the depth-1 MATRIX (same critic, no real depth)\n")
    for a, lab in arms[:3]:
        if data[a]:
            cmp(f"{a} - D1 matrix, tight gate", data[a]["our_win_rate"],
                data[a]["battles_finished"], C["d1_matrix"]["rate"], C["d1_matrix"]["n"])
    print("\n  READ: if a real tree clears GREEDY, step 2 is to scale the budget and")
    print("  put it against FP@500. If it does not, then on this object no search")
    print("  construction tried -- one-ply matrix, selective two-ply, or full UCT --")
    print("  beats playing the policy's own argmax, and that is the finding.")
    print("=" * 78)


if __name__ == "__main__":
    main()
