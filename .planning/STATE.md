---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Plan 03-02 executed
last_updated: "2026-07-10T03:57:00.687Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 9
  completed_plans: 7
  percent: 50
---

# Project State: M3 Hippocampus Section Pipeline — First Run

**Last updated:** 2026-07-10
**Milestone:** 1 — Single-Section Validation Run

---

## Project Reference

**Core value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region for M3 hippocampus, with locked detection parameters and imaging optimization notes ready for the full series.

**Current focus:** Phase 03 — detection-script-and-single-section-end-to-end-test

---

## Current Position

**Active phase:** Phase 3 — Detection Script and Single-Section End-to-End Test — IN PROGRESS
**Active plan:** 03-03 (background-robust Fos/TdT measure) — next up
**Status:** Executing Phase 03

**Progress bar:**

```
[Phase 1] [Phase 2] [Phase 3] [Phase 4]
[======] [======] [====  ] [      ]
  78% of plans complete (7/9); Phase 3: 2/4 plans done
```

**Phase completion:**

- Phase 1: Complete (3/3 plans done, 2026-07-02)
- Phase 2: Complete (2/2 plans done, 2026-07-09 — detection params + classifier thresholds locked; see 02-LOCK-RECORD.md)
- Phase 3: In progress (2/4 plans done, 2026-07-10 — count rollup (SC4) + Atlas_X sanity print (SC3) added; see 03-02-SUMMARY.md)
- Phase 4: Not started

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 4 |
| Phases complete | 1 |
| Requirements mapped | 10/10 |
| Plans written | 5 |
| Plans complete | 4 |

---
| Phase 02 P01 | 12min | 3 tasks | 6 files |
| Phase 03 P01 | 10min | 2 tasks | 2 files |
| Phase 03 P02 | 7min | 2 tasks | 2 files |

## Accumulated Context

### Key Decisions (locked)

| Decision | Rationale | Status |
|----------|-----------|--------|
| No Affine+Spline in ABBA | Elastix degrades without tissue mask; confirmed 2026-06-23 | Locked |
| Channel order override in czi_mip.py | aicspylibczi reads in wrong order vs metadata; always pass `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` | Locked |
| Cytoplasmic expansion ring for TdTomato | TdTomato is cytosolic; measure in cytoplasmic compartment to avoid mis-counting | Pending validation (Phase 2) |
| DeepSlice → manual angle → export only | Minimal steps producing correct overlay | Locked |
| Nucleus-anchored colocalization only | No proximity/overlap heuristics | Locked |
| Export in microns not pixels | CCFv3 is in microns; pixel export produces wrong atlas positions | Locked |
| 4-argument loadWarpedAtlasAnnotations form | Verified from installed JAR bytecode; internal AtlasOntology overload not for Groovy scripts | Locked (Plan 01-01) |
| resolveHierarchy() after load | Claude discretion per CONTEXT.md; required for BraiAnDetect parent-child region assignment | Locked (Plan 01-01) |
| Single DAPI-T4-anchored channelDetections entry (not per-marker + OverlappingDetections) | Nucleus-anchored colocalization per CLAUDE.md; merged SingleClassifier application on the same DAPI-derived object set produces Double+ without geometric overlap | Locked (Plan 02-01) |
| histogramThreshold (not absolute threshold) in BraiAn.yml | D-01: series-scalable, avoids brightness-drift false negatives/positives across sections | Locked (Plan 02-01) |
| TdT classifier reads Cytoplasm: AF568-T2 mean (was Nucleus) | TdTomato is cytosolic; prior TRAP2TdT_Classifier_20x.json analog had the wrong compartment (real mis-count bug) | Locked (Plan 02-01) |
| All BraiAn.yml sigma/area/threshold values are [ASSUMED] TRAP2-paper seeds | Primary paper source returned HTTP 403 during research; not load-bearing, D-05 empirical gates will catch a bad seed | Pending tuning (Plan 02-02) |
| Detection stays separate from classify script (D-01) | run_braian_detection.groovy remains the standalone heavy BraiAnDetect pass; 02_detect_classify.groovy only classifies/labels/reports, letting fast threshold-iteration re-run without re-detecting | Locked (Plan 03-01) |
| Zero-detection guard + idempotent re-classify (D-02) | Entry with no detections aborts with a clear message; setPathClass overwrites so re-running just refreshes classes -- safe during threshold tuning | Locked (Plan 03-01) |
| Atlas region label computed ephemerally via centroid-in-ROI (not stored as per-cell metadata) | QuPath 0.6.0 javadoc warns metadata storage on plentiful detection objects is memory-inefficient; MeasurementList is numeric-only by design so a region acronym cannot be persisted there anyway | Locked (Plan 03-01) |
| Count rollup (SC4) reuses centroid-in-ROI, not the stale results/<image>_regions.tsv | That file reflects BraiAnDetect's incompatible classifier application (Deviation #1) and predates this script's classification ground truth | Locked (Plan 03-02) |
| Atlas_X sanity print stays a <=5-cell console check, no hard-coded unit conversion | Full per-cell export column is v2 scope (EXP-01/EXP-03); SC3 itself is the empirical print-and-check gate for microns-vs-voxel-index | Locked (Plan 03-02) |

### Critical Risks (to monitor)

