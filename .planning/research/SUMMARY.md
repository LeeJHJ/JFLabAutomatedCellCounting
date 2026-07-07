# Project Research Summary

**Project:** TRAP2 Section Pipeline — M3 Hippocampus Single-Section Validation Run
**Domain:** Fluorescence microscopy cell detection, atlas registration, and colocalization analysis
**Researched:** 2026-06-30
**Confidence:** MEDIUM

## Executive Summary

This project uses QuPath 0.6.0 + BraiAnDetect 1.1.0 + ABBA 0.4.0 to count TdTomato+ (encoding engram), Fos+ (recall IEG), and Double+ (reactivated engram) cells in 20x Airyscan MIP images of mouse vibratome sections, registered to the Allen CCFv3 atlas. The validated expert workflow is: ABBA registration (Fiji GUI, DeepSlice + manual angle only, no elastix Affine/Spline) → ROI loading → DAPI nuclear segmentation with cytoplasmic expansion for TdTomato → per-channel classifiers → BraiAn region-level export → braian Python aggregation. The current immediate goal is a single-section parameter validation run on the M3 hippocampus section before scaling to the full series.

The recommended approach is strictly sequential and cannot be parallelized: ABBA registration and ROI loading must precede detection; detection parameters must be locked on one section before batch; classifiers must be created and verified before export; exports must be verified against known coordinate ranges before downstream stats. The architecture is one QuPath project per animal with all sections as entries, driven by a single BraiAn.yml at the project root. All numeric parameters belong in BraiAn.yml, not hardcoded in scripts, so that changing a parameter propagates automatically to all sections.

The dominant risk class is **silent errors that produce plausible-but-wrong counts**: TdTomato measured in the nuclear compartment instead of the cytoplasmic ring, Fos measured in cytoplasm instead of nucleus, channel name mismatches that cause classifiers to apply to no cells, duplicate ABBA ROI loads that double-count regions, and atlas coordinate unit mismatch (mm vs µm) corrupting brainrender positions. None of these produce loud failures — they produce quiet wrong numbers. Mitigation requires explicit verification checkpoints after every step, comparing results against biologically plausible ranges from published TRAP2 literature.

## Key Findings

### Recommended Stack

The installed stack is already correct and pinned. Channel names in the current M3 project are `AF568-T2` (TdTomato, cytosolic), `AF488-T3` (Fos, nuclear), `DAPI-T4` — these must be used verbatim in BraiAn.yml.

**Core technologies:**
- **QuPath 0.6.0**: Image analysis host — detection, classification, atlas annotation management, batch scripting
- **BraiAnDetect 1.1.0**: Detection orchestration — reads BraiAn.yml, runs WatershedCellDetection, applies classifiers, computes OverlappingDetections (Double+), exports region TSV
- **ABBA 0.4.0 (Fiji)**: Atlas registration (GUI only) — writes ABBA-Transform-*.json and ABBA-RoiSet-*.zip per section entry; prerequisite for all downstream steps
- **braian Python (conda env: braian)**: Cross-section aggregation and BraiAnalyse stats
- **brainrender (conda env: brainrender)**: 3D CCFv3 point cloud — deferred until full series complete

### Expected Features

**Must have (table stakes):**
- Per-region cell counts (TdT+, Fos+, Double+, Negative) and region area
- Cell density (cells/mm²) per region per class — absolute counts uninformative across unequal regions
- CCFv3 micron coordinates (Atlas_X/Y/Z) per detected cell
- Atlas region label and hemisphere (L/R) per cell
- Classifier threshold records (TdT, Fos) as locked JSON files
- BraiAnDetect parameter record (sigma, min/max area, threshold, expansion radius)
- Visual detection overlay QC on one representative region before any batch export
- Excluded region record (principled, a priori)

**Should have (differentiators):**
- Channel intensity histograms per classifier
- Nucleus measurement table (raw, before classification) — enables post-hoc threshold adjustment
- Cytoplasmic ring expansion validation image (especially for dense DG)
- Registration overlay image

**Defer (not needed for single-section validation):**
- Group-level statistics, brainrender 3D visualization, BraiAnalyse cross-animal aggregation

