"""Arinze's voice: he talks out loud, listens for his name, and keeps listening for a while.

Everything runs on your Mac. Your audio is never saved and never leaves the computer.

How it works
  * Talking:    a natural offline voice (Kokoro). If it is not installed he falls back to the
                built-in macOS `say` voice. Try the voices with:  python3 arinze_voice.py --audition
  * Listening:  your mic is cut into phrases, and each phrase is turned into text by Whisper
                (faster-whisper, running on the CPU).
  * Wake word:  say "Arinze" (or "Hey Arinze, play some music"). He then keeps listening for
                window_sec seconds, so you do not need to say his name again.
  * Barge-in:   if you start talking while he talks, he stops and listens.

Settings: ~/Arinze/voice_settings.json (created on first run, re-read automatically).

Things you can say (after "Arinze", or any time during a conversation):
  stop / quiet                    he stops talking
  that's all / stop listening     closes the conversation until you say "Arinze" again
  repeat that                     he says his last line again
  speak faster / slower           changes his speed (remembered)
  change voice to Daniel          changes his voice (remembered)   |   what voices do you have
  mute your voice / turn on your voice
  mute the mic                    stops listening (right-click him to turn it back on)
  set a timer for 5 minutes       uses your reminders
"""
import os, re, json, time, queue, threading, subprocess, difflib, collections, atexit, math, random, sys

from PyQt6.QtCore import QObject, QTimer, QRect, QPointF, Qt, pyqtSignal

try:
    from AppKit import NSWorkspace
except Exception:
    NSWorkspace = None

HOME = os.path.expanduser("~/Arinze")
SETTINGS_PATH = os.path.join(HOME, "voice_settings.json")

DEFAULTS = {
    "enabled": True,              # he speaks out loud
    "listen": True,               # the mic is on and he waits for his name
    "engine": "kokoro",           # "kokoro" = natural voice, "say" = the basic Mac voice
    "kokoro_voice": "af_heart",   # try:  python3 arinze_voice.py --audition   (af_=American female, am_=male, bf_/bm_=British)
    "kokoro_speed": 1.0,          # 0.7 slow ... 1.4 fast
    "kokoro_model": "~/Arinze/voices/kokoro-v1.0.onnx",
    "kokoro_voices": "~/Arinze/voices/voices-v1.0.bin",
    "character": True,            # his speed follows his mood (slower when sad, quicker when excited)
    "filler_chance": 0.3,         # how often he starts with a little "hmm," or "oh," (0 = never, 1 = always)
    "voice": "Samantha",          # only for engine "say": any voice from  say -v '?'
    "rate": 185,                  # only for engine "say": words per minute
    "window_sec": 300,            # how long he keeps listening after you call him (5 minutes)
    "sliding_window": True,       # True: every exchange restarts the 5 minutes. False: a hard 5 minutes
    "stt_model": "small.en",      # tiny.en (fastest) / base.en / small.en (best for his name) / small (many languages)
    "language": "en",             # "en", or null to auto-detect (needs a multilingual model such as "small")
    "stt_beam": 5,                # how hard he tries to understand you (1 = fastest, 5 = more accurate)
    "stt_threads": 3,             # CPU threads for listening (fewer = smoother animation)
    "show_heard": True,           # print what he heard in the Terminal, to help tune things
    "question_window_sec": 30,    # after he asks you something he listens this long for your answer, no name needed
    "sensitivity": 1.0,           # higher = hears quieter speech, lower = ignores more noise
    "end_silence_ms": 700,        # how long you must pause before he treats it as the end of a phrase
    "barge_in": True,             # he stops talking when you start talking
    "ack_phrase": "Yes?",         # what he says when you only say his name ("" = a soft chime instead)
    "speak_chatter": True,        # also say his fun facts, greetings and remarks out loud
    "quiet_apps": ["zoom.us", "FaceTime", "Microsoft Teams", "Webex"],  # silent and deaf while one of these is in front
    "input_device": None,         # a mic name or number from  python3 -m sounddevice  (null = system default)
    "auto_builtin_mic": True,     # if the default mic is AirPods or another Bluetooth set, use the Mac's own mic
                                  # instead (a Bluetooth mic forces the headphones into low-quality, crackly sound)
    "max_spoken_chars": 400,      # longest thing he will say in one go
    # the little listening bars next to his ears (units are on his 250 x 250 drawing; centre is 125, 125)
    "bars_sides": "both",         # "both", "left" or "right"
    "bars_x": 105.0,              # how far from his centre the first bar sits (his body ends at about 96). Bigger = further out
    "bars_y": 128.0,              # how high the bars sit (his ear height). Bigger = lower
    "bars_gap": 6.0,              # space between the three bars
    "bars_min": 4.0,              # shortest a bar gets
    "bars_max": 20.0,             # longest a bar gets
}

VOICE_SKIP = {"change", "switch", "voice", "voices", "your", "the", "to", "a", "an", "use", "try", "can", "you",
              "please", "i", "want", "different", "another", "other", "new", "next", "one", "like", "sound",
              "speak", "talk", "with", "more", "do", "have", "any", "what", "which", "are", "there", "me", "my",
              "it", "of", "for", "and", "or", "that", "this", "swap", "pick", "set", "put", "on", "go", "be",
              "male", "female", "man", "woman", "guy", "girl", "boy", "lady", "british", "american", "deep",
              "deeper", "uk", "us", "usa", "london", "posh", "masculine", "feminine", "say", "hear", "give"}
PROMPT = "Arinze."          # only his name. A longer hint makes Whisper invent words from the hint
# how Whisper tends to mishear the voice names
VOICE_HEARD_AS = {"park": "puck", "puk": "puck", "buck": "puck", "pak": "puck", "pock": "puck", "pook": "puck",
                  "pack": "puck", "fabel": "fable", "favel": "fable", "faible": "fable", "fabal": "fable",
                  "hart": "heart", "harp": "heart", "bela": "bella", "nikole": "nicole", "nicolle": "nicole",
                  "mike": "michael", "micheal": "michael", "fenrer": "fenrir", "fenir": "fenrir",
                  "ema": "emma", "ahdam": "adam", "jorge": "george", "sara": "sarah", "sarra": "sarah"}
