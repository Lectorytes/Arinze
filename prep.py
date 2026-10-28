import glob, os
from PIL import Image, ImageDraw
names = ["idle","happy","wink","pain","shy","thinking","alert","angry",
         "sad","sleeping","tired","working","annoyed","loved","confused"]
src = os.path.expanduser("~/Desktop/arinze_15_expressions_250px_png")
files = sorted(glob.glob(src + "/*.png"))
print("Found", len(files), "images")
if len(files) != 15:
    raise SystemExit("Expected 15 images, please tell Claude what you see above")
for name, f in zip(names, files):
    im = Image.open(f).convert("RGBA")
    w, h = im.size
    for pt in [(0,0),(w-1,0),(0,h-1),(w-1,h-1)]:
        ImageDraw.floodfill(im, pt, (255,255,255,0), thresh=45)
    im.save(os.path.expanduser("~/Arinze/assets/" + name + ".png"))
print("Done: 15 transparent images saved")
