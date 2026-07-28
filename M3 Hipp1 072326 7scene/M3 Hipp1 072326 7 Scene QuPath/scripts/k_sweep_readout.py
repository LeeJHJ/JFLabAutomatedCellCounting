#!/usr/bin/env python3
"""k_sweep_readout.py -- k-sweep (robust-cut multiplier) readout across a section series,
generalized from the validated exploratory prototype (PROTOTYPE_ksweep_laba.py).

Reads a QuPath project's exported per-cell TSVs (``03_export_region_table.groovy``'s
``*__percell_export.tsv``, one per section) and reports marker+ counts across a swept
range of k_robust values (the robust-cut multiplier used by ``02_detect_classify.groovy``),
so the operator sees the detection RANGE (e.g. k=2 lenient .. k=3 strict) instead of a
single k, without re-running the pipeline.

EXACT-REPRODUCTION CONTRACT (do not modify -- validated against the real classifier,
02_detect_classify.groovy lines ~416-472):
  - median: numpy's default linear-interpolated median (matches Groovy medianOf's
    even-n 0.5*(a+b)).
  - mad = median(|x - median(x)|); robust_sd = 1.4826 * mad.
  - threshold(k) = median + k * robust_sd.
  - positive iff bgsub >= threshold(k)  (>=, matching Groovy `values.count { it >= threshold }`).
  - classifiable population (used for BOTH threshold derivation AND every count) = rows
    with class != "Excluded" AND finite <marker>_bgsub. Derived PER SECTION PER MARKER.

D-04/D-01 marker-agnostic: iterates whichever non-anchor markers are declared in
pipeline.yml (and actually present as a "<marker>_bgsub" column in a given section's
export) -- never assumes a fixed Fos/TdT pair. Runs identically on a 1-marker (TdT-only)
or 2-marker (Fos+TdT) declared set. The anchor (DAPI) is only ever the denominator
(the classifiable-population size) -- it is never itself swept.

READ-ONLY: this tool only globs and reads *__percell_export.tsv files under
--results-dir. It never re-runs QuPath, never touches pipeline.yml / 02_detect_classify.groovy,
and never reads any image/CZI.

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/k_sweep_readout.py --self-test
  conda run -n braian python scripts/k_sweep_readout.py \\
      --results-dir "wBA/wBA1-2_2-1-tdt-only 072026 project/results"
  conda run -n braian python scripts/k_sweep_readout.py \\
      --results-dir "wBA/wBA1-2_2-1-tdt-only 072026 project/results" \\
      --regions "LA,BLA,BMA" --amygdala-groups \\
      --out results/ksweep_tidy.csv --figure results/ksweep_LA-BA.png
"""
from __future__ import annotations

import argparse
import glob
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (must follow matplotlib.use("Agg"))

# ---------------------------------------------------------------------------
# Built-in amygdala nucleus groups (LA is the amygdala nucleus, NOT "LAT" thalamus).
# ---------------------------------------------------------------------------
AMYGDALA_GROUPS: dict[str, set[str]] = {
    "LA": {"LA"},
    "BLA": {"BLA", "BLAa", "BLAp", "BLAv"},
    "BMA": {"BMA", "BMAa", "BMAp"},
}

REQUIRED_PERCELL_COLS = [
    "class", "region_label", "nucleus_area_um2", "centroid_x_px", "centroid_y_px",
]


# ---------------------------------------------------------------------------
# Robust-cut math (exact-reproduction contract)
# ---------------------------------------------------------------------------

def _median(values: np.ndarray) -> float:
    return float(np.median(values))


def _mad(values: np.ndarray, med: float) -> float:
    return float(np.median(np.abs(values - med)))


