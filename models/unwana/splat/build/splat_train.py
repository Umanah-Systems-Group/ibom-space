"""Train a 3D Gaussian Splatting model of Unwana with gsplat.

Run (inside the CUDA container, venv active):
  python splat_train.py --data splat/data --out splat/run [--steps 30000]

Input: transforms.json (Blender/OpenGL camera-to-world, Z-up), RGBA images, points3d.npz
(points sampled on the mesh surfaces with material colours, so no SfM step is needed).
Backgrounds are randomised every step so the splat learns a clean alpha.
"""
import argparse, json, math, os, time
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from gsplat import rasterization
from gsplat.strategy import DefaultStrategy
from torchmetrics.functional import structural_similarity_index_measure as ssim_fn

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--steps", type=int, default=30000); ap.add_argument("--sh", type=int, default=3)
ap.add_argument("--scale", type=float, default=1.0, help="image downscale factor")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
dev = "cuda"
torch.manual_seed(0); np.random.seed(0)

# ---------------------------------------------------------------- data
meta = json.load(open(os.path.join(args.data, "transforms.json")))
W0, H0 = meta["w"], meta["h"]
W, H = int(W0 / args.scale), int(H0 / args.scale)
K = torch.tensor([[meta["fl_x"] / args.scale, 0, meta["cx"] / args.scale],
                  [0, meta["fl_y"] / args.scale, meta["cy"] / args.scale], [0, 0, 1]], dtype=torch.float32)
GL2CV = np.diag([1, -1, -1, 1]).astype(np.float32)

def load_split(split):
    ims, vms, names = [], [], []
    for fr in meta["frames"]:
        if fr["split"] != split:
            continue
        p = os.path.join(args.data, fr["file_path"])
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGBA")
        if args.scale != 1.0:
            im = im.resize((W, H), Image.LANCZOS)
        ims.append(torch.from_numpy(np.asarray(im, dtype=np.float32) / 255.0))
        c2w = np.array(fr["transform_matrix"], dtype=np.float32) @ GL2CV
        vms.append(torch.from_numpy(np.linalg.inv(c2w)))
        names.append(os.path.basename(p))
    return torch.stack(ims), torch.stack(vms), names

tr_im, tr_vm, _ = load_split("train")
te_im, te_vm, te_names = load_split("test")
print(f"train {len(tr_im)} test {len(te_im)} at {W}x{H}", flush=True)
tr_im = tr_im.to(dev); tr_vm = tr_vm.to(dev); Kd = K.to(dev)

# ---------------------------------------------------------------- init gaussians
pts = np.load(os.path.join(args.data, "points3d.npz"))
xyz = torch.from_numpy(pts["xyz"]).to(dev); rgb = torch.from_numpy(pts["rgb"]).to(dev)
cams = torch.linalg.inv(tr_vm)[:, :3, 3]
center = xyz.mean(0)
scene_scale = float((cams - center).norm(dim=1).max()) * 1.1
# nearest-neighbour spacing for the initial scales
nn = []
for i in range(0, len(xyz), 2048):
    d = torch.cdist(xyz[i:i + 2048], xyz)
    nn.append(d.topk(4, largest=False).values[:, 1:].mean(1))
nn = torch.cat(nn).clamp_min(1e-4)
N = len(xyz)
C0 = 0.28209479177387814
params = torch.nn.ParameterDict({
    "means": torch.nn.Parameter(xyz.clone()),
    "scales": torch.nn.Parameter(torch.log(nn)[:, None].repeat(1, 3)),
    "quats": torch.nn.Parameter(F.normalize(torch.randn(N, 4, device=dev), dim=-1)),
    "opacities": torch.nn.Parameter(torch.logit(torch.full((N,), 0.1, device=dev))),
    "sh0": torch.nn.Parameter(((rgb - 0.5) / C0)[:, None, :]),
    "shN": torch.nn.Parameter(torch.zeros(N, (args.sh + 1) ** 2 - 1, 3, device=dev)),
})
lrs = {"means": 1.6e-4 * scene_scale, "scales": 5e-3, "quats": 1e-3, "opacities": 5e-2, "sh0": 2.5e-3, "shN": 2.5e-3 / 20}
opts = {k: torch.optim.Adam([{"params": params[k], "lr": lrs[k], "name": k}], eps=1e-15) for k in params}
sched = torch.optim.lr_scheduler.ExponentialLR(opts["means"], gamma=0.01 ** (1.0 / args.steps))
strategy = DefaultStrategy(refine_start_iter=500, refine_stop_iter=int(args.steps * 0.5), reset_every=3000,
                           refine_every=100, verbose=False)
strategy.check_sanity(params, opts)
state = strategy.initialize_state(scene_scale=scene_scale)

