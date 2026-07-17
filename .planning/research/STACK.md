# Stack Research

**Domain:** TRAP2/Airyscan section pipeline — v1.1 milestone additions only (First Full-Series Run, LA/BA Amygdala Engram, wBA1-3)
**Researched:** 2026-07-17
**Confidence:** MEDIUM (mixed: HIGH for anything verified by direct inspection of installed packages/files on this machine; LOW/MEDIUM for web-sourced API claims — see per-item notes and Sources)

This is **not** a greenfield stack pick. v1.0's stack (QuPath 0.6.0, elastix 5.2.0, ABBA Method 2, `deepslice`/`braian`/`brainrender` conda envs) is locked and working — see the **v1.0 QuPath/BraiAn Scripting Reference appendix** below for the detailed API this milestone builds on. Every row in this section is either (a) a **new library/API call** needed for a v1.1 feature, or (b) an explicit **"do not add"** flag. Nothing here proposes a version bump or new conda env.

## Recommended Additions (by v1.1 feature)

### 1. Multi-scene `czi_mip.py` extension — NEW code, NO new dependency

| API | Package (already installed) | Purpose | Why |
|-----|------------------------------|---------|-----|
| `CziFile.get_all_mosaic_scene_bounding_boxes()` → `dict[int, BBox(x,y,w,h)]` | `aicspylibczi` 3.3.1 (in `braian` env, already a dependency of `czi_mip.py`) | Enumerate the 5 scene bounding boxes in `-001-07_processed.czi` | `read_mosaic()` **ignores the S dimension internally** and reconstructs by its own mosaic index — it will silently fuse all 5 scenes into one canvas unless the read is constrained. This is exactly the bug that produced the unusable 32 GB merged OME-TIFF already flagged in `PROJECT.md`. |
| `CziFile.read_mosaic(region=bbox, scale_factor=1.0, C=c, Z=z)` looped per scene bbox, per channel, per Z, then `np.max(..., axis=0)` (existing MIP convention) | same | Emit one MIP OME-TIFF per scene (5 outputs instead of 1) | `region=` is the one documented parameter that scopes `read_mosaic` to a sub-rectangle; pairing it with each scene's own bbox is the only documented way to separate scenes in a mosaic file. |

**Integration point:** extend `czi_mip.py`'s main loop to iterate `get_all_mosaic_scene_bounding_boxes().items()`, output `{AnimalID}_scene{N}_20x_MIP.ome.tiff` per scene, keeping the existing `--channels` override (channel-order workaround still applies per-scene). No new package install — same `aicspylibczi==3.3.1` / `tifffile` already in `braian` env.

**Confidence: LOW-MEDIUM.** The exact method names (`get_mosaic_scene_bounding_box`, `get_all_mosaic_scene_bounding_boxes`, `region=` kwarg on `read_mosaic`) came from web-sourced GitHub source excerpts, not a live Context7 doc fetch or hands-on run against the actual 16 GB file (MCP doc tools were unavailable this session — see Gaps). **Before writing the extension, run a 5-minute interactive check**: `czi.get_dims_shape()` and `czi.get_all_mosaic_scene_bounding_boxes()` against the real file to confirm the API surface on this exact aicspylibczi build before committing to the loop structure.

### 2. Registration speedup — mostly USAGE changes, one path explicitly blocked

| Approach | Verdict | Why |
|----------|---------|-----|
| **DeepSlice folder-batch + `propagate_angles()` + `enforce_index_spacing()`** | **RECOMMENDED — do this first** | `deepslice` 1.2.8 (already installed, no upgrade) supports `Model.predict(folderpath, ensemble=True, section_numbers=True)` on all 5 sections in one call, `Model.propagate_angles()` to average the cutting angle across sections from the same block (wBA1-3's 5 sections share one physical cutting angle — v1.0 tuned this manually per single section; v1.1 has 4 more sections to which the same shared angle should apply), and `Model.set_bad_sections()` / `Model.enforce_index_spacing(section_thickness=...)` to keep AP ordering sane. This turns "manual angle review ×5" into "one shared angle, reviewed once, propagated." CPU-only, already in the pinned `deepslice` env — zero new install. |
| **Elastix Affine+Spline with `crop_to_tissue.py`'s DAPI mask fed via `-fMask`/`-mMask`** | **CONDITIONAL / not a clean win — flag as experimental, not default** | elastix 5.2.0's core CLI genuinely supports `-fMask`/`-mMask` binary mask flags, and mask-supported registration is well-documented in the wider registration literature to meaningfully improve accuracy over unmasked (background pixels stop dominating the cost function — exactly the v1.0 failure mode). **However**, ABBA's Fiji GUI Elastix wrapper (`BIOP/ijl-utilities-wrappers`, the one actually invoked by ABBA's "Register" command) documents no mask parameter in its Register/Save/Load commands. Using the mask inside the pinned ABBA workflow would mean running `elastix` CLI directly (bypassing the GUI) and hand-constructing/importing the resulting transform into ABBA's expected `ABBA-Transform-*.json` sequence format — undocumented, custom glue code, non-trivial to validate for a first full series. Recommend: **try DeepSlice batch + shared-angle first**; only reach for masked-elastix-outside-ABBA as a stretch goal if manual BigWarp refinement is still too slow after that, and budget it as its own small research/prototype spike rather than assuming it drops in. |
| **BigWarp landmark reuse across the 5 sections** | **RECOMMENDED as a fallback speedup, not a replacement** | BigWarp supports exporting/importing landmark point-pair files from the landmark table panel, and a documented "apply saved landmarks to another image" pattern exists. For 5 adjacent sections of the same block, seeding each section's BigWarp landmarks from the previous section's saved set (then nudging, not re-placing from scratch) is a legitimate manual-effort reduction that needs no new tooling — just a workflow discipline (save landmarks after each section, load-and-adjust for the next). |
| **ABBA/Fiji headless or scripted batch registration** | **BLOCKED — not available** | No headless/scriptable API exists for ABBA's registration steps (DeepSlice trigger, Affine, Spline, BigWarp) in the standalone Fiji install. The only scripting surface is *post*-registration: `qupath.ext.biop.abba.AtlasTools` (already used in `01_load_abba_rois.groovy` for `loadWarpedAtlasAnnotations()` / `getAtlasToPixelTransform()`). Registration itself stays GUI-mediated — consistent with existing CLAUDE.md guidance ("GUI-only: hand back to the human"). Do not plan around a batch-registration script existing. |

