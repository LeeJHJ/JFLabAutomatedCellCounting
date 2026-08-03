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

PLOTTING (follow-up increment; a pre-analysis interpretation aid alongside the CSV export --
NOT publication figures, NOT statistics; see each plot_* docstring for the specific trap it
defends against):
  1. plot_region_ranking      -- regions ranked by ``overlap_above_chance``, displayed as
                                  log2(overlap_above_chance) on a LINEAR axis (a raw ratio on
                                  a linear axis hides depletion below 1.0x; a log-scaled axis
                                  has no honest bar baseline). Chance sits at 0, labeled
                                  "1.0x (chance)".
  2. plot_raw_vs_corrected    -- two panels, one shared region order, one shared diverging
                                  color encoding: raw reactivation_rate vs the same log2
                                  display transform. Guards the PVH trap (69% raw, only 1.4x
                                  above chance) -- NEVER a dual y-axis.
  3. plot_evidence_guard      -- Double+_count (or {tagged}+_count, 1-marker) vs N on a log
                                  x-axis as dots/lollipops, never bars (a log axis has no
                                  honest bar baseline). Sub-``min_cells`` regions are drawn
                                  de-emphasised (neutral, low alpha) but stay labeled -- never
                                  silently dropped.
  4. plot_slice_spread        -- per-slice reactivation dots vs the POOLED (sum D / sum T,
                                  reported) value vs the mean-of-slices (NOT reported) -- the
                                  anti-pseudoreplication rule made visual. No error bars ever.
  5. plot_hemisphere_symmetry -- L vs R scatter against y=x; a QC check (registration /
                                  tissue-damage flag), not a biology claim.
  Zero-cell / all-NaN regions are excluded from every figure with a visible footnote, never
  drawn as a zero bar. ``build_figures(...)`` orchestrates all five and OMITS a figure whose
  inputs are structurally absent (e.g. a 1-marker project has no ``overlap_above_chance``)
  rather than drawing empty axes. ``save_figures(...)`` writes PNGs under
  ``<out_dir>/figures/``. CLI: ``--plots [--top-n N] [--min-cells N]``.

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/cockpit_animal.py --self-test
  conda run -n braian python scripts/cockpit_animal.py \\
      --project "M3 Hipp1 072326 7scene/M3 Hipp1 072326 7 Scene QuPath" \\
      --regions CA1,CA3,DG,PIR,STRd --out-dir results/animal/m3
"""
from __future__ import annotations

import argparse
import colorsys
import textwrap
import glob
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Claim the headless backend ONLY when run as a CLI (mirrors k_sweep_readout.py lines
# 52-60). As an imported library this module must NOT touch the backend -- an
# unconditional matplotlib.use("Agg") at import time is the bd5d11f regression: it
# silently blanked every notebook plot because the notebook's inline backend got
# clobbered before a single cell ever ran. Nothing outside this guard may call
# matplotlib.use(...).
import matplotlib
if __name__ == "__main__":
    matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (must follow the matplotlib.use above)
import matplotlib.colors as mcolors  # noqa: E402  self-test facecolor assertions
from matplotlib.figure import Figure  # noqa: E402  plot_* return-type annotations

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
        # Same rule as the region_table path -- do not fork it, or two sessions'
        # s1 sections merge here while staying distinct there.
        animal, slice_id = creg.resolve_slice_identity(label, config.animal)

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

    _warn_empty_regions(grouped, anchor)
    add_metrics(grouped, config, roles)
    return grouped


def _warn_empty_regions(df: pd.DataFrame, anchor: str) -> list[str]:
    """Name regions that rolled up to zero anchor cells, and say why they usually do.

    A requested region summing to 0 is almost never "no cells there" -- it is increment 2's
    documented frontier-coverage caveat biting: the region's cells sit on the region's OWN
    annotation, but the region is not a data-frontier leaf (it has a present ontology
    descendant), so frontier summation reads the descendant instead. Verified live on M3:
    `STRd` carries 41,761 anchor cells while its only present ontology child `CP` carries 0
    at an identical area -- QuPath's annotation hierarchy does not match the Allen ontology.
    Every metric for such a row is NaN, which is correct but silent; this makes it loud.
    """
    empty = sorted(df.loc[df[f"{anchor}_count"] == 0, "region_acronym"].unique())
    if empty:
        print(f"  WARNING: {len(empty)} region(s) rolled up to 0 {anchor} cells: "
              f"{', '.join(empty)}", file=sys.stderr)
        print("           A zero here usually means the cells sit on a non-frontier "
              "intermediate annotation (increment 2's coverage caveat), NOT that the region "
              "is empty. Check cockpit_regions.coverage_report() before reporting these.",
              file=sys.stderr)
    return empty


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
        # N > 0 is required, not just d >= 0. An empty region (N==T==A==D==0) satisfies
        # d >= 0, and the Haldane-Anscombe +0.5 correction then yields (0.5*0.5)/(0.5*0.5)
        # = 1 -> log2 = 0.0 -- a real-looking "exactly at chance" value for a region that
        # holds no cells at all. Every other metric NaNs out via _safe_div, so the odds
        # ratios must too, or an empty region silently enters a t-test as a 0.
        d_valid = (d >= 0) & (N > 0)
        n_bad = int(((d < 0) & (N > 0)).sum())
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
# D-2: stacking animals with different marker sets -- fail loud by default
# ---------------------------------------------------------------------------
_PAIR_METRIC_COLS = ("reactivation_rate", "reverse_rate", "overlap_above_chance",
                    "log2_odds_ratio", "log2_odds_ratio_hc", "jaccard")


def _restrict_to_intersection(df: pd.DataFrame, config: creg.Config, roles: Roles,
                              intersection: set[str]) -> pd.DataFrame:
    """Drop count/density/rate columns for markers (and pair-metrics) not in the shared
    intersection marker set, so a concat never produces a NaN wall for the non-shared marker."""
    drop_cols = []
    for m in config.marker_names:
        if m not in intersection:
            drop_cols += [c for c in (f"{m}+_count", f"{m}+_density") if c in df.columns]
    if roles.tagged is not None and roles.tagged not in intersection:
        drop_cols += [c for c in ("tagging_rate",) if c in df.columns]
    if roles.activity is not None and roles.activity not in intersection:
        drop_cols += [c for c in ("activity_rate",) if c in df.columns]
    if len(intersection) < 2:
        drop_cols += [c for c in ("Double+_count", "Double+_density") + _PAIR_METRIC_COLS
                     if c in df.columns]
    return df.drop(columns=[c for c in drop_cols if c in df.columns])


def stack_animals(project_dirs: list[Path], regions: list[str] | None = None,
                  tagged: str | None = None, activity: str | None = None,
                  n_source: str = "auto", stack_on_intersection: bool = False) -> pd.DataFrame:
    """Roll up and concatenate multiple projects/animals into one group-ready table.

    D-2: a marker-set mismatch across projects RAISES by default (silently dropping a marker
    would corrupt a group comparison). ``stack_on_intersection`` opts in to stacking on the
    shared marker set, printing exactly which columns were dropped and why. If the intersection
    has fewer than 2 markers, the pair (overlap) metrics are dropped entirely -- absent columns,
    never a NaN wall.
    """
    project_dirs = [Path(p) for p in project_dirs]
    configs = {p: creg.load_pipeline_config(p) for p in project_dirs}
    marker_sets = {p: tuple(configs[p].marker_names) for p in project_dirs}
    unique_sets = sorted(set(marker_sets.values()))

    if len(unique_sets) > 1:
        if not stack_on_intersection:
            lines = "\n".join(f"  {p}: {marker_sets[p]}" for p in project_dirs)
            raise ValueError(
                "Marker sets differ across stacked projects (D-2) -- stacking would silently "
                "corrupt a group comparison. Declared marker sets:\n" + lines +
                "\nPass --stack-on-intersection to stack on the shared marker set instead.")
        intersection: set[str] = set(unique_sets[0])
        for s in unique_sets[1:]:
            intersection &= set(s)
        for p in project_dirs:
            dropped = [m for m in marker_sets[p] if m not in intersection]
            if dropped:
                print(f"  --stack-on-intersection: dropping {dropped} from {p.name} "
                      f"(declared {marker_sets[p]}, shared {sorted(intersection)})")
        if len(intersection) < 2:
            print(f"  Intersection marker set {sorted(intersection)} has < 2 markers -- "
                  f"overlap/pair metrics skip entirely (columns absent) for every project.")
    else:
        intersection = set(unique_sets[0]) if unique_sets else set()

    frames = []
    for p in project_dirs:
        config = configs[p]
        roles = resolve_roles(config, tagged=tagged, activity=activity)
        df = rollup_animal(p, regions=regions, roles=roles, n_source=n_source)
        if stack_on_intersection and set(marker_sets[p]) != intersection:
            df = _restrict_to_intersection(df, config, roles, intersection)
        frames.append(df)

    return pd.concat(frames, ignore_index=True, sort=False)


# ---------------------------------------------------------------------------
# D-3: explicit operator group/condition assignment -- never inferred
# ---------------------------------------------------------------------------
def load_group_map(path: Path | None, pairs: list[str] | None = None) -> dict[str, str]:
    """YAML `{groups: {animal: group}}` or a two-column CSV `animal,group`; repeatable
    `animal=group` one-offs layer on top (and win on conflict)."""
    mapping: dict[str, str] = {}
    if path is not None:
        path = Path(path)
        suffix = path.suffix.lower()
        if suffix in (".yml", ".yaml"):
            doc = yaml.safe_load(path.read_text()) or {}
            mapping.update({str(k): str(v) for k, v in (doc.get("groups") or {}).items()})
        elif suffix == ".csv":
            gdf = pd.read_csv(path)
            if not {"animal", "group"} <= set(gdf.columns):
                raise ValueError(f"{path}: group CSV must have columns 'animal','group'")
            mapping.update({str(a): str(g) for a, g in zip(gdf["animal"], gdf["group"])})
        else:
            raise ValueError(f"{path}: unrecognized group-map suffix (expected .yml/.yaml/.csv)")
    for pair in (pairs or []):
        if "=" not in pair:
            raise ValueError(f"--group '{pair}' must be of the form animal=group")
        a, g = pair.split("=", 1)
        mapping[a.strip()] = g.strip()
    return mapping


def apply_group_map(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """D-3: a supplied mapping that omits an animal is a hard error (silent blank group would
    corrupt an ANOVA). No mapping at all -> group='unassigned' + a loud warning."""
    animals = sorted(df["animal"].unique())
    df = df.copy()
    if not mapping:
        print("  WARNING: no group mapping supplied -- group='unassigned' for every animal; "
              "group comparisons are not possible until --groups/--group is provided.")
        df["group"] = "unassigned"
        return df
    missing = [a for a in animals if a not in mapping]
    if missing:
        raise ValueError(f"Group mapping omits animal(s) {missing} -- a supplied mapping must "
                         f"cover every stacked animal (D-3); a silent blank group would corrupt "
                         f"a group comparison.")
    df["group"] = df["animal"].map(mapping)
    return df


# ---------------------------------------------------------------------------
# Export shapes: tidy LONG table + Prism-friendly WIDE pivots
# ---------------------------------------------------------------------------
_IDENTITY_COLS = ["group", "animal", "region_acronym", "region_name", "level", "hemisphere",
                  "n_slices", "projects", "N_source"]


def write_long_csv(df: pd.DataFrame, out_path: Path) -> Path:
    """Canonical tidy LONG table: identity -> counts (area_mm2, N, per-category counts) ->
    densities -> metrics. One row per animal x region x hemisphere."""
    identity = [c for c in _IDENTITY_COLS if c in df.columns]
    counts = [c for c in df.columns if c in ("area_mm2", "N") or c.endswith("_count")]
    densities = [c for c in df.columns if c.endswith("_density")]
    metrics = [c for c in df.columns if c not in identity and c not in counts
              and c not in densities]
    ordered = identity + counts + densities + metrics
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df[ordered].to_csv(out_path, index=False)
    return out_path


def _sanitize_colname(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def write_wide_pivots(df: pd.DataFrame, out_dir: Path, hemisphere: str = "both") -> list[Path]:
    """Prism pivots: rows = region, columns = animal (or `{group}:{animal}` when a group
    mapping exists, ordered so Prism gets contiguous group blocks). One file per metric plus
    every `*_density` column. `--hemisphere` selects which slice of the long table is pivoted;
    the long table itself always keeps all three hemisphere values."""
    out_dir = Path(out_dir) / "wide"
    out_dir.mkdir(parents=True, exist_ok=True)

    sub = df[df["hemisphere"] == hemisphere].copy()
    if sub.empty:
        print(f"  WARNING: no rows at hemisphere == '{hemisphere}' -- no wide pivots written.")
        return []

    if "group" in sub.columns:
        order = (sub[["animal", "group"]].drop_duplicates()
                .sort_values(["group", "animal"]))
        col_label = {row.animal: f"{row.group}:{row.animal}" for row in order.itertuples()}
    else:
        order = sub[["animal"]].drop_duplicates().sort_values("animal")
        col_label = {a: a for a in order["animal"]}
    sub["_col"] = sub["animal"].map(col_label)

    density_cols = [c for c in sub.columns if c.endswith("_density")]
    metric_cols = [c for c in ("tagging_rate", "activity_rate") + _PAIR_METRIC_COLS
                  if c in sub.columns]
    pivot_cols = density_cols + metric_cols

    written: list[Path] = []
    seen_names: set[str] = set()
    for col in pivot_cols:
        piv = sub.pivot_table(index="region_acronym", columns="_col", values=col, aggfunc="first")
        fname = "wide__" + _sanitize_colname(col) + ".csv"
        if fname in seen_names:
            raise ValueError(f"filename collision writing wide pivot for column '{col}' -> {fname}")
        seen_names.add(fname)
        p = out_dir / fname
        piv.to_csv(p)
        written.append(p)
    return written


# ---------------------------------------------------------------------------
# Interpretation plots (follow-up increment) -- D-1..D-10, see module docstring
# ---------------------------------------------------------------------------
# D-1: palette validated with the dataviz skill's validate_palette.js (light mode: ALL
# CHECKS PASS; dark mode: contrast WARN on COLOR_BELOW, mitigated by direct region labels
# on every figure that uses it -- never color-only identification). COLOR_NEUTRAL FAILS
# the validator's categorical chroma-floor check BY DESIGN: that check targets categorical
# palettes where every slot must carry identity, but COLOR_NEUTRAL is a diverging
# MIDPOINT, which is supposed to read as "nothing". Do not "fix" this into a hue.
COLOR_ABOVE = "#C0492B"    # warm pole -- above chance / flagged
COLOR_BELOW = "#2E5EAA"    # cool pole -- below chance
COLOR_NEUTRAL = "#8A8F98"  # diverging midpoint + low-evidence de-emphasis
COLOR_INK = "#333333"      # text / axis ink (neutral, carries no data identity)

DEFAULT_TOP_N = 20
DEFAULT_MIN_CELLS = 30
DEFAULT_ASYM_TOL = 0.25

_TIMES = "×"
_LEFT_ARROW = "←"
_RIGHT_ARROW = "→"
_NEAR_CHANCE_LOG2_TOL = 0.05  # +-0.05 log2 (~1.0x) reads as "at chance", not enriched/depleted
_N_IMMUNE_METRIC_PRIORITY = ("reactivation_rate", "tagging_rate")  # D-9, in priority order


def _select_animal(df: pd.DataFrame, animal: str | None) -> tuple[pd.DataFrame, str]:
    """D-7 fail-loud animal selection. ``animal=None`` + exactly one animal in the frame
    selects it; ``animal=None`` + multiple animals RAISES, naming them -- group-level
    faceting of these figures is deliberately out of scope (it edges into a statistical
    comparison)."""
    animals = sorted(df["animal"].unique())
    if animal is None:
        if len(animals) != 1:
            raise ValueError(
                f"animal=None requires exactly one animal in the frame; found {animals}. "
                f"Pass animal=<name> to select one (group-level faceting is out of scope).")
        animal = animals[0]
    elif animal not in animals:
        raise ValueError(f"animal '{animal}' not found in frame; available: {animals}")
    return df[df["animal"] == animal].copy(), animal


def _style_axes(ax: plt.Axes, grid_axis: str = "x") -> None:
    """Recessive chrome shared by every figure: hide top/right spines, tick labels and
    remaining spines in COLOR_INK, grid on the value axis only and behind the marks, no
    bounding box, no chartjunk. Applied by every plot_* function so the whole set of five
    figures reads as one system."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(COLOR_INK)
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(colors=COLOR_INK, labelsize=8.5)
    ax.set_axisbelow(True)
    ax.grid(axis=grid_axis, color=COLOR_NEUTRAL, alpha=0.25, lw=0.6)


