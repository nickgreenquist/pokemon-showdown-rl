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
import ladder_classify as lc  # noqa: E402

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
    """Two sources now, and which one answers WHICH question is the point.

    The leaderboard knows only `listed` and the admission line. The PROFILE
    knows our rating, and knows it whether or not we are listed. Conflating
    them cost LADDER R1 its pre-registered primary read for two days, so
    these pin the separation rather than just the parsing.
    """

    BOARD = {
        "toplist": [
            {"userid": "someone", "gxe": 84.3, "r": 1814.9, "rd": 28.3,
             "elo": 1667.0, "w": 1896, "l": 952, "t": 13},
            {"userid": "cutoffguy", "gxe": 58.8, "r": 1568.0, "rd": 37.0,
             "elo": 1358.0, "w": 10, "l": 9, "t": 0},
        ]
    }
    # Verbatim shape of the live response for our own account, fetched
    # 2026-08-27. Note `rpr`/`rprd` where the board says `r`/`rd`.
    PROFILE = {
        "username": "nickgen1rbrlbot", "userid": "nickgen1rbrlbot",
        "registertime": 1787616000, "group": 1,
        "ratings": {"gen1randombattle": {
            "elo": 1292.2541143813178, "gxe": 59.6,
            "rpr": 1573.0409640158791, "rprd": 26.572951195067724,
            "w": 95, "l": 105, "coil": None}},
    }
    UNRATED = {"username": "newbie", "userid": "newbie", "ratings": {}}

    def _fake_urlopen(self, board=None, profile=None, board_boom=False,
                      profile_boom=False):
        """Routes by URL — the whole change is that there are two now."""
        def _open(req, *_a, **_k):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            is_profile = "/users/" in url
            if (is_profile and profile_boom) or (not is_profile and board_boom):
                raise OSError("no network")
            payload = profile if is_profile else board

            class _Resp:
                def __enter__(_s):
                    return _s

                def __exit__(*_a):
                    return False

                def read(_s):
                    return json.dumps(payload).encode()

            return _Resp()

        return _open

    def test_finds_our_row(self):
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(self.BOARD, self.PROFILE)):
            snap = ladder.ladder_snapshot("gen1randombattle", "someone")
        assert snap["listed"] is True
        # The PROFILE wins on the rating fields even when we are listed —
        # it is the account's own record and always exists.
        assert snap["gxe"] == 59.6
        assert snap["rating_source"] == "profile"

    def test_unlisted_is_normal_not_an_error(self):
        """Early in a run we are legitimately below the 500th cutoff."""
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(self.BOARD, self.PROFILE)):
            snap = ladder.ladder_snapshot("gen1randombattle", "nobody")
        assert snap["listed"] is False
        assert snap["ok"] is True
        assert "error" not in snap
        # Admission is an ELO threshold — the toplist is elo-ranked
        # (verified against the live board 2026-08-25: elo is monotone
        # descending, gxe and glicko are not). The lowest GXE on the list
        # is whoever happens to have it, NOT a cutoff, and calling it one
        # is the mistake this assertion now guards against.
        assert snap["cutoff_elo"] == 1358.0
        assert snap["min_listed_gxe"] == 58.8

    def test_unlisted_still_has_a_rating(self):
        """THE R1 BUG, pinned. Unlisted is a fact about the BOARD; the
        profile carries GXE and Glicko-1 for any rated account. R1 reported
        these as UNMEASURED while they sat on a public page."""
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(self.BOARD, self.PROFILE)):
            snap = ladder.ladder_snapshot("gen1randombattle", "nickgen1rbrlbot")
        assert snap["listed"] is False
        assert snap["rated"] is True
        assert snap["gxe"] == 59.6
        # `rpr`/`rprd` are normalised onto the board's `r`/`rd` spelling so
        # one stopping rule reads either source.
        assert round(snap["r"]) == 1573
        assert round(snap["rd"]) == 27
        assert round(snap["elo"]) == 1292

    def test_profile_with_no_rated_games_is_a_real_negative(self):
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(self.BOARD, self.UNRATED)):
            snap = ladder.ladder_snapshot("gen1randombattle", "newbie")
        assert snap["profile_ok"] is True
        assert snap["rated"] is False
        assert snap.get("rd") is None

    def test_network_failure_is_survivable(self):
        """A scrape must never take down a run mid-ladder."""
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(board_boom=True,
                                             profile_boom=True)):
            snap = ladder.ladder_snapshot("gen1randombattle", "someone")
        assert snap["ok"] is False
        assert snap["board_error"] and snap["profile_error"]
        assert snap.get("listed") is None or snap.get("listed") is False

    def test_a_dead_board_does_not_hide_the_rating(self):
        """One endpoint down must not blind the other. The rating lives on
        the profile, so a 403 on the leaderboard costs us `listed` and the
        admission line — never the primary read."""
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(profile=self.PROFILE,
                                             board_boom=True)):
            snap = ladder.ladder_snapshot("gen1randombattle", "nickgen1rbrlbot")
        assert snap["ok"] is True
        assert snap["board_ok"] is False and snap["profile_ok"] is True
        assert snap["listed"] is None
        assert snap["gxe"] == 59.6

    def test_a_dead_profile_falls_back_to_the_board_row(self):
        with patch.object(ladder.urllib.request, "urlopen",
                          self._fake_urlopen(board=self.BOARD,
                                             profile_boom=True)):
            snap = ladder.ladder_snapshot("gen1randombattle", "someone")
        assert snap["ok"] is True
        assert snap["profile_ok"] is False
        assert snap["rd"] == 28.3
        assert snap["rating_source"] == "leaderboard"


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


