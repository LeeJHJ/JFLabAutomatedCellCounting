---
phase: quick-260724-kmj
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - czi_mip.py
autonomous: true
requirements: [QUICK-kmj-flatfield-blend]
tags: [czi-mip, tile-stitch, flat-field, shading-correction, feather-blend, ome-xml, channel-color]

must_haves:
  truths:
    - "--isolate tiles output is visually seam-free: the per-tile vignetting grid (DAPI column-profile autocorr peak at the ~1382 px tile step) is removed by per-channel flat-field correction + feathered overlap blending"
    - "Flat-field shading SHAPE is estimated from the scene's OWN already-read tiles (per channel, pooled across Z), with no reference image, no new dependency, and no extra CZI reads"
    - "Feathered weighted blending replaces the np.maximum seam resolution in _stitch_scene_tiles; pixels covered by a single tile recover that tile's value exactly on the uint16 round-trip"
    - "OME-XML embeds a per-channel display Color (DAPI blue, AF568/TdTomato red, AF488/Fos green) via OME signed-int32 RGBA packing, so QuPath shows DAPI blue instead of green"
    - "Region path pixel output stays byte-identical; scene isolation, hybrid projection, --isolate semantics (incl. region+overlap SystemExit), pixel-size calibration round-trip, identity thumbnail, --check-scenes, output-count glob, and --channels order contract are all preserved"
    - "Extended --self-test proves (a)-(i) on synthetic data; the 33 GB CZI is never opened in the build/test loop"
  artifacts:
    - "czi_mip.py: new _feather_weights, _estimate_shading_field, _apply_shading, _ome_color helpers"
    - "czi_mip.py: _stitch_scene_tiles rewritten to feathered weighted blending; _read_channel_stacks_tiles restructured to estimate+apply shading before stitching"
    - "czi_mip.py: _build_ome_xml emits a Color attribute per <Channel>; _self_test extended with proofs (f),(g),(h),(i) and proof (d) seam assertion updated to feathered-blend semantics"
  key_links:
    - "_read_channel_stacks_tiles reuses the tiles it already read for shading estimation — the no-extra-CZI-read guarantee"
    - "feather weights strictly > 0 within each tile + round-before-uint16-cast — recovers single-tile core values exactly so existing proof (e) byte-identity holds"
    - "_read_channel_stacks_region + read_mosaic left byte-unchanged — flat-field/feather confined to the tiles path"
---

<objective>
Remove the visible periodic DAPI grid from `czi_mip.py`'s tile-stitch path (`--isolate tiles`) and embed per-channel display colors in the OME-XML.

Two independent defects, both diagnosed this session on the M3 7-scene mosaic output:

1. **Tile grid.** `_stitch_scene_tiles` places raw tiles and resolves overlaps with a hard `np.maximum` — no flat-field/shading correction and no seam blending. Per-tile vignetting (each 1512x1512 tile is brighter at center, ~7-8% dimmer at edges) and hard seams show through as a periodic grid (DAPI column-profile autocorr peaks at exactly 1382 px = the tile step). Fix = retrospective per-channel flat-field correction estimated from the scene's own tiles + feathered overlap blending.
2. **Wrong channel color.** `_build_ome_xml` writes `<Channel ... Name Samples/>` with no `Color`, so QuPath shows DAPI in green. Fix = embed OME signed-int32 RGBA Color per channel.

Purpose: make the tile-stitch output usable for ABBA registration and QuPath review without ZEN's stitcher, while preserving every existing guarantee (scene isolation, hybrid projection, region path byte-identity).
Output: modified `czi_mip.py` with new flat-field/feather/color helpers and an extended synthetic `--self-test`.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@czi_mip.py
@.planning/quick/260724-iqn-czi-mip-tile-stitch/260724-iqn-SUMMARY.md