def _exclude_unusable(df: pd.DataFrame, cols: list[str],
                      anchor: str) -> tuple[pd.DataFrame, list[str]]:
    """D-5: drop rows where any of `cols` is non-finite, OR the anchor count is 0. Returns
    (kept, sorted excluded acronyms) -- callers footnote the excluded list and never render
    a zero bar for a structurally-unusable region (increment 2's frontier-coverage caveat
    surfacing at figure level)."""
    finite_mask = np.ones(len(df), dtype=bool)
    for c in cols:
        finite_mask &= np.isfinite(df[c].to_numpy(dtype=float))
    anchor_col = f"{anchor}_count"
    if anchor_col in df.columns:
        finite_mask &= (df[anchor_col].to_numpy(dtype=float) > 0)
    kept = df.loc[finite_mask].copy()
    excluded = sorted(df.loc[~finite_mask, "region_acronym"].unique())
    return kept, excluded


def _footnote(fig: Figure, excluded: list[str], extra: str | None = None) -> None:
    """D-5 exclusion note, drawn on the figure (not just printed) -- a figure with
    exclusions must never render as if every requested region were usable."""
    if not excluded:
        return
    text = (f"{len(excluded)} region(s) excluded (all-NaN / zero-count): "
           f"{', '.join(excluded)} -- see cockpit_regions.coverage_report()")
    if extra:
        text = extra + "\n" + text
    # Hard-wrap to the figure width. matplotlib's wrap=True measures against the FIGURE
    # box, not the 0.01 left inset, so a long note reliably ran off the right edge.
    width_chars = max(60, int(fig.get_size_inches()[0] / 0.062))
    text = "\n".join(line for para in text.split("\n")
                     for line in textwrap.wrap(para, width_chars) or [""])
    fig.text(0.01, 0.01, text, fontsize=7, color=COLOR_INK, ha="left", va="bottom")


def _rank_regions(df: pd.DataFrame, top_n: int = DEFAULT_TOP_N) -> list[str]:
    """D-6: the ONE ranking helper consumed by figures 1-3 (and 4), guaranteeing a shared
    region order by construction rather than by three call sites agreeing. Sorts by
    overlap_above_chance desc when present, else the first available of reactivation_rate /
    tagging_rate; caps at top_n. NaN sort keys sort last (never dropped here -- a caller
    that needs a region excluded runs it through `_exclude_unusable` first, which produces
    a footnote; silently vanishing from the ranking would not)."""
    if "overlap_above_chance" in df.columns:
        sort_col = "overlap_above_chance"
    elif "reactivation_rate" in df.columns:
        sort_col = "reactivation_rate"
    elif "tagging_rate" in df.columns:
        sort_col = "tagging_rate"
    else:
        raise ValueError(
            "_rank_regions: no rankable metric column present (overlap_above_chance / "
            "reactivation_rate / tagging_rate)")
    ranked = df.sort_values(sort_col, ascending=False, na_position="last")
    return ranked["region_acronym"].tolist()[:top_n]


def _enrichment_colors(values: np.ndarray) -> list[str]:
    """Maps log2(overlap_above_chance) sign to the diverging palette: warm = enriched,
    cool = depleted, neutral within +-0.05 log2 (~1.0x, at chance) or non-finite. Shared by
    figures 1-3 so the enrichment encoding is IDENTICAL across the whole set (D-3)."""
    colors = []
    for v in values:
        if not np.isfinite(v) or abs(v) <= _NEAR_CHANCE_LOG2_TOL:
            colors.append(COLOR_NEUTRAL)
        elif v > 0:
            colors.append(COLOR_ABOVE)
        else:
            colors.append(COLOR_BELOW)
    return colors


def _log2_ratio_axis(ax: plt.Axes, values: np.ndarray) -> None:
    """D-2 display transform: the value axis is log2(overlap_above_chance) on a LINEAR
    scale (never a log-scaled axis -- that has no honest zero, so a bar's origin becomes
    arbitrary). Ticks are relabeled as multiples (0.25x, 0.5x, 1x, 2x, 4x, 8x, ...) and the
    chance reference is drawn at 0 -- bars emanate from 0 (= 1.0x, chance). The "(chance)"
    label is baked directly into the 0-tick's text (not a separate floating annotation) so
    it can never collide with a title or legend above the axes."""
    finite = values[np.isfinite(values)]
    lo = int(np.floor(finite.min())) if finite.size else -1
    hi = int(np.ceil(finite.max())) if finite.size else 1
    lo = min(lo, -1)
    hi = max(hi, 1)
    ticks = list(range(lo, hi + 1))
    labels = [f"1.0{_TIMES} (chance)" if t == 0 else f"{2.0 ** t:g}{_TIMES}" for t in ticks]
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.axvline(0, color=COLOR_NEUTRAL, ls="--", lw=1.0, zorder=1)
    # Short label -- the D-2 display-transform note lives in the docstring/module PLOTTING
    # section, not here. A long label clips off the right edge of a NARROW two-panel figure
    # when rendered inline in a notebook (no bbox_inches="tight" to crop it, unlike savefig).
    ax.set_xlabel("log2(overlap_above_chance)")


def _reserve_chrome(n_rows: int, per_row: float, header_in: float, footer_in: float,
                    min_content_in: float = 1.4) -> tuple[float, float, float]:
    """Returns (total_fig_height_in, top_fraction, bottom_fraction). Header/footer chrome
    (title, legend, footnote, axis label) gets a roughly CONSTANT absolute-inch allowance
    regardless of row count -- a fixed FRACTION reserved on a tall, many-row figure leaves a
    disproportionate, empty-looking gap (found on the real M3 fixture at top_n=20)."""
    content_in = max(min_content_in, per_row * n_rows)
    total_in = content_in + header_in + footer_in
    return total_in, 1.0 - header_in / total_in, footer_in / total_in


