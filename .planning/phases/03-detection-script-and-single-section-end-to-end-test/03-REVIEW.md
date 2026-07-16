---
phase: 03-detection-script-and-single-section-end-to-end-test
reviewed: 2026-07-16T19:26:15Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - scripts/02_detect_classify.groovy
  - M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json
  - M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier_bgsub.json
findings:
  critical: 0
  warning: 4
  info: 1
  total: 5
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-16T19:26:15Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed `scripts/02_detect_classify.groovy` (the classification/labeling/reporting entry point) and the two runtime-generated `_bgsub.json` classifier specs it writes. The QuPath-project hard copy at `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` was diffed against the canonical copy and confirmed byte-identical — no drift, no separate findings filed for it.

The previously-resolved D-01..D-05 fixes were traced end-to-end and are correctly implemented:
- The measurement-key lookup for the local-background annulus (`"AF488-T3: Mean"` style, resolved by prefix+suffix match rather than an assumed `"Cell: <channel> mean"` key) is correct and matches the D-04 fix.
- `getMeasurements().get(...)`/`.put(...)` (not the buffered `getMeasurementList()`) is used consistently for both write and read of the bg-sub measure, so the D-03 write/read split bug does not recur.
- The D-05 robust threshold (`median + k*1.4826*MAD`, k=3) is implemented correctly (median/MAD formulas verified by hand for both odd/even n), and the two committed `_bgsub.json` files match exactly what `writeBgsubClassifierSpec` would produce (correct measurement key, correct threshold value, correct note format) — consistent round-trip, no bootstrap-placeholder drift.
- Nucleus-anchored, non-proximity classification is correctly wired: Fos reads `Nucleus: AF488-T3 mean (bg-sub)` (nuclear compartment) and TdT reads `Cytoplasm: AF568-T2 mean (bg-sub)` (cytoplasmic ring), matching the CLAUDE.md colocalization rule.
- The count-rollup closure param rename (`n` → `cnt`, fixing the earlier dup-param parse error) is present and does not shadow the outer `n = dets.size()`.

No BLOCKER-level defects were found. Four WARNING-level robustness/silent-failure gaps remain open, plus one minor code-quality nit. None of these were part of the D-01..D-05 fix list and none are proven to have produced a wrong result on this run, but each is a real path by which a wrong count could pass silently on a future run — flagged per the review brief.

## Warnings

### WR-01: Region-rollup can double-count a cell if leaf-region ROIs ever overlap, inconsistently with `regionOf`

**File:** `scripts/02_detect_classify.groovy:446-450` and `:494-507`

**Issue:** `regionOf` (used for the sample per-cell print) resolves a detection's region via `regionAnnotations.find { it.getROI().contains(x, y) }` — i.e. the **first** matching leaf annotation only. The SC4 rollup a few lines later does something different: it loops `regionAnnotations.each { ann -> ... dets.each { d -> if (roi.contains(...)) counts[cls]++ } }`, which increments a count for **every** leaf annotation whose ROI contains that centroid, not just the first. The header comment claims this reuses "the SAME centroid-in-ROI containment idiom as regionOf" — true of the containment test, but not of the cardinality handling.

If ABBA-warped leaf-region annotations ever overlap even slightly at a shared boundary (plausible after spline registration — adjacent Allen regions are not guaranteed to remain a strict non-overlapping partition after per-section warping), a single cell gets counted into `Count: <class>` for two or more regions simultaneously. There is no cross-check anywhere that `sum(Count: * over all regions and classes)` equals `classified` (from the earlier `n - cExc` breakdown), so an inflated rollup would pass completely silently — exactly the "wrong result passes silently" failure mode this review was asked to prioritize.

