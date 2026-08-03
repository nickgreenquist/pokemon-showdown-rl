"""Phase 5 milestone-3 figure: every training arm converges to ~0.4 vs
SimpleHeuristics, and a supervised clone through the same network sits above.

Left panel: eval/win_rate vs SimpleHeuristics over training — the three
fixed-bot [512,512] seeds (the lineage every other arm descends from or is
compared to; s1/s2 are the 2026-08-02 pre-registered replication) and the
three from-scratch self-play seeds, which never see the eval bot in
training. Rungs are 100-episode estimates (se ≈ 0.05), so each trace is a
5-rung (500k-step) centered rolling mean with the raw rungs behind it at low
alpha — smoothing disclosed here and in the README caption. The 0.5
milestone-2 bar and the ~0.42 extrapolated fixed-bot asymptote are reference
lines; the BC-clone band (0.453–0.465, the two batteries' pooled reads) is a
gray span because the clone is an instrument, not a training curve.

Right panel: the locked-protocol finals — final checkpoint, 1,000 fresh
battles per seed, deterministic, ties as non-wins — for every arm on the
board, with 95% binomial CIs. Rows carry identity (color never alone):
orange = the fixed-bot training lineage, blue = self-play arms, unfilled
ink = the supervised BC clone (context rows, same convention as the Phase 4
figure's lever rows).

Two hues only (the repo's categorical slots 1 and 2, validated: worst CVD
dE 24.7). One measure per axis: everything on both panels is win rate vs
SimpleHeuristics under the training-eval protocol (left) or the locked
1,000-battle protocol (right) — cross-play numbers stay in the README table
where each can be labelled with its own n and orientation convention.
"""

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#dedcd6"
SELFPLAY_C = "#2a78d6"  # categorical slot 1
FIXEDBOT_C = "#eb6834"  # categorical slot 2

BAR = 0.5
ASYMPTOTE = 0.42
CLONE_BAND = (0.453, 0.465)


def rungs(run: str) -> tuple[np.ndarray, np.ndarray]:
    steps, wins = [], []
    with open(f"runs/{run}/history.csv") as f:
        for row in csv.DictReader(f):
            if row.get("eval/win_rate"):
                steps.append(int(float(row["_step"])))
                wins.append(float(row["eval/win_rate"]))
    return np.array(steps), np.array(wins)


def rolling(y: np.ndarray, w: int = 5) -> np.ndarray:
    pad = w // 2
    padded = np.pad(y, pad, mode="edge")
    return np.convolve(padded, np.ones(w) / w, mode="valid")


def final(path: str) -> tuple[float, float, int]:
    """Pooled win rate, 95% CI half-width, n over one or more eval JSONs."""
    w = n = 0
    for p in path.split("+"):
        r = json.loads(Path(p).read_text())["returns"]
        w += sum(1 for x in r if x == 1)
        n += len(r)
    p_hat = w / n
    return p_hat, 1.96 * math.sqrt(p_hat * (1 - p_hat) / n), n


fig, (left, right) = plt.subplots(
    1, 2, figsize=(11.5, 4.6), facecolor=SURFACE, width_ratios=(1.35, 1)
)

# -- left: training curves -------------------------------------------------
left.axhline(BAR, color=INK2, lw=0.9, ls=(0, (5, 3)), zorder=2)
left.axhline(ASYMPTOTE, color=INK2, lw=0.8, ls=(0, (1, 2)), zorder=2)
left.axhspan(*CLONE_BAND, color="#b9b7b0", alpha=0.35, zorder=1)

for seed in (0, 1, 2):
    steps, wins = rungs(f"showdown_heur_512_s{seed}")
    left.plot(steps / 1e6, wins, color=FIXEDBOT_C, lw=0.7, alpha=0.22, zorder=3)
    left.plot(steps / 1e6, rolling(wins), color=FIXEDBOT_C, lw=1.5, alpha=0.9, zorder=5)
for seed in (0, 1, 2):
    steps, wins = rungs(f"showdown_scratch12m_s{seed}")
    left.plot(steps / 1e6, wins, color=SELFPLAY_C, lw=0.7, alpha=0.22, zorder=3)
    left.plot(steps / 1e6, rolling(wins), color=SELFPLAY_C, lw=1.4, alpha=0.9, zorder=4)

left.text(11.85, BAR + 0.012, "milestone-2 bar (0.5, set 2026-07-25, unmet)",
          ha="right", fontsize=8, color=INK2)