def plot_region_ranking(df: pd.DataFrame, config: creg.Config, roles: Roles,
                        animal: str | None = None, top_n: int = DEFAULT_TOP_N) -> Figure:
    """Figure 1 -- regions ranked by chance-corrected enrichment (D-2), NOT raw rate. A
    single diverging series -> no legend; the title names the metric and the axis ends are
    annotated 'depleted <-' / '-> enriched'. Defends against the PVH trap: a region with a
    huge raw rate but only ~1x enrichment must NOT look important here."""
    sub, animal = _select_animal(df, animal)
    sub = sub[sub["hemisphere"] == "both"].copy()
    anchor = config.anchor_name

    with np.errstate(divide="ignore", invalid="ignore"):
        sub["_log2_oac"] = np.log2(sub["overlap_above_chance"].to_numpy(dtype=float))
    kept, excluded = _exclude_unusable(sub, ["_log2_oac"], anchor)
    order = _rank_regions(kept, top_n=top_n)
    plot_df = kept.set_index("region_acronym").loc[order].reset_index()

    n = len(plot_df)
    total_h, top, bottom = _reserve_chrome(n, per_row=0.34, header_in=0.45, footer_in=0.85)
    fig, ax = plt.subplots(figsize=(7.5, total_h))
    colors = _enrichment_colors(plot_df["_log2_oac"].to_numpy())
    ax.barh(plot_df["region_acronym"], plot_df["_log2_oac"], color=colors, height=0.6, zorder=2)
    ax.invert_yaxis()
    _log2_ratio_axis(ax, plot_df["_log2_oac"].to_numpy())
    _style_axes(ax, grid_axis="x")
    ax.text(0.0, -0.16, f"depleted {_LEFT_ARROW}", ha="left", va="top", fontsize=7.5,
           color=COLOR_INK, transform=ax.transAxes)
    ax.text(1.0, -0.16, f"{_RIGHT_ARROW} enriched", ha="right", va="top", fontsize=7.5,
           color=COLOR_INK, transform=ax.transAxes)
    ax.set_title(f"{animal} -- region ranking by overlap_above_chance (top {n})")
    _footnote(fig, excluded)
    fig.subplots_adjust(top=top, bottom=bottom)
    return fig


def plot_raw_vs_corrected(df: pd.DataFrame, config: creg.Config, roles: Roles,
                          animal: str | None = None, top_n: int = DEFAULT_TOP_N) -> Figure:
    """Figure 2 -- raw reactivation_rate vs chance-corrected overlap_above_chance, two
    panels sharing ONE region order and ONE diverging color encoding (D-3). This is the PVH
    trap made visual: a region with a huge raw bar rendered in neutral/cool immediately
    reads as 'high raw rate, not actually enriched'. Each left-panel row also carries a
    small #k raw-rank annotation, so a rank inversion between raw and corrected is legible
    without a spaghetti slope chart. UNDER NO CIRCUMSTANCE does either panel get a second
    (twin) y-axis -- a dual-axis chart is the single worst chart mistake."""
    sub, animal = _select_animal(df, animal)
    sub = sub[sub["hemisphere"] == "both"].copy()
    anchor = config.anchor_name

    with np.errstate(divide="ignore", invalid="ignore"):
        sub["_log2_oac"] = np.log2(sub["overlap_above_chance"].to_numpy(dtype=float))
    kept, excluded = _exclude_unusable(sub, ["reactivation_rate", "_log2_oac"], anchor)
    order = _rank_regions(kept, top_n=top_n)
    plot_df = kept.set_index("region_acronym").loc[order].reset_index()
    plot_df["_raw_rank"] = (plot_df["reactivation_rate"]
                           .rank(ascending=False, method="min").astype(int))

    n = len(plot_df)
    total_h, top, bottom = _reserve_chrome(n, per_row=0.34, header_in=1.0, footer_in=0.85)
    fig, (axL, axR) = plt.subplots(1, 2, sharey=True, figsize=(11.0, total_h))
    colors = _enrichment_colors(plot_df["_log2_oac"].to_numpy())

    rate_pct = plot_df["reactivation_rate"].to_numpy(dtype=float) * 100.0
    axL.barh(plot_df["region_acronym"], rate_pct, color=colors, height=0.6, zorder=2)
    axL.set_xlim(0, max(float(rate_pct.max()) * 1.24, 1.0))
    for yi, (rate, k) in enumerate(zip(rate_pct, plot_df["_raw_rank"])):
        axL.text(rate, yi, f"  #{k}", va="center", ha="left", fontsize=7, color=COLOR_INK)
    axL.invert_yaxis()
    axL.set_xlabel("reactivation_rate (%) -- raw, D/T")
    _style_axes(axL, grid_axis="x")

    axR.barh(plot_df["region_acronym"], plot_df["_log2_oac"], color=colors, height=0.6, zorder=2)
    _log2_ratio_axis(axR, plot_df["_log2_oac"].to_numpy())
    axR.tick_params(labelleft=False)
    _style_axes(axR, grid_axis="x")

    header_span = 1.0 - top
    handles = [plt.Rectangle((0, 0), 1, 1, color=COLOR_ABOVE),
              plt.Rectangle((0, 0), 1, 1, color=COLOR_BELOW)]
    fig.legend(handles, ["above chance", "below chance"], loc="upper center", ncol=2,
              frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, 1.0 - 0.15 * header_span))
    fig.suptitle(f"{animal} -- raw rate vs chance-corrected enrichment  (#k = raw-rate rank)",
                y=top + 0.40 * header_span, fontsize=10.5)
    _footnote(fig, excluded)
    fig.subplots_adjust(top=top, bottom=bottom, wspace=0.06)
    return fig


def plot_evidence_guard(df: pd.DataFrame, config: creg.Config, roles: Roles,
                        animal: str | None = None, top_n: int = DEFAULT_TOP_N,
                        min_cells: int = DEFAULT_MIN_CELLS) -> Figure:
    """Figure 3 -- evidence guard: Double+_count (2-marker) or {tagged}+_count (1-marker)
    vs N, on a log x-axis as dots/lollipops -- NEVER bars (a log axis has no honest bar
    baseline; dots from a common left edge are). Sub-min_cells regions are DE-EMPHASISED in
    neutral grey at reduced alpha and KEPT LABELED (D-4) -- never silently dropped, so
    '4x on 12 cells' is unmistakable rather than invisible."""
    sub, animal = _select_animal(df, animal)
    sub = sub[sub["hemisphere"] == "both"].copy()
    anchor = config.anchor_name
    count_col = "Double+_count" if config.emit_double else f"{roles.tagged}+_count"
    kept, excluded = _exclude_unusable(sub, [count_col, "N"], anchor)

    if "overlap_above_chance" in kept.columns:
        with np.errstate(divide="ignore", invalid="ignore"):
            kept = kept.copy()
            kept["_log2_oac"] = np.log2(kept["overlap_above_chance"].to_numpy(dtype=float))
        order = _rank_regions(kept, top_n=top_n)
        colors_by_region = dict(zip(kept["region_acronym"],
                                    _enrichment_colors(kept["_log2_oac"].to_numpy())))
    else:
        order = _rank_regions(kept, top_n=top_n)
        colors_by_region = {r: COLOR_NEUTRAL for r in kept["region_acronym"]}

    plot_df = kept.set_index("region_acronym").loc[order].reset_index()
    below = plot_df[count_col].to_numpy(dtype=float) < min_cells
    base_colors = [colors_by_region[r] for r in plot_df["region_acronym"]]
    facecolors = [COLOR_NEUTRAL if b else c for b, c in zip(below, base_colors)]
    alphas = [0.55 if b else 0.9 for b in below]

    n = len(plot_df)
    y = np.arange(n)
    total_h, top, bottom = _reserve_chrome(n, per_row=0.34, header_in=0.55, footer_in=0.85)
    fig, (axL, axR) = plt.subplots(1, 2, sharey=True, figsize=(11.0, total_h))
    for ax_, col, xlabel in ((axL, count_col, f"{count_col}  (log scale)"),
                            (axR, "N", "N  (log scale)")):
        vals = plot_df[col].to_numpy(dtype=float)
        vals_plot = np.clip(vals, a_min=0.5, a_max=None)  # log axis has no honest zero
        ax_.hlines(y, 0.5, vals_plot, color=COLOR_NEUTRAL, lw=1.0, alpha=0.4, zorder=1)
        rgba = [mcolors.to_rgba(fc, alpha=a) for fc, a in zip(facecolors, alphas)]
        ax_.scatter(vals_plot, y, c=rgba, s=42, zorder=2, edgecolors="white", linewidths=0.6)
        ax_.set_xscale("log")
        ax_.set_xlabel(xlabel)
        _style_axes(ax_, grid_axis="x")
    axL.set_yticks(y)
    axL.set_yticklabels(plot_df["region_acronym"])
    axL.invert_yaxis()
    axR.invert_yaxis()
    axR.tick_params(labelleft=False)

    n_below = int(below.sum())
    extra = None
    if n_below:
        extra = (f"{n_below} region(s) below min_cells={min_cells} shown de-emphasised "
               f"(grey, kept labeled): "
               f"{', '.join(plot_df.loc[below, 'region_acronym'])}")
    fig.suptitle(f"{animal} -- evidence guard: {count_col} vs N  (top {n})",
                y=top + 0.45 * (1.0 - top), fontsize=10.5)
    _footnote(fig, excluded, extra=extra)
    fig.subplots_adjust(top=top, bottom=bottom, wspace=0.08)
    return fig


def plot_slice_spread(df: pd.DataFrame, per_slice: pd.DataFrame, config: creg.Config,
                      roles: Roles, animal: str | None = None, top_n: int = 8) -> Figure:
    """Figure 4 -- per-slice reactivation dots vs the POOLED (sum D / sum T, reported)
    value vs the mean-of-slices (NOT reported) -- the anti-pseudoreplication rule made
    visual (D-8). Per-slice reactivation is recomputed role-correctly as
    Double+_count / {tagged}+_count DIRECTLY from per_slice's counts (recon 3) -- the
    per-slice P(...) columns are keyed on marker DECLARATION order and are the REVERSE
    rate on a project (like M3) that declares Fos before TdT; reading them would silently
    plot the wrong quantity. NO error bars anywhere: at n=1 an error bar across slices is
    pseudoreplication dressed as a CI."""
    if roles.tagged is None:
        raise ValueError("plot_slice_spread requires a resolved tagged-marker role")
    sub, animal = _select_animal(df, animal)
    both = sub[sub["hemisphere"] == "both"].copy()

    ps = per_slice[(per_slice["hemisphere"] == "both") & (per_slice["animal"] == animal)].copy()
    tagged_col = f"{roles.tagged}+_count"
    if "Double+_count" not in ps.columns or tagged_col not in ps.columns:
        raise ValueError(f"per_slice frame is missing Double+_count / {tagged_col}")
    with np.errstate(divide="ignore", invalid="ignore"):
        ps["_reactivation"] = (ps["Double+_count"].to_numpy(dtype=float)
                               / ps[tagged_col].to_numpy(dtype=float))

    order = _rank_regions(both, top_n=top_n)

    rows: list[dict] = []
    excluded: list[str] = []
    for region in order:
        rg = ps[ps["region_acronym"] == region]
        rg = rg[np.isfinite(rg[tagged_col]) & (rg[tagged_col] > 0)]
        pooled_row = both[both["region_acronym"] == region]
        if (rg.empty or rg[tagged_col].sum() == 0 or pooled_row.empty
                or not np.isfinite(pooled_row["reactivation_rate"].iloc[0])):
            excluded.append(region)
            continue
        rows.append({
            "region": region,
            "dots": rg["_reactivation"].to_numpy(dtype=float) * 100.0,
            "pooled": float(pooled_row["reactivation_rate"].iloc[0]) * 100.0,
            "mean_of_slices": float(rg["_reactivation"].mean()) * 100.0,
        })

    n = max(len(rows), 1)
    # header_in covers title AND a 3-entry legend placed ABOVE the axes. An in-axes legend
    # collided with real data here: on the M3 fixture the bottom region's pooled diamond
    # landed underneath a lower-right legend box. Dot positions are data-driven, so no
    # in-axes corner is reliably free -- the legend has to leave the data area entirely.
    total_h, top, bottom = _reserve_chrome(n, per_row=0.55, header_in=0.95, footer_in=0.75)
    fig, ax = plt.subplots(figsize=(7.5, total_h))
    if not rows:
        ax.text(0.5, 0.5, "no region has a usable per-slice reactivation series",
               ha="center", va="center", transform=ax.transAxes, color=COLOR_INK)
        ax.set_axis_off()
        _footnote(fig, excluded)
        return fig

    all_dot_x: list[float] = []
    all_dot_y: list[int] = []
    pooled_x: list[float] = []
    pooled_y: list[int] = []
    mean_x: list[float] = []
    mean_y: list[int] = []
    for y_i, r in enumerate(rows):
        all_dot_x.extend(r["dots"].tolist())
        all_dot_y.extend([y_i] * len(r["dots"]))
        pooled_x.append(r["pooled"])
        pooled_y.append(y_i)
        mean_x.append(r["mean_of_slices"])
        mean_y.append(y_i)

    ax.scatter(all_dot_x, all_dot_y, color=COLOR_NEUTRAL, alpha=0.6, s=30, zorder=2,
              label="per-slice")
    ax.scatter(pooled_x, pooled_y, marker="D", color=COLOR_ABOVE, s=64, zorder=3,
              edgecolors="white", linewidths=0.6,
              label=f"pooled ΣD/Σ{roles.tagged}+ (reported)")
    ax.scatter(mean_x, mean_y, marker="o", facecolors="none", edgecolors=COLOR_BELOW,
              s=64, zorder=3, linewidths=1.4, label="mean of slices — NOT reported")

    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["region"] for r in rows])
    ax.invert_yaxis()
    ax.set_xlabel(f"reactivation rate (%) -- Double+/{roles.tagged}+_count per slice, "
                 f"pooled vs mean")
    _style_axes(ax, grid_axis="x")
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False, fontsize=8,
               bbox_to_anchor=(0.5, 1.0 - 0.42 / total_h))
    ax.set_title(f"{animal} -- per-slice reactivation spread (dots = slices per region)")
    _footnote(fig, excluded)
    fig.subplots_adjust(top=top, bottom=bottom)
    return fig


