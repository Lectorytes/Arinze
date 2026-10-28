from pathlib import Path

p = Path.home() / "Arinze" / "arinze_v10.py"
text = p.read_text(encoding="utf-8")

if "def on_charger_plugged" in text:
    print("Already added. Nothing to do.")
    raise SystemExit(0)

# 1) charge glow pixmap after rage_pix
old1 = "        self.rage_pix = tint\n        now = time.time()"
new1 = '''        self.rage_pix = tint
        charge = QPixmap(base.size())
        charge.setDevicePixelRatio(dpr)
        charge.fill(Qt.GlobalColor.transparent)
        cp = QPainter(charge)
        cgrad = QRadialGradient(SIZE / 2, SIZE / 2, SIZE / 2)
        cgrad.setColorAt(0.0, QColor(180, 255, 240, 255))
        cgrad.setColorAt(0.45, QColor(40, 220, 255, 255))
        cgrad.setColorAt(1.0, QColor(0, 120, 255, 220))
        cp.fillRect(0, 0, SIZE, SIZE, cgrad)
        cp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        cp.drawPixmap(0, 0, base)
        cp.end()
        self.charge_pix = charge
        now = time.time()'''
if old1 not in text:
    raise SystemExit("Could not find rage_pix block")
text = text.replace(old1, new1, 1)

# 2) state vars after self.rage = 0.0
old2 = "        self.rage = 0.0\n"
new2 = '''        self.rage = 0.0
        self.charge_glow = 0.0
        self.charge_until = 0.0
        self.power_ac = None
        self.next_power = time.time() + 2.0
'''
if old2 not in text:
    raise SystemExit("Could not find self.rage = 0.0")
text = text.replace(old2, new2, 1)

# 3) methods before check_battery
old3 = "    def check_battery(self, now):"
new3 = '''    def on_charger_plugged(self):
        now = time.time()
        self.charge_until = now + 3.8
        self.last_activity = now
        self.set_expression("happy", 4.0)
        self.start_bounce("excited")
        if not self.busy and not self.bubble.isVisible():
            geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())
            self.bubble.show_text(random.choice([
                "Power connected. Nice.",
                "Charging up!",
                "Ah, juice. Thank you.",
            ]), geo)

    def check_power_source(self, now):
        try:
            out = subprocess.run(
                ["pmset", "-g", "batt"],
                capture_output=True, text=True, timeout=2,
            ).stdout
        except Exception:
            return
        ac = "AC Power" in out
        if self.power_ac is None:
            self.power_ac = ac
            return
        if ac and not self.power_ac:
            self.on_charger_plugged()
        self.power_ac = ac

    def check_battery(self, now):'''
if old3 not in text:
    raise SystemExit("Could not find check_battery")
text = text.replace(old3, new3, 1)

# 4) call power check near battery check
old4 = '''            if now >= self.next_batt:
                self.next_batt = now + 90
                self.check_battery(now)'''
new4 = '''            if now >= self.next_batt:
                self.next_batt = now + 90
                self.check_battery(now)
            if now >= self.next_power:
                self.next_power = now + 2.0
                self.check_power_source(now)'''
if old4 not in text:
    raise SystemExit("Could not find next_batt block")
text = text.replace(old4, new4, 1)

# 5) charge glow fade next to rage
old5 = '''        if now < self.rage_until:
            self.rage = min(1.0, self.rage + dt * 4)
            self.shake = max(self.shake, 0.35)
        else:
            self.rage = max(0.0, self.rage - dt * 0.8)'''
new5 = '''        if now < self.rage_until:
            self.rage = min(1.0, self.rage + dt * 4)
            self.shake = max(self.shake, 0.35)
        else:
            self.rage = max(0.0, self.rage - dt * 0.8)
        if now < self.charge_until:
            self.charge_glow = min(1.0, self.charge_glow + dt * 3.5)
        else:
            self.charge_glow = max(0.0, self.charge_glow - dt * 1.2)'''
if old5 not in text:
    raise SystemExit("Could not find rage fade block")
text = text.replace(old5, new5, 1)

# 6) draw charge glow after rage draw
old6 = '''        if self.rage > 0.01:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setOpacity(self.rage * (0.78 + 0.22 * math.sin(self.t * 16)))
            p.drawPixmap(0, 0, self.rage_pix)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setOpacity(1.0)
        self.voice.paint_ring(p, SIZE)'''
new6 = '''        if self.rage > 0.01:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setOpacity(self.rage * (0.78 + 0.22 * math.sin(self.t * 16)))
            p.drawPixmap(0, 0, self.rage_pix)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setOpacity(1.0)
        if self.charge_glow > 0.01 and hasattr(self, "charge_pix"):
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setOpacity(self.charge_glow * (0.55 + 0.25 * math.sin(self.t * 7)))
            p.drawPixmap(0, 0, self.charge_pix)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setOpacity(1.0)
        self.voice.paint_ring(p, SIZE)'''
if old6 not in text:
    raise SystemExit("Could not find rage paint block")
text = text.replace(old6, new6, 1)

p.write_text(text, encoding="utf-8")
print("OK: charger animation added")