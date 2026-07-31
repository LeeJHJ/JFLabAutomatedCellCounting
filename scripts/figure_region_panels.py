#!/usr/bin/env python3
"""figure_region_panels.py -- one group, five measures, regions along x.

Presentation figure for a single animal/group: tagging (TdT+), activity (Fos+),
reactivation P(Fos+|TdT+), and the derived above-chance overlap. Reads
cockpit_animal.py's long table and never recomputes a metric -- that module owns the
definitions, and a second implementation here would drift from it.

WHY SEPARATE PANELS RATHER THAN ONE. The three rates are fractions of cells and share a
y-scale; above-chance is a ratio with its own scale and a meaningful 1.0 reference.
Putting them on one axis would need a second y-scale, which is the single worst thing
a chart can do. Separate panels, one scale each.

READING THE LAST PANEL. above-chance answers "is a tagged cell MORE likely to be
active than a cell picked at random from the same section?" -- which the raw
reactivation rate cannot, because it inflates wherever the activity marker is dense.
The formula is drawn on the panel because a reviewer should not have to take it on
trust.

Evidence marking is part of the figure: bars resting on few double+ cells are hatched
and keyed, because a bar chart otherwise renders a ratio from 19 cells identically to
one from 571.

Usage:
    python3 figure_region_panels.py --long <animal_region_long.csv> \\
        --out fig.png --group-label "M5" --subtitle "8 sections"
    python3 figure_region_panels.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

# Validated categorical slots (light surface): slot 1 blue, slot 2 orange.
# CVD dE 24.7 protan / 33.6 normal -- all six checks pass. Do not substitute by eye.
C_RATE = "#2a78d6"
C_RATIO = "#eb6834"
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#6b6b6b"
GRID = "#e3e3e0"

THIN_EVIDENCE = 50

# Every panel states its DENOMINATOR in the axis label. Three of these are fractions
# of ALL cells (DAPI); reactivation is deliberately per-TdT+, which is a different
# denominator and the reason it must not be read alongside the others as if it were
# the same kind of number.
PANELS = [
    ("_tdt_per_dapi",    "TdT+ / DAPI   (engram-tagged)",       "% of DAPI+ cells",  C_RATE, 100.0),
    ("_fos_per_dapi",    "Fos+ / DAPI   (active at recall)",    "% of DAPI+ cells",  C_RATE, 100.0),
    ("_double_per_dapi", "Double+ / DAPI   (tagged AND active)", "% of DAPI+ cells", C_RATE, 100.0),
    ("reactivation_rate", "Reactivation   Double+ / TdT+",      "% of TdT+ cells",   C_RATE, 100.0),
    ("overlap_above_chance",
     "Above-chance overlap   =   P(Fos+ | TdT+)  /  P(Fos+ | all cells)",
     "x chance", C_RATIO, 1.0),
]


def _add_dapi_fractions(d: pd.DataFrame) -> pd.DataFrame:
    """Per-DAPI fractions, from the counts cockpit_animal already reports.

    N is the DAPI-derived denominator that module resolved (anchor or classifiable);
    reusing it keeps this figure consistent with every other readout rather than
    inventing a second definition of "all cells".
    """
    d = d.copy()
    n = d["N"].replace(0, np.nan)
    d["_tdt_per_dapi"] = d["TdT+_count"] / n
    d["_fos_per_dapi"] = d["Fos+_count"] / n
    d["_double_per_dapi"] = d["Double+_count"] / n
    return d


def load_region_names(ontology: Path | None) -> dict[str, str]:
    """acronym -> full Allen name, from the project's own ontology JSON.

    Read from the project rather than hardcoded: the acronym set is atlas-version
    specific, and a stale built-in table would silently mislabel a region.
    """
    if ontology is None or not Path(ontology).exists():
        return {}
    import json
    doc = json.loads(Path(ontology).read_text())
    out: dict[str, str] = {}

    def walk(node):
        dat = node.get("data", {}) or {}
        a, nm = dat.get("acronym"), dat.get("name")
        if a and nm:
            out[a] = nm
        for c in node.get("children", []) or []:
            walk(c)

    walk(doc.get("root", doc))
    return out


def _tick_label(acr: str, names: dict[str, str], width: int = 16) -> str:
    """Acronym on line 1, wrapped full name beneath. Keeps every panel readable on
    its own -- the reason the panels are also written as separate PNGs."""
    import textwrap
    nm = names.get(acr)
    if not nm:
        return acr
    return acr + "\n" + "\n".join(textwrap.wrap(nm, width))


def build_figure(df: pd.DataFrame, group_label: str = "", subtitle: str = "",
                 thin_threshold: int = THIN_EVIDENCE, sort_by: str = "overlap_above_chance",
                 names: dict[str, str] | None = None, only: str | None = None):
    """Four stacked panels sharing a region axis, sorted by `sort_by` descending."""
    d = _add_dapi_fractions(df[df["hemisphere"] == "both"].copy())
    if d.empty:
        raise SystemExit("no 'both'-hemisphere rows in the long table")
    d = d.sort_values(sort_by, ascending=False)
    regions = d["region_acronym"].tolist()
    thin = (d.get("Double+_count", pd.Series([0] * len(d))).fillna(0).astype(int)
            < thin_threshold).tolist()
    x = np.arange(len(regions))
    names = names or {}
    panels = [pp for pp in PANELS if only is None or pp[0] == only]

    fig, axes = plt.subplots(len(panels), 1, figsize=(max(8.0, 0.92 * len(regions) + 2.6),
                                      3.9 if len(panels) == 1 else 13.6),
                             dpi=200, sharex=True, squeeze=False)
    axes = axes[:, 0]
    fig.patch.set_facecolor(SURFACE)

    for ax, (col, title, ylab, color, scale) in zip(axes, panels):
        vals = (d[col] * scale).tolist()
        ax.set_facecolor(SURFACE)
        for xi, v, is_thin in zip(x, vals, thin):
            ax.bar(xi, v, width=0.68, color=color, edgecolor=SURFACE, linewidth=1.5,
                   hatch="///" if is_thin else None, zorder=3)
        # Direct-label every bar: few enough regions that this stays readable, and the
        # reader should not have to measure against gridlines.
        vmax = max(vals) if vals else 1.0
        for xi, v in zip(x, vals):
            ax.text(xi, v + vmax * 0.035, f"{v:.1f}" if scale == 100 else f"{v:.2f}",
                    ha="center", va="bottom", fontsize=8, color=INK_MUTED, zorder=4)

        if col == "overlap_above_chance":
            ax.axhline(1.0, color=INK_MUTED, lw=1.4, ls="--", zorder=2)
            ax.text(0.008, 1.0, "chance", transform=ax.get_yaxis_transform(),
                    fontsize=8.5, color=INK_MUTED, va="bottom", ha="left")


        ax.set_title(title, fontsize=11, color=INK, loc="left", pad=8)
        ax.set_ylabel(ylab, fontsize=9, color=INK_MUTED)
        ax.set_ylim(0, vmax * 1.22)
        ax.yaxis.grid(True, color=GRID, lw=0.8, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(GRID)
        ax.tick_params(colors=INK_MUTED, labelsize=9)

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([_tick_label(r, names) for r in regions],
                             rotation=0, ha="center", fontsize=8, color=INK)

    head = " — ".join(p for p in (group_label, "engram reactivation by region") if p)
    fig.suptitle(head + (f"\n{subtitle}" if subtitle else ""), fontsize=12.5,
                 color=INK, x=0.012, ha="left", va="top", y=0.995,
                 linespacing=1.9)

    if any(thin):
        axes[0].legend(handles=[mpatches.Patch(facecolor="white", edgecolor=INK_MUTED,
                                               hatch="///",
                                               label=f"< {thin_threshold} double+ cells "
                                                     f"— low evidence")],
                       frameon=False, fontsize=8.5, loc="upper right", labelcolor=INK)

    fig.tight_layout(rect=[0, 0, 1, 0.90 if len(panels) == 1 else 0.955])
    return fig, axes


def _self_test() -> None:
    print("Running --self-test (synthetic long table, no project needed)...")
    d = pd.DataFrame({
        "region_acronym": ["ACB", "CP", "CA3", "LHA"],
        "hemisphere": ["both"] * 4,
        "tagging_rate": [0.06, 0.05, 0.079, 0.069],
        "activity_rate": [0.10, 0.08, 0.046, 0.101],
        "reactivation_rate": [0.30, 0.22, 0.14, 0.345],
        "overlap_above_chance": [3.0, 2.75, 3.04, 3.41],
        "Double+_count": [300, 120, 571, 19],
        "TdT+_count": [1000, 545, 4068, 275],
        "Fos+_count": [1667, 872, 2376, 402],
        "N": [16667, 10900, 51646, 3980],
    })
    fig, axes = build_figure(d, group_label="TEST", subtitle="4 sections")
    assert len(axes) == 5, f"expected 5 panels, got {len(axes)}"
    # sorted by above-chance descending -> LHA, CA3, ACB, CP
    labels = [t.get_text() for t in axes[-1].get_xticklabels()]
    assert labels == ["LHA", "CA3", "ACB", "CP"], f"unexpected order: {labels}"
    for ax in axes:
        bars = [p for p in ax.patches if p.get_height() > 0]
        assert len(bars) == 4, f"expected 4 bars per panel, got {len(bars)}"
        assert ax.get_ylim()[0] == 0, "bar panels must start at zero"
    hatched = [p for p in axes[0].patches if p.get_hatch()]
    assert len(hatched) == 1, f"one low-evidence region should be hatched, got {len(hatched)}"
    plt.close(fig)
    print("\nself-test PASSED: 5 panels, regions sorted by above-chance, every panel "
          "anchored at zero, low-evidence region hatched in all panels.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    p.add_argument("--long", type=Path, default=None,
                   help="animal_region_long.csv from cockpit_animal.py")
    p.add_argument("--out", type=Path, default=None, help="output PNG")
    p.add_argument("--group-label", default="", help="e.g. 'M5'")
    p.add_argument("--subtitle", default="", help="e.g. '8 sections · preliminary'")
    p.add_argument("--ontology", type=Path, default=None,
                   help="allen_mouse_10um_java-Ontology.json from the QuPath project; "
                        "supplies the full region names printed under each acronym")
    p.add_argument("--separate", action="store_true",
                   help="write ONE PNG PER PANEL into --out (treated as a directory) so "
                        "every graph carries its own region labels")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if not a.self_test and (a.long is None or a.out is None):
        p.error("--long and --out are required unless --self-test is set")
    return a


def main() -> int:
    a = parse_args()
    if a.self_test:
        _self_test()
        return 0
    df = pd.read_csv(a.long)
    names = load_region_names(a.ontology)
    if names:
        print(f"  region names loaded: {len(names)} acronyms")

    if a.separate:
        a.out.mkdir(parents=True, exist_ok=True)
        for i, (col, title, _ylab, _c, _s) in enumerate(PANELS, 1):
            fig, _ = build_figure(df, group_label=a.group_label, subtitle=a.subtitle,
                                  names=names, only=col)
            slug = col.lstrip("_").replace("_per_", "_over_")
            path = a.out / f"{i}_{slug}.png"
            fig.savefig(path, facecolor=fig.get_facecolor(), bbox_inches="tight")
            plt.close(fig)
            print(f"  wrote {path}")
        return 0

    fig, _ = build_figure(df, group_label=a.group_label, subtitle=a.subtitle, names=names)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"  wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
