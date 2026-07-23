# Phase 3: Detection Script and Single-Section End-to-End Test - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 3-detection-script-and-single-section-end-to-end-test
**Areas discussed:** Script composition, SSp autofluorescence fix

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Script composition | Single self-contained script vs. orchestrator vs. detection-separate | ✓ |
| SSp autofluorescence fix | Fix background robustness now vs. defer | ✓ |
| Atlas coord check | Sanity-print vs. full per-cell Atlas_X/Y/Z column | (Claude discretion) |
| Per-region count table | Rollup to annotations / console / TSV reuse | (Claude discretion) |

---

## Script composition

### Q1 — Relationship to the two existing Phase-2 scripts

| Option | Description | Selected |
|--------|-------------|----------|
| Single self-contained script | Inline detection + classification + labeling + reporting into one pass | |
| Thin orchestrator | 02_detect_classify calls the two existing scripts in sequence | |
| Keep detection separate | run_braian_detection standalone; 02 = classify + labels + count table only | ✓ |

**User's choice:** Keep detection separate.
**Notes:** Heavy CPU detection pass stays out of the classify script so the fast threshold-iteration loop can re-run without re-detecting.

### Q2 — Behavior on re-run / undetected entries

| Option | Description | Selected |
|--------|-------------|----------|
| Guard + re-classify in place | Abort if zero detections; else re-classify idempotently (setPathClass overwrites) | ✓ |
| Guard + require clean slate | Refuse to run if cells already classified; force re-detect | |
| Auto-detect if missing | Call detection inline when none found | |

**User's choice:** Guard + re-classify in place.
**Notes:** Matches classify_markers.groovy's existing "No detections — Aborting" guard; safe for the tuning loop; undetected entries abort cleanly under "Run for project".

---

## SSp autofluorescence fix

### Q1 — Fix now or defer

| Option | Description | Selected |
|--------|-------------|----------|
| Defer, document caveat | Run on locked absolute thresholds; hippocampal SC targets unaffected; record for series phase | |
| Fix now | Add background-robust Fos/TdT measure this phase so script is series-ready | ✓ |
| Partial: flag regions | Exclude/flag high-autofluorescence regions like DG-sg/VS instead of changing the measure | |

**User's choice:** Fix now.

### Q2 — Which robust measure

| Option | Description | Selected |
|--------|-------------|----------|
| Compartment-contrast ratio | nucleus:cytoplasm ratio per marker (uniform autofluorescence ≈1) | |
| Local-background subtraction | Subtract local peri-cellular background per compartment | ✓ (resolved) |
| You decide | Defer to research/planning | (user chose "Other") |

**User's choice:** "You decide, but eventually I want to be able to scale this sort of analysis for PNN measurements too (which might potentially affect getting a compartment-contrast ratio)."
**Notes:** Reflected back: PNNs are extracellular pericellular ECM, so a two-compartment intracellular ratio cannot host a PNN signal and won't generalize; local-background subtraction is compartment-agnostic and extends to a future pericellular PNN annulus. User confirmed ("exactly!"): build the robust measure as local-background subtraction, keep PNN as a deferred capability that steers the design, and accept that Fos/TdT thresholds get re-derived on the new measure.

---

## Claude's Discretion

- **Atlas coordinate check (SC3):** lightweight sanity-print of sample cell CCFv3 Atlas_X coords (confirm µm units); no full per-cell Atlas_X/Y/Z column (that's v2 EXP-01).
- **Per-region count table (SC4):** roll per-class counts onto region annotations (annotation-pane measurements) for CA1/CA2/CA3/DG; console table + reuse of BraiAn's _regions.tsv acceptable.
- **Atlas-label mechanism:** resolveHierarchy / parent-annotation assignment — technical plumbing left to researcher/planner.
- **Region exclusions:** DG-sg + VS remain as locked in Phase 2.

## Deferred Ideas

- **PNN (perineuronal net / WFA) quantification** — future phase; new channel + pericellular-annulus compartment. Steers Phase 3's measure choice (local-background subtraction) but not implemented now.
- **Full per-cell Atlas_X/Y/Z micron export + per-region TSV** — v2 EXP-01/02/03.
- **Whole-brain / full-series autofluorescence validation** — SERIES-01/02.
- **Biological-plausibility gates** — Phase 4 (VAL-01).
