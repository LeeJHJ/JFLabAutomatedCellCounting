---
phase: 04-biological-plausibility-validation-and-imaging-optimization-
plan: 02
subsystem: analysis
tags: [python, aicspylibczi, pandas, opt-01, opt-02, opt-03, imaging-optimization]

# Dependency graph
requires:
  - phase: 03-detection-script-and-single-section-end-to-end-test
    provides: the two existing region-TSVs (3-plane and hybrid variants) used for the OPT-01 plateau comparison
provides:
  - "scripts/opt01_zplane_audit.py — measures CZI Z-plane/pixel-size metadata, file sizes, and the 2-of-3 DAPI-count plateau data"
  - "04-IMAGING-NOTES.md — OPT-01/02/03 forward-looking acquisition recommendations, every claim tagged [measured]/[inferred]"
affects: [04-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Metadata-only aicspylibczi read (Scaling/Items block for Z-step/pixel size) — no pixel data loaded, completes in seconds on a ~9 GB CZI"
    - "[measured]/[inferred] claim-labeling convention (D-06) applied throughout a forward-looking documentation deliverable"

key-files:
  created:
    - scripts/opt01_zplane_audit.py
    - .planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-IMAGING-NOTES.md
  modified: []

key-decisions:
  - "OPT-01 plateau argument scoped explicitly to 2-of-3 (3-plane vs hybrid, 1.51% DAPI-count difference) — single-plane (Z2) variant has no region-TSV/classified data.qpdata on disk, so a full three-way comparison is deferred as an optional GUI step, not silently assumed"
  - "Recommended target plane count (3 planes at 2.0 um step) framed as provisional pending the deferred single-plane confirmation, not a locked number"
  - "Nyquist-for-3D-reconstruction math included only as background context, explicitly separated from the operative MIP-adequacy question per RESEARCH.md Pitfall 2"
  - "OPT-03 per-subfield table anchored on Phase 2's measured CA1-separable/DG-sg-not-separable finding rather than re-deriving a fresh resolution argument; every resolution number paired with 'at NA=0.8' or flagged [inferred]"

requirements-completed: [OPT-01, OPT-02, OPT-03]

coverage:
  - id: D1
    description: "scripts/opt01_zplane_audit.py measures CZI Z-plane count (6), Z-step (2.0 um), pixel size (0.690535 um/px), raw/MIP file sizes (9.00 GB / 0.97 GB, 9.29x ratio), and the two existing region-TSVs' Root-row Num DAPI-T4 counts (213100 vs 209888, 1.51% diff), with defensive sys.exit guards on missing inputs"
    requirement: "OPT-01, OPT-02"
    verification:
      - kind: unit
        ref: "conda run -n braian python3 scripts/opt01_zplane_audit.py — printed values match all plan acceptance-criteria numbers exactly (6 planes, 2.0 um, 0.690535 um/px, 9.00/0.97 GB, 9.29x, 213100/209888/1.51%)"
        status: pass
      - kind: unit
        ref: "missing-file guards: --czi /nonexistent.czi and --region-3plane /nonexistent.tsv both exit 1 with a clear message, no traceback"
        status: pass
    human_judgment: false
  - id: D2
    description: "04-IMAGING-NOTES.md documents OPT-01 (Z-plane audit + plateau argument + scope-limit), OPT-02 (file-size/storage tradeoff), and OPT-03 (per-subfield resolution assessment), every numeric claim tagged [measured] or [inferred], no pass/fail framing"
    requirement: "OPT-01, OPT-02, OPT-03"
    verification:
      - kind: unit
        ref: "grep -qi 'OPT-01'/'OPT-02'/'OPT-03' and grep -qF '[measured]'/'[inferred]' on 04-IMAGING-NOTES.md — all pass (plan's automated <verify> command)"
        status: pass
      - kind: unit
        ref: "grep -ni 'FAILED|must fix' 04-IMAGING-NOTES.md — no forbidden pass/fail framing found"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 02: Imaging Optimization Notes (OPT-01/02/03) Summary

**Measured CZI Z-plane/file-size/plateau facts feeding a forward-looking `04-IMAGING-NOTES.md` — 6 planes at 2.0 µm step plateau within 1.5% DAPI count against a 4µm sub-range, 9.29× raw:MIP size ratio, and a per-subfield Airyscan-need table anchored on Phase 2's CA1/DG-sg separability finding.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-17T00:42:47Z
- **Completed:** 2026-07-17T00:47:47Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Authored `scripts/opt01_zplane_audit.py`, a metadata-only `aicspylibczi` read (no pixel data loaded) that measures Z-plane count/step/pixel-size from the raw CZI, file sizes for the raw CZI vs. primary MIP OME-TIFF, and the Root-row `Num DAPI-T4` counts from the two existing region-TSVs (3-plane vs. hybrid) — all printed values matched the plan's acceptance criteria exactly on the live project files (6 planes, 2.0 µm step, 0.690535 µm/px, 9.00 GB/0.97 GB/9.29×, 213,100/209,888/1.51%).
- Verified defensive `sys.exit` guards trigger cleanly (no traceback) on a missing CZI and a missing region-TSV.
- Authored `04-IMAGING-NOTES.md` covering OPT-01 (Z-plane audit, 2-of-3 empirical plateau argument with the single-plane-not-run scope-limit stated explicitly, Nyquist-for-3D background framing, section-thickness cross-check), OPT-02 (measured file sizes, full-series storage projection against the 854 GB free NVMe, keep-raw-vs-MIP-now recommendation), and OPT-03 (per-subfield Airyscan-need table anchored on the Phase-2 CA1-separable/DG-sg-not-separable finding, every resolution number paired with "at NA=0.8" or flagged `[inferred]`), with the TRAP2-paper provenance hedged honestly (403-blocked).

## Task Commits

Each task was committed atomically:

1. **Task 1: Author opt01_zplane_audit.py (CZI Z-count/step + file sizes + DAPI-count plateau)** - `37bd7c1` (feat)
2. **Task 2: Write 04-IMAGING-NOTES.md (OPT-01/02/03, measured/inferred labeled)** - `a7c35df` (docs)

## Files Created/Modified
- `scripts/opt01_zplane_audit.py` - metadata-only CZI Z-plane/pixel-size read + file-size measurement + region-TSV plateau comparison, with defensive missing-file guards
- `.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-IMAGING-NOTES.md` - OPT-01/02/03 forward-looking imaging-recommendations record, separate from the VAL-01 record (D-05)

## Decisions Made
- The OPT-01 plateau argument is stated as an explicit 2-of-3 empirical comparison (3-plane vs. hybrid, 1.51% DAPI-count difference) rather than silently assuming a full three-way confirmation exists — the single-plane (Z2) variant has never been detection-run, and the document states this as a deferred optional GUI step, per RESEARCH.md Open Question 2's resolution option (b).
- The recommended target plane count (3 planes at the current 2.0 µm step) is framed as provisional, pending the deferred single-plane classification run, not a locked recommendation.
- Nyquist-for-3D-reconstruction math is included only as background context (explicitly labeled not the operative question), keeping the actual OPT-01 recommendation grounded in the empirical plateau comparison, per RESEARCH.md Pitfall 2.
- OPT-03's per-subfield table reuses Phase 2's already-measured CA1-separable/DG-sg-not-separable finding as the load-bearing evidence rather than re-deriving a fresh optical argument, and every quantitative resolution figure is paired with "at NA=0.8" or explicitly flagged `[inferred]` per RESEARCH.md Pitfall 3.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' automated verification commands passed without needing any Rule 1/2/3 auto-fixes.

## Issues Encountered

None. All measured values (CZI metadata, file sizes, region-TSV DAPI counts) matched the plan's acceptance-criteria numbers on first run against the live project files — no debugging needed.

## User Setup Required

None - no external service configuration required. This plan has no live QuPath dependency (unlike 04-01's export script, whose live run is deferred to Plan 04-03); both tasks are fully self-contained Python/documentation work.

## Next Phase Readiness
- `04-IMAGING-NOTES.md` is complete and self-contained — no dependency on Plan 04-03's live QuPath export.
- Plan 04-03 (VAL-01 live run + `04-VALIDATION.md`) can proceed independently; this plan's artifacts do not block it.
- Open item carried forward (not a blocker): the single-plane (Z2) variant's detection+classification run remains deferred — if a future series-planning pass wants to close the 2-of-3 gap, that is a scoped, optional follow-up.

---
*Phase: 04-biological-plausibility-validation-and-imaging-optimization-*
*Completed: 2026-07-17*

## Self-Check: PASSED

All claimed files found on disk (`scripts/opt01_zplane_audit.py`, `04-IMAGING-NOTES.md`); both claimed commit hashes (`37bd7c1`, `a7c35df`) found in `git log`.
