# Phase 3: Detection Script and Single-Section End-to-End Test - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 2 (1 new deliverable + its dual-location deploy copy; optional new classifier JSON(s) under D-05)
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `scripts/02_detect_classify.groovy` | controller/script (pipeline stage entry point) | batch / transform (reads existing detections+annotations in `data.qpdata`, writes derived measurements + classes + region rollup) | `scripts/classify_markers.groovy` | exact (same role: nucleus-anchored compound classification script) |
| `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` (hard-copy deploy target) | controller/script | batch / transform | `M3 Hippocampus 20x 062926 3 plane/scripts/classify_markers.groovy` | exact — same dual-location deploy pattern already used for every numbered/named script in this project |
| `classifiers/object_classifiers/Fos_Classifier_*_bgsub.json` / `TdT_classifier_*_bgsub.json` (optional, D-05 re-derived thresholds) | config | CRUD (static JSON read at script runtime) | `classifiers/object_classifiers/Fos_Classifier_20x.json` / `TdT_classifier.json` (referenced, not directly read this pass — schema known from `classify_markers.groovy`'s `readSpec` closure) | role-match |

Supporting analogs consulted for sub-patterns within the single new script (not separate files to create):

| Sub-pattern needed in `02_detect_classify.groovy` | Analog file | What it supplies |
|---|---|---|
| Zero-detection guard + idempotent re-classify (D-02) | `scripts/classify_markers.groovy` line 54 | `if (dets.isEmpty()) { println "..."; return }` |
| Runtime classifier-JSON threshold read (Gson, no `groovy.json`) | `scripts/classify_markers.groovy` lines 32-38; `scripts/qc_detection_gates.groovy` lines 183-196 | `JsonParser.parseString(...).getAsJsonObject().getAsJsonObject("function")` idiom |
| Centroid-in-ROI region containment (exclusion + region label + count rollup) | `scripts/classify_markers.groovy` lines 42-51, 58-60; `scripts/qc_detection_gates.groovy` lines 139-146, 159-164 | `roi.contains(x, y)` on annotation ROI, driven off `getPathClass()?.toString() ?: getName()` |
| Class-breakdown console printout | `scripts/classify_markers.groovy` lines 73-85 | percentage-of-classified formatting, advisory ratio print |
| Pixel-size resolution (server calibration, with fallback) | `scripts/qc_detection_gates.groovy` lines 53-65 | `server.getPixelCalibration()` / `hasPixelSizeMicrons()` / `getAveragedPixelSizeMicrons()` pattern — reused for buffer-distance µm→px conversion (Pitfall 2 in RESEARCH.md) |
| Region-annotation iteration + area/density computation | `scripts/qc_detection_gates.groovy` lines 132-146 | template for the SC4 per-region count rollup loop |
| ABBA hierarchy prerequisite / entry-confirmation println | `scripts/01_load_abba_rois.groovy` lines 22-25, 76-82 | confirms `resolveHierarchy()` already ran upstream; entry-name println pattern to avoid wrong-entry runs |
| `AtlasManager.saveResults` region TSV (optional complement, NOT authoritative per Pitfall 1) | `scripts/run_braian_detection.groovy` lines 76-86 | shows the TSV write call this phase must NOT rely on as ground truth |

## Pattern Assignments

### `scripts/02_detect_classify.groovy` (controller/script, batch/transform)

**Analog:** `scripts/classify_markers.groovy` (full file, 86 lines — read completely, see below)

**Imports pattern** (`scripts/classify_markers.groovy` lines 26-27):
```groovy
import com.google.gson.JsonParser
import static qupath.lib.scripting.QP.*
```
Extend with (per RESEARCH.md Patterns 1/2/3/5, all installed-jar-verified, no new libraries):
```groovy
import qupath.lib.roi.RoiTools
import qupath.lib.objects.PathObjects
import qupath.lib.analysis.features.ObjectMeasurements
import qupath.lib.analysis.features.ObjectMeasurements.Measurements
import qupath.lib.analysis.features.ObjectMeasurements.Compartments
import qupath.lib.regions.ImageRegion
import qupath.ext.braian.ChannelHistogram
import qupath.ext.biop.abba.AtlasTools
import net.imglib2.RealPoint
```

**Zero-detection guard (D-02)** (`scripts/classify_markers.groovy` line 54):
```groovy
def dets = getDetectionObjects()
if (dets.isEmpty()) { println "No detections — run BraiAnDetect first. Aborting."; return }
```
This is the exact pattern D-02 says to match ("No detections — Aborting"). Reuse verbatim; `setPathClass` already overwrites on re-run so no extra idempotency work is needed beyond this guard.

**Runtime classifier-JSON threshold read** (`scripts/classify_markers.groovy` lines 32-38):
```groovy
def base = new File(getProject().getBaseDirectory(), "classifiers/object_classifiers")
def readSpec = { fn ->
    def o = JsonParser.parseString(new File(base, fn).text).getAsJsonObject().getAsJsonObject("function")
    [meas: o.get("measurement").getAsString(), thr: o.get("threshold").getAsDouble()]
}
def fos = readSpec("Fos_Classifier_20x.json")
def tdt = readSpec("TdT_classifier.json")
```
D-05 supersedes the *values* (not the mechanism) — point `readSpec` at new bg-sub classifier JSON(s), or replace with in-script constants derived via Pattern 2's `ChannelHistogram` re-derivation. Keep the read-at-runtime shape so future threshold edits don't require code changes (same rationale documented in the original file's header comment).

**Nucleus-anchored exclusion + compound classification core** (`scripts/classify_markers.groovy` lines 42-71):
```groovy
def EXCLUDE_ACRONYMS = ["DG-sg", "VS"] as Set

def excludeRois = []
getAnnotationObjects().each { ann ->
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    if (label == null || ann.getROI() == null) return
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    def acr = m.find() ? m.group(1) : label
    if (EXCLUDE_ACRONYMS.contains(acr)) excludeRois << ann.getROI()
}

int cFos = 0, cTdt = 0, cDbl = 0, cNeg = 0, cExc = 0
dets.each { d ->
    def r = d.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    if (excludeRois.any { it.contains(x, y) }) {
        d.setPathClass(getPathClass("Excluded")); cExc++; return
    }
    def vf = d.getMeasurements().get(fos.meas)
    def vt = d.getMeasurements().get(tdt.meas)
    boolean isF = vf != null && !Double.isNaN(vf.doubleValue()) && vf.doubleValue() >= fos.thr
    boolean isT = vt != null && !Double.isNaN(vt.doubleValue()) && vt.doubleValue() >= tdt.thr
    def cls = (isF && isT) ? "Double+" : isF ? "Fos+" : isT ? "TdT+" : "Negative"
    d.setPathClass(getPathClass(cls))
    if (cls == "Double+") cDbl++ else if (cls == "Fos+") cFos++ else if (cls == "TdT+") cTdt++ else cNeg++
}
fireHierarchyUpdate()
```
Keep `EXCLUDE_ACRONYMS = ["DG-sg", "VS"]` unchanged (CONTEXT.md: locked in Phase 2, not a Phase-3 decision). The centroid-in-ROI idiom (`excludeRois.any { it.contains(x, y) }`) is the SAME mechanism to reuse for atlas region-label lookup (SC2) and count rollup (SC4) — just against non-excluded leaf region annotations instead of the exclusion set.

**Class-breakdown console printout** (`scripts/classify_markers.groovy` lines 73-85):
```groovy
int n = dets.size()
int classified = n - cExc
def pct = { c -> classified > 0 ? 100.0 * c / classified : 0.0 }
println "Total nuclei: ${n}  |  Excluded (DG/ventricles): ${cExc}  |  Classified: ${classified}"
println String.format("  Negative : %d (%.1f%%)", cNeg, pct(cNeg))
println String.format("  Fos+ only: %d (%.1f%%)", cFos, pct(cFos))
println String.format("  TdT+ only: %d (%.1f%%)", cTdt, pct(cTdt))
println String.format("  Double+  : %d (%.1f%%)", cDbl, pct(cDbl))
```
Reuse verbatim for SC2's console complement; this pattern already satisfies "print class breakdown" per the phase's success criteria.

**Pixel-calibration resolution** (`scripts/qc_detection_gates.groovy` lines 53-65):
```groovy
def server = getCurrentImageData().getServer()
def cal = server.getPixelCalibration()
def pixelSizeUm = FALLBACK_PIXEL_SIZE_UM
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelSizeUm = cal.getAveragedPixelSizeMicrons()
    println "Pixel size read from image server: ${pixelSizeUm} µm/px"
} else {
    println "WARNING: image server has no pixel calibration -- falling back to hard-coded ${FALLBACK_PIXEL_SIZE_UM} µm/px (server.json PhysicalSizeX)"
}
```
Use this before any `RoiTools.buffer(roi, distancePx)` call in the D-04 annulus construction — buffer distance is in pixels (RESEARCH.md Pitfall 2), so `GAP_UM`/`RING_WIDTH_UM` must be divided by `pixelSizeUm` exactly as this analog resolves calibration.

**Region-annotation iteration / area-density template for SC4 rollup** (`scripts/qc_detection_gates.groovy` lines 132-146):
```groovy
annotations.each { ann ->
    def roi = ann.getROI()
    if (roi == null) return
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    def nInside = detections.count { d ->
        def dRoi = d.getROI()
        dRoi != null && roi.contains(dRoi.getCentroidX(), dRoi.getCentroidY())
    }
    def density = nInside / areaMm2
    def label = ann.getPathClass()?.toString() ?: ann.getName() ?: "(unnamed)"
    println "    ${label}: ${nInside} detections / ..."
}
```
Adapt directly for Pattern 4 (count rollup): replace the single `nInside` count with a per-class `counts` map (`["Negative","Fos+","TdT+","Double+","Excluded"]`), and write via `ann.getMeasurementList().put("Count: ${cls}", n as double)` instead of only printing — satisfies SC4's "readable in annotation pane" requirement while keeping the console print as the complement this analog already establishes.

**Entry-confirmation / hierarchy-prerequisite pattern** (`scripts/01_load_abba_rois.groovy` lines 22-25, 76-82):
```groovy
println "Running on: " + getCurrentImageData().getServer().getMetadata().getName()
...
def annotations = getAnnotationObjects()
println "Total annotations loaded: ${annotations.size()}"
```
Add an equivalent entry-name println at the top of `02_detect_classify.groovy` (Pitfall guard against running on the wrong project entry) and confirm `resolveHierarchy()` already ran (it did, in `01_load_abba_rois.groovy`) rather than re-calling it — `02_detect_classify.groovy` only reads the existing hierarchy, it does not rebuild it.

**Anti-pattern flagged from `run_braian_detection.groovy`** (lines 76-86, `AtlasManager.saveResults(...)` writing `results/<image>_regions.tsv`): do NOT treat this file as authoritative for SC4 — it reflects BraiAnDetect's own incompatible classifier application (Deviation #1), predates this script's classification pass, and is written by a separate script run. `02_detect_classify.groovy`'s own annotation-measurement rollup (Pattern 4 above) is the authoritative SC4 mechanism; regenerating a fresh TSV is optional, not required.

---

### `classifiers/object_classifiers/*_bgsub.json` (config, CRUD) — optional, only if new classifier JSON files are authored for D-05

**Analog:** `classifiers/object_classifiers/Fos_Classifier_20x.json` / `TdT_classifier.json` (schema known via `classify_markers.groovy`'s `readSpec` — not re-read here since the schema is already fully captured by the `o.get("measurement").getAsString()` / `o.get("threshold").getAsDouble()` access pattern above)

**Schema to replicate** (inferred from `readSpec`):
```json
{ "function": { "measurement": "<Compartment>: <Channel> mean (bg-sub)", "threshold": <re-derived double> } }
```
Only the `measurement` key changes (append ` (bg-sub)`) and `threshold` is the Pattern-2-derived value; keep the same top-level `function` wrapper so `readSpec`/`loadClassifierSpec` (both `classify_markers.groovy` and `qc_detection_gates.groovy` already parse this shape) continue to work unmodified.

## Shared Patterns

### Zero-detection guard + idempotent re-run (D-02)
**Source:** `scripts/classify_markers.groovy` line 54
**Apply to:** `02_detect_classify.groovy` (Step 0, per RESEARCH.md architecture diagram)
```groovy
if (dets.isEmpty()) { println "No detections — run BraiAnDetect first. Aborting."; return }
```

### Runtime JSON threshold read via bundled Gson (no `groovy.json`)
**Source:** `scripts/classify_markers.groovy` lines 32-38 (also independently reimplemented in `scripts/qc_detection_gates.groovy` lines 183-196 — confirms this is the established project-wide idiom, not a one-off)
**Apply to:** any classifier-JSON consumption in `02_detect_classify.groovy`
```groovy
def o = JsonParser.parseString(new File(base, fn).text).getAsJsonObject().getAsJsonObject("function")
[meas: o.get("measurement").getAsString(), thr: o.get("threshold").getAsDouble()]
```

### Centroid-in-ROI containment idiom
**Source:** `scripts/classify_markers.groovy` lines 58-60; `scripts/qc_detection_gates.groovy` lines 139-146
**Apply to:** exclusion-region test (already present), atlas region label (SC2), count rollup (SC4) — all three use the identical `roi.contains(x, y)` test against different annotation sets
```groovy
def x = r.getCentroidX(), y = r.getCentroidY()
someRoi.contains(x, y)
```

### Dual-location script deploy
**Source:** established Phase 1/2 pattern (D-10/D-11, confirmed present: identical copies of `classify_markers.groovy`, `run_braian_detection.groovy`, `qc_detection_gates.groovy`, `01_load_abba_rois.groovy`, `export_region_dapi_reference.groovy` exist at both `/home/jflab/Analysis/scripts/<name>.groovy` (canonical) and `/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/<name>.groovy` (project-local, required for QuPath's "Run for project"))
**Apply to:** `02_detect_classify.groovy` — write canonical copy at `scripts/02_detect_classify.groovy`, then hard-copy (not symlink — matches existing files, which are real independent copies) to `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy`.

### Pixel-size resolution with fallback
**Source:** `scripts/qc_detection_gates.groovy` lines 53-65
**Apply to:** any µm→px conversion in `02_detect_classify.groovy` (annulus buffer distances, D-04)
```groovy
def cal = server.getPixelCalibration()
def pixelSizeUm = cal.hasPixelSizeMicrons() ? cal.getAveragedPixelSizeMicrons() : FALLBACK_PIXEL_SIZE_UM
```

## No Analog Found

| File/Sub-pattern | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Local-background-subtraction annulus construction (D-04, RESEARCH.md Pattern 1) | transform helper | per-cell geometric+intensity computation | No existing script in this codebase builds an annulus ROI or does neighbor-subtraction; RESEARCH.md's Pattern 1 (verified against installed QuPath/BraiAn jars) is the only source — treat RESEARCH.md as the primary reference for this sub-pattern, not a codebase analog |
| Histogram-peak threshold re-derivation on an arbitrary measurement (D-05, RESEARCH.md Pattern 2) | transform helper | batch/statistical | `ChannelHistogram.findPeaks`/`zeroPhaseFilter` are used internally by BraiAnDetect on raw image histograms (`BraiAn.yml`'s `histogramThreshold` block), not on a Groovy-side measurement array in any existing script — RESEARCH.md Pattern 2 is the reference |
| Atlas pixel↔µm coordinate transform (SC3, RESEARCH.md Pattern 5) | transform helper | request-response (one-shot coordinate query) | No existing script in this codebase calls `AtlasTools.getAtlasToPixelTransform` — Phase 1's `01_load_abba_rois.groovy` only loads region annotations, it never queries coordinates back out. RESEARCH.md Pattern 5 (sourced from an official BIOP-author gist, cross-verified against installed jars) is the reference |

## Metadata

**Analog search scope:** `/home/jflab/Analysis/scripts/` and its mirrored copy under `/home/jflab/Analysis/M3 Hippocampus 20x 062926 3 plane/scripts/`
**Files scanned:** 5 canonical `.groovy` scripts (`classify_markers.groovy`, `run_braian_detection.groovy`, `qc_detection_gates.groovy`, `01_load_abba_rois.groovy`, `export_region_dapi_reference.groovy`), each read in full (all ≤ 90 lines, single-pass reads, no re-reads)
**Pattern extraction date:** 2026-07-09
</content>
