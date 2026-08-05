"""Phase 2 continuous-track figure: PPO on three MuJoCo locomotion envs.

Plots the STOCHASTIC training return, not the deterministic re-eval, because
the published CleanRL anchor drawn alongside it is itself a training return —
one measure per axis. The de-biased greedy re-evals are the README's table,
kept off this figure on purpose: mixing the two on one axis is the mistake
that made the chunk-4 MinAtar comparison read wrong before the re-evals
corrected it.

Per-seed traces are drawn behind the mean in the same hue (same entity, so
same color) because on these envs the seed spread IS a finding — three seeds
cannot separate variants at HalfCheetah's spread, and a mean-only plot would
hide that.

Palette: categorical slot 1 from the dataviz reference palette, matching
make_ppo_figure.py; the anchor is a neutral rule rather than a second
categorical hue, since it is a reference value and not a series.
"""

import csv

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#dedcd6"
PPO_C = "#2a78d6"  # categorical slot 1

ENVS = [
    ("halfcheetah", "HalfCheetah-v5", 1442.64),
    ("hopper", "Hopper-v5", 2382.86),
    ("walker2d", "Walker2d-v5", 2287.95),
]
SEEDS = [0, 100, 200]
BIN = 50_000
EDGES = np.arange(0, 1_000_001, BIN)
CENTRES = (EDGES[:-1] + EDGES[1:]) / 2 / 1e6


def seed_curve(env: str, seed: int) -> np.ndarray:
    """Binned mean training return for one run, in raw env units."""
    steps, returns = [], []
    with open(f"runs/{env}_ppo_s{seed}/history.csv") as f:
        for row in csv.DictReader(f):
            if row.get("rollout/episode_return"):
                steps.append(int(row["_step"]))
                returns.append(float(row["rollout/episode_return"]))
    steps, returns = np.array(steps), np.array(returns)
    idx = np.digitize(steps, EDGES) - 1
    return np.array([
        returns[idx == b].mean() if (idx == b).any() else np.nan
        for b in range(len(CENTRES))
    ])


fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.6), facecolor=SURFACE, sharey=True)
for ax, (env, title, anchor) in zip(axes, ENVS):
    curves = np.array([seed_curve(env, s) for s in SEEDS])

    ax.axhline(anchor, color=INK2, lw=1.4, ls=(0, (5, 3)), zorder=2)
    # Label at the left, where every curve is still low, so it never sits on
    # top of the traces.
    ax.annotate(
        f"CleanRL {anchor:.0f}", xy=(0.02, anchor), xycoords=("axes fraction", "data"),
        xytext=(0, 5), textcoords="offset points", ha="left", va="bottom",
        fontsize=8, color=INK2,
    )
    for row in curves:  # per-seed spread, same hue: one entity
        ax.plot(CENTRES, row, color=PPO_C, lw=1.0, alpha=0.35, zorder=3)
    ax.plot(CENTRES, curves.mean(axis=0), color=PPO_C, lw=2.0, zorder=4)

    ax.set_title(title, fontsize=10.5, color=INK, pad=8)
    ax.set_xlabel("environment steps (M)", fontsize=9, color=INK2)
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5)
    ax.set_xlim(0, 1.0)

axes[0].set_ylabel("training return", fontsize=9, color=INK2)
axes[0].set_ylim(-400, 4700)
# One legend for the whole figure: two things are drawn, so identity is never
# carried by color alone.
axes[0].plot([], [], color=PPO_C, lw=2.0, label="ours (mean of 3 seeds)")
axes[0].plot([], [], color=PPO_C, lw=1.0, alpha=0.35, label="individual seeds")
axes[0].plot([], [], color=INK2, lw=1.4, ls=(0, (5, 3)), label="CleanRL anchor (v4)")
axes[0].legend(
    loc="lower right", fontsize=8, frameon=False, labelcolor=INK2, handlelength=2.2
)

fig.suptitle(
    "PPO on MuJoCo locomotion — 1M steps, 3 seeds, stochastic training return",
    fontsize=11.5, color=INK, y=1.02,
)
fig.tight_layout()
fig.savefig("assets/mujoco_ppo_campaign.png", dpi=200, bbox_inches="tight",
            facecolor=SURFACE)
print("wrote assets/mujoco_ppo_campaign.png")
