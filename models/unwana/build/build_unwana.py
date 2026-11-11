"""Build the Unwana demo smallsat as an editable Blender scene.

Run:  blender -b --factory-startup -P build_unwana.py -- <out.blend> [hdri.hdr]

Everything is procedural and provisional: the reference images set the look,
not engineering dimensions (see NOTES.md). Units are metres, Z up, the front
face looks toward -Y.
"""
import bpy, bmesh, math, random, sys
import numpy as np
from mathutils import Vector, Matrix, Euler

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[0] if argv else "unwana.blend"
HDRI = argv[1] if len(argv) > 1 else None
random.seed(7)

# ---------------------------------------------------------------- dimensions
HX, HY, HZ = 0.26, 0.24, 0.25          # bus half sizes (about 0.52 x 0.48 x 0.50 m)
RAIL = 0.03                            # frame rail section
BUS_Z = 0.22 + HZ                      # bus centre height above the floor
PANEL_W, PANEL_H, PANEL_T = 0.42, 0.40, 0.010
PANEL_GAP = 0.024
LIGHT_SCALE = float(__import__('os').environ.get('LIGHT_SCALE', '0.22'))
YOKE_LEN = 0.03

# ---------------------------------------------------------------- scene reset
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for c in list(bpy.data.collections):
    bpy.data.collections.remove(c)
for m in list(bpy.data.meshes):
    bpy.data.meshes.remove(m)
scene = bpy.context.scene
scene.unit_settings.system = 'METRIC'

COLL = {}
for name in ["Structure", "MLI", "SolarArray_L", "SolarArray_R", "Antenna",
             "OpticalTerminal", "Imager", "Propulsion", "Harness", "Fasteners",
             "Studio", "Cameras"]:
    c = bpy.data.collections.new(name)
    scene.collection.children.link(c)
    COLL[name] = c

# ================================================================ materials
MATS = {}

def nodes_clear(mat):
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial"); out.location = (900, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); bsdf.location = (600, 0)
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return nt, bsdf, out

def inp(bsdf, *names):
    for n in names:
        if n in bsdf.inputs:
            return bsdf.inputs[n]
    raise KeyError(names)

def uvcoord(nt):
    tc = nt.nodes.new("ShaderNodeTexCoord"); tc.location = (-900, 0)
    return tc

def wear_roughness(nt, base, amount, scale=40.0, loc=(-300, -300)):
    """Roughness = base, varied by fingerprints/dust noise (subtle wear)."""
    tc = uvcoord(nt)
    n1 = nt.nodes.new("ShaderNodeTexNoise"); n1.location = (loc[0] - 300, loc[1])
    n1.inputs["Scale"].default_value = scale
    n1.inputs["Detail"].default_value = 8
    n1.inputs["Roughness"].default_value = 0.65
    nt.links.new(tc.outputs["Object"], n1.inputs["Vector"])
    n2 = nt.nodes.new("ShaderNodeTexNoise"); n2.location = (loc[0] - 300, loc[1] - 250)
    n2.inputs["Scale"].default_value = scale * 0.12
    n2.inputs["Detail"].default_value = 3
    nt.links.new(tc.outputs["Object"], n2.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (loc[0], loc[1] - 250)
    ramp.color_ramp.elements[0].position = 0.55
    ramp.color_ramp.elements[1].position = 0.75
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.location = (loc[0] + 200, loc[1] - 100)
    nt.links.new(n2.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], mul.inputs[0])
    nt.links.new(n1.outputs["Fac"], mul.inputs[1])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.location = (loc[0] + 400, loc[1])
    mr.inputs["To Min"].default_value = base
    mr.inputs["To Max"].default_value = base + amount
    nt.links.new(mul.outputs[0], mr.inputs["Value"])
    return mr.outputs[0], tc

def mat_brushed(name, color=(0.86, 0.87, 0.88), rough=0.22, aniso=0.8):
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = nodes_clear(mat)
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = 1.0
    r_out, tc = wear_roughness(nt, rough, 0.18)
    # brushing streaks along U of the box-projected UVs
    mp = nt.nodes.new("ShaderNodeMapping"); mp.location = (-600, 250)
    mp.inputs["Scale"].default_value = (4.0, 900.0, 1.0)
    g2 = nt.nodes.new("ShaderNodeNewGeometry"); g2.location = (-1100, 400)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ"); sep.location = (-1000, 250)
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    swp = nt.nodes.new("ShaderNodeCombineXYZ"); swp.location = (-850, 300)
    nt.links.new(sep.outputs["Y"], swp.inputs["X"]); nt.links.new(sep.outputs["X"], swp.inputs["Y"])
    gt = nt.nodes.new("ShaderNodeMath"); gt.operation = 'GREATER_THAN'; gt.inputs[1].default_value = 0.6
    gt.location = (-850, 450)
    nt.links.new(g2.outputs["Random Per Island"], gt.inputs[0])
    vsel = nt.nodes.new("ShaderNodeMix"); vsel.data_type = 'VECTOR'; vsel.location = (-700, 300)
    nt.links.new(gt.outputs[0], vsel.inputs[0]); nt.links.new(tc.outputs["UV"], vsel.inputs[4])
    nt.links.new(swp.outputs[0], vsel.inputs[5])
    nt.links.new(vsel.outputs[1], mp.inputs["Vector"])
    st = nt.nodes.new("ShaderNodeTexNoise"); st.location = (-400, 250)
    st.inputs["Scale"].default_value = 1.0; st.inputs["Detail"].default_value = 4
    nt.links.new(mp.outputs[0], st.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMath"); mix.operation = 'MULTIPLY_ADD'; mix.location = (200, 100)
    mix.inputs[1].default_value = 0.16
    nt.links.new(st.outputs["Fac"], mix.inputs[0])
    nt.links.new(r_out, mix.inputs[2])
    # per-part tone variation and edge wear (lighter, rougher on sharp machined edges)
    oi = nt.nodes.new("ShaderNodeObjectInfo"); oi.location = (-600, 800)
    tone = nt.nodes.new("ShaderNodeMapRange"); tone.location = (-400, 800)
    tone.inputs["To Min"].default_value = 0.9; tone.inputs["To Max"].default_value = 1.07
    isl = nt.nodes.new("ShaderNodeNewGeometry"); isl.location = (-800, 800)
    rmix = nt.nodes.new("ShaderNodeMath"); rmix.operation = 'MULTIPLY_ADD'; rmix.location = (-600, 900)
    rmix.inputs[1].default_value = 0.5
    nt.links.new(isl.outputs["Random Per Island"], rmix.inputs[0]); nt.links.new(oi.outputs["Random"], rmix.inputs[2])
    tone.inputs["From Max"].default_value = 1.5
    nt.links.new(rmix.outputs[0], tone.inputs["Value"])
    tcol = nt.nodes.new("ShaderNodeVectorMath"); tcol.operation = 'SCALE'; tcol.location = (-200, 800)
    tcol.inputs[0].default_value = color
    nt.links.new(tone.outputs[0], tcol.inputs["Scale"])
    bev = nt.nodes.new("ShaderNodeBevel"); bev.samples = 6; bev.inputs["Radius"].default_value = 0.0018
    bev.location = (-600, 1000)
    geo = nt.nodes.new("ShaderNodeNewGeometry"); geo.location = (-600, 1200)
    dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = 'DOT_PRODUCT'; dot.location = (-400, 1050)
    nt.links.new(bev.outputs[0], dot.inputs[0]); nt.links.new(geo.outputs["Normal"], dot.inputs[1])
    edge = nt.nodes.new("ShaderNodeMapRange"); edge.location = (-200, 1050)
    edge.inputs["From Min"].default_value = 0.985; edge.inputs["From Max"].default_value = 0.9995
    edge.inputs["To Min"].default_value = 0.55; edge.inputs["To Max"].default_value = 0.0
    nt.links.new(dot.outputs["Value"], edge.inputs["Value"])
    cmix = nt.nodes.new("ShaderNodeMix"); cmix.data_type = 'RGBA'; cmix.location = (100, 900)
    cmix.inputs[7].default_value = (0.93, 0.93, 0.93, 1)
    nt.links.new(edge.outputs[0], cmix.inputs[0]); nt.links.new(tcol.outputs[0], cmix.inputs[6])
    nt.links.new(cmix.outputs[2], bsdf.inputs["Base Color"])
    radd = nt.nodes.new("ShaderNodeMath"); radd.operation = 'MULTIPLY_ADD'; radd.location = (350, 100)
    radd.inputs[1].default_value = 0.3
    nt.links.new(edge.outputs[0], radd.inputs[0]); nt.links.new(mix.outputs[0], radd.inputs[2])
    nt.links.new(radd.outputs[0], bsdf.inputs["Roughness"])
    # fine scratches as bump
    sc = nt.nodes.new("ShaderNodeTexWave"); sc.location = (-400, 500)
    sc.wave_type = 'BANDS'; sc.inputs["Scale"].default_value = 60
    sc.inputs["Distortion"].default_value = 25; sc.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], sc.inputs["Vector"])
    sr = nt.nodes.new("ShaderNodeValToRGB"); sr.location = (-200, 500)
    sr.color_ramp.elements[0].position = 0.96; sr.color_ramp.elements[1].position = 1.0
    nt.links.new(sc.outputs["Fac"], sr.inputs[0])
    bump = nt.nodes.new("ShaderNodeBump"); bump.location = (300, -300)
    bump.inputs["Strength"].default_value = 0.03; bump.inputs["Distance"].default_value = 0.0002
    nt.links.new(sr.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs[0], bsdf.inputs["Normal"])
    try:
        inp(bsdf, "Anisotropic").default_value = aniso
        tg = nt.nodes.new("ShaderNodeTangent"); tg.location = (300, -500)
        tg.direction_type = 'UV_MAP'; tg.uv_map = "UVMap"
        nt.links.new(tg.outputs[0], inp(bsdf, "Tangent"))
    except KeyError:
        pass
    mat["gltf"] = dict(color=color, metallic=1.0, roughness=rough + 0.06, tex="brushed")
    return mat

def mat_simple(name, color, metallic, rough, coat=0.0, wear=0.12, scale=40.0, coat_rough=0.05, gl=None):
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = nodes_clear(mat)
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Metallic"].default_value = metallic
    r_out, tc = wear_roughness(nt, rough, wear, scale)
    nt.links.new(r_out, bsdf.inputs["Roughness"])
    if coat:
        inp(bsdf, "Coat Weight", "Coat").default_value = coat
        inp(bsdf, "Coat Roughness").default_value = coat_rough
    mat["gltf"] = dict(color=color, metallic=metallic, roughness=rough + wear * 0.3, tex=gl)
    return mat

