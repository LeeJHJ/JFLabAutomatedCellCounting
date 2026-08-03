#!/usr/bin/env python3
"""smoke_test.py -- run the pipeline against a project that has never been run.

WHY THIS EXISTS
    Ten bugs in four days were the same shape: code that works on whatever state
    the workspace happens to be in, and fails on a genuinely new one. A stage
    wrote into `results/` without creating it, because every project on this
    machine already had one. `02_detect_classify` wrote a classifier JSON into a
    directory QuPath only makes once you have saved a classifier from the GUI.
    The calibrate notebook asked you to pick a slice from the export tables --
    which is what you were trying to produce.

    None of that is visible when the tests run against projects a previous run
    already populated. The generalization pass was validated that way, so
    anything a prior run left lying around was invisible to it, and every one of
    these was found by a human hitting it mid-run.

    So this builds a project from NOTHING -- `project.qpproj`, `pipeline.yml`,
    `BraiAn.yml`, an ontology JSON, and not one byte more. No `results/`, no
    `classifiers/object_classifiers/`, no exports, no prior run -- and drives the
    chain against it.

WHAT "PASS" MEANS HERE
    Not "every stage succeeded" -- most stages CANNOT succeed with no data, and
    demanding they do would be testing the wrong thing. A stage passes when it
    either succeeds, or fails with a message that names the missing path and the
    command that produces it. A bare `IndexError: list index out of range` is a
    FAILURE of this test even though the code "correctly" refused to continue:
    for a student, error text is the manual, and it arrives exactly when needed.

SCOPE -- PYTHON, PLUS A LINT OVER THE GROOVY
    The QuPath stages need a JVM and real images, so they cannot run here. Three
    of the eight regressions below are nonetheless one-line `mkdirs()` calls whose
    ABSENCE is visible in the source, so those are checked by reading it. That
    lint keeps working as new writes are added, which a fixture-based test would
    not.

THE EIGHT REGRESSIONS PINNED (the bug class, by commit)
    fbcb888  find_slices needed export tables that do not exist yet
    624a705  02_detect_classify needed a directory a GUI session had left behind
    641b5dd  four writes into results/ assumed the directory existed
    f9f79f9  --scenes broke per-scene tile counting
    6df29b9  a single-scene CZI was rejected outright
    f21c6b1  sync_project --all enumerated scratch fixtures as real projects
    2415950  three imaging sessions were counted as three animals
    a4f8c16  the template config did not carry per-slice-set tuning to a project

THREE USES, ONE ARTIFACT
    a regression test for that bug class; install verification on a new lab
    machine ("run this, get PASS, you are set up" -- `--self-tests` runs every
    sibling module's own self-test too); and a teaching artifact a student runs
    before touching real data, to watch the whole chain work on something
    disposable.

Usage:
    python3 scripts/smoke_test.py                 # the full run
    python3 scripts/smoke_test.py --no-self-tests # skip the sibling --self-tests
    python3 scripts/smoke_test.py --keep /tmp/x   # keep the synthetic project
    python3 scripts/smoke_test.py --list
    python3 scripts/smoke_test.py --self-test     # prove these checks have teeth
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

# Import before anything pulls in pyplot: cockpit_animal builds figures at import
# time in some paths, and a headless run must not try to open a display.
os.environ.setdefault("MPLBACKEND", "Agg")

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import cockpit_animal as ca                # noqa: E402
import cockpit_checks as cc                # noqa: E402
import cockpit_regions as creg             # noqa: E402
import cockpit_tune as ctune               # noqa: E402
import local_chance as lc                  # noqa: E402
import sync_project as sp                  # noqa: E402
import validate_pipeline_config as vpc     # noqa: E402

PASS = "ok  "
FAIL = "FAIL"

# How far below a `new File(buildPathInProject(...))` the matching mkdirs() may sit.
# Every current call site puts it on the very next line; 5 leaves room for a comment
# without letting an unguarded write hide.
_MKDIRS_WINDOW = 5

# Directories a fresh project must NOT need to already contain. Asserted absent
# after the fixture is built, so a future fixture change cannot quietly weaken
# every fresh-project check at once.
_MUST_BE_ABSENT = ("results", "classifiers", "regions_to_exclude", "reference")


class SmokeFailure(AssertionError):
    """A check failed. The message is the finding -- write it for the operator."""


# ---------------------------------------------------------------------------
# Synthetic projects
# ---------------------------------------------------------------------------
def _qpproj(labels: list[str]) -> str:
    """A QuPath project file with image entries and nothing else.

    QuPath names an imported entry `<file> - <image name>`; `project_image_names`
    reads exactly these strings, so the fixture must reproduce that shape or the
    fresh-project fallback would be tested against a name it will never see.
    """
    return json.dumps({"images": [
        {"entryID": i + 1, "imageName": f"{label}_MIP.ome.tiff - {label}"}
        for i, label in enumerate(labels)
    ]})


def _braian_yml() -> str:
    """BraiAnDetect's own params file (D-14), with the comments that carry the
    reasoning -- the comment-preservation check needs something to preserve."""
    return (
        "# BraiAn.yml -- BraiAnDetect detection params ONLY (D-14).\n"
        "classForDetections: allen_mouse_10um_java\n"
        "channelDetections:\n"
        '  - name: "DAPI-T4"\n'
        "    parameters:\n"
        "      requestedPixelSizeMicrons: 0.460357   # MUST equal server.json PhysicalSizeX\n"
        "      sigmaMicrons: 2.0                     # split-vs-merge control\n"
        "      minAreaMicrons: 20.0\n"
        "      maxAreaMicrons: 250.0\n"
        "      cellExpansionMicrons: 5.0\n"
        "# Empty ON PURPOSE -- classification happens only in 02_detect_classify.groovy.\n"
        "classifiers: []\n"
    )


def _pipeline_yml(animal: str | None = None, per_marker_k: float | None = 2.5,
                  with_detection_threshold: bool = False) -> str:
    """A project pipeline.yml with per-slice-set tuning in it.

    The per-marker `k_robust` and the non-default global are the point: `sync_config`
    must merge INTO this file, never over it. Written as text rather than
    `yaml.safe_dump` so there are real comments on the line the writer edits.
    """
    lines = [
        "# pipeline.yml -- this slice-set's marker declaration.",
        "anchor:",
        '  name: "DAPI"',
        '  channel: "DAPI-T4"',
        "",
        "markers:",
        '  - name: "Fos"                 # recall marker -- nuclear',
        '    channel: "AF488-T3"',
        '    compartment: "nuclear"',
        '  - name: "TdT"                 # engram marker -- fills the whole cell',
        '    channel: "AF568-T2"',
        '    compartment: "whole-cell"',
    ]
    if per_marker_k is not None:
        lines.append(f"    k_robust: {per_marker_k}      # dim TdT was being missed at the global k")
    lines += [
        "",
        'exclude_acronyms: ["DG-sg", "VS"]',
        "",
        "# Global default; a marker may override it above.",
        "k_robust: 3.0",
        "",
        "ring:",
        "  gap_um: 1.0",
        "  width_um: 8.0",
    ]
    if animal:
        lines += ["", "# One brain imaged across several sessions -- pool them.",
                  f'animal: "{animal}"']
    if with_detection_threshold:
        lines += ["", sp.extract_block(sp.ROOT_CONFIG.read_text(), "detection_threshold").rstrip()]
    return "\n".join(lines) + "\n"


def write_fresh_project(base: Path, labels: list[str] | None = None,
                        animal: str | None = None) -> Path:
    """A project as it exists the moment the operator finishes ABBA export.

    Four files, and NOTHING else -- that absence is the whole fixture.
    """
    labels = labels or ["SMOKE_s1", "SMOKE_s2"]
    proj = base / "smoke project"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "project.qpproj").write_text(_qpproj(labels))
    (proj / "pipeline.yml").write_text(_pipeline_yml(animal=animal))
    (proj / "BraiAn.yml").write_text(_braian_yml())
    (proj / "allen_mouse_10um_java-Ontology.json").write_text(
        json.dumps(creg._synthetic_ontology_json()))
    return proj


def write_exported_project(base: Path, name: str, labels: list[str],
                           animal: str | None) -> Path:
    """A project that HAS been through detection + export.

    Used for the happy path (the chain must actually produce numbers, not merely
    fail politely) and for the session-vs-animal check, where the slice labels
    carry three different session prefixes on purpose.
    """
    proj = base / name
    (proj / "results").mkdir(parents=True, exist_ok=True)
    (proj / "project.qpproj").write_text(_qpproj(labels))
    (proj / "pipeline.yml").write_text(_pipeline_yml(animal=animal, per_marker_k=None,
                                                     with_detection_threshold=True))
    (proj / "BraiAn.yml").write_text(_braian_yml())
    (proj / "allen_mouse_10um_java-Ontology.json").write_text(
        json.dumps(creg._synthetic_ontology_json()))

    cats = ["DAPI", "Fos+", "TdT+", "Double+"]
    header = ["acronym", "hemisphere", "area_mm2"] + [f"{c}_count" for c in cats]
    for i, label in enumerate(labels):
        rows = [
            ("LA", "Left", 0.30, [100 + 10 * i, 30, 50, 20]),
            ("LA", "Right", 0.30, [80 + 10 * i, 24, 40, 16]),
            ("CA1", "Left", 1.00, [200 + 10 * i, 40, 60, 24]),
        ]
        lines = ["\t".join(header)]
        for acr, hemi, area, counts in rows:
            lines.append("\t".join([acr, hemi, f"{area:.6f}"] + [str(c) for c in counts]))
        stem = f"{label}_MIP.ome.tiff - {label}"
        (proj / "results" / f"{stem}__id1__region_table.tsv").write_text("\n".join(lines) + "\n")

        pc_header = ["class", "region_label", "nucleus_area_um2", "centroid_x_px",
                     "centroid_y_px", "Fos_bgsub", "TdT_bgsub"]
        pc = ["\t".join(pc_header)]
        for j in range(60):
            cls = ("Double+" if j % 10 == 0 else "TdT+" if j % 5 == 0
                   else "Fos+" if j % 3 == 0 else "Negative")
            pc.append("\t".join([cls, "LA" if j % 2 else "CA1", "40.0",
                                 str(float(j)), str(float(j)), "50.0", "50.0"]))
        (proj / "results" / f"{stem}__id1__percell_export.tsv").write_text("\n".join(pc) + "\n")
    return proj


# ---------------------------------------------------------------------------
# Check plumbing
# ---------------------------------------------------------------------------
@dataclass
class Ctx:
    """Everything the checks read. `groovy_dir` is a field rather than a constant so
    --self-test can point the source lints at a deliberately broken copy."""
    repo: Path
    tmp: Path
    fresh: Path
    exported: Path
    groovy_dir: Path
    run_self_tests: bool = True


@dataclass
class Check:
    check_id: str
    stage: str                      # the docs/pipeline-stages.yml stage this covers
    title: str
    fn: Callable[[Ctx], str]
    pins: str = ""                  # commit whose regression this holds down
    slow: bool = False


CHECKS: list[Check] = []


def check(check_id: str, stage: str, title: str, pins: str = "", slow: bool = False):
    def deco(fn: Callable[[Ctx], str]) -> Callable[[Ctx], str]:
        CHECKS.append(Check(check_id, stage, title, fn, pins, slow))
        return fn
    return deco


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise SmokeFailure(msg)


def _expect_actionable(fn: Callable[[], Any], wants: tuple[type, ...],
                       must_mention: str, what: str) -> str:
    """Assert `fn` refuses, and refuses USEFULLY.

    Refusing is correct -- there is no data. The finding this looks for is HOW: a
    bare IndexError/KeyError from deep inside a helper tells a new user nothing,
    which is the exact failure the calibrate notebook shipped with. So the message
    must name the thing that is missing.
    """
    try:
        fn()
    except wants as exc:
        text = str(exc)
        _require(must_mention in text,
                 f"{what} refused, but its message does not name {must_mention!r} "
                 f"-- a user cannot act on it. Got: {text!r}")
        return f"refused with an actionable message naming {must_mention!r}"
    except (IndexError, KeyError, AttributeError, TypeError) as exc:
        raise SmokeFailure(
            f"{what} raised a bare {type(exc).__name__} ({exc}) instead of a message "
            f"naming what is missing -- this is the fresh-project bug class itself."
        ) from exc
    raise SmokeFailure(f"{what} SUCCEEDED on a project with no data -- it should refuse.")


# ---------------------------------------------------------------------------
# Checks -- the fixture itself
# ---------------------------------------------------------------------------
@check("fixture", "project", "the fresh project really is bare")
def _fixture_is_bare(ctx: Ctx) -> str:
    present = [d for d in _MUST_BE_ABSENT if (ctx.fresh / d).exists()]
    _require(not present,
             f"the fixture is not fresh: {present} already exist(s), so every "
             f"fresh-project check below is testing nothing.")
    for f in ("project.qpproj", "pipeline.yml", "BraiAn.yml"):
        _require((ctx.fresh / f).is_file(), f"fixture is missing {f}")
    return f"4 files, none of {list(_MUST_BE_ABSENT)}"


# ---------------------------------------------------------------------------
# Checks -- stage `deploy` (sync_project.py)
# ---------------------------------------------------------------------------
@check("deploy_bootstrap", "deploy", "a project with no pipeline.yml gets one")
def _deploy_bootstrap(ctx: Ctx) -> str:
    proj = ctx.tmp / "bootstrap project"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "project.qpproj").write_text(_qpproj(["B_s1"]))
    rep = sp.sync_project(proj)
    _require(rep["config"]["created"], "sync_project did not create pipeline.yml")
    _require((proj / "pipeline.yml").is_file(), "pipeline.yml was reported created but is absent")
    n = len(rep["scripts"]["new"])
    _require(n > 0, "no groovy scripts were deployed")
    return f"pipeline.yml created from the repo template, {n} groovy scripts deployed"


@check("deploy_preserves_tuning", "deploy",
       "per-slice-set tuning survives a deploy", pins="a4f8c16")
def _deploy_preserves_tuning(ctx: Ctx) -> str:
    """The template carries a global k_robust only. A project that has tuned a
    marker's own k (M3 Hipp2: TdT at 2.5, Fos left at 3.0) must keep it -- a deploy
    that reset it would silently re-cut every marker."""
    proj = ctx.tmp / "tuned project"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "project.qpproj").write_text(_qpproj(["T_s1"]))
    (proj / "pipeline.yml").write_text(_pipeline_yml(per_marker_k=2.5))

    rep = sp.sync_project(proj)
    _require(rep["config"]["added_blocks"] == ["detection_threshold"],
             f"expected only detection_threshold to be added, got {rep['config']}")
    doc = yaml.safe_load((proj / "pipeline.yml").read_text())
    tdt = next(m for m in doc["markers"] if m["name"] == "TdT")
    _require(tdt.get("k_robust") == 2.5,
             f"the deploy lost TdT's per-marker k_robust (now {tdt.get('k_robust')!r})")
    fos = next(m for m in doc["markers"] if m["name"] == "Fos")
    _require("k_robust" not in fos, "the deploy invented a k_robust for Fos")
    _require(doc["k_robust"] == 3.0, f"global k_robust changed to {doc['k_robust']!r}")
    _require("dim TdT was being missed" in (proj / "pipeline.yml").read_text(),
             "the deploy dropped the comment explaining why TdT's k differs")

    rep2 = sp.sync_project(proj)
    _require(rep2["config"]["already_complete"], "a second deploy was not a no-op")
    return "TdT k=2.5 preserved with its comment; only detection_threshold added; idempotent"


@check("deploy_skips_nosync", "deploy",
       "scratch fixtures are not enumerated as projects", pins="f21c6b1")
def _deploy_skips_nosync(ctx: Ctx) -> str:
    """scratchpad/ held two project-SHAPED test fixtures, and --all listed 7 projects
    where 5 existed. A deploy could have written into a fixture; worse, a later
    analysis could have rolled one up as if it were an animal."""
    root = ctx.tmp / "tree"
    real, fixture, archived = root / "real", root / "scratch fixture", root / "_archive" / "old"
    for d in (real, fixture, archived):
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.qpproj").write_text("{}")
    (fixture / sp.NOSYNC_MARKER).touch()

    found = sp.find_projects(root)
    _require(real in found, "a real project was not found")
    _require(fixture not in found,
             f"a directory carrying {sp.NOSYNC_MARKER} was enumerated as a project")
    _require(archived not in found, "an _archive/ project was enumerated")
    return f"1 of 3 project-shaped dirs enumerated ({sp.NOSYNC_MARKER} + _archive skipped)"


@check("deploy_byte_identical", "deploy", "deployed groovy matches the source exactly")
def _deploy_byte_identical(ctx: Ctx) -> str:
    sp.sync_project(ctx.fresh)
    srcs = sorted(sp.SRC_SCRIPTS.glob("*.groovy"))
    _require(srcs, "no groovy scripts in the repo source directory")
    for src in srcs:
        tgt = ctx.fresh / "scripts" / src.name
        _require(tgt.is_file(), f"{src.name} was not deployed")
        _require(tgt.read_bytes() == src.read_bytes(), f"{src.name} differs from source")
    return f"{len(srcs)} scripts byte-identical"


# ---------------------------------------------------------------------------
# Checks -- the config contract (validate_pipeline_config.py)
# ---------------------------------------------------------------------------
@check("config_validates", "deploy", "the deployed config passes the validator")
def _config_validates(ctx: Ctx) -> str:
    config = vpc.load_config(ctx.fresh / "pipeline.yml")
    contract = vpc.derive_contract(config)
    _require(contract["measurement_keys"]["TdT"] == "Cell: AF568-T2 mean (bg-sub)",
             f"whole-cell TdT resolved to {contract['measurement_keys']['TdT']!r}")
    _require(contract["measurement_keys"]["Fos"] == "Nucleus: AF488-T3 mean (bg-sub)",
             f"nuclear Fos resolved to {contract['measurement_keys']['Fos']!r}")
    _require("Double+" in contract["class_vocabulary"],
             "Double+ absent from a two-marker contract")
    return "contract derived: " + ", ".join(contract["class_vocabulary"])


@check("config_per_marker_k", "classify",
       "a per-marker k_robust override validates", pins="a4f8c16")
def _config_per_marker_k(ctx: Ctx) -> str:
    good = ctx.tmp / "k_ok.yml"
    good.write_text(_pipeline_yml(per_marker_k=2.5, with_detection_threshold=True))
    doc = vpc.load_config(good)
    tdt = next(m for m in doc["markers"] if m["name"] == "TdT")
    _require(tdt["k_robust"] == 2.5, "the validator dropped the per-marker k_robust")

    bad = ctx.tmp / "k_bad.yml"
    bad.write_text(_pipeline_yml(per_marker_k=-1.0, with_detection_threshold=True))
    _expect_actionable(lambda: vpc.load_config(bad), (SystemExit,),
                       "k_robust", "a negative per-marker k_robust")
    return "2.5 accepted; a negative k refused by name"


@check("config_bad_key_named", "deploy", "a malformed config names the offending key")
def _config_bad_key_named(ctx: Ctx) -> str:
    bad = ctx.tmp / "bad.yml"
    doc = yaml.safe_load(_pipeline_yml(with_detection_threshold=True))
    doc["markers"][1]["compartment"] = "cytoplasm"     # near-miss for "cytoplasmic"
    bad.write_text(yaml.safe_dump(doc, sort_keys=False))
    _expect_actionable(lambda: vpc.load_config(bad), (SystemExit,),
                       "compartment", "an invalid compartment")

    missing = ctx.tmp / "missing.yml"
    doc2 = yaml.safe_load(_pipeline_yml(with_detection_threshold=True))
    del doc2["detection_threshold"]
    missing.write_text(yaml.safe_dump(doc2, sort_keys=False))
    _expect_actionable(lambda: vpc.load_config(missing), (SystemExit,),
                       "detection_threshold", "a config with no detection_threshold")
    return "invalid compartment and missing detection_threshold both named"


# ---------------------------------------------------------------------------
# Checks -- stage `calibrate`: a fresh project must be calibratable
# ---------------------------------------------------------------------------
@check("fresh_slice_discovery", "calibrate",
       "a fresh project can be calibrated", pins="fbcb888")
def _fresh_slice_discovery(ctx: Ctx) -> str:
    """find_slices groups EXPORT tables, which only exist after detection. On a new
    project it found nothing and the notebook hit slices[0] -> IndexError: you could
    not pick a slice to detect on until a detection had been exported for it."""
    _expect_actionable(lambda: cc.find_slices(ctx.fresh), (FileNotFoundError,),
                       "results", "find_slices on a project with no results/")

    slices, from_exports = cc.find_candidate_slices(ctx.fresh)
    _require(not from_exports, "from_exports should be False when nothing is exported")
    _require(len(slices) == 2, f"expected 2 candidate slices, got {len(slices)}")

    first = slices[0]                       # the exact operation that used to raise
    _require(first.label == "SMOKE_s1", f"first candidate is {first.label!r}")
    _require(not first.complete, "a fallback slice must not claim to have tables")
    _require(first.regions_tsv is None and first.percell_tsv is None,
             "a fallback slice carries table paths it cannot have")
    return f"2 slices from project entries, slices[0] = {first.label}"


@check("fresh_label_roundtrip", "calibrate", "entry name -> slice label is invertible")
def _fresh_label_roundtrip(ctx: Ctx) -> str:
    names = cc.project_image_names(ctx.fresh)
    _require(names, "no image entries read from project.qpproj")
    for name in names:
        label = cc.label_from_entry_name(name)
        _require(name.endswith(label),
                 f"label {label!r} does not match the endswith() lookup callers use on {name!r}")
    _require(cc.label_from_entry_name("bare_name") == "bare_name",
             "an entry name with no ' - ' separator was mangled")
    return f"{len(names)} entries, plus the no-separator case"


@check("fresh_export_status", "export", "missing exports print the re-export command")
def _fresh_export_status(ctx: Ctx) -> str:
    status = cc.region_table_status(ctx.fresh)
    _require(not status["ready"], "region_table_status called a fresh project ready")
    _require(not status["region_area_only"], "no tables at all, yet reported area-only")
    hint = status["hint"]
    _require("03_export_region_table.groovy" in hint,
             f"the hint does not name the script that fixes it: {hint!r}")
    return "not ready, hint names 03_export_region_table.groovy"


@check("fresh_tune_surface", "tune", "the knob table reads a fresh project")
def _fresh_tune_surface(ctx: Ctx) -> str:
    """cockpit_tune reads BraiAn.yml and pipeline.yml. It must not need a results/
    or a previous tuning round to show the operator the knobs."""
    values = {k.name: ctune._current_value(ctx.fresh, k) for k in ctune.KNOBS if k.settable}
    _require(values["sigmaMicrons"] == 2.0, f"sigmaMicrons read as {values['sigmaMicrons']!r}")
    _require(values["k_robust"] == 3.0, f"k_robust read as {values['k_robust']!r}")

    before = (ctx.fresh / "BraiAn.yml").read_text()
    ctune.apply_sets(ctx.fresh, ["sigmaMicrons=2.5"])
    after = (ctx.fresh / "BraiAn.yml").read_text()
    _require(ctune._current_value(ctx.fresh, ctune.KNOBS_BY_NAME["sigmaMicrons"]) == 2.5,
             "--set did not take")
    _require("# split-vs-merge control" in after,
             "the writer dropped the inline comment carrying the knob's rationale")
    _require("classifiers: []" in after and "ON PURPOSE" in after,
             "the writer dropped the empty-classifiers block or its comment")
    _require(len(after.splitlines()) == len(before.splitlines()),
             "the writer changed the line count -- it should touch one scalar token")
    ctune.apply_sets(ctx.fresh, ["sigmaMicrons=2.0"])
    return "knobs read from both files; --set preserved every comment"


# ---------------------------------------------------------------------------
# Checks -- stages `rollup_region` / `rollup_animal` / `chance` with no data
# ---------------------------------------------------------------------------
@check("fresh_readouts_refuse", "rollup_region",
       "readouts on a fresh project refuse by name", pins="641b5dd")
def _fresh_readouts_refuse(ctx: Ctx) -> str:
    detail = []
    detail.append(_expect_actionable(
        lambda: creg.build_readout(ctx.fresh), (FileNotFoundError,),
        "region_table", "build_readout with no exports"))
    detail.append(_expect_actionable(
        lambda: ca.rollup_animal(ctx.fresh), (FileNotFoundError, ValueError),
        "region_table", "rollup_animal with no exports"))
    detail.append(_expect_actionable(
        lambda: lc.load_percell(ctx.fresh), (FileNotFoundError,),
        "percell_export", "local_chance.load_percell with no exports"))
    return f"{len(detail)} readouts refused, each naming the table it wants"


@check("fresh_gates_report_na", "qc", "QC gates report N/A rather than crashing")
def _fresh_gates_report_na(ctx: Ctx) -> str:
    """Advisory, not refusal: a gate with no data says so and the run continues."""
    slices, _ = cc.find_candidate_slices(ctx.fresh)
    results = cc.run_all_gates(slices[0], ctx.fresh)
    _require(results, "run_all_gates returned nothing on a fallback slice")
    for r in results:
        _require(r.basis in (cc.ANATOMICAL, cc.INTERNAL, cc.ASSUMED),
                 f"gate {r.name!r} carries no evidence tier ({r.basis!r}) -- an "
                 f"unattributed number reads as authority it has not earned")
        _require(r.status in (cc.PASS, cc.FLAG, cc.NA),
                 f"gate {r.name!r} returned status {r.status!r}")
    na = [r.name for r in results if r.status == cc.NA]
    _require(na, "no gate reported N/A on a slice with no per-cell table -- one of them "
                 "invented a verdict from data it does not have")
    return (f"{len(results)} gates ran on a slice with no tables, each tagged with its "
            f"tier; {len(na)} reported N/A")


# ---------------------------------------------------------------------------
# Checks -- the happy path, and session-vs-animal identity
# ---------------------------------------------------------------------------
@check("happy_path", "rollup_animal", "the chain produces numbers once exports exist")
def _happy_path(ctx: Ctx) -> str:
    df = creg.build_readout(ctx.exported, regions=["LA", "CA1"])
    _require(not df.empty, "build_readout produced no rows from real tables")
    roll = ca.rollup_animal(ctx.exported, regions=["LA", "CA1"])
    _require(not roll.empty, "rollup_animal produced no rows")
    both = roll[roll["hemisphere"] == "both"]
    _require(not both.empty, "no pooled ('both') rows in the rollup")
    _require("reactivation_rate" in roll.columns, "the metric family was not computed")
    return f"{len(df)} per-slice rows -> {len(roll)} animal rows, metrics present"


@check("sessions_are_one_animal", "rollup_animal",
       "imaging sessions pool into one animal", pins="2415950")
def _sessions_are_one_animal(ctx: Ctx) -> str:
    """The animal is derived from the slice-label prefix, so M5's three sessions
    (M5a/M5b/M5c) became THREE animals and per-region counts were never pooled --
    STR and HY each appeared twice, which reads as duplicate regions in a figure.
    `animal:` in pipeline.yml is what fixes it."""
    labels = ["M5a_s1", "M5b_s1", "M5c_s1"]

    undeclared = write_exported_project(ctx.tmp, "sessions undeclared", labels, animal=None)
    n_split = ca.rollup_animal(undeclared, regions=["LA"])["animal"].nunique()
    _require(n_split == 3,
             f"the fixture does not reproduce the bug: {n_split} animals from 3 session "
             f"prefixes with no `animal:` declared, expected 3")

    declared = write_exported_project(ctx.tmp, "sessions declared", labels, animal="M5")
    roll = ca.rollup_animal(declared, regions=["LA"])
    animals = sorted(roll["animal"].unique())
    _require(animals == ["M5"], f"three sessions rolled up as {animals}")

    la = roll[(roll["region_acronym"] == "LA") & (roll["hemisphere"] == "L")]
    _require(len(la) == 1, f"LA/L appears {len(la)} times -- sessions were not pooled")
    _require(int(la["DAPI_count"].iloc[0]) == 330,
             f"pooled LA/L counts {int(la['DAPI_count'].iloc[0])} anchors, expected "
             f"100+110+120=330 -- the sessions' counts were not summed")

    # Sessions restart their slice numbering, so all three sections here are `_s1`.
    # n_slices must still see three: it is the provenance of the pooled number.
    _require(int(la["n_slices"].iloc[0]) == 3,
             f"pooled LA covers n_slices={int(la['n_slices'].iloc[0])}, expected 3 -- "
             f"three sections numbered s1 collapsed into one")
    return "3 sessions -> 1 animal, counts summed (330), n_slices=3 (3 animals undeclared)"


# ---------------------------------------------------------------------------
# Checks -- source lints over the Groovy stages (cannot run headless)
# ---------------------------------------------------------------------------
def _groovy_writes_without_mkdirs(source: str) -> list[str]:
    """Call sites that build a path into a project subdirectory but never ensure it.

    Returns the offending lines. Matching is on the assigned variable so a guard for
    a DIFFERENT file two lines down cannot be mistaken for this one's.
    """
    import re
    lines = source.splitlines()
    offenders = []
    pat = re.compile(r"(?:def|var)\s+(\w+)\s*=\s*new File\(\s*buildPathInProject\(")
    for i, line in enumerate(lines):
        m = pat.search(line)
        if not m:
            continue
        var = m.group(1)
        window = "\n".join(lines[i:i + _MKDIRS_WINDOW])
        if f"{var}.getParentFile().mkdirs()" not in window:
            offenders.append(f"line {i + 1}: {line.strip()}")
    return offenders


@check("groovy_results_mkdirs", "export",
       "every Groovy write ensures its directory", pins="641b5dd")
def _groovy_results_mkdirs(ctx: Ctx) -> str:
    """On a fresh project results/ does not exist until something makes it. Every
    stage wrote into it and only calibrate_threshold.groovy created it -- so a batch
    run (which starts at detection, not calibration) failed at the first write,
    AFTER paying for detection."""
    scanned, offenders = 0, []
    for g in sorted(ctx.groovy_dir.glob("*.groovy")):
        src = g.read_text()
        if "buildPathInProject" not in src:
            continue
        scanned += 1
        offenders += [f"{g.name} {o}" for o in _groovy_writes_without_mkdirs(src)]
    _require(scanned > 0, f"no Groovy scripts with project writes found in {ctx.groovy_dir}")
    _require(not offenders,
             "Groovy writes into a project subdirectory without creating it first "
             "(fails on a fresh project):\n      " + "\n      ".join(offenders))
    return f"{scanned} scripts scanned, every write guarded"


@check("groovy_classifier_dir", "classify",
       "02_detect_classify creates its classifier directory", pins="624a705")
def _groovy_classifier_dir(ctx: Ctx) -> str:
    """QuPath only creates classifiers/object_classifiers/ once a classifier has been
    saved from the GUI. On a fresh project the script died there -- after detection
    had already run, so the operator lost the stage-2/3 half of the run."""
    path = ctx.groovy_dir / "02_detect_classify.groovy"
    _require(path.is_file(), f"{path} not found")
    lines = path.read_text().splitlines()
    # Anchor on the line that BUILDS the path, not the comment above it explaining why:
    # a comment survives a refactor that drops the mkdirs.
    hits = [i for i, ln in enumerate(lines)
            if "classifiers/object_classifiers" in ln and "new File(" in ln]
    _require(hits, "02_detect_classify.groovy no longer builds a classifiers/"
                   "object_classifiers path -- has the classifier write moved?")
    for i in hits:
        window = "\n".join(lines[i:i + _MKDIRS_WINDOW])
        _require("mkdirs()" in window,
                 f"02_detect_classify.groovy line {i + 1} builds classifiers/"
                 f"object_classifiers/ but never creates it -- QuPath only makes that "
                 f"directory once a classifier has been saved from the GUI, so this "
                 f"throws FileNotFoundException on a fresh project, AFTER detection has "
                 f"already run.")
    return f"{len(hits)} call site(s), each creating the directory before writing"


# ---------------------------------------------------------------------------
# Checks -- stage `mip` (czi_mip.py), no CZI required
# ---------------------------------------------------------------------------
class _StubBBox:
    def __init__(self, x: int, y: int, w: int = 100, h: int = 100) -> None:
        self.x, self.y, self.w, self.h = x, y, w, h


class _StubCzi:
    """Just enough of a CziFile for the scene pre-flight: it reads bounding boxes
    and nothing else."""

    def __init__(self, n: int) -> None:
        self._boxes = {i: _StubBBox(i * 500, 0) for i in range(n)}

    def get_all_mosaic_scene_bounding_boxes(self) -> dict:
        return self._boxes


@check("czi_single_scene", "mip", "a single-scene CZI is accepted", pins="6df29b9")
def _czi_single_scene(ctx: Ctx) -> str:
    """A hard `n_scenes < 2` guard rejected any one-section acquisition, which blocked
    M5's single-scene hippocampus session. Only a genuinely empty file is refusable."""
    import czi_mip

    bboxes, overlaps = czi_mip._preflight_scenes(_StubCzi(1))
    _require(len(bboxes) == 1, f"single-scene pre-flight returned {len(bboxes)} boxes")
    _require(not overlaps, "a lone scene cannot overlap anything")

    _expect_actionable(lambda: czi_mip._preflight_scenes(_StubCzi(0)), (SystemExit,),
                       "No scenes", "a CZI with zero scenes")
    return "1 scene converted as s1; 0 scenes still refused"


