<!-- GSD:project-start source:PROJECT.md -->

## Project

**M3 Hippocampus Section Pipeline — First Run**

End-to-end TRAP2 cell classification pipeline for the first real section run: M3 hippocampus slices with Z-planes already MIP'd to OME-TIFF. Starting from existing MIP files, this project covers ABBA atlas registration in Fiji, BraiAnDetect parameter tuning in QuPath, TdTomato+/Fos+/Double+ classification per atlas region, and micron-coordinate export. This run serves double duty: validating biologically plausible cell counts and locking detection parameters for the full series.

**Core Value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region for M3 hippocampus, with locked detection parameters and imaging optimization notes ready for the full series.

### Constraints

- **CPU-only**: No CUDA on this box (Intel UHD 630 iGPU only) — all detection runs on i9-9900K cores
- **Version pins**: QuPath v0.6.0 (BIOP catalog), elastix 5.2.0 (ABBA requirement) — do not bump
- **Colocalization rule**: Nucleus-anchored only — detect DAPI nuclei, cytoplasmic ring for TdTomato, nuclear compartment for Fos; no proximity/overlap heuristics
- **Coordinate units**: Export in microns, not pixels — QuPath pixel calibration must be verified against OME-XML `PhysicalSizeX`
- **Stats convention**: Aggregate to animal level before any group comparison; no pseudoreplication on section- or cell-level n
- **No git installed**: Planning docs tracked locally only; git init blocked until git is installed

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.11 — all analysis scripting (`braian`, `brainrender` conda envs)
- Groovy — QuPath automation scripts (`*.groovy` in project `scripts/` directories)
- Python 3.10 — DeepSlice local inference env (`deepslice` conda env)
- Java (bundled JRE) — QuPath 0.6.0 and Fiji runtimes; not directly authored
- JSON — QuPath project files (`.qpproj`), classifier definitions, ABBA transform files
- XML — OME-TIFF metadata embedded as OME-XML (written by `czi_mip.py`)
- CSV — Landmark files for BigWarp registration (`landmarks.csv`)

## Runtime

- Ubuntu 26.04 LTS, kernel 7.0.0, glibc 2.43, x86_64
- CPU-only: Intel i9-9900K 8C/16T, NO NVIDIA/CUDA; all computation is CPU-bound
- RAM: 61 GB; QuPath configured at `-Xmx32G`
- Display: `DISPLAY=:0` (real X session; interactive GUI tools work without xvfb)
- Miniforge / conda 26.3.2 at `$HOME/miniforge3`
- Three isolated conda environments — never merge them (brainrender is fragile with vedo/VTK)
- No lockfiles present; installs done via `pip install` at env creation time

## Frameworks

- `braian` 1.0.5 — whole-brain region statistics (BraiAnalyse); runs inside `braian` env
- `brainrender` 2.1.20 — 3D atlas-space point cloud visualization; runs inside `brainrender` env
- `DeepSlice` 1.2.8 — CNN-based section Z-position / angle estimation; runs inside `deepslice` env
- `brainglobe-atlasapi` 2.3.1 — programmatic access to Allen CCFv3 and other atlases (present in `braian` and `brainrender` envs)
- `aicspylibczi` 3.3.1 — reads Zeiss CZI mosaic files (tile stitching + per-channel/Z access); used in `czi_mip.py`
- `tifffile` 2026.3.3 — writes OME-TIFF output with embedded OME-XML; used in `czi_mip.py`
- `imagecodecs` 2026.3.6 — compression backends for tifffile
- `numpy` 2.1.3 (braian) / 2.4.6 (brainrender) / 2.2.6 (deepslice)
- `scipy` 1.17.1 (braian) / 1.15.3 (deepslice)
- `scikit-image` 0.26.0 (braian) / 0.25.2 (deepslice)
- `pandas` 2.3.3 (braian, deepslice)
- `matplotlib` 3.11.0 (braian)
- `tensorflow` 2.21.0 — inference backend for DeepSlice CNN
- `keras` 3.12.2
- `vedo` 2026.6.1 — 3D rendering engine
- `vtk` 9.6.2 — underlying VTK backend
- JupyterLab 4.6.0 — notebook interface for BraiAnalyse; launched via `conda activate braian && jupyter lab`
- QuPath v0.6.0 — primary cell detection and classification GUI; at `$HOME/section-pipeline/tools/QuPath/bin/QuPath`
- Fiji (latest) — ABBA registration GUI; at `$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64` (symlinked from `fiji-linux-x64`)