def mat_gold_mli(name, color=(1.0, 0.60, 0.16)):
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = nodes_clear(mat)
    tc = uvcoord(nt)
    n = nt.nodes.new("ShaderNodeTexNoise"); n.location = (-500, 200)
    n.inputs["Scale"].default_value = 9; n.inputs["Detail"].default_value = 6
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.location = (-250, 200)
    ramp.color_ramp.elements[0].color = (1.0, 0.66, 0.18, 1)
    ramp.color_ramp.elements[1].color = (1.0, 0.78, 0.30, 1)
    ramp.color_ramp.elements[0].position = 0.3; ramp.color_ramp.elements[1].position = 0.75
    nt.links.new(n.outputs["Fac"], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 1.0
    r_out, _ = wear_roughness(nt, 0.10, 0.08, 25)
    nt.links.new(r_out, bsdf.inputs["Roughness"])
    # micro-wrinkle: fine ridged noise and film creases as bump on top of the displaced geometry
    mw = nt.nodes.new("ShaderNodeTexNoise"); mw.location = (-500, -500)
    mw.inputs["Scale"].default_value = 420; mw.inputs["Detail"].default_value = 3
    nt.links.new(tc.outputs["Object"], mw.inputs["Vector"])
    vo = nt.nodes.new("ShaderNodeTexVoronoi"); vo.location = (-500, -750)
    vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs["Scale"].default_value = 160
    nt.links.new(tc.outputs["Object"], vo.inputs["Vector"])
    b1 = nt.nodes.new("ShaderNodeBump"); b1.location = (0, -500)
    b1.inputs["Strength"].default_value = 0.10; b1.inputs["Distance"].default_value = 0.0002
    nt.links.new(mw.outputs["Fac"], b1.inputs["Height"])
    b2 = nt.nodes.new("ShaderNodeBump"); b2.location = (250, -650)
    b2.inputs["Strength"].default_value = 0.06; b2.inputs["Distance"].default_value = 0.0002
    nt.links.new(vo.outputs["Distance"], b2.inputs["Height"]); nt.links.new(b1.outputs[0], b2.inputs["Normal"])
    nt.links.new(b2.outputs[0], bsdf.inputs["Normal"])
    mat["gltf"] = dict(color=(1.0, 0.76, 0.33), metallic=1.0, roughness=0.14, tex="mli")
    return mat

def mat_glass(name, film_nm=320.0, film_ior=1.38, tint=(1, 1, 1), spec_tint=None):
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = nodes_clear(mat)
    bsdf.inputs["Base Color"].default_value = (*tint, 1)
    bsdf.inputs["Roughness"].default_value = 0.0
    inp(bsdf, "Transmission Weight", "Transmission").default_value = 1.0
    bsdf.inputs["IOR"].default_value = 1.52
    try:
        inp(bsdf, "Thin Film Thickness").default_value = film_nm
        inp(bsdf, "Thin Film IOR").default_value = film_ior
    except KeyError:
        pass
    if spec_tint:
        inp(bsdf, "Specular Tint").default_value = (*spec_tint, 1)
        inp(bsdf, "Specular IOR Level", "Specular").default_value = 1.0
    mat["gltf"] = dict(color=tint, metallic=0.0, roughness=0.02, transmission=1.0, tex=None)
    return mat

def mat_solar(name):
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = nodes_clear(mat)
    tc = uvcoord(nt)
    # cell texture: deep blue with faint gridlines (fingers) and slight sheen variation
    w = nt.nodes.new("ShaderNodeTexWave"); w.location = (-500, 200)
    w.wave_type = 'BANDS'; w.bands_direction = 'X'; w.inputs["Scale"].default_value = 260
    nt.links.new(tc.outputs["Object"], w.inputs["Vector"])
    wr = nt.nodes.new("ShaderNodeValToRGB"); wr.location = (-300, 200)
    wr.color_ramp.elements[0].position = 0.9; wr.color_ramp.elements[1].position = 0.97
    nt.links.new(w.outputs["Fac"], wr.inputs[0])
    n = nt.nodes.new("ShaderNodeTexNoise"); n.location = (-500, -100)
    n.inputs["Scale"].default_value = 30
    nt.links.new(tc.outputs["Object"], n.inputs["Vector"])
    base = nt.nodes.new("ShaderNodeMix"); base.data_type = 'RGBA'; base.location = (-100, 100)
    base.inputs[6].default_value = (0.010, 0.020, 0.10, 1)
    base.inputs[7].default_value = (0.016, 0.032, 0.16, 1)
    nt.links.new(n.outputs["Fac"], base.inputs[0])
    fing = nt.nodes.new("ShaderNodeMix"); fing.data_type = 'RGBA'; fing.location = (150, 150)
    fing.inputs[7].default_value = (0.20, 0.22, 0.26, 1)
    mf = nt.nodes.new("ShaderNodeMath"); mf.operation = 'MULTIPLY'; mf.inputs[1].default_value = 0.35
    nt.links.new(wr.outputs[0], mf.inputs[0])
    nt.links.new(mf.outputs[0], fing.inputs[0])
    nt.links.new(base.outputs[2], fing.inputs[6])
    nt.links.new(fing.outputs[2], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = 0.2
    bsdf.inputs["Roughness"].default_value = 0.35
    inp(bsdf, "Coat Weight", "Coat").default_value = 0.6
    inp(bsdf, "Coat Roughness").default_value = 0.025
    inp(bsdf, "Coat IOR").default_value = 1.5
    mat["gltf"] = dict(color=(0.018, 0.03, 0.10), metallic=0.3, roughness=0.12, tex="solar")
    return mat

def mat_backdrop(name):
    mat = bpy.data.materials.new(name)
    nt, bsdf, out = nodes_clear(mat)
    bsdf.inputs["Base Color"].default_value = (0.052, 0.054, 0.058, 1)
    bsdf.inputs["Roughness"].default_value = 0.55
    inp(bsdf, "Specular IOR Level", "Specular").default_value = 0.35
    return mat

MATS["alu"] = mat_brushed("Aluminium_Brushed", color=(0.68, 0.69, 0.70), rough=0.26)
MATS["alu_dark"] = mat_brushed("Aluminium_Machined", color=(0.70, 0.71, 0.72), rough=0.30, aniso=0.4)
MATS["alu_bead"] = mat_simple("Aluminium_BeadBlasted", (0.64, 0.64, 0.65), 1.0, 0.42, wear=0.1)
MATS["alu_base"] = mat_simple("Aluminium_BasePanel_Alodine", (0.36, 0.36, 0.35), 1.0, 0.45, wear=0.1)
MATS["black"] = mat_simple("Black_Anodised", (0.018, 0.018, 0.02), 0.6, 0.38, coat=0.25, coat_rough=0.2, wear=0.15)
MATS["radiator"] = mat_simple("Radiator_BlackPaint", (0.012, 0.012, 0.013), 0.0, 0.62, wear=0.12, scale=12)
MATS["gold_anod"] = mat_simple("Gold_Anodised", (0.95, 0.62, 0.20), 1.0, 0.28, wear=0.12)
MATS["gold"] = mat_simple("Gold_Plated", (1.0, 0.70, 0.28), 1.0, 0.14, wear=0.08)
MATS["mli"] = mat_gold_mli("Kapton_MLI_Gold")
MATS["mli_tape"] = mat_simple("Kapton_Tape", (1.0, 0.70, 0.26), 1.0, 0.28, wear=0.08)
MATS["stainless"] = mat_simple("Stainless_Steel", (0.62, 0.62, 0.62), 1.0, 0.20, wear=0.12)
MATS["black_oxide"] = mat_simple("Steel_BlackOxide", (0.03, 0.03, 0.03), 1.0, 0.35)
MATS["solar"] = mat_solar("PV_Cell_TripleJunction")
MATS["substrate"] = mat_simple("PV_Substrate_Kapton", (0.06, 0.05, 0.04), 0.0, 0.5)
MATS["frame_orange"] = mat_simple("Panel_Frame_OrangeAnodised", (0.88, 0.46, 0.12), 0.9, 0.28, wear=0.14)
MATS["interconnect"] = mat_simple("Cell_Interconnect_Silver", (0.92, 0.92, 0.92), 1.0, 0.18)
MATS["glass_violet"] = mat_glass("Glass_CoatedViolet", 290.0, 1.6, tint=(0.8, 0.7, 1.0), spec_tint=(0.85, 0.2, 1.0))
inp(MATS["glass_violet"].node_tree.nodes["Principled BSDF"], "Coat Weight").default_value = 0.6
inp(MATS["glass_violet"].node_tree.nodes["Principled BSDF"], "Coat Tint").default_value = (0.75, 0.45, 1.0, 1)
MATS["glass_green"] = mat_glass("Glass_CoatedGreen", 0.0, 1.45, tint=(0.85, 1.0, 0.9), spec_tint=(0.3, 1.0, 0.55))
MATS["glass_clear"] = mat_glass("Glass_Clear", 120.0, 1.38)
MATS["matte_black"] = mat_simple("Lens_Barrel_MatteBlack", (0.008, 0.008, 0.008), 0.0, 0.8)
MATS["nozzle"] = mat_simple("Nozzle_CoatedNiobium", (0.035, 0.035, 0.038), 0.7, 0.42, wear=0.18, scale=20)
MATS["nozzle_band"] = mat_simple("Nozzle_Band_Inconel", (0.30, 0.29, 0.28), 1.0, 0.35, wear=0.15)
MATS["nozzle_in"] = mat_simple("Nozzle_HeatTint", (0.10, 0.20, 0.55), 1.0, 0.25, wear=0.1)
MATS["braid"] = mat_simple("Harness_Overbraid", (0.42, 0.42, 0.43), 1.0, 0.45, wear=0.1, scale=300)
MATS["ptfe"] = mat_simple("Wire_PTFE_White", (0.82, 0.81, 0.78), 0.0, 0.45, wear=0.1)
MATS["wire_kapton"] = mat_simple("Wire_Kapton_Amber", (0.55, 0.25, 0.04), 0.0, 0.25, coat=0.5)
MATS["wire_black"] = mat_simple("Wire_Jacket_Black", (0.02, 0.02, 0.02), 0.0, 0.5)
MATS["lacing"] = mat_simple("Lacing_Tape_White", (0.75, 0.74, 0.70), 0.0, 0.7)
MATS["rubber"] = mat_simple("Clamp_Cushion_Rubber", (0.35, 0.05, 0.04), 0.0, 0.6)
MATS["backdrop"] = mat_backdrop("Studio_Backdrop_Grey")

# ================================================================ mesh builder
def rot_to(n):
    """Rotation matrix taking +Z to direction n."""
    n = Vector(n).normalized()
    return n.to_track_quat('Z', 'Y').to_matrix().to_4x4()

def TR(p, R=None):
    M = Matrix.Translation(Vector(p))
    return M @ R if R is not None else M

class MB:
    def __init__(self):
        self.v, self.f, self.fm, self.mats = [], [], [], []

    def mi(self, name):
        if name not in self.mats:
            self.mats.append(name)
        return self.mats.index(name)

    def add(self, verts, faces, M, mat):
        base = len(self.v); m = self.mi(mat)
        self.v.extend(M @ Vector(p) for p in verts)
        for fc in faces:
            self.f.append(tuple(base + i for i in fc)); self.fm.append(m)

    def box(self, center, size, mat, R=None):
        sx, sy, sz = (s / 2 for s in size)
        vs = [(x, y, z) for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)]
        fs = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        self.add(vs, fs, TR(center, R), mat)

    def lathe(self, prof, segs, M, mat, mod=None, cap=True):
        """prof: list of (r, z[, flag]); revolve around local Z."""
        rings, base = [], len(self.v)
        verts = []
        for (pt) in prof:
            r, z = pt[0], pt[1]
            flag = pt[2] if len(pt) > 2 else None
            if r <= 1e-7:
                rings.append([len(verts)]); verts.append((0, 0, z)); continue
            ring = []
            for i in range(segs):
                a = 2 * math.pi * i / segs
                rr = r
                if flag == 'hex':
                    rr = r / math.cos(((a + math.pi / 6) % (math.pi / 3)) - math.pi / 6)
                elif flag == 'knurl':
                    rr = r * (1.0 + 0.035 * (i % 2))
                elif flag == 'oct':
                    rr = r / math.cos(((a + math.pi / 8) % (math.pi / 4)) - math.pi / 8)
                ring.append(len(verts)); verts.append((rr * math.cos(a), rr * math.sin(a), z))
            rings.append(ring)
        faces = []
        for a, b in zip(rings, rings[1:]):
            if len(a) == 1 and len(b) == 1:
                continue
            for i in range(segs):
                j = (i + 1) % segs
                if len(a) == 1:
                    faces.append((a[0], b[i], b[j]))
                elif len(b) == 1:
                    faces.append((a[i], b[0], a[j]))
                else:
                    faces.append((a[i], b[i], b[j], a[j]))
        self.add(verts, faces, M, mat)

    def cyl(self, p, n, r, h, mat, segs=32, bev=0.0):
        if bev > 0:
            prof = [(0, 0), (r - bev, 0), (r, bev), (r, h - bev), (r - bev, h), (0, h)]
        else:
            prof = [(0, 0), (r, 0), (r, h), (0, h)]
        self.lathe(prof, segs, TR(p, rot_to(n)), mat)

    def tube(self, p, n, r_out, r_in, h, mat, segs=32, bev=0.0006):
        b = bev
        prof = [(r_in + b, 0), (r_out - b, 0), (r_out, b), (r_out, h - b), (r_out - b, h),
                (r_in + b, h), (r_in, h - b), (r_in, b), (r_in + b, 0)]
        self.lathe(prof, segs, TR(p, rot_to(n)), mat)

    def build(self, name, coll, parent=None, smooth=35, bevel=None, wn=False):
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in self.v], [], self.f)
        me.validate(clean_customdata=False)
        me.update()
        fm0 = np.array(self.fm, dtype=np.int32)
        if len(fm0) == len(me.polygons):
            me.polygons.foreach_set("material_index", fm0)
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        for mname in self.mats:
            me.materials.append(MATS[mname])
        box_uv(me)
        me.shade_smooth()
        try:
            me.set_sharp_from_angle(angle=math.radians(smooth))
        except Exception:
            pass
        if bevel:
            md = ob.modifiers.new("Bevel", 'BEVEL')
            md.width = bevel; md.segments = 2; md.limit_method = 'ANGLE'
            md.angle_limit = math.radians(40); md.harden_normals = False
            md.use_clamp_overlap = True
        if wn:
            ob.modifiers.new("WeightedNormal", 'WEIGHTED_NORMAL').keep_sharp = True
        if parent:
            ob.parent = parent
        return ob

