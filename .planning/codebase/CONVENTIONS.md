# Coding Conventions

**Analysis Date:** 2026-06-30

## Overview

This is a single-researcher bioinformatics pipeline. Python scripts are the primary programmatic artifacts; QuPath automation uses Groovy. There is no shared library or package — scripts are standalone entry points.

## Languages in Use

- **Python 3.11** (primary): pipeline scripts in `/home/jflab/section-pipeline/scripts/`
- **Groovy** (QuPath scripting): QuPath automation scripts in `Automated Cell Counting Test/scripts/`
- **OME-XML** (embedded strings): channel/pixel metadata embedded directly in Python output code

## File Naming

- Python scripts: `snake_case.py` (e.g., `czi_to_mip.py`, `run_deepslice.py`)
- QuPath scripts: free-form with dates in name (e.g., `Test 062026 1.groovy`) — not yet standardised
- Output files: `{AnimalID}_{modality}_{MIP|step}.ome.tiff` (e.g., `M3_20x_MIP.ome.tiff`)
- QuPath projects: directory named after experiment + date (e.g., `M3 Hippocampus 20x 062226/`)

## Module-Level Structure

Each Python script follows this layout:

```
1. Module docstring with USAGE and OUTPUT sections
2. from __future__ import annotations
3. stdlib imports (alphabetical)
4. third-party imports (one per line)
5. try/except optional imports with None fallback
6. # ── Section header ──── private helper functions
7. # ── Section header ──── core logic functions
8. # ── Section header ──── CLI (parse_args, main)
9. if __name__ == "__main__": main()
```

Section headers use the pattern `# ── {Label} ─────────────────────────────────────────────` (em-dash + label + trailing dashes).

## Naming Patterns

**Functions:**
- `snake_case` for all functions
- Private/internal helpers prefixed with `_` (e.g., `_get_pixel_size`, `_build_ome_xml`, `_print_info`)
- Public entry points: `main()`, `parse_args()`

**Variables:**
- `snake_case` for local variables (e.g., `pixel_um`, `ch_names`, `mip_channels`)
- Short descriptive names for loop indices: `c` (channel), `z` (z-plane), `n_c`, `n_z`, `n_s`
- Constants in `UPPER_SNAKE_CASE` at module level when hardcoded (e.g., `F_IN`, `F_OUT`, `PIXEL_SIZE_UM` in the prototype `czi_mip.py`)
- Path variables use `Path` objects, not raw strings, in the canonical version (`czi_to_mip.py`)

**Type Annotations:**
- Used in function signatures in `czi_to_mip.py` and `run_deepslice.py`
- Pattern: `list[int] | None` (PEP 604 union syntax, requires `from __future__ import annotations`)
- Return types annotated for non-trivial functions: `-> tuple[np.ndarray, list[str], float]`

## Import Organization

```python
from __future__ import annotations   # always first

# stdlib — alphabetical
import argparse
import json
import sys
from pathlib import Path

# third-party — one per line
import numpy as np
import tifffile

# optional/conditional imports — wrapped in try/except with None sentinel
try:
    import aicspylibczi
except ImportError:
    aicspylibczi = None
```

## Docstrings

**Module-level:** Multi-line docstring with `USAGE` and `OUTPUT` sections using RST-style headings (dashes under section names). Contains runnable example commands.

**Function-level:** Single-line summary sentence. No parameter/return sections in existing code — rely on type annotations and inline comments.

```python
def extract_dapi_8bit(mip_path: Path, dapi_channel: int,
                      lo_pct: float = 0.5, hi_pct: float = 99.5) -> np.ndarray:
    """Read MIP, extract DAPI channel, normalize to uint8 with percentile scaling."""
```

## Error Handling

**Pattern:** `sys.exit(f"ERROR: {message}")` for fatal user-facing errors. No custom exception classes.

```python
if not args.input.exists():
    sys.exit(f"ERROR: file not found: {args.input}")

if pixel_um is None:
    sys.exit("ERROR: could not read pixel size from CZI metadata. "
             "Provide it with --pixel-size X.XX")
```

