#!/usr/bin/env python3
"""cockpit_animal.py -- animal-level rollup + stats-ready export shapes (cockpit increment 3).

Rolls the per-slice, per-region readout emitted by ``cockpit_regions.build_readout``
(increment 2) up to the **animal** level, stacks animals into one group-ready table, computes
the full engram-overlap metric family, and (Task 2) emits a tidy LONG table plus Prism-friendly
WIDE pivots. This module exists to structurally enforce CLAUDE.md's stats convention --
*aggregate to the animal level before any group comparison; sections are not independent.*

POOL-THEN-RECOMPUTE (load-bearing, CLAUDE.md pseudoreplication rule): every animal-level count
is a SUM of per-slice counts/areas; every density and every ratio metric is then RECOMPUTED
from those pooled sums. A ratio is never averaged across slices -- ``mean(D_i/T_i)`` differs
from (and is statistically wrong versus) ``sum(D_i)/sum(T_i)`` whenever per-slice N varies, and
sections are not independent replicates (they are serial samples of the same animal). The
self-test proves the two numbers differ on synthetic data with unequal per-slice N.

TAGGED / ACTIVITY ROLE RESOLUTION (D-1, config-derived, never positional):
  Marker declaration order in pipeline.yml is NOT the role order -- reading ``markers[0]`` as
  "the tagged marker" would silently invert every metric on a project (like M3) that declares
  Fos before TdT. Resolution order, first match wins:
    1. Explicit override -- ``--tagged-marker`` / ``--activity-marker`` (or the equivalent
       ``resolve_roles(config, tagged=..., activity=...)`` arguments).
    2. Optional per-marker ``role: tagged`` / ``role: activity`` key in pipeline.yml, if present
       (additive, forward-compatible; no fixture needs to declare it).
    3. Compartment rule -- exactly one marker with ``compartment in {whole-cell, cytoplasmic}``
       is TAGGED (the engram reporter is a cytosolic/whole-cell fluorophore in this pipeline);
       exactly one with ``compartment: nuclear`` is ACTIVITY (the recall readout is a nuclear
       IEG). M3 -> tagged=TdT, activity=Fos, even though pipeline.yml declares Fos first.
    4. Otherwise: raise, naming both override flags. Never guess by position.
  Single-marker configs (e.g. a TdT-only slice-set) resolve via the same compartment rule and
  only emit that one component rate (``tagging_rate`` or ``activity_rate``) -- no Double+-
  dependent metric is ever computed or referenced.

METRIC FAMILY (locked names, marker-agnostic). N = denominator cells, T = tagged+ count,
A = activity+ count, D = Double+ count; 2x2 cells a=D, b=T-D, c=A-D, d=N-T-A+D:

  tagging_rate            T/N                                       DAPI-dependent (has N)
  activity_rate           A/N                                       DAPI-dependent (has N)
  reactivation_rate       D/T  = P(activity+|tagged+)                N-immune
  reverse_rate            D/A  = P(tagged+|activity+)                N-immune
  overlap_above_chance    (D*N)/(T*A) = reactivation_rate/activity_rate   PRIMARY, DAPI-dependent
  log2_odds_ratio         log2(a*d / (b*c))                          NaN if any 2x2 cell is 0
  log2_odds_ratio_hc      same, all four cells +0.5 (Haldane-Anscombe)    always finite
  jaccard                 D/(T+A-D)                                  N-immune

``d < 0`` (possible if N under-counts relative to T+A) -> both odds ratios NaN for that row,
plus one counted warning. Pair metrics (everything above ``tagging_rate``/``activity_rate``)
are only computed when BOTH a tagged and an activity role resolve for a project; otherwise the
columns are simply absent (never a NaN wall) with one explanatory printed line.

PARKED-GATE CAVEAT (surfaced here, not buried): every metric with N in its denominator
(tagging_rate, activity_rate, overlap_above_chance, both odds ratios) inherits whatever DAPI
over-detection the white-matter/ventricle QC gates would have caught -- those gates are
currently parked as advisory (``cockpit_checks.GateThresholds.advisory_gates``), i.e. DAPI is
known to be over-detected in white matter (cc ~4.8k/mm^2 vs cortex ~4.0k/mm^2). Inflated N
deflates activity_rate and therefore INFLATES overlap_above_chance. reactivation_rate,
reverse_rate and jaccard carry no N and are unaffected.
  Switching ``--n-source`` to ``classifiable`` does NOT fix this: on the M3 fixture the
  classifiable joint population differs from the raw anchor (DAPI) count by only 0.005%
  (recon, this plan) -- classifiable filtering removes ``Excluded`` + non-finite bg-sub rows
  only, it does NOT remove haze-detected nuclei. It buys the correct joint-population
  denominator, nothing more. The actual levers are re-arming the white-matter gate, raising
  ``k_robust``, or lowering ``cellExpansionMicrons`` -- named here so the number this module
  reports is never read as if it were already clean.

READ-ONLY. This module only globs/reads artifacts already on disk under
``<project>/results/`` (via ``cockpit_regions.build_readout`` and
``k_sweep_readout.load_percell``) plus ``<project>/pipeline.yml``. It never launches QuPath,
never re-runs detection/classification/export, and never writes inside a project directory --
all generated tables land under an operator-chosen ``--out-dir`` (default ``results/animal``,
gitignored).

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/cockpit_animal.py --self-test
  conda run -n braian python scripts/cockpit_animal.py \\
      --project "M3 Hipp1 072326 7scene/M3 Hipp1 072326 7 Scene QuPath" \\
      --regions CA1,CA3,DG,PIR,STRd --out-dir results/animal/m3
"""
from __future__ import annotations

