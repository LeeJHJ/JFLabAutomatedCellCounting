#!/usr/bin/env python3
"""cockpit_marker_gui.py -- set k_robust for a marker by LOOKING at the image.

WHY THIS EXISTS
    `cockpit_threshold_gui.py` put the ANCHOR cut where this project's evidence
    hierarchy says decisions belong: on what the operator sees. The marker cuts had
    no equivalent. `k_robust` was set from counts and from borrowed values -- TdT's
    2.0 came from one by-eye call on M3 Hipp2 s3 on 2026-07-30 and has been copied
    across every project since -- while the thing it actually controls, which cells
    get called positive, was only ever inspected in QuPath after a full re-run.

    Operator request, 2026-08-04 (tuning_log.csv): "lets add interactive gui for k
    threshold adjustment like the DAPI".

WHY IT IS CHEAP
    k_robust is applied AFTER detection, to a per-cell measurement that is already
    on disk. `03_export_region_table.groovy` writes `<marker>_bgsub` into
    *__percell_export.tsv, and that column is exactly what 02_detect_classify.groovy
    thresholds. So sweeping k needs NO QuPath, NO re-detection, and no image
    re-processing -- only the TSV and, for the picture, one crop of the MIP.

    Changing k is therefore seconds, not the ~30 minutes a detection re-run costs.

WHAT IT SHOWS, per crop
    1. the marker channel, contrast-stretched
    2. the same crop with every detected cell centroid ringed -- filled where the
       cell is positive at the current k, hollow where it is not
    3. the bg-sub distribution for the whole section, log-y, with the cut drawn on it

    The picture is a crop; the CUT is always derived from the whole section's
    classifiable population, exactly as the pipeline derives it. Deriving it from
    the crop would give a number that changes as you scroll, which is precisely the
    bug this module exists to avoid.

EXACT-REPRODUCTION CONTRACT
    The median / MAD / threshold arithmetic is imported from k_sweep_readout, which
    carries the validated reproduction of 02_detect_classify.groovy. It is NOT
    re-implemented here -- two copies of a classifier rule is how the project got a
    silent double-classification bug before (see CLAUDE.md, "one classification
    path").

WHAT IT DOES NOT DO
    It does not write anything. It prints a paste-ready `pipeline.yml` marker block
    and leaves the edit to you, the same as the anchor picker.

READ-ONLY: reads *__percell_export.tsv, the MIP, and pipeline.yml. Never re-runs
QuPath, never edits config, never touches the CZI.

USAGE
    # notebook (the intended path)
    from scripts.cockpit_marker_gui import launch
    launch(project="M5 Hipp3 080326/M5 Hipp3 080326 QuPath")

    # shell -- numbers only, no widgets
    python3 scripts/cockpit_marker_gui.py --project "<project>" --marker TdT
    python3 scripts/cockpit_marker_gui.py --self-test
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from k_sweep_readout import (  # noqa: E402  -- one definition of the cut, imported not copied
    classifiable_mask,
    load_percell,
    markers_in_df,
    robust_stats,
    robust_threshold,
)

DEFAULT_CROP_PX = 512
DEFAULT_N_CROPS = 6
DEFAULT_K_RANGE = (0.5, 6.0)

# Advisory only. Positive fractions seen on sections this project considers good,
# recorded so a wildly different number prompts a look at the image rather than a
# shrug. [ASSUMED] tier-3 -- never tune to move a number into this band.
ADVISORY_POS_FRAC = {"Fos": (0.02, 0.15), "TdT": (0.01, 0.12)}


# ── config / discovery ──────────────────────────────────────────────────────────

def find_percell(results_dir: Path) -> list[Path]:
    """Every per-cell export in a project's results dir, sorted by slice label."""
    return sorted(results_dir.glob("*__percell_export.tsv"))


def slice_label(path: Path) -> str:
    """'..._MIP.ome.tiff - M5-hipp3_s1__id1__percell_export.tsv' -> 'M5-hipp3_s1'."""
    m = re.search(r"-\s*([A-Za-z0-9._-]+?)__id\d+__percell_export\.tsv$", path.name)
    return m.group(1) if m else path.stem


