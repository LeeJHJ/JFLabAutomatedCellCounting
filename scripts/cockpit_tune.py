#!/usr/bin/env python3
"""cockpit_tune.py -- one place to see and change every tuning knob.

The pipeline's knobs live in three different places by design: the MIP stage takes
them on `czi_mip.py`'s command line, detection reads them from `BraiAn.yml`, and
marker classification reads them from `pipeline.yml`. That split is deliberate (D-14:
BraiAn.yml is BraiAnDetect's own params file and must not be polluted with
pipeline/marker concerns, nor the reverse) -- but it means an operator tuning a run
has to remember which knob lives where, and a tuning round leaves no record of what
was tried.

This module is a READER/WRITER OVER those files, not a replacement for them. The
files stay exactly where they are and keep their own formats:

    --list              every knob, its current value, where it lives, what it does,
                        and which way to move it
    --set knob=value    writes to the CORRECT file, prints old -> new, then validates
                        and (optionally) deploys
    --log               append this round's parameter set + the resulting numbers to
                        <project>/results/tuning_log.csv, so "the settings from two
                        rounds ago looked better" is answerable

COMMENT PRESERVATION -- why the writer looks the way it does. `BraiAn.yml` and
`pipeline.yml` are heavily commented, and those comments carry the reasoning behind
the values (why span_frac is 0.25 and not the old absolute 700, why sigma is 2.0
rather than 2.5, why `classifiers:` is empty ON PURPOSE). `ruamel.yaml` -- the usual
round-trip-preserving YAML library -- is NOT installed in the `braian` env, and a
PyYAML safe_load/safe_dump round-trip silently deletes every one of those comments.
Adding a dependency to one of three deliberately isolated envs for the sake of a
config writer is not worth the blast radius.

So: values are READ with PyYAML (safe, read-only) and WRITTEN by targeted
line-level substitution -- find the line owning the key path, replace only the scalar
token, leave indentation, inline comments, and every other byte untouched. Round-trip
fidelity is asserted in --self-test rather than assumed.

MIP-stage knobs are command-line arguments to czi_mip.py, not file values. --list
shows them so the operator sees the whole surface in one table, but they are marked
"pass to czi_mip.py" and --set refuses them -- pretending to persist them would be a
lie that costs a re-run to discover.

Usage:
    python3 cockpit_tune.py --project "<project dir>" --list
    python3 cockpit_tune.py --project "<dir>" --set sigmaMicrons=2.5 --set span_frac=0.30
    python3 cockpit_tune.py --project "<dir>" --set span_frac=0.30 --deploy
    python3 cockpit_tune.py --project "<dir>" --log --note "seams less visible"
    python3 cockpit_tune.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

BRAIAN = "BraiAn.yml"
PIPELINE = "pipeline.yml"
CLI = "czi_mip.py"


class Knob:
    """One tunable parameter: where it lives, how to reach it, what it does.

    `key_path` is the YAML path as a list of keys and list indices, e.g.
    ["channelDetections", 0, "parameters", "sigmaMicrons"]. For CLI knobs it is None
    -- those are not persisted anywhere and --set refuses them.
    """

    def __init__(self, name: str, stage: str, source: str, key_path: list | None,
                 default: Any, effect: str, direction: str, cast=float) -> None:
        self.name = name
        self.stage = stage
        self.source = source
        self.key_path = key_path
        self.default = default
        self.effect = effect
        self.direction = direction
        self.cast = cast

    @property
    def settable(self) -> bool:
        return self.key_path is not None


# The registry IS the documentation. Anything tunable belongs here, or the operator
# cannot find it -- which was the whole problem this module exists to fix.
KNOBS: list[Knob] = [
    # ── MIP / seams (czi_mip.py command line -- not persisted in any file) ──────
    Knob("feather_margin", "mip", CLI, None, 130,
         "seam blend width, px, for the per-scene tile stitch",
         "RAISE to soften visible seams; LOWER to keep tile edges crisp", int),
    Knob("flat_field", "mip", CLI, None, True,
         "retrospective per-channel shading correction (--no-flat-field disables)",
         "DISABLE to test whether shading estimation is itself causing banding", bool),
    Knob("dapi_z", "mip", CLI, None, None,
         "force the anchor focus plane (0-based Z) instead of the automatic pick",
         "SET when the var-of-Laplacian pick disagrees with your eye", int),
    Knob("scenes", "mip", CLI, None, None,
         "1-based scene subset to convert",
         "SET to one scene to iterate fast (~5 min) instead of a whole series", int),

    # ── Detection (BraiAn.yml -- BraiAnDetect's own params, D-14) ───────────────
    Knob("sigmaMicrons", "detect", BRAIAN,
         ["channelDetections", 0, "parameters", "sigmaMicrons"], 2.0,
         "smoothing before watershed; the split-vs-merge control",
         "RAISE to merge over-split nuclei; LOWER to separate touching nuclei"),
    Knob("minAreaMicrons", "detect", BRAIAN,
         ["channelDetections", 0, "parameters", "minAreaMicrons"], 20.0,
         "smallest accepted nucleus, um^2",
         "RAISE to reject debris/fragments; LOWER if real small nuclei are missing"),
    Knob("maxAreaMicrons", "detect", BRAIAN,
         ["channelDetections", 0, "parameters", "maxAreaMicrons"], 250.0,
         "largest accepted nucleus, um^2",
         "RAISE if large nuclei are clipped; LOWER to reject merged blobs"),
    Knob("cellExpansionMicrons", "detect", BRAIAN,
         ["channelDetections", 0, "parameters", "cellExpansionMicrons"], 5.0,
         "nucleus -> cell expansion; defines the whole-cell/cytoplasm compartment",
         "LOWER to cut TdT contamination from passing axons; RAISE to capture more cytoplasm"),
    Knob("backgroundRadiusMicrons", "detect", BRAIAN,
         ["channelDetections", 0, "parameters", "backgroundRadiusMicrons"], 10.0,
         "background estimation radius for detection",
         "RAISE on broad uneven illumination; LOWER for local background"),
    Knob("requestedPixelSizeMicrons", "detect", BRAIAN,
         ["channelDetections", 0, "parameters", "requestedPixelSizeMicrons"], 0.460357,
         "MUST equal this project's server.json PhysicalSizeX",
         "DO NOT tune -- match the image exactly or every um-denominated param mis-scales"),

    # ── Classification (pipeline.yml -- pipeline/marker concerns, D-14) ─────────
    Knob("span_frac", "classify", PIPELINE,
         ["detection_threshold", "span_frac"], 0.25,
         "anchor cut placement: floor + span_frac*(bright_peak - floor), per section",
         "RAISE for fewer/brighter nuclei; LOWER to catch dimmer nuclei"),
    Knob("peak_prominence", "classify", PIPELINE,
         ["detection_threshold", "peak_prominence"], 100,
         "histogram peak-finding prominence for both threshold endpoints",
         "LOWER if the bright-nuclei peak is not found on a section", int),
    Knob("smooth_window", "classify", PIPELINE,
         ["detection_threshold", "smooth_window"], 15,
         "histogram smoothing window for peak finding",
         "RAISE on noisy histograms", int),
    Knob("k_robust", "classify", PIPELINE, ["k_robust"], 3.0,
         "marker-positive cut: median + k*1.4826*MAD on background-subtracted signal",
         "RAISE to cut TdT false positives from passing axons; LOWER if real positives are missed"),
    Knob("gap_um", "classify", PIPELINE, ["ring", "gap_um"], 1.0,
         "gap between nucleus boundary and the cytoplasmic measurement ring",
         "RAISE to avoid nuclear bleed into the ring (cytoplasmic markers only)"),
    Knob("width_um", "classify", PIPELINE, ["ring", "width_um"], 8.0,
         "cytoplasmic measurement ring thickness",
         "RAISE to capture more cytoplasm (cytoplasmic markers only)"),
]

KNOBS_BY_NAME = {k.name: k for k in KNOBS}


def _read_yaml(path: Path) -> dict:
    """Load a YAML config READ-ONLY. Never used as the basis for a write -- see the
    module docstring on comment preservation."""
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


def _get_by_path(data: Any, key_path: list) -> Any:
    """Walk a mixed key/index path, returning None if any step is missing."""
    cur = data
    for step in key_path:
        try:
            cur = cur[step]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def _scalar_line_index(lines: list[str], key_path: list) -> int:
    """Find the 0-based index of the line that OWNS the scalar at `key_path`.

    Walks the file by indentation, which is what lets the write stay line-level and
    therefore comment-preserving. Integer steps in the path are list indices and are
    matched against `- ` sequence items at the current level.

    Raises KeyError if the path is not present, rather than guessing -- a silent miss
    would leave the operator believing a value changed when it did not.
    """
    target = key_path[-1]
    depth_indent = -1   # indentation of the level currently being searched
    idx = 0
    n = len(lines)

    for step_i, step in enumerate(key_path):
        found = -1
        seq_seen = -1
        while idx < n:
            raw = lines[idx]
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                idx += 1
                continue
            indent = len(raw) - len(raw.lstrip())
            if depth_indent >= 0 and indent <= depth_indent and step_i > 0:
                # Dedented out of the parent block without finding the key.
                break
            if isinstance(step, int):
                if stripped.startswith("- "):
                    if indent == (depth_indent + 2 if depth_indent >= 0 else indent):
                        seq_seen += 1
                        if seq_seen == step:
                            found = idx
                            depth_indent = indent
                            idx += 1
                            break
            else:
                m = re.match(r"^(-\s+)?([A-Za-z_][\w.-]*)\s*:", stripped)
                if m and m.group(2) == step:
                    found = idx
                    # A "- key:" line puts its siblings at the key's own column.
                    depth_indent = indent + (len(m.group(1)) if m.group(1) else 0)
                    idx += 1
                    break
            idx += 1
        if found < 0:
            raise KeyError(f"key path {key_path} not found (stuck at {step!r})")
        if step is target and step_i == len(key_path) - 1:
            return found
    raise KeyError(f"key path {key_path} not found")


def _format_value(value: Any) -> str:
    """Render a Python value as the YAML scalar token to substitute."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return str(value)


