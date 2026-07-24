---
phase: quick-260724-h6y
plan: 01
subsystem: imaging-pipeline
tags: [czi, aicspylibczi, scipy, numpy, tifffile, focus-metric, ome-tiff]

# Dependency graph
requires:
  - phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity
    provides: multi-scene CZI isolation (region=bbox), names-driven _build_ome_xml, identity thumbnail
provides:
  - Per-scene hybrid projection in czi_mip.py -- DAPI/anchor channel = single auto-selected sharpest Z plane (var-of-Laplacian); marker channels = full-Z max projection
  - Pure, unit-testable helpers _sharpest_plane_from_stack and _hybrid_scene_projection (no CZI read)
  - --self-test flag proving the hybrid logic on synthetic arrays (no 16 GB CZI needed)
  - Hybrid provenance embedded in OME-XML (dapi_z) without changing the _MIP.ome.tiff output suffix/glob
affects: [phase-06.1-imaging, future full-series conversion runs, detection-parameter-tuning]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hybrid per-scene projection: anchor(nuclear) channel = single sharpest Z plane, marker channels = full-Z MIP -- ported from czi_hybrid_mip.py into the multi-scene czi_mip.py"
    - "--self-test idiom (seeded np.random.default_rng, assert-based, prints PASSED) matching scripts/build_dapi_reference.py"

key-files:
  created: []
  modified:
    - /home/jflab/Analysis/czi_mip.py

key-decisions:
  - "Marker channels use the FULL read Z stack (not a Z0-2 sub-range like czi_hybrid_mip.py) to capture the observed 2-4 um axial offset between the DAPI-sharp plane and marker signal peak"
  - "Hybrid provenance (chosen dapi_z) embedded as an OME-XML comment rather than a filename change -- keeps the _MIP.ome.tiff suffix/glob (line-276 output-count assertion) unchanged"
  - "_sharpest_plane_from_stack reuses the already-read full-res stack (strided p[::4, ::4] downsample for the focus metric) instead of a second low-res CZI read -- zero extra I/O"

patterns-established:
  - "Pure projection helpers (_sharpest_plane_from_stack, _hybrid_scene_projection) take already-read plane lists and perform no CZI I/O, making them directly unit-testable via --self-test"

requirements-completed: [QUICK-260724-h6y]

coverage:
  - id: D1
    description: "Per-scene hybrid projection: DAPI/anchor channel = single auto-selected sharpest Z plane (var-of-Laplacian); marker channels = full-Z max projection, reusing the already-read stack (no second CZI read)"
    requirement: "QUICK-260724-h6y"
    verification:
      - kind: unit
        ref: "conda run -n braian python /home/jflab/Analysis/czi_mip.py --self-test"
        status: pass
    human_judgment: false
  - id: D2
    description: "Identity thumbnail consumes the single sharpest DAPI plane (out_channels[dapi_idx]), not a DAPI MIP; output filename suffix _MIP.ome.tiff unchanged so the output-count glob keeps matching"
    requirement: "QUICK-260724-h6y"
    verification:
      - kind: unit
        ref: "grep out_channels\\[dapi_idx\\] czi_mip.py && grep _s*_MIP.ome.tiff czi_mip.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Real-CZI end-to-end run (biologically plausible cell counts on the actual wBA1-3 hybrid MIPs) -- not verifiable without the 16 GB CZI per task constraints"
    verification: []
    human_judgment: true
    rationale: "Constraint explicitly forbids running against the real CZI in this quick task; full validation deferred to the next series-conversion run, where visual/quantitative DAPI-blob absence and marker-signal completeness must be confirmed by the operator"

# Metrics
duration: 12min
completed: 2026-07-24
status: complete
---

# Quick Task 260724-h6y: CZI MIP Hybrid DAPI/Marker Projection Summary

**Ported the validated hybrid projection (single sharpest-Z DAPI plane + full-Z marker MIP) from `czi_hybrid_mip.py` into the multi-scene `czi_mip.py`, applied per scene, with a synthetic `--self-test` proving the logic without the 16 GB CZI.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-24T16:20:00Z (approx)
- **Completed:** 2026-07-24T16:32:31Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Replaced the per-channel `np.max` projection (which over-projected DAPI into blobs) with a per-scene hybrid projection: DAPI/anchor channel = single auto-selected sharpest Z plane, marker channels = full-Z max projection
- Added two pure, CZI-I/O-free helpers (`_sharpest_plane_from_stack`, `_hybrid_scene_projection`) that are directly unit-testable
- Per-scene provenance now printed (focus scores per Z, chosen sharpest plane) and embedded in the OME-XML as a comment, without touching the `_MIP.ome.tiff` filename suffix/glob
- Identity thumbnail now consumes the single sharpest DAPI plane instead of a DAPI MIP
- Added `--self-test`, which proves (a) the var-of-Laplacian selector picks the known-sharp plane, (b) anchor output is byte-identical to a single plane while marker output is byte-identical to a full-Z max, and (c) sharpest-plane selection is independent per scene — all without the 16 GB CZI

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace per-channel max-projection with per-scene hybrid projection** - `17e2cd8` (feat)
2. **Task 2: Add --self-test proving the hybrid projection on synthetic arrays** - `3c8e3ad` (test)

_Docs/state metadata commit handled separately by the orchestrator._

## Files Created/Modified
- `czi_mip.py` - Per-scene hybrid DAPI(single sharpest plane)/marker(full-Z MIP) projection, provenance printing, OME-XML provenance comment, `--self-test`

## Decisions Made
- Marker channels project over the FULL read Z stack (all planes), not a Z0-2 sub-range as in `czi_hybrid_mip.py`, to capture the observed 2-4 µm axial offset between the DAPI-sharp plane and marker signal peak (locked decision #2 in the plan).
- Hybrid-projection provenance (chosen `dapi_z`) is embedded as an XML comment inside the OME description rather than encoded in the filename — BioFormats ignores XML comments so the `PhysicalSizeX` round-trip assertion is unaffected, and the `_MIP.ome.tiff` suffix/glob (line-276 output-count assertion) stays unchanged.
- The sharpest-plane focus metric reuses the already-read full-resolution DAPI stack (strided `p[::4, ::4]` downsample for the Laplacian variance calc) rather than issuing a second low-resolution CZI read — zero additional I/O.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' `<done>` criteria were met without needing Rule 1-4 fixes.

## Issues Encountered

None. The `--help` and `--self-test` commands both ran cleanly in the `braian` conda env on first attempt; `_dapi_index` continued to be reused (not hardcoded), and all pre-existing scene-isolation, calibration, and export-integrity assertions (`_preflight_scenes`, `region=` bbox read, `PhysicalSizeX` round-trip, shape==bbox, output-count glob) were left untouched per the plan's explicit "Do NOT touch" list.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`czi_mip.py` is ready to be run against the real 16 GB `wBA1-3` CZI for the next full-series conversion pass. The operator should visually confirm on at least one scene that (1) DAPI nuclei are crisp single-plane segments (no blob merging) and (2) marker channel signal is not clipped/under-projected relative to the prior all-channel-MIP output, since this quick task's verification was deliberately limited to the synthetic `--self-test` (no CZI read attempted, per task constraints). No blockers for the next series-conversion run.

---
*Phase: quick-260724-h6y*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: czi_mip.py
- FOUND: commit 17e2cd8 (Task 1)
- FOUND: commit 3c8e3ad (Task 2)
