#!/usr/bin/env python
"""Pin a monster trio's FINAL checkpoints into the two monster_reads pre-regs.

    python scripts/monster_reads_pin.py --trio l      # l128 l136 l144  (monster_reads*.yaml)
    python scripts/monster_reads_pin.py --trio w      # w104 w112 w120  (monster_reads*.yaml)
    python scripts/monster_reads_pin.py --trio a      # a304 a312 a320  (r6_reads*.yaml, 2026-09-21)
    python scripts/monster_reads_pin.py --trio b      # b328 b336 b344  (r6_reads*.yaml)

For each lane: refuse unless (a) runs/train_watchdog.log carries the lane's
"DONE at step" line, (b) no `rl.train` process for that run dir is alive,
(c) the run dir holds a checkpoint at step >= 200,000,000 (the horizon; lanes
finish at DIFFERENT steps, so the name is READ, never guessed). Then rewrite
the placeholder line `  <lane>: {path: TBD, sha256: TBD, step: TBD}` in BOTH
configs/eval/monster_reads.yaml and configs/eval/monster_reads_offfp.yaml as a
TEXT substitution (a YAML round-trip would destroy the pre-reg's comments),
leaving every other byte untouched. Idempotent: an already-pinned lane is
verified against disk and left alone. Prints the pins; `--commit` commits
the two files with a fixed message (the queue runs it that way).
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIOS = {
    "l": [("l128", "runs/showdown_monster200m_l2lam_s128"),
          ("l136", "runs/showdown_monster200m_l2lam_s136"),
          ("l144", "runs/showdown_monster200m_l2lam_s144")],
    "w": [("w104", "runs/showdown_monster200m_w_s104"),
          ("w112", "runs/showdown_monster200m_w_s112"),
          ("w120", "runs/showdown_monster200m_w_s120")],
    # R6 (2026-09-21): the two R6 trios, pinned into the r6_reads pre-regs.
    "a": [("a304", "runs/showdown_r6_trio_a_s304"),
          ("a312", "runs/showdown_r6_trio_a_s312"),
          ("a320", "runs/showdown_r6_trio_a_s320")],
    "b": [("b328", "runs/showdown_r6_trio_b_s328"),
          ("b336", "runs/showdown_r6_trio_b_s336"),
          ("b344", "runs/showdown_r6_trio_b_s344")],
}
MONSTER_CONFIGS = ["configs/eval/monster_reads.yaml", "configs/eval/monster_reads_offfp.yaml"]
R6_CONFIGS = ["configs/eval/r6_reads.yaml", "configs/eval/r6_reads_offfp.yaml"]
CONFIGS_BY_TRIO = {"l": MONSTER_CONFIGS, "w": MONSTER_CONFIGS, "a": R6_CONFIGS, "b": R6_CONFIGS}
HORIZON = 200_000_000
WATCHDOG_LOG = "runs/train_watchdog.log"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def final_ckpt(run_dir):
    best = None
    for name in os.listdir(run_dir):
        m = re.fullmatch(r"ckpt_(\d+)\.pt", name)
        if m and int(m.group(1)) >= HORIZON:
            step = int(m.group(1))
            if best is None or step > best[0]:
                best = (step, os.path.join(run_dir, name))
    return best


def lane_done(run_dir):
    with open(WATCHDOG_LOG) as f:
        return any(f"{run_dir} DONE at step" in line for line in f)


def lane_alive(run_dir):
    # rl.train's argv carries `--run-name <basename>`, not the `runs/` path
    # (2026-09-15: the path pattern matched nothing; the DONE-line check was
    # the binding guard). Anchor on the run name.
    name = os.path.basename(run_dir.rstrip("/"))
    out = subprocess.run(["pgrep", "-f", f"bin/python -m rl.train.*--run-name {name}$"],
                         capture_output=True, text=True).stdout.split()
    return bool(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trio", choices=sorted(TRIOS), required=True)
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--allow-alive", action="store_true",
                    help="testing only: skip the alive/DONE checks (never for a real pin)")
    args = ap.parse_args()
    os.chdir(REPO)

    pins = {}
    for lane, run_dir in TRIOS[args.trio]:
        if not args.allow_alive:
            if not lane_done(run_dir):
                sys.exit(f"REFUSE: {run_dir} has no 'DONE at step' line in {WATCHDOG_LOG}")
            if lane_alive(run_dir):
                sys.exit(f"REFUSE: an rl.train process for {run_dir} is still alive")
        best = final_ckpt(run_dir)
        if best is None:
            sys.exit(f"REFUSE: {run_dir} has no ckpt at step >= {HORIZON}")
        step, path = best
        pins[lane] = (path, sha256(path), step)
        print(f"{lane}: {path} step={step} sha256={pins[lane][1]}")

    configs = CONFIGS_BY_TRIO[args.trio]
    for cfg in configs:
        text = open(cfg).read()
        for lane, (path, sha, step) in pins.items():
            placeholder = re.compile(rf"^(  {lane}: )\{{path: TBD, sha256: TBD, step: TBD\}}", re.M)
            pinned = re.compile(rf"^  {lane}: \{{path: (\S+), sha256: ([0-9a-f]{{64}}), step: (\d+)\}}", re.M)
            if placeholder.search(text):
                text, n = placeholder.subn(rf"\g<1>{{path: {path}, sha256: {sha}, step: {step}}}", text)
                assert n == 1, (cfg, lane, n)
            else:
                m = pinned.search(text)
                if not m:
                    sys.exit(f"REFUSE: {cfg} has neither a placeholder nor a pin for {lane}")
                if (m.group(1), m.group(2), int(m.group(3))) != (path, sha, step):
                    sys.exit(f"REFUSE: {cfg} already pins {lane} to something else: {m.group(0)}")
                print(f"{cfg}: {lane} already pinned, verified")
        open(cfg, "w").write(text)

    if args.commit:
        subprocess.run(["git", "add", *configs], check=True)
        family = "R6 reads" if args.trio in ("a", "b") else "monster reads"
        msg = (f"{family}: pin the {args.trio.upper()} trio finals (sha256, real step names)\n\n"
               "Mechanical pin by scripts/monster_reads_pin.py at the moment the trio's\n"
               "watchdog printed DONE for all three lanes; no other byte of either\n"
               "pre-reg changed.\n\n"
               "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n"
               "Claude-Session: https://claude.ai/code/session_015BnxVk5jpuc9MZ9pzCEqeS")
        r = subprocess.run(["git", "commit", "-q", "-m", msg], capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip() or "committed")


if __name__ == "__main__":
    main()
