"""D22 read 4, stage 1 (DESIGN §12): collect self-play-distribution obs.

    POKEMON_RL_ENCODER_V2=1 POKEMON_RL_ENCODER_IDS=1 \
        python scripts/d22_collect_obs.py runs/<run>/checkpoint.pt \
        [--episodes 200] [--out results/d22/obs_sN.npz]

Mirror battles of a checkpoint against itself through the same-process
cross-play path (eval_checkpoint.py's --opponent-checkpoint seam): seat 1
deterministic, seat 2 the sampling pool member, per the h2h protocol. Seat 1's
obs (and masks) at every decision are saved — the activation probe's input
distribution is then the lane's own final-policy self-play, i.e. the
distribution training was seeing at the end. Needs the local server up.

D18 adaptation (scoped in configs/showdown_sp_priv12m.yaml, SECONDARY block):
when the checkpoint's config carries env_kwargs.privileged, the mirror env is
built with privileged=True and info["privileged"] (seat 2's own-side block,
408 dims) is saved alongside each obs as `priv` — the widened critic's probe
input is then obs ‖ priv, bit-identical to what training's value stack saw.
Non-privileged checkpoints are unaffected (no `priv` key, byte-compatible
output).

LANDMINE: this script derives Showdown usernames from the checkpoint's own
cfg.seed — running it against a lane whose training process is still alive
is the same-seed username collision (the loser dies at reset). Collect only
with the lane fleet down.
"""

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).parent))

from eval_checkpoint import _load_showdown_agent, _opponent_from_checkpoint  # noqa: E402

from rl.common.checkpoint import load_checkpoint  # noqa: E402
from rl.common.config import Config  # noqa: E402
from rl.common.evaluation import EVAL_SEED_OFFSET  # noqa: E402
from rl.envs.make import make_env  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("checkpoint")
    ap.add_argument("--episodes", type=int, default=200)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ckpt = load_checkpoint(args.checkpoint)
    cfg = Config(**ckpt["config"])
    assert cfg.env_id.startswith("Showdown")
    privileged = bool(cfg.env_kwargs.get("privileged"))
    opponent = _opponent_from_checkpoint(args.checkpoint, cfg.seed)
    env_kwargs = {"opponent": opponent}
    if privileged:
        env_kwargs["privileged"] = True
    env = make_env(cfg.env_id, cfg.seed, env_kwargs=env_kwargs)
    agent = _load_showdown_agent(ckpt, cfg)

    all_obs, all_masks, all_priv, outcomes = [], [], [], []
    for episode in range(args.episodes):
        obs, info = env.reset(seed=EVAL_SEED_OFFSET + cfg.eval_episodes + episode)
        mask = info.get("action_mask")
        priv = info.get("privileged")
        done, steps = False, 0
        while not done and steps < 10_000:
            all_obs.append(np.asarray(obs, dtype=np.float32))
            all_masks.append(np.asarray(mask, dtype=bool))
            if privileged:
                assert priv is not None, "privileged env emitted no block"
                all_priv.append(np.asarray(priv, dtype=np.float32))
            obs, _, terminated, truncated, info = env.step(
                agent.act(obs, mask, deterministic=True)
            )
            mask = info.get("action_mask")
            priv = info.get("privileged")
            steps += 1
            done = terminated or truncated
        outcomes.append(info.get("outcome") if done else 0)
        if (episode + 1) % 50 == 0:
            print(f"{episode + 1}/{args.episodes} episodes, {len(all_obs)} obs")
    env.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    arrays = dict(
        obs=np.stack(all_obs),
        masks=np.stack(all_masks),
        outcomes=np.asarray(outcomes, dtype=np.int8),
        checkpoint=str(args.checkpoint),
    )
    if privileged:
        arrays["priv"] = np.stack(all_priv)
    np.savez_compressed(out, **arrays)
    priv_note = f", priv x {arrays['priv'].shape[1]}" if privileged else ""
    print(f"wrote {out}: obs {len(all_obs)} x {all_obs[0].shape[0]}{priv_note}, "
          f"seat-1 win rate {np.mean(np.asarray(outcomes) == 1):.3f}")


if __name__ == "__main__":
    main()
