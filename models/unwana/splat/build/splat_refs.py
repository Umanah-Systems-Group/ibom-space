"""Render Blender reference views for the splat comparison (same fixed lighting as the training set).

Run: blender -b unwana.blend -P splat_refs.py -- <outdir> <width> <height> <samples> Cam1 [Cam2 ...]
Writes <Cam>.png (RGBA) and refs.json with OpenGL camera-to-world matrices and pinhole intrinsics
(lens shift included); depth of field is switched off because a splat renderer has none.

Derived from splat_dataset.py:

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
NAMES = argv[4:]
START, END = 0, 10 ** 9
os.makedirs(OUT, exist_ok=True)
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

refs = {}
for name in NAMES:
    cam = bpy.data.objects[name]; scene.camera = cam
    cd = cam.data; cd.dof.use_dof = False
    fl = cd.lens / cd.sensor_width * W
    refs[name] = {"w": W, "h": H, "fl": fl, "cx": W / 2 - cd.shift_x * W, "cy": H / 2 + cd.shift_y * W,
                  "c2w": [list(r) for r in cam.matrix_world]}
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
    img.save_render(os.path.join(OUT, name + ".png"), scene=scene)
    bpy.data.images.remove(img)
    print(f"REF {name} {time.time() - t0:.1f}s", flush=True)

json.dump(refs, open(os.path.join(OUT, "refs.json"), "w"), indent=1)
print("REFS_OK", list(refs))