import argparse
import glob
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cockpit_checks as cc  # noqa: E402  resolve_marker_tokens / find_slices -- do not fork
import cockpit_regions as creg  # noqa: E402  Config / build_readout (increment 2) -- do not fork
import k_sweep_readout as ksr  # noqa: E402  load_percell / classifiable_mask -- do not fork


# ---------------------------------------------------------------------------
# D-1: tagged / activity role resolution -- config-derived, never positional
# ---------------------------------------------------------------------------
@dataclass
class Roles:
    tagged: str | None
    activity: str | None


_ROLE_OVERRIDE_FLAGS = "--tagged-marker / --activity-marker (or resolve_roles(tagged=, activity=))"
_COMPARTMENT_TAGGED = {"whole-cell", "cytoplasmic"}
_COMPARTMENT_ACTIVITY = {"nuclear"}


def resolve_roles(config: creg.Config, tagged: str | None = None,
                  activity: str | None = None) -> Roles:
    """D-1 resolution order: explicit override > pipeline.yml `role:` key > compartment rule >
    fail loud. Never infers a role from marker declaration order."""
    # 1. Explicit override wins over everything.
    if tagged is not None or activity is not None:
        for label, name in (("tagged", tagged), ("activity", activity)):
            if name is not None and name not in config.marker_names:
                raise ValueError(
                    f"--{label}-marker '{name}' is not a declared marker "
                    f"({config.marker_names})")
        return Roles(tagged=tagged, activity=activity)

    # 2. Optional per-marker `role:` key in pipeline.yml.
    role_tagged = [m["name"] for m in config.markers if str(m.get("role", "")).lower() == "tagged"]
    role_activity = [m["name"] for m in config.markers
                     if str(m.get("role", "")).lower() == "activity"]
    if role_tagged or role_activity:
        if len(role_tagged) > 1 or len(role_activity) > 1:
            raise ValueError(
                f"ambiguous 'role:' keys in pipeline.yml (tagged={role_tagged}, "
                f"activity={role_activity}); disambiguate with {_ROLE_OVERRIDE_FLAGS}")
        return Roles(tagged=role_tagged[0] if role_tagged else None,
                    activity=role_activity[0] if role_activity else None)

    # 3. Compartment rule (config-derived, never name-derived).
    tagged_candidates = [m["name"] for m in config.markers
                        if m.get("compartment") in _COMPARTMENT_TAGGED]
    activity_candidates = [m["name"] for m in config.markers
                           if m.get("compartment") in _COMPARTMENT_ACTIVITY]
    if len(tagged_candidates) > 1 or len(activity_candidates) > 1:
        raise ValueError(
            f"ambiguous tagged/activity roles by compartment (tagged candidates="
            f"{tagged_candidates}, activity candidates={activity_candidates}); "
            f"disambiguate with {_ROLE_OVERRIDE_FLAGS}")
    t = tagged_candidates[0] if tagged_candidates else None
    a = activity_candidates[0] if activity_candidates else None

    # 4. Otherwise fail loud -- never guess by position.
    if t is None and a is None:
        raise ValueError(
            f"cannot resolve tagged/activity roles for markers {config.marker_names} "
            f"(no role: key, no unambiguous compartment match); specify {_ROLE_OVERRIDE_FLAGS}")
    return Roles(tagged=t, activity=a)