### 3. Generalizable area-based density readout — NEW code on top of QuPath **core** (not BraiAn extension), NO new dependency

| API | Where | Purpose | Why |
|-----|-------|---------|-----|
| `qupath.opencv.ml.pixel.PixelClassifiers.createThreshold(resolution, channel, threshold, belowClass, aboveClass)` | QuPath 0.6.0 core (bundled, no extension needed) | Build a fixed single-channel intensity-threshold pixel classifier entirely from Groovy — no GUI training step | This is the scriptable equivalent of classic IHC "positive pixel counting," runnable headlessly per-section alongside the existing detection scripts. |
| `qupath.opencv.ml.pixel.PixelClassifierTools.createMeasurementManager(imageData, classifier)` + `.addMeasurementsToSelectedObjects()` | same | Attach %-positive-area measurements directly onto the **existing ABBA atlas-region annotations** already in the hierarchy (no new annotation objects needed) | The region annotations from `AtlasTools.loadWarpedAtlasAnnotations()` are already selectable objects in `01_load_abba_rois.groovy`'s output — this is the lowest-friction integration point: run the pixel classifier, select region annotations, call `addMeasurementsToSelectedObjects()`, done. |
| (confirmed absent) `qupath-extension-braian` / BraiAnDetect | — | — | **No area-classifier, density-map, or percent-positive-area feature exists in BraiAnDetect** (it is strictly object/cell-detection + classification: `ChannelDetections` + `SimpleClassifier`/`OverlappingDetections`, per the appendix below). Do not look for a BraiAn-native area mode — build the area readout as a **separate, additive Groovy script** (e.g. `04_area_density_readout.groovy`) that runs after/alongside `02_detect_classify.groovy`, sharing the same DAPI-positive tissue definition but never replacing per-nucleus counts (matches the PROJECT.md Key Decision that this is "additive/parallel, never replacing"). |

**Confidence: LOW-MEDIUM** (web-sourced javadoc/gist excerpts, not confirmed against the actual installed QuPath 0.6.0 jar in this session). **Validate exact method signatures against the installed `QuPath.jar`'s bundled javadoc or a quick Script Editor autocomplete check before writing `04_area_density_readout.groovy`.**

### 4. Section→animal aggregation — USAGE of already-installed `braian` 1.0.5, NO new dependency

Confirmed **directly against the installed package** in the `braian` conda env (`python3 -c "import braian; ..."` — HIGH confidence, not web-sourced):

| Class / method | Signature (as installed) | Role |
|---|---|---|
| `braian.BrainSlice.from_qupath` | `(csv, ch2marker: dict[str,str], atlas=None, *args, **kwargs)` | Loads **one section's** `qupath-extension-braian` export (the `<image>_regions.tsv` produced by `atlas.saveResults()` — already wired up in the existing `02_detect_classify.groovy`/main detection script per the appendix below) |
| `braian.SlicedBrain` / `.from_qupath` | `SlicedBrain(name, slices: Iterable[BrainSlice], markers)` or the one-shot loader `SlicedBrain.from_qupath(name, animal_dir, brain_ontology, ch2marker, results_subdir='results', results_suffix='_regions.tsv', exclusions_subdir='regions_to_exclude', exclusions_suffix='_regions_to_exclude.txt')` | Loads **all 5 of wBA1-3's per-section files from one directory** in a single call — this is the "5 sections → 1 animal, still section-resolved" intermediate object. **Default `results_subdir='results'` / `results_suffix='_regions.tsv'` already match the existing script's output path (`<projectDir>/results/<imageName>_regions.tsv`)** — confirmed against the v1.0 QuPath scripting reference (appendix below), so no naming-convention change is needed on the QuPath side for this to work, only placing all 5 sections' `results/`+`regions_to_exclude/` outputs under one `animal_dir`. |
| `braian.AnimalBrain.from_slices` | `(sliced_brain, metric: SliceMetrics|str = SliceMetrics.SUM, min_slices: int = 0, hemisphere_distinction: bool = True, densities: bool = False)` | **The actual section→animal reduction.** `SliceMetrics` enum = `SUM, MEAN, STD, CVAR`. `densities=True` reduces on **marker/area density** instead of raw counts — directly reusable for the area-based readout's animal-level roll-up too, once that measurement exists per section. `min_slices` guards against a region only appearing in 1-2 of the 5 sections. |
| `braian.AnimalBrain.to_csv()` / `from_csv()` | — | Persist/reload the per-animal region table |
| `braian.AnimalGroup` | `(name, animals: Sequence[AnimalBrain], hemisphere_distinction=True, brain_ontology=None, fill_nan=True)` | Multi-animal comparison — **out of scope this milestone** (n=1 animal), but the class already exists for when wBA1-3 gets siblings |

