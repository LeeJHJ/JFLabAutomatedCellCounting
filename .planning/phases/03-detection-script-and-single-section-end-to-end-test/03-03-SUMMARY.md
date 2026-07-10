---
phase: 03-detection-script-and-single-section-end-to-end-test
plan: 03
subsystem: detection-pipeline
tags: [qupath, groovy, roitools, objectmeasurements, channelhistogram, background-subtraction, threshold-derivation]

# Dependency graph
requires:
  - phase: 03-detection-script-and-single-section-end-to-end-test (Plans 01-02)
    provides: "compound classification loop, EXCLUDE_ACRONYMS exclusion, readSpec runtime-threshold closure, regionOf/regionLabel leaf-annotation lookup, per-class count rollup, Atlas_X sanity print in scripts/02_detect_classify.groovy"
provides:
  - "localBackgroundSubtractedMean closure: compartment-agnostic peri-cellular annulus background measure via RoiTools.buffer/subtract + ObjectMeasurements on a throwaway detection object (D-04)"
  - "Nucleus: AF488-T3 mean (bg-sub) / Cytoplasm: AF568-T2 mean (bg-sub) measurements written on every detection"
  - "derivePeakThreshold closure re-deriving positive-classification thresholds via qupath.ext.braian.ChannelHistogram.zeroPhaseFilter/findPeaks (D-05), with a raw-measure self-check against the locked absolute cutoffs"
  - "Fos_Classifier_20x_bgsub.json / TdT_classifier_bgsub.json classifier files, self-consistent with the existing readSpec schema, overwritten by the script's own runtime re-derivation each run"
  - "Compound classification repointed to the bg-sub measure + re-derived thresholds (superseding the old absolute cutoffs, kept as documented reference)"
affects: [03-04-human-in-the-loop-run]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Peri-cellular annulus background measure: RoiTools.buffer(baseRoi, gapPx) / RoiTools.buffer(baseRoi, outerPx) / RoiTools.subtract(outer, inner) to build the ring, hierarchy.getAllObjectsForRegion(ImageRegion) for bounding-box neighbor candidates (not centroid-only getAllObjectsForROI), RoiTools.subtract(annulus, neighborRois) to clean it, then ObjectMeasurements.addIntensityMeasurements(server, throwawayDetectionObject, 1.0, [Measurements.MEAN], [Compartments.CELL]) to sample the mean -- the throwaway object is never added to the hierarchy"
    - "Histogram-peak threshold re-derivation reused on an arbitrary measurement (not just raw image channel intensity): bin a List<Double> into a double[] histogram, ChannelHistogram.zeroPhaseFilter(hist, kernel) to smooth, ChannelHistogram.findPeaks(smoothed, prominence) to locate peaks, pick the nPeak-th peak's bin-center as the threshold"
    - "Self-bootstrapping classifier JSON: a placeholder JSON committed to disk with the documented-reference threshold value; the script overwrites it in place with the live re-derived threshold on every run, then re-reads it via the existing readSpec closure (round-trip keeps the classification loop's code shape uniform across old/new classifiers)"

key-files:
  created:
    - "M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json"
    - "M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier_bgsub.json"
  modified:
    - scripts/02_detect_classify.groovy
    - "M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy"

key-decisions:
  - "Ring geometry seed constants (GAP_UM=1.0, RING_WIDTH_UM=8.0) taken literally from the plan/RESEARCH.md as [ASSUMED] starting values -- Assumption A4, needs visual DG-bleed-style tuning by a human in QuPath, same as Phase 2's cellExpansionMicrons"
  - "Threshold re-derivation constants (BIN_WIDTH=50.0, SMOOTH_KERNEL=[1,2,3,2,1], PEAK_PROMINENCE=500, N_PEAK=2) taken from the plan/RESEARCH.md Pattern 2 example and BraiAn.yml's locked D-01 semantics"
  - "bgsub classifier JSONs are self-bootstrapping: committed now with the OLD locked absolute threshold as a documented placeholder (labeled via a 'note' field), overwritten by the script's own ChannelHistogram-based re-derivation on first (and every) live run -- chosen because no live QuPath run was available to this executor (GUI-human-only per CLAUDE.md) to produce a real derived value, and because the plan explicitly allows deriving in-script while preferring the JSON path for D-05's runtime-editable shape"
  - "Threshold write-back is guarded: if a re-derivation returns NaN (no data / no peak found), the existing bgsub JSON on disk is left unchanged rather than clobbered -- keeps the idempotent/safe re-run property from D-02"
  - "Old absolute-cutoff classifier JSONs and the old raw-measure classification path are retained as documented reference only (D-05); classification now reads exclusively from the bg-sub measure + re-derived thresholds (Pitfall 9 guard)"

