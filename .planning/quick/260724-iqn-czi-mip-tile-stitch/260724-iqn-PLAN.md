---
phase: quick-260724-iqn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - czi_mip.py
autonomous: true
requirements:
  - QUICK-iqn-tile-stitch
must_haves:
  truths:
    - Overlapping multi-scene CZI files convert without cross-scene tissue contamination (each scene assembled from only its own tiles)
    - Non-overlapping files still use region=bbox isolation, byte-identical to prior behavior (regression preserved)
    - "`--isolate region` on an overlapping file still refuses (the existing safety guard stays reachable)"
    - Tile-stitch composes with the existing hybrid projection (single sharpest DAPI/anchor plane + full-Z marker MIP), not replacing it
  artifacts:
    - "czi_mip.py extended with `_stitch_scene_tiles`, `_scene_tile_geometry`, `_read_channel_stacks_tiles`, `_read_channel_stacks_region`, `_resolve_isolation_mode`, and the `--isolate {auto,region,tiles}` flag"
  key_links:
    - "preflight overlap detection -> `_resolve_isolation_mode` -> per-scene read dispatch (region vs tiles)"
    - "`_read_channel_stacks_tiles` -> `_hybrid_scene_projection` (stitched per-(C,Z) planes feed the unchanged hybrid projector)"
---

<objective>
Add an ADDITIVE per-scene tile-stitch isolation path to `czi_mip.py` so tightly-packed multi-scene mosaics — whose per-scene bounding boxes overlap at shared edges — convert without cross-scene tissue contamination. Today the script isolates scenes with `read_mosaic(region=bbox)` and ABORTS when any two scene bboxes overlap; a real 7-scene M3 file overlaps at 11 pairs whose strips contain real tissue (26% / 40% DAPI coverage), so region reads would splice one section's tissue into another's crop. The 5-scene TdT-only file did NOT overlap and converted fine — so region isolation must remain the default for non-overlapping files; tile-stitch is a fallback selected automatically only when bboxes overlap.

Purpose: Convert overlapping multi-scene mosaics safely while leaving the working non-overlapping path untouched.
Output: `czi_mip.py` with a tile-stitch isolation path, an `--isolate {auto,region,tiles}` selector, and synthetic `--self-test` coverage proving cross-scene isolation and hybrid composition.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@czi_mip.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add tile-stitch isolation path + --isolate mode selection to czi_mip.py</name>
  <files>/home/jflab/Analysis/czi_mip.py</files>
  <action>
Add an additive per-scene tile-stitch isolation path. Non-overlapping files must keep using the existing `read_mosaic(region=bbox)` path with byte-identical behavior.

1. Add pure helper `_stitch_scene_tiles(tiles)` where `tiles` is a list of `(x, y, data)` — the tile's global mosaic top-left pixel coords and its squeezed (Y,X) array. Compute the scene's OWN tile-union: `origin_x = min x`, `origin_y = min y`, `ext_x = max(x + data.shape[1]) - origin_x`, `ext_y = max(y + data.shape[0]) - origin_y`. Allocate `np.zeros((ext_y, ext_x), dtype=tiles[0][2].dtype)` and paint each tile at `(y - origin_y, x - origin_x)` using `np.maximum` over the destination slice (document in the docstring: intra-scene ZEN stitch overlap at seams is resolved brighter-wins, which is safe for MIP / cell-counting). Because only this scene's tiles are passed, no neighbor-scene pixel can enter. Pure — no CZI read — so it is unit-testable.

2. Add `_scene_tile_geometry(czi, scene_idx, n_tiles)`: return a list of per-tile `(x, y)` origins by calling `czi.get_mosaic_tile_bounding_box(S=scene_idx, M=m, C=0, Z=0)` for m in range(n_tiles), reading `.x`/`.y`. Use the reference C=0/Z=0 plane (tile layout is invariant across C/Z within a ZEN mosaic scene). Docstring must state it deliberately avoids `get_all_mosaic_tile_bounding_boxes()`, which was observed to hang on the 33 GB file.

3. Add `_read_channel_stacks_tiles(czi, scene_idx, n_tiles, tile_boxes, n_c, n_z)`: for each channel c and each z, read this scene's tiles via `czi.read_image(S=scene_idx, M=m, C=c, Z=z)` (squeeze to (Y,X)), build the `(x, y, data)` list from the cached `tile_boxes`, and stitch via `_stitch_scene_tiles`. Return `channel_stacks` (one list-of-(Y,X)-planes per physical channel) with the SAME structure the existing region loop produces so it drops straight into `_hybrid_scene_projection`. Print per-channel and per-z progress with `flush=True`, matching the existing print idiom.