@check("czi_scene_tile_count", "mip",
       "--scenes does not break tile counting", pins="f9f79f9")
def _czi_scene_tile_count(ctx: Ctx) -> str:
    """_scene_tile_count aligns a per-scene dims dict BY POSITION and trusts that only
    when the list length matches the scene count. --scenes overwrote the key list with
    the subset, so every tile count came back -1 and the run aborted. The helper was
    right to refuse; the caller was at fault -- so assert both halves."""
    import czi_mip

    dims = [{"M": (0, 100 + 10 * i)} for i in range(6)]
    keys = list(range(6))
    got = czi_mip._scene_tile_count(dims, keys, 2)
    _require(got == 120, f"full key list aligned to {got}, expected 120")
    filtered = czi_mip._scene_tile_count(dims, [2], 2)
    _require(filtered == -1,
             f"a filtered key list returned {filtered} -- it must refuse (-1) rather "
             f"than report a tile count for the wrong scene")

    src = (ctx.repo / "czi_mip.py").read_text()
    _require("all_scene_keys" in src,
             "czi_mip.py no longer keeps a full scene-key list separate from the "
             "filtered iteration list -- --scenes will mis-align tile counts again")
    return "full list -> 120; filtered list -> -1; caller keeps all_scene_keys"


# ---------------------------------------------------------------------------
# Checks -- portability (this machine is not the only machine)
# ---------------------------------------------------------------------------
def _home_path_literals(text: str) -> list[str]:
    """Lines carrying an absolute path with a username baked into it.

    `Path.home()` and `$HOME` are fine -- they resolve per machine. A literal
    `/home/<someone>/` is not: it fails immediately on any other box, and in a
    docstring it teaches the habit to whoever reads it next.
    """
    import re
    pat = re.compile(r"/home/[A-Za-z0-9._-]+/")
    return [ln.strip() for ln in text.splitlines() if pat.search(ln)]


