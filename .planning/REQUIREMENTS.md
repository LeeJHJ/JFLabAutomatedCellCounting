# Requirements: M3 Section Pipeline — v1.1 First Full-Series Run (LA/BA Amygdala Engram, wBA1-3)

**Defined:** 2026-07-17
**Core Value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region across a registered section series, with locked detection parameters and imaging-optimization notes ready to scale brain-wide.

## v1 Requirements

Requirements for milestone v1.1. Each maps to a roadmap phase. Data: `-001-07_processed.czi` (16 GB Airyscan, 5 mosaic scenes, Z=4, C=3, 0.69 µm/px; channels `AF568-T2`/`AF488-T3`/`DAPI-T4`).

### Conversion (multi-scene MIP)

- [x] **CONV-01**: `czi_mip.py` emits one MIP OME-TIFF per scene from the multi-scene processed CZI (5 section files), using `get_all_mosaic_scene_bounding_boxes()` + per-scene `read_mosaic(region=bbox)` so scenes are not fused
- [x] **CONV-02**: Each scene's output OME-TIFF is verified to the correct physical section (scene-identity / AP-order check via bounding box + morphology) before it enters registration

### Imaging Re-Validation (new 4-plane / lower-laser params)

- [ ] **IMG-01**: Detection + classification are re-validated on the new-param MIPs — the D-05 QC gates are re-run and the background-subtraction distribution shape is compared to the v1.0 reference; the k robust-threshold seed is re-locked only if it has drifted (re-swept 3–5), not merely confirmed non-empty
- [ ] **IMG-02**: Under-projection / DAPI-quality is checked on the 4-plane MIP (OPT-01-style plateau confirmation; visual DAPI-blob check) and the new Z-range vs v1.0's stack is documented

### Registration Speedup (continues REG-01/02 from v1.0)

