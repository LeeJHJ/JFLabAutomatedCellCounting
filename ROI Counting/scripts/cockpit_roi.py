#!/usr/bin/env python3
"""cockpit_roi.py -- read out manual-ROI counts, and say when they may not be poolable.

WHAT THIS IS
    The cheap half of the manual-ROI route. `scripts/roi_count.groovy` does the
    expensive work in QuPath (detect, classify, export); this module reads what it
    wrote and turns it into tables you can look at, without QuPath, without a JVM,
    and without re-detecting anything.

WHY THE COMPARABILITY MACHINERY IS THE MAIN FEATURE
    Images counted this way are expected to differ in magnification, Z handling and
    intensity (operator, 2026-08-05). That is fine for counting one image. It is NOT
    fine for putting two images' numbers in the same bar chart, and the failure is
    silent: two densities in the same units look comparable whatever produced them.

    So `roi_count.groovy` stamps a `settings_hash` on every row -- a digest of the
    rule that produced it, deliberately EXCLUDING the resolved threshold under the
    self-calibrating modes (re-measuring the cut per image is what makes images
    comparable, so it must not mark them as different) and INCLUDING pixel size
    (a different pixel size is a different measurement, not a rescaling --
    CLAUDE.md's comparability boundary).

    `comparability()` reports the groups; `describe_split()` says which fields
    actually differ. Neither refuses to do anything: this project's tooling advises
    and ranks, it does not block. The judgement stays with the operator.

WHAT THE OPERATOR SEES IS THE GROUND TRUTH
    Nothing here re-derives a cell. Every number traces to detections the operator
    could look at in QuPath with the overlay on. `acquisition_table()` exists to make
    the one thing you CANNOT see in a spreadsheet visible: how many pixels a nucleus
    actually spans on each image, which is what decides whether the segmentation
    behind these counts could have worked at all.

REUSE, NOT REIMPLEMENTATION
    The engram metric family (`tagging_rate` / `activity_rate` / `reactivation_rate` /
    `overlap_above_chance` / odds ratios / jaccard) is imported from cockpit_animal,
    and the marker roles from its `resolve_roles`. They are not recomputed here.
    `roi_count.groovy` emits its count columns under the SAME names the registered
    route uses (`<marker>+_count`, `Double+_count`, anchor without the '+') precisely
    so that import works.

READ-ONLY. Reads results/roi/*.tsv and results/roi/roi_counts_combined.csv, plus
pipeline.yml for the marker set. Writes nothing, runs no QuPath, touches no image.

Usage (from the Analysis root, braian env):
    conda run -n braian python scripts/cockpit_roi.py --self-test
    conda run -n braian python scripts/cockpit_roi.py --project "<project dir>"
    conda run -n braian python scripts/cockpit_roi.py --project "<dir>" --scope shape
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

# This module lives in the self-contained "ROI Counting/" folder, but it deliberately
# REUSES the registered route's config loader and metric family rather than carrying its
# own. So the repo's scripts/ has to be importable. Found by walking up rather than by a
# fixed number of parents, so moving this folder does not silently break the import.
def _repo_scripts() -> Path:
    here = Path(__file__).resolve()
    for d in here.parents:
        cand = d / "scripts" / "cockpit_regions.py"
        if cand.is_file():
            return cand.parent
    raise ImportError(
        f"could not find the pipeline's scripts/ directory at or above {here}. "
        f"cockpit_roi reuses cockpit_regions/cockpit_animal from it and will not "
        f"duplicate them; check that this folder still sits inside the Analysis repo.")


sys.path.insert(0, str(_repo_scripts()))

import cockpit_regions as creg  # noqa: E402  Config / load_pipeline_config -- do not fork
import cockpit_animal as ca  # noqa: E402  locked metric family + role resolution -- do not fork

ROI_SUBDIR = "results/roi"
COMBINED_NAME = "roi_counts_combined.csv"
AREA_COMBINED_NAME = "roi_area_combined.csv"

# Rows produced by independent marker-channel detection + overlap, rather than by the
# nucleus-anchored rule. Kept separable at every step: the operator enabled the override
# deliberately (2026-08-06), and the whole point of the flag is that a consumer can tell
# the two apart without knowing the naming convention.
ANCHORING_NUCLEUS = "nucleus-anchored"
ANCHORING_OVERLAP = "independent-overlap"

# Provenance fields that describe HOW an image was counted. Printed side by side when
# two settings groups are compared, so "these are not comparable" comes with a reason.
PROVENANCE_FIELDS = (
    "pixel_um", "n_z_planes", "anchor_channel", "threshold_mode", "span_frac",
    "sigma_um", "min_area_um2", "max_area_um2", "cell_expansion_um",
    "background_radius_um", "ring_gap_um", "ring_width_um", "k_scope",
)


# ---------------------------------------------------------------------------
# loading
# ---------------------------------------------------------------------------
def roi_dir(project_dir: Path) -> Path:
    return Path(project_dir) / ROI_SUBDIR


def load_combined(projects: Path | str | list) -> pd.DataFrame:
    """The growing per-(image x roi x class) table from one or several projects.

    Accepts a list so several manual-count projects can be read at once; a `project`
    column is added either way, because the moment two projects are in one frame the
    provenance question is live and the answer must be in the data.
    """
    if isinstance(projects, (str, Path)):
        projects = [projects]
    frames = []
    for p in projects:
        p = Path(p)
        path = roi_dir(p) / COMBINED_NAME
        if not path.exists():
            print(f"  no {COMBINED_NAME} under {roi_dir(p)} -- has roi_count.groovy run there yet?",
                  file=sys.stderr)
            continue
        df = pd.read_csv(path)
        df.insert(0, "project", p.name)
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_area(projects: Path | str | list) -> pd.DataFrame:
    """The per-(image x roi x channel) area/intensity table, if the area pass has run.

    Separate file, separate loader: an area-only run (DG-sg and friends) produces this
    and no counts at all, so the two must not be coupled.
    """
    if isinstance(projects, (str, Path)):
        projects = [projects]
    frames = []
    for p in projects:
        p = Path(p)
        path = roi_dir(p) / AREA_COMBINED_NAME
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df.insert(0, "project", p.name)
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def load_percell(project_dir: Path) -> pd.DataFrame:
    """Every per-cell row the ROI route exported for this project, with `image` added.

    Same schema as the registered route's `*__percell_export.tsv`, which is what lets
    `scripts/cockpit_marker_gui.py` (set k by looking at the cells) run on ROI output
    with no changes.
    """
    frames = []
    for path in sorted(roi_dir(project_dir).glob("*__percell_export.tsv")):
        df = pd.read_csv(path, sep="\t")
        df.insert(0, "image", path.name.split("__id")[0])
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def load_config(project_dir: Path) -> creg.Config:
    """The marker set, from the same pipeline.yml loader every other module uses."""
    return creg.load_pipeline_config(Path(project_dir))


# ---------------------------------------------------------------------------
# reshaping
# ---------------------------------------------------------------------------
def column_prefix(marker: str, cls: str, anchor_name: str | None) -> str:
    """The wide-table column prefix for a tidy (marker, class) pair.

    This is `columnPrefixFor` from 03_export_region_table.groovy and roi_count.groovy,
    in Python: the ANCHOR keeps its bare name (`DAPI_count`) while every marker takes
    the '+' form (`TdT+_count`). The distinction is load-bearing -- `cockpit_regions`
    and `cockpit_animal` look up the denominator as `<anchor>_count` -- and the tidy CSV
    stores class="DAPI+" for the anchor, so the prefix cannot be read off `class` alone.
    """
    if marker == "Double+":
        return "Double+"
    if anchor_name is not None and marker == anchor_name:
        return marker
    return cls


def wide(df: pd.DataFrame, scope: str = "pooled",
         anchor_name: str | None = None) -> pd.DataFrame:
    """One row per (project, image, roi_name); one count + density column per class.

    scope='pooled' uses the by-name rollup (three shapes named LA become one LA row);
    scope='shape' keeps every drawn shape separate. Both are exported by the groovy;
    which one is right depends on whether you care about between-shape variability.

    Pass anchor_name (from pipeline.yml) so the anchor column comes out as
    `<anchor>_count` rather than `<anchor>+_count` -- that is the name the metric
    family looks for as its denominator.
    """
    if df.empty:
        return pd.DataFrame()
    if scope not in {"pooled", "shape"}:
        raise ValueError(f"scope must be 'pooled' or 'shape', not {scope!r}")
    sub = df[df["scope"] == scope].copy()
    if sub.empty:
        return pd.DataFrame()

    # Independent/overlap categories keep their own literal names; only the
    # nucleus-anchored ones go through the anchor-vs-marker prefix rule.
    if "anchoring" in sub.columns:
        is_nuc = sub["anchoring"] == ANCHORING_NUCLEUS
    else:
        is_nuc = pd.Series(True, index=sub.index)
    sub["_col"] = [column_prefix(m, c, anchor_name) if nuc else m
                   for m, c, nuc in zip(sub["marker"], sub["class"], is_nuc)]
    keys = ["project", "image", "roi_name", "settings_hash", "n_shapes", "area_mm2"]
    keys = [k for k in keys if k in sub.columns]
    # pivot_table DROPS any row with NaN in an index column, silently. A count that
    # vanishes because one provenance field was blank is exactly the kind of quiet loss
    # this module exists to prevent, so missing keys are filled and reported instead.
    missing = {k: int(sub[k].isna().sum()) for k in keys if sub[k].isna().any()}
    if missing:
        print(f"  NOTE: filling missing key values before pivoting (rows would otherwise "
              f"be dropped silently): {missing}", file=sys.stderr)
        for k in missing:
            sub[k] = sub[k].fillna("" if sub[k].dtype == object else 0)
    n_before = len(sub)
    counts = sub.pivot_table(index=keys, columns="_col", values="count",
                             aggfunc="sum", observed=True)
    counts.columns = [f"{c}_count" for c in counts.columns]
    dens = sub.pivot_table(index=keys, columns="_col", values="density",
                           aggfunc="sum", observed=True)
    dens.columns = [f"{c}_density" for c in dens.columns]
    out = counts.join(dens).reset_index()
    n_after = int(counts.notna().sum().sum())
    if n_after != n_before:
        print(f"  NOTE: {n_before} tidy rows collapsed into {n_after} filled cells -- "
              f"expected when several shapes share a name, suspicious otherwise.",
              file=sys.stderr)

    # Carry the provenance through, so a wide row is still self-describing.
    prov = [c for c in PROVENANCE_FIELDS if c in sub.columns] + ["anchor_threshold"]
    prov = [c for c in prov if c in sub.columns]
    if prov:
        first = sub.groupby([k for k in keys if k in sub.columns], observed=True)[prov].first().reset_index()
        out = out.merge(first, on=[k for k in keys if k in sub.columns], how="left")
    return out


def add_metrics(wide_df: pd.DataFrame, config: creg.Config,
                tagged: str | None = None, activity: str | None = None) -> pd.DataFrame:
    """Attach the locked engram metric family, computed by cockpit_animal.

    The anchor count becomes `N`, which is what `cockpit_animal.add_metrics` expects.
    Everything downstream of that -- including the choice to report
    `overlap_above_chance` rather than a raw Double+/TdT+ ratio -- is that module's
    definition, not a second one written here.
    """
    if wide_df.empty:
        return wide_df
    out = wide_df.copy()
    anchor_col = f"{config.anchor_name}_count"
    if anchor_col not in out.columns:
        print(f"  no {anchor_col} column -- cannot compute rates without a denominator",
              file=sys.stderr)
        return out
    out["N"] = out[anchor_col]
    roles = ca.resolve_roles(config, tagged=tagged, activity=activity)
    return ca.add_metrics(out, config, roles)


# ---------------------------------------------------------------------------
# comparability
# ---------------------------------------------------------------------------
def area_wide(area_df: pd.DataFrame, scope: str = "pooled") -> pd.DataFrame:
    """One row per (project, image, roi_name); one column block per channel."""
    if area_df.empty:
        return pd.DataFrame()
    sub = area_df[area_df["scope"] == scope].copy()
    if sub.empty:
        return pd.DataFrame()
    keys = [k for k in ("project", "image", "roi_name", "n_shapes", "roi_area_mm2",
                        "settings_hash") if k in sub.columns]
    metrics = [m for m in ("cut", "pos_area_mm2", "area_frac", "mean", "mean_pos",
                           "intden", "blob_count", "blob_median_um2", "blob_p90_um2")
               if m in sub.columns]
    out = sub.pivot_table(index=keys, columns="channel", values=metrics,
                          aggfunc="first", observed=True)
    out.columns = [f"{ch}_{metric}" for metric, ch in out.columns]
    return out.reset_index()


def join_counts_area(counts_wide: pd.DataFrame, area_w: pd.DataFrame,
                     config: creg.Config) -> pd.DataFrame:
    """Counts + area side by side, plus the metrics that need BOTH.

    THE HEADLINE ONE, and the reason the area pass exists (operator, 2026-08-06):

        <marker>+_per_<anchor>_area_mm2 = nucleus-anchored <marker>+ count
                                          / area actually occupied by <anchor>

    That normalises a count to the tissue that could have carried it, rather than to
    whatever shape happened to be drawn -- which is what makes two hand-drawn ROIs of
    different size and different cellularity comparable at all.

    Also emitted: the pure-area analogue (<marker> area / <anchor> area) for fields
    where counting is not defensible, and the same count normalised to the marker's own
    positive area.
    """
    if counts_wide.empty and area_w.empty:
        return pd.DataFrame()
    if area_w.empty:
        return counts_wide
    keys = [k for k in ("project", "image", "roi_name") if k in area_w.columns
            and k in counts_wide.columns]
    if counts_wide.empty or not keys:
        return area_w
    out = counts_wide.merge(area_w.drop(columns=[c for c in ("settings_hash", "n_shapes")
                                                 if c in area_w.columns]),
                            on=keys, how="outer", suffixes=("", "_area"))
    anchor = config.anchor_name
    denom_col = f"{anchor}_pos_area_mm2"
    if denom_col not in out.columns:
        return out
    denom = pd.to_numeric(out[denom_col], errors="coerce")
    # A zero or missing anchor area is not a zero denominator to divide by -- it means
    # the anchor cut found nothing, so the ratio is undefined rather than infinite.
    denom = denom.where(denom > 0)
    for m in config.marker_names:
        cnt_col = f"{m}+_count"
        if cnt_col in out.columns:
            out[f"{m}+_per_{anchor}_area_mm2"] = pd.to_numeric(out[cnt_col], errors="coerce") / denom
        obj_col = f"{m}_obj_count"
        if obj_col in out.columns:
            out[f"{m}_obj_per_{anchor}_area_mm2"] = pd.to_numeric(out[obj_col], errors="coerce") / denom
        marker_area = f"{m}_pos_area_mm2"
        if marker_area in out.columns:
            out[f"{m}_area_per_{anchor}_area"] = pd.to_numeric(out[marker_area], errors="coerce") / denom
    if config.emit_double and f"Double+_count" in out.columns:
        out[f"Double+_per_{anchor}_area_mm2"] = pd.to_numeric(out["Double+_count"], errors="coerce") / denom
    return out


def comparability(df: pd.DataFrame) -> pd.DataFrame:
    """One row per settings_hash: which images share a counting rule.

    A single row means everything in this frame was counted the same way. More than
    one means pooling across them mixes rules, and the difference between two groups
    may be a settings difference rather than biology.
    """
    if df.empty or "settings_hash" not in df.columns:
        return pd.DataFrame()
    rows = []
    for h, grp in df.groupby("settings_hash", observed=True):
        row = {"settings_hash": h,
               "n_images": grp["image"].nunique(),
               "images": ", ".join(sorted(grp["image"].unique())[:4]) +
                         ("  ..." if grp["image"].nunique() > 4 else "")}
        for f in PROVENANCE_FIELDS:
            if f in grp.columns:
                vals = grp[f].dropna().unique()
                row[f] = vals[0] if len(vals) == 1 else f"<{len(vals)} values>"
        rows.append(row)
    return pd.DataFrame(rows)


def describe_split(df: pd.DataFrame) -> list[str]:
    """Which provenance fields actually differ between the settings groups.

    The hash says 'not the same rule'; this says WHICH part, which is the difference
    between an unusable warning and an actionable one. Ordered so the fields that
    break comparability outright come first.
    """
    if df.empty or "settings_hash" not in df.columns:
        return []
    if df["settings_hash"].nunique() <= 1:
        return []
    # Pixel size and Z depth change what a cell physically IS, so they are reported
    # ahead of parameters that merely change where a cut sits (CLAUDE.md: relative
    # thresholds absorb brightness drift, never geometry).
    hard = ("pixel_um", "n_z_planes", "anchor_channel")
    out = []
    for f in PROVENANCE_FIELDS:
        if f not in df.columns:
            continue
        vals = sorted({str(v) for v in df[f].dropna().unique()})
        if len(vals) > 1:
            tag = "GEOMETRY" if f in hard else "setting"
            out.append(f"{tag}  {f}: {', '.join(vals[:5])}"
                       + ("  ..." if len(vals) > 5 else ""))
    out.sort(key=lambda s: 0 if s.startswith("GEOMETRY") else 1)
    return out


def print_comparability(df: pd.DataFrame) -> None:
    """Advisory report. Never refuses -- ranks the risk and hands back the call."""
    table = comparability(df)
    if table.empty:
        print("no counts loaded.")
        return
    n = len(table)
    print(f"settings groups: {n}")
    if n == 1:
        print("  every image here was counted by the same rule -- these numbers are poolable.")
        return
    print("  MORE THAN ONE RULE produced these numbers. Pooling them mixes rules, and a")
    print("  difference between groups may be a settings difference rather than biology.")
    print("  What differs:")
    for line in describe_split(df):
        print(f"    {line}")
    print("  Nothing here is blocked. If the comparison is deliberate, say so alongside")
    print("  the number; if it is not, re-count the odd images with matching settings.")
    print()
    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(table.to_string(index=False))


# ---------------------------------------------------------------------------
# acquisition advisories -- the same checks roi_count.groovy prints, on the exports
# ---------------------------------------------------------------------------
def acquisition_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per image: the micron settings re-expressed in that image's own pixels.

    Micron parameters are the right way to WRITE these down and the wrong way to judge
    them. Whether a 2 um sigma can segment a nucleus depends on how many pixels the
    nucleus spans, and that is what changes between magnifications. This is the table
    that makes a mismatched parameter set visible instead of inferable.
    """
    if df.empty:
        return pd.DataFrame()
    cols = ["image", "pixel_um", "n_z_planes", "sigma_um", "min_area_um2",
            "cell_expansion_um", "anchor_threshold", "threshold_mode", "settings_hash"]
    cols = [c for c in cols if c in df.columns]
    per = df.groupby("image", observed=True)[[c for c in cols if c != "image"]].first().reset_index()
    px = per["pixel_um"].astype(float)
    per["nucleus_10um_px"] = (10.0 / px).round(1)
    if "sigma_um" in per:
        per["sigma_px"] = (per["sigma_um"].astype(float) / px).round(2)
    if "min_area_um2" in per:
        per["min_area_px"] = (per["min_area_um2"].astype(float) / (px * px)).round(0)
    if "cell_expansion_um" in per:
        per["expansion_px"] = (per["cell_expansion_um"].astype(float) / px).round(2)
    per["advisories"] = [" | ".join(_advise(r)) or "-" for _, r in per.iterrows()]
    return per


