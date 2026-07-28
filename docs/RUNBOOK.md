# Pipeline Runbook

Run from repository root unless noted.

## 1) Convert CZI to hybrid OME-TIFF (current path)

```bash
conda run -n braian python3 scripts/czi_hybrid_mip.py \
  --czi data/raw/<input>.czi \
  --out results/<output>.ome.tiff \
  --channels "AF568-T2" "AF488-T3" "DAPI-T4" \
  --dapi-index 2 \
  --dapi-plane auto \
  --marker-planes 0-2
```

## 2) Legacy full-stack MIP conversion (compatibility only)

```bash
conda run -n braian python3 scripts/legacy/czi_mip.py \
  --czi data/raw/<input>.czi \
  --out results/<output>.ome.tiff \
  --channels "DAPI" "Fos-AF488" "TdTomato-AF568" \
  --pixel-um 0.69
```

## 3) QuPath detection/classification (GUI)

Open the target QuPath project under `data/projects/...`, then run scripts from `scripts/` in order:

1. `01_load_abba_rois.groovy`
2. `02_detect_classify.groovy`
3. `03_export_val01_metrics.groovy`

Use `run_braian_detection.groovy` when running the full BraiAn detection flow in one scripted pass.

## 4) Validation metrics

```bash
conda run -n braian python3 scripts/val01_metrics.py \
  --percell-tsv "data/projects/m3-hippocampus-20x-062926-3-plane/results/val01_percell_export.tsv" \
  --region-tsv "data/projects/m3-hippocampus-20x-062926-3-plane/results/val01_region_area.tsv" \
  --out results/val01_metrics.json
```

## 5) DAPI reference build

```bash
conda run -n braian python3 scripts/build_dapi_reference.py
conda run -n braian python3 scripts/build_dapi_reference.py --leaf-only
```

## 6) Hygiene cadence (after each major phase)

- Remove or archive stale generated files from local working directories.
- Keep new project/dataset folder names in kebab-case under `data/projects/`.
- Keep scripts in `scripts/` (or `scripts/legacy/` only if intentionally deprecated).
- Review tracked files with `git status` before commit to avoid accidental data churn.
