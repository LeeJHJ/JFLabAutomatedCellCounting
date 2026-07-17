---
phase: 04-biological-plausibility-validation-and-imaging-optimization-
reviewed: 2026-07-17T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - scripts/03_export_val01_metrics.groovy
  - scripts/val01_metrics.py
  - scripts/opt01_zplane_audit.py
  - M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy
findings:
  critical: 1
  warning: 3
  info: 3
  total: 7
status: resolved
resolved: 2026-07-17T00:00:00Z
---

> **Resolution (2026-07-17):** All findings addressed. CR-01 fixed in `29dbfdc` (smallest-area
> region assignment + geometric `is_leaf` in `03_export_val01_metrics.groovy`) and `1052bc6`
> (dropped the harmful `is_leaf` density filter in `val01_metrics.py`); operator re-ran the QuPath
> export, `grey` attribution collapsed 95,383 → 0, and `04-VALIDATION-RECORD.md` was regenerated on
> corrected data (`99728bb`). WR-01/02/03 + IN-01/03 fixed in `29dbfdc` and verified against
> synthetic fixtures (strict-JSON, empty-area degrade, renamed `_px` cols). IN-02 (opt01 default
> paths span project date-stamps) left open for user confirmation — the defaults may be intentional
> per-variant paths.

# Phase 04: Code Review Report

**Reviewed:** 2026-07-17
**Depth:** standard
**Files Reviewed:** 4 (3 unique; the two `03_export_val01_metrics.groovy` copies are byte-identical — verified via `diff`, no divergence)
**Status:** issues_found

## Summary

Reviewed the VAL-01 export/metrics pair (`03_export_val01_metrics.groovy` + `val01_metrics.py`) and the OPT-01/02 audit (`opt01_zplane_audit.py`). The scripts are well-documented, null-guarded in most hot paths, and the CZI dim-parsing idiom matches `czi_mip.py`. The dual-location Groovy copies are byte-identical (no divergence to flag).

However, an **end-to-end run against the on-disk TSVs surfaced a scientific-correctness defect**: the per-region "leaf-only" density and per-subfield ratio metrics are corrupted because the `is_leaf` heuristic (child-annotation emptiness) is unreliable on the actual ABBA/QuPath hierarchy. The rollup region `grey` (24.6 mm², geometrically overlapping every subfield) leaks into the leaf-only metric and absorbs 95,383 cells, and `regionOf`'s first-match assignment is iteration-order-dependent between a rollup and its children. This silently produces misleading per-region counts/densities — exactly the failure mode called out in the review brief. Three lower-severity issues (invalid JSON output, an unguarded crash path, minor divide-by-zero edges) round out the findings.

I ran `val01_metrics.py` in the `braian` env against the existing exports to confirm CR-01 and WR-01 empirically; findings below cite observed output.

## Critical Issues

### CR-01: Rollup regions leak into the "leaf-only" density/ratio metrics — per-region scientific values are silently wrong

**File:** `scripts/03_export_val01_metrics.groovy:62-72,151` and `scripts/val01_metrics.py:129-145`
**Issue:**
Both the per-cell region assignment (`regionOf` / `regionAnnotations`) and the per-region area export determine "leaf region" by *child-annotation emptiness* (`!ann.getChildObjects().any { it.isAnnotation() }` / `is_leaf`). `val01_metrics.py:compute_density` then relies on `is_leaf` to "avoid double-counting area from ancestor (non-leaf) regions that overlap their leaf children" (comment at lines 137-138). That safeguard is defeated by the real hierarchy on disk:

Inspecting the generated `val01_region_area.tsv`:
```
Right: grey   grey   is_leaf=False   24.834326 mm²
Left:  grey   grey   is_leaf=True    24.599842 mm²   <-- rollup mislabeled as leaf
```
The same rollup acronym is flagged `is_leaf` on one hemisphere but not the other (`grey`, `cst`, and `int` all show mixed `is_leaf` across hemispheres). Because `grey` is a filled polygon that geometrically overlaps every grey-matter subfield, two things go wrong:

