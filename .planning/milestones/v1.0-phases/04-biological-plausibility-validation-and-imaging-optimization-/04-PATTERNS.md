# Phase 4: Biological Plausibility Validation and Imaging Optimization - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 5 (2 code files to create, 2 markdown deliverables, 1 optional CLI helper)
**Analogs found:** 4 / 4 code-bearing files (both markdown docs have no code analog — documentation only)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `scripts/03_export_val01_metrics.groovy` (new — D-03 per-cell + per-region export) | script / utility (QuPath, human-run) | batch / file-I/O (data.qpdata → CSV) | `scripts/export_region_dapi_reference.groovy` (region loop + CSV write) + `scripts/02_detect_classify.groovy` (per-cell measurement keys, region labeling) + `scripts/qc_detection_gates.groovy` (pixel calibration, area binning) | exact (region-export shape) / role-match (per-cell keys) |
| `scripts/val01_metrics.py` (new — Python VAL-01 metrics + histogram) | utility / transform (Python, `braian` env) | batch (TSV → computed metrics → markdown feed) | `scripts/build_dapi_reference.py` (CSV load, groupby/aggregate, CLI, `argparse` conventions) | exact |
| Inline OPT-01 Z-plane-count snippet (folded into `val01_metrics.py` or a small script, per RESEARCH Wave-0 gap) | utility (file-I/O, metadata read) | transform (CZI metadata read) | `czi_mip.py` (`aicspylibczi.CziFile`, `get_dims_shape()`, scaling read) | exact |
| `04-VALIDATION.md` (deliverable) | documentation | n/a | none (new doc type; content dictated by CONTEXT D-01/D-02/D-06) | no analog — documentation only |
| `04-IMAGING-NOTES.md` (deliverable) | documentation | n/a | none | no analog — documentation only |

## Pattern Assignments

### `scripts/03_export_val01_metrics.groovy` (script, batch/file-I/O)

**Primary analog:** `scripts/export_region_dapi_reference.groovy` (whole file, 84 lines) — closest structural match: it already does "iterate region annotations → compute per-region area in mm² → write CSV row" exactly as D-04 requires. This new script should be a **near-copy of that structure, extended with a second per-cell loop.**

**Secondary analogs (measurement keys / region labeling):** `scripts/02_detect_classify.groovy` and `scripts/qc_detection_gates.groovy`.

**Header/doc-comment convention** (`export_region_dapi_reference.groovy` lines 1-21):
```groovy
/**
 * export_region_dapi_reference.groovy
 *
 * Appends THIS image's per-region DAPI density to a central, growing internal
 * reference...
 *
 * Run AFTER a BraiAnDetect detection pass on the current entry. Writes/appends to
 *     <Analysis>/reference/dapi_region_reference.csv
 * ...
 * @author section-pipeline
 */
import static qupath.lib.scripting.QP.*
```
Copy this doc-comment shape (scope, run-order requirement, output path, `@author section-pipeline`) for the new export script header — state explicitly that it must run AFTER `02_detect_classify.groovy` (needs `getPathClass()` already set) and is human-run via "Run for project", following the dual-location deploy convention already established (canonical copy in `/home/jflab/Analysis/scripts/`, hard-copied into `M3 Hippocampus 20x 062926 3 plane/scripts/`).

**Pixel calibration resolution pattern** (`export_region_dapi_reference.groovy` lines 24-28, identically in `qc_detection_gates.groovy` lines 57-66 and `02_detect_classify.groovy` lines 129-137 — this exact idiom is used in 3 files, treat as the canonical shared pattern):
```groovy
def imageData = getCurrentImageData()
def server = imageData.getServer()
def cal = server.getPixelCalibration()
def pixelUm = (cal != null && cal.hasPixelSizeMicrons()) ? cal.getAveragedPixelSizeMicrons() : 0.6905355
def pxToMm2 = (pixelUm * 1e-3) ** 2
```
Copy verbatim (with the `qc_detection_gates.groovy`-style WARNING println if calibration is missing, lines 60-65) — do not re-derive the fallback constant; it is the known entry-1 `PhysicalSizeX` value (0.6905355 µm/px).

