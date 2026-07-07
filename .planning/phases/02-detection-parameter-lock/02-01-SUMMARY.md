---
phase: 02-detection-parameter-lock
plan: 01
subsystem: detection
tags: [qupath, braiandetect, watershedcelldetection, yaml, groovy, classifier]

# Dependency graph
requires:
  - phase: 01-registration
    provides: "M3 062926 3 plane, entry 1 registered to Allen CCFv3 (ABBA-loaded atlas annotations, DG/CA1 regions available for D-04 tuning)"
provides:
  - "M3 Hippocampus 20x 062926 3 plane/BraiAn.yml — single DAPI-T4-anchored channelDetections entry, histogramThreshold (D-01), cellExpansionMicrons 5.0"
  - "Compartment-correct Fos_Classifier_20x.json (Nucleus: AF488-T3 mean) and TdT_classifier.json (Cytoplasm: AF568-T2 mean, rebuilt from the Nucleus-compartment bug)"
  - "scripts/qc_detection_gates.groovy (+ project hard-copy) — D-05 gate measurement harness (nucleus-area peak, DAPI density, D-06 advisory ratio)"
  - "scripts/check_classifier_compartment.py — reusable static compartment assert for classifier JSON"
affects: [02-02-lock-record, phase-03-detection-script]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single DAPI-anchored channelDetections entry with merged SingleClassifier application (not per-marker + OverlappingDetections) — nucleus-anchored colocalization per CLAUDE.md"
    - "histogramThreshold block for series-scalable relative detection threshold (D-01), not an absolute numeric threshold"
    - "QC groovy re-derives Fos+/TdT+/Double+ counts directly from each classifier JSON's own (measurement, threshold) pair rather than parsing merged PathClass name strings — avoids depending on undocumented merge-naming semantics"

key-files:
  created:
    - "M3 Hippocampus 20x 062926 3 plane/BraiAn.yml"
    - "M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x.json"
    - "M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier.json"
    - "scripts/qc_detection_gates.groovy"
    - "M3 Hippocampus 20x 062926 3 plane/scripts/qc_detection_gates.groovy"
    - "scripts/check_classifier_compartment.py"
  modified: []

key-decisions:
  - "Single DAPI-T4-anchored channelDetections entry (not per-marker topology) resolves RESEARCH Open Question #1 in favor of the CLAUDE.md nucleus-anchored mandate"
  - "D-06 advisory ratio computed by re-applying each classifier JSON's own measurement+threshold to detections directly, rather than parsing BraiAnDetect's merged PathClass name (semantics undocumented/bytecode-inferred per RESEARCH Assumption A2)"
  - "All WatershedCellDetectionConfig numeric seeds (sigmaMicrons, minAreaMicrons, maxAreaMicrons) and both classifier thresholds are explicitly flagged [ASSUMED]/SEED — not locked until Plan 02-02's D-05 gate pass"

patterns-established:
  - "Canonical scripts/ + project scripts/ hard-copy convention (established Phase 1) extended to qc_detection_gates.groovy"

requirements-completed: [SCRI-02, CLASS-01]

