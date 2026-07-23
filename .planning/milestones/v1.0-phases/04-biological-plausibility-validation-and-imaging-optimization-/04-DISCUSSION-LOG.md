# Phase 4: Biological Plausibility Validation and Imaging Optimization Notes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 4-biological-plausibility-validation-and-imaging-optimization-notes
**Areas discussed:** Gate vs. findings record, Metric computation path, Imaging notes: evidence & format
**Area offered but not selected:** Negative-control region (handled at Claude's discretion)

---

## Gate vs. findings record

| Option | Description | Selected |
|--------|-------------|----------|
| Findings record + interpretation | Document each metric with target + in/out flag + interpretation; phase completes even if out of range; out-of-range → flagged notes for series | ✓ |
| Hard pass/fail gate | Any metric out of range = fail; iterate thresholds until all in range | |
| Hybrid: gate w/ documented override | Default pass/fail, but out-of-range acceptable with a written a-priori justification | |

**User's choice:** Findings record + interpretation
**Notes:** Sensible for n=1. Double+/TdT+ ~0.45 is already above the 10–40% target; the phase records and interprets it (n=1, biology, threshold sensitivity) rather than blocking. Re-tuning detection is explicitly out of scope. (CONTEXT D-01, D-02)

---

## Metric computation path

| Option | Description | Selected |
|--------|-------------|----------|
| Groovy export → Python analysis | Groovy exports per-cell measurements + per-region areas from data.qpdata; Python (braian env) computes ratios/density/area-histogram and writes the record | ✓ |
| Pure Groovy, compute in QuPath | QuPath itself computes and prints all four metrics; no export, no Python | |
| Hand-record from existing outputs | Read numbers off summary.json / regions.tsv / annotation pane manually | |

**User's choice:** Groovy export → Python analysis
**Notes:** Reproducible and re-runnable; histogram/density math cleaner in Python. Fits the GUI-export / scriptable-analysis split. D-01 precedent favors a separate export script (keep the fast re-classify loop clean) — flagged as planner discretion. Density needs per-region mm² area (D-04). (CONTEXT D-03, D-04)

---

## Imaging notes: evidence & format

Two sub-questions were asked.

### Doc structure

| Option | Description | Selected |
|--------|-------------|----------|
| Two separate docs | 04-VALIDATION.md (VAL-01) + 04-IMAGING-NOTES.md (OPT-01/02/03) | ✓ |
| One combined doc | Single 04-VALIDATION-AND-IMAGING.md with 4 sections | |
| Docs + machine-readable sidecar | Two docs + a JSON/CSV of raw metrics for series diffing | |

**User's choice:** Two separate docs
**Notes:** Different audiences/lifetimes — validation is a per-run scientific record, imaging notes are forward-looking acquisition recommendations. (CONTEXT D-05)

### Evidence basis (OPT-01 / OPT-03)

| Option | Description | Selected |
|--------|-------------|----------|
| Empirical from existing files | Ground both in on-disk data (count comparison across MIP variants; per-subfield quality on existing 20x MIP) | |
| Reasoned judgment + literature | Optical principles + TRAP2 paper + visual inspection; no new numbers | |
| Empirical where possible, reasoned elsewhere | Measure what the files support; reason for gaps; label each claim [measured] vs [inferred] | ✓ |

**User's choice:** Empirical where possible, reasoned elsewhere
**Notes:** Z-count + file sizes measured from CZI/MIP on disk; OPT-01 plane-need grounded in count-plateau comparison across existing MIP variants; OPT-03 falls back to reasoned optical argument for resolutions never captured. Every claim tagged [measured]/[inferred]. (CONTEXT D-06)

---

## Claude's Discretion

- **Negative-control region (VAL-01 Fos+ 1–3%):** hippocampus-only field with no clean control → document absence per VAL-01's explicit allowance; report SSp Fos+ rate as a corroboration point (should read low after the Phase-3 autofluorescence fix), and any within-section low-signal reference if available.
- **Export script boundary:** new script vs. block in 02_detect_classify.groovy → planner's call; D-01 precedent favors a separate script.
- **Nucleus-area-peak estimation method** (histogram/KDE/mode) → researcher/planner's call.

## Deferred Ideas

- Re-tuning thresholds to force Double+/TdT+ into range — series-phase decision with n>1.
- Full per-cell Atlas_X/Y/Z export column + per-region TSV (EXP-01/02/03, v2).
- Whole-brain / full-series autofluorescence + Fos-drift validation (SERIES-01/02).
- PNN (WFA) quantification — future phase.
- BraiAnalyse group stats / brainrender 3D — need the full registered series.
