import os
p = os.path.expanduser("~/Arinze/arinze_v9.py")
s = open(p, encoding="utf-8").read()

def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)

rep('"options": {"num_ctx": 8192},', '"keep_alive": -1, "options": {"num_ctx": 8192},')
rep("app = QApplication(sys.argv)\n", '''def _warm_up():
    # load the model into memory at startup so your first question is not slow
    try:
        requests.post(URL, timeout=300, json={
            "model": MODEL, "stream": False, "format": "json", "keep_alive": -1,
            "options": {"num_ctx": 8192},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "hi"}]})
    except Exception:
        pass


threading.Thread(target=_warm_up, daemon=True).start()

app = QApplication(sys.argv)
''')
open(p, "w", encoding="utf-8").write(s)
print("patched")
