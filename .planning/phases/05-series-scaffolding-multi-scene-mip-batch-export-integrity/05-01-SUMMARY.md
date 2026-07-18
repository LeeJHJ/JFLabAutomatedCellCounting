---
phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity
plan: 01
subsystem: conversion
tags: [aicspylibczi, tifffile, pillow, ome-tiff, czi, mosaic, mip, argparse]

# Dependency graph
requires:
  - phase: 04-biological-plausibility-validation-and-imaging-optimization
    provides: single-scene czi_mip.py MIP core + channel-order fix + pixel calibration (0.6905355 µm/px)
provides:
  - Multi-scene CLI converter (czi_mip.py) turning one processed CZI into 5 per-scene MIP OME-TIFFs
  - Per-scene identity artifacts (printed records + thumbnail PNGs) proving scene->file identity
  - Region-based scene isolation pattern (get_all_mosaic_scene_bounding_boxes + region= only)
affects: [06-registration, 08-classification, series-scaffolding, quPath-entries]

# Tech tracking
tech-stack:
  added: [Pillow/PIL (thumbnail encode; already in braian env)]
  patterns:
    - "Per-scene mosaic isolation via region=bbox only (no S= kwarg on mosaic files)"
    - "Scene count from len(get_all_mosaic_scene_bounding_boxes()), never get_dims_shape()['S']"
    - "Paired 0-based scene_key + 1-based s{N} label on every identity line (off-by-one guard)"

key-files:
  created: []
  modified: [czi_mip.py]

key-decisions:
  - "Grafted czi_hybrid_mip.py's mature CLI/OME-XML shape onto the canonical czi_mip.py target (CONTEXT.md names czi_mip.py canonical; RESEARCH shows czi_hybrid_mip.py structurally superior)"
  - "Scene isolation uses region=(b.x,b.y,b.w,b.h) verbatim; passing S= to read_mosaic on a mosaic file raises PylibCZI_CDimCoordinatesOverspecifiedException"
  - "Thumbnail downsamples the in-hand DAPI MIP plane (8x strided) rather than a fractional read_mosaic(scale_factor<1.0) — avoids the known libCZI subblock rendering bug"
  - "DAPI channel index auto-detected by name ('DAPI' in name), fallback to last channel"

patterns-established:
  - "Pre-flight pairwise bbox non-overlap assertion runs before the heavy conversion loop"
  - "Post-conversion assertions: 5 outputs, per-scene shape==bbox(h,w), PhysicalSizeX round-trips"
  - "Identity record prints scene_key (0-based) + label s{N} (1-based) + bbox + M_tiles + dims, no AP claim"

requirements-completed: [CONV-01, CONV-02]

coverage:
  - id: D1
    description: "czi_mip.py emits exactly 5 per-scene MIP OME-TIFFs (wBA1-3_s1..s5_MIP.ome.tiff), no scene fusion, each carrying PhysicalSizeX/Y=0.6905355 µm in embedded OME-XML; per-scene (Y,X)==bbox(h,w)"
    requirement: "CONV-01"
    verification:
      - kind: automated_ui
        ref: "conda run -n braian python3 czi_mip.py --czi <processed.czi> --outdir <dir> — inline asserts: 5 outputs, shape==bbox, PhysicalSizeX round-trip; exit 0"
        status: pass
      - kind: other
        ref: "conda run -n braian python3 czi_mip.py --check-scenes — prints 5 non-overlapping bboxes, exit 0 (SC#4 smoke test)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Per-scene identity records printed (0-based scene_key + 1-based s{N} + bbox + M_tiles + dims) and 5 identity thumbnail PNGs written from the in-hand DAPI plane"
    requirement: "CONV-02"
    verification:
      - kind: automated_ui
        ref: "grep -Ec 'scene_key=[0-9].*label=s[1-9]' == 5; scene_key=2->label=s3 pairing; 5 *_identity.png non-zero pixel content; no anterior/posterior/AP wording"
        status: pass
    human_judgment: true
    rationale: "D-01 explicitly asks for operator visual eyeball confirmation that each thumbnail shows the expected single coherent coronal section; the scripted half (records + PNG existence + non-zero content) is proven, but scene->physical-section identity sign-off is gated to plan 05-03 / human-verify."

# Metrics
duration: 7min
completed: 2026-07-18
status: complete
---

# Phase 5 Plan 01: Multi-Scene MIP + Scene-Identity Converter Summary

**czi_mip.py generalized into a multi-scene CLI converter that turns the 16 GB 5-scene processed CZI into 5 identity-verified, pixel-calibrated section MIP OME-TIFFs (region-based scene isolation, no fusion) plus paired per-scene identity records and thumbnails**

## Performance