## Key Dependencies

- QuPath v0.6.0 — ABBA and BraiAnDetect extensions tested only against 0.6.x; do not upgrade to 0.7.x without verifying BIOP catalog compatibility
- elastix 5.2.0 — ABBA requires exactly this version; at `$HOME/section-pipeline/tools/elastix/bin/elastix`
- `aicspylibczi` 3.3.1 — CZI channel order differs from metadata; a workaround is applied (see `feedback_channel_order.md`)
- ABBA — section-to-atlas registration UI inside QuPath
- Image Combiner Warpy (`qupath.ext.warpy`) — transfers cell detections between registered image entries
- BraiAnDetect — consistent multichannel cell detection enforcing identical parameters across all sections
- `https://github.com/BIOP/qupath-biop-catalog`
- `https://github.com/carlocastoldi/qupath-extension-braian-catalog`
- ABBA plugin — full atlas-registration workflow (DeepSlice → Affine → Spline → BigWarp)
- BigWarp — landmark-based warping for manual refinement

## Configuration

- `LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib` — required for elastix shared libraries; set in `~/.bashrc`
- `DISPLAY=:0` — X display for GUI tools
- `-Xmx32G` set in `$HOME/section-pipeline/tools/QuPath/lib/app/QuPath.cfg`
- `docs/SECTION_PIPELINE_SETUP.md` — full runbook for initial install
- `CLAUDE.md` — durable rules and constraints

## Platform Requirements

- Ubuntu 26.04 LTS x86_64
- CPU-only; do NOT install CUDA or GPU builds of any library
- Real X display required for QuPath, Fiji/ABBA, and brainrender interactive sessions
- Internet access required on first registration (downloads Allen CCFv3 atlas ~1 GB via brainglobe-atlasapi)
- Zeiss ZEN software handles Airyscan processing, tile stitching, z-projection, and OME-TIFF export
- Exported OME-TIFFs / CZI files are transferred to this Linux machine for all downstream processing

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Overview

## Languages in Use

- **Python 3.11** (primary): pipeline scripts in `/home/jflab/section-pipeline/scripts/`
- **Groovy** (QuPath scripting): QuPath automation scripts in `Automated Cell Counting Test/scripts/`
- **OME-XML** (embedded strings): channel/pixel metadata embedded directly in Python output code

## File Naming

- Python scripts: `snake_case.py` (e.g., `czi_to_mip.py`, `run_deepslice.py`)
- QuPath scripts: free-form with dates in name (e.g., `Test 062026 1.groovy`) — not yet standardised
- Output files: `{AnimalID}_{modality}_{MIP|step}.ome.tiff` (e.g., `M3_20x_MIP.ome.tiff`)
- QuPath projects: directory named after experiment + date (e.g., `M3 Hippocampus 20x 062226/`)

## Module-Level Structure

## Naming Patterns

- `snake_case` for all functions
- Private/internal helpers prefixed with `_` (e.g., `_get_pixel_size`, `_build_ome_xml`, `_print_info`)
- Public entry points: `main()`, `parse_args()`
- `snake_case` for local variables (e.g., `pixel_um`, `ch_names`, `mip_channels`)
- Short descriptive names for loop indices: `c` (channel), `z` (z-plane), `n_c`, `n_z`, `n_s`
- Constants in `UPPER_SNAKE_CASE` at module level when hardcoded (e.g., `F_IN`, `F_OUT`, `PIXEL_SIZE_UM` in the prototype `czi_mip.py`)
- Path variables use `Path` objects, not raw strings, in the canonical version (`czi_to_mip.py`)
- Used in function signatures in `czi_to_mip.py` and `run_deepslice.py`
- Pattern: `list[int] | None` (PEP 604 union syntax, requires `from __future__ import annotations`)
- Return types annotated for non-trivial functions: `-> tuple[np.ndarray, list[str], float]`

