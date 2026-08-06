#!/usr/bin/env python3
"""cockpit_checks.py -- QC self-check gates for the section-pipeline cockpit.

Increment 1 of the cockpit (see .planning/quick/260728-nus-cockpit-checks-notebooks/PLAN.md).
Pure pandas over the per-slice tables already exported by
scripts/03_export_region_table.groovy -- this module is CHEAP (seconds), never
launches QuPath, and never re-runs detection. It is the "inspect" half of the
pipeline's tune -> run -> inspect loop (CLAUDE.md: tune on ONE section, then scale).

Every gate returns a `GateResult` carrying BOTH the measured number and a
"PASS"/"FLAG" verdict (`result.value`, `result.status`), so a notebook can print
the number next to the verdict rather than a bare boolean.

Which tables feed which gate (verified against the wBA1-3 fixture, 2026-07-28):

  <img> - <slice>_regions.tsv
      Image Name | Name | Classification | Area um^2 | Num Detections | Num <anchor channel>
      `Name` is the bare acronym, `Classification` is "Left: <acr>" / "Right: <acr>", and
      the counts are ALREADY hierarchically rolled up per named region by QuPath. Reading
      ONE named region's row therefore yields count and area together -- which is exactly
      how the density gates dodge the nested-annotation denominator bug. Sibling/nested
      rows are NEVER summed here (Isocortex already contains its layers; "fiber tracts"
      already contains cc and int).

  <img> - <slice>__id<N>__val01_percell_export.tsv
      class | region_label | nucleus_area_um2 | centroid_x_px | centroid_y_px | <marker>_bgsub...
      Per-cell; drives the nucleus-area histogram gate and the k-sweep stability gate.

  <img> - <slice>__atlas_cells.tsv
      NOT used for per-region work: its `region_label` column carries the detection class
      ("DAPI-T4") on every row, not an atlas region. Region work uses the two tables above.

Config is the source of truth (CLAUDE.md): the anchor channel, marker set and
exclusions are read from <project>/pipeline.yml; nothing about markers, channels
or classification thresholds is hardcoded. Classification logic is IMPORTED from
k_sweep_readout (robust median + k*1.4826*MAD cut), never reimplemented.

Usage:
    python3 cockpit_checks.py --project "<project dir>"
    python3 cockpit_checks.py --self-test
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

import k_sweep_readout as ksr  # noqa: E402  robust cut / classifiable mask -- do not fork
import cockpit_regions as creg  # noqa: E402  pipeline.yml Config loader (increment 2)


PASS = "PASS"
FLAG = "FLAG"
NA = "N/A"

# ── Gate provenance tiers (project rule: SEEN > STRUCTURAL > ASSUMED) ────────
# What the operator can see with detections overlaid outranks any number here.
# These tags say how much authority a gate's own band carries, so a violation of
# anatomy never reads the same as a deviation from a band borrowed off a paper.
#
#   ANATOMICAL -- true regardless of acquisition, stain, or microscope.
#                 Ventricles are CSF-filled; white matter is sparsely nucleated
#                 compared with cortex. Breaking one of these is real.
#   INTERNAL   -- measured from THIS dataset; checks self-consistency, asserts
#                 no outside expectation (e.g. is the readout stable across k).
#   ASSUMED    -- a band carried in from another acquisition or a paper, never
#                 validated against hand counts on our own images. Informative,
#                 NOT authoritative. A FLAG here is a prompt to go and LOOK.
ANATOMICAL = "anatomical"
INTERNAL = "internal"
ASSUMED = "assumed"


# ---------------------------------------------------------------------------
# Tunable gate thresholds -- every limit lives here, none inside a gate body
# ---------------------------------------------------------------------------
@dataclass
class GateThresholds:
    """All gate limits, in one editable place. A notebook overrides via
    `replace(DEFAULT_THRESHOLDS, white_matter_ratio_max=0.5)`."""

    # Nucleus area histogram peak (um^2).
    #
    # Lower bound widened 50.0 -> 25.0 (operator domain call, 2026-07-28). The old
    # 50-150 band came from M3, whose over-projected DAPI merged and inflated nuclei;
    # it never matched what the images actually showed. wBA's thin Z-stacks deblend
    # properly, so nuclei genuinely measure smaller -- the wBA peak of 27-32 um^2
    # (~5.9-6.4 um equivalent diameter) is real, not fragmentation. Operator reports
    # never having trusted 50-150 for this prep.
    #
    # As equivalent circular diameters: 25 um^2 ~ 5.6 um, 150 um^2 ~ 13.8 um. The floor
    # still catches genuine over-splitting -- fragmented nuclei land well below it
    # (the self-test's over-split fixture peaks at 17.5 um^2 ~ 4.7 um and still FLAGs).
    # Re-tighten if imaging moves back to thicker Z / heavier projection.
    area_peak_min: float = 25.0
    area_peak_max: float = 150.0
    area_bin_width: float = 5.0

    # ── Bands below re-derived 2026-08-05 from THE VALIDATED CORPUS ────────────
    # 16 slices the operator has accepted by eye: M3 Hipp1 s1-s7, M3 Hipp2 s1-s6,
    # M5b s1-s3. Excluded a priori, by threshold PROVENANCE and not by outcome:
    #   M5a_s1          ACQUISITION-CHECKLIST.md records it at cut 104, 5,119/mm^2
    #                   against ~3,400 for its siblings -- documented over-detection
    #   M5c_s1, M5c_s6  cut by the peak-finder at smooth_window 15, since shown to
    #                   lock onto background wrinkles below the detector offset
    # Reproduce with scratchpad/corpus.py.
    #
    # WHAT THESE BANDS ARE, EXACTLY. They are `<internal>` -- consistency with our
    # own accepted slices -- NOT correctness. They can say "this slice is unlike the
    # 16"; they cannot catch an error all 16 share, and if the corpus is systematically
    # wrong they will defend the error. Only a hand count breaks that circle, and
    # scripts/qc_handcount.py has no counts recorded for any dataset yet. Until it
    # does, no band here may be cited as evidence that a number is RIGHT.

    # White matter vs cortex. THE PREMISE WAS BACKWARDS. The old limit (0.6x, i.e.
    # "fiber tracts sit well below cortex") FLAGGED 16 OF 16 validated slices, which
    # measure 1.11-1.45, while the known-bad flooded M5a_s1 scored best of all at
    # 1.09 -- the gate was anti-correlated with the failure it was built to catch.
    # "Sparsely nucleated" is a claim about NEURONS; the anchor channel counts every
    # nucleus, and white matter is full of small, heterochromatin-dense, very bright
    # glial nuclei. Confirmed directly on M5-hipp3_s1: raising the cut from 238 to
    # 4,358 removed CORTICAL objects faster than cc ones (cc/ctx 1.13 -> 1.95 -> 2.29),
    # so the cc detections are the brightest in the section, not haze.
    # The ratio still carries information -- with the sign reversed. An EXCESSIVE
    # ratio now means the cut is too strict: cortex is dying while bright glia survive.
    white_matter_acronyms: tuple[str, ...] = ("cc", "int", "fiber tracts")
    cortex_acronyms: tuple[str, ...] = ("Isocortex",)
    white_matter_ratio_max: float = 1.60     # corpus 1.11-1.45; A060 1.95 / A075 2.29 flag
    white_matter_abs_max: float | None = None  # retired: 1500/mm^2 flagged every good
                                               # slice and duplicated total_density

    # Ventricle. CORRECTED 2026-08-06: the exclusion is NOT broken. An earlier note
    # here claimed VS "carries detections despite exclude_acronyms" -- it does not.
    # 02_detect_classify.groovy finds the VS ROIs (4 exclusion annotations per slice)
    # and the pipeline's own region_table.tsv reports VS with DAPI_count 0, correctly.
    # This gate reads the OTHER file, BraiAn's <image>_regions.tsv, which counts raw
    # detections geometrically inside each annotation BEFORE the pipeline excludes
    # them. That is the more useful number for detector QC -- it answers "is the
    # anchor cut low enough to be segmenting fluid?" and it tracks the cut cleanly
    # (M5-hipp3_s1: 2,265 flooded -> 1,046 at span_frac 0.25 -> 389 at 0.75). It is
    # NOT a claim that ventricle cells reach the counts.
    #
    # No band, still, for a different reason than previously stated: the VS ROI always
    # contains ependymal lining and absorbs registration slop, so the corpus spread is
    # 789-5,019/mm^2 -- a 6x range across slices the operator accepted. A band that
    # wide cannot discriminate. Report it; let it inform the eye.
    ventricle_acronyms: tuple[str, ...] = ("VS",)
    ventricle_density_max: float | None = None   # was 500.0 -- flagged 16/16

    # Per-region grey-matter density. Was 500-2000/mm^2, borrowed from another
    # acquisition (see commit 8939d82, which already named this band as the source of
    # a false over-segmentation narrative) and contradicted by every slice here:
    # corpus per-structure minima run 1,690-4,312 and maxima 3,689-5,775.
    grey_matter_acronyms: tuple[str, ...] = (
        "Isocortex", "CA1", "CA3", "DG", "TH", "HY", "STR", "MB",
    )
    grey_density_min: float = 1600.0
    grey_density_max: float = 5800.0

    # Grey-matter CONTRAST. New gate, and the one that encodes the flooding failure
    # mode directly: real tissue makes different structures differ (corpus CV across
    # the grey set 0.05-0.33, median 0.20), whereas a cut low enough to segment
    # background returns the same density everywhere (M5a_s1 CV 0.02; M5-hipp3_s1 at
    # cut 238 CV 0.05). Separation is real but not wide -- M3-hipp1_s1 sits at 0.05
    # with only 4 of 7 structures present -- so this is ADVISORY and reads alongside
    # total_density rather than instead of it.
    grey_cv_min: float = 0.08

    # Whole-section density -- THE PRIMARY GATE, and now blocking. The old
    # 300-8,000/mm^2 was wide enough that it never once fired. The corpus spans
    # 2,896-4,431 and this single number separates every failure on record:
    # M5a_s1 5,119 above; M5c_s1/s6 748/638 and the too-strict M5 Hipp3 candidates
    # 684-1,552 below; the flooded M5-hipp3_s1 4,897 above its own regime's siblings.
    # NOTE the band spans two acquisition regimes (M3 at 0.46 um/px x 4 Z sits high,
    # 3,566-4,431; M5 at 0.69 um/px x 2 Z sits low, 2,896-3,739). It is therefore a
    # coarse "in the family" test. Per the comparability rule, the like-for-like check
    # is against the SAME regime's siblings; narrow this band per regime once a regime
    # has enough accepted slices to derive one (M5 alone would give 2,896-3,739).
    root_classification: str = "allen_mouse_10um_java"
    total_density_min: float = 2800.0
    total_density_max: float = 4600.0

    # k-sweep stability of P(target+ | condition+).
    k_values: tuple[float, ...] = (2.0, 2.5, 3.0)
    k_swing_max_pp: float = 10.0             # percentage points

    # Gates named here still compute and still print their number, but are demoted
    # to advisory so they no longer drive the slice's overall verdict. Use this to
    # park a known issue you have consciously decided not to chase yet, instead of
    # deleting the gate (which would lose the number) or loosening its threshold
    # (which would fake a PASS). NOTE: demoting the white-matter gate means DAPI
    # DENSITIES are not trustworthy for that run -- ratio readouts such as
    # P(target+|condition+) are unaffected, as they carry no DAPI denominator.
    advisory_gates: tuple[str, ...] = ()


DEFAULT_THRESHOLDS = GateThresholds()


# ---------------------------------------------------------------------------
# Gate result
# ---------------------------------------------------------------------------
class GateResult(NamedTuple):
    """A gate's measured number plus its verdict.

    `value` is the number the gate measured (NaN when not computable) and
    `status` is PASS / FLAG / N/A -- the "(value, PASS|FLAG)" contract. `detail`
    is a short human-readable line; `advisory` marks gates that inform rather
    than block.
    """

    name: str
    value: float
    status: str
    detail: str = ""
    advisory: bool = False
    basis: str = ASSUMED

    @property
    def is_flag(self) -> bool:
        return self.status == FLAG

    def render(self) -> str:
        tag = f"{self.status}{' (advisory)' if self.advisory and self.status == FLAG else ''}"
        val = "n/a" if self.value is None or (isinstance(self.value, float)
                                              and not np.isfinite(self.value)) else f"{self.value:,.1f}"
        return (f"  [{tag:>16}] {self.name:<26} = {val:>10}  "
                f"{'<' + self.basis + '>':<12} {self.detail}")


def _verdict(ok: bool, advisory: bool = False) -> str:
    return PASS if ok else FLAG


# ---------------------------------------------------------------------------
# Config access -- pipeline.yml is the source of truth
# ---------------------------------------------------------------------------
def anchor_channel(project_dir: Path) -> str:
    """anchor.channel from pipeline.yml (e.g. 'DAPI-T4'). This is what names the
    per-region count column in regions.tsv, so it must come from config, never a
    literal."""
    doc = yaml.safe_load((Path(project_dir) / "pipeline.yml").read_text()) or {}
    anchor = doc.get("anchor") or {}
    ch = anchor.get("channel")
    if not ch:
        raise ValueError(f"{project_dir}/pipeline.yml: anchor.channel missing")
    return str(ch)


def k_robust(project_dir: Path) -> float:
    doc = yaml.safe_load((Path(project_dir) / "pipeline.yml").read_text()) or {}
    return float(doc.get("k_robust", 3.0))


def load_config(project_dir: Path) -> creg.Config:
    """Marker set / anchor name / exclusions -- reuses increment 2's loader and
    its validation rather than parsing pipeline.yml a second way."""
    return creg.load_pipeline_config(Path(project_dir))


def detection_params(project_dir: Path) -> dict:
    """The detection params the gates are judging, straight out of BraiAn.yml.
    Returned flat for display; keys absent from the file are simply omitted."""
    path = Path(project_dir) / "BraiAn.yml"
    doc = yaml.safe_load(path.read_text()) or {}
    chans = doc.get("channelDetections") or []
    if not chans:
        raise ValueError(f"{path}: channelDetections is empty")
    params = dict(chans[0].get("parameters") or {})
    out = {"channel": chans[0].get("name"), "classForDetections": doc.get("classForDetections")}
    for key in ("requestedPixelSizeMicrons", "sigmaMicrons", "minAreaMicrons",
                "maxAreaMicrons", "cellExpansionMicrons", "backgroundRadiusMicrons",
                "medianRadiusMicrons", "watershedPostProcess"):
        if key in params:
            out[key] = params[key]
    hist = params.get("histogramThreshold")
    if isinstance(hist, dict):
        for key, val in hist.items():
            out[f"histogramThreshold.{key}"] = val
    elif "threshold" in params:
        out["threshold"] = params["threshold"]
    return out


# ---------------------------------------------------------------------------
# QuPath headless plumbing (the EXPENSIVE half -- built here, run by the notebook)
# ---------------------------------------------------------------------------
# Where QuPath is installed. The default is the layout SECTION_PIPELINE_SETUP.md
# builds, under whichever home directory is running -- NOT a path with a username
# baked into it, which failed immediately on any other machine. Override with
# $QUPATH_BIN when QuPath lives elsewhere:
#     export QUPATH_BIN=/opt/QuPath/bin/QuPath
DEFAULT_QUPATH_BIN = Path.home() / "section-pipeline" / "tools" / "QuPath" / "bin" / "QuPath"
QUPATH_BIN = Path(os.environ.get("QUPATH_BIN") or DEFAULT_QUPATH_BIN)


def project_image_names(project_dir: Path) -> list[str]:
    """Image entry names from project.qpproj, in entryID order. These are the exact
    strings QuPath's `--image` expects."""
    import json
    doc = json.loads((Path(project_dir) / "project.qpproj").read_text())
    imgs = doc.get("images") or []
    return [i["imageName"] for i in sorted(imgs, key=lambda i: i.get("entryID", 0))
            if i.get("imageName")]