def find_mip_for(slice_id: str, project_dir: Path) -> Path | None:
    """The MIP that produced a slice, looked up in the project's sibling mips/ dir."""
    for base in (project_dir.parent / "mips", project_dir / "mips"):
        if not base.is_dir():
            continue
        for p in sorted(base.glob("*.ome.tif*")):
            if slice_id in p.name:
                return p
    return None


def parse_markers(project_dir: Path) -> list[dict]:
    """pipeline.yml's `markers:` block as a list of dicts, in file order.

    One scanner for every field the picker needs (name, channel, compartment,
    k_robust), rather than a regex per field -- a per-field regex has to guess where
    a marker entry ends, and the last entry in the block has no `- name:` after it to
    anchor on. That mis-parse silently reported the global k for the one marker that
    carries an override.

    Deliberately reads the same file 02_detect_classify.groovy reads, so the picture
    and the pipeline can never disagree about a marker's channel.
    """
    cfg = project_dir / "pipeline.yml"
    if not cfg.exists():
        return []
    entries: list[dict] = []
    in_markers = False
    for raw in cfg.read_text().splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if re.match(r"^markers:\s*$", line):
            in_markers = True
            continue
        if in_markers and re.match(r"^\S", line):
            break                       # dedent to column 0 ends the block
        if not in_markers:
            continue
        m = re.match(r"\s*-\s*name:\s*\"?([^\"]+?)\"?\s*$", line)
        if m:
            entries.append({"name": m.group(1)})
            continue
        if not entries:
            continue
        kv = re.match(r"\s*(channel|compartment|k_robust):\s*\"?([^\"]+?)\"?\s*$", line)
        if kv:
            key, val = kv.group(1), kv.group(2)
            entries[-1][key] = float(val) if key == "k_robust" else val
    return entries


def marker_channel_map(project_dir: Path) -> dict[str, str]:
    """marker name -> channel name."""
    return {e["name"]: e["channel"] for e in parse_markers(project_dir) if "channel" in e}


def marker_compartment(project_dir: Path, marker: str) -> str:
    for e in parse_markers(project_dir):
        if e["name"] == marker:
            return str(e.get("compartment", "nuclear"))
    return "nuclear"


def configured_k(project_dir: Path, marker: str) -> float | None:
    """The k_robust in force for a marker: its per-marker override, else the global."""
    cfg = project_dir / "pipeline.yml"
    if not cfg.exists():
        return None
    for e in parse_markers(project_dir):
        if e["name"] == marker and "k_robust" in e:
            return float(e["k_robust"])
    m = re.search(r"^k_robust:\s*([0-9.]+)", cfg.read_text(), re.M)
    return float(m.group(1)) if m else None


# ── the cut, and what it does to the section ────────────────────────────────────

def marker_population(df: pd.DataFrame, marker: str) -> np.ndarray:
    """The classifiable bg-sub values for a marker: class != 'Excluded' and finite.

    This is the population the pipeline derives the cut from AND counts over -- both,
    which is why it must be one function and not two filters that can drift apart.
    """
    return df.loc[classifiable_mask(df, marker), f"{marker}_bgsub"].to_numpy(float)


def summarize(values: np.ndarray, k: float) -> dict:
    med, mad, rsd = robust_stats(values)
    thr = robust_threshold(values, k)
    n_pos = int((values >= thr).sum()) if values.size and np.isfinite(thr) else 0
    return {
        "n": int(values.size), "median": med, "mad": mad, "robust_sd": rsd,
        "threshold": thr, "n_pos": n_pos,
        "frac_pos": (n_pos / values.size) if values.size else float("nan"),
    }


def advisory(marker: str, frac: float) -> str:
    band = ADVISORY_POS_FRAC.get(marker)
    if band is None or not np.isfinite(frac):
        return ""
    lo, hi = band
    if frac < lo:
        return f"  <assumed> below the {lo:.0%}-{hi:.0%} band seen elsewhere -- go LOOK, do not tune to it"
    if frac > hi:
        return f"  <assumed> above the {lo:.0%}-{hi:.0%} band seen elsewhere -- go LOOK, do not tune to it"
    return f"  <assumed> inside the {lo:.0%}-{hi:.0%} band seen elsewhere"


