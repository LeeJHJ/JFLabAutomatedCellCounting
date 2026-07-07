# Phase 2: Detection Parameter Lock - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 2-detection-parameter-lock
**Areas discussed:** Threshold strategy (abs vs relative), Tuning reference + lock/accept bar
**Areas surfaced but not selected (→ Claude's Discretion):** Cytoplasmic expansion + DG bleeding, Reuse vs rebuild classifiers

---

## Threshold strategy

### Detection threshold (WatershedCellDetection on DAPI)

| Option | Description | Selected |
|--------|-------------|----------|
| Histogram-relative | Per-section from DAPI histogram; robust to brightness drift across series | ✓ |
| Absolute fixed value | Single hardcoded intensity (~10k like prior M3); simple but drifts | |

### Classifier positive cutoffs (TdT+/Fos+)

| Option | Description | Selected |
|--------|-------------|----------|
| Same relative philosophy | Derive cutoffs from each section's distribution | ✓ |
| Fixed absolute cutoffs | Lock ~10200/~9341; simple but dim sections under-count | |
| Decide during tuning | Pick after seeing measurement histograms | |

### Lock granularity

| Option | Description | Selected |
|--------|-------------|----------|
| One global file + drift monitor | Single BraiAn.yml all sections; SERIES-02 flags outliers | ✓ |
| Allow per-section nudging | Adaptive but inconsistent criteria | |

**User's choice:** Histogram-relative detection + relative classifier cutoffs + one global locked BraiAn.yml with SERIES-02 drift monitoring.
**Notes:** Coherent series-robust stack — no per-section re-tuning; outliers flagged, not re-fit.

---

## Tuning reference + lock/accept bar

### Tuning target

| Option | Description | Selected |
|--------|-------------|----------|
| M3 062926 entry 1, DG + CA1 | Dense DG stress test + CA1 clean check | ✓ |
| M3 062926 entry 1, DG only | Hardest case only; may over-tighten | |
| Whole hippocampus field | Broader but harder per-nucleus judgment | |

### Hard acceptance gates (multi-select)

| Option | Description | Selected |
|--------|-------------|----------|
| Nucleus area peak 50–150µm² | Validates sigma + area params | ✓ |
| Double+ = 10–40% of TdT+ | Colocalization sanity | (not selected — advisory) |
| DAPI density 500–2000/mm² | Catches gross over/under-detection | ✓ |
| Fos+ ≈1–3% in negative control | Needs a control region | (not selected) |

### Negative-control availability

| Option | Description | Selected |
|--------|-------------|----------|
| Not available — use substitute | Visual sparse check, defer strict gate | |
| Yes — quiet region in frame | Use it for 1–3% gate now | |
| Skip this gate entirely | Rely on other bioplausibility gates | ✓ |

**User's choice:** Tune on M3 062926 entry 1 (DG + CA1). Hard gates = nucleus area peak 50–150µm² AND DAPI density 500–2000/mm². Double+ ratio is advisory only. Fos+ negative-control gate skipped for Phase 2.
**Notes:** Deliberately excluded the Double+ ratio from lock criteria — gating params on the expected biological result would risk circular tuning toward the hypothesis. Single hippocampal section lacks a trustworthy low-Fos control, so the 1–3% gate defers to the full series.

---

## Claude's Discretion

- **Cytoplasmic expansion radius / DG bleeding:** default 5 µm seed (TRAP2 paper), rings clipped at neighboring cell boundaries, verify on dense DG. Planner to make the DG bleed-check explicit.
- **Reuse vs rebuild classifiers:** reuse `Fos_Classifier_20x.json` (correct nuclear compartment) with a relative-threshold re-derivation; rebuild the TdT classifier to read `Cytoplasm: AF568-T2 mean` (existing one wrongly reads Nucleus); discard stale "Automated Cell Counting Test" classifiers.
- **Sigma + min/max nucleus area:** seed from TRAP2 paper, gated by the nucleus-area-peak acceptance criterion.

## Deferred Ideas

- Fos+ ≈1–3% negative-control validation → full-series phase (proper control region).
- Double+ 10–40% of TdT+ → reported as an outcome at series-stats time, not a Phase-2 gate.
- crop_to_tissue.py / masked-elastix registration pilot → registration-domain, series-scaling decision (not this phase).
