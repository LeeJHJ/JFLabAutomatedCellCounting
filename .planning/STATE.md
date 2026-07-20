---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: First Full-Series Run — LA/BA Amygdala Engram
current_phase: 6
current_phase_name: Registration Speedup
status: executing
stopped_at: Phase 6 context gathered
last_updated: "2026-07-20T15:11:56.273Z"
last_activity: 2026-07-19
last_activity_desc: Phase 05 complete, transitioned to Phase 6
progress:
  total_phases: 6
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 17
---

# Project State: M3 Section Pipeline — TRAP2 / Airyscan

**Last updated:** 2026-07-17
**Milestone:** v1.1 — First Full-Series Run — LA/BA Amygdala Engram (wBA1-3)

---

## Project Reference

**Core value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region across a registered section series, with locked detection parameters and imaging-optimization notes ready to scale brain-wide.

**Current focus:** Phase 05 — series-scaffolding-multi-scene-mip-batch-export-integrity

---

## Current Position

Phase: 6 — Registration Speedup
Plan: Not started
Status: Ready to execute
Last activity: 2026-07-19 — Phase 05 complete, transitioned to Phase 6

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total (v1.1) | 6 (Phases 5-10) |
| Phases complete (v1.1) | 0 |
| Requirements mapped | 15/15 |
| Plans written | 3 (Phase 5) |
| Plans complete | 0 |
| Phases complete (v1.0, shipped) | 4/4 |

---
| Phase 05 P01 | 7min | 2 tasks | 1 files |
| Phase 05 P02 | 15min | 2 tasks | 3 files |
| Phase 05 P03 | 8min | 1 tasks | 0 files |

## v1.1 Roadmap Snapshot (created 2026-07-17)

| Phase | Goal (short) | Requirements |
|-------|--------------|--------------|
| 5. Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity | 5 identity-verified section MIPs + fixed multi-entry export | CONV-01, CONV-02, EXP-02 |
| 6. Registration Speedup | DeepSlice batch + reduced-landmark BigWarp; masked-elastix prototype trial | REG-03, REG-04, REG-05 |
| 7. Imaging Re-Validation (4-plane / lower-laser) | Re-run D-05 gates; re-lock k only on drift; under-projection check | IMG-01, IMG-02 |
| 8. LA/BA Classification + Brain-Wide Region-Labeling Validation | Nucleus-anchored TdT+/Fos+/Double+ across 5 sections + CR-01 re-audit on amygdala | CLASS-02, LABEL-01 |
| 9. Generalizable Area-Based Density Readout | Region-parameterized %-area-above-threshold; DG test case; additive/parallel | AREA-01, AREA-02 |
| 10. Animal-Level Aggregation + Atlas-Space Export & Point Cloud | Animal-level table + persisted CCFv3 µm coords + brainrender point cloud | AGG-01, EXP-03, EXP-04 |

**Ordering:** 5 → 6 → 7 → 8 → 9 → 10 (Phase 7 may run parallel with Phase 6). EXP-02 is sequenced early in Phase 5 because it blocks AGG-01 in Phase 10.

---

## Deferred Items

Items acknowledged and deferred at v1.0 milestone close on 2026-07-17:

| Category | Item | Status |
|----------|------|--------|
| verification | Phase 2 (Detection Parameter Lock) has no `02-VERIFICATION.md` | Deferred — override close-out; params validated downstream by Phase 3 (end-to-end) + Phase 4 (bioplausibility) |
| imaging | IN-02: `opt01_zplane_audit.py` default paths span three project date-stamps (062026 CZI / 062226 MIP / 062926 region-TSVs) | Open — confirm same acquisition before the full-series raw:MIP ratio (carried into v1.1 imaging work) |

## Accumulated Context

### Key Decisions (locked)

