"""
CZI multi-scene mosaic -> per-scene HYBRID MIP OME-TIFF

Reads a tiled Zeiss CZI mosaic that contains multiple scenes (e.g. one CZI
holding all sections of a series), isolates each scene via its bounding box
(NOT the S= dimension -- mosaic files reject S=, see Common Pitfalls below),
stitches tiles, and writes one CYX OME-TIFF per scene with correct
pixel-size metadata embedded. Per scene, projection is HYBRID: the DAPI/
anchor channel is a single auto-selected sharpest Z plane (var-of-Laplacian
focus metric, applied to the already-read stack -- no second CZI read),
while every marker channel is a full-Z max projection over ALL planes. This
avoids over-projecting nuclei into blobs / phantom-faint doublets (a plain
per-channel MIP over-projects DAPI) while still capturing axially-spread
marker signal (memory `hybrid-imaging-dapi`).

Scene isolation: `get_all_mosaic_scene_bounding_boxes()` returns a
dict[int, BBox] keyed by 0-based scene index, each BBox carrying (x, y, w, h)
in GLOBAL mosaic pixel coordinates. Each scene's bbox is passed verbatim as
`region=` to `read_mosaic()` -- never pass S= alongside region= for a mosaic
file, it raises PylibCZI_CDimCoordinatesOverspecifiedException.

Output filenames are 1-based (`s1..sN`) while the Python scene loop is
0-based (`0..N-1`): label N = scene_idx + 1. No claim is made about
anterior->posterior order -- this script only proves scene->file identity;
AP ordering is handled downstream (DeepSlice, Phase 6).

Usage:
  conda run -n braian python3 czi_mip.py --check-scenes \
      --czi "in.czi"
  conda run -n braian python3 czi_mip.py \
      --czi "in.czi" --outdir "out_dir" \
      --channels "AF568-T2" "AF488-T3" "DAPI-T4" --pixel-um 0.6905355 \
      --animal-prefix wBA1-3
"""

from __future__ import annotations

import argparse
from pathlib import Path

import aicspylibczi
import numpy as np
import tifffile
from PIL import Image
from scipy import ndimage as ndi


DEFAULT_CHANNELS = ["AF568-T2", "AF488-T3", "DAPI-T4"]
DEFAULT_PIXEL_UM = 0.6905355   # server.json PhysicalSizeX of the registered production MIP
DEFAULT_ANIMAL_PREFIX = "wBA1-3"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument("--czi", type=Path, required=False, default=None,
                   help="input multi-scene CZI mosaic (required unless --self-test)")
    p.add_argument("--outdir", type=Path, required=False, default=None,
                   help="output directory for the per-scene MIP OME-TIFFs "
                        "(required unless --check-scenes or --self-test)")
    p.add_argument("--channels", nargs="+", default=DEFAULT_CHANNELS,
                   help=f"channel names in physical read order (default {DEFAULT_CHANNELS})")
    p.add_argument("--pixel-um", type=float, default=DEFAULT_PIXEL_UM,
                   help=f"pixel size um/px (default {DEFAULT_PIXEL_UM})")
    p.add_argument("--animal-prefix", default=DEFAULT_ANIMAL_PREFIX,
                   help=f"filename prefix, output pattern <prefix>_s{{N}}_MIP.ome.tiff (default {DEFAULT_ANIMAL_PREFIX})")
    p.add_argument("--check-scenes", action="store_true",
                   help="run only the pre-flight scene-bbox assertion, then exit (no heavy read)")
    p.add_argument("--self-test", action="store_true",
                   help="run the built-in synthetic hybrid-projection self-test and exit (no --czi needed)")
    args = p.parse_args()
    if not args.self_test:
        if args.czi is None:
            p.error("--czi is required unless --self-test is set")
        if not args.check_scenes and args.outdir is None:
            p.error("--outdir is required unless --check-scenes or --self-test is set")
    return args


def _bboxes_overlap(a, b) -> bool:
    """True if two (x, y, w, h)-style bbox objects overlap in global mosaic coords."""
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or
        a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def _extent(d: dict, key: str, default: tuple[int, int] = (0, 1)) -> int:
    """Extent (end - start) of a get_dims_shape() dimension tuple.

    get_dims_shape() returns (start, end) per dimension; the true count is
    end - start, correct even when start != 0. Taking the tuple end alone
    overcounts whenever a dimension has a nonzero start index (WR-02)."""
    lo, hi = d.get(key, default)
    return hi - lo


