import sys, os, math, json, time, threading
import requests
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QFont
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QInputDialog

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
        '{"expression": "happy", "say": "Good morning! Ready when you are."} '
        "The expression must be exactly one of: " + ", ".join(NAMES) + ". "
        "Meanings: idle=neutral, happy=pleased, wink=playful, pain=ouch or surprised, "
        "shy=embarrassed or complimented, thinking=pondering, alert=listening, angry=mad, "
        "sad=sad, sleeping=sleepy, tired=weary, working=busy with a task, annoyed=irritated, "
        "loved=very affectionate, confused=does not understand.")

SYSTEM = load_system()

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
        self.move(x, y)
        self.show()
        self.raise_()
        self.hide_timer.start(max(4000, 90 * len(text)))

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
        self.cur = "idle"
        self.prev = "idle"
        self.fade = 1.0
        self.t = 0.0
        self.squash = 0.0
        self.shake = 0.0
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
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(16)
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 40, scr.bottom() - self.height() - 40)

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

    def tick(self):
        dt = 0.016
        self.t += dt
        if self.fade < 1.0:
            self.fade = min(1.0, self.fade + dt / 0.18)
        self.squash *= 0.9
        if abs(self.squash) < 0.004:
            self.squash = 0.0
        self.shake *= 0.94
        if self.shake < 0.02:
            self.shake = 0.0
        if (self.cur == "idle" and not self.busy and self.drag_off is None
                and time.time() - self.last_activity > 90):
            self.set_expression("sleeping")
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        sleeping = (self.cur == "sleeping")
        bob = math.sin(self.t * (1.0 if sleeping else 2.2)) * (2.0 if sleeping else 4.0)
        shake = math.sin(self.t * 70) * self.shake * 6
        p.translate(self.width() / 2 + shake, self.height() / 2 + bob)
        p.scale(1 + self.squash * 0.10, 1 - self.squash * 0.10)
        p.translate(-SIZE / 2, -SIZE / 2)
        if self.fade < 1.0:
            p.drawPixmap(0, 0, self.pix[self.prev])
            p.setOpacity(self.fade)
        p.drawPixmap(0, 0, self.pix[self.cur])

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
                self.move(gp - self.drag_off)

    def mouseReleaseEvent(self, e):
        if self.skip_release:
            self.skip_release = False
            self.drag_off = None
            return
        if self.drag_off is not None:
            if self.moved:
                if not self.busy:
                    self.set_expression("idle")
            elif not self.busy:
                self.poke()
        self.drag_off = None

    def mouseDoubleClickEvent(self, e):
        self.skip_release = True
        self.talk()

    def poke(self):
        self.last_activity = time.time()
        self.set_expression("angry", 2.2)
        self.shake = 1.0
        self.squash = 1.0

    def talk(self):
        if self.busy:
            return
        self.last_activity = time.time()
        self.set_expression("alert")
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
        expr, say = "idle", None
        if isinstance(data, dict):
            expr = str(data.get("expression", "idle"))
            say = data.get("say")
        self.set_expression(expr, 8)
        if say:
            self.bubble.show_text(str(say), self.frameGeometry())

app = QApplication(sys.argv)
w = Arinze()
w.show()
sys.exit(app.exec())
