# ABBA Atlas Registration — Detail Guide

**Screenshot to be captured during the 06.1-06 operator validation run.** The
image slots below are placeholders — they will be filled in the next time
this stage is run end-to-end.

`[GUI]` — this stage is entirely manual, performed in Fiji. It is one of the
two most error-prone steps in the pipeline (the other is
[BraiAnDetect detection](02-detection.md)), and this is the exact seam the
**D-15 "ABBA registration present" boundary assert** guards downstream:
`01_load_abba_rois.groovy`, `02_detect_classify.groovy`, and
`03_export_region_table.groovy` all check
`AtlasTools.getAvailableAtlasRegistration(...)` before doing any work, and
abort with a clear message if this stage hasn't produced its output files
yet.

## Prerequisites

- QuPath v0.6.0 with the **ABBA extension** installed (BIOP catalog,
  `qupath-extension-abba`).
- **Fiji** with the ABBA plugin (`PTBIOP` update site) — a standalone Fiji
  install, not QuPath itself.
- **elastix 5.2.0** on the path Fiji/ABBA expects (`LD_LIBRARY_PATH` pointing
  at `elastix/lib`) — ABBA requires exactly this version.
- The section's MIP OME-TIFF already imported as an entry in a **QuPath
  project** (see step 1 of the pipeline overview in
  [docs/index.md](../index.md)).

## Known pitfall: import FROM the QuPath project, never Bio-Formats

**Always create the QuPath project first, then in standalone Fiji ABBA use
`Import > Import QuPath Project`** to load the image into the registration
session — never `Import > Import With Bio-Formats`.

Why this matters: ABBA's export step (`Export Registrations To QuPath
Project`) writes `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` into the
QuPath entry's `data/<N>/` folder, keyed by a QuPath-entry link that is
established **only** at `Import QuPath Project` time. If you instead import
via Bio-Formats, the slice carries no QuPath-entry link and the export fails
with a "needs to be linked" error — even though a QuPath project with the
identical image file exists. There is no reliable GUI path to relink a
Bio-Formats-imported registration back onto a QuPath project afterward — if
you hit this, the practical fix is to re-register from a fresh
`Import QuPath Project` import (cheap the second time if you already know the
working slicing angle for this animal).

## Workflow

1. **Launch Fiji, open ABBA:** `Plugins > BIOP > Atlas > ABBA`.
2. **Import the image** via `Import > Import QuPath Project` (see pitfall
   above) and select the section(s) to register.
3. **Run DeepSlice** to get an initial AP (anterior-posterior) position
   estimate for each section.
4. **Set the slicing angle manually, using Review Mode.** ABBA's slicing
   angle is a single **global** plane shared by every section in the
   project — there is no per-section through-plane tilt. For a series from
   the same animal, find the best series-wide compromise angle once (leave
   DeepSlice's "Allow change of atlas slicing angle" unchecked and set the
   angle by hand instead), then fix each section's residual misalignment with
   per-section tools: in-plane rotation/translation of the individual slice,
   and BigWarp.
   - A misalignment that's offset by hundreds of microns in one lateral
     region (e.g. amygdala) after tilt is usually a genuine through-plane
     cutting-angle issue, not something a Spline can fix by adding control
     points.
   - If elastix registration is used at all, point the **fixed (atlas)
     channel at Nissl (Ch0)**, never Label Borders (Ch2) — Label Borders is a
     line-drawing with no intensity correspondence to DAPI, so
     intensity-based registration cannot lock onto it.
5. **Refine with BigWarp** if hippocampal/cortical subfields still don't
   line up after tilt + AP adjustment: place 4-6 landmarks on stable
   anatomical features (e.g. CA1/CA3 boundary, DG tip, ventral edge, dorsal
   cortex margin), then run BigWarp from the adjusted state.
6. **Export the registration to the QuPath project:**
   ```
   Plugins > Atlas > Multi Image To Atlas > Export
     -> "ABBA - Export Registrations To QuPath Project"
   ```

![DeepSlice panel](../assets/reg-01-deepslice.png)
![Review Mode tilt adjustment](../assets/reg-02-review-mode.png)
![ABBA export dialog](../assets/reg-03-export.png)

## Outputs consumed downstream

The export writes, into the QuPath project's `data/<entry>/` directory:

- `ABBA-Transform-allen_mouse_10um_java.json` — the invertible transform
  chain (Affine3D + ThinplateSpline) mapping image pixels to Allen CCFv3
  atlas space.
- `ABBA-RoiSet-allen_mouse_10um_java.zip` — the atlas region ROIs, already
  warped into this section's pixel space.

`scripts/01_load_abba_rois.groovy` (the next `[SCRIPTABLE]` step) reads these
two files via `AtlasTools.loadWarpedAtlasAnnotations(...)` and calls
`resolveHierarchy()` to establish the parent/child region nesting that
`03_export_region_table.groovy`'s per-region rollup depends on.

## Channel-index reminder

If a registration step (BigWarp or elastix) throws a "missing channels"
error, it's almost always a channel-**index** mismatch in the registration
dialog, not a data problem — the moving/fixed "channels to use" fields are
0-based indices, and they don't carry over between datasets with different
channel counts (e.g. a single-channel DAPI image only has index 0, even if a
different multi-channel MIP in the same project has DAPI at index 2).
