# Feature Landscape: TRAP2 Section Pipeline — Single-Section Validation Run

**Domain:** TRAP2 vibratome section — TdTomato/Fos colocalization, Allen CCFv3 atlas registration
**Researched:** 2026-06-30
**Overall confidence:** MEDIUM (primary sources: BraiAn docs, ABBA docs, TRAP2 literature; exact column schemas not published but inferable from architecture)

---

## Table Stakes

Features any TRAP2 researcher expects. Missing = run cannot be trusted or published.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-region cell counts (TdT+, Fos+, Double+, Negative) | Core deliverable — all TRAP2 papers report counts by atlas region | Low (QuPath summary.json + BraiAn saveResults()) | `summary.json` written by QuPath; BraiAn `AtlasManager.saveResults()` exports per-region totals |
| Atlas region area (mm²) per section | Required to compute density; counts alone are uninformative across regions of unequal size | Low | ABBA ROIs carry polygon geometry; QuPath annotation area measurement provides this |
| Cell density (cells/mm²) per region per class | Standard reporting unit in literature; allows cross-region and cross-animal comparison | Low (calculation from counts + area) | Compute from above two; density is what BraiAnalyse expects for aggregation |
| Cell centroid coordinates in microns (CCFv3 space) | Required for brainrender point cloud; required for BraiAnalyse cross-section aggregation | Low (ABBA transform applies Atlas_X/Y/Z) | Export Atlas_X, Atlas_Y, Atlas_Z from QuPath after ABBA transform is loaded; pixel coordinates alone are useless |
| Atlas region label per cell | Associates each detected cell to an anatomical structure | Low (ABBA ROIs → annotation containment) | Each QuPath PathObject inherits parent annotation label from the loaded ABBA ROI set |
| Hemisphere side (Left/Right) per cell/region | Standard in IEG/engram literature; engram cells show lateralized patterns | Low (ABBA exports L/R split) | ABBA exports atlas ROIs with L/R suffixes; region containment in QuPath assigns hemisphere |
| Classifier threshold record (TdT+, Fos+) | Reproducibility — parameters must be locked before scaling to series | Low (JSON files already saved) | `classifiers/object_classifiers/TdT_classifier.json` and `Fos_Classifier.json`; must be reviewed and finalized this run |
| Detection parameter record (sigma, min/max nucleus area, cytoplasmic expansion radius) | Required to reproduce detection on subsequent sections and animals | Low (document from BraiAnDetect UI) | Seed from bioRxiv 2024.09.16.611953 / F1000Research 2026 TRAP2 paper, then document final tuned values |
| Visual detection overlay on one representative section | Primary QC check — confirms nuclei are correctly segmented, rings are not invading neighbors | Low (QuPath viewer) | Must be done before any batch export; oversegmented/undersegmented nuclei are visible immediately |
| Excluded region record | Documents damaged tissue sections removed from counts | Low (BraiAn saveExcludedRegions()) | Principled exclusion must be documented; `AtlasManager.saveExcludedRegions()` writes this file |

---

## Differentiators

Outputs that add specific value for this experiment beyond the minimum expected. Not required for a valid single-section run, but high value for locking parameters or enabling downstream work.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Channel intensity histograms per classifier (TdT, Fos) | Directly shows where the threshold sits relative to the population distribution; makes threshold choice defensible | Medium | BraiAnDetect has built-in channel histogram; screenshot and record threshold intercept relative to histogram peaks |
| Nucleus measurement table (raw, before classification) | Enables post-hoc threshold adjustment without rerunning detection; diagnostic for over/undersegmentation | Medium | Export all detected nuclei with Nucleus mean intensity (DAPI, Fos, TdTomato channels) + Cytoplasm mean (TdTomato) + Area; one row per cell |
| Split-region count table (parent + children regions) | Shows whether activity is distributed uniformly across a region or concentrated in a subfield | Medium | ABBA ROI hierarchy supports this; BraiAn can aggregate up the ontology tree |
| Detection efficiency estimate: DAPI nuclei / expected cell density | Sanity check against known cell density of the imaged region (e.g., CA1 ~500-1500 cells/mm² in mouse at 20x) | Low | Divide total DAPI-detected nuclei by section area; compare to published stereology values for hippocampal subfields |
| Cytoplasmic ring expansion validation image | Confirms ring does not bleed into adjacent nuclei; critical for TdTomato which is cytosolic | Low (screenshot from QuPath viewer) | Spot-check 10-20 cells at high zoom; rings should not overlap adjacent nuclei |
| Registration overlay image | Shows atlas region boundaries drawn over the section image; primary check that DeepSlice + manual angle was correct | Low (screenshot from QuPath viewer) | Required before trusting any region labels; misaligned overlay means all counts are wrong |
| Per-section MIP quality flag | Records focus quality, z-plane coverage adequacy, any stitching artefacts in the MIP | Low (manual inspection, written note) | Relevant for deciding whether Z-stack depth was sufficient; informs future acquisition decisions |
| Pixel calibration verification record | Confirms QuPath is using the correct µm/pixel from OME-XML; prevents coordinate errors | Low (compare QuPath pixel calibration vs ome-xml PhysicalSizeX) | One-time check: `pixelCalibration` in `server.json` must match `PhysicalSizeX` in OME-TIFF header |

