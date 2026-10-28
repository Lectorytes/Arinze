import os
p = os.path.expanduser("~/Arinze/arinze_v10.py")
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit("Could not patch (%s) found %d times. Nothing was written. Tell Claude."
                         % (old.strip()[:60], s.count(old)))
    s = s.replace(old, new)


rep("EYE_PUPIL = (6, 8, 40)",
    "PUPIL_ROUND = 1.0         # pupil shape: 0 = square, 0.5 = soft rounded square, 1 = round\n"
    "EYE_PUPIL = (6, 8, 40)")
rep("            p.drawRect(QRectF(cx - pw / 2.0 + ox, cy - ph / 2.0 + oy, pw, ph))\n",
    "            pr = min(pw, ph) / 2.0 * PUPIL_ROUND\n"
    "            p.drawRoundedRect(QRectF(cx - pw / 2.0 + ox, cy - ph / 2.0 + oy, pw, ph), pr, pr)\n")
open(p, "w", encoding="utf-8").write(s)
print("Patched OK. Restart Arinze:  python3 arinze_v10.py")
