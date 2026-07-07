# Testing Patterns

**Analysis Date:** 2026-06-30

## Test Framework

**Runner:** None — no automated test suite exists in this project.

**Assertion Library:** Not applicable.

**Run Commands:** Not applicable.

## Current Validation Approach

This is a single-researcher bioinformatics pipeline. Validation is manual and experimental rather than automated. The following patterns substitute for formal tests:

**1. `--info` flag (metadata dry-run):**
`czi_to_mip.py` supports `--info` to print file metadata without writing output. Use this to verify channel names, z-plane counts, pixel sizes, and tile dimensions before committing to a full MIP run.

```bash
conda activate braian
python /home/jflab/section-pipeline/scripts/czi_to_mip.py brain1.czi --info
```

**2. Single-section pilot before series:**
Per `CLAUDE.md`, detection parameters must be tuned on ONE section before scaling. This is the biological equivalent of a unit test — validate on a known section (M3 hippocampus ~+1.4 mm bregma) before batch processing.

**3. Visual QC in QuPath:**
After MIP generation, open in QuPath and verify:
- Channel count and names match expectation
- Pixel size reads correctly (check Image tab)
- No stitching artifacts visible

**4. DeepSlice AP sanity check:**
`run_deepslice.py` prints estimated AP position from bregma after prediction. Compare against expected anatomy to catch gross registration errors.

```
Estimated AP: +1.42 mm from bregma  (Section_s000.png)
```

**5. ABBA registration visual review:**
After ABBA DeepSlice + manual angle adjustment, use Review Mode to confirm alignment before exporting atlas overlays.

## Test File Organization

No test files exist. The closest approximation:
- `Automated Cell Counting Test/` — QuPath project directory used as a validation workspace for the M3 hippocampus pilot section
- `Automated Cell Counting Test/Test1 062026 Notes.txt` — manual QC notes from first pipeline run

## What Would Need Testing (Gaps)

**High priority — fragile by design:**

1. **Channel order inversion** (`czi_to_mip.py`):
   - `aicspylibczi` reads CZI channels in a different order than CZI metadata reports. This is a known bug (documented in `/home/jflab/.claude/projects/-home-jflab-Analysis/memory/feedback_channel_order.md`). No automated test guards against regression. Any change to the channel-read path needs manual verification with `--info` and visual QuPath inspection.
   - Files: `/home/jflab/section-pipeline/scripts/czi_to_mip.py` (lines 56–69, `_get_channel_names`)

2. **Pixel size extraction from CZI metadata:**
   - `_get_pixel_size()` silently returns `None` on failure. A unit test checking the metres-to-µm conversion against a known CZI fixture would catch regressions.
   - Files: `/home/jflab/section-pipeline/scripts/czi_to_mip.py` (lines 43–53)

3. **Axes normalisation in OME-TIFF reader:**
   - `generate_mip_from_ometiff()` branches on `axes` value (`CYX`, `CZYX`, `ZCYX`, fallback). Only `CZYX` and `CYX` have been tested in practice. Other axis orders fall through silently.
   - Files: `/home/jflab/section-pipeline/scripts/czi_to_mip.py` (lines 94–141)

4. **Atlas coordinate units:**
   - Per `CLAUDE.md`, exports must be in µm not pixels. No automated check exists that exported cell centroids are in the correct unit.

5. **Nucleus-anchored colocalization logic:**
   - The rule (nucleus contains marker centroid) is not yet implemented; when implemented in QuPath Groovy scripts, it will need visual validation against known-positive cells.

## If Automated Tests Were Added

**Recommended framework:** `pytest` in the `braian` conda env (already has Python 3.11, numpy, tifffile).

**Install:**
```bash
conda activate braian
pip install pytest
```

**Suggested test layout:**
```
/home/jflab/section-pipeline/
├── scripts/
│   ├── czi_to_mip.py
│   └── run_deepslice.py
└── tests/
    ├── fixtures/
    │   └── tiny_mock.czi    # minimal synthetic CZI for fast CI
    ├── test_czi_to_mip.py
    └── test_run_deepslice.py
```

**Minimal useful tests to write first:**

```python
# tests/test_czi_to_mip.py
import numpy as np
from pathlib import Path
from scripts.czi_to_mip import _build_ome_xml, generate_mip_from_ometiff

def test_build_ome_xml_channel_count():
    mip = np.zeros((3, 100, 200), dtype=np.uint16)
    ch_names = ["DAPI", "Fos-AF488", "TdTomato-AF568"]
    xml = _build_ome_xml(mip, ch_names, pixel_um=0.69)
    assert xml.count("<Channel") == 3
    assert 'Name="DAPI"' in xml
    assert 'PhysicalSizeX="0.69"' in xml

def test_ometiff_axes_normalisation(tmp_path):
    """Verify CYX OME-TIFF round-trips to correct shape."""
    import tifffile
    arr = np.random.randint(0, 65535, (3, 512, 512), dtype=np.uint16)
    p = tmp_path / "test.ome.tiff"
    tifffile.imwrite(str(p), arr, photometric="minisblack")
    mip, ch_names, pixel_um = generate_mip_from_ometiff(p, z_planes=None)
    assert mip.shape == (3, 512, 512)
```

## Mocking

Not applicable — no test framework in use. When tests are added:
- Mock `aicspylibczi.CziFile` for unit tests that don't need real CZI data
- Use `tmp_path` pytest fixture for output file tests
- Do NOT mock `tifffile` — the OME-XML embedding behaviour needs real file I/O to verify

## Coverage

**Requirements:** None enforced.

**Current state:** 0% automated coverage. All validation is visual/manual.

## Biological Validation Protocol (Manual QC Checklist)

When running a new section through the pipeline:

1. `--info` check: channel names and pixel size match acquisition metadata
2. QuPath import: image opens at correct physical dimensions
3. ABBA registration: AP position within ±0.3 mm of anatomical expectation
4. Detection pilot: run on one ROI, spot-check 10 cells manually for TdT+/Fos+/double+ classification
5. Colocalization check: confirm nucleus-containment rule applied (not proximity)
6. Atlas export: spot-check one region's cell coordinates in µm against atlas reference

---

*Testing analysis: 2026-06-30*
