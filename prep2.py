import glob, os
from PIL import Image, ImageDraw
names = ["idle","happy","wink","pain","shy","thinking","alert","angry",
         "sad","sleeping","tired","working","annoyed","loved","confused"]
src = os.path.expanduser("~/Desktop/arinze_15_expressions_250px_png")
files = sorted(glob.glob(src + "/*.png"))
S = 4
for name, f in zip(names, files):
    im = Image.open(f).convert("RGB")
    w, h = im.size
    work = im.copy()
    for pt in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]:
        ImageDraw.floodfill(work, pt, (255,0,255), thresh=110)
    mask = Image.new("L", (w, h), 0)
    px = work.load()
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            if px[x, y] != (255, 0, 255):
                mp[x, y] = 255
    x0, y0, x1, y1 = mask.getbbox()
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = min(x1 - x0, y1 - y0) / 2 - 2
    big = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(big).ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=255)
    alpha = big.resize((w, h), Image.Resampling.LANCZOS)
    out = im.convert("RGBA")
    out.putalpha(alpha)
    out.save(os.path.expanduser("~/Arinze/assets/" + name + ".png"))
print("Done: 15 clean images saved")
