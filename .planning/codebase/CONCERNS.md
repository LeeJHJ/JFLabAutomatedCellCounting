# Codebase Concerns

**Analysis Date:** 2026-06-30

---

## Tech Debt

**Two divergent czi_to_mip.py versions:**
- Issue: `/home/jflab/Analysis/czi_mip.py` is an old single-purpose script (hardcoded I/O paths, no CLI, no `--channels` flag, fixed channel names in OME-XML). The canonical version is `/home/jflab/section-pipeline/scripts/czi_to_mip.py` (full CLI, `--channels`, pixel-size auto-read). The old file still exists and will be found first by anyone working in the Analysis directory.
- Files: `/home/jflab/Analysis/czi_mip.py`, `/home/jflab/section-pipeline/scripts/czi_to_mip.py`
- Impact: Running the wrong script produces silently mis-labeled channels (DAPI/Fos/TdTomato assigned to wrong data). This is the root cause of the previously documented channel mislabeling bug — and the old script leaves it live.
- Fix approach: Delete or clearly mark `/home/jflab/Analysis/czi_mip.py` as deprecated. Add a header comment or rename to `czi_mip.DEPRECATED.py`.

**Hardcoded paths and pixel size in `/home/jflab/Analysis/czi_mip.py`:**
- Issue: `F_IN`, `F_OUT`, and `PIXEL_SIZE_UM = 0.69` are all hardcoded constants at the top of the script. No argument parsing.
- Files: `/home/jflab/Analysis/czi_mip.py` lines 15–17
- Impact: Silently processes the wrong file if the M3 source CZI is moved or a different animal's file is used. Pixel size `0.69` is correct only for the 20x/0.8 zoom-0.6 acquisition; any change in objective or zoom produces wrong physical dimensions in QuPath without any warning.
- Fix approach: This script should be retired in favour of the canonical `czi_to_mip.py` with `--pixel-size` override.

**OME-XML channel names hardcoded to wrong fluorophore labels in old script:**
- Issue: Lines 68–70 of `/home/jflab/Analysis/czi_mip.py` write `Name="DAPI"`, `Name="Fos-EGFP"`, `Name="TdTom-Cy3"` unconditionally, regardless of what `--channels` the user would intend. "Fos-EGFP" is incorrect (actual dye is AF488); "TdTom-Cy3" is incorrect (actual dye is AF568). These mismatches confuse QuPath channel display names.
- Files: `/home/jflab/Analysis/czi_mip.py` lines 68–70
- Fix approach: Replace with the dynamic `_build_ome_xml()` function from the canonical script.

**Classifier JSON files use inconsistent measurement names across experiments:**
- Issue: `Automated Cell Counting Test/classifiers/object_classifiers/TdT_classifier.json` measures `"Nucleus: Cy3-T1 mean"` (nuclear compartment for TdTomato). `M3 Hippocampus 20x 062226/...Redo/.../TRAP2TdT_Classifier_20x.json` measures `"Nucleus: AF568-T2 mean"` (still nuclear, not cytoplasmic). The CLAUDE.md rule mandates a **cytoplasmic expansion ring** for TdTomato, meaning the correct measurement should be `"Cytoplasm: AF568-T2 mean"`. The Groovy scripts use `Cytoplasm: AF568-T2 mean` correctly, but the saved JSON classifiers do not.
- Files: `Automated Cell Counting Test/classifiers/object_classifiers/TdT_classifier.json`, `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/TRAP2TdT_Classifier_20x.json`
- Impact: If these classifier JSONs are reloaded in QuPath instead of re-running the Groovy script, TdTomato classification will be based on nuclear (not cytoplasmic) intensity — directly violating the analysis correctness rule and over/mis-counting TdT+ cells.
- Fix approach: Rebuild classifiers through the Groovy script pathway (which correctly uses cytoplasmic measurement) and save fresh JSON classifiers only after confirming the measurement name is `Cytoplasm:`.

**`run_deepslice.py` requires a fragile manual hand-off step:**
- Issue: The script writes `results.json` to a temp directory and prints "Put this file into the ABBA temp folder shown in Fiji log." There is no automated way to determine the ABBA temp folder path — the user must manually copy the file. If the Fiji log scrolls or is missed, the registration step breaks silently (DeepSlice runs but ABBA never sees the result).
- Files: `/home/jflab/section-pipeline/scripts/run_deepslice.py` lines 132–134
- Impact: Error-prone in a multi-section workflow. The `--out-dir` option is available but the correct ABBA temp path is undocumented.
- Fix approach: Document the expected ABBA temp folder path pattern (typically `/tmp/qupath-abba-*`) in the script docstring, or add a `--abba-tmp` flag and a helper that auto-discovers the most recently created `/tmp/qupath-abba-*/` directory.