def _first_n_immune_metric(df: pd.DataFrame, config: creg.Config, roles: Roles) -> str | None:
    """D-9: L/R rows have N = NaN when n_source='classifiable' (per-cell N is
    pooled-only), which NaNs every N-dependent metric on L/R. Figure 5 therefore picks the
    first N-IMMUNE metric available: reactivation_rate -> tagging_rate -> {anchor}_density.
    Never activity_rate / overlap_above_chance / N itself (all N-dependent)."""
    for col in _N_IMMUNE_METRIC_PRIORITY:
        if col in df.columns:
            return col
    density_col = f"{config.anchor_name}_density"
    if density_col in df.columns:
        return density_col
    return None


def plot_hemisphere_symmetry(df: pd.DataFrame, config: creg.Config, roles: Roles,
                             animal: str | None = None,
                             asym_tol: float = DEFAULT_ASYM_TOL) -> Figure | None:
    """Figure 5 -- L vs R symmetry QC (D-9): large asymmetry flags registration or tissue
    damage, NOT biology. Selects the first N-immune metric (D-9) so the figure survives
    --n-source=classifiable's L/R N=NaN. Points within tolerance are neutral; points with
    |L-R| / mean(L,R) > asym_tol are warm and DIRECTLY labeled (selective labels only --
    flagged points, not every point). Returns None (with a printed message) when fewer than
    2 regions have finite paired L and R values -- never an empty-axes Figure."""
    sub, animal = _select_animal(df, animal)
    metric = _first_n_immune_metric(sub, config, roles)
    if metric is None:
        print("  plot_hemisphere_symmetry: no N-immune metric available "
             "(reactivation_rate / tagging_rate / anchor density all absent) -- skipped.")
        return None

    lr = sub[sub["hemisphere"].isin(["L", "R"])][["region_acronym", "hemisphere", metric]]
    piv = lr.pivot_table(index="region_acronym", columns="hemisphere", values=metric)
    if "L" not in piv.columns or "R" not in piv.columns:
        print(f"  plot_hemisphere_symmetry: '{metric}' has no paired L AND R data -- "
             f"figure 5 skipped.")
        return None
    piv = piv[np.isfinite(piv["L"]) & np.isfinite(piv["R"])]
    if len(piv) < 2:
        print(f"  plot_hemisphere_symmetry: fewer than 2 regions have finite paired L/R "
             f"'{metric}' values ({len(piv)} found) -- figure 5 skipped.")
        return None

    denom = (piv["L"] + piv["R"]) / 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        asym = (np.abs(piv["L"] - piv["R"]) / denom).to_numpy(dtype=float)
    flagged = np.isfinite(asym) & (asym > asym_tol)

    lo = float(min(piv["L"].min(), piv["R"].min()))
    hi = float(max(piv["L"].max(), piv["R"].max()))

    # D-9 says "selective labels only (flagged points, not all points)" -- but at whole-brain
    # scale (e.g. 275 regions, no --regions cap) dozens of low-evidence regions can exceed
    # asym_tol from sampling noise alone, and labeling every one of them is the "number on
    # every data point" anti-pattern: illegible overlapping text. Every flagged point stays
    # colored/flagged; only up to MAX_LABELED get a direct label, chosen most-severe-first but
    # SKIPPED if too close (in data space) to an already-accepted label -- severity-only
    # selection still clusters labels on top of each other when the worst offenders sit near
    # the same dense corner (observed on the real M3/wBA fixtures). The rest are named in a
    # footnote instead of silently vanishing.
    MAX_LABELED = 15
    scale = max(hi - lo, 1e-9)
    min_sep = 0.06 * scale
    flagged_idx = np.flatnonzero(flagged)
    severity_order = flagged_idx[np.argsort(-asym[flagged_idx])]
    L_arr = piv["L"].to_numpy(dtype=float)
    R_arr = piv["R"].to_numpy(dtype=float)
    label_idx: list[int] = []
    for idx in severity_order:
        if len(label_idx) >= MAX_LABELED:
            break
        if all(abs(L_arr[idx] - L_arr[j]) >= min_sep or abs(R_arr[idx] - R_arr[j]) >= min_sep
              for j in label_idx):
            label_idx.append(int(idx))
    label_mask = np.zeros(len(piv), dtype=bool)
    label_mask[label_idx] = True
    n_unlabeled = len(flagged_idx) - len(label_idx)

    fig, ax = plt.subplots(figsize=(6.5, 6.75))
    colors = [COLOR_ABOVE if f else COLOR_NEUTRAL for f in flagged]
    ax.scatter(piv["L"], piv["R"], c=colors, s=44, edgecolors="white", linewidths=0.6, zorder=3)

    pad = (hi - lo) * 0.08 if hi > lo else max(abs(hi), 1e-6) * 0.1
    ax.plot([lo - pad, hi + pad], [lo - pad, hi + pad], color=COLOR_NEUTRAL, ls="--",
           lw=1.0, zorder=1)
    ax.set_xlim(lo - pad, hi + pad)
    ax.set_ylim(lo - pad, hi + pad)
    ax.set_aspect("equal", adjustable="box")

    for region, do_label in zip(piv.index, label_mask):
        if do_label:
            ax.annotate(region, (piv.loc[region, "L"], piv.loc[region, "R"]),
                       textcoords="offset points", xytext=(6, 4), fontsize=7.5,
                       color=COLOR_ABOVE)

    handles = [plt.Line2D([0], [0], marker="o", linestyle="none",
                         markerfacecolor=COLOR_NEUTRAL, markeredgecolor="none",
                         markersize=7, label=f"within tolerance ({asym_tol:.0%})"),
              plt.Line2D([0], [0], marker="o", linestyle="none",
                         markerfacecolor=COLOR_ABOVE, markeredgecolor="none",
                         markersize=7, label=f"asymmetric (>{asym_tol:.0%}, labeled)")]
    ax.legend(handles=handles, frameon=False, fontsize=8, loc="upper left")
    ax.set_xlabel(f"L  {metric}")
    ax.set_ylabel(f"R  {metric}")
    ax.set_title(f"{animal} -- hemisphere L/R symmetry QC ({metric}):\n"
                f"large asymmetry flags registration/tissue damage, not biology", fontsize=10)
    _style_axes(ax, grid_axis="both")
    if n_unlabeled > 0:
        fig.text(0.01, 0.01,
                 f"{len(flagged_idx)} region(s) flagged asymmetric (>{asym_tol:.0%}); "
                 f"labeling the {len(label_idx)} most severe only ({n_unlabeled} more shown "
                 f"colored but unlabeled to keep labels legible).",
                 fontsize=7, color=COLOR_INK, ha="left", va="bottom", wrap=True)
        fig.subplots_adjust(top=0.87, bottom=0.14)
    else:
        fig.subplots_adjust(top=0.87, bottom=0.09)
    return fig


# ---------------------------------------------------------------------------
# Quick visualization (section 6) -- regions on X, scan a chosen set
# ---------------------------------------------------------------------------
def _k_ramp(base_hex: str, n: int) -> list[str]:
    """`n` steps of ONE hue, lightest first. k is an ORDERED quantity (higher k = stricter
    cut), so its encoding is a single-hue SEQUENTIAL ramp -- light = permissive, dark =
    strict -- never distinct categorical hues.

    The dataviz categorical validator (chroma floor / CVD pair separation) does NOT apply
    to a sequential ramp; the rule for a ramp is monotonic lightness, which `_self_test`
    asserts directly for n=1..5 on both base hues rather than trusting fixed hexes.

    Verified at n=3:
      COLOR_ABOVE #C0492B -> #eab2a3 (L .778), #dc7a61 (L .622), #c0492b (L .461)
      COLOR_BELOW #2E5EAA -> #a7c0e7 (L .780), #5f8cd4 (L .602), #2e5eaa (L .424)
    """
    if n <= 1:
        return [base_hex]
    h, lightness, s = colorsys.rgb_to_hls(*mcolors.to_rgb(base_hex))
    top = max(0.78, lightness)
    return [mcolors.to_hex(colorsys.hls_to_rgb(h, top + (lightness - top) * i / (n - 1), s))
            for i in range(n)]


def _marker_colors(marker_names: list[str]) -> list[str]:
    """Marker identity IS categorical, so it uses the already-validated diverging pair in
    declaration order. COLOR_NEUTRAL is deliberately NOT a fallback -- it is the diverging
    midpoint and carries no identity by design."""
    if len(marker_names) <= 1:
        return [COLOR_ABOVE]
    if len(marker_names) == 2:
        return [COLOR_ABOVE, COLOR_BELOW]
    raise ValueError(
        f"_marker_colors: {len(marker_names)} markers ({marker_names}) exhausts the "
        f"validated categorical pair ({COLOR_ABOVE}, {COLOR_BELOW}). Validate a third hue "
        f"first and report the output:\n  node <dataviz-skill>/scripts/validate_palette.js "
        f'"{COLOR_ABOVE},{COLOR_BELOW},<new>" --mode light   (and --mode dark)')


