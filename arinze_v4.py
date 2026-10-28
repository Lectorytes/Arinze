import sys, os, math, json, time, threading, ctypes, random
import requests
import objc
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRect, QRectF, QPointF, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QRadialGradient, QCursor, QPen, QPainterPath
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QInputDialog
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

MODEL = "qwen2.5:3b"
URL = "http://localhost:11434/api/chat"
ASSETS = os.path.expanduser("~/Arinze/assets")
NAMES = ["idle","happy","wink","pain","shy","thinking","alert","angry",
         "sad","sleeping","tired","working","annoyed","loved","confused",
         "irritated","bashful","big_smile","sassy","pleading","bored","puzzled",
         "content","sunglasses","cool","crying","deadpan","determined",
         "devastated","cheerful","evil_grin","fire_angry","flirty",
         "frustrated","furious",
         "worried","peeved","skeptical","sleeping_zs","shocked","inferno_rage"]
# faces with open eyes (these can blink)
BLINK_FACES = {"idle","alert","angry","annoyed","confused","irritated","pleading","bored",
               "puzzled","deadpan","determined","devastated","evil_grin","fire_angry",
               "inferno_rage","flirty","frustrated","furious","skeptical","sassy",
               "thinking","peeved","worried","shocked"}
ANGRY_FACES = {"angry","furious","fire_angry","inferno_rage","frustrated","peeved","determined"}
SIZE = 150
PAD = 16
K = SIZE / 250.0
YAWN_TIME = 2.6
# How cheeky he is when left alone. 0 = calm, 1 = normal, 2 = very cheeky.
RASCAL = 1.0
# (face, how long, chance of a little hop)
FLICKERS = [("wink", 1.6, 0.3), ("evil_grin", 2.2, 0.4), ("sassy", 2.0, 0.2),
            ("cool", 2.4, 0.2), ("sunglasses", 2.6, 0.3), ("skeptical", 2.0, 0.0),
            ("flirty", 1.8, 0.2), ("big_smile", 1.8, 0.5)]
HOVER_FACES = ["wink", "sassy", "evil_grin", "flirty", "cool"]


def jitter(lo, hi):
    if RASCAL <= 0:
        return 1e9
    return random.uniform(lo, hi) / RASCAL


def load_system():
    try:
        persona = open(os.path.expanduser("~/Arinze/persona.txt"), encoding="utf-8").read().strip()
    except Exception:
        persona = "You are Arinze, a small glowing orb companion who lives on the user's Mac desktop."
    return (persona + "\n\n"
        "You are a playful little rascal: cheeky and teasing, but never mean.\n"
        "RULES: Keep replies under 25 words. Reply ONLY with JSON like this: "
        '{"expression": "happy", "say": "Good morning! Ready when you are.", "bounce": false} '
        "Set bounce to true ONLY when you are really excited or need to grab attention, otherwise false. "
        "The expression must be exactly one of: " + ", ".join(NAMES) + ". "
        "Meanings: idle=neutral, happy=pleased, wink=playful, pain=ouch or startled, "
        "shy=embarrassed or complimented, thinking=pondering, alert=listening, angry=mad, "
        "sad=sad, sleeping=sleepy, tired=weary, working=busy with a task, annoyed=mildly annoyed, "
        "loved=very affectionate, confused=dizzy or overwhelmed, irritated=grumpy, "
        "bashful=shy and blushing, big_smile=laughing or very happy, sassy=sassy attitude, "
        "pleading=begging with sparkly eyes, bored=bored (you yawn), puzzled=curious or unsure, "
        "content=peaceful and satisfied, sunglasses=feeling super cool, cool=smug smirk, "
        "crying=crying hard, deadpan=unimpressed, determined=focused and resolute, "
        "devastated=heartbroken, cheerful=gently smiling, evil_grin=mischievous, "
        "fire_angry=blazing rage, flirty=teasing and flirty, frustrated=frustrated, "
        "furious=very angry, worried=anxious with sparkly worried eyes, peeved=side-eyeing annoyed, "
        "skeptical=doubtful with a raised brow, sleeping_zs=fast asleep, shocked=gasping in surprise, "
        "inferno_rage=maximum rage. Pick the face that best matches your feeling.")


SYSTEM = load_system()