def _scene_tile_count(dims_all, scene_keys: list[int], scene_idx: int) -> int:
    """Per-scene mosaic tile count M, derived defensively from get_dims_shape().

    get_dims_shape() is not self-consistent across files: elsewhere in this
    module (and per the docstring's Pitfall 2) it is treated as a single
    aggregate dict (`dims[0]`), yet on a multi-scene mosaic it can instead
    return one dict per scene. Re-indexing the raw scene key into it blindly
    either raises IndexError (aggregate form -> crash mid-series, after the
    scene's MIP is already written) or silently reports M for the wrong scene
    (CR-01). This helper reconciles both forms and NEVER crashes: M is
    diagnostic-only identity metadata, so any ambiguity yields -1 ("unknown").

    Alignment is by POSITION among the sorted scene keys, not the raw key, and
    is trusted only when the list length matches the scene count exactly.
    """
    dicts = dims_all if isinstance(dims_all, list) else [dims_all]
    if len(dicts) == len(scene_keys):
        d = dicts[scene_keys.index(scene_idx)]
    elif len(dicts) == 1:
        d = dicts[0]
    else:
        return -1
    if "M" not in d:
        return -1
    return _extent(d, "M")


def _preflight_scenes(czi: aicspylibczi.CziFile) -> dict:
    """Retrieve per-scene bounding boxes, print identity, assert pairwise non-overlap.

    Returns the bboxes dict (0-based scene index -> BBox), keyed exactly as
    returned by aicspylibczi -- do NOT derive scene count from
    get_dims_shape()[0]['S'] (silently wrong / returns 1 on multi-scene files
    with inconsistent per-scene shape -- Pitfall 2).
    """
    bboxes = czi.get_all_mosaic_scene_bounding_boxes()
    n_scenes = len(bboxes)
    print(f"Pre-flight: {n_scenes} scenes found (get_all_mosaic_scene_bounding_boxes)")
    for scene_idx in sorted(bboxes):
        b = bboxes[scene_idx]
        print(f"  scene_key={scene_idx} (0-based)  bbox=(x={b.x}, y={b.y}, w={b.w}, h={b.h})")

    scene_ids = sorted(bboxes)
    for i in range(len(scene_ids)):
        for j in range(i + 1, len(scene_ids)):
            a, b = bboxes[scene_ids[i]], bboxes[scene_ids[j]]
            if _bboxes_overlap(a, b):
                raise SystemExit(
                    f"FATAL: scene {scene_ids[i]} and scene {scene_ids[j]} bounding boxes "
                    f"overlap -- region-based scene isolation is unsafe on this file"
                )
    if n_scenes < 2:
        raise SystemExit(f"Expected a multi-scene CZI (>=2 scenes), found {n_scenes}")
    print(f"  All {n_scenes} scene bboxes pairwise non-overlapping -- PASS")
    return bboxes


def _dapi_index(names: list[str]) -> int:
    """Physical channel index of the DAPI/nuclear channel (name containing 'DAPI'),
    falling back to the last channel (physical read order puts DAPI last on this rig)."""
    for i, n in enumerate(names):
        if "DAPI" in n.upper():
            return i
    return len(names) - 1


def _sharpest_plane_from_stack(stack: list[np.ndarray]) -> tuple[int, list[float]]:
    """Pick the sharpest Z plane from an already-read (Y, X) plane list.

    Focus metric is variance-of-Laplacian (matches czi_hybrid_mip.py), computed
    on a strided-downsampled float32 copy (p[::4, ::4]) to bound memory/CPU --
    this reuses planes already read for the channel's full stack, so it costs
    NO second CZI read. Returns (best_z, scores) with scores as plain floats
    (JSON/print-friendly, no numpy scalar types)."""
    scores = [float(ndi.laplace(p[::4, ::4].astype(np.float32)).var()) for p in stack]
    best_z = int(np.argmax(scores))
    return best_z, scores


