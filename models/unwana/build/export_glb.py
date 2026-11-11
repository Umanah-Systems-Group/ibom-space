"""Export unwana.blend to a web-ready GLB.

Run:  blender -b unwana.blend -P export_glb.py -- <out.glb> <texture_dir>

- removes the studio and cameras, converts curves (harness, helix, tubing) to meshes
- swaps each Cycles material for a glTF-compatible Principled setup; the procedural
  look is converted to small tileable image textures generated here (brushed
  aluminium roughness, MLI colour variation, PV cell fingers)
- keeps the object names and the hierarchy: Unwana > group empties > parts
- exports the wing deployment (frames 1-90) as one animation clip named Deploy
Blender's exporter converts Z-up to Y-up, so the spacecraft front (-Y here) faces +Z.
"""
import bpy, os, sys
import numpy as np

argv = sys.argv[sys.argv.index("--") + 1:]
OUT, TEX = argv[0], argv[1]
os.makedirs(TEX, exist_ok=True)
rng = np.random.default_rng(3)

# ---------------------------------------------------------------- strip studio
for cname in ("Studio", "Cameras"):
    for ob in list(bpy.data.collections[cname].objects):
        bpy.data.objects.remove(ob, do_unlink=True)

# ---------------------------------------------------------------- curves -> meshes
dg = bpy.context.evaluated_depsgraph_get()
for ob in [o for o in bpy.data.objects if o.type == 'CURVE']:
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    name, parent, mw, colls = ob.name, ob.parent, ob.matrix_world.copy(), list(ob.users_collection)
    mats = [s.material for s in ob.material_slots]
    bpy.data.objects.remove(ob, do_unlink=True)
    new = bpy.data.objects.new(name, me)
    for c in colls:
        c.objects.link(new)
    new.parent = parent
    new.matrix_world = mw
    if not me.materials:
        for m in mats:
            me.materials.append(m)
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")

# ---------------------------------------------------------------- textures
def periodic_noise(n, sx, sy, seed):
    """Tileable noise: random field low-passed in the frequency domain (wraps at the edges)."""
    r = np.random.default_rng(seed).standard_normal((n, n))
    fy = np.fft.fftfreq(n)[:, None]; fx = np.fft.fftfreq(n)[None, :]
    filt = np.exp(-((fx * sx) ** 2 + (fy * sy) ** 2))
    out = np.real(np.fft.ifft2(np.fft.fft2(r) * filt))
    out -= out.min(); out /= max(out.max(), 1e-9)
    return out

def save_png(name, rgb):
    h, w, _ = rgb.shape
    img = bpy.data.images.new(name, w, h, alpha=False)
    rgba = np.concatenate([np.clip(rgb, 0, 1), np.ones((h, w, 1))], axis=2).astype(np.float32)
    img.pixels.foreach_set(rgba.ravel())
    path = os.path.join(TEX, name + ".png")
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    img.pack()
    return img

def srgb(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * np.power(c, 1 / 2.4) - 0.055)

N = 512
streak = periodic_noise(N, 2.0, 160.0, 1)          # varies along V, smooth along U: brushing along U
smudge = periodic_noise(N, 40.0, 40.0, 2)
TEXCACHE = {}

def tex_for(kind, color, rough, metallic):
    key = (kind, tuple(np.round(color, 3)), round(rough, 3), metallic)
    if key in TEXCACHE:
        return TEXCACHE[key]
    if kind == "brushed":
        v = 0.94 + 0.08 * streak + 0.03 * smudge
        base = srgb(np.clip(np.asarray(color)[None, None, :] * v[..., None], 0, 1))
        r = np.clip(rough - 0.05 + 0.12 * streak + 0.08 * smudge, 0.04, 1)
    elif kind == "mli":
        v = periodic_noise(N, 25.0, 25.0, 5)
        c0, c1 = np.array([1.0, 0.62, 0.15]), np.array([1.0, 0.80, 0.33])
        base = srgb(c0[None, None, :] * (1 - v[..., None]) + c1[None, None, :] * v[..., None])
        r = np.clip(0.10 + 0.10 * periodic_noise(N, 60.0, 60.0, 6), 0, 1)
    elif kind == "solar":
        x = np.arange(N)
        fingers = ((x % 4) == 0).astype(float)[None, :].repeat(N, 0)
        v = periodic_noise(N, 30.0, 30.0, 7)
        c = np.array(color)[None, None, :] * (0.85 + 0.3 * v[..., None])
        c = c * (1 - 0.35 * fingers[..., None]) + 0.22 * 0.35 * fingers[..., None]
        base = srgb(np.clip(c, 0, 1))
        r = np.clip(rough + 0.05 * v, 0, 1)
    else:
        return None
    name = f"tex_{kind}_{len(TEXCACHE)}"
    bc = save_png(name + "_basecolor", base)
    mr = np.stack([np.zeros_like(r), r, np.full_like(r, metallic)], axis=2)
    mrimg = save_png(name + "_metalrough", mr)
    bc.colorspace_settings.name = 'sRGB'; mrimg.colorspace_settings.name = 'Non-Color'
    TEXCACHE[key] = (bc, mrimg)
    return TEXCACHE[key]

def gltf_material(mat):
    spec = mat.get("gltf")
    if spec is None:
        return
    spec = dict(spec)
    color = tuple(spec["color"]); rough = float(spec["roughness"]); metal = float(spec["metallic"])
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(b.outputs[0], out.inputs[0])
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Metallic"].default_value = metal
    b.inputs["Roughness"].default_value = min(max(rough, 0.03), 1)
    if spec.get("transmission"):
        b.inputs["Transmission Weight"].default_value = 1.0
        b.inputs["IOR"].default_value = 1.52
    tex = spec.get("tex")
    if tex:
        t = tex_for(tex, color, rough, metal)
        if t:
            uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
            ti = nt.nodes.new("ShaderNodeTexImage"); ti.image = t[0]
            nt.links.new(uv.outputs[0], ti.inputs[0]); nt.links.new(ti.outputs[0], b.inputs["Base Color"])
            tm = nt.nodes.new("ShaderNodeTexImage"); tm.image = t[1]
            nt.links.new(uv.outputs[0], tm.inputs[0])
            sep = nt.nodes.new("ShaderNodeSeparateColor")
            nt.links.new(tm.outputs[0], sep.inputs[0])
            nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
            nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])

for m in bpy.data.materials:
    gltf_material(m)

# ---------------------------------------------------------------- export
scene = bpy.context.scene
scene.name = "Deploy"
scene.frame_start, scene.frame_end = 1, 90
scene.frame_set(90)
for ob in bpy.data.objects:
    ob.select_set(True)
bpy.ops.export_scene.gltf(
    filepath=OUT, export_format='GLB', use_selection=False, export_apply=True,
    export_yup=True, export_texcoords=True, export_normals=True, export_materials='EXPORT',
    export_image_format='AUTO', export_draco_mesh_compression_enable=False,
    export_animations=True, export_animation_mode='SCENE', export_frame_range=True,
    export_force_sampling=True, export_anim_single_armature=False,
    export_cameras=False, export_lights=False, export_extras=False)
print("GLB_OK", OUT, os.path.getsize(OUT) // 1024, "KB")