def box_uv(me, scale=4.0):
    """Box-projected UVs (1 UV unit = 1/scale m); U follows the brushing direction."""
    nl = len(me.loops)
    if nl == 0:
        return
    uv = me.uv_layers.new(name="UVMap")
    co = np.empty(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    lv = np.empty(nl, dtype=np.int32); me.loops.foreach_get("vertex_index", lv)
    pn = np.empty(len(me.polygons) * 3); me.polygons.foreach_get("normal", pn); pn = pn.reshape(-1, 3)
    ls = np.empty(len(me.polygons), dtype=np.int32); me.polygons.foreach_get("loop_start", ls)
    lt = np.empty(len(me.polygons), dtype=np.int32); me.polygons.foreach_get("loop_total", lt)
    poly_of_loop = np.repeat(np.arange(len(me.polygons)), lt)
    n = np.abs(pn[poly_of_loop]); p = co[lv]
    ax = np.argmax(n, axis=1)
    u = np.where(ax == 0, p[:, 1], p[:, 0])
    v = np.where(ax == 2, p[:, 1], p[:, 2])
    out = np.stack([u * scale, v * scale], axis=1).ravel()
    uv.data.foreach_set("uv", out)

# ---------------------------------------------------------------- face frames
FACES = {
    'front':  (Vector((0, -HY, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, -1, 0)), HX, HZ),
    'rear':   (Vector((0, HY, 0)), Vector((-1, 0, 0)), Vector((0, 0, 1)), Vector((0, 1, 0)), HX, HZ),
    'left':   (Vector((-HX, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)), HY, HZ),
    'right':  (Vector((HX, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((1, 0, 0)), HY, HZ),
    'top':    (Vector((0, 0, HZ)), Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), HX, HY),
    'bottom': (Vector((0, 0, -HZ)), Vector((1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1)), HX, HY),
}

def FP(face, u, v, d=0.0):
    o, U, V, N, _, _ = FACES[face]
    return o + U * u + V * v + N * d

def FM(face, u, v, d=0.0):
    o, U, V, N, _, _ = FACES[face]
    R = Matrix((U, V, N)).transposed().to_4x4()
    return TR(FP(face, u, v, d), R)

def face_box(mb, face, u0, u1, v0, v1, d0, d1, mat):
    o, U, V, N, _, _ = FACES[face]
    R = Matrix((U, V, N)).transposed().to_4x4()
    c = FP(face, (u0 + u1) / 2, (v0 + v1) / 2, (d0 + d1) / 2)
    mb.box(c, (abs(u1 - u0), abs(v1 - v0), abs(d1 - d0)), mat, R)

# ---------------------------------------------------------------- fasteners
FAST = {}

def fast(group):
    if group not in FAST:
        FAST[group] = MB()
    return FAST[group]

def screw(group, p, n, r=0.0032, mat="stainless", washer=True):
    mb = fast(group)
    M = TR(p, rot_to(n))
    tw = 0.0006 if washer else 0.0
    if washer:
        mb.lathe([(r * 1.02, tw), (r * 1.5, tw), (r * 1.58, tw * 0.5), (r * 1.5, 0), (r * 1.02, 0)], 18, M, mat)
    h = r * 1.15
    hexr = r * 0.42
    prof = [(0, tw + h * 0.45), (hexr, tw + h * 0.45, 'hex'), (hexr, tw + h, 'hex'),
            (r * 0.84, tw + h), (r, tw + h * 0.86), (r, tw + 0.0003), (r * 0.97, tw)]
    mb.lathe(prof, 18, M, mat)

def screw_face(group, face, u, v, d=0.0, r=0.0032, **kw):
    screw(group, FP(face, u, v, d), FACES[face][3], r, **kw)

def screw_rect(group, face, u0, u1, v0, v1, d, step=0.045, inset=0.008, r=0.0028, **kw):
    a0, a1, b0, b1 = u0 + inset, u1 - inset, v0 + inset, v1 - inset
    nu = max(1, int(round((a1 - a0) / step))); nv = max(1, int(round((b1 - b0) / step)))
    for i in range(nu + 1):
        u = a0 + (a1 - a0) * i / nu
        screw_face(group, face, u, b0, d, r, **kw); screw_face(group, face, u, b1, d, r, **kw)
    for j in range(1, nv):
        v = b0 + (b1 - b0) * j / nv
        screw_face(group, face, a0, v, d, r, **kw); screw_face(group, face, a1, v, d, r, **kw)

# ================================================================ root
root = bpy.data.objects.new("Unwana", None)
root.empty_display_type = 'PLAIN_AXES'; root.empty_display_size = 0.3
root.location = (0, 0, BUS_Z)
COLL["Structure"].objects.link(root)

# ================================================================ structure
def build_frame():
    mb = MB(); cb = MB(); br = MB()
    a = RAIL; L = 0.052
    xs, ys, zs = (-HX + a / 2, HX - a / 2), (-HY + a / 2, HY - a / 2), (-HZ + a / 2, HZ - a / 2)
    for y in ys:
        for z in zs:
            mb.box((0, y, z), (2 * HX - 2 * L + 0.004, a, a), "alu")
            # lightening slot strip on rails
            mb.box((0, y, z), (2 * HX - 2 * L - 0.06, a + 0.0004, a * 0.35), "alu_dark")
    for x in xs:
        for z in zs:
            mb.box((x, 0, z), (a, 2 * HY - 2 * L + 0.004, a), "alu")
            mb.box((x, 0, z), (a * 0.35, 2 * HY - 2 * L - 0.06, a + 0.0004), "alu_dark")
    for x in xs:
        for y in ys:
            mb.box((x, y, 0), (a, a, 2 * HZ - 2 * L + 0.004), "alu")
            mb.box((x, y, 0), (a + 0.0004, a * 0.35, 2 * HZ - 2 * L - 0.06), "alu_dark")
    # corner blocks: black anodised, slightly proud, with silver bushing on each face
    for sx in (-1, 1):
        for sy in (-1, 1):
            for sz in (-1, 1):
                c = Vector((sx * (HX - L / 2 + 0.004), sy * (HY - L / 2 + 0.004), sz * (HZ - L / 2 + 0.004)))
                cb.box(c, (L, L, L), "black")
                for ax in range(3):
                    n = Vector((0, 0, 0)); n[ax] = (sx, sy, sz)[ax]
                    p = c + n * (L / 2)
                    cb.tube(p - n * 0.002, n, 0.011, 0.0055, 0.004, "alu_dark", segs=28)
                    screw("Corners", p + n * 0.0015, n, 0.0042)
                # gold brackets along the three rails leaving the corner
                for ax in range(3):
                    d = Vector((0, 0, 0)); d[ax] = -(sx, sy, sz)[ax]
                    for ax2 in range(3):
                        if ax2 == ax:
                            continue
                        nrm = Vector((0, 0, 0)); nrm[ax2] = (sx, sy, sz)[ax2]
                        p = c + d * (L / 2 + 0.022) + nrm * (a / 2 + 0.0005 + 0.004)
                        size = [0.0, 0.0, 0.0]
                        size[ax] = 0.04; size[ax2] = 0.002
                        size[3 - ax - ax2] = a * 0.9
                        br.box(p - nrm * 0.004 + nrm * 0.002, size, "gold_anod")
                        screw("Corners", p - nrm * 0.001 + d * 0.01, nrm, 0.0026)
                        screw("Corners", p - nrm * 0.001 - d * 0.01, nrm, 0.0026)
    # gold-anodised clip brackets along every rail (two per outward face)
    def rail_clips(c, axis, length):
        for ax2 in range(3):
            if ax2 == axis or abs(c[ax2]) < 1e-6:
                continue
            nrm = Vector((0, 0, 0)); nrm[ax2] = 1 if c[ax2] > 0 else -1
            for t in (-0.22, 0.22):
                p = Vector(c); p[axis] += t * length / 1.0 * 0.6
                size = [0.0, 0.0, 0.0]; size[axis] = 0.026; size[ax2] = 0.003; size[3 - axis - ax2] = a * 0.8
                br.box(p + nrm * (a / 2 + 0.0015), size, "gold_anod")
                for dt in (-0.008, 0.008):
                    q = Vector(p); q[axis] += dt
                    screw("Rails", q + nrm * (a / 2 + 0.003), nrm, 0.0021, washer=False)
    for y in ys:
        for z in zs:
            rail_clips((0, y, z), 0, 2 * HX)
    for x in xs:
        for z in zs:
            rail_clips((x, 0, z), 1, 2 * HY)
    for x in xs:
        for y in ys:
            rail_clips((x, y, 0), 2, 2 * HZ)
    o1 = mb.build("Frame_Rails", COLL["Structure"], root, bevel=0.0012)
    o2 = cb.build("Frame_CornerBlocks", COLL["Structure"], root, bevel=0.0015)
    o3 = br.build("Frame_Brackets_GoldAnodised", COLL["Structure"], root, bevel=0.0005)
    return o1

def base_panel(face, mat="alu_base", name=None):
    _, _, _, _, hu, hv = FACES[face]
    mb = MB()
    g = 0.0012
    face_box(mb, face, -hu + RAIL + g, hu - RAIL - g, -hv + RAIL + g, hv - RAIL - g, -0.006, -0.002, mat)
    return mb.build(name or f"Panel_{face.capitalize()}_Base", COLL["Structure"], root, bevel=0.0008)

build_frame()
for f in FACES:
    base_panel(f)

# ================================================================ MLI blankets
def mli_blanket(name, face, u0, u1, v0, v1, d=0.0, puff=0.007, res=0.0025, seed=0, tape=True):
    _, U, V, N, _, _ = FACES[face]
    w, h = u1 - u0, v1 - v0
    nu, nv = max(8, int(w / res)), max(8, int(h / res))
    us = np.linspace(0, 1, nu + 1); vs = np.linspace(0, 1, nv + 1)
    uu, vv = np.meshgrid(us, vs, indexing='ij')
    U_m = uu * w; V_m = vv * h                       # metres across the blanket
    # quilted pillow: puffs toward the middle, held down at the edges, tucked under at the rim
    edge = np.minimum(np.minimum(U_m, w - U_m), np.minimum(V_m, h - V_m))
    pil = np.clip(edge / 0.035, 0, 1) ** 0.7
    rng = np.random.default_rng(seed)

    def ridged(scale, amp, aniso=2.5):
        """Ridged noise: band-limited random field n, crease = 1-|n| (sharp crest lines, soft valleys)."""
        g = rng.standard_normal(uu.shape)
        ku = np.fft.fftfreq(uu.shape[0], d=res)[:, None]; kv = np.fft.fftfreq(uu.shape[1], d=res)[None, :]
        ang = rng.uniform(0, math.pi)
        ka = ku * math.cos(ang) + kv * math.sin(ang); kb = -ku * math.sin(ang) + kv * math.cos(ang)
        sa, sb = scale, scale / aniso                  # elongated wrinkles, random direction
        filt = np.exp(-2 * (math.pi ** 2) * ((ka * sa) ** 2 + (kb * sb) ** 2) / 4)
        n = np.real(np.fft.ifft2(np.fft.fft2(g) * filt))
        n /= max(n.std(), 1e-9)
        r = np.clip(1.0 - np.abs(n), 0, 1) ** 2.2
        return (r - r.mean()) * amp

    crease = ridged(0.040, 0.0042) + ridged(0.022, 0.0024) + ridged(0.011, 0.0011, 1.6) + ridged(0.006, 0.0004, 1.3)
    # a few long diagonal slack folds
    folds = np.zeros_like(uu)
    for _ in range(3):
        ang = rng.uniform(0.3, 1.3) * rng.choice([-1, 1]); k = rng.uniform(25, 45); ph = rng.uniform(0, 6.3)
        t = U_m * math.cos(ang) + V_m * math.sin(ang)
        folds += (1 - np.abs(np.sin(t * k + ph))) ** 3 * rng.uniform(0.0015, 0.003)
    # wrinkles gathering at each tie-down and running perpendicular to the taped edges
    gather = np.zeros_like(uu)
    tie = []
    a0, a1, b0, b1 = 0.005, w - 0.005, 0.005, h - 0.005
    nu_t = max(1, int(round((a1 - a0) / 0.06))); nv_t = max(1, int(round((b1 - b0) / 0.06)))
    for i in range(nu_t + 1):
        tie += [(a0 + (a1 - a0) * i / nu_t, b0), (a0 + (a1 - a0) * i / nu_t, b1)]
    for j in range(1, nv_t):
        tie += [(a0, b0 + (b1 - b0) * j / nv_t), (a1, b0 + (b1 - b0) * j / nv_t)]
    for (tu, tv) in tie:
        du, dv = U_m - tu, V_m - tv
        rr = np.hypot(du, dv); th = np.arctan2(dv, du)
        nspk = rng.integers(5, 9)
        gather += np.abs(np.sin(th * nspk + rng.uniform(0, 6.3))) * np.exp(-rr / 0.016) * 0.0016
    seam = np.exp(-edge / 0.008) * (1 - np.abs(np.sin((U_m + V_m) * 140 + seed))) * 0.0012
    dz = d + 0.0012 + pil * (puff + crease + folds) + gather * np.clip(edge / 0.012, 0, 1) + seam - (1 - np.clip(edge / 0.004, 0, 1)) * 0.0025
    o = np.asarray(FP(face, 0, 0, 0))
    P = (o[None, None, :] + np.asarray(U)[None, None, :] * (u0 + uu * w)[..., None]
         + np.asarray(V)[None, None, :] * (v0 + vv * h)[..., None]
         + np.asarray(N)[None, None, :] * dz[..., None])
    verts = P.reshape(-1, 3)
    idx = np.arange((nu + 1) * (nv + 1)).reshape(nu + 1, nv + 1)
    q = np.stack([idx[:-1, :-1], idx[1:, :-1], idx[1:, 1:], idx[:-1, 1:]], axis=-1).reshape(-1, 4)
    if np.dot(np.cross(np.asarray(U), np.asarray(V)), np.asarray(N)) < 0:
        q = q[:, ::-1]
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts)); me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(q.size); me.loops.foreach_set("vertex_index", q.ravel())
    me.polygons.add(len(q)); me.polygons.foreach_set("loop_start", np.arange(0, q.size, 4))
    me.update(); me.validate()
    ob = bpy.data.objects.new(name, me)
    COLL["MLI"].objects.link(ob)
    me.materials.append(MATS["mli"])
    box_uv(me)
    me.shade_smooth()
    ob.parent = root
    if tape:
        tb = MB()
        tw = 0.010
        for (a0, a1, b0, b1) in [(u0, u1, v0, v0 + tw), (u0, u1, v1 - tw, v1), (u0, u0 + tw, v0, v1), (u1 - tw, u1, v0, v1)]:
            face_box(tb, face, a0, a1, b0, b1, d + 0.0008, d + 0.0022, "mli_tape")
        tb.build(name + "_EdgeTape", COLL["MLI"], root, bevel=0.0004)
        # tie-down buttons (polymer button + stainless washer) along the perimeter
        screw_rect("MLI_TieDowns", face, u0, u1, v0, v1, d + 0.0052, step=0.06, inset=0.005, r=0.0022)
        btn = MB()
        a0, a1, b0, b1 = u0 + 0.005, u1 - 0.005, v0 + 0.005, v1 - 0.005
        nu_t = max(1, int(round((a1 - a0) / 0.06))); nv_t = max(1, int(round((b1 - b0) / 0.06)))
        spots = [(a0 + (a1 - a0) * i / nu_t, b) for i in range(nu_t + 1) for b in (b0, b1)]
        spots += [(a, b0 + (b1 - b0) * j / nv_t) for j in range(1, nv_t) for a in (a0, a1)]
        for (bu, bv) in spots:
            btn.lathe([(0, 0.0030), (0.0050, 0.0030), (0.0056, 0.0024), (0.0056, 0.0), (0, 0.0)], 20,
                      FM(face, bu, bv, d + 0.0022), "mli_tape")
        btn.build(name + "_TieDownButtons", COLL["MLI"], root)
    return ob

