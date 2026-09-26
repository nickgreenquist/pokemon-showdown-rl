"""The R7 post-fleet reads (2026-09-26): configs/eval/r7_reads_offfp.yaml (the PRIMARY credit read + the object rule,
off FP@N 25k/12k) and configs/eval/r7_reads.yaml (vs SH), checked against the fleet pre-reg they operationalize -- the
lanes, donors and pairs READ from configs/r7_fleet_*.yaml, never retyped -- plus scripts/monster_reads_pin.py's R7
trios and scripts/r7_reads_queue.sh's lane list and jobs."""
import pathlib
import re
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import monster_reads_pin as pin  # noqa: E402

FP = yaml.safe_load((ROOT / "configs/eval/r7_reads_offfp.yaml").read_text())
SH = yaml.safe_load((ROOT / "configs/eval/r7_reads.yaml").read_text())
R6FP = yaml.safe_load((ROOT / "configs/eval/r6_reads_offfp.yaml").read_text())
MANIFEST = [l.split() for l in (ROOT / "configs/r7_fleet_lanes.txt").read_text().splitlines() if l.strip() and not l.startswith("#")]


def fleet_lanes() -> dict[str, dict]:
    """{lane key: {run_dir, arm, f, donor}} from the fleet's own configs (the manifest, then each config)."""
    out = {}
    for cfg, seed in MANIFEST:
        text = (ROOT / cfg).read_text()
        c = yaml.safe_load(text)
        arm = "searched" if "searched" in cfg else "control"
        f = re.search(r"_f(\d)\.yaml$", cfg).group(1)
        donor = re.search(r"warm-starts from (\S+?\.pt)", text).group(1)
        key = ("s" if arm == "searched" else "c") + seed
        assert int(c["seed"]) == int(seed)
        out[key] = {"run_dir": f"runs/{c['run_name']}", "arm": arm, "f": f"f{f}", "donor": donor}
    return out


LANES = fleet_lanes()


def test_the_fleet_is_three_plus_two_and_the_lanes_match():
    assert sorted(k for k, v in LANES.items() if v["arm"] == "searched") == ["s376", "s384", "s392"]
    assert sorted(k for k, v in LANES.items() if v["arm"] == "control") == ["c400", "c408"]
    assert FP["lanes"]["run_dirs"] == {k: v["run_dir"] for k, v in LANES.items()}
    for arm in ("searched", "control"):
        assert FP["lanes"][arm] == {v["f"]: k for k, v in LANES.items() if v["arm"] == arm}


def test_pairs_share_a_donor_and_the_donors_are_trio_b():
    by_f = {}
    for k, v in LANES.items():
        by_f.setdefault(v["f"], []).append(v["donor"])
    for f, donors in by_f.items():
        assert len(set(donors)) == 1, f                          # a pair is one donor
    trio_b = [R6FP["checkpoints"][x]["path"] for x in ("b328", "b336", "b344")]
    assert [by_f[f][0] for f in ("f1", "f2", "f3")] == trio_b
    assert [FP["checkpoints"][x]["path"] for x in ("b328", "b336", "b344")] == trio_b


def test_primary_arms_greedy_breaker_off_6000_in_the_pinned_order():
    arms = FP["arms"]
    assert FP["run_order"] == ["C1F", "S1F", "C2F", "S2F", "S3F", "E6RR", "E3BR", "ES3F", "EC2F"]
    assert sorted(arms) == sorted(FP["run_order"]) and FP["lost_lanes"] == []
    P = FP["primary"]
    seat = lambda a: arms[a]["seat"]  # noqa: E731
    assert [seat(a) for a in P["searched"]] == ["s376", "s384", "s392"] and [seat(a) for a in P["control"]] == ["c400", "c408"]
    for f, (s, c) in P["pairs"].items():
        assert LANES[seat(s)]["f"] == f == LANES[seat(c)]["f"] and LANES[seat(s)]["arm"] == "searched"
    for a in P["searched"] + P["control"]:
        x = arms[a]
        assert x["kind"] == "greedy_seat" and x["loop_breaker"] is False and x["battles"] == 6000, a


def test_object_rule_arms_in_the_r6_object_form():
    arms = FP["arms"]
    e6rf = R6FP["arms"]["E6RF"]["lanes"]                         # R6's readout R2: the object E6RF
    assert arms["E6RR"]["lanes"] == e6rf and arms["E3BR"]["lanes"] == R6FP["arms"]["E3BF"]["lanes"]
    assert arms["ES3F"]["lanes"] == ["s376", "s384", "s392"] and arms["EC2F"]["lanes"] == ["c400", "c408"]
    for a in ("E6RR", "E3BR", "ES3F", "EC2F"):
        assert arms[a]["kind"] == "ensemble_seat" and arms[a]["loop_breaker"] is True and arms[a]["battles"] == 3000, a
    assert FP["object_rule"] == {"incumbent": "E6RR", "donors_ens3": "E3BR", "fleet": ["ES3F", "EC2F"], "tolerance": 0.013}