**Per-region area export loop** (`export_region_dapi_reference.groovy` lines 53-69) — this is the direct D-04 analog:
```groovy
def rows = []
getAnnotationObjects().each { ann ->
    def roi = ann.getROI()
    if (roi == null) return
    if (ann.getChildObjects().any { it.isDetection() }) return
    def label = ann.getPathClass()?.toString() ?: ann.getName()
    if (label == null || label == "AllDetections") return
    def isLeaf = ann.getChildObjects().findAll { it.isAnnotation() }.isEmpty()
    def hemisphere = ""; def acronym = label
    def m = (label =~ /(?i)^(Left|Right):\s*(.+)$/)
    if (m.find()) { hemisphere = m.group(1); acronym = m.group(2) }
    def areaMm2 = roi.getArea() * pxToMm2
    if (areaMm2 <= 0) return
    int n = 0
    for (int i = 0; i < nDet; i++) if (roi.contains(cx[i], cy[i])) n++
    rows << [timestamp, configTag, imageName, label, hemisphere, acronym, isLeaf, areaMm2, n, n / areaMm2]
}
```
Reuse the hemisphere/acronym regex-split and the leaf-detection idiom unchanged. What must change: replace the single `n` (raw DAPI count) with **per-class counts** (Negative/Fos+/TdT+/Double+/Excluded) matching `02_detect_classify.groovy`'s `ROLLUP_CLASSES` list (lines 492-507) — that script already computes and stores `Count: <class>` on each annotation's `getMeasurementList()`, so the export can simply **read those pre-computed measurements** (`ann.getMeasurementList().get("Count: ${cls}")`) instead of re-deriving containment, avoiding a second O(n_det × n_regions) pass.

**Per-cell measurement export — exact key names (CRITICAL, per RESEARCH Pitfall 4):** read directly from `02_detect_classify.groovy`'s own written keys, do not guess generic names:
```groovy
// From 02_detect_classify.groovy lines 240-241 (bg-sub measures) and area key from
// qc_detection_gates.groovy line 82:
def areaKey  = "Nucleus: Area µm^2"
def fosKey   = "Nucleus: AF488-T3 mean (bg-sub)"
def tdtKey   = "Cytoplasm: AF568-T2 mean (bg-sub)"
// getPathClass() gives the compound class string: "Double+"/"Fos+"/"TdT+"/"Negative"/"Excluded"
// (02_detect_classify.groovy lines 400-413)
```
For per-cell centroid: `d.getROI().getCentroidX()` / `getCentroidY()` (pixel space; D-03 scope is class/region/area/centroid only — NOT the Atlas_X/Y/Z micron export, which is explicitly deferred to v2 EXP-01/03 per CONTEXT.md line 111).

**Region label per cell** — reuse `02_detect_classify.groovy`'s `regionOf`/`regionLabel` closures verbatim (lines 435-461):
```groovy
def regionAnnotations = getAnnotationObjects().findAll { ann ->
    def roi = ann.getROI()
    roi != null && !ann.getChildObjects().any { it.isAnnotation() }
}
def regionOf = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotations.find { it.getROI().contains(x, y) }
}
def regionLabel = { region ->
    if (region == null) return "(no region)"
    def label = region.getPathClass()?.toString() ?: region.getName()
    if (label == null) return "(no region)"
    def m = (label =~ /(?i)^(?:Left|Right):\s*(.+)$/)
    return m.find() ? m.group(1) : label
}
```
Note: `02_detect_classify.groovy`'s own doc-comment (SC2, lines 56-62) explicitly warns against persisting region label as per-cell metadata ("memory-inefficient... MeasurementList is numeric-only") — the export script is the correct place to materialize this ephemeral value into a durable TSV row, which is a one-time full pass, not a per-run recomputation cost.

