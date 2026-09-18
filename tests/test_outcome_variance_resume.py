"""IDEAS 2.11's job has to survive being killed (CLAUDE.md rule 4 (ii)).

`scripts/outcome_variance.py` measures each position as it is reached and
appends its row immediately, so a death costs ONE position. The resume reader
is the part that can silently lose work -- or, worse, crash on the torn last
line a kill leaves behind -- so it is a pure function and it is tested.
"""
import importlib.util
import json
from pathlib import Path

MOD = Path(__file__).parent.parent / "scripts/outcome_variance.py"
spec = importlib.util.spec_from_file_location("outcome_variance", MOD)
ov = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ov)


def test_a_missing_file_is_a_fresh_start_not_an_error(tmp_path):
    assert ov.load_rows(tmp_path / "nothing.jsonl") == ([], set())


def test_rows_and_their_positions_come_back(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text("".join(json.dumps({"ep": e, "mean": 0.1 * e}) + "\n"
                         for e in (0, 3, 7)))
    rows, eps = ov.load_rows(p)
    assert [r["ep"] for r in rows] == [0, 3, 7]
    assert eps == {0, 3, 7}


def test_a_torn_final_line_is_dropped_not_raised(tmp_path):
    """A kill mid-write leaves half a line. A resume that crashes on its own
    crash log is not resume-safe."""
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps({"ep": 1, "mean": 0.5}) + "\n" + '{"ep": 2, "me')
    rows, eps = ov.load_rows(p)
    assert eps == {1}, "the complete row survives and the torn one is dropped"


def test_a_row_without_a_position_is_ignored(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text(json.dumps({"mean": 0.5}) + "\n")
    assert ov.load_rows(p) == ([], set())
