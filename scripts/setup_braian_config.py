#!/usr/bin/env python3
"""setup_braian_config.py -- create or check a project's BraiAn.yml against its images.

WHY THIS EXISTS
    `sync_project.py` deploys the Groovy stages and merges pipeline.yml, but it cannot
    touch BraiAn.yml: that file is PER-ACQUISITION. Its `requestedPixelSizeMicrons` has
    to equal the images' own PhysicalSizeX exactly, or BraiAnDetect resamples and every
    nucleus area comes out wrong -- which silently corrupts the area gate, the
    min/maxArea filters, and every density.

    So the file has been copied by hand, and on 2026-08-04 that failed exactly the way
    hand-copying fails: M5 Hipp3 (0.690535 um/px) was given M3 Hipp2's config
    (0.460357), a 33% error, caught only because calibration refused. The runbook had
    even named the wrong project as the copy source.

    This module removes the guess. It reads the facts off the images, finds which
    existing project shares this one's ACQUISITION REGIME, and either audits what is
    there or writes a correct file.

THREE WAYS IN, all of which end at the same audit
    --audit                 check the BraiAn.yml already present against the images
    --scaffold              copy the best-matching project's config and correct it
    --scaffold --template   same, but you choose the source project
    --scaffold --pixel-um   same, but you supply the number yourself

WHAT IS DERIVED VS ASKED
    Derived from the image (never guessed): pixel size, channel names, image dimensions.
    Carried from the template: every micron-denominated detection seed (sigmaMicrons,
    min/maxAreaMicrons, cellExpansionMicrons, backgroundRadiusMicrons), because those
    are judgement calls that belong to an acquisition regime, not to a file.

    Z DEPTH CANNOT BE DERIVED from a MIP -- projection already collapsed it (sizeZ=1).
    It still matters (markers are max-projected, so 4 planes samples ~3x the cell volume
    of 2), so it is asked for and recorded, never inferred.

Usage:
    python3 scripts/setup_braian_config.py --project "<dir>" --audit
    python3 scripts/setup_braian_config.py --project "<dir>" --scaffold --dry-run
    python3 scripts/setup_braian_config.py --project "<dir>" --scaffold --template "<dir>"
    python3 scripts/setup_braian_config.py --self-test
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Two pixel sizes are "the same regime" if they agree to this many significant figures.
# The projects here carry both 0.6905355 and 0.690535481770835 for the same acquisition
# -- one rounded, one full-precision -- and they must not be reported as a mismatch.
REGIME_RTOL = 1e-4


# ---------------------------------------------------------------------------
# Facts, read off the images
# ---------------------------------------------------------------------------
def _ome_facts(path: Path) -> dict[str, Any]:
    import tifffile

    with tifffile.TiffFile(str(path)) as handle:
        xml = handle.ome_metadata or ""
        shape = handle.series[0].shape
    px = re.findall(r'PhysicalSizeX="([^"]+)"', xml)
    return {
        "mip": path,
        "pixel_um": float(px[0]) if px else None,
        "channels": re.findall(r'<Channel[^>]*Name="([^"]+)"', xml),
        "shape": tuple(shape),
    }


def image_facts(project_dir: Path) -> dict[str, Any]:
    """Pixel size, channel names and dimensions, read from this project's own MIPs.

    Every MIP found is read and they must AGREE. A project whose images disagree on
    pixel size cannot have one correct BraiAn.yml, and saying so here is much cheaper
    than discovering it after a batch run.
    """
    mips = _find_mips(project_dir)
    if not mips:
        raise FileNotFoundError(
            f"no *.ome.tiff found beside or inside {project_dir}. Run czi_mip.py first "
            "(docs/runbook/00-run-a-new-dataset.md step 3).")
    facts = [_ome_facts(m) for m in mips]
    pixels = {f["pixel_um"] for f in facts if f["pixel_um"] is not None}
    channels = {tuple(f["channels"]) for f in facts}
    out = dict(facts[0])
    out["n_images"] = len(facts)
    out["pixel_disagreement"] = sorted(pixels) if len(pixels) > 1 else None
    out["channel_disagreement"] = sorted(channels) if len(channels) > 1 else None
    return out


def _find_mips(project_dir: Path) -> list[Path]:
    project_dir = Path(project_dir)
    seen: list[Path] = []
    for base in (project_dir.parent, project_dir):
        for pattern in ("mips/*.ome.tiff", "mips*/*.ome.tiff", "*.ome.tiff"):
            for p in sorted(base.glob(pattern)):
                if p not in seen:
                    seen.append(p)
    return seen


def anchor_channel(channels: list[str], anchor: str = "DAPI") -> str | None:
    for name in channels:
        if anchor.upper() in name.upper():
            return name
    return channels[-1] if channels else None


# ---------------------------------------------------------------------------
# Existing projects, grouped by regime
# ---------------------------------------------------------------------------
def _read_yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*([^#\n]+)", text, re.MULTILINE)
    return m.group(1).strip().strip('"') if m else None


def known_regimes(repo_root: Path = REPO_ROOT) -> list[dict]:
    """Every project carrying a BraiAn.yml, with the pixel size it declares."""
    out = []
    for path in sorted(repo_root.glob("*/*/BraiAn.yml")) + sorted(repo_root.glob("*/BraiAn.yml")):
        if "_archive" in path.parts or "scratchpad" in path.parts:
            continue
        text = path.read_text()
        raw = _read_yaml_scalar(text, "requestedPixelSizeMicrons")
        try:
            px = float(raw) if raw else None
        except ValueError:
            px = None
        anchor = re.search(r'^\s+-\s+name:\s*"([^"]+)"', text, re.MULTILINE)
        out.append({"project": path.parent, "config": path, "pixel_um": px,
                    "anchor": anchor.group(1) if anchor else None})
    return out


def same_regime(a: float | None, b: float | None) -> bool:
    """Do two pixel sizes describe the same acquisition regime?

    Tolerant on purpose: the same acquisition is recorded here both rounded
    (0.6905355) and at full precision (0.690535481770835), and calling those different
    would send an operator to the wrong template -- the exact failure this module
    exists to prevent.
    """
    if a is None or b is None:
        return False
    return abs(a - b) <= REGIME_RTOL * max(abs(a), abs(b))


def suggest_template(facts: dict, regimes: list[dict],
                     exclude: Path | None = None) -> dict | None:
    """The existing project whose regime matches these images. None if nothing does."""
    for r in regimes:
        if exclude is not None and Path(r["project"]) == Path(exclude):
            continue
        if same_regime(r["pixel_um"], facts["pixel_um"]):
            return r
    return None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
def audit(project_dir: Path) -> list[tuple[str, str]]:
    """Problems with this project's BraiAn.yml, as (severity, message).

    Severity is ERROR for "this will produce wrong numbers" and WARN for "check this".
    Returns an empty list when the config matches the images. Never raises on a
    mismatch -- reporting is the job; the operator decides.
    """
    project_dir = Path(project_dir)
    problems: list[tuple[str, str]] = []
    config = project_dir / "BraiAn.yml"
    if not config.is_file():
        return [("ERROR", f"no BraiAn.yml in {project_dir} -- run with --scaffold")]

    facts = image_facts(project_dir)
    text = config.read_text()

    if facts["pixel_disagreement"]:
        problems.append(("ERROR", "the project's own images disagree on pixel size: "
                                  f"{facts['pixel_disagreement']} -- one BraiAn.yml "
                                  "cannot be correct for all of them"))
    if facts["channel_disagreement"]:
        problems.append(("ERROR", "the project's images disagree on channel names: "
                                  f"{facts['channel_disagreement']}"))

    raw = _read_yaml_scalar(text, "requestedPixelSizeMicrons")
    declared = float(raw) if raw else None
    actual = facts["pixel_um"]
    if declared is None:
        problems.append(("ERROR", "BraiAn.yml declares no requestedPixelSizeMicrons"))
    elif actual is None:
        problems.append(("WARN", "images carry no PhysicalSizeX -- cannot verify the "
                                 "declared pixel size"))
    elif not same_regime(declared, actual):
        ratio = declared / actual
        problems.append(("ERROR",
                         f"pixel size MISMATCH: BraiAn.yml says {declared:g}, the images "
                         f"are {actual:.15g} ({ratio:.3f}x). BraiAnDetect will resample "
                         f"and every nucleus area will be wrong. This is the M5 Hipp3 "
                         f"failure of 2026-08-04."))
    elif declared != actual:
        problems.append(("WARN",
                         f"declared {declared:g} is a rounded form of {actual:.15g}. "
                         "Harmless numerically, but it leaves an exact comparison "
                         "unequal for no reason -- paste the full-precision value."))

    declared_anchor = re.search(r'^\s+-\s+name:\s*"([^"]+)"', text, re.MULTILINE)
    declared_anchor = declared_anchor.group(1) if declared_anchor else None
    if declared_anchor and declared_anchor not in facts["channels"]:
        problems.append(("ERROR",
                         f"BraiAn.yml detects on channel {declared_anchor!r}, which the "
                         f"images do not have. They carry: {facts['channels']}"))

    if re.search(r"^\s*threshold:\s*[0-9]", text, re.MULTILINE):
        problems.append(("WARN", "BraiAn.yml carries an absolute `threshold:` -- it is "
                                 "IGNORED for the anchor channel (pipeline.yml's "
                                 "detection_threshold wins). Delete it to avoid confusion."))
    if re.search(r"classifiers:\s*\[\s*[^\]\s]", text):
        problems.append(("ERROR", "BraiAn.yml `classifiers:` is non-empty. Classification "
                                  "happens ONLY in 02_detect_classify.groovy from "
                                  "pipeline.yml; a populated block classifies twice by "
                                  "two different rules."))
    return problems


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------
def scaffold(project_dir: Path, template: Path | None = None,
             pixel_um: float | None = None, z_planes: int | None = None,
             dry_run: bool = False) -> tuple[Path, list[str]]:
    """Write a BraiAn.yml for this project. Returns (path, list of actions taken).

    Refuses to overwrite an existing file -- correcting one is `--audit` plus a one-line
    edit, and silently replacing a config that carries tuned seeds would throw away
    exactly the judgement this pipeline is built to preserve.
    """
    project_dir = Path(project_dir)
    target = project_dir / "BraiAn.yml"
    actions: list[str] = []
    if target.exists():
        raise FileExistsError(
            f"{target} already exists -- refusing to overwrite tuned parameters. "
            f"Run --audit to check it, and edit the one line that is wrong.")

    facts = image_facts(project_dir)
    resolved_px = pixel_um if pixel_um is not None else facts["pixel_um"]
    if resolved_px is None:
        raise ValueError(
            "images carry no PhysicalSizeX and no --pixel-um was given. The pixel size "
            "is never defaulted: every micron-denominated parameter is scaled by it.")

    if template is None:
        match = suggest_template(facts, known_regimes(), exclude=project_dir)
        if match is None:
            raise ValueError(
                f"no existing project matches {resolved_px:.15g} um/px. Pass --template "
                f"to choose a source explicitly. Known regimes: "
                f"{sorted({r['pixel_um'] for r in known_regimes() if r['pixel_um']})}")
        template = Path(match["project"])
        actions.append(f"template chosen by REGIME MATCH: {template}")
    else:
        template = Path(template)
        t_px = next((r["pixel_um"] for r in known_regimes()
                     if Path(r["project"]) == template), None)
        if not same_regime(t_px, resolved_px):
            actions.append(
                f"WARNING: template {template} is {t_px} um/px but these images are "
                f"{resolved_px:.15g} -- its micron seeds were tuned at a different "
                f"sampling. Proceeding because you asked for it explicitly.")
        else:
            actions.append(f"template (you chose it): {template}")

    src = template / "BraiAn.yml"
    if not src.is_file():
        raise FileNotFoundError(f"{src} does not exist")
    text = src.read_text()

    # Correct the two things that are per-project, and ONLY those.
    text, n_px = re.subn(r"(requestedPixelSizeMicrons:\s*)[0-9.eE+-]+",
                         lambda m: f"{m.group(1)}{resolved_px:.15g}", text, count=1)
    actions.append(f"requestedPixelSizeMicrons -> {resolved_px:.15g}"
                   if n_px else "WARNING: no requestedPixelSizeMicrons found to correct")

    anchor = anchor_channel(facts["channels"])
    if anchor:
        text, n_ch = re.subn(r'(^\s+-\s+name:\s*")[^"]+(")',
                             lambda m: f"{m.group(1)}{anchor}{m.group(2)}",
                             text, count=1, flags=re.MULTILINE)
        if n_ch:
            actions.append(f"anchor channel -> {anchor}")

    header = (
        f"# BraiAn.yml -- generated by scripts/setup_braian_config.py\n"
        f"# project      : {project_dir.name}\n"
        f"# images       : {facts['n_images']} MIP(s), channels {facts['channels']}\n"
        f"# pixel size   : {resolved_px:.15g} um/px  (READ FROM THE IMAGE, not defaulted)\n"
        f"# Z planes     : {z_planes if z_planes is not None else 'NOT RECORDED -- set this by hand'}\n"
        f"#                (cannot be derived from a MIP; projection already collapsed Z,\n"
        f"#                 and it matters because markers are max-projected over it)\n"
        f"# seeds from   : {template}\n"
        f"#\n"
        f"# Verify with: python3 scripts/setup_braian_config.py --project \"{project_dir}\" --audit\n"
        f"#\n"
    )
    text = header + text

    if not dry_run:
        target.write_text(text)
        actions.append(f"wrote {target}")
    else:
        actions.append(f"[dry-run] would write {target}")
    return target, actions


def print_report(project_dir: Path) -> int:
    """Human-readable audit. Exit code 1 if anything is an ERROR."""
    project_dir = Path(project_dir)
    print(f"BraiAn.yml audit -- {project_dir}")
    try:
        facts = image_facts(project_dir)
    except FileNotFoundError as exc:
        print(f"  {exc}")
        return 1
    print(f"  images       : {facts['n_images']} MIP(s), e.g. {facts['mip'].name}")
    print(f"  pixel size   : {facts['pixel_um']!r}")
    print(f"  channels     : {facts['channels']}")
    print(f"  anchor       : {anchor_channel(facts['channels'])}")

    problems = audit(project_dir)
    if not problems:
        print("\n  OK -- BraiAn.yml matches the images.")
        return 0
    print("")
    for severity, message in problems:
        print(f"  [{severity}] {message}")
    return 1 if any(s == "ERROR" for s, _ in problems) else 0


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _self_test() -> None:
    import tempfile

    print("setup_braian_config self-test")

    # (a) Regime matching must tolerate the rounded/full-precision pair that really
    #     exists in this repo, and must NOT merge the two genuine regimes.
    assert same_regime(0.6905355, 0.690535481770835)
    assert same_regime(0.460357, 0.4603569878472219)
    assert not same_regime(0.460357, 0.6905355), "the two real regimes must stay distinct"
    assert not same_regime(None, 0.69) and not same_regime(0.69, None)
    print("  (a) regime matching: rounded == full precision, 0.46 != 0.69")

    # (b) Anchor resolution is BY NAME with a last-channel fallback, matching czi_mip.
    assert anchor_channel(["AF568-T2", "AF488-T3", "DAPI-T4"]) == "DAPI-T4"
    assert anchor_channel(["DAPI-T4", "AF488-T3"]) == "DAPI-T4"
    assert anchor_channel(["red", "green"]) == "green"
    assert anchor_channel([]) is None
    print("  (b) anchor channel by name, falls back to last")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        proj = root / "proj"
        (proj / "mips").mkdir(parents=True)

        import numpy as np
        import tifffile
        ome = ('<?xml version="1.0"?><OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06">'
               '<Image><Pixels PhysicalSizeX="0.690535481770835" PhysicalSizeY="0.690535481770835">'
               '<Channel Name="AF568-T2"/><Channel Name="AF488-T3"/><Channel Name="DAPI-T4"/>'
               '</Pixels></Image></OME>')
        tifffile.imwrite(proj / "mips" / "x_s1_MIP.ome.tiff",
                         np.zeros((3, 32, 32), dtype=np.uint16), description=ome)

        facts = image_facts(proj)
        assert facts["pixel_um"] == 0.690535481770835, facts["pixel_um"]
        assert facts["channels"] == ["AF568-T2", "AF488-T3", "DAPI-T4"]
        print(f"  (c) facts read off the image: {facts['pixel_um']!r}, "
              f"{len(facts['channels'])} channels")

        # (d) A missing config is an ERROR that names the fix.
        problems = audit(proj)
        assert problems and problems[0][0] == "ERROR" and "--scaffold" in problems[0][1]
        print("  (d) missing BraiAn.yml -> ERROR naming --scaffold")

        # (e) THE BUG: a config from the wrong regime must be caught, loudly.
        tmpl = root / "wrong_regime"
        tmpl.mkdir()
        (tmpl / "BraiAn.yml").write_text(
            'channelDetections:\n  - name: "DAPI-T4"\n    parameters:\n'
            '      requestedPixelSizeMicrons: 0.460357\n      sigmaMicrons: 2.0\n'
            '    classifiers: []\n')
        shutil.copy(tmpl / "BraiAn.yml", proj / "BraiAn.yml")
        problems = audit(proj)
        errs = [m for s, m in problems if s == "ERROR"]
        assert any("MISMATCH" in m for m in errs), problems
        assert any("1.500x" in m or "0.667x" in m for m in errs), errs
        print(f"  (e) wrong-regime config -> ERROR: {errs[0][:64]}...")

        # (f) Scaffold refuses to clobber tuned parameters.
        try:
            scaffold(proj, template=tmpl)
            raise AssertionError("scaffold overwrote an existing BraiAn.yml")
        except FileExistsError as exc:
            assert "refusing to overwrite" in str(exc)
        print("  (f) scaffold refuses to overwrite an existing config")

        # (g) Scaffolding into a clean project corrects the pixel size and says so.
        (proj / "BraiAn.yml").unlink()
        target, actions = scaffold(proj, template=tmpl, z_planes=2)
        written = target.read_text()
        assert "0.690535481770835" in written, written[:400]
        assert "0.460357" not in written, "the template's pixel size survived the copy"
        assert "sigmaMicrons: 2.0" in written, "template seeds must be preserved"
        assert "Z planes     : 2" in written
        assert any("WARNING" in a for a in actions), actions
        assert not audit(proj), audit(proj)
        print("  (g) scaffold corrects pixel size, keeps seeds, then audits clean")

        # (h) A populated classifiers block is an ERROR (one classification path).
        (proj / "BraiAn.yml").write_text(
            written.replace("classifiers: []", 'classifiers: [{name: "x"}]'))
        assert any("classifiers" in m for s, m in audit(proj) if s == "ERROR")
        print("  (h) non-empty classifiers block -> ERROR (one classification path)")

    print("\nSELF-TEST PASSED")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--project", type=Path, default=None, help="QuPath project directory")
    parser.add_argument("--audit", action="store_true", help="check the config against the images")
    parser.add_argument("--scaffold", action="store_true", help="write a new BraiAn.yml")
    parser.add_argument("--template", type=Path, default=None,
                        help="source project to copy seeds from (default: regime match)")
    parser.add_argument("--pixel-um", type=float, default=None,
                        help="override the pixel size instead of reading it from the image")
    parser.add_argument("--z-planes", type=int, default=None,
                        help="Z depth of the source acquisition (recorded, never inferred)")
    parser.add_argument("--list-regimes", action="store_true",
                        help="show every project's declared pixel size")
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    parser.add_argument("--self-test", action="store_true", help="run the self-test and exit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0
    if args.list_regimes:
        print("Projects and the pixel size their BraiAn.yml declares:")
        for r in known_regimes():
            print(f"  {str(r['pixel_um'] or '?'):<22} anchor={r['anchor']:<10} {r['project']}")
        return 0
    if args.project is None:
        print("nothing to do: pass --project <dir> with --audit or --scaffold, "
              "or --list-regimes, or --self-test")
        return 1
    if args.scaffold:
        target, actions = scaffold(args.project, args.template, args.pixel_um,
                                   args.z_planes, args.dry_run)
        for a in actions:
            print(f"  {a}")
        if args.dry_run:
            return 0
        print("")
    return print_report(args.project)


if __name__ == "__main__":
    sys.exit(main())
