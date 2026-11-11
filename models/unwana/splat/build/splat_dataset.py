"""Render a multiview training set of Unwana for Gaussian splatting.

Run: blender -b unwana.blend -P splat_dataset.py -- <outdir> <width> <height> <samples> [start] [end]

- cameras on elevation rings plus caps and a closer ring, all aimed at the bus centre
- studio lighting FIXED in world space (rig not rotated), floor/backdrop hidden, transparent film
- frames denoised with OIDN (albedo + normal), saved as RGBA PNG through the AgX view
- writes transforms.json (NeRF/Blender convention: OpenGL camera, camera-to-world matrices)
  and points3d.npz: points sampled on the mesh surfaces with approximate material colours
"""
import bpy, os, sys, json, math, subprocess, time
import numpy as np
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, W, H, SPP = argv[0], int(argv[1]), int(argv[2]), int(argv[3])
START = int(argv[4]) if len(argv) > 4 else 0
END = int(argv[5]) if len(argv) > 5 else 10 ** 9
os.makedirs(os.path.join(OUT, "images"), exist_ok=True)
tmp = os.path.join(OUT, "_tmp"); os.makedirs(tmp, exist_ok=True)
OIDN = os.environ.get("OIDN_BIN")
scene = bpy.context.scene
root = bpy.data.objects["Unwana"]
CENTER = root.matrix_world.translation + Vector((0, 0, 0.05))

# ---------------------------------------------------------------- camera set
def ring(elev_deg, n, dist, phase=0.0):
    out = []
    for k in range(n):
        az = 2 * math.pi * (k + phase) / n
        e = math.radians(elev_deg)
        out.append((dist, az, e))
    return out

CAMS = []
for elev, n in ((-62, 16), (-35, 24), (-10, 30), (12, 32), (35, 30), (58, 22), (80, 8)):
    CAMS += ring(elev, n, 3.3, phase=0.5 * (elev > 0))
CAMS += [(3.3, 0.0, math.radians(89.0)), (3.3, math.pi, math.radians(-89.0))]
for elev, n in ((-20, 10), (20, 12), (50, 8)):
    CAMS += ring(elev, n, 1.7, phase=0.25)

cam_data = bpy.data.cameras.new("SplatCam"); cam_data.lens = 42; cam_data.sensor_width = 36
cam_data.sensor_fit = 'HORIZONTAL'; cam_data.clip_start = 0.05; cam_data.clip_end = 100
cam = bpy.data.objects.new("SplatCam", cam_data); scene.collection.objects.link(cam)
scene.camera = cam

# ---------------------------------------------------------------- scene state
scene.render.resolution_x, scene.render.resolution_y = W, H
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.cycles.samples = SPP
scene.cycles.use_denoising = False
for o in bpy.data.collections["Studio"].objects:
    if o.type == 'MESH':
        o.hide_render = True
rig = bpy.data.objects["Studio_Rig"]; rig.rotation_euler = (0, 0, 0); rig.location = (0, 0, 0)
scene.frame_set(90)
# soft fill from below, fixed in world space (the floor bounce is gone with the floor hidden)
ld = bpy.data.lights.new("Splat_UnderFill", 'AREA'); ld.size = 5.0; ld.energy = 450
for n in scene.world.node_tree.nodes:      # brighter environment so downward-facing metal has something to mirror
    if n.type == 'BACKGROUND' and n.inputs[0].is_linked:
        n.inputs[1].default_value *= 5.0
uf = bpy.data.objects.new("Splat_UnderFill", ld); scene.collection.objects.link(uf)
uf.location = (0.4, -0.6, -1.6); uf.rotation_euler = (math.radians(15), 0, 0)
uf.visible_camera = False

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
fo.format.color_mode = 'RGBA'
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
        f.readline(); w, h = map(int, f.readline().split()); f.readline()
        return np.frombuffer(f.read(), dtype="<f4").reshape(h, w, 3)

def load_exr(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32); img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)

