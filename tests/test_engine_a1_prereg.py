"""Pins configs/engine_a1.yaml + its sidecar — A-1's pre-registration.

A pre-reg is an irreversible artifact: once a run launches against it, editing
it is falsification. These tests are what make that enforceable, and they are
written to catch the three failure modes review 1 actually found rather than to
restate the header:

  * a key the loader would REFUSE (the committed draft carried
    `collector.privileged`, which ENGINE_KEYS rejects — the config could not
    have loaded at all);
  * a claim of byte-identity with the banked arm that is not true;
  * an open ruling the header quietly answers for the maintainer.

No server, no training, no rl imports — YAML only.
"""

from __future__ import annotations

import pathlib
import re

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
HDR = REPO / "configs/engine_a1.yaml"
SIDE_P = REPO / "configs/engine_a1.prereg.yaml"
BANKED = REPO / "configs/showdown_sp_batch50m_async.yaml"
JOURNEY = REPO / "JOURNEY.md"

TXT = HDR.read_text()
RAW = yaml.safe_load(TXT)
SIDE = yaml.safe_load(SIDE_P.read_text())

# The header is a comment block wrapped at ~72 chars; FLAT lets a quote that
# spans lines be compared as one string (the gen-4 pre-reg test's convention).
FLAT = re.sub(r"\s+", " ", "\n".join(
    l.lstrip("#").strip() for l in TXT.splitlines() if l.startswith("#")))

# rl/train.py:687. Duplicated deliberately: importing rl here would pull in the
# env stack, and this test must stay server-free.
ENGINE_KEYS = {"mode", "k", "team_bank", "learner_seat", "min_bank_pairs"}
ALLOWED_DIFF = {"collector", "run_name", "env_kwargs.seat_tag"}


