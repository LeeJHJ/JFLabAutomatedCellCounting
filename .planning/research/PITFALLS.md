# Domain Pitfalls: TRAP2 Section Pipeline

**Domain:** TRAP2 vibratome section cell counting — TdTomato+/Fos+/Double+ colocalization with QuPath + ABBA + BraiAn
**Researched:** 2026-06-30
**Confidence:** MEDIUM (cross-checked against official ABBA documentation, BraiAn documentation, QuPath documentation, peer-reviewed c-Fos counting paper PMC8592694, and bioRxiv 2024.09.16.611953 TRAP2 pipeline preprint)

---

## Critical Pitfalls

Mistakes that produce plausible-looking but wrong cell counts — wrong enough to invalidate a paper.

---

### Pitfall 1: TdTomato measured in the nuclear compartment instead of the cytoplasmic compartment

**What goes wrong:** Running QuPath cell detection with cytoplasmic expansion enabled but then classifying TdTomato+ using a `Nucleus: TdTomato-AF568 mean` measurement instead of `Cytoplasm: TdTomato-AF568 mean`. TdTomato is a cytosolic protein — it is excluded from the nucleus. Nuclear mean values for TdTomato are systematically lower than cytoplasmic values and biologically meaningless. A classifier thresholded on `Nucleus: TdTomato-AF568 mean` will undercount TdT+ cells and may call different cells positive than the true set.

**Why it happens:** QuPath's cell detection dialog defaults to showing `Nucleus:` measurements. When saving a classifier via the GUI, it is easy to accept the default compartment without verifying. The classifier JSON stores the exact measurement string — a subtle mismatch between `Nucleus:` and `Cytoplasm:` is not flagged anywhere.

**Consequences:** Undercounting of TdT+ cells; wrong Double+ fraction; the effect is invisible in QuPath's summary view since counts look reasonable.

**Detection (observable in QuPath):**
- Open the classifier JSON (`classifiers/object_classifiers/TdT_classifier.json`) and verify the `feature` field reads `Cytoplasm: TdTomato-AF568 mean` (or the exact channel name). If it reads `Nucleus:`, the classifier is wrong.
- In QuPath Measurements table, compare `Nucleus: TdTomato-AF568 mean` vs `Cytoplasm: TdTomato-AF568 mean` for a cell that is visually TdT+. Cytoplasmic value should be substantially higher. If they are equal or nuclear > cytoplasmic, cell expansion may not have been enabled.

**Prevention:**
- When setting up the TdT classifier in QuPath, explicitly select `Cytoplasm:` in the compartment dropdown, not `Nucleus:`.
- Verify cell expansion is non-zero (e.g., 5–10 µm) in the detection parameters — `cellExpansionMicrons` must be > 0 or `Cytoplasm:` measurements will not be generated at all.
- After saving the classifier, open the JSON and confirm the `feature` field before running on the full series.
- **Fos is the opposite**: Fos is nuclear, so `Fos_Classifier.json` must reference `Nucleus: Fos-AF488 mean` (not `Cytoplasm:`).

**Phase:** Detection parameter tuning step, before applying to the series.

---

### Pitfall 2: Channel name mismatch between OME-TIFF metadata and classifier JSON

**What goes wrong:** The classifier JSON references a channel name (e.g., `Cytoplasm: TdTomato-AF568 mean`) that does not exactly match the channel name QuPath reads from the OME-TIFF metadata. QuPath silently fails to find the measurement column. Cells are classified as Negative or the result is undefined — not an error, just wrong counts.

**Why it happens:** `czi_mip.py` embeds channel names from the `--channels` argument into the OME-XML. QuPath reads those names and constructs measurement strings as `[Compartment]: [ChannelName] [stat]`. If the classifier was trained on a different import (e.g., with channel names "Ch1", "Ch2") or if the OME-XML was regenerated with different names, the measurement string no longer matches. QuPath does not warn when a classifier measurement is absent.

**Consequences:** All cells classified Negative (no TdT+ or Fos+ cells counted at all), or the classifier applies to an unrelated measurement that happens to have a similar name.

**Detection (observable in QuPath):**
- After running detection, open the Measurements table (any cell). Look for columns starting with `Cytoplasm:` and `Nucleus:`. The full column names shown there are the ground truth — they must match the strings in the classifier JSON character-for-character including spacing.
- If TdT+ count is zero on a section that visually shows TdT+ cells, this is the first thing to check.

