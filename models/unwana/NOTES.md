# Unwana: Blender model notes

This folder holds a photoreal, editable Blender model of the Unwana demo smallsat.
It is built from the owner's reference images in `reference/`. **It is a visual
model, not an engineering model.** The images set the look; every dimension below
is provisional.

## Files

| Path | What it is |
| --- | --- |
| `unwana.blend` | Blender 4.3 scene, textures packed. Collections: Structure, MLI, SolarArray_L, SolarArray_R, Antenna, OpticalTerminal, Imager, Propulsion, Harness, Fasteners, Studio, Cameras |
| `renders/*.png` | The 10 named views at 3840x2160, 200 samples, denoised |
| `closeups/*.png` | Five shallow depth-of-field close-ups at 2560x1440, 256 samples |
| `renders/unwana-contact-sheet.png` | The 10 views on one labelled sheet |
| `unwana.glb` | Web model for `viewer/index.html`. Y-up with the front facing +Z, no Draco, one `Deploy` clip |
| `unwana.usdz` | Static deployed model for iPhone/Mac Quick Look |
| `unwana-turntable.mp4` | 360° turntable: 72 frames, 1920x1080, 24 fps |
| `build/` | The scripts that make all of the above (see "Re-rendering") |
| `preview/` | Review renders from the modelling rounds |

## Provisional dimensions (not engineering data)

| Item | Value used | Basis |
| --- | --- | --- |
| Bus envelope | 0.52 × 0.48 × 0.50 m (W × D × H) | "roughly a 0.5 m cube, ~114 kg class" in the brief |
| Frame rails | 30 mm square on all 12 edges; 52 mm black corner blocks | read off the references |
| Solar wings | 2 panels per side, each 0.42 × 0.40 m, 10 mm thick; 6 × 7 cells per face | front reference shows 2 panels |
| Wing span (deployed) | about 2.3 m tip to tip | follows from the panel size |
| Helical antenna | 7 turns, 0.136 m coil diameter, 23 mm tube, about 0.5 m tall | coordinator review of the references |
| Optical terminal | 108 mm objective barrel on an azimuth/elevation yoke, front-right of the top deck | references |
| Imager | 112 mm black housing, two lenses, front face lower left | references |
| Bottom interface ring | 0.40 m outer diameter, 24 bolts | underside reference |
| Nozzle | 0.19 m long, 0.18 m exit diameter, standing on the floor | side references |

Origin: the floor under the nozzle. The bus centre is 0.47 m above the floor.

## Uncertain geometry (choices made, recorded so they can be corrected)

1. **Bottom aperture vs nozzle.** The bottom view shows a large circular "lens", and the side
   views show a single black nozzle. They are reconciled as **one nozzle in the centre of a
   large silver bolted interface ring**, which matches the underside close-up. The blue seen
   from below is heat-tinted metal inside the nozzle, not glass. *Uncertain.*
2. **Number of solar panels.** The references disagree: 2 per side on the front, 3 per side on
   the rear. **2 per side** is used.
3. **Wing attachment and fold.** The wings hinge at mid-height on the side faces, on a short
   bracket. The deploy animation (frames 1–90) is **illustrative only**. Stowed, the panels
   fold flat beside the side faces and overhang the front face by about 0.18 m; the real stowage
   and hold-down scheme is unknown.
4. **Wing angle.** Some isometric references show the wings swept slightly back. The model
   uses straight, coplanar wings.
5. **Front face.** The right two thirds is two stacked MLI blankets edge to edge. The left third
   has the avionics cover (upper) and the imager plate (lower). Only the left black radiator
   strip is kept.
6. **Side faces.** Left: four black radiator panels on gold MLI, with harnesses, a propellant
   line and a tubing service loop. Right: two black radiator panels with a gold MLI border.
   The panel sizes, harness routing and tubing are plausible inventions in the style of the
   references, not copies of real hardware.
7. **Rear face.** A flat silver service panel flanked by MLI and black radiator strips, with
   three connectors above and below and black overbraided harnesses around the panel.
8. **Top deck items** (sun sensor, small avionics boxes, access covers, the gold patch) are
   generic hardware placed to match the density of the references.
9. **Fasteners, brackets, clamps and connectors** are representative, not a bill of materials.

## Materials

Cycles PBR, all procedural:

- Brushed aluminium: anisotropic, brushing direction varied per plate, tone variation per
  plate, edge wear, fine scratches.
