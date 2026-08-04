#!/usr/bin/env python3
"""cockpit_threshold_gui.py -- set the anchor threshold by LOOKING at the image.

WHY THIS EXISTS
    The anchor cut decides which pixels are nucleus, and until now it was chosen
    from numbers: a floor, a bright peak, a span fraction. Those numbers are hard
    to hold in your head as intensities, and on 2026-08-04 they went wrong in a way
    no number made obvious -- M5-hipp3_s1's histogram is TRIMODAL (zero-padded
    canvas at 0, empty-field detector offset at ~384, nuclei at ~5632), so BraiAn's
    "floor = peak 1, bright = peak 2" rule locked onto the two background
    populations and cut at 123 instead of ~1700. Detection then found 295,585
    nuclei -- 5,305/mm^2, denser than any section ever run here, and denser than
    the one previously excluded for over-detection.

    The cause is BIN WIDTH, not the peak rule: at native 16-bit resolution the
    near-zero background carries enough wrinkles to supply a false second peak, and
    at 128-wide bins it does not. Measured on that exact image -- bins=4096 gives
    floor 32 / bright 384 / cut 120; bins=512 gives floor 256 / bright 5632 / cut
    1600. See find_peaks() for the table and the self-test for the assertion.

    A histogram alone does not show that. The mask over the image does, instantly.

    So this module puts the decision where the project's evidence hierarchy already
    says it belongs: on what the operator SEES. You scrub a slider, you watch the
    mask land on nuclei or bleed into background, and you stop when it looks right.
    The numbers follow the eye instead of leading it.

WHAT IT SHOWS, per crop
    1. the raw anchor channel, contrast-stretched
    2. the same crop with the above-threshold mask overlaid in red
    3. the histogram, log-y, with the floor / bright peak / chosen cut drawn on it

    The mask is applied to the BACKGROUND-SUBTRACTED crop, because that is what
    BraiAnDetect thresholds (BraiAn.yml sets backgroundRadiusMicrons: 10). Masking
    the raw image would mislead badly -- tissue autofluorescence alone sits near
    5,600 on these sections, so any sane cut looks permissive against it.

    Under them: the fraction of pixels the cut accepts, next to the same fraction
    measured on real sections at their real thresholds (76% and 87% on two good
    ones, 98% on the one that over-detected).

THRESHOLDING METHODS
    absolute        one number, straight from the slider. The escape hatch, and the
                    right answer when the peak rule cannot work (see M5c_s3/s4,
                    whose histograms have no separable floor at all).
    span_fraction   floor + frac x (bright - floor), the self-calibrating rule that
                    tracks staining and laser drift across sections. Endpoints are
                    found on a COARSELY binned histogram, which is what keeps the
                    finder out of the background wrinkles; an IGNORE-BELOW control
                    is available when even that is not enough.

    span_fraction is preferred whenever it works, because it re-measures per section
    and so keeps sections comparable. absolute does not -- it must be re-checked on
    every section, and a section dimmer than the one it was tuned on will silently
    under-detect.

Usage:
    # in a notebook (this is the intended path)
    import cockpit_threshold_gui as gui
    gui.launch("M5 Hipp3 080326/M5 Hipp3 080326 QuPath")

    # from the shell -- report the numbers without any widgets
    python3 scripts/cockpit_threshold_gui.py --project "<project dir>"
    python3 scripts/cockpit_threshold_gui.py --self-test
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent

# Crop size in pixels. 512 is a compromise: big enough to hold enough nuclei that
# over/under-segmentation is visible at a glance, small enough to redraw instantly
# while a slider is being dragged.
DEFAULT_CROP_PX = 512
DEFAULT_N_CROPS = 6
DEFAULT_HIST_BINS = 512

# Background-subtraction radius used for the PREVIEW only, mirroring BraiAn.yml's
# backgroundRadiusMicrons. Nothing here is written to any config.
PREVIEW_BACKGROUND_RADIUS_UM = 10.0


# ---------------------------------------------------------------------------
# Reading the image
# ---------------------------------------------------------------------------
def _ome_pixel_um(path: Path) -> float | None:
    """PhysicalSizeX from the OME-XML, or None when the file carries no calibration.

    Never defaulted: every micron-denominated number downstream is scaled by this,
    so a guessed value corrupts the density readout silently (CLAUDE.md).
    """
    import tifffile

    with tifffile.TiffFile(str(path)) as handle:
        xml = handle.ome_metadata or ""
    found = re.findall(r'PhysicalSizeX="([^"]+)"', xml)
    return float(found[0]) if found else None


def _ome_channel_names(path: Path) -> list[str]:
    import tifffile

    with tifffile.TiffFile(str(path)) as handle:
        xml = handle.ome_metadata or ""
    return re.findall(r'<Channel[^>]*Name="([^"]+)"', xml)


def anchor_channel_index(names: list[str], anchor: str = "DAPI") -> int:
    """Physical index of the anchor channel, matched by name.

    Falls back to the LAST channel, which is where DAPI sits in this rig's physical
    read order -- the same fallback czi_mip.py uses, kept identical on purpose.
    """
    for i, name in enumerate(names):
        if anchor.upper() in name.upper():
            return i
    return len(names) - 1 if names else 0


def read_anchor(mip_path: Path, anchor: str = "DAPI") -> tuple[np.ndarray, float | None, str]:
    """Load the anchor channel of a MIP as a 2D array.

    Returns (image, pixel_um, channel_name). The whole plane is read once and then
    cached by the caller -- crops must be instant while a slider is moving.
    """
    import tifffile

    names = _ome_channel_names(mip_path)
    idx = anchor_channel_index(names, anchor)
    with tifffile.TiffFile(str(mip_path)) as handle:
        arr = handle.series[0].asarray()
    if arr.ndim == 3:
        plane = arr[idx]
    elif arr.ndim == 2:
        plane = arr
    else:
        raise ValueError(f"{mip_path.name}: expected 2D or 3D (C,Y,X), got shape {arr.shape}")
    name = names[idx] if idx < len(names) else f"channel {idx}"
    return plane, _ome_pixel_um(mip_path), name


# ---------------------------------------------------------------------------
# Choosing where to look
# ---------------------------------------------------------------------------
def tissue_crops(image: np.ndarray, n_crops: int = DEFAULT_N_CROPS,
                 crop_px: int = DEFAULT_CROP_PX, ignore_below: float = 0.0) -> list[tuple[int, int]]:
    """Origins (y, x) of n_crops windows spread across TISSUE, brightest first.

    Sampling at random would mostly land on the zero-padded canvas -- 7-10% of these
    MIPs is padding and much more is empty field. Crops are scored on the fraction of
    pixels above `ignore_below`, then spread out so they do not all pile into one
    dense structure: the point is to see DIFFERENT parts of the section.
    """
    height, width = image.shape
    crop_px = int(min(crop_px, height, width))
    step = max(crop_px // 2, 1)

    # Score a coarse grid of candidate windows on tissue content.
    candidates: list[tuple[float, int, int]] = []
    for y in range(0, height - crop_px + 1, step):
        for x in range(0, width - crop_px + 1, step):
            window = image[y:y + crop_px:8, x:x + crop_px:8]   # subsample: scoring only
            score = float((window > ignore_below).mean())
            if score > 0.5:                                    # mostly tissue, not edge
                candidates.append((score, y, x))
    if not candidates:
        # Nothing passed -- fall back to the single densest window so the GUI still opens.
        return [((height - crop_px) // 2, (width - crop_px) // 2)]

    # Sample ACROSS the tissue-content range, not the top of it. Taking the highest
    # scoring windows returns the densest structure in the section every time (a
    # granule layer, or a bright artifact) -- the least informative place to judge a
    # threshold, and it hides exactly the sparse regions where a cut that is too low
    # shows itself first.
    candidates.sort()
    picks = np.linspace(0, len(candidates) - 1, num=min(n_crops * 4, len(candidates)))
    ranked = [candidates[int(round(i))] for i in picks][::-1]

    chosen: list[tuple[int, int]] = []
    min_sep = crop_px * 2
    for _, y, x in ranked:
        if all(abs(y - cy) >= min_sep or abs(x - cx) >= min_sep for cy, cx in chosen):
            chosen.append((y, x))
        if len(chosen) >= n_crops:
            break
    for _, y, x in ranked:                      # top up if separation was too strict
        if len(chosen) >= n_crops:
            break
        if (y, x) not in chosen:
            chosen.append((y, x))
    return chosen[:n_crops]


def subtract_background(crop: np.ndarray, pixel_um: float | None,
                        radius_um: float = 10.0) -> np.ndarray:
    """Approximate BraiAnDetect's background subtraction, so the preview is honest.

    THIS MATTERS. Detection does not threshold the raw image -- BraiAn.yml sets
    `backgroundRadiusMicrons: 10` with `backgroundByReconstruction: true`, so the cut
    is applied AFTER background removal. Masking the raw crop instead makes every
    threshold look far too permissive: on M5-hipp3_s1 a tissue crop is 99.8% above
    1600 raw, because tissue autofluorescence alone sits near 5,600.

    A white top-hat is an approximation of opening-by-reconstruction, not the same
    operator. Treat the mask as a faithful GUIDE to what detection sees, not as a
    reproduction of it -- the authority is still the overlay in QuPath.
    """
    from skimage.morphology import disk, white_tophat

    if pixel_um is None or pixel_um <= 0:
        return crop
    radius_px = max(int(round(radius_um / pixel_um)), 1)
    return white_tophat(crop, footprint=disk(radius_px))


# ---------------------------------------------------------------------------
# The histogram and its peaks
# ---------------------------------------------------------------------------
def histogram(image: np.ndarray, bins: int = DEFAULT_HIST_BINS,
              vmax: int = 65536) -> tuple[np.ndarray, np.ndarray]:
    """Counts and left bin edges over the full 16-bit range."""
    counts, edges = np.histogram(image, bins=bins, range=(0, vmax))
    return counts.astype(float), edges[:-1]


def find_peaks(counts: np.ndarray, edges: np.ndarray, ignore_below: float = 0.0,
               smooth_window: int = 5,
               prominence_frac: float = 0.02) -> tuple[float | None, float | None]:
    """Background floor and bright-nuclei peak, in INTENSITY units.

    BIN WIDTH IS THE WHOLE STORY, and it is why this module exists. Measured on
    M5-hipp3_s1 (2026-08-04), same image, same peak-finder, only the bin count
    changed:

        bins=65536 (native)  floor=39   bright=None
        bins= 4096           floor=32   bright=384   -> cut  120
        bins=  512           floor=256  bright=5632  -> cut 1600

    BraiAnDetect works at native resolution, where the near-zero background carries
    enough fine structure to offer a second "peak" (384) long before the tissue is
    reached -- it returned floor=41, bright=370, cut=123, about 14x too low, and
    detection then found 5,305 nuclei/mm^2 against 3,700-4,500 for good sections.
    At 128-wide bins those background wrinkles merge into one mode and the finder
    reaches the real nuclei peak at 5,632. The correct cut, 1600, sits against 1,721
    measured on M5b_s1 -- same acquisition regime, arrived at independently.

    So the default here is COARSE binning (DEFAULT_HIST_BINS), and callers who pass
    a finer histogram should expect BraiAn's failure mode back.

    IGNORE_BELOW is the manual defence, for when even coarse binning is not enough:
    it discards everything below a given intensity before looking, letting an
    operator say where the tissue starts. Usually unnecessary; kept because some
    histograms need a human.

    Returns (floor, bright); either may be None when no peak qualifies -- the caller
    must handle that rather than substituting a default (M5c_s3/s4 genuinely have no
    separable floor, and pretending otherwise is how a bad number gets shipped).
    """
    from scipy.signal import find_peaks as _find_peaks

    mask = edges >= ignore_below
    if mask.sum() < 3:
        return None, None
    sub_counts, sub_edges = counts[mask], edges[mask]

    if smooth_window > 1:
        kernel = np.ones(int(smooth_window)) / float(smooth_window)
        smoothed = np.convolve(sub_counts, kernel, mode="same")
    else:
        smoothed = sub_counts

    prominence = float(smoothed.max()) * float(prominence_frac)
    idx, _ = _find_peaks(smoothed, prominence=max(prominence, 1.0))
    if len(idx) == 0:
        return None, None
    if len(idx) == 1:
        # One peak only. It is the population we can see; there is no second one to
        # call "bright", and inventing one would be a fabricated number.
        return float(sub_edges[idx[0]]), None

    floor_idx = idx[0]
    higher = idx[idx > floor_idx]
    if len(higher) == 0:
        return float(sub_edges[floor_idx]), None
    # Bright = the TALLEST peak above the floor, not merely the next one. On our
    # data both choices agree (verified on M5-hipp3_s1); tallest is kept because a
    # background shoulder that survives binning would derail "next" and not this.
    bright_idx = higher[int(np.argmax(smoothed[higher]))]
    return float(sub_edges[floor_idx]), float(sub_edges[bright_idx])


def threshold_for(method: str, *, absolute: float | None = None, floor: float | None = None,
                  bright: float | None = None, span_frac: float = 0.25) -> float | None:
    """The cut, in intensity units, or None when the method cannot be evaluated."""
    if method == "absolute":
        return None if absolute is None else float(absolute)
    if method == "span_fraction":
        if floor is None or bright is None:
            return None
        return float(floor) + float(span_frac) * (float(bright) - float(floor))
    raise ValueError(f"unknown method {method!r} (expected 'absolute' or 'span_fraction')")


# ---------------------------------------------------------------------------
# What the operator is actually judging
# ---------------------------------------------------------------------------
def crop_stats(crop: np.ndarray, threshold: float, pixel_um: float | None,
               subtract_bg: bool = True) -> dict[str, Any]:
    """What fraction of the crop the cut accepts, after background subtraction.

    COVERAGE, not a nuclei count. An earlier version counted connected components in
    an area band and reported nuclei/mm^2; that was withdrawn because it does not
    model the watershed split that BraiAnDetect applies to touching nuclei, so it
    under-counted dense tissue by more than an order of magnitude and printed
    confident, wrong verdicts ("0/mm^2 VERY LOW") on perfectly good crops.

    Coverage is a real, checkable quantity, and it separates the cases we have:
    see coverage_verdict() for the measured reference values.
    """
    work = subtract_background(crop, pixel_um) if subtract_bg else crop
    mask = work > threshold
    return {
        "frac_above": float(mask.mean()),
        "bg_subtracted": bool(subtract_bg and pixel_um),
        "crop_mm2": (crop.size * float(pixel_um) ** 2 / 1e6) if pixel_um else None,
    }


# Coverage measured on real sections at their real thresholds, 2026-08-04, averaged
# over three crops each. Evidence tier <internal>: measured here, on our own images,
# not borrowed -- but only three sections, so treat it as orientation, not a gate.
COVERAGE_REFERENCE = (
    (0.759, "M5b_s1 at its real cut 1721 -> 3,637/mm^2, good"),
    (0.867, "M3-hipp2_s1 at cut 1056 -> 4,238/mm^2, good"),
    (0.984, "M5-hipp3_s1 at cut 123 -> 5,305/mm^2, OVER-DETECTED"),
)


def coverage_verdict(frac: float | None) -> str:
    """Plain-language read on a coverage fraction, with its evidence tier stated.

    Deliberately weak language. Three sections is not a band, and the project rule is
    that what the operator SEES outranks any expected number -- this line exists to
    orient the eye, never to overrule it.
    """
    if frac is None:
        return "coverage not computable"
    if frac >= 0.96:
        return (f"{frac * 100:.1f}% of pixels pass -- close to the 98.4% measured on the "
                f"section that over-detected. Look for a flooded mask. <internal>")
    if frac >= 0.90:
        return f"{frac * 100:.1f}% pass -- higher than both good sections (76%, 87%) <internal>"
    if frac >= 0.60:
        return f"{frac * 100:.1f}% pass -- in the range of the two good sections <internal>"
    if frac >= 0.25:
        return f"{frac * 100:.1f}% pass -- below both good sections; check for missed nuclei <internal>"
    return f"{frac * 100:.1f}% pass -- very restrictive; dim nuclei are probably being dropped <internal>"


# ---------------------------------------------------------------------------
# Locating a project's images
# ---------------------------------------------------------------------------
def find_mips(project_dir: Path) -> list[Path]:
    """MIP OME-TIFFs belonging to a QuPath project, newest naming first.

    Looks beside the project (the layout docs/runbook/00 builds: <session>/mips/)
    and then inside it, so this works before anything has been imported.
    """
    project_dir = Path(project_dir)
    seen: list[Path] = []
    for base in (project_dir.parent, project_dir):
        for pattern in ("mips/*.ome.tiff", "mips*/*.ome.tiff", "*.ome.tiff"):
            seen.extend(sorted(base.glob(pattern)))
    unique: list[Path] = []
    for path in seen:
        if path not in unique:
            unique.append(path)
    return unique


def slice_label(mip_path: Path) -> str:
    """Slice label from a MIP filename: M5-hipp3_s1_MIP.ome.tiff -> M5-hipp3_s1.

    This is the key `threshold_overrides` is matched on. The groovy matches by
    SUBSTRING against the QuPath entry name (`<file> - <label>`), so the bare label
    is enough and is what the operator recognises.
    """
    name = Path(mip_path).name
    for suffix in ("_MIP.ome.tiff", "_MIP.ome.tif", ".ome.tiff", ".ome.tif"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return Path(name).stem


def _config_block(method: str, threshold: float, span_frac: float,
                  scope: str, label: str) -> tuple[str, str]:
    """The YAML to paste, plus the caveat that belongs with it.

    PROJECT scope rewrites the project-wide rule and hits every section. SLICE scope
    writes a `threshold_overrides` entry, which is the right choice when one section's
    histogram breaks the rule but the rest are fine -- flipping the whole project to
    absolute would throw away self-calibration on every good section.
    """
    if scope == "slice":
        if method == "absolute":
            body = (f'threshold_overrides:\n  {label}:\n    mode: "absolute"\n'
                    f'    absolute: {int(round(threshold))}\n'
                    f'    note: "set by eye -- <say why this slice needed it>"')
        else:
            body = (f'threshold_overrides:\n  {label}:\n'
                    f'    span_frac: {span_frac:.2f}\n'
                    f'    note: "set by eye -- <say why this slice needed it>"')
        carry = ("applies to <b>this slice only</b>; every other section keeps the "
                 "project rule. The override is recorded in "
                 "<code>__detection_threshold.tsv</code>, so a later difference between "
                 "this section and the others can be traced to the threshold rather "
                 "than read as biology.")
        return body, carry

    if method == "span_fraction":
        return (f'detection_threshold:\n  mode: "span_fraction"\n'
                f'  span_frac: {span_frac:.2f}\n  absolute: null',
                "re-measured per section, so sections stay comparable")
    return (f'detection_threshold:\n  mode: "absolute"\n'
            f'  span_frac: {span_frac:.2f}\n  absolute: {int(round(threshold))}',
            "<b>applies to EVERY section</b> and does not self-calibrate. If only one "
            "section needs this, switch 'apply to' to THIS SLICE instead.")


def _load_pipeline_threshold(project_dir: Path) -> dict:
    import yaml

    path = Path(project_dir) / "pipeline.yml"
    if not path.is_file():
        return {}
    doc = yaml.safe_load(path.read_text()) or {}
    return doc.get("detection_threshold") or {}


# ---------------------------------------------------------------------------
# The widget
# ---------------------------------------------------------------------------
def launch(project: str | Path | None = None, mip: str | Path | None = None,
           anchor: str = "DAPI", n_crops: int = DEFAULT_N_CROPS,
           crop_px: int = DEFAULT_CROP_PX):
    """Build and display the interactive threshold picker. Notebook entry point.

    Returns the state dict, so a later cell can read `state["threshold"]` rather than
    the operator retyping what they just chose.
    """
    import ipywidgets as widgets
    import matplotlib
    import matplotlib.pyplot as plt
    from IPython.display import display

    matplotlib.rcParams["figure.dpi"] = 96

    if mip is None:
        if project is None:
            raise ValueError("pass project= or mip=")
        candidates = find_mips(Path(project))
        if not candidates:
            raise FileNotFoundError(
                f"no *.ome.tiff found beside or inside {project}. "
                "Run czi_mip.py first (docs/runbook/00-run-a-new-dataset.md step 3)."
            )
    else:
        candidates = [Path(mip)]

    state: dict[str, Any] = {"threshold": None, "method": "span_fraction", "mip": None}
    cache: dict[str, Any] = {}

    cfg = _load_pipeline_threshold(Path(project)) if project else {}
    cfg_span = float(cfg.get("span_frac", 0.25) or 0.25)

    mip_dd = widgets.Dropdown(options=[(p.name, p) for p in candidates], value=candidates[0],
                              description="image:", layout=widgets.Layout(width="520px"))
    method_dd = widgets.ToggleButtons(options=[("span fraction (self-calibrating)", "span_fraction"),
                                               ("absolute (set by eye)", "absolute")],
                                      value="span_fraction", description="method:")
    # Starts effectively OFF. Coarse binning already keeps the finder out of the
    # background wrinkles; forcing a floor here was actively harmful in testing --
    # ignore_below=1000 on M5-hipp3_s1 raised the floor 256 -> 1280 and the cut
    # 1600 -> 2368, and on s2 it destroyed peak-finding altogether.
    ignore_sl = widgets.FloatLogSlider(value=1.0, base=10, min=0, max=4.2, step=0.02,
                                       description="ignore below:", readout_format=".0f",
                                       layout=widgets.Layout(width="520px"))
    # min=0 so the configured value lands exactly on the step grid -- with min=0.02 a
    # configured 0.25 snapped to 0.20, silently disagreeing with pipeline.yml.
    span_sl = widgets.FloatSlider(value=cfg_span, min=0.0, max=0.9, step=0.01,
                                  description="span frac:", readout_format=".2f",
                                  layout=widgets.Layout(width="520px"))
    abs_sl = widgets.IntSlider(value=1700, min=0, max=20000, step=25, description="threshold:",
                               continuous_update=False, layout=widgets.Layout(width="520px"))
    crop_dd = widgets.Dropdown(description="crop:", layout=widgets.Layout(width="260px"))
    scope_dd = widgets.ToggleButtons(
        options=[("whole project", "project"), ("THIS SLICE only", "slice")],
        value="project", description="apply to:")
    out = widgets.Output()
    note = widgets.HTML()

    def _ensure_loaded(path: Path) -> None:
        if cache.get("path") == path:
            return
        with out:
            out.clear_output(wait=True)
            print(f"loading {path.name} ...")
        image, pixel_um, ch_name = read_anchor(path, anchor)
        counts, edges = histogram(image)
        cache.update(path=path, image=image, pixel_um=pixel_um, ch_name=ch_name,
                     counts=counts, edges=edges)
        origins = tissue_crops(image, n_crops, crop_px, ignore_below=ignore_sl.value)
        cache["origins"] = origins
        crop_dd.options = [(f"{i + 1} of {len(origins)}  (y={y}, x={x})", i)
                           for i, (y, x) in enumerate(origins)]
        crop_dd.value = 0
        state["mip"] = path

    def _redraw(*_ignored) -> None:
        path = mip_dd.value
        _ensure_loaded(path)
        image = cache["image"]
        pixel_um = cache["pixel_um"]
        counts, edges = cache["counts"], cache["edges"]

        floor, bright = find_peaks(counts, edges, ignore_below=ignore_sl.value)
        if method_dd.value == "span_fraction":
            thr = threshold_for("span_fraction", floor=floor, bright=bright, span_frac=span_sl.value)
        else:
            thr = threshold_for("absolute", absolute=abs_sl.value)

        span_sl.layout.display = "" if method_dd.value == "span_fraction" else "none"
        ignore_sl.layout.display = "" if method_dd.value == "span_fraction" else "none"
        abs_sl.layout.display = "" if method_dd.value == "absolute" else "none"

        idx = crop_dd.value or 0
        y, x = cache["origins"][min(idx, len(cache["origins"]) - 1)]
        crop = image[y:y + crop_px, x:x + crop_px]

        with out:
            out.clear_output(wait=True)
            if thr is None:
                reason = ("no peaks found above the ignore-below level"
                          if floor is None else
                          "only ONE peak found -- there is no second population to call "
                          "'bright'. This histogram cannot support the span rule; use "
                          "absolute and set it by eye.")
                print(f"  span_fraction unavailable: {reason}")
                print("  (M5c_s3/s4 failed this way too -- it is a property of the image, "
                      "not a tuning problem.)")
                return

            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            lo, hi = np.percentile(crop, [1, 99.5])
            axes[0].imshow(crop, cmap="gray", vmin=lo, vmax=max(hi, lo + 1))
            axes[0].set_title(f"{cache['ch_name']}  (y={y}, x={x})")

            work = subtract_background(crop, pixel_um, PREVIEW_BACKGROUND_RADIUS_UM)
            mask = work > thr
            overlay = np.zeros((*crop.shape, 3), dtype=float)
            norm = np.clip((crop.astype(float) - lo) / max(hi - lo, 1), 0, 1)
            overlay[..., 0] = norm
            overlay[..., 1] = norm
            overlay[..., 2] = norm
            overlay[mask] = [1.0, 0.25, 0.15]
            axes[1].imshow(overlay)
            axes[1].set_title(f"above cut = red   (cut {thr:,.0f}, background subtracted)")
            for ax in axes[:2]:
                ax.set_xticks([]); ax.set_yticks([])

            axes[2].fill_between(edges, counts, step="post", alpha=0.35, color="0.4")
            axes[2].set_yscale("log")
            axes[2].set_xlim(0, float(np.percentile(image, 99.95)) * 1.3)
            if floor is not None:
                axes[2].axvline(floor, color="tab:blue", ls="--", lw=1.5, label=f"floor {floor:,.0f}")
            if bright is not None:
                axes[2].axvline(bright, color="tab:green", ls="--", lw=1.5, label=f"bright {bright:,.0f}")
            axes[2].axvline(thr, color="tab:red", lw=2.5, label=f"cut {thr:,.0f}")
            if method_dd.value == "span_fraction":
                axes[2].axvspan(0, ignore_sl.value, color="0.85", label="ignored")
            axes[2].set_title("histogram (log y)")
            axes[2].legend(fontsize=8)
            fig.tight_layout()
            plt.show()

            stats = crop_stats(crop, thr, pixel_um)
            print(f"  cut {thr:,.0f}   {coverage_verdict(stats['frac_above'])}")
            if not stats["bg_subtracted"]:
                print("  NOTE: no pixel size in the OME-XML, so background was NOT "
                      "subtracted -- this mask is not what detection sees.")
            print("  reference, measured on real sections at their real cuts:")
            for frac, label in COVERAGE_REFERENCE:
                print(f"    {frac * 100:5.1f}%  {label}")

        state["threshold"] = float(thr)
        state["method"] = method_dd.value
        state["floor"], state["bright"] = floor, bright
        state["span_frac"] = span_sl.value
        state["ignore_below"] = ignore_sl.value

        state["scope"] = scope_dd.value
        yaml_block, carry = _config_block(method_dd.value, thr, span_sl.value,
                                          scope_dd.value, slice_label(path))
        note.value = (f"<pre style='margin:0'>{yaml_block}</pre>"
                      f"<div style='font-size:90%;color:#555'>{carry}</div>")

    for control in (mip_dd, method_dd, ignore_sl, span_sl, abs_sl, crop_dd, scope_dd):
        control.observe(_redraw, names="value")

    ui = widgets.VBox([
        widgets.HTML("<b>Threshold picker</b> &mdash; judge the red mask on the image, "
                     "not the number. What you see outranks any expected band."),
        mip_dd, method_dd, ignore_sl, span_sl, abs_sl, crop_dd, scope_dd, out,
        widgets.HTML("<b>paste into <code>&lt;project&gt;/pipeline.yml</code></b>"), note,
    ])
    display(ui)
    _redraw()
    return state


# ---------------------------------------------------------------------------
# Headless report
# ---------------------------------------------------------------------------
def print_report(project_dir: Path, anchor: str = "DAPI") -> int:
    """The same numbers the GUI shows, without widgets. Works over ssh."""
    mips = find_mips(project_dir)
    if not mips:
        print(f"no MIP OME-TIFFs found for {project_dir}")
        return 1
    cfg = _load_pipeline_threshold(project_dir)
    span_frac = float(cfg.get("span_frac", 0.25) or 0.25)
    print(f"Threshold report -- {project_dir}")
    print(f"  configured: mode={cfg.get('mode')} span_frac={span_frac} "
          f"absolute={cfg.get('absolute')}")
    for path in mips:
        image, pixel_um, ch_name = read_anchor(path, anchor)
        counts, edges = histogram(image)
        floor, bright = find_peaks(counts, edges)
        fine_counts, fine_edges = histogram(image, bins=4096)
        fine_floor, fine_bright = find_peaks(fine_counts, fine_edges)
        print(f"\n  {path.name}   channel {ch_name}  {pixel_um or float('nan'):.6g} um/px")
        print(f"    coarse bins (used here)   : floor={floor} bright={bright}")
        print(f"    fine bins (BraiAn's view) : floor={fine_floor} bright={fine_bright}")
        thr = threshold_for("span_fraction", floor=floor, bright=bright, span_frac=span_frac)
        if thr is None:
            print("    span rule UNAVAILABLE -- set it by eye (mode: absolute)")
            continue
        print(f"    span_fraction cut              : {thr:,.0f}")
        origins = tissue_crops(image, 3, DEFAULT_CROP_PX, ignore_below=floor or 0.0)
        for y, x in origins:
            stats = crop_stats(image[y:y + DEFAULT_CROP_PX, x:x + DEFAULT_CROP_PX], thr, pixel_um)
            print(f"      crop (y={y:6d}, x={x:6d}): {coverage_verdict(stats['frac_above'])}")
    return 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _synthetic_trimodal(rng: np.random.Generator, size: int = 900) -> np.ndarray:
    """An image shaped like M5-hipp3_s1: padding, empty field, then real nuclei."""
    image = np.zeros((size, size), dtype=np.uint16)
    field = rng.normal(400, 60, (size - size // 3, size)).clip(1, None)   # empty-field offset
    image[size // 3:, :] = field.astype(np.uint16)
    yy, xx = np.mgrid[0:size, 0:size]
    for _ in range(220):
        cy = int(rng.integers(size // 3 + 12, size - 12))
        cx = int(rng.integers(12, size - 12))
        image[(yy - cy) ** 2 + (xx - cx) ** 2 < 36] = np.uint16(rng.normal(6000, 400))
    return image


def _measured_histogram() -> tuple[np.ndarray, np.ndarray]:
    """The REAL M5-hipp3_s1 DAPI histogram, coarsely, as measured 2026-08-04.

    Hardcoded on purpose: this is the shape that broke the QuPath-side rule, so the
    test must keep asserting against it even if that image is deleted or re-run.
    Counts are in millions of pixels, at 128-wide bins.
    """
    profile = {0: 16.83, 128: 3.17, 256: 3.77, 384: 3.78, 512: 3.45, 640: 2.89,
               768: 2.28, 896: 1.71, 1024: 1.25, 1152: 0.90, 1280: 0.66, 1408: 0.50,
               1536: 0.41, 1664: 0.37, 1792: 0.36, 1920: 0.37, 2048: 0.38, 2176: 0.42,
               2304: 0.48, 2432: 0.54, 2560: 0.61, 2688: 0.70, 2816: 0.79, 2944: 0.89,
               3072: 0.99, 3200: 1.10, 3328: 1.21, 3456: 1.33, 3584: 1.46, 3712: 1.58,
               3840: 1.70, 3968: 1.81, 4096: 1.92, 4224: 2.03, 4352: 2.13, 4480: 2.21,
               4608: 2.28, 4736: 2.36, 4864: 2.43, 4992: 2.47, 5120: 2.50, 5248: 2.53,
               5376: 2.55, 5504: 2.56, 5632: 2.56, 5760: 2.54, 5888: 2.51, 6016: 2.49,
               6144: 2.48, 6272: 2.43, 6400: 2.38, 6528: 2.34, 6656: 2.30}
    edges = np.arange(0, 65536, 128, dtype=float)
    counts = np.zeros_like(edges)
    for lo, millions in profile.items():
        counts[lo // 128] = millions * 1e6
    tail = np.arange(6784, 20000, 128)
    for i, lo in enumerate(tail):                       # smooth decay past the mode
        counts[lo // 128] = 2.30e6 * (0.93 ** (i + 1))
    return counts, edges


def _rebin(counts: np.ndarray, edges: np.ndarray, factor: int) -> tuple[np.ndarray, np.ndarray]:
    """Split each bin into `factor` finer ones, spreading counts evenly.

    Approximates what a finer native histogram looks like to a peak finder. It cannot
    invent real sub-structure, so the test also injects the specific wrinkle BraiAn
    tripped over.
    """
    fine = np.repeat(counts / factor, factor)
    width = (edges[1] - edges[0]) / factor
    return fine, np.arange(len(fine), dtype=float) * width


def _self_test() -> None:
    print("cockpit_threshold_gui self-test")
    counts, edges = _measured_histogram()

    # (a) At the COARSE default binning the finder reaches the real nuclei peak.
    floor, bright = find_peaks(counts, edges)
    assert floor is not None and bright is not None, (floor, bright)
    assert 4500 < bright < 6500, f"expected the nuclei mode near 5632, got {bright}"
    good = threshold_for("span_fraction", floor=floor, bright=bright)
    assert 1000 < good < 2600, f"expected a cut near 1600-1800, got {good}"
    print(f"  (a) 128-wide bins -> floor={floor:.0f} bright={bright:.0f} cut={good:.0f}")
    print(f"      (M5b_s1, same acquisition regime, was independently cut at 1,721)")

    # (b) THE BUG: at fine binning a background wrinkle becomes the second "peak",
    #     and the cut collapses to roughly BraiAn's 123. Same image, same finder.
    fine_counts, fine_edges = _rebin(counts, edges, 8)
    fine_counts[3] *= 1.6                     # the empty-field wrinkle near ~48
    fine_counts[23] *= 1.9                    # the one BraiAn reported as "370"
    bad_floor, bad_bright = find_peaks(fine_counts, fine_edges, smooth_window=3)
    assert bad_bright is not None and bad_bright < 1000, (
        f"expected fine binning to pick a background peak, got {bad_bright}")
    bad = threshold_for("span_fraction", floor=bad_floor, bright=bad_bright)
    assert bad < good / 4, f"broken cut {bad} should be far below the good one {good}"
    print(f"  (b) fine bins     -> floor={bad_floor:.0f} bright={bad_bright:.0f} cut={bad:.0f}"
          f"   [BraiAn measured 41 / 370 / 123]")

    # (c) ignore_below rescues even the fine histogram -- the manual override.
    _, rescued = find_peaks(fine_counts, fine_edges, ignore_below=1000.0, smooth_window=3)
    assert rescued is not None and rescued > 4000, f"expected rescue >4000, got {rescued}"
    print(f"  (c) fine bins + ignore<1000 -> bright={rescued:.0f}   [manual override works]")

    # (d) absolute mode is literal and never consults the peaks.
    assert threshold_for("absolute", absolute=1700) == 1700.0
    assert threshold_for("absolute", absolute=1700, floor=1, bright=2) == 1700.0
    print("  (d) absolute mode is literal and peak-independent")

    # (e) A single-peak histogram must return None, not a fabricated second peak.
    flat_counts, flat_edges = histogram(np.full((200, 200), 500, dtype=np.uint16))
    _, lone = find_peaks(flat_counts, flat_edges)
    assert lone is None, f"expected no bright peak on a single-peak image, got {lone}"
    assert threshold_for("span_fraction", floor=500, bright=None) is None
    print("  (e) single-peak histogram refuses the span rule (M5c_s3/s4 case)")

    # (f) Crops land on tissue, not on the padded canvas.
    image = _synthetic_trimodal(np.random.default_rng(7))
    origins = tissue_crops(image, n_crops=4, crop_px=200, ignore_below=100.0)
    assert origins, "no crops chosen"
    for y, x in origins:
        crop = image[y:y + 200, x:x + 200]
        assert (crop > 100).mean() > 0.5, f"crop at ({y},{x}) is mostly padding"
    print(f"  (f) {len(origins)} crops chosen, all on tissue")

    # (g) The mask an operator sees really does flood at the broken cut.
    frac_bad = float((image > 123).mean())
    frac_good = float((image > 1600).mean())
    assert frac_bad > frac_good * 5, (frac_bad, frac_good)
    print(f"  (g) pixels above cut: broken {frac_bad * 100:.1f}%  vs  fixed "
          f"{frac_good * 100:.1f}%   [what the red mask shows]")

    # (h) Coverage readout: background IS subtracted, and the verdict tracks the
    #     measured reference values rather than a made-up band.
    #     The cut is deliberately set BELOW the synthetic background (~400), which is
    #     the real-data situation: on M5-hipp3_s1 tissue autofluorescence sits near
    #     5,600, far above any sane cut, so masking the raw image accepts everything.
    stats = crop_stats(image[300:812, 300:812], 200, pixel_um=0.69)
    assert stats["bg_subtracted"] is True, "preview must subtract background"
    assert 0.0 <= stats["frac_above"] <= 1.0
    raw = crop_stats(image[300:812, 300:812], 200, pixel_um=0.69, subtract_bg=False)
    assert raw["frac_above"] > 0.9, "raw background alone should clear a cut of 200"
    assert raw["frac_above"] > stats["frac_above"] * 2, (
        "subtracting background must ACCEPT FAR FEWER pixels at a cut below the "
        "background level; if not, the preview is lying about what detection sees")
    assert "over-detected" in coverage_verdict(0.984)
    assert "range of the two good sections" in coverage_verdict(0.80)
    assert coverage_verdict(None) == "coverage not computable"
    print(f"  (h) coverage readout: bg-sub {stats['frac_above'] * 100:.1f}% vs raw "
          f"{raw['frac_above'] * 100:.1f}% at the same cut")

    # (i) Per-slice override blocks: correct key, correct shape, and PROJECT scope
    #     must never emit a threshold_overrides block (or one slice's by-eye value
    #     would silently become every section's).
    assert slice_label(Path("M5-hipp3_s1_MIP.ome.tiff")) == "M5-hipp3_s1"
    assert slice_label(Path("/a/b/M5c_s3.ome.tif")) == "M5c_s3"
    blk, _ = _config_block("absolute", 1700.4, 0.25, "slice", "M5-hipp3_s1")
    assert blk.startswith("threshold_overrides:"), blk
    assert "M5-hipp3_s1:" in blk and "absolute: 1700" in blk, blk
    blk_frac, _ = _config_block("span_fraction", 1600, 0.40, "slice", "M5c_s3")
    assert "span_frac: 0.40" in blk_frac and "mode:" not in blk_frac, (
        "a span_frac-only override must not also pin mode")
    proj, carry = _config_block("absolute", 1700, 0.25, "project", "M5-hipp3_s1")
    assert "threshold_overrides" not in proj, proj
    assert "EVERY section" in carry, "project-scope absolute must warn about its reach"
    print("  (i) per-slice override blocks are well-formed and scope-correct")

    # (j) The anchor channel is matched BY NAME, never by position.
    assert anchor_channel_index(["AF568-T2", "AF488-T3", "DAPI-T4"]) == 2
    assert anchor_channel_index(["DAPI-T4", "AF488-T3"]) == 0
    assert anchor_channel_index(["red", "green"]) == 1, "fallback must be the LAST channel"
    print("  (j) anchor channel resolved by name, falls back to last")

    print("\nSELF-TEST PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--project", type=Path, default=None,
                        help="QuPath project directory to report on")
    parser.add_argument("--anchor", default="DAPI",
                        help="anchor channel name fragment (default: DAPI)")
    parser.add_argument("--self-test", action="store_true",
                        help="run the built-in self-test and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0
    if args.project is None:
        print("nothing to do: pass --project <dir> or --self-test")
        return 1
    return print_report(args.project, args.anchor)


if __name__ == "__main__":
    sys.exit(main())
