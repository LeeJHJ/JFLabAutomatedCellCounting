#!/usr/bin/env python3
"""verify_export_integrity.py — EXP-02 export-integrity checker (D-06/D-07).

Validates the non-clobbering property of `03_export_val01_metrics.groovy`'s
per-entry output: after a QuPath "Run for project" pass, every distinct
project entry must have written its OWN percell/region TSV pair into
`results/`, named `<stem>__val01_percell_export.tsv` /
`<stem>__val01_region_area.tsv`. This script is read-only — it never
mutates anything in `--results`.

Asserts:
  1. Pairing — every percell stem has a matching region stem and vice versa.
  2. Even file count — total matched files == 2 * <distinct stems>.
  3. Non-clobbering (only when >= 2 distinct stems exist) — per-entry percell
     row counts (data rows, excluding header) are NOT all identical. A
     clobbering regression collapses every entry onto the same fixed
     filename, so either only one file survives (caught by assertion 1/2)
     or, in a more insidious case, every "distinct" file secretly holds
     the same last-entry data (an identical row-count signature across
     all stems is the same distinguishing symptom).

When fewer than 2 distinct stems are present (e.g. run against a
single-entry project), the multi-entry clobbering assertion is skipped —
printed explicitly — but pairing + naming are still verified, so this
checker is runnable now (Phase 5, single M3 entry) and again once the
5-entry wBA1-3 series is classified (Phase 8/10).

Usage (braian env):
  conda run -n braian python3 scripts/verify_export_integrity.py \\
      --results "M3 Hippocampus 20x 062926 3 plane/results"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PERCELL_SUFFIX = "__val01_percell_export.tsv"
REGION_SUFFIX = "__val01_region_area.tsv"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument(
        "--results", type=Path, required=True,
        help="QuPath project results/ directory to check (read-only)",
    )
    return p.parse_args()


def _stem_of(path: Path, suffix: str) -> str:
    name = path.name
    assert name.endswith(suffix)
    return name[: -len(suffix)]


def _count_data_rows(path: Path) -> int:
    """Count data rows (total lines minus the header row)."""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        n = sum(1 for _ in f)
    return max(0, n - 1)


def main() -> None:
    args = parse_args()
    results_dir: Path = args.results

    if not results_dir.exists() or not results_dir.is_dir():
        sys.exit(f"ERROR: --results directory not found: {results_dir}")

    percell_files = sorted(results_dir.glob(f"*{PERCELL_SUFFIX}"))
    region_files = sorted(results_dir.glob(f"*{REGION_SUFFIX}"))

    if not percell_files and not region_files:
        sys.exit(
            f"ERROR: no per-entry export files found in {results_dir}\n"
            f"Expected files matching '*{PERCELL_SUFFIX}' and '*{REGION_SUFFIX}'.\n"
            f"Run 03_export_val01_metrics.groovy (\"Run for project\") first, "
            f"or check --results points at the right directory."
        )

    percell_stems = {_stem_of(p, PERCELL_SUFFIX) for p in percell_files}
    region_stems = {_stem_of(p, REGION_SUFFIX) for p in region_files}

    failures: list[str] = []

    # --- Assertion 1: pairing ---
    only_percell = sorted(percell_stems - region_stems)
    only_region = sorted(region_stems - percell_stems)
    if only_percell:
        failures.append(
            f"percell file(s) with no matching region file: {only_percell}"
        )
    if only_region:
        failures.append(
            f"region file(s) with no matching percell file: {only_region}"
        )

    paired_stems = sorted(percell_stems & region_stems)
    distinct_stems = len(paired_stems)

    # --- Assertion 2: even file count == 2 * distinct stems ---
    total_files = len(percell_files) + len(region_files)
    if total_files != 2 * distinct_stems:
        failures.append(
            f"file count mismatch: found {total_files} total files "
            f"(percell={len(percell_files)}, region={len(region_files)}) "
            f"but {distinct_stems} distinct paired stem(s) implies {2 * distinct_stems} expected"
        )
    if total_files % 2 != 0:
        failures.append(f"total file count is odd: {total_files}")

    # --- Per-stem row-count summary ---
    percell_by_stem = {_stem_of(p, PERCELL_SUFFIX): p for p in percell_files}
    region_by_stem = {_stem_of(p, REGION_SUFFIX): p for p in region_files}

    print(f"Checking {results_dir} ...")
    print(f"Distinct stems (paired): {distinct_stems}")
    row_counts: dict[str, int] = {}
    for stem in paired_stems:
        percell_rows = _count_data_rows(percell_by_stem[stem])
        region_rows = _count_data_rows(region_by_stem[stem])
        row_counts[stem] = percell_rows
        print(f"  stem={stem!r}  percell_rows={percell_rows}  region_rows={region_rows}")

    # --- Assertion 3: non-clobbering (only when >= 2 distinct stems) ---
    if distinct_stems >= 2:
        distinct_row_counts = set(row_counts.values())
        if len(distinct_row_counts) == 1:
            failures.append(
                f"clobbering guard tripped: all {distinct_stems} entries have the "
                f"IDENTICAL percell row count ({next(iter(distinct_row_counts))}) — "
                f"this is the signature of a clobbering regression (every entry "
                f"silently sharing the same data)"
            )
    else:
        print(
            "Only 0 or 1 distinct stem(s) present — multi-entry clobbering assertion "
            "skipped (need >= 2 entries). Pairing + naming still verified above."
        )

    if failures:
        print("\nFAIL:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)

    print("\nPASS")


if __name__ == "__main__":
    main()
