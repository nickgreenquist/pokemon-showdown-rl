"""Derive a monster config at a different horizon, preserving everything else.

`rl.train` has no --total-steps flag, so the horizon lives in the config. Two
keys have to move together and only one of them is obvious: `total_steps` and
`agent.lr_anneal_steps`. The base config calls the second one "THE ANNEAL
TRAP" in its own comment, because a run whose anneal is shorter than its
horizon trains its entire tail at a learning rate of ~0 and nothing says so
until the readout.

This writes a NEW committed config rather than mutating the base or letting a
launcher patch YAML in memory: the pre-registered artifact is the file, and a
run whose config was generated on the fly is a run nobody can audit.

    python scripts/derive_monster_config.py configs/showdown_monster100m.yaml 200000000
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    src, steps = Path(sys.argv[1]), int(sys.argv[2])
    text = src.read_text()

    old = re.search(r"^total_steps:\s*(\d+)", text, re.M)
    if not old:
        print(f"no total_steps in {src}")
        return 2
    old_steps = int(old.group(1))
    m = steps // 1_000_000
    dst = src.with_name(re.sub(r"\d+m", f"{m}m", src.stem, count=1) + src.suffix)
    if dst == src:
        dst = src.with_name(f"{src.stem}_{m}m{src.suffix}")

    text = re.sub(r"^total_steps:\s*\d+", f"total_steps: {steps}", text, count=1,
                  flags=re.M)
    n_anneal = len(re.findall(r"^(\s*)lr_anneal_steps:\s*\d+", text, re.M))
    text = re.sub(r"^(\s*)lr_anneal_steps:\s*\d+",
                  rf"\g<1>lr_anneal_steps: {steps}", text, flags=re.M)
    if n_anneal != 1:
        print(f"expected exactly 1 lr_anneal_steps, found {n_anneal}")
        return 2
    text = re.sub(r"^(run_name:\s*\S*?)(\d+)m(_\S*)", rf"\g<1>{m}m\g<3>", text,
                  count=1, flags=re.M)

    header = (
        f"# DERIVED from {src.name} by scripts/derive_monster_config.py:\n"
        f"# total_steps {old_steps} -> {steps}, and agent.lr_anneal_steps moved\n"
        f"# WITH it. Those two must be equal -- the base config names the\n"
        f"# mismatch THE ANNEAL TRAP, because a horizon longer than the anneal\n"
        f"# trains its whole tail at lr~0 and nothing reports it. Everything\n"
        f"# else, including k=8 and the collector mode, is unchanged.\n#\n"
    )
    dst.write_text(header + text)
    print(f"wrote {dst}  (total_steps = lr_anneal_steps = {steps})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
