import sys, os, math, json, time, threading, ctypes, random
import requests
import objc
from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QRect
from PyQt6.QtGui import QPixmap, QPainter, QFont, QColor, QRadialGradient
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QInputDialog
from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID

MODEL = "qwen2.5:3b"
URL = "http://localhost:11434/api/chat"
ASSETS = os.path.expanduser("~/Arinze/assets")
NAMES = ["idle","happy","wink","pain","shy","thinking","alert","angry",
         "sad","sleeping","tired","working","annoyed","loved","confused"]
SIZE = 150
PAD = 16


def load_system():
    try:
        persona = open(os.path.expanduser("~/Arinze/persona.txt"), encoding="utf-8").read().strip()
    except Exception:
        persona = "You are Arinze, a small glowing orb companion who lives on the user's Mac desktop."
    return (persona + "\n\n"
        "RULES: Keep replies under 25 words. Reply ONLY with JSON like this: "
        '{"expression": "happy", "say": "Good morning! Ready when you are.", "bounce": false} '
        "Set bounce to true ONLY when you are really excited or need to grab attention, otherwise false. "
        "The expression must be exactly one of: " + ", ".join(NAMES) + ". "
        "Meanings: idle=neutral, happy=pleased, wink=playful, pain=ouch or surprised, "
        "shy=embarrassed or complimented, thinking=pondering, alert=listening, angry=mad, "
        "sad=sad, sleeping=sleepy, tired=weary, working=busy with a task, annoyed=irritated, "
        "loved=very affectionate, confused=does not understand.")


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
        self.cur = "idle"
        self.prev = "idle"
        self.fade = 1.0
        self.t = 0.0
        self.squash = 0.0
        self.shake = 0.0
        self.hop = 0.0
        self.hop_v = 0.0
        self.next_hop = 0.0
        self.gap = 0.3
        self.queue = []
        self.next_play = time.time() + random.uniform(180, 360)
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
        self.last_activity = time.time()
        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(lambda: self.set_expression("idle"))
        self.sig = Signals()
        self.sig.reply.connect(self.on_reply)
        self.bubble = Bubble()
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 40, scr.bottom() - self.height() - 40)
        self.base = self.pos()
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
            self.fade = 0.0
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
        # fall asleep after 10 minutes of being ignored
        if calm and idle_for > 600 and self.cur in ("idle", "happy"):
            self.set_expression("sleeping")
        # rare playful burst when left alone for a while
        if (calm and idle_for > 20 and self.cur == "idle" and not self.queue
                and self.hop == 0 and self.hop_v == 0 and now >= self.next_play):
            self.next_play = now + random.uniform(240, 480)
            self.start_bounce("play")
            self.set_expression("happy", 3.0)
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
            self.move(self.base.x(), self.base.y() - int(self.hop))
            self.bubble.follow(int(self.hop))
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        sleeping = (self.cur == "sleeping")
        bob = math.sin(self.t * (1.0 if sleeping else 2.2)) * (2.0 if sleeping else 4.0)
        if self.hop > 0:
            bob = 0.0
        shake = math.sin(self.t * 70) * self.shake * 6
        pulse = 1.0 + 0.05 * self.rage * math.sin(self.t * 18)
        p.translate(self.width() / 2 + shake, self.height() / 2 + bob)
        p.scale((1 + self.squash * 0.10) * pulse, (1 - self.squash * 0.10) * pulse)
        p.translate(-SIZE / 2, -SIZE / 2)
        if self.fade < 1.0:
            p.drawPixmap(0, 0, self.pix[self.prev])
            p.setOpacity(self.fade)
        p.drawPixmap(0, 0, self.pix[self.cur])
        p.setOpacity(1.0)
        if self.rage > 0.01:
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            p.setOpacity(self.rage * (0.78 + 0.22 * math.sin(self.t * 16)))
            p.drawPixmap(0, 0, self.rage_pix)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setOpacity(1.0)

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
        if len(self.pokes) >= 4:
            self.rage_until = now + 6.0
            self.set_expression("angry", 6.0)
        else:
            self.set_expression("angry", 2.2)

    def talk(self):
        if self.busy:
            return
        self.last_activity = time.time()
        self.rage_until = 0.0
        self.pokes = []
        self.queue = []
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
