import os, shutil

main_p = os.path.expanduser("~/Arinze/arinze_v10.py")
brain_p = os.path.expanduser("~/Arinze/arinze_brain.py")
voice_p = os.path.expanduser("~/Arinze/arinze_voice.py")

if not os.path.exists(voice_p):
    raise SystemExit("Put arinze_voice.py in ~/Arinze first.")
src = {"main": open(main_p, encoding="utf-8").read(),
       "brain": open(brain_p, encoding="utf-8").read()}
if "arinze_voice" in src["main"]:
    raise SystemExit("The voice is already patched in. Nothing was written.")


def rep(which, old, new):
    n = src[which].count(old)
    if n != 1:
        raise SystemExit("Could not patch (%s) found %d times. Nothing was written. Tell Claude."
                         % (old.strip()[:60], n))
    src[which] = src[which].replace(old, new)


# ---------------------------------------------------------------- arinze_v10.py
# 1) load the voice
rep("main", "import arinze_brain\n", "import arinze_brain\nimport arinze_voice\n")

# 2) every speech bubble can be spoken out loud
rep("main", "class Bubble(QLabel):\n",
    "SPEAK = {\"fn\": None}      # set to his voice once he exists\n\n\nclass Bubble(QLabel):\n")
rep("main", "    def show_text(self, text, geo):\n        self.setText(text)\n",
    "    def show_text(self, text, geo):\n"
    "        fn = SPEAK[\"fn\"]\n"
    "        if fn is not None:\n"
    "            try:\n"
    "                fn(text)\n"
    "            except Exception:\n"
    "                pass\n"
    "        self.setText(text)\n")

# 3) create the voice right after the brain
rep("main", "        self.brain = arinze_brain.Brain(self, lambda: STATE[\"quiet\"], MODEL, URL)\n",
    "        self.brain = arinze_brain.Brain(self, lambda: STATE[\"quiet\"], MODEL, URL)\n"
    "        self.voice = arinze_voice.Voice(self, lambda: STATE[\"quiet\"])\n"
    "        SPEAK[\"fn\"] = self.voice.say_bubble\n")

# 4) one code path for \"something you said\", typed or spoken
old_chunk = (
    "        rem = parse_reminder(text)\n"
    "        if rem:\n"
    "            secs, what = rem\n"
    "            self.reminders.append({\"at\": time.time() + secs, \"text\": what})\n"
    "            self.save_reminders()\n"
    "            self.set_expression(\"wink\", 5.0)\n"
    "            geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())\n"
    "            self.bubble.show_text(\"Got it! I will remind you in %s: %s\" % (friendly(secs), what), geo)\n"
    "            return\n"
    "        if self.brain.handle_command(text):\n"
    "            return\n"
    "        self.busy = True\n"
    "        self.bubble.hide()\n"
    "        self.set_expression(\"thinking\")\n"
    "        threading.Thread(target=self.ask, args=(text,), daemon=True).start()\n")
rep("main", old_chunk, "        self.process(text)\n")
rep("main", "    def confirm_cb(self, text):\n",
    "    def process(self, text):\n"
    "        # what he does with something you said (typed or spoken)\n"
    "        self.voice.reply_next = time.time()\n"
    + old_chunk +
    "\n"
    "    def hear(self, text):\n"
    "        # something you said out loud (the voice calls this)\n"
    "        text = (text or \"\").strip()\n"
    "        if not text or self.busy:\n"
    "            return\n"
    "        self.last_activity = time.time()\n"
    "        self.rage_until = 0.0\n"
    "        self.dodge_until = 0.0\n"
    "        self.pokes = []\n"
    "        self.queue = []\n"
    "        self.glide = None\n"
    "        self.set_expression(\"alert\")\n"
    "        self.process(text)\n"
    "\n"
    "    def confirm_cb(self, text):\n")

# 5) reminders, battery warnings and other nudges are always spoken; so are answers
rep("main", "    def nudge(self, text, face, bounce=True):\n        self.last_activity = time.time()\n",
    "    def nudge(self, text, face, bounce=True):\n        self.last_activity = time.time()\n"
    "        self.voice.reply_next = time.time()\n")
rep("main", "        self.set_expression(expr, 8)\n",
    "        self.voice.reply_next = time.time()\n        self.set_expression(expr, 8)\n")

# 6) right-click menu
rep("main", "        a_know = menu.addAction(\"What have you learned about me?\")\n",
    "        a_know = menu.addAction(\"What have you learned about me?\")\n"
    "        menu.addSeparator()\n"
    "        a_listen = menu.addAction(\"Listen to me now\")\n"
    "        a_mic = menu.addAction(self.voice.mic_label())\n"
    "        a_vox = menu.addAction(self.voice.voice_label())\n")
rep("main", "        elif chosen == a_quit:\n            QApplication.instance().quit()\n",
    "        elif chosen == a_listen:\n            QTimer.singleShot(0, self.voice.listen_now)\n"
    "        elif chosen == a_mic:\n            QTimer.singleShot(0, self.voice.toggle_mic)\n"
    "        elif chosen == a_vox:\n            QTimer.singleShot(0, self.voice.toggle_voice)\n"
    "        elif chosen == a_quit:\n            QApplication.instance().quit()\n")

# 7) a soft ring while he is listening for you
rep("main", "\n    def enterEvent(self, e):\n",
    "        self.voice.paint_ring(p, SIZE)\n\n    def enterEvent(self, e):\n")

# ---------------------------------------------------------------- arinze_brain.py
# he does not butt in with fun facts while you are in a conversation or while he is talking
rep("brain", "        if now < w.rage_until or now < w.dodge_until or w.bubble.isVisible():\n            return False\n",
    "        if now < w.rage_until or now < w.dodge_until or w.bubble.isVisible():\n            return False\n"
    "        v = getattr(w, \"voice\", None)\n"
    "        if v is not None and (v.awake_now() or v.is_speaking()):\n            return False\n")

# ---------------------------------------------------------------- write (only if everything matched)
for p in (main_p, brain_p):
    if not os.path.exists(p + ".before_voice"):
        shutil.copy(p, p + ".before_voice")
open(main_p, "w", encoding="utf-8").write(src["main"])
open(brain_p, "w", encoding="utf-8").write(src["brain"])
print("Patched OK (backups: *.before_voice). Restart Arinze:  python3 arinze_v10.py")
