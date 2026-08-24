"""CH4 R1 BI-1 — the off-SH instrument grader.

Implements configs/eval/ch4_r1_offsh_instrument.yaml: gates G2/G3/G5/G6/
G6b/G8 + era pins, R-1 s_T on its 95% CI (3-df), R-3 BT residual (rho =
FP EXCESS TAKE, positive = anomaly; hub common-mode se decomposition),
R-4 C1 on the LOGIT scale, R-5 S1-S0, the ORDERED P-cells, the branch
partition (R2 no-anomaly is the DEFAULT), and the MU-8-ruled P2-rider
re-grade. --selftest exercises the rho orientation on synthetic inputs
AND asserts the banked D26 numbers land in the NO-ANOMALY direction.
"""

import argparse
import json
import math
from pathlib import Path

import yaml

OUT = Path("results/ch4_r1_offsh")
CHI2_3DF_LOW_MULT = math.sqrt(3 / 9.3484)   # 0.5665: lower 95% CI multiplier
CHI2_3DF_HIGH_MULT = math.sqrt(3 / 0.2158)  # 3.7285: upper


def logit(p):
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1 / (1 + math.exp(-x))


def binom_se(p, n):
    return math.sqrt(p * (1 - p) / n)


def rho_and_se(obs_take, n_obs, hub, n_hub, vs_sh, n_vs):
    """rho = FP excess take (positive = FP over-performs = ANOMALY).
    se split into the COMMON hub term and the per-lane independent term."""
    pred = sigmoid(logit(hub) - logit(vs_sh))
    rho = obs_take - pred
    dpred = pred * (1 - pred)
    se_hub = dpred * binom_se(hub, n_hub) / (hub * (1 - hub))
    se_vs = dpred * binom_se(vs_sh, n_vs) / (vs_sh * (1 - vs_sh))
    se_obs = binom_se(obs_take, n_obs)
    return rho, pred, se_hub, math.sqrt(se_obs ** 2 + se_vs ** 2)


def pooled_rho(lanes):
    """lanes: list of (rho, se_hub, se_indep). Hub is common-mode: it does
    NOT average down (review 1 MA-6)."""
    k = len(lanes)
    rho = sum(x[0] for x in lanes) / k
    se_hub = sum(x[1] for x in lanes) / k
    se_ind = math.sqrt(sum(x[2] ** 2 for x in lanes)) / k
    return rho, math.sqrt(se_hub ** 2 + se_ind ** 2), se_hub, se_ind


def selftest():
    # Orientation: FP stronger than BT predicts -> positive rho.
    r, pred, _, _ = rho_and_se(0.70, 250, 0.83, 3000, 0.718, 3000)
    assert r > 0.03, f"synthetic over-perform must read POSITIVE, got {r}"
    r2, _, _, _ = rho_and_se(0.55, 250, 0.83, 3000, 0.718, 3000)
    assert r2 < -0.03, "synthetic under-perform must read NEGATIVE"
    # Banked D26 (hub 0.8307 n=7200, s65 0.703, FP take 0.612 n=250):
    r3, pred3, sh, si = rho_and_se(0.612, 250, 0.8307, 7200, 0.703, 3000)
    assert r3 < 0, f"banked D26 must land in the NO-ANOMALY direction, got {r3}"
    assert -0.09 < r3 < -0.03, f"banked rho should be ~-0.06, got {r3}"
    # Pooled se: hub common-mode -> pooled se > naive se_lane/sqrt(k).
    lanes = [rho_and_se(0.68, 3000, 0.83, 3000, p, 3000) for p in (0.71, 0.72, 0.73, 0.70)]
    pr, pse, pseh, psei = pooled_rho([(r, h, i) for r, _, h, i in lanes])
    naive = math.sqrt(sum((h ** 2 + i ** 2) for _, _, h, i in lanes)) / 4
    assert pse > naive, "hub common-mode must NOT average down"
    print(f"SELFTEST PASS: orientation, banked-D26 rho={r3:.4f} (no-anomaly), "
          f"pooled se {pse:.4f} > naive {naive:.4f}")