# ================================================================ FRONT face
def build_front():
    mb = MB(); rad = MB()
    # vertical black radiator strips near the side edges
    for s in (-1,):
        face_box(rad, 'front', s * 0.205 - 0.017, s * 0.205 + 0.017, -0.175, 0.175, -0.002, 0.004, "radiator")
        face_box(mb, 'front', s * 0.205 - 0.024, s * 0.205 + 0.024, -0.19, 0.19, -0.002, 0.0, "alu")
        for v in (-0.183, 0.183):
            screw_face("Front", 'front', s * 0.205, v, 0.0, 0.0026)
    rad.build("Radiator_Front_Strips", COLL["Structure"], root, bevel=0.0008)
    # cross members
    face_box(mb, 'front', -0.23, -0.032, -0.226, -0.198, -0.002, 0.002, "alu")
    face_box(mb, 'front', -0.23, -0.032, 0.198, 0.226, -0.002, 0.002, "alu")
    face_box(mb, 'front', -0.185, -0.032, -0.011, 0.001, -0.002, 0.003, "alu")
    face_box(mb, 'front', -0.034, -0.028, -0.226, 0.226, -0.002, 0.004, "alu")
    for u in np.linspace(-0.22, -0.045, 4):
        screw_face("Front", 'front', u, -0.212, 0.002, 0.0026)
        screw_face("Front", 'front', u, 0.212, 0.002, 0.0026)
    mb.build("Panel_Front_Members", COLL["Structure"], root, bevel=0.0008)
    # avionics cover (upper left): raised machined lid with chamfered corners
    lid = MB()
    face_box(lid, 'front', -0.182, -0.038, 0.008, 0.19, -0.002, 0.003, "alu_dark")
    c = 0.012
    o, U, V, N, _, _ = FACES['front']
    pts2d = [(-0.176 + c, 0.014), (-0.044 - c, 0.014), (-0.044, 0.014 + c), (-0.044, 0.184 - c),
             (-0.044 - c, 0.184), (-0.176 + c, 0.184), (-0.176, 0.184 - c), (-0.176, 0.014 + c)]
    vs = []
    for d in (0.003, 0.016):
        for (uu, vv) in pts2d:
            vs.append(FP('front', uu, vv, d))
    n8 = len(pts2d)
    fs = [tuple(range(n8))[::-1], tuple(range(n8, 2 * n8))]
    for i in range(n8):
        j = (i + 1) % n8
        fs.append((i, j, n8 + j, n8 + i))
    lid.add(vs, fs, Matrix.Identity(4), "alu")
    lid.cyl(FP('front', -0.11, 0.06, 0.016), FACES['front'][3], 0.006, 0.0015, "alu_dark", segs=24)
    lid.build("Avionics_Cover", COLL["Structure"], root, bevel=0.0012)
    for (uu, vv) in [(-0.17, 0.02), (-0.11, 0.02), (-0.05, 0.02), (-0.17, 0.178), (-0.11, 0.178),
                     (-0.05, 0.178), (-0.17, 0.1), (-0.05, 0.1)]:
        screw_face("Front", 'front', uu, vv, 0.016, 0.0028)
    # imager mounting plate (lower left)
    pl = MB()
    face_box(pl, 'front', -0.182, -0.038, -0.19, -0.016, -0.002, 0.004, "alu")
    pl.build("Imager_MountPlate", COLL["Imager"], root, bevel=0.0010)
    screw_rect("Front", 'front', -0.182, -0.038, -0.19, -0.016, 0.004, step=0.07, r=0.0026)
    # MLI blankets: two quilted panels with a horizontal seam
    mli_blanket("MLI_Front_Upper", 'front', -0.026, 0.229, -0.002, 0.226, seed=1)
    mli_blanket("MLI_Front_Lower", 'front', -0.026, 0.229, -0.226, -0.004, seed=2)
    # cover-plate details: label plate, vent slots, test connector
    det = MB()
    face_box(det, 'front', -0.165, -0.115, 0.15, 0.172, 0.016, 0.0175, "black")
    for k in range(5):
        face_box(det, 'front', -0.16 + k * 0.012, -0.154 + k * 0.012, 0.03, 0.07, 0.0155, 0.0162, "matte_black")
    det.build("Avionics_Cover_Details", COLL["Structure"], root, bevel=0.0003)
    connector("Front_TestConnector", 'front', -0.075, 0.05, 0.016, size=0.007, mat="alu_dark")

