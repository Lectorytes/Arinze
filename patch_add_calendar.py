from pathlib import Path

p = Path.home() / "Arinze" / "arinze_tools.py"
text = p.read_text(encoding="utf-8")

if "def calendar_list" in text:
    print("Already added. Nothing to do.")
    raise SystemExit(0)

block = r'''
# ---- calendar + system settings
def get_power():
    code, out = _run(["pmset", "-g", "batt"], timeout=5)
    if code != 0:
        return "ERROR: " + out
    ac = "AC Power" in out
    m = re.search(r"(\d+)%", out)
    pct = m.group(1) if m else "?"
    return "Battery %s%%, power: %s." % (pct, "charger" if ac else "battery")


def system_setting(setting):
    s = str(setting).lower().strip()
    if s in ("dark_mode", "dark"):
        _osa('tell application "System Events" to tell appearance preferences to set dark mode to true')
        return "Dark mode on."
    if s in ("light_mode", "light"):
        _osa('tell application "System Events" to tell appearance preferences to set dark mode to false')
        return "Light mode on."
    if s in ("toggle_dark_mode", "toggle_dark"):
        _osa('tell application "System Events" to tell appearance preferences to set dark mode to not dark mode')
        return "Toggled dark/light mode."
    if s in ("sleep_display", "display_sleep"):
        code, out = _run(["pmset", "displaysleepnow"], timeout=5)
        return "Display sleeping." if code == 0 else "ERROR: " + out
    if s in ("lock_screen", "lock"):
        _osa('tell application "System Events" to keystroke "q" using {command down, control down}')
        return "Lock screen triggered."
    raise ValueError("setting must be dark_mode, light_mode, toggle_dark_mode, sleep_display, or lock_screen")


def calendar_list(days=7):
    d = max(1, min(14, int(days)))
    script = (
        'tell application "Calendar"\n'
        "set startDate to (current date)\n"
        "set time of startDate to 0\n"
        "set endDate to startDate + (%d * days)\n"
        "set lines to {}\n"
        "repeat with c in calendars\n"
        "try\n"
        "set evts to (every event of c whose start date >= startDate and start date < endDate)\n"
        "repeat with e in evts\n"
        'set end of lines to (summary of e) & " | " & ((start date of e) as string) & " | " & (name of c)\n'
        "end repeat\n"
        "end try\n"
        "end repeat\n"
        "set AppleScript's text item delimiters to linefeed\n"
        "return lines as text\n"
        "end tell"
    ) % d
    code, out = _run(["osascript", "-e", script], timeout=45)
    if code != 0:
        raise RuntimeError("Calendar access failed. Allow Automation for Calendar. " + out[:200])
    if not out.strip():
        return "No events in the next %d day(s)." % d
    lines = [ln for ln in out.splitlines() if ln.strip()][:30]
    return "Upcoming (%dd):\n%s" % (d, "\n".join(lines))


def ask_calendar_add(title, start, end=None, calendar=None, notes=None):
    return "ADD calendar event:\n\n%s\nat %s%s" % (
        str(title), str(start), ("\nuntil " + str(end)) if end else "")


def calendar_add(title, start, end=None, calendar=None, notes=None):
    title = str(title).strip()
    if not title:
        raise ValueError("missing title")
    start = str(start).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})$", start)
    if m:
        y, mo, d, h, mi = [int(x) for x in m.groups()]
    else:
        m = re.match(r"^(today|tomorrow)\s+(\d{1,2}):(\d{2})$", start, re.I)
        if not m:
            raise ValueError('start must look like "2026-10-29 15:00" or "tomorrow 10:00"')
        off = 0 if m.group(1).lower() == "today" else 1
        t = time.localtime(time.time() + off * 86400)
        y, mo, d = t.tm_year, t.tm_mon, t.tm_mday
        h, mi = int(m.group(2)), int(m.group(3))
    if end and re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})$", str(end).strip()):
        m2 = re.match(r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})$", str(end).strip())
        y2, mo2, d2, h2, mi2 = [int(x) for x in m2.groups()]
    else:
        t2 = time.mktime((y, mo, d, h, mi, 0, 0, 0, -1)) + 3600
        lt = time.localtime(t2)
        y2, mo2, d2, h2, mi2 = lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min
    if calendar:
        cal_line = 'set targetCal to calendar "%s"' % str(calendar).replace('"', "")
    else:
        cal_line = "set targetCal to first calendar"
    safe = title.replace('"', "'")
    notes_bit = ""
    if notes:
        notes_bit = ', description:"%s"' % str(notes).replace('"', "'")[:200]
    script = (
        'tell application "Calendar"\n'
        + cal_line + "\n"
        "set s to current date\n"
        "set year of s to %d\nset month of s to %d\nset day of s to %d\n"
        "set hours of s to %d\nset minutes of s to %d\nset seconds of s to 0\n"
        "set e to current date\n"
        "set year of e to %d\nset month of e to %d\nset day of e to %d\n"
        "set hours of e to %d\nset minutes of e to %d\nset seconds of e to 0\n"
        "tell targetCal\n"
        'make new event with properties {summary:"%s", start date:s, end date:e%s}\n'
        "end tell\nreturn \"ok\"\nend tell"
    ) % (y, mo, d, h, mi, y2, mo2, d2, h2, mi2, safe, notes_bit)
    code, out = _run(["osascript", "-e", script], timeout=45)
    if code != 0:
        raise RuntimeError("Could not add event. Allow Automation for Calendar. " + out[:200])
    return 'Created "%s" at %04d-%02d-%02d %02d:%02d.' % (title, y, mo, d, h, mi)

'''

marker = "\nTOOLS = {"
if marker not in text:
    raise SystemExit("Could not find TOOLS = { in arinze_tools.py")
text = text.replace(marker, block + marker, 1)

old = '"create_file": (create_file, ask_create),\n}'
new = (
    '"create_file": (create_file, ask_create),\n'
    '    "get_power": (get_power, None),\n'
    '    "system_setting": (system_setting, None),\n'
    '    "calendar_list": (calendar_list, None),\n'
    '    "calendar_add": (calendar_add, ask_calendar_add),\n'
    "}"
)
if old not in text:
    raise SystemExit("Could not find create_file line in TOOLS")
text = text.replace(old, new, 1)

old_doc = 'replace_in_file {"project", "path", "old", "new"} | create_file {"project", "path", "content"}"""'
new_doc = (
    'replace_in_file {"project", "path", "old", "new"} | create_file {"project", "path", "content"}\n'
    "get_power {}\n"
    'system_setting {"setting": "dark_mode"/"light_mode"/"toggle_dark_mode"/"sleep_display"/"lock_screen"}\n'
    'calendar_list {"days": 7}\n'
    'calendar_add {"title": "...", "start": "YYYY-MM-DD HH:MM" or "tomorrow 10:00", "end": optional}"""'
)
if old_doc not in text:
    raise SystemExit("Could not find TOOL_DOC ending")
text = text.replace(old_doc, new_doc, 1)

p.write_text(text, encoding="utf-8")
print("OK: calendar + system tools added")