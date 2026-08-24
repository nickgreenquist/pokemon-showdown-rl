"""CH3 R5b B-5/B-10 stamper: transcribe fit-time facts into the pre-reg,
AFTER the fits, BEFORE any Stage-2 battle.

    python scripts/ch3_r5b_stamp.py --prereg configs/eval/ch3_r5b_exit.yaml

What it stamps (the r4_13_discrimination precedent — transcription into
the registered header pre-launch, then commit, so the launch sha carries
everything):

* the EIGHT fit-time pin sha256s (d62..d65, p62..p65) into `checkpoints:`,
  cross-checked against the values the distiller/placebo transcripts
  recorded at save time — a mismatch means the checkpoint moved after its
  transcript was written and the stamp REFUSES;
* d65's sha into configs/eval/ch3_r5b_fp_anchor.yaml (the FA derived
  config — ch3_fp_h2h sha-asserts the pins it loads);
* `temperature_grid_transcript`: per-lane chosen tau + the full grid;
* `placebo_dose_search_transcript`: per-lane selected step + dose verdict;
* `a0_selfplay_measured`: per-lane GATE-split a0 + the r5a cross-check;
* `b7_fg4_transcript`: the F-P2 static grep transcript (no data/fp_* path
  in the recorder or distiller sources; live FG-4 is driver-automatic).

Edits are literal string replacements on the yaml TEXT (the pre-reg is a
comment-bearing document; a yaml round-trip would destroy it). Each
replacement asserts uniqueness. Run once; a second run is a no-op error
because the placeholders are gone — that is intentional.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ch3_eval import _sha256  # noqa: E402
from ch3_r5b_collect import LANES, assert_t_gate_pass  # noqa: E402
from ch3_r5b_distill import FIT_DIR  # noqa: E402
from ch3_r5b_gates import GATES_DIR  # noqa: E402

FP_ANCHOR = "configs/eval/ch3_r5b_fp_anchor.yaml"
PLACEHOLDER = "<filled at fit time, before any battle>"


def static_grep_transcript() -> str:
    """F-P2: no data/fp_* path in the recorder or distiller sources."""
    sources = ["scripts/ch3_r5b_collect.py", "scripts/ch3_r5b_distill.py",
               "scripts/ch3_r5b_placebo.py"]
    r = subprocess.run(["grep", "-n", "data/fp", *sources],
                       capture_output=True, text=True)
    assert r.returncode == 1 and not r.stdout, (
        f"F-P2 FAIL: data/fp_* reference in recorder/distiller sources:\n{r.stdout}"
    )
    return f"grep -n 'data/fp' {' '.join(sources)} -> no matches (exit 1)"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--prereg", default="configs/eval/ch3_r5b_exit.yaml")
    args = parser.parse_args()
    assert_t_gate_pass()
    prereg_path = Path(args.prereg)
    text = prereg_path.read_text()
    prereg = yaml.safe_load(text)

    tau_grid, placebo, a0 = {}, {}, {}
    stamps = {}
    for lane in LANES:
        t = json.loads((Path(FIT_DIR) / f"{lane}_tau_grid.json").read_text())
        p = json.loads((Path(FIT_DIR) / f"{lane}_placebo.json").read_text())
        g = json.loads((Path(GATES_DIR) / f"{lane}_gates.json").read_text())
        assert not t["smoke"] and not p["smoke"] and not g["smoke"]
        dname = prereg["lane_map"][lane]
        pname = prereg["placebo_map"][lane]
        for name, transcript_sha, path_key in (
                (dname, t["distilled_sha256"], t["distilled_path"]),
                (pname, p["placebo_sha256"], p["placebo_path"])):
            pin_path = prereg["checkpoints"][name]["path"]
            assert path_key == pin_path, f"{name}: transcript path {path_key}"
            live = _sha256(pin_path)
            assert live == transcript_sha, (
                f"{name}: {pin_path} sha {live} != transcript "
                f"{transcript_sha} — the checkpoint moved after its "
                "transcript was written; REFUSING to stamp"
            )
            stamps[name] = live
        tau_grid[lane] = {"chosen_tau": t["chosen_tau"], "grid": t["grid"]}
        placebo[lane] = {"selected_step": p["selected_step"],
                         "dose_matched": p["dose_matched"],
                         "dropped_frac": p["pairing"]["dropped_frac"]}
        a0[lane] = g["D-2"]["a0_selfplay"]
        xc = g["D-2"]["a0_r5a_flip_xcheck"]
        a0[f"{lane}_r5a_xcheck"] = xc

    def sub(old: str, new: str, where: str) -> None:
        nonlocal text
        assert text.count(old) == 1, f"stamp target not unique at {where}: {old[:80]!r}"
        text = text.replace(old, new)

    for name, sha in stamps.items():
        pin_path = prereg["checkpoints"][name]["path"]
        sub(f'{name}: {{path: {pin_path}, sha256: "{PLACEHOLDER}"}}',
            f"{name}: {{path: {pin_path}, sha256: {sha}}}", name)

    j = json.dumps  # compact one-line JSON keeps the yaml scalar simple
    sub('temperature_grid_transcript: "PENDING — written here before any battle (B-10)"',
        f"temperature_grid_transcript: {j(j(tau_grid))}", "tau grid")
    sub('placebo_dose_search_transcript: "PENDING — written here before any battle (B-10)"',
        f"placebo_dose_search_transcript: {j(j(placebo))}", "placebo")
    sub("a0_selfplay_measured: \"PENDING — read from the GATE split at collection time and cross-checked against ch3_r5a's recorded self-play flip rate (B-10)\"",
        f"a0_selfplay_measured: {j(j(a0))}", "a0")
    sub('b7_fg4_transcript: "PENDING — recorded before launch (B-7)"',
        f"b7_fg4_transcript: {j('F-P2 static: ' + static_grep_transcript() + '; live FG-4/SF-13 driver-automatic in every search job')}",
        "b7")
    prereg_path.write_text(text)
    assert yaml.safe_load(prereg_path.read_text()), "stamped yaml no longer parses"

    fp_text = Path(FP_ANCHOR).read_text()
    old = f'd65: {{path: runs/exit_s65/checkpoint.pt, sha256: "{PLACEHOLDER}"}}'
    assert fp_text.count(old) == 1, "FA config d65 placeholder missing"
    Path(FP_ANCHOR).write_text(fp_text.replace(
        old, f"d65: {{path: runs/exit_s65/checkpoint.pt, sha256: {stamps['d65']}}}"))

    print(f"stamped {len(stamps)} pins into {prereg_path} (+ d65 into {FP_ANCHOR})")
    print("taus:", {k: v["chosen_tau"] for k, v in tau_grid.items()})
    print("a0_selfplay:", {k: a0[k] for k in LANES})
    print("NEXT: commit both files — B-2 requires the stamped pre-reg at the launch sha")


if __name__ == "__main__":
    main()
