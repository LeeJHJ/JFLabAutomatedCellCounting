# Presentation Screenshot Index
## Save screenshots into this folder with the filenames below

---

### SLIDE 4 — Imaging Parameters
**File:** `slide04_zen_acquisition_settings.png`
**What it shows:** ZEN Blue acquisition panel showing channels, laser lines, Z-stack settings, and tile configuration  
**Status:** ❌ **Still need to capture** — take on acquisition PC next session  
**Notes:** Screenshot the Channels tab + Z-stack tab in ZEN Blue during or after an acquisition setup

---

### SLIDE 6 — QuPath Project Setup
**File:** `slide06_qupath_correct_channels.png`  
**What it shows:** QuPath image viewer with correct channel names (AF568-T2, AF488-T3, DAPI-T4) visible in the channel panel  
**Status:** ✅ You have this — save from conversation (2026-06-22 session)  
**Notes:** Shows the clean OME-TIFF import with proper ZEN channel names

---

### SLIDE 7 — ABBA Overview
**File:** `slide07_abba_bdv_interface.png`  
**What it shows:** ABBA BDV window with sources panel on the right (SlicingModel rows, ROI row highlighted pink), section visible as blue brain in lower panel, atlas in upper panel  
**Status:** ✅ You have this — save from THIS conversation  
**Notes:** Good for showing what the ABBA interface looks like

---

### SLIDE 8 — DeepSlice AP Positioning
**File:** `slide08_deepslice_dialog.png`  
**What it shows:** ABBA DeepSlice dialog / the sagittal view after DeepSlice places the section  
**Status:** ✅ You have this — save from conversation (2026-06-22 session, showed channel=0 then channel=2 fix)  
**Notes:** Consider using the CORRECT one (channel set to 2/DAPI)

---

### SLIDE 9 — Manual Angle Adjustment
**File:** `slide09a_bad_overlay.png` ← BEFORE tilt fix  
**File:** `slide09b_good_overlay.png` ← AFTER tilt fix  
**What it shows:** Side-by-side comparison of misaligned atlas (LA offset visible) vs corrected alignment  
**Status:** ⚠️ Partial — you have the good overlay from THIS conversation. The "before" (misaligned) overlay was shared in previous session — save from conversation history  
**Notes:** This is the most impactful slide — the before/after is very visual

---

### SLIDE 10 — BigWarp
**File:** `slide10_bigwarp_menu.png`  
**File:** `slide10_fiji_plugins_menu.png`  
**What it shows:** (1) Fiji plugins menu open showing BIOP → Atlas → Multi Image To Atlas → Align → ABBA - BigWarp Registration path; (2) BigWarp split-panel view with landmarks  
**Status:** ✅ Fiji menu — you have this from THIS conversation  
**Status:** ❌ BigWarp split panel — **still need to capture** while using BigWarp  
**Notes:** Fiji menu screenshot clearly shows the navigation path

---

### SLIDE 11 — Why Not Elastix / Registration Quality
**File:** `slide11_near_perfect_overlay.png`  
**What it shows:** The near-perfect QuPath atlas overlay — colorful region boundaries fitted tightly to the brain section, LA well-aligned  
**Status:** ✅ You have this — save from THIS conversation  
**Notes:** This is the best result screenshot — use as the "final good registration" example

---

### SLIDE 12 — Cell Detection
**File:** `slide12_detection_params.png`  
**File:** `slide12_detection_overlay.png`  
**What it shows:** (1) QuPath cell detection parameter panel (sigma=1.5, threshold=2000, expansion=4µm); (2) Detection overlay on LA showing individual nuclei  
**Status:** ✅ You have both — save from conversation (2026-06-22 session)  
**Notes:** The params screenshot was shared as "just for reference" at the end of detection tuning

---

### SLIDE 13 — Cell Classification
**File:** `slide13_classified_cells.png`  
**What it shows:** QuPath viewer with TdTomato+ (red), Fos+ (green), Double+ (yellow), Negative (gray) cell dots overlaid on the section  
**Status:** ❌ **Still need to capture** — run classification script first  

---

## Screenshots Still Needed (Capture These)

| Priority | Screenshot | When to Capture |
|----------|-----------|----------------|
| High | BigWarp split panel with landmarks placed | During your next BigWarp session |
| High | Before/after tilt correction side-by-side | Recreate in ABBA: load old bad registration + good one |
| High | Classified cells (TdT+/Fos+/Double+) | After running classification Groovy script |
| Medium | ZEN Blue export dialog | Next time on acquisition PC |
| Medium | Terminal: czi_to_mip.py running | Next time processing a new section |
| Low | DeepSlice terminal output showing AP estimate | Next time running run_deepslice.py |

---

## Saving Instructions

For screenshots from this Claude conversation:
1. Right-click each image in the chat → Save Image As
2. Name it using the filename above
3. Drop it into `~/Analysis/presentation_screenshots/`
