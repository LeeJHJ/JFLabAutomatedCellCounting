---
phase: 04-biological-plausibility-validation-and-imaging-optimization-
plan: 03
subsystem: analysis
tags: [python, pandas, numpy, val-01, bioplausibility, findings-record, qupath-export]

# Dependency graph
requires:
  - phase: 04-biological-plausibility-validation-and-imaging-optimization-
    provides: "04-01's scripts/03_export_val01_metrics.groovy (export) and scripts/val01_metrics.py (metrics computation), proven against a synthetic fixture"
provides:
  - "04-VALIDATION-RECORD.md — the VAL-01 scientific findings record, all four metrics computed on the real M3 entry-1 export with written interpretation"
  - "Rule-1 bug fix in scripts/val01_metrics.py compute_density() — the density join now works on real data (was silently empty on real data due to a hemisphere-prefix mismatch)"
  - "deferred-items.md — logs an out-of-scope discovery (per-cell region-label resolution appears hemisphere-asymmetric for at least CA1) for the full series to investigate"
affects: [SERIES-01, SERIES-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bilateral-sum density join: aggregate is_leaf region-area rows by acronym across hemispheres before joining to per-cell region counts, since the per-cell export has no hemisphere column"
    - "D-01 findings-record register: value + band flag + written interpretation per metric, explicit 'flagged out of range, interpreted as follows' language, never FAILED/must-fix"

key-files:
  created:
    - .planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-VALIDATION-RECORD.md
    - .planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/deferred-items.md
  modified:
    - scripts/val01_metrics.py

key-decisions:
  - "Reported the per-subfield ratio breakdown (CA1/CA2/CA3/DG-mo/DG-po/DG-sg) rather than only the whole-section aggregate, revealing CA1 (0.295) and DG-mo (0.101) individually land inside the 10-40% target band even though the whole-section aggregate (0.455) reads out of range"
  - "Did not attempt to fix the deeper region-label hemisphere-resolution finding (D-1 in deferred-items.md) — root cause lives in locked Phase-3/Plan-04-01 Groovy closures, out of this task's file scope and Phase 4's D-01 mandate; logged and flagged in the record instead"
  - "Reported the real measured SSp Fos+ corroboration rate (47.1%) as-is rather than reconciling it toward the Task-1 checkpoint's qualitative 'SSp suppressed' prior attestation — reconciled by clarifying what 'suppressed' meant (elimination of the old autofluorescence-threshold artifact, not a low absolute rate)"

requirements-completed: [VAL-01]

coverage:
  - id: D1
    description: "val01_metrics.py run against the real M3 entry-1 export TSVs (213,106 cells, 450 regions); a real density-join bug (zero-row join due to hemisphere-prefix mismatch) was found and fixed"
    requirement: "VAL-01"
    verification:
      - kind: unit
        ref: "conda run -n braian python3 scripts/val01_metrics.py — re-run after the fix, density table populated for all 146 regions, whole-section grey cross-check (3877.4/mm2) matches Phase 2's root reference (~3866-3900/mm2) within noise"
        status: pass
    human_judgment: false
  - id: D2
    description: "04-VALIDATION-RECORD.md written with value + interpretation for all four VAL-01 metrics (D-01 register, D-02 four candidates, D-06 claim labels), automated acceptance grep passes"
    requirement: "VAL-01"
    verification:
      - kind: unit
        ref: "plan Task 2 <verify> automated command: test -f + grep -qiE Double\\+|ratio + grep density/area/SSp + grep -qF '[measured]' + ! grep FAILED|must fix"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 03: VAL-01 Findings Record Summary

**Computed all four VAL-01 bioplausibility metrics on the real 213,106-cell M3 export, fixed a real density-join bug found in the process, and wrote 04-VALIDATION-RECORD.md — a D-01 findings record showing the whole-section Double+/TdT+ ratio (45.5%) and SSp Fos+ rate (47.1%) both read out of range, but the best-resolved hippocampal subfields (CA1, DG-mo) individually land inside their target bands.**

## Performance

- **Duration:** 20 min (this continuation session; Task 1 was completed and approved in a prior session)
- **Started:** 2026-07-17T14:45:00Z
- **Completed:** 2026-07-17T15:05:29Z
- **Tasks:** 1 (Task 2 — Task 1 was already complete/approved before this session)
- **Files modified:** 3 (`scripts/val01_metrics.py`, `04-VALIDATION-RECORD.md`, `deferred-items.md`)

## Accomplishments
- Ran `scripts/val01_metrics.py` against the real, operator-produced `val01_percell_export.tsv` (213,106 cells) and `val01_region_area.tsv` (450 regions, 285 leaf / 165 non-leaf) for the first time — the first real-data run of this pipeline (Plan 04-01 only proved it against a synthetic fixture).
- Found and fixed a genuine Rule-1 bug: `compute_density()` joined on the bare `region_label` column, but the region-area export's `region_label` carries a `"Left: "/"Right: "` hemisphere prefix while the per-cell export's `region_label` is the bare acronym — the join matched zero rows and metric #2 printed an empty table on the first real run. Fixed by aggregating leaf-region areas across hemispheres by `acronym` before joining; verified via a whole-section cross-check (`grey` aggregate density 3,877.4/mm² lands within noise of Phase 2's independently-measured `root` density ~3,866–3,900/mm²).
- Wrote `04-VALIDATION-RECORD.md`: all four VAL-01 metrics with measured value, band flag, and written interpretation. Double+/TdT+ ratio flagged out of range at the whole-section aggregate (raw 0.836 / coexpr 0.455) but the per-subfield breakdown shows CA1 (0.295) and DG-mo (0.101) individually inside the 10–40% target band; all four D-02 candidates weighed, including the 0.40→0.45 Phase-2→Phase-3 methodology-shift data point. DAPI density cites Phase 2's mis-calibration finding rather than re-deriving the seed; several hippocampal subfields (CA1, CA3, DG-mo, DG-sg) read inside the 500–2,000/mm² band this run. Nucleus-area peak reproduces Phase 2's [40,50) µm² sigma=2.5 finding exactly. Fos+ control documents the negative-control absence and reports the real measured SSp corroboration rate (47.1%, n=9,324) honestly, reconciling it against the Task-1 checkpoint's qualitative "SSp suppressed" prior attestation.
- Logged a deeper, out-of-scope discovery to `deferred-items.md`: per-cell region-label resolution appears to under-represent one hemisphere for at least CA1 (current `CA1` cell count matches Phase 2's Right-hemisphere-only raw count exactly; a `Left: grey` annotation is anomalously flagged `is_leaf=true`, spatially disjoint from `CA1`-labeled cells) — root cause is in locked Phase-3/Plan-04-01 Groovy region-labeling closures, out of this task's file scope and Phase 4's D-01 mandate, so it was documented and flagged rather than fixed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Human runs the Groovy export in QuPath and confirms populated TSVs** — completed and approved in a prior session (checkpoint gate, no separate commit tracked in this plan's execution — the export TSVs are gitignored data outputs, not tracked artifacts)
2. **Task 2: Compute VAL-01 metrics on real data and write 04-VALIDATION-RECORD.md** - `ef97e7a` (fix)

## Files Created/Modified
- `scripts/val01_metrics.py` - Fixed `compute_density()`'s region-area join (bilateral-sum-by-acronym instead of bare region_label, which matched zero rows against the real export's hemisphere-prefixed region-area TSV)
- `.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-VALIDATION-RECORD.md` - VAL-01 findings record: four metrics, each with measured value, band flag, and written interpretation (D-01/D-02/D-06)
- `.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/deferred-items.md` - Logs the out-of-scope hemisphere-resolution finding (D-1) and cross-references the density-join fix (D-2, resolved in this task)

