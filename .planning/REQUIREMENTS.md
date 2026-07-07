# Requirements: M3 Hippocampus Section Pipeline — First Run

**Defined:** 2026-06-30
**Core Value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region for M3 hippocampus, with locked detection parameters and imaging optimization notes ready for the full series.

## v1 Requirements

### Registration

- [x] **REG-01**: M3 hippocampus sections registered in ABBA (Fiji GUI) — DeepSlice → manual angle → export; ABBA-Transform-*.json + ABBA-RoiSet-*.zip written per entry
- [x] **REG-02**: Registration overlay QC image produced — atlas region boundaries visually aligned to tissue before proceeding to detection

### Scripting

- [x] **SCRI-01**: `01_load_abba_rois.groovy` written and tested — calls `clearAllObjects()` then `loadWarpedAtlasAnnotations`; runs cleanly on M3 QuPath project via "Run for project"
- [ ] **SCRI-02**: `BraiAn.yml` authored at project root — contains locked sigma, min/max area, threshold (histogram-relative), and `cellExpansionMicrons > 0` for TdTomato channel (seed: 5 µm); channel names match project (`AF568-T2`, `AF488-T3`, `DAPI-T4`)
- [ ] **SCRI-03**: `02_detect_classify.groovy` written and tested on one section — runs WatershedCellDetection, cytoplasmic expansion, TdT and Fos classifiers, OverlappingDetections (Double+) via BraiAnDetect; produces `data.qpdata` with classified cells

### Classifiers

- [ ] **CLASS-01**: Fos classifier verified: `Fos_classifier.json` feature field reads `Nucleus: AF488-T3 mean` (nuclear compartment only — not cytoplasmic)

### Validation

- [ ] **VAL-01**: Bioplausibility check passed and documented: Double+ is 10–40% of TdT+; DAPI nuclei density 500–2,000/mm²; nucleus area distribution peaks 50–150 µm²; if a negative-control region is available, Fos+ rate ≈1–3%

### Imaging Optimization Notes

- [ ] **OPT-01**: Z-plane count audit documented — how many Z-planes were acquired vs. the minimum needed for a good MIP at 20x Airyscan; target recommendation written for next imaging session
- [ ] **OPT-02**: Per-section file size recorded (CZI raw + MIP OME-TIFF); MIP-immediately vs. store-raw-Z tradeoff assessed
- [ ] **OPT-03**: Resolution assessment written — whether 20x Airyscan is required throughout or lower-power tiling would suffice for survey regions; note which hippocampal subfields actually require Airyscan resolution

## v2 Requirements

### Classifiers

- **CLASS-02**: TdT classifier verified: `TdT_classifier.json` feature field reads `Cytoplasm: AF568-T2 mean`; cytoplasmic ring confirmed > 0 µm and not bleeding into adjacent nuclei (visual QC on dense DG)

### Export

- **EXP-01**: `03_export_cells.groovy` written — MeasurementExporter with calibrated micron centroids; Atlas_X/Y/Z range verified in µm (5,000–10,000 for hippocampus)
- **EXP-02**: Per-region TSV exported — TdT+/Fos+/Double+/Negative counts + area mm² + cells/mm² per atlas region + hemisphere
- **EXP-03**: Atlas coordinate unit confirmed — Atlas_X in µm not mm (multiply by 1000 before brainrender if ABBA outputs mm)

### Full Series

- **SERIES-01**: Full batch detection run on all M3 sections — all entries processed with locked BraiAn.yml via "Run for project"
- **SERIES-02**: Fos+ rate vs. section-position plot — detect threshold drift across sections; flag outliers before stats

### Stats & Visualization

- **STATS-01**: BraiAnalyse aggregation — animal-level density tables, Welch's t-test + Hedges' g, multiple-comparison correction (deferred: needs full series)
- **VIZ-01**: brainrender 3D point cloud of classified cells in Allen CCFv3 (deferred: after stats complete)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Elastix Affine+Spline registration | Confirmed to degrade result without tissue mask (2026-06-23); DeepSlice + manual angle only |
| Section-level p-values or group statistics | Sections are not independent; pseudoreplication; aggregate to animal level first |
| Absolute counts without area normalization | Uninformative across unequal-area regions; always report cells/mm² |
| Proximity/overlap-based colocalization | Must be nucleus-anchored containment only |
| Pixel-space coordinate export | CCFv3 is in microns; pixel export produces wrong atlas positions |
| Cellpose/StarDist detection | BraiAnDetect preferred for CPU speed and consistency with BIOP workflow |
| ZEN installation on this machine | Airyscan processing stays on Windows acquisition PC |
| Multi-animal group comparison | Needs >1 animal; this is a single-animal validation run |
| brainrender 3D visualization (v1) | Deferred until export and stats are complete |

## Traceability

*Updated by roadmapper — 2026-07-01.*

| Requirement | Phase | Status |
|-------------|-------|--------|
| REG-01 | Phase 1 | Complete |
| REG-02 | Phase 1 | Complete |
| SCRI-01 | Phase 1 | Complete |
| SCRI-02 | Phase 2 | Pending |
| CLASS-01 | Phase 2 | Pending |
| SCRI-03 | Phase 3 | Pending |
| VAL-01 | Phase 4 | Pending |
| OPT-01 | Phase 4 | Pending |
| OPT-02 | Phase 4 | Pending |
| OPT-03 | Phase 4 | Pending |

**Coverage:**

- v1 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0 (coverage complete)

---
*Requirements defined: 2026-06-30*
*Last updated: 2026-07-01 — traceability updated after roadmap creation*