def qupath_command(project_dir: Path, script: str | Path, image: str | None = None,
                   save: bool = True, qupath_bin: Path = QUPATH_BIN,
                   args: list[str] | None = None) -> list[str]:
    """Build the headless QuPath invocation.

    `--image` restricts the run to ONE entry (omit it and QuPath runs the script
    over every image in the project). `--save` is required to persist detections
    back into data.qpdata -- without it a 30-minute detection pass is discarded.
    A bare script name resolves against <project>/scripts/.
    """
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = Path(project_dir) / "scripts" / script_path
    cmd = [str(qupath_bin), "script", "-p", str(Path(project_dir) / "project.qpproj")]
    if image:
        cmd += ["-i", image]
    if save:
        cmd.append("-s")
    for a in args or []:
        cmd += ["-a", a]
    cmd.append(str(script_path))
    return cmd


def shell_quote(cmd: list[str]) -> str:
    import shlex
    return " ".join(shlex.quote(c) for c in cmd)


def run_qupath(cmd: list[str], dry_run: bool = True, log_path: Path | None = None,
               timeout_s: int = 7200) -> int:
    """Run (or, by default, merely PRINT) a headless QuPath command.

    dry_run defaults to True on purpose: detection is ~30 min/slice, so the cockpit
    never launches a JVM as a side effect of running a cell. Flip it deliberately.
    Returns the exit code, or -1 when dry-run.
    """
    import subprocess
    print(("DRY RUN -- would execute:\n  " if dry_run else "RUNNING:\n  ") + shell_quote(cmd))
    if dry_run:
        return -1
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
    out = (proc.stdout or "") + (proc.stderr or "")
    if log_path:
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)
        Path(log_path).write_text(out)
        print(f"  log -> {log_path}  ({len(out.splitlines())} lines)")
    tail = out.splitlines()[-25:]
    print("  " + "\n  ".join(tail) if tail else "  (no output)")
    print(f"  exit={proc.returncode}")
    return proc.returncode


