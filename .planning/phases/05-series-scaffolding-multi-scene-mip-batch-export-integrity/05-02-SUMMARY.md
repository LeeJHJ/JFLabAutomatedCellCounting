---
phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity
plan: 02
subsystem: infra
tags: [groovy, qupath, python, export-integrity, tsv]

# Dependency graph
requires: []
provides:
  - "03_export_val01_metrics.groovy writes per-entry output pairs (stem from sanitized QuPath entry name) instead of two fixed filenames"
  - "scripts/verify_export_integrity.py — reusable read-only checker for the non-clobbering guarantee"
affects: [phase-08-classification, phase-10-aggregation-export]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-entry output path via getProjectEntry().getImageName() + invalidChars sanitization + buildPathInProject (reused from run_braian_detection.groovy / export_region_dapi_reference.groovy)"

key-files:
  created:
    - scripts/verify_export_integrity.py
  modified:
    - scripts/03_export_val01_metrics.groovy
    - "M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy"

key-decisions:
  - "Reused the invalidChars sanitization idiom verbatim from run_braian_detection.groovy and the null-fallback entry-name idiom from export_region_dapi_reference.groovy, rather than inventing a new pattern"
  - "Added an explicit empty-stem guard (throws RuntimeException) even though entry names are unique by construction (D-04) — makes the T-05-02-02 assumption explicit rather than silent"
  - "verify_export_integrity.py skips the multi-entry clobbering assertion (with an explicit printed message) when fewer than 2 distinct stems exist, so it is runnable now against the single-entry M3 project and again in Phase 8/10 on the 5-entry series"

requirements-completed: [EXP-02]

coverage:
  - id: D1
    description: "03_export_val01_metrics.groovy derives both output filenames from the sanitized running QuPath entry name via buildPathInProject, eliminating cross-entry TSV clobbering on \"Run for project\""
    requirement: "EXP-02"
    verification:
      - kind: unit
        ref: "grep -c buildPathInProject scripts/03_export_val01_metrics.groovy == 2 && grep -q getProjectEntry"
        status: pass
      - kind: unit
        ref: "cmp scripts/03_export_val01_metrics.groovy \"M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy\""
        status: pass
    human_judgment: false
  - id: D2
    description: "Column headers (percell 7 cols, region 5 cols) and downstream row-building/write logic are unchanged — only the output path construction changed"
    requirement: "EXP-02"
    verification:
      - kind: unit
        ref: "git diff scripts/03_export_val01_metrics.groovy shows changes confined to header comment + path-construction block; percellHeader/regionHeader/pixel-calibration block untouched"
        status: pass
    human_judgment: false
  - id: D3
    description: "scripts/verify_export_integrity.py codifies the non-clobbering assertion: percell/region pairing, even file count == 2 * distinct stems, and non-identical per-entry row counts when >= 2 entries exist"
    requirement: "EXP-02"
    verification:
      - kind: integration
        ref: "synthetic fixture (2 distinct stems, differing row counts) -> exits 0, PASS"
        status: pass
      - kind: integration
        ref: "synthetic fixture (unpaired percell file, no region pair) -> exits 1, FAIL with clear message"
        status: pass
      - kind: integration
        ref: "synthetic fixture (2 stems, identical row counts simulating a clobber) -> exits 1, FAIL with clobbering-guard message"
        status: pass
      - kind: integration
        ref: "single-stem fixture -> exits 0, PASS, multi-entry assertion explicitly skipped"
        status: pass
    human_judgment: false
  - id: D4
    description: "verify_export_integrity.py is read-only over --results and never mutates files"
    verification:
      - kind: unit
        ref: "md5sum before/after running the checker against a fixture dir — identical"
        status: pass
    human_judgment: false

# Metrics
duration: 15min
completed: 2026-07-18
status: complete
---

# Phase 5 Plan 2: EXP-02 Batch-Export Non-Clobbering Fix Summary

**Fixed `03_export_val01_metrics.groovy` to derive both output TSV filenames from the sanitized running QuPath entry name (via `buildPathInProject`), and added `scripts/verify_export_integrity.py` to codify the non-clobbering guarantee for the future 5-entry wBA1-3 series.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-18T22:51:41Z
- **Completed:** 2026-07-18T22:54:24Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 new, 2 modified — one modified file is a byte-identical dual-location copy)

