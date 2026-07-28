#!/usr/bin/env python3
"""cockpit_regions.py -- region-of-interest readout CSV (section-pipeline cockpit, increment 2).

Given an operator-supplied list of Allen acronyms, emit a tidy PER-SLICE CSV of DAPI/marker
counts + densities + reactivation ratios per region, with ontology-driven, exclusion-aware
roll-up and a hemisphere split (Left/Right) plus a pooled ("both") row. Marker columns are
generated dynamically from ``pipeline.yml`` -- a TdT-only config emits DAPI + TdT columns
ONLY (no Fos, no Double), with no errors.

READ-ONLY. Reuses artifacts already on disk (per-slice ``*__region_table.tsv`` written by
``03_export_region_table.groovy``, ``pipeline.yml``, ``allen_mouse_10um_java-Ontology.json``).
It never re-runs QuPath / detection / ABBA and never reads an image.

WHY THE ONTOLOGY, NOT THE region_table's PARENT ROWS (load-bearing):
  The region_table's parent-rollup rows follow QuPath's *annotation* hierarchy, which does
  NOT match the Allen ontology (verified: the ``BMA`` parent row reads DAPI=0 while its child
  ``BMAa`` holds the cells -- BMAa is not nested under BMA in QuPath). So we roll up from the
  ontology tree instead, summing only the DATA FRONTIER under each requested acronym:

    included_leaves(R) = { present acronyms that are ontology descendants-or-self of R
                           AND have no present ontology descendant (the frontier) }
                         MINUS ( exclude_acronyms UNION their descendants ).

  Each frontier row's count == its own (finest-containing) bucket, so the leaf set is
  non-overlapping and safe to sum. This makes LA->{LA} and CA1->{CA1} resolve correctly even
  though their region_table rows are geometrically ``is_leaf=False`` with no finer child in
  the data (pure geometric-is_leaf summation would report them as 0).

  count(R,hemi,cat) and area_mm2(R,hemi) are summed over the IDENTICAL frontier-leaf set, so
  there is never denominator drift. Excluding DG-sg drops both its count and its area from
  every roll-up. Pooled ("both") = Left+Right summed counts/areas, with densities and ratios
  RECOMPUTED from the pooled sums (never averaged).

  Coverage caveat (surfaced, not hidden): frontier summation omits cells whose finest
  containing annotation is a non-frontier intermediate node (whole-brain ~16%; focused engram
  regions ~0-0.3%). ``--coverage`` prints the per-slice fraction captured. This matches the
  GOAL's ``count = sum over included_leaves`` definition.

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/cockpit_regions.py --self-test
  conda run -n braian python scripts/cockpit_regions.py \\
      --project "wBA/wBA1-2_2-1-tdt-only 072026 project"
  conda run -n braian python scripts/cockpit_regions.py \\
      --project "wBA/wBA1-2_2-1-tdt-only 072026 project" \\
      --regions LA,BLA,BMA,HPF,CA1 --coverage
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

VALID_COMPARTMENTS = {"nuclear", "cytoplasmic", "whole-cell"}


# ---------------------------------------------------------------------------
# pipeline.yml config
# ---------------------------------------------------------------------------
@dataclass
class Config:
    anchor_name: str
    markers: list[dict]            # [{name, channel, compartment}, ...] -- non-anchor only
    exclude_acronyms: set[str]
    animal: str | None = None      # optional declared subject id (overrides filename parse)

    @property
    def marker_names(self) -> list[str]:
        return [m["name"] for m in self.markers]

    @property
    def emit_double(self) -> bool:
        # Double+ is structurally possible only with >=2 non-anchor markers (D-03).
        return len(self.markers) >= 2

    @property
    def categories(self) -> list[str]:
        # Column/category order: anchor total, then each marker+, then Double+ (if emitted).
        cats = [self.anchor_name] + [f"{m}+" for m in self.marker_names]
        if self.emit_double:
            cats.append("Double+")
        return cats

    def count_column(self, category: str) -> str:
        # region_table column naming: anchor has NO '+', markers/Double do.
        return f"{category}_count"


def load_pipeline_config(project_dir: Path) -> Config:
    path = project_dir / "pipeline.yml"
    if not path.exists():
        raise FileNotFoundError(f"pipeline.yml not found at {path}")
    doc = yaml.safe_load(path.read_text()) or {}
    anchor = doc.get("anchor") or {}
    anchor_name = anchor.get("name")
    if not anchor_name:
        raise ValueError(f"{path}: anchor.name missing")
    markers = doc.get("markers") or []
    if not markers:
        raise ValueError(f"{path}: markers list is empty")
    for i, m in enumerate(markers):
        if not m.get("name"):
            raise ValueError(f"{path}: markers[{i}].name missing")
        comp = m.get("compartment")
        if comp not in VALID_COMPARTMENTS:
            raise ValueError(
                f"{path}: markers[{i}].compartment '{comp}' invalid "
                f"(must be one of {sorted(VALID_COMPARTMENTS)})")
    excl = set(doc.get("exclude_acronyms") or [])
    animal = doc.get("animal") or doc.get("animal_id") or doc.get("subject")
    return Config(anchor_name=anchor_name, markers=markers, exclude_acronyms=excl, animal=animal)


# ---------------------------------------------------------------------------
# Allen ontology
# ---------------------------------------------------------------------------
class Ontology:
    """Allen ontology tree keyed by acronym. acronym/name live under node['data']."""

    def __init__(self) -> None:
        self._parent: dict[str, str | None] = {}
        self._children: dict[str, list[str]] = {}
        self._name: dict[str, str] = {}

    @classmethod
    def from_json(cls, path: Path) -> "Ontology":
        ont = cls()
        doc = json.loads(Path(path).read_text())
        root = doc.get("root") or doc

        def walk(node: dict, parent_acr: str | None) -> None:
            data = node.get("data") or {}
            acr = data.get("acronym")
            here = parent_acr
            if acr:
                ont._parent[acr] = parent_acr
                ont._children.setdefault(acr, [])
                ont._name[acr] = data.get("name") or acr
                if parent_acr is not None:
                    ont._children.setdefault(parent_acr, []).append(acr)
                here = acr
            for child in (node.get("children") or []):
                walk(child, here)

        walk(root, None)
        return ont

    def __contains__(self, acr: str) -> bool:
        return acr in self._parent

    def name(self, acr: str) -> str:
        return self._name.get(acr, acr)

    def descendants_or_self(self, acr: str) -> set[str]:
        if acr not in self._parent:
            return {acr}
        out: set[str] = set()
        stack = [acr]
        while stack:
            a = stack.pop()
            out.add(a)
            stack.extend(self._children.get(a, ()))
        return out

    def ancestors(self, acr: str) -> set[str]:
        out: set[str] = set()
        p = self._parent.get(acr)
        while p is not None:
            out.add(p)
            p = self._parent.get(p)
        return out


def load_ontology(project_dir: Path) -> Ontology:
    path = project_dir / "allen_mouse_10um_java-Ontology.json"
    if path.exists():
        return Ontology.from_json(path)
    # Fallback: build a minimal ontology from brainglobe's Allen atlas.
    try:
        from brainglobe_atlasapi import BrainGlobeAtlas
    except Exception as exc:  # pragma: no cover -- only hit when JSON absent
        raise FileNotFoundError(
            f"{path} not found and brainglobe-atlasapi unavailable ({exc}); "
            "cannot resolve the Allen ontology.")
    atlas = BrainGlobeAtlas("allen_mouse_10um")
    ont = Ontology()
    for region in atlas.structures.values():
        acr = region["acronym"]
        parents = region.get("structure_id_path", [])
        parent_acr = (atlas.structures[parents[-2]]["acronym"]
                      if len(parents) >= 2 else None)
        ont._parent[acr] = parent_acr
        ont._name[acr] = region.get("name", acr)
        ont._children.setdefault(acr, [])
        if parent_acr is not None:
            ont._children.setdefault(parent_acr, []).append(acr)
    return ont


# ---------------------------------------------------------------------------
# per-slice region_table
# ---------------------------------------------------------------------------
_SLICE_RE = re.compile(r"^(?P<animal>.+)_s(?P<n>\d+)$")


def parse_slice_identity(region_table_path: Path, project_dir: Path,
                         config_animal: str | None) -> tuple[str, str, str]:
    """Return (project, animal, slice_id) from a region_table filename.

    Filename looks like ``<image name>__id<N>__region_table.tsv`` where the image name is
    e.g. ``wBA1-2_2-1_s1_MIP.ome.tiff - wBA1-2_2-1_s1``. We take the clean entry name (after
    the last ``' - '``) and split a trailing ``_sN`` into animal prefix + ``sN``.
    """
    project = project_dir.name
    stem = region_table_path.name
    stem = stem.split("__id", 1)[0]                 # drop __id<N>__region_table.tsv
    stem = stem.split("__region_table", 1)[0]       # defensive (no __id case)
    entry = stem.split(" - ")[-1].strip()           # clean entry display name
    m = _SLICE_RE.match(entry)
    if m:
        animal = config_animal or m.group("animal")
        slice_id = f"s{m.group('n')}"
    else:
        animal = config_animal or entry
        slice_id = entry
    return project, animal, slice_id


@dataclass
class RegionTable:
    project: str
    animal: str
    slice_id: str
    # (acronym, hemisphere) -> {"area_mm2": float, "counts": {category: int}}
    rows: dict[tuple[str, str], dict] = field(default_factory=dict)
    present: set[str] = field(default_factory=set)   # acronyms with a Left/Right row
    hemispheres: list[str] = field(default_factory=list)

    def area(self, acr: str, hemi: str) -> float:
        r = self.rows.get((acr, hemi))
        return r["area_mm2"] if r else 0.0

    def count(self, acr: str, hemi: str, category: str) -> int:
        r = self.rows.get((acr, hemi))
        return r["counts"].get(category, 0) if r else 0


def load_region_table(path: Path, project_dir: Path, config: Config) -> RegionTable:
    df = pd.read_csv(path, sep="\t", dtype={"acronym": str, "hemisphere": str})
    project, animal, slice_id = parse_slice_identity(path, project_dir, config.animal)
    rt = RegionTable(project=project, animal=animal, slice_id=slice_id)

    # Confirm every declared category has a count column (config <-> table contract).
    count_cols = {cat: config.count_column(cat) for cat in config.categories}
    missing = [c for c in count_cols.values() if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name}: region_table is missing declared count column(s) {missing}. "
            f"pipeline.yml categories={config.categories}; table columns={list(df.columns)}")

    hemis: set[str] = set()
    for _, row in df.iterrows():
        hemi = (row.get("hemisphere") or "")
        hemi = "" if (isinstance(hemi, float) and math.isnan(hemi)) else str(hemi).strip()
        if hemi not in ("Left", "Right"):
            continue  # skip the whole-brain container row (empty hemisphere)
        acr = str(row["acronym"]).strip()
        area = float(row["area_mm2"])
        counts = {cat: int(row[count_cols[cat]]) for cat in config.categories}
        rt.rows[(acr, hemi)] = {"area_mm2": area, "counts": counts}
        rt.present.add(acr)
        hemis.add(hemi)
    rt.hemispheres = [h for h in ("Left", "Right") if h in hemis]
    return rt


# ---------------------------------------------------------------------------
# roll-up
# ---------------------------------------------------------------------------
def excluded_closure(ontology: Ontology, exclude_acronyms: set[str]) -> set[str]:
    """exclude_acronyms UNION all their descendants."""
    out: set[str] = set()
    for e in exclude_acronyms:
        out |= ontology.descendants_or_self(e)
    return out


def frontier_leaves(ontology: Ontology, present: set[str]) -> set[str]:
    """Present acronyms with no present ontology descendant (the data frontier)."""
    non_frontier: set[str] = set()
    for a in present:
        non_frontier |= (ontology.ancestors(a) & present)
    return present - non_frontier


def included_leaves(ontology: Ontology, present: set[str], region: str,
                    excl_closure: set[str], frontier: set[str]) -> set[str]:
    """Frontier-leaf set under `region`, exclusion-aware."""
    desc = ontology.descendants_or_self(region)
    return (desc & frontier) - excl_closure


def is_leaf_level(ontology: Ontology, present: set[str], region: str,
                  frontier: set[str]) -> bool:
    """A requested acronym is 'leaf' iff it is itself a data-frontier leaf."""
    return region in frontier


# ---------------------------------------------------------------------------
# readout build
# ---------------------------------------------------------------------------
def _density(count: int, area: float) -> float:
    return (count / area) if area > 0 else math.nan


def _ratio(numer: int, denom: int) -> float:
    return (numer / denom) if denom > 0 else math.nan


def read_regions_file(project_dir: Path) -> list[str] | None:
    path = project_dir / "regions_of_interest.txt"
    if not path.exists():
        return None
    regions: list[str] = []
    for line in path.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            regions.append(line)
    return regions


def _row_for(config: Config, rt: RegionTable, ontology: Ontology, region: str,
             hemi: str, area: float, counts: dict[str, int], level: str) -> dict:
    row = {
        "project": rt.project,
        "animal": rt.animal,
        "slice_id": rt.slice_id,
        "hemisphere": {"Left": "L", "Right": "R", "both": "both"}[hemi],
        "region_acronym": region,
        "region_name": ontology.name(region),
        "level": level,
        "area_mm2": round(area, 6),
    }
    anchor = config.anchor_name
    ac = counts.get(anchor, 0)
    row[f"{anchor}_count"] = ac
    row[f"{anchor}_density"] = _density(ac, area)
    for m in config.marker_names:
        mc = counts.get(f"{m}+", 0)
        row[f"{m}+_count"] = mc
        row[f"{m}+_density"] = _density(mc, area)
    if config.emit_double:
        dc = counts.get("Double+", 0)
        row["Double+_count"] = dc
        row["Double+_density"] = _density(dc, area)
        # Reactivation ratios: P(a+|b+) = Double / b_count, for the two ordered pairs of the
        # first two declared markers. With markers [TdT, Fos] this yields the GOAL's
        # P(Fos+|TdT+) = Double/TdT and P(TdT+|Fos+) = Double/Fos.
        m0, m1 = config.marker_names[0], config.marker_names[1]
        c0 = counts.get(f"{m0}+", 0)
        c1 = counts.get(f"{m1}+", 0)
        row[f"P({m1}+|{m0}+)"] = _ratio(dc, c0)
        row[f"P({m0}+|{m1}+)"] = _ratio(dc, c1)
    return row


def build_readout(project_dir: Path, regions: list[str] | None = None,
                  results_dir: Path | None = None,
                  warn=lambda msg: print(msg, file=sys.stderr)) -> pd.DataFrame:
    """Build the tidy per-slice region-of-interest readout DataFrame."""
    project_dir = Path(project_dir)
    config = load_pipeline_config(project_dir)
    ontology = load_ontology(project_dir)
    excl_closure = excluded_closure(ontology, config.exclude_acronyms)

    results_dir = Path(results_dir) if results_dir else project_dir / "results"
    table_paths = sorted(glob.glob(str(results_dir / "*__region_table.tsv")))
    if not table_paths:
        raise FileNotFoundError(f"No *__region_table.tsv files under {results_dir}")

    out_rows: list[dict] = []
    warned_unknown: set[str] = set()
    for tp in table_paths:
        rt = load_region_table(Path(tp), project_dir, config)
        frontier = frontier_leaves(ontology, rt.present)

        # Region list for this slice.
        if regions is None:
            # All INCLUDED leaves (frontier minus excluded), sorted for stable output.
            slice_regions = sorted(frontier - excl_closure)
        else:
            slice_regions = regions

        for region in slice_regions:
            if regions is not None and region not in ontology:
                if region not in warned_unknown:
                    warn(f"WARNING: '{region}' is not in the Allen ontology -- skipping (typo?).")
                    warned_unknown.add(region)
                continue
            leaves = included_leaves(ontology, rt.present, region, excl_closure, frontier)
            if not leaves:
                # Valid acronym but absent from this slice (section doesn't cover it, or fully
                # excluded). Skip silently -- emitting zero rows for every absent region on
                # every slice would swamp the CSV.
                continue
            level = "leaf" if is_leaf_level(ontology, rt.present, region, frontier) else "summary"

            pooled_area = 0.0
            pooled_counts: dict[str, int] = {c: 0 for c in config.categories}
            for hemi in rt.hemispheres:
                area = sum(rt.area(a, hemi) for a in leaves)
                if area <= 0 and all(rt.count(a, hemi, c) == 0 for a in leaves
                                     for c in config.categories):
                    continue  # region genuinely not on this side of this slice
                counts = {c: sum(rt.count(a, hemi, c) for a in leaves)
                          for c in config.categories}
                out_rows.append(_row_for(config, rt, ontology, region, hemi, area, counts, level))
                pooled_area += area
                for c in config.categories:
                    pooled_counts[c] += counts[c]
            # Pooled 'both' -- recomputed from summed counts/areas (never averaged).
            out_rows.append(
                _row_for(config, rt, ontology, region, "both", pooled_area, pooled_counts, level))

    df = pd.DataFrame(out_rows)
    return df


def write_csv(df: pd.DataFrame, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return out_path


def coverage_report(project_dir: Path, results_dir: Path | None = None) -> pd.DataFrame:
    """Per-slice fraction of anchor cells captured by frontier summation vs the region_table's
    own whole-hemisphere rollup row (the finest 'root' total). Surfaces the intermediate
    non-frontier bucket loss noted in the module docstring."""
    project_dir = Path(project_dir)
    config = load_pipeline_config(project_dir)
    ontology = load_ontology(project_dir)
    excl_closure = excluded_closure(ontology, config.exclude_acronyms)
    results_dir = Path(results_dir) if results_dir else project_dir / "results"
    rows = []
    for tp in sorted(glob.glob(str(results_dir / "*__region_table.tsv"))):
        rt = load_region_table(Path(tp), project_dir, config)
        frontier = frontier_leaves(ontology, rt.present)
        anchor = config.anchor_name
        for hemi in rt.hemispheres:
            fr = sum(rt.count(a, hemi, anchor) for a in (frontier - excl_closure))
            root = rt.count("root", hemi, anchor)
            rows.append({"slice_id": rt.slice_id, "hemisphere": hemi,
                         f"frontier_{anchor}": fr, f"rollup_root_{anchor}": root,
                         "coverage_pct": round(100 * fr / root, 1) if root else math.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# self-test (synthetic fixture -- no real data needed)
# ---------------------------------------------------------------------------
def _synthetic_ontology_json() -> dict:
    """Tiny tree: root>grey>{HPF>{CA1, DG>{DG-mo, DG-sg}}, AMY>{LA, BLA}}."""
    def node(acr, name, children=None):
        return {"data": {"acronym": acr, "name": name}, "children": children or []}
    return {"root": node("root", "root", [
        node("grey", "grey", [
            node("HPF", "Hippocampal formation", [
                node("CA1", "Field CA1", []),
                node("DG", "Dentate gyrus", [
                    node("DG-mo", "DG molecular", []),
                    node("DG-sg", "DG granule (excluded)", []),
                ]),
            ]),
            node("AMY", "Amygdala", [
                node("LA", "Lateral amygdalar nucleus", []),
                node("BLA", "Basolateral amygdalar nucleus", []),
            ]),
        ]),
    ])}


def _write_synthetic_project(base: Path, two_marker: bool) -> Path:
    proj = base / "synthetic project"
    (proj / "results").mkdir(parents=True, exist_ok=True)
    (proj / "allen_mouse_10um_java-Ontology.json").write_text(
        json.dumps(_synthetic_ontology_json()))
    markers = [{"name": "TdT", "channel": "AF568-T2", "compartment": "whole-cell"}]
    if two_marker:
        markers.append({"name": "Fos", "channel": "AF488-T1", "compartment": "nuclear"})
    (proj / "pipeline.yml").write_text(yaml.safe_dump({
        "anchor": {"name": "DAPI", "channel": "DAPI-T4"},
        "markers": markers,
        "exclude_acronyms": ["DG-sg", "VS"],
    }))
    # Build a synthetic region_table. CA1 and LA are frontier (no present descendant); DG has
    # present children DG-mo/DG-sg; DG-sg is excluded. Counts are per-annotation OWN buckets
    # for frontier rows; parent rows are deliberately WRONG (0) to prove we never read them.
    cats = ["DAPI"] + [f"{m['name']}+" for m in markers] + (["Double+"] if two_marker else [])
    header = (["region_label", "hemisphere", "acronym", "is_leaf", "area_mm2"]
              + [c2 for c in cats for c2 in (f"{c}_count", f"{c}_density")])
    # leaf own-buckets: (acr, hemi, area, {cat: count})
    def counts(dapi, tdt, fos=0, dbl=0):
        d = {"DAPI": dapi, "TdT+": tdt}
        if two_marker:
            d["Fos+"] = fos
            d["Double+"] = dbl
        return d
    leaves = {
        ("CA1", "Left"): (1.0, counts(100, 20, 10, 5)),
        ("CA1", "Right"): (1.0, counts(80, 16, 8, 4)),
        ("DG-mo", "Left"): (0.5, counts(40, 8, 4, 2)),
        ("DG-mo", "Right"): (0.5, counts(30, 6, 3, 1)),
        ("DG-sg", "Left"): (0.2, counts(0, 0, 0, 0)),   # excluded: 0 count, nonzero area
        ("DG-sg", "Right"): (0.2, counts(0, 0, 0, 0)),
        ("LA", "Left"): (0.3, counts(50, 25, 15, 10)),
        ("LA", "Right"): (0.3, counts(40, 20, 12, 8)),
        ("BLA", "Left"): (0.4, counts(60, 12, 6, 3)),
        ("BLA", "Right"): (0.4, counts(45, 9, 5, 2)),
    }
    # parent rows we must NEVER trust (wrong counts on purpose).
    parents = [("HPF", "Left"), ("HPF", "Right"), ("DG", "Left"), ("DG", "Right"),
               ("AMY", "Left"), ("AMY", "Right"), ("grey", "Left"), ("grey", "Right")]
    lines = ["\t".join(header)]
    for (acr, hemi), (area, cnt) in leaves.items():
        cells = [f"{hemi}: {acr}", hemi, acr, "true", f"{area:.6f}"]
        for c in cats:
            cells += [str(cnt[c]), f"{cnt[c] / area:.3f}"]
        lines.append("\t".join(cells))
    for acr, hemi in parents:
        cells = [f"{hemi}: {acr}", hemi, acr, "false", "9.999999"]
        for c in cats:
            cells += ["0", ""]     # deliberately-wrong parent rollup
        lines.append("\t".join(cells))
    # root rollup row (used only by coverage_report): true whole-hemi anchor total.
    for hemi in ("Left", "Right"):
        root_dapi = sum(cnt["DAPI"] for (a, h), (ar, cnt) in leaves.items() if h == hemi)
        cells = [f"{hemi}: root", hemi, "root", "false", "99.0"]
        for c in cats:
            v = root_dapi if c == "DAPI" else 0
            cells += [str(v), ""]
        lines.append("\t".join(cells))
    (proj / "results" / "synthU_s1_MIP.ome.tiff - synthU_s1__id1__region_table.tsv").write_text(
        "\n".join(lines) + "\n")
    return proj


def _self_test() -> None:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("  PASS " if cond else "  FAIL ") + msg)
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # --- 1-marker (TdT-only) fixture ---------------------------------------
        print("[self-test] TdT-only (1 marker) fixture")
        proj = _write_synthetic_project(base, two_marker=False)
        df = build_readout(proj, regions=["LA", "BLA", "HPF", "CA1", "DG", "ZZZ"],
                            warn=lambda m: None)

        cols = list(df.columns)
        check("Fos+_count" not in cols and "Double+_count" not in cols,
              "TdT-only -> no Fos / Double columns")
        check("DAPI_count" in cols and "TdT+_count" in cols,
              "TdT-only -> DAPI + TdT columns present")
        check(not any(c.startswith("P(") for c in cols),
              "TdT-only -> no reactivation-ratio columns")

        def val(region, hemi, col):
            sub = df[(df.region_acronym == region) & (df.hemisphere == hemi)]
            return sub.iloc[0][col] if len(sub) else None

        # LA/CA1 resolve to their own bucket (not 0 -- the geometric-is_leaf trap).
        check(val("LA", "L", "DAPI_count") == 50, "LA(L) DAPI == own bucket (50), not 0")
        check(val("CA1", "L", "DAPI_count") == 100, "CA1(L) DAPI == own bucket (100), not 0")

        # Roll-up: HPF(L) == CA1 + DG-mo (DG-sg excluded).  100 + 40 = 140.
        check(val("HPF", "L", "DAPI_count") == 140,
              "HPF(L) DAPI == sum of included leaves CA1+DG-mo (140)")
        # Area rolls up over the identical leaf set: 1.0 (CA1) + 0.5 (DG-mo) = 1.5 (NOT +DG-sg 0.2).
        check(abs(val("HPF", "L", "area_mm2") - 1.5) < 1e-9,
              "HPF(L) area excludes DG-sg (1.5, not 1.7)")
        # DG(L) == DG-mo only (DG-sg excluded): count 40, area 0.5 (not 0.7).
        check(val("DG", "L", "DAPI_count") == 40 and abs(val("DG", "L", "area_mm2") - 0.5) < 1e-9,
              "DG(L) excludes DG-sg from both count and area")

        # levels
        check(val("LA", "L", "level") == "leaf" and val("HPF", "L", "level") == "summary",
              "level: LA=leaf, HPF=summary")

        # hemispheres L + R + both all present; pooled = L + R.
        hemis = set(df[df.region_acronym == "HPF"].hemisphere)
        check(hemis == {"L", "R", "both"}, "HPF has L + R + both rows")
        both = val("HPF", "both", "DAPI_count")
        check(both == val("HPF", "L", "DAPI_count") + val("HPF", "R", "DAPI_count"),
              "HPF both DAPI == L + R")
        # pooled density recomputed from sums, not averaged.
        both_area = val("HPF", "both", "area_mm2")
        check(abs(val("HPF", "both", "DAPI_density") - both / both_area) < 1e-6,
              "HPF both density recomputed from pooled sums")

        # DG-sg contributes nowhere.
        check("DG-sg" not in set(df.region_acronym),
              "DG-sg never appears as an included leaf in output")

        # unknown acronym warns (captured) and does not crash / appear.
        warns: list[str] = []
        build_readout(proj, regions=["ZZZ", "LA"], warn=warns.append)
        check(any("ZZZ" in w for w in warns) and "ZZZ" not in set(df.region_acronym),
              "unknown acronym -> warning, not a crash")

        # coverage report runs and is sane (all frontier cells captured here => 100%).
        cov = coverage_report(proj)
        check((cov.coverage_pct == 100.0).all(), "coverage report == 100% on synthetic fixture")

        # --- 2-marker fixture: Double + ratio columns appear -------------------
        print("[self-test] 2-marker (Fos + TdT) fixture")
        proj2 = _write_synthetic_project(base / "two", two_marker=True)
        df2 = build_readout(proj2, regions=["LA", "HPF"], warn=lambda m: None)
        cols2 = list(df2.columns)
        check("Fos+_count" in cols2 and "Double+_count" in cols2,
              "2-marker -> Fos + Double columns present")
        ratio_cols = [c for c in cols2 if c.startswith("P(")]
        check(len(ratio_cols) == 2, f"2-marker -> two reactivation-ratio columns ({ratio_cols})")

        def val2(region, hemi, col):
            sub = df2[(df2.region_acronym == region) & (df2.hemisphere == hemi)]
            return sub.iloc[0][col] if len(sub) else None

        # LA(L): Double=10, TdT=25, Fos=15 -> P(Fos+|TdT+)=10/25=0.4; P(TdT+|Fos+)=10/15.
        check(abs(val2("LA", "L", "P(Fos+|TdT+)") - 0.4) < 1e-9,
              "LA(L) P(Fos+|TdT+) == Double/TdT == 0.4")
        check(abs(val2("LA", "L", "P(TdT+|Fos+)") - (10 / 15)) < 1e-9,
              "LA(L) P(TdT+|Fos+) == Double/Fos")
        # pooled ratio recomputed from summed counts: HPF both Double/TdT.
        d_both = val2("HPF", "both", "Double+_count")
        t_both = val2("HPF", "both", "TdT+_count")
        check(abs(val2("HPF", "both", "P(Fos+|TdT+)") - d_both / t_both) < 1e-9,
              "HPF both P(Fos+|TdT+) recomputed from pooled counts")

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
    ap.add_argument("--project", type=Path,
                    help="QuPath project dir (holds pipeline.yml, ontology JSON, results/).")
    ap.add_argument("--results-dir", type=Path, default=None,
                    help="Override results dir (default: <project>/results).")
    ap.add_argument("--regions", type=str, default=None,
                    help="Comma-separated acronyms. Default: read <project>/regions_of_interest.txt; "
                         "if that is absent, emit all included leaves.")
    ap.add_argument("--out", type=Path, default=None,
                    help="Output CSV (default: <project>/results/region_of_interest_readout.csv).")
    ap.add_argument("--coverage", action="store_true",
                    help="Also print the per-slice frontier-coverage report.")
    ap.add_argument("--self-test", action="store_true", help="Run the built-in self-test and exit.")
    args = ap.parse_args()

    if args.self_test:
        _self_test()
        return

    if not args.project:
        ap.error("--project is required (or use --self-test)")
    project_dir = args.project
    if not project_dir.exists():
        ap.error(f"project dir not found: {project_dir}")

    if args.regions is not None:
        regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    else:
        regions = read_regions_file(project_dir)  # None -> all included leaves
        if regions is None:
            print("No regions_of_interest.txt found -> emitting all included leaves.",
                  file=sys.stderr)

    df = build_readout(project_dir, regions=regions, results_dir=args.results_dir)
    out = args.out or (project_dir / "results" / "region_of_interest_readout.csv")
    write_csv(df, out)
    n_regions = df.region_acronym.nunique() if len(df) else 0
    n_slices = df.slice_id.nunique() if len(df) else 0
    print(f"Wrote {len(df)} rows ({n_regions} regions x {n_slices} slices, L/R/both) -> {out}")

    if args.coverage:
        print("\nFrontier coverage (frontier anchor sum vs region_table root rollup):")
        print(coverage_report(project_dir, args.results_dir).to_string(index=False))


if __name__ == "__main__":
    main()