def _advise(row: pd.Series) -> list[str]:
    """Same bands roi_count.groovy applies, so the notebook and QuPath never disagree."""
    out = []
    if "nucleus_10um_px" in row and float(row["nucleus_10um_px"]) < 5.0:
        out.append(f"pixel-limited ({row['nucleus_10um_px']} px per 10 um nucleus)")
    if "sigma_px" in row and pd.notna(row["sigma_px"]):
        if float(row["sigma_px"]) < 0.8:
            out.append(f"sigma {row['sigma_px']} px -- below 1 px it does nothing")
        elif float(row["sigma_px"]) > 6.0:
            out.append(f"sigma {row['sigma_px']} px -- will merge adjacent nuclei")
    if "min_area_px" in row and pd.notna(row["min_area_px"]) and float(row["min_area_px"]) < 6:
        out.append(f"min area {row['min_area_px']} px -- admits single-pixel noise")
    if "expansion_px" in row and pd.notna(row["expansion_px"]):
        e = float(row["expansion_px"])
        if 0 < e < 1.0:
            out.append(f"expansion {e} px -- whole-cell/cytoplasm compartment near-empty")
    if "n_z_planes" in row and pd.notna(row["n_z_planes"]) and float(row["n_z_planes"]) > 1:
        out.append(f"{int(float(row['n_z_planes']))} Z-planes -- counts are for the ROI's own plane")
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def report(project_dir: Path, scope: str = "pooled") -> pd.DataFrame:
    """The whole readout for one project, printed. Returns the wide table."""
    df = load_combined(project_dir)
    if df.empty:
        print(f"no ROI counts under {roi_dir(project_dir)}.")
        print("Run scripts/roi_count.groovy on at least one image in QuPath first.")
        return pd.DataFrame()

    print("=" * 78)
    print(f"MANUAL-ROI COUNTS -- {Path(project_dir).name}")
    print("=" * 78)
    print_comparability(df)

    print()
    print("ACQUISITION -- micron settings in each image's own pixels")
    acq = acquisition_table(df)
    show = [c for c in ("image", "pixel_um", "nucleus_10um_px", "sigma_px",
                        "min_area_px", "expansion_px", "anchor_threshold",
                        "threshold_mode", "advisories") if c in acq.columns]
    with pd.option_context("display.max_columns", None, "display.width", 200,
                           "display.max_colwidth", 60):
        print(acq[show].to_string(index=False))

    config = None
    try:
        config = load_config(project_dir)
    except FileNotFoundError as exc:
        print(f"\n  no pipeline.yml: {exc}", file=sys.stderr)
    w = wide(df, scope=scope, anchor_name=(config.anchor_name if config else None))
    if config is not None:
        try:
            w = add_metrics(w, config)
        except ValueError as exc:
            print(f"\n  metrics skipped: {exc}", file=sys.stderr)
        aw = area_wide(load_area(project_dir), scope=scope)
        if not aw.empty:
            w = join_counts_area(w, aw, config)

    print()
    print(f"COUNTS ({scope})")
    drop = set(PROVENANCE_FIELDS) | {"settings_hash", "anchor_threshold"}
    show = [c for c in w.columns if c not in drop]
    with pd.option_context("display.max_columns", None, "display.width", 220):
        print(w[show].to_string(index=False))
    if any(c.endswith("_obj_count") for c in w.columns):
        print()
        print("  *_obj_count and Double_overlap_* came from INDEPENDENT marker-channel")
        print("  detection, not from the nucleus-anchored rule. A marker blob is not")
        print("  necessarily a cell, and overlap is a weaker claim than one nucleus")
        print("  carrying both markers. Do not compare them with the columns beside them.")
    print()
    print("Every number above traces to detections you can put on the image in QuPath.")
    print("If the overlay looks wrong, the number is wrong -- re-count, do not reinterpret.")
    return w