**Integration point:** run all 5 sections' `02_detect_classify.groovy` / main detection script (which already calls `atlas.saveResults(...)` per the appendix) so each section's `results/<imageName>_regions.tsv` + `regions_to_exclude/<imageName>_regions_to_exclude.txt` land under one shared `animal_dir` (e.g. one QuPath project directory holding all 5 image entries, which is already the project layout), then call `SlicedBrain.from_qupath(...)` → `AnimalBrain.from_slices(...)` in a new JupyterLab notebook / script in the `braian` env. This is a **new analysis script**, not a QuPath-side change — the QuPath export side is already correct.

### 5. Micron per-region export → brainrender-ready format — USAGE of already-installed packages, NO new dependency

Confirmed **directly against the installed package** in the `brainrender` conda env (HIGH confidence):

| Fact | Value |
|---|---|
| `brainrender.actors.Points.__init__` signature | `(self, data, name=None, colors='salmon', alpha=1, radius=20, res=8)` — `data` is an **Nx3 numpy array** (or path to a `.npy` file) |
| Atlas used | `brainglobe_atlasapi.BrainGlobeAtlas('allen_mouse_10um')` — resolution `(10.0, 10.0, 10.0)` µm, `axes_order = ('sagittal', 'vertical', 'frontal')` i.e. **(AP, DV, ML)**, shape `(1320, 800, 1140)` voxels |
| brainrender installed version | 2.1.20 (PyPI latest is **2.2.0** — a point release exists but is **not required**; do not upgrade for this milestone, since actual brainrender rendering is explicitly out-of-scope for v1.1 per PROJECT.md — only the *export format* needs to be brainrender-ready) |

**What this means for the export step:** the per-cell/per-region atlas coordinates already computed via the existing `AtlasTools.getAtlasToPixelTransform()` script (appendix below — note that script's own caveat: the raw transform output units need the ×1000 mm→µm check already documented there) just need to land in a plain **Nx3 numpy array / CSV with 3 numeric columns in (AP, DV, ML) micron order** to be a direct, zero-transform `Points(data)` input whenever brainrender visualization work resumes. No new library needed to satisfy this requirement — it's a data-shape contract, not a dependency.

## What NOT to Add / Explicitly Blocked

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| Any CUDA/GPU build of anything (Cellpose GPU, TensorFlow-GPU, torch+cuda) | No NVIDIA hardware on this box (Intel UHD 630 iGPU only) — hard constraint | CPU builds only; BraiAnDetect's built-in QuPath detection, CPU TensorFlow (already installed for DeepSlice) |
| QuPath 0.7.x | BIOP/BraiAn catalog compatibility untested against 0.7.x; pinned at 0.6.0 | Stay on 0.6.0 for this milestone; re-evaluate only as its own explicit decision, not a side effect of a v1.1 feature |
| elastix version other than 5.2.0 | ABBA (Method 2 install) requires exactly 5.2.0 | Stay on 5.2.0; if masked-registration is pursued outside ABBA's GUI, it's the *same* 5.2.0 binary invoked differently, not a version change |
| `abba-python` (ABBA Method 3) | Only needed for non-Allen BrainGlobe atlases; this project is Allen CCFv3 only | Keep Method 2 (standalone Fiji + PTBIOP update site) |
| Cellpose / StarDist for detection | Explicitly out of scope per PROJECT.md — BraiAnDetect's built-in QuPath detection preferred for CPU speed | `qupath-extension-braian`'s `ChannelDetections` (already in use) |
| A headless/batch ABBA registration script | Does not exist — confirmed no such API in `ijl-utilities-wrappers` or ABBA's Fiji integration | Manual DeepSlice-batch + BigWarp-per-section GUI workflow (speedup via §2 above, not automation) |
| Assuming BraiAnDetect will grow an area/density feature | Not present in the current extension design (object-detection focused) | Build the area readout directly on QuPath 0.6.0's own `PixelClassifiers`/`PixelClassifierTools` API, as a standalone additive script |
| Forcing a brainrender 2.1.20 → 2.2.0 upgrade this milestone | Not required — brainrender visualization itself is out of scope for v1.1; only the export data shape matters | Keep 2.1.20; revisit the point-release bump when 3D visualization work actually starts |

## Version Compatibility

| Package | Installed | PyPI Latest (checked 2026-07-17) | Action |
|---|---|---|---|
| `aicspylibczi` | 3.3.1 | 3.3.1 | No change |
| `DeepSlice` | 1.2.8 | 1.2.8 | No change — batch/propagate-angle APIs already available in the installed version |
| `braian` | 1.0.5 | 1.0.5 | No change — all aggregation APIs needed are already present |
| `brainrender` | 2.1.20 | 2.2.0 | No change needed for v1.1 (export-format contract only, not live rendering) |
| QuPath | 0.6.0 | — | Pinned, do not bump |
| elastix | 5.2.0 | — | Pinned, do not bump |

## Sources (v1.1 research pass, 2026-07-17)

- Direct inspection of installed packages on this machine (`conda run -n braian python3 -c "import braian; ..."`, `conda run -n brainrender python3 -c "import brainrender, brainglobe_atlasapi; ..."`) — **HIGH confidence**, used for all `braian` API signatures (§4) and `brainrender`/`brainglobe-atlasapi` facts (§5).
- PyPI JSON API (`pypi.org/pypi/<pkg>/json`) — version numbers for `aicspylibczi`, `brainrender`, `braian`, `DeepSlice` — HIGH confidence for version facts only.
- WebSearch/WebFetch on: `github.com/AllenCellModeling/aicspylibczi` source (`CziFile.py`), `github.com/PolarBean/DeepSlice` README/example notebook, `github.com/BIOP/ijl-utilities-wrappers` README, `abba-documentation.readthedocs.io` QuPath-analysis tutorial, `qupath.github.io/javadoc/docs` (`PixelClassifiers`, `PixelClassifierTools`), Pete Bankhead's QuPath scripting gists, `image.sc` forum threads on ABBA/elastix masking and QuPath pixel-classification scripting, `silvalab.codeberg.page/BraiAn` docs pages — **LOW-MEDIUM confidence** (no MCP doc-lookup tool such as Context7 was available in this session; all of §1–§3 and the elastix-mask / BigWarp / ABBA-scripting findings in §2 rest on WebSearch snippet synthesis, not a verified live doc fetch). Flagged individually above where this matters for implementation risk.

## Gaps to Address

- **aicspylibczi scene-iteration API (§1)** should be smoke-tested directly against `-001-07_processed.czi` (`get_dims_shape()`, `get_all_mosaic_scene_bounding_boxes()`) before the `czi_mip.py` extension is written — no MCP/Context7 tool was available this session to verify the exact method names against current library docs, only web-sourced source-code excerpts.
- **QuPath `PixelClassifiers`/`PixelClassifierTools` exact class package (§3)** — verified as `qupath.opencv.ml.pixel.*` from javadoc URLs and a community gist, but not checked against the actual installed `QuPath.jar`'s bundled classes in this session. A 2-minute Script Editor autocomplete check will confirm before coding `04_area_density_readout.groovy`.
- **Masked elastix outside ABBA's GUI (§2)** is the one genuinely open question flagged as CONDITIONAL rather than recommended — if the roadmap wants to pursue it, it deserves its own small phase-level research spike (how to hand-construct/import a transform elastix produces directly into ABBA's `ABBA-Transform-*.json` sequence format) rather than treating it as a known-good drop-in.

