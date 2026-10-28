import os, sys
from PIL import Image, ImageDraw, ImageChops, ImageFilter

# file name -> expression name used by Arinze
MAP = {
    "annoyed": "irritated", "bashful": "bashful", "big_smile": "big_smile",
    "blushing_sassy": "sassy", "blushing": "pleading", "bored": "bored",
    "confused": "puzzled", "content": "content", "cool_sunglasses": "sunglasses",
    "cool": "cool", "crying": "crying", "deadpan": "deadpan",
    "determined": "determined", "devastated": "devastated", "dizzy": "cheerful",
    "evil_grin": "evil_grin", "fire_angry": "fire_angry", "flirty": "flirty",
    "frustrated": "frustrated", "furious": "furious",
}
DEST = os.environ.get("ARINZE_DEST", os.path.expanduser("~/Arinze/assets"))
TARGET_R = 97.0   # visible orb radius, same as the first 15 expressions
CANVAS = 250


def find_source():
    if len(sys.argv) > 1:
        return sys.argv[1]
    home = os.path.expanduser("~")
    for top in ("Desktop", "Downloads", "Documents"):
        for root, dirs, files in os.walk(os.path.join(home, top)):
            if "Arinze" in root.split(os.sep) or "node_modules" in root:
                dirs[:] = []
                continue
            if "bashful.png" in files and "evil_grin.png" in files:
                return root
    return None


def largest_component(mask, w, h):
    seen = bytearray(w * h)
    best = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if mask[i] and not seen[i]:
                comp, stack = [], [i]
                seen[i] = 1
                while stack:
                    j = stack.pop()
                    comp.append(j)
                    cx, cy = j % w, j // w
                    for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                        if 0 <= nx < w and 0 <= ny < h:
                            k = ny * w + nx
                            if mask[k] and not seen[k]:
                                seen[k] = 1
                                stack.append(k)
                if len(comp) > len(best):
                    best = comp
    return best


def process(src_path, out_path, is_fire):
    im = Image.open(src_path).convert("RGB")
    w, h = im.size
    work = im.copy()
    for pt in [(0, 0), (w-1, 0), (0, h-1), (w-1, h-1)]:
        ImageDraw.floodfill(work, pt, (255, 0, 255), thresh=110)
    wp = work.load()
    mask = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            if wp[x, y] != (255, 0, 255):
                mask[y * w + x] = 1
    comp = largest_component(mask, w, h)
    compset = set(comp)
    xs = [j % w for j in comp]
    ys = [j // w for j in comp]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    cx = (x0 + x1) / 2.0
    if is_fire:
        r = bw / 2.0
        cy = y1 + 0.5 - r
    elif bw > bh:
        r = bw / 2.0
        cy = y0 + r
    else:
        r = bh / 2.0
        cy = (y0 + y1) / 2.0 + 0.5
    cut = r - 3.5
    # close gaps where the original picture was cut off at the bottom
    ipx = im.load()
    for x in range(w):
        last = None
        for y in range(h):
            if mask[y * w + x] and (y * w + x) in compset:
                last = ipx[x, y]
            elif last is not None and y > cy and ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 < cut + 1:
                ipx[x, y] = last
    S = 4
    big = Image.new("L", (w * S, h * S), 0)
    ImageDraw.Draw(big).ellipse([(cx - cut) * S, (cy - cut) * S, (cx + cut) * S, (cy + cut) * S], fill=255)
    alpha = big.resize((w, h), Image.Resampling.LANCZOS)
    if is_fire:
        keep = set(comp)
        fm = Image.new("L", (w, h), 0)
        fp = fm.load()
        px = im.load()
        for y in range(h):
            for x in range(w):
                if (y * w + x) in keep:
                    rr, gg, bb = px[x, y]
                    if rr > 180 and bb < 170 and rr - bb > 60:
                        fp[x, y] = 255
        fm = fm.filter(ImageFilter.GaussianBlur(0.7))
        alpha = ImageChops.lighter(alpha, fm)
    rgba = im.convert("RGBA")
    rgba.putalpha(alpha)
    s = TARGET_R / cut
    pre = rgba.convert("RGBa")
    out = pre.transform((CANVAS, CANVAS), Image.Transform.AFFINE,
                        (1 / s, 0, cx - (CANVAS / 2.0) / s, 0, 1 / s, cy - (CANVAS / 2.0) / s),
                        resample=Image.Resampling.BICUBIC)
    out = out.convert("RGBA")
    out.save(out_path)


def main():
    src = find_source()
    if not src:
        raise SystemExit("Could not find your new expression images. Tell Claude where the folder is.")
    os.makedirs(DEST, exist_ok=True)
    print("Using images from:", src)
    done = 0
    for fname, key in MAP.items():
        p = os.path.join(src, fname + ".png")
        if not os.path.exists(p):
            print("MISSING:", fname + ".png")
            continue
        process(p, os.path.join(DEST, key + ".png"), fname == "fire_angry")
        done += 1
    print("Done: added", done, "new expressions")


main()