**Prevention:**
- After importing the MIP OME-TIFF into QuPath, go to Image → Show image info and record the exact channel names as QuPath reads them.
- The `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` argument to `czi_mip.py` must match these names. They must be passed consistently for every section.
- When building classifiers, construct them on a section already imported with the canonical channel names. Never retrain on an ad-hoc import.

**Phase:** MIP conversion (channel naming lock-in), then detection setup.

---

### Pitfall 3: ABBA atlas ROIs loaded multiple times — duplicate annotations corrupt per-region counts

**What goes wrong:** Running `loadWarpedAtlasAnnotations` (via the ABBA extension menu or a Groovy script) more than once on the same QuPath image entry without first clearing existing annotations. The second load adds a second set of atlas region annotations on top of the first. QuPath's per-region counts will be wrong: cells may be double-counted (assigned to two overlapping copies of the same region), or region areas will be doubled.

**Why it happens:** Users may re-register a section in ABBA, re-export, and then re-load ROIs without realizing the old ones are still present. The ABBA extension's overwrite mode only works if the existing hierarchy is intact (all annotations still direct children of Root). If anything has been moved, the overwrite silently adds duplicates instead.

**Consequences:** Per-region cell counts are wrong in ways that are hard to detect — counts in affected regions may be 2× too high, or cells may be assigned to phantom region boundaries.

**Detection (observable in QuPath):**
- Before loading ROIs, check the Annotations panel. If you see a full tree of brain region annotations already present, do not load again without clearing.
- After loading, check whether any region appears twice in the annotation list. Duplicate "CA1", "DG" etc. are the signature of this error.

**Prevention:**
- Always run `clearAllObjects()` or `removeObjects(getAnnotationObjects(), false)` before calling `loadWarpedAtlasAnnotations`. The recommended script pattern is: `clearAllObjects(); AtlasTools.loadWarpedAtlasAnnotations(getCurrentImageData(), "acronym", true);`
- Never manually reclassify, rename, move, or delete atlas annotations after import — doing so breaks the hierarchy that the overwrite check relies on.
- Treat the atlas annotation tree as read-only once loaded.

**Phase:** Atlas ROI loading, each time re-registration is performed.

---

### Pitfall 4: Cells detected outside the Root annotation — not assigned to any atlas region

**What goes wrong:** Detection runs against a user-drawn rectangle or the full image instead of the Root atlas annotation. Detected cells land in QuPath's object hierarchy as children of the image root, not children of any atlas region annotation. The per-region `summary.json` shows zero cells in all regions, while the global cell count is non-zero. Or detection runs inside one leaf annotation only, missing cells in all other regions.

**Why it happens:** QuPath's cell detection runs within whatever annotation is currently selected. If the user runs detection manually with no annotation selected (or selects a specific region), cells are not parented to the atlas hierarchy. The ABBA+BIOP workflow requires detection to run with the Root annotation selected as the parent.

**Consequences:** All per-region counts are zero even though cells are detected. The summary JSON looks like detection was never run.

**Detection (observable in QuPath):**
- In the Objects panel, expand the hierarchy. Cells should appear as children of named atlas regions (e.g., CA1, DG, cortex). If all cells appear at the top level under the image (not under any annotation), the parent assignment is missing.
- After running detection, immediately check: `getDetectionObjects().size()` > 0 but all per-region annotation child counts == 0 → parent assignment failed.

**Prevention:**
- Use the BIOP/NicoKiaru reference script pattern: create a copy of the Root annotation (`PathObjectTools.transformObject(root, null, true)`), run detection inside it, then parent all detected cells back under Root and call `fireHierarchyUpdate()`. This ensures cells land under the atlas hierarchy.
- Alternatively: select the Root annotation before running BraiAnDetect, so detection inherits the correct parent.
- Verify per-region counts in the summary panel immediately after detection on the first section before proceeding to others.

**Phase:** Cell detection (every section).

---

### Pitfall 5: Cell expansion ring radius too large — TdTomato signal contaminated from neighboring cells

