# Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity - Pattern Map

**Mapped:** 2026-07-18
**Files analyzed:** 4 (2 targets are edits of existing files; 2 are net-new or new-artifact-emitting)
**Analogs found:** 4 / 4 (1 target has two candidate analogs to choose between; 1 sub-pattern — thumbnail PNG — has no direct repo analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `czi_mip.py` (extend, per CONTEXT.md D-04/D-05, canonical file to edit) | utility / conversion script | batch, file-I/O | `czi_hybrid_mip.py` (`/home/jflab/Analysis/czi_hybrid_mip.py`) | role-match, structurally superior (CLI + OME-XML builder already generalized) |
| `czi_mip.py` (current body, for comparison) | utility / conversion script | file-I/O | itself — `czi_mip.py` (`/home/jflab/Analysis/czi_mip.py`) | exact-file but single-scene/hardcoded; use only as "what to remove" reference |
| Scene-identity artifact emitter (thumbnail PNG + text record, D-01/D-02) — new code inside the CONV-01/02 script, not a separate file | utility / transform (image downsample + stdout print) | file-I/O, batch | No direct repo analog (no existing PIL/thumbnail script found) — closest conceptual precedent is v1.0's ad-hoc overlay PNGs referenced in CONTEXT.md, but those were not committed as reusable script code (see "No Analog Found") | none — synthesize from RESEARCH.md Pattern 2 |
| `scripts/03_export_val01_metrics.groovy` (edit in place, EXP-02 fix) | route / export script (QuPath Groovy, "Run for project") | batch, file-I/O | `scripts/run_braian_detection.groovy` (primary, lines 79-81) and `scripts/export_region_dapi_reference.groovy` (secondary, lines 41-42) | exact — same repo, same idiom, already used twice |
| `scripts/val01_metrics.py` (read-only reference; column-contract constants must NOT change) | consumer / validation script | batch, transform | itself — `scripts/val01_metrics.py` (`/home/jflab/Analysis/scripts/val01_metrics.py`) | exact — this IS the contract, not something to pattern-match against another file |

## Pattern Assignments

### `czi_mip.py` (extend for CONV-01/CONV-02 — multi-scene MIP converter)

**Two candidate analogs.** CONTEXT.md names `czi_mip.py` as the canonical file to extend; RESEARCH.md recommends borrowing `czi_hybrid_mip.py`'s *shape* (CLI, channel-name-driven OME-XML builder, per-channel/per-Z streaming core) rather than continuing `czi_mip.py`'s current hardcoded body. Both are mapped below so the planner can decide how much of `czi_hybrid_mip.py`'s structure to graft onto `czi_mip.py`.

---

**Analog A (structure to copy): `czi_hybrid_mip.py`**

**Imports pattern** (lines 26-34):
```python
from __future__ import annotations

import argparse
from pathlib import Path

import aicspylibczi
import numpy as np
import tifffile
from scipy import ndimage as ndi
```
(Phase 5 additions: `import Pillow` for the D-01 thumbnail — `from PIL import Image` — no other new imports needed per RESEARCH.md Standard Stack.)

**CLI argparse pattern** (lines 43-63):
```python
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__
    )
    p.add_argument("--czi", type=Path, required=True, help="input CZI mosaic")
    p.add_argument("--out", type=Path, required=True, help="output hybrid OME-TIFF")
    p.add_argument("--channels", nargs="+", default=DEFAULT_CHANNELS,
                   help=f"channel names in physical read order (default {DEFAULT_CHANNELS})")
    ...
    return p.parse_args()
```
Phase 5's converter needs an analogous CLI: `--czi`, `--outdir` (not a single `--out`, since 5 files are emitted), `--channels`, `--pixel-um`, `--animal-prefix` (default `wBA1-3` per D-04) — same `RawDescriptionHelpFormatter` + `epilog=__doc__` convention (matches `.claude/CLAUDE.md`'s documented CLI Pattern section).

