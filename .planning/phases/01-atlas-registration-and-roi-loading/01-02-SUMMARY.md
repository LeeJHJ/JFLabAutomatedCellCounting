---
plan: 01-02
phase: 01-atlas-registration-and-roi-loading
status: complete
completed: 2026-07-02
requirements_addressed: [REG-01]
---

# Plan 01-02 Summary: ABBA Registration and Export

## What Was Built

Registered entry 1 (M3_20x_MIP_Z1-3.ome.tiff) of the "M3 Hippocampus 20x 062926 3 plane" QuPath project to the Allen CCFv3 atlas in Fiji ABBA, and exported the registration into the project's `data/1/` directory.

## Artifacts Produced

| File | Size | Notes |
|------|------|-------|
| `data/1/ABBA-Transform-allen_mouse_10um_java.json` | 9.3 KB | Larger than baseline ~7 KB; BigWarp landmarks included |
| `data/1/ABBA-RoiSet-allen_mouse_10um_java.zip` | 1.3 MB | Within expected range |

## Registration Workflow Used

- **DeepSlice** (local, single-section patch applied): AP position estimate
- **Review Mode**: DV/ML tilt angle adjusted manually
- **BigWarp**: 4–6 landmarks placed on CA1/CA3 boundary, DG tip, ventral edge, dorsal cortex margin to correct residual hippocampal and dorsal cortex misalignment
- **Elastix Affine/Spline**: tried and confirmed to degrade result (diverged from web DeepSlice output) — not used in final registration

## Deviations from Plan

- **BigWarp added**: Plan specified "DeepSlice + manual angle ONLY", but hippocampus and dorsal cortex remained misaligned after tilt correction. BigWarp escalation was approved to achieve subfield-level accuracy (CA1/CA3/DG). This is now the locked workflow for cases where tilt + AP adjustment are insufficient.
- **Elastix Spline confirmed broken**: Tried and produced worse results than the DeepSlice baseline. Confirms the hard constraint against elastix without tissue mask.
- **DeepSlice single-section bug patched**: Local DeepSlice CLI crashed with `ValueError: Only one section found, cannot space according to index`. Fixed by patching `spacing_and_indexing.py` to return early when n=1.

## Self-Check

- [x] ABBA-Transform-allen_mouse_10um_java.json present in data/1/ (non-zero, 9.3 KB)
- [x] ABBA-RoiSet-allen_mouse_10um_java.zip present in data/1/ (1.3 MB)
- [x] Files are in entry 1's data/1/, not data/2/
- [x] Registration used DeepSlice + manual angle + BigWarp (no elastix in final result)
- [x] Target project is 062926 3 plane (not the older 062226)