class TestProvenanceLinks:
    """`results/`, `runs/` and `data/` are gitignored with zero tracked
    files, so a chapter's grader scripts are its ONLY committed provenance.
    An audit on 2026-08-25 found the four CH4 R1 instruments had zero
    references anywhere in the repo — they looked exactly like orphans a
    reference-based cleanup would delete. They are named in the pre-reg's
    `instruments:` block now, and this test keeps those paths honest."""

    def test_every_declared_instrument_exists(self):
        root = Path(__file__).resolve().parents[1]
        found = 0
        for cfg_path in sorted((root / "configs/eval").glob("*.yaml")):
            block = (yaml.safe_load(cfg_path.read_text()) or {}).get(
                "instruments"
            )
            if not block:
                continue
            for role, rel in block.items():
                found += 1
                assert (root / rel).exists(), (
                    f"{cfg_path.name}: instruments.{role} -> {rel} is missing"
                )
        assert found, "no instruments: block found in any eval pre-reg"


class TestSetPoolIntegrity:
    """`rl.envs.randbats_prior.verify_against_showdown()` had ZERO callers —
    a public verifier that never ran. It checks the ENCODER's set-pool copy
    against the vendored sim, which is a different and more load-bearing
    check than the vendored-vs-upstream one done by hand for the ladder:
    if the prior's copy drifts from the sim we actually play, our features
    silently describe a different set pool, and the search determinizer
    samples DVs from the wrong distribution."""

    def test_encoder_set_pool_matches_the_vendored_sim(self):
        root = Path(__file__).resolve().parents[1]
        if not (root / "showdown/data/random-battles/gen1/data.json").exists():
            pytest.skip("showdown/ not vendored in this checkout")
        from rl.envs.randbats_prior import verify_against_showdown

        ok, msg = verify_against_showdown(root / "showdown")
        assert ok, msg


