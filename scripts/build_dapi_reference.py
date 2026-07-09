#!/usr/bin/env python3
"""build_dapi_reference.py — aggregate + QC the internal per-region DAPI density reference.

Reads the CSV appended by ``export_region_dapi_reference.groovy`` and computes, per
``(config_tag, hemisphere, acronym)``, the across-image density mean/SD/CV — so expected
DAPI density can be defined EMPIRICALLY (SERIES-02) instead of trusting a literature seed.
Only rows sharing a ``config_tag`` (identical detection params) are aggregated together.

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/build_dapi_reference.py
  conda run -n braian python scripts/build_dapi_reference.py --leaf-only
  conda run -n braian python scripts/build_dapi_reference.py \\
      --flag-image "M3_20x_MIP_Z1-3.ome.tiff - czi_to_mip" --z 2.5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def load(ref_csv: Path) -> pd.DataFrame:
    if not ref_csv.exists():
        sys.exit(f"reference CSV not found: {ref_csv}\n"
                 f"Run export_region_dapi_reference.groovy in QuPath first.")
    df = pd.read_csv(ref_csv)
    # Groovy writes booleans as 'true'/'false' strings -> coerce to real bool.
    df["is_leaf"] = df["is_leaf"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    df["hemisphere"] = df["hemisphere"].fillna("")
    # If a region for a given (image, config) was exported more than once, keep the latest.
    df = df.sort_values("timestamp").drop_duplicates(
        subset=["config_tag", "image", "region_label"], keep="last")
    return df


def aggregate(df: pd.DataFrame, leaf_only: bool, min_images: int) -> pd.DataFrame:
    if leaf_only:
        df = df[df["is_leaf"]]
    g = df.groupby(["config_tag", "hemisphere", "acronym"])["density_per_mm2"]
    stats = g.agg(n_images="count", mean_density="mean", sd_density="std",
                  min_density="min", max_density="max").reset_index()
    stats["cv"] = stats["sd_density"] / stats["mean_density"]
    stats = stats[stats["n_images"] >= min_images]
    return stats.sort_values(["config_tag", "acronym", "hemisphere"]).reset_index(drop=True)


def flag_image(df: pd.DataFrame, image: str, leaf_only: bool, z: float) -> pd.DataFrame:
    """Report regions in `image` whose density is > z SD from the reference (built from the OTHER images)."""
    ref = aggregate(df[df["image"] != image], leaf_only, min_images=2)
    sub = df[df["image"] == image]
    if sub.empty:
        sys.exit(f"no rows for image {image!r} in the reference CSV")
    merged = sub.merge(ref, on=["config_tag", "hemisphere", "acronym"], how="inner")
    merged["z"] = (merged["density_per_mm2"] - merged["mean_density"]) / merged["sd_density"]
    out = merged.loc[merged["z"].abs() > z,
                     ["config_tag", "hemisphere", "acronym", "density_per_mm2",
                      "mean_density", "sd_density", "z", "n_images"]]
    return out.reindex(out["z"].abs().sort_values(ascending=False).index)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--ref-csv", type=Path, default=Path("reference/dapi_region_reference.csv"),
                    help="input long-format CSV appended by the QuPath exporter")
    ap.add_argument("--out", type=Path, default=Path("reference/dapi_region_reference_stats.csv"),
                    help="output per-region reference stats CSV")
    ap.add_argument("--leaf-only", action="store_true", help="aggregate only finest (leaf) regions")
    ap.add_argument("--min-images", type=int, default=1,
                    help="min images per region to include in the stats table")
    ap.add_argument("--flag-image", type=str, default=None,
                    help="report this image's regions deviating > --z SD from the reference")
    ap.add_argument("--z", type=float, default=2.5, help="z-score threshold for --flag-image")
    args = ap.parse_args()

    df = load(args.ref_csv)
    print(f"Loaded {len(df)} region-rows | {df['image'].nunique()} image(s) | "
          f"{df['config_tag'].nunique()} config(s): {sorted(df['config_tag'].unique())}")

    stats = aggregate(df, args.leaf_only, args.min_images)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(args.out, index=False)
    print(f"Wrote {len(stats)} per-region reference rows -> {args.out}")
    if not stats.empty:
        top = stats.sort_values("cv", ascending=False).head(5)
        print("\nMost variable regions (highest CV — first to watch for drift):")
        print(top[["config_tag", "hemisphere", "acronym", "n_images",
                   "mean_density", "sd_density", "cv"]].to_string(index=False))

    if args.flag_image:
        flagged = flag_image(df, args.flag_image, args.leaf_only, args.z)
        if flagged.empty:
            print(f"\nNo regions in {args.flag_image!r} deviate > {args.z} SD from the reference "
                  f"(need >=2 other images with matching config for this to be meaningful).")
        else:
            print(f"\n⚠ {len(flagged)} region(s) in {args.flag_image!r} deviate > {args.z} SD:")
            print(flagged.to_string(index=False))


if __name__ == "__main__":
    main()