def _set_scalar(path: Path, key_path: list, value: Any) -> tuple[Any, Any]:
    """Replace ONE scalar in a YAML file, preserving every other byte.

    Returns (old_value, new_value). Only the value token on the owning line is
    rewritten; indentation and any trailing `# comment` survive verbatim, which is
    the whole point -- those comments carry the tuning rationale.
    """
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    i = _scalar_line_index(lines, key_path)
    line = lines[i]
    newline = "\n" if line.endswith("\n") else ""
    body = line.rstrip("\n")

    m = re.match(r"^(\s*(?:-\s+)?[A-Za-z_][\w.-]*\s*:\s*)(.*?)(\s*#.*)?$", body)
    if not m:
        raise ValueError(f"{path.name}: line {i + 1} is not a scalar assignment: {body!r}")
    prefix, old_token, comment = m.group(1), m.group(2), m.group(3) or ""
    if old_token.strip() == "":
        raise ValueError(
            f"{path.name}: '{key_path[-1]}' on line {i + 1} has no scalar value "
            f"(it opens a nested block) -- refusing to overwrite a block with a scalar"
        )

    old_value = yaml.safe_load(old_token) if old_token.strip() else None
    new_token = _format_value(value)
    # Keep a trailing comment in its original column when the new token is shorter.
    # These files are hand-aligned; a one-character shift makes an otherwise clean
    # diff look like a reformat.
    if comment and len(new_token) < len(old_token):
        new_token = new_token.ljust(len(old_token))
    lines[i] = f"{prefix}{new_token}{comment}{newline}"
    path.write_text("".join(lines))
    return old_value, value