1. **Order-dependent per-cell attribution.** `regionOf` returns the *first* leaf annotation whose ROI contains the centroid. Since `Left: grey` qualifies as a "leaf" (no annotation children) and overlaps CA1/DG/cortex, cells are assigned to `grey` or to their true subfield depending on `getAnnotationObjects()` iteration order. The metrics run shows **95,383 cells attributed to `grey`** — cells that belong to specific hippocampal subfields are absorbed into the rollup, so the VAL-01 per-subfield ratio and density (the actual scientific target) are undercounted.
2. **Area double-counting.** `compute_density` sums `is_leaf` areas by acronym; `grey`'s 24.6 mm² is included as a "leaf" even though it overlaps the real leaves that are also summed. `density = 95383 / 24.5998 = 3877/mm²` for a rollup that is not a leaf at all.

This is not an imaging artifact — it is a region-set/hierarchy assumption in the code that the data violates, and it produces misleading numbers with no warning. VAL-01 consumes these as the findings record feeding `04-VALIDATION.md`.

**Fix:** Do not infer "leaf" from child-annotation emptiness against a hierarchy that is not guaranteed to be consistently nested. Options, in order of robustness:
- Anchor "leaf" to the atlas itself: label/keep only regions whose acronym has no children in the Allen CCFv3 ontology (BraiAn / brainglobe `atlasapi` can supply the leaf set), rather than QuPath child-annotation topology.
- Or, in the Groovy, explicitly exclude known rollups (`root`, `grey`, `CH`, `CTX`, `Isocortex`, `HPF`, `fiber tracts`, …) and assign each cell to the *smallest-area* containing region rather than the first match:
```groovy
def regionOf = { detection ->
    def r = detection.getROI()
    double x = r.getCentroidX(), y = r.getCentroidY()
    regionAnnotations.findAll { it.getROI().contains(x, y) }
                     .min { it.getROI().getArea() }   // smallest containing region = true leaf
}
```
- And in `val01_metrics.py`, guard against overlapping-area contamination (e.g., drop any acronym whose area exceeds a plausible single-subfield bound, or intersect against the atlas leaf set) so a rollup can never enter the density/ratio tables.

## Warnings

### WR-01: `--out` JSON dump emits invalid JSON; the nan→null `default` lambda is dead code

**File:** `scripts/val01_metrics.py:280`
**Issue:** The intent is to serialize NaN metrics as `null`:
```python
json.dump(..., default=lambda o: None if isinstance(o, float) and np.isnan(o) else o)
```
`json.dump`'s `default` callback only fires for objects the encoder *cannot* natively serialize. Native Python `float("nan")` (used throughout for missing ratios/rates) *is* natively serialized — as the literal token `NaN`, which the lambda never sees. Confirmed by running with `--out`: the output file contains **28 literal `NaN` tokens** and fails strict JSON parsing (`json.loads(..., parse_constant=raise)` → `ValueError: NaN`). Any strict/cross-language consumer of the findings-record JSON will reject it, and the intended null-substitution silently does nothing.
**Fix:** Sanitize NaNs before dumping and disable non-standard tokens:
```python
def _clean(o):
    if isinstance(o, float) and np.isnan(o): return None
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list): return [_clean(v) for v in o]
    return o
json.dump(_clean(payload), f, indent=2, allow_nan=False)
```

### WR-02: `compute_area_peak` crashes on an all-NaN area column instead of degrading to n/a

**File:** `scripts/val01_metrics.py:60-71,148-159`
**Issue:** `area_histogram_mode` filters NaNs then calls `np.argmax(counts)`. On an empty array this raises `ValueError: attempt to get argmax of an empty sequence` (confirmed in repro). Every *other* stat in `compute_area_peak` guards with `if areas_valid.size`, but the mode call does not. This matters here specifically: the Groovy header (lines 84-89) documents that `nucleus_area_um2` was previously **all-null** (the exact 04-03 human-verify regression this script was written to fix). If that ROI-geometry fix regresses (e.g., `getNucleusROI` returns null across a QuPath version bump), the column is all-empty → all-NaN → this metric crashes with an opaque error instead of reporting `n/a` like the others.
**Fix:** Guard the mode call:
```python
areas_um2 = areas_um2[~np.isnan(areas_um2)]
if areas_um2.size == 0:
    return float("nan"), float("nan"), 0
```

