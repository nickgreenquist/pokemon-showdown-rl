"""CH4 R1 BI-5 — the Foul-Play tape parser (archaeology R-6).

THE PARSE RULES ARE THE PRE-REGISTRATION (configs/eval/
ch4_r1_offsh_instrument.yaml Q5 R-6): forced replacements suppressed
(|faint| -> that side's next |switch|), automatic lead switch-ins between
|start and |turn|1 excluded, recharge |cant| excluded from the decision
denominator (slp/frz/par/flinch KEPT — the player had a live request),
sw_FP cross-validated against FP's own "Choice:" ground truth, battles
keyed by room prefix, rooms without |win| dropped AND counted.

Run:  python scripts/ch4_fp_tape_parse.py --selftest       # fixture first
      python scripts/ch4_fp_tape_parse.py                  # full corpus
Output: results/ch4_r1_offsh/archaeology.json
"""

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path

TAPES = {
    "FG":    {"tape": "results/ch3_r2_fp_h2h/fp_fg.stdout", "fp_ms": 100,
              "extra": ["results/ch3_r2_fp_h2h/fp_fs.attempt1.stdout"][0:0]},
    "FS":    {"tape": "results/ch3_r2_fp_h2h/fp_fs.stdout", "fp_ms": 100,
              "extra": ["results/ch3_r2_fp_h2h/fp_fs.attempt1.stdout"]},
    "FP20":  {"tape": "results/fp_budget_ladder/fp_FP20.stdout", "fp_ms": 20, "extra": []},
    "FP500": {"tape": "results/fp_budget_ladder/fp_FP500.stdout", "fp_ms": 500, "extra": []},
}
# FP usernames per tape corpus (named-file provenance: the ratified pre-regs).
FP_USERS = {"FG": "ch3fpbotg", "FS": "ch3fpbots", "FP20": "fpladbot20", "FP500": "fpladbot500"}

ROOM_RE = re.compile(r">(battle-gen1randombattle-\d+)")
HP_RE = re.compile(r"\|(\d+)/(\d+)")


def new_battle():
    return {
        "turns": 0, "winner_user": None, "leads": 0,
        "sw": {"p1": {"lead": 0, "forced": 0, "voluntary": 0},
               "p2": {"lead": 0, "forced": 0, "voluntary": 0}},
        "pending_faint": {"p1": 0, "p2": 0},
        "faints": {"p1": [], "p2": []},
        "cant": {"p1": defaultdict(int), "p2": defaultdict(int)},
        "first_status": None,          # (inflicting_side, cond, turn)
        "players": {},                 # p1/p2 -> username
        "started": False, "past_leads": False,
        "moves": {"p1": 0, "p2": 0},
        "attacking": {"p1": 0, "p2": 0},
        "crit_against": {"p1": 0, "p2": 0},
        "miss_by": {"p1": 0, "p2": 0},
        "explosion": {"p1": 0, "p2": 0},
        "hp": {},                      # "pN|name" -> frac
        "dmg_frac": defaultdict(lambda: {"p1": 0.0, "p2": 0.0}),  # turn -> frac lost by side
        "vol_switch_turns": {"p1": [], "p2": []},
        "fp_choices": 0, "fp_switch_choices": 0, "fp_forced_requests": 0,
        "avg_scores": [],              # (turn, mean avg_score)
        "mix_entropy": [],             # per-decision entropy of Considered Choices
        "sampling_lines": defaultdict(int),   # (n, ms) -> count
    }


def side_of(tok):
    return "p1" if tok.startswith("p1") else "p2"