def _flatten(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


# --- the loader would accept this file ---------------------------------------

def test_collector_keys_are_exactly_what_the_engine_mode_accepts():
    """The bug that shipped in the first draft: `collector.privileged` is not a
    key. rl/train.py raises 'unknown collector key(s)' and the lane never
    starts. D18 is off BY ABSENCE of agent.privileged_dim instead."""
    assert RAW["collector"]["mode"] == "engine"
    extra = set(RAW["collector"]) - ENGINE_KEYS
    assert not extra, f"collector.mode 'engine' would REFUSE these keys: {sorted(extra)}"
    assert "privileged_dim" not in RAW["agent"], \
        "agent.privileged_dim set — rl/train.py refuses D18 on the engine path"


def test_contamination_guards_are_off():
    assert not RAW["selfplay"].get("harvest_both_seats", False)
    assert RAW["env_kwargs"]["opp_action"] is True, "the banked arm has D25 labels"
    assert RAW["agent"]["aux_oppact_coef"] == 0.1


# --- the arms differ only where the header says they do -----------------------

def test_only_declared_keys_differ_from_the_banked_arm():
    a, b = _flatten(RAW), _flatten(yaml.safe_load(BANKED.read_text()))
    diff = {k for k in set(a) | set(b) if a.get(k, "<absent>") != b.get(k, "<absent>")}
    undeclared = {k for k in diff
                  if not any(k == d or k.startswith(d + ".") for d in ALLOWED_DIFF)}
    assert not undeclared, (
        f"undeclared differences from the banked arm: {sorted(undeclared)} — the "
        "header claims byte-identity below the collector block")


def test_the_anneal_trap_is_pinned():
    """A 12M budget with lr_anneal_steps == total_steps would compare LR
    schedules, not collectors. G9's verbatim obligation."""
    assert RAW["total_steps"] == 50_000_000
    assert RAW["agent"]["lr_anneal_steps"] == 50_000_000
    assert RAW["num_envs"] * RAW["agent"]["rollout_steps"] == 30_720


def test_k_matches_the_banked_concurrency():
    banked = yaml.safe_load(BANKED.read_text())
    assert RAW["collector"]["k"] == banked["collector"]["concurrency"] == 8, \
        "A-1 runs at the banked arm's width so the COLLECTOR is the only delta"


# --- the header says what the repo requires it to say -------------------------

def test_credit_line_is_verbatim_and_appears_once():
    line = ("a lever is credited iff pooled delta >= +0.025 AND >= 2*se_diff, "
            "where se_diff is the LARGER of the pooled-binomial se_diff and the "
            "seed-clustered se_diff, the latter computed from the per-seed finals "
            "at read time.")
    assert FLAT.count(line) == 1
    assert "IT DOES NOT APPLY TO A-1" in FLAT


@pytest.mark.parametrize("quote", [
    "A-1 acceptance is the gate — 3 seeds × 12M inside |Δ| < 0.025 of the async "
    "acceptance fleet, with the signed delta travelling forever after as N-COLL's "
    "does; outside the band we diagnose parity and do NOT switch.",
    "Pre-decided failure branch. If two diagnosis rounds cannot bring A-1's 12M "
    "read inside |Δ| < 0.025, we KEEP the server path; the sunk cost is then the "
    "parity harness, which survives as a test suite.",
])
def test_journey_quotes_are_byte_equal_to_journey(quote):
    """VERBATIM means verbatim, Unicode included — the first draft transliterated
    × to x and Δ to D."""
    # Markdown emphasis markers are formatting, not text: JOURNEY writes
    # "(ii) **Pre-decided failure branch.** If two ...". They are stripped on
    # both sides; every other character must match.
    j = re.sub(r"\s+", " ", JOURNEY.read_text().replace("**", ""))
    assert quote in j, "not a quote of JOURNEY.md at all"
    assert quote in FLAT, "the header's version is not byte-equal"


def test_every_open_ruling_is_named_in_the_header():
    for rw in SIDE["rulings_wanted"]:
        assert rw in TXT, (
            f"{rw} is owed but the header never mentions it — a header that "
            "reads as settled on an open ruling answers it for the maintainer")


def test_every_ruling_is_ratified():
    ratified = SIDE["ratified_decisions"]
    assert set(ratified) == set(SIDE["rulings_wanted"]), \
        "every open ruling must be answered, or the header still speaks for the maintainer"
    assert SIDE["is_equivalence_test"] is False
    assert SIDE["precondition"]["state_at_drafting"] == "NEVER RUN"


def test_launch_authorization_is_a_record_not_a_ratification():
    """Separate acts, separately recorded. The authorization says WHO granted
    it, WHAT it covers, and what was still unmet when it was granted — D-1
    above all, which is step 2 of the chain and hard-stops it on failure."""
    auth = SIDE["launch_authorization"]
    if auth == "NONE":
        return                                  # not yet granted; nothing to check
    assert isinstance(auth, dict)
    for field in ("granted_by", "covers", "preconditions_at_grant", "box_at_grant"):
        assert field in auth, f"launch_authorization is missing {field}"
    assert "UNRUN" in auth["preconditions_at_grant"]["d1"], \
        "an authorization that does not say D-1 was still unrun is not honest"


def test_rw8_ruled_secondary_so_the_verdict_is_the_endpoint_alone():
    """The AUC is WIDER than the endpoint on the async arm — the arm A-1 is
    actually compared against — so promoting it was refused."""
    assert SIDE["primary"]["both_must_hold"] is False
    assert SIDE["primary"]["P-AUC"]["status"] == "SECONDARY_DESCRIPTIVE"
    assert "A1-SPLIT" not in SIDE["branches"]
    assert "the verdict is P-END ALONE" in FLAT


def test_rw6_bank_target_and_enforced_floor_agree():
    assert RAW["collector"]["team_bank"].endswith("teams_a1_5000000.bin")
    assert RAW["collector"]["min_bank_pairs"] == 1_000_000


def test_rw7_amendment_landed_with_ratification():
    """The header says the third-legal-owner amendment belongs to the
    ratification commit, not to a post-hoc fix."""
    guard = (REPO / "tests/test_ch5_r2_prereg.py").read_text()
    assert 'f"engine_a1_s{s}"' in guard


def test_the_precondition_is_recorded_as_unmet():
    assert SIDE["precondition"]["gate"] == "D-1"
    assert SIDE["precondition"]["state_at_drafting"] == "NEVER RUN"
    assert len(SIDE["precondition"]["matchups"]) == 2


# --- the two halves agree ------------------------------------------------------

def test_sidecar_and_header_agree_on_every_constant():
    for value in ("0.67211", "0.64597", "0.025", "0.01499", "+0.02322"):
        assert value in TXT, f"{value} missing from the header"
    assert SIDE["primary"]["P-END"]["band"] == 0.025
    assert SIDE["primary"]["P-AUC"]["band"] == 0.025
    assert SIDE["power"]["planning_sigma"] == 0.01499
    assert SIDE["baseline_by_provenance"]["pooled_endpoint"] == 0.67211
    assert SIDE["baseline_by_provenance"]["pooled_auc"] == 0.64597
    assert len(SIDE["baseline_by_provenance"]["lanes"]) == 3


def test_baseline_is_pinned_by_sha_not_by_the_number():
    for lane in SIDE["baseline_by_provenance"]["lanes"]:
        assert len(lane["config_sha256"]) == 64
        assert len(lane["ckpt_sha256"]) == 64
        assert lane["ckpt"].startswith("ckpt_0120")
        assert lane["config_sha256"] in TXT, "the header must carry the sha too"


def test_no_duplicate_keys_at_any_depth():
    """The R1 defect: a key defined twice parses to the LAST value under PyYAML
    and every passing test saw nothing."""
    class Strict(yaml.SafeLoader):
        pass

    def no_dupes(loader, node, deep=False):
        seen = set()
        for k, _ in node.value:
            key = loader.construct_object(k, deep=deep)
            assert key not in seen, f"duplicate key {key!r}"
            seen.add(key)
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, no_dupes)
    for p in (HDR, SIDE_P):
        yaml.load(p.read_text(), Loader=Strict)