**No output validation / sanity checks in `czi_to_mip.py`:**
- Issue: After writing the OME-TIFF, the script reports file size in MB but does not verify: (a) that pixel size was correctly embedded, (b) that channel count in the output matches expectation, (c) that the MIP is non-zero (i.e., the stack was not all-black). A mis-read channel order produces a plausible-looking output.
- Files: `/home/jflab/section-pipeline/scripts/czi_to_mip.py` (main() end block)
- Fix approach: After write, re-open with tifffile and assert `mip.max() > 0` per channel, print per-channel min/max/mean for quick sanity check.

---

## Known Bugs

**Channel order inversion (aicspylibczi vs CZI metadata):**
- Symptoms: `aicspylibczi` reads physical channel data in order TdTomato → Fos → DAPI (indices 0, 1, 2), while CZI metadata names them DAPI first. Without `--channels` override, all channel names in the output OME-TIFF are assigned to the wrong data.
- Files: `/home/jflab/section-pipeline/scripts/czi_to_mip.py` (`_get_channel_names()` function)
- Trigger: Any CZI from this LSM 980 / 20x acquisition run without `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"`.
- Workaround: Always pass `--channels` override. Confirmed fix. The issue is a library behavior difference, not file corruption.
- Risk: The workaround is not enforced — a new user or a future script invocation can easily omit `--channels` and silently produce mislabeled output. No warning is emitted when channel names are read from metadata vs overridden.

**elastix degrades ABBA registration when run without tissue mask:**
- Symptoms: After DeepSlice + manual angle adjustment (Review Mode), running Affine or Spline registration shifts the atlas 300–500 µm off lateral structures (e.g., Lateral Amygdala), worsening an already-good alignment.
- Files: `Automated Cell Counting Test/elastix_spline_backup/elastix.log`, `Automated Cell Counting Test/elastix_spline_backup/TransformParameters.0.txt`
- Trigger: Running ABBA Affine/Spline on any section with a black image border. Elastix samples ~4096 random points over the full image including ~40% black background, causing the metric to optimize away from the tissue region.
- Workaround: Skip Affine/Spline entirely; export directly from the manual-adjusted DeepSlice state. If elastix is ever needed, crop MIP to remove the black border first.
- Risk: The standard ABBA UI presents Affine and Spline as the expected next steps after DeepSlice — a new user will instinctively run them and degrade the result.

**`classify_cells_adaptive.groovy` stores class names as hash codes:**
- Symptoms: Lines 176–177 store `Class_Otsu` and `Class_Percentile` as `otsuClass.getName().hashCode() as double`. Hash codes are meaningless integers — they cannot be decoded back to class names without knowing the hash function, and they will collide across QuPath versions.
- Files: `/home/jflab/section-pipeline/scripts/classify_cells_adaptive.groovy` lines 176–177
- Trigger: Running the adaptive classifier and then trying to use `Class_Otsu` / `Class_Percentile` measurements in downstream analysis or BraiAn export.
- Fix approach: Store class names as string measurements or use a numeric enum (0=Negative, 1=TdT+, etc.) with a documented legend, rather than hash codes.

---

## Security Considerations

**No security concerns identified** beyond standard bioinformatics pipeline risks (large file I/O, untrusted CZI metadata parsed via `xml.etree.ElementTree`). The XML parser is not configured with entity expansion limits, which could be relevant if CZI files from an untrusted source were processed — not a concern for in-house acquisitions.

---

## Performance Bottlenecks

**Full-section 20x MIP generation loads all Z-planes per channel into RAM simultaneously:**
- Problem: `generate_mip()` in `czi_to_mip.py` builds a `stack = []` list per channel, appending each Z-plane before calling `np.max()`. For a 187-tile mosaic at 20x with 6 Z-planes and 3 channels, this holds up to ~6 planes × ~(8000×6000) px × uint16 in memory at once per channel.
- Files: `/home/jflab/section-pipeline/scripts/czi_to_mip.py` lines 160–167 (`generate_mip()`)
- Cause: The running-max approach (accumulate MIP as each plane is read) is not implemented — instead all planes are collected first.
- Improvement path: Replace `stack = []; stack.append(plane)` with a running max: initialize `mip_c = None`, then `mip_c = plane if mip_c is None else np.maximum(mip_c, plane)`. This halves peak per-channel memory.