**What goes wrong:** Setting `cellExpansionMicrons` too large (e.g., 15 µm) in dense tissue causes the cytoplasmic ring of one nucleus to overlap with the ring of adjacent nuclei. QuPath's expansion stops at neighboring cell boundaries in theory, but in practice the cytoplasmic measurement for a TdT-negative cell picks up signal from an adjacent TdT-positive cell's cytoplasm. The TdT-negative cell is then classified as TdT+.

**Why it happens:** The watershed-based expansion expands until it hits another expansion, but in very dense hippocampal regions (e.g., DG granule layer), packing is so tight that the expansion immediately overlaps with neighbors before reaching a meaningful cytoplasmic area. Paradoxically, setting expansion too small fails to capture the TdTomato cytoplasmic signal at all.

**Consequences:** Overcounting of TdT+, inflating Double+ fraction. Effect is worse in dense regions (DG, CA layers) than sparse regions (cortex), creating a region-specific artifact.

**Detection (observable in QuPath):**
- In the cell overlay, zoom into a dense region (DG granule cell layer). If many cells that look DAPI-positive-only (no visible TdTomato halo) are showing as TdT+, the expansion is too large.
- Compare TdT+ rate in DG vs. cortex on the same section. If DG rate is implausibly high relative to cortex (opposite to the biology of encoding in hippocampus is expected, but implausible absolute numbers suggest artifact), suspect contamination.
- Use the `Cytoplasm: TdTomato-AF568 mean` measurement histogram to look for a bimodal distribution — if a clear valley separates positive from negative, threshold is working. If the distribution is flat or unimodal with a long tail, expansion may be contaminating.

**Prevention:**
- Tune `cellExpansionMicrons` on the hippocampal DG (densest region in the section) before declaring parameters locked.
- Starting parameters from bioRxiv 2024.09.16.611953: cytoplasmic expansion 5 µm (tuned on mouse brain vibratome sections). Do not exceed 10 µm without visual validation in dense tissue.
- Use BraiAnDetect's permissive-detect-then-classify strategy: err permissive on detection, strict on classifier threshold.

**Phase:** Detection parameter tuning.

---

### Pitfall 6: Fos+ classified on cytoplasmic signal instead of nuclear signal

**What goes wrong:** The Fos classifier is set to `Cytoplasm: Fos-AF488 mean` or `Cell: Fos-AF488 mean` instead of `Nucleus: Fos-AF488 mean`. Fos is an IEG transcription factor — it is nuclear. Cytoplasmic Fos signal is background. A cytoplasmic threshold for Fos will call many cells falsely positive in regions with moderate autofluorescence at 488 nm.

**Why it happens:** Mirror image of the TdTomato pitfall — accidentally selecting the wrong compartment when building the classifier. Also: if the anti-Fos antibody produces any cytoplasmic haze (nonspecific binding), using the Cell compartment will incorporate that haze.

**Consequences:** Overcounting Fos+ and Double+; effect is systematic across all sections and regions.

**Detection (observable in QuPath):**
- Open `Fos_Classifier.json` and confirm `feature` field reads `Nucleus: Fos-AF488 mean`.
- On a negative-control section (no recall stimulus), Fos+ count should be near background (1–3% of cells). If it is 10–30%, the classifier is measuring the wrong compartment or the threshold is too low.

**Prevention:**
- Set Fos classifier to `Nucleus:` compartment only. This is non-negotiable given the biology.
- Set TdT classifier to `Cytoplasm:` compartment only.
- Document the compartment setting explicitly in the parameter lock table before applying to the series.

**Phase:** Detection parameter tuning.

---

## Moderate Pitfalls

Mistakes that degrade counts but may not completely invalidate them.

---

### Pitfall 7: Fixed intensity threshold for Fos fails to generalize across sections

**What goes wrong:** A fixed-intensity Fos threshold (e.g., `Nucleus: Fos-AF488 mean > 150`) is set on one section and applied identically to all sections. Fos signal intensity varies across sections due to antibody penetration depth (the first and last sections in a batch typically show weaker labeling), section thickness variation, and photobleaching from prior Z-stack imaging. The same numerical threshold calls too few Fos+ on dim sections and too many on bright sections.

**Why it happens:** Single-threshold classifiers are the default QuPath approach and are easy to set up. Section-to-section intensity normalization is not automatic.

**Consequences:** Regional Fos+ counts are not comparable across sections from the same animal. This introduces a position-in-series artifact — sections cut early in the series show different counts than later sections.