class TestStoppingRule:
    """Until 2026-08-25 the pre-registered stop (rd <= 40 AND n >= 200) was
    prose in a config header that no code read — a human instruction an
    operator could overrun by hundreds of public battles. These pin it."""

    CFG = {"stopping_rule": {"glicko_rd_max": 40, "min_battles": 200}}
    LISTED = {"ok": True, "profile_ok": True, "listed": True, "rated": True,
              "rd": 35.0, "rating_source": "profile"}

    def test_met_when_both_halves_hold(self):
        met, why = ladder.stopping_rule_met(self.CFG, 200, self.LISTED)
        assert met is True
        assert "200" in why and "35" in why

    def test_n_floor_blocks_an_early_lucky_convergence(self):
        met, why = ladder.stopping_rule_met(self.CFG, 40, {"ok": True, "listed": True,
                                                           "rd": 39.0})
        assert met is False
        assert "40 < 200" in why

    def test_rd_bound_blocks_a_long_but_uncertain_run(self):
        met, _ = ladder.stopping_rule_met(self.CFG, 900, {"ok": True, "listed": True,
                                                          "rd": 41.0})
        assert met is False

    def test_unlisted_with_an_rd_IS_a_pass(self):
        """THE REGRESSION THAT COST R1 ITS PRIMARY READ, pinned in the
        direction it actually failed.

        Two tests used to live here — `test_genuinely_unlisted_still_blocks`
        and `test_unlisted_is_not_a_pass` — both asserting that an unlisted
        account blocks the rule, on the stated premise that "an unlisted
        account has no published rd". **The premise was false**: the rd is
        on the USER PROFILE. R1 finished at rd 26.6 / n 200 and reported
        `stopped_by_rule: false`. The `listed` gate is gone; these are the
        real R1 numbers and they must read MET."""
        met, why = ladder.stopping_rule_met(
            self.CFG, 200,
            {"ok": True, "profile_ok": True, "listed": False, "rated": True,
             "rd": 26.572951195067724, "rating_source": "profile"},
        )
        assert met is True
        assert "26.6" in why and "profile" in why

    def test_unrated_account_blocks(self):
        """The one case that genuinely has no rd: reachable profile, no
        rated games in this format. A real negative — keep playing — and it
        must not be confused with a dead endpoint."""
        met, why = ladder.stopping_rule_met(
            self.CFG, 5000,
            {"ok": True, "profile_ok": True, "rated": False, "listed": False},
        )
        assert met is False
        assert "no rated games" in why

    def test_dead_profile_is_not_confused_with_unrated(self):
        met, why = ladder.stopping_rule_met(
            self.CFG, 5000,
            {"ok": True, "board_ok": True, "profile_ok": False,
             "profile_error": "HTTPError 403", "listed": False},
        )
        assert met is False
        assert "PROFILE is unreachable" in why

    def test_listed_without_rd_is_not_a_pass(self):
        met, _ = ladder.stopping_rule_met(
            self.CFG, 5000, {"ok": True, "profile_ok": True, "listed": True})
        assert met is False

    def test_a_dead_board_is_not_reported_as_unlisted(self):
        """The bug this pins: the first version returned an error dict with
        no `listed` key, so `not snap.get("listed")` read a 403 as a real
        negative and answered "not yet on the top-500 list" — specific,
        plausible, and wrong. Every board call of the first 20-battle run
        failed that way (urllib's default UA is 403'd) and nothing said so."""
        met, why = ladder.stopping_rule_met(
            self.CFG, 500, {"ok": False, "error": "HTTPError 403"}
        )
        assert met is False
        assert "UNREACHABLE" in why
        assert "unlisted" not in why.lower().replace("not 'unlisted'", "")

    def test_no_rule_configured_never_stops(self):
        met, why = ladder.stopping_rule_met({}, 10_000, self.LISTED)
        assert met is False
        assert "no stopping rule" in why

    def test_the_real_prereg_values_are_the_ones_pinned_here(self, cfg):
        assert cfg["stopping_rule"] == self.CFG["stopping_rule"]


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

    def test_no_unresolved_maintainer_markers(self, cfg):
        """The DRAFT carried three `<< MAINTAINER n >>` decisions and this
        test asserted they were still present, so the draft could not
        quietly become a launched pre-reg. They were RESOLVED 2026-08-25
        (L2 / one arm / rd<=40 AND n>=200), so the test flips in the same
        commit — deliberately, which is the point of having had it."""
        raw = PREREG.read_text()
        assert not re.findall(r"<< MAINTAINER \d+ >>", raw)
        assert "Status: RATIFIED" in raw

    def test_primary_arm_is_named_and_real(self, cfg):
        """A ladder run with no named primary is post-hoc selection waiting
        to happen — the whole reason the A/B was deferred."""
        assert cfg["primary_arm"] == "L2"
        assert cfg["primary_arm"] in cfg["arms"]
        assert cfg["arms"][cfg["primary_arm"]]["kind"] == "ensemble"

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