---
*Stack research for: TRAP2/Airyscan section pipeline — v1.1 First Full-Series Run (LA/BA Amygdala Engram, wBA1-3)*
*Researched: 2026-07-17*

---

# Appendix: v1.0 QuPath/BraiAn Scripting API Reference

**Project:** M3 Hippocampus Section Pipeline (TRAP2 / Steps 3–4)
**Researched:** 2026-06-30
**Scope:** QuPath Groovy scripting API, BraiAnDetect configuration, coordinate export — carried forward from v1.0 phase research; still the operative reference for the extensions/detection layer that v1.1 builds on top of.

## Installed Extension Versions (verified on-disk)

| Extension | Version | Jar path |
|-----------|---------|----------|
| QuPath | 0.6.0 | `$HOME/section-pipeline/tools/QuPath/bin/QuPath` |
| qupath-extension-braian | 1.1.0 | `.../BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/` |
| qupath-extension-abba | 0.4.0 | `.../QuPath-BIOP catalog/QuPath ABBA extension/v0.4.0/main-jar/` |
| qupath-extension-warpy | 0.4.2 | `.../QuPath-BIOP catalog/QuPath Warpy extension/v0.4.2/main-jar/` |

## Actual Channel Names in the M3 20x MIP

From `project.qpproj` (M3 Hippocampus 20x 062926 3 plane, pixelWidth = 0.6905 µm/px):

| QuPath channel name | Marker | Role |
|--------------------|--------|------|
| `AF568-T2` | TdTomato | Encoding engram; cytosolic |
| `AF488-T3` | Fos | Recall IEG; nuclear |
| `DAPI-T4` | DAPI | Nuclear stain for segmentation |

BraiAn.yml must use these **exact** channel name strings — they come from the OME-TIFF metadata as written by `czi_mip.py` and are how QuPath labels channels internally. Cross-check with the project's channel list before running detection. (wBA1-3's channels are named the same per PROJECT.md — no change expected.)

## BraiAn.yml Configuration

BraiAn reads a `BraiAn.yml` file placed in the QuPath project folder **or** its parent directory. It is the single source of truth for all detection, classification, and overlap parameters. The file must be present before running the main detection script.

### Full Annotated Schema (with TRAP2-specific values)