def _current_value(project: Path, knob: Knob) -> Any:
    """Current value of a knob, or None when unset/unreachable."""
    if not knob.settable:
        return None
    cfg_path = project / knob.source
    if not cfg_path.exists():
        return None
    return _get_by_path(_read_yaml(cfg_path), knob.key_path)


def print_knobs(project: Path) -> None:
    """--list: the whole tuning surface in one table."""
    print(f"Tuning knobs for {project}")
    rows = []
    for knob in KNOBS:
        if knob.settable:
            val = _current_value(project, knob)
            shown = "(not set)" if val is None else str(val)
            where = knob.source
        else:
            shown = f"default {knob.default}"
            where = "pass to czi_mip.py"
        rows.append((knob.stage, knob.name, shown, where, knob.effect, knob.direction))

    w_stage = max(len(r[0]) for r in rows)
    w_name = max(len(r[1]) for r in rows)
    w_val = max(len(r[2]) for r in rows)
    w_src = max(len(r[3]) for r in rows)

    last_stage = None
    for stage, name, val, src, effect, direction in rows:
        if stage != last_stage:
            print()
            last_stage = stage
        print(f"  {stage:<{w_stage}}  {name:<{w_name}}  {val:>{w_val}}  {src:<{w_src}}  {effect}")
        print(f"  {'':<{w_stage}}  {'':<{w_name}}  {'':>{w_val}}  {'':<{w_src}}  -> {direction}")
    print()
    print("  MIP knobs are czi_mip.py command-line arguments -- they are not stored in any")
    print("  config file, so --set cannot persist them. Pass them on the czi_mip.py call.")


