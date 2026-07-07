# Technology Stack

**Analysis Date:** 2026-06-30

## Languages

**Primary:**
- Python 3.11 — all analysis scripting (`braian`, `brainrender` conda envs)
- Groovy — QuPath automation scripts (`*.groovy` in project `scripts/` directories)

**Secondary:**
- Python 3.10 — DeepSlice local inference env (`deepslice` conda env)
- Java (bundled JRE) — QuPath 0.6.0 and Fiji runtimes; not directly authored

**Data / Config:**
- JSON — QuPath project files (`.qpproj`), classifier definitions, ABBA transform files
- XML — OME-TIFF metadata embedded as OME-XML (written by `czi_mip.py`)
- CSV — Landmark files for BigWarp registration (`landmarks.csv`)

## Runtime

**Environment:**
- Ubuntu 26.04 LTS, kernel 7.0.0, glibc 2.43, x86_64
- CPU-only: Intel i9-9900K 8C/16T, NO NVIDIA/CUDA; all computation is CPU-bound
- RAM: 61 GB; QuPath configured at `-Xmx32G`
- Display: `DISPLAY=:0` (real X session; interactive GUI tools work without xvfb)

**Package Manager:**
- Miniforge / conda 26.3.2 at `$HOME/miniforge3`
- Three isolated conda environments — never merge them (brainrender is fragile with vedo/VTK)
- No lockfiles present; installs done via `pip install` at env creation time

## Frameworks

**Core (Python):**
- `braian` 1.0.5 — whole-brain region statistics (BraiAnalyse); runs inside `braian` env
- `brainrender` 2.1.20 — 3D atlas-space point cloud visualization; runs inside `brainrender` env
- `DeepSlice` 1.2.8 — CNN-based section Z-position / angle estimation; runs inside `deepslice` env
- `brainglobe-atlasapi` 2.3.1 — programmatic access to Allen CCFv3 and other atlases (present in `braian` and `brainrender` envs)

**Image I/O:**
- `aicspylibczi` 3.3.1 — reads Zeiss CZI mosaic files (tile stitching + per-channel/Z access); used in `czi_mip.py`
- `tifffile` 2026.3.3 — writes OME-TIFF output with embedded OME-XML; used in `czi_mip.py`
- `imagecodecs` 2026.3.6 — compression backends for tifffile

**Scientific / Numerical:**
- `numpy` 2.1.3 (braian) / 2.4.6 (brainrender) / 2.2.6 (deepslice)
- `scipy` 1.17.1 (braian) / 1.15.3 (deepslice)
- `scikit-image` 0.26.0 (braian) / 0.25.2 (deepslice)
- `pandas` 2.3.3 (braian, deepslice)
- `matplotlib` 3.11.0 (braian)

**Deep Learning (deepslice env only):**
- `tensorflow` 2.21.0 — inference backend for DeepSlice CNN
- `keras` 3.12.2

**3D Visualization (brainrender env):**
- `vedo` 2026.6.1 — 3D rendering engine
- `vtk` 9.6.2 — underlying VTK backend

**Interactive Analysis:**
- JupyterLab 4.6.0 — notebook interface for BraiAnalyse; launched via `conda activate braian && jupyter lab`

**GUI Applications (binary installs, not conda):**
- QuPath v0.6.0 — primary cell detection and classification GUI; at `$HOME/section-pipeline/tools/QuPath/bin/QuPath`
- Fiji (latest) — ABBA registration GUI; at `$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64` (symlinked from `fiji-linux-x64`)

## Key Dependencies

**Critical (pin versions — do not bump without explicit verification):**
- QuPath v0.6.0 — ABBA and BraiAnDetect extensions tested only against 0.6.x; do not upgrade to 0.7.x without verifying BIOP catalog compatibility
- elastix 5.2.0 — ABBA requires exactly this version; at `$HOME/section-pipeline/tools/elastix/bin/elastix`
- `aicspylibczi` 3.3.1 — CZI channel order differs from metadata; a workaround is applied (see `feedback_channel_order.md`)

**QuPath Extensions (installed via BIOP catalog, GUI-only):**
- ABBA — section-to-atlas registration UI inside QuPath
- Image Combiner Warpy (`qupath.ext.warpy`) — transfers cell detections between registered image entries
- BraiAnDetect — consistent multichannel cell detection enforcing identical parameters across all sections

**QuPath Extension Catalogs:**
- `https://github.com/BIOP/qupath-biop-catalog`
- `https://github.com/carlocastoldi/qupath-extension-braian-catalog`

**Fiji Plugins (installed via PTBIOP update site, GUI-only):**
- ABBA plugin — full atlas-registration workflow (DeepSlice → Affine → Spline → BigWarp)
- BigWarp — landmark-based warping for manual refinement

## Configuration

**Environment variables:**
- `LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib` — required for elastix shared libraries; set in `~/.bashrc`
- `DISPLAY=:0` — X display for GUI tools

**QuPath memory:**
- `-Xmx32G` set in `$HOME/section-pipeline/tools/QuPath/lib/app/QuPath.cfg`

**Build / setup:**
- `SECTION_PIPELINE_SETUP (1).md` — full runbook for initial install
- `CLAUDE.md` — durable rules and constraints

## Platform Requirements

**Development & Production (same machine):**
- Ubuntu 26.04 LTS x86_64
- CPU-only; do NOT install CUDA or GPU builds of any library
- Real X display required for QuPath, Fiji/ABBA, and brainrender interactive sessions
- Internet access required on first registration (downloads Allen CCFv3 atlas ~1 GB via brainglobe-atlasapi)

**Input data (from Windows acquisition PC — not installed here):**
- Zeiss ZEN software handles Airyscan processing, tile stitching, z-projection, and OME-TIFF export
- Exported OME-TIFFs / CZI files are transferred to this Linux machine for all downstream processing

---

*Stack analysis: 2026-06-30*
