"""D26 pre-launch gates — R0-A, R0-C, R0-E acceptance, R0-F, R0-H, R0-J.

    python scripts/d26_gates.py                      # all gates
    python scripts/d26_gates.py --skip-smoke         # before the smoke exists

Every gate PRINTS its evidence and RAISES on failure; nothing is reported as
passing on the strength of a config value alone. R0-B lives in
tests/test_anneal_aux_group.py because it needs the encoder flags at import.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

ARM = REPO / "configs/showdown_sp_recipe12m.yaml"
SMOKE = REPO / "configs/showdown_sp_recipe12m_smoke.yaml"
D25 = REPO / "configs/showdown_sp_actpred12m.yaml"
SMOKE_RUN = REPO / "runs/showdown_sp_recipe12m_smoke_s99"
BASE_LR, ANNEAL, STEPS_PER_UPDATE = 2.5e-4, 12_000_000, 1024

# D25's banked finals — the comparator. NEVER re-scored (Q6).
D25_FINALS = {52: 0.6233, 53: 0.6573, 54: 0.6063, 55: 0.6073, 56: 0.5980}
D25_POOLED, D25_SD = 0.6184667, 0.0235815

_FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        _FAILURES.append(name)


def flat(d, p=""):
    out = {}
    for k, v in d.items():
        out.update(flat(v, f"{p}{k}.") if isinstance(v, dict) else {f"{p}{k}": v})
    return out


def r0a() -> None:
    """Mechanical one-diff proof: the arm differs from D25 in EXACTLY three keys."""
    print("\nR0-A  ONE-DIFF PROOF vs configs/showdown_sp_actpred12m.yaml")
    a, b = flat(yaml.safe_load(ARM.read_text())), flat(yaml.safe_load(D25.read_text()))
    diff = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    want = {"seed", "run_name", "agent.lr_anneal_steps"}
    for k in sorted(diff):
        print(f"      {k}: {b.get(k, '<absent>')} -> {a.get(k, '<absent>')}")
    check("R0-A arm", diff == want, f"{sorted(diff)} == {sorted(want)}")
    check("R0-A anneal value", a["agent.lr_anneal_steps"] == ANNEAL,
          f"lr_anneal_steps={a['agent.lr_anneal_steps']}")
    check("R0-A aux head still on", a["agent.aux_oppact_coef"] == 0.1,
          f"aux_oppact_coef={a['agent.aux_oppact_coef']}")
    check("R0-A lambda unchanged", a["agent.gae_lambda"] == 0.95,
          f"gae_lambda={a['agent.gae_lambda']} (bundle would be 1.0)")

    s = flat(yaml.safe_load(SMOKE.read_text()))
    sdiff = {k for k in set(s) | set(a) if s.get(k) != a.get(k)}
    swant = {"seed", "run_name", "total_steps", "eval_every", "checkpoint_every"}
    check("R0-A smoke", sdiff == swant, f"{sorted(sdiff)} == {sorted(swant)}")
    check("R0-A smoke anneals on the ARM's schedule",
          s["agent.lr_anneal_steps"] == ANNEAL, f"{s['agent.lr_anneal_steps']}")


def r0c_and_e() -> None:
    """R0-C: read the realised lr OUT OF THE OPTIMIZER, not the config.
    R0-E: the 100k smoke's acceptance band."""
    print("\nR0-C  REALISED LR, READ OFF THE CHECKPOINT")
    from rl.common.checkpoint import load_checkpoint

    cks = sorted(SMOKE_RUN.glob("ckpt_*.pt"))
    if not cks:
        check("R0-C", False, f"no checkpoint under {SMOKE_RUN}")
        return
    ck = load_checkpoint(str(cks[-1]))
    opt = ck["agent"]["optimizer"] if "agent" in ck else ck["optimizer"]
    groups = opt["param_groups"]
    updates = ck["agent"].get("updates") if "agent" in ck else ck.get("updates")
    # Q3's off-by-one: the lr was written from the PRE-increment counter.
    want = BASE_LR * max(0.0, 1.0 - (updates - 1) * STEPS_PER_UPDATE / ANNEAL)
    print(f"      {cks[-1].name}: updates={updates}, {len(groups)} param groups")
    check("R0-C three groups", len(groups) == 3, f"{len(groups)} (actor, critic, AUX)")
    for i, g in enumerate(groups):
        check(f"R0-C group {i} lr", abs(g["lr"] - want) <= 1e-12 * max(want, 1e-12),
              f"{g['lr']:.10e} vs expected {want:.10e}")
    print("\nR0-E  SMOKE ACCEPTANCE")
    check("R0-E lr is the 100k value", abs(want - 2.479520e-04) < 1e-9,
          f"{want:.6e} (must be 2.479520e-04, NOT Q3's 200k row 2.4586e-04)")

    hist = SMOKE_RUN / "history.csv"
    if hist.exists():
        import csv
        rows = list(csv.DictReader(hist.open()))
        def col(k):
            return [float(r[k]) for r in rows if r.get(k) not in (None, "")]
        for key, lo, hi in (("aux/illegal_label_frac", 0.0, 0.0),
                            ("aux/frame_collision_frac", 0.0, 0.0)):
            v = col(key)
            check(f"R0-E {key}", bool(v) and max(v) <= hi,
                  f"max {max(v) if v else 'n/a'} (must be {hi})")
        lf = col("aux/labelled_frac")
        if lf:
            m = float(np.mean(lf))
            check("R0-E aux/labelled_frac", 0.84 <= m <= 0.88,
                  f"mean {m:.4f} in the SMOKE-ERA band [0.84, 0.88]")
        for key in ("loss/policy", "loss/value", "loss/entropy"):
            v = col(key)
            check(f"R0-E {key} finite", bool(v) and np.isfinite(v).all(),
                  f"{len(v)} readings, all finite")