## Decisions Made
- Reported the per-subfield Double+/TdT+ ratio breakdown rather than only the whole-section aggregate — this surfaced that CA1 (0.295) and DG-mo (0.101), the two best-resolved hippocampal subfields, individually land inside the 10–40% target band, while the whole-section aggregate (0.455) is pulled upward by the broad `grey` catch-all bucket (49.7% of all Double+ cells) and numerous small-n peripheral cortical regions.
- Left the deeper hemisphere-resolution finding (deferred-items.md D-1) unfixed and explicitly out of scope — its root cause is in locked Groovy files from Phase 3 (`02_detect_classify.groovy`) and Plan 04-01 (`03_export_val01_metrics.groovy`), neither in this task's `files` list, and re-deriving detection/classification logic is explicitly excluded by D-01. Flagged instead, per the Scope Boundary rule.
- Reported the real measured SSp Fos+ corroboration rate (47.1%) as-is rather than silently reconciling it toward the Task-1 checkpoint's carried-forward qualitative claim that SSp was "suppressed" post-Phase-3-fix — instead interpreted what "suppressed" actually meant (elimination of the specific pre-Phase-3 autofluorescence-threshold artifact where SSp's raw intensity exceeded the old absolute cutoff, not a low absolute post-fix rate) and presented both the measured number and the two non-exclusive candidate explanations (genuine regional sensory activation vs. residual global-threshold sensitivity) per D-01's "do not silently pass or silently fail" framing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `compute_density()`'s region-area join, which matched zero rows on real data**
- **Found during:** Task 2, first real-data run of `scripts/val01_metrics.py`
- **Issue:** `compute_density()` joined per-cell region counts to `val01_region_area.tsv` on the bare `region_label` column. The region-area export's `region_label` carries a `"Left: "/"Right: "` hemisphere prefix (e.g. `"Right: CA1"`), while the per-cell export's `region_label` is the bare leaf acronym (e.g. `"CA1"`) — the inner-join matched zero rows, so metric #2 (DAPI density) printed an empty table. This bug was invisible against Plan 04-01's synthetic fixture (which used a trivial single-row region-area table with no hemisphere prefix) and only surfaced on the real, hemisphere-annotated export.
- **Fix:** `compute_density()` now filters `region_area` to `is_leaf == True` rows, groups by `acronym` summing `area_mm2` across both hemispheres, then joins per-cell region counts on `acronym == region_label`. This computes a bilateral-sum density (total nuclei ÷ total leaf-region area per acronym across both hemispheres), matching the grain of the per-cell export (which carries no hemisphere column).
- **Files modified:** `scripts/val01_metrics.py`
- **Verification:** Re-ran the script end-to-end against the real export; the density table now populates all 146 matched regions. Cross-checked the whole-section `grey` aggregate (3,877.4/mm²) against Phase 2's independently-measured `root` density (~3,866–3,900/mm² per hemisphere, `reference/dapi_region_reference.csv`) — the two land within noise of each other, corroborating the fix computes a sane bilateral density.
- **Committed in:** `ef97e7a` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug). One additional finding (hemisphere-asymmetric per-cell region-label resolution) was discovered but deliberately NOT auto-fixed — logged to `deferred-items.md` per the Scope Boundary rule (root cause in locked, out-of-scope Groovy files; re-deriving classification logic is out of Phase 4's D-01 mandate).
**Impact on plan:** The density-join fix was necessary for the record to contain any density findings at all (Rule 1: code didn't work as intended on real data). No scope creep — the deferred hemisphere-resolution finding was explicitly left unfixed rather than chased into an out-of-scope Groovy investigation.

## Issues Encountered
None beyond the density-join bug (documented above as an auto-fixed deviation) and the deferred hemisphere-resolution finding (documented in `deferred-items.md`, not an "issue" requiring resolution in this task — it is a flagged note for the full series per D-01's own framing).

## User Setup Required
None - no external service configuration required. Task 1's human-in-the-loop QuPath export was already completed and approved before this continuation session began.

## Next Phase Readiness
- VAL-01 requirement complete: `04-VALIDATION-RECORD.md` records a computed value and written interpretation for all four metrics, D-01's findings-record register honored throughout (no metric written as "FAILED"/"must fix"), D-02's four candidates weighed for the ratio, D-06 claim labels (`[measured]`/`[inferred]`/`[ASSUMED]`) applied.
- Plan 04-02 (OPT-01/02/03 imaging notes) is independent (`depends_on: []`) and unaffected by this plan.
- Recommendation for the full series (SERIES-01/02, out of scope here): confirm or rule out the deferred hemisphere-resolution finding (`deferred-items.md` D-1) before batch-processing additional sections, since a silent per-hemisphere region-label gap would bias whole-brain density/ratio aggregates across many sections, not just this one.
- No blockers to Phase 4 completion.

---
*Phase: 04-biological-plausibility-validation-and-imaging-optimization-*
*Completed: 2026-07-17*

## Self-Check: PASSED

All claimed files found on disk (`04-VALIDATION-RECORD.md`, `deferred-items.md`, `scripts/val01_metrics.py`); claimed commit hash `ef97e7a` found in `git log`; automated acceptance-check command (test -f + grep ratio/density/area/SSp/`[measured]` + no FAILED/must-fix) re-run and confirmed passing.