**Detection (observable in QuPath):**
- After running the classifier on all sections, plot Fos+ count (or rate) vs. section position. A monotonic trend correlated with position in the batch is a red flag.
- Look at the `Nucleus: Fos-AF488 mean` histogram for two sections — one from the middle of the batch and one from the beginning. If the distributions are shifted by > 20% in mean intensity, the sections are not comparable at a fixed threshold.

**Prevention:**
- Use a relative threshold: after detection, compute the 95th percentile of `Nucleus: Fos-AF488 mean` across all Negative cells on each section, then set the Fos+ threshold as a multiple of that background value. This normalizes for section-to-section brightness.
- Or: tune the threshold on the dimmest acceptable section in the batch, so the threshold is conservative everywhere.
- Use the TRAP2 paper's approach (bioRxiv 2024.09.16.611953): validate parameter stability across a representative set of sections before locking.

**Phase:** Detection parameter tuning, series application.

---

### Pitfall 8: Atlas coordinate units mismatch (mm vs µm) between ABBA export and brainrender

**What goes wrong:** ABBA's Groovy export script writes `Atlas_X`, `Atlas_Y`, `Atlas_Z` in millimeters. brainrender's `allen_mouse` atlas expects coordinates in micrometers (CCFv3 native unit: 10 µm voxels, coordinates in µm). Passing ABBA mm coordinates directly to brainrender places all cells in a 1000× too-small cluster near the origin — cells appear outside the brain or in the wrong hemisphere.

**Why it happens:** The CCFv3 native resolution is 10 µm/voxel, but ABBA's Warpy transform operates in real-world millimeter space. The confusion is that both ABBA and brainrender reference "CCFv3" but with different scale conventions.

**Consequences:** All cell positions in brainrender are wrong by a factor of 1000. The visualization looks like a tiny cluster near one corner of the atlas. The bug is obvious once the 3D render is viewed but easy to miss if the render is not inspected carefully.

**Detection:**
- Render 10 cells in brainrender. If they cluster tightly in one corner of the atlas mesh rather than distributed across the hippocampus, the scale is wrong.
- Print the range of Atlas_X values from a section: should span ~5,000–10,000 µm for a hippocampal section. If values are 5–10 (mm), multiply by 1000.

**Prevention:**
- After ABBA coordinate export, verify the numerical range of Atlas_X/Y/Z. Values in the range 0–14 mm (whole brain AP span) indicate millimeters — multiply by 1000 before passing to brainrender.
- Document the scale factor in the export Groovy script as a comment.

**Phase:** Coordinate export, brainrender visualization.

---

### Pitfall 9: QuPath pixel calibration missing — centroid export in pixels instead of microns

**What goes wrong:** If the MIP OME-TIFF lacks a valid `PhysicalSizeX`/`PhysicalSizeY` in its OME-XML (or if QuPath fails to read it), the image is imported uncalibrated. QuPath then exports `Centroid X µm` = `Centroid X px` × 1 (no conversion). At 20x with 0.69 µm/px, all centroid coordinates are off by a factor of ~0.69 — cells are placed in the wrong spatial positions.

**Why it happens:** `czi_mip.py` hand-builds the OME-XML and embeds `PIXEL_SIZE_UM`. If the pixel size constant is wrong, or if a section is added to the QuPath project from a different source (e.g., a TIFF without OME metadata), the calibration is silently missing.

**Consequences:** Centroid coordinates are systematically wrong; within-region cell positions are off, affecting the ABBA coordinate transform quality and brainrender positions.

**Detection (observable in QuPath):**
- With the image open, check the pixel calibration display at the bottom of the QuPath window. It shows the pixel size in µm. If it reads "1 px" or is blank, calibration is missing.
- Or: open Image → Show image info → look for `Pixel width` in µm.
- Cross-check: the image scale bar should show plausible distances (~500 µm across a vibratome section).

**Prevention:**
- After importing every section into QuPath, immediately verify pixel calibration before running detection.
- `czi_mip.py` must embed the correct `PIXEL_SIZE_UM` for the objective used (20x Airyscan: 0.069 µm/px at the scan setting used — verify against ZEN metadata or measure a known structure).
- If calibration is missing, set it manually in QuPath: right-click the image entry → Set pixel size → enter µm value.