## Accomplishments
- `03_export_val01_metrics.groovy` now writes `results/<sanitized-entry-name>__val01_percell_export.tsv` and `results/<sanitized-entry-name>__val01_region_area.tsv` instead of two fixed filenames (`results/val01_percell_export.tsv`, `results/val01_region_area.tsv`) — a QuPath "Run for project" across N entries now produces 2*N distinct files with no cross-entry clobbering (EXP-02).
- Column headers (`percellHeader`, `regionHeader`) and all downstream row-building / truncate-write logic are byte-for-byte unchanged — only the two `File(...)` construction lines changed (D-07 scope lock verified via `git diff`).
- Both the canonical `scripts/` copy and the QuPath project's `scripts/` copy are byte-identical (`cmp` confirms).
- New `scripts/verify_export_integrity.py`: a read-only CLI checker that asserts percell/region stem pairing, an even total file count equal to `2 * distinct stems`, and (when >= 2 entries exist) that per-entry row counts are not all identical — the signature of a clobbering regression. Prints a per-stem row-count summary and a final PASS/FAIL; exits non-zero on any failed assertion.

## Task Commits

Each task was committed atomically:

1. **Task 1: Derive per-entry output filenames in 03_export_val01_metrics.groovy** - `eb53e05` (fix)
2. **Task 2: Add scripts/verify_export_integrity.py** - `24aba76` (feat)

**Plan metadata:** (this commit follows)

## Files Created/Modified
- `scripts/03_export_val01_metrics.groovy` - EXP-02 fix: output paths now derive from `getProjectEntry().getImageName()` + `invalidChars` sanitization + `buildPathInProject`; empty-stem guard added; header comment updated to describe the new per-entry naming convention
- `M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy` - byte-identical dual-location copy (established deploy convention)
- `scripts/verify_export_integrity.py` - new read-only CLI checker for the export non-clobbering guarantee

## Decisions Made
- Reused the `invalidChars` regex and `getProjectEntry()` idiom verbatim from `run_braian_detection.groovy`, combined with the defensive null-fallback idiom from `export_region_dapi_reference.groovy`, rather than inventing a new sanitization pattern.
- Added an explicit empty-stem guard (throws with a clear message) even though entry names are unique by construction (D-04) — makes the T-05-02-02 threat-model assumption explicit rather than silently trusting it.
- Designed `verify_export_integrity.py` to gracefully skip (with an explicit printed message, not silent) the multi-entry clobbering assertion when fewer than 2 distinct stems are present, so the same checker validates both the current single-entry M3 project and the eventual 5-entry wBA1-3 series without modification.

## Deviations from Plan

None - plan executed exactly as written. `resultsDir.mkdirs()` was removed as specified (buildPathInProject resolves against the project base dir; no sibling script calls mkdir on results/).

## Issues Encountered

None. The existing `M3 Hippocampus 20x 062926 3 plane/results/` directory contains legacy fixed-name TSVs from before this fix (`val01_percell_export.tsv`, `val01_region_area.tsv`) — these predate the new naming convention and were left untouched (out of scope for this plan; they are historical single-run snapshots, not something this fix rewrites retroactively). `verify_export_integrity.py` correctly reports "no per-entry export files found" against that directory since none of its files match the new `__val01_percell_export.tsv` / `__val01_region_area.tsv` suffix pattern — this is expected until an operator re-runs "Run for project" with the fixed script (deferred to plan 05-03 / Phase 8).

Verified all four checker code paths (PASS single-entry, PASS multi-entry with differing counts, FAIL unpaired file, FAIL identical-row-count clobber) against synthetic fixtures in the scratchpad, since no live multi-entry classified series exists yet in Phase 5.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The EXP-02 batch-export mechanism is fixed and scriptably verified; it is not yet exercised against the real 5-entry wBA1-3 series (that data doesn't exist until Phase 8's classification pass completes) — the full 10-non-empty-TSV proof is correctly sequenced to Phase 8/10, not fabricated here.
- `scripts/verify_export_integrity.py` is ready to run against `results/` once the 5 entries are classified and "Run for project" is executed.
- No blockers for Wave 2 (plan 05-03, human-verify gate) or downstream phases.

---
*Phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity*
*Completed: 2026-07-18*
