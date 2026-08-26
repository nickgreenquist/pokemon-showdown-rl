import os, sys
os.environ.setdefault("POKEMON_RL_ENCODER_V2","1"); os.environ.setdefault("POKEMON_RL_ENCODER_IDS","1")
sys.path.insert(0,"scripts")
import numpy as np, torch, yaml
from rl.common.seeding import set_seed
from rl.envs.make import make_env
import rl.envs.showdown as sd
from eval_checkpoint import _load_showdown_agent
from rl.common.checkpoint import load_checkpoint
from rl.common.config import Config
from rl.common.masking import masked_logits

set_seed(4242); torch.set_num_threads(1)
prereg=yaml.safe_load(open("configs/eval/ladder_r1.yaml"))
ck=load_checkpoint(prereg["checkpoints"]["s62"]["path"])
agent=_load_showdown_agent(ck, Config(**ck["config"]))
MOVE0 = sd.GLOBAL_DIM + 6*sd.MON_DIM + sd.ACTIVE_DIM
env=make_env("Showdown-v0", 4242, env_kwargs={"opponent":"heuristics"})

n_fs=n_fs_live=n_move=0; flips=0; examples=[]
for b in range(12):
    obs,info=env.reset(); done=False
    while not done:
        mask=info["action_mask"]
        force = obs[3] > 0.5
        aliased = obs[5] > 0.5
        known=[float(obs[MOVE0+j*sd.MOVE_DIM]) for j in range(4)]
        legal_moves=[j for j in range(4) if mask[6+j]]
        if force:
            n_fs+=1
            if any(k>0.5 for k in known) and not aliased:
                n_fs_live+=1
                if len(examples)<3:
                    mult=[round(float(obs[MOVE0+j*sd.MOVE_DIM+4]),2) for j in range(4)]
                    examples.append((known,mult,list(mask.astype(int))))
                # counterfactual: zero the move blocks, does the choice change?
                o2=obs.copy(); o2[MOVE0:MOVE0+4*sd.MOVE_DIM]=0.0
                t=lambda v: torch.as_tensor(v,dtype=torch.float32).unsqueeze(0)
                mt=torch.as_tensor(mask,dtype=torch.bool)
                with torch.no_grad():
                    a1=int(masked_logits(agent.actor(t(obs)),mt).argmax(-1))
                    a2=int(masked_logits(agent.actor(t(o2)),mt).argmax(-1))
                if a1!=a2: flips+=1
        elif legal_moves: n_move+=1
        with torch.no_grad():
            a=int(masked_logits(agent.actor(torch.as_tensor(obs,dtype=torch.float32).unsqueeze(0)),
                                torch.as_tensor(mask,dtype=torch.bool)).argmax(-1))
        obs,r,term,trunc,info=env.step(a); done=term or trunc
env.close()
print(f"force-switch decisions          : {n_fs}")
print(f"  ...with LIVE-looking move blocks and vec[5]==0 : {n_fs_live}"
      f"  ({n_fs_live/max(n_fs,1):.0%})")
print(f"normal move decisions           : {n_move}")
print(f"force-switch share of decisions : {n_fs/max(n_fs+n_move,1):.1%}")
print(f"\nCOUNTERFACTUAL: zeroing the stale move blocks changes the replacement"
      f" choice in {flips}/{n_fs_live} cases ({flips/max(n_fs_live,1):.0%})")
for k,m,msk in examples:
    print(f"  example: known flags {k}  multipliers {m}")
    print(f"           mask {msk}  <- no move action legal, yet 4 blocks read live")