# ---------------------------------------------------------------------------
# BraiAn.yml parameter locking
# ---------------------------------------------------------------------------
def _yaml_scalar(val) -> str:
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, float) and val.is_integer():
        return f"{val:.1f}"
    return str(val)


def lock_detection_params(project_dir: Path, params: dict,
                          backup: bool = True) -> tuple[Path, Path | None]:
    """Write tuned detection params into BraiAn.yml, backing the file up first.
    Returns (braian_yml, backup_path).

    Edits values IN PLACE line by line rather than round-tripping through
    yaml.safe_dump, because BraiAn.yml carries extensive comments recording WHY each
    number is what it is (the sigmaMicrons entry alone documents the whole wBA-vs-M3
    tuning call). A dump-based rewrite would silently delete all of that; here the
    indentation and any trailing `# comment` on the edited line are preserved.

    `histogramThreshold.<key>` dotted keys address the nested block. A key that is
    missing, or that matches more than one line, raises -- a param that appears to
    lock but does not would quietly invalidate the calibrate-then-scale premise.
    Every write is verified by re-parsing the file.
    """
    import re
    from datetime import datetime

    path = Path(project_dir) / "BraiAn.yml"
    original = path.read_text()

    doc = yaml.safe_load(original) or {}
    chans = doc.get("channelDetections") or []
    if not chans:
        raise ValueError(f"{path}: channelDetections is empty")
    known = set(chans[0].get("parameters") or {})
    hist_known = set((chans[0].get("parameters") or {}).get("histogramThreshold") or {})

    for key in params:
        if key.startswith("histogramThreshold."):
            leaf = key.split(".", 1)[1]
            if leaf not in hist_known:
                raise KeyError(f"unknown histogramThreshold key '{leaf}'; "
                               f"known: {sorted(hist_known)}")
        elif key not in known:
            raise KeyError(f"unknown detection param '{key}'; known: {sorted(known)}")

    lines = original.splitlines(keepends=True)
    for key, val in params.items():
        leaf = key.split(".", 1)[1] if key.startswith("histogramThreshold.") else key
        pat = re.compile(rf"^(?P<indent>\s*){re.escape(leaf)}:(?P<gap>[ \t]*)"
                         r"(?P<val>[^#\n]*?)(?P<comment>[ \t]*#.*)?(?P<eol>\r?\n?)$")
        hits = [i for i, ln in enumerate(lines) if pat.match(ln)]
        if len(hits) != 1:
            raise KeyError(f"'{leaf}' matched {len(hits)} lines in {path} "
                           f"(need exactly 1) -- edit by hand")
        m = pat.match(lines[hits[0]])
        lines[hits[0]] = (f"{m['indent']}{leaf}:{m['gap'] or ' '}{_yaml_scalar(val)}"
                          f"{m['comment'] or ''}{m['eol'] or chr(10)}")

    updated = "".join(lines)

    # Verify BEFORE touching the real file: a bad edit must not land at all.
    check = yaml.safe_load(updated) or {}
    cparams = ((check.get("channelDetections") or [{}])[0].get("parameters") or {})
    for key, val in params.items():
        got = (cparams.get("histogramThreshold", {}).get(key.split(".", 1)[1])
               if key.startswith("histogramThreshold.") else cparams.get(key))
        if got != val and float(got if got is not None else "nan") != float(val):
            raise ValueError(f"lock verification failed for '{key}': wrote {val!r}, "
                             f"re-parsed {got!r}")

    bak = None
    if backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = path.parent / f"{path.name}.bak-{stamp}"
        bak.write_text(original)
    path.write_text(updated)
    return path, bak


# ---------------------------------------------------------------------------
# Slice discovery
# ---------------------------------------------------------------------------
@dataclass
class SliceFiles:
    label: str
    regions_tsv: Path | None = None
    percell_tsv: Path | None = None
    region_area_tsv: Path | None = None

    @property
    def complete(self) -> bool:
        return self.regions_tsv is not None and self.percell_tsv is not None


def _label_from_regions(path: Path) -> str:
    stem = path.name.split(" - ")[-1]
    return stem[: -len("_regions.tsv")] if stem.endswith("_regions.tsv") else stem


def find_slices(project_dir: Path, results_dir: Path | None = None) -> list[SliceFiles]:
    """Group the per-slice exports in <project>/results/ by slice label. A slice
    missing one of its tables is still returned (with None) so the caller can
    report it rather than silently skipping it."""
    rdir = Path(results_dir) if results_dir else Path(project_dir) / "results"
    if not rdir.is_dir():
        raise FileNotFoundError(f"results dir not found: {rdir}")

    slices: dict[str, SliceFiles] = {}

    def _slot(label: str) -> SliceFiles:
        return slices.setdefault(label, SliceFiles(label=label))

    for p in sorted(rdir.glob("*_regions.tsv")):
        _slot(_label_from_regions(p)).regions_tsv = p
    for p in sorted(rdir.glob("*percell_export.tsv")):
        _slot(ksr.section_label(p)).percell_tsv = p
    for p in sorted(rdir.glob("*region_area.tsv")):
        _slot(ksr.section_label(p)).region_area_tsv = p

    return [slices[k] for k in sorted(slices)]


def label_from_entry_name(entry_name: str) -> str:
    """Slice label from a QuPath image-entry name.

    QuPath names an imported entry `<file> - <image name>`, e.g.
    `M3-hipp2_s3_MIP.ome.tiff - M3-hipp2_s3`. The trailing part is the label the
    export tables are keyed by, so this is the inverse of the `endswith(label)`
    match callers use to go from a slice back to its `--image` argument.
    """
    return entry_name.rsplit(" - ", 1)[-1].strip() if " - " in entry_name else entry_name.strip()


def find_candidate_slices(project_dir: Path,
                          results_dir: Path | None = None) -> tuple[list[SliceFiles], bool]:
    """Slices available to work on, whether or not anything has been exported yet.

    `find_slices` groups EXPORT tables, so on a brand-new project it finds nothing --
    which made the calibrate notebook circular: you could not pick a slice to detect
    on until a detection had already been exported for it. Here the QuPath project's
    own image entries are the fallback, so a fresh project can be calibrated.

    Returns (slices, from_exports). `from_exports` is False when the list came from
    project entries, i.e. the SliceFiles carry no tables yet and any gate needing
    per-cell data will (correctly) report N/A rather than crash.
    """
    try:
        exported = find_slices(project_dir, results_dir)
    except FileNotFoundError:
        exported = []
    if exported:
        return exported, True
    return [SliceFiles(label=label_from_entry_name(n))
            for n in project_image_names(project_dir)], False