def _hybrid_scene_projection(
    channel_stacks: list[list[np.ndarray]], dapi_idx: int
) -> tuple[list[np.ndarray], int, list[float]]:
    """Pure per-scene hybrid projection -- no CZI read, unit-testable on synthetic arrays.

    `channel_stacks` is one Z-plane list per physical channel (already read).
    The anchor channel (`dapi_idx`) becomes a single auto-selected sharpest
    plane (var-of-Laplacian). Every other (marker) channel becomes a full-Z
    max projection over ALL its planes (deliberately the full stack, not a
    Z0-2 sub-range, to capture the observed 2-4 um axial offset between the
    DAPI-sharp plane and marker signal peak). Physical channel order is
    preserved in `out_channels`."""
    dapi_z, dapi_scores = _sharpest_plane_from_stack(channel_stacks[dapi_idx])
    out_channels: list[np.ndarray] = [None] * len(channel_stacks)
    for c, stack in enumerate(channel_stacks):
        if c == dapi_idx:
            out_channels[c] = stack[dapi_z]
        else:
            out_channels[c] = np.max(stack, axis=0)
    return out_channels, dapi_z, dapi_scores


def _scene_identity_record(scene_idx: int, N: int, bbox, M: int, dims: tuple[int, int]) -> None:
    """Print one identity line carrying BOTH the 0-based scene key and the 1-based
    s{N} label (D-05 off-by-one guard), plus bbox, tile count M, and dims. Makes NO
    anterior->posterior claim (D-03) -- raw scene identity only."""
    h, w = dims
    print(
        f"scene_key={scene_idx} (0-based)  label=s{N} (1-based)  "
        f"bbox=(x={bbox.x}, y={bbox.y}, w={bbox.w}, h={bbox.h})  "
        f"M_tiles={M}  dims=({h}, {w})",
        flush=True,
    )


def _save_identity_thumbnail(dapi_plane: np.ndarray, out_path: Path) -> None:
    """Normalize the already-read DAPI plane (1/99.5 percentile clip -> uint8),
    downsample ~8x by strided slicing, and save as a PNG. Reuses the in-hand
    full-res array -- no fractional read_mosaic(scale_factor<1.0) (Pitfall 4)."""
    lo, hi = np.percentile(dapi_plane, [1, 99.5])
    norm = np.clip((dapi_plane.astype(np.float32) - lo) / (hi - lo + 1e-6), 0, 1)
    thumb = (norm[::8, ::8] * 255).astype(np.uint8)
    Image.fromarray(thumb).save(str(out_path))


