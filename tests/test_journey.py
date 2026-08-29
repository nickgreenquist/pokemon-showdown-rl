"""JOURNEY.md is the arc; STATUS.md says where we are on it.

Two mechanisms, both deliberately cheap, because this repo's evidence is that
documents WITHOUT an enforcement hook rot (DESIGN, DESIGN2, RESEARCH_BRIEF)
while documents WITH one do not (STATUS's line cap, the pre-reg tests).

  1. STATUS's `JOURNEY POSITION` line must name a step that exists in
     JOURNEY.md. STATUS is the only mandatory session-start read, so this is
     what makes the arc unmissable; the assertion is what stops the two from
     drifting apart silently.

  2. ONCE THE MAINTAINER RATIFIES the journey, it must stay ARC-LEVEL: no bare
     decimals outside an explicitly permitted block. An unratified draft may
     contain anything, so these tests are green today and become binding the
     moment the stamp lands -- which is also the moment the doc starts being
     quoted at.

     Why decimals: JOURNEY.md was written 2026-08-28 citing "the 0.072 bar"
     and was stale within four hours (r9 corrected R2's bar to 0.1007, since
     both sides carry the clustered term). A measurement in an arc document is
     a staleness liability with no upside -- the number's home is the chapter
     pre-reg that owns it. To keep a number anyway, fence it:

         <!-- numbers-ok: why this one is safe -->
         ... prose with figures ...
         <!-- /numbers-ok -->
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JOURNEY = ROOT / "JOURNEY.md"
STATUS = ROOT / "STATUS.md"

STEP_RE = re.compile(r"^###\s+([0-9]+(?:\.[0-9]+)?)\.?\s", re.M)
POSITION_RE = re.compile(r"JOURNEY POSITION\s*[—-]\s*step\s+([0-9]+(?:\.[0-9]+)?)", re.I)
DECIMAL_RE = re.compile(r"(?<![\w.])\d+\.\d+(?![\w.])")
FENCE_OPEN = "<!-- numbers-ok"
FENCE_CLOSE = "<!-- /numbers-ok -->"


def step_ids(text):
    return STEP_RE.findall(text)


def ratified(text):
    """The stamp is the maintainer's, and it is what makes the rules bind."""
    return re.search(r"^\s*(\*\*)?RATIFIED\b", text, re.M | re.I) is not None


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


def test_ratified_journey_stays_arc_level():
    text = JOURNEY.read_text()
    if not ratified(text):
        pytest.skip("JOURNEY.md is not RATIFIED yet -- a draft may hold anything")
    offenders, fenced = [], False
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith(FENCE_OPEN):
            fenced = True
            continue
        if line.strip().startswith(FENCE_CLOSE):
            fenced = False
            continue
        if fenced or line.startswith("###") or line.startswith("##"):
            continue
        for hit in DECIMAL_RE.findall(line):
            offenders.append(f"  line {n}: {hit}  ({line.strip()[:72]})")
    assert not offenders, (
        "a RATIFIED JOURNEY.md must be arc-level -- these decimals belong in the "
        "chapter pre-reg that owns them, or inside a numbers-ok fence:\n"
        + "\n".join(offenders))


def test_ratified_journey_steps_declare_an_exit_condition():
    """A step without an exit condition is where a project moves in and lives.

    JOURNEY.md says so itself about gen4. Accepts either wording the doc
    already uses, so ratification does not force a rewrite.
    """
    text = JOURNEY.read_text()
    if not ratified(text):
        pytest.skip("JOURNEY.md is not RATIFIED yet")
    blocks = re.split(r"^###\s+", text, flags=re.M)[1:]
    missing = [b.splitlines()[0][:60] for b in blocks
               if not re.search(r"exit condition|scope guard|OPTIONAL", b, re.I)]
    assert not missing, ("every ratified step needs an exit condition (or an "
                         "explicit OPTIONAL): " + "; ".join(missing))