def parse_stream(lines, battles, order):
    room = None
    in_protocol = False
    pending_mix = None
    for raw in lines:
        line = raw.rstrip("\n")
        if line.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")):
            in_protocol = False
            m = ROOM_RE.search(line)
            if m and "Received message from websocket" in line:
                room = m.group(1)
                if room not in battles:
                    battles[room] = new_battle()
                    order.append(room)
                in_protocol = True
                continue
            if room is None:
                continue
            b = battles[room]
            s = line[8:].strip()
            if s.startswith("Choice: "):
                b["fp_choices"] += 1
                if s.startswith("Choice: switch "):
                    b["fp_switch_choices"] += 1
                if pending_mix:
                    ps = [p for p in pending_mix if p > 0]
                    tot = sum(ps)
                    if tot > 0:
                        ent = -sum((p / tot) * math.log(p / tot) for p in ps)
                        b["mix_entropy"].append(ent)
                pending_mix = None
            elif s.startswith("Policy ") and "avg_score=" in s:
                try:
                    sc = float(s.split("avg_score=")[1].split()[0])
                    b.setdefault("_cur_scores", []).append(sc)
                except ValueError:
                    pass
            elif s.startswith("Sampling ") and "battles at" in s and "ms each" in s:
                m2 = re.search(r"Sampling (\d+) battles at (\d+)ms each", s)
                if m2:
                    b["sampling_lines"][(int(m2.group(1)), int(m2.group(2)))] += 1
                if b.get("_cur_scores"):
                    b["avg_scores"].append(
                        (b["turns"], sum(b["_cur_scores"]) / len(b["_cur_scores"])))
                    b["_cur_scores"] = []
            elif re.match(r"\d+(\.\d+)?%: ", s):
                if pending_mix is None:
                    pending_mix = []
                pending_mix.append(float(s.split("%")[0]))
            continue
        if not (in_protocol and room and line.startswith("|")):
            continue
        b = battles[room]
        parts = line.split("|")
        tag = parts[1] if len(parts) > 1 else ""
        if tag == "player" and len(parts) > 3:
            b["players"][parts[2]] = parts[3]
        elif tag == "start":
            b["started"] = True
        elif tag == "turn":
            b["turns"] = int(parts[2])
            b["past_leads"] = True
            if b.get("_cur_scores"):
                b["avg_scores"].append(
                    (b["turns"] - 1, sum(b["_cur_scores"]) / len(b["_cur_scores"])))
                b["_cur_scores"] = []
        elif tag == "switch":
            sd = side_of(parts[2])
            if not b["past_leads"]:
                b["sw"][sd]["lead"] += 1
                b["leads"] += 1
            elif b["pending_faint"][sd] > 0:
                b["sw"][sd]["forced"] += 1
                b["pending_faint"][sd] -= 1
            else:
                b["sw"][sd]["voluntary"] += 1
                b["vol_switch_turns"][sd].append(b["turns"])
            mm = HP_RE.search(line)
            if mm:
                b["hp"][parts[2].split(":")[0] + "|" + parts[3].split(",")[0]] = (
                    int(mm.group(1)) / max(1, int(mm.group(2))))
        elif tag == "faint":
            sd = side_of(parts[2])
            b["pending_faint"][sd] += 1
            b["faints"][sd].append(b["turns"])
        elif tag == "cant":
            sd = side_of(parts[2])
            reason = parts[3] if len(parts) > 3 else "?"
            b["cant"][sd][reason] += 1
        elif tag == "-status":
            sd = side_of(parts[2])
            cond = parts[3] if len(parts) > 3 else "?"
            if cond in ("slp", "frz", "par") and b["first_status"] is None:
                b["first_status"] = ("p2" if sd == "p1" else "p1", cond, b["turns"])
        elif tag == "-damage":
            sd = side_of(parts[2])
            key = parts[2].split(":")[0] + "|" + parts[3].split(",")[0] if len(parts) > 3 else None
            mm = HP_RE.search(line)
            newfrac = None
            if mm:
                newfrac = int(mm.group(1)) / max(1, int(mm.group(2)))
            elif len(parts) > 3 and parts[3].startswith("0"):
                newfrac = 0.0
            if newfrac is not None:
                k = parts[2].split(":")[0]
                name = parts[2].split(": ", 1)[1] if ": " in parts[2] else "?"
                key = k + "|" + name
                old = b["hp"].get(key, 1.0)
                if newfrac < old:
                    b["dmg_frac"][b["turns"]][sd] += old - newfrac
                b["hp"][key] = newfrac
        elif tag == "-heal":
            mm = HP_RE.search(line)
            if mm and ": " in parts[2]:
                k = parts[2].split(":")[0]
                name = parts[2].split(": ", 1)[1]
                b["hp"][k + "|" + name] = int(mm.group(1)) / max(1, int(mm.group(2)))
        elif tag == "-crit":
            b["crit_against"][side_of(parts[2])] += 1
        elif tag == "-miss":
            b["miss_by"][side_of(parts[2])] += 1
        elif tag == "move":
            sd = side_of(parts[2])
            b["moves"][sd] += 1
            if len(parts) > 3 and parts[3].lower() in ("explosion", "self-destruct", "selfdestruct"):
                b["explosion"][sd] += 1
        elif tag == "request":
            if '"forceSwitch"' in line:
                b["fp_forced_requests"] += 1
        elif tag == "win":
            b["winner_user"] = parts[2]
    return battles, order