@check("portable_paths", "deploy", "no source carries a hardcoded home directory")
def _portable_paths(ctx: Ctx) -> str:
    files = (sorted((ctx.repo / "scripts").glob("*.py"))
             + sorted((ctx.repo / "scripts").glob("*.groovy"))
             + [ctx.repo / "czi_mip.py", ctx.repo / "czi_hybrid_mip.py",
                ctx.repo / "run_pipeline.py"])
    offenders = []
    for f in files:
        if not f.is_file():
            continue
        offenders += [f"{f.name}: {ln[:90]}" for ln in _home_path_literals(f.read_text())]

    # Notebook SOURCE only. Outputs are a transcript of a past run on a real machine
    # and legitimately contain that machine's paths; rewriting them would be falsifying
    # a record for the sake of a lint.
    for nb in sorted((ctx.repo / "notebooks").glob("*.ipynb")):
        doc = json.loads(nb.read_text())
        for i, cell in enumerate(doc.get("cells", [])):
            src = "".join(cell.get("source", []))
            offenders += [f"{nb.name} cell {i}: {ln[:90]}" for ln in _home_path_literals(src)]

    _require(not offenders,
             "absolute paths with a username in them (these fail on any other machine, "
             "and a new user's first act should not be editing them):\n      "
             + "\n      ".join(offenders))
    return f"{len(files)} source files + notebook cells clean"