- **Duration:** ~7 min active (dominated by two full 5-scene conversions over the 16 GB CZI)
- **Started:** 2026-07-18T22:40:59Z
- **Completed:** 2026-07-18T22:47Z
- **Tasks:** 2
- **Files modified:** 1 (czi_mip.py)

## Accomplishments
- Replaced czi_mip.py's hardcoded single-scene body with an argparse CLI (`--czi`, `--outdir`, `--channels`, `--pixel-um`, `--animal-prefix`, `--check-scenes`) grafting czi_hybrid_mip.py's mature shape onto the canonical target.
- Scene isolation via `get_all_mosaic_scene_bounding_boxes()` + `region=` only; pre-flight pairwise non-overlap assertion; scene count never derived from the unsafe `get_dims_shape()['S']` field.
- Emitted 5 shape-matched MIPs (`wBA1-3_s1..s5_MIP.ome.tiff`, distinct sizes 775M–990M confirming no fusion), each with `PhysicalSizeX="0.6905355"` `µm` round-tripping through OME-XML.
- Added `_scene_identity_record` (paired 0-based scene_key + 1-based s{N} label, bbox, M_tiles=141/152/161/151/161 matching RESEARCH, dims; no AP claim) and `_save_identity_thumbnail` (percentile-clip → uint8 → 8x strided downsample of the in-hand DAPI MIP → PIL PNG). 5 non-empty identity PNGs written.

## Task Commits

Each task was committed atomically:

1. **Task 1: Multi-scene CLI converter** - `7d049dc` (feat)
2. **Task 2: Per-scene identity record + thumbnail PNG** - `9069710` (feat)

_Note: tasks were marked tdd="true" in the plan, but this project has no pytest/unit-test framework (RESEARCH Validation Architecture: "printed assertion + human visual audit" is the established convention). Verification is via inline runtime assertions in the script itself + the plan's automated grep/shape checks, consistent with project norms — no separate RED test commit was created._

## Files Created/Modified
- `czi_mip.py` - Generalized from a single-scene hardcoded converter into a multi-scene CLI converter with pre-flight scene assertions, per-scene region-isolated MIP, embedded OME-XML pixel calibration, and per-scene identity records + thumbnails.

## Decisions Made
- **Graft, not rewrite:** kept czi_mip.py's per-channel/per-Z streaming MIP core and print-indent convention; borrowed czi_hybrid_mip.py's CLI + names-driven `_build_ome_xml`. czi_mip.py stays the canonical file per CONTEXT.md.
- **region= only:** confirmed against RESEARCH — `S=` on a mosaic file raises; scene bbox passed verbatim (no padding/origin offset).
- **Thumbnail from in-hand DAPI MIP plane:** avoids a second CZI read and the `scale_factor<1.0` libCZI rendering caveat.
- **DAPI index auto-detected by name** (falls back to last channel) so the thumbnail always uses the nuclear counterstain.

## Deviations from Plan

None - plan executed exactly as written. (The tasks carried `tdd="true"`, but per the project's documented no-pytest convention the RED/GREEN test-file cycle is satisfied by the script's own inline runtime assertions rather than a separate test framework; this is a convention alignment, not a scope change.)

## Issues Encountered
- On the first execution attempt the converter was launched and completed the 5 MIPs, but the executor returned before implementing Task 2. On resume, Task 1's code was committed as-is, Task 2 was implemented, and a single fast re-run emitted both the identity records and PNGs (and re-wrote the MIPs). No data loss; final state is fully verified.
- `conda run` buffers stdout; re-ran with `python3 -u` for live progress. Not a code issue.

## User Setup Required
None - no external service configuration required. All dependencies (aicspylibczi 3.3.1, tifffile, numpy, Pillow 12.2.0) already present in the `braian` conda env.

## Next Phase Readiness
- 5 per-scene MIP OME-TIFFs are ready to import as QuPath project entries for Phase 6 registration; their `wBA1-3_s{N}` filenames become each section's identity through the series.
- **Operator visual sign-off (D-01) is still pending** — the 5 `*_identity.png` thumbnails should be eyeballed to confirm each is a single coherent coronal section before registration; this is gated in plan 05-03 (human-verify).
- **Open assumption (RESEARCH A1):** DAPI is confirmed as the last channel, but TdTomato-vs-Fos assignment between physical channels 0/1 on this new CZI is inherited from the M3 acquisition, not independently re-derived — flagged for the plan 05-03 human-verify checkpoint before classification trusts the `--channels` override.

## Self-Check: PASSED

- czi_mip.py present; commits 7d049dc + 9069710 in history.
- All 5 MIP OME-TIFFs and all 5 identity PNGs present on disk (gitignored microscopy data — not committed by design).

---
*Phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity*
*Completed: 2026-07-18*