def _build_ome_xml(
    names: list[str], x: int, y: int, pixel_um: float, image_name: str, dapi_z: int
) -> str:
    chans = "\n".join(
        f'      <Channel ID="Channel:0:{i}" Name="{n}" SamplesPerPixel="1"/>'
        for i, n in enumerate(names)
    )
    # Hybrid-projection provenance (T-h6y-01): BioFormats ignores XML comments,
    # so this does not affect the PhysicalSizeX round-trip assertion -- it's a
    # human/audit-readable record embedded in the file itself without touching
    # the filename suffix.
    provenance = (
        f"<!-- hybrid-projection: anchor channel single plane Z={dapi_z}; "
        f"marker channels full-Z max-projection -->"
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
  {provenance}
  <Image ID="Image:0" Name="{image_name}">
    <Pixels ID="Pixels:0" Type="uint16" DimensionOrder="XYZCT"
            SizeX="{x}" SizeY="{y}" SizeZ="1" SizeC="{len(names)}" SizeT="1"
            PhysicalSizeX="{pixel_um}" PhysicalSizeXUnit="µm"
            PhysicalSizeY="{pixel_um}" PhysicalSizeYUnit="µm">
{chans}
      <TiffData/>
    </Pixels>
  </Image>
</OME>"""


def _self_test() -> None:
    """Synthetic, assert-based proof of the hybrid projection -- no CZI needed.

    Proves, via the pure helpers (no CZI read anywhere):
    (a) `_sharpest_plane_from_stack` picks the known-sharp plane out of a
        mostly-flat stack.
    (b) `_hybrid_scene_projection` emits the anchor channel as a single plane
        (byte-identical to stack[dapi_z]) and every marker channel as a
        full-Z max projection (byte-identical to np.max(stack, axis=0)).
    (c) Sharpest-plane selection is independent per scene: two scenes with
        the sharp plane at different Z indices yield different dapi_z.
    """
    print("Running --self-test (synthetic hybrid-projection proof, no CZI)...")
    rng = np.random.default_rng(0)

    # (a) Sharpest-plane selection: one high-frequency-noise plane among near-constant planes.
    flat_a = np.full((64, 64), 100.0, dtype=np.float32)
    flat_b = np.full((64, 64), 100.0, dtype=np.float32)
    sharp = rng.normal(loc=100.0, scale=500.0, size=(64, 64)).astype(np.float32)
    known_sharp_z = 1
    dapi_stack_a = [flat_a, sharp, flat_b]
    best_z, scores = _sharpest_plane_from_stack(dapi_stack_a)
    assert best_z == known_sharp_z, (
        f"expected sharpest plane Z={known_sharp_z}, got Z={best_z} (scores={scores})"
    )
    assert len(scores) == len(dapi_stack_a)
    assert all(isinstance(s, float) for s in scores)

    # (b) Hybrid output: anchor = single plane, markers = full-Z max projection.
    dapi_idx = 2   # mirrors this rig's physical read order (DAPI last)
    marker0_stack = [rng.integers(0, 4000, size=(64, 64)).astype(np.uint16) for _ in range(3)]
    marker1_stack = [rng.integers(0, 4000, size=(64, 64)).astype(np.uint16) for _ in range(3)]
    channel_stacks = [marker0_stack, marker1_stack, dapi_stack_a]
    out_channels, dapi_z, dapi_scores_b = _hybrid_scene_projection(channel_stacks, dapi_idx)
    assert dapi_z == known_sharp_z
    assert np.array_equal(out_channels[dapi_idx], dapi_stack_a[dapi_z]), (
        "anchor output must be byte-identical to the single sharpest plane"
    )
    assert np.array_equal(out_channels[0], np.max(marker0_stack, axis=0)), (
        "marker channel 0 output must be byte-identical to the full-Z max projection"
    )
    assert np.array_equal(out_channels[1], np.max(marker1_stack, axis=0)), (
        "marker channel 1 output must be byte-identical to the full-Z max projection"
    )

    # (c) Per-scene independence: a second scene puts the sharp plane at a DIFFERENT Z.
    known_sharp_z_2 = 0
    sharp2 = rng.normal(loc=100.0, scale=500.0, size=(64, 64)).astype(np.float32)
    flat_c = np.full((64, 64), 100.0, dtype=np.float32)
    flat_d = np.full((64, 64), 100.0, dtype=np.float32)
    dapi_stack_b = [sharp2, flat_c, flat_d]
    channel_stacks_2 = [marker0_stack, marker1_stack, dapi_stack_b]
    _, dapi_z_2, _ = _hybrid_scene_projection(channel_stacks_2, dapi_idx)
    assert dapi_z_2 == known_sharp_z_2
    assert dapi_z_2 != dapi_z, (
        f"per-scene independence violated: both scenes picked the same dapi_z={dapi_z}"
    )

    print(
        "\nself-test PASSED: (a) var-of-Laplacian selector picks the known-sharp plane; "
        "(b) hybrid projection emits a single anchor plane (byte-identical to stack[dapi_z]) "
        "and full-Z max-projected markers (byte-identical to np.max(stack, axis=0)); "
        "(c) sharpest-plane selection is independent per scene (different scenes -> "
        f"different dapi_z: {dapi_z} vs {dapi_z_2})."
    )


def main() -> None:
    args = parse_args()

    if args.self_test:
        _self_test()
        return

    print(f"Opening CZI: {args.czi}")
    czi = aicspylibczi.CziFile(str(args.czi))
    dims = czi.get_dims_shape()
    dim0 = dims[0] if isinstance(dims, list) else dims
    n_c = _extent(dim0, "C")
    n_z = _extent(dim0, "Z")
    print(f"  Channels={n_c}  Z-planes={n_z}")

    bboxes = _preflight_scenes(czi)
    if args.check_scenes:
        return

    if len(args.channels) != n_c:
        raise SystemExit(f"--channels has {len(args.channels)} names but CZI has {n_c} channels")

    n_scenes = len(bboxes)
    args.outdir.mkdir(parents=True, exist_ok=True)
    dapi_idx = _dapi_index(args.channels)
    dims_all = czi.get_dims_shape()
    scene_keys = sorted(bboxes)

    for scene_idx in scene_keys:
        b = bboxes[scene_idx]
        N = scene_idx + 1
        region = (b.x, b.y, b.w, b.h)
        print(f"Processing scene {scene_idx} -> s{N}  "
              f"bbox=(x={b.x}, y={b.y}, w={b.w}, h={b.h})")

        print(f"  Generating hybrid projection for scene {scene_idx} (s{N})...")
        channel_stacks = []
        for c in range(n_c):
            print(f"    Channel {c}/{n_c - 1}: reading {n_z} z-planes...", flush=True)
            stack = []
            for z in range(n_z):
                plane = czi.read_mosaic(region=region, C=c, Z=z, scale_factor=1.0)
                stack.append(plane.squeeze())   # remove all size-1 dims -> (Y, X)
                print(f"      z={z} shape={plane.shape} dtype={plane.dtype}", flush=True)
            channel_stacks.append(stack)
            print(f"    Channel {c} read done ({n_z} planes).", flush=True)

        out_channels, dapi_z, dapi_scores = _hybrid_scene_projection(channel_stacks, dapi_idx)
        score_str = ", ".join(f"Z{z}={s:.3g}" for z, s in enumerate(dapi_scores))
        print(f"    anchor channel {dapi_idx} ({args.channels[dapi_idx]}) focus (var-of-Laplacian) "
              f"by Z: {score_str}")
        print(f"    scene {scene_idx} (s{N}): sharpest anchor plane -> Z={dapi_z} "
              f"(markers full-Z max-projected)", flush=True)

        mip = np.stack(out_channels, axis=0)   # (C, Y, X)
        C, Y, X = mip.shape
        if (Y, X) != (b.h, b.w):
            raise SystemExit(
                f"Scene {scene_idx}: MIP shape (Y,X)=({Y},{X}) != scene bbox (h,w)=({b.h},{b.w})"
            )
        print(f"  Scene {scene_idx} (s{N}) hybrid MIP shape: {mip.shape}  dtype: {mip.dtype}")

        # ── Scene-identity artifact (CONV-02, D-01/D-02/D-05) ────────────────
        # Reuse the anchor channel's already-computed single sharpest plane -- no extra CZI read.
        M = _scene_tile_count(dims_all, scene_keys, scene_idx)
        _scene_identity_record(scene_idx, N, b, M, (b.h, b.w))
        thumb_path = args.outdir / f"{args.animal_prefix}_s{N}_identity.png"
        _save_identity_thumbnail(out_channels[dapi_idx], thumb_path)
        print(f"  Identity thumbnail: {thumb_path}")

        image_name = f"{args.animal_prefix}_s{N}"
        ome_xml = _build_ome_xml(args.channels, X, Y, args.pixel_um, image_name, dapi_z)
        out_path = args.outdir / f"{args.animal_prefix}_s{N}_MIP.ome.tiff"
        print(f"  Writing {out_path} ...")
        tifffile.imwrite(
            str(out_path),
            mip,
            photometric="minisblack",
            metadata=None,
            description=ome_xml.encode(),
        )

        with tifffile.TiffFile(str(out_path)) as tf:
            ome_meta = tf.ome_metadata
        expected_tag = f'PhysicalSizeX="{args.pixel_um}"'
        if expected_tag not in ome_meta:
            raise SystemExit(
                f"Scene {scene_idx}: written OME-XML missing {expected_tag!r} -- pixel size did not round-trip"
            )
        print(f"  Done: {out_path}")

    written = sorted(args.outdir.glob(f"{args.animal_prefix}_s*_MIP.ome.tiff"))
    if len(written) != n_scenes:
        raise SystemExit(
            f"FATAL: expected {n_scenes} output MIPs, found {len(written)} in {args.outdir} "
            f"-- silent scene truncation (see Common Pitfalls)"
        )
    print(f"All {n_scenes} scenes converted -> {len(written)} MIP OME-TIFFs written to {args.outdir}")


if __name__ == "__main__":
    main()
