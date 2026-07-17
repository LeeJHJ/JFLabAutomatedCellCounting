---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 04-01-PLAN.md
last_updated: "2026-07-17T00:40:13.351Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 12
  completed_plans: 10
  percent: 75
---

# Project State: M3 Hippocampus Section Pipeline — First Run

**Last updated:** 2026-07-16
**Milestone:** 1 — Single-Section Validation Run

---

## Project Reference

**Core value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region for M3 hippocampus, with locked detection parameters and imaging optimization notes ready for the full series.

**Current focus:** Phase 04 — biological-plausibility-validation-and-imaging-optimization-

---

## Current Position

**Active phase:** Phase 4 — Biological Plausibility Validation and Imaging Optimization Notes — IN PROGRESS
**Plan:** 2 of 3
**Status:** Ready to execute

**Progress bar:**

```
[Phase 1] [Phase 2] [Phase 3] [Phase 4]
[======] [======] [======] [      ]
  9/9 planned plans complete; Phase 3 done (4/4); Phase 4 not yet planned
```

**Phase completion:**

- Phase 1: Complete (3/3 plans done, 2026-07-02)
- Phase 2: Complete (2/2 plans done, 2026-07-09 — detection params + classifier thresholds locked; see 02-LOCK-RECORD.md)
- Phase 3: Complete (4/4 plans done, 2026-07-16 — 03-04 human gate PASSED on M3 entry 1; D-04/D-05 all-Negative bug resolved; SCRI-03 verified end-to-end, 03-VERIFICATION.md 7/7)
- Phase 4: Not started

---

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases total | 4 |
| Phases complete | 3 |
| Requirements mapped | 10/10 |
| Plans written | 9 |
| Plans complete | 9 |

---
| Phase 02 P01 | 12min | 3 tasks | 6 files |
| Phase 03 P01 | 10min | 2 tasks | 2 files |
| Phase 03 P02 | 7min | 2 tasks | 2 files |
| Phase 03 P03 | 7min | 2 tasks | 4 files |
| Phase 04 P01 | 5min | 2 tasks | 3 files |

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
- [x] Plan 03-03 executed (2026-07-10) — compartment-agnostic local-background-subtracted Fos/TdT measure (D-04) + ChannelHistogram-based threshold re-derivation (D-05); classification repointed to bg-sub measure + re-derived thresholds; Fos_Classifier_20x_bgsub.json/TdT_classifier_bgsub.json authored (self-bootstrapping placeholders, overwritten on live run); grep/cmp/JSON-parse verified, human QuPath run deferred to Plan 03-04
- [x] Plan 03-04: human-in-the-loop run PASSED (2026-07-16) — all four SC confirmed on M3 entry 1 with the final bg-sub script (Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp suppressed); D-04/D-05 all-Negative bug resolved; SCRI-03 marked complete; Phase 3 verified (03-VERIFICATION.md 7/7)

### Blockers

None (Plan 02 is a human GUI step in Fiji; not a blocker, just a handoff).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260706-kfm | DAPI tissue-mask auto-crop CLI (crop_to_tissue.py) for ABBA elastix scaling | 2026-07-06 | n/a (no git) | [260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t](./quick/260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t/) |

---

## Session Continuity

**Last session:** 2026-07-17T00:40:13.344Z
**Stopped at:** Completed 04-01-PLAN.md
**Resume file:** None