**Phase:** MIP conversion, QuPath import (per-section check).

---

### Pitfall 10: Double+ classification using proximity rather than nucleus-anchored containment

**What goes wrong:** Instead of requiring that both TdTomato centroid (in the cytoplasmic compartment) and Fos centroid (in the nuclear compartment) belong to the same detected nucleus, a proximity or overlap heuristic is used (e.g., "TdT+ and Fos+ cells within X µm of each other are counted as Double+"). This produces false Double+ when a TdT+ cell and a neighboring Fos+ cell are close but not colocalized.

**Why it happens:** Proximity-based colocalization is intuitively appealing and simple to implement. It is a standard approach in older ImageJ macros and may be suggested by naive implementations.

**Consequences:** Double+ (reactivated engram) fraction is inflated, especially in dense tissue where TdT+ and Fos+ cells are spatially close by chance. This directly affects the key biological claim of the paper.

**Detection (observable in QuPath):**
- Zoom into a region with both TdT+ and Fos+ cells. Visually confirm that cells marked Double+ have both signals within the same DAPI nucleus. If a Double+ cell shows only one signal, the colocalization logic is wrong.
- Run detection on a negative-control section. Double+ rate should be near 0 (only spontaneous Fos expression in the absence of recall; 1–2% is biological background). If it is high, the logic is wrong.

**Prevention:**
- Use BraiAn's `BoundingBoxHierarchy` colocalization tool which operates on the same detected nucleus object — not on proximity between separate detection objects.
- The classifier architecture: TdT_classifier.json → classifies each cell as TdT+/- based on its own Cytoplasm measurement. Fos_Classifier.json → classifies the same cell as Fos+/- based on its own Nucleus measurement. A cell is Double+ iff it is classified TdT+ AND Fos+ on the same PathObject.

**Phase:** Detection parameter tuning, classifier setup.

---

## Minor Pitfalls

Issues that cause inconvenience but are easy to detect and fix.

---

### Pitfall 11: Pseudoreplication — using section-level counts as independent replicates

**What goes wrong:** Cell counts or densities from individual sections are used directly in a statistical comparison between groups (e.g., 6 sections from Animal A vs. 6 sections from Animal B, treated as n=6 per group). Sections from the same animal are not independent.

**Prevention:** Aggregate to animal level first. Compute mean density (cells/mm² or cells/atlas-region) across all sections for each animal, then use animal as the statistical unit. BraiAn explicitly manages this aggregation — follow its one-project-per-animal structure.

**Phase:** Statistics (BraiAnalyse), before any group comparison.

---

### Pitfall 12: Nucleus sigma too large — nuclei merged across touching cells

**What goes wrong:** Setting `sigmaMicrons` too high in WatershedCellDetection smooths away the boundary between adjacent nuclei. The watershed algorithm merges two touching DAPI nuclei into one large object. That merged object has a large `Nucleus area` and may have very high or very low TdTomato/Fos mean depending on which cells were merged.

**Prevention:** Sigma should be set to roughly half the typical nuclear radius. For mouse neurons at 20x (~8–10 µm diameter nuclei), sigma = 1–2 µm. Validate by overlaying the detected nucleus outlines on the DAPI channel — each DAPI blob should have exactly one detection circle.

**Detection (observable in QuPath):** Detected cells that look oversized in the overlay, or unexpectedly high `Nucleus area` values (> 200 µm² for typical neurons), or fewer detections than expected in a dense region.

**Phase:** Detection parameter tuning.

---

### Pitfall 13: ABBA-Transform JSON file name mismatch

**What goes wrong:** The coordinate export Groovy script references a hardcoded transform file name (e.g., `"ABBA-Transform-Adult Mouse Brain - Allen Brain Atlas V3p1.json"`) that does not match the actual filename written by the version of ABBA in use. The script fails silently or throws a null-pointer exception; cells get no atlas coordinates but detection counts remain.

**Why it happens:** ABBA has changed its atlas naming conventions across versions. The filename encodes the atlas name.

**Detection:** After running the coordinate export script, check that Atlas_X/Y/Z measurements appear in the Measurements table for a few cells. If those columns are missing, the transform file was not found.

