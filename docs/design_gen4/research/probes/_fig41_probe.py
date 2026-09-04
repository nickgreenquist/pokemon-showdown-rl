# Reads _fig41.bmp (sips conversion of _wang_fig41_crop-29.png, a crop of Wang
# thesis Fig 4.1, p.29) and digitizes the dark smoothed validation-winrate curve.
import struct, numpy as np
d = open('_fig41.bmp','rb').read()
off, = struct.unpack_from('<I', d, 10)
w, h = struct.unpack_from('<ii', d, 18)
bpp, = struct.unpack_from('<H', d, 28)
print('w,h,bpp,off', w, h, bpp, off)
nb = bpp//8
row = ((w*nb + 3)//4)*4
flip = h > 0; H = abs(h)
a = np.frombuffer(d, dtype=np.uint8, count=row*H, offset=off).reshape(H, row)
a = a[:, :w*nb].reshape(H, w, nb)[:, :, :3][:, :, ::-1]  # BGR->RGB
if flip: a = a[::-1]
g = a.mean(axis=2)
H, W = g.shape
colg = ((g>165)&(g<230)).sum(axis=0)
rowg = ((g>165)&(g<230)).sum(axis=1)
print('vgrid cols:', [i for i in range(W) if colg[i] > 0.5*H])
print('hgrid rows:', [i for i in range(H) if rowg[i] > 0.5*W])
np.save('_fig41_gray.npy', g)