**CSV/TSV write idiom** (`export_region_dapi_reference.groovy` lines 71-83):
```groovy
def refDir = new File(getProject().getBaseDirectory().getParentFile(), "reference")
refDir.mkdirs()
def csv = new File(refDir, "dapi_region_reference.csv")
def header = "timestamp,config_tag,image,region_label,hemisphere,acronym,is_leaf,area_mm2,n_dapi,density_per_mm2"
if (!csv.exists()) csv.text = header + "\n"
def sb = new StringBuilder()
rows.each { r -> sb.append(String.format('%s,%s,"%s","%s",%s,"%s",%s,%.6f,%d,%.3f%n', ...)) }
csv.append(sb.toString())
println "Appended ${rows.size()} region rows to ${csv}"
```
Copy this append-with-header-guard idiom for both the per-cell TSV (suggest a distinct output path, e.g. `<project>/results/val01_percell_export.tsv`, since this is a Phase-4-scoped one-off export, not a growing cross-image reference like `dapi_region_reference.csv`) and the per-region-area TSV (D-04). Use `\t` delimiter if TSV per CONTEXT's "CSV/TSV" wording — either is fine, but must match what `val01_metrics.py` parses.

**Config-tag / BraiAn.yml read pattern** (`export_region_dapi_reference.groovy` lines 30-39) — optional but useful for provenance stamping the export with the same `config_tag` convention already used by the DAPI reference CSV:
```groovy
def yml = new File(getProject().getBaseDirectory(), "BraiAn.yml").text
def grab = { pat -> def m = (yml =~ pat); m.find() ? m.group(1) : "NA" }
def sigma = grab(/sigmaMicrons:\s*([0-9.]+)/)
```

**Classifier-threshold read pattern** (if the export needs to re-report thresholds, e.g. for the k=3-sensitivity interpretation in D-02) — `qc_detection_gates.groovy` lines 183-196, using bundled Gson because QuPath's Groovy lacks `groovy.json`:
```groovy
import com.google.gson.JsonParser
def loadClassifierSpec = { String fileName ->
    def f = new File(classifiersDir, fileName)
    def fn = JsonParser.parseString(f.text).getAsJsonObject().getAsJsonObject("function")
    return [fileName: fileName, measurement: fn.get("measurement").getAsString(), threshold: fn.get("threshold").getAsDouble()]
}
```

**What must change vs. the analogs:**
- Add a per-cell TSV output (analogs only export per-region rows) — new code, not present in any analog.
- Do not append/grow like `dapi_region_reference.csv` (that file is a cross-image drift reference; this export is a single-run Phase-4 snapshot) — write a fresh file per run (or timestamp-suffixed) rather than appending indefinitely.
- Must run strictly after classification (unlike `export_region_dapi_reference.groovy`, which only needs DAPI detections, not marker classification).

---

### `scripts/val01_metrics.py` (utility, batch/transform)

**Analog:** `scripts/build_dapi_reference.py` (full file, 105 lines).

**Module docstring + usage-block convention** (lines 1-14):
```python
#!/usr/bin/env python3
"""build_dapi_reference.py — aggregate + QC the internal per-region DAPI density reference.

Reads the CSV appended by ``export_region_dapi_reference.groovy`` and computes...

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/build_dapi_reference.py
  conda run -n braian python scripts/build_dapi_reference.py --leaf-only
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import numpy as np
import pandas as pd
```
Copy this exact shebang/docstring/usage-example/import-order shape for `val01_metrics.py`.

**CSV load-and-clean pattern** (lines 25-36) — the "Groovy writes booleans as strings, coerce" idiom is directly relevant since the new Groovy export will have the same string-boolean issue for any `is_leaf`/`Excluded` flags:
```python
def load(ref_csv: Path) -> pd.DataFrame:
    if not ref_csv.exists():
        sys.exit(f"reference CSV not found: {ref_csv}\nRun export_region_dapi_reference.groovy in QuPath first.")
    df = pd.read_csv(ref_csv)
    df["is_leaf"] = df["is_leaf"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    df["hemisphere"] = df["hemisphere"].fillna("")
    df = df.sort_values("timestamp").drop_duplicates(subset=["config_tag", "image", "region_label"], keep="last")
    return df
```