**Internal functions:** Bare `except Exception: pass` to suppress non-fatal metadata parse failures; return `None` sentinel to caller, which then `sys.exit()`.

```python
def _get_pixel_size(czi) -> float:
    try:
        ...
        return round(val_m * 1e6, 6)
    except Exception:
        pass
    return None
```

**Optional dependency guard:** Check the `None` sentinel before use:

```python
if aicspylibczi is None:
    sys.exit("ERROR: aicspylibczi is not installed in this environment. "
             "Re-run with `conda activate braian` for .czi input ...")
```

## Progress / Logging

No logging framework — use `print()` with `flush=True` for long loops so output appears in real time.

```python
print(f"  Channel {c}/{n_channels - 1}: reading {len(z_idx)} z-plane(s)...", flush=True)
```

Indentation convention for nested progress:
- Top-level steps: `print("Step name...")` — no indent
- Sub-steps: `print(f"  detail")` — 2-space indent
- Inner loop: `print(f"    inner")` — 4-space indent

Summary block after write:
```python
print(f"\nDone. {out.name}  ({size_mb:.0f} MB)")
print(f"  Channels : {ch_names}")
print(f"  Shape    : {mip.shape[2]} × {mip.shape[1]} px")
```

## CLI Pattern

All scripts use `argparse` with:
- `formatter_class=argparse.RawDescriptionHelpFormatter`
- `epilog=__doc__` (reuses module docstring as extended help)
- `type=Path` for file arguments
- Explicit `default=None` and helpful `help=` strings with units and defaults noted

```python
def parse_args():
    p = argparse.ArgumentParser(
        description="One-line description.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("input", type=Path, help="Input .czi file")
    p.add_argument("-o", "--output", type=Path, default=None,
                   help="Output path (default: input_dir/stem_MIP.ome.tiff)")
    return p.parse_args()
```

## Path Handling

Use `pathlib.Path` everywhere in canonical scripts. String conversion only at library call boundaries:

```python
tifffile.imwrite(str(out), ...)
aicspylibczi.CziFile(str(args.input))
```

Output path construction strips compound extensions before appending suffix:
```python
for ext in (".ome.tiff", ".ome.tif", ".tiff", ".tif", ".czi"):
    if stem.lower().endswith(ext):
        stem = stem[: -len(ext)]
        break
```

## Array / NumPy Conventions

- Canonical array dimension order: `(C, Y, X)` for MIP output
- Per-plane reads squeezed immediately: `.squeeze()` → `(Y, X)`
- Stack per channel then `np.stack(mip_channels, axis=0)` → `(C, Y, X)`
- Use `np.max(stack, axis=0)` for MIP (not `np.maximum.reduce`)
- Normalisation for 8-bit: percentile clip then cast: `np.clip(...).astype(np.uint8)`

## Groovy (QuPath) Conventions

Scripts in `Automated Cell Counting Test/scripts/` are boilerplate from BIOP/Warpy with minimal modification. No project-specific Groovy conventions are established yet.

- Javadoc-style header comments with `@author` tags
- Inline comments explain each logical step
- `println` for output (not `print`)
- `def` for all variable declarations

## Hardcoded Values vs. Arguments

Prototype scripts (`czi_mip.py`) use module-level constants:
```python
F_IN  = "/home/jflab/Analysis/..."
PIXEL_SIZE_UM = 0.69
```

Production scripts (`czi_to_mip.py`, `run_deepslice.py`) expose everything as CLI args with sensible defaults. **Prefer the production pattern for any new script.**

## Biological Constants and Units

- Pixel size always in **µm** — variable named `pixel_um`; unit written `µm` (Unicode mu, not `um`)
- AP coordinates in **mm from bregma** (positive = anterior)
- Atlas coordinates in **µm** (CCFv3 space)
- Channel order in CZI files may not match metadata — always pass `--channels` override when known

---

*Convention analysis: 2026-06-30*
