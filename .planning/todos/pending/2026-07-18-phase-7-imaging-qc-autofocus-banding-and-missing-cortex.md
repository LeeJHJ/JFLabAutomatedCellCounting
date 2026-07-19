---
created: 2026-07-19T02:42:48Z
title: Phase 7 imaging QC — autofocus banding and missing cortex tissue
area: imaging
files:
  - Automated Cell Counting/wBA Sungmo/wBA1-3_s1_MIP.ome.tiff
  - Automated Cell Counting/wBA Sungmo/wBA1-3_s1_identity.png
---

## Problem

Operator sign-off during Phase 5 plan 05-03 (multi-scene MIP identity gate) surfaced two
genuine imaging/tissue-QC findings on the wBA1-3 5-section series. Both are orthogonal to the
converter's channel-identity and scene-fusion concerns (which were separately confirmed correct
and do NOT reopen plan 05-01) — these are acquisition-quality issues that need to be re-checked
under Phase 7 (Imaging Re-Validation) before the series is trusted for classification/area
readout:

1. **Autofocus failure on some slices → row-to-row (tile-row) contrast/focus banding.**
   Visible in `wBA1-3_s1_MIP.ome.tiff`. Some tile rows differ in contrast/focus from
   neighboring rows because autofocus did not lock consistently across the mosaic.
   Primary risk: detection/classification quality — defocused rows blur/dim nuclei.
   `histogramThreshold` + robust median+k·MAD absorb brightness *drift* but NOT focus *blur*.
   Low risk to the DeepSlice → manual-angle → export registration workflow (no elastix, so
   local contrast banding doesn't feed a similarity-metric optimizer).

2. **Small missing cortex pieces on some sections.**
   Not a registration-breaker under the no-elastix workflow (DeepSlice + manual angle doesn't
   depend on complete tissue extent the way elastix mutual-information optimization would).
   However it causes region-level under-count and under-area (deflated density denominator)
   for the affected cortical region on the affected section(s) — relevant to Phase 9
   (Generalizable Area-Based Density Readout, AREA-01/AREA-02) where %-area-above-threshold
   is the readout.

## Solution

Handle both under Phase 7 (Imaging Re-Validation, IMG-01/IMG-02) as part of re-running the
D-05 imaging gates at the new 4-plane/lower-laser acquisition parameters:

1. Autofocus/focus-banding: extend the per-section visual tissue-QC (OPT-01-style plateau +
   visual DAPI check already planned for IMG-02) to explicitly flag tile-row contrast/focus
   discontinuities before detection is trusted on the affected rows. If the k=3 threshold
   (IMG-01) is re-swept for brightness drift, confirm it does not mask focus-blur separately.
2. Missing cortex tissue: per-section visual tissue-QC (already an open risk in STATE.md —
   "Tissue damage in the 5-section series undetected") should explicitly check for missing
   cortical pieces per section, and any region exclusion from area-based readout (Phase 9)
   must be a priori and principled (document the rule, not the outcome), consistent with the
   project's stats conventions in CLAUDE.md.

Source: operator sign-off transcript, Phase 5 plan 05-03
(`.planning/phases/05-series-scaffolding-multi-scene-mip-batch-export-integrity/05-03-SUMMARY.md`).