# ---------------------------------------------------------------------------
# Table loading
# ---------------------------------------------------------------------------
def region_table_status(project_dir: Path, results_dir: Path | None = None) -> dict:
    """Report whether the consolidated `*__region_table.tsv` exports that
    cockpit_regions.build_readout() consumes are present.

    Older projects were exported before 03_export_region_table.groovy was
    consolidated and carry only `*__region_area.tsv`, which holds areas but NO
    per-category counts -- it is not a substitute. Rather than let build_readout
    raise deep inside a notebook cell, callers check this first and surface the
    exact re-export command.
    """
    rdir = Path(results_dir) if results_dir else Path(project_dir) / "results"
    tables = sorted(rdir.glob("*__region_table.tsv")) if rdir.is_dir() else []
    areas = sorted(rdir.glob("*region_area.tsv")) if rdir.is_dir() else []
    return {
        "ready": bool(tables),
        "region_tables": tables,
        "region_area_only": bool(areas) and not tables,
        "hint": ("" if tables else
                 "No *__region_table.tsv found"
                 + (" (only the older *__region_area.tsv, which has areas but no counts)"
                    if areas else "")
                 + ". Re-export with 03_export_region_table.groovy: "
                 + shell_quote(qupath_command(project_dir, "03_export_region_table.groovy"))),
    }


def load_regions_tsv(path: Path, anchor_ch: str) -> pd.DataFrame:
    """Normalise regions.tsv into: acronym, hemisphere, classification, area_mm2,
    count, density (per mm^2). One row per (region, hemisphere) exactly as QuPath
    exported it -- no aggregation happens here."""
    df = pd.read_csv(path, sep="\t")

    count_col = f"Num {anchor_ch}"
    if count_col not in df.columns:
        if "Num Detections" not in df.columns:
            raise ValueError(
                f"{path}: neither '{count_col}' nor 'Num Detections' present. "
                f"Columns: {list(df.columns)}")
        count_col = "Num Detections"

    area_col = "Area um^2"
    if area_col not in df.columns:
        raise ValueError(f"{path}: '{area_col}' column missing. Columns: {list(df.columns)}")

    out = pd.DataFrame({
        "acronym": df["Name"].astype(str).str.strip(),
        "classification": df["Classification"].astype(str).fillna(""),
        "area_mm2": pd.to_numeric(df[area_col], errors="coerce") / 1e6,
        "count": pd.to_numeric(df[count_col], errors="coerce"),
    })
    out["hemisphere"] = out["classification"].map(
        lambda s: s.split(": ")[0] if ": " in s else "")
    out["density"] = np.where(out["area_mm2"] > 0, out["count"] / out["area_mm2"], np.nan)
    return out


def load_percell_for_slice(sl: SliceFiles) -> pd.DataFrame:
    if sl.percell_tsv is None:
        raise FileNotFoundError(f"slice {sl.label}: no percell_export.tsv")
    return ksr.load_percell(sl.percell_tsv)


def region_density(regions_df: pd.DataFrame, acronym: str) -> tuple[float, float, float]:
    """(count, area_mm2, density) for ONE named region, pooling its Left and Right
    rows. Pooling two hemispheres of the SAME region is safe; summing different
    regions is not, and this function deliberately cannot do it."""
    sel = regions_df[regions_df["acronym"] == acronym]
    if sel.empty:
        return (np.nan, np.nan, np.nan)
    count = float(sel["count"].sum())
    area = float(sel["area_mm2"].sum())
    return (count, area, count / area if area > 0 else np.nan)


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------
def gate_nucleus_area_peak(percell: pd.DataFrame,
                           th: GateThresholds = DEFAULT_THRESHOLDS) -> GateResult:
    """Modal nucleus area must land in the expected band. A peak below
    area_peak_min means over-splitting or noise being segmented as nuclei."""
    name = "nucleus_area_peak_um2"
    col = "nucleus_area_um2"
    if col not in percell.columns:
        return GateResult(name, float("nan"), NA, f"no '{col}' column")

    areas = pd.to_numeric(percell[col], errors="coerce")
    areas = areas[np.isfinite(areas) & (areas > 0)]
    if areas.empty:
        return GateResult(name, float("nan"), NA, "no finite nucleus areas")

    hi = float(min(areas.max(), th.area_peak_max * 4))
    edges = np.arange(0.0, hi + th.area_bin_width, th.area_bin_width)
    if edges.size < 2:
        return GateResult(name, float("nan"), NA, "area range too narrow to bin")
    counts, _ = np.histogram(areas, bins=edges)
    peak = float((edges[int(counts.argmax())] + edges[int(counts.argmax()) + 1]) / 2.0)

    ok = th.area_peak_min <= peak <= th.area_peak_max
    detail = (f"modal bin of {len(areas):,} nuclei; expect "
              f"{th.area_peak_min:g}-{th.area_peak_max:g} um^2"
              + ("" if ok else "  <-- over-splitting / noise" if peak < th.area_peak_min
                 else "  <-- under-splitting / merged nuclei"))
    return GateResult(name, peak, _verdict(ok), detail, basis=ASSUMED)


def gate_white_matter(regions: pd.DataFrame,
                      th: GateThresholds = DEFAULT_THRESHOLDS) -> GateResult:
    """White matter carried relative to cortex. REINTERPRETED 2026-08-05 -- read the
    GateThresholds comment before using this number.

    This gate used to assert that fiber tracts sit BELOW cortex (0.6x) and blamed
    "DAPI haze" when they did not. That premise is wrong for a pan-nuclear anchor:
    every one of the 16 validated slices runs 1.11-1.45, and the known-bad flooded
    slice scored the LOWEST of all. White matter is densely populated by small, bright
    glial nuclei.

    What the ratio does track is the cut being too STRICT: as the anchor threshold
    rises, dim cortical nuclei drop out before bright glial ones, so the ratio climbs.
    A value above the corpus range is therefore a hint to LOWER the cut, the opposite
    of what the old message said.

    Each white-matter region is measured independently and the WORST is reported --
    'fiber tracts' already contains cc and int, so summing them would double-count.
    """
    name = "white_matter_density"

    cortex_d = [region_density(regions, a)[2] for a in th.cortex_acronyms]
    cortex_d = [d for d in cortex_d if np.isfinite(d)]
    cortex = float(np.mean(cortex_d)) if cortex_d else float("nan")

    worst_acr, worst = None, float("-inf")
    for acr in th.white_matter_acronyms:
        _c, _a, d = region_density(regions, acr)
        if np.isfinite(d) and d > worst:
            worst_acr, worst = acr, d
    if worst_acr is None:
        return GateResult(name, float("nan"), NA,
                          f"none of {list(th.white_matter_acronyms)} present")

    over_abs = (th.white_matter_abs_max is not None and worst > th.white_matter_abs_max)
    over_rel = np.isfinite(cortex) and cortex > 0 and worst > th.white_matter_ratio_max * cortex
    ok = not (over_abs or over_rel)

    ratio = worst / cortex if np.isfinite(cortex) and cortex > 0 else float("nan")
    why = []
    if over_rel:
        why.append(f"{ratio:.2f}x cortex > {th.white_matter_ratio_max:g}x "
                   f"(corpus 1.11-1.45); anchor cut likely TOO STRICT -- dim cortical "
                   f"nuclei are dropping out while bright glial ones survive")
    if over_abs:
        why.append(f"> {th.white_matter_abs_max:g}/mm^2")
    detail = (f"worst='{worst_acr}' {worst:,.0f}/mm^2 vs cortex {cortex:,.0f}/mm^2 "
              f"(ratio {ratio:.2f})"
              + ("" if ok else "  <-- " + "; ".join(why)))
    return GateResult(name, worst, _verdict(ok), detail, basis=INTERNAL)


