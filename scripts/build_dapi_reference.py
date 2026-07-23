#!/usr/bin/env python3
"""build_dapi_reference.py — aggregate + QC the growing long/tidy per-region marker CSV.

Reads the long/tidy combined CSV appended by ``03_export_region_table.groovy``
(``slice,config_tag,region,hemisphere,is_leaf,marker,class,count,density``) and
computes, per ``(config_tag, marker, class, hemisphere, region)``, the
across-slice density mean/SD/CV — so expected per-marker/per-class density can
be defined EMPIRICALLY (SERIES-02) instead of trusting a literature seed. Only
rows sharing a ``config_tag`` (identical detection params) are aggregated
together. The aggregate never fabricates rows for an absent marker: a
TdT-only slice contributes only DAPI/TdT rows (D-04/D-13) — there is no NA
column, no schema conflict, just fewer rows.

Also provides a ``--check-zero-leak`` re-proof of the D-10 leaf-summed parent
rollup invariant, independent of ``03_export_region_table.groovy``'s own
in-script assertion: for each ``(slice, config_tag, marker, class)`` group,
the sum of ``count`` over ``is_leaf == True`` rows must equal the atlas-root
rollup's count — the maximum ``count`` among that group's
``is_leaf == False`` (parent) rows, since the atlas root is an ancestor of
every leaf in the group and therefore holds the largest cumulative count.

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/build_dapi_reference.py
  conda run -n braian python scripts/build_dapi_reference.py --leaf-only
  conda run -n braian python scripts/build_dapi_reference.py --check-zero-leak
  conda run -n braian python scripts/build_dapi_reference.py \\
      --flag-slice "M3_20x_MIP_Z1-3.ome.tiff - czi_to_mip" --z 2.5
  conda run -n braian python scripts/build_dapi_reference.py --self-test
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_REF_CSV = Path("reference/region_marker_combined.csv")

# D-13: the long/tidy combined CSV is one row per (region x marker x class);
# every aggregation and dedup key below must include marker/class or two
# different markers' rows silently collapse into one another.
GROUP_KEYS = ["config_tag", "marker", "class", "hemisphere", "region"]


def load(ref_csv: Path) -> pd.DataFrame:
    if not ref_csv.exists():
        sys.exit(f"reference CSV not found: {ref_csv}\n"
                 f"Run 03_export_region_table.groovy in QuPath first.")
    df = pd.read_csv(ref_csv)
    # Groovy writes booleans as 'True'/'False' strings -> coerce to real bool.
    df["is_leaf"] = df["is_leaf"].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    df["hemisphere"] = df["hemisphere"].fillna("")
    df["count"] = pd.to_numeric(df["count"], errors="coerce")
    df["density"] = pd.to_numeric(df["density"], errors="coerce")
    # Rows are now one-per-(region x marker x class), not one-per-region (D-13) --
    # a given (config_tag, slice, region, marker, class) tuple can only repeat if
    # the exporter was re-run on the same slice. There is no timestamp column in
    # this schema (unlike the old DAPI-only reference CSV), so file order (==
    # append order == recency, since the append is header-guarded and idempotent)
    # is the recency signal; keep='last' keeps the most recently appended row.
    df = df.drop_duplicates(
        subset=["config_tag", "slice", "region", "marker", "class"], keep="last")
    return df


def aggregate(df: pd.DataFrame, leaf_only: bool, min_slices: int) -> pd.DataFrame:
    if leaf_only:
        df = df[df["is_leaf"]]
    g = df.groupby(GROUP_KEYS)["density"]
    stats = g.agg(n_slices="count", mean_density="mean", sd_density="std",
                  min_density="min", max_density="max").reset_index()
    stats["cv"] = stats["sd_density"] / stats["mean_density"]
    total_count = df.groupby(GROUP_KEYS)["count"].sum().rename("total_count")
    stats = stats.merge(total_count, on=GROUP_KEYS, how="left")
    stats = stats[stats["n_slices"] >= min_slices]
    return stats.sort_values(
        ["config_tag", "marker", "class", "region", "hemisphere"]).reset_index(drop=True)


def flag_slice(df: pd.DataFrame, slice_name: str, leaf_only: bool, z: float) -> pd.DataFrame:
    """Report (marker, class, region) rows in `slice_name` whose density is > z SD
    from the reference (built from every OTHER slice sharing the same config_tag)."""
    ref = aggregate(df[df["slice"] != slice_name], leaf_only, min_slices=2)
    sub = df[df["slice"] == slice_name]
    if sub.empty:
        sys.exit(f"no rows for slice {slice_name!r} in the reference CSV")
    merged = sub.merge(ref, on=GROUP_KEYS, how="inner")
    merged["z"] = (merged["density"] - merged["mean_density"]) / merged["sd_density"]
    out = merged.loc[merged["z"].abs() > z,
                     GROUP_KEYS + ["density", "mean_density", "sd_density", "z", "n_slices"]]
    return out.reindex(out["z"].abs().sort_values(ascending=False).index)


def check_zero_leak(df: pd.DataFrame) -> bool:
    """D-10 re-proof, independent of the groovy exporter's own assertion: for each
    (slice, config_tag, marker, class) group, assert sum(count where is_leaf) ==
    max(count where NOT is_leaf) -- the atlas-root rollup, which as an ancestor
    of every leaf in the group holds the largest cumulative count. Prints
    PASS/FAIL/SKIP per group; returns True iff every checked group passes."""
    all_pass = True
    n_groups = 0
    for (slice_, config_tag, marker, cls), g in df.groupby(["slice", "config_tag", "marker", "class"]):
        n_groups += 1
        leaf_sum = int(g.loc[g["is_leaf"], "count"].sum())
        non_leaf_counts = g.loc[~g["is_leaf"], "count"]
        if non_leaf_counts.empty:
            print(f"[SKIP] slice={slice_!r} config_tag={config_tag!r} marker={marker!r} class={cls!r}: "
                  f"no parent (is_leaf=False) rows present -- nothing to re-prove")
            continue
        root_count = int(non_leaf_counts.max())
        ok = leaf_sum == root_count
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] slice={slice_!r} config_tag={config_tag!r} marker={marker!r} class={cls!r}: "
              f"sum(leaf counts)={leaf_sum}  root rollup count={root_count}")
        if not ok:
            all_pass = False
    print(f"\nchecked {n_groups} (slice, config_tag, marker, class) group(s)")
    return all_pass


def _build_synthetic_combined_csv(path: Path, corrupt_leaf: bool) -> None:
    """Two-leaf/one-root, TdT-only synthetic combined CSV for --self-test.

    LeafA + LeafB roll up into Root. When corrupt_leaf=True, LeafB's TdT count
    is tampered with so the leaf sum no longer equals Root's TdT count (Root's
    own count is left as the TRUE rollup) -- the exact zero-leak-violation
    shape --check-zero-leak exists to catch.
    """
    leaf_a_dapi, leaf_a_tdt = 10, 3
    leaf_b_dapi, leaf_b_tdt_true = 15, 5
    leaf_b_tdt = 999 if corrupt_leaf else leaf_b_tdt_true
    root_dapi = leaf_a_dapi + leaf_b_dapi
    root_tdt = leaf_a_tdt + leaf_b_tdt_true  # root always reflects the TRUE rollup

    rows = [
        ("sliceA", "cfgX", "LeafA", "", "True", "DAPI", "DAPI+", leaf_a_dapi, 100.0),
        ("sliceA", "cfgX", "LeafA", "", "True", "TdT", "TdT+", leaf_a_tdt, 30.0),
        ("sliceA", "cfgX", "LeafB", "", "True", "DAPI", "DAPI+", leaf_b_dapi, 150.0),
        ("sliceA", "cfgX", "LeafB", "", "True", "TdT", "TdT+", leaf_b_tdt, 50.0),
        ("sliceA", "cfgX", "Root", "", "False", "DAPI", "DAPI+", root_dapi, 25.0),
        ("sliceA", "cfgX", "Root", "", "False", "TdT", "TdT+", root_tdt, 8.0),
    ]
    header = "slice,config_tag,region,hemisphere,is_leaf,marker,class,count,density"
    lines = [header] + [",".join(str(v) for v in row) for row in rows]
    path.write_text("\n".join(lines) + "\n")


def _self_test() -> None:
    print("Running --self-test (synthetic 2-leaf/1-root TdT-only combined CSV)...")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # (a) consistent tree -- aggregate groups by marker/class; no fabricated Fos rows.
        good_csv = tmp_path / "combined_good.csv"
        _build_synthetic_combined_csv(good_csv, corrupt_leaf=False)
        df_good = load(good_csv)
        markers = set(df_good["marker"].unique())
        assert markers == {"DAPI", "TdT"}, f"expected only DAPI/TdT markers, got {sorted(markers)}"
        assert "Fos" not in markers, "TdT-only synthetic input must never fabricate a Fos group"

        stats = aggregate(df_good, leaf_only=False, min_slices=1)
        assert set(stats["marker"].unique()) == {"DAPI", "TdT"}
        assert set(stats["class"].unique()) == {"DAPI+", "TdT+"}
        assert len(stats) == 6, f"expected 6 aggregate rows (2 markers x 3 regions), got {len(stats)}"

        ok_good = check_zero_leak(df_good)
        assert ok_good is True, "check_zero_leak must PASS on the consistent synthetic tree"

        # (b) corrupted tree -- a leaf count is tampered with; check_zero_leak must FAIL.
        bad_csv = tmp_path / "combined_bad.csv"
        _build_synthetic_combined_csv(bad_csv, corrupt_leaf=True)
        df_bad = load(bad_csv)
        ok_bad = check_zero_leak(df_bad)
        assert ok_bad is False, "check_zero_leak must FAIL on the corrupted-leaf synthetic tree"

    print("\nself-test PASSED: aggregate groups by marker/class with no fabricated absent-marker "
          "rows; --check-zero-leak passes on a consistent tree and fails on a corrupted-leaf tree.")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--ref-csv", type=Path, default=DEFAULT_REF_CSV,
                    help="input long/tidy combined CSV emitted by 03_export_region_table.groovy")
    ap.add_argument("--out", type=Path, default=Path("reference/region_marker_combined_stats.csv"),
                    help="output per-(marker,class,region) reference stats CSV")
    ap.add_argument("--leaf-only", action="store_true", help="aggregate only finest (leaf) regions")
    ap.add_argument("--min-slices", type=int, default=1,
                    help="min slices per (marker,class,region) group to include in the stats table")
    ap.add_argument("--flag-slice", type=str, default=None,
                    help="report this slice's (marker,class,region) rows deviating > --z SD from the reference")
    ap.add_argument("--z", type=float, default=2.5, help="z-score threshold for --flag-slice")
    ap.add_argument("--check-zero-leak", action="store_true",
                    help="re-prove D-10 from the CSV alone: sum(leaf counts) == root rollup count, "
                         "per (slice, config_tag, marker, class); prints PASS/FAIL, exits non-zero on any FAIL")
    ap.add_argument("--self-test", action="store_true",
                    help="run the built-in synthetic-tree self-test and exit (no --ref-csv needed)")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    df = load(args.ref_csv)
    print(f"Loaded {len(df)} region-rows | {df['slice'].nunique()} slice(s) | "
          f"{df['config_tag'].nunique()} config(s): {sorted(df['config_tag'].unique())} | "
          f"markers: {sorted(df['marker'].unique())}")

    if args.check_zero_leak:
        ok = check_zero_leak(df)
        if not ok:
            sys.exit(1)
        print("\nAll zero-leak checks PASSED.")
        return

    stats = aggregate(df, args.leaf_only, args.min_slices)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    stats.to_csv(args.out, index=False)
    print(f"Wrote {len(stats)} per-(marker,class,region) reference rows -> {args.out}")
    if not stats.empty:
        top = stats.sort_values("cv", ascending=False).head(5)
        print("\nMost variable (marker,class,region) combos (highest CV — first to watch for drift):")
        print(top[["config_tag", "marker", "class", "hemisphere", "region", "n_slices",
                   "mean_density", "sd_density", "cv"]].to_string(index=False))

    if args.flag_slice:
        flagged = flag_slice(df, args.flag_slice, args.leaf_only, args.z)
        if flagged.empty:
            print(f"\nNo (marker,class,region) rows in {args.flag_slice!r} deviate > {args.z} SD from the "
                  f"reference (need >=2 other slices with matching config for this to be meaningful).")
        else:
            print(f"\n⚠ {len(flagged)} (marker,class,region) row(s) in {args.flag_slice!r} deviate > {args.z} SD:")
            print(flagged.to_string(index=False))


if __name__ == "__main__":
    main()