| Decision | Rationale | Status |
|----------|-----------|--------|
| No Affine+Spline in ABBA | Elastix degrades without tissue mask; confirmed 2026-06-23 | Locked (REG-05 trials a masked prototype outside ABBA's GUI as the only exception) |
| Channel order override in czi_mip.py | aicspylibczi reads in wrong order vs metadata; always pass `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` | Locked |
| Cytoplasmic expansion ring for TdTomato | TdTomato is cytosolic; measure in cytoplasmic compartment to avoid mis-counting | Locked (validated Phase 3 — bg-sub AF568-T2 cytoplasmic measure) |
| DeepSlice → manual angle → export only | Minimal steps producing correct overlay | Locked |
| Nucleus-anchored colocalization only | No proximity/overlap heuristics | Locked |
| Export in microns not pixels | CCFv3 is in microns; pixel export produces wrong atlas positions | Locked |
| 4-argument loadWarpedAtlasAnnotations form | Verified from installed JAR bytecode; internal AtlasOntology overload not for Groovy scripts | Locked (Plan 01-01) |
| resolveHierarchy() after load | Required for BraiAnDetect parent-child region assignment | Locked (Plan 01-01) |
| Single DAPI-T4-anchored channelDetections entry (not per-marker + OverlappingDetections) | Nucleus-anchored colocalization per CLAUDE.md; merged SingleClassifier application on the same DAPI-derived object set produces Double+ without geometric overlap | Locked (Plan 02-01) |
| histogramThreshold (not absolute threshold) in BraiAn.yml | D-01: series-scalable, avoids brightness-drift false negatives/positives across sections | Locked (Plan 02-01) |
| TdT classifier reads Cytoplasm: AF568-T2 mean (was Nucleus) | TdTomato is cytosolic; prior analog had the wrong compartment (real mis-count bug) | Locked (Plan 02-01) |
| Robust median + k·1.4826·MAD (k=3) positive threshold on bg-sub measure | Self-calibrating cut replacing absolute cutoffs; series-ready | Locked (Phase 3, 03-04) — re-validated at new imaging params in Phase 7 (IMG-01) |
| Per-cell atlas label = smallest-area containing region, is_leaf computed geometrically | ABBA/QuPath annotations aren't reliably nested; child-emptiness + first-match leaked ~95k cells into `grey` (CR-01) | Locked (fixed 2026-07-17) — re-audited on non-laminar amygdala in Phase 8 (LABEL-01) |
| Area-based density readout is a documented, generalizable exception to nucleus-anchored colocalization | Compact-nuclei regions (DG-granule, etc.) defeat per-nucleus segmentation; area-over-DAPI is additive/parallel, never replacing primary counts | Pending build (v1.1 Phase 9) |

### Critical Risks (to monitor in v1.1)

- **CR-01 fix may fail differently on amygdala** — smallest-area-leaf heuristic validated only on laminar hippocampus; LA/BA are adjacent, comparable-size, non-nested nuclei. Re-audited in Phase 8 (LABEL-01) before trusting the series.
- **k=3 threshold seed may drift at new laser power / Z-count** — lower laser changes photon statistics, not just brightness. Re-run D-05 gates AND compare bg-sub histogram shape vs v1.0 reference in Phase 7 (IMG-01); re-sweep k (3-5) on drift.
- **Under-projection at 4 Z-planes** — narrower range risks dimming nuclei / reintroducing DAPI blobs. OPT-01-style plateau + visual DAPI check in Phase 7 (IMG-02).
- **Multi-scene CZI scene→section mapping untested** — off-by-one/shuffle silently mislabels physical sections (project already hit this with the 32 GB merged file). Verify each scene bbox/morphology in Phase 5 (CONV-02); name files with scene index verbatim.
- **Tissue damage in the 5-section series undetected** — ABBA/BraiAnDetect produce locally plausible wrong counts on folds/tears. Per-section visual tissue-QC before registration; any exclusion a priori + principled.
- **Multi-entry export truncation (EXP-02)** — `03_export_val01_metrics.groovy` "Run for project" truncates to only the last entry. Blocking prerequisite for AGG-01; fixed early in Phase 5.

### Environment

- Machine: Ubuntu 26.04, i9-9900K, 61 GB RAM, Intel UHD 630 iGPU (NO CUDA)
- QuPath: v0.6.0 at `$HOME/section-pipeline/tools/QuPath/bin/QuPath` (-Xmx32G)
- Fiji: `$HOME/section-pipeline/tools/Fiji.app/fiji-linux-x64`
- elastix: 5.2.0 at `$HOME/section-pipeline/tools/elastix/bin/`; LD_LIBRARY_PATH set
- Channel names: `AF568-T2` (TdTomato cytosolic), `AF488-T3` (Fos nuclear), `DAPI-T4`
- v1.1 data: `Automated Cell Counting/wBA Sungmo/-001-07_processed.czi` (16 GB, 5 scenes, Z=4, C=3, 0.69 µm/px). The merged 32 GB OME-TIFF is unusable (scenes fused, Z not projected) — do not use it.
- Git: installed (v2.53.0), repo INITIALIZED 2026-07-07 (branch `main`, no remote). `.gitignore` excludes microscopy data. GSD executors commit atomically; worktrees auto-degrade to sequential-on-main.

### Todos

- [x] v1.0 shipped 2026-07-17 (4 phases, 12 plans) — single-section validation on M3 entry 1
- [x] v1.1 requirements defined (15 requirements) — 2026-07-17
- [x] v1.1 research synthesized (`research/SUMMARY.md`, MEDIUM confidence) — 2026-07-17
- [x] v1.1 roadmap created (Phases 5-10, 15/15 mapped) — 2026-07-17
- [x] Plan Phase 5 — 3 plans, checker PASSED — 2026-07-18
- [ ] Execute Phase 5 — `/gsd-execute-phase 5`

### Blockers

None. First v1.1 execution step (Phase 5) is scriptable (no GUI dependency); Phases 6-8 include human-in-the-loop QuPath/ABBA GUI handoffs.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260706-kfm | DAPI tissue-mask auto-crop CLI (crop_to_tissue.py) for ABBA elastix scaling | 2026-07-06 | n/a | [260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t](./quick/260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t/) |

---

## Session Continuity

**Last session:** 2026-07-19T15:28:05.877Z
**Stopped at:** Phase 6 context gathered
**Resume file:** 

.planning/phases/06-registration-speedup/06-CONTEXT.md

**Side task:** TRACR registration for another lab in progress (rough, may need a per-section second pass) — see memory. (Retired notes archived in `.planning/archive/retired-memory-notes.md`.)

---
*State initialized: 2026-07-01 | Last updated: 2026-07-17 (v1.1 roadmap created — Phases 5-10, 15/15 requirements mapped)*

## Operator Next Steps

- Review the Phase 5 plans in `.planning/phases/05-series-scaffolding-multi-scene-mip-batch-export-integrity/` (05-01, 05-02, 05-03).
- Execute the first phase: `/gsd-execute-phase 5` (Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity).

## Decisions

- [Phase ?]: 05-01: Multi-scene CZI isolation uses region=bbox only (get_all_mosaic_scene_bounding_boxes); S= on a mosaic read raises — scene count never from get_dims_shape()['S']
- [Phase ?]: 05-01: czi_mip.py generalized by grafting czi_hybrid_mip.py CLI + names-driven _build_ome_xml onto the canonical file; identity thumbnail downsamples the in-hand DAPI MIP (no fractional scale_factor)
- [Phase ?]: 05-02: 03_export_val01_metrics.groovy output paths derive from getProjectEntry().getImageName() + invalidChars sanitization + buildPathInProject (reused from run_braian_detection.groovy), eliminating cross-entry TSV clobbering on Run for project (EXP-02)
- [Phase ?]: 05-02: verify_export_integrity.py skips the multi-entry non-clobbering assertion when fewer than 2 stems exist, so the checker is runnable now (single-entry M3) and again on the 5-entry wBA1-3 series in Phase 8/10
- [Phase ?]: 05-03: Operator confirmed OME-TIFF channel index order (0=TdTomato, 1=Fos, 2=DAPI) on the wBA1-3 series -- the A1 sign-off Phase 8 classification depends on
- [Phase ?]: 05-03: Operator confirmed 5-scene identity (distinct, intact sections, consistent scene_key<->s{N} mapping) -- CONV-02 satisfied
