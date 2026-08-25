"""Ladder runner — offline gates. No server, no network, no battles.

The ladder is the one path in this repo that leaves localhost and plays
strangers on a public board under a named account, so the failure modes are
not the usual ones: a bad username looks like a deadlock, an exception in
`choose_move` forfeits a live rated game, and a resume that miscounts
silently republishes the wrong n. What is pinned here:

* the 18-char USERID rule (server/users.ts:745) — including that
  underscores are stripped rather than counted, which is exactly the trap
  the maintainer's first proposed name fell into;
* `ladder_snapshot` parsing, including the "not on the top-500 list yet"
  case, which is NORMAL early and must not read as an error;
* `choose_move`'s never-raise contract, which is a deliberate DEVIATION
  from the strict Chapter-3 seat;
* the pre-reg's arms resolving against real checkpoint keys, and every
  `<< MAINTAINER >>` marker still being present (the config is a DRAFT and
  must not be launched until they are resolved).
"""

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ladder  # noqa: E402

PREREG = Path(__file__).resolve().parents[1] / "configs/eval/ladder_r1.yaml"


class TestUsername:
    def test_to_id_strips_non_alphanumerics(self):
        assert ladder.to_id("nick_gen1rb_rl_bot") == "nickgen1rbrlbot"
        assert ladder.to_id("Nick GEN1 Bot!") == "nickgen1bot"

    def test_maintainers_first_name_is_refused(self):
        """21-char userid. This is the whole reason the check exists."""
        with pytest.raises(SystemExit) as exc:
            ladder._check_username("nick_gen1randbats_rl_bot")
        assert "18" in str(exc.value)

    def test_the_shortened_name_passes(self):
        assert ladder._check_username("nick_gen1rb_rl_bot") == "nickgen1rbrlbot"

    def test_underscores_are_free(self):
        """18 visible chars of underscore + 1 letter is a 1-char userid."""
        assert ladder._check_username("a_________________") == "a"

    def test_exactly_18_is_allowed_and_19_is_not(self):
        assert ladder._check_username("a" * 18) == "a" * 18
        with pytest.raises(SystemExit):
            ladder._check_username("a" * 19)

    def test_empty_userid_refused(self):
        with pytest.raises(SystemExit):
            ladder._check_username("____")


class TestLadderSnapshot:
    BOARD = {
        "toplist": [
            {"userid": "someone", "gxe": 84.3, "r": 1814.9, "rd": 28.3,
             "elo": 1667.0, "w": 1896, "l": 952, "t": 13},
            {"userid": "cutoffguy", "gxe": 58.8, "r": 1568.0, "rd": 37.0,
             "elo": 1358.0, "w": 10, "l": 9, "t": 0},
        ]
    }

    def _fake_urlopen(self, board):
        class _Resp:
            def __enter__(_s):
                return _s

            def __exit__(*_a):
                return False

            def read(_s):
                return json.dumps(board).encode()

        return lambda *_a, **_k: _Resp()

    def test_finds_our_row(self):
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(self.BOARD)):
            snap = ladder.ladder_snapshot("gen1randombattle", "someone")
        assert snap["listed"] is True
        assert snap["gxe"] == 84.3
        assert snap["elo"] == 1667.0

    def test_unlisted_is_normal_not_an_error(self):
        """Early in a run we are legitimately below the 500th cutoff."""
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(self.BOARD)):
            snap = ladder.ladder_snapshot("gen1randombattle", "nobody")
        assert snap["listed"] is False
        assert "error" not in snap
        assert snap["cutoff_gxe"] == 58.8

    def test_network_failure_is_survivable(self):
        """A scrape must never take down a run mid-ladder."""
        def _boom(*_a, **_k):
            raise OSError("no network")

        with patch.object(ladder.urllib.request, "urlopen", _boom):
            snap = ladder.ladder_snapshot("gen1randombattle", "someone")
        assert "error" in snap
        assert snap.get("listed") is None or snap.get("listed") is False


class TestChooseMoveNeverRaises:
    """DEVIATION from scripts/ch3_fp_h2h.py's seat, and a deliberate one:
    there, an assert is correct (a controlled eval should die rather than
    log a wrong number). Here it would forfeit a live rated game against a
    human and drop the account, so the fallback is the right trade — but it
    must be COUNTED, or a broken policy silently plays default moves."""

    def _player(self, act_fn):
        p = ladder.LadderPlayer.__new__(ladder.LadderPlayer)
        p._act = act_fn
        p._type_chart = {}
        p._battle_tag = None
        p._battle_index = -1
        p._decision_index = 0
        p.decision_errors = 0
        p.decision_ms = []
        p.choose_default_move = lambda: "DEFAULT"
        return p

    def test_policy_exception_falls_back_and_counts(self):
        def _boom(*_a):
            raise RuntimeError("policy exploded")

        p = self._player(_boom)
        battle = type("B", (), {"battle_tag": "battle-x-1"})()
        assert p.choose_move(battle) == "DEFAULT"
        assert p.decision_errors == 1
        assert len(p.decision_ms) == 1

    def test_encoder_exception_also_falls_back(self):
        p = self._player(lambda *_a: 0)
        battle = type("B", (), {"battle_tag": "battle-x-2"})()
        # embed_battle on a duck-typed stub raises; the point is it survives.
        assert p.choose_move(battle) == "DEFAULT"
        assert p.decision_errors == 1

    def test_battle_index_advances_per_tag(self):
        p = self._player(lambda *_a: 0)
        for tag in ("battle-a", "battle-a", "battle-b"):
            p.choose_move(type("B", (), {"battle_tag": tag})())
        assert p._battle_index == 1


