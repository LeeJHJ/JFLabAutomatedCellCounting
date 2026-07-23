---
phase: 03-detection-script-and-single-section-end-to-end-test
plan: 01
subsystem: detection
tags: [qupath, groovy, gson, abba, nucleus-anchored-classification, atlas-region-label]

# Dependency graph
requires:
  - phase: 02-detection-parameter-lock
    provides: locked BraiAn.yml detection params, Fos_Classifier_20x.json (Nucleus AF488-T3, thr 13000.4538), TdT_classifier.json (Cytoplasm AF568-T2, thr 16766.4671), classify_markers.groovy compound-classification core
provides:
  - "scripts/02_detect_classify.groovy: runnable numbered classify/label entry point (canonical + project-local hard-copy)"
  - "D-01/D-02 guard + idempotent re-classify semantics wired into the numbered pipeline"
  - "regionOf/regionLabel ephemeral centroid-in-ROI atlas region label lookup per classified cell"
affects: [03-02-annotation-count-rollup, 03-03-background-robust-measure, 03-04-human-verify-run]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Numbered pipeline script extends an existing analog (classify_markers.groovy) rather than starting from scratch"
    - "Ephemeral centroid-in-ROI lookup (no per-cell String metadata; MeasurementList stays numeric-only)"

key-files:
  created:
    - scripts/02_detect_classify.groovy
    - "M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy"
  modified: []

key-decisions:
  - "Task 1/Task 2 split into two atomic commits even though authored together, to match the plan's task-level commit granularity"
  - "Region-label lookup (SC2) recomputes per run via a closure -- never stored on the detection object, per QuPath 0.6.0 javadoc metadata-cost warning and MeasurementList's numeric-only design"
  - "Kept the BraiAnDetect parent-chain nesting hypothesis (A2) as a diagnostic-only println; implementation does not depend on it"

patterns-established:
  - "regionOf/regionLabel closures: leaf-region-only centroid-in-ROI containment, reusable for Plan 02's per-region count rollup"

requirements-completed: [SCRI-03]

coverage:
  - id: D1
    description: "02_detect_classify.groovy runs the D-01/D-02 guarded, nucleus-anchored compound classification (Fos+/TdT+/Double+/Negative/Excluded) and writes classified data.qpdata via fireHierarchyUpdate"
    requirement: "SCRI-03"
    verification:
      - kind: other
        ref: "grep -q 'No detections' && grep -q 'EXCLUDE_ACRONYMS' && grep -q 'Double+' && grep -q 'Fos+' && grep -q 'TdT+' && grep -q 'Negative' && grep -q 'fireHierarchyUpdate' scripts/02_detect_classify.groovy; cmp scripts/02_detect_classify.groovy 'M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy'"
        status: pass
    human_judgment: true
    rationale: "Static grep/cmp checks confirm the source contains the required guard/classes/idempotency shape and dual-location byte-identity, but actually running the script in QuPath (no red error, four-class breakdown all non-zero, data.qpdata mtime update) requires a human at the GUI -- deferred to Plan 03-04 per this plan's own <human-check> verification split."
  - id: D2
    description: "Each classified cell resolves to an ABBA atlas leaf-region label via ephemeral centroid-in-ROI lookup (regionOf/regionLabel), with no per-cell metadata persisted"
    requirement: "SCRI-03"
    verification:
      - kind: other
        ref: "grep -q 'regionOf' && grep -q 'getChildObjects' && grep -Eq 'contains\\(' scripts/02_detect_classify.groovy; cmp scripts/02_detect_classify.groovy 'M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy'"
        status: pass
    human_judgment: true
    rationale: "Static checks confirm the closure and leaf-filtering/containment idiom exist in source, but confirming the sample println actually resolves to real ABBA acronyms (CA1, CA3, DG-mo) requires running the script live in QuPath against loaded ABBA annotations -- deferred to Plan 03-04's human-in-the-loop run."

duration: ~10min
completed: 2026-07-10
status: complete
---

# Phase 3 Plan 1: Detection/Classify Script Entry Point Summary

**Authored `02_detect_classify.groovy` (canonical + project hard-copy): extends `classify_markers.groovy` into the numbered pipeline with a D-02 zero-detection guard and an ephemeral centroid-in-ROI atlas region-label lookup per classified cell.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-07-10T03:49:37Z
- **Tasks:** 2
- **Files modified:** 2 (canonical + project-local hard-copy of the same script)

