#!/usr/bin/env python3
"""compare_datasets.py -- can these datasets be compared, and on which metrics?

ADVISORY ONLY. This prints what it measured, what it means, and how much weight each
comparison can carry. It never refuses, never blocks, never drops a dataset. The
operator knows things about the experiment the tool cannot -- a "risky" comparison may
be exactly the right one for a particular design (project rule, 2026-08-01).

THE PROBLEM. Acquisition parameters change between sessions, animals and labs. The
self-calibrating thresholds absorb overall BRIGHTNESS drift, which is why sections
within a run stay comparable. They do NOT absorb:

  * geometry    -- pixel size, Z-slab depth, projection method change what a cell
                   physically IS, so area- and expansion-denominated params do not carry
  * separability-- a narrower background distribution moves a relative cut relative to
                   the biological populations, calling a different fraction
  * detection   -- over/under-detection changes N, which sits in the denominator of
                   every DAPI-normalised metric

Different metrics survive different changes, and nothing previously told a user which:

  metric                              geometry  SNR  detection
  density (cells/mm^2)                   no      no     no
  marker+ % of DAPI                      no      no     no
  P(activity+|tagged+) raw              partly   no    YES  (carries no N)
  above-chance                          partly partly   no   (N in the denominator)
  above-chance / own control region      YES   partly  YES
  RANK ORDER of regions                  YES    YES    YES

The two robust rows are the recommendation: normalise WITHIN a dataset, then compare
ACROSS datasets by rank. A sensitivity change is largely a monotonic distortion, which
moves values but preserves ordering.

WHAT IT MEASURES (never assumes):
  declared   pixel size, sigma, min/max area, cell expansion, k_robust, per-marker k,
             compartment                                          [pipeline/BraiAn.yml]
  measured   modal nucleus area, DAPI density, per-section anchor-threshold spread,
             marker+ rates, anchor floor (a pseudo-marker cut from the anchor channel,
             whose overlap with a real marker is the TECHNICAL floor), and the
             above-chance value of a nominated control region

Usage:
    python3 compare_datasets.py --project A --project B [--control SSp] [--regions ...]
    python3 compare_datasets.py --project A --project B --rank-regions CA1,CA3,STR,HY
    python3 compare_datasets.py --self-test
"""

from __future__ import annotations

import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cockpit_regions as creg    # noqa: E402
import cockpit_animal as ca       # noqa: E402
import local_chance as lc         # noqa: E402
import chance_methods as cm       # noqa: E402

# How far two datasets may differ on a declared parameter before it matters.
GEOMETRY_TOL = 0.02      # relative; pixel size
AREA_TOL = 0.25          # relative; modal nucleus area
DENSITY_TOL = 0.30       # relative; DAPI density


def describe(project_dir: Path, control: str | None = None) -> dict:
    """Everything measurable about one dataset, declared and observed."""
    p = Path(project_dir)
    config = creg.load_pipeline_config(p)
    ba = {}
    bp = p / "BraiAn.yml"
    if bp.exists():
        import yaml
        y = yaml.safe_load(bp.read_text()) or {}
        ba = (y.get("channelDetections") or [{}])[0].get("parameters", {}) or {}

    tdt = [m for m in (config.markers or []) if m.get("k_robust") is not None]
    out = {
        "project": p.name,
        "pixel_um": ba.get("requestedPixelSizeMicrons"),
        "sigma_um": ba.get("sigmaMicrons"),
        "min_area": ba.get("minAreaMicrons"),
        "max_area": ba.get("maxAreaMicrons"),
        "expansion": ba.get("cellExpansionMicrons"),
        "k_global": config.__dict__.get("k_robust", None),
        "per_marker_k": {m["name"]: m["k_robust"] for m in tdt} or None,
        "compartments": {m["name"]: m.get("compartment") for m in (config.markers or [])},
    }

    # measured: thresholds actually used, from the detection provenance files
    ths = []
    for f in glob.glob(str(p / "results" / "*__detection_threshold.tsv")):
        try:
            t = pd.read_csv(f, sep="\t")
            if "threshold" in t.columns and len(t):
                ths.append(float(t["threshold"].iloc[0]))
        except Exception:
            pass
    out["n_sections"] = len(ths) or None
    out["threshold_med"] = float(np.median(ths)) if ths else None
    out["threshold_spread"] = (max(ths) / min(ths)) if len(ths) > 1 and min(ths) > 0 else None

    # measured: per-cell derived quantities
    try:
        roles = ca.resolve_roles(config)
        d = lc._flags(lc.load_percell(p), roles.tagged, roles.activity)
        area = pd.to_numeric(d.get("nucleus_area_um2"), errors="coerce").dropna()
        if len(area):
            edges = np.arange(0, min(area.max(), 300) + 5, 5)
            h, _ = np.histogram(area, bins=edges)
            out["area_modal_um2"] = float((edges[h.argmax()] + edges[h.argmax() + 1]) / 2)
        out["n_cells"] = int(len(d))
        out["tagged_pct"] = 100.0 * float(d["tagged"].mean())
        out["activity_pct"] = 100.0 * float(d["activity"].mean())
        out["anchor_floor"] = cm.anchor_floor_ratio(d)
        if control:
            ont = creg.load_ontology(p)
            mem = ont.descendants_or_self(control) & set(d["region_label"].dropna().unique())
            sub = d[d["region_label"].isin(mem)]
            out["control_region"] = control
            out["control_above_chance"] = cm.naive_ratio(sub) if len(sub) > 200 else None
            out["control_n"] = int(len(sub))
    except Exception as exc:  # advisory: a dataset that cannot be read is reported, not fatal
        out["read_error"] = str(exc)[:90]
    return out


