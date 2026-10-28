import os
p = os.path.expanduser("~/Arinze/arinze_tools.py")
s = open(p, encoding="utf-8").read()
a = s.index("def set_brightness(level):")
b = s.index("# ---- apps and websites")
new = '''def set_brightness(level):
    import ctypes
    n = max(5, min(100, int(float(level))))
    ds = ctypes.CDLL("/System/Library/PrivateFrameworks/DisplayServices.framework/DisplayServices")
    cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
    cg.CGMainDisplayID.restype = ctypes.c_uint32
    ds.DisplayServicesSetBrightness.argtypes = [ctypes.c_uint32, ctypes.c_float]
    ds.DisplayServicesSetBrightness.restype = ctypes.c_int
    ds.DisplayServicesGetBrightness.argtypes = [ctypes.c_uint32, ctypes.POINTER(ctypes.c_float)]
    ds.DisplayServicesGetBrightness.restype = ctypes.c_int
    disp = cg.CGMainDisplayID()
    if ds.DisplayServicesSetBrightness(disp, ctypes.c_float(n / 100.0)) != 0:
        raise RuntimeError("macOS refused the brightness change")
    time.sleep(0.3)
    cur = ctypes.c_float()
    if ds.DisplayServicesGetBrightness(disp, ctypes.byref(cur)) != 0:
        return "Sent brightness %d%% but could not read it back to confirm." % n
    actual = round(cur.value * 100)
    if abs(actual - n) > 5:
        raise RuntimeError("asked for %d%% but the screen is at %d%%" % (n, actual))
    return "Brightness set to %d%%." % actual


'''
s = s[:a] + new + s[b:]
open(p, "w", encoding="utf-8").write(s)
print("patched")