- TdTomato classified from nuclear compartment instead of cytoplasmic ring — FIXED in Plan 02-01 (TdT_classifier.json now reads Cytoplasm: AF568-T2 mean); still needs a live detection run + visual DG bleed-check in Plan 02-02 to confirm no over/under-count in practice
- Channel name mismatch between OME-TIFF and BraiAn.yml/classifiers — silent failure (zero cells detected per channel); BraiAn.yml + both classifiers verified to use exact server.json channel names (AF568-T2, AF488-T3, DAPI-T4) in Plan 02-01, but not yet exercised against a live detection run
- Duplicate ABBA ROI loads double-count regions — `clearAllObjects()` guard in SCRI-01 (mitigated in Plan 01-01)
- Atlas coordinate unit mismatch (mm vs µm) — sanity-print block authored in Plan 03-02 (grep/cmp verified); live µm-range confirmation still deferred to Plan 03-04's human-in-the-loop QuPath run

### Environment

- Machine: Ubuntu 26.04, i9-9900K, 61 GB RAM, Intel UHD 630 iGPU (NO CUDA)
- QuPath: v0.6.0 at `$HOME/section-pipeline/tools/QuPath/bin/QuPath` (-Xmx32G)
- Fiji: `$HOME/section-pipeline/tools/Fiji.app/fiji-linux-x64`
- elastix: 5.2.0 at `$HOME/section-pipeline/tools/elastix/bin/`; LD_LIBRARY_PATH set
- Channel names: `AF568-T2` (TdTomato cytosolic), `AF488-T3` (Fos nuclear), `DAPI-T4`
- Git: installed (v2.53.0) and repo INITIALIZED 2026-07-07 (branch `main`, no remote). `.gitignore` excludes all microscopy data (*.tif/*.tiff/*.czi/*.lif), *.qpdata, *.bfmemo (~23 GB). GSD executors now commit atomically; worktrees auto-degrade to sequential-on-main (no origin/HEAD, #683).

### Todos

- [x] Phase 1 complete — script authored, ABBA registration (BigWarp) done, QC approved (2026-07-02)
- [x] Phase 2 context gathered (2026-07-07) — threshold + tuning decisions locked in CONTEXT.md
- [x] Plan 02-01 executed (2026-07-07) — BraiAn.yml, Fos/TdT classifiers, and qc_detection_gates.groovy authored
- [x] Plan 02-02: run BraiAnDetect in QuPath on M3 062926 3 plane entry 1, run qc_detection_gates.groovy, tune sigma/area/threshold against D-05 gates (DG + CA1), write 02-LOCK-RECORD.md (2026-07-09)
- [x] Plan 03-01 executed (2026-07-10) — 02_detect_classify.groovy authored (canonical + project hard-copy): D-01/D-02 guard, nucleus-anchored compound classification, atlas region label (regionOf/regionLabel)
- [x] Plan 03-02 executed (2026-07-10) — per-region count rollup (SC4, MeasurementList.put("Count: ...") onto CA1/CA2/CA3/DG-* leaf annotations) + Atlas_X micron sanity print (SC3) via AtlasTools; both grep/cmp-verified, human QuPath run deferred to Plan 03-04
- [ ] Plan 03-03: background-robust (local-background-subtraction) Fos/TdT measure (D-03/D-04/D-05); re-derive thresholds
- [ ] Plan 03-04: human-in-the-loop run — "Run for project" on M3 entry 1, verify four-class breakdown, region labels, data.qpdata update; only then mark SCRI-03 complete

### Blockers

None (Plan 02 is a human GUI step in Fiji; not a blocker, just a handoff).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260706-kfm | DAPI tissue-mask auto-crop CLI (crop_to_tissue.py) for ABBA elastix scaling | 2026-07-06 | n/a (no git) | [260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t](./quick/260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t/) |

---

## Session Continuity

**Last session:** 2026-07-10T03:57:00Z
**Stopped at:** Plan 03-02 executed — per-region count rollup (SC4) + Atlas_X micron sanity print (SC3) added
**Resume file:** .planning/phases/03-detection-script-and-single-section-end-to-end-test/03-03-PLAN.md

**To resume:** Plan 03-02 extended `scripts/02_detect_classify.groovy` (+ byte-identical project hard-copy) with two read-only reporting slices built on Plan 01's `regionAnnotations`/`regionOf`/`regionLabel` machinery: (1) a per-region count rollup writing `Count: <class>` numeric measurements (Negative/Fos+/TdT+/Double+/Excluded) onto every leaf region annotation via `MeasurementList.put`, satisfying SC4, with a console table complement; explicitly does NOT read the stale `results/<image>_regions.tsv`; (2) an Atlas_X/Y/Z micron sanity print for up to 5 sampled Fos+/TdT+/Double+ cells via `AtlasTools.getAtlasToPixelTransform(imageData).inverse()`, satisfying SC3, with a guarded skip path and a documented (not hard-coded) x10 voxel-index fallback comment. Both automated verifications (grep/cmp) passed; the plan's `<human-check>` QuPath run-through steps were explicitly NOT attempted per CLAUDE.md's GUI-human-only constraint and remain deferred to Plan 03-04. SCRI-03 requirement NOT yet marked complete (requires "tested on one section" per REQUIREMENTS.md, which only happens in Plan 03-04). Next: Plan 03-03 — background-robust (local-background-subtraction) Fos/TdT measure (D-03/D-04/D-05), re-deriving thresholds on the new measurement.

**Phase 2 locked decisions (see 02-CONTEXT.md):** histogram-relative detection threshold + relative classifier cutoffs + one global BraiAn.yml (drift-monitored via SERIES-02); hard lock gates = nucleus-area peak 50–150µm² AND DAPI density 500–2000/mm²; Double+ ratio advisory only; Fos+ negative-control gate deferred. Reuse `Fos_Classifier_20x.json` (correct nuclear compartment), rebuild TdT classifier to read Cytoplasm — both done in Plan 02-01.

**Side task:** TRACR registration for another lab in progress (rough, may need a per-section second pass) — see memory.

---
*State initialized: 2026-07-01 | Last updated: 2026-07-10 (Phase 3 Plan 01 executed)*