def gate_ventricle(regions: pd.DataFrame,
                   th: GateThresholds = DEFAULT_THRESHOLDS) -> GateResult:
    """Ventricular systems are fluid-filled and should be near-empty.

    REPORT-ONLY while `ventricle_density_max` is None. The premise is structural and
    still believed; the measurement is not usable as a test, because VS is named in
    pipeline.yml `exclude_acronyms` and nevertheless carries 789-5,019/mm^2 on all 16
    validated slices. Something upstream -- the exclusion not taking effect, ependymal
    lining inside the ROI, registration slop, or all three -- has to be fixed before a
    number here means anything. Setting a band now would turn that defect into an
    expectation.
    """
    name = "ventricle_density"
    worst_acr, worst = None, float("-inf")
    for acr in th.ventricle_acronyms:
        _c, _a, d = region_density(regions, acr)
        if np.isfinite(d) and d > worst:
            worst_acr, worst = acr, d
    if worst_acr is None:
        return GateResult(name, float("nan"), NA,
                          f"none of {list(th.ventricle_acronyms)} present")
    if th.ventricle_density_max is None:
        return GateResult(name, worst, NA,
                          f"'{worst_acr}' {worst:,.0f}/mm^2 RAW detections inside the "
                          f"ROI, before pipeline exclusion (the region table correctly "
                          f"reports VS at 0). Reported, not tested: corpus spans "
                          f"789-5,019/mm^2, too wide to discriminate. Tracks the anchor "
                          f"cut -- falling means a stricter cut.",
                          advisory=True, basis=ANATOMICAL)
    ok = worst <= th.ventricle_density_max
    detail = (f"'{worst_acr}'; expect <= {th.ventricle_density_max:g}/mm^2"
              + ("" if ok else "  <-- detections inside ventricle"))
    return GateResult(name, worst, _verdict(ok), detail, basis=ANATOMICAL)


def gate_grey_matter_density(regions: pd.DataFrame,
                             th: GateThresholds = DEFAULT_THRESHOLDS) -> GateResult:
    """Advisory. Each named grey region is measured on its OWN row (count and area
    from the same hierarchical rollup) -- never a sum of nested annotations, which
    would inflate the denominator. Reports the median density across the regions
    present and how many fall inside the plausible band."""
    name = "grey_density_median"
    per: list[tuple[str, float]] = []
    for acr in th.grey_matter_acronyms:
        _c, _a, d = region_density(regions, acr)
        if np.isfinite(d):
            per.append((acr, d))
    if not per:
        return GateResult(name, float("nan"), NA, "no reference grey regions present",
                          advisory=True)

    vals = np.array([d for _a, d in per], dtype=float)
    median = float(np.median(vals))
    in_band = int(((vals >= th.grey_density_min) & (vals <= th.grey_density_max)).sum())
    ok = th.grey_density_min <= median <= th.grey_density_max
    detail = (f"{in_band}/{len(per)} regions inside "
              f"{th.grey_density_min:g}-{th.grey_density_max:g}/mm^2 "
              f"({', '.join(f'{a} {d:,.0f}' for a, d in per)})")
    return GateResult(name, median, _verdict(ok), detail, advisory=True, basis=INTERNAL)


def gate_grey_contrast(regions: pd.DataFrame,
                       th: GateThresholds = DEFAULT_THRESHOLDS) -> GateResult:
    """Advisory. Do different grey structures come out at different densities?

    Real tissue does: the corpus spreads 0.05-0.33 (CV across the grey set, median
    0.20). A cut low enough to segment background returns the SAME density everywhere,
    because what is being counted is no longer cells -- the flooded M5a_s1 sits at 0.02
    and M5-hipp3_s1 at cut 238 sat at 0.05 while reading ~5,000/mm^2 in every region
    including white matter.

    Advisory, not blocking: the separation is real but narrow at the low end, since a
    slice carrying only a few of the reference structures can score low honestly
    (M3-hipp1_s1 is 0.05 with 4 of 7 present). Read it next to total_density, which
    catches the same failure with more margin.
    """
    name = "grey_contrast_cv"
    vals = np.array([d for acr in th.grey_matter_acronyms
                     for d in (region_density(regions, acr)[2],) if np.isfinite(d)])
    if vals.size < 3:
        return GateResult(name, float("nan"), NA,
                          f"only {vals.size} reference grey regions present; need 3",
                          advisory=True, basis=INTERNAL)
    cv = float(vals.std() / vals.mean()) if vals.mean() > 0 else float("nan")
    ok = cv >= th.grey_cv_min
    detail = (f"CV {cv:.2f} across {vals.size} grey structures "
              f"(corpus 0.05-0.33, median 0.20; flooded M5a_s1 0.02)"
              + ("" if ok else "  <-- structures are indistinguishable; the anchor cut "
                               "is likely segmenting background, not nuclei"))
    return GateResult(name, cv, _verdict(ok), detail, advisory=True, basis=INTERNAL)


def gate_total_count(regions: pd.DataFrame,
                     th: GateThresholds = DEFAULT_THRESHOLDS) -> GateResult:
    """THE PRIMARY GATE, and the only blocking one that has ever discriminated on this
    machine. Detections per registered mm^2 across the whole section, taken from the
    SINGLE root row so nested annotations are never double-counted.

    Promoted from advisory 2026-08-05. Its old 300-8,000/mm^2 band never fired once;
    the corpus band 2,800-4,600 separates every failure on record -- over-detection
    above (M5a_s1 5,119, M5-hipp3_s1-at-cut-238 4,897) and under-detection below
    (M5c_s1/s6 748/638, the too-strict M5 Hipp3 candidates 684-1,552).

    It is `<internal>`: it asks whether this slice looks like our 16 accepted ones, not
    whether either is right. And it spans two acquisition regimes, so it is coarse --
    see the GateThresholds comment.
    """
    name = "total_density"
    root = regions[regions["classification"].str.strip() == th.root_classification]
    if root.empty:
        root = regions[regions["acronym"].str.lower() == "root"]
    if root.empty:
        return GateResult(name, float("nan"), NA, "no root row found", advisory=True)

    count = float(root["count"].sum())
    area = float(root["area_mm2"].sum())
    if not area > 0:
        return GateResult(name, float("nan"), NA, "root area is zero", advisory=True)
    dens = count / area
    ok = th.total_density_min <= dens <= th.total_density_max
    which = "" if ok else ("  <-- ABOVE corpus; cut likely too low"
                           if dens > th.total_density_max
                           else "  <-- BELOW corpus; cut likely too high")
    detail = (f"{count:,.0f} detections over {area:,.1f} mm^2 registered; corpus "
              f"{th.total_density_min:g}-{th.total_density_max:g}/mm^2 "
              f"(16 validated slices)" + which)
    return GateResult(name, dens, _verdict(ok), detail, basis=INTERNAL)


# --- k-sweep stability -------------------------------------------------------
def resolve_marker_tokens(percell: pd.DataFrame, config: creg.Config) -> dict[str, str]:
    """Map each pipeline.yml marker NAME to the token actually used in the export's
    '<token>_bgsub' column, matching case-insensitively.

    The exports write lowercase columns ('fos_bgsub', 'tdt_bgsub') while pipeline.yml
    declares display names ('Fos', 'TdT'), so an exact-match lookup silently finds
    nothing and every marker-dependent gate degrades to N/A. Markers with no matching
    column are simply absent from the result.
    """
    by_lower = {c[: -len("_bgsub")].lower(): c[: -len("_bgsub")]
                for c in percell.columns if c.endswith("_bgsub")}
    return {name: by_lower[name.lower()] for name in config.marker_names
            if name.lower() in by_lower}