**Channel-name-driven OME-XML builder** (lines 92-110):
```python
def _build_ome_xml(names: list[str], x: int, y: int, pixel_um: float) -> str:
    chans = "\n".join(
        f'      <Channel ID="Channel:0:{i}" Name="{n}" SamplesPerPixel="1"/>'
        for i, n in enumerate(names)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<OME xmlns="http://www.openmicroscopy.org/Schemas/OME/2016-06"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.openmicroscopy.org/Schemas/OME/2016-06 http://www.openmicroscopy.org/Schemas/OME/2016-06/ome.xsd">
  <Image ID="Image:0" Name="{Path.cwd().name}_hybrid">
    <Pixels ID="Pixels:0" Type="uint16" DimensionOrder="XYZCT"
            SizeX="{x}" SizeY="{y}" SizeZ="1" SizeC="{len(names)}" SizeT="1"
            PhysicalSizeX="{pixel_um}" PhysicalSizeXUnit="µm"
            PhysicalSizeY="{pixel_um}" PhysicalSizeYUnit="µm">
{chans}
      <TiffData/>
    </Pixels>
  </Image>
</OME>"""
```
This is the pattern to copy verbatim for CONV-01's per-scene OME-XML — replace the hardcoded `Name="M3_20x_MIP"` / hardcoded 3-channel block in `czi_mip.py`'s current lines 56-74 with this generic, `names`-driven version. For Phase 5, `Image ID="Image:0" Name=...` should be set to `f"wBA1-3_s{N}"` per scene (D-04 filename convention), not `Path.cwd().name`.

**Channel-count validation guard** (lines 116-121):
```python
    dim0 = czi.get_dims_shape()[0]
    n_c = dim0.get("C", (0, 1))[1]
    n_z = dim0.get("Z", (0, 1))[1]
    print(f"CZI: {args.czi.name}  channels={n_c}  z-planes={n_z}")
    if len(args.channels) != n_c:
        raise SystemExit(f"--channels has {len(args.channels)} names but CZI has {n_c} channels")
```
⚠ RESEARCH.md Pitfall 2 flags exactly this `dims[0]`/`'S'`-field trap as unsafe for scene *count* (must use `len(get_all_mosaic_scene_bounding_boxes())` instead) — but `dim0.get("C", ...)` / `dim0.get("Z", ...)` for channel/Z count is still valid since C/Z are consistent across scenes on this file (confirmed C=3, Z=4 in CONTEXT.md). Keep this guard, don't reuse `n_s` from `dim0`.

**Output-shape / write idiom** (lines 143-154):
```python
    img = np.stack(out_planes, axis=0)   # (C, Y, X)
    ...
    C, Y, X = img.shape
    ome = _build_ome_xml(args.channels, X, Y, args.pixel_um)
    print(f"Writing {args.out}  ({C}, {Y}, {X}) uint16 ...")
    tifffile.imwrite(str(args.out), img, photometric="minisblack", description=ome.encode())
    print(f"Done: {args.out}")
```
Reuse verbatim per scene inside the new scene loop (see RESEARCH.md Pattern 1/2 for the loop shape itself — `for scene_idx in sorted(bboxes): ... region=(b.x,b.y,b.w,b.h) ... N=scene_idx+1`).

---

**Analog B (file identity / progress-print convention, current `czi_mip.py` body — what NOT to keep):**

**Progress-print convention** (lines 20-23, 37, 40-49) — matches `.claude/CLAUDE.md`'s documented Progress/Logging convention (top-level unindented, sub-steps 2-space indent):
```python
print("Opening CZI...")
czi = aicspylibczi.CziFile(F_IN)
...
print("Generating MIP (this will take a few minutes for a full-section mosaic)...")
mip_channels = []
for c in range(n_c):
    print(f"  Channel {c}/{n_c-1}: reading {n_z} z-planes...", flush=True)
    stack = []
    for z in range(n_z):
        plane = czi.read_mosaic(C=c, Z=z, scale_factor=1.0)
        stack.append(plane.squeeze())
        print(f"    z={z} shape={plane.shape} dtype={plane.dtype}", flush=True)
```
Keep this per-channel/per-Z streaming MIP core and its print-indent convention — it is the "per-channel/per-Z streaming MIP core" RESEARCH.md's summary calls directly reusable — but wrap it inside the new scene loop with `region=bbox` on every `read_mosaic()` call (Pitfall 6: pass the bbox tuple verbatim, do not offset by `b.x`/`b.y`).

