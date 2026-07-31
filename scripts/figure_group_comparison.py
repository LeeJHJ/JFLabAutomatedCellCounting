#!/usr/bin/env python3
"""figure_group_comparison.py -- reactivation by region, one bar per group.

Builds the presentation figure from `cockpit_animal.py`'s long table. Reads the
numbers, never recomputes them -- cockpit_animal owns the metric definitions and a
second implementation here would drift from it.

WHAT IS PLOTTED: `overlap_above_chance` = P(activity+|tagged+) / P(activity+|all
cells), i.e. how much more likely a tagged cell is to be active than a cell picked at
random from the SAME section. 1.0x is chance. The raw reactivation rate is deliberately
NOT the headline -- it inflates wherever the activity marker is dense (M3 Hipp2:
Isocortex has the highest raw reactivation in the whole brain, 41.9%, and almost the
lowest enrichment, 1.66x, because a quarter of cortical cells are Fos+ anyway).

EVIDENCE MARKING IS PART OF THE FIGURE, not a caption afterthought. Bars built on few
Double+ cells are drawn hatched and labelled, because a 4.9x enrichment computed from
19 cells is not the same claim as a 3.0x from 571 and a bar chart otherwise renders
them identically.

Usage:
    python3 figure_group_comparison.py --long results/animal/shortlist/animal_region_long.csv \\
        --out results/animal/shortlist/fig_reactivation.png
    python3 figure_group_comparison.py --self-test
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

# Validated categorical slots 1 and 2 (light surface): CVD ΔE 24.7 protan / 32.7
# tritan, normal-vision ΔE 33.6 -- all six checks pass. Do not substitute by eye.
GROUP_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_MUTED = "#6b6b6b"
GRID = "#e3e3e0"

# Below this many Double+ cells a bar is marked low-evidence.
THIN_EVIDENCE = 50


def _fmt_region(acr: str) -> str:
    return acr


def build_figure(df: pd.DataFrame, metric: str = "overlap_above_chance",
                 thin_threshold: int = THIN_EVIDENCE, title: str | None = None):
    """One horizontal bar per region per group, sorted by the first group's value."""
    df = df[df["hemisphere"] == "both"].copy()
    groups = list(dict.fromkeys(df["group"]))
    regions = (df[df["group"] == groups[0]]
               .sort_values(metric, ascending=True)["region_acronym"].tolist())
    # Regions only present in later groups still get a slot.
    for g in groups[1:]:
        for r in df[df["group"] == g]["region_acronym"]:
            if r not in regions:
                regions.insert(0, r)

    n_g = len(groups)
    height = max(3.2, 0.52 * len(regions) + 1.5)
    fig, ax = plt.subplots(figsize=(8.4, height), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    bar_h = 0.72 / n_g
    y_base = np.arange(len(regions))
    any_thin = False

    for gi, g in enumerate(groups):
        sub = df[df["group"] == g].set_index("region_acronym")
        vals, ys, thin = [], [], []
        for ri, r in enumerate(regions):
            if r not in sub.index:
                continue
            row = sub.loc[r]
            vals.append(float(row[metric]))
            # 2px surface gap between adjacent bars comes from the height gap below.
            ys.append(y_base[ri] + (gi - (n_g - 1) / 2) * bar_h)
            thin.append(int(row.get("Double+_count", 0)) < thin_threshold)

        for v, y, is_thin in zip(vals, ys, thin):
            ax.barh(y, v, height=bar_h * 0.88, color=GROUP_COLORS[gi],
                    edgecolor=SURFACE, linewidth=1.5,
                    hatch="///" if is_thin else None, zorder=3)
            any_thin = any_thin or is_thin
            ax.text(v + 0.06, y, f"{v:.2f}×", va="center", ha="left",
                    fontsize=8.5, color=INK_MUTED, zorder=4)

    ax.axvline(1.0, color=INK_MUTED, lw=1.4, ls="--", zorder=2)
    ax.text(1.0, len(regions) - 0.35, "  chance", fontsize=8.5,
            color=INK_MUTED, va="bottom", ha="left")

    ax.set_yticks(y_base)
    ax.set_yticklabels([_fmt_region(r) for r in regions], fontsize=10, color=INK)
    ax.set_xlabel("reactivation above chance   P(Fos+|TdT+) / P(Fos+|all cells)",
                  fontsize=9.5, color=INK)
    ax.set_title(title or "Engram reactivation by region", fontsize=12,
                 color=INK, pad=14, loc="left")

    ax.xaxis.grid(True, color=GRID, lw=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=INK_MUTED, labelsize=9)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, max(2.0, df[metric].max() * 1.18))

    handles = [mpatches.Patch(facecolor=GROUP_COLORS[i], label=str(g))
               for i, g in enumerate(groups)]
    if any_thin:
        handles.append(mpatches.Patch(facecolor="white", edgecolor=INK_MUTED,
                                      hatch="///",
                                      label=f"< {thin_threshold} double+ cells"))
    # A single group needs no identity legend, but the evidence key still matters.
    if len(groups) > 1 or any_thin:
        ax.legend(handles=handles, frameon=False, fontsize=9,
                  loc="lower right", labelcolor=INK)

    fig.tight_layout()
    return fig, ax


def _self_test() -> None:
    print("Running --self-test (synthetic two-group frame, no project needed)...")
    df = pd.DataFrame({
        "group": ["A"] * 3 + ["B"] * 3,
        "region_acronym": ["CA3", "LHA", "PERI"] * 2,
        "hemisphere": ["both"] * 6,
        "overlap_above_chance": [3.0, 3.4, 2.7, 4.1, 3.9, 2.2],
        "Double+_count": [571, 209, 147, 600, 180, 12],
    })
    fig, ax = build_figure(df, title="self-test")
    bars = [p for p in ax.patches if p.get_width() > 0]
    assert len(bars) == 6, f"expected 6 bars, got {len(bars)}"
    hatched = [p for p in bars if p.get_hatch()]
    assert len(hatched) == 1, (
        f"exactly the one region under {THIN_EVIDENCE} double+ cells should be "
        f"hatched, got {len(hatched)}"
    )
    # Sorted ascending by the FIRST group's value -> PERI(2.7) < CA3(3.0) < LHA(3.4)
    labels = [t.get_text() for t in ax.get_yticklabels()]
    assert labels == ["PERI", "CA3", "LHA"], f"unexpected region order: {labels}"
    assert ax.get_xlim()[0] == 0, "bar chart x-axis must start at zero"
    plt.close(fig)

    # Single group: no identity legend needed, but a thin bar still gets the key.
    one = df[df["group"] == "A"].copy()
    fig2, ax2 = build_figure(one)
    assert len([p for p in ax2.patches if p.get_width() > 0]) == 3
    plt.close(fig2)

    print("\nself-test PASSED: bars per group-region, low-evidence bars hatched, "
          "regions sorted by the first group, x-axis anchored at zero, "
          "single-group path works.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument("--long", type=Path, default=None,
                   help="animal_region_long.csv from cockpit_animal.py")
    p.add_argument("--out", type=Path, default=None, help="output PNG path")
    p.add_argument("--metric", default="overlap_above_chance",
                   help="column to plot (default: overlap_above_chance)")
    p.add_argument("--title", default=None, help="figure title")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args()
    if not args.self_test and (args.long is None or args.out is None):
        p.error("--long and --out are required unless --self-test is set")
    return args


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0

    df = pd.read_csv(args.long)
    fig, _ = build_figure(df, metric=args.metric, title=args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, facecolor=fig.get_facecolor(), bbox_inches="tight")
    print(f"  wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
