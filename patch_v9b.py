import os
base = os.path.expanduser("~/Arinze/")

def patch(fname, pairs):
    s = open(base + fname, encoding="utf-8").read()
    for old, new in pairs:
        assert s.count(old) == 1, (fname, old[:60], s.count(old))
        s = s.replace(old, new)
    open(base + fname, "w", encoding="utf-8").write(s)

patch("arinze_v9.py", [
    ('"bounce": false, "action": null}', '"bounce": false}'),
    ("data = json.loads(content)", "data = json.loads(content, object_pairs_hook=_pairs)"),
    ("Set action to null unless another tool is truly needed.", "Leave out action unless another tool is truly needed."),
    ("class Signals(QObject):",
     "def _pairs(pairs):\n"
     "    # if the model repeats a key, keep the real value rather than a later null\n"
     "    d = {}\n"
     "    for k, v in pairs:\n"
     "        if k not in d or (d[k] is None and v is not None):\n"
     "            d[k] = v\n"
     "    return d\n\n\nclass Signals(QObject):"),
])
patch("arinze_tools.py", [
    ('Otherwise set "action" to null.', 'Otherwise leave "action" out of the JSON.'),
    ('with "action" null.', 'and no "action".'),
])
print("patched")
