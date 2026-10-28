import os, shutil

src = os.path.expanduser("~/Arinze/arinze_v9.py")
dst = os.path.expanduser("~/Arinze/arinze_v10.py")
brain = os.path.expanduser("~/Arinze/arinze_brain.py")

if not os.path.exists(brain):
    raise SystemExit("Put arinze_brain.py in ~/Arinze first.")
s = open(src, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        raise SystemExit("Could not patch (%s) found %d times. Nothing was written. Tell Claude."
                         % (old.strip()[:60], s.count(old)))
    s = s.replace(old, new)


# 1) load the brain
rep("import arinze_tools as tools\n",
    "import arinze_tools as tools\nimport arinze_brain\n")

# 2) create it once everything he needs exists
rep("        self.reminders = self.load_reminders()\n",
    "        self.reminders = self.load_reminders()\n"
    "        self.brain = arinze_brain.Brain(self, lambda: STATE[\"quiet\"], MODEL, URL)\n")

# 3) greetings that remember you (streaks, long absences, being poked yesterday)
rep('        self.set_expression("happy", 4.0)\n'
    '        geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())\n'
    '        self.bubble.show_text(hello + " " + line, geo)\n',
    '        hello, line = self.brain.greeting(hello, line)\n'
    '        self.set_expression("happy", 4.0)\n'
    '        geo = QRect(self.base.x(), self.base.y(), self.width(), self.height())\n'
    '        self.bubble.show_text(hello + " " + line, geo)\n')

# 4) his heartbeat
rep("        self.bubble.follow(int(self.hop), self.base.x(), self.base.y())\n",
    "        self.brain.tick(now)\n"
    "        self.bubble.follow(int(self.hop), self.base.x(), self.base.y())\n")

# 5) he remembers being poked
rep("        n = len(self.pokes)\n",
    "        n = len(self.pokes)\n        self.brain.on_poke(now)\n")

# 6) things you can say to him (what do you know about me, forget that, fun fact...)
rep('        self.busy = True\n        self.bubble.hide()\n        self.set_expression("thinking")\n',
    '        if self.brain.handle_command(text):\n            return\n'
    '        self.busy = True\n        self.bubble.hide()\n        self.set_expression("thinking")\n')

# 7) he knows you when he answers
rep('"messages": [{"role": "system", "content": SYSTEM}] + self.history})',
    '"messages": [{"role": "system", "content": SYSTEM + self.brain.context()}] + self.history})')

# 8) he learns from what you tell him
rep("        self.sig.reply.emit(data)\n",
    "        self.brain.learn_async(text, data)\n        self.sig.reply.emit(data)\n")

# 9) right-click menu
rep('        menu.addSeparator()\n        a_quit = menu.addAction("Quit Arinze")\n',
    '        menu.addSeparator()\n'
    '        a_fact = menu.addAction("Tell me a fun fact")\n'
    '        a_know = menu.addAction("What have you learned about me?")\n'
    '        menu.addSeparator()\n'
    '        a_quit = menu.addAction("Quit Arinze")\n')
rep("        elif chosen == a_quit:\n            QApplication.instance().quit()\n",
    "        elif chosen == a_fact:\n            QTimer.singleShot(0, self.brain.fun_fact_now)\n"
    "        elif chosen == a_know:\n            QTimer.singleShot(0, self.brain._tell_known)\n"
    "        elif chosen == a_quit:\n            QApplication.instance().quit()\n")

open(dst, "w", encoding="utf-8").write(s)
print("Created arinze_v10.py (your arinze_v9.py is untouched). Run:  python arinze_v10.py")