@pytest.fixture(scope="module")
def cfg():
    return yaml.safe_load(PREREG.read_text())


class TestSummarize:
    """The JSONL is the source of truth across resumes — a running tally kept
    in memory is exactly what broke the first version (a resumed session
    looked its old tags up in `player.battles`, which belongs to the previous
    process, and KeyError'd on the first battle of day two)."""

    def _write(self, tmp_path, outcomes):
        p = tmp_path / "b.jsonl"
        p.write_text("".join(
            json.dumps({"index": i, "tag": f"t{i}", "outcome": o,
                        "turns": 10, "opponent": "x"}) + "\n"
            for i, o in enumerate(outcomes)
        ))
        return p

    def test_counts_and_ties_are_non_wins(self, tmp_path):
        p = self._write(tmp_path, ["win", "loss", "tie", "win"])
        s = ladder.summarize(p)
        assert (s["wins"], s["losses"], s["ties"]) == (2, 1, 1)
        assert s["battles_total"] == 4
        assert s["raw_win_rate"] == pytest.approx(0.5)

    def test_missing_file_is_empty_not_an_error(self, tmp_path):
        s = ladder.summarize(tmp_path / "nope.jsonl")
        assert s["battles_total"] == 0
        assert s["raw_win_rate"] is None

    def test_survives_a_trailing_partial_write(self, tmp_path):
        """flush() per battle means a kill mid-write is possible."""
        p = self._write(tmp_path, ["win", "loss"])
        with open(p, "a") as fh:
            fh.write("\n")
        assert ladder.summarize(p)["battles_total"] == 2


class TestPrereg:

    def test_every_arm_kind_is_supported(self, cfg):
        for name, arm in cfg["arms"].items():
            assert arm["kind"] in ladder.POLICY_KINDS, name

    def test_arm_lanes_resolve_to_declared_checkpoints(self, cfg):
        keys = set(cfg["checkpoints"])
        for name, arm in cfg["arms"].items():
            lanes = arm.get("lanes", []) + (
                [arm["lane"]] if "lane" in arm else []
            )
            assert lanes, name
            assert set(lanes) <= keys, f"{name}: {set(lanes) - keys}"

    def test_every_display_name_is_a_legal_userid(self, cfg):
        for name, arm in cfg["arms"].items():
            ladder._check_username(arm["display_name"])

    def test_display_names_declare_the_bot(self, cfg):
        """Maintainer ruling 2026-08-25: the account announces itself."""
        for name, arm in cfg["arms"].items():
            assert "bot" in ladder.to_id(arm["display_name"]), name

    def test_no_credentials_in_the_committed_config(self, cfg):
        raw = PREREG.read_text().lower()
        for banned in ("password:", "ps_password:", "secret:"):
            assert banned not in raw

    def test_draft_markers_still_present(self, cfg):
        """The config is a DRAFT. If these ever disappear it is because the
        maintainer resolved them — at which point this test is updated in
        the same commit, deliberately, rather than drifting."""
        raw = PREREG.read_text()
        markers = re.findall(r"<< MAINTAINER \d+ >>", raw)
        assert len(markers) == 3, markers

    def test_stopping_rule_is_pre_stated(self, cfg):
        assert cfg["stopping_rule"]["glicko_rd_max"] == 40
        assert cfg["stopping_rule"]["min_battles"] == 200

    def test_hard_cap_exceeds_the_stopping_floor(self, cfg):
        assert cfg["max_battles_total"] > cfg["stopping_rule"]["min_battles"]

    def test_set_pool_pin_matches_the_vendored_server(self, cfg):
        """VOID (c). The search determinizer samples DVs and sets from the
        vendored gen1 generator; if `showdown/` is ever re-cloned to a newer
        commit, the pre-registered pin is how we find out — silently playing
        the ladder against a set pool we did not calibrate to is the failure
        this guards."""
        import hashlib

        root = Path(__file__).resolve().parents[1]
        base = root / "showdown/data/random-battles/gen1"
        if not base.exists():
            pytest.skip("showdown/ not vendored in this checkout")
        pin = cfg["set_pool_pin"]
        for fname, key in (("data.json", "data_json_sha256"),
                           ("teams.ts", "teams_ts_sha256")):
            got = hashlib.sha256((base / fname).read_bytes()).hexdigest()
            assert got == pin[key], (
                f"{fname} drifted from the pre-registered pin: {got} != "
                f"{pin[key]}. VOID (c) — re-check against upstream before "
                "laddering."
            )