def k_for_threshold(values: np.ndarray, threshold: float) -> float:
    """Inverse of robust_threshold: the k that puts the cut at a chosen value."""
    med, _mad, rsd = robust_stats(values)
    if not np.isfinite(rsd) or rsd == 0:
        return float("nan")
    return (threshold - med) / rsd


def sweep(values: np.ndarray, ks: np.ndarray) -> pd.DataFrame:
    rows = []
    for k in ks:
        s = summarize(values, float(k))
        rows.append({"k": float(k), "threshold": s["threshold"],
                     "n_pos": s["n_pos"], "frac_pos": s["frac_pos"]})
    return pd.DataFrame(rows)


def config_block(marker: str, channel: str, compartment: str, k: float) -> str:
    """Paste-ready pipeline.yml marker entry. Printed, never written."""
    return (f'  - name: "{marker}"\n'
            f'    channel: "{channel}"\n'
            f'    compartment: "{compartment}"\n'
            f'    k_robust: {k:g}        # set by eye on the marker overlay, '
            f'cockpit_marker_gui\n')


# ── crop selection ──────────────────────────────────────────────────────────────

def positive_dense_crops(df: pd.DataFrame, marker: str, k: float,
                         crop_px: int = DEFAULT_CROP_PX,
                         n_crops: int = DEFAULT_N_CROPS) -> list[tuple[int, int]]:
    """Crop origins with the most positive cells at k.

    Judging a marker cut needs positives in frame. A crop chosen for tissue density
    (what the anchor picker does) often contains none, and an empty crop cannot
    discriminate a good cut from a strict one.
    """
    sub = df[classifiable_mask(df, marker)]
    if sub.empty:
        return [(0, 0)]
    vals = sub[f"{marker}_bgsub"].to_numpy(float)
    thr = robust_threshold(marker_population(df, marker), k)
    pos = sub.loc[vals >= thr] if np.isfinite(thr) else sub
    if pos.empty:
        pos = sub
    gy = (pos["centroid_y_px"] // crop_px).astype(int)
    gx = (pos["centroid_x_px"] // crop_px).astype(int)
    counts = pd.Series(list(zip(gy, gx))).value_counts()
    return [(int(y) * crop_px, int(x) * crop_px) for (y, x) in counts.index[:n_crops]]


def cells_in_crop(df: pd.DataFrame, marker: str, y: int, x: int,
                  crop_px: int) -> pd.DataFrame:
    m = classifiable_mask(df, marker)
    sub = df[m]
    sel = ((sub["centroid_y_px"] >= y) & (sub["centroid_y_px"] < y + crop_px) &
           (sub["centroid_x_px"] >= x) & (sub["centroid_x_px"] < x + crop_px))
    return sub[sel]


# ── shell report ────────────────────────────────────────────────────────────────

def report(project: Path, marker: str | None = None, ks: np.ndarray | None = None,
           results_dir: Path | str | None = None) -> int:
    project = Path(project)
    # results_dir exists so the MANUAL-ROI route (scripts/roi_count.groovy, which writes
    # the identical per-cell schema into results/roi/) can use this picker as-is. Default
    # None keeps the registered route's behaviour byte-for-byte unchanged.
    results = Path(results_dir) if results_dir is not None else project / "results"
    if not results.is_dir():
        print(f"no {results} -- run the pipeline first.")
        return 2
    exports = find_percell(results)
    if not exports:
        print(f"no *__percell_export.tsv in {results}.")
        return 2

    chans = marker_channel_map(project)
    ks = np.arange(*DEFAULT_K_RANGE, 0.5) if ks is None else ks

    for path in exports:
        df = load_percell(path)
        label = slice_label(path)
        names = markers_in_df(df) if marker is None else [marker]
        print(f"\n=== {label}   ({len(df):,} cells)")
        for name in names:
            if f"{name}_bgsub" not in df.columns:
                print(f"  {name}: no {name}_bgsub column in this export -- skipped")
                continue
            vals = marker_population(df, name)
            cfg_k = configured_k(project, name)
            print(f"  {name}  (channel {chans.get(name, '?')})   "
                  f"classifiable n={vals.size:,}   configured k={cfg_k}")
            s = sweep(vals, ks)
            for _, r in s.iterrows():
                mark = "  <- configured" if cfg_k is not None and abs(r["k"] - cfg_k) < 1e-9 else ""
                print(f"    k={r['k']:>4.1f}  cut={r['threshold']:>10.1f}  "
                      f"{int(r['n_pos']):>8,} positive  {r['frac_pos']*100:>6.2f} %{mark}")
            if cfg_k is not None:
                cur = summarize(vals, cfg_k)
                print(advisory(name, cur["frac_pos"]).rstrip())
    return 0


# ── notebook widget ─────────────────────────────────────────────────────────────

def launch(project: str | Path, marker: str | None = None,
           crop_px: int = DEFAULT_CROP_PX, n_crops: int = DEFAULT_N_CROPS,
           results_dir: Path | str | None = None):
    """Interactive k picker. Mirrors cockpit_threshold_gui.launch().

    results_dir points the picker at a different export directory — used by the
    manual-ROI route, whose exports live in results/roi/ but carry the identical
    schema. Default None is the registered route, unchanged.
    """
    import ipywidgets as widgets
    import matplotlib.pyplot as plt
    import tifffile
    from IPython.display import display

    project = Path(project)
    results = Path(results_dir) if results_dir is not None else project / "results"
    exports = find_percell(results)
    if not exports:
        raise FileNotFoundError(f"no *__percell_export.tsv under {results}")
    chans = marker_channel_map(project)
    cache: dict = {}

    slice_dd = widgets.Dropdown(options=[(slice_label(p), p) for p in exports],
                                value=exports[0], description="slice:",
                                layout=widgets.Layout(width="480px"))
    df0 = load_percell(exports[0])
    names = markers_in_df(df0) if marker is None else [marker]
    marker_dd = widgets.ToggleButtons(options=names, value=names[0], description="marker:")
    k_sl = widgets.FloatSlider(value=configured_k(project, names[0]) or 3.0,
                               min=DEFAULT_K_RANGE[0], max=DEFAULT_K_RANGE[1], step=0.05,
                               description="k_robust:", continuous_update=False,
                               readout_format=".2f", layout=widgets.Layout(width="520px"))
    crop_dd = widgets.Dropdown(description="crop:", layout=widgets.Layout(width="300px"))
    out = widgets.Output()

    def _load(path: Path):
        if cache.get("path") == path:
            return
        df = load_percell(path)
        sid = slice_label(path)
        mip = find_mip_for(sid, project)
        img_names: list[str] = []
        if mip is not None:
            with tifffile.TiffFile(mip) as tf:
                img_names = re.findall(r'<Channel[^>]*Name="([^"]+)"', tf.ome_metadata or "")
        cache.update(path=path, df=df, sid=sid, mip=mip, img_names=img_names, planes={})

    def _plane(channel: str):
        """Lazily read one channel of the MIP; cached per slice."""
        import tifffile as tif
        if channel in cache["planes"]:
            return cache["planes"][channel]
        mip, names_ = cache["mip"], cache["img_names"]
        if mip is None or channel not in names_:
            cache["planes"][channel] = None
        else:
            cache["planes"][channel] = tif.imread(mip, key=names_.index(channel))
        return cache["planes"][channel]

    def _redraw(*_):
        _load(slice_dd.value)
        df, name = cache["df"], marker_dd.value
        if f"{name}_bgsub" not in df.columns:
            with out:
                out.clear_output(wait=True)
                print(f"{name}_bgsub not in this export.")
            return
        vals = marker_population(df, name)
        k = k_sl.value
        s = summarize(vals, k)

        origins = positive_dense_crops(df, name, k, crop_px, n_crops)
        if crop_dd.options != tuple(range(len(origins))):
            crop_dd.options = [(f"{i+1} of {len(origins)}  (y={y}, x={x})", i)
                               for i, (y, x) in enumerate(origins)]
            crop_dd.value = 0
        y, x = origins[min(crop_dd.value or 0, len(origins) - 1)]

        with out:
            out.clear_output(wait=True)
            fig, axes = plt.subplots(1, 3, figsize=(16, 5))
            plane = _plane(chans.get(name, ""))
            if plane is None:
                axes[0].text(.5, .5, "MIP or channel not found", ha="center")
                axes[1].text(.5, .5, "no image -- numbers below still valid", ha="center")
                for a in axes[:2]:
                    a.set_xticks([]); a.set_yticks([])
            else:
                crop = plane[y:y + crop_px, x:x + crop_px]
                lo, hi = np.percentile(crop, [1, 99.5])
                for a in axes[:2]:
                    a.imshow(crop, cmap="gray", vmin=lo, vmax=max(hi, lo + 1))
                    a.set_xticks([]); a.set_yticks([])
                axes[0].set_title(f"{chans.get(name)}   (y={y}, x={x})")
                cc = cells_in_crop(df, name, y, x, crop_px)
                cv = cc[f"{name}_bgsub"].to_numpy(float)
                pos = cv >= s["threshold"]
                axes[1].scatter(cc["centroid_x_px"] - x, cc["centroid_y_px"] - y,
                                s=46, facecolors="none", edgecolors="#38b000", linewidths=.9)
                axes[1].scatter(cc["centroid_x_px"][pos] - x, cc["centroid_y_px"][pos] - y,
                                s=46, facecolors="#ff2d00", edgecolors="#ff2d00",
                                alpha=.55, linewidths=.9)
                axes[1].set_xlim(0, crop_px); axes[1].set_ylim(crop_px, 0)
                axes[1].set_title(f"filled = {name}+ at k={k:g}   "
                                  f"({int(pos.sum())} of {len(cc)} in crop)")

            axes[2].hist(vals, bins=200, color="0.45",
                         range=(float(np.nanpercentile(vals, .5)),
                                float(np.nanpercentile(vals, 99.8))))
            axes[2].set_yscale("log")
            axes[2].axvline(s["median"], color="tab:blue", ls="--", lw=1.4,
                            label=f"median {s['median']:,.0f}")
            axes[2].axvline(s["threshold"], color="tab:red", lw=2.4,
                            label=f"cut {s['threshold']:,.0f}  (k={k:g})")
            axes[2].set_title(f"{name}_bgsub, whole section (log y)")
            axes[2].legend(fontsize=8)
            fig.tight_layout()
            plt.show()

            cfg_k = configured_k(project, name)
            print(f"  {name}: {s['n_pos']:,} of {s['n']:,} classifiable positive "
                  f"({s['frac_pos']*100:.2f} %)   cut {s['threshold']:,.1f}")
            print(f"  median {s['median']:,.1f}   robust_sd {s['robust_sd']:,.1f} "
                  f"(1.4826 x MAD {s['mad']:,.1f})")
            if cfg_k is not None and abs(cfg_k - k) > 1e-9:
                cur = summarize(vals, cfg_k)
                print(f"  configured k={cfg_k:g} would give {cur['n_pos']:,} "
                      f"({cur['frac_pos']*100:.2f} %) -- a change of "
                      f"{s['n_pos'] - cur['n_pos']:+,} cells")
            print(advisory(name, s["frac_pos"]).rstrip())
            print("\n  paste into pipeline.yml markers: ")
            print(config_block(name, chans.get(name, "?"),
                               marker_compartment(project, name), k))

    for w in (slice_dd, marker_dd, k_sl, crop_dd):
        w.observe(_redraw, names="value")
    _redraw()
    display(widgets.VBox([widgets.HBox([slice_dd, marker_dd]),
                          widgets.HBox([k_sl, crop_dd]), out]))


# ── self-test ───────────────────────────────────────────────────────────────────

def _self_test() -> int:
    ok = True

    def check(name: str, cond: bool, detail: str = "") -> None:
        nonlocal ok
        print(f"  {'PASS' if cond else 'FAIL'}  {name}{'' if cond else '  -- ' + detail}")
        ok &= bool(cond)

    print("cockpit_marker_gui self-test")

    # the cut must be the imported one, applied with >= as the groovy does
    v = np.array([0., 1., 2., 3., 4., 100.])
    med, mad, rsd = robust_stats(v)
    thr = robust_threshold(v, 2.0)
    check("threshold == median + k*1.4826*MAD",
          abs(thr - (med + 2.0 * rsd)) < 1e-9, f"{thr} vs {med + 2.0*rsd}")
    s = summarize(v, 2.0)
    check("positive uses >= (boundary cell counts)",
          summarize(np.array([0., 0., 0., 10.]), 0.0)["n_pos"] >= 1)
    check("summarize n matches input", s["n"] == 6)

    # k_for_threshold inverts robust_threshold
    kk = k_for_threshold(v, thr)
    check("k_for_threshold inverts robust_threshold", abs(kk - 2.0) < 1e-9, f"{kk}")

    # classifiable excludes 'Excluded' and non-finite
    df = pd.DataFrame({"class": ["Negative", "Excluded", "Fos+", "Negative"],
                       "TdT_bgsub": [1.0, 5.0, 2.0, np.nan],
                       "centroid_x_px": [0, 1, 2, 3], "centroid_y_px": [0, 1, 2, 3]})
    pop = marker_population(df, "TdT")
    check("classifiable drops Excluded and NaN", pop.size == 2 and set(pop) == {1.0, 2.0},
          f"{pop}")

    # a monotone sweep: raising k can never increase positives
    vals = np.random.default_rng(0).normal(100, 10, 5000)
    sw = sweep(vals, np.arange(1, 5, .5))
    check("n_pos is non-increasing in k", bool((sw["n_pos"].diff().dropna() <= 0).all()))

    # marker/channel + k parsing off a synthetic pipeline.yml
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        (p / "pipeline.yml").write_text(
            'markers:\n'
            '  - name: "Fos"\n    channel: "AF488-T3"\n    compartment: "nuclear"\n'
            '  - name: "TdT"\n    channel: "AF568-T2"\n    compartment: "whole-cell"\n'
            '    k_robust: 2.0        # override\n'
            'exclude_acronyms: ["VS"]\n'
            'k_robust: 3.0\n')
        cm = marker_channel_map(p)
        check("marker->channel parsed", cm == {"Fos": "AF488-T3", "TdT": "AF568-T2"}, f"{cm}")
        # TdT is the LAST entry in the block, which is the case the old per-field
        # regex got wrong -- it had no `- name:` after it to anchor the block end on.
        check("per-marker k override wins (last entry in block)",
              configured_k(p, "TdT") == 2.0, f"{configured_k(p, 'TdT')}")
        check("global k used when no override", configured_k(p, "Fos") == 3.0)
        check("compartment parsed", marker_compartment(p, "TdT") == "whole-cell",
              marker_compartment(p, "TdT"))
        check("markers block ends at dedent (exclude_acronyms not absorbed)",
              [e["name"] for e in parse_markers(p)] == ["Fos", "TdT"],
              f"{[e['name'] for e in parse_markers(p)]}")

    check("slice_label strips the export suffix",
          slice_label(Path("X_MIP.ome.tiff - M5-hipp3_s1__id1__percell_export.tsv"))
          == "M5-hipp3_s1")

    # crop picker puts the densest positive tile first
    rng = np.random.default_rng(1)
    big = pd.DataFrame({
        "class": ["Negative"] * 400,
        "TdT_bgsub": np.r_[rng.normal(0, 1, 300), rng.normal(500, 1, 100)],
        "centroid_x_px": np.r_[rng.integers(0, 512, 300), rng.integers(512, 1024, 100)],
        "centroid_y_px": np.zeros(400, dtype=int)})
    origins = positive_dense_crops(big, "TdT", 3.0, crop_px=512, n_crops=2)
    check("crop picker finds the positive-dense tile", origins[0] == (0, 512), f"{origins}")

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--project", type=Path, default=None,
                   help="QuPath project dir (contains results/ and pipeline.yml)")
    p.add_argument("--marker", type=str, default=None,
                   help="restrict to one marker name (default: every marker in the export)")
    p.add_argument("--k-min", type=float, default=DEFAULT_K_RANGE[0])
    p.add_argument("--k-max", type=float, default=DEFAULT_K_RANGE[1])
    p.add_argument("--k-step", type=float, default=0.5)
    p.add_argument("--self-test", action="store_true", help="run built-in tests and exit")
    return p.parse_args()


def main() -> int:
    a = parse_args()
    if a.self_test:
        return _self_test()
    if a.project is None:
        print("--project is required (or use --self-test)")
        return 2
    return report(a.project, a.marker, np.arange(a.k_min, a.k_max + 1e-9, a.k_step))


if __name__ == "__main__":
    raise SystemExit(main())