def apply_float(widget):
    # Keeps the window above everything, on every desktop, even over full-screen apps.
    try:
        view = objc.objc_object(c_void_p=ctypes.c_void_p(int(widget.winId())))
        win = view.window()
        win.setLevel_(101)
        win.setCollectionBehavior_(1 | 16 | 64 | 256)
        win.setHidesOnDeactivate_(False)
    except Exception:
        pass


def notif_windows():
    # Looks for Notification Center windows currently on screen.
    out = {}
    try:
        info = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID) or []
        for wi in info:
            owner = str(wi.get("kCGWindowOwnerName", ""))
            if "notification" not in owner.lower():
                continue
            b = wi.get("kCGWindowBounds", {})
            out[int(wi.get("kCGWindowNumber", 0))] = (
                int(wi.get("kCGWindowLayer", 0)),
                int(b.get("Width", 0)), int(b.get("Height", 0)))
    except Exception:
        pass
    return out


def glow_path(p, path, rgb):
    # Draws a neon-style glowing line, like the lines in his face.
    for width, alpha in ((16, 35), (10, 80), (5, 255)):
        pen = QPen(QColor(rgb[0], rgb[1], rgb[2], alpha), width * K)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)


class Signals(QObject):
    reply = pyqtSignal(object)


class Bubble(QLabel):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet("background-color: rgba(20,20,45,235); color: white; border-radius: 12px;")
        self.setContentsMargins(12, 8, 12, 8)
        f = QFont()
        f.setPointSize(13)
        self.setFont(f)
        self.setWordWrap(True)
        self.bx = 0
        self.by = 0
        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_text(self, text, geo):
        self.setText(text)
        w = max(100, min(280, self.fontMetrics().horizontalAdvance(text) + 40))
        self.setFixedWidth(w)
        self.setFixedHeight(self.heightForWidth(w) + 6)
        x = geo.x() + (geo.width() - w) // 2
        y = geo.y() - self.height() - 2
        if y < 0:
            y = geo.bottom() + 2
        self.bx, self.by = x, y
        self.move(x, y)
        self.show()
        self.raise_()
        apply_float(self)
        self.hide_timer.start(max(4000, 90 * len(text)))

    def follow(self, dy):
        if self.isVisible():
            self.move(self.bx, self.by - dy)


