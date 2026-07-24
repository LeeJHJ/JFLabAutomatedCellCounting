#!/usr/bin/env python3
"""run_pipeline.py — friendly one-command launcher for the per-region
cell-counting pipeline (TRAP2/Airyscan section pipeline, D-18b).

This is a numbered text menu, stdlib only (argparse + subprocess), runnable
with the SYSTEM python (no extra installs). It drives the SCRIPTABLE steps
for you via `conda run -n braian ...` behind plain-English prompts, and at
each [GUI] seam (ABBA registration, BraiAnDetect detection, classify/export
"Run for project") it prints a short STOP-and-do-this-in-the-app handoff and
does NOT attempt to run anything — this launcher never claims to drive
QuPath or ABBA.

Full tutorial (read this first if you're new): docs/index.md — preview it
as a searchable website with:
    pip install -r requirements-docs.txt
    mkdocs serve
then open http://127.0.0.1:8000. The two GUI stages have their own detail
docs: docs/runbook/01-registration.md and docs/runbook/02-detection.md.

Usage:
    python run_pipeline.py              interactive numbered menu
    python run_pipeline.py --self-test  print the menu and exit 0
                                         (no execution, no QuPath needed)
    python run_pipeline.py -h           this help text

Every SCRIPTABLE menu item below shells out to a script in scripts/ via:
    conda run -n braian python scripts/<name>.py ...
No user-supplied shell strings are interpolated into that command — the
argument list is fixed per item; only a directory path you type is appended
as a single argv entry (never passed through a shell).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CONDA_ENV = "braian"

TUTORIAL_HOME = "docs/index.md (preview with `mkdocs serve`)"
REGISTRATION_DOC = "docs/runbook/01-registration.md"
DETECTION_DOC = "docs/runbook/02-detection.md"


def _conda_run(script_rel: str, *args: str) -> int:
    """Run `conda run -n braian python <script_rel> <args...>` from REPO_ROOT.

    Fixed allowlist invocation — no shell, no user-supplied command strings.
    """
    cmd = ["conda", "run", "-n", CONDA_ENV, "python", script_rel, *args]
    print(f"  Running: conda run -n {CONDA_ENV} python {script_rel} {' '.join(args)}")
    try:
        result = subprocess.run(cmd, cwd=REPO_ROOT)
    except FileNotFoundError:
        print("  FAILED: `conda` was not found on PATH. Activate/install "
              "Miniforge per SECTION_PIPELINE_SETUP.md, then try again.")
        return 1
    if result.returncode == 0:
        print("  Done.")
    else:
        print(f"  FAILED (exit code {result.returncode}). See the output "
              f"above for the script's own error message.")
    return result.returncode


def action_validate_config() -> int:
    """[SCRIPTABLE] Validate pipeline.yml config."""
    print("Validating pipeline.yml against the shared contract "
          "(measurement keys, class vocabulary, columns)...")
    return _conda_run("scripts/validate_pipeline_config.py", "--config", "pipeline.yml")


def action_gui_registration() -> int:
    """[GUI] STOP — ABBA atlas registration."""
    print(f"  [GUI] Stop here and register this section in Fiji/ABBA.")
    print(f"  Full click-path + screenshots: {REGISTRATION_DOC}")
    print("  This launcher cannot drive Fiji/ABBA — come back here when the "
          "registration is exported to the QuPath project.")
    return 0


def action_gui_detection() -> int:
    """[GUI] STOP — BraiAnDetect detection."""
    print("  [GUI] Stop here and run BraiAnDetect detection in QuPath "
          "(run_braian_detection.groovy, Automate > Run for project).")
    print(f"  Full detail + tuning loop + screenshots: {DETECTION_DOC}")
    print("  This launcher cannot drive QuPath — come back here once "
          "detections look correct.")
    return 0


def action_gui_classify_export() -> int:
    """[GUI] STOP — classify + export ("Run for project" in QuPath)."""
    print("  [GUI] Stop here and run, in QuPath (Automate > Run for "
          "project), in order:")
    print("    1. 02_detect_classify.groovy   (classify TdT+/Fos+/Double+)")
    print("    2. 03_export_region_table.groovy  (per-cell TSV, per-region "
          "table, combined CSV)")
    print(f"  Full step-by-step: {TUTORIAL_HOME}")
    print("  This launcher cannot drive QuPath — come back here once the "
          "export has run.")
    return 0


def action_aggregate_zero_leak() -> int:
    """[SCRIPTABLE] Aggregate the combined CSV + re-prove zero-leak."""
    print("Aggregating reference/region_marker_combined.csv (per config_tag/"
          "marker/class/hemisphere/region) and re-proving the D-10 "
          "leaf-summed zero-leak invariant from the CSV alone...")
    rc = _conda_run("scripts/build_dapi_reference.py", "--check-zero-leak")
    if rc == 0:
        print("  Tip: run without --check-zero-leak (menu is fixed to the "
              "zero-leak re-proof; use the script directly for the full "
              "aggregate/stats output) if you want the aggregate stats file.")
    return rc


def action_verify_export_integrity() -> int:
    """[SCRIPTABLE] Verify per-slice export integrity."""
    print("Verify per-slice export integrity checks a QuPath project's "
          "results/ directory for paired, non-clobbering per-cell/region "
          "TSV files (EXP-02).")
    results_dir = input(
        "  Path to the QuPath project's results/ directory "
        "(e.g. 'M3 Hippocampus 20x 062926 3 plane/results'): "
    ).strip()
    if not results_dir:
        print("  No path entered — skipping.")
        return 1
    return _conda_run("scripts/verify_export_integrity.py", "--results", results_dir)


def action_show_outputs() -> int:
    """[SCRIPTABLE] Show where outputs landed."""
    print("Looking for pipeline outputs under this repo...\n")
    combined_csv = REPO_ROOT / "reference" / "region_marker_combined.csv"
    if combined_csv.exists():
        print(f"  Combined long/tidy CSV: {combined_csv}")
    else:
        print(f"  (not yet created) Combined long/tidy CSV would be at: {combined_csv}")

    found_results = False
    for results_dir in sorted(REPO_ROOT.glob("*/results")):
        if not results_dir.is_dir():
            continue
        percell = sorted(results_dir.glob("*__percell_export.tsv"))
        region = sorted(results_dir.glob("*__region_table.tsv"))
        if percell or region:
            found_results = True
            print(f"\n  {results_dir}/")
            for f in percell:
                print(f"    {f.name}")
            for f in region:
                print(f"    {f.name}")
    if not found_results:
        print("\n  No per-entry results/*__percell_export.tsv or "
              "*__region_table.tsv files found yet. Run the [GUI] classify + "
              "export step first, then check back here.")
    return 0


# Menu, in pipeline order. Each entry: (label, tag, handler).
# tag is "SCRIPTABLE" (real conda-run action) or "GUI" (stop-and-handoff only).
MENU = [
    ("Validate pipeline.yml config", "SCRIPTABLE", action_validate_config),
    ("ABBA atlas registration", "GUI", action_gui_registration),
    ("BraiAnDetect detection", "GUI", action_gui_detection),
    ("Classify + export (\"Run for project\" in QuPath)", "GUI", action_gui_classify_export),
    ("Aggregate combined CSV + re-prove zero-leak", "SCRIPTABLE", action_aggregate_zero_leak),
    ("Verify per-slice export integrity", "SCRIPTABLE", action_verify_export_integrity),
    ("Show where outputs landed", "SCRIPTABLE", action_show_outputs),
]


def print_menu() -> None:
    print("\nPer-Region Cell-Counting Pipeline — friendly launcher")
    print(f"Full tutorial: {TUTORIAL_HOME}\n")
    for i, (label, tag, _handler) in enumerate(MENU, start=1):
        print(f"  {i}. [{tag}] {label}")
    print("  q. Quit")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Print the menu and exit 0 without executing any step "
             "(no QuPath install or live pipeline run required).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.self_test:
        print_menu()
        print("\n--self-test: menu listed, nothing executed. Exiting 0.")
        return 0

    while True:
        print_menu()
        choice = input("\nChoose a step (number) or q to quit: ").strip().lower()
        if choice in ("q", "quit", "exit"):
            print("Goodbye.")
            return 0
        if not choice.isdigit() or not (1 <= int(choice) <= len(MENU)):
            print("Not a valid choice — pick a number from the menu above.")
            continue
        label, tag, handler = MENU[int(choice) - 1]
        print(f"\n--- {label} [{tag}] ---")
        handler()


if __name__ == "__main__":
    sys.exit(main())
