# Phase 6: Registration Speedup - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-19
**Phase:** 6-Registration Speedup
**Areas discussed:** DeepSlice run mode, Angle propagation, Elastix keep/reject (BigWarp spec delegated to Claude)

---

## Gray-area selection

| Option | Description | Selected |
|--------|-------------|----------|
| DeepSlice run mode | How the one-pass batch is run + AP ordering | ✓ |
| Angle propagation | Shared-angle source of truth | ✓ |
| BigWarp spec | Landmark count/features + effort target | (left to Claude) |
| Elastix keep/reject | A-priori rule + trial section | ✓ |

---

## DeepSlice run mode

### Q1 — How to run the one-pass DeepSlice registration
| Option | Description | Selected |
|--------|-------------|----------|
| ABBA built-in (online) | Run DeepSlice inside ABBA GUI on all 5, web service, least scripting | |
| Standalone online web tool | Upload 5, download alignment, import to ABBA | |
| Local deepslice env script | run_deepslice.py, offline predict()+propagate_angles(), reproducible | ✓ |

### Q2 — Section ordering source
| Option | Description | Selected |
|--------|-------------|----------|
| Operator provides known order | Section numbers + spacing supplied to DeepSlice | ✓ |
| Let DeepSlice infer, then verify | No ordering assumption; operator visually verifies | |

### Q3 — Handoff of results into ABBA
| Option | Description | Selected |
|--------|-------------|----------|
| Import DeepSlice results file | Alignment file → ABBA "Import DeepSlice results" (name-match gotcha) | ✓ |
| Numbers as manual reference | Print AP/tilt; operator sets by hand | |

**User's choice:** Local env script; operator-known order; import results file.
**Notes:** Deliberate override of CLAUDE.md "prefer DeepSlice online" — operator wants reproducible/offline/scriptable batch. Name-matching between DeepSlice proxy images and ABBA slice names flagged as the gotcha.

---

## Angle propagation

### Q1 — Source of truth for shared cutting angle
| Option | Description | Selected |
|--------|-------------|----------|
| DeepSlice propagate_angles() | One consistent angle derived jointly from all 5 | ✓ (as candidate) |
| Manual angle, copied across | Best manual tilt on one section, reused on the other 4 | ✓ (as validation) |
| Per-section independent angles | Keep each section's own estimate, no propagation | |

### Q2 — Outlier-section rule
| Option | Description | Selected |
|--------|-------------|----------|
| Allow documented per-section override | Shared angle default, override + document for outliers | ✓ |
| Rigid shared angle, fix via BigWarp | One angle for all 5; residuals only via BigWarp | |

**User's choice:** Run propagate_angles() AS A CANDIDATE, validated against a manually-copied angle — adopt whichever fits. Per-section override allowed and documented.
**Notes:** Verbatim rationale — "I've run into some trouble previously with fully trusting DeepSlice's DV/ML estimates." DeepSlice angle never adopted unseen.

---

## Elastix keep/reject (REG-05)

### Q1 — Trial section
| Option | Description | Selected |
|--------|-------------|----------|
| Worst-fitting section | Where DeepSlice+angle+BigWarp fits worst at LA/BA | ✓ |
| Representative mid-quality section | Typical/average fit | |
| Tightest-framed section | DAPI already fills frame (leans reject) | |

### Q2 — A-priori accept rule
| Option | Description | Selected |
|--------|-------------|----------|
| Must beat BigWarp on fit AND time | Keep only if better fit and no more time | |
| At-least-as-good fit at less time | Keep if no worse and faster | |
| Better fit, time irrelevant | Keep if visibly better fit regardless of time | ✓ |

**User's choice:** Trial on the worst-fitting section; keep elastix iff visibly better LA/BA fit — time irrelevant (quality-first). Decision recorded either way.
**Notes:** Quality-over-speed because LA/BA boundary accuracy drives the amygdala engram readout. crop_to_tissue.py supplies the mask; pilot caveat (tight sections barely benefit) respected by choosing the worst-fitting section + quality-only acceptance.

---

## Claude's Discretion

- **BigWarp spec (REG-04)** — user delegated. Planned: ~4 amygdala-relevant landmarks (LA/BA boundary, external capsule, optic tract, ventral edge), effort target ≈ ≤5 min/section (below v1.0's 5–15 min), effort recorded as operator wall-clock; applied across all 5.
- DeepSlice input-image prep (channel/downsample) and ensemble flag.
- Elastix/BigWarp moving-channel index = 2 (DAPI on these MIPs), not 0.

## Deferred Ideas

- None from discussion (stayed within scope).
- Reviewed-not-folded todo: "Phase 7 imaging QC — autofocus banding and missing cortex tissue" → Phase 7 scope, not registration.
