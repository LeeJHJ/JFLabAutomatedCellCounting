# Phase 6: Registration Speedup - Pattern Map

**Mapped:** 2026-07-19
**Files analyzed:** 8 (post-CONTEXT-resolution; `scripts/run_deepslice.py` explicitly excluded — see 06-CONTEXT.md ⟳ RESOLUTION)
**Analogs found:** 6 / 8

## Scope Note (read first)

06-CONTEXT.md's ⟳ RESOLUTION supersedes 06-RESEARCH.md's "Recommended Project Structure" on one point: **`scripts/run_deepslice.py` is NOT built this phase.** REG-03 uses ABBA's native Fiji "DeepSlice Registration (Local)" command; D-01's reproducibility goal is met instead by a committed operator SOP record (markdown), not a script. Do not map or plan that file. All entries below reflect the corrected file set.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `scripts/extract_atlas_plate.py` | utility | transform (file-I/O, array indexing) | `scripts/crop_to_tissue.py` | role-match (both are standalone `braian`-env array-processing CLIs with `--self-test`) |
| `scripts/elastix_trial_harness.py` (recommend `.py` over `.sh`, see below) | utility | event-driven (subprocess invocation) | `scripts/crop_to_tissue.py` (CLI/self-test shape); no existing subprocess-wrapper analog in repo | partial (no direct subprocess-CLI analog exists; borrowing argparse/self-test skeleton only) |
| `scripts/elastix_params/Par_Affine.txt` | config | n/a (static parameter file) | none in repo | no analog — use elastix.dev standard component set from 06-RESEARCH.md Code Examples |
| `scripts/elastix_params/Par_BSpline.txt` | config | n/a (static parameter file) | none in repo | no analog — same as above |
| `scripts/bigwarp_effort_log.csv` | config/data (operator log) | batch (append-only CSV) | none in repo | no analog — schema pinned in 06-VALIDATION.md |
| REG-03 operator SOP doc (markdown) | test/config (procedure record) | n/a | `~/.claude/.../memory/feedback_abba_tilt.md`; `.planning/phases/05-.../05-REVIEW.md`-style findings notes | role-match (project's existing markdown findings/procedure convention) |
| REG-05 keep/reject findings record (markdown) | test (decision record) | n/a | `~/.claude/.../memory/feedback_abba_tilt.md` ("Crop-to-tissue pilot finding" block is exactly this pattern — a-priori rule stated, then outcome recorded) | exact (same project already has this precise pattern) |
| `scripts/01_load_abba_rois.groovy` | route/script (Groovy, QuPath) | n/a | UNCHANGED — no new work; downstream consumer only, listed for completeness | n/a (existing, not modified) |

## Pattern Assignments

### `scripts/extract_atlas_plate.py` (utility, transform)

**Analog:** `scripts/crop_to_tissue.py` (full file read above — 374 lines, `braian` env)

**Imports pattern** (crop_to_tissue.py lines 19-30):
```python
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np
import tifffile
from scipy.ndimage import binary_fill_holes
from skimage.filters import threshold_otsu
from skimage.morphology import closing, disk, remove_small_objects
```
For `extract_atlas_plate.py`, swap the tifffile/skimage stack for:
```python
from brainglobe_atlasapi import BrainGlobeAtlas
```
(per 06-RESEARCH.md "Code Examples" — `BrainGlobeAtlas("allen_mouse_10um")` → `.reference`, `.resolution`, `.orientation`, `.shape`; already installed in `braian` env, matches ABBA's `allen_mouse_10um_java` atlas key).

**Module docstring pattern** (crop_to_tissue.py lines 1-17): a top docstring stating purpose, CPU/env constraint, and both a real-usage example and a `--self-test` invocation example. Copy this shape verbatim, e.g.:
```python
"""
Allen CCFv3 coronal-plate extraction for the REG-05 elastix fixed image.
Reads the allen_mouse_10um atlas via brainglobe-atlasapi, resolves the AP
axis from atlas.orientation (do NOT hardcode axis 0 -- 06-RESEARCH.md
Assumption A1), and extracts a single 2D coronal plate at a given AP
position in mm from bregma.

CPU-only. Runs in the `braian` conda env.

Usage:
  conda run -n braian python3 scripts/extract_atlas_plate.py \\
      --ap-mm -1.4 -o atlas_plate_10um.tif

  # Synthetic self-test (no atlas download needed):
  conda run -n braian python3 scripts/extract_atlas_plate.py --self-test
"""
```

**Core pattern — private helpers + step-numbered main()** (crop_to_tissue.py lines 33-91 for helper shape, lines 300-369 for main()):
- Prefix internal helpers with `_` (`_select_dapi_index`, `_compute_tissue_mask`, `_tissue_bbox`) — same convention for `_resolve_ap_axis(atlas)`, `_ap_mm_to_index(ap_mm, resolution, axis)`, `_extract_plate(volume, index, axis)`.
- `main()` prints numbered `Step N: ...` lines exactly like crop_to_tissue.py's `Step 1: Reading MIP...` / `Step 2: Selecting DAPI channel...` etc. (lines 316, 324, 329, 337, 342) — 2-space indent for sub-detail per CLAUDE.md's Progress/Logging convention.
- Raise `ValueError`/`SystemExit` with a descriptive message on invalid input (crop_to_tissue.py lines 69-73, 78-80, 87-90, 121-122) — same style for "atlas.orientation not recognized" / "AP index out of volume bounds" guards. **This directly implements 06-RESEARCH.md Assumption A1's mitigation**: print `atlas.orientation` and `atlas.shape` and assert the AP axis before indexing, never hardcode axis 0.

**Self-test pattern** (crop_to_tissue.py lines 178-260, `_self_test()`): build a small synthetic 3D numpy array in place of a real (1 GB) atlas download, assert plate-indexing math and shape/dtype, print `PASS:` lines per assertion, end with `SELF-TEST PASS`. Directly satisfies 06-RESEARCH.md's Validation Architecture requirement ("unit (synthetic, using a small dummy volume, no real atlas download)").

**CLI arg pattern** (crop_to_tissue.py lines 264-297): `argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)`, `type=Path` for file args, a `--self-test` boolean flag that short-circuits before requiring positional/required args (main() lines 303-309 checks `args.self_test` first, then validates `args.input is None`).

**Error handling pattern:** no try/except wrapping — this codebase favors early `raise ValueError(...)` / `raise SystemExit(...)` with an explanatory f-string rather than caught exceptions (see crop_to_tissue.py lines 121-122, 69-73; czi_mip.py lines 132-137, 210-211, 241-244, 270-273). Follow this — no bare `except`.

---

### `scripts/elastix_trial_harness.py` (utility, event-driven / subprocess)

**Analog:** `scripts/crop_to_tissue.py` for the CLI/self-test skeleton; **no existing repo file wraps an external CLI subprocess** — this is a genuinely new pattern for the codebase. Build from 06-RESEARCH.md's verified CLI invocation directly.

**Recommendation:** author as `.py` not `.sh` — this repo has zero existing shell scripts; every executable script in `scripts/` is `.py` (braian/deepslice env) or `.groovy` (QuPath). A Python harness lets the `--self-test` requirement (dry-run argv construction, no real elastix call) reuse the exact same `argparse` + `_self_test()` shape as every other script in this codebase, and satisfies 06-RESEARCH.md Security Domain's explicit mitigation: `subprocess.run([...], shell=False)` with an argument list, never a shell string.

**Core pattern — argv construction, not string interpolation** (per 06-RESEARCH.md "Code Examples" / "Known Threat Patterns"):
```python
import subprocess
import os

def _build_elastix_argv(elastix_bin: Path, fixed: Path, moving: Path,
                         fixed_mask: Path, moving_mask: Path,
                         param_files: list[Path], out_dir: Path) -> list[str]:
    argv = [str(elastix_bin), "-f", str(fixed), "-m", str(moving),
            "-fMask", str(fixed_mask), "-mMask", str(moving_mask)]
    for p in param_files:
        argv += ["-p", str(p)]
    argv += ["-out", str(out_dir)]
    return argv

def _run(argv: list[str], dry_run: bool) -> None:
    print("  argv:", argv)
    if dry_run:
        return
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = (
        f"{Path.home()}/section-pipeline/tools/elastix/lib:" + env.get("LD_LIBRARY_PATH", "")
    )
    subprocess.run(argv, shell=False, check=True, env=env)
```
This mirrors 06-RESEARCH.md's verified CLI:
```bash
$HOME/section-pipeline/tools/elastix/bin/elastix \
  -f atlas_plate_10um.tif -m worst_section_dapi_cropped.tif \
  -fMask atlas_plate_mask.tif -mMask tissue_mask_from_crop_to_tissue.tif \
  -p Par_Affine.txt -p Par_BSpline.txt -out elastix_trial_out/
```
followed by a `transformix -in ... -tp TransformParameters.1.txt -out ...` call built the same way.

**Self-test / dry-run pattern:** a `--self-test` (or `--dry-run`) flag that calls `_build_elastix_argv()` with synthetic `Path` placeholders and asserts the resulting list contains `-f`, `-m`, `-fMask`, `-mMask`, `-p` (twice, Affine then BSpline), `-out`, in the documented order — never actually invokes `subprocess.run`. Matches crop_to_tissue.py's "assert on returned structure, print PASS" self-test idiom (lines 192-257) and directly satisfies 06-RESEARCH.md's Validation Architecture line: *"unit (dry-run / argument-construction self-test, not a real registration run)"*.

**Input validation pattern (V5, per 06-RESEARCH.md Security Domain):** validate that `fixed`, `moving`, `fixed_mask`, `moving_mask`, and each param file `Path.exists()` before building argv — matching crop_to_tissue.py's early-fail style (raise with descriptive message, not a bare crash).

**Env/path constant pattern:** hardcode elastix/transformix bin paths and `LD_LIBRARY_PATH` as module-level `UPPER_SNAKE_CASE` constants at the top of the file, mirroring czi_mip.py's `DEFAULT_CHANNELS`, `DEFAULT_PIXEL_UM`, `DEFAULT_ANIMAL_PREFIX` (czi_mip.py lines 41-43) — e.g. `ELASTIX_BIN = Path.home() / "section-pipeline/tools/elastix/bin/elastix"`.

---

### `scripts/elastix_params/Par_Affine.txt`, `Par_BSpline.txt` (config, static)

**No code analog exists in this repo.** Source directly from 06-RESEARCH.md's "Don't Hand-Roll" table: use the standard elastix component set (`AdvancedMattesMutualInformation` metric, `AdaptiveStochasticGradientDescent` optimizer, `AffineTransform` then `BSplineTransform`, standard resolution pyramid) documented at elastix.dev — this is exactly the component set ABBA's own (currently-disabled) internal elastix commands use, per RESEARCH.md's Don't Hand-Roll rationale. Do not invent a custom metric/optimizer combination (RESEARCH.md flags this project already hit an elastix failure mode once, 2026-06-23, from a mismatched combination — see `[[feedback-abba-tilt]]`).

---

### `scripts/bigwarp_effort_log.csv` (data/config, batch log)

**No code analog** — this is an operator-filled artifact, not a generated file. Column schema is pinned by 06-VALIDATION.md (referenced in RESEARCH.md's Wave 0 Gaps): `section, start_time, end_time, elapsed_min, landmark_count, notes`. If the executor pre-seeds the file, use a header-only CSV with these 6 columns and one example row showing the amygdala-relevant landmark anchors (LA/BA lateral boundary, external capsule, optic tract, ventral brain edge) in `notes`, e.g.:
```csv
section,start_time,end_time,elapsed_min,landmark_count,notes
wBA1-3_s1,,,,,"anchors: LA/BA boundary, ext. capsule, optic tract, ventral edge"
```

---

### REG-03 operator SOP record (markdown)

**Analog:** `~/.claude/.../memory/feedback_abba_tilt.md` (full file read above) — this project's existing convention for a "locked procedure + parameters + outcome" markdown note. Structure to copy:
- Short problem/context statement up top.
- **Numbered fix/procedure steps** (feedback_abba_tilt.md lines 12-17) — copy this numbered-step shape for the REG-03 SOP: exact menu path, exact parameter values (per 06-CONTEXT.md ⟳ RESOLUTION: `channels=2`, `model=mouse`, `section_numbers=true`, `post_processing=KEEP_ORDER_SET_SPACING` + operator spacing, `propagate_angles=true`, `ensemble=true`), then the D-04 compare-angle step, then D-05 outlier-override step.
- A **dated finding/decision block** at the end (feedback_abba_tilt.md lines 25, "Crop-to-tissue pilot finding (2026-07-06): ... Decision: ...") — reuse this exact "what was tried, what was found, Decision: X" shape for recording per-section overlay-fit outcomes and any D-05 outlier overrides.
- Cross-reference existing memory notes by name (`[[feedback-abba-tilt]]`, `[[feedback-abba-channel-index]]`) as this file already does.

**Suggested location:** `.planning/phases/06-registration-speedup/06-REG03-SOP.md` (or fold into the phase's SUMMARY/REVIEW doc, following the `05-*` phase directory's `-SUMMARY.md`/`-REVIEW.md` convention observed in `.planning/phases/05-.../`).

---

### REG-05 keep/reject findings record (markdown)

**Analog:** `~/.claude/.../memory/feedback_abba_tilt.md` lines 25 (the "Crop-to-tissue pilot finding" paragraph) is the *exact* pattern already used in this project for an a-priori-rule-then-outcome record: states what was tried, the empirical finding, and ends with an explicit **`Decision: ...`** line. Copy this shape precisely for D-07's mandatory "recorded either way" requirement:
```markdown
**REG-05 masked-elastix trial finding (<date>):** Trialed on <worst-fitting section id>
per D-06. Fixed image: <atlas AP mm> via extract_atlas_plate.py. Moving: crop_to_tissue.py
output, DAPI channel index 2. Elastix Par_Affine.txt + Par_BSpline.txt, masked both sides.
Operator visual comparison at LA/BA boundary + ventral edge vs. BigWarp-only result:
<description>. **Decision: KEEP / REJECT** — <one-line justification tied to D-07's
quality-only rule, time irrelevant>.
```
**Suggested location:** same phase directory, e.g. `.planning/phases/06-registration-speedup/06-REG05-FINDINGS.md`, or as a new dated memory note (`~/.claude/.../memory/`) if the decision is expected to recur across future series — follow whichever convention the executor's phase output template already uses (check `05-REVIEW.md` for the precedent of where phase-level empirical outcomes get recorded).

---

## Shared Patterns

### Script header docstring + env/usage convention
**Source:** `scripts/crop_to_tissue.py` lines 1-17, `czi_mip.py` lines 1-28
**Apply to:** `extract_atlas_plate.py`, `elastix_trial_harness.py`
```python
"""
<One-line purpose>
<2-4 sentence description of algorithm/IO>

CPU-only. Runs in the `braian` conda env.

Usage:
  conda run -n braian python3 <script>.py <required-args>

  # Synthetic self-test (no large files/downloads needed):
  conda run -n braian python3 <script>.py --self-test
"""
```

### `--self-test` CLI convention (project-wide test framework)
**Source:** `scripts/crop_to_tissue.py` lines 178-260 (`_self_test()`), 293-309 (flag wiring)
**Apply to:** all three new/modified Python scripts (`extract_atlas_plate.py`, `elastix_trial_harness.py`)
```python
parser.add_argument(
    "--self-test", action="store_true",
    help="Run the synthetic self-test (no input file needed) and exit",
)
...
def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
        return
    if args.input is None:
        print("ERROR: input path is required (unless --self-test)", file=sys.stderr)
        sys.exit(2)
```
This is the project's only test framework (per 06-RESEARCH.md Validation Architecture: "none (project convention: a `--self-test` CLI flag with synthetic in-script assertions)"). No pytest, no fixtures — every new script gets this flag and nothing else.

### Progress/logging convention
**Source:** CLAUDE.md "Progress / Logging" section; `crop_to_tissue.py` lines 316-369, `czi_mip.py` lines 196-282
**Apply to:** all new scripts
- Top-level steps: `print("Step N: name...")` — no indent.
- Sub-detail: `print(f"  detail")` — 2-space indent.
- Inner loop detail: `print(f"    inner")` — 4-space indent.

### Error handling convention
**Source:** `crop_to_tissue.py` lines 69-73, 78-80, 87-90, 121-122; `czi_mip.py` lines 132-137, 210-211, 241-244, 270-273
**Apply to:** all new scripts
No try/except wrapping of business logic. Raise `ValueError(f"...descriptive message with actual values...")` for programmer/data errors inside helpers; raise `SystemExit(f"FATAL: ...")` at the `main()` level for CLI-facing fatal conditions (e.g. missing files, shape mismatches, out-of-range indices). Always include the offending value(s) in the message.

### Input-path validation (ASVS V5, per 06-RESEARCH.md Security Domain)
**Source:** 06-RESEARCH.md Security Domain table; pattern precedent in `crop_to_tissue.py`'s argparse `type=Path` + explicit existence/shape checks before any file I/O
**Apply to:** `extract_atlas_plate.py`, `elastix_trial_harness.py`
Validate that every path argument exists and is the expected type (file vs. dir) before passing it into `tifffile`/`brainglobe_atlasapi` calls or into a `subprocess.run` argv — matches the existing `crop_to_tissue.py`/`czi_mip.py` explicit-check style, and specifically for the elastix harness: never build a shell string, always `subprocess.run([...], shell=False)`.

### Deploy convention (Phase 1 precedent, unchanged)
**Source:** `.planning/phases/01-atlas-registration-and-roi-loading/01-CONTEXT.md` (per 06-CONTEXT.md canonical_refs); `scripts/01_load_abba_rois.groovy` header comment lines 12-13
**Apply to:** any Groovy touched this phase (none new — `01_load_abba_rois.groovy` is read-only downstream this phase)
Author canonically in `/home/jflab/Analysis/scripts/`; hard-copy into the QuPath project's `scripts/` directory for GUI "Run for project" access. Not applicable to the Python/config files this phase creates (those are operator-run standalone, not QuPath-project scripts).

### Findings/decision record convention (markdown)
**Source:** `~/.claude/.../memory/feedback_abba_tilt.md` line 25
**Apply to:** REG-03 operator SOP record, REG-05 keep/reject findings record
State: what was tried → what was empirically found → an explicit bolded **Decision: ...** line with a one-sentence justification. This is the project's established idiom for recording a-priori-rule outcomes (already used once for the crop-to-tissue pilot).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `scripts/elastix_params/Par_Affine.txt` | config | n/a | No parameter-file config exists anywhere in the repo yet; content sourced from 06-RESEARCH.md's cited elastix.dev standard component set, not an in-repo pattern |
| `scripts/elastix_params/Par_BSpline.txt` | config | n/a | Same as above |
| `scripts/bigwarp_effort_log.csv` | data/config | batch | Purely an operator-filled log artifact; schema is pinned by 06-VALIDATION.md, not derived from existing code |
| `scripts/elastix_trial_harness.py` (subprocess-wrapping aspect specifically) | utility | event-driven | No existing script in this repo wraps an external CLI tool via `subprocess`; only the argparse/self-test *skeleton* has an analog (`crop_to_tissue.py`), the subprocess-argv-construction core does not |

## Metadata

**Analog search scope:** `/home/jflab/Analysis/scripts/`, `/home/jflab/Analysis/czi_mip.py`, `/home/jflab/Analysis/.planning/phases/01-*`, `/home/jflab/Analysis/.planning/phases/05-*`, `~/.claude/projects/-home-jflab-Analysis/memory/*.md`
**Files scanned:** `scripts/crop_to_tissue.py` (374 lines, full read), `czi_mip.py` (287 lines, full read), `scripts/01_load_abba_rois.groovy` (90 lines, full read), `~/.claude/.../memory/feedback_abba_tilt.md` (full read), 06-CONTEXT.md, 06-RESEARCH.md
**Pattern extraction date:** 2026-07-19
