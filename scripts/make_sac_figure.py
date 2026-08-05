"""Phase 3 figure: SAC vs PPO on three MuJoCo locomotion envs, on two axes.

The top row is return against ENVIRONMENT STEPS and the bottom row is the same
return against WALL-CLOCK MINUTES. That pairing is the whole point of the
figure: SAC wins the first axis decisively and loses the second one just as
decisively, and neither panel alone is an honest summary of "which algorithm is
better". A table can carry the numbers; only this can carry the trade.

Not a dual-axis chart — that would be two y-scales on one plot, which is the
single worst thing you can do to a reader. This is small multiples: one y
quantity (training return), two different x quantities, shared y within each
column so the two views of an env are directly comparable.

STOCHASTIC training return on both rows, never the deterministic re-eval. Same
rule as the Phase 2 figure: one measure per axis. The de-biased greedy re-evals
and the published anchors live in the README table, where each can be labelled
with the protocol it was measured under — mixing protocols on a shared axis is
exactly the error that made the chunk-4 MinAtar comparison read wrong.

Three series, two hues. SAC takes categorical slot 2; both PPO arms keep slot 1
because they are the same algorithm under two environment stacks, and color
follows the entity — the raw arm is distinguished by dash, not by a third hue.
Per-seed traces sit behind each mean in the same hue, because at these spreads
the seed variance IS a finding (Hopper's SAC seeds differ by 1250).

Wall-clock caveat, stated on the figure itself: the arms ran at different
concurrency (9-wide for both PPO arms, 12-wide for SAC) on the same 14-core
machine, so the ratio is approximate. It is corroborated rather than confounded
— solo throughput measured 442 vs ~9,900 steps/s (22x), campaign wall-clock
gives 24x.
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
SAC_C = "#eb6834"  # categorical slot 2
PPO_C = "#2a78d6"  # categorical slot 1, as in make_continuous_figure.py

ENVS = [("halfcheetah", "HalfCheetah-v5"), ("hopper", "Hopper-v5"), ("walker2d", "Walker2d-v5")]
SEEDS = [0, 100, 200]
ARMS = [
    ("{env}_sac_s{seed}", "SAC", SAC_C, "-", 2.0),
    ("{env}_ppo_s{seed}", "PPO (normalized)", PPO_C, "-", 2.0),
    ("{env}_ppo_raw_s{seed}", "PPO (raw envs)", PPO_C, (0, (5, 2)), 1.6),
]
BIN = 50_000
EDGES = np.arange(0, 1_000_001, BIN)
CENTRES = (EDGES[:-1] + EDGES[1:]) / 2


def seed_curve(run: str) -> tuple[np.ndarray, np.ndarray]:
    """Binned mean training return and mean elapsed wall-clock, per step bin."""
    steps, returns, runtimes = [], [], []
    with open(f"runs/{run}/history.csv") as f:
        for row in csv.DictReader(f):
            if row.get("rollout/episode_return"):
                steps.append(int(float(row["_step"])))
                returns.append(float(row["rollout/episode_return"]))
                runtimes.append(float(row["_runtime"]) / 60.0)
    steps, returns, runtimes = np.array(steps), np.array(returns), np.array(runtimes)
    idx = np.digitize(steps, EDGES) - 1
    binned = np.array([
        returns[idx == b].mean() if (idx == b).any() else np.nan for b in range(len(CENTRES))
    ])
    clock = np.array([
        runtimes[idx == b].mean() if (idx == b).any() else np.nan for b in range(len(CENTRES))
    ])
    return binned, clock


fig, axes = plt.subplots(2, 3, figsize=(11.5, 6.6), facecolor=SURFACE)
for col, (env, title) in enumerate(ENVS):
    top, bottom = axes[0][col], axes[1][col]
    top.sharey(bottom)
    for pattern, _label, color, dash, width in ARMS:
        curves = np.array([seed_curve(pattern.format(env=env, seed=s))[0] for s in SEEDS])
        clocks = np.array([seed_curve(pattern.format(env=env, seed=s))[1] for s in SEEDS])
        mean_clock = np.nanmean(clocks, axis=0)
        for row in curves:  # same entity, same hue
            top.plot(CENTRES / 1e6, row, color=color, lw=0.9, ls=dash, alpha=0.3, zorder=3)
            bottom.plot(mean_clock, row, color=color, lw=0.9, ls=dash, alpha=0.3, zorder=3)
        top.plot(CENTRES / 1e6, np.nanmean(curves, axis=0), color=color, lw=width, ls=dash, zorder=4)
        bottom.plot(mean_clock, np.nanmean(curves, axis=0), color=color, lw=width, ls=dash, zorder=4)

    top.set_title(title, fontsize=10.5, color=INK, pad=8)
    top.set_xlabel("environment steps (M)", fontsize=9, color=INK2)
    bottom.set_xlabel("wall clock (min)", fontsize=9, color=INK2)
    bottom.set_xscale("log")
    for ax in (top, bottom):
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, lw=0.6, zorder=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK2, labelsize=8.5)

axes[0][0].set_ylabel("training return", fontsize=9, color=INK2)
axes[1][0].set_ylabel("training return", fontsize=9, color=INK2)

# Legend is always present at three series; identity is never carried by color
# alone (the two PPO arms share a hue and differ by dash).
for _p, label, color, dash, width in ARMS:
    axes[0][0].plot([], [], color=color, lw=width, ls=dash, label=label)
axes[0][0].legend(loc="lower right", fontsize=8, frameon=False, labelcolor=INK2, handlelength=2.4)

fig.suptitle(
    "SAC vs PPO on MuJoCo locomotion — 1M steps, 3 seeds, identical harness",
    fontsize=11.5, color=INK, y=0.985,
)
# The caption belongs at the top, not between the rows: placed mid-figure it
# lands on top of the first row's x-axis labels.
fig.text(
    0.5, 0.945,
    "top: return per environment step   ·   bottom: the same runs per wall-clock minute (log scale)",
    ha="center", fontsize=8.5, color=INK2, style="italic",
)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.subplots_adjust(hspace=0.34)
fig.savefig("assets/mujoco_sac_vs_ppo.png", dpi=200, bbox_inches="tight", facecolor=SURFACE)
print("wrote assets/mujoco_sac_vs_ppo.png")
