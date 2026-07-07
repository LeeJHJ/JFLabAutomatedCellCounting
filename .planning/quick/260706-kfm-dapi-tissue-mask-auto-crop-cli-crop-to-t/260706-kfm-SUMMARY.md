---
phase: 260706-kfm
plan: 01
subsystem: imaging-pipeline
tags: [tifffile, scikit-image, scipy, ome-tiff, dapi, tissue-mask, elastix-pilot]

requires: []
provides:
  - "Reusable CPU-only CLI (`scripts/crop_to_tissue.py`) that auto-crops a multichannel MIP OME-TIFF to its DAPI tissue bounding box, preserving pixel calibration and channel names."
affects: [ABBA-elastix-pilot, full-series-registration]

tech-stack:
  added: []
  patterns:
    - "Name-based channel selection (never hardcoded index) via case-insensitive substring match, mirroring the czi_mip.py channel-order lesson."
    - "Downsample-for-masking / scale-back-for-crop pattern: Otsu + morphology run on a strided-downsampled DAPI plane (auto factor to ~2048px), bbox scaled back to full resolution before cropping the full-res array."

key-files:
  created:
    - scripts/crop_to_tissue.py
  modified: []

key-decisions:
  - "DAPI channel resolved by case-insensitive substring match with a --dapi-channel override (name or int index) — never a hardcoded index, per the locked channel-order lesson (AF568-T2, AF488-T3, DAPI-T4 order in real files)."
  - "Smoke test used --margin-percent 0 instead of the script's 5% default, because the real M3 hippocampus MIP's DAPI signal already extends to within ~1.4-2.8% of the frame's bottom/right edges — the default 5% margin exceeds that thin remaining border and clamps back to the full frame (a correct, not buggy, clamping outcome). See 'Deviations' below."
  - "Smoke test I/O overridden to a scratchpad throwaway path per explicit task instruction, to avoid modifying any project directory (especially the older 062226 project)."

requirements-completed: [QUICK-CROP-01]

coverage:
  - id: D1
    description: "crop_to_tissue.py CLI selects the DAPI channel by name (never hardcoded index), Otsu-thresholds + cleans a downsampled tissue mask, computes an edge-clamped bbox with configurable margin, crops all channels, and writes an OME-TIFF preserving pixel calibration and channel names/order."
    requirement: "QUICK-CROP-01"
    verification:
      - kind: unit
        ref: "conda run -n braian python3 scripts/crop_to_tissue.py --self-test (synthetic DAPI-at-index-2 blob, edge-clamped margin, dtype/channel preservation, OME-XML round-trip)"
        status: pass
      - kind: integration
        ref: "conda run -n braian python3 scripts/crop_to_tissue.py <real M3 MIP Z1-3> -o <scratchpad>/M3_20x_MIP_Z1-3_cropped.ome.tiff --margin-percent 0, followed by re-read assertion script (dtype, channel count/order/names, PhysicalSizeX equality, reduced Y/X dims) printing 'SMOKE OK'"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-07-06
status: complete
---

# Phase 260706-kfm: DAPI Tissue-Mask Auto-Crop CLI Summary

**Built a CPU-only, name-based DAPI-channel tissue-mask auto-crop CLI (`scripts/crop_to_tissue.py`) and validated it end-to-end against a real M3 hippocampus MIP, discovering that this particular MIP's tissue already nearly fills the frame (crop headroom is thin, not absent).**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-06
- **Tasks:** 2/2 completed
- **Files modified:** 1 created (`scripts/crop_to_tissue.py`)

## Accomplishments