def r0f() -> None:
    """Fingerprint: the WRITTEN config snapshot, not the file on disk."""
    print("\nR0-F  LAUNCH FINGERPRINT (from the smoke's written config/meta)")
    cfg_p, meta_p = SMOKE_RUN / "config.yaml", SMOKE_RUN / "meta.yaml"
    if not cfg_p.exists():
        check("R0-F", False, f"no config.yaml under {SMOKE_RUN}")
        return
    c = flat(yaml.safe_load(cfg_p.read_text()))
    check("R0-F lr_anneal_steps stamped", c.get("agent.lr_anneal_steps") == ANNEAL,
          str(c.get("agent.lr_anneal_steps")))
    check("R0-F aux coef stamped", c.get("agent.aux_oppact_coef") == 0.1,
          str(c.get("agent.aux_oppact_coef")))
    check("R0-F privileged ABSENT", "agent.privileged_dim" not in c
          or not c.get("agent.privileged_dim"), "no privileged critic")
    check("R0-F purity seam", c.get("selfplay.opponent") == "self",
          f"selfplay.opponent={c.get('selfplay.opponent')}")
    if meta_p.exists():
        m = flat(yaml.safe_load(meta_p.read_text()))
        enc = {k: v for k, v in m.items() if "encoder" in k or "obs_dim" in k}
        check("R0-F encoder fingerprint", any("828" in str(v) for v in enc.values())
              or m.get("obs_dim") == 828, f"{enc or m.get('obs_dim')}")


def r0h() -> None:
    """Attestation: re-read D25's banked finals FROM DISK. Hard-stop on drift."""
    print("\nR0-H  COMPARATOR ATTESTATION (re-read from results/d25/)")
    got = {}
    for s, want in D25_FINALS.items():
        p = REPO / f"results/d25/final_s{s}.json"
        if not p.exists():
            check(f"R0-H s{s}", False, f"missing {p}")
            continue
        j = json.loads(p.read_text())
        # The locked key is env-supplied `eval/win_rate`, NEVER the sign of the
        # return (CLAUDE.md landmine); `wins_from_returns` is kept only as the
        # sign-bug cross-check and the two must agree.
        wr = j.get("eval/win_rate")
        got[s] = wr
        check(f"R0-H s{s}", abs(wr - want) < 5e-5, f"{wr} vs banked {want}")
        wfr = j.get("wins_from_returns")
        if wfr is not None:
            check(f"R0-H s{s} sign-guard", abs(wfr - wr) < 1e-9,
                  f"wins_from_returns {wfr} == eval/win_rate {wr}")
    if len(got) == 5:
        v = np.array(list(got.values()))
        check("R0-H pooled", abs(v.mean() - D25_POOLED) < 5e-5,
              f"{v.mean():.7f} vs {D25_POOLED}")
        check("R0-H sd", abs(v.std(ddof=1) - D25_SD) < 5e-5,
              f"{v.std(ddof=1):.7f} vs {D25_SD}")


def r0j() -> None:
    """Backup + the frozen artifacts that a lost directory would void."""
    print("\nR0-J  ARTIFACTS AND BACKUP")
    backup = REPO.parent / "pokemon-showdown-rl-d25-backup-20260815"
    for d in ("d25", "d25p", "d19_closeout", "c4_transfer"):
        check(f"R0-J results/{d}", (REPO / "results" / d).is_dir(), "present")
    check("R0-J backup dir", backup.is_dir(), str(backup))
    tape = REPO / "results/d25/oppact_s36ref.npz"
    if tape.exists():
        sha = hashlib.sha256(tape.read_bytes()).hexdigest()
        check("R0-J frozen s36 tape sha",
              sha.startswith("3ffee9ba8f0c8fd8"), sha[:32] + "...")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-smoke", action="store_true")
    args = ap.parse_args()
    print("D26 PRE-LAUNCH GATES  (R0-B is tests/test_anneal_aux_group.py)")
    r0a()
    if not args.skip_smoke:
        r0c_and_e()
        r0f()
    r0h()
    r0j()
    print("\n" + "=" * 62)
    if _FAILURES:
        print(f"BLOCKED — {len(_FAILURES)} gate(s) failed: {_FAILURES}")
        raise SystemExit(1)
    print("ALL GATES PASS — the arm may launch once the header is ratified.")


if __name__ == "__main__":
    main()