def conditional_positive_rate(percell: pd.DataFrame, target: str, condition: str,
                              k: float) -> tuple[float, int, int]:
    """P(target+ | condition+) at robust multiplier k, plus (numerator, denominator).

    The cut is k_sweep_readout's: threshold = median + k * 1.4826 * MAD, derived per
    marker on that marker's own classifiable population (class != 'Excluded' and a
    finite <marker>_bgsub). Both markers are then evaluated on the rows classifiable
    for BOTH, so the conditional is a genuine joint statistic.
    """
    tcol, ccol = f"{target}_bgsub", f"{condition}_bgsub"
    if tcol not in percell.columns or ccol not in percell.columns:
        return (float("nan"), 0, 0)

    t_thr = ksr.robust_threshold(
        percell.loc[ksr.classifiable_mask(percell, target), tcol].to_numpy(float), k)
    c_thr = ksr.robust_threshold(
        percell.loc[ksr.classifiable_mask(percell, condition), ccol].to_numpy(float), k)

    both = ksr.classifiable_mask(percell, target) & ksr.classifiable_mask(percell, condition)
    sub = percell.loc[both]
    if sub.empty:
        return (float("nan"), 0, 0)

    cond_pos = sub[ccol].to_numpy(float) >= c_thr
    targ_pos = sub[tcol].to_numpy(float) >= t_thr
    denom = int(cond_pos.sum())
    numer = int((cond_pos & targ_pos).sum())
    return ((numer / denom if denom else float("nan")), numer, denom)


def gate_k_stability(percell: pd.DataFrame, config: creg.Config,
                     th: GateThresholds = DEFAULT_THRESHOLDS,
                     target: str | None = None,
                     condition: str | None = None) -> GateResult:
    """P(target+ | condition+) must not swing wildly with the robust multiplier k.
    A big swing means the classification cut is sitting on a slope rather than in a
    valley, and the readout would be an artefact of k.

    With fewer than two markers declared (e.g. a TdT-only slice-set) the conditional
    does not exist; the gate reports N/A rather than failing.
    """
    name = "k_swing_pp"
    tokens = resolve_marker_tokens(percell, config)
    present = list(tokens)
    if len(present) < 2:
        return GateResult(name, float("nan"), NA,
                          f"needs 2 markers, have {present or 'none'} -- conditional undefined")

    target = target or present[0]
    condition = condition or present[1]
    t_tok, c_tok = tokens.get(target, target), tokens.get(condition, condition)

    rates = {k: conditional_positive_rate(percell, t_tok, c_tok, k)[0]
             for k in th.k_values}
    finite = [r for r in rates.values() if np.isfinite(r)]
    if not finite:
        return GateResult(name, float("nan"), NA, f"no {condition}+ cells at any k")

    swing_pp = (max(finite) - min(finite)) * 100.0
    ok = swing_pp <= th.k_swing_max_pp
    shown = ", ".join(f"k={k:g}:{rates[k]*100:.1f}%" if np.isfinite(rates[k]) else f"k={k:g}:n/a"
                      for k in th.k_values)
    detail = (f"P({target}+|{condition}+) [{shown}]; max swing "
              f"{th.k_swing_max_pp:g} pp" + ("" if ok else "  <-- cut is unstable"))
    return GateResult(name, swing_pp, _verdict(ok), detail, basis=INTERNAL)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run_all_gates(sl: SliceFiles, project_dir: Path,
                  th: GateThresholds = DEFAULT_THRESHOLDS,
                  config: creg.Config | None = None,
                  anchor_ch: str | None = None) -> list[GateResult]:
    """Every gate for ONE slice. Missing tables degrade to N/A results instead of
    raising, so one bad slice never takes down a batch summary."""
    config = config or load_config(project_dir)
    anchor_ch = anchor_ch or anchor_channel(project_dir)
    results: list[GateResult] = []

    if sl.percell_tsv is not None:
        percell = load_percell_for_slice(sl)
        results.append(gate_nucleus_area_peak(percell, th))
        results.append(gate_k_stability(percell, config, th))
    else:
        results.append(GateResult("nucleus_area_peak_um2", float("nan"), NA, "no percell export"))
        results.append(GateResult("k_swing_pp", float("nan"), NA, "no percell export"))

    if sl.regions_tsv is not None:
        regions = load_regions_tsv(sl.regions_tsv, anchor_ch)
        results.append(gate_white_matter(regions, th))
        results.append(gate_ventricle(regions, th))
        results.append(gate_grey_matter_density(regions, th))
        results.append(gate_grey_contrast(regions, th))
        results.append(gate_total_count(regions, th))
    else:
        for nm, adv in (("white_matter_density", False), ("ventricle_density", False),
                        ("grey_density_median", True), ("total_density", True)):
            results.append(GateResult(nm, float("nan"), NA, "no regions.tsv", advisory=adv))

    if th.advisory_gates:
        results = [r._replace(advisory=True, detail=(r.detail + "  [demoted to advisory]").strip())
                   if r.name in th.advisory_gates and not r.advisory else r
                   for r in results]

    return results


def print_gates(sl_label: str, results: list[GateResult]) -> None:
    blocking = [r for r in results if r.is_flag and not r.advisory]
    verdict = "FLAG" if blocking else "PASS"
    print(f"\n{sl_label}  ->  {verdict}"
          + (f"  ({len(blocking)} blocking gate(s) flagged)" if blocking else ""))
    for r in results:
        print(r.render())


def gate_table(project_dir: Path, th: GateThresholds = DEFAULT_THRESHOLDS,
               results_dir: Path | None = None) -> pd.DataFrame:
    """One PASS/FLAG row per slice -- the batch notebook's QC summary table.
    Advisory gates contribute their value and status but never decide `overall`.
    """
    project_dir = Path(project_dir)
    config = load_config(project_dir)
    anchor_ch = anchor_channel(project_dir)

    rows = []
    for sl in find_slices(project_dir, results_dir):
        results = run_all_gates(sl, project_dir, th, config, anchor_ch)
        row: dict[str, object] = {"slice": sl.label}
        blocking_flags = []
        for r in results:
            row[r.name] = r.value
            row[f"{r.name}__status"] = r.status
            if r.is_flag and not r.advisory:
                blocking_flags.append(r.name)
        row["overall"] = FLAG if blocking_flags else PASS
        row["flagged"] = ", ".join(blocking_flags)
        rows.append(row)

    if not rows:
        return pd.DataFrame(columns=["slice", "overall", "flagged"])
    return pd.DataFrame(rows)


def summary_view(table: pd.DataFrame) -> pd.DataFrame:
    """Compact value+status view of gate_table for display: one column per gate
    rendered as 'value (STATUS)'."""
    if table.empty:
        return table
    out = pd.DataFrame({"slice": table["slice"]})
    for col in table.columns:
        if col in ("slice", "overall", "flagged") or col.endswith("__status"):
            continue
        status = table.get(f"{col}__status")
        out[col] = [
            ("n/a" if not np.isfinite(v) else f"{v:,.1f}") + f" ({s})"
            for v, s in zip(table[col], status)
        ]
    out["overall"] = table["overall"]
    return out


