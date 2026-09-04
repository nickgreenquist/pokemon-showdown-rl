# Digitize Wang Fig 4.1 smoothed curve from _fig41_gray.npy (see _fig41_probe.py).
import numpy as np
g = np.load('_fig41_gray.npy')
x0, x20 = 270.5, 428.0          # px of 0 and 20M steps
y08, y06 = 200.0, 323.0         # px of winrate 0.8 and 0.6
px_per_M = (x20-x0)/20.0
def wr(ypx): return 0.8 + (y08-ypx)*(0.2/(y06-y08))
def col(step):
    c = int(round(x0 + step*px_per_M))
    band = g[80:695, c]
    idx = np.where(band < 150)[0]
    if len(idx)==0: return None
    return wr(80 + idx.mean()), wr(80+idx.min()), wr(80+idx.max())
for s in [1,2,3,4,5,6,7,8,10,12,15,20,30,40,50,60,80,100,120,140,148]:
    r = col(s)
    print(f'{s:>4}M  mean {r[0]:.3f}  hi {r[1]:.3f}  lo {r[2]:.3f}')
