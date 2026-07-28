# JFLabAutomatedCellCounting

Section-pipeline workspace for TRAP2/Airyscan section analysis and Allen CCF registration.

## Repository layout

- `scripts/` — active automation scripts (Groovy + Python)
  - `scripts/czi_hybrid_mip.py` — current CZI -> hybrid OME-TIFF converter
  - `scripts/legacy/czi_mip.py` — legacy full-MIP converter (kept for compatibility)
- `reference/` — tracked reference tables and reference-building outputs
- `docs/` — runbooks, setup docs, notes, and presentation materials
- `data/` — QuPath projects and raw/derived dataset folders
  - `data/projects/` — project directories (standardized kebab-case names)
  - `data/raw/` — expected location for local raw microscopy source files (`*.czi`, etc.; ignored)
- `results/` — repo-level generated outputs from scripts (ignored)

## Active vs archival

- **Active pipeline entrypoints**: scripts under `scripts/`, especially `scripts/czi_hybrid_mip.py` and the QuPath Groovy workflow scripts (`01_*`, `02_*`, `03_*`, `run_braian_detection.groovy`).
- **Legacy tooling**: `scripts/legacy/czi_mip.py` (older all-plane MIP path; use only when needed for backward compatibility).
- **Historical project content**: files under `data/projects/` may contain archival experiments and prior project states; keep them for provenance but avoid creating new top-level folders.

## Quick start

See `docs/RUNBOOK.md` for common commands (convert, detect, export, validate) and cleanup cadence.