patterns-established:
  - "Pattern 1 (compartment-agnostic local-background subtraction) and Pattern 2 (histogram-peak threshold re-derivation on an arbitrary measurement) from 03-RESEARCH.md, both implemented as documented"

requirements-completed: [SCRI-03]

coverage:
  - id: D1
    description: "localBackgroundSubtractedMean closure writes Nucleus: AF488-T3 mean (bg-sub) and Cytoplasm: AF568-T2 mean (bg-sub) on every detection using RoiTools.buffer/subtract, getAllObjectsForRegion neighbor exclusion, and ObjectMeasurements on a throwaway detection object -- no nucleus:cytoplasm ratio (D-04)"
    requirement: "SCRI-03"
    verification:
      - kind: other
        ref: "grep -q 'localBackgroundSubtractedMean' scripts/02_detect_classify.groovy && grep -q 'RoiTools.buffer' scripts/02_detect_classify.groovy && grep -q 'RoiTools.subtract' scripts/02_detect_classify.groovy && grep -q 'getAllObjectsForRegion' scripts/02_detect_classify.groovy && grep -q 'addIntensityMeasurements' scripts/02_detect_classify.groovy && grep -q 'bg-sub' scripts/02_detect_classify.groovy && cmp scripts/02_detect_classify.groovy \"M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy\""
        status: pass
    human_judgment: true
    rationale: "Static source checks (grep/cmp) confirm the code is authored correctly and both script copies are byte-identical, but whether every detection actually gains valid, non-negative (for TdT) (bg-sub) measurements after a live BraiAnDetect + this script run can only be confirmed by a human running it in QuPath (GUI-only per CLAUDE.md) -- deferred to Plan 03-04's human-in-the-loop run."
  - id: D2
    description: "derivePeakThreshold closure re-derives Fos/TdT positive thresholds on the (bg-sub) measure via ChannelHistogram.zeroPhaseFilter/findPeaks (excluding DG-sg/VS from the population), with a raw-measure self-check printed against the locked absolute cutoffs; Fos_Classifier_20x_bgsub.json/TdT_classifier_bgsub.json authored and read back via readSpec; classification loop repointed to the bg-sub measure + re-derived thresholds (D-05, D-03)"
    requirement: "SCRI-03"
    verification:
      - kind: other
        ref: "grep -q 'ChannelHistogram' scripts/02_detect_classify.groovy && grep -q 'findPeaks' scripts/02_detect_classify.groovy && grep -q 'zeroPhaseFilter' scripts/02_detect_classify.groovy && grep -q 'bg-sub' \"M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json\" && grep -q 'bg-sub' \"M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier_bgsub.json\" && python3 -c \"import json; [json.load(open('M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/%s'%f))['function']['threshold'] for f in ['Fos_Classifier_20x_bgsub.json','TdT_classifier_bgsub.json']]\" && cmp scripts/02_detect_classify.groovy \"M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy\""
        status: pass
    human_judgment: true
    rationale: "Static checks confirm the ChannelHistogram-based re-derivation code, the bgsub classifier JSON schema/parseability, and script-copy sync -- but whether the live raw-measure self-check actually lands near the locked 13000.4538/16766.4671 (validating the histogram-kernel semantics transfer) and whether the resulting bg-sub classification measurably reduces the SSp false-positive fraction can only be confirmed by a human running the script in QuPath against the real M3 image data -- deferred to Plan 03-04."

duration: 7min
completed: 2026-07-10
status: complete
---

# Phase 3 Plan 03: Background-Robust Fos/TdT Measure + Threshold Re-Derivation Summary

**Compartment-agnostic local-background-subtracted Fos/TdT measurement (peri-cellular annulus via RoiTools + ObjectMeasurements) with positive thresholds re-derived on that measure via ChannelHistogram peak-finding, replacing the old absolute cutoffs in the compound classification loop.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-10T15:01:24Z
- **Completed:** 2026-07-10T15:08:03Z
- **Tasks:** 2
- **Files modified:** 4 (2 modified script copies, 2 new classifier JSONs)