def test_every_arm_is_fpn_25k_12k_c6_on_with_its_usernames():
    for a, x in FP["arms"].items():
        assert (x["search_iterations"], x["search_iterations_early"], x["search_time_ms"]) == (25000, 12000, 20), a
        assert FP["arm_encoder"][a] == {"c6": True}, a
        pair = FP["usernames"]["pairs"][a]
        assert (x["seat_username"], x["fp_username"]) == (pair["seat"], pair["fp"]), a
        for lane in ([x["seat"]] if x["kind"] == "greedy_seat" else x["lanes"]):
            assert lane in FP["checkpoints"], (a, lane)
    assert set(FP["usernames"]["rerun_pairs"]) == set(FP["arms"])
    assert FP["fp"]["search_iterations"] == 25000 and FP["fp"]["search_iterations_early"] == 12000


def test_usernames_prefix_free_across_the_inventory():
    names = set()
    for f in (ROOT / "configs/eval").glob("*.yaml"):
        names |= set(re.findall(r"(?:seat_username|fp_username|seat|fp):\s*([a-z0-9]+)\b", f.read_text()))
    names = sorted(names)
    assert not [(a, b) for a in names for b in names if a != b and b.startswith(a)]
    mine = [v for p in (FP["usernames"]["pairs"], FP["usernames"]["rerun_pairs"]) for d in p.values() for v in d.values()]
    assert all(n.startswith("r7rd") and len(n) <= 18 for n in mine) and len(mine) == len(set(mine))


def test_placeholders_and_copied_pins():
    for f in (FP, SH):
        for lane in ("s376", "s384", "s392", "c400", "c408"):
            assert f["checkpoints"][lane] == {"path": "TBD", "sha256": "TBD", "step": "TBD"}
    for x in ("a304", "a312", "a320", "b328", "b336", "b344"):
        assert FP["checkpoints"][x] == R6FP["checkpoints"][x]
    assert SH["arms"]["GS"]["lanes"] == ["s376", "s384", "s392"] and SH["arms"]["GC"]["lanes"] == ["c400", "c408"]
    assert SH["credits_nothing"] is True and FP["credits_nothing"] is False


def test_pin_script_knows_the_r7_trios():
    s = dict(pin.TRIOS["s"]); c = dict(pin.TRIOS["c"])
    assert s == {k: FP["lanes"]["run_dirs"][k] for k in ("s376", "s384", "s392")}
    assert c == {k: FP["lanes"]["run_dirs"][k] for k in ("c400", "c408")}
    assert pin.HORIZON_BY_TRIO == {"s": 100_000_000, "c": 100_000_000} and pin.HORIZON == 200_000_000
    assert pin.CONFIGS_BY_TRIO["s"] == pin.CONFIGS_BY_TRIO["c"] == ["configs/eval/r7_reads.yaml", "configs/eval/r7_reads_offfp.yaml"]
    # the placeholder regex the pin rewrites must match every R7 lane line in both files
    for cfg in pin.R7_CONFIGS:
        text = (ROOT / cfg).read_text()
        for lane in ("s376", "s384", "s392", "c400", "c408"):
            assert re.search(rf"^(  {lane}: )\{{path: TBD, sha256: TBD, step: TBD\}}", text, re.M), (cfg, lane)


def test_final_ckpt_reads_the_horizon(tmp_path):
    for step in (99_500_012, 100_000_031, 100_000_007):
        (tmp_path / f"ckpt_{step:09d}.pt").write_bytes(b"")
    step, path = pin.final_ckpt(str(tmp_path), 100_000_000)
    assert step == 100_000_031 and path.endswith("ckpt_100000031.pt")
    assert pin.final_ckpt(str(tmp_path)) is None                 # the 200M default finds nothing here


def test_queue_lanes_and_jobs_match():
    q = (ROOT / "scripts/r7_reads_queue.sh").read_text()
    lanes = re.search(r'^LANES="([^"]+)"', q, re.M).group(1).split()
    assert lanes == [FP["lanes"]["run_dirs"][k] for k in ("s376", "s384", "s392", "c400", "c408")]
    import ch3_eval
    jobs = sorted(ch3_eval._jobs(SH))
    assert jobs == ["gc_c400", "gc_c408", "gs_s376", "gs_s384", "gs_s392"]
    assert sorted(re.findall(r"\bjob (g[sc]_[sc]\d+)", q)) == jobs