**Anti-features (must not produce):**
- Section-level p-values (pseudoreplication)
- Absolute counts reported cross-region without area normalization
- Proximity-based colocalization instead of nucleus-anchored containment
- Elastix Affine+Spline registration (confirmed to degrade result without tissue mask)
- Pixel-space coordinate export

### Architecture Approach

One QuPath project per animal, all sections as entries, three Groovy scripts run in strict order via "Run for project", BraiAn.yml as single parameter source of truth.

**Major components:**
1. **ABBA (Fiji GUI)** — registers each section; outputs ABBA-Transform + ABBA-RoiSet per entry; GUI-only
2. **01_load_abba_rois.groovy** — loads warped atlas annotations; prerequisite for detection
3. **BraiAn.yml** — parameter lock artifact; all numeric detection parameters
4. **02_detect_classify.groovy** — WatershedCellDetection + cytoplasmic expansion + classifiers + OverlappingDetections + export
5. **03_export_cells.groovy** — MeasurementExporter with calibrated micron centroids
6. **braian Python (BraiAnalyse)** — animal-level aggregation and multi-region statistics

### Critical Pitfalls

1. **TdTomato classified using nuclear compartment instead of cytoplasmic** — verify classifier JSON `feature` field reads `Cytoplasm: AF568-T2 mean`; requires `cellExpansionMicrons > 0`
2. **Fos classified using cytoplasmic compartment instead of nuclear** — verify `Fos_classifier.json` feature field reads `Nucleus: AF488-T3 mean`
3. **Channel name mismatch between OME-TIFF and classifier** — classifiers silently apply to no cells; always pass `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` consistently to czi_mip.py
4. **Duplicate ABBA ROI loads corrupt per-region counts** — always `clearAllObjects()` before `loadWarpedAtlasAnnotations`
5. **Atlas coordinate units mismatch (mm vs µm)** — ABBA outputs mm; brainrender expects µm; verify Atlas_X range spans ~5,000–10,000 for hippocampal section

## Implications for Roadmap

### Phase 1: Atlas Registration and ROI Loading (GUI + Groovy)
**Rationale:** ABBA-Transform and ABBA-RoiSet files must exist before any detection script can run. Mechanically required — not optional.
**Delivers:** Atlas annotation hierarchy in QuPath; verified registration overlay; `01_load_abba_rois.groovy` written and tested
**Avoids:** Duplicate ROI loading (Pitfall 3), cells detected outside Root annotation (Pitfall 4), ABBA-Transform filename mismatch

### Phase 2: Detection Parameter Tuning on One Section (GUI + BraiAn.yml authoring)
**Rationale:** Batch detection with un-tuned parameters wastes hours of CPU time (10–30 min/section on i9-9900K). Must lock parameters before batch.
**Delivers:** Locked BraiAn.yml; verified TdT_classifier.json (`Cytoplasm:`); verified Fos_classifier.json (`Nucleus:`); overlay QC passed; ring expansion validated in dense DG; parameter lock record written
**Avoids:** Classifier compartment and segmentation errors

### Phase 3: Batch Script Authoring and Single-Section End-to-End Test (Scriptable)
**Rationale:** Test the three Groovy scripts end-to-end on the single M3 section before trusting for batch. Use canonical BraiAn prebaked script as template.
**Delivers:** `results/<imageName>_regions.tsv`; Atlas_X/Y/Z coordinate range verified; pixel calibration confirmed; per-region count table for hippocampal subfields
**Avoids:** Coordinate unit mismatch, pixel calibration errors, transform filename errors

### Phase 4: Biological Plausibility Validation and Parameter Lock Finalization
**Rationale:** "Detection ran without errors" is not the same as "detection is biologically correct." Silent errors require numerical sanity checks against literature ranges.
**Delivers:** Written validation: DAPI nuclei/mm² vs expected (500–2,000/mm²); Double+ % of TdT+ (expect 10–40%); nucleus area distribution peak (50–150 µm²); Fos+ rate on negative-control section (~1–3%)
**Avoids:** Ring contamination overcounting, proximity colocalization errors