4. Extract today's region read loop (the `read_mosaic(region=..., C=c, Z=z, scale_factor=1.0)` block, roughly current lines 358-367) into `_read_channel_stacks_region(czi, region, n_c, n_z)` returning the identical `channel_stacks` list. Behavior must be byte-identical to today for region mode.

5. Refactor `_preflight_scenes` to DETECT but not abort on overlap: collect `overlapping_pairs` (list of `(i, j)` scene-key pairs), print each overlapping pair, KEEP the `n_scenes < 2` abort, and change the return to `(bboxes, overlapping_pairs)`. When there is no overlap, still print the existing pairwise-non-overlapping PASS line.

6. Add `_resolve_isolation_mode(requested, overlapping_pairs)` returning `"region"` or `"tiles"`: for `requested == "region"` with a non-empty `overlapping_pairs`, raise `SystemExit` with a FATAL message naming the overlap count and suggesting `--isolate auto` or `--isolate tiles` (this preserves the current safety guard); `requested == "tiles"` -> always `"tiles"`; `requested == "auto"` -> `"tiles"` when any overlap else `"region"`.

7. Add CLI flag `--isolate` to `parse_args` with `choices=["auto", "region", "tiles"]`, `default="auto"`, help text explaining auto = region when scene bboxes are non-overlapping, tiles when they overlap.

8. Wire `main()`: change the preflight call to `bboxes, overlapping_pairs = _preflight_scenes(czi)`; compute `mode = _resolve_isolation_mode(args.isolate, overlapping_pairs)` and print the resolved mode BEFORE the `if args.check_scenes: return` line (so `--check-scenes` now reports the mode instead of aborting on overlap). In the scene loop, compute `n_tiles = _scene_tile_count(dims_all, scene_keys, scene_idx)`; when `mode == "tiles"` and `n_tiles == -1`, raise a clear FATAL (tile-stitch requires a reliable per-scene tile count — do NOT silently proceed). Dispatch the channel read: tiles -> `tile_boxes = _scene_tile_geometry(czi, scene_idx, n_tiles)` then `_read_channel_stacks_tiles(...)`; region -> `_read_channel_stacks_region(region, ...)`. Print `scene {scene_idx} (s{N}) isolated via {mode}`. Feed the resulting `channel_stacks` into `_hybrid_scene_projection` UNCHANGED.

9. Scope the existing bbox shape assertion (roughly current lines 378-381) to region mode ONLY: keep the exact `(Y, X) != (b.h, b.w)` SystemExit for region mode; for tiles mode replace it with an informational print of the stitched `(Y, X)` vs the bbox `(h, w)` (the tile-union geometry legitimately differs from the scene bbox) and continue without aborting.

PRESERVE unchanged (regression surface): `_hybrid_scene_projection` and `_sharpest_plane_from_stack` semantics; pixel-size OME-XML via `_build_ome_xml` plus the `PhysicalSizeX` round-trip assertion; the identity thumbnail fed `out_channels[dapi_idx]`; the final `*_MIP.ome.tiff` glob output-count assertion; the `--channels` physical-read-order contract; the output filename suffix. Add NO new dependencies (numpy / scipy / tifffile / aicspylibczi / PIL only).
  </action>
  <verify>
    <automated>PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 -c "import ast; ast.parse(open('/home/jflab/Analysis/czi_mip.py').read()); print('parse ok')" && /home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --help | grep -q -- --isolate && PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --self-test</automated>
  </verify>
  <done>Script parses; `--help` lists `--isolate {auto,region,tiles}`; the pre-existing hybrid self-test still passes (hybrid path unaffected). Overlapping files auto-select tiles; non-overlapping auto-select region; `--isolate region` on overlap raises FATAL; the region read path is byte-identical to prior behavior.</done>
</task>

<task type="auto">
  <name>Task 2: Extend --self-test with synthetic tile-stitch proofs and verify end-to-end</name>
  <files>/home/jflab/Analysis/czi_mip.py</files>
  <action>
Extend `_self_test()` with tile-stitch coverage. Keep it fully synthetic, fast, and assert-based, matching the existing idiom. Do NOT open or read the 33 GB M3 CZI anywhere in the test — USB reads stall the build loop.

