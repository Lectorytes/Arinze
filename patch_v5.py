src = open("arinze.py").read()


def rep(old, new):
    global src
    if src.count(old) != 1:
        raise SystemExit("Could not patch (" + old[:50].strip() + "). Tell Claude.")
    src = src.replace(old, new)


rep("import sys, os, math, json, time, threading, ctypes, random\n",
    "import sys, os, math, json, time, threading, ctypes, random, re, subprocess\n")
rep("from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QInputDialog\n",
    "from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QInputDialog, QMenu\n")
rep("from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID\n",
    "from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID\n"
    "from Quartz import (CGEventSourceSecondsSinceLastEventType, kCGEventSourceStateCombinedSessionState,\n"
    "                    kCGEventKeyDown, kCGAnyInputEventType)\n")

rep('''def jitter(lo, hi):
    if RASCAL <= 0:
        return 1e9
    return random.uniform(lo, hi) / RASCAL
''', r'''STATE = {"quiet": False}
REMIND_RE = re.compile(
    r"remind me (?:in|after)\s+(\d+(?:\.\d+)?)\s*(seconds?|secs?|minutes?|mins?|hours?|hrs?|s|m|h)\b\s*(?:to|about|that)?\s*(.*)",
    re.I)


def rascal():
    return 0.0 if STATE["quiet"] else RASCAL


def jitter(lo, hi):
    r = rascal()
    if r <= 0:
        return 1e9
    return random.uniform(lo, hi) / r


def parse_reminder(text):
    m = REMIND_RE.search(text)
    if not m:
        return None
    n = float(m.group(1))
    unit = m.group(2).lower()
    mult = 1 if unit.startswith("s") else (3600 if unit.startswith("h") else 60)
    what = m.group(3).strip(" .!?") or "your reminder"
    return n * mult, what


def friendly(secs):
    if secs < 90:
        return "%d seconds" % round(secs)
    if secs < 5400:
        return "%d minutes" % round(secs / 60.0)
    return "%.1f hours" % (secs / 3600.0)
''')

# state variables
rep("        self.seen_notif = set(notif_windows().keys())\n",
    '''        self.typing = False
        self.typing_home = None
        self.return_at = None
        self.no_type_until = 0.0
        self.last_key = 0.0
        self.look = 0.0
        self.in_dialog = False
        self.next_keycheck = 0.0
        self.next_slow = now + 1.0
        self.next_batt = now + 20.0
        self.last_batt_warn = 0.0
        self.next_break = now + 50 * 60
        self.reminders = self.load_reminders()
        # the eye area of his idle face, used to make his eyes look down at the keyboard
        self.band_idle = None
        if "idle" in self.lids:
            _, lx, ly, lw, lh = self.lids["idle"]
            bp = self.pix["idle"].copy(int(lx * dpr), int(ly * dpr), int(lw * dpr), int(lh * dpr))
            bp.setDevicePixelRatio(dpr)
            self.band_idle = bp
        self.seen_notif = set(notif_windows().keys())
''')
rep("        self.notif_timer.start(500)\n",
    "        self.notif_timer.start(500)\n        QTimer.singleShot(1500, self.greet)\n")

