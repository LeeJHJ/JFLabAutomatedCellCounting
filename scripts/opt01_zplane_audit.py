#!/usr/bin/env python3
"""opt01_zplane_audit.py — OPT-01/OPT-02 imaging-optimization audit for M3 hippocampus.

Measures (does not hardcode, per D-06) the facts feeding 04-IMAGING-NOTES.md:
  1. OPT-01 CZI acquisition facts — Z-plane count, Z-step, pixel size, read directly
     from the raw CZI's metadata via aicspylibczi (same reader czi_mip.py already uses).
  2. OPT-02 file sizes — raw CZI vs. primary MIP OME-TIFF, and their ratio.
  3. OPT-01 plateau data — the two existing region-TSVs' Root-row "Num DAPI-T4" counts
     (3-plane vs. hybrid variant), their percent difference, and an explicit note that
     the single-plane (Z2) variant has never been detection-run (2-of-3 comparison only,
     per RESEARCH.md Open Question 2 / this plan's scope-down resolution).

Metadata-only CZI read (no pixel/tile load) — completes in seconds even on a ~9 GB file.

Usage (from the Analysis root, braian env):
  conda run -n braian python3 scripts/opt01_zplane_audit.py
  conda run -n braian python3 scripts/opt01_zplane_audit.py --czi "/path/to/other.czi"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import aicspylibczi
import pandas as pd

DEFAULT_CZI = Path("Automated Cell Counting/M3 Hippocampus 20x 062026.czi")
DEFAULT_MIP = Path("M3 Hippocampus 20x 062226/M3_20x_MIP_Z1-3.ome.tiff")
DEFAULT_REGION_3PLANE = Path(
    "M3 Hippocampus 20x 062926 3 plane/results/"
    "M3_20x_MIP_Z1-3.ome.tiff - czi_to_mip_regions.tsv"
)
DEFAULT_REGION_HYBRID = Path(
    "M3 Hippocampus 20x 062926 3 plane/results/"
    "M3_20x_hybrid_dapiZ2_mipZ0-2.ome.tiff - Analysis_hybrid_regions.tsv"
)


def audit_czi_acquisition(czi_path: Path) -> dict:
    """OPT-01: read Z-plane count, channel/tile counts, Z-step, and pixel size
    directly from the raw CZI's metadata (no pixel data loaded)."""
    if not czi_path.exists():
        sys.exit(f"CZI not found: {czi_path}\n"
                 f"Pass the correct path with --czi.")

    czi = aicspylibczi.CziFile(str(czi_path))
    dims = czi.get_dims_shape()
    dim0 = dims[0] if isinstance(dims, list) else dims
    n_z = dim0.get("Z", (0, 1))[1]
    n_c = dim0.get("C", (0, 1))[1]
    n_m = dim0.get("M", (0, 1))[1]
    n_s = dim0.get("S", (0, 1))[1]

    scaling = czi.meta.find(".//Scaling/Items")
    if scaling is None:
        sys.exit(f"CZI metadata has no Scaling/Items block: {czi_path}\n"
                 f"Cannot read Z-step / pixel size — file may be corrupt or an unexpected format.")

    z_dist = scaling.find("./Distance[@Id='Z']/Value")
    x_dist = scaling.find("./Distance[@Id='X']/Value")
    if z_dist is None or x_dist is None:
        sys.exit(f"CZI Scaling/Items block missing Z or X Distance entries: {czi_path}")

    z_step_um = float(z_dist.text) * 1e6
    xy_um = float(x_dist.text) * 1e6
    total_z_range_um = (n_z - 1) * z_step_um if n_z > 1 else 0.0

    return {
        "n_z": n_z,
        "n_c": n_c,
        "n_m": n_m,
        "n_s": n_s,
        "z_step_um": z_step_um,
        "pixel_size_um": xy_um,
        "total_z_range_um": total_z_range_um,
    }


def audit_file_sizes(czi_path: Path, mip_path: Path) -> dict:
    """OPT-02: raw CZI vs. primary MIP OME-TIFF size, and their ratio."""
    if not czi_path.exists():
        sys.exit(f"CZI not found: {czi_path}\nPass the correct path with --czi.")
    if not mip_path.exists():
        sys.exit(f"MIP OME-TIFF not found: {mip_path}\nPass the correct path with --mip.")

    czi_bytes = czi_path.stat().st_size
    mip_bytes = mip_path.stat().st_size
    ratio = czi_bytes / mip_bytes if mip_bytes else float("nan")

    return {
        "czi_bytes": czi_bytes,
        "czi_gb": czi_bytes / 1e9,
        "mip_bytes": mip_bytes,
        "mip_gb": mip_bytes / 1e9,
        "ratio": ratio,
    }