**argparse CLI convention** (lines 65-77), matching the project-wide convention (`formatter_class=RawDescriptionHelpFormatter`, `epilog=__doc__`, `type=Path`):
```python
ap = argparse.ArgumentParser(
    description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
ap.add_argument("--ref-csv", type=Path, default=Path("reference/dapi_region_reference.csv"), help="...")
ap.add_argument("--out", type=Path, default=Path("reference/dapi_region_reference_stats.csv"), help="...")
```
For `val01_metrics.py`: use `--export-tsv` (default e.g. `results/val01_percell_export.tsv`) and `--out` (e.g. `04-VALIDATION-metrics.json` or directly print + let the phase-4 doc-writing step consume stdout — planner's call per RESEARCH's Wave-0 gap note that no test framework exists; the "quick run command" is just re-running this script).

**Aggregation pattern** (`groupby(...).agg(...)`, lines 39-47) — directly reusable shape for the per-region DAPI-density computation (D-04):
```python
g = df.groupby(["config_tag", "hemisphere", "acronym"])["density_per_mm2"]
stats = g.agg(n_images="count", mean_density="mean", sd_density="std", min_density="min", max_density="max").reset_index()
```
Adapt for VAL-01: group per-cell rows by `region_label` to get counts per class, join with the per-region-area TSV (D-04) to compute density.

**Histogram-mode function — already fully specified in RESEARCH.md** (`## Nucleus-Area-Peak Estimation Method`), copy verbatim as the area-peak estimator, matching `qc_detection_gates.groovy`'s Gate-1 10 µm² binning (`AREA_BIN_WIDTH_UM2 = 10.0`, lines 40, 101-108):
```python
import numpy as np

def area_histogram_mode(areas_um2: np.ndarray, bin_width: float = 10.0) -> tuple[float, float, int]:
    """Returns (bin_start, bin_end, count) of the modal 10 um^2 bin."""
    areas_um2 = areas_um2[~np.isnan(areas_um2)]
    bin_starts = np.floor(areas_um2 / bin_width) * bin_width
    values, counts = np.unique(bin_starts, return_counts=True)
    peak_idx = np.argmax(counts)
    return values[peak_idx], values[peak_idx] + bin_width, int(counts[peak_idx])
```

**Print/report convention** (lines 80-100) — `print(f"Loaded {len(df)} ...")` top-level, then a labeled results block; reuse for VAL-01's four metrics + interpretation notes printed to stdout before being transcribed into `04-VALIDATION.md`.

**What must change vs. the analog:** `build_dapi_reference.py` aggregates *across images* (drift-monitoring use case); `val01_metrics.py` operates on a *single* run's per-cell + per-region export and computes ratio/density/area-peak/Fos-control-rate — no cross-image join logic needed. Also needs the ratio computation (`Double+ / TdT+`) which has no direct analog in `build_dapi_reference.py` but is trivial pandas (`df["class"].value_counts()`).

---

### OPT-01 CZI Z-plane-count / pixel-size read (inline snippet or small helper)