# ---------------------------------------------------------------- transforms.json
fl = cam_data.lens / cam_data.sensor_width * W
frames = []
for i, (dist, az, el) in enumerate(CAMS):
    d = Vector((math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el)))
    cam.location = CENTER + d * dist
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    bpy.context.view_layer.update()
    name = f"r_{i:03d}"
    frames.append({"file_path": f"images/{name}.png", "transform_matrix": [list(r) for r in cam.matrix_world],
                   "split": "test" if i % 10 == 5 else "train"})
    if not (START <= i < END) or os.path.exists(os.path.join(OUT, "images", name + ".png")):
        continue
    t0 = time.time()
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    scene.render.filepath = os.path.join(tmp, "composite")
    bpy.ops.render.render(write_still=False)
    files = {k: os.path.join(tmp, sorted(f for f in os.listdir(tmp) if f.startswith(k))[0]) for k in ("beauty", "albedo", "normal")}
    beauty = load_exr(files["beauty"]); alb = load_exr(files["albedo"]); nrm = load_exr(files["normal"])
    rgb = beauty[..., :3]
    if OIDN and os.path.exists(OIDN):
        write_pfm(os.path.join(tmp, "c.pfm"), rgb); write_pfm(os.path.join(tmp, "a.pfm"), alb[..., :3])
        write_pfm(os.path.join(tmp, "n.pfm"), nrm[..., :3])
        r = subprocess.run([OIDN, "--hdr", os.path.join(tmp, "c.pfm"), "--alb", os.path.join(tmp, "a.pfm"),
                            "--nrm", os.path.join(tmp, "n.pfm"), "-o", os.path.join(tmp, "d.pfm")], capture_output=True)
        if r.returncode == 0:
            rgb = read_pfm(os.path.join(tmp, "d.pfm"))
    img = bpy.data.images.new("out", W, H, float_buffer=True, alpha=True)
    img.pixels.foreach_set(np.concatenate([rgb, beauty[..., 3:4]], axis=2).astype(np.float32).ravel())
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    img.save_render(os.path.join(OUT, "images", name + ".png"), scene=scene)
    bpy.data.images.remove(img)
    print(f"SPLATVIEW {name} {time.time() - t0:.1f}s", flush=True)

meta = {"camera_model": "OPENCV", "w": W, "h": H, "fl_x": fl, "fl_y": fl, "cx": W / 2, "cy": H / 2,
        "k1": 0, "k2": 0, "p1": 0, "p2": 0, "camera_angle_x": 2 * math.atan(W / (2 * fl)),
        "convention": "blender/opengl c2w, Z-up world", "background": "transparent (alpha mask)",
        "frames": frames}
json.dump(meta, open(os.path.join(OUT, "transforms.json"), "w"), indent=1)

# ---------------------------------------------------------------- init point cloud from mesh surfaces
if START == 0:
    dg = bpy.context.evaluated_depsgraph_get()
    pts, cols = [], []
    rng = np.random.default_rng(0)
    def srgb(c):
        c = np.clip(np.asarray(c, float), 0, 1)
        return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
    meshes = [o for o in bpy.data.objects if o.type in ('MESH', 'CURVE') and o.users_collection[0].name not in ("Studio", "Cameras")]
    tri_all = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        n = len(me.loop_triangles)
        if n == 0:
            ev.to_mesh_clear(); continue
        co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
        tv = np.empty(n * 3, dtype=np.int32); me.loop_triangles.foreach_get("vertices", tv); tv = tv.reshape(-1, 3)
        mi = np.empty(n, dtype=np.int32); me.loop_triangles.foreach_get("material_index", mi)
        M = np.array(o.matrix_world)
        wc = co @ M[:3, :3].T + M[:3, 3]
        a, b, c = wc[tv[:, 0]], wc[tv[:, 1]], wc[tv[:, 2]]
        area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
        mcols = []
        for s in o.material_slots:
            g = s.material.get("gltf") if s.material else None
            mcols.append(srgb(list(g["color"])) if g else np.array([0.5, 0.5, 0.5]))
        mcols = np.array(mcols) if mcols else np.array([[0.5, 0.5, 0.5]])
        tri_all.append((a, b, c, area, mcols[np.clip(mi, 0, len(mcols) - 1)]))
        ev.to_mesh_clear()
    A = np.concatenate([t[3] for t in tri_all]); total = A.sum()
    N = 150000
    for (a, b, c, area, tc) in tri_all:
        k = int(rng.poisson(area.sum() / total * N))
        if k == 0:
            continue
        idx = rng.choice(len(area), size=k, p=area / area.sum())
        u = rng.random((k, 1)); v = rng.random((k, 1)); flip = (u + v) > 1
        u = np.where(flip, 1 - u, u); v = np.where(flip, 1 - v, v)
        pts.append(a[idx] + u * (b[idx] - a[idx]) + v * (c[idx] - a[idx])); cols.append(tc[idx])
    np.savez(os.path.join(OUT, "points3d.npz"), xyz=np.concatenate(pts).astype(np.float32), rgb=np.concatenate(cols).astype(np.float32))
    print("POINTS", sum(len(p) for p in pts))
print("DATASET_OK", len(CAMS), "cameras")
