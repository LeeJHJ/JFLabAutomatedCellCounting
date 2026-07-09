---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 3 context gathered
last_updated: "2026-07-09T20:05:21.795Z"
progress:
  total_phases: 4
  completed_phases: 2
  total_plans: 5
  completed_plans: 5
  percent: 50
---

# Project State: M3 Hippocampus Section Pipeline — First Run

**Last updated:** 2026-07-07
**Milestone:** 1 — Single-Section Validation Run

---

## Project Reference

**Core value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region for M3 hippocampus, with locked detection parameters and imaging optimization notes ready for the full series.

**Current focus:** Phase 2 complete (detection params locked) → Phase 3 next

---

## Current Position

**Active phase:** Phase 2 — Detection Parameter Lock — **COMPLETE** (2026-07-09)
**Active plan:** None — both plans done; ready for Phase 3
**Status:** Phase 2 complete

**Progress bar:**

```
[Phase 1] [Phase 2] [Phase 3] [Phase 4]
[======] [======] [      ] [      ]
  50% (Phases 1-2 complete)
```

**Phase completion:**

- Phase 1: Complete (3/3 plans done, 2026-07-02)
- Phase 2: Complete (2/2 plans done, 2026-07-09 — detection params + classifier thresholds locked; see 02-LOCK-RECORD.md)
- Phase 3: Not started
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

### Critical Risks (to monitor)

- TdTomato classified from nuclear compartment instead of cytoplasmic ring — FIXED in Plan 02-01 (TdT_classifier.json now reads Cytoplasm: AF568-T2 mean); still needs a live detection run + visual DG bleed-check in Plan 02-02 to confirm no over/under-count in practice
- Channel name mismatch between OME-TIFF and BraiAn.yml/classifiers — silent failure (zero cells detected per channel); BraiAn.yml + both classifiers verified to use exact server.json channel names (AF568-T2, AF488-T3, DAPI-T4) in Plan 02-01, but not yet exercised against a live detection run
- Duplicate ABBA ROI loads double-count regions — `clearAllObjects()` guard in SCRI-01 (mitigated in Plan 01-01)
- Atlas coordinate unit mismatch (mm vs µm) — verify Atlas_X range in Phase 3

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
- [ ] Plan 02-02: run BraiAnDetect in QuPath on M3 062926 3 plane entry 1, run qc_detection_gates.groovy, tune sigma/area/threshold against D-05 gates (DG + CA1), write 02-LOCK-RECORD.md

### Blockers

None (Plan 02 is a human GUI step in Fiji; not a blocker, just a handoff).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260706-kfm | DAPI tissue-mask auto-crop CLI (crop_to_tissue.py) for ABBA elastix scaling | 2026-07-06 | n/a (no git) | [260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t](./quick/260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t/) |

---

## Session Continuity

**Last session:** 2026-07-09T20:05:21.790Z
**Stopped at:** Phase 3 context gathered
**Resume file:** .planning/phases/03-detection-script-and-single-section-end-to-end-test/03-CONTEXT.md

**To resume:** Plan 02-01 authored the full scriptable half of the detection-parameter lock: `BraiAn.yml` (single DAPI-T4-anchored channelDetections entry, histogramThreshold, cellExpansionMicrons 5.0), `Fos_Classifier_20x.json` (reused, nuclear) and `TdT_classifier.json` (rebuilt, cytoplasmic — fixed the Nucleus-compartment bug), and `scripts/qc_detection_gates.groovy` (+ project hard-copy) for the D-05 gate measurements. All numeric seeds ([ASSUMED] sigma/area/thresholds) are unlocked. Next: Plan 02-02 (human-in-the-loop) — run BraiAnDetect in QuPath on M3 062926 3 plane entry 1, run `qc_detection_gates.groovy`, tune params against the D-05 hard gates (nucleus-area peak 50–150µm² AND DAPI density 500–2000/mm² on both DG and CA1), and write `02-LOCK-RECORD.md` once both PASS.

**Phase 2 locked decisions (see 02-CONTEXT.md):** histogram-relative detection threshold + relative classifier cutoffs + one global BraiAn.yml (drift-monitored via SERIES-02); hard lock gates = nucleus-area peak 50–150µm² AND DAPI density 500–2000/mm²; Double+ ratio advisory only; Fos+ negative-control gate deferred. Reuse `Fos_Classifier_20x.json` (correct nuclear compartment), rebuild TdT classifier to read Cytoplasm — both done in Plan 02-01.

**Side task:** TRACR registration for another lab in progress (rough, may need a per-section second pass) — see memory.

---
*State initialized: 2026-07-01 | Last updated: 2026-07-07 (Phase 1 complete + Phase 2 context)*