```yaml
# Place in the QuPath project dir or its parent dir.
# Channel names must match QuPath's internal channel labels exactly.

classForDetections: null        # null = run on whole image root annotation
                                # Set to an annotation class name (string) to restrict

detectionsCheck:
  apply: true                   # MANDATORY for TRAP2: ensures every Fos/TdT detection
                                #   is contained within a DAPI nucleus
  controlChannel: "AF568-T2"   # Use TdTomato (cytosolic, larger ROI) as the container
                                #   cell, not DAPI — DAPI detections are nuclear-only
                                #   while TdT detections include a cytoplasmic ring

channelDetections:
  # ── DAPI: nuclear segmentation basis ──────────────────────────────────────
  - name: "DAPI-T4"
    parameters:
      requestedPixelSizeMicrons: 0.69   # match native pixel size (no downsampling)
      backgroundRadiusMicrons: 10.0     # > largest nucleus; 10 µm is safe for neurons
      backgroundByReconstruction: true  # true = more accurate background, default
      medianRadiusMicrons: 0.0
      sigmaMicrons: 1.5                 # starting value from BraiAn example; tune up
                                        #   (e.g. 2.0) if nuclei fragment
      minAreaMicrons: 30.0              # mouse neuron nucleus ~5–8 µm diam → ~80 µm²
                                        #   start at 30 to reject debris; tune from overlay
      maxAreaMicrons: 500.0             # reject merged clumps; neurons rarely exceed 300 µm²
      threshold: 200                    # or use histogramThreshold (see below)
      watershedPostProcess: true        # split merged nuclei; keep true
      cellExpansionMicrons: 0.0         # DAPI detection = nuclei only; no expansion here
      includeNuclei: true
      smoothBoundaries: true
      makeMeasurements: true

  # ── TdTomato: cytosolic engram marker ─────────────────────────────────────
  - name: "AF568-T2"
    parameters:
      requestedPixelSizeMicrons: 0.69
      backgroundRadiusMicrons: 10.0
      backgroundByReconstruction: true
      medianRadiusMicrons: 0.0
      sigmaMicrons: 1.5                 # nucleus seed; tune to 2.0 if fragmented
      minAreaMicrons: 30.0
      maxAreaMicrons: 500.0
      # Use auto-threshold from histogram (recommended over fixed threshold):
      histogramThreshold:
        resolutionLevel: 4              # coarser level = faster; 4 is standard
        smoothWindowSize: 15
        peakProminence: 100             # raise if background peaks contaminate
        nPeak: 1                        # first local max above background = signal
      watershedPostProcess: true
      cellExpansionMicrons: 5.0         # CRITICAL: expands nucleus into cytoplasm
                                        #   to capture TdT signal (cytosolic dye).
                                        #   5 µm = starting point; tune visually.
                                        #   Increase to 7–8 µm if TdT signal missed.
      includeNuclei: true               # measure both nuclear + cytoplasmic compartments
      smoothBoundaries: true
      makeMeasurements: true
    classifiers:
      - name: "TdTomato_classifier"    # must exist in project classifiers/ dir

  # ── Fos: nuclear IEG marker ───────────────────────────────────────────────
  - name: "AF488-T3"
    parameters:
      requestedPixelSizeMicrons: 0.69
      backgroundRadiusMicrons: 10.0
      backgroundByReconstruction: true
      medianRadiusMicrons: 0.0
      sigmaMicrons: 1.5
      minAreaMicrons: 30.0
      maxAreaMicrons: 500.0
      histogramThreshold:
        resolutionLevel: 4
        smoothWindowSize: 15
        peakProminence: 100
        nPeak: 1
      watershedPostProcess: true
      cellExpansionMicrons: 0.0         # Fos is NUCLEAR; do NOT expand into cytoplasm.
                                        #   Expanding would merge adjacent nuclei and
                                        #   create false Fos+ calls.
      includeNuclei: true
      smoothBoundaries: true
      makeMeasurements: true
    classifiers:
      - name: "Fos_classifier"         # must exist in project classifiers/ dir
```

**Note (v1.1):** the M3-062926-3-plane project's live `BraiAn.yml` deviates deliberately from this canonical example (single channelDetections entry rooted on DAPI with both classifiers nested under it, not per-marker-channel topology) — see that project's own `BraiAn.yml` header comment for the rationale (nucleus-anchored colocalization without `OverlappingDetections`). Carry that same deliberate topology into wBA1-3's config, not this appendix's literal schema.

### Key Parameter Rationale for TRAP2

| Parameter | DAPI | TdTomato (AF568-T2) | Fos (AF488-T3) | Reason |
|-----------|------|---------------------|-----------------|--------|
| `cellExpansionMicrons` | 0 | **5.0** (start) | **0** | TdT is cytosolic — must measure in cytoplasmic ring. Fos is nuclear — expansion causes boundary errors. |
| `sigmaMicrons` | 1.5 | 1.5 | 1.5 | Gaussian smoothing; increase to 2.0 if nuclei fragment. Seed from BraiAn example. |
| `minAreaMicrons` | 30 | 30 | 30 | Mouse neuron nuclei ~5–8 µm diam. Adjust down to 20 if small cells missed, up to 50 to exclude debris. |
| `maxAreaMicrons` | 500 | 500 | 500 | Exclude glial clumps and merged nuclei. |
| `detectionsCheck.controlChannel` | — | `AF568-T2` | — | TdT has the cytoplasmic ring, so it is the containing cell object. All Fos detections must fall inside a TdT detection. |

### `detectionsCheck` logic

When `apply: true`, BraiAn checks that every detection in non-control channels (here, Fos/AF488-T3) is spatially contained within a detection in the `controlChannel` (here, TdTomato/AF568-T2). This enforces nucleus-anchored colocalization without proximity heuristics. Detections that fail the check are discarded or flagged, not counted as double+.

**Note:** `detectionsCheck` is BraiAn's colocalization guard. The OverlappingDetections class in the main script provides the actual double+ count.

## WatershedCellDetection — Raw `runPlugin` API (QuPath 0.6.x)

BraiAn calls this internally via `ChannelDetections`. For manual/one-off scripting, the raw form is:

