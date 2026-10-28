import os, shutil

p = os.path.expanduser("~/Arinze/arinze_v10.py")
s = open(p, encoding="utf-8").read()
if "_small_box" in s:
    raise SystemExit("This patch is already applied. Nothing was written.")


def once(old):
    n = s.count(old)
    if n != 1:
        raise SystemExit("Could not patch (%s) found %d times. Nothing was written. Tell Claude."
                         % (old.strip()[:60], n))


def rep(old, new):
    global s
    once(old)
    s = s.replace(old, new)


def rep_between(start, end, new):
    # replaces everything from `start` up to (not including) `end`
    global s
    once(start)
    once(end)
    a, b = s.index(start), s.index(end)
    if b <= a:
        raise SystemExit("Could not patch (%s). Nothing was written. Tell Claude." % start.strip()[:60])
    s = s[:a] + new + s[b:]


# 1) two extra Accessibility tools, if this Mac has them
rep('MODEL = "hermes3:8b"\n',
    'try:\n'
    '    from ApplicationServices import AXUIElementCreateSystemWide, AXUIElementCopyElementAtPosition\n'
    'except Exception:\n'
    '    AXUIElementCreateSystemWide = AXUIElementCopyElementAtPosition = None\n\n'
    'MODEL = "hermes3:8b"\n')

# 2) a stronger way to find the text box you are typing in
rep_between("def focus_info(woken):", "def glow_path(", '''def _wake_app(ax_app, name):
    # asks the app to show its text boxes to Accessibility (browsers and Electron apps hide them otherwise)
    try:
        AXUIElementSetAttributeValue(ax_app, "AXManualAccessibility", True)
    except Exception:
        pass
    if re.search(r"chrome|chromium|brave|edge|arc|opera|vivaldi", name, re.I):
        try:
            AXUIElementSetAttributeValue(ax_app, "AXEnhancedUserInterface", True)
        except Exception:
            pass


def _caret_rect(el):
    rng = ax_get(el, "AXSelectedTextRange")
    if rng is None:
        return None
    try:
        err, b = AXUIElementCopyParameterizedAttributeValue(el, "AXBoundsForRange", rng, None)
        if err == 0 and b is not None:
            r = ax_rect(b)
            if r and r[3] > 0 and not (r[0] == 0 and r[1] == 0):
                return r
    except Exception:
        pass
    return None


def _small_box(box):
    # a text box, not a whole window
    return bool(box) and box[3] < 600 and box[2] * box[3] < 1500000


def focus_info(woken):
    # Where is the text you are typing? Asks macOS Accessibility for the text box and the caret.
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        pid = int(app.processIdentifier())
        if pid == os.getpid():
            return None
        name = str(app.localizedName() or "")
        ax_app = AXUIElementCreateApplication(pid)
        now = time.time()
        if AX_WAKE and now - woken.get(pid, 0.0) > 20.0:
            woken[pid] = now
            _wake_app(ax_app, name)
        els = [ax_get(ax_app, "AXFocusedUIElement")]
        if AXUIElementCreateSystemWide is not None:
            try:
                els.append(ax_get(AXUIElementCreateSystemWide(), "AXFocusedUIElement"))
            except Exception:
                pass
        fallback = None
        for el in els:
            if el is None:
                continue
            info = {"box": ax_frame(el), "caret": _caret_rect(el), "role": str(ax_get(el, "AXRole") or ""),
                    "app": name}
            if _small_box(info["box"]) or info["caret"]:
                return info
            if fallback is None:
                fallback = info
        return fallback or {"box": None, "caret": None, "role": "", "app": name}
    except Exception:
        return None


''')

# 3) the background loop: also tries the element under your last click, and prints what it sees
rep_between("    def ax_loop(self):", "    def danger(self, grow=0.0):", '''    def ax_loop(self):
        woken = {}
        last_log = None
        while True:
            time.sleep(0.25)
            if not self.typing:
                continue
            info = focus_info(woken)
            if info is not None and not (_small_box(info.get("box")) or info.get("caret")):
                cp = self.click_pt
                if (cp is not None and time.time() - self.click_t < 600
                        and AXUIElementCopyElementAtPosition is not None):
                    try:
                        err, el = AXUIElementCopyElementAtPosition(AXUIElementCreateSystemWide(),
                                                                   float(cp[0]), float(cp[1]), None)
                        if err == 0 and el is not None:
                            role = str(ax_get(el, "AXRole") or "")
                            fr = ax_frame(el)
                            if role in ("AXTextArea", "AXTextField", "AXComboBox", "AXSearchField") and _small_box(fr):
                                info["box"] = fr
                                info["role"] = role + " (under your last click)"
                    except Exception:
                        pass
            self.ax = (time.time(), info) if info else None
            if info is not None:
                b, c = info.get("box"), info.get("caret")
                line = "%s | %s | box=%s | caret=%s" % (
                    info.get("app"), info.get("role") or "?",
                    tuple(int(v) for v in b) if b else None, tuple(int(v) for v in c) if c else None)
                if line != last_log:
                    last_log = line
                    print("[Arinze] you are typing in " + line, flush=True)

''')

# 4) when he cannot find the text box, he keeps a much wider area around your last click clear
rep("            got = (kx - 220, ky - 140, kx + 220, ky + 140)\n",
    "            got = (kx - 430, ky - 170, kx + 430, ky + 170)\n")
rep("                got = (box[0] - 30, box[1] - 30, box[0] + box[2] + 30, box[1] + box[3] + 30)\n",
    "                got = (box[0] - 40, box[1] - 40, box[0] + box[2] + 40, box[1] + box[3] + 40)\n")
rep("            if box and box[2] * box[3] < 0.25 * area and box[3] < 600:\n",
    "            if _small_box(box):\n")

# 5) when he starts hiding from your typing he goes to the bottom corner away from your mouse,
#    not the bottom middle where most chat boxes are
rep("        spot = self.clear_spot(lambda x, y: abs(x - mid) + 3 * (floor - y), rows=2)\n"
    "        if spot is None:\n"
    "            spot = (mid, floor)\n",
    "        corner = (geo.left() + 10 if QCursor.pos().x() > geo.center().x()\n"
    "                  else geo.right() - self.width() - 10)\n"
    "        spot = self.clear_spot(lambda x, y: abs(x - corner) + 3 * (floor - y), rows=2)\n"
    "        if spot is None:\n"
    "            spot = (corner, floor)\n")

if not os.path.exists(p + ".before_typing"):
    shutil.copy(p, p + ".before_typing")
open(p, "w", encoding="utf-8").write(s)
print("Patched OK (backup: arinze_v10.py.before_typing). Restart Arinze with Arinze.command")