# Key facts (from CLAUDE.md + measured this session)
# - CPU-only (Intel UHD 630, no CUDA); i9-9900K, 61 GB RAM. No new heavy deps: numpy/scipy/tifffile/aicspylibczi/PIL only.
# - Tiles are 1512x1512 with ~130 px overlap (x-step 1382). scipy.ndimage is already imported as `ndi`.
# - Coordinate units in microns; --channels order contract: "TdTomato-AF568" "Fos-AF488" "DAPI" (physical read order, DAPI last on this rig).
# - Run the self-test with the env python directly (NOT conda run, which buffers):
#     PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 czi_mip.py --self-test
# - The real M3 re-conversion + grid re-measurement is a SEPARATE orchestrator step AFTER this task, NOT part of it.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Flat-field shading correction + feathered overlap blending in the tile-stitch path</name>
  <files>/home/jflab/Analysis/czi_mip.py</files>
  <behavior>
    - Proof (f): a known synthetic radial vignette times "tissue", tiled with overlap, shows measurable boundary-vs-interior modulation when stitched WITHOUT correction; after _estimate_shading_field + _apply_shading + feather stitch, the corrected stitch is uniform within tolerance (boundary/interior ratio -> ~1.0, tile-step column modulation collapses toward noise).
    - Proof (g): two uniform tiles of different values overlapping produce a smooth ramp across the seam (max absolute first-difference across the overlap is small), not a hard brighter-wins step.
    - Proof (h): with feathering active, a neighbor-scene tile placed at a global position inside the first scene's extent still never leaks into that scene's own-tiles canvas (its value is absent).
    - Proof (d) UPDATED: overlap value is strictly between the two tile values (feathered blend), not the old exact brighter-wins value; isolation (neighbor value absent) and union-shape (40,70) assertions kept verbatim.
    - Proofs (a),(b),(c),(e) still pass unchanged (single-tile cores recover exactly; hybrid composition byte-identical).
  </behavior>
  <action>
Modify ONLY the tile-stitch path. Do NOT touch `_read_channel_stacks_region` or `read_mosaic` — those are the region path and must stay byte-identical.

Add `_feather_weights(h, w, margin)`: return an (h, w) float64 weight map that ramps linearly from a small POSITIVE floor at each of the four edges up to 1.0 at `margin` pixels inward, and stays 1.0 in the core. Compute it as the per-pixel minimum of a horizontal edge-ramp and a vertical edge-ramp. Weight must be strictly greater than zero at every pixel of the tile (never exactly 0) so a pixel covered by a single tile recovers that tile's value exactly after normalization. Clamp `margin` to at most min(h,w)//2 so small self-test tiles stay valid.