```groovy
// Run detection on the current image, in all annotations
def detectionParams = [
    detectionImage: "DAPI-T4",
    requestedPixelSizeMicrons: 0.69,
    backgroundRadiusMicrons: 10.0,
    medianRadiusMicrons: 0.0,
    sigmaMicrons: 1.5,
    minAreaMicrons: 30.0,
    maxAreaMicrons: 500.0,
    threshold: 200.0,
    watershedPostProcess: true,
    cellExpansionMicrons: 0.0,
    includeNuclei: true,
    smoothBoundaries: true,
    makeMeasurements: true
]
runPlugin(
    'qupath.imagej.detect.cells.WatershedCellDetection',
    detectionParams
)
```

**QuPath 0.6.x note:** The `runPlugin` API accepting a `Map` is available in 0.6.x. Prefer BraiAn's `ChannelDetections` constructor over raw `runPlugin` for batch runs — it handles channel selection, parameter storage in the YAML, and consistent application across all project images.

## Main Detection Script

BraiAn ships a canonical script inside the jar at `scripts/compute_classify_overlap_export_exclude_detections.groovy`. Copy this script into the QuPath project `scripts/` directory and run it from the Script Editor (or via QuPath CLI for batch). It does, in order:

1. Reads `BraiAn.yml` (from project dir or parent)
2. For each `channelDetections` entry: runs `WatershedCellDetection` with YAML params
3. Applies classifiers per channel
4. Computes double+ (`OverlappingDetections`) using the control channel
5. Exports results to `<projectDir>/results/<imageName>_regions.tsv`
6. Exports excluded regions to `<projectDir>/regions_to_exclude/<imageName>_regions_to_exclude.txt`

```groovy
import qupath.ext.braian.AtlasManager
import qupath.ext.braian.OverlappingDetections
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.ChannelDetections
import qupath.ext.braian.config.ProjectsConfig
import static qupath.lib.scripting.QP.*

var imageData = getCurrentImageData()
var server = imageData.getServer()      // avoid in 0.6.x hot-path — makes scripts slow
var hierarchy = imageData.getHierarchy()
var config = ProjectsConfig.read("BraiAn.yml")
var annotations = config.getAnnotationsForDetections(hierarchy)

// 1. Detect per channel
var allDetections = config.channelDetections.collect { detectionsConf ->
    var channel = new ImageChannelTools(detectionsConf.name, server)
    try {
        new ChannelDetections(channel, annotations, detectionsConf.parameters, hierarchy)
    } catch (IllegalArgumentException ignored) { null }
}.findAll { it != null }

// 2. Classify
allDetections.forEach { detections ->
    var detectionsConfig = config.channelDetections
        .find { it.name == detections.getId() }
    if (detectionsConfig.classifiers == null) return
    var partialClassifiers = detectionsConfig.classifiers.collect { it.toPartialClassifier(hierarchy) }
    detections.applyClassifiers(partialClassifiers, imageData)
}

// 3. Double+ overlap
var overlaps = []
Optional<String> control
if ((control = config.getControlChannel()).isPresent()) {
    var controlChannel = allDetections.find { it.getId() == control.get() }
    var otherChannels  = allDetections.findAll { it.getId() != control.get() }
    overlaps = [new OverlappingDetections(controlChannel, otherChannels, true, hierarchy)]
}

// 4. Export
var atlasName = "allen_mouse_10um_java"
if (AtlasManager.isImported(atlasName, hierarchy)) {
    var atlas = new AtlasManager(atlasName, hierarchy)
    def imageName = getProjectEntry().getImageName()
        .replaceAll('[<>:"/\\\\|?*]', '')
    var resultsFile = new File(buildPathInProject("results", imageName + "_regions.tsv"))
    atlas.saveResults(allDetections + overlaps, resultsFile)
    def exclusionsFile = new File(buildPathInProject("regions_to_exclude", imageName + "_regions_to_exclude.txt"))
    atlas.fixExclusions()
    atlas.saveExcludedRegions(exclusionsFile)
}
println getCurrentImageName() + " : DONE!"
```

**QuPath 0.6.x performance note:** The comment in the shipped script warns explicitly: "unless explicitly needed, from QuPath 0.6.* avoid calling `imageData.getServer()`. It makes scripts considerably slower." Use `imageData.getHierarchy()` and `getCurrentImageData()` instead; only call `getServer()` once for `ImageChannelTools` initialization.

## Export File Format (BraiAn TSV)

### Per-image results file: `<projectDir>/results/<imageName>_regions.tsv`

Tab-separated. The braian Python library reads these via `BrainSlice.from_qupath()` — **this is the exact file/naming convention `braian.SlicedBrain.from_qupath(..., results_subdir='results', results_suffix='_regions.tsv')` expects by default (confirmed against the installed braian 1.0.5 package, §4 above)** — no QuPath-side naming change needed for v1.1's section→animal aggregation.

**Required columns (verified from braian Python library source):**

| Column | Type | Description |
|--------|------|-------------|
| `Name` | string | Atlas region annotation name (e.g. `"Root"`, `"CA1"`) |
| `Classification` | string | Region acronym with hemisphere: `"Left: CA1"`, `"Right: DG"` |
| `Num Detections` | int | Total detection count across all channels in this region |
| `Area um^2` | float | Region area in square microns |
| `Num <channelName>` | int | Per-channel detection count; one column per `channelDetections` entry |

**Example column set for TRAP2:**
```
Name  Classification  Num Detections  Area um^2  Num AF568-T2  Num AF488-T3  Num AF568-T2+AF488-T3
```

The `"Num AF568-T2+AF488-T3"` column is the double+ count from `OverlappingDetections`. The braian Python library maps these via `ch2marker`:

```python
ch2marker = {
    "AF568-T2": "TdTomato",
    "AF488-T3": "Fos",
}
# SlicedBrain.from_qupath(tsv_path, ch2marker, atlas="allen_mouse_10um_java")
```

### Exclusion file: `<projectDir>/regions_to_exclude/<imageName>_regions_to_exclude.txt`

Plain text, one region acronym per line. Regions to drop from braian Python analysis due to tissue damage or poor alignment.

## Atlas Coordinate Export (per-cell XYZ in Allen CCFv3 space)

BraiAn's `saveResults` exports **region-level counts**, not per-cell coordinates. For per-cell brainrender point clouds, add Atlas XYZ measurements to detections with this script (run after detection, before export):

```groovy
import net.imglib2.RealPoint
import qupath.lib.measurements.MeasurementList
import qupath.ext.biop.abba.AtlasTools
import static qupath.lib.gui.scripting.QPEx.*

def pixelToAtlasTransform =
    AtlasTools.getAtlasToPixelTransform(getCurrentImageData()).inverse()

getDetectionObjects().forEach { detection ->
    RealPoint atlasCoords = new RealPoint(3)
    MeasurementList ml = detection.getMeasurementList()
    atlasCoords.setPosition(
        [detection.getROI().getCentroidX(),
         detection.getROI().getCentroidY(), 0] as double[]
    )
    pixelToAtlasTransform.apply(atlasCoords, atlasCoords)
    ml.put("Atlas_X", atlasCoords.getDoublePosition(0))
    ml.put("Atlas_Y", atlasCoords.getDoublePosition(1))
    ml.put("Atlas_Z", atlasCoords.getDoublePosition(2))
}
fireHierarchyUpdate()
```