# ---------------------------------------------------------------------------
# D-4: classifiable-N per region (per-cell derived, pooled ("both") level only -- recon 3)
# ---------------------------------------------------------------------------
def classifiable_n_by_region(project_dir: Path, config: creg.Config,
                             regions: list[str] | None = None) -> pd.DataFrame:
    """Per-slice classifiable joint-population N, rolled up over the SAME
    ``creg.included_leaves(...)`` frontier set increment 2 uses -- zero denominator drift.

    Returns columns [animal, slice_id, region_acronym, N_classifiable]. Empty (not an error)
    when the project has no percell export at all. ``percell_export.tsv``'s ``region_label``
    is a bare acronym with no hemisphere prefix (recon), so this is only ever a POOLED
    (hemisphere == 'both') quantity -- callers must not try to split it L/R.
    """
    project_dir = Path(project_dir)
    rdir = project_dir / "results"
    percell_files = sorted(glob.glob(str(rdir / "*percell_export.tsv")))
    empty = pd.DataFrame(columns=["animal", "slice_id", "region_acronym", "N_classifiable"])
    if not percell_files:
        return empty

    region_table_files = {ksr.section_label(Path(p)): Path(p)
                          for p in glob.glob(str(rdir / "*__region_table.tsv"))}
    ontology = creg.load_ontology(project_dir)
    excl_closure = creg.excluded_closure(ontology, config.exclude_acronyms)

    rows: list[dict] = []
    for pf in percell_files:
        pf = Path(pf)
        label = ksr.section_label(pf)
        m = creg._SLICE_RE.match(label)
        animal = config.animal or (m.group("animal") if m else label)
        slice_id = f"s{m.group('n')}" if m else label

        rt_path = region_table_files.get(label)
        if rt_path is None:
            continue  # no matching region_table for this slice -- frontier undefined, skip

        rt = creg.load_region_table(rt_path, project_dir, config)
        frontier = creg.frontier_leaves(ontology, rt.present)

        df = ksr.load_percell(pf)
        tokens = cc.resolve_marker_tokens(df, config)
        if not tokens:
            continue
        masks = [ksr.classifiable_mask(df, tok) for tok in tokens.values()]
        joint = masks[0]
        for mk in masks[1:]:
            joint = joint & mk
        sub = df.loc[joint]

        region_list = regions if regions is not None else sorted(frontier - excl_closure)
        for region in region_list:
            if region not in ontology:
                continue
            leaves = creg.included_leaves(ontology, rt.present, region, excl_closure, frontier)
            if not leaves:
                continue
            n = int(sub["acronym"].isin(leaves).sum())
            rows.append({"animal": animal, "slice_id": slice_id,
                        "region_acronym": region, "N_classifiable": n})

    if not rows:
        return empty
    return pd.DataFrame(rows, columns=["animal", "slice_id", "region_acronym", "N_classifiable"])


# ---------------------------------------------------------------------------
# Rollup core: pool per-slice counts/areas, recompute densities and metrics
# ---------------------------------------------------------------------------
def _safe_div(numer: np.ndarray, denom: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denom > 0, numer / denom, np.nan)


