---
phase: 260706-kfm
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/crop_to_tissue.py
autonomous: true
requirements: [QUICK-CROP-01]
must_haves:
  truths:
    - "Running crop_to_tissue.py on a MIP OME-TIFF writes a cropped OME-TIFF containing all channels."
    - "The DAPI channel is selected by name (case-insensitive substring 'DAPI') with a --dapi-channel override accepting a name or an integer index."
    - "Output pixel calibration (PhysicalSizeX/Y in µm) equals the input, unchanged by cropping."
    - "Cropped dimensions are smaller than input dimensions and the tissue bounding box (plus margin) is reported."
    - "Crop stats (original dims, tissue bbox, cropped dims, tissue-fill fraction) are printed to stdout."
  artifacts:
    - "/home/jflab/Analysis/scripts/crop_to_tissue.py"
  key_links:
    - "DAPI channel name match → correct channel used for the tissue mask"
    - "Input OME-XML PhysicalSize → output OME-XML PhysicalSize (preserved unchanged)"
    - "Downsampled mask bounding box → full-resolution crop indices (scaled back correctly)"
---

<objective>
Build a reusable DAPI→tissue-mask→auto-crop CLI script, `scripts/crop_to_tissue.py`, that reads a MIP OME-TIFF, thresholds the DAPI channel (Otsu) into a binary tissue mask, cleans the mask (morphological close + fill holes + small-object removal), computes the tissue bounding box plus a small margin, crops all channels to that box, and writes a cropped OME-TIFF that preserves the input's micron pixel calibration and channel names.

Purpose: Feed cropped MIPs to ABBA's native elastix so tissue fills ~90% of the frame, making elastix Affine/Spline viable for the full section series (Path A of the masked-elastix pilot) — a pilot to compare cropped-elastix against the current BigWarp-only workflow (per the locked "No Affine+Spline in ABBA" decision, which this pilot is testing whether to revisit).

Output: `scripts/crop_to_tissue.py` (CPU-only, runs in the `braian` conda env) and a validated cropped OME-TIFF of the M3 hippocampus MIP.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@/home/jflab/Analysis/.planning/STATE.md
@/home/jflab/Analysis/CLAUDE.md
@/home/jflab/Analysis/.claude/CLAUDE.md

# Canonical script to match for style/conventions (argparse pattern, OME-XML builder,
# pixel-calibration handling, _private helpers, progress printing, PEP 604 type hints):
@/home/jflab/Analysis/czi_mip.py

# Environment facts confirmed during planning (do NOT re-verify — treat as given):
# - `braian` env has: numpy 2.1.3, scipy 1.17.1, scikit-image 0.26.0, tifffile 2026.3.3, imagecodecs.
#   Invoke everything via `conda run -n braian python3 ...`. CPU-only; no GPU libraries.
# - Real test MIP (confirmed to exist): "/home/jflab/Analysis/M3 Hippocampus 20x 062226/M3_20x_MIP.ome.tiff"
#     shape (C=3, Y=10240, X=15770) uint16; PhysicalSizeX = 0.6905355 µm;
#     channel names (in file order) = ["AF568-T2", "AF488-T3", "DAPI-T4"].
#   NOTE: DAPI is the LAST channel (index 2), not index 0 — this is exactly why channel
#   selection MUST be by name, never a hardcoded index. See feedback_channel_order.md.
# - The input OME-XML carries channel names + PhysicalSizeX/Y in its `description` (OME-XML string),
#   readable via `tifffile.TiffFile(path).ome_metadata`. Parse names + pixel size + unit from it.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement crop_to_tissue.py (DAPI mask → bbox → crop → OME-TIFF) with a synthetic --self-test</name>
  <files>/home/jflab/Analysis/scripts/crop_to_tissue.py</files>
  <behavior>
    Assertable behavior exercised by a built-in `--self-test` (synthetic in-memory arrays, no large files):
    - Given a synthetic (C=3, Y, X) uint16 array whose DAPI channel (placed at index 2, mirroring the
      real AF568/AF488/DAPI ordering) has a bright rectangular blob in a known sub-region on a zero
      background, `_compute_tissue_mask` recovers the blob and `_tissue_bbox` returns the blob's extent.
    - DAPI selection by name (case-insensitive substring "DAPI") returns index 2 even though DAPI is NOT
      index 0; `--dapi-channel 2` and `--dapi-channel DAPI` and `--dapi-channel dapi-t4` all resolve the same.
    - Applying a margin expands the bbox but CLAMPS at image edges: a blob flush against an edge yields no
      negative index and no index past the array bound.
    - The cropped array has shape (C, bbox_h_with_margin, bbox_w_with_margin), dtype uint16 preserved,
      and channel count/order unchanged.
    - A round-trip through `_build_ome_xml` preserves the supplied pixel size and channel names verbatim.
    - `--self-test` prints "SELF-TEST PASS" and exits 0 on success; asserts (nonzero exit) on any failure.
  </behavior>
  <action>
