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
    "R5": {(128, 72), (327, 273)},        # runner-logged (200) / cumulative profile (600)
}
# WITHIN-RUN CELLS, not records. A cell is admitted here only if it has
# GENERATOR provenance -- i.e. `scripts/ladder_readout.py` prints it into the
# committed readout -- so the list cannot become a place to park a number
# somebody typed. R5's pair is the top-500 exposure split (record while at or
# above the admission line vs below it), which the readout's "Top-500 exposure"
# section emits under BOTH candidate lines; both are listed so that naming the
# other line is not a test failure. Added 2026-09-16 in the R5 audit, with the
# R5 headline pairs above -- the R5 write-up shipped without teaching this
# guard about R5 at all, and the guard was RED at HEAD until now.
CELLS = {
    "R5": {(93, 53), (95, 53)},           # stop-cutoff / n=0-cutoff exposure split
}
PAIR = re.compile(r"(?<![\d.])(\d{2,3})\s*[-–]\s*(\d{2,3})(?![\d.]|\s*%)")  # a % range is not a record
# \bR\d\b, not \bR[134]\b: the old class did not know R5 existed, so STATUS's
# R5 record line matched no ladder keyword and was never scanned at all.
LADDER_LINE = re.compile(r"ladder|GXE|\bElo\b|rated battles|\bR\d\b", re.IGNORECASE)
ALLOWED_ALL = set().union(*ALLOWED.values(), *CELLS.values())


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


# ---------------------------------------------------------------------------
# The hand-written appendix marker. `scripts/ladder_readout.py` re-appends
# everything at or after MARK when it regenerates over an existing --out file;
# an appendix written WITHOUT the marker is deleted, silently, by the next
# regeneration. LADDER R5 shipped that way (2026-09-16, bb1a0dc) and the
# opponent-pool appendix -- the CLEANUP L1 evidence -- was one re-run from
# gone. This test is the guard, not the memory.
MARK = "<!-- HAND-WRITTEN APPENDIX — preserved on regeneration -->"


def test_hand_written_readout_appendices_sit_behind_the_marker():
    bad = []
    for path in sorted((ROOT / "readouts").glob("LADDER_*_READOUT.md")):
        text = path.read_text()
        heads = [i for i, line in enumerate(text.splitlines())
                 if line.startswith("## Appendix")]
        if not heads:
            continue
        if MARK not in text:
            bad.append(f"{path.name}: has {len(heads)} '## Appendix' section(s) "
                       "but no preservation marker — a regeneration deletes them")
            continue
        mark_line = next(i for i, line in enumerate(text.splitlines()) if MARK in line)
        if min(heads) < mark_line:
            bad.append(f"{path.name}: an '## Appendix' section sits ABOVE the marker")
    assert not bad, "\n".join(bad)
