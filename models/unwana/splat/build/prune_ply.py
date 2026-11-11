"""Drop near-transparent gaussians from a 3DGS .ply.  python prune_ply.py in.ply out.ply [min_opacity]"""
import sys
import numpy as np
src, dst = sys.argv[1], sys.argv[2]
thr = float(sys.argv[3]) if len(sys.argv) > 3 else 0.02
with open(src, 'rb') as f:
    hdr = b''
    while True:
        l = f.readline(); hdr += l
        if l.strip() == b'end_header':
            break
    names = [l.split()[-1].decode() for l in hdr.split(b'\n') if l.startswith(b'property')]
    n = int([l for l in hdr.split(b'\n') if l.startswith(b'element vertex')][0].split()[-1])
    d = np.frombuffer(f.read(), dtype='<f4').reshape(n, len(names))
keep = 1 / (1 + np.exp(-d[:, names.index('opacity')])) > thr
d = d[keep]
with open(dst, 'wb') as f:
    f.write(hdr.replace(b'element vertex %d' % n, b'element vertex %d' % len(d))); f.write(d.tobytes())
print('PRUNED', n, '->', len(d))