(d) Cross-scene isolation + union sizing + seam resolution via `_stitch_scene_tiles`. Fabricate two scenes of tiles where a neighbor tile's GLOBAL position falls INSIDE the first scene's extent (mirrors the real bug). Example: scene A tiles = `[(0, 0, full((40,40), 10)), (30, 0, full((40,40), 20))]` (they overlap in x=30..40); scene B tile = `[(20, 0, full((40,40), 99))]`. Stitch A from ONLY A's tiles and assert: canvas shape == `(40, 70)` (correct tile-union sizing); value 99 is ABSENT from A's canvas (neighbor scene B excluded — the exact contamination bug this task fixes); the seam pixel (e.g. `canvas_A[0, 35]`) == 20 (np.maximum brighter-wins over the 10/20 overlap). Stitch B alone and assert its canvas is uniformly 99 with shape `(40, 40)`.

(e) Tile-stitch composes with hybrid projection. Build a tiny synthetic scene (2 tiles, 1 marker channel + 1 DAPI/anchor channel, 2 Z-planes) by stitching per (c, z) with `_stitch_scene_tiles`, feed the resulting `channel_stacks` to `_hybrid_scene_projection`, and assert the anchor channel output is byte-identical to the single sharpest stitched plane (`stack[dapi_z]`) and the marker channel output is byte-identical to the full-Z `np.max` of its stitched planes.

Also add a lightweight `_resolve_isolation_mode` check: auto + no overlap -> `"region"`; auto + overlap -> `"tiles"`; tiles -> `"tiles"`; region + overlap raises `SystemExit` (assert via try/except). Update the final `self-test PASSED` summary line to also mention the tile-stitch isolation and hybrid-composition proofs.
  </action>
  <verify>
    <automated>PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --self-test && test "$(find /home/jflab -name 'czi_mip*.py' | wc -l)" -eq 1 && /home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --help | grep -q -- --isolate</automated>
  </verify>
  <done>`--self-test` exits 0 including (d) cross-scene isolation / union sizing / seam and (e) hybrid composition, plus the `_resolve_isolation_mode` cases; exactly one `czi_mip.py` exists on disk (repo-root, no deploy copies); region-mode regression intact.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator CZI file -> conversion script | A multi-scene mosaic crosses into per-scene MIPs; the risk is scientific-data integrity (wrong tissue in a section's crop), not classic untrusted input |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-iqn-01 | Tampering (data integrity) | `read_mosaic(region=bbox)` composite on overlapping scenes | high | mitigate | Tile-stitch path assembles each scene from only its S-scoped tiles; self-test (d) proves a neighbor tile's value never enters the scene canvas |
| T-iqn-02 | Information disclosure (wrong-section splice) | scene->file identity under the new path | medium | mitigate | Per-scene `isolated via {mode}` print + unchanged `s{N}` identity record and thumbnail; auto-mode selection is explicit and logged |
| T-iqn-03 | Denial of service | `get_all_mosaic_tile_bounding_boxes()` hang on 33 GB file | medium | mitigate | Use per-tile `get_mosaic_tile_bounding_box` only; validate logic on synthetic tiles in `--self-test`; any real-file read stays time-boxed and out of the build/test loop |
</threat_model>

<verification>
- `--self-test` passes with all pre-existing hybrid assertions AND the new tile-stitch assertions (d)/(e) and the `_resolve_isolation_mode` cases — run via `PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3` (NOT `conda run`, which buffers child stdout until exit).
- `--help` lists `--isolate {auto,region,tiles}` (default auto).
- No deploy copies: `find /home/jflab -name 'czi_mip*.py'` returns exactly the repo-root path.
- Regression: the non-overlapping region path is untouched; `--isolate region` on an overlapping file still raises FATAL; hybrid projection, pixel-size OME-XML round-trip, identity thumbnail, output-count glob, and `--channels` order contract are all preserved.
- (Out of scope for this task — operator follow-up) The actual M3 33 GB conversion is a SEPARATE background operational run after this self-test passes. If any pre-run API smoke is done, time-box it to open + one `read_image(S=0,M=0,C=0,Z=0)` + one `get_mosaic_tile_bounding_box`; never a full-scene or full-file read.
</verification>

<success_criteria>
- `czi_mip.py` converts overlapping multi-scene mosaics via tile-stitch isolation with zero cross-scene contamination (proven on synthetic tiles).
- Non-overlapping files remain on the region path, unchanged.
- `--isolate {auto,region,tiles}` selects the path; auto = region when non-overlapping, tiles when overlapping; region+overlap refuses.
- Tile-stitch output flows through the unchanged hybrid projection (single sharpest anchor plane + full-Z marker MIP).
- `--self-test` (synthetic, fast, no CZI) is the blocking verification and passes.
</success_criteria>

<output>
Create `.planning/quick/260724-iqn-czi-mip-tile-stitch/260724-iqn-SUMMARY.md` when done.
</output>
