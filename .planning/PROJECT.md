# M3 Hippocampus Section Pipeline — First Run

## What This Is

End-to-end TRAP2 cell classification pipeline for the first real section run: M3 hippocampus slices with Z-planes already MIP'd to OME-TIFF. Starting from existing MIP files, this project covers ABBA atlas registration in Fiji, BraiAnDetect parameter tuning in QuPath, TdTomato+/Fos+/Double+ classification per atlas region, and micron-coordinate export. This run serves double duty: validating biologically plausible cell counts and locking detection parameters for the full series.

## Core Value

Biologically plausible TdT+/Fos+/Double+ counts per atlas region for M3 hippocampus, with locked detection parameters and imaging optimization notes ready for the full series.

## Requirements

### Validated

- ✓ CZI → MIP OME-TIFF conversion (`czi_mip.py`) — channel order workaround applied (aicspylibczi reads in wrong order vs metadata)
- ✓ ABBA registration workflow (DeepSlice → manual angle → export, no Affine/Spline) — tested and confirmed on one section 2026-06-23
- ✓ QuPath v0.6.0 with ABBA + BraiAnDetect + Warpy extensions installed
- ✓ Three conda envs operational: deepslice (py3.10), braian (py3.11), brainrender (py3.11)
- ✓ elastix 5.2.0 at `$HOME/section-pipeline/tools/elastix/`; LD_LIBRARY_PATH set in `~/.bashrc`

### Active

- [ ] ABBA-register M3 hippocampus sections (Z-planes → MIP) in Fiji (GUI)
- [ ] Tune BraiAnDetect nuclear segmentation params on one section (sigma, min/max area, threshold)
- [ ] Set cytoplasmic expansion ring radius for TdTomato channel measurement
- [ ] Validate TdTomato+ classifier: nucleus contains TdT centroid via cytoplasmic compartment
- [ ] Validate Fos+ classifier: nuclear compartment only
- [ ] Confirm Double+ logic: nucleus-anchored colocalization (no proximity heuristics)
- [ ] Export cell coordinates in microns per atlas region
- [ ] Document locked detection parameters (all BraiAnDetect settings) for series application
- [ ] Measure how many Z-planes are actually needed vs. acquired (MIP efficiency)
- [ ] Assess whether 20x is needed throughout vs. lower-power survey for future runs
- [ ] Document per-section file sizes and identify compression / MIP-immediately strategies

### Out of Scope

- BraiAnalyse whole-brain statistics — deferred; needs full registered series, not one section
- brainrender 3D visualization — deferred until stats are ready
- Multi-animal group comparison — needs >1 animal
- Elastix Affine+Spline registration — no tissue mask available; degrades result (confirmed 2026-06-23)
- Cellpose/StarDist detection — BraiAnDetect's built-in QuPath detection preferred (CPU speed)

## Context

- Pipeline infrastructure is fully installed and tested on one section (M3 hippocampus, 10x, 2026-06-20)
- 20x CZI → MIP pipeline confirmed 2026-06-22; channel order fix required: always pass `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"`
- M3 hippocampus MIP OME-TIFFs exist and are ready for ABBA registration
- Detection starting parameters should be seeded from F1000Research 2026 / bioRxiv 2024.09.16.611953 TRAP2 paper, then tuned visually on one section
- This is the section pipeline (vibratome + Airyscan); a parallel cleared light-sheet / ClearMap2 pipeline runs on a different machine ("engram") — do not conflate

## Constraints

- **CPU-only**: No CUDA on this box (Intel UHD 630 iGPU only) — all detection runs on i9-9900K cores
- **Version pins**: QuPath v0.6.0 (BIOP catalog), elastix 5.2.0 (ABBA requirement) — do not bump
- **Colocalization rule**: Nucleus-anchored only — detect DAPI nuclei, cytoplasmic ring for TdTomato, nuclear compartment for Fos; no proximity/overlap heuristics
- **Coordinate units**: Export in microns, not pixels — QuPath pixel calibration must be verified against OME-XML `PhysicalSizeX`
- **Stats convention**: Aggregate to animal level before any group comparison; no pseudoreplication on section- or cell-level n
- **No git installed**: Planning docs tracked locally only; git init blocked until git is installed

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| No Affine+Spline in ABBA | Elastix degrades without tissue mask; background pixels dominate optimization — confirmed 2026-06-23 | ✓ Good |
| Channel order override in czi_mip.py | aicspylibczi reads CZI channels in wrong order vs metadata; always pass explicit `--channels` | ✓ Good |
| Cytoplasmic expansion ring for TdTomato | TdTomato is cytosolic, not nuclear; must measure in cytoplasmic compartment to avoid mis-counting | — Pending (to be validated this run) |
| DeepSlice → manual angle → export only | Minimal registration steps that produce correct overlay; Affine/Spline excluded | ✓ Good |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-30 after initialization*