- Implemented `scripts/crop_to_tissue.py`: reads a MIP OME-TIFF, selects the DAPI channel by case-insensitive name match (with a `--dapi-channel` name-or-index override), computes a downsampled Otsu tissue mask (morphological close + fill holes + small-object removal), derives an edge-clamped bounding box with a configurable per-axis margin, crops all channels, and writes an output OME-TIFF that preserves the input's PhysicalSizeX/Y (µm) and channel names/order exactly.
- Built a synthetic `--self-test` (no large files required) exercising every helper: DAPI-by-name selection with DAPI deliberately placed at index 2 (not 0, mirroring the real AF568/AF488/DAPI ordering), mask/bbox recovery of a known blob, edge-clamped margin expansion, dtype/channel-count preservation through cropping, and an OME-XML round-trip of pixel size + channel names. All assertions pass; script prints `SELF-TEST PASS` and exits 0.
- Ran an end-to-end smoke crop against the real M3 hippocampus MIP (`M3_20x_MIP_Z1-3.ome.tiff`, shape (3, 10240, 15770), channels `AF568-T2, AF488-T3, DAPI-T4`), writing to a scratchpad throwaway path (no project directory touched). Re-read the output and confirmed: uint16 dtype preserved, channel count/order/names preserved verbatim (including `DAPI-T4`), `PhysicalSizeX` exactly equal to the input (`0.6905355`), and Y/X dims strictly reduced (10240→9952, 15770→15546). Assertion script printed `SMOKE OK`.
- Diagnosed (not "fixed around") an initial full-frame no-op result at the script's default 5% margin: confirmed via direct pixel-intensity sampling that the real DAPI channel's signal genuinely extends to within ~2.8% (Y) / ~1.4% (X) of the frame's bottom/right edges already — the mask/bbox math is correct; the default margin simply exceeds that thin remaining border and clamps back to the full frame for this specific image. Re-ran with `--margin-percent 0` to demonstrate genuine tissue-tight cropping.

## Task Commits

No git repository is present in this project (git is not installed on this machine per `.claude/CLAUDE.md`) — per the sequential-executor instructions for this run, git add/commit steps were skipped entirely. All work is present directly on disk:

1. **Task 1: Implement crop_to_tissue.py (DAPI mask → bbox → crop → OME-TIFF) with a synthetic --self-test** — no commit (no git repo); verified via `--help` and `--self-test` (both exit 0, self-test prints `SELF-TEST PASS`).
2. **Task 2: End-to-end smoke crop of the real M3 hippocampus MIP and validate the pilot artifact** — no commit (no git repo); verified via re-read assertion script printing `SMOKE OK`.

## Files Created/Modified

- `/home/jflab/Analysis/scripts/crop_to_tissue.py` - DAPI tissue-mask auto-crop CLI: `_read_mip`, `_select_dapi_index`, `_compute_tissue_mask`, `_tissue_bbox`, `_build_ome_xml`, `_self_test`, and `main()`/`parse_args()`. CPU-only (numpy, scipy.ndimage, skimage.filters/morphology, tifffile — no GPU imports).

## Smoke Test Artifact (not tracked in project)

- Input: `/home/jflab/Analysis/M3 Hippocampus 20x 062226/M3_20x_MIP_Z1-3.ome.tiff` (read-only; untouched)
- Output (throwaway, per explicit task instruction — NOT written into any project/QuPath directory): `/tmp/claude-1000/-home-jflab-Analysis/fc5d78b7-a64a-4c79-8e92-22979c77ff55/scratchpad/M3_20x_MIP_Z1-3_cropped.ome.tiff`
- Invocation used: `--margin-percent 0` (see Deviations below for why the script's 5% default was not used for this particular smoke run)
- Result: (3, 10240, 15770) → (3, 9952, 15546), uint16, channels `['AF568-T2', 'AF488-T3', 'DAPI-T4']` preserved verbatim, `PhysicalSizeX = 0.6905355` unchanged, tissue bbox `(y0=288, y1=10240, x0=224, x1=15770)`, bbox-occupancy fill fraction 1.0, foreground-pixel coverage ~0.52.

## Decisions Made

- DAPI channel selection is strictly name-based (case-insensitive substring "dapi"), with a `--dapi-channel` override accepting either a channel-name substring or an integer index — never a hardcoded index, per the project's locked channel-order lesson (`AF568-T2, AF488-T3, DAPI-T4` order; DAPI is index 2, not 0, in real files).
- Margin is applied per-axis as a percentage of the tissue bbox extent, expanded symmetrically and clamped to `[0, full_dim]` — this is the correct, edge-safe behavior verified by the self-test's flush-to-edge case.
- Script matches `czi_mip.py` conventions exactly: `from __future__ import annotations` first, `RawDescriptionHelpFormatter` + `epilog=__doc__`, `Path` objects for file args, snake_case, `_`-prefixed private helpers, staged "Step N..." progress prints.
- `skimage.morphology.binary_closing`/`remove_small_objects(min_size=...)` were updated to their non-deprecated scikit-image 0.26 equivalents (`closing` and `remove_small_objects(max_size=...)`, translating `max_size = min_size - 1` to preserve identical "remove strictly smaller than min_size" semantics) — this was a Rule 1 auto-fix applied during Task 1 to eliminate `FutureWarning`s observed on the first self-test run, with no behavior change (verified: self-test still passes identically, warnings gone).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug/Future-breakage] Replaced deprecated scikit-image 0.26 morphology calls**
- **Found during:** Task 1, first `--self-test` run
- **Issue:** `binary_closing(mask, footprint=...)` and `remove_small_objects(mask, min_size=...)` both emitted `FutureWarning`s — scikit-image 0.26 deprecates `binary_closing` in favor of `closing`, and deprecates `remove_small_objects`'s `min_size` parameter in favor of `max_size` (with inverted inclusive/exclusive semantics: old `min_size` kept objects `>= min_size`; new `max_size` removes objects `<= max_size`).
- **Fix:** Imported `closing` instead of `binary_closing`; called `remove_small_objects(mask, max_size=min_size - 1)` to preserve identical "remove strictly smaller than the fractional threshold" behavior.
- **Files modified:** `scripts/crop_to_tissue.py`
- **Commit:** none (no git repository in this project)

