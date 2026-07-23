---
phase: 03-detection-script-and-single-section-end-to-end-test
plan: 04
subsystem: detection-pipeline
tags: [qupath, groovy, human-verify, phase-gate, background-subtraction, threshold-derivation, trap2]

# Dependency graph
requires:
  - phase: 03-detection-script-and-single-section-end-to-end-test (Plans 01-03)
    provides: "final scripts/02_detect_classify.groovy — D-01/D-02 guards, nucleus-anchored compound classification, atlas region labels, per-region count rollup, Atlas_X sanity print, D-04 local-background-subtracted Fos/TdT measure, D-05 self-calibrating robust threshold"
provides:
  - "Human-confirmed Phase-3 gate pass: all four SC verified on M3 entry 1 with the final bg-sub-based script"
  - "SCRI-03 satisfied end-to-end (tested on one section)"
  - "Locked series seed k=3 for the D-05 robust threshold (median + k*1.4826*MAD)"
  - "Biologically plausible per-section baseline: Total Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp autofluorescence suppressed"
affects: [phase-04-biological-plausibility-validation, full-series-detection-run]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Human-in-the-loop phase gate: no code authored; a human runs the finished GUI script in QuPath and attests the success criteria (GUI-only per CLAUDE.md)"

key-files:
  created:
    - ".planning/phases/03-detection-script-and-single-section-end-to-end-test/03-04-SUMMARY.md"
  modified: []

key-decisions:
  - "Gate accepted from the validated run performed during the D-05 debug resolution (2026-07-16), not a separate fresh run — the same final, committed bg-sub script was exercised on M3 entry 1 and the operator visually confirmed the outcome"
  - "k=3 locked as the series seed for the D-05 robust threshold; can be swept 3–5 per section if a future section drifts"

patterns-established:
  - "Pattern 1: a failed human gate is closed by confirming the fixed artifact against the same success criteria, with the debug session's verification record as the objective evidence trail"

requirements-completed: [SCRI-03]

coverage:
  - id: D1
    description: "SC1 — 02_detect_classify.groovy runs via 'Run for project' on M3 entry 1 with no error and writes data.qpdata with classified cells"
    requirement: "SCRI-03"
    verification:
      - kind: manual_procedural
        ref: "QuPath 0.6.0 run on M3 entry 1 (2026-07-16); ~207k-cell population, no crash — recorded in .planning/debug/resolved/d05-threshold-all-negative.md"
        status: pass
    human_judgment: true
    rationale: "GUI pipeline with no automated test harness (03-VALIDATION.md); the run result is a human observation of the QuPath log + saved data.qpdata."
  - id: D2
    description: "SC2 — all four classes (TdT+/Fos+/Double+/Negative) present and non-zero, each cell carrying an ABBA atlas region label"
    requirement: "SCRI-03"
    verification:
      - kind: manual_procedural
        ref: "Debug verification: Total Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp suppressed, LA confirmed; atlas labels resolve (CA1/SSp-bfd/DG-mo)"
        status: pass
    human_judgment: true
    rationale: "Class-half was the failing criterion on 2026-07-10 (100% Negative); now confirmed non-zero and biologically concentrated by operator visual inspection."
  - id: D3
    description: "SC3 — printed Atlas_X sample values fall in 5,000–10,000 µm (CCFv3 microns, not mm/voxel-index)"
    requirement: "SCRI-03"
    verification:
      - kind: manual_procedural
        ref: "Operator-confirmed as part of accepting the gate (2026-07-16); positive cells now exist so the Atlas_X print is no longer blocked"
        status: pass
    human_judgment: true
    rationale: "SC3 was blocked in the failed run (no positive cells to sample); confirmed by the operator on acceptance."
  - id: D4
    description: "SC4 — per-region Count: columns for CA1/CA2/CA3/DG populated in the QuPath annotation pane"
    requirement: "SCRI-03"
    verification:
      - kind: manual_procedural
        ref: "Operator-confirmed on acceptance (2026-07-16); rollup mechanism was already correct, now populated with non-zero classes"
        status: pass
    human_judgment: true
    rationale: "Count-rollup mechanism verified in Plan 03-02; SC4 pass requires a human to read the populated columns in the GUI."

duration: "n/a (human-in-the-loop gate; validated during D-05 debug resolution)"
completed: 2026-07-16
status: complete
---

# Phase 3 Plan 04: End-to-End Human Verification Gate — PASSED

**All four Phase-3 success criteria confirmed on M3 entry 1 with the final background-subtracted `02_detect_classify.groovy`: clean run + saved data.qpdata (SC1), four non-zero classes with atlas labels (SC2), Atlas_X in microns (SC3), and populated CA1/CA2/CA3/DG count columns (SC4) — biology plausible (Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp suppressed).**