ALIASES = {"arinze", "arinzi", "arenzi", "arinzy", "arenzy", "erinze", "erinzi", "irinze", "arinse",
           "arinsi", "arrinze", "arrenzi", "aranzi", "arensi", "arrinzi", "arinzee", "arinzey", "arenze"}
FILLER = {"hey", "hi", "hello", "ok", "okay", "yo", "oh", "so"}
# Whisper likes to invent these from noise, so on their own they are ignored
JUNK = {"thank you", "thanks", "you", "bye", "bye bye", "okay", "ok", "so", "uh", "um", "hmm", "mm",
        "yeah", "oh", "the", "i", "thanks for watching", "thank you for watching", "you you"}
STOP_RE = re.compile(r"^(?:ok(?:ay)? )?(?:stop|stop talking|stop it|be quiet|quiet|hush|shush|shh+|"
                     r"enough|that'?s enough|shut up|silence)$")
END_RE = re.compile(r"^(?:ok(?:ay)? )?(?:that'?s all|that will be all|that'?ll be all|i'?m done|"
                    r"stop listening|go to sleep|goodbye|bye(?: bye)?|never ?mind|dismissed|go away|"
                    r"good night|talk to you later|see you later)$")
NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
            "nine": 9, "ten": 10, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30,
            "forty five": 45, "forty-five": 45, "sixty": 60, "a": 1, "an": 1}


# little sounds a person makes before a thought, matched to how he feels
FILLERS = {
    "thinking": ["Hmm,", "Let me see...", "Hmm... okay,"], "puzzled": ["Hmm,", "Huh,", "Hm, well,"],
    "confused": ["Uh,", "Hmm,", "Okay, so,"], "skeptical": ["Hmm,", "Mm, right,", "Well..."],
    "happy": ["Oh,", "Ah,", "Ha,"], "cheerful": ["Oh,", "Ah,", "Well,"],
    "big_smile": ["Ha,", "Oh!", "Ah,"], "loved": ["Aww,", "Oh,"], "shy": ["Oh,", "Um,", "Ah,"],
    "bashful": ["Um,", "Oh,", "Ah,"], "sassy": ["Mm,", "Well, well,", "Oh, please,"],
    "evil_grin": ["Mmm,", "Ooh,", "Well,"], "wink": ["Ha,", "Well,", "Mm,"],
    "cool": ["Mm,", "Well,"], "flirty": ["Mm,", "Oh,", "Well,"],
    "sad": ["Aww,", "Oh,", "Ah,"], "worried": ["Oh,", "Um,", "Ah,"], "devastated": ["Oh...", "Ah,"],
    "shocked": ["Oh!", "Whoa,", "Oh,"], "deadpan": ["Mm.", "Right,", "Okay,"],
    "bored": ["Mm.", "Uh,", "Well,"], "tired": ["Mm,", "Uh,", "Ah,"],
    "angry": ["Ugh,", "Okay,"], "annoyed": ["Ugh,", "Mm,"], "irritated": ["Ugh,", "Mm."],
}
DEFAULT_FILLERS = ["Well,", "So,", "Okay,", "Mm,", "Ah,"]
# how quickly he talks when he feels this way (1.0 = normal)
FACE_SPEED = {
    "sad": 0.90, "tired": 0.88, "sleeping": 0.85, "bored": 0.92, "devastated": 0.88, "crying": 0.90,
    "worried": 0.97, "deadpan": 0.95, "thinking": 0.95, "evil_grin": 0.96, "flirty": 0.95,
    "happy": 1.04, "cheerful": 1.05, "big_smile": 1.08, "shocked": 1.08, "angry": 1.05,
    "furious": 1.10, "fire_angry": 1.10, "inferno_rage": 1.12, "loved": 0.97, "alert": 1.03,
}
KOKORO_VOICES = ["af_heart", "af_bella", "af_nicole", "af_sky", "af_sarah", "am_michael", "am_puck",
                 "am_fenrir", "am_adam", "bf_emma", "bm_george", "bm_fable"]


def humanize(text, face, chance):
    """Sometimes starts a line with a small, natural filler ("Hmm,") that fits his mood."""
    words = text.split()
    if len(words) < 5 or random.random() >= float(chance):
        return text
    if re.match(r"^(?:hm+|well|oh|ah|um|uh|so|okay|ok|aww|ha|mm+|ugh|huh|whoa|ooh)\b", text.lower()):
        return text
    return random.choice(FILLERS.get(face) or DEFAULT_FILLERS) + " " + text


def split_sentences(text, max_len=200):
    parts = [x.strip() for x in re.split(r"(?<=[.!?\u2026])\s+", text) if x.strip()]
    out = []
    for x in parts:
        if out and (len(out[-1]) < 14 or len(x) < 8) and len(out[-1]) + len(x) < max_len:
            out[-1] += " " + x
        else:
            out.append(x)
    return out or [text]


def _kokoro_lang(voice):
    return "en-gb" if str(voice).startswith(("bf_", "bm_")) else "en-us"


# ---------------------------------------------------------------- small helpers
def _is_name(tok):
    t = tok.lower().replace("'s", "").strip("'")
    if t in ALIASES:
        return True
    if not 5 <= len(t) <= 9 or t[0] not in "aeiy":
        return False
    return difflib.SequenceMatcher(None, t, "arinze").ratio() >= 0.8


