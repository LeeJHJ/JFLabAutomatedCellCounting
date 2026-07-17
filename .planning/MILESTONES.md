# Milestones

## v1.0 Single-Section Validation Run (Shipped: 2026-07-17)

**Phases completed:** 4 phases, 12 plans, 15 tasks

**Key accomplishments:**

- Single-DAPI-anchored `BraiAn.yml` (histogram-relative threshold), a rebuilt Cytoplasm-compartment TdT classifier fixing a real mis-count bug, and a D-05 measurement-QC harness — the full scriptable half of the detection-parameter lock, ready for Plan 02-02's human-in-the-loop tuning.
- Human-in-the-loop detection tuning on M3 entry 1 (DG + CA1) against the D-05 QC gates — locked sigma/area/histogram-threshold and re-derived classifier thresholds in `02-LOCK-RECORD.md`, the parameter set carried through Phases 3–4.
- Authored `02_detect_classify.groovy` (canonical + project hard-copy): extends `classify_markers.groovy` into the numbered pipeline with a D-02 zero-detection guard and an ephemeral centroid-in-ROI atlas region-label lookup per classified cell.
- Compartment-agnostic local-background-subtracted Fos/TdT measurement (peri-cellular annulus via RoiTools + ObjectMeasurements) with positive thresholds re-derived on that measure via ChannelHistogram peak-finding, replacing the old absolute cutoffs in the compound classification loop.
- All four Phase-3 success criteria confirmed on M3 entry 1 with the final background-subtracted `02_detect_classify.groovy`: clean run + saved data.qpdata (SC1), four non-zero classes with atlas labels (SC2), Atlas_X in microns (SC3), and populated CA1/CA2/CA3/DG count columns (SC4) — biology plausible (Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp suppressed).
- Two-stage VAL-01 pipeline authored: Groovy per-cell/per-region TSV export reading 02_detect_classify.groovy's exact bg-sub measurement keys, plus a Python (braian env) metrics script computing all four VAL-01 bioplausibility numbers, proven against a synthetic fixture.
- Measured CZI Z-plane/file-size/plateau facts feeding a forward-looking `04-IMAGING-NOTES.md` — 6 planes at 2.0 µm step plateau within 1.5% DAPI count against a 4µm sub-range, 9.29× raw:MIP size ratio, and a per-subfield Airyscan-need table anchored on Phase 2's CA1/DG-sg separability finding.
- Computed all four VAL-01 bioplausibility metrics on the real 213,106-cell M3 export, fixed a real density-join bug found in the process, and wrote 04-VALIDATION-RECORD.md — a D-01 findings record showing the whole-section Double+/TdT+ ratio (45.5%) and SSp Fos+ rate (47.1%) both read out of range, but the best-resolved hippocampal subfields (CA1, DG-mo) individually land inside their target bands.

**Delivered:** A locked, end-to-end TRAP2 section pipeline (ABBA registration → BraiAnDetect nucleus-anchored classification → per-region VAL-01 bioplausibility record + imaging-optimization notes), validated on M3 hippocampus entry 1 and ready to scale to the full series.

**Stats:** 4 phases · 12 plans · 15 tasks · 71 commits · 2026-07-07 → 2026-07-17 (10 days).

**Known verification overrides:** 1 — Phase 2 (Detection Parameter Lock) closed without a formal `02-VERIFICATION.md`; its locked parameters were validated downstream by Phase 3 (end-to-end) and Phase 4 (bioplausibility). See STATE.md → Deferred Items.

**Notable:** A mid-milestone code review (Phase 4, CR-01) caught a region-labeling bug that had leaked ~95,000 cells into a `grey` rollup; it was fixed and the VAL-01 record regenerated on corrected data before close.

---