Create `/home/jflab/Analysis/scripts/crop_to_tissue.py` matching czi_mip.py conventions exactly: `from __future__ import annotations` first (enables PEP 604 `X | None` hints), a module docstring with a Usage block, `argparse` with `formatter_class=argparse.RawDescriptionHelpFormatter` and `epilog=__doc__`, `type=Path` for file args, snake_case throughout, `_`-prefixed private helpers, `Path` objects (not raw strings), and progress prints ("Step ..." at top level, 2-space-indented sub-steps).

Imports: `argparse`, `Path` from `pathlib`, `re`, `sys`, `numpy as np`, `tifffile`, and from scikit-image/scipy: `threshold_otsu` (skimage.filters), `binary_closing`, `remove_small_objects`, `disk` (skimage.morphology), and `binary_fill_holes` (scipy.ndimage). CPU-only — do not import or reference any GPU/CUDA library.

CLI (parse_args): positional `input` (`type=Path`); `--output`/`-o` (`type=Path`, default None → derive `<input_stem>_cropped.ome.tiff` beside the input); `--dapi-channel` (str, default None — accepts a channel NAME substring or an integer index; when None, auto-match the first channel whose OME-XML name contains "DAPI" case-insensitively); `--margin-percent` (float, default 5.0 — margin added on EACH side as a percentage of the tissue bbox extent per axis, so tissue fills ~1/(1+2·margin) of each cropped axis); `--mask-downsample` (int, default 0 → auto: choose an integer factor so the DAPI channel's larger axis is ≈2048 px for fast CPU Otsu/morphology); `--min-object-frac` (float, default 0.001 — remove connected components smaller than this fraction of the (downsampled) frame area before taking the bbox, to stop stray bright specks from inflating the box); `--self-test` (store_true — run the synthetic self-test and exit).

Helpers to implement:
- `_read_mip(path: Path) -> tuple[np.ndarray, list[str], float, str]`: load the array with `tifffile.imread` (expect (C, Y, X) uint16; if a singleton Z/T axis appears, squeeze to (C, Y, X)); read OME-XML via `tifffile.TiffFile(path).ome_metadata`; extract channel names with `re.findall(r'Name="([^"]+)"', ...)` scoped to Channel elements, PhysicalSizeX with `re.findall(r'PhysicalSizeX="([^"]+)"', ...)`, and the unit with `PhysicalSizeXUnit="([^"]+)"` (default "µm" — the Unicode mu, not "um"). Return (array, channel_names, pixel_um, unit).
- `_select_dapi_index(channel_names, override) -> int`: if override is None, return the first index whose name contains "dapi" (lowercased); if override is an all-digits string, return int(override); else return the first index whose lowercased name contains the lowercased override. Raise a clear ValueError listing the available names if nothing matches.
- `_compute_tissue_mask(dapi: np.ndarray, downsample: int, min_object_frac: float) -> tuple[np.ndarray, int]`: downsample by simple strided slicing `dapi[::f, ::f]` (resolve auto factor here when downsample==0), Otsu-threshold the downsampled image, `binary_closing` with a `disk(...)` footprint, `binary_fill_holes`, then `remove_small_objects(mask, min_size=int(min_object_frac * mask.size))`. Return (cleaned_downsampled_mask, factor_used).
- `_tissue_bbox(mask, factor, full_shape, margin_percent) -> tuple[int,int,int,int]`: derive y/x extents from the downsampled mask via `np.any(mask, axis=...)`; scale bbox coords back to full resolution by multiplying by `factor` (clamp the far edge to full_shape); compute per-axis margin as `margin_percent/100 * extent`, expand, and CLAMP to [0, full_dim]. Return (y0, y1, x0, x1) as full-resolution ints. Raise a clear error if the mask is empty (no tissue found).
- `_build_ome_xml(C, Y, X, channel_names, pixel_um, unit) -> str`: mirror czi_mip.py's OME-XML exactly (Type="uint16", DimensionOrder="XYZCT", SizeZ=1, SizeT=1, PhysicalSizeX/Y + unit), but emit SizeC and one `<Channel ID="Channel:0:{i}" Name="{name}" SamplesPerPixel="1"/>` per preserved channel name — do NOT hardcode names or channel count.
- `_self_test() -> None`: build the synthetic case described in <behavior>, exercise the helpers, assert every listed property, print "SELF-TEST PASS", and let assertion failures propagate (nonzero exit).

`main()`: if `--self-test`, call `_self_test()` and return. Otherwise: Step 1 read the MIP and print original dims + detected channel names + pixel size; Step 2 select the DAPI channel (print which name/index was chosen); Step 3 compute the mask and bbox (print the downsample factor used); Step 4 crop ALL channels `array[:, y0:y1, x0:x1]` (keep dtype uint16, order (C,Y,X)); Step 5 write with `tifffile.imwrite(out, cropped, photometric="minisblack", metadata=None, description=_build_ome_xml(...).encode())`. Then print a stats block: original (Y,X), tissue bbox (y0,y1,x0,x1), cropped (Y,X), the bbox-occupancy fill fraction (bbox area ÷ cropped-frame area — the geometric "tissue fills ~N% of frame" number the researcher confirms against ~90%), AND the foreground-pixel coverage of the cropped frame (mask-true pixels ÷ cropped-frame pixels) as a secondary tissue-coverage stat. Print the output path last.

Do NOT alter the array values or dtype (cropping changes extent only, never pixel size). Preserve the µm unit literally.
  </action>
  <verify>
    <automated>conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py --help >/dev/null && conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py --self-test</automated>
  </verify>
  <done>`--help` prints usage (RawDescriptionHelpFormatter + epilog) and exits 0; `--self-test` prints "SELF-TEST PASS" and exits 0, proving DAPI-by-name selection (DAPI at index 2), Otsu mask + bbox recovery, edge-clamped margin, dtype/channel preservation, and OME-XML calibration/name round-trip.</done>
</task>

<task type="auto">
  <name>Task 2: End-to-end smoke crop of the real M3 hippocampus MIP and validate the pilot artifact</name>
  <files>/home/jflab/Analysis/M3 Hippocampus 20x 062226/M3_20x_MIP_cropped.ome.tiff</files>
  <action>
Run the script end-to-end on the confirmed real MIP to produce the pilot deliverable that will feed ABBA elastix. Use input `"/home/jflab/Analysis/M3 Hippocampus 20x 062226/M3_20x_MIP.ome.tiff"`; if that exact path is absent, glob `/home/jflab/Analysis/M3 Hippocampus 20x 062226/*MIP*.ome.tiff` and use the first match. Invoke: `conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py "<input>" -o "/home/jflab/Analysis/M3 Hippocampus 20x 062226/M3_20x_MIP_cropped.ome.tiff"` (default 5% margin). The write of the ~1 GB uncompressed array may take up to a minute — this is expected.

Inspect the printed stats block: confirm DAPI-T4 was auto-selected by name, cropped (Y,X) is smaller than the original (10240, 15770), and a tissue-fill fraction is reported (the geometric bbox-occupancy should land near ~90% per the 5% margin; the foreground-pixel coverage will be lower because tissue is irregular within its rectangular box — both are informational, do not fail on the exact value). If the crop is obviously wrong (empty mask error, or cropped dims equal to original), diagnose and fix the mask/bbox logic in Task 1's script rather than tuning around it.

Then re-read the output to prove calibration and channels survived the crop unchanged.
  </action>
  <verify>
    <automated>conda run -n braian python3 -c "import re,glob,tifffile,numpy as np; ip=glob.glob('/home/jflab/Analysis/M3 Hippocampus 20x 062226/*MIP*.ome.tiff'); ip=[p for p in ip if 'cropped' not in p][0]; op='/home/jflab/Analysis/M3 Hippocampus 20x 062226/M3_20x_MIP_cropped.ome.tiff'; oi=tifffile.imread(ip); oo=tifffile.imread(op); mi=tifffile.TiffFile(ip).ome_metadata or ''; mo=tifffile.TiffFile(op).ome_metadata or ''; px=lambda s: re.findall(r'PhysicalSizeX=\"([^\"]+)\"', s); nm=lambda s: re.findall(r'Name=\"([^\"]+)\"', s); assert oo.dtype==np.uint16, oo.dtype; assert oo.shape[0]==oi.shape[0], (oo.shape, oi.shape); assert oo.shape[-2] < oi.shape[-2] and oo.shape[-1] < oi.shape[-1], (oi.shape, oo.shape); assert px(mo)==px(mi) and px(mo), (px(mi), px(mo)); assert nm(mo)==nm(mi) and any('dapi' in n.lower() for n in nm(mo)), (nm(mi), nm(mo)); print('SMOKE OK', 'in', oi.shape, '-> out', oo.shape, 'pxX', px(mo), 'ch', nm(mo))"</automated>
  </verify>
  <done>`M3_20x_MIP_cropped.ome.tiff` exists; cropped dims are strictly smaller than the input on both Y and X; dtype uint16 and channel count/order preserved; output PhysicalSizeX equals the input's exactly; channel names (including a DAPI channel) preserved verbatim; the re-read assertion prints "SMOKE OK".</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| file → script | The input OME-TIFF is untrusted structured input (path, array shape, embedded OME-XML) crossing into the script. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-260706-01 | Tampering/DoS | `_read_mip` OME-XML parse + channel select | low | mitigate | Regex-extract names/pixel size defensively; if no DAPI channel matches, raise a clear ValueError listing available channel names (fail loud, never silently crop the wrong channel). Missing PhysicalSize unit defaults to "µm". |
| T-260706-02 | DoS | Full-array load of a ~1 GB MIP | low | accept | 61 GB RAM vs ~1 GB image is ample; mask work runs on a downsampled copy (auto factor to ≈2048 px) so morphology stays cheap on CPU. No streaming needed at this scale. |
| T-260706-SC | Tampering | package installs | low | accept | No new packages installed — all deps (numpy, scipy, scikit-image, tifffile, imagecodecs) already present in the `braian` env. No supply-chain surface introduced by this pilot. |
</threat_model>

<verification>
Overall phase checks:
1. `conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py --help` — usage prints, exit 0.
2. `conda run -n braian python3 /home/jflab/Analysis/scripts/crop_to_tissue.py --self-test` — prints "SELF-TEST PASS", exit 0 (synthetic mask/bbox/margin/calibration correctness).
3. Real-image smoke crop produces `M3_20x_MIP_cropped.ome.tiff` with preserved pixel calibration + channel names and reduced dims; re-read assertion prints "SMOKE OK".
4. DAPI selected by NAME (index 2 in the real file), never by hardcoded index — verified by both the self-test and the smoke assertion (`any('dapi' in n.lower() ...)`).
</verification>

<success_criteria>
- `scripts/crop_to_tissue.py` exists, matches czi_mip.py conventions, and is CPU-only (no GPU imports).
- DAPI channel is selected by case-insensitive name with a `--dapi-channel` name-or-index override.
- Output OME-TIFF preserves PhysicalSizeX/Y (µm) and channel names/order exactly; dtype uint16, order (C,Y,X).
- Cropping reduces frame extent to the tissue bbox + configurable margin (default 5%), clamped to image bounds.
- Crop stats (original dims, tissue bbox, cropped dims, tissue-fill fraction) print to stdout.
- The cropped M3 MIP artifact exists and is ready to feed ABBA's native elastix for the pilot.
</success_criteria>

<output>
Create `.planning/quick/260706-kfm-dapi-tissue-mask-auto-crop-cli-crop-to-t/260706-kfm-SUMMARY.md` when done.
</output>
