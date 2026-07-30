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

## Evidence hierarchy — WHAT THE OPERATOR SEES OUTRANKS WHAT WE EXPECTED (2026-07-30)

When an observation and an expectation disagree, **the observation wins.** Rank evidence:

1. **SEEN** — what the operator observes on the actual image with detections overlaid.
   Highest authority, always. If the operator says TdT+ cells are being missed, they are
   being missed, regardless of what any band, seed value, or reference paper says.
2. **STRUCTURAL** — facts true regardless of acquisition, stain, or microscope (ventricles
   are CSF-filled and near-empty; white matter is sparsely nucleated relative to cortex).
   Violating one of these is a real defect, not a threshold-tuning preference.
3. **ASSUMED** — bands and seeds carried in from another acquisition or a paper, never
   validated against hand counts on our own images. **Informative, never authoritative.**
   A deviation here is a prompt to go and LOOK, not a verdict that the data is wrong.

Every QC gate in `scripts/cockpit_checks.py` is tagged with its tier and prints it
(`<anatomical>` / `<internal>` / `<assumed>`). Consequences that are binding:

- **Never tune a parameter to move an ASSUMED number into its expected band.** Tune only
  to match what is visible on the image. If the numbers then sit outside a borrowed band,
  that is a fact about the band, not a problem with the run.
- **Never tell the operator their observation conflicts with an expected value as though
  the expected value settles it.** Report the disagreement, name the tier, and defer.
- When a seed or band is cited anywhere, say where it came from and whether it was ever
  checked on our data. An unattributed number reads as authority it has not earned.
- Values marked `[ASSUMED]` in `pipeline.yml`/`BraiAn.yml` are tier-3 by definition.

## Analysis correctness rules (bake into every detection/registration script)
- **Nucleus-anchored colocalization only.** A cell is TdT+/Fos+/double+ iff the detected nucleus *contains* the marker centroid — never proximity/overlap heuristics.
- **DAPI-nucleus-anchored detection; whole-cell TdTomato measurement (REVISED 2026-07-25):** detect nuclei on DAPI (unchanged — still nucleus-anchored, no proximity/overlap heuristics). Measure TdTomato on the **whole cell** (nucleus + cytoplasmic expansion ring), QuPath's area-weighted whole-cell mean — the operator confirmed (2026-07-25) TdTomato fills the whole cell in this line/prep, so ring-only measurement under-counts it. This revises the former "cytoplasmic-ring-only, non-negotiable" wording; the **cytoplasmic-ring compartment remains available** (config option, `compartment: cytoplasmic`) for any future strictly-cytosolic marker. Classify Fos on the nuclear compartment (unchanged).
- **Export atlas coordinates in microns, not pixels** — otherwise the brainrender point cloud lands in the wrong place. ABBA's Allen atlas and brainrender's `allen_mouse` are both CCFv3; keep that consistent.
- **"3D" = atlas-space cell point cloud** (cells plotted in the Allen reference brain), **not** physical tissue reconstruction. Confirm scope with PI before attempting the latter.
- Detection starting parameters (threshold, min/max area, sigma, cytoplasmic expansion radius): seed from the F1000Research 2026 / bioRxiv 2024.09.16.611953 TRAP2 paper, then tune on ONE section before scaling to the series.
- **Detection threshold must be RELATIVE, never absolute (2026-07-29).** The anchor-channel cut is `floor + span_frac * (bright_peak - floor)`, with both endpoints re-measured from *each section's own* histogram by `run_braian_detection.groovy`; `span_frac` lives in `pipeline.yml` (`detection_threshold`). BraiAn.yml's own `threshold:` / `histogramThreshold:` are ignored for the anchor channel. Rationale: `histogramThreshold` needs a dim-nuclei peak this data does not have, and an absolute cut (the former `threshold: 700`) silently under-detects on any section dimmer than the one it was tuned on — a comparability bug, not a preference. Inspect placement in `notebooks/01_calibrate.ipynb` §3 before changing `span_frac`.
- **Pixel size comes from the CZI, never a default.** `czi_mip.py` reads `Scaling/Items/Distance` and stamps it into the OME-XML; every micron-denominated detection parameter is scaled by that number downstream. `--pixel-um` overrides explicitly and reports disagreement.
- **One classification path.** Marker classification happens only in `02_detect_classify.groovy` from `pipeline.yml`. Every project's `BraiAn.yml` `classifiers:` block is empty by design — do not repopulate it, or classification silently happens twice by two different rules.