### WR-03: `opt01_zplane_audit.py` divide-by-zero / int(NaN) on degenerate region-TSV inputs

**File:** `scripts/opt01_zplane_audit.py:127,120`
**Issue:** `pct_diff = abs(n_3plane - n_hybrid) / n_3plane * 100.0` raises `ZeroDivisionError` if the 3-plane Root DAPI count is 0. Separately, `int(root_rows.iloc[0]["Num DAPI-T4"])` raises `ValueError` if that cell is blank/NaN (pandas coerces an empty numeric cell to NaN). Both are edge cases (a real Root DAPI rollup should be a positive integer), but they fail with cryptic tracebacks rather than the script's otherwise-clear `sys.exit` diagnostics.
**Fix:** Validate before dividing/casting:
```python
val = root_rows.iloc[0]["Num DAPI-T4"]
if pd.isna(val):
    sys.exit(f"region TSV {region_tsv}: Root row 'Num DAPI-T4' is empty.")
return int(val)
...
if n_3plane == 0:
    sys.exit("3-plane Root DAPI count is 0 — cannot compute percent difference.")
```

## Info

### IN-01: Per-cell `centroid_x`/`centroid_y` are exported in pixels, unlabeled, and unused downstream

**File:** `scripts/03_export_val01_metrics.groovy:110-112,124`
**Issue:** `r.getCentroidX()/getCentroidY()` are image pixel coordinates, exported under bare column names `centroid_x`/`centroid_y`. `val01_metrics.py` reads them (`to_numeric`) but never uses them. CLAUDE.md mandates micron export for coordinates; these are harmless today only because nothing consumes them, but the unlabeled pixel units are a trap for any future consumer (e.g., a brainrender point cloud).
**Fix:** Either drop the columns, or multiply by `pixelUm` and rename to `centroid_x_um`/`centroid_y_um` (note: these would still be image-space, not CCFv3 atlas microns — document that).

### IN-02: `opt01` default paths span three different project date-stamps

**File:** `scripts/opt01_zplane_audit.py:28-37,141`
**Issue:** `DEFAULT_CZI` → `…062026.czi`, `DEFAULT_MIP` → `M3 Hippocampus 20x 062226/…`, region TSVs → `M3 Hippocampus 20x 062926 3 plane/`. All three exist on disk so the script runs, but the OPT-02 raw:MIP ratio compares a CZI and a MIP that live in different project directories than the region TSVs. If these are not the same acquisition/projection, the ratio is misleading.
**Fix:** Confirm the three defaults refer to the same underlying M3 acquisition; if the intended MIP lives in the `062926 3 plane` project, point `DEFAULT_MIP` there.

### IN-03: `ratio_convention` and `coexpr_fraction` are checked against the same target band

**File:** `scripts/val01_metrics.py:201-204,46`
**Issue:** `Double+/TdT+` (`ratio_convention`) and `Double+/(Double++TdT+)` (`coexpr_fraction`) are mathematically different quantities but are both banded against `RATIO_TARGET = (0.10, 0.40)` and printed with the same "target 10%-40%" label. They cannot both sit meaningfully in the same band (e.g., ratio 0.40 ↔ coexpr 0.286). Since this is a findings record, not a gate, the risk is only interpretive, but the shared label can mislead transcription into `04-VALIDATION.md`.
**Fix:** Either give each metric its own target band or annotate the print lines so the reader knows the band was defined for one convention only.

---

## Structural Findings (fallow)

No structural pre-pass was provided for this review.

---

_Reviewed: 2026-07-17_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