---

## Anti-Features

Outputs that seem useful but must NOT be produced from a single-section run, or that violate correctness rules.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Group-level statistics from this run | Only one animal, one session — no basis for any group comparison | Reserve BraiAnalyse group stats for after full series with N>=3 animals per group |
| Section-level p-values or significance tests | Sections are not independent replicates; pseudoreplication inflates n | Aggregate to animal level first; sections are replicates within animal, not between animals |
| Absolute cell counts (not density) reported cross-region | Regions differ in size; CA1 has more cells than DG not because it is more active but because it is larger | Always normalize to area: cells/mm² |
| Proximity-based colocalization (overlap or distance thresholds) | TdTomato is cytosolic, Fos is nuclear; proximity heuristics over-count TdT+ and mis-classify double+ | Nucleus-anchored colocalization only: nucleus must contain the marker centroid; cytoplasmic ring for TdTomato, nuclear compartment for Fos |
| Elastix Affine+Spline registration output | Without a tissue mask, elastix degrades the result (confirmed 2026-06-23); background pixels dominate optimization | DeepSlice + manual angle only; no Affine/Spline step |
| Pixel-space coordinate export | Pixel coordinates at 20x/0.8 (~0.69 µm/px) land cells in entirely wrong CCFv3 atlas positions | Always export Atlas_X/Y/Z from ABBA transform, verified against µm calibration |
| Cellpose/StarDist detection on this machine | No CUDA; GPU-accelerated model inference is slow or unavailable on Intel UHD 630 | BraiAnDetect built-in QuPath DAPI segmentation (watershed-based, CPU-native) |
| Per-Z-plane cell counts (before MIP) | The pipeline operates on MIP images; counting on individual Z-planes produces redundant/inflated counts | Count only on the MIP; Z-stack exists only to construct the MIP |
| Cross-section normalization without section thickness correction | If section thickness varies, raw density (cells/mm²) is not comparable across sections | For this single-section validation, flag and defer; full series will need consistent section thickness |

---

## Feature Dependencies

```
DAPI nuclear segmentation
    → cytoplasmic expansion ring (TdTomato measurement)
    → TdT+ classifier (threshold on cytoplasmic mean intensity)
    → Fos+ classifier (threshold on nuclear mean intensity)
    → Double+ logic (nucleus is both TdT+ and Fos+)
    → Per-cell atlas region label (from ABBA ROI containment)
    → Per-region count table (aggregate cells by atlas label)
    → Region area from ABBA ROI geometry
    → Cell density per region (count / area)
    → CCFv3 micron coordinates (Atlas_X/Y/Z from ABBA transform)
    → brainrender point cloud (future, deferred)
    → BraiAnalyse aggregation (deferred until series complete)

Atlas registration (DeepSlice + manual angle, no Affine/Spline)
    → ABBA-Transform-*.json (maps pixels to CCFv3 microns)
    → ABBA-RoiSet-*.zip (region polygons in image space)
    → Both required before any cell detection can be region-labeled
```

---

## Single-Section Validation Run: What Must Be Checked

These are the specific checks that confirm the run is biologically plausible and detection is trustworthy before locking parameters for the series.

### Registration quality (must pass before detection)
- Atlas region boundaries visibly fit tissue boundaries in QuPath viewer (hippocampal subfields CA1, CA3, DG, SUB are where they should be at the expected bregma level)
- Left/right hemisphere split is correct (not flipped)
- Atlas_X/Y/Z coordinates for a known landmark cell fall within the expected CCFv3 bounding box for that structure

### Nuclear segmentation quality
- Total DAPI-detected nuclei / section area is in the plausible range for the imaged region (~500-2000 cells/mm² for mouse hippocampal subfields at 20x; much higher values indicate oversegmentation of debris or background, much lower indicate missed nuclei)
- No systematic false splits visible on zoomed overlay (one nucleus detected as two)
- No systematic merges visible (two adjacent nuclei detected as one)
- Nucleus area distribution is unimodal with a reasonable peak (mouse cortical/hippocampal neurons ~50-150 µm²; if peak is below 20 µm² the threshold is catching debris)

