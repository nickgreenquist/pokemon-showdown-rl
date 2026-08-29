"""JOURNEY.md is the arc; STATUS.md says where we are on it.

ONE mechanism, deliberately: STATUS's `JOURNEY POSITION` line must name a step
that exists in JOURNEY.md. STATUS is the only mandatory session-start read, so
this is what keeps the arc in front of a session before it picks up work, and
the assertion is what stops the two files from drifting apart silently.

WHAT USED TO BE HERE, AND WHY IT IS GONE (2026-08-28, maintainer). Two further
tests, gated on a RATIFIED stamp, enforced that every step declare an exit
condition and that the doc carry no bare decimals. Both were removed the day
they were written. JOURNEY.md is the maintainer's HIGH-LEVEL GOALS DOC, chapter
by chapter -- not a pre-registration -- and applying this repo's pre-reg
machinery to it manufactures work: a future session would have written an exit
condition for step 10 because a test asked, not because the work needed one.
The staleness protection the altitude test provided is already in the file, in
the maintainer's own words: "Not a spec. Chapter documents, config headers, and
STATUS.md remain authoritative for anything currently in flight."

The general lesson, since this repo keeps relearning it: an enforcement hook is
right for a document that makes CLAIMS (pre-regs, readouts, STATUS) and wrong
for one that states INTENT.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOURNEY = ROOT / "JOURNEY.md"
STATUS = ROOT / "STATUS.md"

STEP_RE = re.compile(r"^###\s+([0-9]+(?:\.[0-9]+)?)\.?\s", re.M)
POSITION_RE = re.compile(r"JOURNEY POSITION\s*[—-]\s*step\s+([0-9]+(?:\.[0-9]+)?)", re.I)


def step_ids(text):
    return STEP_RE.findall(text)


def test_journey_exists_with_unique_numbered_steps():
    assert JOURNEY.exists(), "JOURNEY.md is the arc; STATUS points at it"
    ids = step_ids(JOURNEY.read_text())
    assert ids, "no '### <n>. <title>' steps found -- did the heading style change?"
    assert len(ids) == len(set(ids)), f"duplicate step ids: {ids}"


def test_status_position_names_a_step_that_exists():
    """The one that catches drift: STATUS says step N, JOURNEY must have it."""
    status = STATUS.read_text()
    m = POSITION_RE.search(status)
    assert m, ("STATUS.md must carry a 'JOURNEY POSITION — step <n>' line. It is "
               "the only mandatory read, so it is where the arc has to live.")
    here = m.group(1)
    ids = step_ids(JOURNEY.read_text())
    assert here in ids, (f"STATUS says step {here}; JOURNEY.md defines {ids}. "
                         "One of the two moved without the other.")