## Performance

- **Type:** Human-in-the-loop checkpoint (`checkpoint:human-verify`, blocking phase gate) — no code authored
- **Completed:** 2026-07-16
- **Tasks:** 1 (verification run)
- **Files modified:** 0 source files (SUMMARY only)

## Accomplishments
- **Phase-3 gate cleared.** A human ran the finished `02_detect_classify.groovy` on M3 entry 1 in QuPath 0.6.0 and confirmed all four success criteria hold together on the final bg-sub-based script.
- **SC2 (the prior failure) now passes.** The 2026-07-10 run classified 100% of cells Negative; after the D-04/D-05 fix the class-half is non-zero and biologically concentrated — Total Fos+ ~20%, Total TdT+ ~3.5%, Double+/TdT+ ~0.45, with SSp cortical autofluorescence visibly suppressed and LA confirmed (operator visual inspection).
- **SCRI-03 satisfied end-to-end** — "tested on one section" is now met, the last outstanding condition for the requirement.
- **Series seed locked:** k=3 for the D-05 robust threshold (`median + k·1.4826·MAD`), ready to carry into the full series (sweep 3–5 per section only if drift appears).

## Task Commits

This is a verification-only plan (no source changes). The artifacts under test were delivered and committed in Plans 03-01/03-02/03-03 and the D-04/D-05 debug fixes:

- D-05 all-Negative root cause + fixes — `89f4095` (fix)
- D-04 local-bg annulus JTS resilience — `d6ea728` (fix)
- Count-rollup closure param rename — `72decba` (fix)
- Plan 03-03 (bg-sub measure + threshold re-derivation) — `3c5f818`, `32278ee` (feat)

**Plan metadata:** committed with this SUMMARY (docs).

## Files Created/Modified
- `.planning/phases/03-detection-script-and-single-section-end-to-end-test/03-04-SUMMARY.md` — this record.

No source files were modified by this plan — it runs and inspects the artifacts from Plans 01–03.

## Decisions Made
- **Gate accepted from the D-05 debug-resolution validation run**, not a separate re-run. The same final, committed script (canonical `scripts/02_detect_classify.groovy` and its byte-identical M3 project copy, sha256 `d3286e61…`) was exercised on M3 entry 1 during that session; the operator confirmed all four criteria, so a duplicate run was unnecessary.
- **k=3 locked** as the series seed for the robust threshold.

## Deviations from Plan
Plan step 7 ("confirm the raw-measure re-derivation printout lands near 13000.4538 / 16766.4671") was **stale** and not applied: the D-05 approach was redesigned during debugging from the nth-histogram-peak cutoff to the self-calibrating robust threshold (`median + k·1.4826·MAD`), and its self-check now compares against a scale-free sanity band, not those raw absolute cutoffs. All other steps (SC1–SC4 + the SSp-suppression spot-check) were followed as written.

## Issues Encountered
- **The gate initially FAILED (2026-07-10): 100% Negative.** Root-caused via `/gsd-debug` to a measurement-key mismatch in the D-04 local-background function (annulus mean looked up under `"Cell: <channel> mean"` but a plain detection object names it `"<channel>: Mean"`) → NaN bg-sub for every cell → empty D-05 population → NaN threshold → placeholder raw-scale JSON kept → all-Negative. Fixed by resolving the annulus key against the object's actual key set (`keySet().find { startsWith(channel) && endsWith("mean") }`) and committing bg-sub writes via `getMeasurements().put()`. The D-05 sparse-marker redesign was kept (correct once the population is non-empty). Full trail: [03-GATE-FAILURE-D05.md](./03-GATE-FAILURE-D05.md) and [d05-threshold-all-negative.md](../../debug/resolved/d05-threshold-all-negative.md). Resolved 2026-07-16.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- **SCRI-03 complete; Phase 3 gate cleared.** The classified M3 section is trustworthy and the classifier is series-ready with k=3 locked.
- **Ready for Phase 4** (Biological Plausibility Validation and Imaging Optimization Notes): the per-section baseline (Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45) is the input to Phase-4's bioplausibility gate — note Phase-4 SC1 expects Double+ at 10–40% of TdT+; 0.45 (~45%) sits just above that band and should be examined during Phase-4 validation (single-section estimate, not yet aggregated).
- No blockers.

## Self-Check: PASSED

The human operator confirmed all four success criteria on M3 entry 1; the fix under test is present and committed on disk (HEAD `89f4095`), both script copies byte-identical.

---
*Phase: 03-detection-script-and-single-section-end-to-end-test*
*Completed: 2026-07-16*
