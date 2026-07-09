# Phase 02 — Detection Parameter Lock Record

**Section:** M3 062926 3-plane, entry 1 (`M3_20x_MIP_Z1-3.ome.tiff`)
**Date:** 2026-07-09
**Requirements:** SCRI-02 (channel-correct, histogram-relative `BraiAn.yml`), CLASS-01 (nuclear Fos classifier)
**Status:** **LOCKED** (first-run validation; classification-mechanism + SSp-background refinements deferred to Phase 3)

## Locked detection config — `BraiAn.yml`
| Param | Value | Notes |
|-------|-------|-------|
| classForDetections | `allen_mouse_10um_java` | confine detection to the atlas Root (brain outline, ~56 mm²); `null` detected the whole 77 mm² image (~380k spurious background nuclei) |
| entry / anchor | `DAPI-T4` | nucleus anchor; exact server.json channel name |
| requestedPixelSizeMicrons | 0.6905355 | = PhysicalSizeX, no resampling |
| sigmaMicrons | **2.5** | 2.0 over-split (area peak 30–40, density ~4000); 3.0 merged/missed larger cortical nuclei; 2.5 = compromise |
| minAreaMicrons / maxAreaMicrons | 20 / **250** | 250 raised from 150 to stop clipping larger nuclei/blobs |
| histogramThreshold | resLevel 0, smoothWindow 15, peakProminence 500, **nPeak 2** | D-01 histogram-relative; nPeak 2 → tissue peak (≈2536); nPeak 1 → background floor (≈45, over-detects) |
| cellExpansionMicrons | 5.0 | D-03; creates the Cytoplasm compartment the TdT classifier reads |

## Locked classifier thresholds (D-02 — histogram-relative, entry-1 distributions)
| Classifier | Compartment / measurement | Threshold | Derivation |
|-----------|---------------------------|-----------|-----------|
| `Fos_Classifier_20x` | `Nucleus: AF488-T3 mean` | **13000.4538** | interactive single-measurement UI; ≈ p75 (median 8199) — deliberately liberal to catch dim real Fos+ |
| `TdT_classifier` | `Cytoplasm: AF568-T2 mean` | **16766.4671** | interactive UI; ≈ p98 (median 6380) — stringent |

Compartments unchanged: Fos nuclear (CLASS-01), TdT cytoplasmic ring.

## D-05 detection-quality gates (locked config, sigma 2.5)
- **Gate 1 — nucleus-area peak:** **[40, 50) µm²** (mode ≈45), marginally below the 50–150 µm² seed lower bound. (Peak was [50,60) at sigma 3.0; sigma 2.5 chosen for cortical-cluster completeness — accepted trade.)
- **Gate 2 — DAPI density:** **DG 2886 /mm², CA1 3508 /mm²** (whole-brain ≈4000), above the 500–2000 /mm² seed.
- **Verdict on the seeds:** both seed ranges (TRAP2 literature) judged **mis-calibrated for 20× Airyscan MIP DAPI** and **superseded by the empirical internal per-region reference** (`reference/`, SERIES-02) — expected ranges defined from our own accumulating data, applied prospectively (a-priori, principled).
- **Visual (D-04):** CA1 nuclei cleanly separable (confirmed by researcher). DG granule layer not per-cell separable (expected) → density-only, `DG-sg` excluded from marker classification.

## SCRI-02 / CLASS-01
- **SCRI-02 — SATISFIED:** detection produces non-zero Fos (AF488-T3) and TdT (AF568-T2) cells; channel names verified live vs server.json.
- **CLASS-01 — SATISFIED:** Fos+ lands only in nuclei (`Nucleus: AF488-T3 mean`); confirmed on the `classify_markers` overlay.

## D-06 advisory / D-07
- **D-06 (advisory, NOT a gate):** Double+/TdT+ ratio ≈ **0.40** (within the advisory 0.10–0.40 band). Reported only — not used to tune.
- **D-07:** Fos+ negative-control rate **SKIPPED** — no trustworthy low-activity control region on one hippocampal section. Deferred to the full series.

## Region exclusions (marker classification)
`DG-sg` (granule cell layer — too dense for per-cell marker calls) and `VS` (ventricular systems — no real nuclei) excluded from Fos/TdT classification (`Excluded` class). DG-mo and DG-po remain included. Configurable in `classify_markers.groovy` (`EXCLUDE_ACRONYMS`).

## Deviations discovered → Phase 3 (SCRI-03)
1. **BraiAnDetect classifier list incompatible with our topology.** `AbstractDetections.applyClassifiers` (v1.1.0) requires each classifier to output `[<entry>, Other: <entry>]` and cannot apply two markers to one DAPI set (research A3 risk confirmed). **Resolution:** detect with BraiAnDetect, classify with `scripts/classify_markers.groovy` (nucleus-anchored, compound Double+/Fos+/TdT+, no overlap). Phase-3 export must use this path — **not** `BraiAn.yml classifiers:` / `OverlappingDetections`.
2. **Regional autofluorescence (SSp) breaks absolute thresholds.** Somatosensory cortex reads ~2× AF488, ~1.5× AF568, DAPI ≈1.16×, uniform nucleus/cytoplasm → autofluorescence, not signal. SSp median nuclear-488 (15072) > Fos cutoff (13000) → a global absolute threshold false-positives >50% of SSp. **Phase-3 fix:** background-robust measure — nucleus:cytoplasm ratio (SSp 1.16 ≈ rest 1.02) or local-background subtraction.
3. **Classifier path resolution:** `BraiAn.resolvePath` resolves `<name>.json` against project base + parent (not `classifiers/object_classifiers/`); `name` fields carry the subpath.
4. **Environment:** git repo initialized this phase (was blocked pending git install); QuPath 0.6.0 API fixes to the QC harness (Gson vs `JsonSlurper`, `getMeasurements()` vs removed `getMeasurementValue`, `ImageChannelTools(name, imageData)`).

## Locked artifacts
- `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml`
- `.../classifiers/object_classifiers/Fos_Classifier_20x.json` (thr 13000.4538)
- `.../classifiers/object_classifiers/TdT_classifier.json` (thr 16766.4671)
- `scripts/run_braian_detection.groovy`, `scripts/classify_markers.groovy`, `scripts/qc_detection_gates.groovy`
- `scripts/export_region_dapi_reference.groovy`, `scripts/build_dapi_reference.py`, `reference/README.md`