## Accomplishments
- `scripts/02_detect_classify.groovy` created as the runnable classify/label/report entry point per D-01 (detection stays in `run_braian_detection.groovy`) and D-02 (zero-detection guard; idempotent re-classify via `setPathClass` overwrite)
- Nucleus-anchored compound classification core reused verbatim from `classify_markers.groovy`: Fos+ (Nucleus AF488-T3), TdT+ (Cytoplasm AF568-T2), Double+, Negative, with DG-sg/VS exclusion — no proximity/overlap heuristics, no BraiAn.yml `classifiers:`/OverlappingDetections (Deviation #1 stayed forbidden)
- Runtime classifier-JSON threshold read via Gson `JsonParser` against `Fos_Classifier_20x.json` / `TdT_classifier.json` (not hard-coded)
- Atlas region label per cell (SC2): `regionOf` closure resolves each detection's centroid against leaf region annotations (annotations with no annotation children) using the same `contains(x, y)` idiom already proven in `classify_markers.groovy`/`qc_detection_gates.groovy`; `regionLabel` strips the Left/Right hemisphere prefix to bare acronyms
- Region membership is computed ephemeraly (never persisted as per-cell metadata), per QuPath 0.6.0 javadoc's memory-cost warning and `MeasurementList`'s numeric-only design (Pitfalls 4/5 from 03-RESEARCH.md)
- Diagnostic-only println of the BraiAnDetect parent-chain nesting hypothesis (A2), explicitly not depended on by the implementation
- Dual-location deploy: canonical `scripts/02_detect_classify.groovy` and project-local `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` kept byte-identical (`cmp` verified after each task)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create runnable classify script from classify_markers.groovy (D-01, D-02)** - `69c198a` (feat)
2. **Task 2: Attach an ABBA atlas region label to each classified cell (SC2)** - `89b200d` (feat)

_Note: authored together in one pass, but split into two commits matching the plan's per-task granularity — each commit independently passes its task's automated verification (grep/cmp)._

## Files Created/Modified
- `scripts/02_detect_classify.groovy` - Canonical classify/label/report script: D-01/D-02 guard, compound classification, atlas region label lookup
- `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` - Byte-identical project-local hard-copy for QuPath "Run for project"

## Decisions Made
- Split the single-pass authoring into two commits (Task 1 content, then Task 2 additions) to preserve atomic per-task commit granularity even though both tasks were drafted together
- Kept `EXCLUDE_ACRONYMS = ["DG-sg", "VS"]` unchanged (locked in Phase 2, not a Phase-3 decision)
- Did NOT implement the per-region count rollup (SC4, `MeasurementList.put("Count: ...")`) or the Atlas_X sanity print (SC3) in this plan — those are explicitly scoped to Plan 03-02 per the plan's stated boundary ("Atlas_X range SC3 and per-region count table SC4 come in Plan 02")
- Did NOT implement the background-robust local-background-subtraction measure (D-03/D-04/D-05) — explicitly scoped to Plan 03-03

## Deviations from Plan

None - plan executed exactly as written. No auto-fixes were needed; both tasks' automated verification (`grep`/`cmp` checks) passed on the first attempt.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Human-in-the-Loop Verification (Deferred)

Per this project's CLAUDE.md, QuPath is GUI-only and human-operated. This plan's `<human-check>` verification steps (running the script via "Run for project" in QuPath, confirming no red error, the four-class breakdown printing with all classes non-zero, the entry-name println showing the M3 entry, `data.qpdata` mtime updating, and the sample println resolving real ABBA region acronyms) were NOT attempted by this executor and remain deferred to Plan 03-04, as instructed. Only the plan's `<automated>` grep/cmp verifications were run in this execution.

## Next Phase Readiness

- `02_detect_classify.groovy` exists in both required locations, passes all static/automated verification for both tasks, and is ready for the human-in-the-loop run in Plan 03-04
- Plan 03-02 can build the per-region count rollup (SC4) directly on top of the `regionAnnotations`/`regionOf` machinery already established here
- Plan 03-03 can extend the classification core with the background-robust measure without restructuring the guard/threshold-read/region-label scaffolding built in this plan

---
*Phase: 03-detection-script-and-single-section-end-to-end-test*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: `scripts/02_detect_classify.groovy`
- FOUND: `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy`
- FOUND: `.planning/phases/03-detection-script-and-single-section-end-to-end-test/03-01-SUMMARY.md`
- FOUND: commit `69c198a` (Task 1)
- FOUND: commit `89b200d` (Task 2)
- FOUND: commit `303971a` (docs: summary)
