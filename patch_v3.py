src = open("arinze.py").read()

def rep(old, new):
    global src
    if src.count(old) != 1:
        raise SystemExit("Could not patch (" + old[:40] + "). Tell Claude.")
    src = src.replace(old, new)

rep('''NAMES = ["idle","happy","wink","pain","shy","thinking","alert","angry",
         "sad","sleeping","tired","working","annoyed","loved","confused"]''',
'''NAMES = ["idle","happy","wink","pain","shy","thinking","alert","angry",
         "sad","sleeping","tired","working","annoyed","loved","confused",
         "irritated","bashful","big_smile","sassy","pleading","bored","puzzled",
         "content","sunglasses","cool","crying","deadpan","determined",
         "devastated","cheerful","evil_grin","fire_angry","flirty",
         "frustrated","furious"]''')

rep('''        "Meanings: idle=neutral, happy=pleased, wink=playful, pain=ouch or surprised, "
        "shy=embarrassed or complimented, thinking=pondering, alert=listening, angry=mad, "
        "sad=sad, sleeping=sleepy, tired=weary, working=busy with a task, annoyed=irritated, "
        "loved=very affectionate, confused=does not understand.")''',
'''        "Meanings: idle=neutral, happy=pleased, wink=playful, pain=ouch or startled, "
        "shy=embarrassed or complimented, thinking=pondering, alert=listening, angry=mad, "
        "sad=sad, sleeping=sleepy, tired=weary, working=busy with a task, annoyed=mildly annoyed, "
        "loved=very affectionate, confused=dizzy or overwhelmed, irritated=grumpy, "
        "bashful=shy and blushing, big_smile=laughing or very happy, sassy=sassy attitude, "
        "pleading=begging with sparkly eyes, bored=bored, puzzled=curious or unsure, "
        "content=peaceful and satisfied, sunglasses=feeling super cool, cool=smug smirk, "
        "crying=crying hard, deadpan=unimpressed, determined=focused and resolute, "
        "devastated=heartbroken, cheerful=gently smiling, evil_grin=mischievous, "
        "fire_angry=blazing rage, flirty=teasing and flirty, frustrated=frustrated, "
        "furious=very angry. Pick the face that best matches your feeling.")''')

rep('''        if len(self.pokes) >= 4:
            self.rage_until = now + 6.0
            self.set_expression("angry", 6.0)
        else:
            self.set_expression("angry", 2.2)''',
'''        n = len(self.pokes)
        if n >= 4:
            self.rage_until = now + 6.0
            self.set_expression("fire_angry", 6.0)
        elif n == 3:
            self.set_expression("furious", 2.5)
        elif n == 2:
            self.set_expression("angry", 2.2)
        else:
            self.set_expression("irritated", 2.2)''')

rep('''            self.start_bounce("play")
            self.set_expression("happy", 3.0)''',
'''            self.start_bounce("play")
            self.set_expression(random.choice(["happy", "big_smile", "cheerful"]), 3.0)''')

rep('''        if calm and idle_for > 600 and self.cur in ("idle", "happy"):''',
    '''        if calm and idle_for > 600 and self.cur in ("idle", "happy", "big_smile", "cheerful"):''')

open("arinze.py", "w").write(src)
print("Patched OK")
