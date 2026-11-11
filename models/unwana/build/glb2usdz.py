"""Convert unwana.glb to unwana.usdz for iPhone/Mac Quick Look (static, deployed pose).

Run with the usd-core venv:  tools/usdvenv/bin/python glb2usdz.py out/unwana.glb out/unwana.usdz

This Blender build has no USD exporter, so the GLB is converted directly: node
hierarchy and names, triangle meshes with normals and UVs, and UsdPreviewSurface
materials (base colour, metallic/roughness textures, glass as partial opacity).
"""
import json, os, struct, sys, tempfile, re
import numpy as np
from pxr import Usd, UsdGeom, UsdShade, Sdf, Gf, UsdUtils, Vt

src, dst = sys.argv[1], sys.argv[2]
b = open(src, 'rb').read()
jl = struct.unpack('<I', b[12:16])[0]
J = json.loads(b[20:20 + jl])
bin_off = 20 + jl + 8
BIN = b[bin_off:]

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}

def acc(i):
    a = J['accessors'][i]; bv = J['bufferViews'][a['bufferView']]
    dt = np.dtype(CT[a['componentType']]); n = NC[a['type']]
    start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
    stride = bv.get('byteStride', 0)
    if stride and stride != dt.itemsize * n:
        raw = np.frombuffer(BIN, np.uint8, count=stride * a['count'], offset=start).reshape(a['count'], stride)
        arr = raw[:, :dt.itemsize * n].copy().view(dt).reshape(a['count'], n)
    else:
        arr = np.frombuffer(BIN, dt, count=a['count'] * n, offset=start).reshape(a['count'], n)
    return arr

work = tempfile.mkdtemp(prefix="unwana_usd_")
stage_path = os.path.join(work, "unwana.usdc")
stage = Usd.Stage.CreateNew(stage_path)
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
UsdGeom.SetStageMetersPerUnit(stage, 1.0)

def clean(name, used):
    s = re.sub(r'[^A-Za-z0-9_]', '_', name or 'node')
    if s[0].isdigit():
        s = '_' + s
    base, k = s, 1
    while s in used:
        k += 1; s = f"{base}_{k}"
    used.add(s)
    return s

# textures
tex_files = {}
for i, img in enumerate(J.get('images', [])):
    bv = J['bufferViews'][img['bufferView']]
    data = BIN[bv.get('byteOffset', 0): bv.get('byteOffset', 0) + bv['byteLength']]
    ext = '.png' if img.get('mimeType', 'image/png') == 'image/png' else '.jpg'
    fn = f"tex_{i}{ext}"
    open(os.path.join(work, fn), 'wb').write(data)
    tex_files[i] = fn

root = UsdGeom.Xform.Define(stage, '/Unwana')
stage.SetDefaultPrim(root.GetPrim())
mscope = UsdGeom.Scope.Define(stage, '/Unwana/Materials')
mat_paths = {}
used_m = set()

def tex_node(mat, name, tex_index, st_reader, out_type):
    t = UsdShade.Shader.Define(stage, mat.GetPath().AppendChild(name))
    t.CreateIdAttr("UsdUVTexture")
    img = J['textures'][tex_index]['source']
    t.CreateInput("file", Sdf.ValueTypeNames.Asset).Set("./" + tex_files[img])
    t.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(st_reader.ConnectableAPI(), "result")
    t.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
    t.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")
    t.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(out_type)
    return t