### Cytoplasmic ring validation (TdTomato)
- Ring expansion does not bleed into adjacent nuclei at typical cell densities in DG (dense packing)
- TdTomato mean in cytoplasmic ring is systematically higher in visually-red cells than in visually-negative cells (sanity check on channel assignment: channel must be TdTomato-AF568, not Fos-AF488)
- A clearly TdT+ cell (bright cytosolic red) scores above threshold; a clearly negative cell scores below (visual spot-check 10-20 cells)

### Fos classifier (nuclear)
- Fos mean intensity is measured in the nuclear compartment, not the cytoplasmic ring
- A clearly Fos+ cell (bright nuclear green) scores above threshold; a negative cell scores below
- Confirm channel is Fos-AF488 (Ch1), not TdTomato-AF568 (Ch2) — channel order confusion is the documented failure mode for this pipeline

### Double+ logic
- Double+ cells are a subset of TdT+ cells that are also Fos+ (encoding AND recall)
- Double+ % of TdT+ cells: plausible range for hippocampal engram reactivation is roughly 10-40% of TdT+ cells; near 0% suggests classifier is too strict or recall was not effective; near 100% suggests a threshold error
- Visually confirm at least one double+ cell looks correct in overlay (bright cytosolic red + bright nuclear green in the same DAPI nucleus)

### Region labeling
- At least the major hippocampal subfields (CA1, CA3, DG, SUB) are present as distinct annotation regions
- No cells land in "root" or "undefined" region (indicates ABBA ROIs did not fully tile the section; small gaps at region boundaries are acceptable)
- Hemisphere L/R assignment is anatomically correct for each subfield

### Parameter lock record
Before accepting this run as the reference for the series, write down:
- BraiAnDetect: sigma (Gaussian smoothing), min nucleus area (µm²), max nucleus area (µm²), threshold (intensity), cytoplasmic expansion radius (µm)
- TdT classifier: measurement name (must be cytoplasmic compartment), threshold value, class labels
- Fos classifier: measurement name (must be nuclear compartment), threshold value, class labels
- Section used for tuning (image name, bregma level, date)

---

## MVP for the Single-Section Validation Run

Produce in this order (each depends on the previous):

1. Atlas registration overlay passes visual QC (region boundaries fit tissue)
2. DAPI nuclear segmentation with cytoplasmic ring on one representative region (e.g., CA1)
3. TdT+ and Fos+ classifiers applied; Double+ cells identified
4. Per-region count table: TdT+, Fos+, Double+, Negative, Total nuclei, Region area (mm²), Density (cells/mm²) — for each hippocampal subfield present in this section
5. CCFv3 micron coordinates (Atlas_X/Y/Z) exported for all detected cells with their class label
6. Detection parameter record written (all BraiAnDetect settings, classifier thresholds)
7. Excluded regions record (any damaged tissue flagged)

Defer: brainrender visualization, BraiAnalyse stats, cross-animal comparison — all require full series.

---

## Sources

- [ABBA+BraiAn Cell Reports 2025 (ABBA+BraiAn integrated suite)](https://www.cell.com/cell-reports/fulltext/S2211-1247(25)00647-3) — MEDIUM confidence (paywall, abstract only)
- [BraiAn for QuPath documentation](https://silvalab.codeberg.page/BraiAn/braian-qupath/) — MEDIUM confidence (official docs)
- [BraiAnalyse Python library documentation](https://silvalab.codeberg.page/BraiAn/braian-python/) — MEDIUM confidence (official docs)
- [ABBA QuPath analysis tutorial](https://abba-documentation.readthedocs.io/en/latest/tutorial/4_qupath_analysis.html) — MEDIUM confidence (official docs)
- [bioRxiv 2024.09.16.611953 — BraiAn TRAP2 workflow paper](https://www.biorxiv.org/content/10.1101/2024.09.16.611953v2.full) — MEDIUM confidence (preprint, now published as F1000Research 2026)
- [Hippocampal engram segregation study (PMC9512908)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9512908/) — MEDIUM confidence (peer-reviewed)
- [ABBA-QuPath post-processing scripts](https://github.com/bmi-lsym/ABBA-QuPath-post_processing) — MEDIUM confidence (community scripts)
- [QuPath cell detection documentation v0.6.0](https://qupath.readthedocs.io/en/latest/docs/tutorials/cell_detection.html) — MEDIUM confidence (official docs)
- Project CLAUDE.md and ARCHITECTURE.md (on-disk, first-party) — HIGH confidence