class Arinze(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(SIZE + 2 * PAD, SIZE + 2 * PAD)
        dpr = self.devicePixelRatioF()
        self.pix = {}
        for n in NAMES:
            p = QPixmap(os.path.join(ASSETS, n + ".png"))
            if p.isNull():
                raise SystemExit("Missing image: " + n + ".png")
            p = p.scaled(int(SIZE * dpr), int(SIZE * dpr),
                         Qt.AspectRatioMode.KeepAspectRatio,
                         Qt.TransformationMode.SmoothTransformation)
            p.setDevicePixelRatio(dpr)
            self.pix[n] = p
        # eyelids, used for blinking and yawning
        self.lids = {}
        try:
            rects = json.load(open(os.path.join(ASSETS, "lids.json")))
            for n in BLINK_FACES:
                if n not in rects:
                    continue
                x, y, w, h = rects[n]
                lp = QPixmap(os.path.join(ASSETS, "lid_" + n + ".png"))
                if lp.isNull():
                    continue
                lp = lp.scaled(max(1, int(w * K * dpr)), max(1, int(h * K * dpr)),
                               Qt.AspectRatioMode.IgnoreAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
                lp.setDevicePixelRatio(dpr)
                self.lids[n] = (lp, x * K, y * K, w * K, h * K)
        except Exception:
            self.lids = {}
        # Fiery red glow, shaped exactly like the orb, used when he is furious
        base = self.pix["angry"]
        tint = QPixmap(base.size())
        tint.setDevicePixelRatio(dpr)
        tint.fill(Qt.GlobalColor.transparent)
        tp = QPainter(tint)
        grad = QRadialGradient(SIZE / 2, SIZE / 2, SIZE / 2)
        grad.setColorAt(0.0, QColor(255, 170, 0, 255))
        grad.setColorAt(0.55, QColor(255, 55, 0, 255))
        grad.setColorAt(1.0, QColor(210, 0, 0, 255))
        tp.fillRect(0, 0, SIZE, SIZE, grad)
        tp.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        tp.drawPixmap(0, 0, base)
        tp.end()
        self.rage_pix = tint
        now = time.time()
        self.cur = "idle"
        self.prev = "idle"
        self.cur_since = now
        self.fade = 1.0
        self.t = 0.0
        self.squash = 0.0
        self.shake = 0.0
        self.hop = 0.0
        self.hop_v = 0.0
        self.next_hop = 0.0
        self.gap = 0.3
        self.queue = []
        self.glide = None
        self.lid = 0.0
        self.blink_t0 = None
        self.next_blink = now + random.uniform(2.0, 5.0)
        self.yawn_t0 = None
        self.yawned = False
        self.hover_t0 = None
        self.next_hover = 0.0
        self.next_flicker = now + jitter(35, 90)
        self.next_wander = now + jitter(70, 160)
        self.next_sneak = now + jitter(300, 540)
        self.next_bored = now + random.uniform(150, 240)
        self.next_play = now + random.uniform(180, 360)
        self.last_notif = 0.0
        self.pokes = []
        self.rage_until = 0.0
        self.rage = 0.0
        self.drag_off = None
        self.press_pos = None
        self.moved = False
        self.skip_release = False
        self.busy = False
        self.history = []
        self.last_activity = now
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(lambda: self.set_expression("idle"))
        self.sig = Signals()
        self.sig.reply.connect(self.on_reply)
        self.bubble = Bubble()
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 40, scr.bottom() - self.height() - 40)
        self.base = self.pos()
        self.setMouseTracking(True)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        self.seen_notif = set(notif_windows().keys())
        self.notif_timer = QTimer(self)
        self.notif_timer.timeout.connect(self.check_notifications)
        self.notif_timer.start(500)

    def set_expression(self, name, hold=None):
        if name not in self.pix:
            name = "idle"
        if name != self.cur:
            self.prev = self.cur
            self.cur = name
            self.cur_since = time.time()
            self.fade = 0.0
            self.yawned = False
            if name != "bored":
                self.yawn_t0 = None
        if hold:
            self.hold_timer.start(int(hold * 1000))
        else:
            self.hold_timer.stop()

    def start_bounce(self, kind):
        # Each hop gets its own random height and its own pause afterwards.
        if kind == "notify":
            n = random.randint(3, 4)
            lo, hi, glo, ghi = 520, 720, 0.12, 0.30
        elif kind == "excited":
            n = random.randint(3, 5)
            lo, hi, glo, ghi = 400, 700, 0.10, 0.40
        else:
            n = random.randint(2, 3)
            lo, hi, glo, ghi = 300, 520, 0.25, 0.70
        q = [(random.uniform(lo, hi), random.uniform(glo, ghi)) for _ in range(n)]
        if random.random() < 0.4:
            q[-1] = (q[-1][0] * 1.2, q[-1][1])
        self.queue = q

    def check_notifications(self):
        cur = notif_windows()
        new = [wid for wid in cur if wid not in self.seen_notif]
        self.seen_notif = set(cur.keys())
        now = time.time()
        for wid in new:
            layer, wd, ht = cur[wid]
            print("[Arinze] new Notification Center window: layer=%d size=%dx%d" % (layer, wd, ht), flush=True)
            if layer > 0 and 40 < ht < 260 and wd < 700 and now - self.last_notif > 2:
                self.last_notif = now
                print("[Arinze] notification detected -> bounce", flush=True)
                self.set_expression("alert", 3.5)
                self.start_bounce("notify")

    def glide_to(self, x, y):
        geo = self.screen().availableGeometry()
        x = int(max(geo.left() + 10, min(x, geo.right() - self.width() - 10)))
        y = int(max(geo.top() + 70, min(y, geo.bottom() - self.height() - 10)))
        dist = math.hypot(x - self.base.x(), y - self.base.y())
        if dist < 40:
            return False
        self.glide = (self.base.x(), self.base.y(), x, y, time.time(), max(0.8, dist / 380.0))
        self.bubble.hide()
        return True

    def wander(self):
        c = QCursor.pos()
        for _ in range(10):
            ang = random.uniform(0, 2 * math.pi)
            rad = random.uniform(150, 340)
            x = self.base.x() + math.cos(ang) * rad
            y = self.base.y() + math.sin(ang) * rad * 0.6
            if math.hypot(x + self.width() / 2 - c.x(), y + self.height() / 2 - c.y()) < 170:
                continue
            if self.glide_to(x, y):
                return True
        return False

    def sneak(self):
        # Sneaks up near the mouse cursor (never on top of it) with a mischievous grin.
        c = QCursor.pos()
        cx = self.base.x() + self.width() / 2
        cy = self.base.y() + self.height() / 2
        dx, dy = cx - c.x(), cy - c.y()
        d = math.hypot(dx, dy) or 1.0
        tx = c.x() + dx / d * 210 - self.width() / 2
        ty = c.y() + dy / d * 210 - self.height() / 2
        self.glide_to(tx, ty)
        self.set_expression("evil_grin", 3.5)

    def yawn_amount(self):
        if self.yawn_t0 is None:
            return 0.0
        u = (time.time() - self.yawn_t0) / YAWN_TIME
        if u < 0.25:
            return max(0.0, u / 0.25)
        if u < 0.7:
            return 1.0
        return max(0.0, (1.0 - u) / 0.3)

    def tick(self):
        dt = 0.016
        now = time.time()
        self.t += dt
        if self.fade < 1.0:
            self.fade = min(1.0, self.fade + dt / 0.18)
        self.squash *= 0.9
        if abs(self.squash) < 0.004:
            self.squash = 0.0
        self.shake *= 0.94
        if self.shake < 0.02:
            self.shake = 0.0
        # fiery rage
        if now < self.rage_until:
            self.rage = min(1.0, self.rage + dt * 4)
            self.shake = max(self.shake, 0.35)
        else:
            self.rage = max(0.0, self.rage - dt * 0.8)
        idle_for = now - self.last_activity
        calm = (not self.busy and self.drag_off is None and now >= self.rage_until)
        can_hop = (self.drag_off is None and now >= self.rage_until)
        still = (self.hop == 0 and self.hop_v == 0 and self.glide is None and not self.queue)
        free = calm and self.cur == "idle" and still and self.yawn_t0 is None
        # fall asleep after 10 minutes of being ignored
        if calm and idle_for > 600 and self.cur in ("idle", "happy", "big_smile", "cheerful", "bored"):
            self.set_expression("sleeping_zs")
        # --- rascal behaviour, only when left alone ---
        if free and idle_for > 8 and now >= self.next_flicker:
            self.next_flicker = now + jitter(35, 90)
            face, hold, hop_chance = random.choice(FLICKERS)
            self.set_expression(face, hold)
            if random.random() < hop_chance:
                self.start_bounce("play")
        elif free and idle_for > 15 and now >= self.next_wander:
            self.next_wander = now + jitter(70, 160)
            self.wander()
        elif free and idle_for > 30 and now >= self.next_sneak:
            self.next_sneak = now + jitter(300, 540)
            self.sneak()
        elif free and idle_for > 150 and now >= self.next_bored:
            self.next_bored = now + random.uniform(150, 240)
            self.set_expression("bored", 8.0)
        elif (free and idle_for > 20 and now >= self.next_play and RASCAL > 0):
            self.next_play = now + random.uniform(240, 480)
            self.start_bounce("play")
            self.set_expression(random.choice(["happy", "big_smile", "cheerful"]), 3.0)
        # hovering the mouse over him for a moment makes him cheeky
        if (self.hover_t0 is not None and now - self.hover_t0 > 1.6 and now >= self.next_hover
                and calm and self.cur == "idle" and RASCAL > 0):
            self.next_hover = now + 25
            self.hover_t0 = None
            self.set_expression(random.choice(HOVER_FACES), 2.0)
            if random.random() < 0.5:
                self.start_bounce("play")
        # yawn when bored
        if (self.cur == "bored" and not self.yawned and self.yawn_t0 is None
                and now - self.cur_since > 1.3 and "bored" in self.lids and self.blink_t0 is None):
            self.yawn_t0 = now
            self.yawned = True
        # random blinking, in any open-eyed face (even angry ones)
        if self.blink_t0 is None and self.yawn_t0 is None and now >= self.next_blink:
            if self.cur in BLINK_FACES and self.cur in self.lids and self.fade >= 1.0:
                self.blink_t0 = now
                if random.random() < 0.2:
                    self.next_blink = now + 0.3
                elif self.cur in ANGRY_FACES:
                    self.next_blink = now + random.uniform(3.5, 9.0)
                else:
                    self.next_blink = now + random.uniform(2.2, 6.5)
            else:
                self.next_blink = now + 0.8
        if self.yawn_t0 is not None:
            u = (now - self.yawn_t0) / YAWN_TIME
            if u >= 1.0 or self.cur != "bored":
                self.yawn_t0 = None
                self.lid = 0.0
            else:
                self.lid = min(1.0, u / 0.12, (1.0 - u) / 0.12)
        elif self.blink_t0 is not None:
            d = now - self.blink_t0
            if d < 0.06:
                self.lid = d / 0.06
            elif d < 0.10:
                self.lid = 1.0
            elif d < 0.17:
                self.lid = 1.0 - (d - 0.10) / 0.07
            else:
                self.blink_t0 = None
                self.lid = 0.0
        else:
            self.lid = 0.0
        # gliding across the screen
        if self.glide is not None:
            sx, sy, ex, ey, t0, dur = self.glide
            p = (now - t0) / dur
            if p >= 1.0:
                self.base = QPoint(ex, ey)
                self.glide = None
            else:
                e = p * p * (3 - 2 * p)
                self.base = QPoint(int(sx + (ex - sx) * e), int(sy + (ey - sy) * e))
        # launch the next queued hop
        if (self.queue and can_hop and self.hop == 0 and self.hop_v == 0
                and now >= self.next_hop):
            v0, gap = self.queue.pop(0)
            self.hop_v = v0
            self.gap = gap
        if self.hop > 0 or self.hop_v != 0:
            self.hop_v -= 2600.0 * dt
            self.hop += self.hop_v * dt
            if self.hop <= 0:
                if self.hop_v < -150:
                    self.squash = 0.8
                self.hop = 0.0
                self.hop_v = 0.0
                self.next_hop = now + self.gap
        tx, ty = self.base.x(), self.base.y() - int(self.hop)
        if self.x() != tx or self.y() != ty:
            self.move(tx, ty)
        self.bubble.follow(int(self.hop))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        sleeping = self.cur in ("sleeping", "sleeping_zs")
        bob = math.sin(self.t * (1.0 if sleeping else 2.2)) * (2.0 if sleeping else 4.0)
        if self.hop > 0 or self.glide is not None:
            bob = 0.0
        ym = self.yawn_amount()
        shake = math.sin(self.t * 70) * self.shake * 6
        pulse = 1.0 + 0.05 * self.rage * math.sin(self.t * 18)
        p.translate(self.width() / 2 + shake, self.height() / 2 + bob - 3 * ym)
        p.scale((1 + self.squash * 0.10) * pulse, (1 - self.squash * 0.10 + 0.05 * ym) * pulse)
        p.translate(-SIZE / 2, -SIZE / 2)
        if self.fade < 1.0:
            p.drawPixmap(0, 0, self.pix[self.prev])
            p.setOpacity(self.fade)
        p.drawPixmap(0, 0, self.pix[self.cur])
        p.setOpacity(1.0)
        # eyelid (blink or yawn)
        if self.lid > 0.01 and self.cur in self.lids:
            lp, lx, ly, lw, lh = self.lids[self.cur]
            p.save()
            p.setClipRect(QRectF(lx, ly, lw, lh * min(1.0, self.lid)))
            p.drawPixmap(QPointF(lx, ly), lp)
            p.restore()
        # yawn: closed happy eyes and a big open mouth
        if self.yawn_t0 is not None:
            col = (150, 210, 255)
            if self.lid > 0.95:
                eyes = QPainterPath()
                eyes.moveTo(70 * K, 128 * K)
                eyes.quadTo(85 * K, 141 * K, 100 * K, 128 * K)
                eyes.moveTo(150 * K, 128 * K)
                eyes.quadTo(165 * K, 141 * K, 180 * K, 128 * K)
                glow_path(p, eyes, col)
            if ym > 0.03:
                mouth = QPainterPath()
                mouth.addEllipse(QPointF(125 * K, 166 * K), 18 * K * ym, 27 * K * ym)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(6, 8, 40, 235))
                p.drawPath(mouth)
                p.setBrush(Qt.BrushStyle.NoBrush)
                glow_path(p, mouth, col)
        if self.rage > 0.01:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setOpacity(self.rage * (0.78 + 0.22 * math.sin(self.t * 16)))
            p.drawPixmap(0, 0, self.rage_pix)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setOpacity(1.0)

    def enterEvent(self, e):
        self.hover_t0 = time.time()

    def leaveEvent(self, e):
        self.hover_t0 = None

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            gp = e.globalPosition().toPoint()
            self.drag_off = gp - self.frameGeometry().topLeft()
            self.press_pos = gp
            self.moved = False

    def mouseMoveEvent(self, e):
        if self.drag_off is not None and bool(e.buttons() & Qt.MouseButton.LeftButton):
            gp = e.globalPosition().toPoint()
            if not self.moved and (gp - self.press_pos).manhattanLength() > 6:
                self.moved = True
                self.bubble.hide()
                self.last_activity = time.time()
                if not self.busy:
                    self.set_expression("alert")
            if self.moved:
                self.hop = 0.0
                self.hop_v = 0.0
                self.queue = []
                self.glide = None
                self.base = gp - self.drag_off
                self.move(self.base)

    def mouseReleaseEvent(self, e):
        if self.skip_release:
            self.skip_release = False
            self.drag_off = None
            return
        if self.drag_off is not None:
            if self.moved:
                self.last_activity = time.time()
                if not self.busy:
                    self.set_expression("idle")
            elif not self.busy:
                self.poke()
        self.drag_off = None

    def mouseDoubleClickEvent(self, e):
        self.skip_release = True
        self.talk()

    def poke(self):
        now = time.time()
        self.last_activity = now
        self.pokes = [x for x in self.pokes if now - x < 6.0] + [now]
        self.shake = 1.0
        self.squash = 1.0
        self.queue = []
        self.glide = None
        n = len(self.pokes)
        if n >= 6:
            self.rage_until = now + 6.0
            self.set_expression("inferno_rage", 6.0)
        elif n >= 4:
            self.rage_until = now + 6.0
            self.set_expression("fire_angry", 6.0)
        elif n == 3:
            self.set_expression("furious", 2.5)
        elif n == 2:
            self.set_expression("angry", 2.2)
        else:
            self.set_expression("irritated", 2.2)

    def talk(self):
        if self.busy:
            return
        self.last_activity = time.time()
        self.rage_until = 0.0
        self.pokes = []
        self.queue = []
        self.glide = None
        self.set_expression("alert")
        try:
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
        text, ok = QInputDialog.getText(None, "Talk to Arinze", "Say something:")
        text = text.strip()
        if not ok or not text:
            self.set_expression("idle")
            return
        self.busy = True
        self.bubble.hide()
        self.set_expression("thinking")
        threading.Thread(target=self.ask, args=(text,), daemon=True).start()

    def ask(self, text):
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-8:]
        try:
            r = requests.post(URL, timeout=180, json={
                "model": MODEL, "stream": False, "format": "json",
                "messages": [{"role": "system", "content": SYSTEM}] + self.history})
            content = r.json()["message"]["content"]
            data = json.loads(content)
            self.history.append({"role": "assistant", "content": content})
        except Exception:
            data = {"expression": "confused",
                    "say": "My brain is not answering. Is Ollama open?"}
        self.sig.reply.emit(data)

    def on_reply(self, data):
        self.busy = False
        self.last_activity = time.time()
        expr, say, bounce = "idle", None, False
        if isinstance(data, dict):
            expr = str(data.get("expression", "idle"))
            say = data.get("say")
            bounce = str(data.get("bounce", False)).lower() == "true"
        self.set_expression(expr, 8)
        if say:
            geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())
            self.bubble.show_text(str(say), geo)
        if bounce:
            self.start_bounce("excited")


app = QApplication(sys.argv)
try:
    NSApplication.sharedApplication().setActivationPolicy_(NSApplicationActivationPolicyAccessory)
except Exception:
    pass
w = Arinze()
w.show()
apply_float(w)
QTimer.singleShot(400, lambda: apply_float(w))
keep = QTimer()
keep.timeout.connect(lambda: apply_float(w))
keep.start(2000)
sys.exit(app.exec())