def _self_test() -> None:
    """Exercised without QuPath: build a synthetic combined CSV and check the readout."""
    import tempfile

    def check(cond: bool, msg: str) -> None:
        if not cond:
            raise AssertionError(msg)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "proj"
        (base / ROI_SUBDIR).mkdir(parents=True)
        (base / "pipeline.yml").write_text(
            'anchor:\n  name: "DAPI"\n  channel: "DAPI-T4"\n'
            'markers:\n'
            '  - name: "Fos"\n    channel: "AF488-T3"\n    compartment: "nuclear"\n'
            '  - name: "TdT"\n    channel: "AF568-T2"\n    compartment: "whole-cell"\n'
            'exclude_acronyms: []\nk_robust: 3.0\nring:\n  gap_um: 1.0\n  width_um: 8.0\n')

        prov_a = dict(image="imgA", pixel_um=0.46, n_z_planes=1, anchor_channel="DAPI-T4",
                      threshold_mode="image_span", span_frac=0.25, anchor_threshold=700,
                      sigma_um=2.0, min_area_um2=20.0, max_area_um2=250.0,
                      cell_expansion_um=5.0, background_radius_um=10.0,
                      ring_gap_um=1.0, ring_width_um=8.0, k_scope="image",
                      k_Fos=3.0, k_TdT=2.0, settings_hash="aaaa1111")
        # Same rule, different resolved threshold -- must NOT split the group, or the
        # self-calibrating design would mark every image incomparable with every other.
        prov_b = dict(prov_a, image="imgB", anchor_threshold=915)
        # Different pixel size -- MUST split the group.
        prov_c = dict(prov_a, image="imgC", pixel_um=2.5, settings_hash="cccc3333")

        rows = []
        for prov, dapi, fos, tdt, dbl in ((prov_a, 1000, 100, 200, 40),
                                          (prov_b, 900, 90, 180, 30),
                                          (prov_c, 500, 50, 100, 10)):
            for scope in ("shape", "pooled"):
                for marker, cls, cnt in (("DAPI", "DAPI+", dapi), ("Fos", "Fos+", fos),
                                         ("TdT", "TdT+", tdt), ("Double+", "Double+", dbl)):
                    rows.append(dict(scope=scope, roi_name="LA", n_shapes=1, z=0,
                                     area_mm2=0.5, marker=marker, cls=cls, count=cnt,
                                     density=cnt / 0.5, **prov))
        # NOTE: class="DAPI+" for the anchor is what roi_count.groovy ACTUALLY writes
        # (verified against a real headless run, 2026-08-05). An earlier version of this
        # fixture wrote "DAPI" here, which made the anchor column resolve by accident and
        # hid the fact that wide() could not name the denominator column correctly.
        df = pd.DataFrame(rows).rename(columns={"cls": "class"})
        df.to_csv(base / ROI_SUBDIR / COMBINED_NAME, index=False)

        loaded = load_combined(base)
        check(len(loaded) == len(rows), f"load_combined lost rows: {len(loaded)} vs {len(rows)}")
        check("project" in loaded.columns, "load_combined must add a project column")

        comp = comparability(loaded)
        check(len(comp) == 2, f"expected 2 settings groups, got {len(comp)}")
        same = comp[comp["settings_hash"] == "aaaa1111"].iloc[0]
        check(same["n_images"] == 2,
              "imgA and imgB share a rule and differ only in the RE-MEASURED threshold; "
              "they must stay in one group or self-calibration would read as incomparability")

        split = describe_split(loaded)
        check(any(s.startswith("GEOMETRY") and "pixel_um" in s for s in split),
              f"pixel_um must be reported first as a geometry break; got {split}")

        config = load_config(base)
        w = wide(loaded, scope="pooled", anchor_name=config.anchor_name)
        check(len(w) == 3, f"expected one pooled row per image, got {len(w)}")
        check("TdT+_count" in w.columns, f"missing TdT+_count; columns={list(w.columns)}")
        check("DAPI_count" in w.columns,
              f"anchor column must be <anchor>_count with no '+', because that is what "
              f"cockpit_animal looks up as the denominator; columns={list(w.columns)}")
        check("DAPI+_count" not in w.columns, "anchor must not also appear in '+' form")

        # Without the anchor name there is no way to tell the anchor from a marker, so the
        # column keeps its tidy-CSV class. Asserted so the fallback stays deliberate.
        w_noanchor = wide(loaded, scope="pooled")
        check("DAPI+_count" in w_noanchor.columns,
              f"without anchor_name the anchor should fall back to its class form; "
              f"columns={list(w_noanchor.columns)}")
        m = add_metrics(w, config)
        check("overlap_above_chance" in m.columns, "metric family did not attach")
        a = m[m["image"] == "imgA"].iloc[0]
        # Reproduce the locked definition by hand: (D*N)/(T*A).
        expect = (40 * 1000) / (200 * 100)
        check(abs(float(a["overlap_above_chance"]) - expect) < 1e-9,
              f"overlap_above_chance {a['overlap_above_chance']} != {expect}")

        acq = acquisition_table(loaded)
        c = acq[acq["image"] == "imgC"].iloc[0]
        check(float(c["nucleus_10um_px"]) == 4.0, f"nucleus_10um_px wrong: {c['nucleus_10um_px']}")
        check("pixel-limited" in c["advisories"],
              f"2.5 um/px must be flagged pixel-limited; got {c['advisories']!r}")
        a_row = acq[acq["image"] == "imgA"].iloc[0]
        check("pixel-limited" not in a_row["advisories"],
              f"0.46 um/px must NOT be flagged; got {a_row['advisories']!r}")

        # ---- area pass + the metrics that need both tables -----------------------
        arows = []
        for img, dapi_area, fos_area in (("imgA", 0.10, 0.02), ("imgB", 0.09, 0.018),
                                         ("imgC", 0.05, 0.01)):
            for scope in ("shape", "pooled"):
                for ch, pos in (("DAPI", dapi_area), ("Fos", fos_area), ("TdT", 0.03)):
                    arows.append(dict(scope=scope, roi_name="LA", n_shapes=1, z=0,
                                      roi_area_mm2=0.5, channel=ch, cut=700,
                                      pos_area_mm2=pos, area_frac=pos / 0.5, mean=12.0,
                                      mean_pos=40.0, intden=1e6, blob_count=100,
                                      blob_median_um2=30.0, blob_p90_um2=90.0,
                                      image=img, settings_hash="aaaa1111"))
        pd.DataFrame(arows).to_csv(base / ROI_SUBDIR / AREA_COMBINED_NAME, index=False)

        area = load_area(base)
        check(not area.empty, "load_area found nothing")
        aw = area_wide(area, scope="pooled")
        check(len(aw) == 3, f"expected one pooled area row per image, got {len(aw)}")
        check("DAPI_pos_area_mm2" in aw.columns, f"columns={list(aw.columns)}")

        joined = join_counts_area(m, aw, config)
        ja = joined[joined["image"] == "imgA"].iloc[0]
        # THE headline metric: Fos+ count / DAPI+ area. imgA has 100 Fos+ over 0.10 mm^2.
        check(abs(float(ja["Fos+_per_DAPI_area_mm2"]) - 1000.0) < 1e-6,
              f"Fos+_per_DAPI_area_mm2 {ja['Fos+_per_DAPI_area_mm2']} != 1000")
        check(abs(float(ja["Fos_area_per_DAPI_area"]) - 0.2) < 1e-9,
              f"Fos_area_per_DAPI_area {ja['Fos_area_per_DAPI_area']} != 0.2")

        # A zero anchor area must give NaN, never inf: "the anchor cut found nothing" is
        # not the same statement as "infinitely many cells per unit area".
        aw0 = aw.copy()
        aw0.loc[aw0["image"] == "imgA", "DAPI_pos_area_mm2"] = 0.0
        j0 = join_counts_area(m, aw0, config)
        v0 = j0.loc[j0["image"] == "imgA", "Fos+_per_DAPI_area_mm2"].iloc[0]
        check(pd.isna(v0), f"zero DAPI+ area must give NaN, got {v0}")

        # ---- independent-detection rows stay in their own columns ----------------
        obj_rows = []
        for scope in ("shape", "pooled"):
            for marker, cnt in (("Fos_obj", 500), ("Double_overlap_Fos_TdT", 20)):
                obj_rows.append(dict(project=base.name, scope=scope, roi_name="LA",
                                     n_shapes=1, z=0, area_mm2=0.5, marker=marker,
                                     **{"class": marker},
                                     anchoring=ANCHORING_OVERLAP, count=cnt,
                                     density=cnt / 0.5, **prov_a))
        base_rows = loaded.copy()
        base_rows["anchoring"] = ANCHORING_NUCLEUS
        mixed = pd.concat([base_rows, pd.DataFrame(obj_rows)], ignore_index=True)
        wm = wide(mixed, scope="pooled", anchor_name=config.anchor_name)
        check("Fos_obj_count" in wm.columns,
              f"independent-detection counts must keep their own column; {list(wm.columns)}")
        check("Fos_obj+_count" not in wm.columns,
              "an independent-detection category must NOT be given the '+' marker form")
        row = wm[wm["image"] == "imgA"].iloc[0]
        check(int(row["Fos+_count"]) == 100 and int(row["Fos_obj_count"]) == 500,
              "nucleus-anchored and independent counts must not be merged: "
              f"Fos+={row['Fos+_count']} Fos_obj={row['Fos_obj_count']}")

        empty = load_combined(Path(tmp) / "nope")
        check(empty.empty, "a missing project must give an empty frame, not raise")
        check(comparability(empty).empty, "comparability of an empty frame must be empty")

    print("cockpit_roi self-test: all checks passed")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Read out manual-ROI counts and flag non-poolable settings groups.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--project", type=Path, action="append",
                   help="QuPath project directory (repeatable to compare several)")
    p.add_argument("--scope", choices=["pooled", "shape"], default="pooled",
                   help="pooled: one row per ROI name. shape: one row per drawn shape.")
    p.add_argument("--self-test", action="store_true", help="run the built-in checks and exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0
    if not args.project:
        print("nothing to do: pass --project <QuPath project dir> (or --self-test)")
        return 1
    if len(args.project) == 1:
        report(args.project[0], scope=args.scope)
        return 0
    df = load_combined(args.project)
    if df.empty:
        print("no ROI counts found in any of those projects.")
        return 1
    print_comparability(df)
    with pd.option_context("display.max_columns", None, "display.width", 220):
        anchor = None
        try:
            anchor = load_config(args.project[0]).anchor_name
        except FileNotFoundError:
            pass
        print(wide(df, scope=args.scope, anchor_name=anchor).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