# --- what review 2 changed, pinned so it cannot drift back --------------------

def test_both_arms_are_read_at_the_same_raised_n():
    """Precision here is bought with battles, not seeds: ~71% of the
    regime-matched sigma is eval-replicate noise. Raising n on one arm only
    would buy precision on one side only, so the banked arm is re-evaluated."""
    assert SIDE["power"]["eval_n_per_seed"] == 12000
    assert "RE-EVALUATED at the same n" in TXT or "RE-EVALUATED at the same n" in FLAT
    assert "12,000/seed" in FLAT


def test_the_planning_sigma_is_regime_matched_not_merely_annealed():
    """showdown_sp_recipe12m anneals over 12M and is fully decayed at the rung
    A-1 reads; A-1's arms still hold ~76% of base LR there."""
    assert "showdown_sp_recipe12m" in SIDE["power"]["excluded_from_regime"]
    fleets = SIDE["power"]["planning_sigma_fleets"]
    assert {f["fleet"] for f in fleets} == {
        "showdown_sp_batch50m", "showdown_sp_batch50m_async"}
    assert SIDE["power"]["planning_sigma_ci95"] == [0.0090, 0.0431]


def test_the_r0_label_gate_names_the_metric_that_can_actually_pass():
    """aux/label_present_frac measures [0.8345, 0.9406] on the BANKED lanes, so
    a [0.74, 0.88] gate on it would kill a perfect engine arm. The band belongs
    to aux/labelled_frac."""
    assert "aux/labelled_frac within [0.74, 0.88]" in FLAT
    assert "aux/label_present_frac within [0.74, 0.88]" not in FLAT


def test_the_auc_window_is_a_bucket_rule():
    """The 48th eval lands PAST 12,000,000, so a literal 250k..12.0M interval
    holds 47 async rungs against 48 sync ones."""
    assert "floor(_step / 250000) in 1..48" in FLAT


def test_the_blind_surface_and_the_anchor_leg_are_both_named():
    assert "FOE-SIDE PROJECTION" in FLAT and "recharge_fix" in FLAT
    assert "L-FP20" in TXT and "SEARCH IS THE TRAP" in FLAT
    assert "P-PARITY" in TXT and "rollout/episode_length" in FLAT