**What must be discarded from `czi_mip.py`'s current body:**
- Hardcoded `F_IN`/`F_OUT` module-level string constants (lines 15-16) → replace with argparse per Analog A.
- `n_s = dim0.get('S', (0, 1))[1]` (line 30) → RESEARCH.md Pitfall 2: silently wrong on multi-scene files; delete, use `len(czi.get_all_mosaic_scene_bounding_boxes())`.
- Hardcoded 3-channel `<Channel Name=.../>` block + `Name="M3_20x_MIP"` (lines 61-70) → replace with Analog A's `_build_ome_xml(names, ...)`.

---

### Scene-identity verification artifact (CONV-02, D-01/D-02) — thumbnail PNG + text record

**No direct analog file in the repo.** CONTEXT.md's "in the spirit of v1.0's overlay PNGs" refers to `.planning/phases/03-detection-script-and-single-section-end-to-end-test/plane_experiment_overlay.png` and `plane_experiment_dapi.png` — these exist as *committed output artifacts* from Phase 3 but there is no corresponding checked-in Python script that generated them (searched `*.py` for `PIL`/`matplotlib`/`Image.fromarray` repo-wide — zero hits). They were most likely produced by ad-hoc inline code during Phase 3 execution, not saved as reusable script.

**Recommendation for the planner:** synthesize this directly from RESEARCH.md's own worked example (already grounded against the real CZI this session, not hypothetical):

**Text record + thumbnail pattern** (RESEARCH.md "Pattern 2", verified against `-001-07_processed.czi`):
```python
M = dims_by_scene[scene_idx]['M'][1]
print(f"scene_key={scene_idx} (0-based)  label=s{N} (1-based)  "
      f"bbox=(x={b.x}, y={b.y}, w={b.w}, h={b.h})  M_tiles={M}  "
      f"dims=({b.h}, {b.w})")

from PIL import Image
import numpy as np
lo, hi = np.percentile(dapi_plane, [1, 99.5])
norm = np.clip((dapi_plane.astype(np.float32) - lo) / (hi - lo + 1e-6), 0, 1)
thumb = Image.fromarray((norm[::8, ::8] * 255).astype(np.uint8))  # 8x downsample
thumb.save(out_dir / f"wBA1-3_s{N}_identity.png")
```
This reuses the DAPI plane already read for the MIP itself (no extra CZI read) — normalization idiom (`np.percentile` 1/99.5 clip-and-cast to uint8) mirrors the "Normalisation for 8-bit: percentile clip then cast" convention already documented in `.claude/CLAUDE.md`'s Array/NumPy Conventions section, so this is consistent with project norms even without a direct file analog.

---

### `scripts/03_export_val01_metrics.groovy` (EXP-02 fix — per-entry output filenames)

**Analog (primary): `scripts/run_braian_detection.groovy`, lines 79-81**
```groovy
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set).collect { java.util.regex.Pattern.quote(it) }.join('|')
def imageName = getProjectEntry().getImageName().replaceAll(invalidChars, '')
var resultsFile = new File(buildPathInProject("results", imageName + "_regions.tsv"))
```

**Analog (secondary, confirms the idiom is already used twice): `scripts/export_region_dapi_reference.groovy`, lines 41-42**
```groovy
def entry = getProjectEntry()
def imageName = entry != null ? entry.getImageName() : server.getMetadata().getName()
```
Note this second file's null-fallback (`entry != null ? ... : server.getMetadata().getName()`) is a slightly more defensive variant worth folding in — `03_export_val01_metrics.groovy` currently reads the image name only via `getCurrentImageData().getServer().getMetadata().getName()` (its own line 37), which does not use `getProjectEntry()` at all.