left.text(0.25, ASYMPTOTE - 0.005, "fixed-bot asymptote ~0.42 (extrapolated)",
          fontsize=8, color=INK2, va="top")
left.text(0.25, CLONE_BAND[1] + 0.012, "BC clone of the eval bot, same net (0.453–0.465)",
          fontsize=8, color=INK2)
left.text(3.1, 0.252, "trained vs the eval bot", fontsize=8.5, color=FIXEDBOT_C)
left.text(8.6, 0.215, "from-scratch self-play\n(never sees the eval bot)",
          fontsize=8.5, color=SELFPLAY_C)
left.set_xlim(0, 12.1)
left.set_ylim(0, 0.56)
left.set_xlabel("training step (M)", fontsize=9, color=INK2)
left.set_ylabel("win rate vs SimpleHeuristics (100-episode rungs)",
                fontsize=9, color=INK2)
left.set_title("training curves, 500k rolling mean over raw rungs",
               fontsize=10.5, color=INK, pad=8)

# -- right: locked-protocol finals ----------------------------------------
S3 = "runs/showdown_{a}_s0/{f}.json+runs/showdown_{a}_s1/{f}.json+runs/showdown_{a}_s2/{f}.json"
B3 = "runs/{a}_s0/p4_eval_heur_1000.json+runs/{a}_s1/p4_eval_heur_1000.json+runs/{a}_s2/p4_eval_heur_1000.json"
ROWS = [
    ("BC clone, 20k-battle battery", B3.format(a="bc_p4_512"), None),
    ("BC clone, 40k-battle battery", B3.format(a="bc_p4_512_40k"), None),
    ("fixed-bot + 6M continuation (18M)", S3.format(a="cont6m", f="final_eval_heur_1000"), FIXEDBOT_C),
    ("fixed-bot 12M  (3 seeds)", S3.format(a="heur_512", f="final_eval_heur_1000"), FIXEDBOT_C),
    ("warm-start + 6M self-play (18M)", S3.format(a="sp6m", f="final_eval_heur_1000"), SELFPLAY_C),
    ("from-scratch self-play 12M", S3.format(a="scratch12m", f="final_eval_heur_1000"), SELFPLAY_C),
    ("opponent mixture 6M", S3.format(a="mix512", f="final_eval_heur_1000"), FIXEDBOT_C),
]

right.axvline(BAR, color=INK2, lw=0.9, ls=(0, (5, 3)), zorder=2)
right.axvline(ASYMPTOTE, color=INK2, lw=0.8, ls=(0, (1, 2)), zorder=2)
for y, (label, paths, color) in enumerate(ROWS):
    p_hat, ci, n = final(paths)
    filled = color is not None
    right.errorbar(p_hat, -y, xerr=ci, color=color or INK2, elinewidth=1.2,
                   capsize=2.5, zorder=3, fmt="none")
    right.plot(p_hat, -y, "o", ms=7 if filled else 6, color=color or SURFACE,
               mec=color or INK2, mew=1.4, zorder=4)
right.set_yticks([-y for y in range(len(ROWS))])
right.set_yticklabels([label for label, _, _ in ROWS], fontsize=8.5)
right.set_xlim(0.30, 0.54)
right.text(BAR - 0.004, -6.45, "0.5 bar", ha="right", fontsize=8, color=INK2)
right.text(ASYMPTOTE + 0.004, -6.45, "~0.42", fontsize=8, color=INK2)
right.set_xlabel("final-checkpoint win rate vs SimpleHeuristics  (1,000 battles/seed, 95% CI)",
                 fontsize=9, color=INK2)
right.set_title("locked-protocol finals", fontsize=10.5, color=INK, pad=8)

for ax in (left, right):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5)
right.grid(axis="y", visible=False)

fig.suptitle(
    "Pokémon Showdown milestone 3: every training arm converges to ~0.4 vs SimpleHeuristics — "
    "a supervised clone through the same network sits above it",
    fontsize=11.5, color=INK, y=0.99,
)
fig.text(
    0.5, 0.925,
    "Gen 1 random battles; 611-dim observable-state encoder, [512,512] trunk; "
    "finals: final checkpoint, deterministic, ties as non-wins",
    ha="center", fontsize=8.5, color=INK2, style="italic",
)
fig.tight_layout(rect=(0, 0, 1, 0.89))
fig.savefig("assets/showdown_milestone3.png", dpi=200, bbox_inches="tight", facecolor=SURFACE)
print("wrote assets/showdown_milestone3.png")