def apply_sets(project: Path, assignments: list[str]) -> list[tuple[str, Any, Any]]:
    """--set: route each knob=value to the right file. Returns [(name, old, new)]."""
    changes: list[tuple[str, Any, Any]] = []
    for raw in assignments:
        if "=" not in raw:
            raise SystemExit(f"--set expects knob=value, got {raw!r}")
        name, _, value_text = raw.partition("=")
        name, value_text = name.strip(), value_text.strip()
        knob = KNOBS_BY_NAME.get(name)
        if knob is None:
            known = ", ".join(sorted(KNOBS_BY_NAME))
            raise SystemExit(f"unknown knob {name!r}. Known knobs: {known}")
        if not knob.settable:
            raise SystemExit(
                f"'{name}' is a czi_mip.py command-line argument, not a stored config value.\n"
                f"       Pass it on the czi_mip.py call instead, e.g. --{name.replace('_', '-')} {value_text}"
            )
        try:
            value = knob.cast(value_text)
        except ValueError:
            raise SystemExit(f"{name}: {value_text!r} is not a valid {knob.cast.__name__}")

        cfg_path = project / knob.source
        if not cfg_path.exists():
            raise SystemExit(f"{cfg_path} does not exist -- is {project} a deployed project?")
        old, new = _set_scalar(cfg_path, knob.key_path, value)
        print(f"  {knob.source:<12} {name:<26} {old} -> {new}")
        changes.append((name, old, new))
    return changes


def validate_config(project: Path) -> bool:
    """Run the existing validator over the project's pipeline.yml."""
    validator = SCRIPT_DIR / "validate_pipeline_config.py"
    cfg = project / PIPELINE
    if not validator.exists() or not cfg.exists():
        print("  (validator or pipeline.yml missing -- skipping validation)")
        return True
    proc = subprocess.run([sys.executable, str(validator), "--config", str(cfg)],
                          capture_output=True, text=True)
    ok = proc.returncode == 0
    print(f"  validate_pipeline_config.py: {'OK' if ok else 'FAILED'}")
    if not ok:
        print(proc.stdout.strip() or proc.stderr.strip())
    return ok


def deploy(project: Path) -> bool:
    """Deploy via sync_project.py -- repo scripts/ is SOURCE, project scripts/ DEPLOYED."""
    syncer = SCRIPT_DIR / "sync_project.py"
    if not syncer.exists():
        print("  (sync_project.py missing -- skipping deploy)")
        return True
    proc = subprocess.run([sys.executable, str(syncer), "--project", str(project)],
                          capture_output=True, text=True)
    ok = proc.returncode == 0
    print(f"  sync_project.py: {'OK' if ok else 'FAILED'}")
    if not ok:
        print(proc.stdout.strip() or proc.stderr.strip())
    return ok


def _readout_numbers(project: Path) -> dict[str, Any]:
    """Key numbers from the cockpit outputs that already exist.

    These are READ, never recomputed -- cockpit_checks.py and the export stage own
    them, and a second implementation would drift from the first.
    """
    out: dict[str, Any] = {}
    qc = project / "results" / "cockpit_qc_summary.csv"
    readout = project / "results" / "cockpit_readout.csv"

    if qc.exists():
        with qc.open() as fh:
            rows = list(csv.DictReader(fh))
        area = [float(r["nucleus_area_peak_um2"]) for r in rows
                if (r.get("nucleus_area_peak_um2") or "").strip()]
        dens = [float(r["total_density"]) for r in rows if (r.get("total_density") or "").strip()]
        if area:
            out["area_peak_um2_median"] = round(sum(area) / len(area), 2)
        if dens:
            out["total_density_median"] = round(sum(dens) / len(dens), 1)
        out["slices"] = len(rows)

    if readout.exists():
        with readout.open() as fh:
            rows = list(csv.DictReader(fh))
        dapi = sum(float(r["DAPI_n"]) for r in rows if (r.get("DAPI_n") or "").strip())
        fos = sum(float(r["Fos+_n"]) for r in rows if (r.get("Fos+_n") or "").strip())
        tdt = sum(float(r["TdT+_n"]) for r in rows if (r.get("TdT+_n") or "").strip())
        if dapi > 0:
            out["Fos+_frac"] = round(fos / dapi, 4)
            out["TdT+_frac"] = round(tdt / dapi, 4)
        out["DAPI_n"] = int(dapi)
    return out


