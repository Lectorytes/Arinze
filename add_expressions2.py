import os, sys, shutil, json
from PIL import Image, ImageDraw, ImageChops, ImageFilter

# file name -> expression name used by Arinze
MAP = {
    "in_love": "worried", "inferno_rage": "inferno_rage", "irritated": "peeved",
    "skeptical": "skeptical", "sleeping_zs": "sleeping_zs", "sleepy_smile": "shocked",
}
FLAMES = ("inferno_rage",)
DEST = os.environ.get("ARINZE_DEST", os.path.expanduser("~/Arinze/assets"))
TARGET_R = 97.0
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
            if "inferno_rage.png" in files and "skeptical.png" in files:
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


def process(src_path, out_path, is_flame):
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
    if is_flame:
        r = bw / 2.0
        cy = y1 + 0.5 - r
    elif bw > bh:
        r = bw / 2.0
        cy = y0 + r
    else:
        r = bh / 2.0
        cy = (y0 + y1) / 2.0 + 0.5
    cut = r - 3.5
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
    s = TARGET_R / cut
    cy_out = CANVAS / 2.0
    if is_flame:
        fm = Image.new("L", (w, h), 0)
        fp = fm.load()
        px = im.load()
        for y in range(h):
            for x in range(w):
                if (y * w + x) in compset:
                    rr, gg, bb = px[x, y]
                    if rr > 180 and bb < 170 and rr - bb > 60:
                        fp[x, y] = 255
        fm = fm.filter(ImageFilter.GaussianBlur(0.7))
        alpha = ImageChops.lighter(alpha, fm)
        flame_h = max(1.0, cy - y0)
        s = min(s, (151.0 - 4.0) / flame_h)
        cy_out = max(CANVAS / 2.0, 4.0 + flame_h * s)
    rgba = im.convert("RGBA")
    rgba.putalpha(alpha)
    pre = rgba.convert("RGBa")
    out = pre.transform((CANVAS, CANVAS), Image.Transform.AFFINE,
                        (1 / s, 0, cx - (CANVAS / 2.0) / s, 0, 1 / s, cy - cy_out / s),
                        resample=Image.Resampling.BICUBIC)
    out.convert("RGBA").save(out_path)
    return cy_out - CANVAS / 2.0


def build_lids(dest, dy_map):
    # For every face, makes an "eyelid" patch: the eye area refilled with the orb's own colours.
    skip = ("idle_old",)
    files = [f for f in sorted(os.listdir(dest))
             if f.endswith(".png") and not f.startswith("lid_") and f[:-4] not in skip]
    rects = {}
    for f in files:
        name = f[:-4]
        face = Image.open(os.path.join(dest, f)).convert("RGBA")
        px = face.load()
        dy = int(round(dy_map.get(name, 0)))
        x0, x1 = 38, 212
        y0 = 92 + dy
        y1 = min(166 + dy, 238)
        w, h = x1 - x0, y1 - y0
        lid = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        lp = lid.load()
        for x in range(x0, x1):
            def darkest(rng):
                best = None
                for y in rng:
                    if y < 0 or y > 249:
                        continue
                    r, g, b, a = px[x, y]
                    if a < 200:
                        continue
                    lum = r * 3 + g * 6 + b
                    if best is None or lum < best[0]:
                        best = (lum, (r, g, b))
                return best[1] if best else None
            top = darkest(range(y0 - 1, y0 - 32, -1))
            bot = darkest(range(y1, y1 + 40))
            for y in range(y0, y1):
                a = px[x, y][3]
                if a == 0:
                    continue
                t = (y - y0) / float(max(1, h - 1))
                if top and bot:
                    col = tuple(int(top[i] * (1 - t) + bot[i] * t) for i in range(3))
                else:
                    col = top or bot or (10, 20, 70)
                lp[x - x0, y - y0] = (col[0], col[1], col[2], a)
        lid = lid.filter(ImageFilter.GaussianBlur(1.5))
        # feather the edges so the eyelid melts into the orb
        fade = Image.new("L", (w, h), 255)
        fpx = fade.load()
        for fx in range(w):
            ax = min(1.0, fx / 16.0, (w - 1 - fx) / 16.0)
            for fy in range(h):
                ay = min(1.0, fy / 6.0, (h - 1 - fy) / 8.0)
                fpx[fx, fy] = int(255 * ax * ay)
        lid.putalpha(ImageChops.multiply(lid.getchannel("A"), fade))
        lid.save(os.path.join(dest, "lid_" + name + ".png"))
        rects[name] = [x0, y0, w, h]
    with open(os.path.join(dest, "lids.json"), "w") as fh:
        json.dump(rects, fh)
    return len(files)


def main():
    src = find_source()
    if not src:
        raise SystemExit("Could not find the new expression images. Tell Claude where the folder is.")
    os.makedirs(DEST, exist_ok=True)
    print("Using images from:", src)
    dy_path = os.path.join(DEST, "eye_dy.json")
    try:
        dy_map = json.load(open(dy_path))
    except Exception:
        dy_map = {}
    done = 0
    for fname, key in MAP.items():
        p = os.path.join(src, fname + ".png")
        if not os.path.exists(p):
            print("MISSING:", fname + ".png")
            continue
        dy_map[key] = process(p, os.path.join(DEST, key + ".png"), fname in FLAMES)
        done += 1
    print("Added", done, "new expressions")
    alert = os.path.join(DEST, "alert.png")
    idle = os.path.join(DEST, "idle.png")
    if os.path.exists(alert):
        if not os.path.exists(os.path.join(DEST, "idle_old.png")) and os.path.exists(idle):
            shutil.copy(idle, os.path.join(DEST, "idle_old.png"))
        shutil.copy(alert, idle)
        print("Default pose set: open eyes, no mouth")
    json.dump(dy_map, open(dy_path, "w"))
    n = build_lids(DEST, dy_map)
    print("Blink eyelids built for", n, "faces")
    print("Done")


if __name__ == "__main__":
    main()
