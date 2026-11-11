"""Convert a standard 3DGS .ply to Niantic's .spz (version 2, gzip) for web viewers such as Spark.

Run: python3 ply2spz.py in.ply out.spz [--sh 3]

Layout (all little-endian, whole stream gzipped):
  header: magic 'NGSP' (0x5053474e), version 2, numPoints u32, shDegree u8, fractionalBits u8, flags u8, reserved u8
  positions 24-bit signed fixed point (x,y,z) | alphas u8 | colours u8x3 | log-scales u8x3 |
  rotations u8x3 (x,y,z of the unit quaternion with w >= 0) | SH coefficients u8 (point, coefficient, rgb)
"""
import gzip, struct, sys
import numpy as np

src, dst = sys.argv[1], sys.argv[2]
sh_out = int(sys.argv[sys.argv.index("--sh") + 1]) if "--sh" in sys.argv else 3

with open(src, "rb") as f:
    names, n = [], 0
    while True:
        line = f.readline().decode().strip()
        if line.startswith("element vertex"):
            n = int(line.split()[-1])
        elif line.startswith("property float"):
            names.append(line.split()[-1])
        elif line == "end_header":
            break
    data = np.frombuffer(f.read(n * 4 * len(names)), dtype="<f4").reshape(n, len(names))
col = {k: data[:, i] for i, k in enumerate(names)}

xyz = np.stack([col["x"], col["y"], col["z"]], 1)
frac = 12
pos = np.round(xyz * (1 << frac)).astype(np.int32)
pos_b = np.stack([(pos >> s) & 0xFF for s in (0, 8, 16)], -1).astype(np.uint8).reshape(n, 9)

def u8(x):
    return np.clip(np.round(x), 0, 255).astype(np.uint8)

alpha = u8(255 / (1 + np.exp(-col["opacity"])))
dc = np.stack([col[f"f_dc_{i}"] for i in range(3)], 1)
colors = u8(dc * (0.15 * 255) + 0.5 * 255)
scales = u8((np.stack([col[f"scale_{i}"] for i in range(3)], 1) + 10) * 16)
q = np.stack([col[f"rot_{i}"] for i in range(4)], 1)          # (w, x, y, z)
q /= np.linalg.norm(q, axis=1, keepdims=True)
q *= np.where(q[:, :1] < 0, -1, 1)
rots = u8(q[:, 1:] * 127.5 + 127.5)

rest = [k for k in names if k.startswith("f_rest_")]
deg_in = {0: 0, 9: 1, 24: 2, 45: 3}[len(rest)]
sh_deg = min(sh_out, deg_in)
sh_bytes = b""
if sh_deg > 0:
    ncoef_in = (deg_in + 1) ** 2 - 1
    ncoef = (sh_deg + 1) ** 2 - 1
    R = np.stack([col[f"f_rest_{i}"] for i in range(len(rest))], 1).reshape(n, 3, ncoef_in)   # channel-major in .ply
    R = R[:, :, :ncoef].transpose(0, 2, 1)                                                      # -> (point, coef, rgb)
    qv = np.round(R * 128 + 128)
    bucket = np.full(ncoef, 16.0); bucket[:3] = 8.0                                             # 5 bits for degree 1, 4 for the rest
    qv = np.floor((qv + bucket[None, :, None] / 2) / bucket[None, :, None]) * bucket[None, :, None]
    sh_bytes = np.clip(qv, 0, 255).astype(np.uint8).tobytes()

hdr = struct.pack("<IIIBBBB", 0x5053474E, 2, n, sh_deg, frac, 0, 0)
raw = hdr + pos_b.tobytes() + alpha.tobytes() + colors.tobytes() + scales.tobytes() + rots.tobytes() + sh_bytes
with gzip.open(dst, "wb", compresslevel=9) as f:
    f.write(raw)
import os
print(f"SPZ_OK {dst} points={n} sh={sh_deg} {os.path.getsize(dst) / 1e6:.1f} MB")
