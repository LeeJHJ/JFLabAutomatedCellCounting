import os, numpy as np, pandas as pd
os.environ.setdefault("DISPLAY", ":0")
SP = "/tmp/claude-1000/-home-jflab-Analysis/ece91a60-2a3f-4654-a80b-38b834ad8d83/scratchpad"
df = pd.read_csv(f"{SP}/cells_pos.csv")
def coords(sub, n=25000):
    if len(sub) > n: sub = sub.sample(n, random_state=0)
    return np.c_[sub.atlas_z_um, sub.atlas_y_um, sub.atlas_x_um]  # [AP, DV, ML]

from brainrender import Scene, settings
from brainrender.actors import Points
settings.SHOW_AXES = False
settings.WHOLE_SCREEN = False

scene = Scene(atlas_name="allen_mouse_25um", title="wBA1-3 amygdala engram (n=1)", screenshots_folder=SP)
for acr, col in [("LA", "#4da6ff"), ("BLA", "#7fbfff"), ("BMA", "#a9d4ff")]:
    try: scene.add_brain_region(acr, alpha=0.25, color=col, hemisphere="both")
    except Exception as e: print("region", acr, "skip:", e)

tdt = df[df["class"] == "TdT+"]; fos = df[df["class"] == "Fos+"]; dbl = df[df["class"] == "Double+"]
scene.add(Points(coords(fos), name="Fos+ (recall)",       colors="#33cc33", radius=18, alpha=0.5))
scene.add(Points(coords(tdt), name="TdT+ (engram)",       colors="#ff33cc", radius=18, alpha=0.6))
scene.add(Points(coords(dbl), name="Double+ (reactiv.)",  colors="#ffdd00", radius=28, alpha=0.9))

scene.render(interactive=False, zoom=1.3, camera="frontal")
scene.screenshot(name="wba1_engram_cloud", scale=2)
print("SCREENSHOT_OK")
