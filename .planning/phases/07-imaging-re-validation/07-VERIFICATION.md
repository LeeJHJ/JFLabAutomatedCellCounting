---
phase: 07-imaging-re-validation
type: verification
status: complete
mode: backfill
executed: ad-hoc (2026-07-20 → 2026-07-23 session)
backfilled: 2026-07-23
requirements: [IMG-01, IMG-02]
source_of_truth:
  - memory/wba1_amygdala_engram_result.md
  - .planning/todos/pending/2026-07-18-phase-7-imaging-qc-autofocus-banding-and-missing-cortex.md
---

# Phase 7 — Imaging Re-Validation (4-Plane / Lower-Laser Params) — VERIFICATION (backfilled)

> **Provenance note.** Phase 7 was **executed ad-hoc** during the wBA1-3 full-series session
> (no `07-*-PLAN.md` was authored). This VERIFICATION is a **retrospective backfill** grounded
> in the recorded session outcome (`memory/wba1_amygdala_engram_result.md`) and the operator
> QC findings captured in the Phase-7 pending todo. It documents what was actually done and
> what remains open — it is not a claim that the phase ran through the normal plan→execute
> →verify loop.

## Goal (from ROADMAP)

Confirm detection/classification are valid on the new 4-plane / lower-laser imaging params;
re-run the D-05 QC gates; re-lock the k robust-threshold seed only on drift; confirm the
4-plane MIP is not under-projected.

## Success Criteria — actual outcome

**SC-1 — D-05 gates re-run + bg-sub distribution shape compared to v1.0 reference.**
✅ Met (adapted). Detection was re-run on the new thin-z-stack MIPs. The key empirical finding
is a **deliberate detection-parameter change driven by the new imaging**: `sigmaMicrons` was
lowered from M3's **2.5 → 2.0**, because the thinner z-stack deblends the over-projected DAPI
blobs that forced the coarser sigma in v1.0. This is the imaging-drift response SC-1 exists to
catch — the thin-z acquisition changed the DAPI PSF, and detection was re-tuned accordingly
rather than blindly reused.

**SC-2 — k robust-threshold seed re-confirmed or re-swept + drift decision documented.**
✅ Met. k was **re-swept (k = 2.0 / 2.5 / 3.0)**, not blindly re-locked. Recorded outcome:
absolute Fos+/TdT+ fractions scale with k (LA Fos+: 10.5% @ k2.0, 8.7% @ k2.5, 7.8% @ k3.0),
but the engram metric **P(Fos+|TdT+) is threshold-robust (34–36% across k=2–3)**. Decision:
**k=3 stays the conservative locked seed for absolutes; k≈2.0 aligns absolute Fos+/TdT+ with
the operator's validated ~10–15% reference band.** The engram conclusion does not depend on k.

**SC-3 — under-projection / plateau + visual DAPI-blob check on the 4-plane MIP.**
⚠️ Partially met. The thin z-stack was confirmed to *improve* DAPI (deblended blobs → finer
sigma viable), which is the positive-direction under-projection evidence. However, two
acquisition-quality QC items surfaced at operator sign-off remain **OPEN** and were carried,
not closed (see below).

## Open / carried items (do NOT treat as closed)

From `todos/pending/2026-07-18-phase-7-imaging-qc-...md` (operator sign-off, Phase 5 05-03):

1. **Autofocus / tile-row focus banding** on some slices (visible in `wBA1-3_s1_MIP.ome.tiff`).
   `histogramThreshold` + robust median+k·MAD absorb brightness *drift* but NOT focus *blur*.
   Detection quality on defocused rows is not yet explicitly gated.
2. **Small missing cortex pieces** on some sections — deflates region-level count/area
   denominators (relevant to Phase 9 area readout). Any exclusion must be a-priori/principled.

These are acquisition-quality issues on a **suboptimally cut/mounted n=1 methods-validation
brain**; the undergrad operator is re-cutting for the real series. They are acceptable-to-carry
for a methods-validation run but MUST be re-gated when the real series arrives.

## Verdict

**Phase goal substantially achieved for a methods-validation run.** Detection was re-validated
and re-tuned to the new imaging (sigma 2.0), k was swept and the drift decision documented, and
the engram readout was shown threshold-robust. Two acquisition-QC items (focus banding, missing
cortex) are explicitly **carried open** into the real-series re-run, not silently passed.
