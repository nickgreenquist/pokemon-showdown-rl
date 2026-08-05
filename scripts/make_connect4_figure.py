"""Phase 4 figure: the forgetting demonstration, both measures.

Left panel: tournament Elo of every checkpoint-ladder rung against its
training step — pool vs naive, all three seeds each, drawn per seed with
NO mean overlay because the seed traces are the finding: naive ladders
crater 200+ Elo mid-run and end below their own early rungs, while pool
ladders mostly climb. Every rating is from that run's own 500-games/pair
round-robin, anchored at alphabeta2 = 0 (the dashed reference line), so
curves are comparable across runs up to anchor noise (~±13 Elo CIs).

Right panel: the primary pre-registered measure — AlphaStar's min-winrate
proxy per run (Nature 2019 Fig. 3C/D; mean over rungs of each rung's
worst win rate against any earlier self). The demonstration is the
separation: every naive seed sits below every pool seed. The three
chunk-4 probe levers appear as unfilled context rows in ink, not a third
hue — they are context, and their identity is carried by row labels.

Two hues only (the repo's categorical slots 1 and 2, validated: worst
CVD dE 24.7); arms are also separated by panel-A direct labels and
panel-B rows, so identity never rides on color alone.
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#dedcd6"
POOL_C = "#2a78d6"  # categorical slot 1
NAIVE_C = "#eb6834"  # categorical slot 2

SEEDS = (0, 1, 2)
ARMS = (("connect4_pool", "pool (20 snapshots)", POOL_C),
        ("connect4_naive", "naive (pool of 1)", NAIVE_C))
LEVERS = (("connect4_pool_entropy", "entropy 0.05"),
          ("connect4_pool_pfsp", "PFSP p=2"),
          ("connect4_pool_mix", "5% fixed mix"))


def ladder(run: str) -> tuple[list[int], list[float]]:
    t = json.loads(Path(f"runs/{run}/tournament.json").read_text())
    rungs = sorted(
        (int(name[5:]), elo) for name, elo in t["ratings"].items()
        if name.startswith("ckpt_")
    )
    return [s for s, _ in rungs], [e for _, e in rungs]


def proxy(run: str) -> float:
    return json.loads(Path(f"runs/{run}/forgetting.json").read_text())["alphastar_proxy"]


fig, (pool_ax, naive_ax, right) = plt.subplots(
    1, 3, figsize=(11.5, 4.4), facecolor=SURFACE, width_ratios=(1, 1, 1.15)
)
naive_ax.sharey(pool_ax)

for ax, (prefix, label, color) in zip((pool_ax, naive_ax), ARMS):
    ax.axhline(0, color=INK2, lw=0.9, ls=(0, (5, 3)), zorder=2)
    for seed in SEEDS:
        steps, elos = ladder(f"{prefix}_s{seed}")
        ax.plot([s / 1e6 for s in steps], elos, color=color, lw=1.6,
                marker="o", ms=3, zorder=4, alpha=0.85)
    ax.set_xlabel("training step (M)", fontsize=9, color=INK2)
    # One entity per panel (3 seeds, one hue): the title IS the label,
    # no legend box needed.
    ax.set_title(label, fontsize=10.5, color=INK, pad=8)
pool_ax.text(1.95, 10, "alphabeta2 anchor", ha="right", fontsize=8, color=INK2)
pool_ax.set_ylabel("tournament Elo (500 games/pair)", fontsize=9, color=INK2)
naive_ax.tick_params(labelleft=False)

rows = [(f"{p}_s{s}", label if s == 1 else "", c)
        for p, label, c in ARMS for s in SEEDS]
lever_rows = [(f"{p}_s{s}", label if s == 1 else "", None)
              for p, label in LEVERS for s in SEEDS]
for y, (run, label, color) in enumerate(rows + lever_rows):
    value = proxy(run)
    filled = color is not None
    right.plot(value, -y, "o", ms=7 if filled else 6,
               color=color or SURFACE, mec=color or INK2, mew=1.4, zorder=4)
right.axvline(0.5, color=GRID, lw=0.8, zorder=1)
labels = [label for _, label, _ in rows + lever_rows]
right.set_yticks([-y for y in range(len(labels))])
right.set_yticklabels(labels, fontsize=8.5)
right.set_xlim(0.2, 0.68)
right.set_xlabel("AlphaStar min-winrate proxy  (higher = less forgetting)",
                 fontsize=9, color=INK2)
right.set_title("forgetting, primary measure", fontsize=10.5, color=INK, pad=8)

for ax in (pool_ax, naive_ax, right):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.6, zorder=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5)
right.grid(axis="y", visible=False)

fig.suptitle(
    "Connect 4 self-play: a 20-snapshot opponent pool prevents forgetting that naive self-play suffers",
    fontsize=11.5, color=INK, y=0.99,
)
fig.text(
    0.5, 0.935,
    "2M steps, 3 seeds/arm; every point from a 500-games/pair round-robin vs 4 fixed anchors (B=1000 bootstrap)",
    ha="center", fontsize=8.5, color=INK2, style="italic",
)
fig.tight_layout(rect=(0, 0, 1, 0.90))
fig.savefig("assets/connect4_forgetting.png", dpi=200, bbox_inches="tight", facecolor=SURFACE)
print("wrote assets/connect4_forgetting.png")
