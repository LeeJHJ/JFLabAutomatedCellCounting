---
phase: quick-260724-kmj
plan: 01
subsystem: infra
tags: [czi-mip, tile-stitch, flat-field, shading-correction, feather-blend, ome-xml, channel-color]

# Dependency graph
requires:
  - phase: quick-260724-iqn
    provides: additive per-scene tile-stitch isolation path in czi_mip.py (_stitch_scene_tiles brighter-wins, _read_channel_stacks_tiles)
provides:
  - Per-channel retrospective flat-field shading correction (_estimate_shading_field, _apply_shading) applied in the tile-stitch path only
  - Feathered weighted-average seam blending in _stitch_scene_tiles (replaces np.maximum brighter-wins)
  - OME-XML per-channel display Color (DAPI blue, AF568/TdTomato red, AF488/Fos green) via _ome_color
  - Extended synthetic --self-test proofs (f) vignette-flattening, (g) no-hard-seam, (h) isolation-under-feathering, (i) OME channel colors
affects: [phase-06.1-06-operator-czi-conversion, wBA-series-conversion, M3-7scene-reconversion]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Retrospective (no-reference-image) flat-field shading: per-tile robust-mean normalize -> per-pixel median across pooled tiles -> gaussian smooth -> renormalize to mean 1.0, estimated per channel from that channel's own already-read tiles (no extra CZI reads)"
    - "Feathered weighted-average seam blending: float64 weighted-sum + weight-sum canvases accumulated per tile, normalized at the end (weight==0 -> 0), round-before-cast for integer dtypes so single-tile cores recover exactly"
    - "OME signed-int32 RGBA Color packing: (r<<24)|(g<<16)|(b<<8)|a, subtract 2**32 when >= 2**31 to match OME's xsd:int Color attribute"

key-files:
  created: []
  modified:
    - czi_mip.py

key-decisions:
  - "Flat-field/feather changes confined strictly to the tile-stitch path (_stitch_scene_tiles, _read_channel_stacks_tiles) plus new pure helpers; _read_channel_stacks_region and read_mosaic left byte-unchanged (verified against pre-task baseline commit 750b9be)"
  - "DEFAULT_FEATHER_MARGIN=130 and DEFAULT_SHADING_SMOOTH_SIGMA=5.0 added as module-level, operator-tunable constants (not CLI flags) -- matches the plan's 'module constant' directive, sized to the real ~130px ZEN tile overlap"
  - "_feather_weights clamps margin to min(h,w)//2 so tiny self-test tiles never overshoot; floor=1e-3 keeps every weight strictly positive so single-tile-only regions recover their tile's value exactly after normalization"
  - "_estimate_shading_field pools all (z,m) tiles matching a channel's MODAL tile shape (guards against any ragged edge tile at the mosaic boundary) and falls back to a uniform ones field (no-op) on no-qualifying-tile or shape-mismatch input -- never emits NaN/inf per threat T-kmj-01"
  - "_ome_color matches DAPI/AF568/TDT/TDTOMATO/AF488/FOS by case-insensitive substring, defaulting unmatched channel names to white -- keeps the function usable on any future channel naming variant without crashing"

patterns-established:
  - "Two synthetic self-test proof idioms reused going forward: (1) a known-shape corruption (vignette) proven present before a fix and collapsed after, via a boundary/interior sample ratio; (2) a smooth-ramp check via max absolute first-difference across a profile row, to distinguish feathered blending from a hard step"

requirements-completed: [QUICK-kmj-flatfield-blend]