**`classify_cells_adaptive.groovy` uses O(n²) centroid-in-ROI check:**
- Problem: Line 138: `def cells = allCells.findAll { cell -> roi.contains(...) }` iterates over all cells for every annotation. With many annotations and many cells (tens of thousands per section), this is O(annotations × cells).
- Files: `/home/jflab/section-pipeline/scripts/classify_cells_adaptive.groovy` line 138
- Cause: No spatial index used.
- Improvement path: Use QuPath's built-in `hierarchy.getObjectsForROI()` which uses an R-tree internally, or pre-group cells by atlas annotation using `getAnnotationObjects()` parent-child relationships.

---

## Fragile Areas

**Detection parameters are untuned (pipeline-critical pending step):**
- Files: `/home/jflab/section-pipeline/scripts/classify_cells.groovy` lines 26–28, `/home/jflab/section-pipeline/scripts/classify_cells_adaptive.groovy` lines 27–29
- Why fragile: `DAPI_THRESHOLD = 1000`, `TDT_THRESHOLD = 500`, `FOS_THRESHOLD = 200` are seeded from a published TRAP2 paper and have not been validated on this dataset. The presentation notes (as of 2026-06-30) explicitly flag this as unresolved. Running the full series with unseeded thresholds risks systematic miscounting across all brain regions.
- Safe modification: Do not run classifiers on the full series until thresholds are validated by spot-check on at least one complete section. Document the validated values in CLAUDE.md.
- Test coverage: None. No automated test exists for classification accuracy.

**Cytoplasmic expansion radius is a fixed assumption, not a measured parameter:**
- Files: `classify_cells.groovy` line 19 (comment: "4 µm cytoplasmic expansion"), `classify_cells_adaptive.groovy` line 19
- Why fragile: 4 µm is hardcoded in QuPath cell detection (not in the scripts, but in the manual QuPath step). If the expansion radius is too small, TdTomato is missed; if too large, it captures signal from adjacent cells in dense regions. This parameter must be set consistently across all sections and is not recorded in any configuration file.
- Safe modification: Record the confirmed expansion radius in CLAUDE.md once validated. Consider parameterizing it in a config comment at the top of both Groovy scripts.

**QuPath project data is stored as binary `.qpdata` files:**
- Files: `Automated Cell Counting Test/data/1/data.qpdata`, `M3 Hippocampus 20x 062226/.../data/1/data.qpdata`, etc.
- Why fragile: `.qpdata` files are QuPath-version-specific binary serializations. They are not human-readable and may not be forward-compatible if QuPath is bumped from v0.6.0 to 0.7.x. CLAUDE.md correctly pins QuPath to v0.6.0 for this reason.
- Safe modification: Never upgrade QuPath without first exporting all detections to GeoJSON (File → Export → GeoJSON) and saving the export. Do not bump to v0.7.x without verifying BIOP catalog compatibility.

**ABBA `.abba` project file format:**
- Files: `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/bigwarp M3 Hippocampus 20x.abba`
- Why fragile: ABBA project files embed absolute paths to the source image and atlas. If the Analysis directory is moved, or if ABBA is updated, these projects may fail to load. The `ABBA-Transform-allen_mouse_10um_java.json` files (present in multiple data/ subdirectories) are more portable and should be preserved separately.
- Safe modification: Keep `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` files versioned alongside each section. Do not rely solely on the `.abba` project file for transform recovery.

**No registered full series — pipeline has only one validated section (M3 hippocampus):**
- Why fragile: The entire downstream pipeline (BraiAn stats, brainrender point cloud) is designed for a full-cohort series, but as of 2026-06-30 only one section from one animal has been registered. All quantitative parameters (thresholds, expansion radius, registration workflow) are calibrated on a single hippocampal section. Lateral amygdala and other structures in the target cohort may require parameter re-tuning.
- Safe modification: Scale to the full series only after validating detection on at least 3 sections from different AP levels.

---

## Scaling Limits

**RAM constraint for large-mosaic MIP generation:**
- Current capacity: 61 GB RAM, no swap configured (assumed).
- Limit: A full coronal section at 20x (187 tiles × 6 Z × 3 channels) consumes ~12–18 GB RAM during `generate_mip()` with the current implementation. A larger objective (e.g., 40x) or more Z-planes would exceed available RAM.
- Scaling path: Implement running-max per channel (see Performance Bottlenecks above). For very large acquisitions, consider tile-by-tile stitching with `tifffile.memmap` output.