def rollup_animal(project_dir: Path, regions: list[str] | None = None,
                  roles: Roles | None = None, n_source: str = "auto") -> pd.DataFrame:
    """Pool increment 2's per-slice readout to the animal level and recompute the metric
    family. Never `.mean()`s a ratio -- only counts/areas are ever aggregated across slices."""
    if n_source not in ("auto", "anchor", "classifiable"):
        raise ValueError(f"n_source must be one of auto/anchor/classifiable, got {n_source!r}")

    project_dir = Path(project_dir)
    config = creg.load_pipeline_config(project_dir)
    if roles is None:
        roles = resolve_roles(config)

    df = creg.build_readout(project_dir, regions=regions)
    if df.empty:
        raise ValueError(f"{project_dir}: build_readout returned no rows (check --regions / project)")

    anchor = config.anchor_name
    count_cols = [c for c in df.columns if c.endswith("_count")]
    group_cols = ["animal", "region_acronym", "hemisphere"]

    agg_kwargs = {
        "area_mm2": ("area_mm2", "sum"),
        "region_name": ("region_name", "first"),
        "level": ("level", "first"),
        "n_slices": ("slice_id", "nunique"),
        "projects": ("project", lambda s: ",".join(sorted(set(s)))),
    }
    agg_kwargs.update({c: (c, "sum") for c in count_cols})
    grouped = df.groupby(group_cols, as_index=False).agg(**agg_kwargs)

    area = grouped["area_mm2"].to_numpy(dtype=float)
    grouped[f"{anchor}_density"] = _safe_div(grouped[f"{anchor}_count"].to_numpy(dtype=float), area)
    for m in config.marker_names:
        grouped[f"{m}+_density"] = _safe_div(grouped[f"{m}+_count"].to_numpy(dtype=float), area)
    if config.emit_double:
        grouped["Double+_density"] = _safe_div(
            grouped["Double+_count"].to_numpy(dtype=float), area)

    # D-4: N (denominator) source.
    grouped["N"] = grouped[f"{anchor}_count"].astype(float)
    grouped["N_source"] = "anchor_count"

    if n_source in ("auto", "classifiable"):
        n_df = classifiable_n_by_region(project_dir, config, regions=regions)
        if not n_df.empty:
            n_agg = (n_df.groupby(["animal", "region_acronym"], as_index=False)["N_classifiable"]
                     .sum())
            grouped = grouped.merge(n_agg, on=["animal", "region_acronym"], how="left")
        else:
            grouped["N_classifiable"] = np.nan

        both_mask = grouped["hemisphere"] == "both"
        if n_source == "classifiable":
            grouped["N_source"] = "classifiable"
            grouped.loc[both_mask, "N"] = grouped.loc[both_mask, "N_classifiable"]
            grouped.loc[~both_mask, "N"] = np.nan
        else:  # auto
            has_n = both_mask & grouped["N_classifiable"].notna()
            grouped.loc[has_n, "N"] = grouped.loc[has_n, "N_classifiable"]
            grouped.loc[has_n, "N_source"] = "classifiable"
        grouped = grouped.drop(columns=["N_classifiable"])

    add_metrics(grouped, config, roles)
    return grouped


def add_metrics(df: pd.DataFrame, config: creg.Config, roles: Roles) -> pd.DataFrame:
    """Adds the eight-column metric family in place. Skips the pair-metrics entirely (columns
    absent, one printed line) when fewer than two roles resolve -- never a NaN wall."""
    N = df["N"].to_numpy(dtype=float)

    T = None
    if roles.tagged:
        T = df[f"{roles.tagged}+_count"].to_numpy(dtype=float)
        df["tagging_rate"] = _safe_div(T, N)

    A = None
    if roles.activity:
        A = df[f"{roles.activity}+_count"].to_numpy(dtype=float)
        df["activity_rate"] = _safe_div(A, N)

    if T is not None and A is not None and config.emit_double:
        D = df["Double+_count"].to_numpy(dtype=float)
        df["reactivation_rate"] = _safe_div(D, T)
        df["reverse_rate"] = _safe_div(D, A)
        df["overlap_above_chance"] = _safe_div(D * N, T * A)

        a, b, c, d = D, T - D, A - D, N - T - A + D
        d_valid = d >= 0
        n_bad = int((~d_valid).sum())
        if n_bad:
            print(f"  WARNING: {n_bad} row(s) have d = N-T-A+D < 0 (N under-count relative to "
                  f"T+A) -- log2_odds_ratio(_hc) set to NaN for those rows", file=sys.stderr)

        all_pos = d_valid & (a > 0) & (b > 0) & (c > 0) & (d > 0)
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio = (a * d) / (b * c)
            log_or = np.log2(ratio)
        df["log2_odds_ratio"] = np.where(all_pos, log_or, np.nan)

        ah, bh, ch, dh = a + 0.5, b + 0.5, c + 0.5, d + 0.5
        with np.errstate(divide="ignore", invalid="ignore"):
            ratio_hc = (ah * dh) / (bh * ch)
            log_or_hc = np.log2(ratio_hc)
        df["log2_odds_ratio_hc"] = np.where(d_valid, log_or_hc, np.nan)

        df["jaccard"] = _safe_div(D, T + A - D)
    else:
        print("  Fewer than 2 resolved roles (or single-marker config) -- skipping pair metrics "
              "(reactivation_rate/reverse_rate/overlap_above_chance/log2_odds_ratio(_hc)/jaccard); "
              "columns absent, not NaN.")
    return df