coverage:
  - id: D1
    description: "BraiAn.yml authored at project root: single DAPI-T4 channelDetections entry, histogramThreshold (not absolute threshold), cellExpansionMicrons > 0, exact channel names matching server.json"
    requirement: "SCRI-02"
    verification:
      - kind: other
        ref: "python3 -c yaml.safe_load + structural asserts (single entry, histogramThreshold present, threshold absent, cellExpansionMicrons>0, requestedPixelSizeMicrons==0.6905355, classifiers==[Fos_Classifier_20x,TdT_classifier], channels=={AF488-T3,AF568-T2}, detectionsCheck.apply==False) -- printed 'BraiAn.yml OK'"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fos classifier reads Nucleus: AF488-T3 mean (nuclear compartment, CLASS-01); TdT classifier rebuilt to read Cytoplasm: AF568-T2 mean with Negative/Positive classes"
    requirement: "CLASS-01"
    verification:
      - kind: other
        ref: "jq -e '.function.measurement == \"Nucleus: AF488-T3 mean\"' Fos_Classifier_20x.json && jq -e '.function.measurement == \"Cytoplasm: AF568-T2 mean\"' TdT_classifier.json && jq -e '.pathClasses == [\"Negative\",\"Positive\"]' TdT_classifier.json"
        status: pass
    human_judgment: false
  - id: D3
    description: "D-05 measurement-QC harness (nucleus-area peak bin, whole-section/DG/CA1 DAPI density, D-06 advisory ratio) authored as a runnable QuPath script, plus a reusable static classifier-compartment check"
    verification:
      - kind: other
        ref: "scripts/qc_detection_gates.groovy: test -s, grep getDetectionObjects/getAnnotationObjects/0.6905355 all pass; scripts/check_classifier_compartment.py exits 0 on known-good Fos classifier, exits 1 on the known-wrong TRAP2TdT analog"
        status: pass
    human_judgment: true
    rationale: "qc_detection_gates.groovy's actual output (peak bin, density numbers, D-06 ratio) can only be exercised by running it inside QuPath against real detection data in Plan 02-02 -- this plan authors and statically verifies the script but cannot execute a live QuPath detection pass"

# Metrics
duration: 12min
completed: 2026-07-07
status: complete
---

# Phase 2 Plan 01: Author Detection-Parameter Artifacts Summary

**Single-DAPI-anchored `BraiAn.yml` (histogram-relative threshold), a rebuilt Cytoplasm-compartment TdT classifier fixing a real mis-count bug, and a D-05 measurement-QC harness — the full scriptable half of the detection-parameter lock, ready for Plan 02-02's human-in-the-loop tuning.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-07T22:02:21Z
- **Completed:** 2026-07-07T22:08:54Z
- **Tasks:** 3/3
- **Files modified:** 6 created

## Accomplishments
- Authored `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml`: one global config for the whole series (D-03), single `channelDetections` entry rooted at `DAPI-T4` with two nested classifiers (Fos on `AF488-T3`, TdT on `AF568-T2`), `histogramThreshold` block instead of an absolute `threshold` (D-01), `cellExpansionMicrons: 5.0`, `requestedPixelSizeMicrons: 0.6905355` matched to `server.json`
- Fixed a real correctness bug: rebuilt `TdT_classifier.json` to read `Cytoplasm: AF568-T2 mean` (was `Nucleus: AF568-T2 mean` in the source analog `TRAP2TdT_Classifier_20x.json`) — TdTomato is cytosolic, so the prior compartment was silently mis-counting it; standardized classes to `Negative`/`Positive`
- Reused `Fos_Classifier_20x.json` verbatim (already reads `Nucleus: AF488-T3 mean`, satisfying CLASS-01)
- Created `classifiers/object_classifiers/` directory in the target project (did not previously exist there)
- Authored `scripts/qc_detection_gates.groovy` (+ project hard-copy): prints D-05 gate 1 (nucleus-area peak bin), D-05 gate 2 (whole-section + explicit DG/CA1 DAPI density/mm²), and the D-06 advisory Double+/TdT+ ratio — no baked-in pass/fail, all raw numbers for the human to judge against target ranges in Plan 02-02
- Authored `scripts/check_classifier_compartment.py`: stdlib-only static assert reusable for CLASS-01 (this phase) and CLASS-02 (later)

## Task Commits

Each task was committed atomically:

1. **Task 1: Author the D-05 validation harness (measurement-QC Groovy + static compartment check)** - `5e3dc3b` (feat)
2. **Task 2: Author the two object classifiers (reuse Fos for CLASS-01, rebuild TdT to Cytoplasm)** - `1b6b05f` (feat)
3. **Task 3: Author the single-DAPI-anchored BraiAn.yml (SCRI-02, D-01/D-03)** - `8dcdf43` (feat)

**Plan metadata:** (final commit hash recorded after this Summary is committed)

