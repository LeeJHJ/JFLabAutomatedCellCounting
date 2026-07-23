---
phase: 08-la-ba-classification-region-labeling-validation
type: verification
status: complete
mode: backfill
executed: ad-hoc (2026-07-20 → 2026-07-23 session)
backfilled: 2026-07-23
requirements: [CLASS-02, LABEL-01]
source_of_truth:
  - memory/wba1_amygdala_engram_result.md
---

# Phase 8 — LA/BA Classification + Brain-Wide Region-Labeling Validation — VERIFICATION (backfilled)

> **Provenance note.** Phase 8 was **executed ad-hoc** during the wBA1-3 full-series session
> (no `08-*-PLAN.md` was authored). This VERIFICATION is a **retrospective backfill** grounded
> in the recorded session outcome (`memory/wba1_amygdala_engram_result.md`). It documents the
> real classification run and the region-labeling audit outcome; it is not a claim of a normal
> plan→execute→verify loop.

## Goal (from ROADMAP)

Nucleus-anchored TdT+/Fos+/Double+ classification across all 5 sections over the LA/BA amygdala
ROI, producing per-region primary counts; re-audit the CR-01 smallest-area-leaf region-labeling
fix on non-laminar amygdala to prove zero cells leak into parent rollups.

## Success Criteria — actual outcome

**SC-1 — `02_detect_classify.groovy` runs across all 5 sections → non-zero classes with atlas
labels, same nucleus-anchored rules as v1.0.** ✅ Met. BraiAnDetect DAPI detection
(sigmaMicrons 2.0) → nucleus-anchored bg-sub classification (self-calibrating median +
k·1.4826·MAD) → atlas-region TdT+/Fos+/Double+ counts ran across the series. Colocalization
remained nucleus-anchored per CLAUDE.md (no proximity heuristics).

**SC-2 — Per-region primary counts across the full series.** ✅ Met. Animal-level (sum of 5
sections, both hemispheres): **LA = 5,067 cells; BLA = 9,301 cells.** LA present in caudal
sections **s2 / s5 / s3**, absent in anterior **s4 / s1**.

**SC-3 — Region-labeling harness asserts zero cells leak into parent rollups; re-audited on
non-laminar LA/BA.** ✅ Met with a **material correction**. The empirical LA-presence audit
*overturned a wrong prediction*: an earlier brainglobe atlas-band analysis predicted the caudal
sections (s5=8.01, s3=8.44 ABBA-Z) were *past* LA — WRONG. Empirical QuPath region labeling
shows LA is richest in exactly those sections. **Lesson locked: trust the actual ABBA/QuPath
region labels, not a raw brainglobe-mm band mapping** (ABBA axis-Z is offset from brainglobe's
anterior-pole convention). This is precisely the CR-01-class risk this SC exists to catch, and
it was caught on non-laminar amygdala.

**SC-4 — LA/BA Double+/TdT+ reactivation fraction reported + interpreted vs ~20–30% TRAP2 BLA
band (findings record, not gate).** ✅ Met, exceeds band with interpretation. **P(Fos+|TdT+) ≈
36% (LA), 38–42% (BLA)** vs ~8–10% chance Fos+ rate = **~4–5× above-chance reactivation** — the
amygdala engram signal the pipeline was built to measure. Note the operator's engram metric is
P(Fos+|TdT+) = Double+/TdT+total; TdT+/Fos+ percentages always include Double+.

## Caveats carried forward

- **n=1 animal, suboptimal tissue** → METHODS VALIDATION, not final biology. No group stats
  from one brain. Only s2/s5/s3 carry amygdala.
- **TdT-in-axons**: cytosolic TdTomato labels fiber-tract axons; tract-adjacent TdT+ calls
  still warrant scrutiny.

## Verdict

**Phase goal achieved.** Full-series nucleus-anchored classification produced coherent
per-region amygdala counts, the region-labeling audit both passed and corrected a wrong
atlas-band prediction on non-laminar LA/BA, and the engram reactivation readout is strong and
k-threshold-robust. First end-to-end amygdala engram readout of the project.