def split_wake(text):
    """Finds his name in a phrase. Returns (heard_his_name, the_rest_of_the_phrase)."""
    toks = [(m.group(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z']+", text)]
    for i, (t, s, e) in enumerate(toks):
        span = None
        if _is_name(t):
            span = (s, e)
        elif i + 1 < len(toks) and len(t) <= 3 and _is_name(t + toks[i + 1][0]):
            span = (s, toks[i + 1][2])      # "a rinze" -> Arinze
        if span:
            start = span[0]
            if i > 0 and toks[i - 1][0].lower() in FILLER:
                start = toks[i - 1][1]      # drop the "hey" in front of his name
            rest = (text[:start] + " " + text[span[1]:])
            rest = re.sub(r"\s+", " ", rest).strip(" ,.!?;:-")
            return True, rest
    return False, text.strip()


def clean_for_speech(text, limit):
    t = re.sub(r"https?://\S+", " link ", str(text))
    t = re.sub(r"[`*_#>~|\[\]{}<>\\^]", " ", t)
    t = re.sub(r"[^\w\s.,!?;:'\"%&@()+\-/$]", " ", t)      # drops emojis
    t = re.sub(r"\s+", " ", t).strip()
    if len(t) > limit:
        cut = max(t.rfind(". ", 0, limit), t.rfind("! ", 0, limit), t.rfind("? ", 0, limit))
        t = t[:cut + 1] if cut > limit // 2 else t[:limit]
    return t


def _normalise(text):
    low = re.sub(r"\bplease\b", " ", text.lower())
    low = re.sub(r"[^a-z0-9' \-]", " ", low)
    return re.sub(r"\s+", " ", low).strip(" -")


# ---------------------------------------------------------------- cuts the mic stream into phrases
class Segmenter:
    """Gets 30 ms frames and their loudness. Tells you when a phrase ended, or when you talked over him."""
    FRAME_S = 0.03
    MAX_FRAMES = 666          # 20 seconds

    def __init__(self, get):
        self.get = get
        self.floor = 0.006    # background noise level, learned as it goes
        self.echo = 0.0       # how loud his own voice is in the mic
        self.pre = collections.deque(maxlen=10)
        self._was_speaking = False
        self.reset()

    def reset(self):
        self.in_speech = False
        self.run = 0
        self.silence = 0
        self.vcount = 0
        self.buf = []

    def base(self):
        return max(self.floor * 3.0, 0.008) / max(0.2, float(self.get("sensitivity")))

    def feed(self, frame, rms, speaking, age):
        out = []
        base = self.base()
        if speaking and not self._was_speaking:
            self.echo = 0.0
        self._was_speaking = speaking
        if self.in_speech:
            voiced = rms > base * 0.7
        elif speaking:
            if not self.get("barge_in"):
                voiced = False
            elif age < 0.8:
                # the first moments of his speech: whatever the mic hears is his own voice
                self.echo = max(self.echo, rms)
                voiced = False
            else:
                # you must be clearly louder than his own echo (headphones make this easy)
                thr = max(base * 1.5, self.echo * 2.0)
                voiced = rms > thr
                if not voiced:
                    self.echo = max(self.echo * 0.998, rms)
        else:
            voiced = rms > base
            if rms < base:
                self.floor = min(0.05, max(0.002, self.floor * 0.97 + rms * 0.03))
        if not self.in_speech:
            self.pre.append(frame)
            self.run = self.run + 1 if voiced else 0
            need = 12 if speaking else 3          # talking over him needs about 0.36 s of real speech
            if self.run >= need:
                self.in_speech = True
                self.silence = 0
                self.vcount = need
                self.buf = list(self.pre)
                if speaking:
                    out.append(("barge", None))
        else:
            self.buf.append(frame)
            self.silence = 0 if voiced else self.silence + 1
            self.vcount += 1 if voiced else 0
            end_n = max(3, int(float(self.get("end_silence_ms")) / 30.0))
            if self.silence >= end_n or len(self.buf) >= self.MAX_FRAMES:
                if self.vcount * self.FRAME_S >= 0.3:       # a click or a cough is not a phrase
                    out.append(("phrase", self.buf))
                if len(self.buf) >= self.MAX_FRAMES:
                    self.floor = min(0.05, self.floor * 1.5)     # probably steady noise, adapt to it
                self.reset()
                self.pre.clear()
        return out


# ---------------------------------------------------------------- the voice
class Voice(QObject):
    heard = pyqtSignal(str, float)     # text, seconds of audio (from the listening thread)
    barged = pyqtSignal()              # you talked over him
    spoke_done = pyqtSignal(int)       # he finished a sentence
    tts_ready = pyqtSignal()           # the natural voice finished loading (or could not load)

    def __init__(self, w, quiet):
        super().__init__()
        self.w = w
        self.quiet = quiet
        self.s = dict(DEFAULTS)
        self._mtime = None
        self._load_settings(force=True)
        self.proc = None
        self.gen = 0
        self.speak_t0 = 0.0
        self.last_said = ""
        self.last_kind = ""
        self.reply_next = 0.0          # set when the next bubble is an answer to you (so it is always spoken)
        self.mic_on = bool(self.s["listen"])
        self.stt_ready = False
        self.awake_until = 0.0
        self.in_call = False
        self.inbox = []                # [(time, text)] things you said that are waiting for him
        self.tq = queue.Queue(maxsize=4)
        self.voices = None
        self.tts = None                # the natural voice, once loaded
        self.tts_state = "loading" if str(self.s["engine"]).lower() == "kokoro" else "off"
        self.voice_trial = 0.0         # when he last offered you a voice to try or a list to pick from
        self.pending = None            # (time, text, kind) he wanted to say while his voice was still loading
        self.k_names = []
        self.sd_out = None
        self.talking = False
        self.play_proc = None
        self.level = 0.0               # how loudly you are speaking (drives the listening bars)
        self.tts_lock = threading.Lock()
        self.play_lock = threading.Lock()
        self.lock = threading.RLock()
        self.heard.connect(self._on_heard)
        self.barged.connect(self._on_barge)
        self.spoke_done.connect(self._on_spoke_done)
        self.tts_ready.connect(self._on_tts_ready)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(250)
        self._next_settings = time.time() + 10
        self._next_call = 0.0
        atexit.register(self.stop_speech)
        threading.Thread(target=self._list_voices, daemon=True).start()
        threading.Thread(target=self._load_tts, daemon=True).start()
        threading.Thread(target=self._start_listening, daemon=True).start()

    # ------------------------------------------------------------ settings
    def _load_settings(self, force=False):
        try:
            m = os.path.getmtime(SETTINGS_PATH)
        except OSError:
            m = None
        if not force and m == self._mtime:
            return
        self._mtime = m
        if m is None:
            self._write_settings(dict(DEFAULTS))
            return
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print("[Arinze voice] could not read voice_settings.json (%r). Using the defaults." % e, flush=True)
            return
        if not isinstance(data, dict):
            return
        for k, v in data.items():
            if k not in DEFAULTS:
                continue
            d = DEFAULTS[k]
            try:
                if d is None:
                    self.s[k] = v
                elif isinstance(d, bool):
                    self.s[k] = bool(v)
                elif isinstance(d, list):
                    self.s[k] = [str(x) for x in v] if isinstance(v, list) else d
                elif k == "language":
                    self.s[k] = v if v else None
                else:
                    self.s[k] = type(d)(v)
            except Exception:
                self.s[k] = d

    def _write_settings(self, obj):
        try:
            os.makedirs(HOME, exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
                json.dump(obj, f, indent=2)
            self._mtime = os.path.getmtime(SETTINGS_PATH)
        except Exception:
            pass

    def _set(self, key, value):
        self.s[key] = value
        try:
            with open(SETTINGS_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data[key] = value
        self._write_settings(data)

    # ------------------------------------------------------------ talking
    def _list_voices(self):
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=10).stdout
            names = []
            for line in out.splitlines():
                m = re.match(r"^(.+?)\s{2,}([a-z]{2,3}[_-][A-Za-z0-9]+)\b", line)
                if m:
                    names.append((m.group(1).strip(), m.group(2)))
            self.voices = names or None
        except Exception:
            self.voices = None

    def _voice_arg(self):
        name = str(self.s.get("voice") or "").strip()
        if not name:
            return None
        if self.voices and name.lower() not in [v[0].lower() for v in self.voices]:
            return None
        return name

    def _load_tts(self):
        if str(self.s["engine"]).lower() != "kokoro":
            return
        try:
            self._load_tts_inner()
        finally:
            if self.tts is None:
                self.tts_state = "failed"
            else:
                self.tts_state = "ready"
            self.tts_ready.emit()

    def _load_tts_inner(self):
        try:
            import sounddevice as sd
            from kokoro_onnx import Kokoro
        except Exception as e:
            print("[Arinze voice] The natural voice is not installed yet (%r). Using the Mac voice for now.\n"
                  "  To install it:  python3 -m pip install kokoro-onnx\n"
                  "  (Start Arinze with the Arinze.command launcher so it uses the right Python.)" % e, flush=True)
            return
        model = os.path.expanduser(str(self.s["kokoro_model"]))
        vfile = os.path.expanduser(str(self.s["kokoro_voices"]))
        if not (os.path.exists(model) and os.path.exists(vfile)):
            print("[Arinze voice] The natural voice files are missing. Expected:\n  %s\n  %s\n"
                  "  Using the Mac voice for now." % (model, vfile), flush=True)
            return
        try:
            tts = Kokoro(model, vfile)
            try:
                self.k_names = sorted(tts.get_voices())
            except Exception:
                self.k_names = []
            v = self._k_voice()
            tts.create("Hi.", voice=v, speed=1.0, lang=_kokoro_lang(v))      # warm-up, so the first line is quick
        except Exception as e:
            print("[Arinze voice] Could not start the natural voice (%r). Using the Mac voice." % e, flush=True)
            return
        self.sd_out = sd
        self.tts = tts
        print("[Arinze voice] natural voice ready (%s)." % self._k_voice(), flush=True)

    def _on_tts_ready(self):
        # whatever he wanted to say while his voice was loading is said now, in the right voice
        pend, self.pending = self.pending, None
        if pend and time.time() - pend[0] < 25:
            self.speak(pend[1], pend[2])

    def _k_voice(self):
        v = str(self.s.get("kokoro_voice") or "af_heart")
        if self.k_names and v not in self.k_names:
            return "af_heart" if "af_heart" in self.k_names else self.k_names[0]
        return v

    def _k_pick(self, want):
        names = self.k_names or KOKORO_VOICES
        want = want.lower().strip().replace(" ", "_")
        want = VOICE_HEARD_AS.get(want, want)
        for n in names:
            if n == want or n.split("_", 1)[-1] == want:
                return n
        close = difflib.get_close_matches(want, [n.split("_", 1)[-1] for n in names], n=1, cutoff=0.8)
        if close:
            for n in names:
                if n.split("_", 1)[-1] == close[0]:
                    return n
        return None

    def _voice_pool(self, prefixes=None):
        have = set(self.k_names) if self.k_names else None
        return [v for v in KOKORO_VOICES
                if (have is None or v in have) and (not prefixes or v.startswith(tuple(prefixes)))]

    def _next_voice(self, prefixes=None):
        pool = self._voice_pool(prefixes) or self._voice_pool()
        cur = self._k_voice()
        return pool[(pool.index(cur) + 1) % len(pool)] if cur in pool else pool[0]

    def _voice_from_text(self, low):
        """A voice name ('puck') or a kind of voice ('a deeper male one', 'british') in what you said."""
        for w in re.findall(r"[a-z]+", low):
            if w in VOICE_SKIP:
                continue
            v = self._k_pick(w)
            if v:
                return ("name", v)
        allowed = {"af_", "am_", "bf_", "bm_"}
        if re.search(r"\b(?:male|man|guy|boy|masculine|deep|deeper)\b", low):
            allowed &= {"am_", "bm_"}
        if re.search(r"\b(?:female|woman|girl|lady|feminine)\b", low):
            allowed &= {"af_", "bf_"}
        if re.search(r"\b(?:british|uk|london|posh)\b", low):
            allowed &= {"bf_", "bm_"}
        if re.search(r"\b(?:american|us|usa)\b", low):
            allowed &= {"af_", "am_"}
        if allowed != {"af_", "am_", "bf_", "bm_"} and allowed:
            return ("kind", tuple(sorted(allowed)))
        return None

    def _announce_voice(self, hit):
        v = hit[1] if hit[0] == "name" else self._next_voice(hit[1])
        self._set("kokoro_voice", v)
        self.voice_trial = time.time()
        self._note("Hi, I'm Arinze, in the %s voice. Do you like it?" % v.split("_", 1)[1].capitalize(), "cheerful")

    def _list_voices_say(self, prefix=""):
        names = [n.split("_", 1)[-1].capitalize() for n in self._voice_pool()]
        self.voice_trial = time.time()
        self._note(prefix + "I can sound like " + ", ".join(names[:8]) + ". Which one would you like?", "cool")

    def _use_kokoro(self):
        return self.tts is not None and str(self.s["engine"]).lower() == "kokoro"

    def is_speaking(self):
        if self.talking:
            return True
        p = self.proc
        return p is not None and p.poll() is None

    def stop_speech(self):
        with self.lock:
            self.gen += 1
            p, self.proc = self.proc, None
            self.talking = False
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        pp, self.play_proc = self.play_proc, None
        if pp is not None and pp.poll() is None:
            try:
                pp.terminate()
            except Exception:
                pass

    def say_bubble(self, text):
        # called every time he shows a speech bubble
        now = time.time()
        kind = "reply" if now - self.reply_next < 120 else "chatter"
        self.reply_next = 0.0
        self.speak(text, kind)

    def speak(self, text, kind="reply"):
        if not self.s["enabled"] or self.in_call:
            return
        if kind == "chatter" and (not self.s["speak_chatter"] or self.quiet() or self.is_speaking()):
            return
        text = clean_for_speech(text, int(self.s["max_spoken_chars"]))
        if not text:
            return
        if str(self.s["engine"]).lower() == "kokoro" and self.tts_state == "loading":
            self.pending = (time.time(), text, kind)       # said as soon as his real voice is ready
            return
        self.stop_speech()
        if text.rstrip().endswith("?") and kind != "ack" and self.mic_on and self.stt_ready:
            # he asked you something: you can answer without saying his name
            self.awake_until = max(self.awake_until, time.time() + 6.0 + len(text) / 12.0
                                   + float(self.s["question_window_sec"]))
        if self._use_kokoro():
            face = str(getattr(self.w, "cur", "idle"))
            spoken = text if kind in ("ack",) else humanize(text, face, self.s["filler_chance"])
            speed = float(self.s["kokoro_speed"])
            if self.s["character"]:
                speed *= FACE_SPEED.get(face, 1.0)
            speed = max(0.6, min(1.6, speed))
            with self.lock:
                gen = self.gen
                self.talking = True
            self.speak_t0 = time.time()
            if kind != "ack":
                self.last_said = text
            self.last_kind = kind
            threading.Thread(target=self._kokoro_speak, args=(spoken, gen, self._k_voice(), speed),
                             daemon=True).start()
            return
        cmd = ["say", "-r", str(int(self.s["rate"])), "-f", "-"]
        v = self._voice_arg()
        if v:
            cmd[1:1] = ["-v", v]
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            proc.stdin.write(text.encode("utf-8"))
            proc.stdin.close()
        except Exception as e:
            print("[Arinze voice] could not speak: %r" % e, flush=True)
            return
        with self.lock:
            self.proc = proc
            gen = self.gen
        self.speak_t0 = time.time()
        if kind != "ack":
            self.last_said = text
        self.last_kind = kind
        threading.Thread(target=self._watch_speech, args=(proc, gen), daemon=True).start()

    def _kokoro_speak(self, text, gen, voice, speed):
        """Makes the voice one sentence at a time, and plays each while the next is being made."""
        lang = _kokoro_lang(voice)
        q = queue.Queue(maxsize=2)

        def put(item):
            while gen == self.gen:
                try:
                    q.put(item, timeout=0.1)
                    return True
                except queue.Full:
                    pass
            return False

        def producer():
            try:
                for sent in split_sentences(text):
                    if gen != self.gen:
                        break
                    with self.tts_lock:
                        if gen != self.gen:
                            break
                        audio, sr = self.tts.create(sent, voice=voice, speed=speed, lang=lang)
                    if not put((audio, sr)):
                        break
            except Exception as e:
                print("[Arinze voice] the natural voice failed: %r" % e, flush=True)
            put(None)

        threading.Thread(target=producer, daemon=True).start()
        first = True
        try:
            while gen == self.gen:
                try:
                    item = q.get(timeout=0.1)
                except queue.Empty:
                    continue
                if item is None:
                    break
                audio, sr = item
                if gen != self.gen:
                    break
                if first:
                    first = False
                    self.speak_t0 = time.time()      # the echo of his own voice starts being measured here
                self._play_audio(audio, sr, gen)
                if gen != self.gen:
                    break
                time.sleep(0.05)
        except Exception as e:
            print("[Arinze voice] could not play his voice: %r" % e, flush=True)
        finally:
            if gen == self.gen:
                with self.lock:
                    self.talking = False
                self.spoke_done.emit(gen)

    def _play_audio(self, audio, sr, gen):
        """Plays one sentence with the Mac's own player. It runs outside Python, so busy moments in Arinze
        cannot make it crackle. Tiny fades and a little silence on each end stop clicks and pops."""
        import numpy as np, wave, tempfile
        a = np.asarray(audio, dtype="float32").reshape(-1).copy()
        n = max(1, int(sr * 0.006))
        if len(a) > 2 * n:
            ramp = np.linspace(0.0, 1.0, n, dtype="float32")
            a[:n] *= ramp
            a[-n:] *= ramp[::-1]
        pcm = np.concatenate([np.zeros(int(sr * 0.06), "float32"), a, np.zeros(int(sr * 0.04), "float32")])
        pcm = (np.clip(pcm, -1.0, 1.0) * 32767).astype("<i2")
        path = os.path.join(tempfile.gettempdir(), "arinze_%d_%d.wav" % (os.getpid(), int(time.time() * 1000)))
        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(int(sr))
                wf.writeframes(pcm.tobytes())
            if gen != self.gen:
                return
            proc = subprocess.Popen(["afplay", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.lock:
                if gen != self.gen:
                    proc.terminate()
                    return
                self.play_proc = proc
            while proc.poll() is None and gen == self.gen:
                time.sleep(0.02)
            if proc.poll() is None:
                proc.terminate()
        finally:
            try:
                os.remove(path)
            except OSError:
                pass

    def _watch_speech(self, proc, gen):
        try:
            proc.wait()
        except Exception:
            pass
        if gen == self.gen:
            self.spoke_done.emit(gen)

    def _chime(self):
        try:
            subprocess.Popen(["afplay", "-v", "0.4", "/System/Library/Sounds/Pop.aiff"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _note(self, text, face="content"):
        # show and say something quickly (always spoken)
        self.reply_next = time.time()
        w = self.w
        w.set_expression(face, 5.0)
        w.bubble.show_text(text, QRect(w.base.x(), w.base.y(), w.width(), w.height()))

    # ------------------------------------------------------------ listening (background threads)
    def _start_listening(self):
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
        except Exception as e:
            print("[Arinze voice] He can talk, but listening is off (%r).\n"
                  "  To turn listening on, run:  pip3 install faster-whisper sounddevice numpy" % e, flush=True)
            return
        self.np, self.sd = np, sd
        try:
            print("[Arinze voice] loading the listening model '%s' (the first time it downloads)..."
                  % self.s["stt_model"], flush=True)
            self.model = WhisperModel(self.s["stt_model"], device="cpu", compute_type="int8",
                                      cpu_threads=int(self.s["stt_threads"]))
        except Exception as e:
            print("[Arinze voice] could not load the listening model: %r" % e, flush=True)
            return
        self.stt_ready = True
        threading.Thread(target=self._transcribe_loop, daemon=True).start()
        self._audio_loop()

    def _pick_input(self):
        dev = self.s.get("input_device")
        if dev is not None or not self.s.get("auto_builtin_mic"):
            return dev
        try:
            name = str(self.sd.query_devices(kind="input")["name"])
            if re.search(r"airpods|beats|bluetooth|buds|headset|bose|jabra|sony|wh-|wf-", name, re.I):
                for i, d in enumerate(self.sd.query_devices()):
                    if d["max_input_channels"] > 0 and re.search(r"macbook|built-in", d["name"], re.I):
                        print("[Arinze voice] '%s' is a Bluetooth mic, so I will listen with '%s' instead. "
                              "That keeps your headphones in high-quality sound." % (name, d["name"]), flush=True)
                        return i
        except Exception:
            pass
        return None

    def _audio_loop(self):
        sd = self.sd
        q = queue.Queue(maxsize=400)

        def cb(indata, frames, t, status):
            try:
                q.put_nowait(indata[:, 0].copy())
            except queue.Full:
                pass

        while True:
            try:
                dev = self._pick_input()
                with sd.InputStream(samplerate=16000, channels=1, dtype="float32", blocksize=480,
                                    device=dev, callback=cb):
                    print("[Arinze voice] listening. Say 'Arinze'.", flush=True)
                    self._process_frames(q)
            except Exception as e:
                print("[Arinze voice] microphone problem (%r). Trying again in 5 seconds." % e, flush=True)
                time.sleep(5)

    def _process_frames(self, q):
        np = self.np
        seg = Segmenter(lambda k: self.s[k])
        zeros = 0
        warned = False
        while True:
            try:
                f = q.get(timeout=1.0)
            except queue.Empty:
                continue
            rms = float(np.sqrt(np.mean(f * f)))
            if rms == 0.0:
                zeros += 1
                if zeros > 260 and not warned:
                    warned = True
                    print("[Arinze voice] the mic is giving pure silence. Allow your Terminal in System Settings, "
                          "Privacy & Security, Microphone, then restart Arinze.", flush=True)
            else:
                zeros = 0
            if not self.mic_on or self.in_call:
                seg.reset()
                seg.pre.clear()
                self.level = 0.0
                continue
            speaking = self.is_speaking()
            lv = 0.0 if speaking else min(1.0, max(0.0, (rms - seg.floor * 1.5) / max(0.02, seg.base() * 5.0)))
            self.level = max(lv, self.level * 0.88)
            age = time.time() - self.speak_t0
            for ev, data in seg.feed(f, rms, speaking, age):
                if ev == "barge":
                    self.stop_speech()
                    self.barged.emit()
                elif ev == "phrase":
                    try:
                        self.tq.put_nowait(np.concatenate(data))
                    except queue.Full:
                        pass

    def _transcribe_loop(self):
        while True:
            audio = self.tq.get()
            try:
                segs, _info = self.model.transcribe(
                    audio, language=self.s["language"] or None, beam_size=max(1, int(self.s["stt_beam"])),
                    temperature=0.0, vad_filter=True,
                    vad_parameters={"threshold": 0.35, "min_silence_duration_ms": 400, "speech_pad_ms": 300},
                    condition_on_previous_text=False, initial_prompt=PROMPT, no_speech_threshold=0.7)
                parts = []
                dropped = []
                for sg in segs:
                    if sg.no_speech_prob > 0.75 or sg.avg_logprob < -1.8:
                        dropped.append(sg.text.strip())
                        continue
                    parts.append(sg.text.strip())
                text = " ".join(p for p in parts if p).strip()
                if self.s["show_heard"]:
                    if text:
                        print('[Arinze heard] "%s"' % text, flush=True)
                    elif dropped:
                        print('[Arinze heard] (unclear, ignored) "%s"' % " ".join(dropped), flush=True)
                if text:
                    self.heard.emit(text, len(audio) / 16000.0)
            except Exception as e:
                print("[Arinze voice] could not understand a phrase: %r" % e, flush=True)

    # ------------------------------------------------------------ what he does with what he heard (main thread)
    def awake_now(self):
        return self.mic_on and time.time() < self.awake_until

    def open_window(self):
        self.awake_until = time.time() + float(self.s["window_sec"])

    def _on_barge(self):
        self.w.bubble.hide()
        if self.awake_now():
            self.w.set_expression("alert", 6.0)

    def _on_spoke_done(self, gen):
        if self.last_kind in ("reply", "ack") and self.s["sliding_window"] and self.awake_now():
            self.open_window()
        if self.mic_on and self.last_kind != "ack" and self.last_said.rstrip().endswith("?"):
            # he asked a question: give you time to answer
            self.awake_until = max(self.awake_until, time.time() + float(self.s["question_window_sec"]))

    def _on_heard(self, text, dur):
        if self.in_call or not self.mic_on:
            return
        now = time.time()
        hit, rest = split_wake(text)
        awake = now < self.awake_until
        low = _normalise(rest)
        if not hit and not awake:
            return
        if not hit and low in JUNK:
            return
        if hit or self.s["sliding_window"]:
            self.open_window()
        if not low:
            self._ack()
            return
        if STOP_RE.match(low):
            self.stop_speech()
            self.w.bubble.hide()
            return
        if END_RE.match(low):
            self.awake_until = 0.0
            self.stop_speech()
            self._note("Okay, I'll be here. Say my name when you need me.", "content")
            return
        if self._voice_command(low, rest):
            return
        self.inbox.append((now, rest))
        del self.inbox[:-3]

    def _ack(self):
        self.w.set_expression("alert", 6.0)
        phrase = str(self.s["ack_phrase"] or "").strip()
        if phrase:
            self.speak(phrase, "ack")
        else:
            self._chime()

    def _voice_command(self, low, raw):
        if re.match(r"^(?:repeat that|repeat|say that again|what did you say|come again|say again)$", low):
            if self.last_said:
                self.speak(self.last_said, "reply")
            else:
                self._note("I haven't said anything yet.", "puzzled")
            return True
        m = re.match(r"^(?:(?:speak|talk) )?(faster|slower)$", low)
        if m:
            if self._use_kokoro():
                sp = float(self.s["kokoro_speed"]) + (0.1 if m.group(1) == "faster" else -0.1)
                self._set("kokoro_speed", round(max(0.7, min(1.4, sp)), 2))
            else:
                rate = int(self.s["rate"]) + (25 if m.group(1) == "faster" else -25)
                self._set("rate", max(110, min(300, rate)))
            self._note("How is this?", "cheerful")
            return True
        if re.match(r"^(?:(?:turn off|mute|disable) (?:your )?voice|mute yourself|stop talking out loud|"
                    r"stop speaking out loud)$", low):
            self._set("enabled", False)
            self._note("Okay, I'll just type from now on.", "content")
            return True
        if re.match(r"^(?:(?:turn on|unmute|enable|start) (?:your )?voice|unmute yourself)$", low):
            self._set("enabled", True)
            self._note("I'm back! Can you hear me?", "cheerful")
            return True
        if re.match(r"^(?:mute|turn off|stop) (?:the |my )?(?:mic|microphone)$", low):
            self.mic_on = False
            self.awake_until = 0.0
            self._set("listen", False)
            self._note("Mic off. Right-click me to turn it back on.", "content")
            return True
        if self._use_kokoro():
            if self.voice_trial and time.time() - self.voice_trial < 60:
                # he just offered you a voice, or a list of voices: short answers are about that
                if re.match(r"^(?:yes|yeah|yep|sure|keep(?: it| this| this one)?|i like it|i like this one|"
                            r"that'?s (?:good|great|fine|perfect|nice)|this one|perfect|good|nice|love it)$", low):
                    self.voice_trial = 0.0
                    self._note("Great, I'll keep this voice.", "happy")
                    return True
                if re.match(r"^(?:no|nope|next|next one|another|another one|different|something else|"
                            r"try another(?: one)?|try the next one|not this one)$", low):
                    self._announce_voice(("kind", ()))
                    return True
                if len(low.split()) <= 4:
                    hit = self._voice_from_text(low)
                    if hit:
                        self._announce_voice(hit)
                        return True
            if re.search(r"\b(?:sound|speak|talk) (?:like|more)\b", low) and not re.search(r"\bvoices?\b", low):
                hit = self._voice_from_text(low)          # "sound like Fable": only if a voice is named
                if hit:
                    self._announce_voice(hit)
                    return True
            if re.search(r"\bvoices?\b", low):
                hit = self._voice_from_text(low)
                if hit:
                    self._announce_voice(hit)
                    return True
                m = (re.search(r"\b(?:to|as) (?:the )?([a-z]+)$", low)
                     or re.search(r"\b(?:use|try) (?:the )?([a-z]+) voice\b", low))
                if m and m.group(1) not in VOICE_SKIP:
                    self._list_voices_say("I don't have a voice called %s. " % m.group(1))
                    return True
                if (re.search(r"\b(?:change|switch|try|another|different|next|new|swap)\b", low)
                        and not re.search(r"\b(?:what|which|list|do you have|how many)\b", low)):
                    self._announce_voice(("kind", ()))
                    return True
                self._list_voices_say()
                return True
        if re.match(r"^(?:what|which|list)(?: other)? voices(?: do you have| are there| can you use)?$", low):
            if self._use_kokoro():
                names = [n.split("_", 1)[-1].capitalize() for n in (self.k_names or KOKORO_VOICES)
                         if n.startswith(("af_", "am_", "bf_", "bm_"))]
            else:
                names = [v[0] for v in (self.voices or []) if v[1].lower().startswith("en")]
            if names:
                self._note("I can sound like " + ", ".join(names[:6]) + ". Say change voice to one of them.",
                           "cool")
            else:
                self._note("I couldn't read my voice list.", "puzzled")
            return True
        m = (re.match(r"^(?:change|switch|set|use)(?: your)? voice (?:to |as )?(?:the )?(.+)$", low)
             or re.match(r"^(?:use|try|switch to|change to) (?:the )?(.+?) voice$", low))
        if m:
            want = m.group(1).strip()
            if self._use_kokoro():
                kv = self._k_pick(want)
                if kv:
                    self._set("kokoro_voice", kv)
                    self._note("Hey, this is my new voice. What do you think?", "cheerful")
                else:
                    self._note("I don't have a voice called %s." % want, "puzzled")
                return True
            pick = None
            for name, _lang in (self.voices or []):
                if name.lower() == want or name.lower().split(" (")[0] == want:
                    pick = name
                    break
            if pick:
                self._set("voice", pick)
                self._note("Hello, this is my new voice.", "cheerful")
            else:
                self._note("I don't have a voice called %s." % want, "puzzled")
            return True
        if re.search(r"\btimer\b", low):
            m = re.search(r"(\d+(?:\.\d+)?|a|an|one|two|three|four|five|six|seven|eight|nine|ten|twelve|"
                          r"fifteen|twenty|thirty|forty[ -]five|sixty)\s*(sec\w*|min\w*|hour\w*|hr\w*)", low)
            if m:
                n = m.group(1)
                n = NUMWORDS.get(n, n)
                self.inbox.append((time.time(), "remind me in %s %s to check your timer" % (n, m.group(2))))
                return True
        return False

    # ------------------------------------------------------------ housekeeping (main thread, 4 times a second)
    def _tick(self):
        now = time.time()
        if now >= self._next_settings:
            self._next_settings = now + 10
            self._load_settings()
        if now >= self._next_call:
            self._next_call = now + 2
            self._check_call()
        if (self.awake_until and now > self.awake_until and not self.is_speaking()
                and not self.w.busy and not self.inbox):
            self.awake_until = 0.0
        self.inbox = [(t, x) for t, x in self.inbox if now - t < 30]
        if self.inbox and not self.w.busy and not self.w.in_dialog:
            _t, text = self.inbox.pop(0)
            self.w.hear(text)

    def _check_call(self):
        if NSWorkspace is None:
            return
        try:
            app = NSWorkspace.sharedWorkspace().frontmostApplication()
            name = str(app.localizedName() or "").lower()
        except Exception:
            return
        new = name in [a.lower() for a in self.s["quiet_apps"]]
        if new and not self.in_call:
            self.stop_speech()
        self.in_call = new

    # ------------------------------------------------------------ menu and look
    def mic_label(self):
        if not self.stt_ready:
            return "Listening is not set up (see the Terminal)"
        return "Mic is ON (click to mute)" if self.mic_on else "Mic is OFF (click to listen for Arinze)"

    def voice_label(self):
        return "Voice is ON (click to mute him)" if self.s["enabled"] else "Voice is OFF (click to hear him)"

    def toggle_mic(self):
        if not self.stt_ready:
            self._note("I can't listen yet. Check the Terminal for what to install.", "puzzled")
            return
        self.mic_on = not self.mic_on
        self.awake_until = 0.0
        self._set("listen", self.mic_on)
        self._note("I'm listening for my name." if self.mic_on else "Mic off.", "happy" if self.mic_on else "content")

    def toggle_voice(self):
        on = not self.s["enabled"]
        self._set("enabled", on)
        if not on:
            self.stop_speech()
        self._note("I'm back! Can you hear me?" if on else "Okay, I'll just type.", "cheerful" if on else "content")

    def listen_now(self):
        if not self.stt_ready or not self.mic_on:
            self._note("My mic is off. Right-click me to turn it on.", "puzzled")
            return
        self.open_window()
        self._ack()

    def paint_ring(self, p, size):
        # (the name is from the old ring.) Three tiny bars beside each ear while he is listening.
        # They dim and brighten gently, and grow when you speak.
        try:
            if not self.awake_now():
                return
            from PyQt6.QtGui import QPainter, QPen, QColor
            k = size / 250.0
            t = time.time()
            alpha = 120 + int(70 * math.sin(t * 4.0))
            lv = min(1.0, self.level)
            s = self.s
            x0, y0, gap = float(s["bars_x"]), float(s["bars_y"]), float(s["bars_gap"])
            lo, hi = float(s["bars_min"]), float(s["bars_max"])
            sides = {"left": (-1,), "right": (1,)}.get(str(s["bars_sides"]).lower(), (-1, 1))
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(QColor(150, 210, 255, alpha))
            pen.setWidthF(max(1.2, 3.4 * k))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            for i in range(3):
                breathe = 0.5 + 0.5 * math.sin(t * 3.0 + i * 1.3)
                jig = 0.7 + 0.3 * math.sin(t * 9.0 + i * 2.1)
                amt = min(1.0, 0.16 * breathe + lv * (0.7, 1.0, 0.8)[i] * jig)
                half = (lo + (hi - lo) * amt) / 2.0
                for sx in sides:
                    x = (125.0 + sx * (x0 + i * gap)) * k
                    p.drawLine(QPointF(x, (y0 - half) * k), QPointF(x, (y0 + half) * k))
            p.restore()
        except Exception:
            pass


def _audition():
    """python3 arinze_voice.py --audition : plays a line in each natural voice so you can pick one."""
    import sounddevice as sd
    from kokoro_onnx import Kokoro
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            s.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except Exception:
        pass
    model = os.path.expanduser(str(s["kokoro_model"]))
    vfile = os.path.expanduser(str(s["kokoro_voices"]))
    k = Kokoro(model, vfile)
    try:
        have = set(k.get_voices())
    except Exception:
        have = set(KOKORO_VOICES)
    for v in KOKORO_VOICES:
        if v not in have:
            continue
        name = v.split("_", 1)[1].capitalize()
        print("\n%s   (to use it, set \"kokoro_voice\": \"%s\" in voice_settings.json, or say: change voice to %s)"
              % (v, v, name), flush=True)
        audio, sr = k.create("Hey, I'm Arinze. This is the %s voice. Hmm, what do you think?" % name,
                             voice=v, speed=1.0, lang=_kokoro_lang(v))
        sd.play(audio, sr)
        sd.wait()
        time.sleep(0.4)


if __name__ == "__main__":
    if "--audition" in sys.argv:
        _audition()
    else:
        print("This file is part of Arinze. Run arinze_v10.py. To try the voices:  python3 arinze_voice.py --audition")
