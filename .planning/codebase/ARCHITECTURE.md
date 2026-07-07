<!-- refreshed: 2026-06-30 -->
# Architecture

**Analysis Date:** 2026-06-30

## System Overview

```text
┌─────────────────────────────────────────────────────────────────────┐
│  ACQUISITION (off-machine, Windows PC)                              │
│  ZEN Blue — Airyscan processing, tile stitching, OME-TIFF export   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ OME-TIFF (3-channel: DAPI/Fos/TdTom)
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1: CZI → MIP CONVERSION  (optional; for raw CZI input)      │
│  `czi_mip.py`  (conda: braian)                                      │
│  aicspylibczi + numpy + tifffile                                    │
│  Input:  .czi mosaic  →  Output: CYX OME-TIFF with pixel metadata  │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ MIP OME-TIFF
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 2: ATLAS REGISTRATION  (GUI — Fiji + ABBA)                  │
│  `$HOME/section-pipeline/tools/Fiji.app/`                          │
│  DeepSlice → Manual angle review → BigWarp                         │
│  Outputs: ABBA-Transform-*.json + ABBA-RoiSet-*.zip               │
│  stored in QuPath project: `<project>/data/<entry>/`               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Atlas transform + region ROIs
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 3: CELL DETECTION & CLASSIFICATION  (GUI — QuPath)          │
│  `$HOME/section-pipeline/tools/QuPath/bin/QuPath`                  │
│  BraiAnDetect extension — DAPI nuclear segmentation +              │
│  cytoplasmic expansion ring for TdTomato channel                   │
│  Classifiers: `<project>/classifiers/object_classifiers/*.json`    │
│  Outputs: TdT+, Fos+, Double+, Negative per nucleus per region    │
│  Optional Groovy scripts: `<project>/scripts/*.groovy`             │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Cell coordinates + atlas region labels
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 4: WHOLE-BRAIN STATISTICS  (conda: braian + jupyter)        │
│  BraiAnalyse Python library                                         │
│  Aggregate to animal level → Welch's t-test + Hedges' g            │
│  Multi-region multiple-comparison correction via BraiAn tools      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ Region-level density tables
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 5: 3D VISUALIZATION  (conda: brainrender)                   │
│  brainrender — Allen CCFv3 point cloud                              │
│  Cell coordinates (microns) → atlas-space scatter plot             │
└─────────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File / Location |
|-----------|----------------|-----------------|
| `czi_mip.py` | Convert multi-scene CZI mosaic to MIP OME-TIFF | `/home/jflab/Analysis/czi_mip.py` |
| QuPath project | Holds image entries, atlas transforms, classifiers, and detection data | `<project>/project.qpproj` |
| ABBA (Fiji) | Register section image to Allen CCFv3; produce per-image transform JSON | `$HOME/section-pipeline/tools/Fiji.app/` |
| `ABBA-Transform-*.json` | Invertible real-transform sequence (Affine3D + ThinplateSpline) for each registered section | `<project>/data/<entry>/ABBA-Transform-allen_mouse_10um_java.json` |
| `ABBA-RoiSet-*.zip` | Atlas region ROIs transferred to image pixel space | `<project>/data/<entry>/ABBA-RoiSet-allen_mouse_10um_java.zip` |
| `server.json` | QuPath image server spec (BioFormats URI, channel metadata, pyramid levels) | `<project>/data/<entry>/server.json` |
| `summary.json` | Detection summary: object counts by type and class per atlas region | `<project>/data/<entry>/summary.json` |
| `data.qpdata` | QuPath binary object store: all PathObjects (annotations + cells) for the entry | `<project>/data/<entry>/data.qpdata` |
| Object classifiers | Single-measurement threshold classifiers (Positive/Negative) per marker | `<project>/classifiers/object_classifiers/*.json` |
| Groovy scripts | Warpy-based object transfer between registered images | `<project>/scripts/*.groovy` |
| `braian` conda env | BraiAnalyse stats library + JupyterLab; also used to run `czi_mip.py` | `$HOME/miniforge3/envs/braian` |
| `brainrender` conda env | 3D atlas-space point cloud rendering | `$HOME/miniforge3/envs/brainrender` |
| `deepslice` conda env | Optional local DeepSlice for AP-position estimation | `$HOME/miniforge3/envs/deepslice` |

## Pattern Overview

**Overall:** Linear ETL pipeline — each stage produces file artifacts consumed by the next. No shared in-memory state between stages. GUI tools (QuPath, Fiji/ABBA) persist state to project directories on disk.

**Key Characteristics:**
- CPU-only throughout (no CUDA; Intel UHD 630 iGPU, no NVIDIA)
- Each stage is independently resumable from its output artifacts
- Atlas registration and cell detection are GUI-mediated (QuPath/Fiji); stats and visualization are script-mediated (Python)
- Three isolated conda environments prevent dependency conflicts between BraiAn, brainrender, and DeepSlice

## Layers

**Acquisition Layer (off-machine):**
- Purpose: Raw data generation — Airyscan processing, Z-stack, tile stitching
- Location: Windows acquisition PC (ZEN Blue)
- Output: OME-TIFF files dropped into `/home/jflab/Analysis/`
- Depends on: Nothing on this machine
- Used by: CZI conversion or direct QuPath import

**Format Conversion Layer:**
- Purpose: Stitch CZI mosaic tiles, max-project over Z, embed pixel calibration into OME-TIFF
- Location: `/home/jflab/Analysis/czi_mip.py`
- Contains: Python script (aicspylibczi, numpy, tifffile)
- Depends on: `braian` conda env
- Used by: QuPath (imports the MIP OME-TIFF as a project entry)

**Registration Layer:**
- Purpose: Map each 2D section image to its coronal position in Allen CCFv3
- Location: `$HOME/section-pipeline/tools/Fiji.app/` (ABBA plugin via PTBIOP update site)
- Contains: DeepSlice AP estimate → manual DV/ML tilt review → BigWarp landmark refinement
- Depends on: elastix 5.2.0 at `$HOME/section-pipeline/tools/elastix/`; `LD_LIBRARY_PATH` pointing to `…/elastix/lib`
- Used by: QuPath (reads `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` to create atlas-region annotations)

**Detection & Classification Layer:**
- Purpose: Segment nuclei (DAPI), expand to cytoplasm (TdTomato), classify TdT+/Fos+/Double+/Negative
- Location: QuPath (`$HOME/section-pipeline/tools/QuPath/bin/QuPath`) with BraiAnDetect and ABBA extensions
- Contains: QuPath project directories under `/home/jflab/Analysis/`
- Depends on: MIP OME-TIFF; ABBA-RoiSet for region labeling; `classifiers/object_classifiers/*.json`
- Used by: BraiAnalyse (reads exported cell tables)

**Statistics Layer:**
- Purpose: Aggregate cell counts to animal level, run region-level comparisons
- Location: `braian` conda env; BraiAnalyse Python library; JupyterLab notebooks (not yet present)
- Depends on: Exported cell data (coordinates in microns) from QuPath
- Used by: Visualization layer

**Visualization Layer:**
- Purpose: 3D atlas-space point cloud of classified cells in Allen CCFv3 reference brain
- Location: `brainrender` conda env
- Depends on: Cell coordinates in microns (CCFv3); `allen_mouse` atlas built into brainrender
- Used by: Final figures / PI presentations

## Data Flow

### Primary Section Processing Path

1. ZEN Blue exports OME-TIFF (acquisition PC) — deposited to `/home/jflab/Analysis/`
2. If input is raw CZI: run `czi_mip.py` (`conda run -n braian python3 /home/jflab/Analysis/czi_mip.py`) to produce MIP OME-TIFF
3. Import MIP OME-TIFF into a QuPath project (BioFormats; `server.json` records URI + channel metadata)
4. Register section in ABBA (Fiji): DeepSlice → manual angle review → BigWarp; export produces `ABBA-Transform-allen_mouse_10um_java.json` + `ABBA-RoiSet-allen_mouse_10um_java.zip` in `<project>/data/<entry>/`
5. In QuPath: load ABBA ROIs as annotations; run BraiAnDetect (DAPI nuclear segmentation + cytoplasmic expansion); apply `TdT_classifier.json` and `Fos_Classifier.json`; resulting `data.qpdata` holds all PathObjects; `summary.json` tallies per-region counts
6. Export cell coordinates (microns, not pixels) for BraiAnalyse stats
7. `conda activate braian` → JupyterLab → BraiAnalyse: aggregate per animal, Welch's t-test, Hedges' g, multiple-comparison correction
8. `conda activate brainrender` → `allen_mouse` atlas scene → scatter cells by CCFv3 coordinate

### CZI MIP Conversion Detail

1. Open CZI with `aicspylibczi.CziFile` — detects mosaic, scenes, channels, Z-planes
2. Per channel: iterate Z-planes, call `read_mosaic(C=c, Z=z, scale_factor=1.0)` to stitch tiles
3. `np.max(stack, axis=0)` produces (Y, X) MIP per channel
4. Stack channels → (C, Y, X); embed `PIXEL_SIZE_UM` in hand-built OME-XML description
5. Write with `tifffile.imwrite(..., description=ome_xml.encode())`

**State Management:**
- No shared in-memory state between stages
- All inter-stage state is on disk: OME-TIFF files, QuPath project `.qpproj` + `data/` tree, conda environments
- QuPath project `data/<entry>/` directory is the canonical per-section state store

## Key Abstractions

**QuPath Project Entry:**
- Purpose: Represents one registered section image with all its objects, transforms, and region annotations
- Examples: `Automated Cell Counting Test/data/1/`, `M3 Hippocampus 20x 062226/data/1/`
- Pattern: Directory contains `server.json` (image URI), `data.qpdata` (PathObjects), `summary.json` (counts), `ABBA-Transform-*.json` (registration), `ABBA-RoiSet-*.zip` (region polygons)

**ABBA Transform (InvertibleRealTransformSequence):**
- Purpose: Maps pixel coordinates in the section image to Allen CCFv3 atlas coordinates (and inverse)
- Examples: `Automated Cell Counting Test/data/1/ABBA-Transform-allen_mouse_10um_java.json`
- Pattern: JSON sequence of up to 8 transforms — AffineTransform3D followed by BoundedRealTransform (ThinplateSplineTransform); consumed by QuPath ABBA extension to warp atlas ROIs into image space

**Object Classifier:**
- Purpose: Single-measurement threshold rule applied to all detected cells to assign TdT+ or Fos+ class
- Examples: `Automated Cell Counting Test/classifiers/object_classifiers/TdT_classifier.json`, `Fos_Classifier.json`
- Pattern: `SimpleClassifier` → `ClassifyByMeasurementFunction` — one channel mean measurement, one numeric threshold, two output classes (Positive/Negative or Other/Negative)

**MIP OME-TIFF:**
- Purpose: Single-plane, multi-channel image suitable for QuPath import and ABBA registration
- Examples: `Automated Cell Counting/M3_20x_MIP.ome.tiff`, `M3 Hippocampus 20x 062226/M3_20x_MIP.ome.tiff`
- Pattern: (C, Y, X) uint16 array; OME-XML description carries physical pixel size in µm; produced by `czi_mip.py` or ZEN Blue export

## Entry Points

**CZI to MIP Conversion:**
- Location: `/home/jflab/Analysis/czi_mip.py`
- Triggers: `conda run -n braian python3 /home/jflab/Analysis/czi_mip.py` (paths hardcoded; edit `F_IN`, `F_OUT`, `PIXEL_SIZE_UM` at top of script)
- Responsibilities: Open CZI mosaic, stitch tiles, max-project Z, write MIP OME-TIFF with calibration metadata

**Atlas Registration:**
- Location: `$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64` (symlink) or `fiji-linux-x64`
- Triggers: Human launches Fiji; `Plugins > BIOP > Atlas > ABBA`
- Responsibilities: Load sections, run DeepSlice, adjust tilt manually, BigWarp refinement, export transform + ROI files to QuPath project

**Cell Detection & Classification:**
- Location: `$HOME/section-pipeline/tools/QuPath/bin/QuPath`
- Triggers: Human opens QuPath project
- Responsibilities: Import MIP OME-TIFF, load ABBA ROIs, run BraiAnDetect, apply classifiers, produce per-region cell counts

**Statistics:**
- Location: `conda activate braian && jupyter lab`
- Triggers: Human launches JupyterLab
- Responsibilities: Read exported cell tables, aggregate per animal, run BraiAnalyse whole-brain stats

**3D Visualization:**
- Location: `conda activate brainrender && python <render_script>.py`
- Triggers: Human runs script
- Responsibilities: Render classified cell coordinates in Allen CCFv3 reference space

## Architectural Constraints

- **CPU-only:** No CUDA anywhere. Detection (StarDist/Cellpose/BraiAnDetect), DeepSlice, elastix all run on Intel i9-9900K cores. Do not install GPU/CUDA builds.
- **Version pins:** QuPath v0.6.0 (BIOP catalog compatibility), elastix 5.2.0 (ABBA requirement). Do not upgrade without verifying extension compatibility.
- **LD_LIBRARY_PATH:** elastix requires `export LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib:$LD_LIBRARY_PATH` (set in `~/.bashrc`).
- **Isolated conda envs:** `deepslice` (Python 3.10), `braian` (Python 3.11), `brainrender` (Python 3.11) — never merge; brainrender is fragile with vedo/VTK/allensdk.
- **QuPath max memory:** `-Xmx32G` (set in `$HOME/section-pipeline/tools/QuPath/lib/app/QuPath.cfg`)
- **No global state:** Each QuPath project is self-contained; the Python scripts are standalone; no database or shared service.
- **Coordinate units:** Coordinates must be exported in microns (not pixels) from QuPath/ABBA. Both ABBA's Allen CCFv3 and brainrender's `allen_mouse` are in CCFv3 micron space.

## Anti-Patterns

### Proximity-based colocalization

**What happens:** Classifying a cell as TdT+/Fos+/Double+ based on overlap or distance between marker signals rather than nucleus containment.
**Why it's wrong:** TdTomato is cytosolic and Fos is nuclear; proximity heuristics over- or under-count. The detected nucleus must *contain* the marker centroid.
**Do this instead:** Detect nuclei on DAPI; add cytoplasmic expansion ring in BraiAnDetect for TdTomato measurement; classify Fos within the nuclear compartment only. See `classifiers/object_classifiers/TdT_classifier.json` — threshold on `Nucleus: Cy3-T1 mean` (nuclear measurement), not a proximity measure.

### Pseudoreplication on section-level counts

**What happens:** Treating each section (or each cell) as an independent replicate in statistical comparisons between groups.
**Why it's wrong:** Sections from the same animal are not independent; inflates n and produces spurious significance.
**Do this instead:** Aggregate cell density (cells / mm²) to the animal level first; use animal as the unit of replication in all BraiAnalyse group comparisons.

### Exporting pixel coordinates instead of micron coordinates

**What happens:** Exporting cell X/Y in pixel units from QuPath instead of calibrated micron units before passing to brainrender.
**Why it's wrong:** The Allen CCFv3 atlas uses micron coordinates; pixel coordinates at 20x/0.8 (0.69 µm/px) will land cells in entirely wrong atlas positions.
**Do this instead:** Confirm QuPath export uses the physical pixel calibration (`pixelCalibration` in `server.json`); verify against the `PhysicalSizeX` in the MIP OME-TIFF header.

### Elastix spline registration without tissue mask

**What happens:** Running ABBA's Affine+Spline registration (elastix) on sections without a tissue mask.
**Why it's wrong:** Elastix degrades the result when background pixels dominate the optimization — observed on 20x sections (see CLAUDE.md status block 2026-06-23).
**Do this instead:** Final registration workflow is DeepSlice → Review Mode manual angle adjust → export (no Affine/Spline unless a tissue mask is available).

## Error Handling

**Strategy:** No automated error recovery. Each stage is manually supervised. Failures surface as visible artifacts in GUI tools (misaligned atlas overlay in QuPath) or as Python tracebacks printed to terminal.

**Patterns:**
- `czi_mip.py` prints per-channel, per-Z progress to stdout; shape/dtype printed at each Z-plane to catch read failures early
- ABBA registration quality is verified visually before export (atlas region boundaries must fit tissue boundaries)
- QuPath `summary.json` persists detection counts after each classification run — serves as a manual audit checkpoint
- Groovy scripts (`scripts/*.groovy`) log warnings to QuPath's logger for multi-candidate source entries

## Cross-Cutting Concerns

**Logging:** Stdout print statements in `czi_mip.py`; QuPath logger in Groovy scripts; no centralized log file.
**Validation:** Manual visual inspection at each stage (ZEN export → MIP → ABBA overlay → QuPath detection overlay → classified cell overlay).
**Authentication:** None — all tools run locally; no cloud services (DeepSlice online is optional and requires no auth key for the web API).

---

*Architecture analysis: 2026-06-30*