def _flag(a, b, tol, label) -> tuple[str, str]:
    """(severity, message) for one declared/measured parameter pair."""
    if a is None or b is None:
        return ("?", f"{label}: not measurable in one dataset")
    try:
        a, b = float(a), float(b)
    except (TypeError, ValueError):
        return ("!", f"{label}: {a} vs {b}") if a != b else ("ok", "")
    if a == 0 or b == 0:
        return ("?", f"{label}: zero value")
    rel = abs(a - b) / max(abs(a), abs(b))
    if rel <= tol:
        return ("ok", "")
    return ("!", f"{label}: {a:g} vs {b:g}  ({100*rel:.0f}% apart)")


def verdict(A: dict, B: dict) -> list[tuple[str, str, str]]:
    """(metric class, weight, why) -- ADVISORY. Never a refusal."""
    issues = []
    for key, tol, lab in (("pixel_um", GEOMETRY_TOL, "pixel size"),
                          ("sigma_um", 0.01, "sigma"),
                          ("expansion", 0.01, "cell expansion"),
                          ("area_modal_um2", AREA_TOL, "modal nucleus area"),
                          ("n_cells", 10.0, "")):
        if not lab:
            continue
        sev, msg = _flag(A.get(key), B.get(key), tol, lab)
        if sev != "ok":
            issues.append((sev, msg))

    geom = any("pixel size" in m or "nucleus area" in m for _s, m in issues)
    sens = A.get("per_marker_k") != B.get("per_marker_k") or A.get("k_global") != B.get("k_global")
    comp = A.get("compartments") != B.get("compartments")
    dens = _flag(A.get("n_cells"), B.get("n_cells"), DENSITY_TOL, "cell count")[0] != "ok"

    rows = []
    rows.append(("absolute density / counts", "DO NOT COMPARE" if (geom or dens) else "usable",
                 "geometry or detection differs" if (geom or dens) else "parameters match"))
    rows.append(("marker+ % of DAPI", "weak" if (geom or sens) else "usable",
                 "sensitivity/geometry differs -- N and the cut both move" if (geom or sens)
                 else "parameters match"))
    rows.append(("raw P(activity+|tagged+)", "weak" if sens or comp else "usable",
                 "carries no N, but the cut differs" if sens or comp else "parameters match"))
    rows.append(("above-chance (region baseline)", "weak" if (geom or dens or sens) else "usable",
                 "N sits in the denominator" if (geom or dens or sens) else "parameters match"))
    rows.append(("above-chance / own control", "usable" if A.get("control_above_chance")
                 and B.get("control_above_chance") else "needs a control region",
                 "self-normalising -- the recommended value comparison"))
    rows.append(("RANK ORDER of regions", "usable",
                 "robust to monotonic sensitivity changes -- the recommended cross-dataset test"))
    return issues, rows


def rank_agreement(pA: Path, pB: Path, regions: list[str]) -> dict:
    """Spearman rank correlation of above-chance across shared regions."""
    def vals(p):
        df = cm.compare(Path(p), regions, n_rot=1)
        return df.set_index("region")["naive"] if len(df) else pd.Series(dtype=float)
    a, b = vals(pA), vals(pB)
    shared = [r for r in a.index if r in b.index and np.isfinite(a[r]) and np.isfinite(b[r])]
    if len(shared) < 3:
        return {"n_shared": len(shared), "spearman": None}
    ra = pd.Series({r: a[r] for r in shared}).rank()
    rb = pd.Series({r: b[r] for r in shared}).rank()
    n = len(shared)
    rho = 1 - 6 * ((ra - rb) ** 2).sum() / (n * (n ** 2 - 1))
    return {"n_shared": n, "spearman": float(rho),
            "regions": shared, "A": a[shared].to_dict(), "B": b[shared].to_dict()}


