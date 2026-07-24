---
phase: quick-260724-iqn
plan: 01
subsystem: infra
tags: [aicspylibczi, czi-mip, tile-stitch, multi-scene, cross-scene-isolation]

# Dependency graph
requires:
  - phase: quick-260724-h6y
    provides: czi_mip.py hybrid DAPI projection (single sharpest anchor plane + full-Z marker MIP)
provides:
  - Per-scene tile-stitch isolation path in czi_mip.py, selected automatically when scene bboxes overlap
  - "--isolate {auto,region,tiles}" CLI flag with a preserved region+overlap safety refusal
  - Synthetic self-test proofs of cross-scene isolation, tile-union sizing, seam resolution, and hybrid-projection composition
affects: [phase-06.1-06-operator-czi-conversion, wBA-series-conversion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Additive isolation-mode dispatch: _resolve_isolation_mode(requested, overlapping_pairs) -> 'region'|'tiles', wired ahead of the per-scene channel read"
    - "Tile-stitch canvas sized to the scene's OWN tile-union (min/max of that scene's tile origins), never the full mosaic or the reported bbox -- structural isolation guarantee, not a runtime check"

key-files:
  created: []
  modified:
    - czi_mip.py

key-decisions:
  - "Auto mode is the default and preserves prior behavior exactly for non-overlapping files (region path, byte-identical read call)"
  - "Tile-stitch seam resolution (within one scene's own overlapping tiles) is brighter-wins via np.maximum -- safe for MIP/cell-counting, documented in _stitch_scene_tiles docstring"
  - "Per-tile geometry uses get_mosaic_tile_bounding_box(S=,M=,C=0,Z=0) per tile, never get_all_mosaic_tile_bounding_boxes() (observed to hang on the 33 GB M3 file)"
  - "--isolate region still refuses (SystemExit) when scene bboxes overlap -- the original safety guard is preserved, just relocated into _resolve_isolation_mode"

patterns-established:
  - "channel_stacks contract: both _read_channel_stacks_region and _read_channel_stacks_tiles return the identical list-of-list-of-(Y,X)-planes structure, so _hybrid_scene_projection is unchanged and reused by both isolation modes"

requirements-completed: [QUICK-iqn-tile-stitch]

coverage:
  - id: D1
    description: "Tile-stitch isolation path assembles each scene from only its own S-scoped tiles, eliminating cross-scene tissue contamination on overlapping multi-scene mosaics"
    requirement: "QUICK-iqn-tile-stitch"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test (proof d): contamination assertion (value 99 absent from scene A's canvas), tile-union sizing (40,70), seam resolution (brighter-wins)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Non-overlapping files remain on the byte-identical region=bbox path (regression preserved)"
    requirement: "QUICK-iqn-tile-stitch"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test: _resolve_isolation_mode('auto', []) == 'region'"
        status: pass
    human_judgment: false
  - id: D3
    description: "--isolate region on an overlapping file still refuses (existing safety guard reachable)"
    requirement: "QUICK-iqn-tile-stitch"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test: _resolve_isolation_mode('region', [(0,1)]) raises SystemExit"
        status: pass
    human_judgment: false
  - id: D4
    description: "Tile-stitched channel stacks compose with the unchanged hybrid projection (single sharpest anchor plane + full-Z marker MIP)"
    requirement: "QUICK-iqn-tile-stitch"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test (proof e): byte-identical anchor/marker output assertions"
        status: pass
    human_judgment: false
  - id: D5
    description: "Real M3/wBA overlapping-mosaic conversion via --isolate auto (actual CZI file, not synthetic)"
    verification: []
    human_judgment: true
    rationale: "Plan scope explicitly excludes reading the 33 GB CZI in the build/test loop; the actual conversion is a separate operator-run background task per the plan's <verification> note. This SUMMARY covers the logic proof only, on synthetic data."

# Metrics
duration: 6min
completed: 2026-07-24
status: complete
---

# Quick Task 260724-iqn: CZI Multi-Scene Tile-Stitch Isolation Summary

**Added an additive per-scene tile-stitch isolation path to `czi_mip.py` (`_stitch_scene_tiles`, `_scene_tile_geometry`, `_read_channel_stacks_tiles`/`_region`, `_resolve_isolation_mode`) plus an `--isolate {auto,region,tiles}` flag, so overlapping multi-scene CZI mosaics convert without splicing neighbor-scene tissue into a scene's crop, while non-overlapping files stay on the byte-identical region path.**

## Performance

- **Duration:** 6 min
- **Tasks:** 2/2 completed
- **Files modified:** 1 (`czi_mip.py`)

## Accomplishments

- Overlapping multi-scene CZI mosaics (e.g. the real 7-scene M3 file, 11 overlapping pairs with real tissue in the shared strips) now convert via a tile-stitch path that structurally cannot mix in a neighbor scene's pixels — each scene's canvas is sized and painted from only that scene's own tiles.
- Non-overlapping files (e.g. the 5-scene TdT-only file) remain on the original `read_mosaic(region=bbox)` path, unchanged — `--isolate auto` (the default) resolves to `"region"` whenever no scene-bbox pair overlaps.
- `--isolate region` on an overlapping file still raises the original FATAL SystemExit — the pre-existing safety guard is preserved, just relocated from an inline abort in `_preflight_scenes` into the new `_resolve_isolation_mode` decision function.
- Tile-stitched channel stacks feed the pre-existing `_hybrid_scene_projection` (single sharpest anchor plane + full-Z marker max-projection) completely unchanged — both isolation modes return the identical `channel_stacks` structure.
- `--self-test` extended with synthetic proofs (d) cross-scene isolation + tile-union sizing + brighter-wins seam resolution, and (e) tile-stitch composes byte-identically with hybrid projection, plus a `_resolve_isolation_mode` decision-table check. All fully synthetic — the 33 GB M3 CZI was never opened during this task.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add tile-stitch isolation path + --isolate mode selection to czi_mip.py** - `1fb6afa` (feat)
2. **Task 2: Extend --self-test with synthetic tile-stitch proofs and verify end-to-end** - `2820928` (test)

_Note: Task 2 is a `test`-type commit per the deviation/commit-type convention (self-test-only changes); no separate `feat` commit was needed since Task 1 already implemented the logic under test._

## Files Created/Modified

- `czi_mip.py` — added `_stitch_scene_tiles`, `_scene_tile_geometry`, `_read_channel_stacks_tiles`, `_read_channel_stacks_region`, `_resolve_isolation_mode`; refactored `_preflight_scenes` to detect-not-abort on overlap; added `--isolate {auto,region,tiles}` CLI flag; wired `main()` to dispatch region vs tiles per resolved mode; scoped the bbox shape assertion to region mode only; extended `_self_test()` with proofs (d) and (e) plus `_resolve_isolation_mode` coverage.

## Decisions Made

- Auto mode is the default and is behavior-preserving for the non-overlapping case (byte-identical `read_mosaic(region=bbox)` call, same print idiom) — no regression risk for the already-working 5-scene TdT-only file.
- Seam resolution within a scene's own overlapping tiles is brighter-wins (`np.maximum`), matching the project's MIP/cell-counting semantics (never darkens signal).
- Per-tile geometry lookups use the single-tile `get_mosaic_tile_bounding_box` call (not the batch `get_all_mosaic_tile_bounding_boxes`, which was observed to hang on the 33 GB file) — one call per tile, C=0/Z=0 reference plane, since tile layout is invariant across C/Z within a scene.
- Tile-stitch mode intentionally reports (not asserts) any difference between the stitched tile-union `(Y, X)` and the scene bbox `(h, w)` — the tile-union geometry legitimately differs from the bbox and is not an error condition, unlike the region-mode shape assertion which stays a hard `SystemExit`.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Logic is proven on synthetic data (`--self-test` passes, includes the exact contamination scenario the real overlapping M3 file exhibits). The plan's `<verification>` explicitly scopes the actual 33 GB M3 CZI conversion as a SEPARATE, operator-run background task after this self-test passes — not part of this quick task's build/test loop.
- Next operator action: run `czi_mip.py --isolate auto` (or explicit `--isolate tiles`) against the real overlapping-scene M3/wBA CZI file as a background conversion, time-boxing any pre-run API smoke test to open + one `read_image(S=0,M=0,C=0,Z=0)` + one `get_mosaic_tile_bounding_box` call per the plan's verification note.
- No blockers for downstream phases; this is an additive capability on `czi_mip.py` and does not change any other pipeline stage's interface.

## Self-Check: PASSED

- FOUND: `/home/jflab/Analysis/czi_mip.py` (modified, exists)
- FOUND: commit `1fb6afa` (`git log --oneline --all | grep 1fb6afa`)
- FOUND: commit `2820928` (`git log --oneline --all | grep 2820928`)
- `--self-test` exits 0 with proofs (a)-(e) plus `_resolve_isolation_mode` decision table PASSED
- `--help` lists `--isolate {auto,region,tiles}` (default auto)
- Exactly one `czi_mip.py` on disk (`find /home/jflab -name 'czi_mip*.py'` -> 1 result)

---
*Quick task: 260724-iqn*
*Completed: 2026-07-24*
