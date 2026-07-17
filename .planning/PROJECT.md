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
- ✓ M3 hippocampus sections ABBA-registered (Z→MIP) in Fiji, atlas ROIs loaded into QuPath — Phase 1 (REG-01/REG-02/SCRI-01)
- ✓ Detection parameters locked on one M3 section (BraiAn.yml: sigma/area/histogram-threshold + 5 µm cytoplasmic expansion) — Phase 2, 02-LOCK-RECORD.md (SCRI-02)
- ✓ Fos+ reads nuclear compartment (AF488-T3); TdTomato+ reads cytoplasmic compartment (bg-sub AF568-T2) — validated end-to-end on M3 entry 1, Phase 3 (CLASS-01)
- ✓ Nucleus-anchored Double+ colocalization (no proximity heuristics) yields plausible counts — Phase 3: Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp autofluorescence suppressed
- ✓ `02_detect_classify.groovy` runs end-to-end on one section → classified TdT+/Fos+/Double+/Negative cells with atlas region labels + per-region counts (SCRI-03) — Phase 3, 03-VERIFICATION.md 7/7; robust threshold seed k=3 locked series-ready
- ✓ VAL-01 bioplausibility findings record on M3 entry 1 (213,106 cells) — `04-VALIDATION-RECORD.md`; per-subfield hippocampal coexpression lands in-band (CA1 0.35, CA3 0.14, DG-mo 0.13), densities cluster ~3,000/mm² (Phase-2 calibration), nucleus-area peak 40–50 µm² — v1.0 (Phase 4)
- ✓ Imaging-optimization notes for the full series (Z-plane audit, raw:MIP file-size tradeoff, per-subfield Airyscan-need assessment) — `04-IMAGING-NOTES.md` (OPT-01/OPT-02/OPT-03) — v1.0 (Phase 4)

### Active

_(Next milestone — full-series run; not yet scoped. Start with `/gsd-new-milestone`.)_

- [ ] Full per-atlas-region micron coordinate export for a brainrender point cloud (SC3 confirmed CCFv3 micron units on M3; full per-region export is v1.1+ scope)
- [ ] Scale the locked pipeline to the full registered section series (BraiAnalyse animal-level aggregation)
- [ ] Confirm the region-labeler / geometric atlas-leaf handling brain-wide (Phase-4 CR-01 fixed it for the VAL-01 metrics; validate across all sections before series-wide per-region counts)
- [ ] Confirm `opt01_zplane_audit.py` default paths refer to the same acquisition (IN-02)

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
- **Phase 3 complete (2026-07-16):** `02_detect_classify.groovy` validated end-to-end on M3 entry 1 (four-class breakdown, atlas labels, per-region counts). The D-04/D-05 "100% Negative" bug was root-caused (annulus measurement-key mismatch + buffered-write path) and fixed; positive thresholds now use a self-calibrating robust cut (median + k·1.4826·MAD, k=3).
- **v1.0 shipped (2026-07-17) — Single-Section Validation Run:** 4 phases, 12 plans. The full ABBA → BraiAnDetect → VAL-01 pipeline runs end-to-end on M3 entry 1 with locked detection params (`02-LOCK-RECORD.md`), a bioplausibility findings record (`04-VALIDATION-RECORD.md`), and forward-looking imaging notes (`04-IMAGING-NOTES.md`). A Phase-4 code review caught and fixed a region-labeling bug (cells leaking into a `grey` rollup) before close. Ready to scale to the full series via `/gsd-new-milestone`.

## Constraints

- **CPU-only**: No CUDA on this box (Intel UHD 630 iGPU only) — all detection runs on i9-9900K cores
- **Version pins**: QuPath v0.6.0 (BIOP catalog), elastix 5.2.0 (ABBA requirement) — do not bump
- **Colocalization rule**: Nucleus-anchored only — detect DAPI nuclei, cytoplasmic ring for TdTomato, nuclear compartment for Fos; no proximity/overlap heuristics
- **Coordinate units**: Export in microns, not pixels — QuPath pixel calibration must be verified against OME-XML `PhysicalSizeX`
- **Stats convention**: Aggregate to animal level before any group comparison; no pseudoreplication on section- or cell-level n
- **Git**: installed (v2.53.0), repo initialized 2026-07-07 (branch `main`, no remote); `.gitignore` excludes microscopy data (*.tif/*.tiff/*.czi/*.lif, *.qpdata, *.bfmemo — ~23 GB). GSD commits planning + code atomically on `main`

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| No Affine+Spline in ABBA | Elastix degrades without tissue mask; background pixels dominate optimization — confirmed 2026-06-23 | ✓ Good |
| Channel order override in czi_mip.py | aicspylibczi reads CZI channels in wrong order vs metadata; always pass explicit `--channels` | ✓ Good |
| Cytoplasmic expansion ring for TdTomato | TdTomato is cytosolic, not nuclear; must measure in cytoplasmic compartment to avoid mis-counting | ✓ Good (validated Phase 3 — bg-sub AF568-T2 cytoplasmic measure; TdT+ ~3.5% on M3 entry 1) |
| DeepSlice → manual angle → export only | Minimal registration steps that produce correct overlay; Affine/Spline excluded | ✓ Good |
| VAL-01 is a findings record, not a pass/fail gate (D-01) | n=1 single-section run; out-of-range metrics are interpreted (biology, Phase-2 calibration, threshold sensitivity), not failed | ✓ Good (Phase 4) |
| Per-cell atlas labeling = smallest-area containing region; `is_leaf` computed geometrically | ABBA/QuPath annotations aren't reliably nested — child-emptiness + first-match leaked ~95k cells into the `grey` rollup (Phase-4 CR-01) | ✓ Good (fixed 2026-07-17) |

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
*Last updated: 2026-07-17 after v1.0 milestone (Single-Section Validation Run shipped)*