- [x] **REG-03**: DeepSlice batch `predict()` + angle propagation registers the 5-section series with materially less manual effort than per-section from scratch
- [x] **REG-04**: A reduced-landmark BigWarp workflow with a documented per-section effort target (middle ground vs the v1.0 5–15 min manual pass), applied across all 5 sections
- [x] **REG-05**: An experimental masked-elastix prototype (`crop_to_tissue.py` DAPI mask → elastix Affine/Spline outside ABBA's GUI) is trialed on one section and compared to DeepSlice-only on fit quality + time; kept only if it demonstrably wins (a priori accept/reject rule)

### Pipeline Generalization (region-agnostic per-region readout spine — Phase 06.1)

Derived from Phase 06.1 discuss-phase decisions D-01→D-17 (see `phases/06.1-…/06.1-CONTEXT.md`). This phase consolidates the ad-hoc wBA1-3 script collection into one region-agnostic, config-driven pipeline; its per-slice/per-region spine feeds CLASS-02, LABEL-01, AGG-01, EXP-03/04 downstream.

- [x] **PIPE-01**: The marker set is variable and config-declared — an explicit `name → channel → compartment` block declares markers, the detection/segmentation anchor channel is itself declared in config (default DAPI, never hardwired), Double+ is auto-derived only when ≥2 non-anchor markers are declared, and per-slice tables omit columns for absent markers (a TdT-only slice emits DAPI+/TdT+ only — no assumed Fos+/Double+) (D-01–D-04)
- [x] **PIPE-02**: The ad-hoc scripts consolidate to one canonical spine — the detect/classify split is kept (`run_braian_detection.groovy` + `02_detect_classify.groovy`), the duplicate `classify_markers.groovy` is retired (its logic already lives in `02`), and a single config-driven export emits both the per-cell TSV and the per-region table (folding in `export_region_dapi_reference.groovy` + `03_export_val01_metrics.groovy`) (D-05–D-07)
- [ ] **PIPE-03**: The export emits all atlas regions present on the slice (exclusion literals like `["DG-sg","VS"]` moved from source into config), every cell is assigned to exactly one smallest-area leaf (CR-01 rule) and parent rows are the SUM of descendant-leaf counts up the atlas tree — never an independent parent-ROI containment pass — with density reported as cells/mm² (region count ÷ region area_mm²) (D-08–D-11)
- [ ] **PIPE-04**: Each slice produces a self-contained per-region table, and rows are appended to a growing combined CSV in long/tidy format — one row per region×marker: `slice, config_tag, region, hemisphere, is_leaf, marker, class, count, density` — where absent markers produce no rows (no NA, aggregation-ready for BraiAnalyse/pandas) (D-12–D-13)
- [x] **PIPE-05**: Pipeline config (marker list, anchor, compartments, exclusions) lives in a new sidecar file separate from `BraiAn.yml` and is read by every groovy entry; each scriptable entry fail-loud asserts its preconditions (ABBA ROIs loaded, detections present, image channels match the declared markers) before doing work, guarding the human-in-the-loop GUI seams (D-14–D-15)
- [ ] **PIPE-06**: The pipeline is captured as a single operator-checklist `RUNBOOK.md` (czi→MIP → ABBA register → BraiAnDetect → classify → export → per-region table, each step marked GUI-vs-scriptable with exact commands + QuPath/ABBA click-paths and the marker-config block documented) backed by per-stage detail docs, and validated end-to-end on the incoming TdT-only slice set — a schema-correct, non-empty per-region table with correctly omitted Fos+/Double+ columns plus a spot bioplausibility sanity check (DAPI+ densities in the ~Phase-2 band) (D-16–D-17)

### Classification (continues CLASS-01 from v1.0)

- [ ] **CLASS-02**: Nucleus-anchored TdT+/Fos+/Double+ classification runs across all 5 sections over the LA/BA amygdala ROI, producing the per-region primary counts (same detection/colocalization rules as v1.0)

### Region Labeling (brain-wide correctness)

- [ ] **LABEL-01**: A brain-wide region-labeling validation harness confirms the CR-01 geometric smallest-area-leaf fix holds across all 5 sections and all regions — re-audited specifically on non-laminar amygdala (LA/BA), asserting zero cells leak into parent rollups (rollup acronyms taken verbatim from `04-REVIEW.md`)

### Area-Based Density Readout (generalizable, brain-wide-ready)

- [ ] **AREA-01**: A generalizable, region-parameterized area-based readout measures Fos+/TdT+ percent-area-above-threshold within a DAPI+ mask for compact-nuclei regions — additive/parallel to nucleus counts, written as disjoint measurement keys on the region annotation (never touching `PathClass`), reported as a fraction and never a per-cell count
- [ ] **AREA-02**: An explicit non-separability trigger rule governs when the area-based method applies (reserved for genuinely unsegmentable regions, not a general noise fallback), validated on DG granule layer as the in-section test case with a crosswalk against nucleus-based counts on overlapping tissue

### Section→Animal Aggregation

- [ ] **AGG-01**: Per-section region counts aggregate to a single animal-level table for wBA1-3 via BraiAnalyse (`SlicedBrain.from_qupath` → `AnimalBrain.from_slices`), with per-region section-coverage documented and aggregation math (sum/mean, missing-section handling) verified against the project stats conventions

### Export & Visualization (continues from v1.0 export work)

- [x] **EXP-02**: `03_export_val01_metrics.groovy` is fixed for multi-entry batch execution — per-entry output filenames, no TSV truncation across the 5 sections (blocking prerequisite for AGG-01)
- [ ] **EXP-03**: Per-cell atlas coordinates are persisted as Atlas_X/Y/Z columns in microns (CCFv3) via the proven `AtlasTools.getAtlasToPixelTransform` path with the mm→µm ×1000 conversion applied
- [ ] **EXP-04**: A brainrender 3D point-cloud figure renders wBA1-3's classified cells (colored by TdT+/Fos+/Double+) in CCFv3 micron space, confirming the exported coordinates land in the right anatomical location

## v2 Requirements

Deferred to a future milestone.

### Statistics

- **STAT-01**: Multi-animal group comparison (Welch's t, Hedges' g, multiple-comparison correction) — needs n>1 animal
- **STAT-02**: Chance-overlap statistical gate for above-chance double-positive coexpression, brain-wide

### Detection

- **DET-01**: Per-nucleus dense-region segmentation (as an alternative to the area-based readout) — GPU-costly, deferred

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-animal statistics / group testing | Single animal (wBA1-3) this milestone; no pseudoreplication — group tests need n>1 |
| Re-enabling unmasked elastix Affine+Spline in ABBA | Confirmed to degrade without a tissue mask (2026-06-23); only the masked prototype (REG-05) is trialed |
| Bumping QuPath (0.6.0) / elastix (5.2.0) versions | Extension-compatibility pins; research confirmed no bump needed |
| GPU/CUDA builds of any library | CPU-only box (Intel UHD 630) |
| Area-based method replacing nucleus-anchored counts | Area-based is additive/parallel only; nucleus-anchored remains the primary readout (hard project rule) |

## Traceability

Each requirement maps to exactly one phase. Phases continue from v1.0 (Phases 1-4); v1.1 spans Phases 5-10, plus inserted Phase 06.1 (pipeline generalization, PIPE-01…06).

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONV-01 | Phase 5 | Complete |
| CONV-02 | Phase 5 | Complete |
| EXP-02 | Phase 5 | Complete |
| REG-03 | Phase 6 | Complete |
| REG-04 | Phase 6 | Complete |
| REG-05 | Phase 6 | Complete |
| PIPE-01 | Phase 06.1 | Complete |
| PIPE-02 | Phase 06.1 | Complete |
| PIPE-03 | Phase 06.1 | Pending |
| PIPE-04 | Phase 06.1 | Pending |
| PIPE-05 | Phase 06.1 | Complete |
| PIPE-06 | Phase 06.1 | Pending |
| IMG-01 | Phase 7 | Pending |
| IMG-02 | Phase 7 | Pending |
| CLASS-02 | Phase 8 | Pending |
| LABEL-01 | Phase 8 | Pending |
| AREA-01 | Phase 9 | Pending |
| AREA-02 | Phase 9 | Pending |
| AGG-01 | Phase 10 | Pending |
| EXP-03 | Phase 10 | Pending |
| EXP-04 | Phase 10 | Pending |

**Coverage:**

- v1.1 requirements: 21 total
- Mapped to phases: 21 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-17*
*Last updated: 2026-07-23 — Phase 06.1 requirements minted (PIPE-01…06 from decisions D-01→D-17), 21/21 coverage*