## Import Organization

## Docstrings

## Error Handling

## Progress / Logging

- Top-level steps: `print("Step name...")` — no indent
- Sub-steps: `print(f"  detail")` — 2-space indent
- Inner loop: `print(f"    inner")` — 4-space indent

## CLI Pattern

- `formatter_class=argparse.RawDescriptionHelpFormatter`
- `epilog=__doc__` (reuses module docstring as extended help)
- `type=Path` for file arguments
- Explicit `default=None` and helpful `help=` strings with units and defaults noted

## Path Handling

## Array / NumPy Conventions

- Canonical array dimension order: `(C, Y, X)` for MIP output
- Per-plane reads squeezed immediately: `.squeeze()` → `(Y, X)`
- Stack per channel then `np.stack(mip_channels, axis=0)` → `(C, Y, X)`
- Use `np.max(stack, axis=0)` for MIP (not `np.maximum.reduce`)
- Normalisation for 8-bit: percentile clip then cast: `np.clip(...).astype(np.uint8)`

## Groovy (QuPath) Conventions

- Javadoc-style header comments with `@author` tags
- Inline comments explain each logical step
- `println` for output (not `print`)
- `def` for all variable declarations

## Hardcoded Values vs. Arguments

## Biological Constants and Units

- Pixel size always in **µm** — variable named `pixel_um`; unit written `µm` (Unicode mu, not `um`)
- AP coordinates in **mm from bregma** (positive = anterior)
- Atlas coordinates in **µm** (CCFv3 space)
- Channel order in CZI files may not match metadata — always pass `--channels` override when known

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

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

- CPU-only throughout (no CUDA; Intel UHD 630 iGPU, no NVIDIA)
- Each stage is independently resumable from its output artifacts
- Atlas registration and cell detection are GUI-mediated (QuPath/Fiji); stats and visualization are script-mediated (Python)
- Three isolated conda environments prevent dependency conflicts between BraiAn, brainrender, and DeepSlice

## Layers

- Purpose: Raw data generation — Airyscan processing, Z-stack, tile stitching
- Location: Windows acquisition PC (ZEN Blue)
- Output: OME-TIFF files dropped into `/home/jflab/Analysis/`
- Depends on: Nothing on this machine
- Used by: CZI conversion or direct QuPath import
- Purpose: Stitch CZI mosaic tiles, max-project over Z, embed pixel calibration into OME-TIFF
- Location: `/home/jflab/Analysis/czi_mip.py`
- Contains: Python script (aicspylibczi, numpy, tifffile)
- Depends on: `braian` conda env
- Used by: QuPath (imports the MIP OME-TIFF as a project entry)
- Purpose: Map each 2D section image to its coronal position in Allen CCFv3
- Location: `$HOME/section-pipeline/tools/Fiji.app/` (ABBA plugin via PTBIOP update site)
- Contains: DeepSlice AP estimate → manual DV/ML tilt review → BigWarp landmark refinement
- Depends on: elastix 5.2.0 at `$HOME/section-pipeline/tools/elastix/`; `LD_LIBRARY_PATH` pointing to `…/elastix/lib`
- Used by: QuPath (reads `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` to create atlas-region annotations)
- Purpose: Segment nuclei (DAPI), expand to cytoplasm (TdTomato), classify TdT+/Fos+/Double+/Negative
- Location: QuPath (`$HOME/section-pipeline/tools/QuPath/bin/QuPath`) with BraiAnDetect and ABBA extensions
- Contains: QuPath project directories under `/home/jflab/Analysis/`
- Depends on: MIP OME-TIFF; ABBA-RoiSet for region labeling; `classifiers/object_classifiers/*.json`
- Used by: BraiAnalyse (reads exported cell tables)
- Purpose: Aggregate cell counts to animal level, run region-level comparisons
- Location: `braian` conda env; BraiAnalyse Python library; JupyterLab notebooks (not yet present)
- Depends on: Exported cell data (coordinates in microns) from QuPath
- Used by: Visualization layer
- Purpose: 3D atlas-space point cloud of classified cells in Allen CCFv3 reference brain
- Location: `brainrender` conda env
- Depends on: Cell coordinates in microns (CCFv3); `allen_mouse` atlas built into brainrender
- Used by: Final figures / PI presentations

