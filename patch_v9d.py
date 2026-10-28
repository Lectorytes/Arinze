import os
p = os.path.expanduser("~/Arinze/arinze_tools.py")
s = open(p, encoding="utf-8").read()

NEW = r"""# ---- Spotify and YouTube
def _osa(script, timeout=15):
    code, out = _run(["osascript", "-e", script], timeout=timeout)
    if code != 0:
        raise RuntimeError(out[:200])
    return out


def _spotify_running():
    return _run(["pgrep", "-x", "Spotify"])[0] == 0


def _spotify_ready():
    if not _spotify_running():
        code, out = _run(["open", "-a", "Spotify"])
        if code != 0:
            raise RuntimeError("Spotify is not installed")
        time.sleep(4)


def _spotify_token():
    import base64
    cid = _secret("arinze-spotify-id")
    sec = _secret("arinze-spotify-secret")
    auth = base64.b64encode((cid + ":" + sec).encode()).decode()
    r = requests.post("https://accounts.spotify.com/api/token", data={"grant_type": "client_credentials"},
                      headers={"Authorization": "Basic " + auth}, timeout=15)
    if r.status_code != 200:
        raise RuntimeError("Spotify login failed (%d)" % r.status_code)
    return r.json()["access_token"]


def spotify_play(query):
    q = str(query).strip()[:120]
    if not q:
        raise ValueError("what should I play?")
    _spotify_ready()
    try:
        token = _spotify_token()
    except RuntimeError as e:
        _run(["open", "spotify:search:" + urllib.parse.quote(q)])
        return "Could not search Spotify (%s). I opened a search for '%s' instead, press play yourself." % (e, q)
    r = requests.get("https://api.spotify.com/v1/search", params={"q": q, "type": "track", "limit": 1},
                     headers={"Authorization": "Bearer " + token}, timeout=15)
    items = r.json().get("tracks", {}).get("items", []) if r.status_code == 200 else []
    if not items:
        return "Spotify found nothing for '%s'." % q
    t = items[0]
    if not re.match(r"^spotify:track:[A-Za-z0-9]+$", t["uri"]):
        raise RuntimeError("odd track id")
    _osa('tell application "Spotify" to play track "%s"' % t["uri"])
    return "Playing %s by %s." % (t["name"], ", ".join(a["name"] for a in t["artists"]))


def spotify_control(action):
    a = str(action).lower().strip()
    if not _spotify_running():
        raise ValueError("Spotify is not running")
    scripts = {
        "play": 'tell application "Spotify" to play',
        "pause": 'tell application "Spotify" to pause',
        "next": 'tell application "Spotify" to next track',
        "previous": 'tell application "Spotify"\nset player position to 0\nprevious track\nend tell',
    }
    a = {"back": "previous", "prev": "previous", "skip": "next", "resume": "play"}.get(a, a)
    if a not in scripts:
        raise ValueError("action must be play, pause, next or previous")
    _osa(scripts[a])
    time.sleep(0.5)
    return "Done (%s). %s" % (a, spotify_now_playing())


def spotify_now_playing():
    if not _spotify_running():
        return "Spotify is not running."
    return "Now playing: " + _osa('tell application "Spotify" to (name of current track) & " by " & (artist of current track)')


def spotify_like():
    if not _spotify_running():
        raise ValueError("Spotify is not running")
    before = spotify_now_playing()
    _osa('tell application "Spotify" to activate')
    time.sleep(0.8)
    _osa('tell application "System Events" to keystroke "b" using {option down, shift down}')
    return "Sent Spotify's Like shortcut (Option+Shift+B). " + before


def youtube_play(query, browser=None):
    q = str(query).strip()[:120]
    if not q:
        raise ValueError("what should I search for?")
    vid = None
    try:
        r = requests.get("https://www.youtube.com/results", params={"search_query": q}, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9", "Cookie": "CONSENT=YES+cb; SOCS=CAI"})
        m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
        vid = m.group(1) if m else None
    except Exception:
        pass
    if vid:
        url = "https://www.youtube.com/watch?v=" + vid
    else:
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(q)
    msg = open_url(url, browser)
    if vid:
        return "Playing the top YouTube result for '%s'. %s" % (q, msg)
    return "Could not pick a video, so I opened the YouTube search for '%s'. %s" % (q, msg)


"""

def rep(old, new):
    global s
    assert s.count(old) == 1, (old[:60], s.count(old))
    s = s.replace(old, new)

rep("def _sb(project, method, table, params=None, body=None):", NEW + "def _sb(project, method, table, params=None, body=None):")
rep('    "open_url": (open_url, None),\n',
    '    "open_url": (open_url, None),\n'
    '    "spotify_play": (spotify_play, None),\n'
    '    "spotify_control": (spotify_control, None),\n'
    '    "spotify_now_playing": (spotify_now_playing, None),\n'
    '    "spotify_like": (spotify_like, None),\n'
    '    "youtube_play": (youtube_play, None),\n')
rep('open_url {"url": "https://...", "browser": "chrome" or "safari"}\n',
    'open_url {"url": "https://...", "browser": "chrome" or "safari"}\n'
    'spotify_play {"query": "song and artist"} | spotify_control {"action": "play"/"pause"/"next"/"previous"}\n'
    'spotify_now_playing {} | spotify_like {}  (likes the current song)\n'
    'youtube_play {"query": "what to watch", "browser": "chrome" or "safari"}\n')
open(p, "w", encoding="utf-8").write(s)
print("patched")
