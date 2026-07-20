# 06-05 SUMMARY — REG-05 masked-elastix trial

**Status:** Complete (answered in-GUI, 2026-07-20)

## What was done
REG-05's question — *does elastix earn its keep?* — was answered **KEEP**, in-GUI, on all 5 sections
(not the planned separate out-of-ABBA CLI trial on one worst section). ABBA's built-in `Elastix 2D
Affine` + `Elastix 2D Spline (15 pts)`, with atlas **Nissl (Ch0)** fixed / DAPI (Ch2) moving, visibly
improved the fit and is now part of the standard pipeline.

## Decision: KEEP
- **Root cause found:** the 2026-06-23 "elastix degrades" failure was substantially the **wrong atlas
  fixed channel** (Label Borders Ch2, no DAPI-intensity correspondence), not only the missing mask.
  With Nissl (Ch0), in-GUI elastix Affine+Spline works. **This overturns the locked "No Affine+Spline
  in ABBA" decision** (recorded in STATE.md Key Decisions).
- Per operator decision, the redundant out-of-ABBA CLI trial is skipped; the Wave-1 scripts
  (`extract_atlas_plate.py`, `elastix_trial_harness.py`, `Par_Affine/BSpline.txt`) are retained as
  tested tools (all pass `--self-test`).

## Artifacts
- `06-REG05-FINDINGS.md` — filled (in-GUI KEEP + root cause).
- Wave-1 REG-05 scripts (self-tested, unused this run, retained).

## Open
- In-GUI elastix mask status TBC — resolve at the QuPath annotation-overlay check (Phase 8).
