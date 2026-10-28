import os
p = os.path.expanduser("~/Arinze/arinze_v10.py")
s = open(p, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit("Could not patch (%s) found %d times. Nothing was written. Tell Claude."
                         % (old.strip()[:60], s.count(old)))
    s = s.replace(old, new)


# the bubble may never leave the screen, even when he stands in a corner
rep("        x = geo.x() + (geo.width() - w) // 2\n"
    "        y = geo.y() - self.height() - 2\n"
    "        if y < 0:\n"
    "            y = geo.bottom() + 2\n",
    "        sc = QApplication.screenAt(geo.center()) or QApplication.primaryScreen()\n"
    "        self.bounds = sc.availableGeometry()\n"
    "        x = geo.x() + (geo.width() - w) // 2\n"
    "        y = geo.y() - self.height() - 2\n"
    "        if y < self.bounds.top() + 4:\n"
    "            y = geo.bottom() + 2\n"
    "        x = max(self.bounds.left() + 8, min(x, self.bounds.right() - w - 8))\n"
    "        y = max(self.bounds.top() + 4, min(y, self.bounds.bottom() - self.height() - 4))\n")

# and it stays on screen while he glides or hops
rep("            self.move(self.bx + sx, self.by + sy - dy)\n",
    "            nx, ny = self.bx + sx, self.by + sy - dy\n"
    "            b = getattr(self, \"bounds\", None)\n"
    "            if b is not None:\n"
    "                nx = max(b.left() + 8, min(nx, b.right() - self.width() - 8))\n"
    "                ny = max(b.top() + 4, min(ny, b.bottom() - self.height() - 4))\n"
    "            self.move(nx, ny)\n")

open(p, "w", encoding="utf-8").write(s)
print("Patched OK. Restart Arinze:  python3 arinze_v10.py")