**Units:** `getCentroidX()` / `getCentroidY()` return **pixel** coordinates. The `AtlasTools` transform converts these to Allen CCFv3 coordinates in **mm** (the atlas is defined in µm/10 = 10 µm steps, but the transform output is typically in mm). Cross-check the brainrender import: `brainrender` expects CCFv3 coordinates in µm, so multiply by 1000 if the transform returns mm. (Confirmed consistent with the project's own `atlas_coords_mm_units.md` memory note: AtlasTools coords are mm, ×1000 for brainrender microns.)

**Alternative micron approach** — if you want image-space microns (not atlas space), convert directly:

```groovy
double pixelWidth  = server.getPixelCalibration().getPixelWidthMicrons()
double pixelHeight = server.getPixelCalibration().getPixelHeightMicrons()
// per detection:
double xMicrons = roi.getCentroidX() * pixelWidth
double yMicrons = roi.getCentroidY() * pixelHeight
```

The image-space microns are only useful for intra-section measurements; use atlas-transform coordinates for cross-section point clouds in brainrender.

## MeasurementExporter — Standard QuPath 0.6.x Export

For exporting the QuPath measurement table (shape + intensity measurements per cell, not region counts):

```groovy
import qupath.lib.gui.tools.MeasurementExporter
import qupath.lib.objects.PathCellObject

def project = getProject()
def imagesToExport = project.getImageList()
def outputFile = new File(buildPathInProject("export", "all_detections.tsv"))
outputFile.parentFile.mkdirs()

new MeasurementExporter()
    .imageList(imagesToExport)
    .separator("\t")
    .exportType(PathCellObject.class)     // PathDetectionObject.class for non-cell detections
    .exportMeasurements(outputFile)
```

**Default columns in the exported TSV** (shape measurements added by `makeMeasurements: true`):
- `Image`, `Name`, `Class`, `Parent`
- `Centroid X µm`, `Centroid Y µm` — image-space centroids in microns (uses OME-XML pixel calibration)
- `Area µm^2`, `Perimeter µm`, `Circularity`, `Max diameter µm`, `Min diameter µm`
- Per-channel intensity: `<ChannelName>: Nucleus: Mean`, `<ChannelName>: Cell: Mean`, `<ChannelName>: Cytoplasm: Mean`

`Centroid X µm` and `Centroid Y µm` are **image-space microns** (not atlas space). They are correct for inter-channel comparisons within a section but cannot be used directly for 3D atlas mapping.

## Auto-Threshold Helper (for threshold tuning)

BraiAn ships `scripts/find_threshold.groovy` for interactive histogram inspection:

```groovy
import qupath.ext.braian.ImageChannelTools
import qupath.ext.braian.config.AutoThresholdParmameters
import qupath.ext.braian.config.WatershedCellDetectionConfig
import static qupath.lib.scripting.QP.*

var server = getCurrentImageData().getServer()
var channel = new ImageChannelTools("AF568-T2", server)   // adjust channel name
var thresholder = new AutoThresholdParmameters()           // defaults: resLevel=4, smooth=15, prominence=100, nPeak=1
WatershedCellDetectionConfig.findThreshold(channel, thresholder)
// Prints found threshold to QuPath log
```

Use this interactively on a representative image section before committing a `histogramThreshold` block to BraiAn.yml.

## Classifier Setup

BraiAn applies classifiers from `project/classifiers/` or its parent directory. The classifier JSON files are created in QuPath's GUI (Train Object Classifier or Simple Threshold Classifier). For TRAP2:

- `TdTomato_classifier.json` — trained on AF568-T2 cytoplasmic intensity; classifies cells as `TdTomato` or background
- `Fos_classifier.json` — trained on AF488-T3 nuclear intensity; classifies as `Fos` or background

The class names `Fos` and `TdTomato` are already present in the M3 Hippocampus 20x 062926 3 plane project's `classifiers/classes.json`. These class names are what BraiAn uses in `ChannelClassifierConfig` and what the braian Python library receives in the TSV `Classification` column to identify double+ cells.

**Create classifiers via:** QuPath GUI → Objects → Classify → Train Object Classifier → Simple Threshold Classifier on channel intensity → Save. Name the file exactly as referenced in BraiAn.yml `classifiers.name` field.

## Batch Run Across Multiple Images

BraiAn ships `scripts/run_script_for_multiple_projects.groovy` for one-script-across-all-projects execution. For a single project with multiple images (a series), use QuPath's built-in batch runner: Script Editor → Run → Run for Project. All images in the current project are processed in sequence using the same `BraiAn.yml` parameters. **This is the mechanism v1.1 uses to run all 5 wBA1-3 sections through the same detection/classification config.**

## Key API Calls Reference

| Goal | Groovy call |
|------|-------------|
| Load ABBA atlas annotations | `AtlasTools.loadWarpedAtlasAnnotations(getCurrentImageData(), "acronym", true)` |
| Get all cell detections | `getCellObjects()` / `getDetectionObjects()` |
| Get annotations (atlas regions) | `getAnnotationObjects()` |
| Build path inside project | `buildPathInProject("results", imageName + "_regions.tsv")` |
| Get pixel calibration | `getCurrentImageData().getServer().getPixelCalibration().getPixelWidthMicrons()` |
| Get image hierarchy | `getCurrentImageData().getHierarchy()` |
| Get atlas→pixel transform | `AtlasTools.getAtlasToPixelTransform(getCurrentImageData())` |
| Check atlas imported | `AtlasManager.isImported("allen_mouse_10um_java", hierarchy)` |
| Save region results | `atlas.saveResults(allDetections + overlaps, resultsFile)` |
| Save excluded regions | `atlas.saveExcludedRegions(exclusionsFile)` |
| Read BraiAn config | `ProjectsConfig.read("BraiAn.yml")` |

## Critical Caveats (QuPath 0.6.x + BraiAnDetect 1.1.0)

1. **`getServer()` is slow in 0.6.x.** Call it once at script start, only when needed for `ImageChannelTools`. Do not call inside loops. The BraiAn script comment flags this explicitly.

2. **Channel names are case-sensitive and must match exactly.** BraiAn throws `IllegalChannelName` if the name in BraiAn.yml does not match the QuPath server channel name character-for-character. The names in this project are `AF568-T2`, `AF488-T3`, `DAPI-T4`.

3. **ABBA must be imported before running BraiAn detection.** `AtlasManager.isImported("allen_mouse_10um_java", hierarchy)` returns false if ABBA annotations have not been loaded; the export silently skips. Load atlas annotations via `Extensions > ABBA > Load Atlas Annotations` before running the detection script.

4. **`detectionsCheck` requires the control channel to be detected first.** BraiAn processes channels in YAML order. Place the control channel (`AF568-T2`) first or ensure it is detected before the others.

5. **Cytoplasmic expansion is the detection compartment for TdTomato.** Setting `cellExpansionMicrons: 0.0` on the TdT channel means TdT is measured in the nuclear compartment only — the DAPI nucleus. Because TdTomato is cytosolic, this would produce systematically low signal. The expansion ring is mandatory.

6. **braian Python `from_qupath` expects `"allen_mouse_10um_java"` as atlas name.** The atlas name string in the TSV header is set by BraiAn at export time from the QuPath ABBA atlas identifier. If the atlas name differs (e.g., `"allen_mouse_25um_java"`), the Python library's sanity check raises an `AssertionError`.

7. **Double+ count column name is `"Num AF568-T2+AF488-T3"`** (or whatever the channel names are, joined by `+`). The braian Python `_column_from_qupath_channel` function generates per-channel columns as `f"Num {channel}"`. The overlap column follows the same pattern with the two channel names concatenated with `+`.

## Sources (v1.0 appendix)

- BraiAn.yml canonical example: `https://raw.githubusercontent.com/carlocastoldi/qupath-extension-braian/master/BraiAn.yml`
- BraiAn extension README: `https://github.com/carlocastoldi/qupath-extension-braian`
- Bundled sample scripts: extracted from `/home/jflab/section-pipeline/tools/QuPath/extensions/catalogs/BraiAn catalog/QuPath BraiAn extension/v1.1.0/main-jar/qupath-extension-braian-1.1.0.jar`
- braian Python library source (installed): `/home/jflab/miniforge3/envs/braian/lib/python3.11/site-packages/braian/`
- ABBA atlas coordinate export script: `https://abba-documentation.readthedocs.io/en/latest/tutorial/4_qupath_analysis.html`
- QuPath 0.6.0 QP Javadoc: `https://qupath.github.io/javadoc/docs/qupath/lib/scripting/QP.html`
- QuPath project files verified on-disk: `project.qpproj` files in `/home/jflab/Analysis/`
- [WatershedCellDetection Javadoc (QuPath 0.6.0)](https://qupath.github.io/javadoc/docs/qupath/imagej/detect/cells/WatershedCellDetection.html)
- [MeasurementExporter usage (QuPath 0.5 docs)](https://qupath.readthedocs.io/en/0.5/docs/tutorials/exporting_measurements.html)
- [ABBA + QuPath cell detection Gist (NicoKiaru/BIOP)](https://gist.github.com/NicoKiaru/f45f56e3ff2d1fb708821c110fbdee62)
