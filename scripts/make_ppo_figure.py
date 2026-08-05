"""Phase 2 figure: PPO vs DQN on MinAtar — 5 training-return panels + the
de-biased re-eval headline as a dumbbell plot.

Palette slots 1/2 from the dataviz reference palette, validated: CVD dE 24.7,
normal-vision 33.6, both well clear of the floors.
"""

import glob
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#dedcd6"
PPO_C = "#2a78d6"   # categorical slot 1
DQN_C = "#eb6834"   # categorical slot 2

GAMES = [
    ("breakout", "Breakout", "nstep3", "n-step 3"),
    ("freeway", "Freeway", "rmsprop", "RMSprop"),
    ("asterix", "Asterix", "rmsprop_lr1e4", "RMSprop lr 1e-4"),
    ("seaquest", "Seaquest", "rmsprop", "RMSprop"),
    ("space_invaders", "Space Invaders", "rmsprop", "RMSprop"),
]
BIN = 100_000
EDGES = np.arange(0, 5_000_001, BIN)
CENTRES = (EDGES[:-1] + EDGES[1:]) / 2 / 1e6


def curve(pattern):
    """Per-seed binned mean training return -> (mean, std) across seeds."""
    per_seed = []
    for p in sorted(glob.glob(pattern)):
        df = pd.read_csv(p).dropna(subset=["rollout/episode_return"])
        idx = np.digitize(df["_step"].values, EDGES) - 1
        vals = df["rollout/episode_return"].values
        binned = np.full(len(EDGES) - 1, np.nan)
        for b in range(len(EDGES) - 1):
            m = idx == b
            if m.any():
                binned[b] = vals[m].mean()
        per_seed.append(binned)
    a = np.vstack(per_seed)
    return np.nanmean(a, axis=0), np.nanstd(a, axis=0)


def reeval(pattern):
    v = [json.load(open(p))["return_mean"] for p in sorted(glob.glob(pattern))]
    return float(np.mean(v))


fig, axes = plt.subplots(2, 3, figsize=(13.5, 7.4), dpi=150)
fig.patch.set_facecolor(SURFACE)

for ax, (slug, title, variant, vlabel) in zip(axes.flat, GAMES):
    ax.set_facecolor(SURFACE)
    pm, ps = curve(f"runs/minatar_{slug}_ppo_lr1e3_s*/history.csv")
    dm, ds = curve(f"runs/minatar_{slug}_dqn_{variant}_s*/history.csv")
    for m, s, c, lab in ((dm, ds, DQN_C, f"DQN ({vlabel})"), (pm, ps, PPO_C, "PPO")):
        ax.fill_between(CENTRES, m - s, m + s, color=c, alpha=0.16, linewidth=0)
        ax.plot(CENTRES, m, color=c, linewidth=2.0, label=lab, solid_capstyle="round")
    ax.set_title(title, color=INK, fontsize=12, fontweight="600", pad=8, loc="left")
    ax.grid(True, color=GRID, linewidth=0.7, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9, length=0)
    ax.set_xlim(0, 5)
    ax.set_ylim(bottom=0)
    # Per-panel legend: each names its own DQN variant, so identity is never
    # color-alone and the variant label stays next to the curve it describes.
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK2,
              handlelength=1.6, borderpad=0.2, labelspacing=0.25)

for ax in axes[1]:
    ax.set_xlabel("env steps (M)", color=INK2, fontsize=9.5)
for ax in (axes[0][0], axes[1][0]):
    ax.set_ylabel("training return", color=INK2, fontsize=9.5)

# --- panel 6: the actual headline, de-biased 100-episode greedy re-eval.
# Plotted as a ratio against parity: raw scores span 25..277 across games, and
# on Breakout/Freeway the two algorithms land close enough that any shared
# absolute axis hides the result. Bars run from 1.0, so length is the margin
# and the side is the winner. Colour still follows the entity: blue = PPO
# ahead, orange = DQN ahead.
ax = axes[1][2]
ax.set_facecolor(SURFACE)
rows = []
for slug, title, variant, _ in GAMES:
    rows.append((title,
                 reeval(f"runs/minatar_{slug}_ppo_lr1e3_s*/final_eval100.json"),
                 reeval(f"runs/minatar_{slug}_dqn_{variant}_s*/final_eval100.json")))
rows.reverse()
ys = np.arange(len(rows))
for y, (_, p, d) in zip(ys, rows):
    ratio = p / d
    ax.barh(y, ratio - 1.0, left=1.0, height=0.52,
            color=PPO_C if ratio >= 1 else DQN_C, zorder=2)
    # Labels always sit to the right of their anchor: a DQN-ahead bar runs
    # left toward the category names, so its label is placed just right of
    # parity instead, into empty space.
    anchor = ratio if ratio >= 1 else 1.0
    ax.annotate(f"{p:.1f} vs {d:.1f}", (anchor, y), textcoords="offset points",
                xytext=(8, 0), ha="left", va="center", color=INK2, fontsize=8.5)
ax.axvline(1.0, color=INK2, linewidth=1.2, zorder=3)
ax.set_yticks(ys, [r[0] for r in rows], color=INK2, fontsize=9.5)
ax.set_xlim(0.55, 3.75)
ax.set_xticks([1, 2, 3], ["parity", "2x", "3x"])
ax.set_ylim(-0.62, len(rows) - 0.15)
ax.set_title("De-biased re-eval (100 greedy episodes)", color=INK, fontsize=12,
             fontweight="600", pad=8, loc="left")
ax.set_xlabel("PPO score relative to DQN", color=INK2, fontsize=9.5)
ax.grid(True, axis="x", color=GRID, linewidth=0.7, alpha=0.9)
ax.set_axisbelow(True)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(colors=INK2, labelsize=9, length=0)
ax.annotate("PPO ahead →", (1.06, -0.5), color=PPO_C, fontsize=8.5,
            fontweight="600", va="center")
ax.annotate("← DQN", (0.94, -0.5), color=DQN_C, fontsize=8.5,
            fontweight="600", ha="right", va="center")

fig.suptitle("PPO vs DQN on MinAtar — 5M steps, 3 seeds, identical harness and conv trunk",
             color=INK, fontsize=13.5, fontweight="600", x=0.008, ha="left", y=0.985)
fig.text(0.008, 0.945,
         "Curves are training return (each algorithm's own exploration tax, so not comparable across algorithms); "
         "the re-eval panel is. Bands are ±1 std across seeds.",
         color=INK2, fontsize=9.5, ha="left")
fig.tight_layout(rect=[0, 0, 1, 0.925])
fig.savefig("assets/minatar_ppo_vs_dqn.png", facecolor=SURFACE, bbox_inches="tight")
print("wrote assets/minatar_ppo_vs_dqn.png")
for title, p, d in reversed(rows):
    print(f"  {title:16s} PPO {p:7.2f}   DQN {d:7.2f}")
