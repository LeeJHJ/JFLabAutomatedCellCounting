#!/usr/bin/env python3
"""cockpit_threshold.py -- see and adjust the anchor-channel detection threshold.

The CHEAP half of the threshold loop. `scripts/calibrate_threshold.groovy` runs in
QuPath (expensive, needs the image) and writes one
`<image>__threshold_calibration.json` per slice into `<project>/results/`. This
module reads those JSONs and answers the questions that a bare number cannot:

  * where does the cut actually sit on this section's intensity histogram?
  * how far is it from the background floor and the bright-nuclei peak?
  * what would a different `span_frac` have given -- on THIS section?
  * do all slices in the series agree, or is one section an outlier?

Why this exists at all: detection used a fixed absolute threshold (700), tuned by
eye on one section. That is pinned to one acquisition's intensity scale and
silently under-detects on any dimmer section. The replacement rule is

    threshold = floor + span_frac * (bright_peak - floor)

re-measured per section, so it tracks staining and laser drift. The one knob is
`span_frac` in pipeline.yml. This module exists so that knob is turned while
LOOKING at the histogram rather than guessing -- the plot is the point.

Reading the plot: the shaded band spans floor -> bright_peak. The solid line is
the chosen cut. Too close to the floor and background noise is detected as
nuclei; too close to the bright peak and dim real nuclei are dropped (the failure
the reference workflow reports as destroying regional contrast). Roughly the
lower quarter of the span is the working range.

Usage:
    python3 cockpit_threshold.py --project "<project dir>"
    python3 cockpit_threshold.py --project "<dir>" --plots
    python3 cockpit_threshold.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# Notebook-safe: never force a matplotlib backend at import time -- doing that
# killed inline plots once already (commit bd5d11f). Import pyplot lazily inside
# the plotting functions instead.

CALIB_GLOB = "*__threshold_calibration.json"

# Advisory band on where the cut should sit within the floor->bright span. Not a
# hard gate: it is a "look again" prompt, in the spirit of the other cockpit
# gates reporting a number next to a verdict rather than a bare boolean.
SANE_FRAC_LO = 0.10
SANE_FRAC_HI = 0.45


@dataclass
class Calibration:
    """One slice's threshold calibration, as written by calibrate_threshold.groovy."""

    image: str
    anchor_channel: str
    mode: str
    span_frac: float
    floor: int
    bright_peak: int
    span: int
    threshold: int
    sweep: pd.DataFrame          # columns: frac, threshold
    histogram: pd.DataFrame      # columns: lo, hi, count  (empty if unavailable)
    source: Path | None = None

    @property
    def achieved_frac(self) -> float:
        """Where the chosen threshold actually sits in the span.

        Equals `span_frac` in span_fraction mode; in absolute mode it reveals
        where a hardcoded number happens to land on THIS section -- which is the
        whole argument against hardcoding it.
        """
        if self.span <= 0:
            return float("nan")
        return (self.threshold - self.floor) / self.span

    @property
    def status(self) -> str:
        f = self.achieved_frac
        if not np.isfinite(f):
            return "FLAG"
        return "PASS" if SANE_FRAC_LO <= f <= SANE_FRAC_HI else "FLAG"


def _slice_label(image: str) -> str:
    """Short label for plots/tables. Mirrors the '<file> - <slice>' naming the
    exports use; falls back to the whole string when that shape is absent."""
    return image.split(" - ")[-1] if " - " in image else image


def load_calibration(path: Path) -> Calibration:
    """Load one calibration JSON. Raises with the offending path on bad input."""
    try:
        raw = json.loads(Path(path).read_text())
    except json.JSONDecodeError as e:
        raise ValueError(f"{path}: not valid JSON ({e})") from e

    required = ("image", "anchor_channel", "mode", "floor", "bright_peak", "threshold")
    absent = [k for k in required if k not in raw]
    if absent:
        raise ValueError(f"{path}: missing key(s) {absent} -- re-run calibrate_threshold.groovy")

    sweep = pd.DataFrame(raw.get("sweep") or [], columns=["frac", "threshold"])
    hist = pd.DataFrame(raw.get("histogram") or [], columns=["lo", "hi", "count"])

    span = int(raw.get("span", raw["bright_peak"] - raw["floor"]))
    return Calibration(
        image=raw["image"],
        anchor_channel=raw["anchor_channel"],
        mode=raw["mode"],
        span_frac=float(raw.get("span_frac", float("nan"))),
        floor=int(raw["floor"]),
        bright_peak=int(raw["bright_peak"]),
        span=span,
        threshold=int(raw["threshold"]),
        sweep=sweep,
        histogram=hist,
        source=Path(path),
    )


