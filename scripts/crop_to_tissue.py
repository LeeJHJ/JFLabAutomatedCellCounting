"""
DAPI tissue-mask auto-crop CLI
Reads a multichannel MIP OME-TIFF, thresholds the DAPI channel (Otsu) into a
binary tissue mask, cleans the mask (morphological close + fill holes + small
object removal), computes the tissue bounding box plus a margin, crops ALL
channels to that box, and writes a cropped OME-TIFF that preserves the
input's micron pixel calibration and channel names/order.

CPU-only. Runs in the `braian` conda env.

Usage:
  conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py \\
      "/path/to/M3_20x_MIP.ome.tiff" -o "/path/to/M3_20x_MIP_cropped.ome.tiff"

  # Synthetic self-test (no large files needed):
  conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_fill_holes
from skimage.filters import threshold_otsu
from skimage.morphology import closing, disk, remove_small_objects


# ── Private helpers ──────────────────────────────────────────────────────────

def _read_mip(path: Path) -> tuple[np.ndarray, list[str], float, str]:
    """Load a (C, Y, X) uint16 MIP OME-TIFF and its OME-XML calibration."""
    arr = tifffile.imread(path)
    arr = np.asarray(arr)
    # Squeeze any singleton Z/T axes down to (C, Y, X).
    while arr.ndim > 3:
        singleton_axes = [i for i, s in enumerate(arr.shape) if s == 1]
        if not singleton_axes:
            break
        arr = np.squeeze(arr, axis=singleton_axes[0])
    if arr.ndim != 3:
        raise ValueError(f"Expected a (C, Y, X) array after squeeze, got shape {arr.shape}")

    ome_xml = tifffile.TiffFile(path).ome_metadata or ""
    channel_names = re.findall(r'<Channel[^>]*\bName="([^"]+)"', ome_xml)
    if not channel_names:
        # Fall back to generic names if the OME-XML has no Channel Name attrs.
        channel_names = [f"Channel:{i}" for i in range(arr.shape[0])]

    px_matches = re.findall(r'PhysicalSizeX="([^"]+)"', ome_xml)
    pixel_um = float(px_matches[0]) if px_matches else 1.0

    unit_matches = re.findall(r'PhysicalSizeXUnit="([^"]+)"', ome_xml)
    unit = unit_matches[0] if unit_matches else "µm"

    return arr, channel_names, pixel_um, unit


def _select_dapi_index(channel_names: list[str], override: str | None) -> int:
    """Resolve the DAPI channel index by name (case-insensitive) or override."""
    if override is None:
        for i, name in enumerate(channel_names):
            if "dapi" in name.lower():
                return i
        raise ValueError(
            f"No channel name contains 'DAPI' (case-insensitive). "
            f"Available channel names: {channel_names}. "
            f"Use --dapi-channel to specify a name or index explicitly."
        )

    if override.isdigit():
        idx = int(override)
        if not (0 <= idx < len(channel_names)):
            raise ValueError(
                f"--dapi-channel index {idx} out of range for {len(channel_names)} channels: {channel_names}"
            )
        return idx

    override_lower = override.lower()
    for i, name in enumerate(channel_names):
        if override_lower in name.lower():
            return i
    raise ValueError(
        f"--dapi-channel '{override}' matched no channel name. "
        f"Available channel names: {channel_names}"
    )


def _compute_tissue_mask(
    dapi: np.ndarray, downsample: int, min_object_frac: float
) -> tuple[np.ndarray, int]:
    """Otsu-threshold + clean a (downsampled) DAPI plane into a tissue mask."""
    factor = downsample
    if factor <= 0:
        larger_axis = max(dapi.shape)
        factor = max(1, round(larger_axis / 2048))

    small = dapi[::factor, ::factor]

    threshold = threshold_otsu(small)
    mask = small > threshold
    mask = closing(mask, footprint=disk(2))
    mask = binary_fill_holes(mask)
    # remove_small_objects (skimage >= 0.26) removes objects with area <=
    # max_size; translate the "remove strictly smaller than min_size" intent
    # by using max_size = min_size - 1.
    min_size = max(1, int(min_object_frac * mask.size))
    mask = remove_small_objects(mask, max_size=min_size - 1)

    return mask, factor


def _tissue_bbox(
    mask: np.ndarray, factor: int, full_shape: tuple[int, int], margin_percent: float
) -> tuple[int, int, int, int]:
    """Compute full-resolution (y0, y1, x0, x1) bbox from a downsampled mask."""
    if not mask.any():
        raise ValueError("Tissue mask is empty — no tissue detected. Check DAPI channel/threshold.")

    full_y, full_x = full_shape
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    y0_ds, y1_ds = np.where(rows)[0][[0, -1]]
    x0_ds, x1_ds = np.where(cols)[0][[0, -1]]

    # Scale downsampled indices back to full resolution. y1/x1 are inclusive
    # indices in the downsampled mask, so the exclusive full-res end is
    # (index + 1) * factor, clamped to the full image extent.
    y0 = int(y0_ds) * factor
    y1 = min(full_y, (int(y1_ds) + 1) * factor)
    x0 = int(x0_ds) * factor
    x1 = min(full_x, (int(x1_ds) + 1) * factor)

    extent_y = y1 - y0
    extent_x = x1 - x0
    margin_y = int(round(margin_percent / 100.0 * extent_y))
    margin_x = int(round(margin_percent / 100.0 * extent_x))

    y0 = max(0, y0 - margin_y)
    y1 = min(full_y, y1 + margin_y)
    x0 = max(0, x0 - margin_x)
    x1 = min(full_x, x1 + margin_x)

    return y0, y1, x0, x1


def _build_ome_xml(
    C: int, Y: int, X: int, channel_names: list[str], pixel_um: float, unit: str
) -> str:
    """Build a minimal OME-XML string, mirroring czi_mip.py's structure."""
    channel_elems = "\n".join(
        f'      <Channel ID="Channel:0:{i}" Name="{name}" SamplesPerPixel="1"/>'
        for i, name in enumerate(channel_names)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06
       http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
  <Image ID="Image:0" Name="cropped">
    <Pixels ID="Pixels:0"
            Type="uint16"
            DimensionOrder="XYZCT"
            SizeX="{X}" SizeY="{Y}" SizeZ="1" SizeC="{C}" SizeT="1"
            PhysicalSizeX="{pixel_um}" PhysicalSizeXUnit="{unit}"
            PhysicalSizeY="{pixel_um}" PhysicalSizeYUnit="{unit}">
{channel_elems}
      <TiffData/>
    </Pixels>
  </Image>
</OME>"""


def _self_test() -> None:
    """Synthetic in-memory exercise of every helper. Exits nonzero on failure."""
    print("Running self-test...")

    # ── Synthetic (C=3, Y, X) uint16 array, DAPI at index 2 (mirrors real
    # AF568/AF488/DAPI ordering — DAPI is NOT index 0). ──
    Y, X = 400, 600
    channel_names = ["AF568-T2", "AF488-T3", "DAPI-T4"]
    arr = np.zeros((3, Y, X), dtype=np.uint16)

    # Known bright rectangular blob for the DAPI channel.
    blob_y0, blob_y1, blob_x0, blob_x1 = 100, 300, 150, 450
    arr[2, blob_y0:blob_y1, blob_x0:blob_x1] = 4000

    # 1. DAPI selection by name (case-insensitive substring), and by index.
    idx_auto = _select_dapi_index(channel_names, None)
    assert idx_auto == 2, f"expected auto DAPI index 2, got {idx_auto}"
    idx_by_index_str = _select_dapi_index(channel_names, "2")
    assert idx_by_index_str == 2
    idx_by_name = _select_dapi_index(channel_names, "DAPI")
    assert idx_by_name == 2
    idx_by_lower_substr = _select_dapi_index(channel_names, "dapi-t4")
    assert idx_by_lower_substr == 2
    print("  PASS: DAPI selection by name/index (index 2, not 0)")

    # 2. _compute_tissue_mask recovers the blob; _tissue_bbox returns its extent.
    dapi_plane = arr[idx_auto]
    mask, factor = _compute_tissue_mask(dapi_plane, downsample=1, min_object_frac=0.0001)
    assert mask.any(), "mask should not be empty"

    y0, y1, x0, x1 = _tissue_bbox(mask, factor, dapi_plane.shape, margin_percent=0.0)
    # Allow small tolerance from morphological closing/fill.
    assert abs(y0 - blob_y0) <= 3, (y0, blob_y0)
    assert abs(y1 - blob_y1) <= 3, (y1, blob_y1)
    assert abs(x0 - blob_x0) <= 3, (x0, blob_x0)
    assert abs(x1 - blob_x1) <= 3, (x1, blob_x1)
    print(f"  PASS: tissue mask + bbox recovery ({(y0, y1, x0, x1)} ~ {(blob_y0, blob_y1, blob_x0, blob_x1)})")

    # 3. Margin expands the bbox but clamps at image edges — test a blob flush
    # against an edge.
    edge_arr = np.zeros((Y, X), dtype=np.uint16)
    edge_arr[0:50, 0:50] = 4000  # flush against top-left corner
    edge_mask, edge_factor = _compute_tissue_mask(edge_arr, downsample=1, min_object_frac=0.0001)
    ey0, ey1, ex0, ex1 = _tissue_bbox(edge_mask, edge_factor, edge_arr.shape, margin_percent=50.0)
    assert ey0 >= 0 and ex0 >= 0, (ey0, ex0)
    assert ey1 <= Y and ex1 <= X, (ey1, ex1)
    assert ey0 == 0 and ex0 == 0, "margin should clamp to 0 at the top-left edge"
    print("  PASS: margin expansion clamps at image edges (no negative / out-of-bound index)")

    # Also confirm margin actually expands away from the far edge (non-edge side).
    y0_nomargin, y1_nomargin, x0_nomargin, x1_nomargin = _tissue_bbox(
        mask, factor, dapi_plane.shape, margin_percent=0.0
    )
    y0_margin, y1_margin, x0_margin, x1_margin = _tissue_bbox(
        mask, factor, dapi_plane.shape, margin_percent=10.0
    )
    assert y0_margin <= y0_nomargin and y1_margin >= y1_nomargin
    assert x0_margin <= x0_nomargin and x1_margin >= x1_nomargin
    assert (y0_margin, y1_margin, x0_margin, x1_margin) != (y0_nomargin, y1_nomargin, x0_nomargin, x1_nomargin)
    print("  PASS: margin expands bbox when not clamped by an edge")

    # 4. Cropped array shape/dtype/channel-count preserved.
    cy0, cy1, cx0, cx1 = _tissue_bbox(mask, factor, dapi_plane.shape, margin_percent=5.0)
    cropped = arr[:, cy0:cy1, cx0:cx1]
    assert cropped.shape == (3, cy1 - cy0, cx1 - cx0)
    assert cropped.dtype == np.uint16
    assert cropped.shape[0] == arr.shape[0]
    print("  PASS: cropped array shape/dtype/channel-count preserved")

    # 5. OME-XML round-trip preserves pixel size and channel names verbatim.
    pixel_um = 0.6905355
    unit = "µm"
    xml = _build_ome_xml(3, cy1 - cy0, cx1 - cx0, channel_names, pixel_um, unit)
    px_out = re.findall(r'PhysicalSizeX="([^"]+)"', xml)
    unit_out = re.findall(r'PhysicalSizeXUnit="([^"]+)"', xml)
    names_out = re.findall(r'<Channel[^>]*\bName="([^"]+)"', xml)
    assert px_out and float(px_out[0]) == pixel_um, (px_out, pixel_um)
    assert unit_out and unit_out[0] == unit, (unit_out, unit)
    assert names_out == channel_names, (names_out, channel_names)
    print("  PASS: OME-XML round-trip preserves pixel size, unit, and channel names verbatim")

    print("SELF-TEST PASS")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("input", type=Path, nargs="?", help="Input MIP OME-TIFF path")
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output cropped OME-TIFF path (default: <input_stem>_cropped.ome.tiff beside input)",
    )
    parser.add_argument(
        "--dapi-channel", type=str, default=None,
        help="DAPI channel name substring (case-insensitive) or integer index. "
             "Default: auto-match the first channel whose name contains 'DAPI'.",
    )
    parser.add_argument(
        "--margin-percent", type=float, default=5.0,
        help="Margin added on each side of the tissue bbox, as a percentage of the bbox extent per axis (default: 5.0)",
    )
    parser.add_argument(
        "--mask-downsample", type=int, default=0,
        help="Integer downsample factor for mask computation (default: 0 = auto, "
             "chosen so the DAPI channel's larger axis is approx 2048 px)",
    )
    parser.add_argument(
        "--min-object-frac", type=float, default=0.001,
        help="Remove connected components smaller than this fraction of the (downsampled) "
             "frame area before taking the bbox (default: 0.001)",
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="Run the synthetic self-test (no input file needed) and exit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.self_test:
        _self_test()
        return

    if args.input is None:
        print("ERROR: input path is required (unless --self-test)", file=sys.stderr)
        sys.exit(2)

    output = args.output
    if output is None:
        output = args.input.with_name(args.input.stem.replace(".ome", "") + "_cropped.ome.tiff")

    # Step 1: read the MIP.
    print("Step 1: Reading MIP...")
    arr, channel_names, pixel_um, unit = _read_mip(args.input)
    C, Y, X = arr.shape
    print(f"  Original dims (C,Y,X): ({C}, {Y}, {X})  dtype: {arr.dtype}")
    print(f"  Channel names: {channel_names}")
    print(f"  Pixel size: {pixel_um} {unit}")

    # Step 2: select the DAPI channel.
    print("Step 2: Selecting DAPI channel...")
    dapi_idx = _select_dapi_index(channel_names, args.dapi_channel)
    print(f"  Selected channel index {dapi_idx} ('{channel_names[dapi_idx]}')")

    # Step 3: compute the mask and bbox.
    print("Step 3: Computing tissue mask and bounding box...")
    dapi_plane = arr[dapi_idx]
    mask, factor = _compute_tissue_mask(dapi_plane, args.mask_downsample, args.min_object_frac)
    print(f"  Downsample factor used: {factor}")
    y0, y1, x0, x1 = _tissue_bbox(mask, factor, dapi_plane.shape, args.margin_percent)
    print(f"  Tissue bbox (y0,y1,x0,x1): ({y0}, {y1}, {x0}, {x1})")

    # Step 4: crop all channels.
    print("Step 4: Cropping all channels...")
    cropped = arr[:, y0:y1, x0:x1]
    print(f"  Cropped dims (C,Y,X): {cropped.shape}  dtype: {cropped.dtype}")

    # Step 5: write the cropped OME-TIFF.
    print("Step 5: Writing cropped OME-TIFF...")
    ome_xml = _build_ome_xml(cropped.shape[0], cropped.shape[1], cropped.shape[2], channel_names, pixel_um, unit)
    tifffile.imwrite(
        output,
        cropped,
        photometric="minisblack",
        metadata=None,
        description=ome_xml.encode(),
    )

    # Stats block.
    bbox_area = (y1 - y0) * (x1 - x0)
    cropped_frame_area = cropped.shape[1] * cropped.shape[2]
    bbox_fill_fraction = bbox_area / cropped_frame_area if cropped_frame_area else 0.0
    # Foreground-pixel coverage of the cropped frame (mask-true pixels at
    # downsampled resolution, normalized against the downsampled crop area).
    mask_y0, mask_y1 = y0 // factor, min(mask.shape[0], -(-y1 // factor))
    mask_x0, mask_x1 = x0 // factor, min(mask.shape[1], -(-x1 // factor))
    cropped_mask_region = mask[mask_y0:mask_y1, mask_x0:mask_x1]
    fg_coverage = float(cropped_mask_region.mean()) if cropped_mask_region.size else 0.0

    print("Crop stats:")
    print(f"  Original (Y,X): ({Y}, {X})")
    print(f"  Tissue bbox (y0,y1,x0,x1): ({y0}, {y1}, {x0}, {x1})")
    print(f"  Cropped (Y,X): ({cropped.shape[1]}, {cropped.shape[2]})")
    print(f"  Tissue-fill fraction (bbox area / cropped-frame area): {bbox_fill_fraction:.4f}")
    print(f"  Foreground-pixel coverage (mask-true / cropped-frame): {fg_coverage:.4f}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
