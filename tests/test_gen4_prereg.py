"""configs/gen4_wang50m.yaml — internal-consistency gates (R0-a's automated
half). Green from draft through ratification through readout; reads no run
data. The pattern is tests/test_100m_prereg.py's: the one-diff assertion
against the smoke partner in BOTH directions (the defect class is R2's own —
a "one-lever" config that silently carries a second delta), the recipe
values against the sidecar's record of Wang's Table A.3, the update-size
arithmetic, the seed windows, and the header's load-bearing verbatims."""

import math
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
MAIN = yaml.safe_load((REPO / "configs/gen4_wang50m.yaml").read_text())
SMOKE = yaml.safe_load((REPO / "configs/gen4_wang50m_smoke.yaml").read_text())
SIDE = yaml.safe_load((REPO / "configs/gen4_wang50m.prereg.yaml").read_text())
TXT = (REPO / "configs/gen4_wang50m.yaml").read_text()
# The header is a wrapped comment block; verbatim checks read it unwrapped.
FLAT = re.sub(r"\n#\s*", " ", TXT)


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = v
    return out


def test_r0a_one_diff_vs_the_smoke_both_directions():
    m, s = _flat(MAIN), _flat(SMOKE)
    assert m.keys() == s.keys(), f"key sets differ: {sorted(m.keys() ^ s.keys())}"
    changed = sorted(k for k in m if m[k] != s[k])
    assert changed == [
        "agent.lr_anneal_steps", "checkpoint_every", "eval_episodes", "eval_every",
        "run_name", "seed", "total_steps",
    ], f"unexpected delta set: {changed}"
    assert SMOKE["total_steps"] == SMOKE["agent"]["lr_anneal_steps"] == 3 * 19_968
    assert SMOKE["checkpoint_every"] == 0 and SMOKE["seed"] == 999


def test_r0b_recipe_is_wangs_table_a3():
    a, w = MAIN["agent"], SIDE["wang_recipe"]
    assert MAIN["total_steps"] == a["lr_anneal_steps"] == 50_000_000
    assert math.isclose(a["lr"], 10 ** -4.23, rel_tol=1e-4) and a["lr"] == w["learning_rate"]
    assert a["lr_schedule"] == "power" and a["lr_power_a"] == 8.0 and a["lr_power_b"] == 1.5
    assert a["epochs"] == w["n_epochs"] == 7
    assert a["gamma"] == w["gamma"] == 0.9999
    assert a["gae_lambda"] == w["gae_lambda"] == 0.754
    assert a["clip_eps"] == w["clip_range"] == 0.0829
    assert a["value_clip_eps"] == w["clip_range_vf"] == 0.0184
    assert a["entropy_coef"] == w["entropy_coef"] == 0.0588
    assert a["value_coef"] == w["value_coef"] == 0.4375
    assert a["max_grad_norm"] == w["max_grad_norm"] == 0.543
    assert math.isclose((8.0 + 1.0) ** 1.5, SIDE["update_arithmetic"]["lr_floor_factor"])


