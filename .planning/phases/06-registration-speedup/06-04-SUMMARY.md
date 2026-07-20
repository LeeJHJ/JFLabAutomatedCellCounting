# 06-04 SUMMARY — REG-04 BigWarp refinement

**Status:** Complete (operator GUI, 2026-07-20)

## What was done
Nonlinear refinement applied across all 5 sections. The planned "reduced ~4-landmark, ≤5 min/section"
approach was **superseded by the operator's empirically-best pipeline**: elastix Affine (Nissl Ch0) →
elastix Spline (15 pts) → **BigWarp** via "Edit last registration" (nudge the 15 pts + add more).

## Effort (honest, REG-04 evidence)
- **~40 min total for all 5 ≈ 8 min/section** — inside v1.0's 5–15 min/section baseline. So effort is
  *comparable per-section*, not "≤5 min", but with **materially better accuracy** and a repeatable
  strategy. The real effort win vs v1.0 is REG-03's one-pass batch DeepSlice.
- `scripts/bigwarp_effort_log.csv` — 5 rows filled (series-level timing, ~15 landmarks/section).

## Deviation
- Reduced-landmark target not met; richer elastix+spline+BigWarp pipeline adopted for accuracy
  (quality-first, consistent with the amygdala-engram readout's needs).

## Carry-forward
- Worst-mounted sections (all suboptimal per operator) — LA-presence of s3/s5 → Phase 8 LABEL-01.
