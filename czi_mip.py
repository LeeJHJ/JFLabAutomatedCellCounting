"""
CZI multi-scene mosaic -> per-scene MIP OME-TIFF

Reads a tiled Zeiss CZI mosaic that contains multiple scenes (e.g. one CZI
holding all sections of a series), isolates each scene via its bounding box
(NOT the S= dimension -- mosaic files reject S=, see Common Pitfalls below),
stitches tiles, max-projects over Z per channel, and writes one CYX OME-TIFF
per scene with correct pixel-size metadata embedded.

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


DEFAULT_CHANNELS = ["AF568-T2", "AF488-T3", "DAPI-T4"]
DEFAULT_PIXEL_UM = 0.6905355   # server.json PhysicalSizeX of the registered production MIP
DEFAULT_ANIMAL_PREFIX = "wBA1-3"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument("--czi", type=Path, required=True, help="input multi-scene CZI mosaic")
    p.add_argument("--outdir", type=Path, required=False, default=None,
                   help="output directory for the per-scene MIP OME-TIFFs (required unless --check-scenes)")
    p.add_argument("--channels", nargs="+", default=DEFAULT_CHANNELS,
                   help=f"channel names in physical read order (default {DEFAULT_CHANNELS})")
    p.add_argument("--pixel-um", type=float, default=DEFAULT_PIXEL_UM,
                   help=f"pixel size um/px (default {DEFAULT_PIXEL_UM})")
    p.add_argument("--animal-prefix", default=DEFAULT_ANIMAL_PREFIX,
                   help=f"filename prefix, output pattern <prefix>_s{{N}}_MIP.ome.tiff (default {DEFAULT_ANIMAL_PREFIX})")
    p.add_argument("--check-scenes", action="store_true",
                   help="run only the pre-flight scene-bbox assertion, then exit (no heavy read)")
    args = p.parse_args()
    if not args.check_scenes and args.outdir is None:
        p.error("--outdir is required unless --check-scenes is set")
    return args


def _bboxes_overlap(a, b) -> bool:
    """True if two (x, y, w, h)-style bbox objects overlap in global mosaic coords."""
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or
        a.y + a.h <= b.y or b.y + b.h <= a.y
    )


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
    assert n_scenes >= 2, f"Expected a multi-scene CZI (>=2 scenes), found {n_scenes}"
    print(f"  All {n_scenes} scene bboxes pairwise non-overlapping -- PASS")
    return bboxes


def _dapi_index(names: list[str]) -> int:
    """Physical channel index of the DAPI/nuclear channel (name containing 'DAPI'),
    falling back to the last channel (physical read order puts DAPI last on this rig)."""
    for i, n in enumerate(names):
        if "DAPI" in n.upper():
            return i
    return len(names) - 1


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


def _build_ome_xml(names: list[str], x: int, y: int, pixel_um: float, image_name: str) -> str:
    chans = "\n".join(
        f'      <Channel ID="Channel:0:{i}" Name="{n}" SamplesPerPixel="1"/>'
        for i, n in enumerate(names)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
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


def main() -> None:
    args = parse_args()

    print(f"Opening CZI: {args.czi}")
    czi = aicspylibczi.CziFile(str(args.czi))
    dims = czi.get_dims_shape()
    dim0 = dims[0] if isinstance(dims, list) else dims
    n_c = dim0.get("C", (0, 1))[1]
    n_z = dim0.get("Z", (0, 1))[1]
    print(f"  Channels={n_c}  Z-planes={n_z}")

    bboxes = _preflight_scenes(czi)
    if args.check_scenes:
        return

    if len(args.channels) != n_c:
        raise SystemExit(f"--channels has {len(args.channels)} names but CZI has {n_c} channels")

    n_scenes = len(bboxes)
    args.outdir.mkdir(parents=True, exist_ok=True)
    dapi_idx = _dapi_index(args.channels)
    dims_by_scene = czi.get_dims_shape()

    for scene_idx in sorted(bboxes):
        b = bboxes[scene_idx]
        N = scene_idx + 1
        region = (b.x, b.y, b.w, b.h)
        print(f"Processing scene {scene_idx} -> s{N}  "
              f"bbox=(x={b.x}, y={b.y}, w={b.w}, h={b.h})")

        print(f"  Generating MIP for scene {scene_idx} (s{N})...")
        mip_channels = []
        for c in range(n_c):
            print(f"    Channel {c}/{n_c - 1}: reading {n_z} z-planes...", flush=True)
            stack = []
            for z in range(n_z):
                plane = czi.read_mosaic(region=region, C=c, Z=z, scale_factor=1.0)
                stack.append(plane.squeeze())   # remove all size-1 dims -> (Y, X)
                print(f"      z={z} shape={plane.shape} dtype={plane.dtype}", flush=True)
            mip_c = np.max(stack, axis=0)   # (Y, X)
            mip_channels.append(mip_c)
            print(f"    Channel {c} MIP done. Shape: {mip_c.shape}", flush=True)

        mip = np.stack(mip_channels, axis=0)   # (C, Y, X)
        C, Y, X = mip.shape
        assert (Y, X) == (b.h, b.w), (
            f"Scene {scene_idx}: MIP shape (Y,X)=({Y},{X}) != scene bbox (h,w)=({b.h},{b.w})"
        )
        print(f"  Scene {scene_idx} (s{N}) MIP shape: {mip.shape}  dtype: {mip.dtype}")

        # ── Scene-identity artifact (CONV-02, D-01/D-02/D-05) ────────────────
        # Reuse the DAPI channel's already-computed MIP plane -- no extra CZI read.
        M = dims_by_scene[scene_idx]["M"][1]
        _scene_identity_record(scene_idx, N, b, M, (b.h, b.w))
        thumb_path = args.outdir / f"{args.animal_prefix}_s{N}_identity.png"
        _save_identity_thumbnail(mip_channels[dapi_idx], thumb_path)
        print(f"  Identity thumbnail: {thumb_path}")

        image_name = f"{args.animal_prefix}_s{N}"
        ome_xml = _build_ome_xml(args.channels, X, Y, args.pixel_um, image_name)
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
        assert expected_tag in ome_meta, (
            f"Scene {scene_idx}: written OME-XML missing {expected_tag!r} -- pixel size did not round-trip"
        )
        print(f"  Done: {out_path}")

    written = sorted(args.outdir.glob(f"{args.animal_prefix}_s*_MIP.ome.tiff"))
    assert len(written) == n_scenes, (
        f"FATAL: expected {n_scenes} output MIPs, found {len(written)} in {args.outdir} "
        f"-- silent scene truncation (see Common Pitfalls)"
    )
    print(f"All {n_scenes} scenes converted -> {len(written)} MIP OME-TIFFs written to {args.outdir}")


if __name__ == "__main__":
    main()