def load(tag):
    p = OUT / f"{tag}.json"
    return json.loads(p.read_text()) if p.exists() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    selftest()
    if args.selftest:
        return

    pre = yaml.safe_load(open("configs/eval/ch4_r1_offsh_instrument.yaml"))
    arch = json.loads((OUT / "archaeology.json").read_text())
    spb = json.loads((OUT / "sp_baseline.json").read_text())
    R = {"gates": {}, "era_pins": {}, "reads": {}, "notes": []}

    # ---- arms ----------------------------------------------------------
    V = {l: load(f"v{l[1:]}") for l in ("s62", "s63", "s64", "s65")}
    H1, H2 = load("h1"), load("h2")
    L = {l: load(f"l{l[1:]}") for l in ("s62", "s63", "s64", "s65")}
    C1, C1b, S1, E1 = load("c1"), load("c1b"), load("s1"), load("e1")
    runners = {t: json.loads((OUT / f"{t}.runner.json").read_text())
               for t in ("h1", "h2", "l62", "l63", "l64", "l65", "c1", "c1b", "s1", "e1")
               if (OUT / f"{t}.runner.json").exists()}

    # ---- gates ---------------------------------------------------------
    for tag, rj in runners.items():
        seat = load(tag)
        if seat is None:
            continue
        if "battles_finished" in seat:   # ch3_fp_h2h arms
            n_seat, n_fp = seat["battles_finished"], rj["fp_completed_battles"]
            cf = rj["crash_forfeits"]
            R["gates"][f"G2_{tag}"] = {
                "seat_finished": n_seat, "fp_completed": n_fp, "crash_forfeits": cf,
                "n_eff": n_seat - cf, "pass": n_fp == n_seat - cf}
            R["gates"][f"G3_{tag}"] = {"pass": seat["gate_all_challenges_resolved"]}
            R["gates"][f"G5_{tag}"] = {"mask_desyncs": seat["mask_desyncs"],
                                       "pass": True, "disclosed": seat["mask_desyncs"] != 0}
        if rj.get("void_too_many_crashes"):
            R["gates"][f"VOID_{tag}"] = True
    # G6 tiered (H arms report FP's take)
    if H1 and H2:
        h1t, h2t = H1["foulplay_win_rate"], H2["foulplay_win_rate"]
        d = abs(h1t - h2t)
        tier = "PASS" if d <= 0.02 else ("MARGINAL" if d <= 0.05 else "FAIL")
        R["gates"]["G6"] = {"h1_fp_take": h1t, "h2_fp_take": h2t, "abs_diff": d,
                            "tier": tier,
                            "se_diff": math.sqrt(binom_se(h1t, 3000) ** 2 + binom_se(h2t, 1000) ** 2)}
    # G6b from archaeology (style equivalence, quotability + MU-2)
    fg, fp20 = arch["FG"], arch["FP20"]
    g6b = {"d_sw": abs(fp20["sw_fp"]["rate"] - fg["sw_fp"]["rate"]),
           "d_turns_frac": abs(fp20["mean_turns"] - fg["mean_turns"]) / fg["mean_turns"],
           "d_faints": abs(fp20["faints_per_battle"] - fg["faints_per_battle"])}
    g6b["pass"] = g6b["d_sw"] <= 0.05 and g6b["d_turns_frac"] <= 0.15 and g6b["d_faints"] <= 0.75
    R["gates"]["G6b"] = g6b
    R["gates"]["G7"] = {"skipped": "k=1 everywhere (strictly serial wave) — the gate's trigger (k>1) never occurred"}
    # G8: prereg sha consistency across FP arms + realized budgets from logs
    shas = {t: load(t).get("prereg_sha256") for t in ("l62", "l63", "l64", "l65", "c1", "c1b", "s1", "e1") if load(t)}
    R["gates"]["G8_prereg_sha_consistent"] = {"values": sorted(set(shas.values())), "pass": len(set(shas.values())) == 1}
    import re
    budgets = {}
    for tag in ("h1", "h2", "l62", "l63", "l64", "l65", "c1", "c1b", "s1", "e1"):
        fplog = OUT / f"{tag}.fp.stdout"
        if not fplog.exists():
            continue
        arm = pre["arms"][tag.upper() if tag != "c1b" else "C1b"]
        declared = arm["search_time_ms"]
        combos = set()
        ok = True
        with open(fplog, errors="replace") as f:
            for line in f:
                m = re.search(r"Sampling (\d+) battles at (\d+)ms each", line)
                if m:
                    n_, ms_ = int(m.group(1)), int(m.group(2))
                    combos.add((n_, ms_))
                    if n_ * ms_ != 2 * declared:
                        ok = False
        budgets[tag] = {"declared_ms": declared, "combos": sorted(combos),
                        "invariant_NxM_eq_2xdeclared": ok, "pass": ok and bool(combos)}
    R["gates"]["G8_realized_budget"] = budgets

    # ---- era pins ------------------------------------------------------
    v_pooled = sum(v["eval/win_rate"] for v in V.values()) / 4
    R["era_pins"]["V"] = {"pooled": v_pooled, "banked": 0.71825,
                          "diff": v_pooled - 0.71825, "pass": abs(v_pooled - 0.71825) <= 0.020,
                          "per_lane": {l: v["eval/win_rate"] for l, v in V.items()}}
    if E1:
        R["era_pins"]["E1"] = {"value": E1["our_win_rate"], "band": [0.301, 0.475],
                               "pass": 0.301 <= E1["our_win_rate"] <= 0.475}
    if L["s65"]:
        R["era_pins"]["L65"] = {"value": L["s65"]["our_win_rate"], "band": [0.251, 0.373],
                                "pass": 0.251 <= L["s65"]["our_win_rate"] <= 0.373}

    # ---- R-1 s_T -------------------------------------------------------
    rates = {l: L[l]["our_win_rate"] for l in L if L[l]}
    xs = list(rates.values())
    k = len(xs)
    mean = sum(xs) / k
    s_T = math.sqrt(sum((x - mean) ** 2 for x in xs) / (k - 1))
    s_lo, s_hi = s_T * CHI2_3DF_LOW_MULT, s_T * CHI2_3DF_HIGH_MULT
    R["reads"]["R1_sT"] = {"per_lane": rates, "mean": mean, "s_T": s_T, "ddof": 1,
                           "ci95": [s_lo, s_hi], "lanes": k}

    # ---- R-2 rank agreement -------------------------------------------
    vs_order = sorted(rates, key=lambda l: V[l]["eval/win_rate"])
    fp_order = sorted(rates, key=lambda l: rates[l])
    R["reads"]["R2_rank"] = {"vs_sh_order": vs_order, "fp_order": fp_order,
                             "caveat": "n=4 rank stats are nearly uninformative"}

    # ---- R-3 rho -------------------------------------------------------
    hub = H1["foulplay_win_rate"]
    lanes = {}
    parts = []
    for l in rates:
        obs_take = 1 - rates[l]
        r, pred, sh, si = rho_and_se(obs_take, L[l]["battles_finished"], hub, 3000,
                                     V[l]["eval/win_rate"], 3000)
        lanes[l] = {"obs_fp_take": obs_take, "bt_pred_take": pred, "rho": r}
        parts.append((r, sh, si))
    pr, pse, pseh, psei = pooled_rho(parts)
    R["reads"]["R3_rho"] = {
        "hub_fp20_pinned": hub, "per_lane": lanes,
        "rho_pooled": pr, "se": pse, "se_hub_common": pseh, "se_indep": psei,
        "aggregator": "equal_weight_mean_of_per_lane_rho",
        "orientation": "positive = FP over-performs = anomaly against us"}

    # ---- R-4 C1 --------------------------------------------------------
    if C1:
        clone_vs_sh = pre["clone_vs_sh_pinned"]["value"]
        obs = C1["foulplay_win_rate"]
        pred = sigmoid(logit(hub) - logit(clone_vs_sh))
        excess = logit(obs) - logit(pred)
        se_l = 1 / math.sqrt(C1["battles_finished"] * obs * (1 - obs))
        R["reads"]["R4_C1"] = {
            "obs_take": obs, "bt_pred_take": pred, "logit_excess": excess,
            "se_logit": se_l, "threshold": 0.30,
            "our_pooled_comparator_logits": 0.60,
            "generic_brittleness": excess >= 0.30,
            "c1b_recorded_only": C1b["foulplay_win_rate"] if C1b else None}

    # ---- R-5 S1-S0 -----------------------------------------------------
    if S1 and L["s65"]:
        s0 = [b for b in L["s65"]["per_battle"] if b["index"] < 1000]
        s0_rate = sum(b["outcome"] == "win" for b in s0) / len(s0)
        s1_rate = S1["our_win_rate"]
        d = s1_rate - s0_rate
        se_d = math.sqrt(binom_se(s1_rate, S1["battles_finished"]) ** 2 + binom_se(s0_rate, len(s0)) ** 2)
        R["reads"]["R5_sampled_minus_greedy"] = {
            "s1": s1_rate, "s0_first_1000_of_l65": s0_rate, "delta": d,
            "two_se": 2 * se_d, "resolved": abs(d) >= 2 * se_d,
            "note": "inference-time observation, NOT a lever without its own pre-reg"}

    # ---- P-cells, ordered ---------------------------------------------
    thr = pre["thresholds"]
    cells = {}
    d_sw, d_se = fg["delta_sw"], fg["delta_sw_se"]
    cells["P_SHARP"] = {"stat": d_sw, "thr": thr["p_sharp_delta_sw"],
                        "fires": d_sw >= thr["p_sharp_delta_sw"] + 2 * d_se
                        and fg["sw_fp_crossval"]["pass_0.02"]}
    sw_v, sw_se = fg["status_ledger"]["swing"], fg["status_ledger"]["swing_se"]
    sp_v, sp_se = fg["sweep_share"]["value"], fg["sweep_share"]["se"]
    cells["P_MECH"] = {"status_swing": sw_v, "sweep_share": sp_v,
                       "fires": (sw_v >= thr["p_mech_status_swing"] + 2 * sw_se)
                       or (sp_v >= thr["p_mech_sweep_share"] + 2 * sp_se)}
    pc, pc_se = fg["p_cover"]["top_tercile_loss_share"], fg["p_cover"]["se"]
    cells["P_COVER"] = {"stat": pc, "fires": pc >= thr["p_cover_top_tercile_loss_share"] + 2 * pc_se}
    pe, pe_se = fg["p_eval_ahead_t20_loss_share"]["value"], fg["p_eval_ahead_t20_loss_share"]["se"]
    cells["P_EVAL"] = {"stat": pe, "fires": pe >= thr["p_eval_ahead_at_t20_loss_share"] + 2 * pe_se}
    fired = next((c for c in ("P_SHARP", "P_MECH", "P_COVER", "P_EVAL") if cells[c]["fires"]), None)
    R["reads"]["p_cells"] = {"cells": cells, "first_fired": fired,
                             "order": ["P_SHARP", "P_MECH", "P_COVER", "P_EVAL"]}
    # E-b sanity vs recomputed baseline
    band = spb["_band"]
    R["reads"]["E_b"] = {"fg_sw_us": fg["sw_us"]["rate"], "sp_band": [band["min"], band["max"]],
                         "within_band_plus_0.06": band["min"] - 0.06 <= fg["sw_us"]["rate"] <= band["max"] + 0.06}

    # ---- branch --------------------------------------------------------
    bt_fires = pr >= 0.03 and pr >= 2 * pse
    if s_lo >= 0.05:
        branch = "R1_instrument_infeasible"
    elif s_lo < 0.05 <= s_hi:
        branch = "R1b_instrument_unresolved"
    elif bt_fires and fired:
        branch = f"R3_real_hole_route_{fired}"
    elif bt_fires and not fired:
        branch = "R3_NULL_mechanism_unlocated"
    elif fired:
        branch = f"R3_real_hole_route_{fired}"
    else:
        branch = "R2_no_anomaly_DEFAULT"
    R["branch"] = branch
    R["branch_inputs"] = {"s_T_ci_low": s_lo, "s_T_ci_high": s_hi,
                          "rho_pooled": pr, "rho_2se": 2 * pse,
                          "bt_fires": bt_fires, "p_cell_fired": fired}

    # ---- P2-rider re-grade (MU-8 SUPERSEDE) ---------------------------
    # Lane-consistent s65 levels (falsifier anchors): greedy 0.71133 ->
    # search 0.79233 vs SH. BT-commensurate FP transfer prediction vs the
    # observed FG->FS delta (-0.020, se_diff 0.0434); clone analogue.
    def transfer_z(hub100):
        p_g = sigmoid(logit(hub100) - logit(0.71133))   # FP take vs greedy
        p_s = sigmoid(logit(hub100) - logit(0.79233))   # FP take vs search
        pred_delta = (1 - p_s) - (1 - p_g)              # our predicted gain
        return pred_delta, (-0.020 - pred_delta) / 0.0434
    hubs = {"banked_0.8307": 0.8307}
    if H2:
        hubs["h2_measured"] = H2["foulplay_win_rate"]
    R["reads"]["p2_regrade"] = {
        h: {"pred_transfer": round(t[0], 4), "z": round(t[1], 2)}
        for h, t in ((h, transfer_z(v)) for h, v in hubs.items())}
    R["reads"]["p2_regrade"]["status"] = "RULED_MU-8_SUPERSEDE — supersedes 'the FP anchor carried ~no information'"

    (OUT / "r1_readout.json").write_text(json.dumps(R, indent=2, default=str) + "\n")
    print(json.dumps({"branch": R["branch"], **R["branch_inputs"]}, indent=2))
    print("gates:", {k: (v if isinstance(v, bool) else v.get("pass", v.get("tier", "info")))
                     for k, v in R["gates"].items() if not isinstance(v, dict) or "pass" in v or "tier" in v})
    print(f"wrote {OUT/'r1_readout.json'}")


if __name__ == "__main__":
    main()