def build_imager():
    mb = MB()
    o, U, V, N, _, _ = FACES['front']
    M = FM('front', -0.11, -0.103, 0.004)
    R = 0.056
    # stepped black housing
    mb.lathe([(0, 0), (R + 0.006, 0), (R + 0.006, 0.006), (R, 0.008), (R, 0.032), (R - 0.003, 0.035),
              (0.022, 0.035), (0, 0.035)], 64, M, "black")
    # rotating bezel ring with knurl
    mb.lathe([(R + 0.0005, 0.012), (R + 0.003, 0.013, 'knurl'), (R + 0.003, 0.024, 'knurl'), (R + 0.0005, 0.025)],
             96, M, "black")
    eyes = MB(); glass = MB()
    for (du, dv, rr) in [(-0.02, -0.004, 0.0135), (0.021, 0.0, 0.0115)]:
        Me = M @ Matrix.Translation((du, dv, 0.035))
        eyes.lathe([(rr + 0.004, 0), (rr + 0.004, 0.006), (rr + 0.0025, 0.007), (rr, 0.004), (rr * 0.8, -0.012),
                    (0, -0.012)], 48, Me, "matte_black")
        eyes.tube(Me.translation, N, rr + 0.0045, rr + 0.0018, 0.0062, "alu_dark", segs=48)
        # front element (meniscus) and inner element
        glass.lathe([(0, 0.0045), (rr * 0.6, 0.0040), (rr, 0.0028), (rr, 0.0005), (rr * 0.6, 0.0012), (0, 0.0016)],
                    48, Me, "glass_green")
        glass.lathe([(0, -0.004), (rr * 0.7, -0.0045), (rr * 0.7, -0.0065), (0, -0.006)], 32, Me, "glass_clear")
    mb.build("Imager_Housing", COLL["Imager"], root, bevel=0.0006)
    eyes.build("Imager_LensBarrels", COLL["Imager"], root)
    glass.build("Imager_Lenses", COLL["Imager"], root, smooth=80)
    for k in range(6):
        a = k * math.pi / 3 + 0.3
        screw("Imager", (M @ Vector((math.cos(a) * (R + 0.002), math.sin(a) * (R + 0.002), 0.006))), N, 0.0022)

# ================================================================ REAR face
def build_rear():
    mli_blanket("MLI_Rear", 'rear', -0.23, 0.23, -0.226, 0.226, seed=3, puff=0.004)
    rad = MB(); mb = MB()
    for s in (-1, 1):
        face_box(mb, 'rear', s * 0.188 - 0.03, s * 0.188 + 0.03, -0.17, 0.17, 0.0, 0.010, "alu")
        face_box(rad, 'rear', s * 0.188 - 0.02, s * 0.188 + 0.02, -0.155, 0.155, 0.010, 0.014, "radiator")
        screw_rect("Rear", 'rear', s * 0.188 - 0.03, s * 0.188 + 0.03, -0.17, 0.17, 0.010, step=0.08, r=0.0026)
    rad.build("Radiator_Rear_Strips", COLL["Structure"], root, bevel=0.0008)
    # large flat silver service panel
    face_box(mb, 'rear', -0.1, 0.1, -0.11, 0.135, 0.0, 0.016, "alu")
    face_box(mb, 'rear', -0.085, 0.085, -0.095, 0.12, 0.016, 0.018, "alu_dark")
    mb.build("Rear_ServicePanel", COLL["Structure"], root, bevel=0.0015)
    screw_rect("Rear", 'rear', -0.1, 0.1, -0.11, 0.135, 0.016, step=0.05, r=0.0028)
    screw_face("Rear", 'rear', 0.0, 0.012, 0.018, 0.003)
    # connector rows
    for vv, d in ((-0.165, 0.004), (0.165, 0.004)):
        for uu in (-0.05, 0.0, 0.05):
            connector("Rear_Connector", 'rear', uu, vv, d, size=0.011)

CONN = MB()

def connector(name, face, u, v, d, size=0.010, mat="gold"):
    """Circular MIL-style receptacle: square flange, 4 screws, knurled coupling nut, backshell."""
    o, U, V, N, _, _ = FACES[face]
    face_box(CONN, face, u - size * 1.45, u + size * 1.45, v - size * 1.45, v + size * 1.45, d, d + 0.002, "alu_dark")
    for du in (-1, 1):
        for dv in (-1, 1):
            screw("Connectors", FP(face, u + du * size * 1.05, v + dv * size * 1.05, d + 0.002), N, 0.0014, washer=False)
    M = FM(face, u, v, d + 0.002)
    CONN.lathe([(0, 0), (size, 0), (size, 0.004), (size * 1.1, 0.0045, 'knurl'), (size * 1.1, 0.012, 'knurl'),
                (size * 0.95, 0.013), (size * 0.8, 0.016), (size * 0.8, 0.026), (size * 0.55, 0.03), (0, 0.03)],
               36, M, mat)

# ================================================================ LEFT / RIGHT faces
def build_left():
    mli_blanket("MLI_Left", 'left', -0.21, 0.21, -0.226, 0.226, seed=4, puff=0.004)
    rad = MB(); mb = MB()
    for (u0, u1) in ((-0.15, -0.025), (0.025, 0.15)):
        for (v0, v1) in ((-0.185, -0.025), (0.025, 0.185)):
            face_box(rad, 'left', u0, u1, v0, v1, 0.002, 0.013, "radiator")
            screw_rect("Left", 'left', u0, u1, v0, v1, 0.013, step=0.08, inset=0.007, r=0.0026)
    rad.build("Radiator_Left_Panels", COLL["Structure"], root, bevel=0.001)
    for s in (-1, 1):
        face_box(mb, 'left', s * 0.2 - 0.012, s * 0.2 + 0.012, -0.226, 0.226, 0.0, 0.009, "alu")
        for vv in np.linspace(-0.2, 0.2, 6):
            screw_face("Left", 'left', s * 0.2, vv, 0.009, 0.0026)
    mb.build("Panel_Left_Members", COLL["Structure"], root, bevel=0.0008)

def build_right():
    mli_blanket("MLI_Right", 'right', -0.21, 0.21, -0.226, 0.226, seed=5, puff=0.004)
    rad = MB()
    for (v0, v1) in ((-0.185, -0.022), (0.022, 0.185)):
        face_box(rad, 'right', -0.15, 0.15, v0, v1, 0.002, 0.014, "radiator")
        screw_rect("Right", 'right', -0.15, 0.15, v0, v1, 0.014, step=0.09, inset=0.008, r=0.0028)
    rad.build("Radiator_Right_Panels", COLL["Structure"], root, bevel=0.0012)

# ================================================================ TOP deck
def build_top():
    mb = MB()
    face_box(mb, 'top', -0.23, 0.23, -0.21, 0.21, -0.002, 0.003, "alu")
    # avionics boxes and a sun sensor
    face_box(mb, 'top', 0.08, 0.2, 0.07, 0.19, 0.003, 0.045, "alu_dark")
    face_box(mb, 'top', -0.2, -0.13, -0.19, -0.12, 0.003, 0.03, "alu_dark")
    face_box(mb, 'top', -0.205, -0.125, 0.12, 0.2, 0.003, 0.012, "gold_anod")
    for (u0, u1, v0, v1) in ((-0.21, -0.12, -0.09, -0.02), (0.03, 0.12, 0.13, 0.195)):
        face_box(mb, 'top', u0, u1, v0, v1, 0.003, 0.0065, "alu_dark")
        screw_rect("Top", 'top', u0, u1, v0, v1, 0.0065, step=0.03, inset=0.006, r=0.0019, washer=False)
    mb.build("TopDeck", COLL["Structure"], root, bevel=0.0012)
    screw_rect("Top", 'top', -0.23, 0.23, -0.21, 0.21, 0.003, step=0.06, r=0.0028)
    screw_rect("Top", 'top', 0.08, 0.2, 0.07, 0.19, 0.045, step=0.11, r=0.0024)
    screw_rect("Top", 'top', -0.2, -0.13, -0.19, -0.12, 0.03, step=0.07, r=0.0022)
    sens = MB()
    sens.cyl(FP('top', -0.165, -0.155, 0.03), (0, 0, 1), 0.016, 0.006, "black", bev=0.001)
    sens.lathe([(0, 0.0065), (0.012, 0.006), (0.012, 0.0045)], 32, TR(FP('top', -0.165, -0.155, 0.03)), "glass_clear")
    sens.build("SunSensor", COLL["Structure"], root)
    for (uu, vv) in ((0.1, 0.05), (0.15, 0.05)):
        connector("Top_Connector", 'top', uu, vv, 0.003, size=0.007, mat="alu_dark")

