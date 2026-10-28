import os, shutil, json
import add_expressions2 as m

dest = m.DEST
old = os.path.join(dest, "idle_old.png")
if not os.path.exists(old):
    raise SystemExit("Could not find the old horizontal idle face (idle_old.png). Tell Claude.")
shutil.copy(old, os.path.join(dest, "idle.png"))
try:
    dy = json.load(open(os.path.join(dest, "eye_dy.json")))
except Exception:
    dy = {}
n = m.build_lids(dest, dy)
print("Done: idle is horizontal again and can blink. Eyelids rebuilt for", n, "faces")