def robust_stats(values: np.ndarray) -> tuple[float, float, float]:
    """Returns (median, mad, robust_sd) for a classifiable bg-sub population.
    robust_sd = 1.4826 * mad. NaN triple if values is empty."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return float("nan"), float("nan"), float("nan")
    med = _median(values)
    mad = _mad(values, med)
    return med, mad, 1.4826 * mad


def robust_threshold(values: np.ndarray, k: float) -> float:
    """threshold = median(values) + k * 1.4826 * MAD(values) -- exact reproduction of
    02_detect_classify.groovy's medianOf/madOf/robustThreshold (linear-interpolated
    median, matching Groovy's even-n 0.5*(a+b))."""
    med, _mad_v, robust_sd = robust_stats(values)
    return med + k * robust_sd


# ---------------------------------------------------------------------------
# Per-cell TSV loading
# ---------------------------------------------------------------------------

def region_acronym(region_label: pd.Series) -> pd.Series:
    """acronym = region_label.split(': ')[-1] if ': ' in region_label else region_label
    -- handles both a 'Left: <acronym>'/'Right: <acronym>' hemisphere prefix and a bare
    acronym."""
    def _acr(s: str) -> str:
        return s.split(": ")[-1] if ": " in s else s
    return region_label.astype(str).map(_acr)


def section_label(path: Path) -> str:
    """Derive the section label from the export filename exactly as the validated
    prototype: basename.split(' - ')[-1].split('__')[0]
    (e.g. 'wBA1-2_2-1_s1_MIP.ome.tiff - wBA1-2_2-1_s1__id1__percell_export.tsv'
     -> 'wBA1-2_2-1_s1')."""
    return path.name.split(" - ")[-1].split("__")[0]


