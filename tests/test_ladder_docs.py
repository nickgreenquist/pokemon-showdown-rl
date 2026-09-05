"""BI-R4-6 (ladder_r4.yaml obligation viii): the committed-docs W-L grep test.

WHY. LADDER R3's readout said 106-102 (profile, 208 rated games) while
STATUS carried the runner tally 106-94 for four days as if it were the
record. The propagation rule now says every downstream quote takes the
record from the readout's headline row — the PROFILE record — and labels
a runner tally as the runner-logged subset. This test greps the committed
docs for ladder W-L pairs and fails on any pair that is not one of the
headline pairs for the run the line names.

SCOPE, deliberately narrow: only lines that read as ladder lines (they
mention "ladder", "GXE", "Elo", "rated battles" or a LADDER R<n> label),
only W-L pairs whose two numbers are both in [40, 400] (ratings and bands
are >= 1000, dates and hours are < 40). The allowed set is the union of
every run's headline pairs — a stale pair (the failure mode) is never a
headline pair of any run, so the union loses nothing that matters.
SESSION_LOGS is history and is NOT scanned — it records what was said at
the time, including the drift this test exists to catch.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["README.md", "STATUS.md", "RESULTS.md"]

# Headline pairs per run, from each run's committed readout. R4 has two
# because the account was reused: the run's own record is the runner-logged
# JSONL tally and the profile record is CUMULATIVE (R1's 200 + R4's 200).
ALLOWED = {
    "R1": {(95, 105)},
    "R3": {(106, 102), (106, 94)},        # profile (208 rated) / runner-logged (200)
    "R4": {(104, 96), (199, 201)},        # runner-logged (200) / cumulative profile (400)
}
PAIR = re.compile(r"(?<![\d.])(\d{2,3})\s*[-–]\s*(\d{2,3})(?![\d.]|\s*%)")  # a % range is not a record
LADDER_LINE = re.compile(r"ladder|GXE|\bElo\b|rated battles|\bR[134]\b", re.IGNORECASE)
ALLOWED_ALL = set().union(*ALLOWED.values())


def ladder_pairs(text):
    for lineno, line in enumerate(text.splitlines(), 1):
        if not LADDER_LINE.search(line):
            continue
        for m in PAIR.finditer(line):
            a, b = int(m.group(1)), int(m.group(2))
            if 40 <= a <= 400 and 40 <= b <= 400:
                yield lineno, line, (a, b)


def test_committed_docs_quote_only_headline_records():
    bad = []
    for doc in DOCS:
        for lineno, line, pair in ladder_pairs((ROOT / doc).read_text()):
            if pair not in ALLOWED_ALL:
                bad.append(f"{doc}:{lineno}: {pair}: {line.strip()[:110]}")
    assert not bad, "W-L pairs that are not a readout headline pair:\n" + "\n".join(bad)


def test_the_scanner_catches_the_r3_drift_that_motivated_it():
    line = "LADDER R3 STATUS 106-94 (n=200) vs readout 106-102 (208)."
    assert {p for _, _, p in ladder_pairs(line)} == {(106, 94), (106, 102)}
    stale = "LADDER R3: record 107-93 over 200 rated battles, GXE 60.3%"
    assert {p for _, _, p in ladder_pairs(stale)} == {(107, 93)}
    assert (107, 93) not in ALLOWED_ALL
    # ratings, bands, dates and hours are out of scope by construction
    quiet = "LADDER R4: Elo 1292-1354, band 1300-1400, 2026-09-04, 12-16 h, se 0.19-0.22, GXE 66-77%"
    assert not list(ladder_pairs(quiet))