# ================================================================ ANTENNA
def build_antenna():
    base = FP('top', -0.045, 0.025, 0.003)
    mb = MB()
    M = TR(base)
    mb.lathe([(0, 0), (0.088, 0), (0.088, 0.008), (0.085, 0.010), (0, 0.010)], 72, M, "alu")
    mb.lathe([(0, 0.010), (0.08, 0.010), (0.08, 0.026), (0.076, 0.030), (0.03, 0.032), (0.03, 0.05), (0, 0.05)], 72, M, "gold")
    for k in range(12):
        a = k * math.pi / 6
        screw("Antenna", base + Vector((math.cos(a) * 0.084, math.sin(a) * 0.084, 0.010)), (0, 0, 1), 0.0022)
    mb.cyl(base + Vector((0, 0, 0.05)), (0, 0, 1), 0.007, 0.12, "gold")
    mb.build("Antenna_Base", COLL["Antenna"], root, bevel=0.0008)
    # helix: 6 turns, gold-plated tube
    cu = bpy.data.curves.new("Antenna_Helix", 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = 0.0115; cu.bevel_resolution = 5; cu.resolution_u = 24
    sp = cu.splines.new('POLY')
    turns, rad, h0, h1 = 7, 0.068, 0.04, 0.54
    n = turns * 48
    pts = []
    # feed: radial leg from the mast out to the helix start
    pts.append((0, 0, h0 + 0.01)); pts.append((rad * 0.5, 0, h0 + 0.012))
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        pts.append((rad * math.cos(a), rad * math.sin(a), h0 + 0.02 + (h1 - h0) * t))
    sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    ob = bpy.data.objects.new("Antenna_Helix", cu)
    cu.materials.append(MATS["gold"])
    ob.location = base
    COLL["Antenna"].objects.link(ob); ob.parent = root

# ================================================================ OPTICAL TERMINAL
def build_terminal():
    base = FP('top', 0.13, -0.115, 0.003)
    ped = MB()
    ped.box(base + Vector((0, 0, 0.03)), (0.13, 0.10, 0.06), "alu")
    ped.lathe([(0, 0), (0.05, 0), (0.05, 0.012), (0.045, 0.016), (0, 0.016)], 64, TR(base + Vector((0, 0, 0.06))), "alu_dark")
    ped.build("OpticalTerminal_Pedestal", COLL["OpticalTerminal"], root, bevel=0.0015)
    for dx in (-0.058, 0.058):
        for dy in (-0.043, 0.043):
            screw("OpticalTerminal", base + Vector((dx, dy, 0.0)), (0, 0, 1), 0.0026)
    # azimuth turntable + yoke
    yk = MB()
    piv = base + Vector((0, 0, 0.076))
    yk.lathe([(0, 0), (0.046, 0), (0.046, 0.012), (0, 0.012)], 64, TR(piv), "alu")
    for s in (-1, 1):
        yk.box(piv + Vector((s * 0.068, 0, 0.05)), (0.012, 0.05, 0.09), "alu")
        yk.cyl(piv + Vector((s * 0.074, 0, 0.08)), (s, 0, 0), 0.02, 0.006, "alu_dark", segs=40, bev=0.001)
        screw("OpticalTerminal", piv + Vector((s * 0.080, 0, 0.08)), (s, 0, 0), 0.004)
    yk.box(piv + Vector((0, 0, 0.012 + 0.004)), (0.148, 0.05, 0.008), "alu")
    yk.build("OpticalTerminal_Yoke", COLL["OpticalTerminal"], root, bevel=0.0012)
    # elevation head: cylinder telescope pointing forward (-Y), violet-coated objective
    head_c = piv + Vector((0, 0, 0.08))
    hd = MB(); gl = MB()
    M = TR(head_c, rot_to((0, -1, 0)))
    R = 0.054
    hd.lathe([(0, -0.07), (R - 0.006, -0.07), (R, -0.064), (R, 0.03), (R + 0.004, 0.034), (R + 0.004, 0.05),
              (R + 0.001, 0.056), (R - 0.006, 0.056), (R - 0.008, 0.05), (R - 0.008, -0.02), (0, -0.02)], 72, M, "alu")
    hd.lathe([(R + 0.0002, -0.03), (R + 0.0015, -0.03), (R + 0.0015, -0.022), (R + 0.0002, -0.022)], 72, M, "gold_anod")
    # inner barrel: matte black baffles
    hd.lathe([(R - 0.0085, 0.0495), (R - 0.0085, 0.03), (R - 0.016, 0.028), (R - 0.016, 0.018), (R - 0.011, 0.016),
              (R - 0.012, -0.019), (0.0, -0.019)], 64, M, "matte_black")
    hd.build("OpticalTerminal_Head", COLL["OpticalTerminal"], root, bevel=0.0008)
    gl.lathe([(0, 0.049), (R * 0.45, 0.0485), (R - 0.008, 0.0455), (R - 0.008, 0.041), (R * 0.45, 0.042),
              (0, 0.0425)], 64, M, "glass_violet")
    gl.lathe([(0, 0.022), (R - 0.017, 0.0205), (R - 0.017, 0.017), (0, 0.016)], 48, M, "glass_clear")
    gl.build("OpticalTerminal_Objective", COLL["OpticalTerminal"], root, smooth=80)
    # cable from head down to pedestal
    harness("OpticalTerminal_Cable", [head_c + Vector((0.06, 0.03, 0.0)), head_c + Vector((0.075, 0.035, -0.03)),
                                      base + Vector((0.06, 0.03, 0.05)), base + Vector((0.058, 0.03, 0.02))],
            wires=2, r=0.0022, mats=("wire_black", "ptfe"), ties=2, coll="OpticalTerminal")

# ================================================================ PROPULSION
def build_propulsion():
    bot = FP('bottom', 0, 0, 0)
    mb = MB()
    # large bolted interface ring on the bottom face
    M = TR(bot, rot_to((0, 0, -1)))
    mb.lathe([(0.095, 0), (0.2, 0), (0.2, 0.012), (0.196, 0.016), (0.1, 0.016), (0.095, 0.012), (0.095, 0)],
             128, M, "alu")
    mb.lathe([(0.12, 0.016), (0.165, 0.016), (0.165, 0.02), (0.12, 0.02)], 128, M, "alu_dark")
    mb.build("Propulsion_InterfaceRing", COLL["Propulsion"], root, bevel=0.0008)
    for k in range(24):
        a = k * 2 * math.pi / 24
        screw("Propulsion", bot + Vector((math.cos(a) * 0.182, math.sin(a) * 0.182, -0.016)), (0, 0, -1), 0.0032)
        if k % 2 == 0:
            screw("Propulsion", bot + Vector((math.cos(a + 0.13) * 0.142, math.sin(a + 0.13) * 0.142, -0.02)),
                  (0, 0, -1), 0.0026)
    # adapter ring + valve body + nozzle
    ad = MB()
    ad.lathe([(0.0, -0.002), (0.095, -0.002), (0.095, -0.02), (0.09, -0.024), (0.082, -0.024), (0.082, -0.032),
              (0.07, -0.035), (0.0, -0.035)], 96, TR(bot), "alu")
    for k in range(12):
        a = k * math.pi / 6
        screw("Propulsion", bot + Vector((math.cos(a) * 0.088, math.sin(a) * 0.088, -0.024)), (0, 0, -1), 0.0024)
    ad.build("Propulsion_AdapterRing", COLL["Propulsion"], root, bevel=0.0008)
    nz = MB()
    top = bot + Vector((0, 0, -0.035))
    L = 0.19
    prof = []
    for i in range(25):
        t = i / 24
        r = 0.038 + (0.092 - 0.038) * (t ** 0.75)
        prof.append((r, -L * t))
    outer = [(0, 0), (0.05, 0), (0.05, -0.012), (0.042, -0.016)] + [(r + 0.003, z) for r, z in prof[1:]]
    outer += [(prof[-1][0] + 0.001, -L - 0.001)]
    nz.lathe(outer, 96, TR(top), "nozzle")
    inner = [(prof[-1][0] - 0.0005, -L - 0.001)] + [(r, z) for r, z in reversed(prof)] + [(0.0, -0.002)]
    nz.lathe(inner, 96, TR(top), "nozzle_in")
    # bolted nozzle flange and two stiffening bands
    nz.lathe([(0.04, -0.004), (0.064, -0.004), (0.066, -0.006), (0.066, -0.012), (0.064, -0.014), (0.04, -0.014)],
             96, TR(top), "nozzle_band")
    for k in range(10):
        a = k * 2 * math.pi / 10
        screw("Propulsion", top + Vector((math.cos(a) * 0.057, math.sin(a) * 0.057, -0.014)), (0, 0, -1), 0.0022)
    for t in (0.22, 0.5):
        r = 0.038 + (0.092 - 0.038) * (t ** 0.75) + 0.003; z = -L * t
        nz.lathe([(r - 0.001, z + 0.006), (r + 0.0025, z + 0.005), (r + 0.0025, z - 0.005), (r - 0.001, z - 0.006)],
                 96, TR(top), "nozzle_band")
    nz.build("Propulsion_Nozzle", COLL["Propulsion"], root, smooth=50)

# ================================================================ HARNESS
HARN = []

def harness(name, pts, wires=3, r=0.0022, mats=("ptfe", "ptfe", "wire_kapton"), ties=3, coll="Harness", clamps=()):
    pts = [Vector(p) for p in pts]
    # build a smooth path, then parallel wires around it
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = r; cu.bevel_resolution = 3; cu.resolution_u = 16; cu.use_fill_caps = True
    offs = [(0, 0)] if wires == 1 else [(math.cos(2 * math.pi * k / wires) * r * 1.15,
                                         math.sin(2 * math.pi * k / wires) * r * 1.15) for k in range(wires)]
    frames = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        a = t.cross(Vector((0, 0, 1)))
        if a.length < 1e-3:
            a = t.cross(Vector((1, 0, 0)))
        a.normalize(); b = t.cross(a)
        frames.append((a, b))
    for k, (ox, oy) in enumerate(offs):
        sp = cu.splines.new('BEZIER')
        sp.bezier_points.add(len(pts) - 1)
        for bp, p, (a, b) in zip(sp.bezier_points, pts, frames):
            bp.co = p + a * ox + b * oy
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
        sp.material_index = k % len(mats)
    ob = bpy.data.objects.new(name, cu)
    for m in mats:
        cu.materials.append(MATS[m])
    COLL[coll].objects.link(ob); ob.parent = root
    # lacing ties along the bundle
    tb = MB()
    seg_len = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seg_len)
    for j in range(ties):
        s = total * (j + 0.5) / ties
        for i, L in enumerate(seg_len):
            if s <= L:
                p = pts[i].lerp(pts[i + 1], s / L); t = (pts[i + 1] - pts[i]).normalized(); break
            s -= L
        rr = r * (2.3 if wires > 1 else 1.2)
        tb.lathe([(rr, -0.0012), (rr + 0.0007, -0.0012), (rr + 0.0007, 0.0012), (rr, 0.0012)], 16, TR(p, rot_to(t)), "lacing")
    for (p, n) in clamps:
        p = Vector(p); n = Vector(n)
        # P-clamp: cushioned loop + tab screwed to the structure
        rr = r * 2.6
        tb.lathe([(rr, -0.003), (rr + 0.0012, -0.003), (rr + 0.0012, 0.003), (rr, 0.003)], 20,
                 TR(p, rot_to((pts[-1] - pts[0]).normalized())), "stainless")
        tb.box(p - n * (rr + 0.001), (0.012, 0.012, 0.0012), "stainless", rot_to(n))
    if ties or clamps:
        tb.build(name + "_Ties", COLL[coll], root)
    return ob

def tubing(name, pts, r=0.0024):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = r; cu.bevel_resolution = 4; cu.resolution_u = 12
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p, c in zip(sp.points, pts):
        p.co = (*c, 1)
    ob = bpy.data.objects.new(name, cu); cu.materials.append(MATS["stainless"])
    COLL["Propulsion"].objects.link(ob); ob.parent = root
    fb = MB()
    for i, c in enumerate(pts):
        if i in (0, len(pts) - 1) or i % 3 == 1:
            c = Vector(c)
            nb = Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])
            fb.lathe([(r * 1.4, -0.005, 'hex'), (r * 2.3, -0.005, 'hex'), (r * 2.3, 0.005, 'hex'), (r * 1.4, 0.005, 'hex')],
                     6, TR(c, rot_to(nb)), "stainless")
    fb.build(name + "_Fittings", COLL["Propulsion"], root, smooth=20)

def build_harness():
    o = FACES
    # rear: from top connectors around the service panel down to the bottom connectors
    for s in (-1, 1):
        for k, uu in enumerate((0.05 * s, 0.0)):
            harness(f"Harness_Rear_{'R' if s > 0 else 'L'}{k}",
                    [FP('rear', uu, 0.15, 0.03), FP('rear', s * 0.12, 0.13, 0.012 + k * 0.006),
                     FP('rear', s * (0.12 + k * 0.008), 0.0, 0.012 + k * 0.006),
                     FP('rear', s * 0.12, -0.13, 0.012 + k * 0.006), FP('rear', s * 0.05 * (k + 0.2), -0.15, 0.03)],
                    wires=3, ties=4, mats=("wire_black", "braid", "wire_black"),
                    clamps=[(FP('rear', s * (0.12 + k * 0.008), 0.05, 0.012 + k * 0.006),
                                              FACES['rear'][3])])
    # left side: harness bundles running along the radiator seams
    harness("Harness_Left_Main", [FP('left', -0.2, 0.21, 0.01), FP('left', -0.12, 0.2, 0.012), FP('left', 0.0, 0.17, 0.014),
                                  FP('left', 0.0, -0.17, 0.014), FP('left', 0.12, -0.2, 0.012),
                                  FP('left', 0.21, -0.215, 0.006)],
            wires=4, r=0.0024, ties=6, mats=("ptfe", "wire_kapton", "ptfe", "wire_black"),
            clamps=[(FP('left', 0.0, 0.08, 0.014), FACES['left'][3]), (FP('left', 0.0, -0.08, 0.014), FACES['left'][3])])
    harness("Harness_Left_Branch", [FP('left', 0.0, 0.02, 0.014), FP('left', -0.06, 0.006, 0.012), FP('left', -0.17, 0.006, 0.011)],
            wires=2, r=0.002, ties=2)
    tubing("Propellant_Line_Left", [tuple(FP('left', 0.19, -0.226, 0.012)), tuple(FP('left', 0.19, -0.1, 0.012)),
                                    tuple(FP('left', 0.185, 0.0, 0.016)), tuple(FP('left', 0.12, 0.006, 0.02)),
                                    tuple(FP('left', 0.03, 0.006, 0.02))])
    tubing("Propellant_Line_Left_B", [tuple(FP('left', -0.19, -0.226, 0.012)), tuple(FP('left', -0.19, -0.05, 0.012)),
                                      tuple(FP('left', -0.17, 0.0, 0.016)), tuple(FP('left', -0.1, -0.006, 0.02))])
    for (uu, vv) in ((-0.17, 0.205), (-0.12, 0.205), (0.17, 0.205)):
        connector("Left_Connector", 'left', uu, vv, 0.004, size=0.008, mat="alu_dark")
    harness("Harness_Left_Upper", [FP('left', -0.12, 0.19, 0.03), FP('left', -0.09, 0.0, 0.012), FP('left', -0.09, -0.12, 0.012),
                                   FP('left', -0.19, -0.2, 0.008)], wires=3, r=0.002, ties=4,
            mats=("wire_black", "braid", "ptfe"), clamps=[(FP('left', -0.09, -0.05, 0.012), FACES['left'][3])])
    harness("Harness_Left_Aft", [FP('left', 0.17, 0.19, 0.03), FP('left', 0.165, 0.1, 0.012), FP('left', 0.165, -0.12, 0.012),
                                 FP('left', 0.05, -0.2, 0.01)], wires=2, r=0.0022, ties=3, mats=("braid", "wire_black"),
            clamps=[(FP('left', 0.165, 0.0, 0.012), FACES['left'][3])])
    # service loop of propellant tubing with fittings near the bottom of the left face
    loop = []
    for i in range(25):
        a = 2 * math.pi * i / 24
        loop.append(tuple(FP('left', 0.09 + 0.035 * math.cos(a) + i * 0.0012, -0.16 + 0.025 * math.sin(a), 0.02 + 0.004 * math.sin(a / 2))))
    tubing("Propellant_ServiceLoop", [tuple(FP('left', 0.19, -0.16, 0.012))] + loop + [tuple(FP('left', 0.03, -0.16, 0.014))])
    for (uu, vv) in ((-0.06, -0.2), (0.06, -0.2)):
        connector("Rear_Connector_Low", 'rear', uu + 0.14 * (1 if uu > 0 else -1), vv, 0.004, size=0.008, mat="alu_dark")
    # front: short harness from the imager into the structure
    harness("Harness_Front_Imager", [FP('front', -0.045, -0.06, 0.006), FP('front', -0.035, -0.04, 0.012),
                                     FP('front', -0.035, 0.0, 0.01), FP('front', -0.02, 0.005, 0.004)],
            wires=2, r=0.0018, ties=1)
    # bottom: propulsion feed and heater wiring
    tubing("Propellant_Feed_Bottom", [tuple(FP('bottom', -0.21, 0.19, 0.008)), tuple(FP('bottom', -0.19, 0.12, 0.012)),
                                      tuple(FP('bottom', -0.12, 0.08, 0.025)), tuple(FP('bottom', -0.07, 0.05, 0.03))])
    harness("Harness_Bottom", [FP('bottom', 0.21, -0.19, 0.006), FP('bottom', 0.17, -0.12, 0.01),
                               FP('bottom', 0.1, -0.09, 0.025), FP('bottom', 0.06, -0.06, 0.03)],
            wires=3, r=0.0018, ties=3)
    # top: terminal and antenna cabling
    harness("Harness_Top", [FP('top', 0.1, 0.05, 0.03), FP('top', 0.05, -0.04, 0.012), FP('top', 0.07, -0.11, 0.012)],
            wires=2, r=0.0018, ties=2)

