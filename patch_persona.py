import re
src = open("arinze.py").read()
new = '''def load_system():
    try:
        persona = open(os.path.expanduser("~/Arinze/persona.txt"), encoding="utf-8").read().strip()
    except Exception:
        persona = "You are Arinze, a small glowing orb companion who lives on the user's Mac desktop."
    return (persona + "\\n\\n"
        "RULES: Keep replies under 25 words. Reply ONLY with JSON like this: "
        '{"expression": "happy", "say": "Good morning! Ready when you are."} '
        "The expression must be exactly one of: " + ", ".join(NAMES) + ". "
        "Meanings: idle=neutral, happy=pleased, wink=playful, pain=ouch or surprised, "
        "shy=embarrassed or complimented, thinking=pondering, alert=listening, angry=mad, "
        "sad=sad, sleeping=sleepy, tired=weary, working=busy with a task, annoyed=irritated, "
        "loved=very affectionate, confused=does not understand.")

SYSTEM = load_system()
'''
out, n = re.subn(r"SYSTEM = \(.*?\n\)\n", lambda m: new, src, count=1, flags=re.S)
if n != 1:
    raise SystemExit("Could not patch arinze.py, tell Claude")
open("arinze.py", "w").write(out)
print("Patched OK")