@check("qupath_bin_env", "qc", "QUPATH_BIN is overridable by environment")
def _qupath_bin_env(ctx: Ctx) -> str:
    src = (ctx.repo / "scripts" / "cockpit_checks.py").read_text()
    _require('os.environ.get("QUPATH_BIN")' in src,
             "cockpit_checks no longer reads $QUPATH_BIN -- QuPath's location is "
             "machine-specific and must not be a literal")
    probe = ("import sys; sys.path.insert(0, 'scripts'); "
             "import cockpit_checks as cc; print(cc.QUPATH_BIN)")
    env = dict(os.environ, QUPATH_BIN="/opt/QuPath/bin/QuPath")
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                         cwd=str(ctx.repo), env=env, timeout=120)
    _require(out.stdout.strip() == "/opt/QuPath/bin/QuPath",
             f"$QUPATH_BIN was ignored; got {out.stdout.strip()!r}")
    _require(str(cc.DEFAULT_QUPATH_BIN).startswith(str(Path.home())),
             f"the default QuPath path is not under the running user's home "
             f"({cc.DEFAULT_QUPATH_BIN})")
    return "default under $HOME, $QUPATH_BIN wins"


@check("notebooks_discover_repo", "qc", "notebooks find the repo instead of hardcoding it")
def _notebooks_discover_repo(ctx: Ctx) -> str:
    """The setup cell is executed from the notebooks/ directory, the way JupyterLab
    runs it -- asserting the source merely CONTAINS a discovery helper would not
    prove the helper works."""
    checked = []
    for nb in sorted((ctx.repo / "notebooks").glob("*.ipynb")):
        doc = json.loads(nb.read_text())
        setup = next((c for c in doc["cells"]
                      if c.get("cell_type") == "code" and "PARAMS" in "".join(c["source"])), None)
        _require(setup is not None, f"{nb.name} has no PARAMS setup cell")
        src = "\n".join(ln for ln in "".join(setup["source"]).splitlines()
                        if not ln.strip().startswith("%"))     # drop IPython magics
        _require("_find_repo_root" in src,
                 f"{nb.name}'s setup cell does not discover the repo root")
        probe = ctx.tmp / f"probe_{nb.stem}.py"
        probe.write_text(src + "\nprint('REPO=', REPO)\n")
        out = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True,
                             cwd=str(ctx.repo / "notebooks"),
                             env=dict(os.environ, MPLBACKEND="Agg"), timeout=300)
        _require(out.returncode == 0,
                 f"{nb.name}'s setup cell failed when run from notebooks/: "
                 f"{(out.stderr or out.stdout).strip().splitlines()[-1:]}")
        _require(f"REPO= {ctx.repo}" in out.stdout,
                 f"{nb.name} resolved the repo root to something unexpected: {out.stdout!r}")
        checked.append(nb.name)
    return f"{len(checked)} notebooks resolve REPO from notebooks/ and run their setup cell"