for mi, m in enumerate(J.get('materials', [])):
    name = clean(m.get('name', f'mat{mi}'), used_m)
    mat = UsdShade.Material.Define(stage, f'/Unwana/Materials/{name}')
    sh = UsdShade.Shader.Define(stage, mat.GetPath().AppendChild('PBR'))
    sh.CreateIdAttr("UsdPreviewSurface")
    pbr = m.get('pbrMetallicRoughness', {})
    bc = pbr.get('baseColorFactor', [1, 1, 1, 1])
    sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(*bc[:3]))
    sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(float(pbr.get('metallicFactor', 1.0)))
    sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(float(pbr.get('roughnessFactor', 1.0)))
    if 'KHR_materials_transmission' in m.get('extensions', {}):
        sh.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(0.35)
        sh.CreateInput("ior", Sdf.ValueTypeNames.Float).Set(1.52)
    st = UsdShade.Shader.Define(stage, mat.GetPath().AppendChild('st'))
    st.CreateIdAttr("UsdPrimvarReader_float2")
    st.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
    if 'baseColorTexture' in pbr:
        t = tex_node(mat, 'baseColorTex', pbr['baseColorTexture']['index'], st, "sRGB")
        t.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        sh.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(t.ConnectableAPI(), "rgb")
    if 'metallicRoughnessTexture' in pbr:
        t = tex_node(mat, 'metalRoughTex', pbr['metallicRoughnessTexture']['index'], st, "raw")
        t.CreateOutput("g", Sdf.ValueTypeNames.Float); t.CreateOutput("b", Sdf.ValueTypeNames.Float)
        sh.CreateInput("roughness", Sdf.ValueTypeNames.Float).ConnectToSource(t.ConnectableAPI(), "g")
        sh.CreateInput("metallic", Sdf.ValueTypeNames.Float).ConnectToSource(t.ConnectableAPI(), "b")
    mat.CreateSurfaceOutput().ConnectToSource(sh.ConnectableAPI(), "surface")
    mat_paths[mi] = mat

def node_xform(n):
    if 'matrix' in n:
        return Gf.Matrix4d(*n['matrix'])
    t = n.get('translation', [0, 0, 0]); r = n.get('rotation', [0, 0, 0, 1]); s = n.get('scale', [1, 1, 1])
    M = Gf.Matrix4d().SetScale(Gf.Vec3d(*s))
    R = Gf.Matrix4d().SetRotate(Gf.Quatd(r[3], Gf.Vec3d(r[0], r[1], r[2])))
    T = Gf.Matrix4d().SetTranslate(Gf.Vec3d(*t))
    return M * R * T

ntri = 0
def emit(ni, parent_path, used):
    global ntri
    n = J['nodes'][ni]
    name = clean(n.get('name', f'n{ni}'), used)
    path = parent_path.AppendChild(name)
    x = UsdGeom.Xform.Define(stage, path)
    x.AddTransformOp().Set(node_xform(n))
    if 'mesh' in n:
        used_p = set()
        for pi, prim in enumerate(J['meshes'][n['mesh']]['primitives']):
            at = prim['attributes']
            P = acc(at['POSITION']).astype(np.float32)
            idx = acc(prim['indices']).ravel().astype(np.int32) if 'indices' in prim else np.arange(len(P), dtype=np.int32)
            mp = path.AppendChild(clean(f"geo{pi}", used_p))
            mesh = UsdGeom.Mesh.Define(stage, mp)
            mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(P))
            mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(np.full(len(idx) // 3, 3, np.int32)))
            mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(idx))
            mesh.CreateSubdivisionSchemeAttr("none")
            ntri += len(idx) // 3
            if 'NORMAL' in at:
                Nn = acc(at['NORMAL']).astype(np.float32)
                mesh.CreateNormalsAttr(Vt.Vec3fArray.FromNumpy(Nn))
                mesh.SetNormalsInterpolation(UsdGeom.Tokens.vertex)
            if 'TEXCOORD_0' in at:
                uv = acc(at['TEXCOORD_0']).astype(np.float32).copy()
                uv[:, 1] = 1.0 - uv[:, 1]
                pv = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
                pv.Set(Vt.Vec2fArray.FromNumpy(uv))
            ext = np.concatenate([P.min(0), P.max(0)])
            mesh.CreateExtentAttr([Gf.Vec3f(*map(float, ext[:3])), Gf.Vec3f(*map(float, ext[3:]))])
            if 'material' in prim:
                UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(mat_paths[prim['material']])
    child_used = set()
    for c in n.get('children', []):
        emit(c, path, child_used)

top_used = {"Materials"}
for ni in J['scenes'][0]['nodes']:
    n = J['nodes'][ni]
    if n.get('name') == 'Unwana':
        root.AddTransformOp().Set(node_xform(n))
        cu = set()
        for c in n.get('children', []):
            emit(c, root.GetPath(), cu)
    else:
        emit(ni, root.GetPath(), top_used)
stage.GetRootLayer().Save()
cwd = os.getcwd(); os.chdir(work)
ok = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(os.path.join(work, "unwana.usdc")), os.path.abspath(os.path.join(cwd, dst)))
os.chdir(cwd)
print("USDZ_OK" if ok else "USDZ_FAILED", dst, os.path.getsize(dst) // 1024 if os.path.exists(dst) else 0, "KB", ntri, "tris")