# ================================================================ SOLAR ARRAYS
def solar_panel(name, coll, parent, M_local, side):
    """Panel lying in the local XZ plane, extending +X from its inner hinge line (local origin)."""
    w, h, t = PANEL_W, PANEL_H, PANEL_T
    sub = MB(); cells = MB(); dots = MB(); frame = MB()
    c0 = Vector((w / 2, 0, 0))
    sub.box(c0, (w - 0.01, t * 0.8, h - 0.01), "substrate")
    fw = 0.006
    for (cx, cz, sx, sz) in [(w / 2, h / 2 - fw / 2, w, fw), (w / 2, -h / 2 + fw / 2, w, fw),
                             (fw / 2, 0, fw, h - 2 * fw - 0.0004), (w - fw / 2, 0, fw, h - 2 * fw - 0.0004)]:
        frame.box((cx, 0, cz), (sx, t, sz), "frame_orange")
    # mid-span stiffener tabs
    for cz in (-h / 2 + 0.004, h / 2 - 0.004):
        frame.box((w / 2, 0, cz), (0.03, t + 0.004, 0.02), "frame_orange")
    cols, rows = 6, 7
    gap = 0.0022
    cw = (w - 2 * fw - (cols + 1) * gap) / cols
    ch = (h - 2 * fw - (rows + 1) * gap) / rows
    cut = cw * 0.12
    for face_y in (-1, 1):
        y = face_y * (t * 0.4 + 0.0004)
        for i in range(cols):
            for j in range(rows):
                cx = fw + gap + cw / 2 + i * (cw + gap)
                cz = -h / 2 + fw + gap + ch / 2 + j * (ch + gap)
                # cell outline with cropped corners
                ol = [(-cw / 2 + cut, -ch / 2), (cw / 2 - cut, -ch / 2), (cw / 2, -ch / 2 + cut), (cw / 2, ch / 2 - cut),
                      (cw / 2 - cut, ch / 2), (-cw / 2 + cut, ch / 2), (-cw / 2, ch / 2 - cut), (-cw / 2, -ch / 2 + cut)]
                vs = [(cx + a, y, cz + b) for a, b in ol] + [(cx + a, y + face_y * 0.0006, cz + b) for a, b in ol]
                fs = [tuple(range(8)), tuple(range(8, 16))]
                for k in range(8):
                    l = (k + 1) % 8
                    fs.append((k, l, 8 + l, 8 + k))
                cells.add(vs, fs, Matrix.Identity(4), "solar")
        # silver interconnect dots at the cropped corners
        for i in range(cols):
            for j in range(rows):
                bx = fw + gap + cw / 2 + i * (cw + gap)
                bz = -h / 2 + fw + gap + ch / 2 + j * (ch + gap)
                for du in (-cw / 4, cw / 4):
                    dots.box((bx + du, y + face_y * 0.00075, bz), (0.0011, 0.0003, ch * 0.92), "interconnect")
        for i in range(cols + 1):
            for j in range(rows + 1):
                cx = fw + gap / 2 + i * (cw + gap)
                cz = -h / 2 + fw + gap / 2 + j * (ch + gap)
                dots.cyl((cx, y + face_y * 0.0001, cz), (0, face_y, 0), 0.0021, 0.0008, "interconnect", segs=10)
    obs = []
    for mb, nm, bev in ((sub, "Substrate", None), (frame, "Frame", 0.0008), (cells, "Cells", None), (dots, "Interconnects", None)):
        mb.v = [M_local @ v for v in mb.v]
        o = mb.build(f"{name}_{nm}", coll, parent, bevel=bev)
        obs.append(o)
    return obs

def hinge(mb, p, axis_len=0.03):
    """Silver piano-style hinge: two leaves, knuckles and a pin."""
    mb.box(p + Vector((-0.012, 0, 0)), (0.02, 0.003, axis_len), "alu")
    mb.box(p + Vector((0.012, 0, 0)), (0.02, 0.003, axis_len), "alu")
    for k in range(3):
        z = -axis_len / 2 + axis_len * (k + 0.5) / 3
        mb.cyl(p + Vector((0, 0, z - axis_len / 6 + 0.0005)), (0, 0, 1), 0.0045, axis_len / 3 - 0.001, "alu", segs=20, bev=0.0004)
    mb.cyl(p + Vector((0, 0, -axis_len / 2 - 0.0015)), (0, 0, 1), 0.0018, axis_len + 0.003, "stainless", segs=12)

def build_wing(side):
    """side = -1 (left, -X) or +1 (right, +X). Wing lies in the XZ plane (y = 0), hinges are vertical."""
    tag = "L" if side < 0 else "R"
    coll = COLL[f"SolarArray_{tag}"]
    Sx = Matrix.Scale(side, 4, Vector((1, 0, 0)))
    def mirror_vec(x, y, z):
        return Vector((side * x, y, z))
    # body-mounted bracket + root hinge empty
    hr = bpy.data.objects.new(f"Hinge_{tag}_Root", None)
    hr.empty_display_type = 'ARROWS'; hr.empty_display_size = 0.05
    hr.location = mirror_vec(HX + 0.012, 0, 0)
    coll.objects.link(hr); hr.parent = root
    br = MB()
    br.box(Vector((0, 0, 0)) + mirror_vec(-0.006, 0, 0), (0.016, 0.07, 0.11), "alu")
    br.box(mirror_vec(0.004, 0, 0), (0.01, 0.03, 0.09), "gold_anod")
    for z in (-0.04, 0.04):
        for y in (-0.025, 0.025):
            screw(f"SolarArray_{tag}", mirror_vec(0.0025, y, z), (side, 0, 0), 0.0028)
    for z in (-0.05, 0.05):
        hinge(br, mirror_vec(0.012, 0, z), 0.026)
    br.build(f"SolarArray_{tag}_RootBracket", coll, hr, bevel=0.0008)
    # yoke: two arms from root hinge to panel 1
    yk = MB()
    for z in (-0.13, 0.13):
        yk.box(mirror_vec(0.012 + YOKE_LEN / 2, 0, z), (YOKE_LEN + 0.012, 0.014, 0.022), "alu")
        yk.box(mirror_vec(0.012 + YOKE_LEN / 2, 0, z), (YOKE_LEN - 0.006, 0.0145, 0.008), "gold_anod")
        for dz in (-0.006, 0.006):
            screw(f"SolarArray_{tag}", mirror_vec(0.012 + YOKE_LEN / 2, -0.0072, z + dz), (0, -1, 0), 0.0018, washer=False)
    yk.box(mirror_vec(0.016, 0, 0), (0.012, 0.016, 0.3), "alu")
    yk.box(mirror_vec(0.012 + YOKE_LEN, 0, 0), (0.01, 0.014, PANEL_H * 0.8), "alu")
    yk.build(f"SolarArray_{tag}_Yoke", coll, hr, bevel=0.0006)
    # panel hinges A (yoke→panel 1) and B (panel 1→panel 2)
    hA = bpy.data.objects.new(f"Hinge_{tag}_A", None)
    hA.empty_display_type = 'ARROWS'; hA.empty_display_size = 0.05
    hA.location = mirror_vec(0.012 + YOKE_LEN + 0.012, 0, 0)
    coll.objects.link(hA); hA.parent = hr
    hm = MB()
    for z in (-PANEL_H / 2 + 0.03, PANEL_H / 2 - 0.03):
        hinge(hm, Vector((0, 0, z)), 0.03)
    hm.build(f"SolarArray_{tag}_HingeA_Hardware", coll, hA)
    solar_panel(f"SolarArray_{tag}_Panel1", coll, hA, Sx @ Matrix.Translation((0.006, 0, 0)), side)
    hB = bpy.data.objects.new(f"Hinge_{tag}_B", None)
    hB.empty_display_type = 'ARROWS'; hB.empty_display_size = 0.05
    hB.location = mirror_vec(0.006 + PANEL_W + PANEL_GAP / 2, 0, 0)
    coll.objects.link(hB); hB.parent = hA
    hm2 = MB()
    for z in (-PANEL_H / 2 + 0.03, PANEL_H / 2 - 0.03):
        hinge(hm2, Vector((0, 0, z)), 0.03)
    # mid-span orange latch brackets (as in the references)
    hm2.box(Vector((0, 0, 0)), (PANEL_GAP + 0.02, PANEL_T + 0.004, 0.028), "frame_orange")
    hm2.build(f"SolarArray_{tag}_HingeB_Hardware", coll, hB, bevel=0.0005)
    solar_panel(f"SolarArray_{tag}_Panel2", coll, hB, Sx @ Matrix.Translation((PANEL_GAP / 2, 0, 0)), side)
    return hr, hA, hB

# ================================================================ assemble
build_front(); build_imager(); build_rear(); build_left(); build_right(); build_top()
build_antenna(); build_terminal(); build_propulsion(); build_harness()
CONN.build("Connectors", COLL["Harness"], root, bevel=0.0004)
WINGS = {s: build_wing(s) for s in (-1, 1)}
for g, mb in FAST.items():
    mb.build(f"Fasteners_{g}", COLL["Fasteners"], root, smooth=40)