Rewrite `_stitch_scene_tiles(tiles, feather_margin=<module constant>)`: KEEP the existing canvas sizing (origin = min of this scene's own tile x/y, extent = max of x+w / y+h) and the isolation guarantee verbatim — only this scene's own tiles are ever passed in, so no neighbor pixel can enter. Replace the `np.maximum` seam resolution with weighted accumulation: maintain a float64 weighted-sum canvas and a float64 weight canvas both sized to the union; for each tile compute `_feather_weights` for its shape and add `weight*data` into the weighted-sum canvas and `weight` into the weight canvas at the tile's placement slice. Final canvas = weighted_sum / weight where weight>0 (guard weight==0 -> 0). Cast back to the INPUT tile dtype (`tiles[0][2].dtype`): round to nearest BEFORE the cast for integer dtypes so single-tile cores round-trip exactly; no rounding for float dtypes (proof (e) feeds float32 anchor tiles). Update the docstring: seam resolution is now a feathered weighted-average cross-fade over the overlap (not brighter-wins); isolation and union-sizing guarantees are unchanged. Set the default `feather_margin` module constant sized to roughly the real ~130 px tile overlap, and note it is operator-tunable.

Add `_estimate_shading_field(tile_arrays, smooth_sigma=<default>)`: given a list of same-shape (tileH, tileW) arrays (one channel's tiles pooled across all Z and all M), estimate the illumination SHAPE. For each tile compute robust mean = max(float mean, eps); SKIP near-empty tiles (mean at or below a small floor). Normalize each kept tile by its own robust mean so bright and dim tiles contribute the SHAPE equally. Take the per-pixel MEDIAN across the normalized kept tiles -> raw field. Smooth with `ndi.gaussian_filter` at `smooth_sigma` (proportional to tile size, tunable). Normalize the field to mean 1.0 (guard mean>0). If NO tile qualifies (all near-empty) or the input tiles are not all the same shape, return a uniform ones field (identity -> no correction). Never return NaN or inf.

Add `_apply_shading(tile, field)`: divide `tile.astype(float32)` by `field` (field is guarded > 0), round, clip to the tile dtype's valid range (0..iinfo.max for uint16), cast back to the tile dtype. Vignetting is corrected PER CHANNEL because the field is estimated per channel.

Restructure `_read_channel_stacks_tiles`: for each channel, read all its (z, m) tiles into memory once using the existing per-tile `czi.read_image(S,M,C,Z)` calls — NO extra CZI reads, reuse the tiles you already read. Pool all read tile arrays that match the modal tile shape and call `_estimate_shading_field` once for the channel. Then for each z, apply `_apply_shading` to that z's tiles and pass the corrected (x, y, data) tuples to `_stitch_scene_tiles`. Preserve the per-channel and per-z print idiom and the returned `channel_stacks` structure (list-of-list-of-(Y,X)) exactly so `_hybrid_scene_projection` stays untouched. Peak memory is bounded to one channel's tiles across Z (released before the next channel) — acceptable on 61 GB.

Extend `_self_test` (keep proofs (a),(b),(c),(e) unchanged): update proof (d)'s seam assertion — replace the exact brighter-wins overlap-pixel check with a strictly-between check (overlap value greater than the dimmer tile and less than the brighter tile) and update its message to feathered-blend semantics; KEEP proof (d)'s isolation assertion (neighbor value absent) and the (40,70) union-shape assertion verbatim. Add proof (f) (flat-field flattens a known vignette: build a radial vignette profile times uniform-or-random tissue over a grid of many same-shape overlapping tiles, assert boundary-vs-interior modulation present without correction and boundary/interior ratio -> ~1.0 and tile-step modulation collapsed after _estimate_shading_field + _apply_shading + feather stitch). Add proof (g) (feather no-hard-seam: assert the stitched profile across a synthetic overlap ramps smoothly, max absolute first-difference small). Add proof (h) (isolation under feathering: neighbor-scene tile value absent from the scene's own-tiles canvas). Extend the final self-test PASSED summary line to mention (f),(g),(h).

Do NOT place fenced code blocks in comments that an assertion later negative-greps for; there are none required here.
  </action>
  <verify>
    <automated>PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --self-test</automated>
    <automated>git -C /home/jflab/Analysis diff -- czi_mip.py | grep -A40 'def _read_channel_stacks_region' | grep -v '^+' | grep -v '^-' >/dev/null; git -C /home/jflab/Analysis diff --unified=0 -- czi_mip.py | grep -E '^[+-].*read_mosaic|^[+-].*_read_channel_stacks_region' | grep -vc '^ ' | { read n; [ "$n" -eq 0 ] && echo "REGION PATH UNCHANGED" || echo "REGION PATH TOUCHED: $n"; }</automated>
  </verify>
  <done>--self-test exits 0 with proofs (a)-(h) passing; tile-stitch path applies per-channel flat-field correction + feathered blending; the region path (`_read_channel_stacks_region` / `read_mosaic`) is byte-unchanged in the diff.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: OME-XML per-channel display colors + self-test proof (i) + single-copy verification</name>
  <files>/home/jflab/Analysis/czi_mip.py</files>
  <behavior>
    - Proof (i): _build_ome_xml output contains a Color attribute for every channel; DAPI maps to blue (65535), AF568 to red (-16776961), AF488 to green (16711935).
    - The existing PhysicalSizeX round-trip assertion in main() still passes (Color is an additive attribute, calibration untouched).
  </behavior>
  <action>
Add `_ome_color(name)`: return the OME signed-int32 RGBA packing for a channel name by case-insensitive substring — DAPI -> blue (0,0,255); AF568 or TDT or TDTOMATO -> red (255,0,0); AF488 or FOS -> green (0,255,0); otherwise white (255,255,255). Pack as (r<<24)|(g<<16)|(b<<8)|a with a=255, then convert to a SIGNED int32 (subtract 2**32 when the packed value is at or above 2**31). This yields blue=65535, green=16711935, red=-16776961, white=-1.

In `_build_ome_xml`, add `Color="{_ome_color(n)}"` to each generated `<Channel ...>` element alongside the existing Name and SamplesPerPixel attributes. Leave the PhysicalSizeX/Y calibration attributes, the hybrid-projection provenance comment, the DimensionOrder, and every other part of the XML unchanged so the `PhysicalSizeX="{pixel_um}"` round-trip assertion in `main()` still passes.

Add self-test proof (i) in `_self_test`: call `_build_ome_xml(["AF568-T2", "AF488-T3", "DAPI-T4"], ...)` with placeholder geometry args and assert the returned XML string contains a Color attribute for every channel and that the DAPI channel maps to blue (65535), AF568 to red (-16776961), and AF488 to green (16711935). Extend the final PASSED summary line to mention (i) OME channel colors with DAPI->blue.
  </action>
  <verify>
    <automated>PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --self-test</automated>
    <automated>/home/jflab/miniforge3/envs/braian/bin/python3 /home/jflab/Analysis/czi_mip.py --help >/dev/null && echo HELP_OK</automated>
    <automated>[ "$(find /home/jflab -name 'czi_mip*.py' -not -path '*/miniforge3/*' | wc -l)" = "1" ] && echo SINGLE_COPY_OK</automated>
  </verify>
  <done>--self-test exits 0 with proofs (a)-(i) passing; every `<Channel>` in the OME-XML carries a display Color with DAPI mapped to blue; `--help` runs; exactly one `czi_mip.py` exists (repo root, no deploy copies).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator CZI + CLI params -> local processing | operator-supplied 33 GB mosaic and channel/pixel args are the only inputs; no network, no untrusted external input |
| float math -> uint16 output | numerical guards (divide-by-zero, NaN, clip, round) protect the scientific output's integrity |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-kmj-01 | Tampering | _estimate_shading_field / _apply_shading | medium | mitigate | Guard robust-mean and field-mean divisors with eps; skip near-empty tiles; fall back to a uniform ones field when no tile qualifies or shapes differ; never emit NaN/inf — a bad field must never silently corrupt pixel values |
| T-kmj-02 | Tampering | _stitch_scene_tiles feather cast | medium | mitigate | Weight canvas guarded (weight==0 -> 0); round + clip to dtype range before uint16 cast so single-tile cores round-trip exactly and no overflow wraps |
| T-kmj-03 | Denial of Service | _read_channel_stacks_tiles memory | low | accept | Holding one channel's tiles across Z (~2.7 GB) is bounded and released between channels; well within 61 GB RAM |
| T-kmj-SC | Tampering | dependencies | low | accept | No package installs — numpy/scipy/tifffile/aicspylibczi/PIL only, all already present; supply-chain surface unchanged |
</threat_model>

<verification>
- `--self-test` runs the full synthetic proof set (a)-(i) with the env python directly; NO CZI is opened.
- Region path regression guard: `git diff` on `czi_mip.py` shows no change to `_read_channel_stacks_region` or any `read_mosaic` call.
- `--help` still lists all flags (`--isolate {auto,region,tiles}`, `--check-scenes`, `--self-test`).
- Exactly one `czi_mip.py` on disk under /home/jflab (excluding miniforge3), at repo root.
- The real M3 re-conversion + grid re-measurement (autocorr peak at 1382 must drop) is a SEPARATE orchestrator step AFTER this task.
</verification>

<success_criteria>
- Tile-stitch path (`--isolate tiles`) applies per-channel retrospective flat-field correction (estimated from the scene's own already-read tiles) + feathered overlap blending, removing the periodic grid — proven synthetically by proof (f) (vignette flattened) and proof (g) (no hard seam).
- Scene isolation (proof (h)/(d)), hybrid projection composition (proof (e)), single-tile exact recovery (proofs (a)-(e)), and the region path (byte-unchanged) are all preserved.
- OME-XML `<Channel>` elements carry a display Color; DAPI is blue, AF568/TdTomato red, AF488/Fos green (proof (i)); pixel-size calibration still round-trips.
- No new dependencies; CPU-only; single repo-root `czi_mip.py`.
</success_criteria>

<output>
Create `.planning/quick/260724-kmj-flatfield-blend/260724-kmj-SUMMARY.md` when done.
</output>
