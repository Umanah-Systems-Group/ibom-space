"""Render named cameras from unwana.blend, denoised with Intel Open Image Denoise.

Run:  blender -b unwana.blend -P render_views.py -- <outdir> <width> <height> <samples> Cam1 [Cam2 ...]

This Blender build has no built-in OIDN, so each frame is rendered with its
albedo and normal passes, denoised by the oidnDenoise tool (built from source,
see NOTES.md) and then saved through the scene's AgX view transform.
"""
import bpy, os, sys, subprocess, time
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
outdir, W, H, SPP = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
cams = argv[4:]
os.makedirs(outdir, exist_ok=True)
tmp = os.path.join(outdir, "_tmp"); os.makedirs(tmp, exist_ok=True)
OIDN = os.environ.get("OIDN_BIN")

scene = bpy.context.scene
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100
scene.cycles.samples = SPP
scene.cycles.use_denoising = False
try:
    scene.render.threads_mode = 'AUTO'
except Exception:
    pass

# compositor: write the noisy beauty, albedo and normal passes as float EXR
scene.use_nodes = True
nt = scene.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
rl = nt.nodes.new("CompositorNodeRLayers")
comp = nt.nodes.new("CompositorNodeComposite")
nt.links.new(rl.outputs["Image"], comp.inputs["Image"])
fo = nt.nodes.new("CompositorNodeOutputFile")
fo.base_path = tmp
fo.format.file_format = 'OPEN_EXR'; fo.format.color_depth = '32'; fo.format.exr_codec = 'ZIP'
fo.file_slots.clear()
for slot, sock in (("beauty", "Image"), ("albedo", "Denoising Albedo"), ("normal", "Denoising Normal")):
    fo.file_slots.new(slot)
    nt.links.new(rl.outputs[sock], fo.inputs[slot])

def write_pfm(path, rgb):
    h, w, _ = rgb.shape
    with open(path, "wb") as f:
        f.write(f"PF\n{w} {h}\n-1.0\n".encode())
        f.write(np.ascontiguousarray(rgb, dtype="<f4").tobytes())

def read_pfm(path):
    with open(path, "rb") as f:
        assert f.readline().strip() == b"PF"
        w, h = map(int, f.readline().split())
        scale = float(f.readline())
        data = np.frombuffer(f.read(), dtype="<f4" if scale < 0 else ">f4")
    return data.reshape(h, w, 3)

def load_exr(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)

floor_objs = [o for o in bpy.data.collections["Studio"].objects if o.type == 'MESH']
TT = int(os.environ.get("TURNTABLE", "0"))
jobs = [(c, None) for c in cams] if not TT else [(cams[0], k) for k in range(TT)]
import math as _m
for cam, tt_k in jobs:
    if tt_k is not None:
        bpy.data.objects["Unwana"].rotation_euler = (0, 0, 2 * _m.pi * tt_k / TT)
        if os.path.exists(os.path.join(outdir, f"frame_{tt_k:03d}.png")):
            continue
    t0 = time.time()
    scene.camera = bpy.data.objects[cam]
    under = cam == "Bottom"
    for o in floor_objs:
        o.hide_render = under
    # the studio rig (backdrop + lights) turns to face the camera, as on a product set;
    # for the underside view it is flipped so the softboxes light the bottom
    import math
    rig = bpy.data.objects["Studio_Rig"]
    cam_ob = bpy.data.objects[cam]
    d = cam_ob.matrix_world.translation - bpy.data.objects["Unwana"].matrix_world.translation
    az = math.atan2(d.x, -d.y) if (abs(d.x) + abs(d.y)) > 0.05 * d.length else 0.0
    rig.rotation_euler = (math.pi if under else 0.0, 0.0, az)
    rig.location = (0, 0, 2 * bpy.data.objects["Unwana"].location.z if under else 0.0)
    scene.frame_set(scene.frame_current)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    scene.render.filepath = os.path.join(tmp, "composite")
    bpy.ops.render.render(write_still=False)
    files = {k: os.path.join(tmp, sorted(f for f in os.listdir(tmp) if f.startswith(k))[0]) for k in ("beauty", "albedo", "normal")}
    beauty = load_exr(files["beauty"])
    alb = load_exr(files["albedo"]); nrm = load_exr(files["normal"])
    out_rgb = beauty[..., :3]
    if OIDN and os.path.exists(OIDN):
        write_pfm(os.path.join(tmp, "c.pfm"), beauty[..., :3])
        write_pfm(os.path.join(tmp, "a.pfm"), alb[..., :3])
        write_pfm(os.path.join(tmp, "n.pfm"), nrm[..., :3])
        r = subprocess.run([OIDN, "--hdr", os.path.join(tmp, "c.pfm"), "--alb", os.path.join(tmp, "a.pfm"),
                            "--nrm", os.path.join(tmp, "n.pfm"), "-o", os.path.join(tmp, "d.pfm")],
                           capture_output=True, text=True)
        if r.returncode == 0:
            out_rgb = read_pfm(os.path.join(tmp, "d.pfm"))
        else:
            print("OIDN_FAILED", r.stderr[-500:])
    h, w, _ = out_rgb.shape
    img = bpy.data.images.new("out", w, h, float_buffer=True, alpha=False)
    rgba = np.concatenate([out_rgb, np.ones((h, w, 1), np.float32)], axis=2)
    img.pixels.foreach_set(rgba.ravel())
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    dst = os.path.join(outdir, f"{cam}.png" if tt_k is None else f"frame_{tt_k:03d}.png")
    img.save_render(dst, scene=scene)
    bpy.data.images.remove(img)
    print(f"RENDERED {cam} {W}x{H} spp={SPP} {time.time() - t0:.1f}s -> {dst}", flush=True)