**Fix:** Either (a) make the rollup use the same first-match semantics as `regionOf` (assign each detection to exactly one region, e.g. via a single pass computing `regionOf(d)` per detection and accumulating into that one region's bucket), or (b) if multi-region counting is intentional, add an explicit sum-check print comparing total rolled-up counts to `classified` so silent inflation is caught immediately:
```groovy
// after the rollup loop:
int rolledUpTotal = regionAnnotations.sum { ann ->
    ROLLUP_CLASSES.sum { cls -> ann.getMeasurementList().get("Count: ${cls}") ?: 0 }
} as int
println "Rollup sanity: sum of all region counts = ${rolledUpTotal} (classified total = ${classified}); " +
        (rolledUpTotal == classified ? "OK" : "MISMATCH -- check for overlapping leaf-region ROIs or unassigned cells")
```

---

### WR-02: `catch (Throwable t)` in `localBackgroundSubtractedMean` is too broad and can mask serious errors as routine geometry failures

**File:** `scripts/02_detect_classify.groovy:171-208` (catch at `:202-207`)

**Issue:** The catch block is documented as guarding against JTS OverlayNG's "side location conflict" robustness failures during the annulus subtract, which is a legitimate and narrow concern. But `catch (Throwable t)` also swallows `OutOfMemoryError`, `StackOverflowError`, thread interruption, and any other `Error`/unchecked exception that could occur inside `RoiTools.buffer/subtract` or `ObjectMeasurements.addIntensityMeasurements` for reasons unrelated to geometry robustness. All of these get folded into the same `bgGeomFailures` counter and reported as "negligible if small" — so a real resource-exhaustion or JVM-level failure partway through a 10^4–10^5-detection batch would look identical in the console output to a handful of harmless geometry edge cases, and the run would silently continue (and finish "successfully") instead of surfacing the real problem.

**Fix:** Narrow the catch to the actual exception family JTS throws for topology/robustness failures (`org.locationtech.jts.geom.TopologyException` and, if QuPath's `RoiTools` wraps it, `RuntimeException` is the practical minimum — but not `Throwable`/`Error`):
```groovy
} catch (RuntimeException e) {
    bgGeomFailures++
    return Double.NaN
}
```
This lets genuine `Error`s propagate and abort the run loudly, rather than being counted as "1 more geometry failure."

---

### WR-03: Script has a hard runtime dependency on two files it documents as superseded, purely for an informational `println`

**File:** `scripts/02_detect_classify.groovy:100-103`

**Issue:** `readSpec("Fos_Classifier_20x.json")` and `readSpec("TdT_classifier.json")` are called unconditionally near the top of the script, before the D-02 zero-detection guard even runs. `readSpec` does `new File(base, fn).text`, which throws `FileNotFoundException`/`NoSuchFileException` if the file is missing. Per the header comment (lines 32-35), these two files are explicitly "SUPERSEDED for classification and retained only as a documented reference point" — their only remaining use in this script is the "(Superseded reference only, NOT operative...)" println at line 398. If either file is deleted or renamed during a future cleanup pass (which the comment itself signals is plausible, since they're no longer authoritative), the entire classification run — including the operative D-04/D-05 logic — fails before it starts, for a println that isn't load-bearing.

**Fix:** Make the reference read best-effort so the operative path is not coupled to a file that is documented as no longer required:
```groovy
def readSpecSafe = { fn ->
    def f = new File(base, fn)
    if (!f.exists()) return [meas: "(missing: ${fn})", thr: Double.NaN]
    return readSpec(fn)
}
def fos = readSpecSafe("Fos_Classifier_20x.json")
def tdt = readSpecSafe("TdT_classifier.json")
```

---

### WR-04: No explicit handling of tissue/image-boundary effects in the local-background annulus

**File:** `scripts/02_detect_classify.groovy:171-208`

**Issue:** For a detection near the edge of the imaged field, `outerRoi = RoiTools.buffer(baseRoi, outerPx)` can extend past the valid pixel extent of the image. Nothing in `localBackgroundSubtractedMean` clips the annulus to the image bounds or flags/excludes border cells before computing `ObjectMeasurements.addIntensityMeasurements`. Depending on how that call handles a region that partially falls outside the pixel data (clip-and-average over the in-bounds pixels only vs. an implicit zero/undefined contribution from out-of-bounds area), a border cell's local-background estimate could be systematically biased low, which would inflate its `bg-sub` value and risk a false positive call — a wrong classification that would pass completely silently (no exception, no NaN, no counter incremented) since this is a distinct failure mode from the JTS-robustness case that D-04 already guards against.

**Fix:** At minimum, add a border-proximity diagnostic so the failure mode is at least observable if it exists in this section's data:
```groovy
def imgW = server.getWidth(), imgH = server.getHeight()
def bbox = outerRoi.getBoundsX() // .. and getBoundsY/getBoundsWidth/getBoundsHeight
boolean nearBorder = bbox.x < 0 || bbox.y < 0 ||
        (bbox.x + outerRoi.getBoundsWidth()) > imgW || (bbox.y + outerRoi.getBoundsHeight()) > imgH
// tally nearBorder count and report alongside bgGeomFailures
```
If it turns out to matter for this section (non-trivial border cell count with unusually large bg-sub values), consider excluding border cells from classification the same way DG-sg/VS-excluded cells are, or shrink the annulus dynamically to stay within bounds.

## Info

### IN-01: `getNucleusROI()` called twice per detection

**File:** `scripts/02_detect_classify.groovy:220`

**Issue:** `(d.respondsTo('getNucleusROI') && d.getNucleusROI() != null) ? d.getNucleusROI() : d.getROI()` invokes `getNucleusROI()` twice when the true branch is taken. Not a correctness issue (idempotent getter), just a minor readability/DRY nit.

**Fix:**
```groovy
def nucRoi = d.respondsTo('getNucleusROI') ? d.getNucleusROI() : null
def nucleusRoi = nucRoi != null ? nucRoi : d.getROI()
```

---

_Reviewed: 2026-07-16T19:26:15Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
