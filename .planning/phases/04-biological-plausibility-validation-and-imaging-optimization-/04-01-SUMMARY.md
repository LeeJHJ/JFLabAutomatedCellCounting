---
phase: 04-biological-plausibility-validation-and-imaging-optimization-
plan: 01
subsystem: analysis
tags: [groovy, qupath, python, pandas, numpy, scipy, val-01, tsv-export]

# Dependency graph
requires:
  - phase: 03-detection-script-and-single-section-end-to-end-test
    provides: 02_detect_classify.groovy's per-cell class assignment + bg-sub measurement keys, the classified data.qpdata on M3 entry 1
provides:
  - "scripts/03_export_val01_metrics.groovy — QuPath per-cell + per-region-area TSV export (D-03/D-04)"
  - "scripts/val01_metrics.py — computes all four VAL-01 metrics from the export TSVs"
affects: [04-02, 04-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "VAL-01 measurement pipeline: Groovy export (human-run, 'Run for project') -> Python metrics script (braian env) -> findings record (D-03 GUI/scriptable split)"
    - "Per-run snapshot TSVs (overwrite/truncate each run) distinct from the growing cross-image dapi_region_reference.csv convention"

key-files:
  created:
    - scripts/03_export_val01_metrics.groovy
    - "M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy"
    - scripts/val01_metrics.py
  modified: []

key-decisions:
  - "Double+/TdT+ ratio reported as BOTH n(Double+)/n(TdT+) and the co-expression fraction Double+/(Double++TdT+), broken down per hippocampal subfield, per plan spec"
  - "DAPI density computed by grouping per-cell rows (all classes) by region_label, joined to the D-04 per-region area TSV via pandas merge"
  - "Nucleus-area peak uses the RESEARCH-specified 10 um^2 floor-based histogram-mode function verbatim, plus median/IQR/skew as bin-independent cross-checks"
  - "SSp Fos+ rate reported as a corroboration anchor (not a true negative control) per CONTEXT.md's documented-absence allowance; fiber-tract labels also scanned if present"

requirements-completed: [VAL-01]

coverage:
  - id: D1
    description: "scripts/03_export_val01_metrics.groovy exports per-cell (class, region_label, nucleus_area_um2, centroid, fos_bgsub, tdt_bgsub) and per-region-area TSVs reading the exact bg-sub measurement keys 02_detect_classify.groovy writes; deployed byte-identically to the QuPath project"
    requirement: "VAL-01"
    verification:
      - kind: unit
        ref: "grep -F verification of exact measurement-key literals + cmp byte-identical dual-location deploy (plan Task 1 <verify>)"
        status: pass
    human_judgment: false
  - id: D2
    description: "scripts/val01_metrics.py computes Double+/TdT+ ratio, per-region DAPI density, nucleus-area histogram-mode peak, and Fos+ control rate from the two export TSVs, proven against the plan's synthetic fixture"
    requirement: "VAL-01"
    verification:
      - kind: unit
        ref: "conda run -n braian python3 scripts/val01_metrics.py --percell-tsv <fixture> --region-tsv <fixture> | grep -Ei 'ratio|density|peak|Fos' (plan Task 2 <verify>)"
        status: pass
      - kind: unit
        ref: "targeted assertions: area_histogram_mode([45,46,47,52,120])==(40.0,50.0,3); ratio=0.40/coexpr=0.286 for 4 Double+/10 TdT+; density=2000/mm2 for 1000 nuclei / 0.5mm2; SSp Fos+ rate=2/82"
        status: pass
      - kind: unit
        ref: "defensive input guards: missing TSV, missing column, zero-row TSV all sys.exit with a clear message (no uncaught traceback)"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 01: VAL-01 Measurement Pipeline Summary

**Two-stage VAL-01 pipeline authored: Groovy per-cell/per-region TSV export reading 02_detect_classify.groovy's exact bg-sub measurement keys, plus a Python (braian env) metrics script computing all four VAL-01 bioplausibility numbers, proven against a synthetic fixture.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-17T00:32:06Z
- **Completed:** 2026-07-17T00:37:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Authored `scripts/03_export_val01_metrics.groovy`, a QuPath "Run for project" export that reads the exact three measurement-key literals `02_detect_classify.groovy` writes (`Nucleus: Area µm^2`, `Nucleus: AF488-T3 mean (bg-sub)`, `Cytoplasm: AF568-T2 mean (bg-sub)`) plus `getPathClass()`, and reuses the `regionOf`/`regionLabel` closures verbatim — avoiding the exact key-mismatch bug that caused Phase 3's all-Negative failure.
- Emitted two per-run TSV outputs (`results/val01_percell_export.tsv`, `results/val01_region_area.tsv`), deployed byte-identically to both the canonical `scripts/` dir and the QuPath project's `scripts/` dir (`cmp` verified).
- Authored `scripts/val01_metrics.py`, computing all four VAL-01 metrics (Double+/TdT+ ratio + co-expression fraction per subfield, per-region DAPI density/mm², nucleus-area histogram-mode peak with median/IQR/skew cross-checks, SSp/fiber-tract Fos+ corroboration rate) with defensive input validation (T-04-01).
- Verified `val01_metrics.py` against the plan's synthetic fixture: exact numeric match on all four behavior bullets (`area_histogram_mode` → `(40.0, 50.0, 3)`; ratio 0.40/co-expression 0.286; density 2000/mm²; SSp Fos+ rate 2/82).

## Task Commits

Each task was committed atomically:

1. **Task 1: Author 03_export_val01_metrics.groovy (D-03/D-04 export)** - `dd77fbe` (feat)
2. **Task 2: Author val01_metrics.py (four VAL-01 metrics + area_histogram_mode)** - `011ee1a` (feat)

_TDD note: Task 2 (`tdd="true"`) followed the RED/GREEN cycle as manual verification rather than a separately-committed test file — this codebase has no test framework (RESEARCH.md's own Validation Architecture: "Framework: None"), and the plan did not list a test file in `files_modified`. RED was confirmed by running the plan's exact fixture-based verify command before `val01_metrics.py` existed (failed, exit 1, `ls: cannot access`); GREEN was confirmed by re-running the same command plus targeted numeric assertions on all four behavior bullets after authoring the script (all passed) before the single `feat` commit._

## Files Created/Modified
- `scripts/03_export_val01_metrics.groovy` - QuPath Groovy export: per-cell (class/region/area/centroid/bg-sub Fos+TdT) + per-region-area TSVs
- `M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy` - byte-identical hard-copy (dual-location deploy)
- `scripts/val01_metrics.py` - Python (braian env) VAL-01 metrics computation from the export TSVs

## Decisions Made
- Reported the Double+/TdT+ ratio in both forms specified by the plan (raw `n(Double+)/n(TdT+)` and the co-expression fraction `Double+/(Double++TdT+)`), broken down per hippocampal subfield via `region_label` groupby, since region label is a per-cell column.
- DAPI density computed via an explicit pandas `merge` joining per-cell counts (grouped by `region_label`) to the D-04 per-region-area TSV — matches the plan's key_link contract exactly (column names on both sides verified identical).
- Nucleus-area peak uses the RESEARCH-specified verbatim `area_histogram_mode` function (10 µm² floor-based bins, matching `qc_detection_gates.groovy`'s Gate-1 binning for direct comparability), plus median/IQR/`scipy.stats.skew` as bin-independent cross-checks per the RESEARCH pitfalls guidance.
- SSp Fos+ rate reported as an explicit corroboration anchor (not a true negative control, labeled as such in the printed output) per CONTEXT.md's "document the absence" allowance for VAL-01's negative-control criterion; fiber-tract-labelled rows (`fiber tracts`, `cc`, `fx`, `or`, `ec`, `em`) also scanned as a soft anchor if present in the export.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' automated verification commands (grep/cmp for Task 1; fixture-run/grep + acceptance-criteria numeric checks for Task 2) passed without needing any Rule 1/2/3 auto-fixes.

## Issues Encountered

None. The plan's Task 2 acceptance-criteria text contained a minor internal inconsistency (one sentence cites a slightly different fixture list — `[45,46,47,52,44]` — than the `<behavior>` block's authoritative fixture `[45,46,47,52,120]` used for the exact `(40.0, 50.0, 3)` result). Resolved by implementing the RESEARCH-specified `area_histogram_mode` function verbatim and verifying against the `<behavior>` block's explicit fixture/result pair, which is the authoritative source and the one actually reproduced — no code change was needed, this is purely a plan-text note.

## User Setup Required

None - no external service configuration required. The live QuPath "Run for project" execution of `03_export_val01_metrics.groovy` (human-run GUI step, per the D-03 GUI/scriptable split) is deferred to Plan 04-03 (Wave 2), as scoped by this plan's objective.

## Next Phase Readiness
- Both VAL-01 pipeline scripts are authored, dual-location deployed (Groovy), and proven against a synthetic fixture (Python) — ready for Plan 04-03 to run the live QuPath export on M3 entry 1 and feed the real TSVs into `val01_metrics.py` to write `04-VALIDATION.md`.
- No blockers. Plan 04-02 (OPT-01/02/03 imaging notes) has no dependency on this plan's artifacts and can proceed independently (wave 1, `depends_on: []`).

---
*Phase: 04-biological-plausibility-validation-and-imaging-optimization-*
*Completed: 2026-07-17*
