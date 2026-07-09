---
phase: 02-detection-parameter-lock
plan: 02
type: execute
status: complete
requirements: [SCRI-02, CLASS-01]
completed: 2026-07-09
---

# Plan 02-02 Summary — Detection Tuning & Lock

## Objective
Human-in-the-loop tuning of BraiAnDetect on M3 062926 entry 1 (DG + CA1), then write the
locked detection params + re-derived classifier thresholds into the config and record the lock.

## Outcome: LOCKED
Detection parameters and both classifier thresholds are locked for the M3 series (first-run
validation). See [02-LOCK-RECORD.md](02-LOCK-RECORD.md) for the full record.

**Locked values:** `sigmaMicrons 2.5`, `nPeak 2` histogram threshold (≈2536), `min/max area 20/250`,
`cellExpansion 5.0`, `classForDetections = allen_mouse_10um_java`; Fos ≥ 13000.4538
(`Nucleus: AF488-T3 mean`), TdT ≥ 16766.4671 (`Cytoplasm: AF568-T2 mean`).

**Gates:** SCRI-02 ✓ (non-zero Fos+/TdT+, channel names verified live). CLASS-01 ✓ (Fos+ in nuclei).
D-05.1 area peak 40–50 µm² (accepted; sigma tradeoff for cortical completeness). D-05.2 density
DG 2886 / CA1 3508 /mm² (above the seed — seed superseded by the empirical internal reference).
D-06 Double+/TdT+ ≈ 0.40 (advisory). D-07 skipped.

## Key deviations (→ Phase 3 / SCRI-03)
1. **BraiAnDetect classifier list can't apply two markers to one DAPI set** (A3 risk confirmed) →
   classification moved to `classify_markers.groovy` (nucleus-anchored, no overlap). Export path
   for Phase 3 must use this, not `BraiAn.yml classifiers:`.
2. **SSp regional autofluorescence** breaks absolute thresholds (SSp median 488 > Fos cutoff) →
   Phase 3 refinement to a background-robust measure (nucleus:cytoplasm ratio / local-bg subtraction).
3. Detection was confined to the atlas Root (was detecting the whole image); DG-sg + ventricles
   excluded from marker classification; git repo initialized; QuPath 0.6.0 API fixes to the QC harness.

## Key files
**Created:** `scripts/classify_markers.groovy`, `scripts/run_braian_detection.groovy`,
`scripts/export_region_dapi_reference.groovy`, `scripts/build_dapi_reference.py`,
`reference/README.md`, `02-LOCK-RECORD.md`
**Locked (edited):** `BraiAn.yml`, `Fos_Classifier_20x.json`, `TdT_classifier.json`,
`scripts/qc_detection_gates.groovy`

## Self-Check: PASSED
BraiAn.yml parses with topology/compartment invariants intact; both classifier thresholds are
numeric and compartments unchanged (Fos nuclear, TdT cytoplasmic); lock record captures D-05
values, D-06 advisory, D-07 skip, and the Phase-3 deviations.