coverage:
  - id: D1
    description: "Per-channel flat-field shading correction estimated from the scene's own already-read tiles (no reference image, no new dependency, no extra CZI reads) flattens a known synthetic radial vignette"
    requirement: "QUICK-kmj-flatfield-blend"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test (proof f): boundary/interior ratio 0.902 (uncorrected) -> 1.001 (corrected)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Feathered weighted-average blending replaces np.maximum brighter-wins seam resolution; single-tile cores still recover exactly on the uint16 round-trip"
    requirement: "QUICK-kmj-flatfield-blend"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test (proof d) strictly-between overlap assertion; (proof g) smooth-ramp max-first-diff check; (proof e) byte-identical hybrid composition unaffected"
        status: pass
    human_judgment: false
  - id: D3
    description: "Cross-scene isolation is preserved under the new feathered blend path"
    requirement: "QUICK-kmj-flatfield-blend"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test (proof d) neighbor-value-absent + (proof h) explicit re-proof under feathering"
        status: pass
    human_judgment: false
  - id: D4
    description: "OME-XML embeds a per-channel display Color; DAPI maps to blue, AF568/TdTomato to red, AF488/Fos to green; PhysicalSizeX calibration round-trip still passes"
    requirement: "QUICK-kmj-flatfield-blend"
    verification:
      - kind: unit
        ref: "czi_mip.py --self-test (proof i): color values 65535/-16776961/16711935 + Color attribute present on all 3 <Channel> elements + PhysicalSizeX round-trip intact"
        status: pass
    human_judgment: false
  - id: D5
    description: "Region path (_read_channel_stacks_region / read_mosaic) stays byte-identical; scene isolation, hybrid projection, --isolate semantics, --check-scenes, output-count glob, --channels order contract all preserved"
    requirement: "QUICK-kmj-flatfield-blend"
    verification:
      - kind: unit
        ref: "git diff of _read_channel_stacks_region function body against pre-task baseline (750b9be) is empty; --self-test proofs (a)-(e) unchanged pass; --help lists all flags"
        status: pass
    human_judgment: false
  - id: D6
    description: "Real M3 re-conversion + grid re-measurement (autocorr peak at 1382 must drop) on the actual 33 GB CZI"
    verification: []
    human_judgment: true
    rationale: "Plan scope explicitly excludes reading the 33 GB CZI in the build/test loop; the actual re-conversion + measurement is a SEPARATE orchestrator step after this quick task. This SUMMARY covers the logic proof only, on synthetic data."

# Metrics
duration: 7min
completed: 2026-07-24
status: complete
---

# Quick Task 260724-kmj: CZI Flat-Field Shading Correction + Feathered Blend + OME Channel Colors Summary

**Removed the periodic DAPI tile grid from `czi_mip.py`'s tile-stitch path via per-channel retrospective flat-field correction (estimated from the scene's own already-read tiles) + feathered overlap blending, and fixed QuPath's wrong DAPI display color by embedding OME per-channel RGBA colors — both proven on synthetic data only, with the region path and all prior guarantees byte-unchanged.**

## Performance

- **Duration:** 7 min
- **Tasks:** 2/2 completed
- **Files modified:** 1 (`czi_mip.py`)

## Accomplishments

- `_stitch_scene_tiles` no longer resolves overlapping-tile seams with a hard `np.maximum` brighter-wins step. It now accumulates float64 weighted-sum/weight-sum canvases per tile using `_feather_weights` (a per-pixel linear edge-ramp, strictly > 0 everywhere) and normalizes at the end — a smooth cross-fade across the seam, while single-tile-only regions still recover their source tile's value exactly (round-before-cast for integer dtypes; no rounding for float dtypes).
- `_estimate_shading_field` estimates each channel's illumination SHAPE (vignetting) purely from that channel's own already-read tiles pooled across Z and M — robust per-tile mean normalization, per-pixel median across normalized tiles, gaussian smoothing, renormalize to mean 1.0. No reference image, no new dependency, no extra CZI reads. Falls back to a uniform (no-op) field if no tile qualifies or shapes mismatch, and never emits NaN/inf.
- `_apply_shading` divides each tile by the guarded (> 0) field, rounds and clips to the tile's own dtype range before casting back — corrects vignetting per channel because the field is estimated per channel.
- `_read_channel_stacks_tiles` was restructured to read all of a channel's (z, m) tiles once, pool them (matching the channel's modal tile shape) to estimate one shading field per channel, then apply + feather-stitch per Z — no extra CZI reads, and peak memory stays bounded to one channel's tiles across Z (released before the next channel).
- `_ome_color(name)` maps a channel name (case-insensitive substring match) to an OME signed-int32 RGBA display Color — DAPI blue (65535), AF568/TdTomato red (-16776961), AF488/Fos green (16711935), else white (-1). `_build_ome_xml` now emits `Color="..."` on every `<Channel>` element; the `PhysicalSizeX` calibration round-trip is untouched.
- `--self-test` extended with proofs (f) (a known synthetic radial vignette shows boundary/interior modulation before correction, ~0.902, and flattens to ~1.001 after `_estimate_shading_field` + `_apply_shading` + feather stitch), (g) (feathered blending ramps smoothly across a seam — max first-difference stays well below the value of a hard brighter-wins step), (h) (cross-scene isolation re-proven explicitly under the feathered blend path), and (i) (OME channel color mapping + `Color` attribute presence + `PhysicalSizeX` round-trip). Proof (d)'s seam assertion was updated from an exact brighter-wins value to a strictly-between check reflecting the new feathered-blend semantics; its isolation and union-shape (40,70) assertions were kept verbatim. Proofs (a),(b),(c),(e) pass unchanged.
- `_read_channel_stacks_region` and every `read_mosaic` call in it are byte-identical to the pre-task baseline (verified via `diff` against commit `750b9be`, the completion of the prior `260724-iqn` tile-stitch task) — the region path is fully preserved.