# ---------------------------------------------------------------------------
# Checks -- install verification
# ---------------------------------------------------------------------------
def _self_testable_modules(repo: Path) -> list[Path]:
    """Every sibling module that ships its own --self-test, smoke_test excluded (it
    would recurse)."""
    out = []
    for p in sorted(repo.glob("scripts/*.py")) + [repo / "czi_mip.py"]:
        if p.name == Path(__file__).name or not p.is_file():
            continue
        if '"--self-test"' in p.read_text():
            out.append(p)
    return out


@check("sibling_self_tests", "tune", "every module's own --self-test passes", slow=True)
def _sibling_self_tests(ctx: Ctx) -> str:
    if not ctx.run_self_tests:
        return "skipped (--no-self-tests)"
    mods = _self_testable_modules(ctx.repo)
    _require(mods, "no modules with a --self-test were found")
    failed = []
    for m in mods:
        proc = subprocess.run([sys.executable, str(m), "--self-test"],
                              capture_output=True, text=True, cwd=str(ctx.repo), timeout=600)
        if proc.returncode != 0:
            tail = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
            failed.append(f"{m.name} (exit {proc.returncode}): {' / '.join(tail)}")
    _require(not failed, "module self-tests failed:\n      " + "\n      ".join(failed))
    return f"{len(mods)} modules, all green"


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def build_context(base: Path, run_self_tests: bool = True) -> Ctx:
    fresh = write_fresh_project(base)
    exported = write_exported_project(base, "exported project", ["SMOKE_s1", "SMOKE_s2"],
                                      animal="SMOKE")
    return Ctx(repo=REPO_ROOT, tmp=base, fresh=fresh, exported=exported,
               groovy_dir=REPO_ROOT / "scripts", run_self_tests=run_self_tests)


