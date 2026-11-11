"""Side-by-side stills: Blender (Cycles) reference vs Gaussian splat from the same camera.

Run: python3 splat_compare.py <refs_dir> <splat_compare_dir> <out_dir> Cam1:slug1 [Cam2:slug2 ...]
The Blender reference (RGBA) is composited onto the same grey the splat was rendered over.
"""
import sys, os, json
from PIL import Image, ImageDraw, ImageFont

refs, spl, out = sys.argv[1:4]
os.makedirs(out, exist_ok=True)
BG = tuple(round(v * 255) for v in (0.235, 0.235, 0.245))

def font(sz, bold=False):
    try:
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf", sz)
    except OSError:
        return ImageFont.load_default()

for spec in sys.argv[4:]:
    cam, slug = spec.split(":")
    a = Image.open(os.path.join(refs, cam + ".png")).convert("RGBA")
    base = Image.new("RGBA", a.size, BG + (255,)); base.alpha_composite(a); a = base.convert("RGB")
    b = Image.open(os.path.join(spl, cam + ".png")).convert("RGB")
    W, H = a.size; bar = H // 12; gap = W // 120
    sheet = Image.new("RGB", (2 * W + gap, H + bar), (12, 14, 18))
    sheet.paste(a, (0, bar)); sheet.paste(b, (W + gap, bar))
    d = ImageDraw.Draw(sheet)
    for x, label, sub in ((0, "Blender (Cycles)", "path-traced mesh, PBR materials"),
                          (W + gap, "Gaussian splat", "trained from 175 Blender renders")):
        d.text((x + bar * 0.4, bar * 0.18), label, fill=(238, 241, 245), font=font(int(bar * 0.42), True))
        d.text((x + bar * 0.4, bar * 0.62), sub, fill=(154, 163, 175), font=font(int(bar * 0.24)))
    sheet.save(os.path.join(out, f"splat-compare-{slug}.png"), optimize=True)
    print("SHEET", slug)