**CPU-only DeepSlice is slow for large series:**
- Current capacity: i9-9900K 8C/16T, no GPU.
- Limit: DeepSlice ensemble prediction on CPU takes several minutes per section. For a full cohort (e.g., 30 animals × 20 sections = 600 sections), local DeepSlice becomes the dominant bottleneck.
- Scaling path: Use DeepSlice online (web API) for the first pass, then fall back to local only if internet is unavailable. Alternatively, batch-export all DAPI PNGs and submit to the DeepSlice web service.

---

## Dependencies at Risk

**`aicspylibczi` channel-order behavior is undocumented:**
- Risk: The channel inversion bug (TdTomato/Fos/DAPI read in reverse of metadata) is a library quirk that is not documented in aicspylibczi's public API. A library update could change this behavior without notice, making the `--channels` workaround incorrect.
- Impact: Silent channel swapping in all future CZI conversions.
- Migration plan: After any `aicspylibczi` version update, re-run `--info` on a known CZI and verify channel order before processing new data.

**`brainrender` env is fragile (vedo/VTK/allensdk conflict zone):**
- Risk: CLAUDE.md explicitly flags the `brainrender` conda env as fragile due to vedo/VTK/allensdk version interactions. This env has not yet been exercised (brainrender step is not yet done as of 2026-06-30).
- Impact: The 3D atlas-space cell point cloud step could fail at first invocation with a dependency conflict that requires rebuilding the env.
- Migration plan: Before running brainrender for the first time, test with a minimal script (`import brainrender; from brainrender import Scene`) and resolve any import errors before committing to a full render.

**elastix pinned to 5.2.0 with no upgrade path:**
- Risk: ABBA requires exactly elastix 5.2.0. A future ABBA update may require a different elastix version, requiring a re-install that breaks the existing `LD_LIBRARY_PATH` setup.
- Impact: ABBA registration workflow breaks on elastix upgrade.
- Migration plan: Keep the current elastix 5.2.0 binary in `/home/jflab/section-pipeline/tools/elastix/` and do not update until ABBA release notes explicitly call for a new version.

---

## Missing Critical Features

**No export pipeline from QuPath detections to BraiAn input format:**
- Problem: The pipeline ends at QuPath cell classification. There is no script to export classified cell centroids (in atlas coordinates) from QuPath to the CSV/HDF5 format expected by BraiAn for whole-brain statistics.
- Blocks: Cannot run any BraiAn regional cell density analysis or brainrender visualization until this export step exists.

**No batch registration script for the full section series:**
- Problem: The current workflow registers one section at a time via manual ABBA GUI steps. There is no script or documented protocol for running DeepSlice + angle adjustment + export across a full set of sections from one animal.
- Blocks: Cannot scale from a single validated section to a full-cohort analysis.

**No animal-level aggregation step:**
- Problem: CLAUDE.md mandates aggregating cell counts to the animal level before any group comparison (sections are not independent). There is no script or notebook that performs this aggregation. BraiAn is planned for this step but has not been integrated.
- Blocks: Cannot perform any valid statistical comparison across animals.

---

## Test Coverage Gaps

**No automated tests for any pipeline component:**
- What's not tested: Channel order in CZI → OME-TIFF conversion, OME-XML correctness, classifier threshold application, atlas coordinate export units (microns vs pixels).
- Files: All scripts under `/home/jflab/section-pipeline/scripts/`
- Risk: Regression in any of these components (e.g., after a library update) would go undetected until visual inspection of results.
- Priority: High — the channel-order bug (already hit once) and the pixel/micron coordinate unit issue (flagged in CLAUDE.md as non-negotiable) are both silent failures that produce plausible-looking but scientifically incorrect outputs.

**No validation that exported atlas coordinates are in microns:**
- What's not tested: The ABBA export and the downstream coordinate system are both CCFv3, but the unit of export (microns vs voxels vs pixels) is not verified anywhere in code. CLAUDE.md marks this as a hard constraint.
- Files: The QuPath → BraiAn export step (does not yet exist)
- Risk: A coordinate unit error places the entire point cloud in the wrong region of the Allen atlas — cells would appear in completely wrong brain structures with no obvious visual error in the final render.
- Priority: High.

---

*Concerns audit: 2026-06-30*