# new methods
rep("    def yawn_amount(self):\n", r'''    def key_seconds(self, kind):
        try:
            return float(CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateCombinedSessionState, kind))
        except Exception:
            return 9999.0

    def start_typing(self, now):
        self.typing = True
        self.return_at = None
        self.queue = []
        self.typing_home = QPoint(self.base.x(), self.base.y())
        self.set_expression("idle")
        geo = self.screen().availableGeometry()
        self.glide_to(geo.center().x() - self.width() / 2, geo.bottom() - self.height() - 6)

    def stop_typing(self, now):
        self.typing = False
        self.return_at = now + 1.5

    def nudge(self, text, face, bounce=True):
        self.last_activity = time.time()
        self.set_expression(face, 9.0)
        geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())
        self.bubble.show_text(text, geo)
        if bounce:
            self.start_bounce("notify")

    def greet(self):
        h = time.localtime().tm_hour
        hello = "Good morning!" if h < 12 else ("Good afternoon!" if h < 18 else "Good evening!")
        line = random.choice(["Miss me?", "Did you do anything fun without me?",
                              "Ready to cause some trouble?", "I'm awake. Mostly."])
        self.set_expression("happy", 4.0)
        geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())
        self.bubble.show_text(hello + " " + line, geo)
        self.start_bounce("play")

    def load_reminders(self):
        try:
            return json.load(open(os.path.expanduser("~/Arinze/reminders.json")))
        except Exception:
            return []

    def save_reminders(self):
        try:
            json.dump(self.reminders, open(os.path.expanduser("~/Arinze/reminders.json"), "w"))
        except Exception:
            pass

    def check_battery(self, now):
        try:
            out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=3).stdout
        except Exception:
            return
        m = re.search(r"(\d+)%", out)
        if not m:
            return
        pct = int(m.group(1))
        if "discharging" in out and pct <= 20 and now - self.last_batt_warn > 1800:
            self.last_batt_warn = now
            self.nudge("Battery is at %d%%. Find a charger?" % pct, "worried" if pct > 10 else "sad")

    def toggle_quiet(self):
        STATE["quiet"] = not STATE["quiet"]
        now = time.time()
        self.next_flicker = now + jitter(35, 90)
        self.next_wander = now + jitter(70, 160)
        self.next_sneak = now + jitter(300, 540)
        self.next_play = now + random.uniform(180, 360)
        msg = "Okay, I will behave." if STATE["quiet"] else "Rascal mode is back on!"
        self.set_expression("deadpan" if STATE["quiet"] else "evil_grin", 3.0)
        geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())
        self.bubble.show_text(msg, geo)

    def contextMenuEvent(self, e):
        menu = QMenu()
        a_talk = menu.addAction("Talk to Arinze")
        if STATE["quiet"]:
            a_quiet = menu.addAction("Quiet mode is ON (click to be a rascal again)")
        else:
            a_quiet = menu.addAction("Rascal mode is ON (click to make him quiet)")
        menu.addSeparator()
        a_quit = menu.addAction("Quit Arinze")
        try:
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
        chosen = menu.exec(e.globalPos())
        if chosen is None:
            return
        if chosen == a_talk:
            QTimer.singleShot(0, self.talk)
        elif chosen == a_quiet:
            self.toggle_quiet()
        elif chosen == a_quit:
            QApplication.instance().quit()

    def yawn_amount(self):
''')

# free state
rep('''        free = calm and self.cur == "idle" and still and self.yawn_t0 is None\n''',
    '''        free = (calm and self.cur == "idle" and still and self.yawn_t0 is None
                and not self.typing and self.return_at is None)\n''')