### Phase 5: Full Series Batch Execution (Scriptable)
**Rationale:** Only after parameter lock is validated does batch begin. Monitor for Fos threshold drift across sections.
**Delivers:** `*_regions.tsv` for every section; `cells_all_sections.tsv` with micron coordinates; Fos+ rate vs section-position plot
**Avoids:** Fixed threshold failing on dim/bright sections, pseudoreplication

### Phase 6: BraiAnalyse Aggregation (Python, braian conda env)
**Rationale:** Deferred until full series complete. Aggregate to animal level — sections are not independent.
**Delivers:** Animal-level density tables; Welch's t-test + Hedges' g; multiple-comparison correction; brainrender 3D point cloud

### Phase Ordering Rationale
- ABBA before detection: mechanically required (no ROI files = no atlas labels = re-detection required)
- Tuning before batch: economic necessity (CPU-only, hours per re-run)
- Single-section test before batch: catch script errors cheaply
- Plausibility check before lock: only defense against silent misclassification errors
- Aggregation deferred: sections are not independent statistical units

### Research Flags

Phases needing extra attention during planning:
- **Phase 2:** Exact `cellExpansionMicrons` needs empirical tuning on DG (densest region); literature seed 5 µm may need adjustment
- **Phase 3:** Exact BraiAnDetect API method signatures for v1.1.0 need verification against installed jar — use canonical prebaked script to be safe
- **Phase 5:** Fos threshold generalizability across batch is empirical; background-relative threshold approach may be needed

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Versions verified on-disk; channel names verified from live project.qpproj; API calls cross-checked against QuPath 0.6.0 Javadoc |
| Features | MEDIUM | Table stakes and anti-features from primary sources; exact TSV column schema inferred from installed braian Python source |
| Architecture | MEDIUM | Core patterns cross-checked across official QuPath, ABBA, BraiAn docs; BraiAnDetect internal method signatures not verified against installed jar |
| Pitfalls | MEDIUM | Cross-checked against official docs, PMC8592694, bioRxiv 2024.09.16.611953, image.sc forum Dec 2025 TRAP2 thread |

**Overall confidence:** MEDIUM

### Gaps to Address During Planning

- **Fos threshold generalizability:** Flag in Phase 5 — plot Fos+ rate vs. section position immediately after batch to detect drift
- **BraiAnDetect API surface v1.1.0:** Use canonical prebaked script; avoid manual API construction until method signatures confirmed
- **cellExpansionMicrons optimal value:** Tune visually on DG; literature seed 5 µm, document final value in parameter lock record
- **Atlas coordinate units confirmation:** Print Atlas_X range for a known hippocampal cell after Phase 3 export; expect 5,000–10,000 µm; if 5–10, multiply by 1000

## Sources

### Primary (HIGH confidence)
- Project CLAUDE.md (on-disk, first-party) — machine constraints, installed versions, confirmed workflow decisions
- `project.qpproj` files in `/home/jflab/Analysis/` — actual channel names, pixel calibration
- braian Python library source (`/home/jflab/miniforge3/envs/braian/`) — TSV column schema, atlas name expectations

### Secondary (MEDIUM confidence)
- [BraiAn for QuPath documentation](https://silvalab.codeberg.page/BraiAn/braian-qupath/)
- [ABBA documentation — QuPath analysis](https://abba-documentation.readthedocs.io/en/latest/tutorial/4_qupath_analysis.html)
- [bioRxiv 2024.09.16.611953](https://www.biorxiv.org/content/10.1101/2024.09.16.611953v2.full) — TRAP2 parameter seeds
- [QuPath 0.6.0 Javadoc](https://qupath.github.io/javadoc/docs/qupath/lib/scripting/QP.html)
- [PMC8592694 — c-Fos counting accuracy](https://pmc.ncbi.nlm.nih.gov/articles/PMC8592694/)
- [image.sc forum — TRAP2 TdTomato/Fos overcounting, Dec 2025](https://forum.image.sc/t/qupath-cell-detection-issues-misalignment-between-dapi-and-cytosolic-markers-tdtomato-c-fos-leading-to-overcounting/118276)
- [NicoKiaru/BIOP Gist — cell detection after ABBA](https://gist.github.com/NicoKiaru/f45f56e3ff2d1fb708821c110fbdee62)

---
*Research completed: 2026-06-30*
*Ready for roadmap: yes*
