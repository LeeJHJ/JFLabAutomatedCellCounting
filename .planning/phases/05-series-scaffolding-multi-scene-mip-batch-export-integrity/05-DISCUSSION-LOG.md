# Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-18
**Phase:** 5-series-scaffolding-multi-scene-mip-batch-export-integrity
**Areas discussed:** Scene-identity artifact, AP-order handling, Output filename convention, EXP-02 fix strategy

---

## Scene-identity verification artifact (CONV-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Thumbnail PNG + text | Per-scene downsampled PNG for visual check AND printed bbox/tile-count/dims text record | ✓ |
| Thumbnail PNG only | Just the per-scene PNG, no text morphology record | |
| Printed text only | bbox/M/dims to stdout, no image | |

**User's choice:** Thumbnail PNG + text
**Notes:** Belt-and-suspenders against a silent scene→section shuffle, consistent with v1.0's overlay-PNG habit. Artifact must print both raw 0-based scene key and 1-based `s{N}` label (paired with the filename decision below).

---

## AP-order handling

| Option | Description | Selected |
|--------|-------------|----------|
| Preserve index, defer AP | Keep raw scene index only; no AP claim now; DeepSlice sorts AP in Phase 6 | ✓ |
| Assert AP = scene index | Treat scene 0 as most-anterior, annotate/assert AP order now | |

**User's choice:** Preserve index, defer AP
**Notes:** Scene acquisition order is not assumed to equal anatomical AP order. CONV-02 verifies scene→physical-section identity only; AP ordering is Phase 6's job.

---

## Output filename convention

| Option | Description | Selected |
|--------|-------------|----------|
| wBA1-3_scene00 (0-based, padded) | Zero-based zero-padded, matches Python loop exactly (Claude-recommended) | |
| wBA1-3_s1 (1-based) | One-based human-friendly section number s1..s5 | ✓ |
| v1.0 style + index | Extend {Animal}_20x_MIP with a scene-index suffix | |

**User's choice:** wBA1-3_s1 (1-based) → `wBA1-3_s1_MIP.ome.tiff` … `wBA1-3_s5_MIP.ome.tiff`
**Notes:** User chose 1-based over Claude's 0-based recommendation. This introduces a +1 offset vs the 0-based Python scene loop; flagged as an off-by-one guard (D-05) — the identity artifact must print both the raw 0-based scene key and the 1-based label so `s1`=scene-0 … `s5`=scene-4 is provable and no shuffle can hide in the translation.

---

## EXP-02 fix strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Stem from entry name, flat | Output filename derived from QuPath image/entry name (sanitized), flat in results/ | ✓ |
| Scene-index suffix, flat | Append numeric entry index as suffix in results/ | |
| Subfolder per entry | results/<entry_name>/ with current fixed inner filenames | |

**User's choice:** Stem from entry name, flat
**Notes:** Entry name is already each section's identity, so outputs are self-describing. Both TSVs get the per-entry stem; column contract with `val01_metrics.py` preserved. Blocking prerequisite for AGG-01 (Phase 10).

---

## Claude's Discretion

- Thumbnail channel/size and exact text-record fields beyond {bbox, M tile count, dims}.
- Entry-name → filesystem-safe stem sanitization rule.
- Per-scene MIP memory strategy on the 16 GB input.

## Deferred Ideas

None — discussion stayed within phase scope. AP ordering was explicitly deferred to Phase 6 (a sequencing decision, not new scope).
