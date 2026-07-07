# CLAUDE.md — Section Pipeline (TRAP2 / Airyscan)

Project memory for Claude Code. Read every session. Full install procedure lives in `SECTION_PIPELINE_SETUP.md` — this file is the durable rules-of-the-road, not the step list.

## What this project is
Turn ZEN-exported OME-TIFFs of **TRAP2 vibratome sections** (Zeiss Airyscan 2) into an **Allen CCFv3-registered** whole-brain map of cell densities: **TdTomato+** (encoding engram, cytosolic), **Fos+** (recall, nuclear), **double+** (reactivated). Tooling: QuPath → ABBA(Fiji)+elastix → BraiAn → brainrender. This is the **section** pipeline; it runs in parallel with the **cleared light-sheet / ClearMap2** project on a *different* machine ("engram"). Same biological question, two modalities — do not conflate the two codebases.

## This machine
Ubuntu 26.04 LTS · i9-9900K (8C/16T) · 61 GB RAM · 854 GB NVMe free · **Intel UHD 630 iGPU, NO NVIDIA/CUDA** · real display (`DISPLAY=:0`).

## Hard constraints — do not change without flagging to the user first
- **CPU-only everywhere.** No CUDA on this box. Detection (StarDist/Cellpose), DeepSlice, elastix all run on CPU. Do **not** install GPU/CUDA builds. Prefer **DeepSlice online** and **BraiAnDetect's built-in QuPath detection** over Cellpose for speed.
- **QuPath pinned to v0.6.0** (ABBA + BraiAn extensions are tested against 0.6.x via the BIOP catalog). Do not bump to 0.7.x without verifying catalog-extension compatibility.
- **elastix pinned to 5.2.0** (ABBA requires exactly this).
- **ABBA = Method 2** (standalone Fiji + `PTBIOP` update site). The Linux one-click installer does not exist; do not reach for `abba-python` (Method 3) unless a non-Allen BrainGlobe atlas is ever needed.
- **Three isolated conda envs** (`deepslice`, `braian`, `brainrender`), Python 3.11. Never merge them; brainrender is fragile with vedo/VTK/allensdk.
- **QuPath max memory = `-Xmx32G`.**
- **Do not install ZEN** — Airyscan processing stays on the Windows acquisition PC; this box only ingests OME-TIFFs.

## Agent behavior
- **Scriptable** (you do it): downloads, extraction, Miniforge, conda envs, pip installs, verification, and any analysis/visualization code.
- **GUI-only** (hand back to the human at the monitor, do not try to automate): Fiji `PTBIOP` update site, elastix path setting, QuPath catalog + extension install. These are clicks; surface the instructions and stop.
- If a step needs `sudo`, surface the exact command for the user to run rather than assuming privilege.

## Paths & entry points
```
$HOME/section-pipeline/tools/QuPath/bin/QuPath
$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64
$HOME/section-pipeline/tools/elastix/bin/{elastix,transformix}
conda activate braian      # whole-brain stats (BraiAnalyse) + jupyter lab
conda activate brainrender # 3D point cloud in Allen space
conda activate deepslice   # optional local DeepSlice (else use online)
```

## Analysis correctness rules (bake into every detection/registration script)
- **Nucleus-anchored colocalization only.** A cell is TdT+/Fos+/double+ iff the detected nucleus *contains* the marker centroid — never proximity/overlap heuristics.
- **DAPI nuclear / TdTomato cytosolic mismatch:** detect nuclei on DAPI, add a **cytoplasmic expansion ring** to measure TdTomato; classify Fos on the nuclear compartment. This is non-negotiable or TdT is mis/over-counted.
- **Export atlas coordinates in microns, not pixels** — otherwise the brainrender point cloud lands in the wrong place. ABBA's Allen atlas and brainrender's `allen_mouse` are both CCFv3; keep that consistent.
- **"3D" = atlas-space cell point cloud** (cells plotted in the Allen reference brain), **not** physical tissue reconstruction. Confirm scope with PI before attempting the latter.
- Detection starting parameters (threshold, min/max area, sigma, cytoplasmic expansion radius): seed from the F1000Research 2026 / bioRxiv 2024.09.16.611953 TRAP2 paper, then tune on ONE section before scaling to the series.

## Stats conventions for BraiAnalyse work
- **Aggregate to the animal level before any group comparison** — sections are not independent; never pseudoreplicate on section- or cell-level n.
- Report **effect sizes (Hedges' g)** alongside p-values; prefer **Welch's t-test** (unequal variance) for two-group region comparisons.
- Any animal/section exclusion must be **a priori and principled** — document the rule, not the outcome.
- Whole-brain multi-region testing: correct for multiple comparisons; let BraiAn's region-set tools drive the brain-wide difference detection.

## Status
- [x] Tools installed (QuPath v0.6.0, Fiji latest+jdk, elastix 5.2.0) — 2026-06-19
- [x] conda envs built (deepslice py3.10, braian py3.11, brainrender py3.11) — 2026-06-19
- [x] QuPath memory set to -Xmx32G — 2026-06-19
- [x] OpenGL verified hardware-accelerated (Mesa Intel UHD 630, direct rendering: Yes) — 2026-06-19
- [x] GUI config done (PTBIOP site, elastix paths, QuPath catalogs) — 2026-06-19
- [x] Test: ZEN export → QuPath import on ONE section — 2026-06-20 (M3 hippocampus ~+1.4mm bregma, 10x confocal, 3ch: DAPI/Ch0, Fos-488/Ch1, TdTomato-568/Ch2)
- [x] First registered section (DeepSlice + Affine + Spline, Allen CCFv3 regions loaded) — 2026-06-20
- [x] 20x CZI → MIP pipeline (czi_to_mip.py); channel fix: always pass --channels "TdTomato-AF568" "Fos-AF488" "DAPI" — 2026-06-22
- [x] 20x section ABBA registration — final workflow: DeepSlice → Review Mode manual angle adjust → export (no Affine/Spline; elastix degrades result due to no tissue mask) — 2026-06-23
- [ ] Detection params tuned on one section
- [ ] First registered series
_Update this block as the setup progresses._

## Notes from install (2026-06-19)
- Fiji new packaging: binary is `fiji-linux-x64` (not `ImageJ-linux64`); symlink created for back-compat.
- elastix requires `LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib` — added to `~/.bashrc`.
- DeepSlice env prefix for Fiji ABBA config: `/home/jflab/miniforge3/envs/deepslice`
