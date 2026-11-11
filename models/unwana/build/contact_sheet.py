"""Assemble the 10 named views into a labelled contact sheet.  python3 contact_sheet.py <dir> <out.png> [tile_w]"""
import sys
from PIL import Image, ImageDraw, ImageFont
d, out = sys.argv[1], sys.argv[2]
tw = int(sys.argv[3]) if len(sys.argv) > 3 else 960
VIEWS = [("Front", "FRONT"), ("Rear", "REAR"), ("Left", "LEFT"), ("Right", "RIGHT"), ("Top", "TOP"),
         ("Bottom", "BOTTOM"), ("FrontLeftIso", "FRONT-LEFT ISO"), ("FrontRightIso", "FRONT-RIGHT ISO"),
         ("RearLeftIso", "REAR-LEFT ISO"), ("RearRightIso", "REAR-RIGHT ISO")]
th = tw * 9 // 16
pad, head, lab = tw // 60, tw // 9, tw // 24
W = 5 * tw + 6 * pad; H = head + 2 * (th + lab) + 3 * pad + lab
sheet = Image.new("RGB", (W, H), (22, 23, 25))
dr = ImageDraw.Draw(sheet)
def font(sz, bold=False):
    for f in (f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if bold else ''}.ttf",):
        try: return ImageFont.truetype(f, sz)
        except OSError: pass
    return ImageFont.load_default()
dr.text((pad, head * 0.22), "UNWANA  ·  10-VIEW CONTACT SHEET", fill=(235, 235, 235), font=font(int(head * 0.36), True))
dr.text((pad, head * 0.66), "Provisional visual model (Blender 4.3, Cycles). Dimensions are not engineering data.",
        fill=(150, 152, 156), font=font(int(head * 0.2)))
for i, (name, label) in enumerate(VIEWS):
    im = Image.open(f"{d}/{name}.png").convert("RGB").resize((tw, th), Image.LANCZOS)
    x = pad + (i % 5) * (tw + pad); y = head + pad + (i // 5) * (th + lab + pad)
    sheet.paste(im, (x, y))
    dr.text((x + 2, y + th + lab * 0.18), f"{i + 1:02d}  {label}", fill=(210, 210, 210), font=font(int(lab * 0.55), True))
sheet.save(out, optimize=True)
print("SHEET", out, sheet.size)