def log_round(project: Path, note: str = "") -> Path:
    """--log: append this parameter set + resulting numbers to results/tuning_log.csv."""
    results = project / "results"
    results.mkdir(parents=True, exist_ok=True)
    log_path = results / "tuning_log.csv"

    row: dict[str, Any] = {"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M")}
    for knob in KNOBS:
        if knob.settable:
            row[knob.name] = _current_value(project, knob)
    row.update(_readout_numbers(project))
    row["note"] = note

    existing: list[dict] = []
    fieldnames = list(row)
    if log_path.exists():
        with log_path.open() as fh:
            reader = csv.DictReader(fh)
            existing = list(reader)
            for name in reader.fieldnames or []:
                if name not in fieldnames:
                    fieldnames.append(name)

    # "round" is always the first column. Rebuilding the header from the existing
    # file would otherwise migrate it to the end on the second write, so the column
    # order would churn between rounds -- exactly the kind of instability that makes
    # a log hard to eyeball.
    round_no = len(existing) + 1
    if "round" in fieldnames:
        fieldnames.remove("round")
    fieldnames.insert(0, "round")
    row["round"] = round_no

    with log_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for old in existing:
            writer.writerow(old)
        writer.writerow(row)

    print(f"  round {round_no} appended -> {log_path}")
    for key in ("area_peak_um2_median", "total_density_median", "Fos+_frac", "TdT+_frac"):
        if key in row:
            print(f"    {key}: {row[key]}")
    return log_path


