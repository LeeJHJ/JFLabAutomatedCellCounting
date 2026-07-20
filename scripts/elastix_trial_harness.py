"""
elastix + transformix argv wrapper for the REG-05 masked-elastix single-
section trial. Builds `subprocess.run([...], shell=False)` argument lists
for elastix (masked Affine + BSpline) and transformix (apply the resulting
transform to the full-res section) -- never a shell string.

CPU-only. Runs in the `braian` conda env. Requires elastix 5.2.0 at
$HOME/section-pipeline/tools/elastix/ (LD_LIBRARY_PATH set at run time).

Usage:
  conda run -n braian python3 scripts/elastix_trial_harness.py \\
      --fixed atlas_plate_10um.tif --moving worst_section_dapi_cropped.tif \\
      --fixed-mask atlas_plate_mask.tif --moving-mask tissue_mask.tif \\
      --out elastix_trial_out/ --transformix-in worst_section_full_res.tif

  # Dry-run (print argv, no real elastix call):
  conda run -n braian python3 scripts/elastix_trial_harness.py ... --dry-run

  # Synthetic self-test (no filesystem access, no subprocess call):
  conda run -n braian python3 scripts/elastix_trial_harness.py --self-test
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# ── Module constants ─────────────────────────────────────────────────────────

ELASTIX_BIN = Path.home() / "section-pipeline/tools/elastix/bin/elastix"
TRANSFORMIX_BIN = Path.home() / "section-pipeline/tools/elastix/bin/transformix"
ELASTIX_LIB = Path.home() / "section-pipeline/tools/elastix/lib"

DEFAULT_PARAM_DIR = Path(__file__).resolve().parent / "elastix_params"
DEFAULT_PARAMS = [DEFAULT_PARAM_DIR / "Par_Affine.txt", DEFAULT_PARAM_DIR / "Par_BSpline.txt"]


# ── Private helpers ──────────────────────────────────────────────────────────

def _validate_paths(paths: list[Path]) -> None:
    """Raise SystemExit for any path that does not exist (ASVS V5)."""
    raise NotImplementedError


def _build_elastix_argv(
    elastix_bin: Path,
    fixed: Path,
    moving: Path,
    fixed_mask: Path,
    moving_mask: Path,
    param_files: list[Path],
    out_dir: Path,
) -> list[str]:
    """Build the elastix subprocess argv list (shell=False)."""
    raise NotImplementedError


def _build_transformix_argv(
    transformix_bin: Path, in_image: Path, transform_params: Path, out_dir: Path
) -> list[str]:
    """Build the transformix subprocess argv list (shell=False)."""
    raise NotImplementedError


def _run(argv: list[str], dry_run: bool, env: dict | None = None) -> None:
    """Print then (unless dry_run) execute argv via subprocess.run(shell=False)."""
    print("  argv:", argv)
    if dry_run:
        return
    run_env = os.environ.copy() if env is None else dict(env)
    run_env["LD_LIBRARY_PATH"] = f"{ELASTIX_LIB}:{run_env.get('LD_LIBRARY_PATH', '')}"
    subprocess.run(argv, shell=False, check=True, env=run_env)


def _self_test() -> None:
    """Synthetic argv-construction exercise. No subprocess call, no filesystem access."""
    print("Running self-test...")

    elastix_bin = Path("/tmp/elastix")
    transformix_bin = Path("/tmp/transformix")
    fixed = Path("/tmp/fixed.tif")
    moving = Path("/tmp/moving.tif")
    fixed_mask = Path("/tmp/fixed_mask.tif")
    moving_mask = Path("/tmp/moving_mask.tif")
    param_affine = Path("Par_Affine.txt")
    param_bspline = Path("Par_BSpline.txt")
    out_dir = Path("/tmp/out")

    # ── elastix argv ──
    argv = _build_elastix_argv(
        elastix_bin, fixed, moving, fixed_mask, moving_mask, [param_affine, param_bspline], out_dir
    )
    assert argv[0] == str(elastix_bin)
    assert argv.count("-p") == 2, f"expected exactly two -p flags, got {argv.count('-p')}"
    idx_affine = argv.index(str(param_affine))
    idx_bspline = argv.index(str(param_bspline))
    assert idx_affine < idx_bspline, "Par_Affine.txt must precede Par_BSpline.txt"
    for flag in ("-f", "-m", "-fMask", "-mMask", "-p", "-out"):
        assert flag in argv, f"missing flag {flag}"
    assert argv[argv.index("-f") + 1] == str(fixed)
    assert argv[argv.index("-m") + 1] == str(moving)
    assert argv[argv.index("-fMask") + 1] == str(fixed_mask)
    assert argv[argv.index("-mMask") + 1] == str(moving_mask)
    assert argv[argv.index("-out") + 1] == str(out_dir)
    print("  PASS: _build_elastix_argv order/contents (-p x2, Affine before BSpline)")

    # ── transformix argv ──
    t_argv = _build_transformix_argv(transformix_bin, moving, Path("/tmp/out/TransformParameters.1.txt"), out_dir)
    assert t_argv == [
        str(transformix_bin),
        "-in", str(moving),
        "-tp", str(Path("/tmp/out/TransformParameters.1.txt")),
        "-out", str(out_dir),
    ], f"unexpected transformix argv: {t_argv}"
    print("  PASS: _build_transformix_argv order/contents")

    print("SELF-TEST PASS")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--fixed", type=Path, default=None, help="Fixed image (atlas plate)")
    parser.add_argument("--moving", type=Path, default=None, help="Moving image (section DAPI, cropped)")
    parser.add_argument("--fixed-mask", type=Path, default=None, help="Fixed image binary mask")
    parser.add_argument("--moving-mask", type=Path, default=None, help="Moving image binary mask")
    parser.add_argument("--param", type=Path, nargs="+", default=DEFAULT_PARAMS, help="Parameter files, in order (default: Par_Affine.txt then Par_BSpline.txt)")
    parser.add_argument("--out", type=Path, default=None, help="elastix output directory")
    parser.add_argument("--transformix-in", type=Path, default=None, help="Full-res section image to warp via transformix (optional)")
    parser.add_argument("--dry-run", action="store_true", help="Print argv only, skip execution")
    parser.add_argument("--self-test", action="store_true", help="Run the synthetic self-test and exit")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.self_test:
        _self_test()
        return

    required = {"--fixed": args.fixed, "--moving": args.moving, "--fixed-mask": args.fixed_mask,
                "--moving-mask": args.moving_mask, "--out": args.out}
    missing = [name for name, val in required.items() if val is None]
    if missing:
        print(f"ERROR: missing required args: {missing} (unless --self-test)", file=sys.stderr)
        sys.exit(2)

    _validate_paths([args.fixed, args.moving, args.fixed_mask, args.moving_mask, *args.param])

    print("Step 1: Building elastix argv...")
    elastix_argv = _build_elastix_argv(
        ELASTIX_BIN, args.fixed, args.moving, args.fixed_mask, args.moving_mask, args.param, args.out
    )

    print("Step 2: Running elastix...")
    _run(elastix_argv, args.dry_run)

    if args.transformix_in is not None:
        print("Step 3: Validating transformix inputs...")
        transform_params = args.out / "TransformParameters.1.txt"
        _validate_paths([args.transformix_in] + ([] if args.dry_run else [transform_params]))

        print("Step 4: Building + running transformix argv...")
        transformix_argv = _build_transformix_argv(TRANSFORMIX_BIN, args.transformix_in, transform_params, args.out)
        _run(transformix_argv, args.dry_run)


if __name__ == "__main__":
    main()