def _k_split_counts(project_dir: Path, config: creg.Config, roles: Roles,
                    k_values: list[float], regions: list[str],
                    rollup_n: dict[str, float]) -> tuple[pd.DataFrame, list[str]]:
    """Recomputes per-region counts at each k from `results/*percell_export.tsv`.

    Why not region_table.tsv: its counts are FROZEN at the single k baked in when QuPath
    classified. Varying k requires going back to the per-cell measures.

    LIMITATION (2026-08-01): one k is applied to EVERY marker. With a per-marker
    k_robust override declared in pipeline.yml, no point on the sweep reproduces the
    locked configuration, and the function warns. Do not read the sweep as the result.

    LOCKED CORRECTNESS RULE: the cut applied inside a region is the SECTION-level threshold
    at that k (`ksr._threshold_at_k` over `ksr.analyze_section`). A threshold is NEVER
    re-derived from a region's own cells -- a small region would get its own noise-driven
    cut. Thresholds are per-section; COUNTS are summed across slices; ratios are computed
    from the sums ONLY at the end (pool then recompute, never a mean of per-slice ratios).

    `ksr.region_stats_for_group` is deliberately bypassed for counting: it returns a
    per-marker array that is not row-aligned ACROSS markers, so it cannot express joint
    (Double+) positivity. Instead the counting population is the row-aligned intersection
    of `ksr.classifiable_mask` over every marker, so the singles and the joint share one
    denominator exactly. For a 1-marker config that intersection reduces to precisely what
    `region_stats_for_group` would have returned.

    FRONTIER-BASIS GUARD: `percell.region_label` is a BARE acronym with no hemisphere
    prefix, so this path is POOLED-HEMISPHERE ONLY, and it matches an acronym LITERALLY --
    whereas the rollup sums over the ontology-frontier descendant set. Measured on M3:
    identical to the integer on frontier leaves (CA1 22740, PVH 4495, ...), but DG is
    rollup 9806 vs percell 0 (cells sit on DG-mo/DG-po) and STRd is rollup 0 vs percell
    165595. Silently swapping basis would change a denominator ~100x with nothing to say
    so, so any region whose count at the LOCKED k differs from the rollup's N is DROPPED
    and returned for footnoting. Consequence: for every surviving region the locked-k point
    is guaranteed to land exactly on the no-k default value read from the rollup.
    """
    locked_k = float(ksr.load_pipeline_config(Path(project_dir) / "pipeline.yml")["k_robust"])
    compute_ks = sorted({float(k) for k in k_values} | {locked_k})

    # A k-sweep applies ONE k to every marker. If any marker carries a per-marker
    # k_robust override, no point on the sweep reproduces the actual configuration --
    # the rollup used, say, TdT k=2.0 and Fos k=3.0, a combination the curve never
    # visits. Saying so is the whole fix: a figure that silently contradicts the table
    # printed beside it is worse than no figure.
    _overrides = {m["name"]: m["k_robust"] for m in (config.markers or [])
                  if m.get("k_robust") is not None}
    if _overrides:
        print(f"  WARNING: per-marker k_robust override(s) in effect {_overrides}, but a "
              f"k-sweep varies ONE k across all markers.")
        print(f"           No point on this series matches the configuration the tables "
              f"were computed with (global k={locked_k:g}).")
        print(f"           Read the sweep as a SENSITIVITY analysis only, never as the "
              f"locked result.")
    tally: dict[tuple[str, float], dict[str, int]] = {
        (r, k): {"N": 0} for r in regions for k in compute_ks}

    paths = sorted(Path(project_dir).glob("results/*percell_export.tsv"))
    if not paths:
        raise ValueError(f"_k_split_counts: no *percell_export.tsv under {project_dir}/results")

    for path in paths:
        d = ksr.load_percell(path)
        present = ksr.markers_in_df(d)
        ms = [m for m in config.marker_names if m in present]
        if not ms:
            continue
        st = ksr.analyze_section(d, ms)
        inter = np.ones(len(d), dtype=bool)
        for m in ms:
            inter &= ksr.classifiable_mask(d, m).to_numpy(dtype=bool)
        sub = d.loc[inter]
        acrs = sub["acronym"].to_numpy()
        pair = [roles.tagged, roles.activity] if (roles.tagged and roles.activity) else []
        emit_double = config.emit_double and len([m for m in pair if m in ms]) == 2

        for k in compute_ks:
            pos = {m: sub[f"{m}_bgsub"].to_numpy(dtype=float) >= ksr._threshold_at_k(st[m], k)
                   for m in ms}
            for region in regions:
                mask = acrs == region
                cell = tally[(region, k)]
                cell["N"] += int(mask.sum())
                for m in ms:
                    cell[f"{m}+_count"] = cell.get(f"{m}+_count", 0) + int((pos[m] & mask).sum())
                if emit_double:
                    joint = pos[pair[0]] & pos[pair[1]] & mask
                    cell["Double+_count"] = cell.get("Double+_count", 0) + int(joint.sum())

    dropped = sorted(r for r in regions
                     if float(tally[(r, locked_k)]["N"]) != float(rollup_n.get(r, np.nan)))
    kept = [r for r in regions if r not in dropped]

    rows = []
    for region in kept:
        for k in k_values:
            c = tally[(region, float(k))]
            n = float(c["N"])
            row = {"region_acronym": region, "k": float(k), "N": n}
            for key, val in c.items():
                if key.endswith("+_count"):
                    row[key] = val
                    row[key.replace("_count", "_pct")] = 100.0 * val / n if n > 0 else np.nan
            t = float(row.get(f"{roles.tagged}+_count", np.nan)) if roles.tagged else np.nan
            a = float(row.get(f"{roles.activity}+_count", np.nan)) if roles.activity else np.nan
            dbl = float(row.get("Double+_count", np.nan))
            row["overlap_above_chance"] = (
                dbl * n / (t * a) if np.isfinite(dbl) and t > 0 and a > 0 else np.nan)
            rows.append(row)
    return pd.DataFrame(rows), dropped


_QV_DODGE = 0.28
_K_BASIS_NOTE = ("k series recomputed from per-cell exports -- POOLED ACROSS HEMISPHERES. "
                 "One k is applied to all markers; with a per-marker override in "
                 "pipeline.yml no point here equals the locked configuration.")


def _qv_regions(sub: pd.DataFrame, regions: list[str] | None) -> list[str]:
    """Caller order preserved by default -- that is the point of this figure (scanning a
    chosen set, comparably across animals and across k). Figure 1 already does ranking."""
    if regions is None:
        return sub["region_acronym"].tolist()
    return [r for r in regions if r in set(sub["region_acronym"])]


def _qv_layout(n_regions: int, n_panels: int = 1) -> tuple[float, float, float, float]:
    total_h, top, bottom = _reserve_chrome(n_panels, per_row=3.4, header_in=0.75,
                                           footer_in=1.15, min_content_in=3.0)
    return max(6.0, 0.42 * n_regions + 1.8), total_h, top, bottom


def _qv_finish(ax: plt.Axes, order: list[str]) -> None:
    """Region acronyms on an X axis collide, so they are always rotated and anchored."""
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(order, rotation=45, ha="right", rotation_mode="anchor")
    ax.set_xlim(-0.6, len(order) - 0.4)
    _style_axes(ax, grid_axis="y")


def plot_regions_overlap(df: pd.DataFrame, config: creg.Config, roles: Roles,
                         regions: list[str] | None = None, animal: str | None = None,
                         k_values: list[float] | None = None,
                         project_dir: Path | None = None,
                         sort_by_value: bool = False) -> Figure | None:
    """Quick-viz A -- above-chance overlap (y) across the chosen regions (x), against a
    dashed reference line at 1.0 = chance.

    MARK IS DOTS, NOT BARS, deliberately: overlap_above_chance is a ratio whose honest
    baseline is 1.0, not 0. A bar drawn from 0 up to 4.2x reads as "4.2 units of stuff".
    Dots make no baseline claim and the dashed chance line supplies the reference. Do not
    "fix" this into a bar chart.

    Returns None (with a printed reason) on a 1-marker project -- never empty axes.
    """
    if "overlap_above_chance" not in df.columns:
        print("  plot_regions_overlap: no overlap_above_chance column (1-marker project / "
              "fewer than 2 resolved roles) -- skipping. This is the expected single-marker "
              "path, not an error.")
        return None

    sub, animal = _select_animal(df, animal)
    sub = sub[sub["hemisphere"] == "both"].copy()
    kept, excluded = _exclude_unusable(sub, ["overlap_above_chance"], config.anchor_name)
    order = _qv_regions(kept, regions)
    if sort_by_value:
        order = (kept[kept["region_acronym"].isin(order)]
                 .sort_values("overlap_above_chance", ascending=False)["region_acronym"].tolist())
    base = kept.set_index("region_acronym")

    extra, dropped = None, []
    kdf = None
    if k_values:
        if project_dir is None:
            raise ValueError("plot_regions_overlap: k_values requires project_dir (the k "
                             "series is recomputed from that project's per-cell exports).")
        rollup_n = {r: float(base.loc[r, "N"]) for r in order}
        kdf, dropped = _k_split_counts(Path(project_dir), config, roles,
                                       [float(k) for k in k_values], order, rollup_n)
        order = [r for r in order if r not in dropped]
        extra = _K_BASIS_NOTE
        if dropped:
            extra += (f" Dropped (per-cell labels sit on descendant annotations, so the "
                      f"bare-acronym basis != the rollup's frontier basis): "
                      f"{', '.join(dropped)}.")

    width, height, top, bottom = _qv_layout(len(order))
    fig, ax = plt.subplots(figsize=(width, height))
    x = np.arange(len(order))

    if kdf is None:
        vals = base.loc[order, "overlap_above_chance"].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            colors = _enrichment_colors(np.log2(vals))
        ax.scatter(x, vals, c=colors, s=46, zorder=3)
    else:
        ks = sorted({float(k) for k in k_values})
        ramp = _k_ramp(COLOR_ABOVE, len(ks))
        offs = np.linspace(-_QV_DODGE, _QV_DODGE, len(ks)) if len(ks) > 1 else [0.0]
        piv = kdf.pivot(index="region_acronym", columns="k", values="overlap_above_chance")
        for i, k in enumerate(ks):
            ax.plot(x + offs[i], piv.loc[order, k].to_numpy(dtype=float), ls="none",
                    marker="o", ms=6, color=ramp[i], label=f"k={k:g}", zorder=3)
        ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=len(ks),
                  frameon=False, fontsize=8)

    ax.axhline(1.0, ls="--", lw=1.0, color=COLOR_NEUTRAL, zorder=1)
    ax.annotate("1.0x = chance", xy=(1.0, 1.0), xycoords=("axes fraction", "data"),
                xytext=(-4, 4), textcoords="offset points", ha="right", va="bottom",
                fontsize=7.5, color=COLOR_INK)
    ax.set_ylabel("overlap above chance (x)")
    ax.set_title(f"{animal} -- above-chance overlap by region",
                 pad=24 if kdf is not None else 8)
    _qv_finish(ax, order)
    _footnote(fig, excluded, extra=extra)
    fig.subplots_adjust(top=top, bottom=bottom)
    return fig