**Analog:** `czi_mip.py` (full file) — specifically the open/inspect block (lines 19-31):
```python
import aicspylibczi
czi = aicspylibczi.CziFile(F_IN)
dims = czi.get_dims_shape()
dim0 = dims[0] if isinstance(dims, list) else dims
n_c = dim0.get('C', (0, 1))[1]
n_z = dim0.get('Z', (0, 1))[1]
n_s = dim0.get('S', (0, 1))[1]
print(f"  Scenes={n_s}  Channels={n_c}  Z-planes={n_z}")
```
RESEARCH.md's own Code Examples section (`## Code Examples`) already extends this with the Scaling/Items metadata read for Z-step and pixel size (not present in `czi_mip.py`, which hardcodes `PIXEL_SIZE_UM = 0.69` at line 17 rather than reading it) — copy that RESEARCH-provided snippet, not `czi_mip.py`'s hardcoded constant, for OPT-01 (the whole point is to measure rather than hardcode):
```python
scaling = czi.meta.find('.//Scaling/Items')
z_step_m = float(scaling.find("./Distance[@Id='Z']/Value").text)
xy_um    = float(scaling.find("./Distance[@Id='X']/Value").text) * 1e6
```
Fold this into `val01_metrics.py` as an `--opt01` flag or a standalone `scripts/opt01_zplane_audit.py` (planner's call, RESEARCH Wave-0 gap explicitly allows either). File path convention for `F_IN` follows `czi_mip.py`'s `F_IN`/`F_OUT` UPPER_SNAKE_CASE module constants at top of script (line 15-16), or pass as `argparse` `type=Path` per the `build_dapi_reference.py` CLI convention if made a standalone script.

---

### `04-VALIDATION.md` / `04-IMAGING-NOTES.md` (documentation deliverables)

No code analog exists in this codebase for markdown deliverable structure — these are new document types. Follow the phase's own CONTEXT.md/RESEARCH.md prose conventions already used in this project's `.planning/phases/*/` tree (e.g. `03-VERIFICATION.md`, `02-LOCK-RECORD.md` are the closest sibling *documents*, not code, for section-heading and "measured vs. interpreted" framing) — content requirements are fully specified in CONTEXT.md D-01/D-02/D-05/D-06 and RESEARCH.md's per-metric writeups; no additional pattern extraction needed since this is prose, not code structure.

## Shared Patterns

### Pixel-calibration resolution (µm/px, with fallback)
**Source:** `scripts/qc_detection_gates.groovy` lines 57-66 (canonical, most defensive: prints a WARNING on fallback); same idiom also in `export_region_dapi_reference.groovy` lines 24-28 and `02_detect_classify.groovy` lines 129-137.
**Apply to:** the new D-03 export script (both per-cell and per-region area sections).
```groovy
def cal = server.getPixelCalibration()
def pixelSizeUm = FALLBACK_PIXEL_SIZE_UM   // 0.6905355 — server.json PhysicalSizeX, entry 1
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelSizeUm = cal.getAveragedPixelSizeMicrons()
    println "Pixel size read from image server: ${pixelSizeUm} µm/px"
} else {
    println "WARNING: image server has no pixel calibration -- falling back to hard-coded ${FALLBACK_PIXEL_SIZE_UM} µm/px (server.json PhysicalSizeX)"
}
```

### Exact measurement-key access (avoid the Phase-3 D-04/D-05 bug)
**Source:** `scripts/02_detect_classify.groovy` lines 230-241, 240-241 (bg-sub keys written), reiterated as RESEARCH Pitfall 4.
**Apply to:** the D-03 export script — must read these literal strings, not reconstruct generic names:
```
"Nucleus: Area µm^2"
"Nucleus: AF488-T3 mean (bg-sub)"    (Fos)
"Cytoplasm: AF568-T2 mean (bg-sub)"  (TdT)
getPathClass()                        (Double+/Fos+/TdT+/Negative/Excluded)
```

### CSV/TSV append-with-header-guard idiom
**Source:** `scripts/export_region_dapi_reference.groovy` lines 71-83.
**Apply to:** both new TSV outputs from the D-03 export script.
```groovy
if (!csv.exists()) csv.text = header + "\n"
csv.append(sb.toString())
println "Appended ${rows.size()} rows to ${csv}"
```

### Groovy JSON parsing without `groovy.json` (Gson)
**Source:** `scripts/qc_detection_gates.groovy` lines 36, 183-196.
**Apply to:** any part of the export script that needs to read classifier JSON (e.g. reporting the k=3 threshold values alongside the Double+/TdT+ ratio for the D-02 interpretation).
```groovy
import com.google.gson.JsonParser
def fn = JsonParser.parseString(f.text).getAsJsonObject().getAsJsonObject("function")
```

### Python CLI / docstring / load-clean-aggregate skeleton
**Source:** `scripts/build_dapi_reference.py` (whole file).
**Apply to:** `val01_metrics.py` — reuse `argparse` shape, `Path` typing, `sys.exit` for missing-input guard, and pandas groupby/agg idiom.

### Dual-location script deploy (canonical + project-copy)
**Source:** established convention, visible in the parallel existence of `scripts/*.groovy` and `M3 Hippocampus 20x 062926 3 plane/scripts/*.groovy` (identical filenames in both locations, confirmed via directory listing this session).
**Apply to:** the new `03_export_val01_metrics.groovy` — author it in `/home/jflab/Analysis/scripts/`, then hard-copy into `M3 Hippocampus 20x 062926 3 plane/scripts/` before running "Run for project" in QuPath.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `04-VALIDATION.md` | documentation | n/a | No markdown deliverable of this exact shape exists yet in the codebase; content fully specified by CONTEXT.md/RESEARCH.md prose, not by a code pattern |
| `04-IMAGING-NOTES.md` | documentation | n/a | Same as above — new forward-looking-recommendations document type |

## Metadata

**Analog search scope:** `/home/jflab/Analysis/scripts/` (all `.groovy` and `.py`), `/home/jflab/Analysis/czi_mip.py`, `/home/jflab/Analysis/czi_hybrid_mip.py` (checked, not needed — no closer match than `czi_mip.py`)
**Files scanned:** 11 Groovy scripts (canonical + project-copies, treated as 6 unique canonical files), 4 Python scripts
**Pattern extraction date:** 2026-07-16

## PATTERN MAPPING COMPLETE

**Phase:** 04 - biological-plausibility-validation-and-imaging-optimization
**Files classified:** 5 (2 new code files with strong analogs, 1 inline metadata-read snippet with strong analog, 2 documentation deliverables with no code analog)
**Analogs found:** 4 / 4 code-bearing files (both docs correctly listed as no-analog)

### Coverage
- Files with exact analog: 2 (`val01_metrics.py` ← `build_dapi_reference.py`; OPT-01 CZI read ← `czi_mip.py`)
- Files with role-match/near-exact analog: 1 (`03_export_val01_metrics.groovy` ← `export_region_dapi_reference.groovy` + `02_detect_classify.groovy` + `qc_detection_gates.groovy`, composite of three)
- Files with no analog: 2 (both markdown deliverables — expected, documentation only)

### Key Patterns Identified
- The D-03 Groovy export is a **direct structural extension of `export_region_dapi_reference.groovy`'s region-loop + CSV-write idiom**, plus a new per-cell loop that must read `02_detect_classify.groovy`'s exact bg-sub measurement keys (`"Nucleus: AF488-T3 mean (bg-sub)"`, `"Cytoplasm: AF568-T2 mean (bg-sub)"`, `"Nucleus: Area µm^2"`) and reuse its `regionOf`/`regionLabel` closures verbatim — this is the single highest-risk area (RESEARCH Pitfall 4, the exact root cause of the Phase-3 all-Negative bug).
- The Python metrics script should follow `build_dapi_reference.py`'s docstring/argparse/pandas-groupby skeleton, dropping the cross-image aggregation logic (not needed for a single n=1 run) and adding the RESEARCH-specified `area_histogram_mode` function (10 µm² bins, matches Groovy's Gate-1 binning for direct comparability).
- Pixel-calibration resolution (`getPixelCalibration()` + `0.6905355` fallback + WARNING println) is a 3x-repeated shared idiom across `qc_detection_gates.groovy`, `export_region_dapi_reference.groovy`, and `02_detect_classify.groovy` — copy it verbatim into the new export script rather than re-deriving.

### File Created
`/home/jflab/Analysis/.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-PATTERNS.md`

### Ready for Planning
Pattern mapping complete. Planner can now reference analog patterns in PLAN.md files.