def render(vm, sh_deg, bg):
    colors = torch.cat([params["sh0"], params["shN"]], 1)
    out, alpha, info = rasterization(
        params["means"], F.normalize(params["quats"], dim=-1), torch.exp(params["scales"]),
        torch.sigmoid(params["opacities"]), colors, vm[None], Kd[None], W, H,
        sh_degree=sh_deg, backgrounds=bg[None], packed=False)
    return out[0], alpha[0], info

# ---------------------------------------------------------------- train
t0 = time.time()
for step in range(args.steps):
    i = np.random.randint(len(tr_im))
    gt = tr_im[i]
    bg = torch.rand(3, device=dev)
    target = gt[..., :3] * gt[..., 3:] + bg * (1 - gt[..., 3:])
    sh_deg = min(args.sh, step // 1000)
    img, alpha, info = render(tr_vm[i], sh_deg, bg)
    strategy.step_pre_backward(params, opts, state, step, info)
    l1 = (img - target).abs().mean()
    ss = ssim_fn(img.permute(2, 0, 1)[None], target.permute(2, 0, 1)[None], data_range=1.0)
    loss = 0.8 * l1 + 0.2 * (1 - ss)
    loss.backward()
    for o in opts.values():
        o.step(); o.zero_grad(set_to_none=True)
    sched.step()
    strategy.step_post_backward(params, opts, state, step, info, packed=False)
    if step % 1000 == 0 or step == args.steps - 1:
        print(f"step {step} loss {loss.item():.4f} gaussians {len(params['means'])} {time.time() - t0:.0f}s", flush=True)
train_time = time.time() - t0

# ---------------------------------------------------------------- evaluate on held-out views
BG = torch.tensor([0.235, 0.235, 0.245], device=dev)
ps, ss_ = [], []
os.makedirs(os.path.join(args.out, "test"), exist_ok=True)
with torch.no_grad():
    for k in range(len(te_im)):
        gt = te_im[k].to(dev)
        target = gt[..., :3] * gt[..., 3:] + BG * (1 - gt[..., 3:])
        img, _, _ = render(te_vm[k].to(dev), args.sh, BG)
        img = img.clamp(0, 1)
        mse = F.mse_loss(img, target).item()
        ps.append(-10 * math.log10(max(mse, 1e-10)))
        ss_.append(ssim_fn(img.permute(2, 0, 1)[None], target.permute(2, 0, 1)[None], data_range=1.0).item())
        if k < 6:
            side = torch.cat([target, img], 1).cpu().numpy()
            Image.fromarray((side * 255).astype(np.uint8)).save(os.path.join(args.out, "test", te_names[k]))
metrics = {"psnr": float(np.mean(ps)), "ssim": float(np.mean(ss_)), "test_views": len(ps),
           "gaussians_trained": int(len(params["means"])), "train_seconds": round(train_time), "steps": args.steps,
           "resolution": [W, H], "sh_degree": args.sh}

# ---------------------------------------------------------------- crop + export .ply (standard 3DGS layout)
with torch.no_grad():
    m = params["means"]
    lo = xyz.min(0).values - 0.05; hi = xyz.max(0).values + 0.05
    keep = ((m > lo) & (m < hi)).all(1) & (torch.sigmoid(params["opacities"]) > 0.005)
    metrics["gaussians_exported"] = int(keep.sum())
    torch.save({k: v.detach()[keep].cpu() for k, v in params.items()}, os.path.join(args.out, "splat.pt"))
    means = m[keep].cpu().numpy()
    sh0 = params["sh0"][keep].cpu().numpy().reshape(-1, 3)
    shN = params["shN"][keep].cpu().numpy().transpose(0, 2, 1).reshape(len(means), -1)
    op = params["opacities"][keep].cpu().numpy()[:, None]
    sc = params["scales"][keep].cpu().numpy()
    q = F.normalize(params["quats"][keep], dim=-1).cpu().numpy()
    attrs = ["x", "y", "z", "nx", "ny", "nz"] + [f"f_dc_{i}" for i in range(3)] + [f"f_rest_{i}" for i in range(shN.shape[1])] \
        + ["opacity"] + [f"scale_{i}" for i in range(3)] + [f"rot_{i}" for i in range(4)]
    data = np.concatenate([means, np.zeros_like(means), sh0, shN, op, sc, q], axis=1).astype(np.float32)
    with open(os.path.join(args.out, "unwana-splat.ply"), "wb") as f:
        f.write(("ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % len(data)).encode())
        for a in attrs:
            f.write(f"property float {a}\n".encode())
        f.write(b"end_header\n"); f.write(data.tobytes())
json.dump(metrics, open(os.path.join(args.out, "metrics.json"), "w"), indent=1)
print("METRICS", json.dumps(metrics), flush=True)