def plot_regions_positivity(df: pd.DataFrame, config: creg.Config, roles: Roles,
                            regions: list[str] | None = None, animal: str | None = None,
                            k_values: list[float] | None = None,
                            project_dir: Path | None = None,
                            sort_by_value: bool = False) -> Figure:
    """Quick-viz B -- per-marker positivity percent (y) across the chosen regions (x).

    Marker names are CONFIG-DERIVED everywhere, including axis labels, legend and titles.
    y starts at 0: unlike an above-chance ratio, a percentage has an honest zero.

    With k_values: ONE PANEL PER MARKER. Marker identity is categorical (hue) while k is
    ordered (lightness); crossing them on one axes would stack n_markers x n_k overlapping
    dots at every region. A 1-marker project therefore yields exactly one panel.
    """
    sub, animal = _select_animal(df, animal)
    sub = sub[sub["hemisphere"] == "both"].copy()
    markers = list(config.marker_names)
    cols = [f"{m}+_count" for m in markers if f"{m}+_count" in sub.columns]
    kept, excluded = _exclude_unusable(sub, cols + ["N"], config.anchor_name)
    order = _qv_regions(kept, regions)
    base = kept.set_index("region_acronym")
    for m in markers:
        base[f"{m}+_pct"] = 100.0 * base[f"{m}+_count"].to_numpy(dtype=float) / \
            base["N"].to_numpy(dtype=float)
    if sort_by_value and markers:
        order = (base.loc[order].sort_values(f"{markers[0]}+_pct", ascending=False)
                 .index.tolist())

    extra, dropped, kdf = None, [], None
    if k_values:
        if project_dir is None:
            raise ValueError("plot_regions_positivity: k_values requires project_dir (the k "
                             "series is recomputed from that project's per-cell exports).")
        rollup_n = {r: float(base.loc[r, "N"]) for r in order}
        kdf, dropped = _k_split_counts(Path(project_dir), config, roles,
                                       [float(k) for k in k_values], order, rollup_n)
        order = [r for r in order if r not in dropped]
        extra = _K_BASIS_NOTE
        if dropped:
            extra += (f" Dropped (per-cell labels on descendant annotations): "
                      f"{', '.join(dropped)}.")

    m_colors = _marker_colors(markers)
    n_panels = len(markers) if kdf is not None else 1
    width, height, top, bottom = _qv_layout(len(order), n_panels=n_panels)
    fig, axes = plt.subplots(n_panels, 1, figsize=(width, height), sharex=True, squeeze=False)
    axes = axes.ravel()
    x = np.arange(len(order))

    if kdf is None:
        ax = axes[0]
        for m, color in zip(markers, m_colors):
            ax.plot(x, base.loc[order, f"{m}+_pct"].to_numpy(dtype=float), ls="none",
                    marker="o", ms=6, color=color, label=f"{m}+", zorder=3)
        if len(markers) > 1:
            ax.legend(loc="lower left", bbox_to_anchor=(0, 1.02), ncol=len(markers),
                      frameon=False, fontsize=8)
        ax.set_title(f"{animal} -- marker positivity by region",
                     pad=24 if len(markers) > 1 else 8)
    else:
        ks = sorted({float(k) for k in k_values})
        offs = np.linspace(-_QV_DODGE, _QV_DODGE, len(ks)) if len(ks) > 1 else [0.0]
        ymax = 0.0
        for ax, m, color in zip(axes, markers, m_colors):
            ramp = _k_ramp(color, len(ks))
            piv = kdf.pivot(index="region_acronym", columns="k", values=f"{m}+_pct")
            for i, k in enumerate(ks):
                vals = piv.loc[order, k].to_numpy(dtype=float)
                ymax = max(ymax, float(np.nanmax(vals)) if vals.size else 0.0)
                ax.plot(x + offs[i], vals, ls="none", marker="o", ms=6, color=ramp[i],
                        label=f"k={k:g}", zorder=3)
            ax.set_title(f"{m}+", fontsize=9.5, color=COLOR_INK)
        for ax in axes:
            ax.set_ylim(0, ymax * 1.08 if ymax > 0 else 1.0)
        axes[0].legend(loc="lower left", bbox_to_anchor=(0, 1.14), ncol=len(ks),
                       frameon=False, fontsize=8)

    for ax in axes:
        ax.set_ylabel("% positive")
        if kdf is None:
            ax.set_ylim(bottom=0)
        _style_axes(ax, grid_axis="y")
    _qv_finish(axes[-1], order)
    _footnote(fig, excluded, extra=extra)
    fig.subplots_adjust(top=top, bottom=bottom)
    return fig


def build_figures(df: pd.DataFrame, config: creg.Config, roles: Roles,
                  per_slice: pd.DataFrame | None = None, animal: str | None = None,
                  top_n: int = DEFAULT_TOP_N,
                  min_cells: int = DEFAULT_MIN_CELLS,
                  quick_viz: bool = False, regions: list[str] | None = None,
                  k_values: list[float] | None = None,
                  project_dir: Path | None = None,
                  sort_by_value: bool = False) -> dict[str, Figure]:
    """Orchestrates figures 1-5. Applies D-10: a figure whose inputs are structurally
    absent (no overlap_above_chance; no per_slice frame; fewer than 2 finite L/R pairs) is
    OMITTED from the returned dict with one printed explanatory line -- NEVER a Figure with
    empty axes, never a NaN wall. Keys, when present, in order: region_ranking,
    raw_vs_corrected, evidence_guard, slice_spread, hemisphere_symmetry."""
    figs: dict[str, Figure] = {}
    both = df[df["hemisphere"] == "both"]
    has_pair_metrics = "overlap_above_chance" in both.columns

    if has_pair_metrics:
        figs["region_ranking"] = plot_region_ranking(df, config, roles, animal=animal,
                                                      top_n=top_n)
        figs["raw_vs_corrected"] = plot_raw_vs_corrected(df, config, roles, animal=animal,
                                                         top_n=top_n)
    else:
        print("  build_figures: no overlap_above_chance column (1-marker project / single "
             "resolved role) -- skipping region_ranking and raw_vs_corrected.")

    figs["evidence_guard"] = plot_evidence_guard(df, config, roles, animal=animal,
                                                 top_n=top_n, min_cells=min_cells)

    if per_slice is None:
        print("  build_figures: no per_slice frame supplied -- skipping slice_spread "
             "(figure 4 needs the per-slice readout; only built when exactly one "
             "--project was given).")
    elif not has_pair_metrics or roles.tagged is None:
        print("  build_figures: no resolved pair metrics -- skipping slice_spread "
             "(figure 4 needs Double+_count and a resolved tagged-marker role).")
    else:
        try:
            figs["slice_spread"] = plot_slice_spread(df, per_slice, config, roles,
                                                      animal=animal, top_n=8)
        except ValueError as exc:
            print(f"  build_figures: slice_spread skipped ({exc})")

    fig5 = plot_hemisphere_symmetry(df, config, roles, animal=animal)
    if fig5 is not None:
        figs["hemisphere_symmetry"] = fig5

    # Section 6 quick-viz is opt-in via an EXPLICIT flag rather than inferred from
    # `regions`, so notebook section 5 provably keeps returning exactly the five figures
    # above and section 6 cannot double-render them.
    if quick_viz:
        if k_values and project_dir is None:
            raise ValueError("build_figures: k_values requires project_dir (the k series is "
                             "recomputed from that project's per-cell exports).")
        fig6 = plot_regions_overlap(df, config, roles, regions=regions, animal=animal,
                                    k_values=k_values, project_dir=project_dir,
                                    sort_by_value=sort_by_value)
        if fig6 is not None:
            figs["regions_overlap"] = fig6
        figs["regions_positivity"] = plot_regions_positivity(
            df, config, roles, regions=regions, animal=animal, k_values=k_values,
            project_dir=project_dir, sort_by_value=sort_by_value)

    return figs


