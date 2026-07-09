# Internal per-region DAPI density reference

Purpose: build an **empirical** reference for DAPI nucleus density per Allen CCF region
from *our own* images, so expected densities and QC gates are defined from data
(SERIES-02 drift monitoring) rather than a literature seed. This is the principled
replacement for the rough `500–2000 /mm²` D-05 seed range.

## Workflow

1. **Per section (in QuPath), after a BraiAnDetect detection pass:**
   run `scripts/export_region_dapi_reference.groovy`. It appends one row per atlas
   region to `reference/dapi_region_reference.csv`, tagged with a `config_tag` that
   encodes the exact detection params (sigma / threshold / area limits / expansion),
   read straight from `BraiAn.yml`.

2. **Whenever you want the reference (braian env, from the Analysis root):**
   ```bash
   conda run -n braian python scripts/build_dapi_reference.py            # per-region mean±SD/CV
   conda run -n braian python scripts/build_dapi_reference.py --leaf-only
   ```
   → writes `reference/dapi_region_reference_stats.csv`.

3. **QC a section against the accumulated reference:**
   ```bash
   conda run -n braian python scripts/build_dapi_reference.py \
       --flag-image "<image name as shown in QuPath>" --z 2.5
   ```
   Flags regions whose density is > z SD from the reference (bad staining /
   registration / detection). Needs ≥2 other same-config images to be meaningful.

## Rules
- **Only same-`config_tag` rows are ever compared.** Change a detection param → new tag →
  don't mix. Re-export earlier sections under the new config before comparing.
- Rows include every region *level* (leaf + parents + whole-brain `allen_mouse_10um_java`);
  use `--leaf-only` for the finest, non-overlapping regions.
- `dapi_region_reference.csv` is the raw append log; `*_stats.csv` is regenerated.

_Scaffold — extend with marker (Fos⁺/TdT⁺/Double⁺) fractions once detection is locked._