# ---------------------------------------------------------------------------
# Self-test on synthetic data (no fixture required)
# ---------------------------------------------------------------------------
def _write_synthetic_project(base: Path, two_marker: bool = True) -> Path:
    """A minimal project whose numbers are engineered so each gate's PASS and FLAG
    branch can both be exercised."""
    proj = base / "synthetic_project"
    (proj / "results").mkdir(parents=True, exist_ok=True)

    markers = [{"name": "Fos", "channel": "AF488-T3", "compartment": "nuclear"}]
    if two_marker:
        markers.append({"name": "TdT", "channel": "AF568-T2", "compartment": "whole-cell"})
    (proj / "pipeline.yml").write_text(yaml.safe_dump({
        "anchor": {"name": "DAPI", "channel": "DAPI-T4"},
        "markers": markers,
        "exclude_acronyms": ["DG-sg", "VS"],
        "k_robust": 3.0,
        "ring": {"gap_um": 1.0, "width_um": 8.0},
    }, sort_keys=False))
    (proj / "BraiAn.yml").write_text(yaml.safe_dump({
        "classForDetections": "allen_mouse_10um_java",
        "channelDetections": [{
            "name": "DAPI-T4",
            "parameters": {
                "requestedPixelSizeMicrons": 0.69,
                "sigmaMicrons": 2.0,
                "minAreaMicrons": 20.0,
                "maxAreaMicrons": 250.0,
                "cellExpansionMicrons": 5.0,
                "histogramThreshold": {"resolutionLevel": 0, "nPeak": 2},
            },
        }],
    }, sort_keys=False))

    rng = np.random.default_rng(7)

    def _regions(good: bool) -> pd.DataFrame:
        # density = count / (area_um2 / 1e6)
        #
        # Numbers rebuilt 2026-08-05 against the re-derived corpus bands. The clean
        # slice sits mid-corpus (3,500/mm^2 total, grey structures spread 2,000-4,500,
        # cc at 1.25x cortex like every real slice). The degraded slice models the
        # failure the OLD fixture could not express -- an anchor cut that is too
        # STRICT: total density collapses below the corpus, grey falls under the band,
        # and white matter climbs to 3x cortex because dim cortical nuclei die while
        # bright glial ones survive. (The flooding mode is covered separately by the
        # gate_grey_contrast check in the self-test, which needs a flat frame.)
        spec = [
            ("Root", "allen_mouse_10um_java", 40e6, 140_000 if good else 48_000),
            ("Isocortex", "Left: Isocortex", 7e6, 24_500 if good else 7_000),
            ("Isocortex", "Right: Isocortex", 7e6, 24_500 if good else 7_000),
            ("CA1", "Left: CA1", 0.7e6, 1_540 if good else 630),
            ("CA3", "Left: CA3", 0.5e6, 1_000 if good else 400),
            ("DG", "Left: DG", 0.5e6, 1_400 if good else 500),
            ("TH", "Left: TH", 2e6, 9_000 if good else 2_400),
            ("cc", "Left: cc", 1.0e6, 4_375 if good else 3_000),   # 1.25x vs 3.0x cortex
            ("int", "Left: int", 0.4e6, 1_600 if good else 900),
            ("fiber tracts", "Left: fiber tracts", 2.0e6, 8_400 if good else 4_000),
            ("VS", "Left: VS", 0.7e6, 1_000 if good else 1_400),   # report-only now
        ]
        return pd.DataFrame([{
            "Image Name": "syn", "Name": n, "Classification": c,
            "Area um^2": a, "Num Detections": k, "Num DAPI-T4": k,
        } for n, c, a, k in spec])

    def _percell(good: bool, n: int = 4000) -> pd.DataFrame:
        area = rng.normal(80 if good else 20, 10, n).clip(5, None)
        cols = {
            "class": ["Negative"] * n,
            "region_label": rng.choice(["CA1", "Isocortex", "TH"], n),
            "nucleus_area_um2": area,
            "centroid_x_px": rng.uniform(0, 1000, n),
            "centroid_y_px": rng.uniform(0, 1000, n),
        }
        # Clean bimodal signal -> a stable cut across k. Both markers positive on
        # the SAME 12% of cells, so P(Fos+|TdT+) is high and barely k-dependent.
        # NOTE: columns are LOWERCASE ('fos_bgsub') exactly as the real exports write
        # them, while pipeline.yml declares 'Fos'/'TdT' -- this mismatch is what
        # resolve_marker_tokens() exists to bridge, so the fixture must reproduce it.
        for marker in ("Fos", "TdT") if two_marker else ("Fos",):
            cols[f"{marker.lower()}_bgsub"] = rng.normal(100, 10, n)
        if two_marker:
            hot = rng.random(n) < 0.12
            cols["fos_bgsub"] = np.where(hot, rng.normal(900, 20, n), cols["fos_bgsub"])
            cols["tdt_bgsub"] = np.where(hot, rng.normal(900, 20, n), cols["tdt_bgsub"])
        return pd.DataFrame(cols)

    for label, good in (("syn_s1", True), ("syn_s2", False)):
        stem = f"syn.ome.tiff - {label}"
        _regions(good).to_csv(proj / "results" / f"{stem}_regions.tsv", sep="\t", index=False)
        _percell(good).to_csv(proj / "results" / f"{stem}__id1__val01_percell_export.tsv",
                              sep="\t", index=False)
    return proj