**Exact edit target in `03_export_val01_metrics.groovy` (current, lines 145-148, 184):**
```groovy
def resultsDir = new File(getProject().getBaseDirectory(), "results")
resultsDir.mkdirs()

def percellFile = new File(resultsDir, "val01_percell_export.tsv")
...
def regionFile = new File(resultsDir, "val01_region_area.tsv")
```
**Replace with** (per RESEARCH.md Pattern 3 / Code Examples, and D-06/D-07's exact filename spec):
```groovy
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
    .collect { java.util.regex.Pattern.quote(it) }.join('|')
def entry = getProjectEntry()
def stem = (entry != null ? entry.getImageName() : getCurrentImageData().getServer().getMetadata().getName())
    .replaceAll(invalidChars, '')

def percellFile = new File(buildPathInProject("results", "${stem}__val01_percell_export.tsv"))
def regionFile  = new File(buildPathInProject("results", "${stem}__val01_region_area.tsv"))
```
Everything downstream of these two lines (row-building at lines 148-166 and 184-192, headers, `.text =` truncate-write semantics) stays **unchanged** — D-07 explicitly locks the column contract. Only the `File` construction changes; `resultsDir.mkdirs()` becomes unnecessary since `buildPathInProject` resolves relative to the QuPath project base dir directly (matches `run_braian_detection.groovy`'s usage, which never calls `.mkdirs()` on `results/` either — QuPath's project scaffolding already creates it).

**Deploy convention (per CONTEXT.md canonical_refs and the file's own header comment, lines 29-30):** author the fix in `scripts/03_export_val01_metrics.groovy`, then hard-copy byte-identically into `<QuPath project>/scripts/03_export_val01_metrics.groovy` — confirmed this dual-location convention already exists: `M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy` is a second copy of the same file in the repo.

---

### `scripts/val01_metrics.py` (downstream consumer — column contract, read-only reference)

**Column-contract constants that MUST NOT change** (`/home/jflab/Analysis/scripts/val01_metrics.py`, lines 53-57):
```python
PERCELL_EXPECTED_COLS = [
    "class", "region_label", "nucleus_area_um2",
    "centroid_x_px", "centroid_y_px", "fos_bgsub", "tdt_bgsub",
]
REGION_EXPECTED_COLS = ["region_label", "hemisphere", "acronym", "is_leaf", "area_mm2"]
```
Enforced at load time via `_load_tsv()` (lines 78-87):
```python
def _load_tsv(path: Path, expected_cols: list[str], label: str) -> pd.DataFrame:
    if not path.exists():
        sys.exit(f"ERROR: {label} TSV not found: {path}\n"
                  f"Run 03_export_val01_metrics.groovy in QuPath first (AFTER 02_detect_classify.groovy).")
    df = pd.read_csv(path, sep="\t")
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        sys.exit(f"ERROR: {label} TSV {path} is missing expected column(s): {missing}\n"
                  f"Found columns: {list(df.columns)}")
    return df
```
This already fails loudly (`sys.exit`) on a header mismatch — RESEARCH.md's Validation Architecture table confirms "no new test needed" here; EXP-02's fix must change only the *path*, never the header row emitted by `03_export_val01_metrics.groovy`'s `percellHeader`/`regionHeader` (lines 151, 185 of the groovy file). Note also `DEFAULT_PERCELL_TSV`/`DEFAULT_REGION_TSV` (lines 43-44) point at the single-entry M3 path and are NOT updated by this phase — Phase 5 only fixes the Groovy export side; any multi-file aggregation of the 5 new per-entry TSVs is explicitly out of scope here (deferred to Phase 10 AGG-01 per CONTEXT.md's Integration Points).

---

## Shared Patterns

### Filesystem-safe stem sanitization (Groovy)
**Source:** `scripts/run_braian_detection.groovy` lines 79-80; confirmed identical in `scripts/export_region_dapi_reference.groovy` lines 30-42
**Apply to:** `scripts/03_export_val01_metrics.groovy` (EXP-02 fix) — this is the only file this phase touches that needs it, but any future "Run for project" script needing a per-entry filename should reuse the same idiom.
```groovy
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
    .collect { java.util.regex.Pattern.quote(it) }.join('|')
def stem = someEntryName.replaceAll(invalidChars, '')
```

### Project-relative path construction (Groovy)
**Source:** `scripts/run_braian_detection.groovy` line 81 (`buildPathInProject`); confirmed against QuPath 0.6.0 javadoc by RESEARCH.md
**Apply to:** `scripts/03_export_val01_metrics.groovy`
```groovy
new File(buildPathInProject("results", "${stem}__suffix.tsv"))
```
Do not hand-roll `new File(getProject().getBaseDirectory(), "results")` string-gluing (RESEARCH.md "Don't Hand-Roll" table) — `03_export_val01_metrics.groovy`'s current line 145 does exactly this and should be replaced by the `buildPathInProject` idiom during the fix, matching the sibling scripts.

### Pixel-calibration read idiom (Groovy, shared convention already used across scripts — not part of this phase's edit, but do not disturb it)
**Source:** `scripts/03_export_val01_metrics.groovy` lines 41-51; same idiom in `scripts/export_region_dapi_reference.groovy` lines 24-28
```groovy
def imageData = getCurrentImageData()
def server = imageData.getServer()
def cal = server.getPixelCalibration()
def FALLBACK_PIXEL_SIZE_UM = 0.6905355
def pixelUm = FALLBACK_PIXEL_SIZE_UM
if (cal != null && cal.hasPixelSizeMicrons()) {
    pixelUm = cal.getAveragedPixelSizeMicrons()
}
```
Untouched by EXP-02's fix (D-07 scope is filename-only) — flagged here only so the planner knows this block is off-limits.

### Percentile-clip 8-bit normalization (Python)
**Source:** `.claude/CLAUDE.md` Array/NumPy Conventions ("Normalisation for 8-bit: percentile clip then cast: `np.clip(...).astype(np.uint8)`") — no single file analog, but this is the documented project-wide convention the new thumbnail code (D-01) should follow, and RESEARCH.md's own Pattern 2 example already applies it.

### CLI scaffold convention (Python)
**Source:** `czi_hybrid_mip.py` lines 43-63 (`argparse.RawDescriptionHelpFormatter`, `epilog=__doc__`, `type=Path` args) — matches `.claude/CLAUDE.md`'s documented "CLI Pattern" section verbatim; reuse for the extended `czi_mip.py`'s new argparse interface.

## No Analog Found

| File / Sub-pattern | Role | Data Flow | Reason |
|---------------------|------|-----------|--------|
| Scene-identity thumbnail PNG generator (D-01) | utility (image downsample + save) | file-I/O | No PIL/matplotlib/thumbnail-generation Python script exists anywhere in the repo (verified via repo-wide grep for `PIL`/`Image.fromarray`/`matplotlib` imports — zero hits outside `.planning/` binary artifacts). The v1.0 "overlay PNGs" CONTEXT.md references (`plane_experiment_overlay.png`, `plane_experiment_dapi.png`) are committed *output images* only — their generating code was not checked in. Planner should synthesize this from RESEARCH.md's own Pattern 2 code example (already grounded against the real CZI) plus `.claude/CLAUDE.md`'s documented percentile-clip-to-uint8 normalization convention, rather than searching for a nonexistent analog file. |

## Metadata

**Analog search scope:** `/home/jflab/Analysis` root (`czi_mip.py`, `czi_hybrid_mip.py`), `/home/jflab/Analysis/scripts/` (all `.groovy` and `val01_metrics.py`), repo-wide grep for PIL/matplotlib usage, `.planning/phases/03-*/` for the v1.0 overlay-PNG precedent.
**Files scanned:** 7 read in full (`czi_mip.py`, `czi_hybrid_mip.py`, `run_braian_detection.groovy`, `export_region_dapi_reference.groovy`, `03_export_val01_metrics.groovy`, `val01_metrics.py`) + repo-wide greps for PIL/thumbnail code (none found) + directory listing of Phase 3 artifacts.
**Pattern extraction date:** 2026-07-18
