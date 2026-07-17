#!/usr/bin/env python3
"""val01_metrics.py — compute the four VAL-01 bioplausibility metrics (D-03).

Reads the per-cell and per-region-area TSVs exported by
``03_export_val01_metrics.groovy`` (QuPath, human-run "Run for project", AFTER
02_detect_classify.groovy) and computes, for the single M3 hippocampus entry:

  1. Double+/TdT+ ratio (both the raw n(Double+)/n(TdT+) convention and the
     Double+/(Double++TdT+) co-expression fraction), broken down per
     hippocampal subfield (region_label is a per-cell column).
  2. Per-region DAPI nucleus density/mm² (per-cell counts joined to the
     per-region area export).
  3. Nucleus-area distribution peak (10 µm^2 histogram-mode bins, matching
     qc_detection_gates.groovy's Gate-1 binning), plus median/IQR/skew as
     bin-independent cross-checks.
  4. Fos+ rate on the SSp corroboration region (hippocampus has no clean
     negative control; SSp's post-bg-sub-fix Fos+ rate is reported as a
     sanity anchor per CONTEXT.md's Claude's-Discretion allowance), plus any
     fiber-tract-labelled rows if present.

All four metrics are printed to stdout in a labeled block, each against its
VAL-01 target band, so Plan 04-03 can transcribe them into 04-VALIDATION.md.
This script does NOT assert pass/fail (D-01: findings record, not a gate).

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/val01_metrics.py
  conda run -n braian python scripts/val01_metrics.py \\
      --percell-tsv "M3 Hippocampus 20x 062926 3 plane/results/val01_percell_export.tsv" \\
      --region-tsv "M3 Hippocampus 20x 062926 3 plane/results/val01_region_area.tsv" \\
      --out results/val01_metrics.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import skew

DEFAULT_PERCELL_TSV = Path("M3 Hippocampus 20x 062926 3 plane/results/val01_percell_export.tsv")
DEFAULT_REGION_TSV = Path("M3 Hippocampus 20x 062926 3 plane/results/val01_region_area.tsv")

RATIO_TARGET = (0.10, 0.40)
DENSITY_TARGET = (500.0, 2000.0)
AREA_PEAK_TARGET = (50.0, 150.0)
FOS_CONTROL_TARGET = (0.01, 0.03)

FIBER_TRACT_LABELS = ["fiber tracts", "cc", "fx", "or", "ec", "em"]

PERCELL_EXPECTED_COLS = [
    "class", "region_label", "nucleus_area_um2",
    "centroid_x", "centroid_y", "fos_bgsub", "tdt_bgsub",
]
REGION_EXPECTED_COLS = ["region_label", "hemisphere", "acronym", "is_leaf", "area_mm2"]


def area_histogram_mode(areas_um2: np.ndarray, bin_width: float = 10.0) -> tuple[float, float, int]:
    """Returns (bin_start, bin_end, count) of the modal bin_width um^2 bin.

    Matches qc_detection_gates.groovy's Gate-1 binning (AREA_BIN_WIDTH_UM2=10.0):
    floor-based bins, argmax over counts.
    """
    areas_um2 = np.asarray(areas_um2, dtype=float)
    areas_um2 = areas_um2[~np.isnan(areas_um2)]
    bin_starts = np.floor(areas_um2 / bin_width) * bin_width
    values, counts = np.unique(bin_starts, return_counts=True)
    peak_idx = np.argmax(counts)
    return float(values[peak_idx]), float(values[peak_idx] + bin_width), int(counts[peak_idx])


def _load_tsv(path: Path, expected_cols: list[str], label: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"ERROR: {label} TSV not found: {path}\n"
                  f"Run 03_export_val01_metrics.groovy in QuPath first (AFTER 02_detect_classify.groovy).")
    df = pd.read_csv(path, sep="\t")
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: {label} TSV {path} is missing expected column(s): {missing}\n"
                  f"Found columns: {list(df.columns)}")
    return df


def load_percell(path: Path) -> pd.DataFrame:
    df = _load_tsv(path, PERCELL_EXPECTED_COLS, "per-cell")
    if len(df) == 0:
        sys.exit(f"ERROR: per-cell TSV {path} has zero rows.")
    df["class"] = df["class"].fillna("Negative")
    df["region_label"] = df["region_label"].fillna("(no region)")
    for col in ["nucleus_area_um2", "centroid_x", "centroid_y", "fos_bgsub", "tdt_bgsub"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def load_region_area(path: Path) -> pd.DataFrame:
    df = _load_tsv(path, REGION_EXPECTED_COLS, "per-region-area")
    df["is_leaf"] = df["is_leaf"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    df["area_mm2"] = pd.to_numeric(df["area_mm2"], errors="coerce")
    return df


def compute_double_tdt_ratio(percell: pd.DataFrame) -> dict:
    counts = percell["class"].value_counts()
    n_double = int(counts.get("Double+", 0))
    n_tdt = int(counts.get("TdT+", 0))
    ratio_convention = (n_double / n_tdt) if n_tdt > 0 else float("nan")
    coexpr_fraction = (n_double / (n_double + n_tdt)) if (n_double + n_tdt) > 0 else float("nan")

    per_region = []
    for region, g in percell.groupby("region_label"):
        c = g["class"].value_counts()
        nd = int(c.get("Double+", 0))
        nt = int(c.get("TdT+", 0))
        r = (nd / nt) if nt > 0 else float("nan")
        cf = (nd / (nd + nt)) if (nd + nt) > 0 else float("nan")
        per_region.append({"region_label": region, "n_double": nd, "n_tdt": nt,
                            "ratio": r, "coexpr_fraction": cf})

    return {
        "n_double": n_double, "n_tdt": n_tdt,
        "ratio_convention": ratio_convention,
        "coexpr_fraction": coexpr_fraction,
        "per_region": per_region,
    }


def compute_density(percell: pd.DataFrame, region_area: pd.DataFrame) -> dict:
    n_per_region = percell.groupby("region_label").size().rename("n_nuclei").reset_index()
    # region_area's region_label carries a "Left: "/"Right: " hemisphere prefix (from the
    # ABBA per-hemisphere annotation hierarchy), while per-cell region_label is the bare
    # leaf acronym with no hemisphere split (regionOf/regionLabel resolve to acronym only).
    # A direct region_label join therefore matches zero rows. Fix: aggregate leaf-region
    # areas across hemispheres by acronym (bilateral sum) before joining on acronym, so
    # density = total nuclei / total leaf-region area for that acronym, matching the
    # per-cell data's grain. Restrict to is_leaf rows to avoid double-counting area from
    # ancestor (non-leaf) regions that overlap their leaf children.
    leaf_area = (region_area[region_area["is_leaf"]]
                 .groupby("acronym")["area_mm2"].sum()
                 .rename("area_mm2").reset_index()
                 .rename(columns={"acronym": "region_label"}))
    merged = n_per_region.merge(leaf_area, on="region_label", how="inner")
    merged["density_per_mm2"] = merged["n_nuclei"] / merged["area_mm2"]
    return {"table": merged.to_dict(orient="records")}


def compute_area_peak(percell: pd.DataFrame) -> dict:
    areas = percell["nucleus_area_um2"].to_numpy(dtype=float)
    areas_valid = areas[~np.isnan(areas)]
    bin_start, bin_end, count = area_histogram_mode(areas, bin_width=10.0)
    median = float(np.median(areas_valid)) if areas_valid.size else float("nan")
    q1 = float(np.percentile(areas_valid, 25)) if areas_valid.size else float("nan")
    q3 = float(np.percentile(areas_valid, 75)) if areas_valid.size else float("nan")
    iqr = q3 - q1
    sk = float(skew(areas_valid)) if areas_valid.size > 2 else float("nan")
    return {"peak_bin_start": bin_start, "peak_bin_end": bin_end, "peak_count": count,
            "median": median, "q1": q1, "q3": q3, "iqr": iqr, "skew": sk,
            "n_valid": int(areas_valid.size)}


def compute_fos_control_rate(percell: pd.DataFrame) -> dict:
    ssp = percell[percell["region_label"].astype(str).str.startswith("SSp")]
    result = {"ssp_n": int(len(ssp))}
    if len(ssp) > 0:
        c = ssp["class"].value_counts()
        n_pos = int(c.get("Fos+", 0)) + int(c.get("Double+", 0))
        result["ssp_fos_positive_n"] = n_pos
        result["ssp_fos_rate"] = n_pos / len(ssp)
    else:
        result["ssp_fos_positive_n"] = 0
        result["ssp_fos_rate"] = float("nan")

    fiber_rows = percell[percell["region_label"].astype(str).isin(FIBER_TRACT_LABELS)]
    result["fiber_tract_n"] = int(len(fiber_rows))
    if len(fiber_rows) > 0:
        c = fiber_rows["class"].value_counts()
        n_pos = int(c.get("Fos+", 0)) + int(c.get("Double+", 0))
        result["fiber_tract_fos_positive_n"] = n_pos
        result["fiber_tract_fos_rate"] = n_pos / len(fiber_rows)
    else:
        result["fiber_tract_fos_positive_n"] = 0
        result["fiber_tract_fos_rate"] = float("nan")
    return result


def _band(v: float, lo: float, hi: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "n/a"
    return "IN RANGE" if lo <= v <= hi else "flagged OUT of range"


def print_report(ratio: dict, density: dict, area_peak: dict, fos_control: dict) -> None:
    print("=" * 78)
    print("VAL-01 BIOPLAUSIBILITY METRICS (findings record, not a pass/fail gate -- D-01)")
    print("=" * 78)

    print("-" * 78)
    print("1. Double+/TdT+ ratio")
    print(f"   n(Double+)={ratio['n_double']}  n(TdT+)={ratio['n_tdt']}")
    print(f"   Double+/TdT+ ratio  (n(Double+)/n(TdT+))          = {ratio['ratio_convention']:.3f}"
          f"   [target {RATIO_TARGET[0]:.0%}-{RATIO_TARGET[1]:.0%}: {_band(ratio['ratio_convention'], *RATIO_TARGET)}]")
    print(f"   Co-expression fraction (Double+/(Double++TdT+))   = {ratio['coexpr_fraction']:.3f}"
          f"   [target {RATIO_TARGET[0]:.0%}-{RATIO_TARGET[1]:.0%}: {_band(ratio['coexpr_fraction'], *RATIO_TARGET)}]")
    print("   Per hippocampal subfield (region_label):")
    for row in ratio["per_region"]:
        r = row["ratio"]
        rs = f"{r:.3f}" if not np.isnan(r) else "n/a"
        cf = row["coexpr_fraction"]
        cfs = f"{cf:.3f}" if not np.isnan(cf) else "n/a"
        print(f"     {row['region_label']}: n(Double+)={row['n_double']} n(TdT+)={row['n_tdt']} "
              f"ratio={rs} coexpr_fraction={cfs}")

    print("-" * 78)
    print(f"2. Per-region DAPI nucleus density (target {DENSITY_TARGET[0]:.0f}-{DENSITY_TARGET[1]:.0f}/mm^2)")
    for row in density["table"]:
        d = row["density_per_mm2"]
        print(f"   {row['region_label']}: n_nuclei={row['n_nuclei']} area_mm2={row['area_mm2']:.4f} "
              f"density={d:.1f}/mm^2  [{_band(d, *DENSITY_TARGET)}]")

    print("-" * 78)
    print(f"3. Nucleus-area distribution peak (target {AREA_PEAK_TARGET[0]:.0f}-{AREA_PEAK_TARGET[1]:.0f} um^2)")
    print(f"   Peak bin: [{area_peak['peak_bin_start']:.1f}, {area_peak['peak_bin_end']:.1f}) um^2 "
          f"(count={area_peak['peak_count']}, n_valid={area_peak['n_valid']})  "
          f"[{_band(area_peak['peak_bin_start'], *AREA_PEAK_TARGET)}]")
    print(f"   Median={area_peak['median']:.2f}  IQR=[{area_peak['q1']:.2f}, {area_peak['q3']:.2f}] "
          f"(IQR width={area_peak['iqr']:.2f})  Skew={area_peak['skew']:.3f}")

    print("-" * 78)
    print(f"4. Fos+ control rate (target {FOS_CONTROL_TARGET[0]:.0%}-{FOS_CONTROL_TARGET[1]:.0%}, or absence documented)")
    print("   No clean negative-control region in this hippocampus-only section (documented absence).")
    if fos_control["ssp_n"] > 0:
        print(f"   SSp corroboration: n={fos_control['ssp_n']} "
              f"Fos+={fos_control['ssp_fos_positive_n']} "
              f"rate={fos_control['ssp_fos_rate']:.3f}  "
              f"[{_band(fos_control['ssp_fos_rate'], *FOS_CONTROL_TARGET)}] "
              f"(SSp is NOT a true negative control -- corroboration anchor only)")
    else:
        print("   SSp corroboration: no SSp-labelled cells found in this export.")
    if fos_control["fiber_tract_n"] > 0:
        print(f"   Fiber-tract soft anchor: n={fos_control['fiber_tract_n']} "
              f"Fos+={fos_control['fiber_tract_fos_positive_n']} "
              f"rate={fos_control['fiber_tract_fos_rate']:.3f}")
    else:
        print("   Fiber-tract soft anchor: no fiber-tract-labelled cells found in this export.")
    print("=" * 78)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--percell-tsv", type=Path, default=DEFAULT_PERCELL_TSV,
                     help="per-cell export TSV from 03_export_val01_metrics.groovy")
    ap.add_argument("--region-tsv", type=Path, default=DEFAULT_REGION_TSV,
                     help="per-region-area export TSV from 03_export_val01_metrics.groovy")
    ap.add_argument("--out", type=Path, default=None,
                     help="optional JSON dump of all computed metrics")
    args = ap.parse_args()

    percell = load_percell(args.percell_tsv)
    region_area = load_region_area(args.region_tsv)
    print(f"Loaded {len(percell)} per-cell rows from {args.percell_tsv}")
    print(f"Loaded {len(region_area)} per-region-area rows from {args.region_tsv}")

    ratio = compute_double_tdt_ratio(percell)
    density = compute_density(percell, region_area)
    area_peak = compute_area_peak(percell)
    fos_control = compute_fos_control_rate(percell)

    print_report(ratio, density, area_peak, fos_control)

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w") as f:
            json.dump({
                "double_tdt_ratio": ratio,
                "density": density,
                "area_peak": area_peak,
                "fos_control": fos_control,
            }, f, indent=2, default=lambda o: None if isinstance(o, float) and np.isnan(o) else o)
        print(f"\nWrote metrics JSON -> {args.out}")


if __name__ == "__main__":
    main()
