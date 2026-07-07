"""
Static compartment check for QuPath object-classifier JSON files.
Asserts that a classifier's `function.measurement` string matches an expected
compartment string (e.g. "Nucleus: AF488-T3 mean" or "Cytoplasm: AF568-T2 mean")
without needing QuPath or a conda env -- stdlib only.

Reusable for CLASS-01 (this phase, Fos nuclear compartment) and CLASS-02
(later, TdT cytoplasmic compartment).

Usage:
  python3 scripts/check_classifier_compartment.py <classifier.json> "<expected measurement>"

Exit codes:
  0  measurement matches expected string (prints OK)
  1  measurement does not match (prints actual vs expected to stderr)
  2  usage error (wrong arg count) or file/parse error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _check(classifier_path: Path, expected_measurement: str) -> bool:
    """Return True if the classifier's function.measurement matches expected."""
    with open(classifier_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    actual_measurement = data.get("function", {}).get("measurement")

    if actual_measurement == expected_measurement:
        print(f"OK: {classifier_path} -> function.measurement == '{expected_measurement}'")
        return True

    print(
        f"MISMATCH: {classifier_path}\n"
        f"  expected: '{expected_measurement}'\n"
        f"  actual:   '{actual_measurement}'",
        file=sys.stderr,
    )
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("classifier", type=Path, help="Path to a classifier JSON file")
    parser.add_argument(
        "expected_measurement",
        type=str,
        help="Expected function.measurement string, e.g. 'Nucleus: AF488-T3 mean'",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.classifier.is_file():
        print(f"ERROR: classifier file not found: {args.classifier}", file=sys.stderr)
        sys.exit(2)

    try:
        ok = _check(args.classifier, args.expected_measurement)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"ERROR: could not read/parse {args.classifier}: {exc}", file=sys.stderr)
        sys.exit(2)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