## Files Created/Modified
- `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml` - single DAPI-T4-anchored detection+classifier config for the whole series
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x.json` - nuclear Fos classifier (reused, CLASS-01)
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier.json` - cytoplasmic TdT classifier (rebuilt, fixes compartment bug)
- `scripts/qc_detection_gates.groovy` - canonical D-05/D-06 measurement-QC helper
- `M3 Hippocampus 20x 062926 3 plane/scripts/qc_detection_gates.groovy` - project hard-copy (Phase-1 convention)
- `scripts/check_classifier_compartment.py` - stdlib static classifier-compartment check, reusable for CLASS-02

## Decisions Made
- **Topology:** single DAPI-T4-anchored `channelDetections` entry with two nested classifiers, resolving RESEARCH Open Question #1 in favor of CLAUDE.md's nucleus-anchored/no-proximity-heuristic mandate over the upstream extension's per-marker example pattern.
- **D-06 ratio computation:** `qc_detection_gates.groovy` re-derives Fos+/TdT+/Double+ counts directly from each classifier JSON's own `(measurement, threshold)` pair (loaded at runtime via `JsonSlurper`) rather than parsing BraiAnDetect's merged `PathClass` name string. Rationale: the merge-naming semantics (`PathClassTools.mergeClasses`) are bytecode-inferred, not documentation-verified (RESEARCH Assumption A2), and both classifiers currently share the literal class names `Negative`/`Positive` — parsing a merged name string would be ambiguous/fragile, while re-deriving from source-of-truth threshold specs is deterministic and testable independent of QuPath's internal merge behavior.
- **Pixel size:** `requestedPixelSizeMicrons` set to `0.6905355` (matches `server.json` `PhysicalSizeX` exactly) rather than a round default, avoiding WatershedCellDetection internal resampling (RESEARCH Assumption A4).
- All numeric detection parameters (`sigmaMicrons: 2.0`, `minAreaMicrons: 20.0`, `maxAreaMicrons: 150.0`, `cellExpansionMicrons: 5.0`) and both classifier `threshold` values (`9341.31736526946` Fos-inherited, `10200.8443` TdT-inherited) are explicitly flagged as `[ASSUMED]`/SEED in code comments and this Summary — **not locked**. TRAP2-paper primary source returned HTTP 403 during Phase 2 research (RESEARCH Assumption A1); these are starting points only, to be tuned against the D-05 empirical gates (nucleus-area peak 50–150 µm²; DAPI density 500–2000/mm²) on DG + CA1 in Plan 02-02.

## Deviations from Plan

None - plan executed exactly as written. All `must_haves` truths, artifacts, and key_links from the plan frontmatter are satisfied by the files above.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. Plan 02-02 requires the researcher to run BraiAnDetect and `qc_detection_gates.groovy` inside the QuPath GUI (`DISPLAY=:0`), which is a GUI-only handoff per CLAUDE.md, not an external service setup.

## Next Phase Readiness

Plan 02-02 can proceed immediately: `BraiAn.yml`, both classifier JSONs, and the QC harness are all in place and pass their static checks. Plan 02-02's job is to run detection on M3 062926 3 plane entry 1, run `qc_detection_gates.groovy`, tune `sigmaMicrons`/`minAreaMicrons`/`maxAreaMicrons`/`cellExpansionMicrons`/classifier thresholds against the D-05 hard gates (both DG and CA1 per D-04), and write `02-LOCK-RECORD.md` once both gates PASS. No blockers.

---
*Phase: 02-detection-parameter-lock*
*Completed: 2026-07-07*

## Self-Check: PASSED

All 7 created files verified present on disk:
- FOUND: `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml`
- FOUND: `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x.json`
- FOUND: `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier.json`
- FOUND: `scripts/qc_detection_gates.groovy`
- FOUND: `M3 Hippocampus 20x 062926 3 plane/scripts/qc_detection_gates.groovy`
- FOUND: `scripts/check_classifier_compartment.py`
- FOUND: `.planning/phases/02-detection-parameter-lock/02-01-SUMMARY.md`

All 4 commit hashes verified present in `git log --oneline --all`:
- FOUND: `5e3dc3b` (Task 1)
- FOUND: `1b6b05f` (Task 2)
- FOUND: `8dcdf43` (Task 3)
- FOUND: `edf980d` (Summary)