## Task Commits

Each task was committed atomically:

1. **Task 1: Flat-field shading correction + feathered overlap blending in the tile-stitch path** - `cd21f24` (feat)
2. **Task 2: OME-XML per-channel display colors + self-test proof (i) + single-copy verification** - `00b6261` (feat)

## Files Created/Modified

- `czi_mip.py` — added `_feather_weights`, `_estimate_shading_field`, `_apply_shading`, `_ome_color`; rewrote `_stitch_scene_tiles` (feathered weighted-average blend, `feather_margin` parameter defaulting to new module constant `DEFAULT_FEATHER_MARGIN`); restructured `_read_channel_stacks_tiles` to estimate + apply per-channel shading before stitching; `_build_ome_xml` now emits a `Color` attribute per `<Channel>`; extended `_self_test()` with proofs (f), (g), (h), (i) and updated proof (d)'s seam assertion.

## Decisions Made

- Flat-field/feather changes are confined strictly to the tile-stitch path and its new pure helpers — `_read_channel_stacks_region` and `read_mosaic` are byte-unchanged, verified by diffing the function body text against the pre-task baseline commit.
- `DEFAULT_FEATHER_MARGIN` (130 px, ~ the real ZEN tile overlap) and `DEFAULT_SHADING_SMOOTH_SIGMA` (5.0 px) are module-level, operator-tunable constants rather than new CLI flags, per the plan's directive.
- `_feather_weights` clamps its margin to `min(h, w) // 2` so small self-test tiles (down to 30x30 and smaller) never see the ramp overshoot the tile, and keeps every weight strictly positive (floor = 1e-3) so single-tile-only canvas regions recover their source tile's value exactly after the weighted normalization and integer rounding.
- `_estimate_shading_field` pools only tiles matching a channel's *modal* tile shape (guards against a ragged edge tile at the mosaic boundary silently corrupting the median), and falls back to a uniform (identity, no-op) field whenever no tile qualifies or shapes are inconsistent — never emits NaN/inf, satisfying threat T-kmj-01.
- `_ome_color` matches by case-insensitive substring (`DAPI`, `AF568`/`TDT`/`TDTOMATO`, `AF488`/`FOS`) and defaults any unmatched channel name to white, so it never raises on an unexpected channel name.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. All proofs (a)-(i) passed on the first `--self-test` run after implementation; no auto-fix iterations were required.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Logic is proven on synthetic data only (`--self-test` passes all proofs a-i; the 33 GB M3 CZI was never opened during this task, per the plan's explicit build/test-loop exclusion).
- Next operator action (separate orchestrator step, NOT part of this quick task): re-run `czi_mip.py --isolate tiles` (or `auto`, since the M3 7-scene file overlaps) against the real M3 CZI and re-measure the DAPI column-profile autocorrelation — the peak at the ~1382 px tile step should drop, and QuPath should now show DAPI in blue instead of green.
- No blockers for downstream phases; this is an additive/corrective change to `czi_mip.py`'s tile-stitch path and does not change any other pipeline stage's interface or the region-path behavior used by non-overlapping files.

## Self-Check: PASSED

- FOUND: `/home/jflab/Analysis/czi_mip.py` (modified, exists)
- FOUND: commit `cd21f24` (`git log --oneline --all | grep cd21f24`)
- FOUND: commit `00b6261` (`git log --oneline --all | grep 00b6261`)
- `--self-test` exits 0 with proofs (a)-(i) PASSED
- `--help` lists `--isolate {auto,region,tiles}`, `--check-scenes`, `--self-test`
- Exactly one `czi_mip.py` on disk under `/home/jflab` (excluding `miniforge3`) — repo root
- `_read_channel_stacks_region` function body (incl. its `read_mosaic` call) is byte-identical to the pre-task baseline commit `750b9be`

---
*Quick task: 260724-kmj*
*Completed: 2026-07-24*