def binom_se(p, n):
    return math.sqrt(max(p * (1 - p), 1e-12) / n) if n else float("nan")


def summarize(arm, battles, order, fp_user):
    done = [battles[r] for r in order if battles[r]["winner_user"] is not None]
    dropped = len(order) - len(done)
    out = {"arm": arm, "battles_parsed": len(done), "rooms_dropped_no_win": dropped}
    if not done:
        return out
    # seat orientation per battle: which side is FP
    for b in done:
        fps = next((k for k, v in b["players"].items() if v.lower() == fp_user.lower()), None)
        b["_fp"], b["_us"] = fps, ("p2" if fps == "p1" else "p1")
        b["_we_won"] = b["winner_user"].lower() != fp_user.lower()
    n = len(done)
    wins = sum(b["_we_won"] for b in done)
    out["our_wins"] = wins
    out["our_win_rate"] = wins / n
    # decision denominators + switch rates (parse rules iii/iv)
    for who in ("us", "fp"):
        vol = forced = lead = turns = recharge = 0
        for b in done:
            sd = b["_" + who]
            vol += b["sw"][sd]["voluntary"]; forced += b["sw"][sd]["forced"]
            lead += b["sw"][sd]["lead"]; turns += b["turns"]
            recharge += b["cant"][sd].get("recharge", 0)
        den = turns - recharge
        out[f"sw_{who}"] = {"voluntary": vol, "forced": forced, "lead": lead,
                            "denominator": den, "rate": vol / den if den else None,
                            "rate_se": binom_se(vol / den, den) if den else None}
    # FP ground truth (rule iv)
    ch = sum(b["fp_choices"] for b in done)
    sw_ch = sum(b["fp_switch_choices"] for b in done)
    # Protocol |request| lines appear ONCE per forced event (the "x2" in the
    # review's corpus count came from DEBUG echo lines, which are not counted
    # here). Validation on FG: choices 7819 - forced 916 = 6903 = the exact
    # |turn| total, and switch_choices 1915 - 916 = 999 = the heuristic's
    # voluntary count TO THE UNIT.
    forced_req = sum(b["fp_forced_requests"] for b in done)
    den_t = ch - forced_req
    truth = (sw_ch - forced_req) / den_t if den_t > 0 else None
    out["sw_fp_truth"] = {"choices": ch, "switch_choices": sw_ch,
                          "forced_requests": forced_req, "rate": truth}
    heur = out["sw_fp"]["rate"]
    out["sw_fp_crossval"] = {
        "heuristic": heur, "truth": truth,
        "abs_diff": abs(heur - truth) if (heur is not None and truth is not None) else None,
        "pass_0.02": (abs(heur - truth) <= 0.02) if (heur is not None and truth is not None) else False}
    out["delta_sw"] = (out["sw_fp"]["rate"] - out["sw_us"]["rate"]
                       if out["sw_fp"]["rate"] is not None and out["sw_us"]["rate"] is not None else None)
    if out["delta_sw"] is not None:
        out["delta_sw_se"] = math.sqrt(out["sw_fp"]["rate_se"] ** 2 + out["sw_us"]["rate_se"] ** 2)
    # (c) length dist / sweep / mon differential
    lens = sorted(b["turns"] for b in done)
    out["mean_turns"] = sum(lens) / n
    t1, t2 = lens[n // 3], lens[2 * n // 3]
    losses = [b for b in done if not b["_we_won"]]
    out["faints_per_battle"] = sum(len(b["faints"]["p1"]) + len(b["faints"]["p2"]) for b in done) / n
    if losses:
        top = [b for b in losses if b["turns"] >= t2]
        out["p_cover"] = {"tercile_bounds": [t1, t2], "n_losses": len(losses),
                          "top_tercile_loss_share": len(top) / len(losses),
                          "se": binom_se(len(top) / len(losses), len(losses))}
        sweeps = 0
        for b in losses:
            f = sorted(b["faints"][b["_us"]])
            if len(f) >= 3 and f[-1] - f[-3] <= 5:
                sweeps += 1
        out["sweep_share"] = {"value": sweeps / len(losses),
                              "se": binom_se(sweeps / len(losses), len(losses))}
        ahead = 0
        for b in losses:
            if b["turns"] >= 20:
                ours = 6 - sum(1 for t in b["faints"][b["_us"]] if t < 20)
                theirs = 6 - sum(1 for t in b["faints"][b["_fp"]] if t < 20)
                if ours > theirs:
                    ahead += 1
        out["p_eval_ahead_t20_loss_share"] = {"value": ahead / len(losses),
                                              "se": binom_se(ahead / len(losses), len(losses)),
                                              "note": "losses shorter than 20 turns count in the denominator"}
    # (e) status ledger
    we_first = [b for b in done if b["first_status"] and b["first_status"][0] == b["_us"]]
    fp_first = [b for b in done if b["first_status"] and b["first_status"][0] == b["_fp"]]
    if we_first and fp_first:
        pw = sum(b["_we_won"] for b in we_first) / len(we_first)
        pf = sum(b["_we_won"] for b in fp_first) / len(fp_first)
        out["status_ledger"] = {
            "n_we_first": len(we_first), "n_fp_first": len(fp_first),
            "p_win_we_first": pw, "p_win_fp_first": pf, "swing": pw - pf,
            "swing_se": math.sqrt(binom_se(pw, len(we_first)) ** 2 + binom_se(pf, len(fp_first)) ** 2)}
    # (d) switch ledger: sign of next-turn damage exchange
    for who in ("us", "fp"):
        pos = neg = zero = 0
        for b in done:
            sd, od = b["_" + who], b["_" + ("fp" if who == "us" else "us")]
            for t in b["vol_switch_turns"][sd]:
                d = b["dmg_frac"].get(t + 1)
                if d is None:
                    zero += 1; continue
                x = d[od] - d[sd]   # damage FP side took minus ours -> paid for
                pos += x > 0.02; neg += x < -0.02; zero += abs(x) <= 0.02
        tot = pos + neg + zero
        out[f"switch_ledger_{who}"] = {"paid_for": pos, "punished": neg, "even_or_unknown": zero,
                                       "net_positive": pos > neg, "n": tot}
    # (h) hax, normalized by attacking exposure ~ damaging evidence
    hax = {}
    for who in ("us", "fp"):
        moves = sum(b["moves"][b["_" + who]] for b in done)
        crit = sum(b["crit_against"][b["_" + ("fp" if who == "us" else "us")]] for b in done)
        miss = sum(b["miss_by"][b["_" + who]] for b in done)
        hax[who] = {"moves": moves, "crits_dealt": crit, "misses": miss,
                    "crit_per_move": crit / moves if moves else None,
                    "miss_per_move": miss / moves if moves else None}
    out["hax"] = hax
    # (g) explosion + partial trap absence
    out["explosion"] = {who: sum(b["explosion"][b["_" + who]] for b in done) for who in ("us", "fp")}
    out["partial_trap"] = "ABSENT in corpus (rule vii: 0 Wrap/Bind/FireSpin/Clamp moves; request-side trapped not aggregated here)"
    # (f) avg_score losing turn over our losses
    lose_turns = []
    for b in losses if losses else []:
        crossed = None
        for t, s in b["avg_scores"]:
            if s > 0.5:
                if crossed is None:
                    crossed = t
            else:
                crossed = None
        if crossed is not None:
            lose_turns.append(crossed)
    if lose_turns:
        lose_turns.sort()
        out["fp_avgscore_losing_turn"] = {
            "n": len(lose_turns), "median": lose_turns[len(lose_turns) // 2],
            "p25": lose_turns[len(lose_turns) // 4], "p75": lose_turns[3 * len(lose_turns) // 4]}
    ents = [e for b in done for e in b["mix_entropy"]]
    if ents:
        out["fp_mix_entropy_mean"] = sum(ents) / len(ents)
    # G8-style realized budget summary
    samp = defaultdict(int)
    for b in done:
        for k, v in b["sampling_lines"].items():
            samp[k] += v
    out["realized_budget_lines"] = {f"{k[0]}x{k[1]}ms": v for k, v in sorted(samp.items())}
    out["total_turns"] = sum(b["turns"] for b in done)
    return out


FIXTURE = """DEBUG    Received message from websocket: >battle-gen1randombattle-1
|player|p1|fpuser|1|
|player|p2|ususer|1|
|start
|switch|p1a: Alpha|Alpha, L80|100/100
|switch|p2a: Beta|Beta, L80|200/200
|turn|1
DEBUG    Received message from websocket: >battle-gen1randombattle-1
|move|p1a: Alpha|Body Slam|p2a: Beta
|-damage|p2a: Beta|150/200
|move|p2a: Beta|Blizzard|p1a: Alpha
|-damage|p1a: Alpha|40/100
|turn|2
DEBUG    Received message from websocket: >battle-gen1randombattle-1
|switch|p2a: Gamma|Gamma, L80|300/300
|move|p1a: Alpha|Hyper Beam|p2a: Gamma
|-damage|p2a: Gamma|100/300
|-crit|p2a: Gamma
|turn|3
DEBUG    Received message from websocket: >battle-gen1randombattle-1
|cant|p1a: Alpha|recharge
|move|p2a: Gamma|Earthquake|p1a: Alpha
|-damage|p1a: Alpha|0 fnt
|faint|p1a: Alpha
|switch|p1a: Delta|Delta, L80|100/100
|turn|4
DEBUG    Received message from websocket: >battle-gen1randombattle-1
|move|p1a: Delta|Thunder Wave|p2a: Gamma
|-status|p2a: Gamma|par
|cant|p2a: Gamma|par
|turn|5
DEBUG    Received message from websocket: >battle-gen1randombattle-1
|move|p2a: Gamma|Surf|p1a: Delta
|-miss|p2a: Gamma|p1a: Delta
|move|p1a: Delta|Thunderbolt|p2a: Gamma
|-damage|p2a: Gamma|0 fnt
|faint|p2a: Gamma
|switch|p2a: Beta|Beta, L80|150/200
|turn|6
DEBUG    Received message from websocket: >battle-gen1randombattle-1
|win|ususer
"""


def selftest():
    battles, order = parse_stream(FIXTURE.splitlines(), {}, [])
    b = battles["battle-gen1randombattle-1"]
    assert b["players"] == {"p1": "fpuser", "p2": "ususer"}, b["players"]
    assert b["sw"]["p1"]["lead"] == 1 and b["sw"]["p2"]["lead"] == 1, b["sw"]
    assert b["sw"]["p1"]["forced"] == 1, "p1 faint->switch must be FORCED"
    assert b["sw"]["p2"]["forced"] == 1, "p2 faint->switch must be FORCED"
    assert b["sw"]["p2"]["voluntary"] == 1, "p2 turn-2 switch is VOLUNTARY"
    assert b["sw"]["p1"]["voluntary"] == 0
    assert b["cant"]["p1"].get("recharge") == 1
    assert b["cant"]["p2"].get("par") == 1
    assert b["turns"] == 6 and b["winner_user"] == "ususer"
    assert b["first_status"] == ("p1", "par", 4), b["first_status"]
    assert b["crit_against"]["p2"] == 1 and b["miss_by"]["p2"] == 1
    s = summarize("FIX", battles, order, "fpuser")
    assert s["our_wins"] == 1
    # us=p2: den = 6 turns - 0 recharge = 6; voluntary 1 -> rate 1/6
    assert abs(s["sw_us"]["rate"] - 1 / 6) < 1e-9, s["sw_us"]
    # fp=p1: den = 6 - 1 recharge = 5; voluntary 0
    assert s["sw_fp"]["rate"] == 0.0 and s["sw_fp"]["denominator"] == 5
    print("SELFTEST PASS: lead/forced/voluntary/cant/status/crit/miss/denominators all as pre-registered")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--out", default="results/ch4_r1_offsh/archaeology.json")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    selftest()  # the fixture ALWAYS runs before the corpus (rule vi)
    results = {}
    for arm, spec in TAPES.items():
        battles, order = {}, []
        for path in [spec["tape"], *spec["extra"]]:
            with open(path, errors="replace") as f:
                parse_stream(f, battles, order)
        results[arm] = summarize(arm, battles, order, FP_USERS[arm])
        print(f"{arm}: {results[arm]['battles_parsed']} battles, "
              f"delta_sw={results[arm].get('delta_sw')}, turns={results[arm].get('total_turns')}")
    # rule vi free cross-check: FG turn total = 250 x 27.612 = 6903
    fg_turns = results["FG"]["total_turns"]
    results["_crosscheck_fg_turns_6903"] = {"value": fg_turns, "pass": fg_turns == 6903}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(results, indent=2, default=str) + "\n")
    print(f"wrote {args.out}; FG turn cross-check: {results['_crosscheck_fg_turns_6903']}")


if __name__ == "__main__":
    main()