## Data Flow

### Primary Section Processing Path

### CZI MIP Conversion Detail

- No shared in-memory state between stages
- All inter-stage state is on disk: OME-TIFF files, QuPath project `.qpproj` + `data/` tree, conda environments
- QuPath project `data/<entry>/` directory is the canonical per-section state store

## Key Abstractions

- Purpose: Represents one registered section image with all its objects, transforms, and region annotations
- Examples: `Automated Cell Counting Test/data/1/`, `M3 Hippocampus 20x 062226/data/1/`
- Pattern: Directory contains `server.json` (image URI), `data.qpdata` (PathObjects), `summary.json` (counts), `ABBA-Transform-*.json` (registration), `ABBA-RoiSet-*.zip` (region polygons)
- Purpose: Maps pixel coordinates in the section image to Allen CCFv3 atlas coordinates (and inverse)
- Examples: `Automated Cell Counting Test/data/1/ABBA-Transform-allen_mouse_10um_java.json`
- Pattern: JSON sequence of up to 8 transforms — AffineTransform3D followed by BoundedRealTransform (ThinplateSplineTransform); consumed by QuPath ABBA extension to warp atlas ROIs into image space
- Purpose: Single-measurement threshold rule applied to all detected cells to assign TdT+ or Fos+ class
- Examples: `Automated Cell Counting Test/classifiers/object_classifiers/TdT_classifier.json`, `Fos_Classifier.json`
- Pattern: `SimpleClassifier` → `ClassifyByMeasurementFunction` — one channel mean measurement, one numeric threshold, two output classes (Positive/Negative or Other/Negative)
- Purpose: Single-plane, multi-channel image suitable for QuPath import and ABBA registration
- Examples: `Automated Cell Counting/M3_20x_MIP.ome.tiff`, `M3 Hippocampus 20x 062226/M3_20x_MIP.ome.tiff`
- Pattern: (C, Y, X) uint16 array; OME-XML description carries physical pixel size in µm; produced by `czi_mip.py` or ZEN Blue export

## Entry Points

- Location: `/home/jflab/Analysis/czi_mip.py`
- Triggers: `conda run -n braian python3 /home/jflab/Analysis/czi_mip.py` (paths hardcoded; edit `F_IN`, `F_OUT`, `PIXEL_SIZE_UM` at top of script)
- Responsibilities: Open CZI mosaic, stitch tiles, max-project Z, write MIP OME-TIFF with calibration metadata
- Location: `$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64` (symlink) or `fiji-linux-x64`
- Triggers: Human launches Fiji; `Plugins > BIOP > Atlas > ABBA`
- Responsibilities: Load sections, run DeepSlice, adjust tilt manually, BigWarp refinement, export transform + ROI files to QuPath project
- Location: `$HOME/section-pipeline/tools/QuPath/bin/QuPath`
- Triggers: Human opens QuPath project
- Responsibilities: Import MIP OME-TIFF, load ABBA ROIs, run BraiAnDetect, apply classifiers, produce per-region cell counts
- Location: `conda activate braian && jupyter lab`
- Triggers: Human launches JupyterLab
- Responsibilities: Read exported cell tables, aggregate per animal, run BraiAnalyse whole-brain stats
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

### Pseudoreplication on section-level counts

### Exporting pixel coordinates instead of micron coordinates

### Elastix spline registration without tissue mask

## Error Handling

- `czi_mip.py` prints per-channel, per-Z progress to stdout; shape/dtype printed at each Z-plane to catch read failures early
- ABBA registration quality is verified visually before export (atlas region boundaries must fit tissue boundaries)
- QuPath `summary.json` persists detection counts after each classification run — serves as a manual audit checkpoint
- Groovy scripts (`scripts/*.groovy`) log warnings to QuPath's logger for multi-candidate source entries

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