## Comparability boundary — one acquisition regime per comparison (2026-07-30)

The self-calibrating thresholds (`span_frac` for the anchor cut, `k_robust` for marker
positivity) rescale with the data, so they absorb **overall brightness drift** — staining,
laser power, exposure. That is what makes sections within a run comparable, and it works:
M3 Hipp1 cut at 688, M3 Hipp2 at 798, same `span_frac`.

They do **not** absorb changes in **separability or geometry**:
- SNR changes — `k` is in robust SDs of the population; a narrower background distribution
  moves the cut relative to the actual biological populations, calling a different fraction
- saturation/clipping — changes histogram *shape*, not just scale
- pixel size, Z-slab depth, projection method — change what a cell physically *is*, so
  area/expansion params do not carry
- spatially-structured artifacts (e.g. per-tile shading gradients)

**Consequence, binding:** animals acquired under different imaging parameters are NOT
directly comparable, and `k`/`span_frac` tuned on one regime do not transfer to another.
Group comparisons require one settled acquisition regime across every animal in the
comparison — otherwise imaging is confounded with biology, and the confound sits in the
same direction as the effect. Record the acquisition regime alongside any reported number,
and state the `k` it was measured at (**operator, 2026-07-30**: imaging parameters are still
being tuned, so cross-run numbers to date are methods validation, not cohort data).

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
- [x] 20x CZI → MIP pipeline (`czi_mip.py`, repo root — there is no `czi_to_mip.py`); channel names are `AF568-T2` (TdTomato) / `AF488-T3` (Fos) / `DAPI-T4`; pass `--channels` in physical read order (aicspylibczi order ≠ metadata order) — 2026-06-22, corrected 2026-07-29
- [x] 20x section ABBA registration — **CURRENT WORKFLOW (revised 2026-07-30, operator, M3
      Hipp2 all 6 sections): fully manual after DeepSlice.**
      DeepSlice → Review/positioning mode (position + tilt) → **Affine tab: match the slice to
      the overlay BY HAND** (angle, X, Y, scale) → **Spline tab: manual BigWarp** to finalize →
      export. Match against the **Label Borders** overlay: you are aligning boundaries by eye.
      **elastix is NO LONGER in the chain.** This reverses the 2026-07-20 REG-05 "KEEP elastix
      Affine+Spline" decision, under that decision's own quality-first / time-irrelevant rule.
      If elastix is ever used again, its fixed channel must be atlas **Nissl (Ch0)**, never
      Label Borders — an intensity optimizer needs intensity correspondence, which is precisely
      why the human-facing overlay choice is the opposite one. Section moving channel = DAPI,
      index **2** in these 3-channel MIPs.
- [x] First registered series + animal-level readout (wBA1-3, LA/BA amygdala) — 2026-07-23
- [x] Generalization pass — 2026-07-29:
      - self-calibrating relative detection threshold (`detection_threshold` in `pipeline.yml`), replacing absolute `threshold: 700`
      - `scripts/calibrate_threshold.groovy` (read-only) + `scripts/cockpit_threshold.py` (histogram / sweep / series plots) + notebook §3
      - `scripts/sync_project.py` — repo `scripts/` is SOURCE, project `scripts/` is DEPLOYED; retires stale copies, merges missing config blocks without touching project values
      - pixel size read from CZI metadata, not defaulted
      - one classification path (legacy `BraiAn.yml` `classifiers:` blocks emptied)
      - unregistered QuPath entries now skipped loudly instead of silently entering a batch run
      - archived: TRACR, cohort 1, Automated Cell Counting Test, 062226 Redo, 11 dead classifier JSONs
- [ ] Detection params re-tuned against hand counts (over-segmentation open — see `.planning/codebase/TESTING.md` gaps)
- [ ] Minimum-viable acquisition validated (see `IMAGING-MINIMUM-VIABLE-ACQUISITION.md`)
_Update this block as the setup progresses._

## Notes from install (2026-06-19)
- Fiji new packaging: binary is `fiji-linux-x64` (not `ImageJ-linux64`); symlink created for back-compat.
- elastix requires `LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib` — added to `~/.bashrc`.
- DeepSlice env prefix for Fiji ABBA config: `/home/jflab/miniforge3/envs/deepslice`
