---
phase: 03-detection-script-and-single-section-end-to-end-test
plan: 02
subsystem: detection-pipeline
tags: [qupath, groovy, abba, atlas-registration, measurementlist, ccfv3]

# Dependency graph
requires:
  - phase: 03-detection-script-and-single-section-end-to-end-test (Plan 01)
    provides: "regionAnnotations/regionOf/regionLabel closures (leaf-annotation centroid-in-ROI lookup) and the compound-classification loop over detections in scripts/02_detect_classify.groovy"
provides:
  - "Per-class (Negative/Fos+/TdT+/Double+/Excluded) count rollup written onto CA1/CA2/CA3/DG-* leaf region annotations via MeasurementList.put, rendering in QuPath's annotation-pane measurement table (SC4)"
  - "Atlas_X/Y/Z micron sanity print for up to 5 sampled Fos+/TdT+/Double+ classified cells via AtlasTools.getAtlasToPixelTransform(imageData).inverse() (SC3)"
affects: [03-03-background-robust-measure, 03-04-human-in-the-loop-run]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Count rollup: iterate leaf region annotations, count classified detections via roi.contains(centroidX, centroidY) into a per-class map, write each class as a numeric MeasurementList.put(\"Count: <class>\", n) entry on the annotation"
    - "Atlas coordinate sanity print: AtlasTools.getAtlasToPixelTransform(imageData).inverse().apply(RealPoint, RealPoint) in-place on a 3-element RealPoint built from (centroidX, centroidY, 0d), sampled on a small (<=5) subset only — not a full per-cell export column"

key-files:
  created: []
  modified:
    - scripts/02_detect_classify.groovy
    - "M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy"

key-decisions:
  - "Count rollup reuses the regionAnnotations/regionOf centroid-in-ROI machinery from Plan 01 rather than reading the pre-existing results/<image>_regions.tsv, which reflects BraiAnDetect's incompatible classifier application and predates this script's classification (RESEARCH Pitfall 1)"
  - "Atlas_X sanity print is a lightweight console check on <=5 sampled classified cells, not a full per-cell Atlas_X/Y/Z export column (that is v2 EXP-01/EXP-03, per 03-CONTEXT.md Claude's-Discretion)"
  - "No hard-coded unit conversion applied to the printed Atlas_X values; the x10 voxel-index fallback (allen_mouse_10um_java is 10 um/voxel) is documented as a comment only, treating SC3 itself as the empirical print-and-check verification"

patterns-established:
  - "Pattern 4 (count rollup to annotation measurements) and Pattern 5 (Atlas_X sanity print) from 03-RESEARCH.md, both implemented as documented"

requirements-completed: [SCRI-03]

coverage:
  - id: D1
    description: "Per-class count rollup (Count: Negative/Fos+/TdT+/Double+/Excluded) written onto CA1/CA2/CA3/DG-* leaf region annotations via MeasurementList.put, with a matching console table"
    requirement: "SCRI-03"
    verification:
      - kind: other
        ref: "grep -Eq 'Count: ' scripts/02_detect_classify.groovy && grep -q 'getMeasurementList' scripts/02_detect_classify.groovy && grep -Eq 'put\\(' scripts/02_detect_classify.groovy && cmp scripts/02_detect_classify.groovy \"M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy\""
        status: pass
    human_judgment: true
    rationale: "Static source checks (grep/cmp) confirm the code is authored correctly, but whether CA1/CA2/CA3/DG annotations actually display populated Count: * columns in QuPath's live annotation-pane measurement table can only be confirmed by a human running the script in QuPath (GUI-only per CLAUDE.md) — deferred to Plan 03-04's human-in-the-loop run."
  - id: D2
    description: "Atlas_X/Y/Z micron sanity print for a sample (<=5) of classified cells via AtlasTools.getAtlasToPixelTransform(imageData).inverse(), with a documented x10 voxel-index fallback and a guarded skip path when no transform is available"
    requirement: "SCRI-03"
    verification:
      - kind: other
        ref: "grep -q 'AtlasTools' scripts/02_detect_classify.groovy && grep -q 'getAtlasToPixelTransform' scripts/02_detect_classify.groovy && grep -q 'RealPoint' scripts/02_detect_classify.groovy && grep -Eq 'Atlas_X' scripts/02_detect_classify.groovy && cmp scripts/02_detect_classify.groovy \"M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy\""
        status: pass
    human_judgment: true
    rationale: "Static source checks confirm the transform call, imports, and print statement are present, but whether the printed Atlas_X values actually fall in the 5,000-10,000 um range (confirming CCFv3 microns, not mm or voxel indices) can only be confirmed by a human running the script in QuPath against the live ABBA registration — deferred to Plan 03-04."

duration: 7min
completed: 2026-07-10
status: complete
---

# Phase 3 Plan 02: Per-Region Count Rollup + Atlas_X Micron Sanity Print Summary

**Per-class count rollup onto CA1/CA2/CA3/DG-* annotation measurements (SC4) and an Atlas_X/Y/Z micron sanity print via AtlasTools for sampled classified cells (SC3), both layered read-only onto Plan 01's classification path.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-09T23:49:24-04:00 (immediately following Plan 01's last commit)
- **Completed:** 2026-07-09T23:55:57-04:00
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Per-class (Negative/Fos+/TdT+/Double+/Excluded) counts now written as numeric `Count: <class>` measurements onto every leaf region annotation (CA1, CA2, CA3, DG-mo/DG-po/DG-sg, and any other leaf region) via `MeasurementList.put`, so they render natively in QuPath's annotation-pane measurement table (SC4), with a matching console table.
- Atlas_X/Y/Z micron sanity print added for up to 5 sampled Fos+/TdT+/Double+ classified cells, using the official `AtlasTools.getAtlasToPixelTransform(imageData).inverse()` pattern, with a guarded skip path if no ABBA transform is available and a documented (not hard-coded) x10 voxel-index fallback comment (SC3).
- Both script copies (canonical `scripts/` and the QuPath project's spaced-path `scripts/` directory) remain byte-identical after each task.

## Task Commits

Each task was committed atomically:

1. **Task 1: Roll per-class counts onto CA1/CA2/CA3/DG annotation measurements (SC4)** - `ff7e6a6` (feat)
2. **Task 2: Atlas_X micron sanity print for a sample of classified cells (SC3)** - `269fdc3` (feat)

**Plan metadata:** (pending — final commit below)

## Files Created/Modified
- `scripts/02_detect_classify.groovy` - Extended with the SC4 count-rollup block (per-class `Count: *` MeasurementList writes on leaf region annotations) and the SC3 Atlas_X/Y/Z sanity-print block (AtlasTools transform, sampled cells, documented x10 fallback comment)
- `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` - Byte-identical project hard-copy, re-synced after each task

## Decisions Made
- Count rollup treats the annotation-measurement write as the sole authoritative SC4 mechanism, explicitly not reading the pre-existing `results/<image>_regions.tsv` (stale — reflects BraiAnDetect's incompatible classifier application per Deviation #1 from Plan 02-01).
- Atlas_X sanity print stays a lightweight console check (<=5 sampled cells), not a full per-cell export column — that scope is reserved for a future v2 requirement (EXP-01/EXP-03).
- No unit conversion is hard-coded on the printed Atlas_X values; the plan's SC3 acceptance criterion is itself the empirical print-and-check gate for the microns-vs-voxel-index question, with the x10 fallback documented only as a comment for the human to apply if needed.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the RESEARCH.md Pattern 4 / Pattern 5 code templates closely, adapted only to reuse the existing `regionAnnotations`/`regionLabel` closures already present in the script from Plan 01.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness

- Static/source verification (grep + `cmp`) passed for both tasks; the plan's `<human-check>` steps (confirming `Count: *` columns render in QuPath's live annotation pane, and that printed Atlas_X values fall in [5000, 10000] µm) are GUI-only per CLAUDE.md and are explicitly deferred to Plan 03-04's human-in-the-loop run, per this project's GUI-human-only constraint — QuPath/Fiji were not launched and the script was not executed as part of this plan.
- SCRI-03 requirement remains NOT marked fully complete until Plan 03-04 confirms the "tested on one section" criterion live in QuPath.
- Next: Plan 03-03 — background-robust (local-background-subtraction) Fos/TdT measure (D-03/D-04/D-05), re-deriving thresholds on the new measurement before Plan 03-04's human-in-the-loop run.

## Self-Check: PASSED

All created/modified files exist on disk and both task commit hashes (`ff7e6a6`, `269fdc3`) are present in git log.

---
*Phase: 03-detection-script-and-single-section-end-to-end-test*
*Completed: 2026-07-10*
