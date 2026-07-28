"""Legacy CZI mosaic -> MIP OME-TIFF converter.

This script is retained for backward compatibility. Prefer
`scripts/czi_hybrid_mip.py` for current production usage.

Usage:
  conda run -n braian python3 scripts/legacy/czi_mip.py \
      --czi data/raw/M3_Hippocampus_20x_062026.czi \
      --out results/M3_20x_MIP.ome.tiff \
      --channels "DAPI" "Fos-AF488" "TdTomato-AF568"
"""

from __future__ import annotations

import argparse
from pathlib import Path

import aicspylibczi
import numpy as np
import tifffile

DEFAULT_PIXEL_SIZE_UM = 0.69
DEFAULT_CHANNELS = ["DAPI", "Fos-AF488", "TdTomato-AF568"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    parser.add_argument("--czi", type=Path, required=True, help="Input CZI file path")
    parser.add_argument("--out", type=Path, required=True, help="Output OME-TIFF path")
    parser.add_argument(
        "--channels",
        nargs="+",
        default=DEFAULT_CHANNELS,
        help=f"Channel names in physical read order (default: {DEFAULT_CHANNELS})",
    )
    parser.add_argument(
        "--pixel-um",
        type=float,
        default=DEFAULT_PIXEL_SIZE_UM,
        help=f"Pixel size in microns per pixel (default: {DEFAULT_PIXEL_SIZE_UM})",
    )
    return parser.parse_args()


def _build_ome_xml(channel_names: list[str], x: int, y: int, pixel_um: float) -> str:
    channels_xml = "\n".join(
        f'      <Channel ID="Channel:0:{idx}" Name="{name}" SamplesPerPixel="1"/>'
        for idx, name in enumerate(channel_names)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06
       http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
  <Image ID="Image:0" Name="{Path(__file__).stem}">
    <Pixels ID="Pixels:0"
            Type="uint16"
            DimensionOrder="XYZCT"
            SizeX="{x}" SizeY="{y}" SizeZ="1" SizeC="{len(channel_names)}" SizeT="1"
            PhysicalSizeX="{pixel_um}" PhysicalSizeXUnit="µm"
            PhysicalSizeY="{pixel_um}" PhysicalSizeYUnit="µm">
{channels_xml}
      <TiffData/>
    </Pixels>
  </Image>
</OME>"""


def main() -> None:
    args = parse_args()
    if not args.czi.exists():
        raise SystemExit(f"Input CZI not found: {args.czi}")

    print("Opening CZI...")
    czi = aicspylibczi.CziFile(str(args.czi))
    dims = czi.get_dims_shape()
    print(f"  Dims shape : {dims}")
    print(f"  Is mosaic  : {czi.is_mosaic()}")

    dim0 = dims[0] if isinstance(dims, list) else dims
    n_c = dim0.get("C", (0, 1))[1]
    n_z = dim0.get("Z", (0, 1))[1]
    n_s = dim0.get("S", (0, 1))[1]
    print(f"  Scenes={n_s}  Channels={n_c}  Z-planes={n_z}")
    if len(args.channels) != n_c:
        raise SystemExit(f"--channels has {len(args.channels)} names but CZI has {n_c} channels")

    print("Generating MIP (this may take several minutes)...")
    mip_channels = []
    for c in range(n_c):
        print(f"  Channel {c}/{n_c - 1}: reading {n_z} z-planes...", flush=True)
        stack = []
        for z in range(n_z):
            plane = czi.read_mosaic(C=c, Z=z, scale_factor=1.0)
            stack.append(np.asarray(plane).squeeze())
            print(f"    z={z} shape={plane.shape} dtype={plane.dtype}", flush=True)
        mip_c = np.max(stack, axis=0)
        mip_channels.append(mip_c)
        print(f"  Channel {c} MIP done. Shape: {mip_c.shape}", flush=True)

    mip = np.stack(mip_channels, axis=0)
    print(f"Final MIP shape: {mip.shape}  dtype: {mip.dtype}")
    _, y, x = mip.shape
    ome_xml = _build_ome_xml(args.channels, x, y, args.pixel_um)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    print(f"Writing {args.out} ...")
    tifffile.imwrite(
        str(args.out),
        mip,
        photometric="minisblack",
        metadata=None,
        description=ome_xml.encode(),
    )
    print("Done.")
    print(f"Output: {args.out}")


if __name__ == "__main__":
    main()