def load_config_threshold(project_dir: Path) -> dict:
    """Read the `detection_threshold` block from a project's pipeline.yml.

    Shows the RULE currently configured, next to the calibration JSONs showing what
    that rule produced. Config is the source of truth (CLAUDE.md) -- nothing about
    the threshold is duplicated in Python.
    """
    import yaml

    cfg_path = Path(project_dir) / "pipeline.yml"
    if not cfg_path.exists():
        return {"error": f"no pipeline.yml in {project_dir}"}
    cfg = yaml.safe_load(cfg_path.read_text()) or {}
    dt = cfg.get("detection_threshold")
    if not isinstance(dt, dict):
        return {
            "error": "pipeline.yml has no detection_threshold block -- deploy it with "
                     "scripts/sync_project.py --project <dir>"
        }
    keys = ("mode", "span_frac", "absolute", "resolution_level", "smooth_window", "peak_prominence")
    return {k: dt.get(k) for k in keys if k in dt}


def find_calibrations(project_dir: Path, results_dir: Path | None = None) -> list[Calibration]:
    """Load every slice's calibration in a project, sorted by slice label.

    Returns [] rather than raising when none exist -- a project simply may not
    have been calibrated yet, and the caller prints the command to fix that.
    """
    rdir = Path(results_dir) if results_dir else Path(project_dir) / "results"
    if not rdir.is_dir():
        return []
    out = [load_calibration(p) for p in sorted(rdir.glob(CALIB_GLOB))]
    return sorted(out, key=lambda c: _slice_label(c.image))


def summary_table(calibs: list[Calibration]) -> pd.DataFrame:
    """One row per slice: the numbers behind the cut, plus the advisory verdict.

    `threshold_cv` context: compare `threshold` across rows. Under the
    span-fraction rule the thresholds SHOULD differ between sections -- that is
    the rule tracking each section's own intensity scale, not a fault. What would
    be a fault is `achieved_frac` differing, since that is the fixed knob.
    """
    if not calibs:
        return pd.DataFrame(
            columns=["slice", "anchor", "mode", "floor", "bright_peak", "span",
                     "threshold", "achieved_frac", "status"]
        )
    return pd.DataFrame(
        [
            {
                "slice": _slice_label(c.image),
                "anchor": c.anchor_channel,
                "mode": c.mode,
                "floor": c.floor,
                "bright_peak": c.bright_peak,
                "span": c.span,
                "threshold": c.threshold,
                "achieved_frac": round(c.achieved_frac, 4),
                "status": c.status,
            }
            for c in calibs
        ]
    )


def consistency_report(calibs: list[Calibration]) -> dict:
    """Series-level check: is one slice's histogram unlike the others?

    A section whose floor or bright peak is far from its siblings usually means an
    acquisition inconsistency (different laser/gain, a bleached section, a focus
    miss) rather than biology. Worth knowing BEFORE spending a batch detection run
    on it -- which is the whole point of catching it in the cheap half.
    """
    if len(calibs) < 2:
        return {"n_slices": len(calibs), "checkable": False, "outliers": []}

    df = summary_table(calibs)
    out = []
    for col in ("floor", "bright_peak", "span"):
        v = df[col].astype(float)
        med = v.median()
        # MAD-based, consistent with the project's robust-statistics convention
        # (k*1.4826*MAD) rather than mean/SD, which one outlier would drag.
        mad = float(np.median(np.abs(v - med)))
        scale = 1.4826 * mad
        if scale <= 0:
            continue
        z = (v - med) / scale
        for slc, zz in zip(df["slice"], z):
            if abs(zz) > 3.5:
                out.append({"slice": slc, "metric": col, "robust_z": round(float(zz), 2)})
    return {
        "n_slices": len(calibs),
        "checkable": True,
        "frac_spread": round(float(df["achieved_frac"].max() - df["achieved_frac"].min()), 4),
        "outliers": out,
    }