# one parent empty per component group, direct children of the root (viewer hierarchy)
for cname in ("Structure", "MLI", "SolarArray_L", "SolarArray_R", "Antenna", "OpticalTerminal", "Imager",
              "Propulsion", "Harness", "Fasteners"):
    g = bpy.data.objects.new(cname, None)
    g.empty_display_size = 0.05
    COLL[cname].objects.link(g); g.parent = root
    for ob in list(COLL[cname].objects):
        if ob.parent == root and ob is not g:
            ob.parent = g

# ---------------------------------------------------------------- deployment action
def deployment_action():
    """Frames 1-90: wings unfold from stowed (folded against the sides) to deployed."""
    for side, (hr, hA, hB) in WINGS.items():
        for ob, stow, f0, f1 in ((hA, -side * math.radians(90), 1, 50), (hB, side * math.radians(178), 30, 90)):
            ob.rotation_euler = (0, 0, stow); ob.keyframe_insert("rotation_euler", index=2, frame=f0)
            ob.rotation_euler = (0, 0, 0); ob.keyframe_insert("rotation_euler", index=2, frame=f1)
        for ob in (hA, hB):
            if ob.animation_data and ob.animation_data.action:
                ob.animation_data.action.name = f"Deploy_{ob.name}"
    scene.frame_start, scene.frame_end = 1, 90
    scene.frame_set(90)

deployment_action()

# ================================================================ studio
def build_studio():
    st = COLL["Studio"]
    rig = bpy.data.objects.new("Studio_Rig", None); st.objects.link(rig)
    rig.empty_display_size = 0.5
    # seamless sweep: floor that curves up into a back wall
    mb = MB()
    prof = []
    R, W, D, H = 1.6, 14.0, 9.0, 7.0
    for i in range(17):
        a = (math.pi / 2) * i / 16
        prof.append((D / 2 - R + R * math.sin(a), R - R * math.cos(a)))
    ys = [-D / 2 - 6, -D / 2] + [p[0] for p in prof] + [D / 2]
    zs = [0, 0] + [p[1] for p in prof] + [H]
    vs = []
    for x in (-W / 2, W / 2):
        for y, z in zip(ys, zs):
            vs.append((x, y, z))
    n = len(ys)
    fs = [(i, i + 1, n + i + 1, n + i) for i in range(n - 1)]
    mb.add(vs, [f[::-1] for f in fs], Matrix.Identity(4), "backdrop")
    sweep = mb.build("Studio_Sweep", st, rig)
    sweep.data.polygons.foreach_set("use_smooth", [True] * len(sweep.data.polygons))
    md = sweep.modifiers.new("Subdivide", 'SUBSURF'); md.levels = 1; md.render_levels = 2
    # area lights: big softboxes
    def area(name, loc, target, size, power, shape='RECTANGLE', size_y=None, temp=None):
        ld = bpy.data.lights.new(name, 'AREA'); ld.shape = shape; ld.size = size
        if size_y:
            ld.size_y = size_y
        ld.energy = power * LIGHT_SCALE
        if temp:
            ld.color = temp
        ob = bpy.data.objects.new(name, ld); st.objects.link(ob)
        ob.parent = rig
        ob.location = loc
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
        return ob
    tgt = (0, 0, BUS_Z + 0.1)
    area("Softbox_Key", (-2.2, -3.1, 2.7), tgt, 2.6, 1500, size_y=1.8, temp=(1.0, 0.97, 0.93))
    area("Softbox_Fill", (3.4, -1.2, 2.4), tgt, 2.2, 140, size_y=1.6, temp=(0.93, 0.96, 1.0))
    area("Strip_Rim_L", (-2.2, 2.6, 1.8), tgt, 0.35, 650, size_y=2.4)
    area("Strip_Rim_R", (2.4, 2.4, 2.0), tgt, 0.35, 650, size_y=2.4)
    area("Softbox_Top", (1.4, 1.6, 3.4), (0, 0, 0.5), 2.0, 300, size_y=2.0)
    fb = area("Floor_Bounce", (0.8, -2.8, 0.25), tgt, 1.6, 45, size_y=0.5)
    fb.visible_glossy = False
    sc = area("Scrim_Front", (1.6, -4.6, 2.2), tgt, 2.5, 150, size_y=1.5)
    sc.visible_camera = False
    for nm, loc, sz, szy, pw in (("Card_Front", (0.3, -4.2, 1.4), 4.0, 2.6, 850), ("Card_Top", (0.0, 0.0, 3.4), 3.0, 3.0, 750),
                                 ("Card_Left", (-3.8, -0.8, 1.3), 2.6, 2.4, 750), ("Card_Right", (3.8, -0.8, 1.3), 2.6, 2.4, 750),
                                 ("Card_Back", (0.0, 3.8, 1.6), 3.0, 2.4, 450)):
        cd_ = area(nm, loc, tgt, sz, pw, size_y=szy)
        cd_.visible_camera = False
        try:
            cd_.light_linking.receiver_collection = COLL["MLI"]
        except AttributeError:
            pass

build_studio()

def build_world():
    w = bpy.data.worlds.new("Studio_World"); scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg_cam = nt.nodes.new("ShaderNodeBackground"); bg_cam.inputs[0].default_value = (0.045, 0.046, 0.05, 1)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    if HDRI:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(HDRI)
        mp = nt.nodes.new("ShaderNodeMapping"); tc = nt.nodes.new("ShaderNodeTexCoord")
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(110))
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs[0], env.inputs["Vector"])
        nt.links.new(env.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = 0.18 * LIGHT_SCALE
    else:
        bg.inputs[0].default_value = (0.25, 0.25, 0.26, 1); bg.inputs[1].default_value = 0.5
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(mix.outputs[0], out.inputs[0])

build_world()

# ================================================================ cameras
def sat_bbox():
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for c in ("Structure", "MLI", "SolarArray_L", "SolarArray_R", "Antenna", "OpticalTerminal", "Imager", "Propulsion"):
        for ob in COLL[c].all_objects:
            if ob.type in ('MESH', 'CURVE'):
                for v in ob.bound_box:
                    pts.append(ob.matrix_world @ Vector(v))
    return pts

VIEWS = {
    "Front": (0, -1, 0.06), "Rear": (0, 1, 0.06), "Left": (-1, 0, 0.06), "Right": (1, 0, 0.06),
    "Top": (0, -0.0001, 1), "Bottom": (0, 0.0001, -1),
    "FrontLeftIso": (-1, -1, 0.45), "FrontRightIso": (1, -1, 0.45),
    "RearLeftIso": (-1, 1, 0.45), "RearRightIso": (1, 1, 0.45),
}

def frame_camera(ob, ctr, dv, pts, margin=0.05):
    """Place the camera along dv so every point projects inside the frame, centred via lens shift."""
    from bpy_extras.object_utils import world_to_camera_view
    cd = ob.data
    d = 3.0
    for _ in range(40):
        ob.location = ctr + dv * d
        bpy.context.view_layer.update()
        pr = [world_to_camera_view(scene, ob, p) for p in pts]
        x0 = min(p.x for p in pr); x1 = max(p.x for p in pr)
        y0 = min(p.y for p in pr); y1 = max(p.y for p in pr)
        span = max((x1 - x0), (y1 - y0) * 1.0)
        need = max((x1 - x0) / (1 - 2 * margin), (y1 - y0) / (1 - 2 * margin))
        d *= need ** 0.9 if need > 0 else 1
        if abs(need - 1) < 0.005:
            break
    # centre the projected bounds with lens shift (fractions of the larger frame side)
    aspect = scene.render.resolution_y / scene.render.resolution_x
    cd.shift_x = ((x0 + x1) / 2 - 0.5)
    cd.shift_y = ((y0 + y1) / 2 - 0.5) * aspect

def build_cameras():
    bpy.context.view_layer.update()
    pts = sat_bbox()
    ctr = sum(pts, Vector()) / len(pts)
    scene.render.resolution_x, scene.render.resolution_y = 2560, 1440
    for name, d in VIEWS.items():
        cd = bpy.data.cameras.new(name); cd.lens = 85; cd.sensor_width = 36
        cd.clip_start = 0.05; cd.clip_end = 100
        ob = bpy.data.objects.new(name, cd); COLL["Cameras"].objects.link(ob)
        dv = Vector(d).normalized()
        ob.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
        ob.location = ctr + dv * 8
        frame_camera(ob, ctr, dv, pts)
        cd.dof.use_dof = False
    # turntable camera: framed so the whole spacecraft stays in shot through a full turn
    from mathutils import Matrix as _M
    rpts = [(_M.Rotation(math.radians(k * 15), 4, 'Z') @ (p - Vector((0, 0, 0)))) for k in range(24) for p in pts]
    cd = bpy.data.cameras.new("Turntable"); cd.lens = 85; cd.sensor_width = 36; cd.clip_end = 100
    ob = bpy.data.objects.new("Turntable", cd); COLL["Cameras"].objects.link(ob)
    dv = Vector((-1, -1.4, 0.55)).normalized()
    ob.rotation_euler = (-dv).to_track_quat('-Z', 'Y').to_euler()
    frame_camera(ob, ctr, dv, rpts, margin=0.04)
    scene.camera = bpy.data.objects["FrontLeftIso"]

build_cameras()

# ---------------------------------------------------------------- close-up cameras
def closeup(name, target, from_dir, dist, lens=100, fstop=2.0):
    cd = bpy.data.cameras.new(name); cd.lens = lens
    ob = bpy.data.objects.new(name, cd); COLL["Cameras"].objects.link(ob)
    t = root.matrix_world @ Vector(target)
    d = Vector(from_dir).normalized()
    ob.location = t + d * dist
    ob.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    cd.dof.use_dof = True; cd.dof.focus_distance = dist; cd.dof.aperture_fstop = fstop
    return ob

bpy.context.view_layer.update()
closeup("Closeup_OpticalTerminal", FP('top', 0.13, -0.17, 0.14), (-0.35, -1, 0.25), 0.55, lens=100, fstop=2.8)
closeup("Closeup_MLISeam", FP('front', 0.07, -0.003, 0.0), (0.3, -1, 0.35), 0.42, lens=100, fstop=2.8)
closeup("Closeup_Nozzle", FP('bottom', 0.0, 0.0, 0.07), (0.8, -1, -0.12), 0.85, lens=100, fstop=3.2)
closeup("Closeup_SolarHinge", Vector((HX + 0.012 + YOKE_LEN + 0.03 + PANEL_W, 0.0, PANEL_H / 2 - 0.03)),
        (0.25, -1, 0.35), 0.38, lens=100, fstop=2.8)
closeup("Closeup_Imager", FP('front', -0.11, -0.103, 0.03), (0.35, -1, 0.15), 0.4, lens=100, fstop=2.8)

# ================================================================ render settings
scene.render.engine = 'CYCLES'
cy = scene.cycles
cy.device = 'CPU'
cy.samples = 256; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.015
cy.max_bounces = 10; cy.glossy_bounces = 6; cy.transmission_bounces = 10; cy.diffuse_bounces = 4
cy.caustics_reflective = False; cy.caustics_refractive = False
cy.sample_clamp_indirect = 8.0
cy.use_denoising = False   # this Blender build has no OIDN; renders are denoised externally (denoise.py)
scene.view_settings.view_transform = 'AgX'
scene.view_settings.exposure = -0.25
for look in ("AgX - Medium High Contrast", "AgX - Base Contrast"):
    try:
        scene.view_settings.look = look; break
    except TypeError:
        pass
scene.render.film_transparent = False
vl = scene.view_layers[0]
vl.use_pass_normal = True
vl.cycles.denoising_store_passes = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'

bpy.ops.file.pack_all() if bpy.data.images else None
bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
nobj = len([o for o in bpy.data.objects])
ntri = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
print(f"BUILD_OK objects={nobj} polys={ntri} saved={OUT}")