## Accomplishments
- Every detection now gains two compartment-agnostic local-background-subtracted measurements -- `Nucleus: AF488-T3 mean (bg-sub)` (Fos, ring anchored outside the nucleus ROI) and `Cytoplasm: AF568-T2 mean (bg-sub)` (TdT, ring anchored outside the expanded cell/cytoplasm ROI) -- via a `localBackgroundSubtractedMean` closure built from `RoiTools.buffer`/`subtract`, `PathObjectHierarchy.getAllObjectsForRegion` neighbor exclusion, and `ObjectMeasurements.addIntensityMeasurements` on a throwaway (never-added-to-hierarchy) detection object. No nucleus:cytoplasm contrast ratio was implemented (forbidden by D-04).
- Positive-classification thresholds are now re-derived on the bg-sub measure via `qupath.ext.braian.ChannelHistogram.zeroPhaseFilter`/`findPeaks` -- the same primitives already locked into `BraiAn.yml`'s D-01 detection threshold -- with a mandatory self-check that first re-derives the threshold on the *existing raw* measures and prints a PASS/CHECK comparison against the locked absolute cutoffs (13000.4538 / 16766.4671) before the bg-sub-measure derivation is trusted.
- New `Fos_Classifier_20x_bgsub.json` / `TdT_classifier_bgsub.json` files authored in the project's `classifiers/object_classifiers/` directory, matching the existing classifier JSON schema; the script itself overwrites these with the live re-derived threshold on every run (idempotent -- a failed/NaN re-derivation leaves the existing file untouched) and re-reads them via the same `readSpec` closure already used for the old classifiers.
- The compound classification loop (Double+/Fos+/TdT+/Negative) now reads the bg-sub measure + re-derived thresholds exclusively; the old absolute-cutoff JSONs remain on disk and are printed for reference only, never applied to the new measure (Pitfall 9 guard).
- Both script copies (canonical `scripts/` and the QuPath project's spaced-path `scripts/` directory) remain byte-identical after each task.

## Task Commits

Each task was committed atomically:

1. **Task 1: Compartment-agnostic local-background-subtracted measure (D-04, Pattern 1)** - `3c5f818` (feat)
2. **Task 2: Re-derive thresholds on the bg-sub measure and wire classification to use them (D-05)** - `32278ee` (feat)

**Plan metadata:** (pending — final commit below)

## Files Created/Modified
- `scripts/02_detect_classify.groovy` - Added `localBackgroundSubtractedMean` (D-04 pre-pass, Task 1), `derivePeakThreshold`/`ChannelHistogram`-based threshold re-derivation with raw-measure self-check and bgsub-JSON write-back (D-05, Task 2), refactored the exclusion check into a shared `isExcluded` closure, and repointed the compound classification loop to the bg-sub measure + re-derived thresholds
- `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` - Byte-identical project hard-copy, re-synced after each task
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json` - New classifier JSON, `measurement: "Nucleus: AF488-T3 mean (bg-sub)"`, placeholder `threshold` (locked raw cutoff, documented in a `note` field), overwritten by the script's runtime re-derivation
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier_bgsub.json` - New classifier JSON, `measurement: "Cytoplasm: AF568-T2 mean (bg-sub)"`, placeholder `threshold` (locked raw cutoff, documented in a `note` field), overwritten by the script's runtime re-derivation

## Decisions Made
- Ring geometry (`GAP_UM=1.0`, `RING_WIDTH_UM=8.0`) and threshold-derivation constants (`BIN_WIDTH=50.0`, kernel `[1,2,3,2,1]`, `PEAK_PROMINENCE=500`, `N_PEAK=2`) taken literally from the plan/RESEARCH.md as documented [ASSUMED] seeds -- both need empirical visual tuning by a human once run against real image data (Plan 03-04).
- The bgsub classifier JSONs are committed now as self-bootstrapping placeholders (threshold = the old locked absolute cutoff, explicitly labeled via a `note` field), because no live QuPath run was available to this executor (GUI-human-only per CLAUDE.md) to produce an actual data-derived value. The script's own `writeBgsubClassifierSpec` closure overwrites these files with the live ChannelHistogram-derived threshold every time a human runs it in QuPath, satisfying D-05's "runtime-editable shape" while keeping the plan's static verification checks (file exists, schema valid, threshold numeric) satisfiable now.
- Threshold write-back is guarded against NaN (insufficient data / no peak found) -- the existing bgsub JSON is left unchanged rather than clobbered, preserving D-02's idempotent/safe re-run property.
- Old absolute-cutoff classifier JSONs (`Fos_Classifier_20x.json`, `TdT_classifier.json`) and their thresholds are kept as documented reference only, per D-05; the compound classification loop reads exclusively from the new bg-sub classifiers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed duplicate `imageData` variable declaration**
- **Found during:** Task 1
- **Issue:** The plan's new bg-sub pre-pass needs a shared `imageData`/`server`/`hierarchy` handle early in the script (before the classification loop), but the pre-existing Atlas_X sanity-print block (Plan 02) already declared its own local `def imageData = getCurrentImageData()` further down the same script. Groovy scripts do not allow re-declaring a `def` variable of the same name in the same top-level scope -- this would be a compile error once the earlier declaration was added.
- **Fix:** Removed the later duplicate `def imageData = ...` declaration and reused the single shared `imageData` variable defined near the top of the script (same value, same script run, same entry).
- **Files modified:** scripts/02_detect_classify.groovy, "M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy"
- **Verification:** Manual re-read of the full file confirmed no remaining duplicate `def` declarations; brace/paren balance checked via a Python script (96/96 braces, 402/402 parens).
- **Committed in:** `3c5f818` (Task 1 commit)

**2. [Rule 1 - Bug] Corrected the RESEARCH.md-suggested `hasProperty('getNucleusROI')` idiom to `respondsTo('getNucleusROI')`**
- **Found during:** Task 1
- **Issue:** RESEARCH.md's Pattern 1 code example used `d.hasProperty('getNucleusROI') ? d.getNucleusROI() : d.getROI()` to detect whether a detection is a `PathCellObject` with a nucleus ROI. In Groovy, `hasProperty()` checks for a bean-style *property* named exactly `getNucleusROI` (which does not exist), not for a method with that name -- this idiom would always evaluate false, silently falling back to `d.getROI()` for every detection and defeating the Fos-anchors-on-nucleus intent (Pitfall 3).
- **Fix:** Used the correct Groovy dynamic-method-existence check, `d.respondsTo('getNucleusROI')`, which returns a non-empty (truthy) list of matching `MetaMethod`s when the method exists on the runtime object.
- **Files modified:** scripts/02_detect_classify.groovy, "M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy"
- **Verification:** Manual review of Groovy MOP semantics (`respondsTo` vs `hasProperty`); no live QuPath run available to confirm at runtime -- flagged for the human to spot-check during Plan 03-04 (Fos ring should anchor on the smaller nucleus ROI, not the larger cell ROI, for `PathCellObject` detections).
- **Committed in:** `3c5f818` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs, both Rule 1)
**Impact on plan:** Both fixes were necessary for the script to be valid Groovy / to correctly implement the plan's Pitfall-3 anchor-ROI requirement. No scope creep -- both stay strictly within Task 1's existing surface.

