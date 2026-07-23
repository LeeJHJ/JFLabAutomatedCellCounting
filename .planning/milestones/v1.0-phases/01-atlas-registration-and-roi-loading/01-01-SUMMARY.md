---
phase: 01-atlas-registration-and-roi-loading
plan: "01"
subsystem: groovy-scripting
tags:
  - abba
  - qupath
  - roi-loading
  - atlas-registration
  - groovy
dependency_graph:
  requires:
    - QuPath ABBA Extension v0.4.0 (already installed)
    - Fiji ABBA Plugin v0.11.1 (already installed; GUI step for REG-01)
  provides:
    - /home/jflab/Analysis/scripts/01_load_abba_rois.groovy (canonical script)
    - /home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/01_load_abba_rois.groovy (deployment copy)
  affects:
    - Plan 02 (ABBA registration in Fiji — GUI step; unblocked now that script is ready)
    - Plan 03 (script execution + QC — depends on both this plan and Plan 02)
tech_stack:
  added: []
  patterns:
    - JAR-verified 4-argument AtlasTools.loadWarpedAtlasAnnotations API
    - Guard on getAvailableAtlasRegistration before any load attempt
    - resolveHierarchy() post-load for BraiAnDetect parent-child nesting
    - Imports-at-bottom Groovy convention
    - clearAllObjects() with multi-line warning comment for Phase 3 re-run risk
key_files:
  created:
    - /home/jflab/Analysis/scripts/ (directory — canonical central pipeline scripts location)
    - /home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/ (directory — QuPath project scripts dir)
    - /home/jflab/Analysis/scripts/01_load_abba_rois.groovy (canonical source)
    - /home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/01_load_abba_rois.groovy (byte-identical hard copy)
  modified: []
decisions:
  - "4-argument loadWarpedAtlasAnnotations form used (ImageData, acronym, true, true) — verified from installed JAR bytecode"
  - "resolveHierarchy() included after load (Claude discretion per CONTEXT.md; required for BraiAnDetect region assignment)"
  - "clearAllObjects() retained with prominent multi-line warning comment (D-05; Phase 1 is pre-detection so no data loss risk)"
  - "atlasName variable defined at script top as allen_mouse_10um_java (D-06)"
  - "getAvailableAtlasRegistration guard added to fail loudly rather than silently if ABBA export not yet done"
metrics:
  duration: ~10 minutes
  completed: "2026-07-02"
  tasks_completed: 3
  tasks_total: 3
  files_created: 4
status: complete
---

# Phase 01 Plan 01: ROI-Loading Script Authoring Summary

ABBA ROI-loading script authored using JAR-verified 4-argument API, deployed to both the canonical `Analysis/scripts/` location and the target QuPath project `scripts/` directory.

## What Was Built

A QuPath Groovy script (`01_load_abba_rois.groovy`) that:

1. Prints the active entry name (Pitfall 5 guard — catches wrong-entry runs)
2. Calls `AtlasTools.getAvailableAtlasRegistration()` and returns early with a clear error if ABBA files are absent (Pitfall 1 guard — prevents silent no-ops)
3. Calls `clearAllObjects()` with a prominent multi-line warning about Phase 3 data loss risk and two documented remedies
4. Calls `AtlasTools.loadWarpedAtlasAnnotations(getCurrentImageData(), "acronym", true, true)` — the exact 4-argument public form extracted from the bundled JAR example
5. Calls `resolveHierarchy()` to establish parent-child atlas region nesting (required for BraiAnDetect region assignment)
6. Prints total annotation count and a "Next step" prompt to save the project and take the QC screenshot

The script was hard-copied (not symlinked) into the QuPath project's own `scripts/` directory, which is required for QuPath "Run for project" to discover it.

## Tasks Completed

| # | Task | Status | Key Output |
|---|------|--------|------------|
| 1 | Create scripts directories | Done | `/home/jflab/Analysis/scripts/` and `M3 Hippocampus 20x 062926 3 plane/scripts/` both created |
| 2 | Author 01_load_abba_rois.groovy | Done | All 9 required elements present; grep checks pass |
| 3 | Hard-copy into QuPath project scripts dir | Done | `diff` returns no differences; byte-identical copy confirmed |

## Deviations from Plan

None. Plan executed exactly as written.

## Script Content Verification

```
grep -q "allen_mouse_10um_java"              PASS
grep -q "loadWarpedAtlasAnnotations"         PASS
grep -q "getAvailableAtlasRegistration"      PASS
grep -q "resolveHierarchy"                   PASS
grep -q "clearAllObjects"                    PASS
grep -q "import qupath.ext.biop.abba.AtlasTools"  PASS
diff canonical vs project copy              PASS (byte-identical)
062226 project untouched                    PASS (no scripts/ dir created there)
```

## Threat Flags

None. The script hardcodes all paths and atlas names; no external input is interpolated. The `clearAllObjects()` data-loss risk (T-01-02) is mitigated by the warning comment.

## Known Stubs

None. This plan produces a Groovy script artifact, not a UI component. The script cannot be run until Plan 02 (ABBA Fiji GUI registration) produces the `ABBA-Transform-allen_mouse_10um_java.json` and `ABBA-RoiSet-allen_mouse_10um_java.zip` files — this is expected and the guard block handles that state correctly.

## What Comes Next

- **Plan 02 (ABBA Registration — GUI):** Researcher runs Fiji ABBA: DeepSlice AP estimate → manual DV/ML tilt review → export. This produces `data/1/ABBA-Transform-allen_mouse_10um_java.json` and `data/1/ABBA-RoiSet-allen_mouse_10um_java.zip`. This is a human GUI step — Claude cannot automate it.
- **Plan 03 (Execute Script + QC):** After Plan 02 files exist, researcher opens QuPath, selects entry 1 (`M3_20x_MIP_Z1-3.ome.tiff`), runs `01_load_abba_rois.groovy` via Automate → Run for project, saves project, and takes a QC screenshot showing CA1/CA3/DG subfields aligned to atlas outlines.

## Self-Check: PASSED

- `/home/jflab/Analysis/scripts/` exists: FOUND
- `/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/` exists: FOUND
- `/home/jflab/Analysis/scripts/01_load_abba_rois.groovy` exists: FOUND
- `/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/01_load_abba_rois.groovy` exists: FOUND
- Files are byte-identical: CONFIRMED (diff returned no differences)
- Older 062226 project untouched: CONFIRMED (no scripts/ directory created there)