def run_checks(ctx: Ctx, checks: list[Check] | None = None) -> list[tuple[Check, bool, str]]:
    """Run every check, never stopping at the first failure -- a run that reports one
    bug at a time is the workflow this exists to replace."""
    results = []
    for c in (checks if checks is not None else CHECKS):
        try:
            detail = c.fn(ctx)
            results.append((c, True, detail))
        except SmokeFailure as exc:
            results.append((c, False, str(exc)))
        except Exception as exc:  # noqa: BLE001 -- an unexpected type IS the finding
            results.append((c, False, f"unexpected {type(exc).__name__}: {exc}"))
    return results


def print_results(results: list[tuple[Check, bool, str]]) -> None:
    stage = None
    for c, ok, detail in results:
        if c.stage != stage:
            stage = c.stage
            print(f"\n  stage: {stage}")
        pin = f"  [pins {c.pins}]" if c.pins else ""
        print(f"    {PASS if ok else FAIL}  {c.title}{pin}")
        print(f"          {detail}")


def main() -> int:
    args = parse_args()
    if args.self_test:
        return _self_test()

    if args.list:
        print("Checks:")
        for c in CHECKS:
            pin = f"  (pins {c.pins})" if c.pins else ""
            print(f"  {c.check_id:<26} [{c.stage}] {c.title}{pin}")
        print(f"\n  {len(CHECKS)} checks, "
              f"{sum(1 for c in CHECKS if c.pins)} pinning a specific regression")
        return 0

    print("Fresh-project smoke test")
    print(f"  repo: {REPO_ROOT}")

    tmp = Path(tempfile.mkdtemp(prefix="smoke_"))
    try:
        ctx = build_context(tmp, run_self_tests=not args.no_self_tests)
        print(f"  built a bare project at {ctx.fresh}")
        results = run_checks(ctx)
        print_results(results)

        failed = [(c, d) for c, ok, d in results if not ok]
        print(f"\n  {len(results) - len(failed)}/{len(results)} checks passed")
        if failed:
            print("\nFAILED:")
            for c, d in failed:
                print(f"  {c.check_id}: {d}")
            print("\nsmoke test FAILED")
            return 1
        print("\nsmoke test PASSED -- a project with no prior state runs the chain, "
              "and every stage that cannot run says why in terms an operator can act on.")
        return 0
    finally:
        if args.keep:
            args.keep.parent.mkdir(parents=True, exist_ok=True)
            if args.keep.exists():
                shutil.rmtree(args.keep)
            shutil.move(str(tmp), str(args.keep))
            print(f"  kept the synthetic project at {args.keep}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Self-test -- do these checks have teeth?
# ---------------------------------------------------------------------------
def _self_test() -> int:
    """Assert the checks can go RED.

    A smoke test that passes is worth nothing until you know it is capable of
    failing. Each case below breaks exactly the thing one check watches, and
    asserts THAT check (not merely some check) reports it.
    """
    print("Running --self-test (each case breaks one thing and asserts the check catches it)...")
    ok = True

    def case(name: str, cond: bool, note: str = "") -> None:
        nonlocal ok
        print(f"  {PASS if cond else FAIL}  {name}" + (f" -- {note}" if note else ""))
        ok = ok and cond

    def run_one(check_id: str, ctx: Ctx) -> tuple[bool, str]:
        c = next(c for c in CHECKS if c.check_id == check_id)
        (_c, passed, detail), = run_checks(ctx, [c])
        return passed, detail

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)

        # Baseline: the real repo must be green, or nothing below means anything.
        ctx = build_context(base / "clean", run_self_tests=False)
        results = run_checks(ctx)
        reds = [c.check_id for c, passed, _ in results if not passed]
        case("baseline: every check passes against the real repo", not reds,
             f"red: {reds}" if reds else "")

        # 1. An unguarded Groovy write must be caught.
        broken = base / "broken_groovy"
        broken.mkdir()
        for g in (REPO_ROOT / "scripts").glob("*.groovy"):
            shutil.copy2(g, broken / g.name)
        tgt = broken / "03_export_region_table.groovy"
        tgt.write_text(tgt.read_text().replace(
            "percellFile.getParentFile().mkdirs()", "// removed by --self-test"))
        bad_ctx = build_context(base / "c1", run_self_tests=False)
        bad_ctx.groovy_dir = broken
        passed, detail = run_one("groovy_results_mkdirs", bad_ctx)
        case("an unguarded results/ write is caught", not passed and "03_export" in detail,
             detail if passed else "")

        # 2. A missing classifier-directory mkdirs must be caught.
        tgt2 = broken / "02_detect_classify.groovy"
        src2 = tgt2.read_text()
        i = src2.find("classifiers/object_classifiers")
        tgt2.write_text(src2[:i] + src2[i:].replace("mkdirs()", "isDirectory()", 1))
        passed, _ = run_one("groovy_classifier_dir", bad_ctx)
        case("a missing classifier-directory mkdirs is caught", not passed)

        # 3. The bare-fixture guard must notice a fixture that is not bare.
        ctx3 = build_context(base / "c3", run_self_tests=False)
        (ctx3.fresh / "results").mkdir()
        passed, _ = run_one("fixture", ctx3)
        case("a fixture that is not actually fresh is caught", not passed)

        # 4. A deploy that OVERWRITES pipeline.yml instead of merging into it -- the
        #    exact regression the merge-only rule exists to prevent.
        ctx4 = build_context(base / "c4", run_self_tests=False)
        real_sync_config = sp.sync_config
        try:
            def _clobber(project: Path, dry_run: bool = False) -> dict:
                if not dry_run:
                    shutil.copy2(sp.ROOT_CONFIG, project / "pipeline.yml")
                return {"created": False, "added_blocks": ["detection_threshold"],
                        "already_complete": False}
            sp.sync_config = _clobber
            passed, detail = run_one("deploy_preserves_tuning", ctx4)
            case("a deploy that overwrites pipeline.yml is caught",
                 not passed and "k_robust" in detail, detail if passed else "")
        finally:
            sp.sync_config = real_sync_config

        # 5. The nosync check must notice a fixture being enumerated.
        real_find = sp.find_projects
        try:
            sp.find_projects = lambda root=sp.REPO_ROOT: sorted(
                p.parent for p in Path(root).rglob("project.qpproj"))
            passed, _ = run_one("deploy_skips_nosync", build_context(base / "c5",
                                                                    run_self_tests=False))
            case("enumerating a .pipeline-nosync fixture is caught", not passed)
        finally:
            sp.find_projects = real_find

        # 6. Session-vs-animal: with the declaration removed, pooling must fail.
        ctx6 = build_context(base / "c6", run_self_tests=False)
        real_writer = globals()["write_exported_project"]
        try:
            globals()["write_exported_project"] = (
                lambda b, n, l, animal: real_writer(b, n, l, None))
            passed, detail = run_one("sessions_are_one_animal", ctx6)
            case("three sessions counted as three animals is caught",
                 not passed and "M5" in detail, detail if passed else "")
        finally:
            globals()["write_exported_project"] = real_writer

        # 7. Portability: a repo carrying a hardcoded home directory must be caught,
        #    as must a cockpit_checks with QUPATH_BIN back as a literal and a notebook
        #    that hardcodes its sys.path.
        # The poison path is ASSEMBLED at runtime, never written as a literal: this
        # file is itself inside scripts/, so a literal here would make portable_paths
        # fail against the real repo -- as it correctly did the first time.
        poison = "/" + "home/" + "someone/" + "Analysis"
        fake = base / "fake_repo"
        (fake / "scripts").mkdir(parents=True)
        (fake / "notebooks").mkdir(parents=True)
        (fake / "scripts" / "poison.py").write_text(f'BIN = "{poison}/tools/QuPath"\n')
        (fake / "scripts" / "cockpit_checks.py").write_text(
            f'from pathlib import Path\nQUPATH_BIN = Path("{poison}/QuPath")\n')
        (fake / "notebooks" / "x.ipynb").write_text(json.dumps({"cells": [{
            "cell_type": "code",
            "source": [f'PARAMS = {{"project": "{poison}/proj"}}\n',
                       'import sys\n',
                       f'sys.path.insert(0, "{poison}/scripts")\n'],
        }]}))
        ctx7 = build_context(base / "c7", run_self_tests=False)
        ctx7.repo = fake
        passed, detail = run_one("portable_paths", ctx7)
        case("a hardcoded home directory in source is caught",
             not passed and "poison.py" in detail, detail if passed else "")
        passed, detail = run_one("qupath_bin_env", ctx7)
        case("QUPATH_BIN back as a literal is caught",
             not passed and "QUPATH_BIN" in detail, detail if passed else "")
        passed, detail = run_one("notebooks_discover_repo", ctx7)
        case("a notebook that hardcodes its sys.path is caught",
             not passed and "discover" in detail, detail if passed else "")

        # 8. _expect_actionable must reject a bare IndexError as loudly as a success.
        def bare() -> None:
            [][0]
        try:
            _expect_actionable(bare, (FileNotFoundError,), "results", "a bare raiser")
            case("a bare IndexError is reported as the bug class", False, "not caught")
        except SmokeFailure as exc:
            case("a bare IndexError is reported as the bug class",
                 "IndexError" in str(exc) and "bug class" in str(exc))
        try:
            _expect_actionable(lambda: None, (FileNotFoundError,), "results", "a no-op")
            case("silently succeeding with no data is caught", False, "not caught")
        except SmokeFailure as exc:
            case("silently succeeding with no data is caught", "SUCCEEDED" in str(exc))

        # 9. An unhelpful message (right exception, no path named) must still fail.
        def vague() -> None:
            raise FileNotFoundError("something went wrong")
        try:
            _expect_actionable(vague, (FileNotFoundError,), "results", "a vague raiser")
            case("an exception that names nothing is caught", False, "not caught")
        except SmokeFailure as exc:
            case("an exception that names nothing is caught", "does not name" in str(exc))

    if ok:
        print("\nself-test PASSED: every check was shown to fail on a deliberately broken "
              "input, so a green run means something.")
        return 0
    print("\nself-test FAILED: at least one check could not be made to fail, which means "
          "it is not actually testing what it claims.")
    return 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--no-self-tests", action="store_true",
                   help="skip running every sibling module's own --self-test (the slow part)")
    p.add_argument("--keep", type=Path, default=None,
                   help="move the synthetic project here instead of deleting it")
    p.add_argument("--list", action="store_true", help="list the checks and exit")
    p.add_argument("--self-test", action="store_true",
                   help="prove the checks can fail, then exit")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(main())