def _self_test() -> None:
    import tempfile

    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(f"  {'ok  ' if cond else 'FAIL'}  {msg}")
        if not cond:
            failures.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)

        print("\n[1] two-marker project")
        proj = _write_synthetic_project(base, two_marker=True)

        check(anchor_channel(proj) == "DAPI-T4", "anchor.channel read from pipeline.yml")
        cfg = load_config(proj)
        check(cfg.marker_names == ["Fos", "TdT"], "marker set read from pipeline.yml")
        check(cfg.emit_double, "Double+ emitted with 2 markers")
        dp = detection_params(proj)
        check(dp.get("sigmaMicrons") == 2.0, "sigmaMicrons read from BraiAn.yml")
        check(dp.get("histogramThreshold.nPeak") == 2, "histogramThreshold flattened")

        slices = find_slices(proj)
        check([s.label for s in slices] == ["syn_s1", "syn_s2"], "find_slices groups by label")
        check(all(s.complete for s in slices), "both synthetic slices complete")

        # find_candidate_slices: a project WITH exports is unchanged; a FRESH project
        # (no results/ at all) still yields its entries, which is what makes the
        # calibrate notebook runnable before anything has been detected.
        cand, from_exports = find_candidate_slices(proj)
        check([s.label for s in cand] == ["syn_s1", "syn_s2"] and from_exports,
              "find_candidate_slices prefers exports when they exist")
        check(label_from_entry_name("M3-hipp2_s3_MIP.ome.tiff - M3-hipp2_s3") == "M3-hipp2_s3",
              "label_from_entry_name strips the QuPath '<file> - <name>' prefix")
        check(label_from_entry_name("no_separator_name") == "no_separator_name",
              "label_from_entry_name passes through a name with no separator")
        import json as _json
        with tempfile.TemporaryDirectory() as fresh_dir:
            fresh = Path(fresh_dir)
            (fresh / "project.qpproj").write_text(_json.dumps({"images": [
                {"entryID": 1, "imageName": "a_MIP.ome.tiff - a_s1"},
                {"entryID": 2, "imageName": "b_MIP.ome.tiff - b_s2"},
            ]}))
            fresh_slices, fresh_from_exports = find_candidate_slices(fresh)
            check([s.label for s in fresh_slices] == ["a_s1", "b_s2"] and not fresh_from_exports,
                  "find_candidate_slices falls back to project entries on a fresh project")
            check(all(s.percell_tsv is None for s in fresh_slices),
                  "fallback slices carry no tables (gates report N/A rather than crash)")

        good, bad = slices[0], slices[1]

        regions_good = load_regions_tsv(good.regions_tsv, "DAPI-T4")
        _c, _a, d = region_density(regions_good, "Isocortex")
        check(abs(d - 3500.0) < 1e-6, f"region_density pools hemispheres (Isocortex {d:.0f}/mm^2)")

        print("\n[2] gates -- clean slice should PASS")
        for r in run_all_gates(good, proj):
            print(r.render())
        res_good = {r.name: r for r in run_all_gates(good, proj)}
        check(res_good["nucleus_area_peak_um2"].status == PASS, "area peak PASS on clean slice")
        check(res_good["white_matter_density"].status == PASS, "white matter PASS on clean slice")
        check(res_good["total_density"].status == PASS, "total density inside corpus band")
        check(res_good["grey_contrast_cv"].status == PASS, "grey structures differ on clean slice")
        check(res_good["ventricle_density"].status == NA
              and res_good["ventricle_density"].advisory,
              "ventricle is report-only while its measurement is confounded")
        check(res_good["k_swing_pp"].status == PASS, "k-sweep stable on clean bimodal signal")

        toks = resolve_marker_tokens(load_percell_for_slice(good), cfg)
        check(toks == {"Fos": "fos", "TdT": "tdt"},
              f"marker names resolve case-insensitively to export columns ({toks})")

        print("\n[3] gates -- degraded slice should FLAG")
        for r in run_all_gates(bad, proj):
            print(r.render())
        res_bad = {r.name: r for r in run_all_gates(bad, proj)}
        check(res_bad["nucleus_area_peak_um2"].status == FLAG, "area peak FLAG when over-split")
        check(res_bad["white_matter_density"].status == FLAG,
              "white matter FLAG when the cut is too strict (3x cortex)")
        check(res_bad["total_density"].status == FLAG, "total density FLAG below corpus")
        check("too high" in res_bad["total_density"].detail,
              "total density says WHICH WAY the cut is wrong")
        # The ventricle band is retired, not deleted: setting one re-arms the gate.
        armed = replace(DEFAULT_THRESHOLDS, ventricle_density_max=500.0)
        r_v = gate_ventricle(load_regions_tsv(bad.regions_tsv, "DAPI-T4"), armed)
        check(r_v.status == FLAG, "ventricle FLAGs again once a band is set")

        # Flooding is the other failure mode, and needs a frame where every structure
        # reads the same -- the shape M5a_s1 and M5-hipp3_s1-at-238 both had.
        flat = load_regions_tsv(good.regions_tsv, "DAPI-T4").copy()
        flat["density"] = 5_000.0
        flat["count"] = flat["area_mm2"] * 5_000.0
        check(gate_grey_contrast(flat).status == FLAG,
              "grey contrast FLAGs when every structure reads the same (flooding)")

        print("\n[4] every gate exposes (value, status)")
        for r in run_all_gates(good, proj):
            check(isinstance(r.value, float) and r.status in (PASS, FLAG, NA),
                  f"{r.name}: value={r.value!r} status={r.status}")

        print("\n[5] gate_table -- one row per slice")
        tbl = gate_table(proj)
        check(len(tbl) == 2, f"gate_table has one row per slice (got {len(tbl)})")
        check(tbl.loc[tbl["slice"] == "syn_s1", "overall"].iloc[0] == PASS, "clean slice overall PASS")
        check(tbl.loc[tbl["slice"] == "syn_s2", "overall"].iloc[0] == FLAG, "bad slice overall FLAG")
        check("white_matter_density__status" in tbl.columns, "gate_table carries per-gate status")
        print(summary_view(tbl).to_string(index=False))

        print("\n[6] thresholds are tunable, not baked in")
        loose = replace(DEFAULT_THRESHOLDS, white_matter_ratio_max=99.0,
                        white_matter_abs_max=1e9)
        r = gate_white_matter(load_regions_tsv(bad.regions_tsv, "DAPI-T4"), loose)
        check(r.status == PASS, "loosened white-matter threshold flips FLAG -> PASS")

        print("\n[7] single-marker project must not crash (TdT-only edge case)")
        proj1 = _write_synthetic_project(base / "one", two_marker=False)
        cfg1 = load_config(proj1)
        check(not cfg1.emit_double, "Double+ NOT emitted with 1 marker")
        res1 = {r.name: r for r in run_all_gates(find_slices(proj1)[0], proj1)}
        check(res1["k_swing_pp"].status == NA, "k-sweep gate N/A with a single marker")
        check(res1["white_matter_density"].status == PASS, "density gates still work single-marker")
        tbl1 = gate_table(proj1)
        check(len(tbl1) == 2, "gate_table works on single-marker project")

        print("\n[8] missing tables degrade to N/A, never raise")
        partial = SliceFiles(label="partial", regions_tsv=good.regions_tsv, percell_tsv=None)
        res_p = {r.name: r for r in run_all_gates(partial, proj)}
        check(res_p["nucleus_area_peak_um2"].status == NA, "missing percell -> N/A not crash")
        check(res_p["white_matter_density"].status in (PASS, FLAG), "regions gate still evaluated")

        print("\n[9] advisory_gates demotes without hiding the number")
        demoted = replace(DEFAULT_THRESHOLDS,
                          advisory_gates=("white_matter_density", "ventricle_density",
                                          "total_density"))
        base = {r.name: r for r in run_all_gates(bad, proj)}
        dem = {r.name: r for r in run_all_gates(bad, proj, demoted)}
        check(base["white_matter_density"].status == FLAG
              and dem["white_matter_density"].status == FLAG,
              "demoted gate still reports FLAG (verdict is not faked)")
        check(dem["white_matter_density"].value == base["white_matter_density"].value,
              "demoted gate still reports its number unchanged")
        check(dem["white_matter_density"].advisory and not base["white_matter_density"].advisory,
              "demoted gate is marked advisory")
        check(dem["nucleus_area_peak_um2"].advisory is False,
              "non-demoted gate keeps blocking")
        t_dem = gate_table(proj, demoted)
        check(t_dem.loc[t_dem["slice"] == "syn_s2", "flagged"].iloc[0] == "nucleus_area_peak_um2",
              "overall verdict now driven only by the remaining blocking gate")

        print("\n[10] headless command construction")
        cmd = qupath_command(proj, "run_braian_detection.groovy", image="syn_s1")
        check(cmd[1] == "script" and "-i" in cmd and "syn_s1" in cmd, "single-image cmd uses -i")
        check("-s" in cmd, "cmd passes --save (else a 30-min pass is discarded)")
        check(cmd[-1].endswith("scripts/run_braian_detection.groovy"),
              "bare script name resolves under <project>/scripts")
        check("-i" not in qupath_command(proj, "x.groovy"), "project-wide cmd omits -i")
        check(run_qupath(cmd, dry_run=True) == -1, "dry_run prints instead of launching a JVM")

        print("\n[11] lock_detection_params preserves comments and verifies the write")
        (proj / "BraiAn.yml").write_text(
            "classForDetections: allen_mouse_10um_java\n"
            "channelDetections:\n"
            "  - name: DAPI-T4\n"
            "    parameters:\n"
            "      sigmaMicrons: 2.0   # KEEP ME: documents the wBA-vs-M3 tuning call\n"
            "      minAreaMicrons: 20.0\n"
            "      maxAreaMicrons: 250.0\n"
            "      histogramThreshold:\n"
            "        nPeak: 2\n")
        _p, bakp = lock_detection_params(
            proj, {"sigmaMicrons": 2.5, "minAreaMicrons": 25.0,
                   "histogramThreshold.nPeak": 3})
        txt = (proj / "BraiAn.yml").read_text()
        check("KEEP ME" in txt, "trailing comment survives the edit")
        after = detection_params(proj)
        check(after["sigmaMicrons"] == 2.5, f"sigmaMicrons locked (got {after['sigmaMicrons']})")
        check(after["minAreaMicrons"] == 25.0, "minAreaMicrons locked")
        check(after["histogramThreshold.nPeak"] == 3, "nested histogramThreshold key locked")
        check(after["maxAreaMicrons"] == 250.0, "untouched param unchanged")
        check(bakp is not None and bakp.exists(), "backup written before edit")
        check("sigmaMicrons: 2.0" in bakp.read_text(), "backup holds the pre-edit value")

        try:
            lock_detection_params(proj, {"sigmaMicronz": 1.0})
            check(False, "typo'd param must raise")
        except KeyError:
            check(True, "typo'd param raises instead of silently no-op'ing")

    print("\n" + ("ALL SELF-TESTS PASSED" if not failures
                  else f"{len(failures)} SELF-TEST FAILURE(S):\n  - " + "\n  - ".join(failures)))
    if failures:
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="QC self-check gates for the section-pipeline cockpit.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--project", type=Path, help="QuPath project dir (holds pipeline.yml, results/)")
    ap.add_argument("--results-dir", type=Path, default=None,
                    help="override <project>/results")
    ap.add_argument("--slice", default=None, help="only this slice label")
    ap.add_argument("--table", action="store_true", help="print the per-slice PASS/FLAG table")
    ap.add_argument("--self-test", action="store_true", help="run on synthetic data and exit")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return
    if not args.project:
        sys.exit("ERROR: --project is required (or use --self-test)")

    proj = args.project
    print(f"Project: {proj}")
    cfg = load_config(proj)
    print(f"  anchor : {cfg.anchor_name} ({anchor_channel(proj)})")
    print(f"  markers: {', '.join(cfg.marker_names) or '(none)'}"
          f"   Double+: {'yes' if cfg.emit_double else 'no'}")
    print(f"  exclude: {sorted(cfg.exclude_acronyms) or '(none)'}   k_robust: {k_robust(proj):g}")

    slices = find_slices(proj, args.results_dir)
    if args.slice:
        slices = [s for s in slices if s.label == args.slice]
        if not slices:
            sys.exit(f"ERROR: slice '{args.slice}' not found in results/")

    if args.table:
        print()
        print(summary_view(gate_table(proj, results_dir=args.results_dir)).to_string(index=False))
        return

    for sl in slices:
        print_gates(sl.label, run_all_gates(sl, proj))


if __name__ == "__main__":
    main()
