"""R0-2(a) of configs/showdown_sp_signal12m.yaml — the offline half of the
shaping-correctness gate, on REAL recorded gen1randombattle protocol.

Replays two recorded Foul-Play collection tapes (raw inbound frames, one
seat's websocket stream — but the protocol names both sides absolutely, so
the same stream IS both seats' event log) through `hl_event_sum` from both
seats' perspective and asserts, per battle:

    sum_seat1 + sum_seat2 == 0.0   (EXACTLY — not a tolerance check)

Any nonzero value means the attribution rule read the same event
differently for the two seats, which is precisely the farmable-shaping
failure K3 kills the arm for. Also asserts the term-by-term counts on one
battle against an independent hand-parse of the raw text, and that every
one of the five terms actually fires somewhere in the corpus (a vacuous
pass is a pass of nothing).

Tapes are local collection artifacts (gitignored); the test skips loudly
where they are absent. R0-2(a) must run — and pass — on the training box
before the Rung 1 launch.
"""

import json
from pathlib import Path

import pytest

from rl.envs.showdown import _HL_WEIGHTS, hl_event_sum

TAPES = [
    Path("data/fp_tapes2/run_92564.jsonl"),
    Path("data/fp_tapes/run_90336.jsonl"),
]


def _battles_from_tape(path):
    """{room: (split_entries, raw_lines)} for every battle room on the tape."""
    battles = {}
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            if ev.get("k") != "m":
                continue
            raw = ev["v"]
            head = raw.split("\n", 1)[0]
            if not head.startswith(">battle-"):
                continue
            entries, raw_lines = battles.setdefault(head[1:], ([], []))
            for msg in raw.split("\n")[1:]:
                raw_lines.append(msg)
                sm = msg.split("|")
                if len(sm) > 1:
                    entries.append(sm)
    return battles


@pytest.mark.skipif(
    not all(t.exists() for t in TAPES),
    reason="local FP tapes absent — R0-2(a) must run on the training box",
)
def test_r02a_antisymmetry_on_recorded_battles():
    corpus = {}
    for tape in TAPES:
        for room, battle in _battles_from_tape(tape).items():
            corpus[(tape.name, room)] = battle
    # The gate's own precondition: enough real battles to mean something.
    assert len(corpus) >= 50, f"only {len(corpus)} battles on {TAPES}"

    fired = dict.fromkeys(_HL_WEIGHTS, 0)
    nonzero_battles = 0
    for key, (entries, _) in corpus.items():
        s1 = hl_event_sum(entries, "p1")
        s2 = hl_event_sum(entries, "p2")
        assert s1 + s2 == 0.0, (key, s1, s2)  # exact, per the IEEE argument
        if s1 != 0.0:
            nonzero_battles += 1
        for entry in entries:
            if len(entry) >= 3 and entry[1] in fired:
                fired[entry[1]] += 1
    assert nonzero_battles >= 50, "shaping summed to zero almost everywhere"
    assert all(fired.values()), f"terms that never fired: {fired}"

    # Term-by-term hand-parse on one eventful battle: count the raw protocol
    # lines by string prefix — a deliberately different parse from the
    # split-message path the scan uses — and require exact agreement.
    key, (entries, raw_lines) = max(
        corpus.items(),
        key=lambda kv: sum(1 for e in kv[1][0] if len(e) >= 3 and e[1] in _HL_WEIGHTS),
    )
    for tag in _HL_WEIGHTS:
        scanned = sum(1 for e in entries if len(e) >= 3 and e[1] == tag)
        hand = sum(1 for msg in raw_lines if msg.startswith(f"|{tag}|"))
        assert scanned == hand, (key, tag, scanned, hand)
