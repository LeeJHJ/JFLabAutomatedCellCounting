# Project Retrospective — M3 Hippocampus Section Pipeline

A living record of what worked, what didn't, and lessons carried forward across milestones.

---

## Milestone: v1.0 — Single-Section Validation Run

**Shipped:** 2026-07-17
**Phases:** 4 | **Plans:** 12 | **Tasks:** 15 | **Timeline:** 2026-07-07 → 2026-07-17 (10 days)

### What Was Built
End-to-end TRAP2 section pipeline validated on M3 hippocampus entry 1: ABBA atlas registration + idempotent ROI loading (Phase 1), locked BraiAnDetect detection parameters with compartment-correct Fos/TdT classifiers (Phase 2), `02_detect_classify.groovy` producing nucleus-anchored TdT+/Fos+/Double+/Negative cells with atlas labels (Phase 3), and the VAL-01 bioplausibility findings record + full-series imaging-optimization notes (Phase 4). 213,106 cells classified on the real section.

### What Worked
- **Human-in-the-loop checkpoint gates caught real bugs before they reached results.** The Phase-4 export gate caught an all-null `nucleus_area_um2` column (wrong measurement key); code review caught CR-01 (region-labeling leaking ~95k cells into a `grey` rollup). Both were fixed before the findings record was finalized.
- **Scriptable/GUI split** (Claude authors scripts + docs; operator drives QuPath/Fiji) matched the CPU-only, GUI-tool-heavy reality of the pipeline.
- **Findings-record framing (D-01)** — treating VAL-01 as an interpreted record rather than a pass/fail gate — let the phase complete honestly with out-of-range-but-explained metrics (n=1, Phase-2 calibration).
- **Worktree auto-degrade to sequential-on-main** (#683, no origin) executed cleanly without manual intervention.

### What Was Inefficient
- **Three QuPath re-runs in Phase 4** (nucleus-area fix → CR-01 fix → is_leaf-filter fix), each requiring an operator round-trip. The region-labeling fragility could have been caught during Phase 3's region-label design rather than at Phase-4 validation.
- **Phase 2 shipped without a `VERIFICATION.md`** — carried as a documented override at milestone close.

### Patterns Established
- **Dual-location Groovy deploy** (canonical `scripts/` + byte-identical QuPath-project copy).
- **Smallest-area containing region** for per-cell atlas labeling; **geometric `is_leaf`** — not child-annotation topology.
- **`[measured]` / `[inferred]` / `[ASSUMED]` claim tagging** (D-06) in scientific records.
- **Compute geometry from ROIs, not stored measurements** (nucleus area from `roi.getArea()`).

### Key Lessons
- ABBA/QuPath atlas annotations are **not reliably nested** — never infer "leaf" from child-emptiness or assign region by first-match containment.
- At any export gate, **verify column population** (non-null fraction), not just file existence — the all-null-column failure mode is silent.
- **Aggregate metrics can mask/mimic per-region truth**: the whole-section Double+/TdT+ ratio read out-of-range while per-subfield hippocampal values were in-band — always break down before interpreting.

### Cost Observations
- Model mix: orchestration on Opus, plan execution + verification + code review on Sonnet subagents.
- Notable: fresh-context subagents per plan kept the orchestrator lean across a long, multi-checkpoint phase.

---

## Cross-Milestone Trends

| Milestone | Phases | Plans | Days | Verification | Notable |
|-----------|--------|-------|------|--------------|---------|
| v1.0 | 4 | 12 | 10 | 3/4 phases have VERIFICATION.md (Phase 2 override) | CR-01 region-labeling bug caught in code review |