def _self_test() -> None:
    print("Running --self-test (synthetic descriptors, no project needed)...")
    check = lambda c, m: print(f"  {'ok  ' if c else 'FAIL'}  {m}") or (c or sys.exit(1))
    same = {"pixel_um": 0.46, "sigma_um": 2.0, "expansion": 5.0, "area_modal_um2": 37.5,
            "n_cells": 200000, "k_global": 3.0, "per_marker_k": {"TdT": 2.0},
            "compartments": {"TdT": "whole-cell"}, "control_above_chance": 2.0}
    diff = dict(same, pixel_um=0.69, area_modal_um2=60.0)

    _, rows = verdict(same, dict(same))
    d = {m: w for m, w, _why in rows}
    check(d["absolute density / counts"] == "usable", "identical params -> densities usable")
    check(d["RANK ORDER of regions"] == "usable", "rank always usable")

    issues, rows = verdict(same, diff)
    d = {m: w for m, w, _why in rows}
    check(d["absolute density / counts"] == "DO NOT COMPARE",
          "geometry difference -> densities flagged DO NOT COMPARE")
    check(d["above-chance / own control"] == "usable",
          "control-normalised still usable across a geometry change")
    check(d["RANK ORDER of regions"] == "usable", "rank survives a geometry change")
    check(any("pixel size" in m for _s, m in issues), "pixel-size difference is named")

    # ADVISORY CONTRACT: no code path raises or exits on a judgement call.
    weak = verdict({"pixel_um": None}, {"pixel_um": None})
    check(isinstance(weak, tuple), "unmeasurable inputs still return a verdict, never raise")
    print("\nself-test PASSED: verdicts downgrade density/percentage metrics on a geometry "
          "change, keep control-normalised and rank comparisons usable, name the offending "
          "parameter, and never refuse.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--project", type=Path, action="append", default=[],
                   help="QuPath project dir (repeatable; 2+ to compare)")
    p.add_argument("--control", default=None,
                   help="control region acronym, e.g. SSp -- enables the recommended "
                        "control-normalised comparison")
    p.add_argument("--rank-regions", default=None,
                   help="comma-separated regions for the rank-agreement test")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if not a.self_test and len(a.project) < 1:
        p.error("at least one --project is required unless --self-test is set")
    return a


def main() -> int:
    a = parse_args()
    if a.self_test:
        _self_test(); return 0

    ds = [describe(p, a.control) for p in a.project]
    print("=" * 78)
    print("DATASET DESCRIPTORS  (declared above the line, measured below)")
    print("=" * 78)
    keys = [("pixel_um", "pixel size um"), ("sigma_um", "sigma um"),
            ("expansion", "cell expansion"), ("k_global", "k_robust (global)"),
            ("per_marker_k", "per-marker k"), ("compartments", "compartments"),
            ("n_sections", "sections"), ("threshold_med", "median anchor threshold"),
            ("threshold_spread", "threshold spread (max/min)"),
            ("area_modal_um2", "modal nucleus area"), ("n_cells", "cells"),
            ("tagged_pct", "tagged %"), ("activity_pct", "activity %"),
            ("anchor_floor", "ANCHOR FLOOR (technical)"),
            ("control_above_chance", "control above-chance")]
    w = max(len(d["project"]) for d in ds) + 2
    for k, lab in keys:
        vals = []
        for d in ds:
            v = d.get(k)
            vals.append("-" if v is None else (f"{v:.3g}" if isinstance(v, float) else str(v)))
        print(f"  {lab:28}" + "".join(f"{v:>{max(w,14)}}" for v in vals))
    print(f"  {'':28}" + "".join(f"{d['project'][:13]:>{max(w,14)}}" for d in ds))

    if len(ds) < 2:
        print("\n(one dataset -- nothing to compare)"); return 0

    for i in range(len(ds) - 1):
        A, B = ds[i], ds[i + 1]
        print("\n" + "=" * 78)
        print(f"ADVISORY: {A['project']}  vs  {B['project']}")
        print("=" * 78)
        issues, rows = verdict(A, B)
        if issues:
            print("  parameter differences found:")
            for _s, m in issues:
                print(f"    - {m}")
        else:
            print("  no parameter differences detected")
        print(f"\n  {'metric':34}{'weight':>18}   why")
        for metric, weight, why in rows:
            print(f"  {metric:34}{weight:>18}   {why}")

    if a.rank_regions and len(a.project) >= 2:
        regs = [r.strip() for r in a.rank_regions.split(",")]
        print("\n" + "=" * 78)
        print("RANK AGREEMENT (the recommended cross-dataset test)")
        print("=" * 78)
        r = rank_agreement(a.project[0], a.project[1], regs)
        if r.get("spearman") is None:
            print(f"  only {r['n_shared']} shared region(s) -- need >=3 for a rank test")
        else:
            print(f"  {r['n_shared']} shared regions   Spearman rho = {r['spearman']:+.3f}")
            print(f"  {'region':10}{'A':>10}{'B':>10}")
            for reg in r["regions"]:
                print(f"  {reg:10}{r['A'][reg]:>10.2f}{r['B'][reg]:>10.2f}")

    print("\n  ADVISORY ONLY -- nothing here is a refusal. You know the experiment; these")
    print("  are measurements and their consequences, not permissions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