### Notable Finding (not a code defect — documented per plan's Task 2 diagnose-first instruction)

**Default 5% margin produces a full-frame (no-op) crop on `M3_20x_MIP_Z1-3.ome.tiff`.**
- **What was observed:** Running the script with its default `--margin-percent 5.0` on the real smoke-test MIP returned a bbox of `(0, 10240, 0, 15770)` — i.e., cropped dims equal to the original, which the plan explicitly flags as a signal to diagnose before assuming success.
- **Diagnosis:** Direct pixel sampling on the full-resolution DAPI channel showed the top edge is genuinely blank (mean intensity ~240, ~0% of pixels above the Otsu threshold) but the bottom edge (mean ~9640, 8.7% above threshold) and right edge (mean ~21239, 33% above threshold) already carry real tissue signal. The margin-free tissue bbox is `(y0=288, y1=10240, x0=224, x1=15770)` — i.e., tissue already reaches to within 288px (2.8%) of the bottom and 224px (1.4%) of the right edge. The default 5% margin (498px / 777px on this frame) exceeds that already-thin border on all four clamped sides, so the margin-expanded-then-clamped bbox lands back at `(0, 10240, 0, 15770)` — the full frame. This is the mask/bbox logic behaving *correctly* (edge-clamping exactly as designed and self-test-verified), not a bug to patch.
- **Resolution:** No code change was made to the mask/bbox algorithm (per plan's instruction not to "tune around" a genuine bug — there wasn't one to fix). The smoke-test invocation used `--margin-percent 0` to demonstrate the underlying tissue-tight crop working correctly and to satisfy the "reduced Y/X dims" verification requirement.
- **Recommendation for the full series:** For sections whose MIP mosaic is already tightly framed around the tissue (as this hippocampus MIP appears to be, likely because the CZI mosaic tile-stitching already follows the tissue outline), a smaller `--margin-percent` (or 0) should be used; the 5% default remains appropriate for MIPs with more surrounding blank canvas. This is an operational note for the researcher, not a script defect.

## Self-Check: PASSED

- FOUND: `/home/jflab/Analysis/scripts/crop_to_tissue.py`
- FOUND: `--help` exits 0 and prints RawDescriptionHelpFormatter usage + epilog
- FOUND: `--self-test` prints `SELF-TEST PASS` and exits 0
- FOUND: smoke-test output at scratchpad path exists, re-read assertion prints `SMOKE OK`
- FOUND: no files written into any project directory (`M3 Hippocampus 20x 062226/` unchanged — verified via directory listing before/after)
- N/A: git commit hashes (no git repository present in this project; git steps skipped per explicit sequential-executor instructions)
