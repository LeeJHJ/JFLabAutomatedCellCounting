"""
CZI mosaic → HYBRID OME-TIFF (single-plane nuclei + MIP markers)

Segmentation and marker measurement have opposite Z needs:
  - DAPI nuclei segment cleanest on a SINGLE well-focused plane (a MIP stacks
    axially-adjacent nuclei into blobs -- confirmed on M3 062026, all 6 planes
    near-focus, nucleus separation degrades single→2→3→6-plane).
  - Cytosolic markers (TdTomato) benefit from a small MIP so signal that spans Z
    is captured.

So this builds a composite CYX OME-TIFF where the nuclear channel is one plane and
the marker channels are a max-projection over a Z-range. QuPath/BraiAnDetect then
detects nuclei on the crisp single-plane DAPI and measures Fos/TdT on the MIP'd
marker channels.

Channel read order for this microscope (Zeiss LSM 980 / 20x): aicspylibczi reads
physical data as TdTomato(AF568)=0, Fos(AF488)=1, DAPI=2 -- NOT the metadata order
(see feedback_channel_order). Defaults below follow the physical read order.

Usage:
  conda run -n braian python3 czi_hybrid_mip.py \
      --czi "in.czi" --out "out.ome.tiff" \
      --dapi-plane auto --marker-planes 0-2 --crop 15770x10240
"""

from __future__ import annotations

import argparse
from pathlib import Path

import aicspylibczi
import numpy as np
import tifffile
from scipy import ndimage as ndi


# Physical read order for this acquisition (feedback_channel_order): index -> (name, role)
DEFAULT_CHANNELS = ["AF568-T2", "AF488-T3", "DAPI-T4"]
DEFAULT_DAPI_INDEX = 2
DEFAULT_PIXEL_UM = 0.6905355   # server.json PhysicalSizeX of the registered production MIP


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument("--czi", type=Path, required=True, help="input CZI mosaic")
    p.add_argument("--out", type=Path, required=True, help="output hybrid OME-TIFF")
    p.add_argument("--channels", nargs="+", default=DEFAULT_CHANNELS,
                   help=f"channel names in physical read order (default {DEFAULT_CHANNELS})")
    p.add_argument("--dapi-index", type=int, default=DEFAULT_DAPI_INDEX,
                   help="physical channel index of the nuclear/DAPI channel (default 2)")
    p.add_argument("--dapi-plane", default="auto",
                   help="Z index for the single nuclear plane, or 'auto' for sharpest (default auto)")
    p.add_argument("--marker-planes", default=None,
                   help="Z range 'a-b' (inclusive, 0-based) MIP'd for marker channels; "
                        "default = full stack")
    p.add_argument("--pixel-um", type=float, default=DEFAULT_PIXEL_UM,
                   help=f"pixel size µm/px (default {DEFAULT_PIXEL_UM})")
    p.add_argument("--crop", default=None,
                   help="crop output to WxH from origin (e.g. 15770x10240) to match a "
                        "previously registered image; default = full mosaic")
    return p.parse_args()


def _read_plane(czi: aicspylibczi.CziFile, c: int, z: int, scale: float = 1.0) -> np.ndarray:
    """Stitched single C/Z mosaic plane → (Y, X)."""
    return np.asarray(czi.read_mosaic(C=c, Z=z, scale_factor=scale)).squeeze()


def _sharpest_plane(czi: aicspylibczi.CziFile, c: int, n_z: int) -> int:
    """Pick the Z plane with the highest focus (variance of Laplacian) on a low-res read."""
    scores = []
    for z in range(n_z):
        lo = _read_plane(czi, c, z, scale=0.25).astype(np.float32)
        scores.append(ndi.laplace(lo).var())
    best = int(np.argmax(scores))
    print(f"  focus (var-of-Laplacian) by Z: "
          f"{', '.join(f'Z{z}={s:.3g}' for z, s in enumerate(scores))}")
    print(f"  sharpest nuclear plane -> Z={best}")
    return best


def _parse_range(spec: str, n_z: int) -> list[int]:
    if spec is None:
        return list(range(n_z))
    a, b = spec.split("-")
    lo, hi = int(a), int(b)
    return list(range(lo, hi + 1))


def _build_ome_xml(names: list[str], x: int, y: int, pixel_um: float) -> str:
    chans = "\n".join(
        f'      <Channel ID="Channel:0:{i}" Name="{n}" SamplesPerPixel="1"/>'
        for i, n in enumerate(names)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
  <Image ID="Image:0" Name="{Path.cwd().name}_hybrid">
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
    czi = aicspylibczi.CziFile(str(args.czi))
    dim0 = czi.get_dims_shape()[0]
    n_c = dim0.get("C", (0, 1))[1]
    n_z = dim0.get("Z", (0, 1))[1]
    print(f"CZI: {args.czi.name}  channels={n_c}  z-planes={n_z}")
    if len(args.channels) != n_c:
        raise SystemExit(f"--channels has {len(args.channels)} names but CZI has {n_c} channels")

    dapi_plane = (_sharpest_plane(czi, args.dapi_index, n_z)
                  if args.dapi_plane == "auto" else int(args.dapi_plane))
    marker_zs = _parse_range(args.marker_planes, n_z)
    print(f"Nuclear channel: index {args.dapi_index} ({args.channels[args.dapi_index]}) "
          f"single plane Z={dapi_plane}")
    print(f"Marker channels: MIP over Z={marker_zs}")

    out_planes: list[np.ndarray] = [None] * n_c   # keep physical channel order
    for c in range(n_c):
        if c == args.dapi_index:
            print(f"  C{c} {args.channels[c]} (nuclear): reading single plane Z={dapi_plane}...")
            out_planes[c] = _read_plane(czi, c, dapi_plane).astype(np.uint16)
        else:
            print(f"  C{c} {args.channels[c]} (marker): MIP over {len(marker_zs)} planes...")
            stack = [_read_plane(czi, c, z) for z in marker_zs]
            out_planes[c] = np.max(stack, axis=0).astype(np.uint16)
        p99 = np.percentile(out_planes[c], 99)
        sat = "  *** SATURATED (clipping at 65535) ***" if p99 >= 65535 else ""
        print(f"    {args.channels[c]} shape={out_planes[c].shape} p99={p99:.0f}{sat}")

    img = np.stack(out_planes, axis=0)   # (C, Y, X)

    if args.crop:
        w, h = (int(v) for v in args.crop.lower().split("x"))
        print(f"Cropping {img.shape[2]}x{img.shape[1]} -> {w}x{h} to match registered image")
        img = img[:, :h, :w]

    C, Y, X = img.shape
    ome = _build_ome_xml(args.channels, X, Y, args.pixel_um)
    print(f"Writing {args.out}  ({C}, {Y}, {X}) uint16 ...")
    tifffile.imwrite(str(args.out), img, photometric="minisblack", description=ome.encode())
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
