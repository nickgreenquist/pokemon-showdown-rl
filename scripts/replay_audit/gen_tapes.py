"""Generate replay tapes for each anchor so their PLAY STYLE can be profiled
the same way the human ladder field was."""
import os, sys, argparse
os.environ.setdefault("POKEMON_RL_ENCODER_V2","1"); os.environ.setdefault("POKEMON_RL_ENCODER_IDS","1")
sys.path.insert(0,"scripts")
import torch, yaml
from rl.common.seeding import set_seed
from rl.common.masking import masked_logits
from rl.envs.make import make_env
from eval_checkpoint import _load_showdown_agent, _opponent_from_checkpoint
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config

ap=argparse.ArgumentParser()
ap.add_argument("--opponent", required=True)
ap.add_argument("--battles", type=int, default=150)
ap.add_argument("--seed", type=int, required=True)
ap.add_argument("--outdir", required=True)
a=ap.parse_args()
set_seed(a.seed); torch.set_num_threads(1)
pre=yaml.safe_load(open("configs/eval/ladder_r1.yaml"))
ck=load_checkpoint(pre["checkpoints"]["s62"]["path"])
agent=_load_showdown_agent(ck, Config(**ck["config"]))
opp = _opponent_from_checkpoint(a.opponent, a.seed) if a.opponent.endswith(".pt") else a.opponent
env=make_env("Showdown-v0", a.seed,
             env_kwargs={"opponent": opp, "save_replays": a.outdir})
for b in range(a.battles):
    obs,info=env.reset(); done=False
    while not done:
        o=torch.as_tensor(obs,dtype=torch.float32).unsqueeze(0)
        m=torch.as_tensor(info["action_mask"],dtype=torch.bool)
        with torch.no_grad(): act=int(masked_logits(agent.actor(o),m).argmax(-1))
        obs,r,term,trunc,info=env.step(act); done=term or trunc
env.close()
import pathlib
print(f"{a.opponent}: {len(list(pathlib.Path(a.outdir).glob('*.html')))} replay files")