# ---------------------------------------------------------------------------
# Self-test (synthetic fixture -- no real data needed)
# ---------------------------------------------------------------------------
def _percell_rows(acronym_counts: dict[str, int], marker_names: list[str]) -> list[dict]:
    rows = []
    i = 0
    for acr, n in acronym_counts.items():
        for _ in range(n):
            row = {"class": "Negative", "region_label": acr, "nucleus_area_um2": 40.0,
                  "centroid_x_px": float(i), "centroid_y_px": float(i)}
            for m in marker_names:
                row[f"{m}_bgsub"] = 50.0
            rows.append(row)
            i += 1
    return rows


def _write_region_table(proj: Path, animal: str, slice_name: str, cats: list[str],
                        rows: dict[tuple[str, str], tuple[float, dict[str, int]]]) -> None:
    header = ["acronym", "hemisphere", "area_mm2"] + [f"{c}_count" for c in cats]
    lines = ["\t".join(header)]
    for (acr, hemi), (area, counts) in rows.items():
        line = [acr, hemi, f"{area:.6f}"] + [str(counts.get(c, 0)) for c in cats]
        lines.append("\t".join(line))
    fname = f"{animal}_{slice_name}_MIP.ome.tiff - {animal}_{slice_name}__id1__region_table.tsv"
    (proj / "results" / fname).write_text("\n".join(lines) + "\n")


def _write_synthetic_project(base: Path, animal: str, two_marker: bool,
                            with_percell: bool) -> Path:
    """A project with >=2 slices whose per-slice N differs enough that the pooled ratio
    provably differs from the mean of per-slice ratios (the anti-averaging proof)."""
    proj = base / f"synthetic_{animal}"
    (proj / "results").mkdir(parents=True, exist_ok=True)
    (proj / "allen_mouse_10um_java-Ontology.json").write_text(
        __import__("json").dumps(creg._synthetic_ontology_json()))

    # Declared order Fos-then-TdT (mirrors real M3 pipeline.yml) -- proves role resolution is
    # NOT positional: TdT is markers[1] yet must resolve to "tagged".
    markers = []
    if two_marker:
        markers.append({"name": "Fos", "channel": "AF488-T3", "compartment": "nuclear"})
    markers.append({"name": "TdT", "channel": "AF568-T2", "compartment": "whole-cell"})
    (proj / "pipeline.yml").write_text(yaml.safe_dump({
        "anchor": {"name": "DAPI", "channel": "DAPI-T4"},
        "markers": markers,
        "exclude_acronyms": ["DG-sg", "VS"],
        "animal": animal,
    }, sort_keys=False))

    cats = ["DAPI"] + (["Fos+", "TdT+", "Double+"] if two_marker else ["TdT+"])

    def _c(dapi: int, tdt: int, fos: int = 0, dbl: int = 0) -> dict[str, int]:
        d = {"DAPI": dapi, "TdT+": tdt}
        if two_marker:
            d["Fos+"] = fos
            d["Double+"] = dbl
        return d

    # LA: unequal per-slice N so pooled D/T != mean(D_i/T_i). CA1: single-hemisphere (Left).
    # BLA: Right-only, engineered so pooled b = T-D == 0 exactly (log2_odds_ratio NaN, hc finite).
    slice_specs: dict[str, dict[tuple[str, str], tuple[float, dict[str, int]]]] = {
        "s1": {
            ("LA", "Left"): (0.3, _c(100, 50, 30, 20)),
            ("LA", "Right"): (0.3, _c(80, 40, 24, 16)),
            ("CA1", "Left"): (1.0, _c(200, 60, 40, 24)),
            ("BLA", "Right"): (0.2, _c(50, 10, 10, 10)),
        },
        "s2": {
            ("LA", "Left"): (0.3, _c(200, 10, 8, 2)),
            ("LA", "Right"): (0.3, _c(150, 8, 6, 1)),
            ("CA1", "Left"): (1.0, _c(300, 15, 10, 3)),
            ("BLA", "Right"): (0.2, _c(40, 5, 5, 5)),
        },
    }
    percell_counts = {
        "s1": {"LA": 40, "CA1": 90, "BLA": 10},
        "s2": {"LA": 15, "CA1": 60, "BLA": 5},
    }
    marker_names_for_percell = ["Fos", "TdT"] if two_marker else ["TdT"]

    for slice_name, rows in slice_specs.items():
        _write_region_table(proj, animal, slice_name, cats, rows)
        if with_percell:
            pdf = pd.DataFrame(_percell_rows(percell_counts[slice_name], marker_names_for_percell))
            pname = (f"{animal}_{slice_name}_MIP.ome.tiff - "
                    f"{animal}_{slice_name}__id1__percell_export.tsv")
            pdf.to_csv(proj / "results" / pname, sep="\t", index=False)

    return proj