def test_r0f_update_arithmetic():
    u, a = SIDE["update_arithmetic"], MAIN["agent"]
    assert MAIN["num_envs"] * a["rollout_steps"] == u["seat1_rows_per_update"] == 19_968
    assert 2 * u["seat1_rows_per_update"] == u["union_rows_per_update_nominal"] == 78 * 512
    assert a["minibatches"] == u["minibatches"] == 39
    assert u["union_rows_per_update_nominal"] // u["minibatches"] == u["minibatch_width_nominal"] == 1024
    assert SIDE["wang_recipe"]["batch_size"] == 1024 and SIDE["wang_recipe"]["n_steps_total_rows"] == 39_936
    assert MAIN["total_steps"] // u["seat1_rows_per_update"] == u["updates"] == 2_504
    assert u["updates"] * u["seat1_rows_per_update"] == 49_999_872
    assert MAIN["total_steps"] % MAIN["num_envs"] == 0  # the loop ends at 50M exactly
    assert MAIN["total_steps"] // MAIN["checkpoint_every"] == u["rungs_per_lane"] == 100
    assert MAIN["checkpoint_every"] % MAIN["num_envs"] == 0  # rungs land on their grid literal
    assert math.isclose(MAIN["total_steps"] / SIDE["wang_recipe"]["per_seat_dose"], 2 / 3, rel_tol=1e-9)
    # [R1-2 / R2-M3]: the union batch is not a multiple of 39, so the plan is
    # 39 full slices plus a 0–38-row tail under `keep` — 40 on ~38/39 of updates.
    from rl.agents.ppo import _minibatch_slices

    for rows in (39_936, 39_654, 40_087):
        slices, floor = _minibatch_slices(rows, rows // 39, "keep")
        assert len(slices) == (39 if rows % 39 == 0 else 40) and floor == 2
    assert u["minibatch_slices_per_epoch"] == 40
    # [R1-1]: the anneal is applied from steps_seen = (u - 1) x 19,968 at a
    # checkpoint whose `updates` field reads u — the D-A closed form.
    lr0 = MAIN["agent"]["lr"]
    for u_field in (250, 1252, 2504):
        x = ((u_field - 1) * 19_968) / 5e7
        assert 0 < x < 1 and math.isclose(lr0 * (8 * x + 1) ** -1.5, lr0 / (8 * x + 1) ** 1.5)
    assert math.isclose(lr0 / (8 * (2503 * 19_968 / 5e7) + 1) ** 1.5, 2.1821e-6, rel_tol=1e-4)


def test_mirror_selfplay_and_harvest_are_on():
    sp = MAIN["selfplay"]
    assert sp == {"opponent": "self", "eval_opponent": "heuristics", "pool_size": 1,
                  "push_every_updates": 1, "latest_prob": 1.0, "harvest_both_seats": True}
    assert MAIN["env_id"] == "ShowdownGen4-v0" and "collector" not in MAIN and "env_kwargs" not in MAIN
    assert "privileged_dim" not in MAIN["agent"] and "aux_oppact_coef" not in MAIN["agent"]
    tk = MAIN["agent"]["trunk_kwargs"]
    assert MAIN["agent"]["trunk"] == "entity_deepsets" and tk["layout"] == "gen4"
    assert [tk["species_vocab"], tk["move_vocab"], tk["item_vocab"], tk["ability_vocab"]] == SIDE["freeze"]["vocab_tables"]


def test_freeze_matches_the_code_and_the_hash_gate():
    from rl.envs.gen4.spec import ENCODER_FINGERPRINT_GEN4, LAYOUT
    from rl.envs.gen4.vocab import VOCAB
    from tests.test_gen4_encoder import GEN4_CORPUS_SHA, GEN4_FIXTURE_SHA

    f = SIDE["freeze"]
    assert LAYOUT.obs_dim == f["obs_dim"] == 1448 and LAYOUT.priv_dim == f["priv_dim"] == 703
    assert ENCODER_FINGERPRINT_GEN4["layout"] == f["layout"] == "v0.1"
    assert f["corpus_sha256"] == GEN4_CORPUS_SHA and f["fixture_sha256"] == GEN4_FIXTURE_SHA
    assert VOCAB.showdown_commit == f["showdown_commit"] and VOCAB.sets_sha256 == f["sets_sha256"]
    assert [VOCAB.n_species, VOCAB.n_moves, VOCAB.n_items, VOCAB.n_abilities] == f["vocab_tables"]
    for sha in (f["corpus_sha256"], f["fixture_sha256"], f["showdown_commit"], f["sets_sha256"]):
        assert sha in TXT, f"{sha[:12]} not carried in the header"


def test_thresholds_are_the_rulings():
    p = SIDE["primary"]
    assert p["milestone_threshold"] == 0.60 and p["step5_threshold"] == 0.756 and p["step5_target"] == 0.786
    se = math.sqrt(0.786 * (1 - 0.786) / 200)
    assert math.isclose(se, p["wang_se"], abs_tol=5e-5)
    # The arithmetic (0.757) vs the ruled 0.756: the gap is disclosed, not corrected (RW-1).
    assert round(0.786 - se, 3) == 0.757 and "0.7570" in TXT and "RW-1" in TXT
    assert p["k_min_for_a_branch"] == 3 and SIDE["credits_nothing"] is True


def test_seed_windows_disjoint_and_unused():
    lanes, spares, w = SIDE["seeds"]["lanes"], SIDE["seeds"]["spares"], SIDE["seeds"]["window"]
    assert lanes == [200, 208, 216] and spares == [224, 232, 240] and w == MAIN["num_envs"] == 8
    assert MAIN["seed"] == lanes[0] and MAIN["run_name"] == "gen4_wang50m_s200"
    windows = [set(range(s, s + w)) for s in lanes + spares]
    for i in range(len(windows)):
        for j in range(i + 1, len(windows)):
            assert not windows[i] & windows[j]
    used = set()
    legal = {f"gen4_wang50m_s{s}" for s in lanes + spares}
    if (REPO / "runs").exists():
        for p in (REPO / "runs").glob("*/config.yaml"):
            if p.parent.name in legal:
                continue
            m = re.search(r"^seed: (\d+)", p.read_text(), re.M)
            if m:
                used.add(int(m.group(1)))
    for win in windows:
        assert not (win & used), f"window {sorted(win)} hits stamped seeds {win & used}"


def test_agent_constructs_with_the_stamped_param_counts():
    """[R2-M2] R0-d: the pre-reg's own config builds the gen-4 entity trunk at
    exactly the stamped widths — a trunk-width, vocab-table or layout change
    fails here, not silently at launch."""
    from types import SimpleNamespace

    import torch

    from rl.common.config import load_config
    from rl.envs.gen4.env import fake_spaces_gen4
    from rl.train import make_agent

    cfg = load_config(REPO / "configs/gen4_wang50m.yaml")
    obs, act = fake_spaces_gen4()
    torch.manual_seed(0)
    agent = make_agent(cfg, SimpleNamespace(observation_space=obs, action_space=act, num_envs=cfg.num_envs))
    actor = sum(p.numel() for p in agent.actor.parameters())
    critic = sum(p.numel() for p in agent.critic.parameters())
    assert (actor, critic) == (674_763, 543_553)
    assert (actor, critic) == (SIDE["freeze"]["params"]["actor"], SIDE["freeze"]["params"]["critic"])
    assert agent.lr_schedule == "power" and agent.value_clip_eps == 0.0184 and agent.minibatch_tail == "keep"


def test_header_carries_the_load_bearing_verbatims():
    assert FLAT.count("LARGER of the pooled-binomial se_diff") == 1
    assert "THIS RUN CREDITS NOTHING" in FLAT
    assert "journey_step: 3 -> 4" in FLAT
    for s in ("≥ 0.60 vs", "≥ 0.756, one-sided", "0.786 (Table", "names DOSE"):
        assert s in FLAT, s
    assert TXT.count("[SMOKE-FILL") == 0, "unfilled smoke cells remain"
    for d in SIDE["disclosures"]:
        assert TXT.count(d) >= 2, f"disclosure {d} named fewer than twice"
    for leg in ("L1", "L2", "L3", "L4", "L5"):
        assert f"#   {leg} " in TXT and leg in SIDE["battery"]  # [R1-21]
    # [R2-M4] the barred phrases (minus their parenthetical rules) must not
    # appear in the header as assertions — only inside the barring sentences,
    # which all carry the word BARRED or the barred_language pointer.
    for phrase in SIDE["barred_language"]:
        head = phrase.split(" (")[0]
        if head in ("flat", "plateau"):
            continue  # the S-SHAPE sentence enumerates the permitted forms
        exempt = ("BARRED", "barred", "only \"matched\"", "credited iff", "called credited",
                  'carries "credited"')
        for line in TXT.splitlines():
            if head in line:
                assert any(e in line for e in exempt), (head, line)
    assert '"flat" and "plateau" are BARRED' in TXT
    assert "NETWORK ALONE" in TXT and "3v3" in TXT and "0.836" in TXT  # [R1-3, R1-9]
    assert "(u − 1) × 19,968" in TXT  # [R1-1]
    assert "[173, 234]" in TXT  # [R1-7]
    assert "N_EFF" in TXT and "CELL K ROUTE" in TXT  # [R1-6, R1-23]
    # [R2-S14] the frozen review copy is byte-identical to the config.
    assert (REPO / "results/design_gen4_wang50m/gen4_wang50m.draft.yaml").read_text() == TXT
    for rw in SIDE["rulings_wanted"]:
        assert rw in TXT
    assert SIDE["prereg_for"] == "configs/gen4_wang50m.yaml"