def plot_histogram(calib: Calibration, ax=None, xlim_quantile: float = 0.9995):
    """Histogram of the anchor channel with floor / bright peak / chosen cut marked.

    This is the plot the whole module exists for: it shows WHY a threshold is or
    is not reasonable, instead of asserting a number.
    """
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(9, 4.2))

    if calib.histogram.empty:
        ax.text(0.5, 0.5, "no histogram in JSON\n(re-run calibrate_threshold.groovy)",
                ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return ax

    h = calib.histogram.copy()
    centres = (h["lo"] + h["hi"]) / 2.0
    counts = h["count"].astype(float)

    # Background dominates by orders of magnitude; log-y keeps the nuclei
    # population visible instead of a single spike at zero.
    ax.fill_between(centres, counts, step="mid", alpha=0.35, color="#6b7fd7", linewidth=0)
    ax.plot(centres, counts, drawstyle="steps-mid", color="#3b4c9a", linewidth=1.0)
    ax.set_yscale("log")

    ax.axvspan(calib.floor, calib.bright_peak, color="#f0c000", alpha=0.12,
               label=f"floor→bright span ({calib.span})")
    ax.axvline(calib.floor, color="#888888", linestyle=":", linewidth=1.4,
               label=f"background floor ({calib.floor})")
    ax.axvline(calib.bright_peak, color="#d08770", linestyle=":", linewidth=1.4,
               label=f"bright peak ({calib.bright_peak})")
    ax.axvline(calib.threshold, color="#bf3b3b", linestyle="-", linewidth=2.0,
               label=f"threshold ({calib.threshold}, frac {calib.achieved_frac:.2f})")

    # Trim the long empty tail so the interesting range is not a sliver.
    cum = counts.cumsum() / max(counts.sum(), 1.0)
    hi_idx = int(np.searchsorted(cum.to_numpy(), xlim_quantile))
    hi = float(centres.iloc[min(hi_idx, len(centres) - 1)])
    ax.set_xlim(0, max(hi, calib.bright_peak * 1.25))

    ax.set_xlabel(f"{calib.anchor_channel} intensity")
    ax.set_ylabel("pixel count (log)")
    ax.set_title(f"{_slice_label(calib.image)} — detection threshold placement", fontsize=11)
    # Legend outside the data: an in-axes legend sat on top of the curve before
    # (same problem as commit aa1b41a).
    ax.legend(fontsize=8, loc="upper right", framealpha=0.9)
    return ax


def plot_sweep(calib: Calibration, ax=None):
    """What other span_frac values would have produced on THIS section."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(6, 3.6))
    if calib.sweep.empty:
        ax.text(0.5, 0.5, "no sweep in JSON", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return ax

    s = calib.sweep.sort_values("frac")
    ax.plot(s["frac"], s["threshold"], marker="o", color="#3b4c9a", linewidth=1.6, markersize=4)
    ax.axhline(calib.floor, color="#888888", linestyle=":", linewidth=1.2, label="background floor")
    ax.axhline(calib.bright_peak, color="#d08770", linestyle=":", linewidth=1.2, label="bright peak")
    ax.axvspan(SANE_FRAC_LO, SANE_FRAC_HI, color="#7fbf7f", alpha=0.12, label="working range")
    if np.isfinite(calib.span_frac):
        ax.axvline(calib.span_frac, color="#bf3b3b", linewidth=1.8,
                   label=f"configured ({calib.span_frac:g})")
    ax.set_xlabel("span_frac (pipeline.yml)")
    ax.set_ylabel("resulting threshold")
    ax.set_title(f"{_slice_label(calib.image)} — span_frac sweep", fontsize=11)
    ax.legend(fontsize=8, framealpha=0.9)
    return ax


def plot_series(calibs: list[Calibration], ax=None):
    """Floor / threshold / bright peak per slice -- acquisition drift at a glance."""
    import matplotlib.pyplot as plt

    if ax is None:
        _, ax = plt.subplots(figsize=(max(6.0, 1.1 * len(calibs) + 3), 4.0))
    if not calibs:
        ax.text(0.5, 0.5, "no calibrations found", ha="center", va="center", transform=ax.transAxes)
        ax.set_axis_off()
        return ax

    df = summary_table(calibs)
    x = np.arange(len(df))
    ax.fill_between(x, df["floor"], df["bright_peak"], alpha=0.15, color="#f0c000",
                    step="mid", label="floor→bright span")
    ax.plot(x, df["floor"], marker="_", linestyle="none", color="#888888", markersize=14, label="floor")
    ax.plot(x, df["bright_peak"], marker="_", linestyle="none", color="#d08770", markersize=14, label="bright peak")
    ax.plot(x, df["threshold"], marker="o", color="#bf3b3b", linewidth=1.6, markersize=5, label="threshold")
    ax.set_xticks(x)
    ax.set_xticklabels(df["slice"], rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("intensity")
    ax.set_title("Per-slice threshold calibration across the series", fontsize=11)
    ax.legend(fontsize=8, framealpha=0.9)
    return ax


def print_report(project_dir: Path, plots: bool = False) -> int:
    """CLI/notebook report. Returns a process exit code."""
    calibs = find_calibrations(project_dir)
    print("=" * 76)
    print(f"Threshold calibration — {Path(project_dir).name}")
    print("=" * 76)

    if not calibs:
        print("No *__threshold_calibration.json found in results/.")
        print("Run this in QuPath on at least one slice, then re-run:")
        print("    scripts/calibrate_threshold.groovy")
        return 1

    df = summary_table(calibs)
    print(df.to_string(index=False))
    print()

    absolute = df[df["mode"] == "absolute"]
    if not absolute.empty:
        print(f"WARNING: {len(absolute)} slice(s) used mode=absolute. An absolute cut does not")
        print("         transfer between sections or acquisitions. Set")
        print("         detection_threshold.mode: \"span_fraction\" in pipeline.yml.")
        print()

    flagged = df[df["status"] == "FLAG"]
    if not flagged.empty:
        print(f"FLAG: {len(flagged)} slice(s) place the cut outside the "
              f"{SANE_FRAC_LO:.2f}–{SANE_FRAC_HI:.2f} working range:")
        for _, r in flagged.iterrows():
            where = "near the background floor" if r["achieved_frac"] < SANE_FRAC_LO else "near the bright peak"
            risk = "background may be detected as nuclei" if r["achieved_frac"] < SANE_FRAC_LO \
                   else "dim real nuclei may be dropped"
            print(f"  {r['slice']}: frac {r['achieved_frac']:.3f} — {where}; {risk}")
        print()

    cons = consistency_report(calibs)
    if cons["checkable"]:
        print(f"Series consistency: {cons['n_slices']} slices, "
              f"achieved_frac spread {cons['frac_spread']:.4f}")
        if cons["outliers"]:
            print("  Histogram outlier(s) — likely acquisition inconsistency, not biology:")
            for o in cons["outliers"]:
                print(f"    {o['slice']}: {o['metric']} robust z = {o['robust_z']}")
        else:
            print("  No histogram outliers (robust z <= 3.5 on floor/bright_peak/span).")
        print()

    if plots:
        import matplotlib.pyplot as plt
        for c in calibs:
            plot_histogram(c)
            plt.tight_layout()
        plot_series(calibs)
        plt.tight_layout()
        plt.show()

    return 0 if flagged.empty and absolute.empty else 0  # advisory only, never fails the run


# ---------------------------------------------------------------------------
# Self-test -- synthetic data, no QuPath, no real images (project convention)
# ---------------------------------------------------------------------------
def _synthetic_json(tmp: Path, label: str, floor: int, bright: int,
                    frac: float = 0.25, mode: str = "span_fraction") -> Path:
    span = bright - floor
    thr = round(floor + frac * span)
    # Bimodal-ish histogram: a big background peak at `floor`, a small one at `bright`.
    bins = []
    for lo in range(0, 4096, 8):
        d0 = abs(lo - floor)
        d1 = abs(lo - bright)
        count = int(1e6 * np.exp(-(d0 ** 2) / (2 * 40.0 ** 2))
                    + 2e3 * np.exp(-(d1 ** 2) / (2 * 300.0 ** 2)))
        bins.append({"lo": lo, "hi": lo + 7, "count": count})
    payload = {
        "image": f"{label}_MIP.ome.tiff - {label}",
        "anchor_channel": "DAPI-T4",
        "mode": mode,
        "span_frac": frac,
        "resolution_level": 0,
        "smooth_window": 15,
        "peak_prominence": 100,
        "floor": floor,
        "bright_peak": bright,
        "span": span,
        "threshold": thr,
        "sweep": [{"frac": f, "threshold": round(floor + f * span)}
                  for f in (0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)],
        "histogram": bins,
    }
    p = tmp / f"{label}__threshold_calibration.json"
    p.write_text(json.dumps(payload))
    return p


def _self_test() -> None:
    import tempfile

    print("cockpit_threshold self-test")
    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "proj"
        res = proj / "results"
        res.mkdir(parents=True)

        # The real 2026-07-28 numbers: floor 162, bright 2268, operator chose 700.
        _synthetic_json(res, "s1", 162, 2268, frac=0.25)
        _synthetic_json(res, "s2", 180, 2400, frac=0.25)
        _synthetic_json(res, "s3", 150, 2100, frac=0.25)

        calibs = find_calibrations(proj)
        assert len(calibs) == 3, f"expected 3 calibrations, got {len(calibs)}"

        c1 = calibs[0]
        # The load-bearing arithmetic: 162 + 0.25*(2268-162) = 688.5, which rounds to
        # 688 or 689 depending on the half-rounding convention (Python round() is
        # banker's, Groovy Math.round() is half-up). Either is correct -- a 1-count
        # difference in a 2106-wide span is immaterial -- so assert the value to
        # within 1, not exactly. achieved_frac is likewise quantized to 1/span
        # (~4.7e-4) because the threshold is an integer.
        assert c1.span == 2106, f"span {c1.span} != 2106"
        assert abs(c1.threshold - 688.5) <= 1, f"threshold {c1.threshold} not ~688.5"
        assert abs(c1.achieved_frac - 0.25) < 2.0 / c1.span, f"achieved_frac {c1.achieved_frac}"
        assert c1.status == "PASS", f"status {c1.status}"
        print(f"  span_fraction arithmetic OK: floor {c1.floor} + 0.25 x {c1.span} -> {c1.threshold}")

        # Sanity check against the historical absolute value: 700 on this section
        # corresponds to frac 0.256, i.e. the new rule reproduces the operator call.
        hist_frac = (700 - 162) / 2106
        assert abs(hist_frac - 0.2555) < 1e-3, hist_frac
        print(f"  historical absolute 700 == frac {hist_frac:.4f} -> new default 0.25 reproduces it")

        df = summary_table(calibs)
        assert list(df["slice"]) == ["s1", "s2", "s3"], list(df["slice"])
        assert (df["status"] == "PASS").all()
        print(f"  summary_table OK ({len(df)} rows, all PASS)")

        cons = consistency_report(calibs)
        assert cons["checkable"] and not cons["outliers"], cons
        print("  consistency_report OK (no outliers on a consistent series)")

        # An outlier slice must be caught: a section imaged much brighter.
        _synthetic_json(res, "s4", 900, 9000, frac=0.25)
        cons2 = consistency_report(find_calibrations(proj))
        assert cons2["outliers"], "failed to flag a clearly outlying slice"
        print(f"  outlier detection OK (flagged {sorted({o['slice'] for o in cons2['outliers']})})")

        # An absolute-mode slice that lands too high must be FLAGged, since that is
        # exactly the silent-under-detection failure this module exists to surface.
        p = _synthetic_json(res, "s5", 162, 2268, frac=0.80, mode="absolute")
        c5 = load_calibration(p)
        assert c5.status == "FLAG", f"expected FLAG for frac 0.80, got {c5.status}"
        print(f"  FLAG OK: absolute cut at frac {c5.achieved_frac:.2f} -> dim nuclei dropped")

        # Empty project must not raise.
        empty = Path(td) / "empty"
        (empty / "results").mkdir(parents=True)
        assert find_calibrations(empty) == []
        assert summary_table([]).empty
        print("  empty-project handling OK")

        # load_config_threshold: reads the rule, and degrades to a helpful message
        # rather than raising when the block is absent.
        assert "error" in load_config_threshold(empty)
        (proj / "pipeline.yml").write_text(
            'anchor:\n  name: "DAPI"\n  channel: "DAPI-T4"\n'
            'detection_threshold:\n  mode: "span_fraction"\n  span_frac: 0.25\n'
            "  resolution_level: 0\n  smooth_window: 15\n  peak_prominence: 100\n"
        )
        cfg = load_config_threshold(proj)
        assert cfg["mode"] == "span_fraction" and cfg["span_frac"] == 0.25, cfg
        print(f"  load_config_threshold OK ({cfg['mode']}, span_frac={cfg['span_frac']})")

        # Plotting must work headless without a display.
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plot_histogram(c1); plot_sweep(c1); plot_series(calibs)
        plt.close("all")
        print("  plots render headless OK")

    print("SELF-TEST PASSED")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--project", type=Path, default=None, help="QuPath project directory")
    p.add_argument("--results-dir", type=Path, default=None,
                   help="override <project>/results")
    p.add_argument("--plots", action="store_true", help="render the histogram/series plots")
    p.add_argument("--self-test", action="store_true", help="run on synthetic data and exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0
    if args.project is None:
        sys.exit("ERROR: --project is required (or use --self-test)")
    return print_report(args.project, plots=args.plots)


if __name__ == "__main__":
    sys.exit(main())
