#!/usr/bin/env python3
"""sync_project.py -- deploy the repo's pipeline into a QuPath project.

WHY THIS EXISTS
    QuPath can only run Groovy scripts that live inside the project's own
    `scripts/` directory, so every project needs a copy. Historically those copies
    were made by hand, and the repo accumulated 5 byte-identical duplicates across
    4 projects plus 2 stale one-offs. Nobody could tell which copy was current.

    The fix is not deduplication -- the copies are load-bearing. It is a clear
    SOURCE and a repeatable DEPLOY:

        repo scripts/*.groovy   ->   <project>/scripts/*.groovy      (overwrite)
        repo pipeline.yml       ->   <project>/pipeline.yml          (MERGE ONLY)

    Groovy scripts are project-agnostic code and are overwritten wholesale.
    pipeline.yml is NOT: it declares this project's marker set, channel names and
    anchor, which legitimately differ per slice-set (a TdT-only set has no Fos
    marker). So this script never overwrites it -- it only ADDS missing blocks
    that the scripts now require, leaving every existing value alone.

    This is also what makes the pipeline usable by someone else: point it at a
    fresh QuPath project and it becomes runnable, with no hand-copying.

Usage:
    python3 scripts/sync_project.py --project "<project dir>"
    python3 scripts/sync_project.py --all              # every project under the repo
    python3 scripts/sync_project.py --all --dry-run    # show what would change
    python3 scripts/sync_project.py --self-test
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_SCRIPTS = REPO_ROOT / "scripts"

# The manual-ROI route is a self-contained module in its own folder, but QuPath can
# still only run Groovy that lives inside the project -- so its scripts deploy from
# here alongside the registered route's. Listing the directory rather than hardcoding
# filenames means adding a script to that folder is enough to ship it.
ROI_SRC_SCRIPTS = REPO_ROOT / "ROI Counting" / "scripts"


def source_script_dirs() -> list[Path]:
    """Every directory whose *.groovy deploys into a QuPath project."""
    return [d for d in (SRC_SCRIPTS, ROI_SRC_SCRIPTS) if d.is_dir()]


def source_scripts() -> list[Path]:
    """Every Groovy file that deploys, across all source directories.

    A name collision between the two source dirs would mean one silently overwriting
    the other in every project, so it is refused here rather than discovered later.
    """
    seen: dict[str, Path] = {}
    out = []
    for d in source_script_dirs():
        for g in sorted(d.glob("*.groovy")):
            if g.name in seen:
                raise SystemExit(
                    f"two source directories both provide {g.name}:\n"
                    f"  {seen[g.name]}\n  {g}\n"
                    f"Deploying both would leave every project carrying whichever copied "
                    f"last. Rename one.")
            seen[g.name] = g
            out.append(g)
    return out
ROOT_CONFIG = REPO_ROOT / "pipeline.yml"

# Scripts that were superseded and must be REMOVED from project script dirs, so an
# operator cannot open a stale one out of habit. Only these exact names are ever
# deleted -- an operator's own scratch scripts are never touched.
RETIRED_SCRIPTS = (
    "find_threshold().groovy",        # -> calibrate_threshold.groovy (channel was hardwired
                                      #    to DAPI-T4, and its prominence sweep changed WHICH
                                      #    peak was found rather than where the cut sat)
    "classify_markers.groovy",        # -> folded into 02_detect_classify.groovy (06.1)
    "03_export_val01_metrics.groovy", # -> folded into 03_export_region_table.groovy (06.1)
    "export_region_dapi_reference.groovy",  # -> folded into 03_export_region_table.groovy
)

# Config blocks the current scripts require. Each entry is a top-level key; when
# absent from a project's pipeline.yml, the canonical block (comments included) is
# copied verbatim from the repo-root pipeline.yml and appended.
REQUIRED_CONFIG_BLOCKS = ("detection_threshold",)

# A project containing this file is skipped by --all. Used for QuPath projects that
# are not analysis targets -- e.g. a legacy project retained only because live
# projects' server.json entries point at image files inside it. Scaffolding a
# pipeline.yml into one of those would advertise a marker set nobody will run.
NOSYNC_MARKER = ".pipeline-nosync"


def is_qupath_project(path: Path) -> bool:
    return (path / "project.qpproj").is_file()


def find_projects(root: Path = REPO_ROOT) -> list[Path]:
    """Every syncable QuPath project under the repo.

    Excludes archived projects and any carrying the NOSYNC_MARKER file. An explicit
    --project path is always honoured, marker or not.
    """
    out = []
    for qp in root.rglob("project.qpproj"):
        if "_archive" in qp.parts:
            continue
        if (qp.parent / NOSYNC_MARKER).exists():
            continue
        out.append(qp.parent)
    return sorted(out)


def extract_block(config_text: str, key: str) -> str:
    """Pull a top-level YAML block (with its leading comment paragraph) out of text.

    Returns "" when the key is absent. The leading comments are deliberately
    included: they carry the reasoning a future reader needs, and a config block
    copied without its rationale is how the absolute-threshold decision became
    invisible in the first place.
    """
    lines = config_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"{key}:"):
            start = i
            break
    if start is None:
        return ""

    # Walk back over the contiguous comment paragraph immediately above the key.
    first = start
    while first > 0 and lines[first - 1].lstrip().startswith("#"):
        first -= 1

    # Forward to the end of the block: the key's indented children.
    end = start + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() == "":
            # A blank line ends the block only if what follows is not still indented.
            nxt = end + 1
            while nxt < len(lines) and lines[nxt].strip() == "":
                nxt += 1
            if nxt >= len(lines) or not lines[nxt].startswith((" ", "\t")):
                break
            end = nxt
            continue
        if not line.startswith((" ", "\t")):
            break
        end += 1

    return "\n".join(lines[first:end]).rstrip() + "\n"


def sync_scripts(project: Path, dry_run: bool = False) -> dict:
    """Copy source Groovy into the project; remove retired copies."""
    dest = project / "scripts"
    report = {"new": [], "updated": [], "unchanged": [], "retired": []}
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)

    for src in source_scripts():
        tgt = dest / src.name
        if not tgt.exists():
            report["new"].append(src.name)
            if not dry_run:
                shutil.copy2(src, tgt)
        elif tgt.read_bytes() != src.read_bytes():
            report["updated"].append(src.name)
            if not dry_run:
                shutil.copy2(src, tgt)
        else:
            report["unchanged"].append(src.name)

    for name in RETIRED_SCRIPTS:
        stale = dest / name
        if stale.exists():
            report["retired"].append(name)
            if not dry_run:
                stale.unlink()

    return report


def sync_config(project: Path, dry_run: bool = False) -> dict:
    """Ensure the project's pipeline.yml carries every block the scripts require.

    NEVER overwrites existing values -- only appends absent blocks.
    """
    tgt = project / "pipeline.yml"
    root_text = ROOT_CONFIG.read_text()
    report = {"created": False, "added_blocks": [], "already_complete": False}

    if not tgt.exists():
        report["created"] = True
        if not dry_run:
            shutil.copy2(ROOT_CONFIG, tgt)
        return report

    text = tgt.read_text()
    additions = []
    for key in REQUIRED_CONFIG_BLOCKS:
        if any(line.startswith(f"{key}:") for line in text.splitlines()):
            continue
        block = extract_block(root_text, key)
        if not block:
            raise RuntimeError(
                f"repo-root pipeline.yml has no '{key}' block to copy -- "
                "the source config is itself incomplete"
            )
        additions.append((key, block))

    if not additions:
        report["already_complete"] = True
        return report

    new_text = text.rstrip() + "\n"
    for key, block in additions:
        new_text += (
            f"\n# ── added by scripts/sync_project.py (block required by the current "
            f"scripts) ──\n{block}"
        )
        report["added_blocks"].append(key)
    if not dry_run:
        tgt.write_text(new_text)
    return report


def sync_project(project: Path, dry_run: bool = False) -> dict:
    if not is_qupath_project(project):
        raise ValueError(f"{project} is not a QuPath project (no project.qpproj)")
    return {
        "project": project,
        "scripts": sync_scripts(project, dry_run=dry_run),
        "config": sync_config(project, dry_run=dry_run),
    }


def print_report(rep: dict, dry_run: bool) -> None:
    tag = "[dry-run] " if dry_run else ""
    print(f"\n{tag}{rep['project']}")
    s = rep["scripts"]
    for label, key in (("new", "new"), ("updated", "updated"), ("REMOVED (retired)", "retired")):
        if s[key]:
            print(f"    scripts {label}: {', '.join(s[key])}")
    if s["unchanged"]:
        print(f"    scripts unchanged: {len(s['unchanged'])}")
    c = rep["config"]
    if c["created"]:
        print("    pipeline.yml CREATED from repo root -- EDIT its markers/channels "
              "to match this slice-set")
    elif c["added_blocks"]:
        print(f"    pipeline.yml: added block(s) {', '.join(c['added_blocks'])} "
              "(existing values untouched)")
    else:
        print("    pipeline.yml: already complete")


def _self_test() -> None:
    import tempfile

    print("sync_project self-test")

    # extract_block must capture the block AND its comment paragraph.
    sample = (
        "anchor:\n"
        '  name: "DAPI"\n'
        "\n"
        "# leading comment line 1\n"
        "# leading comment line 2\n"
        "detection_threshold:\n"
        '  mode: "span_fraction"\n'
        "  span_frac: 0.25\n"
        "\n"
        "k_robust: 3.0\n"
    )
    blk = extract_block(sample, "detection_threshold")
    assert "# leading comment line 1" in blk, blk
    assert "span_frac: 0.25" in blk, blk
    assert "k_robust" not in blk, f"block bled into the next key:\n{blk}"
    assert "anchor" not in blk, f"block bled into the previous key:\n{blk}"
    print("  extract_block OK (comments included, neighbours excluded)")

    assert extract_block(sample, "nope") == ""
    print("  extract_block absent-key OK")

    # The real root config must actually contain every required block.
    root_text = ROOT_CONFIG.read_text()
    for key in REQUIRED_CONFIG_BLOCKS:
        b = extract_block(root_text, key)
        assert b and f"{key}:" in b, f"repo-root pipeline.yml missing '{key}'"
    print(f"  repo-root pipeline.yml has all required blocks: {list(REQUIRED_CONFIG_BLOCKS)}")

    with tempfile.TemporaryDirectory() as td:
        proj = Path(td) / "fake project"
        (proj / "scripts").mkdir(parents=True)
        (proj / "project.qpproj").write_text("{}")

        # A config with a DIFFERENT marker set: sync must preserve it exactly.
        custom = (
            'anchor:\n  name: "DAPI"\n  channel: "DAPI-T4"\n\n'
            'markers:\n  - name: "TdT"\n    channel: "AF568-T2"\n    compartment: "whole-cell"\n\n'
            'exclude_acronyms: ["DG-sg"]\nk_robust: 2.5\nring:\n  gap_um: 1.0\n  width_um: 8.0\n'
        )
        (proj / "pipeline.yml").write_text(custom)

        # A retired script the operator might still have lying around.
        (proj / "scripts" / "find_threshold().groovy").write_text("// stale")

        rep = sync_project(proj)
        assert rep["config"]["added_blocks"] == ["detection_threshold"], rep["config"]
        out = (proj / "pipeline.yml").read_text()
        assert "k_robust: 2.5" in out, "overwrote the project's own k_robust"
        assert '- name: "TdT"' in out and "Fos" not in out, "clobbered the project's marker set"
        assert "detection_threshold:" in out and "span_frac" in out
        print("  config merge OK (added block, preserved custom markers + k_robust 2.5)")

        assert "find_threshold().groovy" in rep["scripts"]["retired"]
        assert not (proj / "scripts" / "find_threshold().groovy").exists()
        print("  retired-script removal OK")

        srcs = source_scripts()
        n_src = len(srcs)
        assert len(rep["scripts"]["new"]) == n_src, rep["scripts"]
        for g in srcs:
            assert (proj / "scripts" / g.name).read_bytes() == g.read_bytes()
        assert any(g.parent == ROI_SRC_SCRIPTS for g in srcs), (
            "no Groovy deployed from the ROI Counting module -- a project would come up "
            "without the manual-ROI route")
        print(f"  deployed {n_src} groovy scripts byte-identical to source "
              f"(from {len(source_script_dirs())} source dirs)")

        # Idempotence: a second run must change nothing.
        rep2 = sync_project(proj)
        assert rep2["config"]["already_complete"], rep2["config"]
        assert not rep2["scripts"]["new"] and not rep2["scripts"]["updated"], rep2["scripts"]
        assert len(rep2["scripts"]["unchanged"]) == n_src
        print("  idempotent on re-run OK")

        # dry-run must not touch the filesystem.
        (proj / "scripts" / "02_detect_classify.groovy").write_text("// locally edited")
        rep3 = sync_project(proj, dry_run=True)
        assert "02_detect_classify.groovy" in rep3["scripts"]["updated"]
        assert (proj / "scripts" / "02_detect_classify.groovy").read_text() == "// locally edited"
        print("  dry-run leaves files untouched OK")

        # Missing config -> created from root.
        proj2 = Path(td) / "fresh"
        proj2.mkdir()
        (proj2 / "project.qpproj").write_text("{}")
        rep4 = sync_project(proj2)
        assert rep4["config"]["created"]
        assert (proj2 / "pipeline.yml").exists()
        print("  fresh-project bootstrap OK")

        # Non-project must be refused.
        bad = Path(td) / "not a project"
        bad.mkdir()
        try:
            sync_project(bad)
        except ValueError:
            print("  refuses non-QuPath directory OK")
        else:
            raise AssertionError("should have refused a directory with no project.qpproj")

    print("SELF-TEST PASSED")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--project", type=Path, default=None, help="a single QuPath project directory")
    p.add_argument("--all", action="store_true", help="every QuPath project under the repo")
    p.add_argument("--dry-run", action="store_true", help="report changes without writing")
    p.add_argument("--self-test", action="store_true", help="run on synthetic data and exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0

    if args.all:
        targets = find_projects()
        if not targets:
            print("No QuPath projects found under the repo.")
            return 1
    elif args.project is not None:
        targets = [args.project]
    else:
        sys.exit("ERROR: pass --project <dir>, --all, or --self-test")

    for d in source_script_dirs():
        print(f"Source: {d}")
    print(f"Config: {ROOT_CONFIG}")
    for t in targets:
        try:
            print_report(sync_project(t, dry_run=args.dry_run), args.dry_run)
        except (ValueError, RuntimeError) as e:
            print(f"\nSKIPPED {t}: {e}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