**To resume:** Plan 03-03 extended `scripts/02_detect_classify.groovy` (+ byte-identical project hard-copy) with the phase's crux capability: (1) a `localBackgroundSubtractedMean` closure building a peri-cellular annulus outside each marker's own compartment ROI (nucleus for Fos, expanded cell/cytoplasm for TdT) via `RoiTools.buffer`/`subtract`, excluding neighboring detections via `getAllObjectsForRegion` (not centroid-only), and sampling the mean via `ObjectMeasurements` on a throwaway detection object — writes `Nucleus: AF488-T3 mean (bg-sub)` / `Cytoplasm: AF568-T2 mean (bg-sub)` on every detection (D-04); (2) a `derivePeakThreshold` closure re-deriving Fos/TdT positive thresholds on the bg-sub measure via `qupath.ext.braian.ChannelHistogram.zeroPhaseFilter`/`findPeaks`, with a mandatory raw-measure self-check printed against the locked absolute cutoffs (13000.4538/16766.4671) before trusting the bg-sub derivation; new `Fos_Classifier_20x_bgsub.json`/`TdT_classifier_bgsub.json` authored as self-bootstrapping placeholders (old locked threshold + a `note` field) that the script itself overwrites with the live re-derived value on every run, then re-reads via the existing `readSpec` closure; the compound classification loop is now repointed to the bg-sub measure + re-derived thresholds (old absolute cutoffs retained as documented reference only, Pitfall 9 guard). Two Rule-1 bugs auto-fixed: a duplicate `imageData` declaration (compile error) and RESEARCH.md's broken `hasProperty('getNucleusROI')` idiom corrected to `respondsTo('getNucleusROI')`. All static/source verification (grep/cmp/`python3` JSON parse) passed; the plan's `<human-check>` QuPath run-through steps (A5 key-set println, non-negative TdT bg-sub check, raw-measure self-check landing near the locked thresholds, measurable SSp false-positive reduction) were explicitly NOT attempted per CLAUDE.md's GUI-human-only constraint and remain deferred to Plan 03-04. SCRI-03 requirement NOT yet marked complete (requires "tested on one section" per REQUIREMENTS.md, which only happens in Plan 03-04). Outcome: Plan 03-04 ran on M3 entry 1 (2026-07-16) and initially failed 100% Negative; root-caused via /gsd-debug to a D-04 annulus measurement-key mismatch + a buffered-write path, fixed, and the D-05 threshold redesigned to a robust median+k·1.4826·MAD (k=3) cut. On re-run the operator confirmed all four SC with plausible biology (Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp suppressed). SCRI-03 complete; Phase 3 verified. Next: Phase 4 — Biological Plausibility Validation and Imaging Optimization Notes (not yet planned).

**Phase 2 locked decisions (see 02-CONTEXT.md):** histogram-relative detection threshold + relative classifier cutoffs + one global BraiAn.yml (drift-monitored via SERIES-02); hard lock gates = nucleus-area peak 50–150µm² AND DAPI density 500–2000/mm²; Double+ ratio advisory only; Fos+ negative-control gate deferred. Reuse `Fos_Classifier_20x.json` (correct nuclear compartment), rebuild TdT classifier to read Cytoplasm — both done in Plan 02-01.

**Side task:** TRACR registration for another lab in progress (rough, may need a per-section second pass) — see memory.

---
*State initialized: 2026-07-01 | Last updated: 2026-07-16 (Phase 3 complete — 03-04 gate passed, verified)*

## Decisions

- [Phase 03]: bgsub classifier JSONs are self-bootstrapping placeholders (old locked threshold, documented via a note field); script's own runtime ChannelHistogram re-derivation overwrites them each live QuPath run — No live QuPath run is available to this executor (GUI-human-only per CLAUDE.md); the plan allows deriving in-script while preferring the JSON path for D-05's runtime-editable shape
- [Phase 03]: Threshold write-back to bgsub classifier JSON is guarded against NaN (insufficient data / no peak found); leaves the existing file unchanged rather than clobbering it — Preserves D-02's idempotent/safe re-run property
- [Phase 04-01]: Double+/TdT+ ratio reported both as n(Double+)/n(TdT+) and as the co-expression fraction Double+/(Double++TdT+), per hippocampal subfield — Plan spec requires both forms; region_label is a per-cell column so subfield breakdown is free
- [Phase 04-01]: DAPI density via pandas merge joining per-cell region counts to the D-04 per-region-area TSV; nucleus-area peak uses the RESEARCH-specified 10 um^2 histogram-mode function verbatim — Matches qc_detection_gates.groovy's Gate-1 binning for direct comparability
- [Phase 04-01]: SSp Fos+ rate reported as a corroboration anchor (not a true negative control) — Hippocampus-only section has no clean negative control; CONTEXT.md permits documenting the absence and reporting SSp as a sanity anchor