def _self_test() -> None:
    """Prove the writer preserves comments, and that the knob table is coherent."""
    print("Running --self-test (comment-preserving YAML write, no project needed)...")

    fixture = """\
# Header comment that MUST survive.
# Second header line.
anchor:
  name: "DAPI"                # inline comment on a string
  channel: "DAPI-T4"

k_robust: 3.0                 # robust multiplier -- rationale lives HERE

detection_threshold:
  mode: "span_fraction"
  span_frac: 0.25             # WHY 0.25: reproduces the operator's visual call
  peak_prominence: 100

ring:
  gap_um: 1.0
  width_um: 8.0

channelDetections:
  - name: "DAPI-T4"
    parameters:
      sigmaMicrons: 2.0       # split-vs-merge control
      minAreaMicrons: 20.0
      cellExpansionMicrons: 5.0
    classifiers: []           # intentionally empty -- do not repopulate
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.yml"
        path.write_text(fixture)
        before = path.read_text()

        # (a) nested scalar under a mapping
        old, new = _set_scalar(path, ["detection_threshold", "span_frac"], 0.30)
        assert old == 0.25 and new == 0.30, f"expected 0.25 -> 0.30, got {old} -> {new}"

        # (b) scalar under a LIST item (the BraiAn.yml shape)
        old_s, _ = _set_scalar(path, ["channelDetections", 0, "parameters", "sigmaMicrons"], 2.5)
        assert old_s == 2.0, f"expected sigma 2.0, got {old_s}"

        # (c) top-level scalar
        old_k, _ = _set_scalar(path, ["k_robust"], 3.5)
        assert old_k == 3.0, f"expected k_robust 3.0, got {old_k}"

        after = path.read_text()

        # THE contract: every comment survives. This is why the writer is line-level.
        for comment in (
            "# Header comment that MUST survive.",
            "# Second header line.",
            "# inline comment on a string",
            "# robust multiplier -- rationale lives HERE",
            "# WHY 0.25: reproduces the operator's visual call",
            "# split-vs-merge control",
            "# intentionally empty -- do not repopulate",
        ):
            assert comment in after, f"comment destroyed by write: {comment!r}"

        # Values actually changed, and NOTHING else did.
        reloaded = yaml.safe_load(after)
        assert reloaded["detection_threshold"]["span_frac"] == 0.30
        assert reloaded["channelDetections"][0]["parameters"]["sigmaMicrons"] == 2.5
        assert reloaded["k_robust"] == 3.5
        assert reloaded["anchor"]["channel"] == "DAPI-T4", "untouched keys must not change"
        assert reloaded["ring"] == {"gap_um": 1.0, "width_um": 8.0}, "untouched block must not change"
        assert reloaded["channelDetections"][0]["parameters"]["minAreaMicrons"] == 20.0
        assert reloaded["channelDetections"][0]["classifiers"] == [], (
            "the intentionally-empty classifiers block must stay empty (one classification path)"
        )

        # Line count is unchanged -- a line-level write adds and removes nothing.
        assert len(before.splitlines()) == len(after.splitlines()), (
            "a comment-preserving write must not change the line count"
        )

        # (d) a missing key must raise, not silently no-op.
        try:
            _set_scalar(path, ["detection_threshold", "not_a_real_key"], 1)
            raise AssertionError("expected KeyError for a missing key path")
        except KeyError:
            pass

        # (e) refusing to overwrite a block-opening key with a scalar.
        try:
            _set_scalar(path, ["ring"], 5)
            raise AssertionError("expected ValueError when overwriting a block with a scalar")
        except ValueError:
            pass

    # (f) registry coherence: unique names, CLI knobs unsettable, paths well-formed.
    assert len(KNOBS_BY_NAME) == len(KNOBS), "duplicate knob name in the registry"
    for knob in KNOBS:
        assert knob.stage in ("mip", "detect", "classify"), f"{knob.name}: bad stage"
        if knob.source == CLI:
            assert not knob.settable, f"{knob.name}: CLI knobs must not be settable"
        else:
            assert knob.settable and knob.key_path, f"{knob.name}: file knob needs a key_path"
            assert knob.source in (BRAIAN, PIPELINE), f"{knob.name}: unknown source"

    # (g) D-14: no detection param may be routed into pipeline.yml, and no
    # pipeline/marker concern into BraiAn.yml. This is the constraint most likely to
    # be broken by a careless registry edit, so it is asserted rather than trusted.
    for knob in KNOBS:
        if knob.stage == "detect":
            assert knob.source in (BRAIAN, CLI), (
                f"D-14 violation: detection knob '{knob.name}' routed to {knob.source}"
            )
        if knob.stage == "classify":
            assert knob.source == PIPELINE, (
                f"D-14 violation: classification knob '{knob.name}' routed to {knob.source}"
            )

    print("\nself-test PASSED: (a-c) scalars set at top level, nested, and inside a list "
          "item; every comment, the line count, and all untouched keys survive the write; "
          "(d) a missing key path raises instead of silently no-op'ing; (e) a block-opening "
          "key cannot be overwritten with a scalar; (f) the knob registry is coherent; "
          "(g) D-14 holds -- detection params route to BraiAn.yml, classification params "
          "to pipeline.yml, never crossed.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument("--project", type=Path, default=None,
                   help="QuPath project directory holding BraiAn.yml and pipeline.yml")
    p.add_argument("--list", action="store_true",
                   help="show every knob: current value, source file, effect, direction to move it")
    p.add_argument("--set", dest="assignments", action="append", default=[], metavar="KNOB=VALUE",
                   help="set a knob (repeatable); routes to the correct config file")
    p.add_argument("--deploy", action="store_true",
                   help="after --set, deploy to the project via sync_project.py")
    p.add_argument("--log", action="store_true",
                   help="append the current parameter set + resulting numbers to "
                        "<project>/results/tuning_log.csv")
    p.add_argument("--note", default="",
                   help="free-text note recorded with --log (e.g. 'seams less visible')")
    p.add_argument("--self-test", action="store_true",
                   help="run the built-in comment-preservation self-test and exit")
    args = p.parse_args()
    if not args.self_test:
        if args.project is None:
            p.error("--project is required unless --self-test is set")
        if not (args.list or args.assignments or args.log):
            p.error("nothing to do: pass --list, --set, and/or --log")
    return args


def main() -> int:
    args = parse_args()

    if args.self_test:
        _self_test()
        return 0

    project = args.project
    if not project.is_dir():
        raise SystemExit(f"not a directory: {project}")

    if args.assignments:
        print("Setting knobs...")
        apply_sets(project, args.assignments)
        print("Verifying...")
        if not validate_config(project):
            return 1
        if args.deploy:
            print("Deploying...")
            if not deploy(project):
                return 1
        else:
            print("  (not deployed -- pass --deploy to run sync_project.py)")

    if args.list:
        print_knobs(project)

    if args.log:
        print("Logging this round...")
        log_round(project, args.note)

    return 0


if __name__ == "__main__":
    sys.exit(main())
