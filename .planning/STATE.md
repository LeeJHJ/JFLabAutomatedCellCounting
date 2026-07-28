---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: First Full-Series Run — LA/BA Amygdala Engram
current_phase: 07
current_phase_name: New 4-Plane / Lower-Laser Params
status: verifying
stopped_at: Completed 06.1-05-PLAN.md
last_updated: "2026-07-27T19:00:29.438Z"
last_activity: 2026-07-27
last_activity_desc: Phase 06.1 complete, transitioned to Phase 07
progress:
  total_phases: 7
  completed_phases: 3
  total_plans: 14
  completed_plans: 14
  percent: 43
---

# Project State: M3 Section Pipeline — TRAP2 / Airyscan

**Last updated:** 2026-07-17
**Milestone:** v1.1 — First Full-Series Run — LA/BA Amygdala Engram (wBA1-3)

---

## Project Reference

**Core value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region across a registered section series, with locked detection parameters and imaging-optimization notes ready to scale brain-wide.

**Current focus:** Phase 06.1 — pipeline-generalization-per-region-readout-runbook

---

## Current Position

Phase: 07 — Imaging Re-Validation (New 4-Plane / Lower-Laser Params)
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-07-27 — Phase 06.1 complete, transitioned to Phase 07

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
| Phase 06 P01 | 5min | 3 tasks | 4 files |
| Phase 06 P02 | 6min | 3 tasks | 3 files |
| Phase 06.1 P01 | 6min | 2 tasks | 4 files |
| Phase 06.1 P02 | 4min | 3 tasks | 6 files |
| Phase 06.1 P03 | 12min | 3 tasks | 3 files |
| Phase 06.1 P04 | ~5min | 3 tasks | 5 files |
| Phase 06.1 P05 | ~20min | 4 tasks | 14 files |
| Phase quick-260724-h6y P01 | 12min | 2 tasks | 1 files |
| Phase quick-260724-iqn P01 | 6min | 2 tasks | 1 files |
| Phase quick-260724-kmj P01 | 7min | 2 tasks | 1 files |
| Phase quick-260725-npx P01 | 18min | 2 tasks | 1 files |
| Phase quick-260725-w88 P01 | 15min | 3 tasks | 12 files |

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
| ~~No Affine+Spline in ABBA~~ → **works with Nissl (Ch0)** | Original (2026-06-23): elastix degrades without a tissue mask. **REVISED 2026-07-20 (operator, wBA1-3):** root cause was substantially the **wrong atlas fixed channel** — Label Borders (Ch2) is a region-outline line-drawing with no DAPI-intensity correspondence. With atlas **Nissl (Ch0)** as the fixed channel, in-GUI elastix Affine+Spline works. Working pipeline: DeepSlice → single global slicing angle (X=−8.6/Y=3.9, locked) → elastix Affine(Nissl Ch0 // DAPI Ch2) → elastix Spline(15 pts) → BigWarp "Edit last registration" refine (~40 min total / ~8 min per section for all 5). | **Superseded** (Phase 6 REG-04/05) |
| Channel order override in czi_mip.py | aicspylibczi reads in wrong order vs metadata; always pass `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` | Locked |
| TdTomato measured whole-cell (nucleus + ring, area-weighted; QuPath `Cell: <ch> mean`) | Operator domain call 2026-07-25: TdTomato fills the whole cell in this line/prep, so ring-only measurement under-counts it; revises the earlier CLAUDE.md "cytoplasmic-ring-only, non-negotiable" wording. Cytoplasmic-ring compartment remains available (config option) for any future strictly-cytosolic marker. | Revised 2026-07-25 — whole-cell, operator domain call (quick-260725-w88) |
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

First v1.1 execution step (Phase 5) is scriptable (no GUI dependency); Phases 6-8 include human-in-the-loop QuPath/ABBA GUI handoffs.

- 06.1-06 Task 2 (operator GUI run: ABBA register + BraiAnDetect + classify + export on the TdT-only slice set) awaiting the incoming TdT-only slice set data + operator availability at the monitor. pipeline.tdt-only.yml authored and config-side validated (D-03/D-04 proven); no TdT-only QuPath project exists on disk yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260706-kfm | DAPI tissue-mask auto-crop CLI (crop_to_tissue.py) for ABBA elastix scaling | 2026-07-06 | n/a | [260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t](./quick/260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t/) |
| 260724-h6y | czi_mip.py hybrid DAPI projection — single sharpest Z plane (var-of-Laplacian, per scene) + full-Z marker MIP | 2026-07-24 | 17e2cd8 | [260724-h6y-czi-mip-hybrid-dapi](./quick/260724-h6y-czi-mip-hybrid-dapi/) |
| 260724-iqn | czi_mip.py multi-scene tile-stitch isolation — additive per-scene tile-stitch path + `--isolate {auto,region,tiles}` for overlapping mosaics, region path unchanged for non-overlapping files | 2026-07-24 | 2820928 | [260724-iqn-czi-mip-tile-stitch](./quick/260724-iqn-czi-mip-tile-stitch/) |
| 260724-kmj | czi_mip.py flat-field shading correction + feathered overlap blending in tile-stitch path (fixes periodic DAPI grid) + OME per-channel display colors (DAPI blue, AF568/TdT red, AF488/Fos green); region path byte-unchanged | 2026-07-24 | 00b6261 | [260724-kmj-flatfield-blend](./quick/260724-kmj-flatfield-blend/) |
| 260724-fast | fix(03_export): D-10 zero-leak assertion reconciles unresolved detections (cell centroid outside all atlas regions) — `sumAnchorOwn + nUnresolved == nClassified`; found on wBA1-2_2-1 s5 (off-by-1); propagated to deploy copies | 2026-07-24 | e712989 | — |
| 260725-fast | fix(02_classify): coerce whole-cell guard key to String (GString!=String in Set.contains) — was false-aborting on a valid `Cell: AF568-T2 mean`; propagated to deploy copies | 2026-07-25 | 7c1d7eb | — |
| 260725-fast2 | fix(03_export): accept whole-cell compartment (validator + COMPARTMENT_LABELS) — 260725-w88 rollout missed 03; propagated | 2026-07-25 | c40cb95 | — |
| 260728-kbs | cockpit increment 2: `scripts/cockpit_regions.py` — region-of-interest readout CSV (ontology-frontier roll-up, exclusion-aware, L/R+pooled, dynamic marker cols). Rolls up from the Allen ontology, NOT the region_table parent rows (QuPath annotation hierarchy ≠ ontology — BMA parent row=0 while BMAa=1253). Self-test 21/21 + real tdt-only fixture validated | 2026-07-28 | c7d567f | [260728-kbs-add-cockpit-regions-py-region-of-interes](./quick/260728-kbs-add-cockpit-regions-py-region-of-interes/) |

---

### Roadmap Evolution

- Phase 06.1 inserted after Phase 6: Pipeline Generalization + Per-Region Readout Runbook (URGENT)

## Session Continuity

**Last session:** 2026-07-26T03:26:06.514Z
**Stopped at:** Completed 06.1-05-PLAN.md
**Resume file:** 

None

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
- [Phase ?]: 06-01: AP axis resolved dynamically from atlas.orientation (scan for a/p char), never hardcoded to axis 0 (RESEARCH A1)
- [Phase ?]: 06-01: elastix parameter files use only the standard elastix.dev component set (no invented metric/optimizer combination), flagged as operator-retunable starting values (A2)
- [Phase ?]: 06-01: elastix_trial_harness.py authored as .py (not .sh) to match project's all-Python/Groovy convention and reuse the --self-test idiom
- [Phase 06]: 06-02: scripts/run_deepslice.py NOT authored -- 06-CONTEXT resolution supersedes RESEARCH; REG-03 uses ABBA native DeepSlice Registration (Local) command, D-01 met by 06-REG03-SOP.md record
- [Phase ?]: 06.1-01: Compartment-label map fixed nuclear->Nucleus, cytoplasmic->Cytoplasm; bg-sub measurement key locked as '<label>: <channel> mean (bg-sub)' for all downstream consumers
- [Phase ?]: 06.1-01: pipeline.yml's load_config() defensively rejects any leaked BraiAnDetect detection-param key, enforcing D-14's separation from BraiAn.yml at validation time, not just by convention
- [Phase ?]: 06.1-02: pipeline.yml parsed via a line-based state-machine (no YAML lib in QuPath Groovy); config-driven per-marker bg-sub classifier JSON filenames replace the two legacy literal filenames
- [Phase ?]: 06.1-03: Export consumes the class vocabulary already assigned by 02_detect_classify.groovy (getPathClass()) rather than recomputing thresholds -- pure readout, not a second classifier
- [Phase ?]: 06.1-03: columnPrefixFor (wide-table, anchor no '+') and classFor (combined-CSV class label, anchor has '+') kept as two distinct closures -- collapsing them would break one of the two established contracts
- [Phase ?]: 06.1-03: zero-leak assertion sums only the anchor category's own-bucket counts vs total non-excluded classified detections; unresolved cells (no containing region) counted/reported separately, not silently dropped
- [Phase ?]: 06.1-04: check-zero-leak re-proves D-10 from the CSV alone, independent of the groovy exporter's own assertion, decoupled from live QuPath data via a --self-test synthetic tree
- [Phase ?]: 06.1-04: Fos/Double-dependent VAL-01 metrics (ratio, Fos control rate) SKIP rather than report 0/NaN when their marker is structurally absent (D-03/D-04)
- [Phase 06.1-05]: Completed prior executor's Rule-3 fix: added six 1x1 placeholder screenshot PNGs under docs/assets/ (+ README explaining the stubs) so mkdocs build --strict resolves every screenshot-slot link with zero broken-link warnings
- [Phase 06.1-05]: run_pipeline.py menu scope kept to exactly the SCRIPTABLE actions the plan named (validate config, aggregate+zero-leak, verify export integrity, show outputs) plus GUI stop items for the three GUI-mediated stages; GUI handlers never call subprocess, structurally guaranteeing no app automation
- [Phase ?]: 260724-h6y: marker channels use FULL Z stack (not Z0-2 sub-range) to capture 2-4um axial offset between DAPI-sharp plane and marker signal peak
- [Phase ?]: 260724-h6y: hybrid-projection provenance (dapi_z) embedded as OME-XML comment, not filename, to preserve the _MIP.ome.tiff output-count glob
- [Phase ?]: 260724-iqn: tile-stitch canvas sized to each scene's OWN tile-union (min/max of that scene's tile origins), never the full mosaic or reported bbox -- structural isolation guarantee against cross-scene contamination on overlapping mosaics
- [Phase ?]: 260724-iqn: --isolate auto is default and preserves byte-identical region=bbox behavior for non-overlapping files; --isolate region still refuses (SystemExit) on overlap, tile-stitch is the fallback, never silent
- [Phase quick-260724-kmj]: 260724-kmj: flat-field/feather changes confined strictly to the tile-stitch path; _read_channel_stacks_region and read_mosaic left byte-unchanged (verified against pre-task baseline)
- [Phase quick-260724-kmj]: 260724-kmj: DEFAULT_FEATHER_MARGIN=130 and DEFAULT_SHADING_SMOOTH_SIGMA=5.0 are module-level operator-tunable constants, not CLI flags
- [Phase ?]: 260725-npx: k_sweep_readout.py reproduces 02_detect_classify.groovy's robust cut exactly (median+k*1.4826*MAD, >=); region-level threshold always uses the section-level threshold, never re-derived per region
- [Phase ?]: 260725-w88: TdT switched to whole-cell compartment (area-weighted QuPath Cell: mean) per operator domain call 2026-07-25; cytoplasmic ring remains available for strictly-cytosolic markers; D-15 guard 4 added to fail loud on a missing Cell-compartment key
