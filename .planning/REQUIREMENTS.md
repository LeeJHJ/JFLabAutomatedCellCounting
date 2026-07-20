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

- [ ] **REG-03**: DeepSlice batch `predict()` + angle propagation registers the 5-section series with materially less manual effort than per-section from scratch
- [ ] **REG-04**: A reduced-landmark BigWarp workflow with a documented per-section effort target (middle ground vs the v1.0 5–15 min manual pass), applied across all 5 sections
- [x] **REG-05**: An experimental masked-elastix prototype (`crop_to_tissue.py` DAPI mask → elastix Affine/Spline outside ABBA's GUI) is trialed on one section and compared to DeepSlice-only on fit quality + time; kept only if it demonstrably wins (a priori accept/reject rule)

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

Each requirement maps to exactly one phase. Phases continue from v1.0 (Phases 1-4); v1.1 spans Phases 5-10.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONV-01 | Phase 5 | Complete |
| CONV-02 | Phase 5 | Complete |
| EXP-02 | Phase 5 | Complete |
| REG-03 | Phase 6 | Pending |
| REG-04 | Phase 6 | Pending |
| REG-05 | Phase 6 | Complete |
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

- v1.1 requirements: 15 total
- Mapped to phases: 15 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-17*
*Last updated: 2026-07-17 after roadmap creation (Phases 5-10 mapped, 15/15 coverage)*