# replace the sleep + rascal + hover block
start = src.index("        # fall asleep after 10 minutes of being ignored\n")
end = src.index("        # yawn when bored\n")
new_block = r'''        # keyboard: when you start typing he comes down and looks at the keyboard
        if now >= self.next_keycheck:
            self.next_keycheck = now + 0.15
            if self.key_seconds(kCGEventKeyDown) < 1.2:
                self.last_key = now
                if (not self.typing and calm and not self.in_dialog and now >= self.no_type_until):
                    self.start_typing(now)
            if self.typing and now - self.last_key > 4.0:
                self.stop_typing(now)
        self.look += ((1.0 if self.typing else 0.0) - self.look) * min(1.0, dt * 6)
        if self.return_at is not None and not self.typing and now >= self.return_at:
            self.return_at = None
            if self.typing_home is not None:
                self.glide_to(self.typing_home.x(), self.typing_home.y())
                self.typing_home = None
            self.set_expression("cheerful", 2.0)
        # once a second: reminders, break nudges, battery
        if now >= self.next_slow:
            self.next_slow = now + 1.0
            due = [r for r in self.reminders if r["at"] <= time.time()]
            if due:
                self.reminders.remove(due[0])
                self.save_reminders()
                self.nudge("Reminder: " + due[0]["text"], "alert")
            if self.key_seconds(kCGAnyInputEventType) > 300:
                self.next_break = now + 50 * 60
            elif now >= self.next_break:
                self.next_break = now + 50 * 60
                self.nudge("You have been at it for about 50 minutes. Stretch and sip some water?", "pleading")
            if now >= self.next_batt:
                self.next_batt = now + 90
                self.check_battery(now)
        # fall asleep after 10 minutes of being ignored
        if (calm and idle_for > 600 and not self.typing
                and self.cur in ("idle", "happy", "big_smile", "cheerful", "bored")):
            self.set_expression("sleeping_zs")
        # --- rascal behaviour, only when left alone ---
        r_on = rascal() > 0
        if free and r_on and idle_for > 8 and now >= self.next_flicker:
            self.next_flicker = now + jitter(35, 90)
            face, hold, hop_chance = random.choice(FLICKERS)
            self.set_expression(face, hold)
            if random.random() < hop_chance:
                self.start_bounce("play")
        elif free and r_on and idle_for > 15 and now >= self.next_wander:
            self.next_wander = now + jitter(70, 160)
            self.wander()
        elif free and r_on and idle_for > 30 and now >= self.next_sneak:
            self.next_sneak = now + jitter(300, 540)
            self.sneak()
        elif free and idle_for > 150 and now >= self.next_bored:
            self.next_bored = now + random.uniform(150, 240)
            self.set_expression("bored", 8.0)
        elif free and r_on and idle_for > 20 and now >= self.next_play:
            self.next_play = now + random.uniform(240, 480)
            self.start_bounce("play")
            self.set_expression(random.choice(["happy", "big_smile", "cheerful"]), 3.0)
        # hovering the mouse over him for a moment makes him cheeky
        if (self.hover_t0 is not None and now - self.hover_t0 > 1.6 and now >= self.next_hover
                and calm and self.cur == "idle" and r_on):
            self.next_hover = now + 25
            self.hover_t0 = None
            self.set_expression(random.choice(HOVER_FACES), 2.0)
            if random.random() < 0.5:
                self.start_bounce("play")
'''
src = src[:start] + new_block + src[end:]

# look-down drawing
rep("        # eyelid (blink or yawn)\n", r'''        # looking down at the keyboard
        if (self.look > 0.02 and self.cur == "idle" and self.band_idle is not None
                and "idle" in self.lids):
            lp, lx, ly, lw, lh = self.lids["idle"]
            p.save()
            p.setClipRect(QRectF(lx, ly, lw, lh))
            p.drawPixmap(QPointF(lx, ly), lp)
            p.drawPixmap(QPointF(lx, ly + 7 * self.look), self.band_idle)
            p.restore()
        # eyelid (blink or yawn)
''')

# dragging him cancels the typing follow for a while
rep('''                self.queue = []
                self.glide = None
                self.base = gp - self.drag_off
''', '''                self.queue = []
                self.glide = None
                self.typing = False
                self.return_at = None
                self.no_type_until = time.time() + 60
                self.base = gp - self.drag_off
''')
rep('''        self.queue = []
        self.glide = None
        n = len(self.pokes)
''', '''        self.queue = []
        self.glide = None
        self.typing = False
        self.return_at = None
        self.no_type_until = now + 20
        n = len(self.pokes)
''')

# talking: reminders and typing guard
rep('''        text, ok = QInputDialog.getText(None, "Talk to Arinze", "Say something:")
        text = text.strip()
        if not ok or not text:
            self.set_expression("idle")
            return
        self.busy = True
''', '''        self.in_dialog = True
        try:
            text, ok = QInputDialog.getText(None, "Talk to Arinze", "Say something:")
        finally:
            self.in_dialog = False
        text = text.strip()
        if not ok or not text:
            self.set_expression("idle")
            return
        rem = parse_reminder(text)
        if rem:
            secs, what = rem
            self.reminders.append({"at": time.time() + secs, "text": what})
            self.save_reminders()
            self.set_expression("wink", 5.0)
            geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())
            self.bubble.show_text("Got it! I will remind you in %s: %s" % (friendly(secs), what), geo)
            return
        self.busy = True
''')

open("arinze.py", "w").write(src)
print("Patched OK")