**Prevention:** Before writing any export script, print the actual filename of the ABBA transform JSON from the project entry directory. Use that exact name in the script.

**Phase:** Coordinate export scripting.

---

## Phase-Specific Warnings

| Phase Step | Likely Pitfall | Observable Warning Sign | Mitigation |
|---|---|---|---|
| MIP conversion | Channel names differ from what QuPath reads | Classifier finds no matching measurement column; counts all-zero | Lock `--channels` arg; verify channel names in QuPath image info before building classifiers |
| MIP conversion | `PIXEL_SIZE_UM` incorrect or missing from OME-XML | Scale bar in QuPath is wrong; detection radii in µm are applied at wrong physical scale | Verify pixel size against ZEN metadata; confirm scale bar in QuPath immediately after import |
| ABBA ROI loading | Duplicate annotations from re-loading without clearing | Two copies of CA1, DG, etc. in annotation panel | Always `clearAllObjects()` before `loadWarpedAtlasAnnotations` |
| ABBA ROI loading | Atlas ontology file deleted | Coordinate transforms fail; no atlas coordinates exported | Never delete `*.json` atlas ontology file adjacent to `.qpproj` |
| Detection setup | Cell expansion = 0 | `Cytoplasm:` measurements not generated; TdT classifier silently fails | Confirm `cellExpansionMicrons` > 0 before saving classifier |
| Detection setup | Wrong compartment in TdT classifier | TdT+ count systematically wrong; no error shown | Open classifier JSON; confirm `Cytoplasm:` not `Nucleus:` |
| Detection setup | Wrong compartment in Fos classifier | Fos+ count systematically wrong | Open classifier JSON; confirm `Nucleus:` not `Cytoplasm:` |
| Detection — parent assignment | Detection run without Root annotation selected | All cells at top level, zero per-region counts | Use BIOP detection script pattern with Root as parent; check hierarchy immediately after |
| Coordinate export | ABBA Atlas_X/Y/Z in mm, passed to brainrender directly | All cells cluster at atlas corner in 3D render | Multiply ABBA mm coordinates by 1000 before brainrender |
| Coordinate export | Wrong ABBA-Transform filename in script | No Atlas_X/Y/Z measurements generated | Print actual filename first; use that in script |
| Series application | Fixed Fos threshold fails on dim/bright sections | Count correlates with section batch position | Validate on dimmest section; use background-relative threshold |
| Statistics | Section-level counts used as n | Spuriously significant p-values | Aggregate to animal level before any group comparison; follow BraiAn one-project-per-animal structure |

---

## Sources

- ABBA Documentation v0.9 — QuPath analysis tutorial: https://abba-documentation.readthedocs.io/en/0.9.6/tutorial/4_qupath_analysis.html
- BraiAn for QuPath — BraiAnDetect usage guide: https://silvalab.codeberg.page/BraiAn/braian-qupath/
- BraiAn data preparation: https://silvalab.codeberg.page/BraiAn/read_qupath_data/
- BIOP ABBA+QuPath detection reference Groovy script (NicoKiaru): https://gist.github.com/NicoKiaru/f45f56e3ff2d1fb708821c110fbdee62
- QuPath cell detection pitfalls — image.sc forum thread (TRAP2 TdTomato/Fos overcounting, Dec 2025): https://forum.image.sc/t/qupath-cell-detection-issues-misalignment-between-dapi-and-cytosolic-markers-tdtomato-c-fos-leading-to-overcounting/118276
- Cabrera et al. bioRxiv 2024.09.16.611953 — Optimized TRAP2 whole-brain workflow with QuPath+ABBA: https://www.biorxiv.org/content/10.1101/2024.09.16.611953v2.full
- Increased Accuracy to c-Fos-Positive Neuron Counting (PMC8592694) — threshold sensitivity analysis: https://pmc.ncbi.nlm.nih.gov/articles/PMC8592694/
- Pete Bankhead blog — Multichannel fluorescence & multiple classifications: https://petebankhead.github.io/qupath/tips/2018/08/06/multichannel-fluorescence.html
- ABBA+BraiAn Cell Reports paper (Sciencedirect, 2025): https://www.sciencedirect.com/science/article/pii/S2211124725006473
- ABBA-QuPath-post_processing scripts (bmi-lsym): https://github.com/bmi-lsym/ABBA-QuPath-post_processing
