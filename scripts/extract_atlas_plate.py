"""
Allen CCFv3 coronal-plate extraction for the REG-05 elastix fixed image.
Reads the allen_mouse_10um atlas via brainglobe-atlasapi, resolves the AP
axis from atlas.orientation (do NOT hardcode axis 0 -- 06-RESEARCH.md
Assumption A1), and extracts a single 2D coronal plate (+ its binary mask)
at a given AP position in mm from bregma.

CPU-only. Runs in the `braian` conda env.

Usage:
  conda run -n braian python3 scripts/extract_atlas_plate.py \\
      --ap-mm -1.4 -o atlas_plate_10um.tif

  # Synthetic self-test (no atlas download needed):
  conda run -n braian python3 scripts/extract_atlas_plate.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import tifffile


# ── Private helpers ──────────────────────────────────────────────────────────

def _resolve_ap_axis(orientation: str) -> int:
    """Resolve the AP axis index from a brainglobe orientation string."""
    raise NotImplementedError


def _ap_mm_to_index(ap_mm: float, res_um: float, ap_axis: int, volume_shape: tuple[int, int, int]) -> int:
    """Convert an AP position (mm from bregma) to an integer plate index."""
    raise NotImplementedError


def _extract_plate(volume: np.ndarray, index: int, ap_axis: int) -> np.ndarray:
    """Extract a 2D coronal plate from a 3D volume at the given AP index."""
    raise NotImplementedError


def _self_test() -> None:
    """Synthetic in-memory exercise of every helper. Exits nonzero on failure."""
    print("Running self-test...")

    # ── Test A: AP-axis resolution from orientation string ──
    assert _resolve_ap_axis("asr") == 0, "asr orientation: AP should be axis 0"
    assert _resolve_ap_axis("psl") == 0, "psl orientation: AP should be axis 0"
    assert _resolve_ap_axis("srp") == 2, "srp orientation: AP should be axis 2"
    try:
        _resolve_ap_axis("xyz")
        raise AssertionError("expected ValueError for orientation with no a/p axis")
    except ValueError as e:
        assert "xyz" in str(e), f"error message should name offending string, got: {e}"
    print("  PASS: AP-axis resolution from atlas.orientation (A1 mitigation)")

    # ── Test B: AP-mm to index math ──
    volume_shape = (20, 30, 40)
    idx = _ap_mm_to_index(ap_mm=0.1, res_um=10.0, ap_axis=0, volume_shape=volume_shape)
    assert idx == 10, f"expected index 10, got {idx}"
    try:
        _ap_mm_to_index(ap_mm=100.0, res_um=10.0, ap_axis=0, volume_shape=volume_shape)
        raise AssertionError("expected ValueError for out-of-bounds AP index")
    except ValueError as e:
        assert "bound" in str(e).lower() or "20" in str(e), f"error should name index/bound, got: {e}"
    print("  PASS: AP-mm to plate-index math + out-of-bounds guard")

    # ── Test C: plate extraction ──
    volume = np.arange(20 * 30 * 40, dtype=np.uint16).reshape(20, 30, 40)
    plate = _extract_plate(volume, index=5, ap_axis=0)
    assert plate.shape == (30, 40), f"expected (30, 40), got {plate.shape}"
    assert np.array_equal(plate, volume[5]), "extracted plate does not match volume[5]"
    assert plate.dtype == volume.dtype, f"dtype not preserved: {plate.dtype} != {volume.dtype}"
    print("  PASS: plate extraction shape/values/dtype")

    # ── Test D: mask recovers nonzero region ──
    synth_plate = np.zeros((30, 40), dtype=np.uint16)
    synth_plate[5:15, 10:25] = 500
    mask = (synth_plate > 0).astype(np.uint8)
    assert mask.sum() == 10 * 15, f"mask sum mismatch: {mask.sum()}"
    assert np.array_equal(mask > 0, synth_plate > 0), "mask does not recover nonzero region"
    print("  PASS: mask == (plate > 0) recovers nonzero region")

    print("SELF-TEST PASS")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--ap-mm", type=float, default=None, help="AP position in mm from bregma")
    parser.add_argument("--atlas", type=str, default="allen_mouse_10um", help="brainglobe atlas key (default: allen_mouse_10um)")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output plate TIFF path (default: atlas_plate_10um.tif)")
    parser.add_argument("--mask-output", type=Path, default=None, help="Output mask TIFF path (default: <output_stem>_mask.tif)")
    parser.add_argument("--self-test", action="store_true", help="Run the synthetic self-test (no atlas download) and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.self_test:
        _self_test()
        return

    if args.ap_mm is None:
        print("ERROR: --ap-mm is required (unless --self-test)", file=sys.stderr)
        sys.exit(2)

    from brainglobe_atlasapi import BrainGlobeAtlas

    output = args.output or Path("atlas_plate_10um.tif")
    mask_output = args.mask_output or output.with_name(output.stem + "_mask.tif")

    # Step 1: load the atlas.
    print("Step 1: Loading atlas...")
    atlas = BrainGlobeAtlas(args.atlas)
    print(f"  atlas.orientation: {atlas.orientation}")
    print(f"  atlas.shape: {atlas.shape}")
    print(f"  atlas.resolution: {atlas.resolution}")

    # Step 2: resolve the AP axis.
    print("Step 2: Resolving AP axis...")
    ap_axis = _resolve_ap_axis(atlas.orientation)
    res_um = atlas.resolution[ap_axis]
    print(f"  AP axis: {ap_axis}  resolution: {res_um} um")

    # Step 3: compute the plate index.
    print("Step 3: Computing plate index...")
    index = _ap_mm_to_index(args.ap_mm, res_um, ap_axis, atlas.shape)
    print(f"  Plate index: {index}")

    # Step 4: extract the plate + mask.
    print("Step 4: Extracting plate + mask...")
    plate = _extract_plate(atlas.reference, index, ap_axis)
    mask = (plate > 0).astype(np.uint8)
    print(f"  Plate shape: {plate.shape}  dtype: {plate.dtype}")

    # Step 5: write outputs.
    print("Step 5: Writing outputs...")
    tifffile.imwrite(output, plate)
    tifffile.imwrite(mask_output, mask)
    print(f"Output: {output}")
    print(f"Mask output: {mask_output}")


if __name__ == "__main__":
    main()
