# M3 Hippocampus Section Pipeline — First Run

## What This Is

End-to-end TRAP2 cell classification pipeline for TRAP2/Airyscan vibratome sections: ABBA atlas registration in Fiji, BraiAnDetect detection + parameter tuning in QuPath, nucleus-anchored TdTomato+/Fos+/Double+ classification per atlas region, and micron-coordinate export. **v1.0 validated the pipeline on a single M3 hippocampus section (locking detection parameters and imaging-optimization notes); v1.1 runs the first full section series — animal wBA1-3, 5 coronal sections — to quantify LA/BA amygdala engram tagging (TRAP2/tdTomato) and reactivation (Fos).**

## Core Value

Biologically plausible TdT+/Fos+/Double+ counts per atlas region across a registered section series, with locked detection parameters and imaging-optimization notes ready to scale brain-wide.

## Current Milestone: v1.1 First Full-Series Run — LA/BA Amygdala Engram (wBA1-3)

**Goal:** Run animal wBA1-3's full 5-section series end-to-end to quantify TRAP2/tdTomato engram tagging + Fos reactivation across the LA/BA amygdala — validating re-optimized imaging, cutting registration effort, standing up a generalizable area-based readout for compact-nuclei regions, and producing animal-level aggregated counts.

**Target features:**
- Multi-scene MIP conversion — extend `czi_mip.py` for per-scene output (processed CZI → 5 section MIPs)
- Imaging re-validation on the new 4-plane / lower-laser params (D-05 gates; re-lock detection only on drift)
- Registration speedup — research-driven middle ground for BigWarp (`crop_to_tissue.py` + tissue-mask elastix a candidate)
- LA/BA nucleus-anchored TdT+/Fos+/Double+ classification across the amygdala ROI (primary readout)
- Generalizable area-based density readout for compact-nuclei regions — reusable/brain-wide-ready; DG as the in-section test case; additive/parallel to nucleus counts
- Brain-wide region-labeling validation — CR-01 fix confirmed across all 5 sections / all regions
- Section→animal aggregation — first BraiAnalyse roll-up (5 sections → one animal)
- Full per-atlas-region micron export — brainrender-ready CCFv3 point cloud

**Data:** `Automated Cell Counting/wBA Sungmo/-001-07_processed.czi` (16 GB Airyscan-processed, 5 mosaic scenes, Z=4, C=3, 0.69 µm/px, channels `AF568-T2`/`AF488-T3`/`DAPI-T4` — same naming as v1.0). The merged 32 GB OME-TIFF is unusable (all scenes fused into one canvas, Z not projected) — do not use it.

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
- ✓ Multi-scene MIP conversion + batch-export integrity — `czi_mip.py` emits 5 identity-verified section MIP OME-TIFFs from the 16 GB processed CZI (per-scene `region=` loop, no fusion, pixel size in OME-XML) with per-scene identity records + thumbnails; operator-confirmed scene identity and channel identity (index 0=TdTomato / 1=Fos / 2=DAPI); multi-entry export truncation fixed (`03_export_val01_metrics.groovy` collision-safe per-entry stems + `verify_export_integrity.py`) — Phase 5 (CONV-01/CONV-02/EXP-02), 05-VERIFICATION.md 7/7

### Active

Milestone v1.1 (LA/BA Amygdala Engram, wBA1-3) — see `## Current Milestone` above; detailed REQ-IDs in `REQUIREMENTS.md`:

- [ ] Imaging re-validation on the new 4-plane / lower-laser params (re-lock detection only on D-05 drift)
- [ ] Registration speedup for BigWarp (research-driven; tissue-mask elastix a candidate)
- [ ] LA/BA nucleus-anchored TdT+/Fos+/Double+ classification across the amygdala ROI
- [ ] Generalizable area-based density readout for compact-nuclei regions (brain-wide-ready; DG test case; additive/parallel)
- [ ] Brain-wide region-labeling validation across all 5 sections (extends Phase-4 CR-01 fix)
- [ ] Section→animal aggregation via BraiAnalyse (5 sections → one animal)
- [ ] Full per-atlas-region micron coordinate export for a brainrender point cloud
- [ ] Confirm `opt01_zplane_audit.py` default paths refer to the same acquisition (IN-02, carried from v1.0)

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
| Area-based density readout is a documented, generalizable exception to nucleus-anchored colocalization | DG-granule (and other compact-nuclei regions) defeat per-nucleus segmentation; area-over-DAPI is additive/parallel — never replacing primary counts — and built reusable for the eventual brain-wide pipeline | — Pending (v1.1) |

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
*Last updated: 2026-07-19 after Phase 5 complete (Series Scaffolding — 5 identity-verified section MIPs + fixed batch export; CONV-01/CONV-02/EXP-02 validated)*