def _root_dapi_count(region_tsv: Path) -> int:
    """Read a BraiAn AtlasManager region-TSV, return the Root row's Num DAPI-T4 count."""
    if not region_tsv.exists():
        sys.exit(f"region TSV not found: {region_tsv}\n"
                 f"Expected a BraiAn AtlasManager.saveResults region export "
                 f"(columns: Image Name, Name, Classification, Area um^2, "
                 f"Num Detections, Num DAPI-T4).")

    df = pd.read_csv(region_tsv, sep="\t")
    required_cols = {"Name", "Num DAPI-T4"}
    missing = required_cols - set(df.columns)
    if missing:
        sys.exit(f"region TSV {region_tsv} is missing expected column(s): {sorted(missing)}\n"
                 f"Found columns: {list(df.columns)}")

    root_rows = df[df["Name"] == "Root"]
    if root_rows.empty:
        sys.exit(f"region TSV {region_tsv} has no 'Root' row (whole-section rollup) — "
                 f"cannot read the plateau-comparison DAPI count.")

    val = root_rows.iloc[0]["Num DAPI-T4"]
    if pd.isna(val):
        sys.exit(f"region TSV {region_tsv}: Root row 'Num DAPI-T4' is empty/NaN — "
                 f"cannot read the plateau-comparison DAPI count.")
    return int(val)


def audit_plateau(region_3plane: Path, region_hybrid: Path) -> dict:
    """OPT-01 plateau data: 3-plane vs. hybrid Root-row Num DAPI-T4, percent difference."""
    n_3plane = _root_dapi_count(region_3plane)
    n_hybrid = _root_dapi_count(region_hybrid)
    if n_3plane == 0:
        sys.exit("3-plane Root DAPI count is 0 — cannot compute percent difference.")
    pct_diff = abs(n_3plane - n_hybrid) / n_3plane * 100.0

    return {
        "n_3plane": n_3plane,
        "n_hybrid": n_hybrid,
        "pct_diff": pct_diff,
    }


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--czi", type=Path, default=DEFAULT_CZI,
                    help="raw CZI path (OPT-01 acquisition metadata + OPT-02 raw size)")
    ap.add_argument("--mip", type=Path, default=DEFAULT_MIP,
                    help="primary MIP OME-TIFF path (OPT-02 MIP size)")
    ap.add_argument("--region-3plane", type=Path, default=DEFAULT_REGION_3PLANE,
                    help="3-plane variant's BraiAn region-TSV (OPT-01 plateau comparison)")
    ap.add_argument("--region-hybrid", type=Path, default=DEFAULT_REGION_HYBRID,
                    help="hybrid variant's BraiAn region-TSV (OPT-01 plateau comparison)")
    args = ap.parse_args()

    print("=" * 70)
    print("OPT-01 — CZI acquisition facts [measured]")
    print("=" * 70)
    acq = audit_czi_acquisition(args.czi)
    print(f"  CZI file             : {args.czi}")
    print(f"  Z-planes             : {acq['n_z']}")
    print(f"  Channels             : {acq['n_c']}")
    print(f"  Mosaic tiles (M)     : {acq['n_m']}")
    print(f"  Scenes (S)           : {acq['n_s']}")
    print(f"  Z step               : {acq['z_step_um']:.4f} µm/plane")
    print(f"  Pixel size (X/Y)     : {acq['pixel_size_um']:.6f} µm/px")
    print(f"  Total acquired Z-range: {acq['total_z_range_um']:.2f} µm "
          f"({acq['n_z']} planes spanning {acq['total_z_range_um']:.1f} µm depth)")

    print()
    print("=" * 70)
    print("OPT-02 — File sizes / raw:MIP ratio [measured]")
    print("=" * 70)
    sizes = audit_file_sizes(args.czi, args.mip)
    print(f"  Raw CZI    : {sizes['czi_bytes']:,} bytes ({sizes['czi_gb']:.2f} GB)  [{args.czi}]")
    print(f"  MIP OME-TIFF: {sizes['mip_bytes']:,} bytes ({sizes['mip_gb']:.2f} GB)  [{args.mip}]")
    print(f"  Raw:MIP ratio: {sizes['ratio']:.2f}x  "
          f"(MIP is ~{100.0 / sizes['ratio']:.1f}% of raw CZI size)")

    print()
    print("=" * 70)
    print("OPT-01 — Plateau data: 3-plane vs. hybrid DAPI counts (2-of-3) [measured]")
    print("=" * 70)
    plateau = audit_plateau(args.region_3plane, args.region_hybrid)
    print(f"  3-plane (Z1-3) Root Num DAPI-T4 : {plateau['n_3plane']:,}  [{args.region_3plane}]")
    print(f"  hybrid (dapiZ2+mipZ0-2) Root Num DAPI-T4: {plateau['n_hybrid']:,}  "
          f"[{args.region_hybrid}]")
    print(f"  Percent difference               : {plateau['pct_diff']:.2f}%")
    print()
    print("  NOTE: this is a 2-of-3 empirical comparison. The single-plane (Z2) "
          "variant (M3_20x_Z2_single.ome.tiff) has NO region-TSV / detection run "
          "on disk — it was never classified through 02_detect_classify.groovy or "
          "BraiAnDetect. A full three-way empirical confirmation is deferred as an "
          "optional GUI step (per RESEARCH.md Open Question 2 resolution option b).")


if __name__ == "__main__":
    main()
