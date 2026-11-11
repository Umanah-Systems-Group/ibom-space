"""Render the trained splat from the Blender reference cameras and along an orbit.

Run (inside the CUDA container, venv active):
  python splat_render.py --run splat/run --refs splat/refs --orbit 120
Writes <run>/compare/<Cam>.png (same camera, size and background as the Blender reference)
and <run>/orbit/frame_###.png.
"""
import argparse, json, math, os
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from gsplat import rasterization

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True); ap.add_argument("--refs", required=True)
ap.add_argument("--orbit", type=int, default=120)
args = ap.parse_args()
dev = "cuda"
P = {k: v.to(dev) for k, v in torch.load(os.path.join(args.run, "splat.pt")).items()}
sh_deg = int(round(math.sqrt(P["shN"].shape[1] + 1))) - 1
BG = torch.tensor([0.235, 0.235, 0.245], device=dev)
GL2CV = np.diag([1, -1, -1, 1]).astype(np.float32)

def render(c2w_gl, fl, cx, cy, W, H):
    vm = torch.from_numpy(np.linalg.inv(np.asarray(c2w_gl, np.float32) @ GL2CV)).to(dev)
    K = torch.tensor([[fl, 0, cx], [0, fl, cy], [0, 0, 1]], dtype=torch.float32, device=dev)
    with torch.no_grad():
        out, _, _ = rasterization(P["means"], F.normalize(P["quats"], dim=-1), torch.exp(P["scales"]),
                                  torch.sigmoid(P["opacities"]), torch.cat([P["sh0"], P["shN"]], 1),
                                  vm[None], K[None], W, H, sh_degree=sh_deg, backgrounds=BG[None])
    return (out[0].clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)

refs = json.load(open(os.path.join(args.refs, "refs.json")))
os.makedirs(os.path.join(args.run, "compare"), exist_ok=True)
for name, r in refs.items():
    Image.fromarray(render(r["c2w"], r["fl"], r["cx"], r["cy"], r["w"], r["h"])).save(os.path.join(args.run, "compare", name + ".png"))
    print("COMPARE", name, flush=True)

# orbit: 360 degrees around the bus centre, gently bobbing in elevation, 1280x720
os.makedirs(os.path.join(args.run, "orbit"), exist_ok=True)
W, H = 1280, 720
fl = 42 / 36 * W
center = np.array([0.0, 0.0, 0.52])
for k in range(args.orbit):
    az = 2 * math.pi * k / args.orbit - math.radians(40)
    el = math.radians(20 + 10 * math.sin(2 * math.pi * k / args.orbit))
    d = np.array([math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)])
    pos = center + d * 3.4
    fwd = -d; right = np.cross(fwd, [0, 0, 1]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
    c2w = np.eye(4); c2w[:3, 0] = right; c2w[:3, 1] = up; c2w[:3, 2] = -fwd; c2w[:3, 3] = pos
    Image.fromarray(render(c2w, fl, W / 2, H / 2, W, H)).save(os.path.join(args.run, "orbit", f"frame_{k:03d}.png"))
print("ORBIT_OK", args.orbit, flush=True)
