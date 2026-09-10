#!/usr/bin/env python
"""A-1a — DISTRIBUTIONAL ROW PARITY between the two collectors.

WHAT THIS IS FOR. Gate P-1 checks the engine's transitions against the server's
on scripted play; engine/pkmn_gen1/src/track.rs says in terms that this leaves
"the half of the port that gate P-1 deliberately does not test" — the rows the
collector actually hands the learner. A-1 covers that half only downstream, as
a win rate after 12M steps of training, which is a very long lever on a very
small signal. A-1a reads the rows themselves.

WHAT IT CANNOT DECIDE, AND THIS IS THE WHOLE POINT [RW-9]. The policy here is
FROZEN and nothing learns. That tests the collector's OUTPUT, not LEARNING. A
collector can emit rows drawn from exactly the right distribution and still
break learning through staleness, through the recorded-old_logp path, or
through GAE on unfinished episodes — none of which a frozen-policy comparison
touches. So A-1a BLOCKS IN ONE DIRECTION ONLY: failing it blocks the switch and
opens parity diagnosis; passing it licenses nothing on its own, and A-1 still
has to clear its band. Anything stronger would let a frozen-policy test stand in
for a learning test.

THE DESIGN PROBLEM, AND THE ANSWER. The two arms cannot produce the SAME rows —
different RNG, different team draws, different battle order — so "are these
identical" is the wrong question and any test sharp enough to answer it will
reject on n alone. At 50,000 rows a per-dimension KS test flags dimensions that
differ by nothing that matters.

So the null is MEASURED, not assumed, exactly as this project measures
eval-replicate noise rather than quoting the binomial. Collect FOUR arms — two
engine, two node — and read:

    A/A pairs (engine1, engine2) and (node1, node2)   -> what "same collector,
                                                         different seed" looks
                                                         like at this n
    A/B pairs (engine_i, node_j), all four            -> the thing under test

THE A/A BAND IS NOT A FORMALITY — MEASURED 2026-09-10. A 20-episode smoke of
two ENGINE arms against each other, i.e. a TRUE NULL, gave obs_smd_max 1.086,
412 of 828 dimensions over an SMD of 0.10, and episode_length_ks 0.174. Any
fixed threshold anyone would think to write down would have failed a perfectly
healthy collector at that n. The A/A pairs are what make the A/B numbers mean
anything, and they shrink with n while a real defect does not.

A statistic is interesting when the A/B pairs sit clearly outside the spread of
the A/A pairs. A statistic where they overlap is telling you the difference is
the same size as reseeding, which is the honest reading of "no evidence of a
parity defect at this n".

WHAT IS COMPARED, AND WHAT IS DESCRIPTIVE ONLY. Every array in EPISODE_KEYS
(rl/buffers/episode.py) plus episode length and the D25 opp_choice label —
EXCEPT `version`. Staleness DIFFERS BY CONSTRUCTION here (k against the async
path's concurrency), it is not a defect, and testing it would fail a healthy
port. It is reported as a descriptive row and never scored.

THE OPPONENT IS PINNED. Both arms self-play against a ONE-MEMBER SnapshotPool
holding the frozen checkpoint (pool_size 1, latest_prob 1.0), so the pool's
80/20 draw cannot contribute a difference. In a training run the pool is live;
here it must not be.

    python scripts/engine_a1a.py runs/<run>/ckpt_012000008.pt \\
        --episodes 2000 --team-bank data/engine/teams_a1_5000000.bin

A Showdown server must be up for the node arms; the engine arms need none.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import time

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Slots in the gen-1 10-way action space, and the terminal outcomes.
N_ACTIONS = 10
OUTCOMES = (-1.0, 0.0, 1.0)


class ArmStats:
    """Streaming sufficient statistics for one arm.

    Bounded memory on purpose: `obs` is 828 float32 per row and a 2,000-episode
    arm is ~110k rows, so holding four arms' raw observations would be most of
    a gigabyte for statistics that are all first- and second-moment anyway.
    Welford per dimension gives the moments exactly in one pass; the arrays we
    DO keep whole (old_logp, lengths) are one float per row or per episode and
    are kept because their SHAPE matters, not just their moments — a KS test on
    old_logp is the sharpest single read in this harness.
    """

    def __init__(self, name: str, obs_dim: int):
        self.name = name
        self.obs_dim = obs_dim
        self.n_rows = 0
        self.n_episodes = 0
        self._mean = np.zeros(obs_dim, dtype=np.float64)
        self._m2 = np.zeros(obs_dim, dtype=np.float64)
        self._nonzero = np.zeros(obs_dim, dtype=np.int64)
        self.act_hist = np.zeros(N_ACTIONS, dtype=np.int64)
        self.mask_legal = np.zeros(N_ACTIONS, dtype=np.int64)
        self.mask_width = []          # legal actions per row, as a histogram source
        self.outcome = {o: 0 for o in OUTCOMES}
        self.logp = []
        self.lengths = []
        self.version_span = []
        self.opp_choice_hists = None
        self.wall_seconds = 0.0

    def add(self, ep: dict) -> None:
        obs = np.asarray(ep["obs"], dtype=np.float64)
        n = obs.shape[0]
        self.n_rows += n
        self.n_episodes += 1
        # Chunked Welford: combine this episode's moments with the running ones.
        m = obs.mean(axis=0)
        d = m - self._mean
        tot = self.n_rows
        self._mean += d * (n / tot)
        self._m2 += obs.var(axis=0) * n + (d * d) * (n * (tot - n) / tot)
        self._nonzero += (obs != 0).sum(axis=0)

        acts = np.asarray(ep["actions"], dtype=np.int64)
        self.act_hist += np.bincount(acts, minlength=N_ACTIONS)[:N_ACTIONS]
        masks = np.asarray(ep["masks"], dtype=bool)
        self.mask_legal += masks.sum(axis=0)
        self.mask_width.append(masks.sum(axis=1))
        self.outcome[float(np.asarray(ep["rewards"])[-1])] += 1
        self.logp.append(np.asarray(ep["old_logp"], dtype=np.float64))
        self.lengths.append(n)
        v = np.asarray(ep["version"], dtype=np.int64)
        self.version_span.append(int(v.max() - v.min()))
        if "opp_choice" in ep:
            oc = np.asarray(ep["opp_choice"], dtype=np.int64)
            if self.opp_choice_hists is None:
                self.opp_choice_hists = [{} for _ in range(oc.shape[1])]
            for c in range(oc.shape[1]):
                vals, cnts = np.unique(oc[:, c], return_counts=True)
                for val, cnt in zip(vals.tolist(), cnts.tolist()):
                    self.opp_choice_hists[c][val] = \
                        self.opp_choice_hists[c].get(val, 0) + cnt

    # ---- derived reads ------------------------------------------------------
    @property
    def obs_mean(self) -> np.ndarray:
        return self._mean

    @property
    def obs_var(self) -> np.ndarray:
        return self._m2 / max(self.n_rows - 1, 1)

    def flat_logp(self) -> np.ndarray:
        return np.concatenate(self.logp) if self.logp else np.zeros(0)

    def flat_mask_width(self) -> np.ndarray:
        return np.concatenate(self.mask_width) if self.mask_width else np.zeros(0)

    def descriptive(self) -> dict:
        lp = self.flat_logp()
        return {
            "episodes": self.n_episodes,
            "rows": self.n_rows,
            "wall_seconds": round(self.wall_seconds, 1),
            "rows_per_sec": round(self.n_rows / self.wall_seconds, 1)
            if self.wall_seconds else None,
            "episode_length_mean": round(float(np.mean(self.lengths)), 3),
            "episode_length_sd": round(float(np.std(self.lengths, ddof=1)), 3),
            "outcome_fracs": {str(k): round(v / self.n_episodes, 5)
                              for k, v in self.outcome.items()},
            "old_logp_mean": round(float(lp.mean()), 5),
            "old_logp_sd": round(float(lp.std(ddof=1)), 5),
            "legal_actions_per_row_mean": round(float(self.flat_mask_width().mean()), 4),
            # DESCRIPTIVE ONLY — staleness differs by construction between the
            # two collectors and is never scored. See the module docstring.
            "version_span_within_episode_mean":
                round(float(np.mean(self.version_span)), 4),
        }


def _ks(a: np.ndarray, b: np.ndarray) -> float:
    """Two-sample KS statistic. Read against the A/A pairs, never against a
    p-value: at 100k rows every p-value is 0 and the statistic is the only
    part of the test that still carries information."""
    a = np.sort(a)
    b = np.sort(b)
    allv = np.concatenate([a, b])
    ca = np.searchsorted(a, allv, side="right") / a.size
    cb = np.searchsorted(b, allv, side="right") / b.size
    return float(np.max(np.abs(ca - cb)))


def _tv(pa: np.ndarray, pb: np.ndarray) -> float:
    """Total variation distance between two discrete distributions."""
    return float(0.5 * np.abs(pa - pb).sum())


def compare(a: ArmStats, b: ArmStats) -> dict:
    """Every statistic is a DISTANCE in [0, inf), so bigger is more different
    and the four A/B pairs can be read against the two A/A pairs directly."""
    va, vb = a.obs_var, b.obs_var
    pooled = np.sqrt(np.maximum((va + vb) / 2.0, 1e-12))
    smd = np.abs(a.obs_mean - b.obs_mean) / pooled
    # A dead dimension (constant in both arms) has no scale and its SMD is
    # meaningless; zero it rather than let 1e-12 manufacture a huge number.
    dead = (va < 1e-12) & (vb < 1e-12)
    smd[dead] = 0.0
    order = np.argsort(-smd)[:10]

    apa = a.act_hist / max(a.act_hist.sum(), 1)
    apb = b.act_hist / max(b.act_hist.sum(), 1)
    mla = a.mask_legal / max(a.n_rows, 1)
    mlb = b.mask_legal / max(b.n_rows, 1)
    oa = np.array([a.outcome[o] for o in OUTCOMES], dtype=float) / max(a.n_episodes, 1)
    ob = np.array([b.outcome[o] for o in OUTCOMES], dtype=float) / max(b.n_episodes, 1)

    out = {
        "pair": f"{a.name}|{b.name}",
        "obs_smd_max": round(float(smd.max()), 5),
        "obs_smd_mean": round(float(smd.mean()), 5),
        "obs_dims_smd_gt_0.10": int((smd > 0.10).sum()),
        "obs_worst_dims": [[int(j), round(float(smd[j]), 4)] for j in order],
        "obs_deadmask_disagree": int((((va < 1e-12) ^ (vb < 1e-12))).sum()),
        "action_tv": round(_tv(apa, apb), 5),
        "mask_legal_rate_max_abs": round(float(np.abs(mla - mlb).max()), 5),
        "mask_width_ks": round(_ks(a.flat_mask_width(), b.flat_mask_width()), 5),
        "old_logp_ks": round(_ks(a.flat_logp(), b.flat_logp()), 5),
        "old_logp_mean_abs_diff":
            round(abs(float(a.flat_logp().mean() - b.flat_logp().mean())), 5),
        "episode_length_ks": round(_ks(np.array(a.lengths, float),
                                       np.array(b.lengths, float)), 5),
        "outcome_tv": round(_tv(oa, ob), 5),
    }
    if a.opp_choice_hists and b.opp_choice_hists:
        tvs = []
        for ha, hb in zip(a.opp_choice_hists, b.opp_choice_hists):
            keys = sorted(set(ha) | set(hb))
            ta, tb = sum(ha.values()) or 1, sum(hb.values()) or 1
            pa = np.array([ha.get(k, 0) / ta for k in keys])
            pb = np.array([hb.get(k, 0) / tb for k in keys])
            tvs.append(round(_tv(pa, pb), 5))
        out["opp_choice_tv_per_column"] = tvs
    return out


# ---------------------------------------------------------------------------


def build_agent(ckpt_path: pathlib.Path):
    import torch

    from rl.common.config import Config
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from eval_checkpoint import _load_showdown_agent

    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = Config(**ckpt["config"]) if isinstance(ckpt["config"], dict) else ckpt["config"]
    agent = _load_showdown_agent(ckpt, cfg)
    agent.actor.eval()
    agent.critic.eval()
    return agent, cfg


def collect(mode: str, agent, *, episodes: int, seed: int, k: int,
            team_bank: str, opp_action: bool, run_tag: str,
            name: str) -> ArmStats:
    """Drive one collector to `episodes` finished episodes and summarise."""
    from rl.selfplay.pool import SnapshotPool

    # ONE member, always selected: the pool's 80/20 draw is a live-training
    # mechanism and would be a difference between arms that has nothing to do
    # with the collector under test.
    pool = SnapshotPool(pool_size=1, latest_prob=1.0)
    pool.push(agent)

    if mode == "engine":
        from rl.envs.engine_collector import EngineCollector
        collector = EngineCollector(agent.act_logp, pool, seed=seed, k=k,
                                    team_bank=team_bank, opp_action=opp_action)
    else:
        from rl.envs.showdown_async import AsyncCollector
        collector = AsyncCollector(agent.act_logp, pool, seed=seed,
                                   concurrency=k, opp_action=opp_action,
                                   run_tag=run_tag)

    obs_dim = None
    stats = None
    t0 = time.perf_counter()
    collector.start(episodes)
    try:
        while (stats is None) or (stats.n_episodes < episodes):
            done = collector.poll()
            if not done:
                collector.check()
                time.sleep(0.02)
                continue
            if stats is None:
                obs_dim = int(np.asarray(done[0]["obs"]).shape[1])
                stats = ArmStats(name, obs_dim)
            for ep in done:
                stats.add(ep)
            if stats.n_episodes % 250 < len(done):
                print(f"    {name}: {stats.n_episodes}/{episodes} episodes, "
                      f"{stats.n_rows:,} rows", flush=True)
    finally:
        collector.close()
    stats.wall_seconds = time.perf_counter() - t0
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("checkpoint", type=pathlib.Path)
    ap.add_argument("--episodes", type=int, default=2000,
                    help="finished episodes PER ARM; four arms are collected")
    ap.add_argument("--k", type=int, default=8,
                    help="engine k AND async concurrency — matched on purpose, "
                         "so concurrency is not a difference between the arms")
    ap.add_argument("--team-bank", default="data/engine/teams_a1_5000000.bin")
    ap.add_argument("--seeds", default="4101,4102,4103,4104",
                    help="engine1,engine2,node1,node2 — distinct, because "
                         "same-seed poke-env seats collide on usernames "
                         "(CLAUDE.md rule 2)")
    ap.add_argument("--no-opp-action", action="store_true")
    ap.add_argument("--smoke", action="store_true",
                    help="ENGINE ARMS ONLY — no server needed. Exercises every "
                         "path but AsyncCollector construction, and what it "
                         "produces is not a throwaway: two engine arms ARE the "
                         "A/A null calibration this harness reads against.")
    ap.add_argument("--out", type=pathlib.Path,
                    default=pathlib.Path("results/engine_a1/a1a.json"))
    args = ap.parse_args(argv)

    seeds = [int(s) for s in args.seeds.split(",")]
    if len(seeds) != 4 or len(set(seeds)) != 4:
        raise SystemExit("--seeds needs FOUR DISTINCT seeds (CLAUDE.md rule 2)")
    opp_action = not args.no_opp_action

    agent, cfg = build_agent(args.checkpoint)
    print(f"checkpoint {args.checkpoint} loaded; frozen, nothing learns here",
          flush=True)

    arms = {}
    plan = [("engine", "engine1", seeds[0]), ("engine", "engine2", seeds[1]),
            ("node", "node1", seeds[2]), ("node", "node2", seeds[3])]
    if args.smoke:
        plan = plan[:2]
    for mode, name, seed in plan:
        print(f"--- collecting {name} ({mode}, seed {seed})", flush=True)
        arms[name] = collect(mode, agent, episodes=args.episodes, seed=seed,
                             k=args.k, team_bank=args.team_bank,
                             opp_action=opp_action, run_tag=f"a1a{seed}",
                             name=name)

    aa = [compare(arms["engine1"], arms["engine2"])]
    if "node1" in arms:
        aa.append(compare(arms["node1"], arms["node2"]))
    ab = [compare(arms[e], arms[n])
          for e in ("engine1", "engine2") for n in ("node1", "node2")
          if n in arms]

    # THE READ. For every scalar statistic, how far outside the A/A spread do
    # the A/B pairs sit? No p-values: the null here is two numbers, so the
    # honest summary is the ratio and the raw values beside it.
    keys = [k for k, v in aa[0].items() if isinstance(v, (int, float))]
    read = {}
    for kk in [] if not ab else keys:
        aav = [p[kk] for p in aa]
        abv = [p[kk] for p in ab]
        worst_aa = max(aav)
        read[kk] = {
            "AA": aav, "AB": abv,
            "AB_max_over_AA_max": round(max(abv) / worst_aa, 3)
            if worst_aa > 0 else None,
            "separated": bool(min(abv) > worst_aa),
        }

    out = {
        "gate": "A-1a" + (" (SMOKE — engine A/A only, no node arms)"
                          if args.smoke else ""),
        "decides": "NOTHING ON ITS OWN [RW-9]. Failing blocks the switch and "
                   "opens parity diagnosis; passing licenses nothing, because "
                   "a FROZEN-policy row comparison cannot test LEARNING — "
                   "staleness, the recorded-old_logp path and GAE on "
                   "unfinished episodes all survive it untouched.",
        "ratified": False,
        "checkpoint": str(args.checkpoint),
        "episodes_per_arm": args.episodes,
        "k": args.k,
        "team_bank": args.team_bank,
        "seeds": seeds,
        "opponent": "one-member SnapshotPool holding the frozen checkpoint "
                    "(pool_size 1, latest_prob 1.0) — the live pool's 80/20 "
                    "draw is disabled so it cannot differ between arms",
        "arms": {n: s.descriptive() for n, s in arms.items()},
        "pairs_AA": aa,
        "pairs_AB": ab,
        "read": read,
        "not_scored": ["version — staleness differs BY CONSTRUCTION between k "
                       "and the async path's concurrency; scoring it would "
                       "fail a healthy port"],
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, indent=2) + "\n")

    if not ab:
        print("\nA-1a SMOKE — engine A/A only. These ARE the null band; "
              "there is nothing to read them against yet.")
        for kk, v in aa[0].items():
            if isinstance(v, (int, float)):
                print(f"  {kk:<28} {v}")
        print(f"\nwritten: {args.out}")
        return 0
    print("\nA-1a — every statistic is a DISTANCE; A/B is read against A/A")
    print(f"{'statistic':<28} {'A/A worst':>10} {'A/B worst':>10} {'ratio':>8}  separated")
    for kk, r in read.items():
        sep = "YES <-- look" if r["separated"] else "no"
        ratio = "n/a" if r["AB_max_over_AA_max"] is None else f"{r['AB_max_over_AA_max']:.2f}"
        print(f"{kk:<28} {max(r['AA']):>10.5f} {max(r['AB']):>10.5f} {ratio:>8}  {sep}")
    print(f"\nwritten: {args.out}")
    print("A-1a DECIDES NOTHING ON ITS OWN — see `decides` in the JSON.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