def save_figures(figs: dict[str, Figure], out_dir: Path) -> list[Path]:
    """Writes one PNG per figure under <out_dir>/figures/<key>.png, dpi=150, tight bbox,
    white facecolor. <out_dir> defaults to results/animal, which is gitignored --
    generated PNGs are never committed."""
    fig_dir = Path(out_dir) / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, fig in figs.items():
        p = fig_dir / f"{key}.png"
        fig.savefig(p, dpi=150, bbox_inches="tight", facecolor="white")
        written.append(p)
    return written


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
    # DG-mo: BOTH hemispheres present with unequal L/R reactivation -- the second paired
    # L/R region the interpretation-plots self-test needs for figure 5 (a real L/R symmetry
    # scatter needs >= 2 paired regions; LA alone is only one). CEA: present but ALL-ZERO
    # counts on both hemispheres/slices -- the deliberate all-zero-region exclusion case for
    # figures 1-3's footnote check (D-5), reusing this same fixture rather than a new one.
    slice_specs: dict[str, dict[tuple[str, str], tuple[float, dict[str, int]]]] = {
        "s1": {
            ("LA", "Left"): (0.3, _c(100, 50, 30, 20)),
            ("LA", "Right"): (0.3, _c(80, 40, 24, 16)),
            ("CA1", "Left"): (1.0, _c(200, 60, 40, 24)),
            ("BLA", "Right"): (0.2, _c(50, 10, 10, 10)),
            ("DG-mo", "Left"): (0.4, _c(150, 30, 20, 12)),
            ("DG-mo", "Right"): (0.4, _c(140, 28, 18, 9)),
            ("CEA", "Left"): (0.1, _c(0, 0, 0, 0)),
            ("CEA", "Right"): (0.1, _c(0, 0, 0, 0)),
        },
        "s2": {
            ("LA", "Left"): (0.3, _c(200, 10, 8, 2)),
            ("LA", "Right"): (0.3, _c(150, 8, 6, 1)),
            ("CA1", "Left"): (1.0, _c(300, 15, 10, 3)),
            ("BLA", "Right"): (0.2, _c(40, 5, 5, 5)),
            ("DG-mo", "Left"): (0.4, _c(120, 20, 15, 8)),
            ("DG-mo", "Right"): (0.4, _c(110, 18, 12, 6)),
            ("CEA", "Left"): (0.1, _c(0, 0, 0, 0)),
            ("CEA", "Right"): (0.1, _c(0, 0, 0, 0)),
        },
    }
    percell_counts = {
        "s1": {"LA": 40, "CA1": 90, "BLA": 10, "DG-mo": 60},
        "s2": {"LA": 15, "CA1": 60, "BLA": 5, "DG-mo": 40},
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

        # (8b) An all-zero region must NaN BOTH odds ratios. Haldane-Anscombe on
        # N==T==A==D==0 yields (0.5*0.5)/(0.5*0.5) = 1 -> log2 = 0.0, which reads as
        # "exactly at chance" for a region holding no cells. Found live on M3 (STRd).
        empty_df = pd.DataFrame({
            "N": [0.0], "TdT+_count": [0.0], "Fos+_count": [0.0], "Double+_count": [0.0],
            "region_acronym": ["EMPTY"],
        })
        add_metrics(empty_df, config2, Roles(tagged="TdT", activity="Fos"))
        check(not np.isfinite(empty_df["log2_odds_ratio_hc"].iloc[0]),
              "all-zero region -> log2_odds_ratio_hc is NaN, not a spurious 0.0")
        check(not np.isfinite(empty_df["log2_odds_ratio"].iloc[0]),
              "all-zero region -> log2_odds_ratio is NaN")
        check(not np.isfinite(empty_df["overlap_above_chance"].iloc[0]),
              "all-zero region -> overlap_above_chance is NaN")

        # (8c) Zero-cell regions are named out loud (increment 2 coverage caveat).
        named = _warn_empty_regions(
            pd.DataFrame({"DAPI_count": [0, 5], "region_acronym": ["ZED", "LA"]}), "DAPI")
        check(named == ["ZED"], "_warn_empty_regions names only the zero-count region")

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

        # --- D-2: stacking (mismatch raises; --stack-on-intersection drops cleanly) ----------
        print("\n[self-test] D-2 stacking")
        try:
            stack_animals([proj2, proj1], regions=["LA"])
            check(False, "mismatched marker sets must raise without --stack-on-intersection")
        except ValueError as exc:
            check("Animal2M" in str(exc) or "synthetic_Animal2M" in str(exc),
                  "marker-set mismatch error names both projects' declared sets")

        stacked = stack_animals([proj2, proj1], regions=["LA"], stack_on_intersection=True)
        check(set(stacked["animal"]) == {"Animal2M", "Animal1M"},
              "--stack-on-intersection stacks both animals into one table")
        check(not (set(_PAIR_METRIC_COLS) & set(stacked.columns)),
              "intersection {TdT} has < 2 markers -- pair metrics absent, not a NaN wall")
        check("Fos+_count" not in stacked.columns,
              "non-shared marker (Fos) column dropped entirely by --stack-on-intersection")
        check("TdT+_count" in stacked.columns and "tagging_rate" in stacked.columns,
              "shared marker (TdT) columns survive --stack-on-intersection")

        # --- D-3: group mapping ---------------------------------------------------------------
        print("\n[self-test] D-3 group mapping")
        no_map = apply_group_map(stacked, {})
        check((no_map["group"] == "unassigned").all(), "no mapping -> group='unassigned' + warning")

        try:
            apply_group_map(stacked, {"Animal2M": "recall"})
            check(False, "a mapping omitting an animal must raise")
        except ValueError:
            check(True, "group mapping omitting an animal raises (D-3 hard error)")

        mapped = apply_group_map(stacked, {"Animal2M": "recall", "Animal1M": "control"})
        check(set(mapped["group"]) == {"recall", "control"}, "explicit mapping assigns both groups")

        gmap_csv = base / "groups.csv"
        pd.DataFrame({"animal": ["Animal2M", "Animal1M"], "group": ["recall", "control"]}).to_csv(
            gmap_csv, index=False)
        loaded = load_group_map(gmap_csv, ["Animal1M=control2"])
        check(loaded == {"Animal2M": "recall", "Animal1M": "control2"},
              "CSV group map loads and a --group pair overrides it")

        # --- export shapes ----------------------------------------------------------------------
        print("\n[self-test] export shapes")
        long_path = write_long_csv(mapped, base / "out" / "animal_region_long.csv")
        check(long_path.exists(), "write_long_csv writes a file")
        reread = pd.read_csv(long_path)
        check(list(reread.columns[:2]) == ["group", "animal"],
              "long table leads with identity columns (group, animal, ...)")

        wide_paths = write_wide_pivots(mapped, base / "out", hemisphere="both")
        check(len(wide_paths) > 0, "write_wide_pivots writes at least one file")
        check(all(p.exists() for p in wide_paths), "every wide pivot path exists on disk")
        matches = [p for p in wide_paths if "TdT" in p.name and "density" in p.name]
        check(bool(matches), f"a TdT+_density wide pivot was written ({[p.name for p in wide_paths]})")
        if matches:
            piv = pd.read_csv(matches[0], index_col=0)
            check(set(piv.columns) == {"recall:Animal2M", "control:Animal1M"},
                  f"wide pivot columns are '{{group}}:{{animal}}' ({list(piv.columns)})")

        # --- interpretation plots (follow-up increment) --------------------------------------
        print("\n[self-test] interpretation plots -- backend-unchanged subprocess assertion")
        import subprocess
        scripts_dir = Path(__file__).resolve().parent
        backend_code = (
            "import matplotlib; matplotlib.use('pdf'); b0 = matplotlib.get_backend()\n"
            f"import sys; sys.path.insert(0, {str(scripts_dir)!r})\n"
            "import cockpit_animal\n"
            "assert matplotlib.get_backend() == b0, (b0, matplotlib.get_backend())\n"
        )
        proc = subprocess.run([sys.executable, "-c", backend_code],
                              capture_output=True, text=True)
        check(proc.returncode == 0,
              f"subprocess backend-unchanged assertion (bd5d11f regression guard) exits 0 "
              f"(stderr: {proc.stderr.strip()[:300]!r})")

        print("\n[self-test] build_figures (2-marker fixture, LA/CA1/BLA/DG-mo/CEA) -- "
              "all five keys")
        rolled2_full = rollup_animal(proj2, regions=["LA", "CA1", "BLA", "DG-mo", "CEA"],
                                     roles=roles2)
        per_slice2_full = creg.build_readout(proj2, regions=["LA", "CA1", "BLA", "DG-mo", "CEA"])
        figs2 = build_figures(rolled2_full, config2, roles2, per_slice=per_slice2_full,
                              top_n=20, min_cells=15)
        check(set(figs2.keys()) == {"region_ranking", "raw_vs_corrected", "evidence_guard",
                                    "slice_spread", "hemisphere_symmetry"},
              f"build_figures (2-marker) returns all five keys ({sorted(figs2.keys())})")
        check(all(isinstance(f, Figure) for f in figs2.values()),
              "every build_figures value is a matplotlib Figure")

        check(len(figs2["region_ranking"].axes) == 1, "region_ranking has exactly 1 axes")
        check(len(figs2["raw_vs_corrected"].axes) == 2, "raw_vs_corrected has exactly 2 axes")
        check(len(figs2["evidence_guard"].axes) == 2, "evidence_guard has exactly 2 axes")
        for name in ("region_ranking", "raw_vs_corrected", "evidence_guard"):
            fig = figs2[name]
            positions = [tuple(round(v, 6) for v in ax_.get_position().bounds)
                        for ax_ in fig.axes]
            check(len(positions) == len(set(positions)),
                  f"{name}: no two axes share an identical bounding box "
                  f"(dual-axis/twinx prohibition enforced, not just documented)")

        print("\n[self-test] all-zero region (CEA) excluded from figures 1-3, never rendered")
        for name in ("region_ranking", "raw_vs_corrected", "evidence_guard"):
            fig = figs2[name]
            yticklabels = [t.get_text() for ax_ in fig.axes for t in ax_.get_yticklabels()]
            check("CEA" not in yticklabels, f"{name}: CEA (all-zero) absent from y tick labels")
            footnote_text = " ".join(t.get_text() for t in fig.texts)
            check("CEA" in footnote_text, f"{name}: exclusion footnote names CEA")

        print("\n[self-test] 1-marker build_figures -- only evidence_guard + hemisphere_symmetry")
        rolled1_full = rollup_animal(proj1, regions=["LA", "CA1", "BLA", "DG-mo"], roles=roles1)
        figs1 = build_figures(rolled1_full, config1, roles1, per_slice=None,
                              top_n=20, min_cells=15)
        check(set(figs1.keys()) == {"evidence_guard", "hemisphere_symmetry"},
              f"1-marker build_figures returns exactly evidence_guard + hemisphere_symmetry "
              f"({sorted(figs1.keys())})")
        for f in figs1.values():
            plt.close(f)

        print("\n[self-test] figure 4 -- role-correct per-slice reactivation + anti-averaging")
        rolled2_la = rollup_animal(proj2, regions=["LA"], roles=roles2)
        per_slice_la = creg.build_readout(proj2, regions=["LA"])
        fig4 = plot_slice_spread(rolled2_la, per_slice_la, config2, roles2, top_n=8)

        la_slices = per_slice_la[(per_slice_la.region_acronym == "LA")
                                 & (per_slice_la.hemisphere == "both")]
        expected_role_correct = (la_slices["Double+_count"] / la_slices["TdT+_count"]).to_numpy()
        expected_declaration_order = la_slices["P(TdT+|Fos+)"].to_numpy()  # Double/Fos -- WRONG

        dot_offsets = np.asarray(fig4.axes[0].collections[0].get_offsets())
        plotted_dots = np.sort(dot_offsets[:, 0] / 100.0)
        check(np.allclose(plotted_dots, np.sort(expected_role_correct), atol=1e-9),
              "figure 4 per-slice dots equal Double+_count/TdT+_count (role-correct, recon 3)")
        check(not np.allclose(plotted_dots, np.sort(expected_declaration_order), atol=1e-6),
              "figure 4 per-slice dots differ from the declaration-order P(TdT+|Fos+) column")

        pooled_offsets = np.asarray(fig4.axes[0].collections[1].get_offsets())
        mean_offsets = np.asarray(fig4.axes[0].collections[2].get_offsets())
        pooled_x = float(pooled_offsets[0, 0]) / 100.0
        mean_x = float(mean_offsets[0, 0]) / 100.0
        expected_pooled = float(rolled2_la[(rolled2_la.region_acronym == "LA")
                                           & (rolled2_la.hemisphere == "both")]
                                ["reactivation_rate"].iloc[0])
        check(abs(pooled_x - expected_pooled) < 1e-9,
              "figure 4 pooled marker equals the long table's reactivation_rate to 1e-9")
        check(abs(pooled_x - mean_x) > 1e-6,
              "figure 4 pooled marker differs from mean-of-slices by > 1e-6 (anti-averaging)")
        plt.close(fig4)

        print("\n[self-test] min_cells de-emphasis (kept labeled, never dropped)")
        rolled2_4reg = rollup_animal(proj2, regions=["LA", "CA1", "BLA", "DG-mo"], roles=roles2)
        fig3b = plot_evidence_guard(rolled2_4reg, config2, roles2, top_n=20, min_cells=30)
        axL3b = fig3b.axes[0]
        # collections[-1] is the scatter (added after the hlines LineCollection).
        facecolors = axL3b.collections[-1].get_facecolor()
        neutral_rgb = mcolors.to_rgb(COLOR_NEUTRAL)
        n_neutral = sum(1 for row in facecolors if np.allclose(row[:3], neutral_rgb, atol=1e-6))
        below_regions = {"CA1", "BLA"}  # pooled Double+_count 27 and 15, both < min_cells=30
        check(n_neutral == len(below_regions),
              f"evidence_guard: {n_neutral} de-emphasised (neutral) mark(s) == "
              f"{len(below_regions)} below-min_cells region(s)")
        yticklabels3b = {t.get_text() for t in axL3b.get_yticklabels()}
        check(below_regions <= yticklabels3b,
              "de-emphasised regions remain present/labeled in figure 3 (never dropped)")
        plt.close(fig3b)

        print("\n[self-test] save_figures")
        saved = save_figures(figs2, base / "figout")
        check(len(saved) == len(figs2), "save_figures writes one PNG per figure")
        check(all(p.exists() and p.stat().st_size > 1000 for p in saved),
              "every saved PNG exists and is > 1000 bytes")
        for f in figs2.values():
            plt.close(f)

        print("\n[self-test] D-7 multi-animal fail-loud (figures)")
        stacked_two_animal = pd.concat([rolled2, rolled1], ignore_index=True, sort=False)
        try:
            plot_region_ranking(stacked_two_animal, config2, roles2, animal=None)
            check(False, "plot_region_ranking(animal=None) with 2 animals must raise ValueError")
        except ValueError as exc:
            check("Animal2M" in str(exc) and "Animal1M" in str(exc),
                  f"multi-animal ValueError names both animals ({exc})")

        print("\n[self-test] QV-1 sequential k ramp (monotonic lightness)")
        # A ramp's rule is monotonic lightness, NOT the categorical chroma/CVD checks --
        # assert the invariant directly rather than trusting fixed hexes.
        for base in (COLOR_ABOVE, COLOR_BELOW):
            for n in range(1, 6):
                ramp = _k_ramp(base, n)
                hls = [colorsys.rgb_to_hls(*mcolors.to_rgb(c)) for c in ramp]
                ls = [h[1] for h in hls]
                hues = [h[0] for h in hls]
                check(len(ramp) == n, f"_k_ramp({base}, {n}) returns {n} steps")
                check(all(a > b for a, b in zip(ls, ls[1:])),
                      f"_k_ramp({base}, {n}) lightness strictly decreasing (light->dark)")
                # to_hex quantizes to 8-bit, so hue round-trips with small error.
                check(max(hues) - min(hues) < 0.02,
                      f"_k_ramp({base}, {n}) holds one hue (spread {max(hues)-min(hues):.4f})")
        check(_k_ramp(COLOR_ABOVE, 1) == [COLOR_ABOVE], "_k_ramp(n=1) returns the base hue")

        print("\n[self-test] QV-2 _marker_colors uses the validated categorical pair")
        check(_marker_colors(["Fos", "TdT"]) == [COLOR_ABOVE, COLOR_BELOW],
              "two markers -> validated pair in declaration order")
        check(_marker_colors(["TdT"]) == [COLOR_ABOVE], "one marker -> COLOR_ABOVE")
        try:
            _marker_colors(["a", "b", "c"])
            check(False, "_marker_colors must raise on 3 markers")
        except ValueError as exc:
            check("validate_palette" in str(exc),
                  "3-marker ValueError names the palette validator")
        check(COLOR_NEUTRAL not in _marker_colors(["Fos", "TdT"]) + _marker_colors(["TdT"]),
              "COLOR_NEUTRAL is never a marker identity (it is the diverging midpoint)")

        print("\n[self-test] QV-3 quick-viz plots, order, exclusion, skip paths")
        qv_regions = ["CA1", "LA", "BLA"]
        fig_ov = plot_regions_overlap(rolled2, config2, roles2, regions=qv_regions)
        check(isinstance(fig_ov, Figure), "plot_regions_overlap returns a Figure (2-marker)")
        ticks = [t.get_text() for t in fig_ov.axes[0].get_xticklabels()]
        check(ticks == [r for r in qv_regions if r in ticks],
              f"x tick labels preserve the requested regions order ({ticks})")
        fig_sorted = plot_regions_overlap(rolled2, config2, roles2, regions=qv_regions,
                                          sort_by_value=True)
        sticks = [t.get_text() for t in fig_sorted.axes[0].get_xticklabels()]
        svals = [float(rolled2[(rolled2.region_acronym == r) &
                               (rolled2.hemisphere == "both")]["overlap_above_chance"].iloc[0])
                 for r in sticks]
        check(svals == sorted(svals, reverse=True),
              f"sort_by_value=True orders descending by value ({sticks})")

        fig_pos = plot_regions_positivity(rolled2, config2, roles2, regions=qv_regions)
        check(isinstance(fig_pos, Figure), "plot_regions_positivity returns a Figure")
        check(len(fig_pos.axes) == 1, "no k_values -> a single positivity axes")

        # zero-cell region excluded from the axis, named in the footnote -- never a zero
        # dot. Needs the UNFILTERED rollup: rolled2 is scoped to LA/CA1/BLA, so CEA (the
        # fixture's all-zero region) is not in that frame at all.
        rolled_all = rollup_animal(proj2, roles=roles2)
        zero_fig = plot_regions_overlap(rolled_all, config2, roles2)
        zero_ticks = [t.get_text() for t in zero_fig.axes[0].get_xticklabels()]
        check("CEA" not in zero_ticks, "zero-cell region absent from x tick labels")
        zfoot = " ".join(t.get_text() for t in zero_fig.texts)
        check("CEA" in zfoot,
              "zero-cell region IS named in the footnote (excluded, not silently dropped)")
        plt.close(zero_fig)

        # 1-marker: overlap skips (None, not empty axes), positivity still renders
        check(plot_regions_overlap(rolled1, config1, roles1) is None,
              "1-marker project -> plot_regions_overlap returns None (skip, not empty axes)")
        figs_qv1 = build_figures(rolled1, config1, roles1, quick_viz=True)
        check("regions_overlap" not in figs_qv1,
              "1-marker build_figures(quick_viz=True) omits regions_overlap")
        check("regions_positivity" in figs_qv1,
              "1-marker build_figures(quick_viz=True) still returns regions_positivity")
        check(len(figs_qv1["regions_positivity"].axes) == 1,
              "1-marker positivity has exactly one panel")

        # the five section-5 figures must be untouched by the new flag's default
        keys_default = list(build_figures(rolled2, config2, roles2).keys())
        check("regions_overlap" not in keys_default and "regions_positivity" not in keys_default,
              f"quick_viz defaults off -- section 5 keys unchanged ({keys_default})")
        check(list(build_figures(rolled2, config2, roles2, quick_viz=True).keys())[:len(keys_default)]
              == keys_default, "quick-viz keys are APPENDED after the existing five")

        try:
            build_figures(rolled2, config2, roles2, quick_viz=True, k_values=[2.0])
            check(False, "k_values without project_dir must raise")
        except ValueError as exc:
            check("project_dir" in str(exc), "k_values without project_dir raises, naming it")
        for f in list(figs_qv1.values()) + [fig_ov, fig_pos, fig_sorted]:
            plt.close(f)

    print()
    if failures:
        print(f"SELF-TEST FAILED ({len(failures)} check(s)):")
        for f in failures:
            print("  - " + f)
        sys.exit(1)
    print("SELF-TEST PASSED")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--project", type=Path, action="append", default=[],
                    help="QuPath project dir (repeatable; holds pipeline.yml, results/).")
    ap.add_argument("--regions", type=str, default=None,
                    help="Comma-separated acronyms (default: all included leaves per project).")
    ap.add_argument("--groups", type=Path, default=None,
                    help="D-3: YAML ({groups: {animal: group}}) or two-column CSV (animal,group).")
    ap.add_argument("--group", action="append", default=[], metavar="animal=group",
                    help="D-3: one-off animal=group mapping (repeatable; wins over --groups).")
    ap.add_argument("--tagged-marker", default=None,
                    help="D-1: override the tagged-marker role resolution.")
    ap.add_argument("--activity-marker", default=None,
                    help="D-1: override the activity-marker role resolution.")
    ap.add_argument("--n-source", choices=["auto", "anchor", "classifiable"], default="auto",
                    help="D-4: denominator source (default: auto).")
    ap.add_argument("--hemisphere", choices=["both", "L", "R"], default="both",
                    help="Wide-pivot hemisphere slice (the long table always keeps all three).")
    ap.add_argument("--stack-on-intersection", action="store_true",
                    help="D-2: stack on the shared marker set instead of failing on a mismatch.")
    ap.add_argument("--out-dir", type=Path, default=Path("results/animal"),
                    help="Output directory for the long CSV + wide/ pivots (gitignored).")
    ap.add_argument("--plots", action="store_true",
                    help="Also build the interpretation-plot figures (see PLOTTING in "
                        "--help) and save them as PNGs under <out-dir>/figures/.")
    ap.add_argument("--quick-viz", action="store_true",
                    help="also build the section-6 quick-viz plots (regions on X): "
                         "above-chance overlap and per-marker positivity")
    ap.add_argument("--k-values", type=str, default=None,
                    help="comma-separated k list for the quick-viz per-k series, e.g. "
                         "'2,2.5,3'. Recomputes from the per-cell exports, so it POOLS "
                         "HEMISPHERES and needs exactly one --project. Omit to use the k "
                         "locked in pipeline.yml (read straight from the rollup).")
    ap.add_argument("--sort-by-value", action="store_true",
                    help="quick-viz: sort regions descending by value instead of keeping "
                         "the --regions order")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                    help=f"Region cap for the ranked figures (default: {DEFAULT_TOP_N}).")
    ap.add_argument("--min-cells", type=int, default=DEFAULT_MIN_CELLS,
                    help="Evidence-guard (figure 3) de-emphasis threshold "
                        f"(default: {DEFAULT_MIN_CELLS}).")
    ap.add_argument("--self-test", action="store_true", help="Run the built-in self-test and exit.")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.project:
        ap.error("--project is required at least once (or use --self-test)")

    regions = ([r.strip() for r in args.regions.split(",") if r.strip()]
              if args.regions else None)

    print("Resolved roles per animal:")
    for p in args.project:
        config = creg.load_pipeline_config(p)
        roles = resolve_roles(config, tagged=args.tagged_marker, activity=args.activity_marker)
        print(f"  {p.name}: markers={config.marker_names}  "
              f"tagged={roles.tagged}  activity={roles.activity}")

    try:
        combined = stack_animals(args.project, regions=regions, tagged=args.tagged_marker,
                                 activity=args.activity_marker, n_source=args.n_source,
                                 stack_on_intersection=args.stack_on_intersection)
    except ValueError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    group_map = load_group_map(args.groups, args.group)
    combined = apply_group_map(combined, group_map)

    print("\nN_source split (both-hemisphere rows) + classifiable/anchor ratio:")
    both_rows = combined[combined["hemisphere"] == "both"]
    for animal, g in both_rows.groupby("animal"):
        n_classifiable = int((g["N_source"] == "classifiable").sum())
        n_anchor = int((g["N_source"] == "anchor_count").sum())
        anchor_cols = [c for c in g.columns if c.endswith("_count")
                      and "+" not in c and c != "N"]
        ratio_note = ""
        if anchor_cols and n_classifiable:
            classif = g[g["N_source"] == "classifiable"]
            ratio = (classif["N"] / classif[anchor_cols[0]].replace(0, np.nan)).mean()
            if np.isfinite(ratio):
                ratio_note = f"  classifiable/anchor ratio (mean) = {ratio:.4f}"
        print(f"  {animal}: {n_classifiable} region row(s) classifiable-N, "
              f"{n_anchor} anchor-N{ratio_note}")

    print("\nDAPI-dependence caveat: tagging_rate, activity_rate, overlap_above_chance and both "
          "log2_odds_ratio columns carry N (DAPI-derived) in their denominator. The white-matter/"
          "ventricle QC gates are currently parked as advisory, so DAPI is known to be "
          "over-detected in some regions -- inflated N deflates activity_rate and INFLATES "
          "overlap_above_chance. reactivation_rate, reverse_rate and jaccard carry no N and are "
          "unaffected. Switching --n-source to classifiable does NOT fix this (recon: 0.005% "
          "difference on M3) -- it only removes Excluded/non-finite rows from N, it does not "
          "correct DAPI over-detection. The real levers: re-arm the white-matter gate, raise "
          "k_robust, or lower cellExpansionMicrons.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    long_path = write_long_csv(combined, args.out_dir / "animal_region_long.csv")
    print(f"\nWrote long table -> {long_path}")
    for wp in write_wide_pivots(combined, args.out_dir, hemisphere=args.hemisphere):
        print(f"Wrote wide pivot -> {wp}")

    if args.plots:
        config0 = creg.load_pipeline_config(args.project[0])
        roles0 = resolve_roles(config0, tagged=args.tagged_marker, activity=args.activity_marker)
        per_slice = None
        if len(args.project) == 1:
            per_slice = creg.build_readout(args.project[0], regions=regions)
        else:
            print("  --plots: more than one --project given -- skipping figure 4 "
                 "(slice_spread needs a single project's per-slice readout).")
        print("\nBuilding interpretation plots...")
        k_values = None
        if args.k_values:
            k_values = [float(x) for x in args.k_values.split(",") if x.strip()]
            if len(args.project) != 1:
                sys.exit("ERROR: --k-values needs exactly one --project (the per-k series "
                         f"is recomputed from that project's per-cell exports; got "
                         f"{len(args.project)}).")
        figs = build_figures(combined, config0, roles0, per_slice=per_slice,
                             top_n=args.top_n, min_cells=args.min_cells,
                             quick_viz=args.quick_viz or bool(k_values),
                             regions=regions, k_values=k_values,
                             project_dir=args.project[0] if len(args.project) == 1 else None,
                             sort_by_value=args.sort_by_value)
        for p in save_figures(figs, args.out_dir):
            print(f"Wrote figure -> {p}")


if __name__ == "__main__":
    main()
