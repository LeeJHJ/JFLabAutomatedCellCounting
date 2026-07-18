# Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity - Research

**Researched:** 2026-07-18
**Domain:** Zeiss CZI multi-scene mosaic reading (aicspylibczi) + QuPath Groovy batch-export scripting
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Scene-identity verification artifact (CONV-02)**
- **D-01:** Per scene, emit **both** a downsampled thumbnail PNG (for visual eyeball verification, in the spirit of v1.0's overlay PNGs) **and** a printed text record (bbox coords, tile count M, dims). Belt-and-suspenders against a silent scene→section shuffle.
- **D-02:** The identity artifact (text + thumbnail label) MUST print **both** the raw 0-based scene key (`0..4`) **and** the human-facing 1-based label (`s1..s5`) — see D-05. This keeps the 0/1-based off-by-one from ever hiding a shuffle.

**AP-order handling**
- **D-03:** **Preserve raw scene index only; make NO anterior→posterior claim at conversion time.** Scene acquisition order is not assumed to equal anatomical AP order. DeepSlice sorts AP in Phase 6. CONV-02's job is scene→physical-section identity, not AP ordering.

**Output filename convention (the 5 MIP OME-TIFFs)**
- **D-04:** Pattern: **`wBA1-3_s{N}_MIP.ome.tiff`** with **1-based** `N` (`s1`..`s5`). Animal prefix `wBA1-3`. This filename becomes each section's identity through the whole series (QuPath entries, downstream exports).
- **D-05:** Off-by-one guard. The filename is 1-based (`s1..s5`) but the Python scene loop is 0-based (`0..4`): `s{N}` = scene loop index + 1. Because ROADMAP success-criterion #2 says "scene index written verbatim into the filename," the mapping must be unambiguous: the per-scene text/PNG record (D-01/D-02) prints the raw 0-based scene bbox key alongside the `s{N}` filename label, so `s1` is provably scene-0, `s5` is provably scene-4. Do not let the +1 translation live only implicitly in the loop.

**EXP-02 fix strategy**
- **D-06:** Disambiguate the 5 entries' outputs by deriving the output filename **stem from the QuPath image/entry name** (sanitized), all files **flat in `results/`**. The entry name is already each section's identity, so outputs are self-describing. e.g. `results/wBA1-3_s1__val01_percell_export.tsv`, `results/wBA1-3_s1__val01_region_area.tsv`.
- **D-07:** Both TSVs (`val01_percell_export` and `val01_region_area`) get the per-entry stem. Preserve the exact column contract `scripts/val01_metrics.py` parses (do not rename columns). The per-run truncate/overwrite semantics stay, but now scoped to a unique per-entry filename so entries no longer clobber each other.

### Claude's Discretion
- Thumbnail channel/size (DAPI vs composite, downsample factor) and exact text-record fields beyond {bbox, M tile count, dims} — pick sensible defaults.
- Sanitization rule for turning an entry name into a filesystem-safe stem (whitespace/`:`/`/` handling).
- Per-scene MIP memory strategy (per-channel/per-Z streaming vs whole-scene) — implementation detail; keep memory bounded on the 16 GB input as the existing `czi_mip.py` already does.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope (AP ordering explicitly deferred to Phase 6 / DeepSlice per D-03; that is a sequencing decision, not new scope).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONV-01 | `czi_mip.py` emits one MIP OME-TIFF per scene from the multi-scene processed CZI (5 section files), using `get_all_mosaic_scene_bounding_boxes()` + per-scene `read_mosaic(region=bbox)` so scenes are not fused | §Standard Stack, §Architecture Patterns Pattern 1, §Code Examples "Per-scene MIP loop", §Common Pitfalls 1/2/6 — API verified directly against the installed `aicspylibczi==3.3.1` and the real `-001-07_processed.czi` |
| CONV-02 | Each scene's output OME-TIFF is verified to the correct physical section (scene-identity / AP-order check via bounding box + morphology) before it enters registration | §Architecture Patterns Pattern 2 (identity artifact), §Code Examples "Scene identity record + thumbnail", §Validation Architecture |
| EXP-02 | `03_export_val01_metrics.groovy` is fixed for multi-entry batch execution — per-entry output filenames, no TSV truncation across the 5 sections | §Architecture Patterns Pattern 3, §Don't Hand-Roll, §Code Examples "Per-entry output stem (Groovy)" — reuses the exact idiom already established in `run_braian_detection.groovy` / `export_region_dapi_reference.groovy` |
</phase_requirements>

## Summary

This phase has two independent halves, and both risks were fully de-risked by **direct execution against the real project data** (the actual 16 GB `-001-07_processed.czi`, the actual installed `aicspylibczi==3.3.1`, and the actual repo scripts) rather than by documentation alone.

**CONV-01/CONV-02 (multi-scene MIP).** The installed `aicspylibczi` exposes `get_all_mosaic_scene_bounding_boxes()` returning a `dict[int, BBox]` keyed by 0-based scene index, each `BBox` carrying `.x/.y/.w/.h` in **global mosaic pixel coordinates**. Running this against the real CZI reproduces exactly the CONTEXT.md-confirmed 5 scenes with tile counts M=141/152/161/151/161. Critically, `read_mosaic()` for mosaic files does **not** take a scene selector via the `S=` kwarg — passing `S=` alongside `region=` raises `PylibCZI_CDimCoordinatesOverspecifiedException` with the literal message **"Do not set S when reading mosaic files!"** (confirmed by actually triggering it). Scene isolation is achieved **purely** by passing that scene's exact bounding-box tuple as `region=(x, y, w, h)` to `read_mosaic(region=..., C=c, Z=z)` — no `S=` kwarg. Reading a full-resolution single channel/Z-plane for scene 0 with this idiom returned an array whose shape exactly matched `(h, w)` from the bbox, in 0.65 s. All 5 scene bounding boxes were checked pairwise and are **non-overlapping** in global mosaic coordinates (verified programmatically — smallest gap is 62 px between S0/S1), so region-based cropping cannot pull in a neighboring scene's tiles as long as the bbox from `get_all_mosaic_scene_bounding_boxes()` is used verbatim (not padded or expanded). A visual sanity read (scale_factor=0.05, DAPI channel) of scene 0 renders a single, coherent, intact coronal section with no double-brain ghosting — direct visual confirmation that criterion #1 ("no scene fusion") holds for this idiom on this file. Channel identity was independently re-verified for the new CZI (not just inherited from the M3 memory note): a visual crop of C0/C1/C2 shows C2 is the dense-everywhere nuclear counterstain (DAPI, matching `DAPI-T4` being last/index-2 in the metadata's activated-channel order), consistent with the project's established fix (`--channels "TdTomato-AF568" "Fos-AF488" "DAPI"`, physical index 0=TdT, 1=Fos, 2=DAPI). A second, more mature sibling script — `czi_hybrid_mip.py` — already exists in the repo with an argparse CLI, a `--channels` flag whose default `["AF568-T2", "AF488-T3", "DAPI-T4"]` matches this exact CZI's channel names verbatim, and a per-channel-name OME-XML builder; its patterns (not `czi_mip.py`'s current hardcoded body) are the better template to generalize from for CONV-01, even though `czi_mip.py` remains the canonical file to extend per CONTEXT.md.

**EXP-02 (per-entry export).** The truncation bug is exactly as CONTEXT.md describes: `03_export_val01_metrics.groovy` writes to two hardcoded filenames (`results/val01_percell_export.tsv`, `results/val01_region_area.tsv`) that get overwritten on every entry during "Run for project," so only the last-run entry's data survives. The fix is a two-line change, and the exact idiom already exists **twice** elsewhere in this same repo (`run_braian_detection.groovy`, `export_region_dapi_reference.groovy`): `getProjectEntry().getImageName()`, sanitized with a specific already-established `invalidChars` regex, combined with QuPath's built-in `buildPathInProject(...)` helper (confirmed against the official QuPath 0.6.0 javadoc: equivalent to `buildFilePath(PROJECT_BASE_DIR, ...)`, does not touch the filesystem). `scripts/val01_metrics.py`'s expected columns (`PERCELL_EXPECTED_COLS`, `REGION_EXPECTED_COLS`) are unaffected by this fix — only the output path changes, never the header.

**Primary recommendation:** Extend `czi_mip.py`'s MIP core with `czi_hybrid_mip.py`'s CLI/OME-XML patterns, wrap it in a scene loop keyed on `get_all_mosaic_scene_bounding_boxes()`, pass each scene's raw bbox tuple to `read_mosaic(region=bbox, C=c, Z=z)` with **no `S=` kwarg**, and derive the D-01/D-02 identity artifact from data already in hand (bbox, `M` tile count from `get_dims_shape()`, output shape) rather than any new API surface. For EXP-02, copy the `getProjectEntry().getImageName()` + `invalidChars` + `buildPathInProject(...)` idiom verbatim from `run_braian_detection.groovy` into `03_export_val01_metrics.groovy`, changing nothing else.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-scene CZI mosaic decode + MIP | Conversion script (Python, `braian` conda env) | — | `aicspylibczi`/`tifffile` are pure Python-process, CLI-invoked; no GUI or service involved |
| Scene-identity verification artifact (thumbnail + text) | Conversion script (Python) | Operator (visual review) | Generated automatically by the same process that writes the MIP; consumed by a human at the terminal, not a GUI |
| QuPath project entries (the 5 MIPs as images) | QuPath project / Groovy scripting layer | — | Entry creation and "Run for project" iteration are QuPath-native concepts; scripts are authored in `scripts/`, executed inside QuPath |
| Per-entry export filenames | QuPath Groovy scripting layer | Filesystem (`results/`) | The fix lives entirely inside the Groovy script's path-construction logic; QuPath resolves `getProjectEntry()` per running entry |
| Downstream TSV consumption | Python analysis layer (`braian` env, `val01_metrics.py`) | — | Reads whatever the Groovy layer wrote; column contract is the only cross-tier coupling, and this phase does not touch it |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aicspylibczi` | 3.3.1 (installed, `braian` env) [VERIFIED: `conda run -n braian python3 -c "import aicspylibczi; print(aicspylibczi.__version__)"`] | Reads Zeiss CZI mosaic/multi-scene files; the only library in this project's stack that exposes per-scene bounding boxes and region-cropped mosaic reads | Already the project's locked CZI reader (`czi_mip.py`, `czi_hybrid_mip.py`); C++ (libCZI) backend, correct for large tiled Airyscan mosaics |
| `tifffile` | 2026.3.3 (installed) [VERIFIED] | Writes OME-TIFF with embedded OME-XML description | Already the project's locked OME-TIFF writer |
| `numpy` | 2.1.3 (installed) [VERIFIED] | Array stacking / max-projection over Z | Already in use |
| `Pillow` (PIL) | 12.2.0 (installed) [VERIFIED] | Thumbnail PNG encode for the D-01 identity artifact | Already available in `braian` env (confirmed by successful `Image.fromarray(...).save(...)` in this research session); no new dependency needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `scipy.ndimage` | already installed (used by `czi_hybrid_mip.py` for `_sharpest_plane`) | Optional focus-scoring if a single-plane (not MIP) thumbnail source is desired | Not required for CONV-01/02 — MIP output itself is a fine thumbnail source; only relevant if the plan wants a sharpest-plane preview instead |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `region=`-only scene cropping | `S=` kwarg to `read_mosaic` | **Not viable** — raises `PylibCZI_CDimCoordinatesOverspecifiedException` (verified this session); mosaic files ignore the S dimension entirely per the library's own README and error message |
| Reusing `czi_mip.py`'s hardcoded body | Generalizing from `czi_hybrid_mip.py`'s argparse/OME-XML/channel-validation pattern | `czi_hybrid_mip.py` is strictly more mature for this exact use case (its `DEFAULT_CHANNELS` already equals this CZI's real channel names) — recommend borrowing its shape even though `czi_mip.py` is the file CONTEXT.md names as canonical to extend |
| Thumbnail via `read_mosaic(scale_factor=<1)` | Full-res read + numpy/PIL downsample | `scale_factor != 1.0` has a documented upstream rendering bug (missing subblocks) on some files (CITED: GitHub issue); this session's own scale_factor=0.05 test on scene 0 rendered cleanly, but reusing the already-computed full-res DAPI plane and downsampling in numpy avoids the risk entirely and costs no extra CZI read |

**Installation:** None required — all packages are already installed in the `braian` conda env.

**Version verification:** Confirmed this session via direct `conda run -n braian python3 -c "import X; print(X.__version__)"` for `aicspylibczi` (3.3.1), `tifffile` (2026.3.3), `numpy` (2.1.3), and `PIL`/Pillow (12.2.0). All match or exceed what `.claude/CLAUDE.md`'s Key Dependencies section already documents.

## Package Legitimacy Audit

**Not applicable.** This phase introduces no new external packages — `aicspylibczi`, `tifffile`, `numpy`, and `Pillow` are already installed in the `braian` conda env and already used by sibling scripts (`czi_mip.py`, `czi_hybrid_mip.py`). No `pip install` / `npm install` step exists in this phase's scope.

## Architecture Patterns

### System Architecture Diagram

```
                         ┌────────────────────────────────────┐
                         │  -001-07_processed.czi (16 GB)      │
                         │  5 scenes × C=3 × Z=4, tiled mosaic │
                         └──────────────────┬───────────────────┘
                                            │
                         czi = aicspylibczi.CziFile(path)
                         bboxes = czi.get_all_mosaic_scene_bounding_boxes()
                                            │
                         ┌──────────────────▼───────────────────┐
                         │  for scene_idx in sorted(bboxes):     │  (0-based loop)
                         │    bbox = bboxes[scene_idx]           │
                         │    N = scene_idx + 1     (D-05)       │
                         └──────────────────┬───────────────────┘
                                            │
                  ┌─────────────────────────┼─────────────────────────┐
                  │                         │                         │
                  ▼                         ▼                         ▼
        for c in range(3):        M, dims from            scale-down DAPI
          for z in range(4):      get_dims_shape()[si]     plane already
            read_mosaic(          → text record            read → PNG
              region=bbox,        {scene 0-based key,       thumbnail
              C=c, Z=z)           s{N} label, bbox,         (D-01/D-02)
              NO S= kwarg         M, dims}
              (raises if set)
                  │                         │                         │
                  ▼                         ▼                         ▼
          np.max over Z    ──►   printed to stdout    ──►  wBA1-3_s{N}
          per channel                (operator audit)      _identity.png
                  │
                  ▼
          np.stack(C,Y,X)  ──►  OME-XML (channel names,
                                  PhysicalSizeX/Y=0.69µm)
                  │
                  ▼
        wBA1-3_s{N}_MIP.ome.tiff   (5 files, N=1..5)
                  │
                  ▼
        ┌──────────────────────────┐
        │ QuPath project: 5 entries │
        └────────────┬──────────────┘
                     │  "Run for project" → 03_export_val01_metrics.groovy
                     ▼
        entry = getProjectEntry()
        stem = sanitize(entry.getImageName())
        buildPathInProject("results", "${stem}__val01_percell_export.tsv")
        buildPathInProject("results", "${stem}__val01_region_area.tsv")
                     │
                     ▼
        results/wBA1-3_s1__val01_percell_export.tsv   (× 5, one per entry)
        results/wBA1-3_s1__val01_region_area.tsv
                     │
                     ▼
        scripts/val01_metrics.py  (unchanged column contract, Phase 10 AGG-01 consumer)
```

### Recommended Project Structure
No new directories — this phase writes into existing conventions:
```
Automation Cell Counting/wBA Sungmo/
├── -001-07_processed.czi                     # input (existing)
├── wBA1-3_s1_MIP.ome.tiff … wBA1-3_s5_MIP.ome.tiff   # CONV-01 output (new)
└── wBA1-3_s1_identity.png … wBA1-3_s5_identity.png   # CONV-02 artifact (new, D-01)

scripts/
└── 03_export_val01_metrics.groovy            # EXP-02 fix (edited in place)

<QuPath project>/scripts/
└── 03_export_val01_metrics.groovy            # dual-location hard copy (existing convention)

<QuPath project>/results/
└── wBA1-3_s{1..5}__val01_percell_export.tsv, …__val01_region_area.tsv   # EXP-02 output (new naming)
```

### Pattern 1: Per-scene mosaic isolation via region= only (CONV-01)
**What:** Iterate the dict returned by `get_all_mosaic_scene_bounding_boxes()`; for each scene, pass its bbox tuple verbatim as `region=` to `read_mosaic()`, with `C=`/`Z=` constraints but **never `S=`**.
**When to use:** Any per-scene read on a multi-scene mosaic CZI in this project (this is the mechanism CONV-01 requires).
**Example:**
```python
# Source: verified this session against aicspylibczi==3.3.1 and the real
# -001-07_processed.czi (Automated Cell Counting/wBA Sungmo/)
import aicspylibczi
czi = aicspylibczi.CziFile(str(czi_path))
bboxes = czi.get_all_mosaic_scene_bounding_boxes()   # dict[int, BBox], 0-based keys

for scene_idx in sorted(bboxes):          # deterministic 0..4 iteration
    b = bboxes[scene_idx]
    region = (b.x, b.y, b.w, b.h)         # GLOBAL mosaic pixel coords — use verbatim,
                                           # do not pad/expand (bboxes are non-overlapping
                                           # but only by tens-to-hundreds of px)
    N = scene_idx + 1                     # D-05: 1-based filename label
    plane = czi.read_mosaic(region=region, C=c, Z=z, scale_factor=1.0)
    # plane.shape == (1, 1, b.h, b.w) — confirmed exact match this session
    # DO NOT pass S=scene_idx here — raises PylibCZI_CDimCoordinatesOverspecifiedException:
    # "Do not set S when reading mosaic files!" (confirmed by triggering it directly)
```

### Pattern 2: Scene-identity artifact from data already read (CONV-02, D-01/D-02)
**What:** After a scene's DAPI-channel plane is already in memory (needed for the MIP anyway), reuse it for both the text record and the downsampled thumbnail — no extra CZI read.
**When to use:** Immediately after each scene's channel loop completes, before moving to the next scene.
**Example:**
```python
# dims_by_scene = czi.get_dims_shape() — one dict per scene since shape is
# inconsistent across scenes (different M tile counts); index by scene position,
# NOT by dims_by_scene[0]['S'][1] (see Common Pitfalls #4 — that field only
# describes scene 0's own S-range, not the total scene count)
M = dims_by_scene[scene_idx]['M'][1]
print(f"scene_key={scene_idx} (0-based)  label=s{N} (1-based)  "
      f"bbox=(x={b.x}, y={b.y}, w={b.w}, h={b.h})  M_tiles={M}  "
      f"dims=({b.h}, {b.w})")

# Thumbnail: downsample the already-read full-res DAPI (or any) channel/Z-plane
# in numpy — avoids the documented read_mosaic(scale_factor<1.0) rendering
# caveat entirely (this session's own scale_factor=0.05 test rendered cleanly
# on scene 0, but reusing an in-hand array is strictly safer and free).
from PIL import Image
import numpy as np
lo, hi = np.percentile(dapi_plane, [1, 99.5])
norm = np.clip((dapi_plane.astype(np.float32) - lo) / (hi - lo + 1e-6), 0, 1)
thumb = Image.fromarray((norm[::8, ::8] * 255).astype(np.uint8))  # 8x downsample
thumb.save(out_dir / f"wBA1-3_s{N}_identity.png")
```

### Pattern 3: Per-entry disambiguated export path (EXP-02)
**What:** Reuse this project's own established idiom for turning a QuPath entry into a filesystem-safe stem and a project-relative results path.
**When to use:** `03_export_val01_metrics.groovy`'s two `new File(resultsDir, "val01_*.tsv")` lines.
**Example:**
```groovy
// Source: verbatim idiom already in this repo — scripts/run_braian_detection.groovy:79-81
// and scripts/export_region_dapi_reference.groovy:41-42 (grep-confirmed this session)
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
    .collect { java.util.regex.Pattern.quote(it) }.join('|')
def entry = getProjectEntry()
def stem = (entry != null ? entry.getImageName() : getCurrentImageData().getServer().getMetadata().getName())
    .replaceAll(invalidChars, '')

// buildPathInProject(String... more) == buildFilePath(PROJECT_BASE_DIR, more)
// (confirmed against the official QuPath 0.6.0 javadoc, qupath.lib.scripting.QP)
def percellFile = new File(buildPathInProject("results", "${stem}__val01_percell_export.tsv"))
def regionFile  = new File(buildPathInProject("results", "${stem}__val01_region_area.tsv"))
```

### Anti-Patterns to Avoid
- **Passing `S=scene_idx` to `read_mosaic` for a mosaic file:** raises `PylibCZI_CDimCoordinatesOverspecifiedException`. Mosaic files reconstruct via an internal `mIndex`/tile system that ignores `S`; region-based cropping is the only supported per-scene mechanism.
- **Deriving scene count from `get_dims_shape()[0]['S'][1]`:** on a multi-scene CZI with inconsistent per-scene shape (this file: different M tile counts per scene), `get_dims_shape()` returns **one dict per scene**, and each dict's own `'S'` entry describes only that scene's own index range (e.g. scene 2's dict reports `S: (2, 3)`), not the total scene count. `czi_mip.py`'s existing `n_s = dim0.get('S', (0, 1))[1]` pattern silently returns `1` on this file if `dim0` is `dims[0]`. Use `len(czi.get_all_mosaic_scene_bounding_boxes())` instead (returned `5`, correctly, this session).
- **Padding/expanding a scene's bbox "to be safe":** the 5 scenes' bboxes are non-overlapping but by margins as small as 62 px (S0/S1) — any manual padding risks crossing into a neighbor's tile footprint and reintroducing the exact fusion bug this phase exists to prevent. Use the bbox tuple exactly as returned.
- **Hardcoding output filenames in a "Run for project" Groovy script:** any script meant to run across multiple QuPath entries must derive its output path from `getProjectEntry()` (or the current image server name as a fallback) — a fixed filename is a truncation bug waiting to happen, which is exactly EXP-02's root cause.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Filesystem-safe stem from a QuPath entry name | A new regex/sanitizer for EXP-02 | The exact `invalidChars` idiom already in `run_braian_detection.groovy` / `export_region_dapi_reference.groovy` | Two independent scripts in this same repo already solved this identically; a third, slightly-different implementation is a maintenance/consistency risk for zero benefit |
| Project-relative path construction | `new File(getProject().getBaseDirectory(), "results")` string-gluing | `buildPathInProject("results", filename)` (QuPath `QP` static, confirmed in 0.6.0 javadoc) | Already the established convention in `run_braian_detection.groovy`; avoids manual separator/parent-dir bugs |
| CLI scaffold for a per-scene CZI→OME-TIFF converter | A new argparse layout from scratch on top of `czi_mip.py`'s no-arg body | `czi_hybrid_mip.py`'s existing `parse_args()`/`_build_ome_xml()`/channel-name-validation pattern | It already has the right defaults for this exact CZI's channel names (`AF568-T2`, `AF488-T3`, `DAPI-T4`) and a working per-channel-name OME-XML builder — copy the shape, not just the idea |
| Scene bounding-box discovery | Manually parsing CZI XML metadata for tile positions | `aicspylibczi.CziFile.get_all_mosaic_scene_bounding_boxes()` | Already does exactly this, returns global pixel coordinates directly usable as `region=` |

**Key insight:** Every piece this phase needs — sanitization, path-building, CLI/OME-XML scaffolding, scene bbox discovery — already exists somewhere in this repo or in the installed library. This phase is generalization/wiring, not new-algorithm work; the plan should be written as "copy pattern X from file Y" tasks wherever possible.

## Common Pitfalls

### Pitfall 1: Assuming `S=` selects a scene for `read_mosaic`
**What goes wrong:** Code passes `S=scene_idx` alongside `region=` expecting it to double-confirm scene isolation; instead the call raises at runtime.
**Why it happens:** `S` is a documented ZISRAW dimension letter and appears in `read_mosaic`'s own docstring kwargs table, so it looks legitimate — but mosaic files specifically ignore `S` per the library's own error path.
**How to avoid:** Never pass `S=` to `read_mosaic` on a mosaic file. Use `region=` only.
**Warning signs:** `PylibCZI_CDimCoordinatesOverspecifiedException` at the first scene/channel/Z combination.

### Pitfall 2: Scene count derived from the wrong `get_dims_shape()` field
**What goes wrong:** `n_s = dims[0].get('S', (0,1))[1]` returns `1` (or some other wrong single-scene value) on a file where per-scene shape is inconsistent, silently truncating the conversion loop to one scene.
**Why it happens:** `get_dims_shape()` returns a list of per-scene dicts when shapes differ across scenes (confirmed: this file returns 5 dicts, each with its own narrow `'S'` range); code written against a single-scene assumption (like `czi_mip.py`'s current body) indexes only `dims[0]`.
**How to avoid:** Use `len(czi.get_all_mosaic_scene_bounding_boxes())` for scene count; it is unambiguous and was confirmed to return `5` this session.
**Warning signs:** Conversion "succeeds" but emits fewer than 5 output files with no error.

### Pitfall 3: Off-by-one between the 0-based scene loop and the 1-based filename label
**What goes wrong:** `s{N}` in the filename silently drifts from the scene it actually names if the `+1` translation is applied inconsistently (e.g. once in the filename, forgotten in a log line, or applied twice).
**Why it happens:** Python loop indices are naturally 0-based; the locked filename spec (D-04) is 1-based for human readability.
**How to avoid:** Compute `N = scene_idx + 1` once, and print **both** `scene_idx` and `N` together in every log/record line (D-05) — never let a bare `N` or bare `scene_idx` appear without the other nearby.
**Warning signs:** A `wBA1-3_s3_MIP.ome.tiff` whose printed identity record says `scene_key=3` (should be `2`, since `s3` = scene_idx 2).

### Pitfall 4: `read_mosaic(scale_factor != 1.0)` rendering gaps on some files
**What goes wrong:** A documented upstream libCZI issue (GitHub) reports missing/incorrectly-rendered subblocks when `scale_factor` is not exactly `1.0`.
**Why it happens:** Known bug in the underlying Zeiss libCZI resampling path, not specific to this project's files.
**How to avoid:** This session's own `scale_factor=0.05` test on scene 0 of the real file rendered a clean, artifact-free thumbnail — so the bug does not appear to manifest here — but the safer, zero-extra-cost approach is to downsample an already-read full-resolution array in numpy/PIL for the D-01 thumbnail rather than requesting a second CZI read at a fractional `scale_factor`.
**Warning signs:** Thumbnail shows a grid of missing/black tiles that the full-res read does not.

### Pitfall 5: Fixed output filenames inside a "Run for project" script (EXP-02's actual root cause)
**What goes wrong:** `new File(resultsDir, "val01_percell_export.tsv")` is the same `File` object path on every entry; QuPath truncates/overwrites it fresh each entry, so only the last entry processed survives on disk.
**Why it happens:** The script was originally written and tested against a single entry (v1.0, M3 hippocampus) where this was invisible.
**How to avoid:** Any output path in a script intended for "Run for project" must incorporate `getProjectEntry().getImageName()` (or equivalent per-entry identity).
**Warning signs:** After "Run for project" across 5 entries, `results/` contains only 2 files (not 10), and their row counts match only the last-processed section.

### Pitfall 6: Treating a scene's bbox as if it needs a coordinate-origin adjustment
**What goes wrong:** Code subtracts the scene's own `b.x`/`b.y` before passing `region=`, assuming `region` wants scene-relative coordinates, and ends up reading from the wrong global location (often (0,0) of the whole mosaic, or another scene's area).
**Why it happens:** Reasonable assumption by analogy to "crop within an image," but `region` in `read_mosaic` is in the **same absolute pixel coordinate system** as the bbox itself.
**How to avoid:** Pass `(b.x, b.y, b.w, b.h)` verbatim as the 4-tuple. Confirmed this session: `read_mosaic(region=(b.x, b.y, b.w, b.h), ...)` returns an array whose shape is exactly `(b.h, b.w)` and (visually, for scene 0) a single coherent coronal section.
**Warning signs:** Output image is black, cropped to the wrong tissue, or shows a different scene's morphology than expected.

## Code Examples

### Deterministic scene iteration + bbox retrieval
```python
# Source: verified this session, aicspylibczi==3.3.1,
# Automated Cell Counting/wBA Sungmo/-001-07_processed.czi
import aicspylibczi
czi = aicspylibczi.CziFile(str(czi_path))
bboxes = czi.get_all_mosaic_scene_bounding_boxes()
# Confirmed real output on this file (do not re-derive — already grounded in CONTEXT.md):
#   0 -> x=107694 y=56900  w=13902 h=9295
#   1 -> x=107686 y=66257  w=13903 h=10216
#   2 -> x=92423  y=66840  w=14824 h=10216
#   3 -> x=122204 y=77616  w=13903 h=10216
#   4 -> x=107051 y=77487  w=14824 h=11138
for scene_idx in sorted(bboxes):   # deterministic 0..4
    ...
```

### Per-region Groovy path fix (full context)
```groovy
// Source: scripts/run_braian_detection.groovy (this repo) — reused verbatim pattern
def invalidChars = (['<', '>', ':', '"', '/', '\\', '|', '?', '*'] as Set)
    .collect { java.util.regex.Pattern.quote(it) }.join('|')
def entry = getProjectEntry()
def stem = (entry != null ? entry.getImageName()
                          : getCurrentImageData().getServer().getMetadata().getName())
    .replaceAll(invalidChars, '')

def percellFile = new File(buildPathInProject("results", "${stem}__val01_percell_export.tsv"))
def regionFile  = new File(buildPathInProject("results", "${stem}__val01_region_area.tsv"))
// everything downstream of these two lines in 03_export_val01_metrics.groovy is unchanged —
// column headers, row-building, and write logic stay exactly as-is (D-07)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `czi_mip.py`: hardcoded `F_IN`/`F_OUT`, single implicit scene, hardcoded M3 channel names in OME-XML | Per-scene loop over `get_all_mosaic_scene_bounding_boxes()`, `--channels` CLI flag (pattern from `czi_hybrid_mip.py`), OME-XML channel names built from that flag | This phase (CONV-01/02) | Enables the multi-scene wBA1-3 CZI; removes the M3-specific hardcoding that would otherwise mislabel channels on the new file |
| `03_export_val01_metrics.groovy`: fixed output filenames | Per-entry filename stem via `getProjectEntry().getImageName()` | This phase (EXP-02) | Unblocks AGG-01 (Phase 10) — batch export across all 5 sections becomes usable |

**Deprecated/outdated:**
- `czi_mip.py`'s current hardcoded single-file body should be treated as a starting point to generalize from, not a working multi-scene converter — it has never been run against a multi-scene file.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Physical channel index 0 = TdTomato-AF568, index 1 = Fos-AF488, index 2 = DAPI-T4 (i.e. the same `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` mapping established for the M3 acquisition also holds for this new `-001-07_processed.czi`) | Summary, Pattern 1, Anti-Patterns | This session independently confirmed **index 2 = DAPI** for the new file (dense whole-tissue nuclear counterstain, visually distinct from the two sparse channels) — but did **not** independently distinguish which of index 0 vs index 1 is TdTomato vs Fos (both are sparse, similarly-distributed reporter signals in this recall-reactivated tissue, and cannot be told apart by density/pattern alone without a marker-specific positive control). If this assumption is wrong, TdT+/Fos+ class labels would be swapped in every downstream classifier (a repeat of the exact bug class the M3 `feedback_channel_order.md` memory note documents). **Recommend:** the plan should include a `checkpoint:human-verify` comparing one scene's C0/C1 thumbnails against the operator's known expected TdTomato vs Fos distribution before trusting the `--channels` override on this new file. |
| A2 | Scene acquisition order (S0..S4) has no assumed relationship to physical left-right or AP position on the slide | AP-order handling (D-03) | Low — this is explicitly a locked decision (not an assumption to confirm), included here only because CONTEXT.md frames it as "no claim made," and the research did not find evidence either way in the bbox coordinates (S0-S4 bboxes do trace a roughly diagonal path across the mosaic, but interpreting that as AP order is exactly what D-03 forbids doing at this phase) |

## Open Questions

1. **Which of physical channel 0/1 is TdTomato vs Fos on this specific acquisition?**
   - What we know: Channel 2 is definitively DAPI (dense nuclear counterstain, visually confirmed). The metadata's activated-channel order for this file is `AF568-T2, AF488-T3, DAPI-T4` — the same relative ordering (TdT-track, then Fos-track, then DAPI-track) as the M3 acquisition where physical read order was independently confirmed to be TdT→Fos→DAPI.
   - What's unclear: Whether the aicspylibczi physical-read-order quirk (index order ≠ metadata declaration order) applies identically to this file, or whether this file's physical order happens to already match its metadata order (in which case the M3-derived `--channels` override, while producing the same net effect here, would be "accidentally correct" rather than "correctly compensating for a reversal").
   - Recommendation: Treat as low-risk given both channels are inherited from the same acquisition pipeline/microscope (per `.claude/CLAUDE.md`'s "Zeiss LSM 980 / 20x" note), but the plan should still add a cheap visual/statistical spot-check (e.g. compare C0/C1 positive-fraction against the operator's qualitative expectation for this animal) as part of CONV-02's identity verification, not defer it silently to Phase 8 classification.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `aicspylibczi` | CONV-01 | ✓ | 3.3.1 | — |
| `tifffile` | CONV-01 | ✓ | 2026.3.3 | — |
| `numpy` | CONV-01 | ✓ | 2.1.3 | — |
| Pillow (PIL) | CONV-02 thumbnail | ✓ | 12.2.0 | — |
| `braian` conda env | CONV-01/02 (script execution) | ✓ | — | — |
| QuPath v0.6.0 | EXP-02 (GUI-run "Run for project") | ✓ | binary present at `$HOME/section-pipeline/tools/QuPath/bin/QuPath` | — |
| Disk space (output MIPs) | CONV-01 | ✓ | 708 GB free (`df -h /`) vs. ~4-5 GB estimated total output (5 scenes × 3 channels × ~9-15 Mpx × 2 bytes) | — |
| Input CZI file | CONV-01/02 | ✓ | `Automated Cell Counting/wBA Sungmo/-001-07_processed.czi`, 16 GB, confirmed present and readable this session | — |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** None — all dependencies already present and version-confirmed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None present — this project has no pytest/unit-test infrastructure anywhere (`find` for `pytest.ini`/`conftest.py`/`test_*.py` returned nothing). All existing verification in this codebase is script-level printed assertions + human visual audit (per `.claude/CLAUDE.md` Error Handling: "QuPath `summary.json` persists detection counts... serves as a manual audit checkpoint"). This phase should follow that established convention, not introduce a new pytest layer. |
| Config file | none — see Wave 0 |
| Quick run command | `conda run -n braian python3 <conversion_script>.py --czi <path> --outdir <dir>` (prints per-scene assertions to stdout) |
| Full suite command | Same command, run once over the full 5-scene series (this IS the full suite — there is no separate "quick" subset given the small scene count) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONV-01 | Exactly 5 MIP OME-TIFFs emitted, one per scene, no fusion | scripted assertion (inline in conversion script) | `assert len(list(outdir.glob("wBA1-3_s*_MIP.ome.tiff"))) == 5` + per-scene `assert mip.shape[1:] == (b.h, b.w)` | ❌ Wave 0 — add to conversion script itself |
| CONV-01 | Each output carries correct physical pixel size in OME-XML | scripted assertion | round-trip read with `tifffile.TiffFile(out).ome_metadata` and assert `PhysicalSizeX == 0.69` (or the calibrated value) | ❌ Wave 0 |
| CONV-02 | Scene→section identity confirmable by operator | manual (visual) | operator opens the 5 `*_identity.png` thumbnails + reads the printed text record | manual-only, justified: this is explicitly what D-01 asks for (human eyeball verification), not an automatable claim |
| CONV-01 | Scene bboxes non-overlapping (guards against region-based fusion) | scripted assertion | pairwise rectangle-intersection check over `get_all_mosaic_scene_bounding_boxes()` output, asserting no overlap, printed before the conversion loop runs | ❌ Wave 0 — this exact check was run ad hoc this session; promote it into the script as a pre-flight assertion |
| EXP-02 | 5 distinct per-entry TSV pairs, no truncation, no cross-section rows | manual + scripted | after "Run for project," `ls results/*.tsv \| wc -l` should equal 10 (2 files × 5 entries); `wc -l results/*__val01_percell_export.tsv` row counts should differ across entries (proves no clobbering) | ❌ Wave 0 — add a `scripts/verify_export_integrity.py` (or an inline shell check) that asserts file count and non-identical row counts |
| EXP-02 | Column contract unchanged | scripted assertion | `scripts/val01_metrics.py`'s existing `PERCELL_EXPECTED_COLS`/`REGION_EXPECTED_COLS` checks already fail loudly (`sys.exit`) on a header mismatch — this is already covered by existing code, no new test needed |

### Sampling Rate
- **Per task commit:** run the conversion script against the real CZI (only one real input file exists; there is no smaller fixture) and inspect stdout assertions
- **Per wave merge:** re-run the full 5-scene conversion + a "Run for project" pass across all 5 resulting QuPath entries
- **Phase gate:** all 5 MIPs exist with correct OME-XML pixel size, all 5 identity thumbnails visually confirmed by the operator, and `results/` contains 10 non-clobbered TSVs before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Pre-flight bbox-overlap assertion (promote the ad hoc pairwise-rectangle check run this session into the conversion script)
- [ ] Post-conversion assertion: exactly 5 output files, each shape-matched to its bbox
- [ ] Post-export assertion script/command: file count == 10, row counts differ per entry (guards a regression back to the truncation bug)
- [ ] No pytest framework install needed — stays consistent with the project's existing "printed assertion + human visual audit" convention

*(No unit-test framework gap — this project intentionally does not use one; see Test Framework above.)*

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | no | N/A — single-user local desktop pipeline, no auth surface |
| V3 Session Management | no | N/A |
| V4 Access Control | no | N/A — local filesystem only, single operator |
| V5 Input Validation | yes | Filename sanitization for the EXP-02 stem (already-established `invalidChars` regex strips path-unsafe characters `< > : " / \ | ? *` before use in a filesystem path) — prevents a QuPath entry name containing a path-separator-like character from writing outside `results/` |
| V6 Cryptography | no | N/A — no secrets, no encrypted data in scope |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Path traversal via unsanitized entry name (e.g. an entry named `../../etc/passwd`) used directly in a `new File(...)` path | Tampering | Already mitigated by the existing `invalidChars` regex pattern reused from `run_braian_detection.groovy` — strips `/` and `\` among other characters, preventing directory traversal in the constructed stem |
| Silent data loss via filename collision (two entries sanitizing to the same stem) | — (data integrity, not a STRIDE category but worth flagging) | Entry names in this project are already unique by construction (`wBA1-3_s1` .. `wBA1-3_s5`, from D-04's locked filename convention) — no two entries should ever collide post-sanitization, but the conversion/export scripts should assert entry-name uniqueness rather than assume it silently |

## Sources

### Primary (HIGH confidence)
- Direct runtime execution against the installed `aicspylibczi==3.3.1` package and the real project file `Automated Cell Counting/wBA Sungmo/-001-07_processed.czi` (this session) — bbox retrieval, pairwise overlap check, `S=` kwarg exception reproduction, shape-matched region reads, visual channel/thumbnail crops. This is the strongest evidence available for this phase and is what most claims in this document are grounded in.
- `inspect.getsource()` on the installed `aicspylibczi.CziFile` class (this session) — exact signatures and docstrings for `read_mosaic`, `get_all_mosaic_scene_bounding_boxes`, `get_mosaic_scene_bounding_box`, `get_dims_shape`
- `qupath.github.io/javadoc/docs/qupath/lib/scripting/QP.html` (QuPath 0.6.0 official javadoc) - `buildPathInProject`/`buildFilePath` semantics
- `grep` over this repo's own scripts (`run_braian_detection.groovy`, `export_region_dapi_reference.groovy`, `czi_hybrid_mip.py`) - existing, already-proven idioms for exactly this phase's two problems

### Secondary (MEDIUM confidence)
- WebFetch of `github.com/AllenCellModeling/aicspylibczi` README - "Mosaic files ignore the S dimension" statement, cross-verified this session by directly triggering the corresponding exception

### Tertiary (LOW confidence)
- WebSearch results referencing a `scale_factor != 1.0` libCZI rendering bug (GitHub issue, not independently read in full) — this session's own scale_factor=0.05 test on the real file did not reproduce visible corruption, so this is flagged as a caveat/precaution rather than a confirmed active bug on this dataset

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed by direct import in the target conda env this session
- Architecture (scene isolation mechanism): HIGH — the central risk (S= vs region=) was resolved by directly triggering the exception against the real installed library, not by reading documentation alone
- Pitfalls: HIGH — every pitfall listed was either directly reproduced (S= exception, scene-count-field trap) or directly measured (bbox overlap, shape matching) against the real project file
- Channel identity (A1 in Assumptions Log): MEDIUM — DAPI position independently re-confirmed visually; TdT-vs-Fos assignment within the two sparse channels is inherited from the M3 acquisition's established fix, not independently re-derived for this file

**Research date:** 2026-07-18
**Valid until:** No expiry driver — this research is grounded in a specific, unchanging input file (`-001-07_processed.czi`) and a pinned library version (`aicspylibczi==3.3.1`); re-verify only if the input file or installed package version changes