- Gold Kapton MLI: real displaced geometry at 2.5 mm quads. Four octaves of ridged, elongated
  crease noise (creases a few mm deep, 1–4 cm apart), long diagonal slack folds, a pillow
  bulge, wrinkles gathered at each tie-down and along the taped edges, and edges tucked under.
  A fine bump adds micro-wrinkle. Gold (1.0, 0.72, 0.24), roughness 0.10–0.18. Tape seams are
  slightly rougher, with tie-down buttons and screws.
- Solar cells: triple-junction cells with cropped corners, cover-glass coat, finger lines,
  busbars, silver interconnects.
- Coated optical glass: violet on the terminal objective, green on the imager lenses, with inner
  elements and matte black barrels.
- Also black anodised metal, stainless and black-oxide fasteners, a coated niobium nozzle,
  and PTFE, Kapton and overbraided harness.

For the GLB and USDZ, the materials are converted to standard glTF metal/roughness. Small
tileable textures are generated for brushed metal, MLI and cells. The MLI creases, cells,
busbars and fasteners are real geometry, so they carry over. The micro-wrinkle bump,
edge wear and glass coatings are Cycles-only, so the web and Quick Look versions look simpler
than the renders.

## Lighting

A dark grey seamless sweep and the Poly Haven `studio_small_09` HDRI (CC0, low strength),
plus six area lights: off-axis key, fill, two rim strips, top, and a floor bounce hidden
from reflections. A soft front scrim and five large bounce cards
(hidden from the camera, light-linked to the MLI collection only) give the gold foil bright
things to reflect from every camera without washing out the solar cells. The backdrop and lights sit on
`Studio_Rig`, which the render script turns to face each camera, as on a product set. For the
underside view it is flipped and the floor hidden. View transform: AgX, Medium High Contrast,
exposure -0.25.

## Re-rendering

The Spark's Blender is 4.3.2 in the `daedyl-blender:4.3.2-arm64` container (CPU Cycles).
That build has no built-in denoiser and no USD exporter, so:

- **Denoising:** Intel Open Image Denoise 2.3.3 was built from source for ARM64. Each frame
  is rendered with albedo and normal passes, denoised with `oidnDenoise`, then saved through
  the AgX view.
- **USDZ:** `glb2usdz.py` converts the GLB with Pixar's `usd-core` Python package.

From the work folder on the Spark (`~/unwana-model`):

```bash
./run_blender.sh --factory-startup -P build_unwana.py -- $PWD/unwana.blend $PWD/assets/studio_small_09_2k.hdr
./final_renders.sh                                   # 10 views + 5 close-ups
python3 contact_sheet.py out/renders out/renders/unwana-contact-sheet.png 960
./run_blender.sh unwana.blend -P export_glb.py -- $PWD/out/unwana.glb $PWD/out/textures
python3 merge_clips.py out/unwana.glb out/unwana.glb Deploy
tools/usdvenv/bin/python glb2usdz.py out/unwana.glb out/unwana.usdz
./turntable.sh                                       # 72 frames + MP4
# one camera at any size:  ./run_blender.sh unwana.blend -P render_views.py -- <outdir> <w> <h> <samples> <Camera...>
```

`build_unwana.py` is the source of truth: change a dimension or material there and rebuild.
Inside Blender each part is a separate named object, so it can be edited by hand too.
Animate the deployment with the `Hinge_L_A/B` and `Hinge_R_A/B` empties (Z rotation).

## Render times (DGX Spark, 20 ARM cores, Cycles CPU)

| Output | Settings | Time per image |
| --- | --- | --- |
| 10 views | 3840x2160, 200 samples, adaptive, OIDN | 288–438 s (Bottom: 70 s, no floor) |
| Close-ups | 2560x1440, 256 samples, f/2.8–3.2 | 132–437 s |
| Preview | 1920x1080, 128 samples | about 60 s |

The close-up files are `closeup-optical-terminal`, `closeup-mli-seam`, `closeup-nozzle`,
`closeup-solar-hinge` and `closeup-imager`.

## Known limits

- The left and right views show each wing edge-on, as a thin line through the middle of the
  side. The reference side views omit the wings.
- The USDZ is static (deployed). The deploy animation is only in the GLB and the .blend. I have
  not opened it in Quick Look on an Apple device.
- No Gaussian-splatting version was made.