def load_percell(path: Path) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"ERROR: per-cell TSV not found: {path}")
    df = pd.read_csv(path, sep="\t")
    missing = [c for c in REQUIRED_PERCELL_COLS if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: {path} is missing expected column(s): {missing}\n"
                  f"Found columns: {list(df.columns)}")
    df["class"] = df["class"].fillna("Negative")
    df["region_label"] = df["region_label"].fillna("(no region)")
    for col in df.columns:
        if col.endswith("_bgsub"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["acronym"] = region_acronym(df["region_label"])
    return df


def markers_in_df(df: pd.DataFrame) -> list[str]:
    """Marker names (not full column names) for every '<marker>_bgsub' column
    actually present (D-04) -- never assumes a fixed Fos/TdT pair."""
    return sorted(c[: -len("_bgsub")] for c in df.columns if c.endswith("_bgsub"))


def classifiable_mask(df: pd.DataFrame, marker: str) -> pd.Series:
    """classifiable = class != 'Excluded' AND finite <marker>_bgsub. Excluded cells
    removed from BOTH threshold derivation AND every count -- the per-cell 'class'
    column already carries 'Excluded' (written by 02_detect_classify.groovy for cells
    in exclude_acronyms regions); this is read, never re-derived from acronyms."""
    bg = df[f"{marker}_bgsub"]
    return (df["class"] != "Excluded") & bg.notna() & np.isfinite(bg)


# ---------------------------------------------------------------------------
# pipeline.yml config
# ---------------------------------------------------------------------------

def load_pipeline_config(path: Path) -> dict:
    if not path.exists():
        sys.exit(f"ERROR: pipeline config not found: {path}")
    with open(path) as f:
        cfg = yaml.safe_load(f)
    anchor_name = cfg.get("anchor", {}).get("name", "DAPI")
    marker_names = [m["name"] for m in cfg.get("markers", [])]
    k_robust = float(cfg.get("k_robust", 3.0))
    return {"anchor_name": anchor_name, "marker_names": marker_names, "k_robust": k_robust}


def build_k_set(k_min: float, k_max: float, k_step: float, k_values_str: str | None,
                 k_robust: float) -> list[float]:
    """k range: --k-min/--k-max/--k-step, OR an explicit --k-values comma list
    (overrides the range). ALWAYS unions pipeline.yml's k_robust in. Sorted
    ascending, de-duplicated to a stable float tolerance."""
    if k_values_str:
        ks = [float(v.strip()) for v in k_values_str.split(",") if v.strip()]
    else:
        if k_step <= 0:
            sys.exit(f"ERROR: --k-step must be > 0, got {k_step}")
        n = int(round((k_max - k_min) / k_step)) + 1
        ks = [round(k_min + i * k_step, 6) for i in range(max(n, 1))]
    ks.append(round(float(k_robust), 6))
    ks_sorted = sorted(ks)
    deduped: list[float] = []
    for k in ks_sorted:
        if not deduped or abs(k - deduped[-1]) > 1e-6:
            deduped.append(k)
    return deduped


def parse_regions(regions_str: str, amygdala_groups: bool) -> dict[str, set[str]]:
    """--regions "LA,BLA,BMA" -> {group_name: {acronym, ...}}. With --amygdala-groups,
    a token matching a built-in AMYGDALA_GROUPS key expands to its acronym set;
    otherwise (or for an unrecognized token) the token is treated as an exact acronym
    (its own singleton group)."""
    groups: dict[str, set[str]] = {}
    for tok in [t.strip() for t in regions_str.split(",") if t.strip()]:
        if amygdala_groups and tok in AMYGDALA_GROUPS:
            groups[tok] = set(AMYGDALA_GROUPS[tok])
        else:
            groups[tok] = {tok}
    return groups


# ---------------------------------------------------------------------------
# Core per-section engine
# ---------------------------------------------------------------------------

@dataclass
class SectionMarkerStats:
    median: float
    robust_sd: float
    n_classifiable: int
    bgsub_classifiable: np.ndarray
    acronym_classifiable: np.ndarray  # aligned with bgsub_classifiable, for region masks


def analyze_section(df: pd.DataFrame, marker_names: list[str]) -> dict[str, SectionMarkerStats]:
    """Per-marker classifiable population (class != Excluded AND finite <marker>_bgsub),
    derived independently PER MARKER on this section's data. marker_names should already
    be filtered to markers whose <marker>_bgsub column is present in df."""
    out: dict[str, SectionMarkerStats] = {}
    for marker in marker_names:
        col = f"{marker}_bgsub"
        if col not in df.columns:
            continue
        mask = classifiable_mask(df, marker)
        bg = df.loc[mask, col].to_numpy(dtype=float)
        acr = df.loc[mask, "acronym"].to_numpy()
        med, _mad_v, rsd = robust_stats(bg)
        out[marker] = SectionMarkerStats(
            median=med, robust_sd=rsd, n_classifiable=int(bg.size),
            bgsub_classifiable=bg, acronym_classifiable=acr)
    return out


def region_stats_for_group(st: SectionMarkerStats, acronyms: set[str]) -> tuple[np.ndarray, np.ndarray]:
    """Returns (bgsub subset restricted to `acronyms`, boolean mask into the section's
    classifiable population). A region absent from this section yields an empty array
    (size 0), never an error."""
    if st.n_classifiable == 0:
        return np.array([], dtype=float), np.array([], dtype=bool)
    mask = np.isin(st.acronym_classifiable, list(acronyms))
    return st.bgsub_classifiable[mask], mask


def _count_at_k(st: SectionMarkerStats, k: float) -> int:
    if st.n_classifiable == 0:
        return 0
    thr = st.median + k * st.robust_sd
    return int((st.bgsub_classifiable >= thr).sum())


def _threshold_at_k(st: SectionMarkerStats, k: float) -> float:
    if st.n_classifiable == 0:
        return float("nan")
    return st.median + k * st.robust_sd


# ---------------------------------------------------------------------------
# Section-level / region-level printed readouts
# ---------------------------------------------------------------------------

def print_section_table(section_stats: dict[str, dict[str, SectionMarkerStats]],
                         k_set: list[float], k_current: float) -> None:
    print("=" * 100)
    print("SECTION-LEVEL k-SWEEP  (per marker: median, robust_sd, then threshold / count / % at each k)")
    print("=" * 100)
    k_hdr = "  ".join((f"k={k:g}*" if abs(k - k_current) < 1e-6 else f"k={k:g} ") for k in k_set)
    print(f"{'section':16} {'marker':6} {'median':>9} {'robustSD':>9}   {k_hdr}")
    for sl, markers in section_stats.items():
        if not markers:
            print(f"{sl:16}  (no declared marker present in this export)")
            continue
        for marker, st in markers.items():
            thr_row = [_threshold_at_k(st, k) for k in k_set]
            cnt_row = [_count_at_k(st, k) for k in k_set]
            pct_row = [(100.0 * c / st.n_classifiable) if st.n_classifiable else 0.0 for c in cnt_row]
            print(f"{sl:16} {marker:6} {st.median:9.1f} {st.robust_sd:9.1f}   n={st.n_classifiable}")
            print(f"{'':16} {'':6} {'threshold':>19}   " + "  ".join(f"{t:>7.1f}" for t in thr_row))
            print(f"{'':16} {'':6} {'count':>19}   " + "  ".join(f"{c:>7d}" for c in cnt_row))
            print(f"{'':16} {'':6} {'% classifiable':>19}   " + "  ".join(f"{p:>6.1f}%" for p in pct_row))
    print("(* = current pipeline.yml k_robust)")
    print()


def print_region_table(section_stats: dict[str, dict[str, SectionMarkerStats]],
                        region_groups: dict[str, set[str]], k_set: list[float],
                        k_current: float) -> None:
    print("=" * 100)
    print("REGION-LEVEL k-SWEEP  (anchor denom = classifiable-for-marker count in region | marker+ count(k) (% of anchor))")
    print("=" * 100)
    for group_name, acronyms in region_groups.items():
        print(f"-- {group_name} = {sorted(acronyms)} --")
        for sl, markers in section_stats.items():
            if not markers:
                continue
            for marker, st in markers.items():
                bg_in, _mask = region_stats_for_group(st, acronyms)
                denom = int(bg_in.size)
                cells = []
                for k in k_set:
                    thr = _threshold_at_k(st, k)
                    cnt = int((bg_in >= thr).sum()) if denom else 0
                    pct = 100.0 * cnt / denom if denom else 0.0
                    marker_flag = "*" if abs(k - k_current) < 1e-6 else ""
                    cells.append(f"k={k:g}{marker_flag}:{cnt}({pct:.1f}%)")
                print(f"  {sl:14} {marker:6} anchor={denom:>6}   " + "  ".join(cells))
    print("(* = current pipeline.yml k_robust; a region absent from a section reports 0 for every field)")
    print()


# ---------------------------------------------------------------------------
# --out (tidy CSV) / --figure (grouped bar) -- Task 2 implements these bodies
# ---------------------------------------------------------------------------

def write_tidy_csv(section_stats: dict[str, dict[str, SectionMarkerStats]],
                    region_groups: dict[str, set[str]] | None, k_set: list[float],
                    out_path: Path) -> None:
    """Write the long/tidy k-sweep table: section,region,marker,k,threshold,count,pct
    -- one row per (section x region x marker x k). Whole-section rows use the literal
    region value '__section__' so section-level and region-level rows coexist in one
    tidy file."""
    rows = []
    for sl, markers in section_stats.items():
        for marker, st in markers.items():
            for k in k_set:
                thr = _threshold_at_k(st, k)
                cnt = _count_at_k(st, k)
                pct = (100.0 * cnt / st.n_classifiable) if st.n_classifiable else 0.0
                rows.append({"section": sl, "region": "__section__", "marker": marker,
                             "k": k, "threshold": thr, "count": cnt, "pct": pct})
            if region_groups:
                for group_name, acronyms in region_groups.items():
                    bg_in, _mask = region_stats_for_group(st, acronyms)
                    denom = int(bg_in.size)
                    for k in k_set:
                        thr = _threshold_at_k(st, k)
                        cnt = int((bg_in >= thr).sum()) if denom else 0
                        pct = 100.0 * cnt / denom if denom else 0.0
                        rows.append({"section": sl, "region": group_name, "marker": marker,
                                     "k": k, "threshold": thr, "count": cnt, "pct": pct})
    df_out = pd.DataFrame(rows, columns=["section", "region", "marker", "k", "threshold", "count", "pct"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_path, index=False)
    print(f"wrote -> {out_path}")


def write_figure(section_stats: dict[str, dict[str, SectionMarkerStats]],
                  region_groups: dict[str, set[str]], k_set: list[float],
                  marker_names: list[str], anchor_name: str, fig_path: Path) -> None:
    """Two-panel grouped-bar figure: (A) marker+ count, (B) marker+ as % of anchor.
    Grouped bars across sections for the requested --regions groups; bar height =
    count at the MIDDLE k of the swept set; whiskers span strict (largest k, fewest
    positives) <-> lenient (smallest k, most positives)."""
    if not region_groups:
        sys.exit("ERROR: --figure requires --regions (the figure is a per-region grouped bar chart).")

    sections = list(section_stats.keys())
    if not sections:
        sys.exit("ERROR: no sections to plot.")
    k_sorted = sorted(k_set)
    k_lo, k_hi = k_sorted[0], k_sorted[-1]
    k_mid = k_sorted[len(k_sorted) // 2]

    # first declared non-anchor marker actually present anywhere in the data.
    present_markers = {m for markers in section_stats.values() for m in markers}
    marker = next((m for m in marker_names if m in present_markers), None)
    if marker is None:
        sys.exit("ERROR: no marker data available to plot.")
    if len(present_markers) > 1:
        print(f"  note: multiple markers present ({sorted(present_markers)}); "
              f"figure plots marker={marker!r} only (config-lite: one figure per run).")

    x = np.arange(len(sections))
    n_groups = len(region_groups)
    width = 0.8 / max(n_groups, 1)
    palette = plt.get_cmap("tab10").colors

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(13.5, 5.2))
    for i, (group_name, acronyms) in enumerate(region_groups.items()):
        mid_vals, lo_vals, hi_vals, denom_vals = [], [], [], []
        for sl in sections:
            st = section_stats[sl].get(marker)
            if st is None:
                mid_vals.append(0.0); lo_vals.append(0.0); hi_vals.append(0.0); denom_vals.append(0)
                continue
            bg_in, _mask = region_stats_for_group(st, acronyms)
            denom = int(bg_in.size)
            def _cnt(k: float) -> int:
                thr = _threshold_at_k(st, k)
                return int((bg_in >= thr).sum()) if denom else 0
            mid_vals.append(_cnt(k_mid)); lo_vals.append(_cnt(k_hi)); hi_vals.append(_cnt(k_lo))
            denom_vals.append(denom)
        mid_arr = np.array(mid_vals, dtype=float)
        lo_arr = np.array(lo_vals, dtype=float)   # strict end (largest k -> fewest positives)
        hi_arr = np.array(hi_vals, dtype=float)   # lenient end (smallest k -> most positives)
        denom_arr = np.array(denom_vals, dtype=float)
        off = (i - (n_groups - 1) / 2.0) * width
        color = palette[i % len(palette)]
        axA.bar(x + off, mid_arr, width, color=color, label=group_name,
                yerr=[mid_arr - lo_arr, hi_arr - mid_arr], capsize=3, error_kw=dict(lw=1, ecolor="#333"))
        safe_denom = np.where(denom_arr == 0, 1, denom_arr)
        pmid = 100.0 * mid_arr / safe_denom
        plo = 100.0 * lo_arr / safe_denom
        phi = 100.0 * hi_arr / safe_denom
        axB.bar(x + off, pmid, width, color=color, label=group_name,
                yerr=[pmid - plo, phi - pmid], capsize=3, error_kw=dict(lw=1, ecolor="#333"))

    for ax, ttl, yl in [(axA, f"{marker}+ cell count", f"{marker}+ cells"),
                        (axB, f"{marker}+ as % of {anchor_name} (reactivation fraction)",
                         f"% {marker}+ / {anchor_name}")]:
        ax.set_title(ttl, fontsize=11, weight="bold")
        ax.set_ylabel(yl)
        ax.set_xticks(x)
        ax.set_xticklabels(sections, rotation=20, ha="right", fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        ax.legend(title="region", fontsize=9)
    fig.suptitle(f"k-sweep region readout (bar = k{k_mid:g}, whiskers = k{k_hi:g}↔k{k_lo:g})",
                 fontsize=12, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(fig_path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"figure -> {fig_path}")


# ---------------------------------------------------------------------------
# Self-test (synthetic data, no real QuPath project needed)
# ---------------------------------------------------------------------------

def _build_synthetic_percell_tsv(path: Path, marker_names: list[str], n_bg: int = 60,
                                  n_pos: int = 10, seed: int = 0, n_excluded_high: int = 5,
                                  region_present: str = "LA", region_other: str = "VISp1") -> dict:
    """Writes a synthetic per-cell TSV with the real schema (class, region_label,
    nucleus_area_um2, centroid_x_px, centroid_y_px, <marker>_bgsub) and returns the
    ground-truth values used by the self-test assertions. Deterministic (seeded)."""
    rng = np.random.default_rng(seed)
    bg_vals = rng.normal(loc=0.0, scale=20.0, size=n_bg)
    pos_vals = rng.normal(loc=400.0, scale=15.0, size=n_pos)  # well-separated "positive" tail
    all_vals = np.concatenate([bg_vals, pos_vals])
    regions = ([region_present] * (n_bg // 2) + [region_other] * (n_bg - n_bg // 2) +
               [region_present] * (n_pos // 2) + [region_other] * (n_pos - n_pos // 2))

    rows = []
    for i, (v, reg) in enumerate(zip(all_vals, regions)):
        row = {"class": "Negative", "region_label": reg, "nucleus_area_um2": 40.0,
               "centroid_x_px": float(i), "centroid_y_px": float(i)}
        for m in marker_names:
            row[f"{m}_bgsub"] = float(v)
        rows.append(row)
    # Excluded cells with extreme high bgsub -- must NOT affect derivation or counts.
    for i in range(n_excluded_high):
        row = {"class": "Excluded", "region_label": region_other, "nucleus_area_um2": 40.0,
               "centroid_x_px": float(1000 + i), "centroid_y_px": float(1000 + i)}
        for m in marker_names:
            row[f"{m}_bgsub"] = 1.0e6
        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(path, sep="\t", index=False)
    return {"bg_vals": bg_vals, "pos_vals": pos_vals, "all_vals": all_vals,
            "n_bg": n_bg, "n_pos": n_pos,
            "region_present": region_present, "region_other": region_other}


def _self_test() -> None:
    print("Running --self-test (synthetic per-cell TSVs, no real QuPath project needed)...")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # (a) threshold(k) == median + k*1.4826*MAD exactly, against an independent calc.
        vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 100.0])
        med_expected = np.median(vals)
        mad_expected = np.median(np.abs(vals - med_expected))
        for k in (0.0, 1.5, 3.0):
            expected = med_expected + k * 1.4826 * mad_expected
            got = robust_threshold(vals, k)
            assert np.isclose(got, expected), f"(a) threshold mismatch at k={k}: {got} != {expected}"
        assert np.isclose(np.median([1, 2, 3, 4]), 2.5), "(a) even-n median must be linear-interpolated"
        print("  (a) PASS: robust_threshold == median + k*1.4826*MAD (independent check)")

        # 1-marker synthetic set -- also exercises the TSV load path.
        tsv1 = tmp_path / "wBA_s1_MIP.ome.tiff - wBA_s1__id1__percell_export.tsv"
        gt1 = _build_synthetic_percell_tsv(tsv1, ["TdT"], seed=1)
        assert section_label(tsv1) == "wBA_s1", f"section_label mismatch: {section_label(tsv1)}"
        df1 = load_percell(tsv1)
        markers1 = markers_in_df(df1)
        assert markers1 == ["TdT"], f"(e) expected ['TdT'], got {markers1}"
        stats1 = analyze_section(df1, markers1)
        st = stats1["TdT"]

        # (c) Excluded cells removed from BOTH the derivation population AND the counts.
        classifiable_expected = gt1["n_bg"] + gt1["n_pos"]
        assert st.n_classifiable == classifiable_expected, (
            f"(c) classifiable population must EXCLUDE the injected Excluded rows: "
            f"expected {classifiable_expected}, got {st.n_classifiable}")
        med_direct = np.median(gt1["all_vals"])
        mad_direct = np.median(np.abs(gt1["all_vals"] - med_direct))
        assert np.isclose(st.median, med_direct) and np.isclose(st.robust_sd, 1.4826 * mad_direct), (
            "(c) injecting extra high-bgsub Excluded cells must not shift median/MAD derivation")
        print("  (c) PASS: Excluded cells removed from both threshold derivation and counts")

        # (b) positive count is monotonically non-increasing as k increases.
        k_sweep = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
        counts = [_count_at_k(st, k) for k in k_sweep]
        assert all(counts[i] >= counts[i + 1] for i in range(len(counts) - 1)), (
            f"(b) counts must be monotonically non-increasing as k increases, got {counts}")
        print(f"  (b) PASS: counts monotonically non-increasing across k={k_sweep} -> {counts}")

        # (d) region filtering: present region matches a manual count; absent region -> 0.
        present_acr = gt1["region_present"]
        bg_in_present, _mask = region_stats_for_group(st, {present_acr})
        manual_mask = ((df1["class"] != "Excluded") & df1["TdT_bgsub"].notna() &
                        (df1["acronym"] == present_acr))
        manual_bg = df1.loc[manual_mask, "TdT_bgsub"].to_numpy(dtype=float)
        assert bg_in_present.size == manual_bg.size, (
            f"(d) present-region count mismatch: {bg_in_present.size} != {manual_bg.size}")
        bg_absent, _mask2 = region_stats_for_group(st, {"NOT_A_REAL_REGION_XYZ"})
        assert bg_absent.size == 0, "(d) an absent region must report 0, not raise"
        cnt_absent = int((bg_absent >= _threshold_at_k(st, 2.5)).sum()) if bg_absent.size else 0
        assert cnt_absent == 0, "(d) absent-region count must be 0"
        print("  (d) PASS: present region reproduces a manual count; absent region -> 0 (no crash)")

        # (e) marker-agnostic: 2-marker synthetic set runs identically.
        tsv2 = tmp_path / "wBA_s2_MIP.ome.tiff - wBA_s2__id2__percell_export.tsv"
        gt2 = _build_synthetic_percell_tsv(tsv2, ["TdT", "Fos"], seed=2)
        df2 = load_percell(tsv2)
        markers2 = markers_in_df(df2)
        assert markers2 == ["Fos", "TdT"], f"(e) expected ['Fos', 'TdT'], got {markers2}"
        stats2 = analyze_section(df2, markers2)
        assert set(stats2.keys()) == {"Fos", "TdT"}
        for m in ("Fos", "TdT"):
            assert stats2[m].n_classifiable == gt2["n_bg"] + gt2["n_pos"], (
                f"(e) marker {m} classifiable population mismatch")
        print("  (e) PASS: engine runs identically on a 1-marker and a 2-marker declared set")

        # k-set builder sanity (union of k_robust, dedup, sort) -- used by main().
        k_set = build_k_set(2.0, 3.0, 0.25, None, 3.0)
        assert k_set == [2.0, 2.25, 2.5, 2.75, 3.0], f"unexpected k_set: {k_set}"
        k_set2 = build_k_set(2.0, 3.0, 0.5, None, 2.75)
        assert k_set2 == [2.0, 2.5, 2.75, 3.0], f"unexpected k_set with k_robust union: {k_set2}"

        # region-group parsing sanity.
        groups = parse_regions("LA,BLA,BMA", amygdala_groups=True)
        assert groups["LA"] == {"LA"} and groups["BLA"] == {"BLA", "BLAa", "BLAp", "BLAv"}
        groups_exact = parse_regions("LA,BLA", amygdala_groups=False)
        assert groups_exact == {"LA": {"LA"}, "BLA": {"BLA"}}, "non-amygdala-groups tokens must be exact acronyms"

    print("\nself-test PASSED: all proofs (a)-(e) hold.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--results-dir", type=Path, default=None,
                     help="QuPath project results/ dir containing *__percell_export.tsv "
                          "(required unless --self-test)")
    ap.add_argument("--pipeline", type=Path, default=Path("pipeline.yml"),
                     help="pipeline.yml sidecar config (default: ./pipeline.yml)")
    ap.add_argument("--k-min", type=float, default=2.0, help="sweep range start (default: 2.0)")
    ap.add_argument("--k-max", type=float, default=3.0, help="sweep range end (default: 3.0)")
    ap.add_argument("--k-step", type=float, default=0.25, help="sweep range step (default: 0.25)")
    ap.add_argument("--k-values", type=str, default=None,
                     help='explicit comma-separated k list, e.g. "2.0,2.5,3.0" '
                          '-- overrides --k-min/--k-max/--k-step')
    ap.add_argument("--regions", type=str, default=None,
                     help='comma list of region tokens/groups for the region-level readout, '
                          'e.g. "LA,BLA,BMA"')
    ap.add_argument("--amygdala-groups", action="store_true",
                     help="expand LA/BLA/BMA tokens in --regions to their built-in amygdala "
                          "nucleus acronym sets (LA={LA}, BLA={BLA,BLAa,BLAp,BLAv}, "
                          "BMA={BMA,BMAa,BMAp})")
    ap.add_argument("--out", type=Path, default=None,
                     help="write the tidy section,region,marker,k,threshold,count,pct CSV")
    ap.add_argument("--figure", type=Path, default=None,
                     help="write a two-panel grouped-bar PNG (count + %% of anchor); requires --regions")
    ap.add_argument("--self-test", action="store_true",
                     help="run the built-in synthetic-data self-test and exit (no --results-dir needed)")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    if args.results_dir is None:
        ap.error("--results-dir is required (unless --self-test)")
    if args.figure is not None and args.regions is None:
        ap.error("--figure requires --regions (the figure is a per-region grouped bar chart)")

    cfg = load_pipeline_config(args.pipeline)
    k_set = build_k_set(args.k_min, args.k_max, args.k_step, args.k_values, cfg["k_robust"])
    print(f"k-set (pipeline.yml k_robust={cfg['k_robust']:g} marked *current*): "
          + ", ".join(f"{k:g}" for k in k_set))
    print(f"Declared marker(s) (pipeline.yml, D-01/D-04): {cfg['marker_names']} "
          f"| anchor: {cfg['anchor_name']}")

    files = sorted(glob.glob(str(args.results_dir / "*__percell_export.tsv")))
    if not files:
        sys.exit(f"ERROR: no *__percell_export.tsv files found under {args.results_dir}")
    print(f"Found {len(files)} section export(s) under {args.results_dir}")

    section_stats: dict[str, dict[str, SectionMarkerStats]] = {}
    for f in files:
        path = Path(f)
        sl = section_label(path)
        df = load_percell(path)
        present_markers = [m for m in cfg["marker_names"] if f"{m}_bgsub" in df.columns]
        missing_markers = [m for m in cfg["marker_names"] if m not in present_markers]
        if missing_markers:
            print(f"  {sl}: marker(s) absent from this export, skipped: {missing_markers}")
        section_stats[sl] = analyze_section(df, present_markers)

    print_section_table(section_stats, k_set, cfg["k_robust"])

    region_groups: dict[str, set[str]] | None = None
    if args.regions:
        region_groups = parse_regions(args.regions, args.amygdala_groups)
        print_region_table(section_stats, region_groups, k_set, cfg["k_robust"])

    if args.out is not None:
        write_tidy_csv(section_stats, region_groups, k_set, args.out)

    if args.figure is not None:
        write_figure(section_stats, region_groups, k_set, cfg["marker_names"],
                     cfg["anchor_name"], args.figure)


if __name__ == "__main__":
    main()