class TestGameClassification:
    """Readout obligation (iii), as RATIFIED 2026-08-25 at n=26.

    The pre-reg's own instrument — grep the replay for `lost due to
    inactivity` / `forfeited` — was measured to be wrong twice over, and both
    failures are pinned here so neither can come back:

      1. `lost due to inactivity` is emitted for a turn-1 no-show AND for a
         turn-32 abandonment. Text alone cannot separate them.
      2. A forfeit at 28 turns is a concession, i.e. a game we won. Counting
         it as a non-game cost 18 points of descriptive win rate at n=26.

    The ratified instrument is "did the opponent ever submit a MOVE".
    """

    NAMES = "|player|p1|nickgen1rbrlbot|169|1300\n|player|p2|them|170|1250\n"

    def _log(self, body: str) -> str:
        return self.NAMES + body

    def test_no_show_is_not_a_game(self):
        # Both sides get a server-generated lead |switch|; nobody ever moved.
        log = self._log("|switch|p1a: Tauros|Tauros|353/353\n"
                        "|switch|p2a: Chansey|Chansey|703/703\n"
                        "|-message|them lost due to inactivity.\n"
                        "|win|nickgen1rbrlbot\n")
        assert lc.classify(log, "nickgen1rbrlbot") == "no_show"

    def test_midgame_timeout_is_a_game(self):
        # SAME marker string as the no-show above — only the moves differ.
        log = self._log("|switch|p1a: Tauros|Tauros|353/353\n"
                        "|switch|p2a: Chansey|Chansey|703/703\n"
                        "|move|p2a: Chansey|Ice Beam|p1a: Tauros\n"
                        "|move|p1a: Tauros|Body Slam|p2a: Chansey\n"
                        "|-message|them lost due to inactivity.\n"
                        "|win|nickgen1rbrlbot\n")
        assert lc.classify(log, "nickgen1rbrlbot") == "timeout_midgame"

    def test_forfeit_is_a_game_not_a_non_game(self):
        log = self._log("|move|p2a: Chansey|Ice Beam|p1a: Tauros\n"
                        "|-message|them forfeited.\n"
                        "|win|nickgen1rbrlbot\n")
        assert lc.classify(log, "nickgen1rbrlbot") == "forfeit"

    def test_switch_only_opponent_still_counts_as_no_show(self):
        # A switch is not a submitted move for this purpose — the lead is
        # server-generated, so switch>0 must not rescue a no-show.
        log = self._log("|switch|p2a: Chansey|Chansey|703/703\n"
                        "|-message|them lost due to inactivity.\n")
        assert lc.classify(log, "nickgen1rbrlbot") == "no_show"

    def test_seat_is_resolved_by_name_not_by_slot(self):
        # We are p2 here; the opponent is p1. A hardcoded slot would invert.
        log = ("|player|p1|them|169|1250\n"
               "|player|p2|nickgen1rbrlbot|170|1300\n"
               "|move|p1a: Chansey|Ice Beam|p2a: Tauros\n")
        assert lc.opponent_moved(log, "nickgen1rbrlbot") is True

    def test_unknown_seat_returns_none_rather_than_guessing(self):
        log = "|player|p1|alice|1|1|\n|player|p2|bob|2|2|\n|move|p1a: X|Y|p2a: Z\n"
        assert lc.opponent_moved(log, "nickgen1rbrlbot") is None

    def test_real_ids_only_smoke_ids_excluded(self, tmp_path):
        # Local smokes now share the real filename prefix; only id WIDTH
        # separates them. An 8-digit id must not enter the readout.
        (tmp_path / "nickgen1rbrlbot - battle-gen1randombattle-2670552813.html"
         ).write_text("real")
        (tmp_path / "nickgen1rbrlbot - battle-gen1randombattle-40887568.html"
         ).write_text("smoke")
        got = lc.load_replays(tmp_path)
        assert set(got) == {"2670552813"}