def _self_test() -> None:
    import tempfile

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("  PASS " if cond else "  FAIL ") + msg)
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # --- 2-marker animal, WITH percell -------------------------------------------------
        print("[self-test] 2-marker animal (Fos declared first, TdT second) + percell export")
        proj2 = _write_synthetic_project(base, "Animal2M", two_marker=True, with_percell=True)
        config2 = creg.load_pipeline_config(proj2)

        # (6) role resolution picks TdT (whole-cell) as tagged even though it is markers[1].
        roles2 = resolve_roles(config2)
        check(roles2.tagged == "TdT" and roles2.activity == "Fos",
              f"role resolution is compartment-derived, not positional (got {roles2})")

        # (7) ambiguous roles raise; explicit override wins.
        ambiguous_cfg = replace(config2, markers=[
            {"name": "Fos", "channel": "x", "compartment": "nuclear"},
            {"name": "Fos2", "channel": "y", "compartment": "nuclear"},
        ])
        try:
            resolve_roles(ambiguous_cfg)
            check(False, "ambiguous compartment roles must raise")
        except ValueError:
            check(True, "ambiguous compartment roles raise ValueError")
        override = resolve_roles(ambiguous_cfg, tagged="Fos", activity="Fos2")
        check(override.tagged == "Fos" and override.activity == "Fos2",
              "explicit override resolves an otherwise-ambiguous config")

        rolled2 = rollup_animal(proj2, regions=["LA", "CA1", "BLA"], roles=roles2)

        def val(region: str, hemi: str, col: str):
            sub = rolled2[(rolled2.region_acronym == region) & (rolled2.hemisphere == hemi)]
            return sub.iloc[0][col] if len(sub) else None

        # (1) anti-averaging proof: pooled ratio == sum(D)/sum(T) and != mean of per-slice ratios.
        per_slice = creg.build_readout(proj2, regions=["LA"])
        both_slices = per_slice[(per_slice.region_acronym == "LA") & (per_slice.hemisphere == "both")]
        per_slice_ratios = (both_slices["Double+_count"] / both_slices["TdT+_count"]).to_numpy()
        mean_of_ratios = float(np.mean(per_slice_ratios))
        pooled_ratio = float(val("LA", "both", "reactivation_rate"))
        d_sum = float(val("LA", "both", "Double+_count"))
        t_sum = float(val("LA", "both", "TdT+_count"))
        check(abs(pooled_ratio - d_sum / t_sum) < 1e-9,
              f"LA(both) reactivation_rate == pooled sum(D)/sum(T) ({pooled_ratio:.4f})")
        check(abs(pooled_ratio - mean_of_ratios) > 1e-6,
              f"LA(both) pooled ratio ({pooled_ratio:.4f}) != mean-of-per-slice-ratios "
              f"({mean_of_ratios:.4f}) -- anti-averaging proof")

        # (2) both == L + R; the rollup never sums L+R+both together.
        both_tdt = val("LA", "both", "TdT+_count")
        l_tdt = val("LA", "L", "TdT+_count")
        r_tdt = val("LA", "R", "TdT+_count")
        check(both_tdt == l_tdt + r_tdt, "LA both TdT+_count == L + R (hemisphere never mixed)")

        # (3) hand-computed metrics at LA(both): T=108, A=68, D=39, N(anchor)=530.
        check(l_tdt == 60 and r_tdt == 48, f"LA hemisphere sums as expected (L={l_tdt}, R={r_tdt})")
        n_anchor = val("LA", "both", "N")
        t_val, a_val, d_val = val("LA", "both", "TdT+_count"), val("LA", "both", "Fos+_count"), \
            val("LA", "both", "Double+_count")
        check(t_val == 108 and a_val == 68 and d_val == 39,
              f"LA(both) hand-computed pooled T/A/D ({t_val}/{a_val}/{d_val})")
        expected_tagging = t_val / n_anchor
        check(abs(val("LA", "both", "tagging_rate") - expected_tagging) < 1e-9,
              "tagging_rate == T/N (hand-computed)")

        # (4) overlap_above_chance == reactivation_rate / activity_rate.
        oac = val("LA", "both", "overlap_above_chance")
        rr = val("LA", "both", "reactivation_rate")
        ar = val("LA", "both", "activity_rate")
        check(abs(oac - rr / ar) < 1e-9, "overlap_above_chance == reactivation_rate / activity_rate")

        # (8) log2_odds_ratio NaN on a zero cell (BLA: pooled b = T-D == 0) while _hc stays finite.
        bla_or = val("BLA", "both", "log2_odds_ratio")
        bla_or_hc = val("BLA", "both", "log2_odds_ratio_hc")
        check(not np.isfinite(bla_or), "BLA(both) log2_odds_ratio is NaN on a zero 2x2 cell (b=0)")
        check(np.isfinite(bla_or_hc), "BLA(both) log2_odds_ratio_hc stays finite (Haldane-Anscombe)")

        # (8) N_source: classifiable for 'both' rows when percell exists.
        check(val("LA", "both", "N_source") == "classifiable",
              "N_source == 'classifiable' for a both-hemisphere row when percell exists")
        check(pd.isna(val("LA", "L", "N")) is False and val("LA", "L", "N_source") == "anchor_count",
              "N_source == 'anchor_count' for L/R rows (per-cell N is pooled-only, recon 3)")

        # --- 1-marker animal, WITHOUT percell -----------------------------------------------
        print("\n[self-test] 1-marker animal (TdT-only), no percell export")
        proj1 = _write_synthetic_project(base, "Animal1M", two_marker=False, with_percell=False)
        config1 = creg.load_pipeline_config(proj1)
        roles1 = resolve_roles(config1)
        check(roles1.tagged == "TdT" and roles1.activity is None,
              "1-marker config resolves tagged=TdT, activity=None")

        rolled1 = rollup_animal(proj1, regions=["LA", "CA1"], roles=roles1)
        cols1 = set(rolled1.columns)
        pair_cols = {"reactivation_rate", "reverse_rate", "overlap_above_chance",
                    "log2_odds_ratio", "log2_odds_ratio_hc", "jaccard"}
        check(not (pair_cols & cols1),
              "1-marker path has NO Double+/reactivation/overlap/odds-ratio/jaccard columns")
        check("Double+_count" not in cols1, "1-marker path has no Double+_count column")
        check("tagging_rate" in cols1 and "activity_rate" not in cols1,
              "1-marker path emits tagging_rate only")

        both1 = rolled1[rolled1.region_acronym == "LA"]
        check((both1["N_source"] == "anchor_count").all(),
              "N_source == 'anchor_count' everywhere when no percell export exists")

        # --- n_source variants ----------------------------------------------------------------
        print("\n[self-test] --n-source variants")
        rolled_anchor = rollup_animal(proj2, regions=["LA"], roles=roles2, n_source="anchor")
        check((rolled_anchor["N_source"] == "anchor_count").all(),
              "n_source='anchor' forces anchor_count everywhere")
        rolled_classif = rollup_animal(proj2, regions=["LA"], roles=roles2, n_source="classifiable")
        lr_rows = rolled_classif[rolled_classif.hemisphere.isin(["L", "R"])]
        check(lr_rows["N"].isna().all(),
              "n_source='classifiable' leaves L/R N as NaN (per-cell N is pooled-only)")

    print()
    if failures:
        print(f"SELF-TEST FAILED ({len(failures)} check(s)):")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("SELF-TEST PASSED")


# ---------------------------------------------------------------------------
# CLI (Task 2 extends this with stacking / export flags)
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--project", type=Path, action="append", default=[],
                    help="QuPath project dir (repeatable; holds pipeline.yml, results/).")
    ap.add_argument("--regions", type=str, default=None,
                    help="Comma-separated acronyms (default: all included leaves per project).")
    ap.add_argument("--self-test", action="store_true", help="Run the built-in self-test and exit.")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    ap.error("Task 2 adds the full CLI (stacking, groups, export). Use --self-test for now.")


if __name__ == "__main__":
    main()