## Issues Encountered
- Cannot execute or compile-check the Groovy script in this environment (GUI-only, CPU-only pipeline per CLAUDE.md -- QuPath was not launched). Correctness was verified via careful manual re-read, brace/paren balance checking, and cross-referencing every new API call against the RESEARCH.md-documented, installed-jar-verified method signatures. Live runtime behavior (A5 key-set println, self-check PASS/CHECK, actual re-derived threshold values, SSp false-positive reduction) is explicitly deferred to Plan 03-04's human-in-the-loop run.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness

- Static/source verification (grep + `cmp` + `python3` JSON parse) passed for both tasks; the plan's `<human-check>` steps (confirming the A5 key-set println, non-negative TdT bg-sub values, the raw-measure self-check landing near the locked thresholds, and a measurable SSp false-positive reduction) are GUI-only per CLAUDE.md and are explicitly deferred to Plan 03-04's human-in-the-loop run -- QuPath/Fiji were not launched and the script was not executed as part of this plan.
- Ring geometry (`GAP_UM`/`RING_WIDTH_UM`) and threshold-derivation constants (`BIN_WIDTH`/kernel/`PEAK_PROMINENCE`) are seed values per RESEARCH.md Assumption A1/A4 -- budget time in Plan 03-04 to visually tune the ring (DG-bleed-style check) and validate the histogram-kernel semantics before trusting the printed thresholds.
- SCRI-03 requirement remains NOT marked fully complete until Plan 03-04 confirms the "tested on one section" criterion live in QuPath, consistent with Plans 03-01/03-02.
- Next: Plan 03-04 — human-in-the-loop run: "Run for project" on M3 entry 1, verify the four-class breakdown now uses bg-sub thresholds, region labels, count rollup, `data.qpdata` update, and the A5/self-check/SSp-reduction human-check items from this plan and Plans 03-01/03-02; only then mark SCRI-03 complete.

## Self-Check: PASSED

All created/modified files exist on disk and both task commit hashes (`3c5f818`, `32278ee`) are present in git log.

---
*Phase: 03-detection-script-and-single-section-end-to-end-test*
*Completed: 2026-07-10*
