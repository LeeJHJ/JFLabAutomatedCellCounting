---
task: cockpit-checks-notebooks
quick_id: 260728-nus
date: 2026-07-28
status: in-progress
---

# Cockpit increment 1 — QC gates + thin calibrate/batch notebooks

Build the section-pipeline cockpit as thin notebooks over shared modules, following the
pipeline's own "tune on ONE section, then scale" rule (CLAUDE.md). Increment 1 of 3;
increment 2 (`scripts/cockpit_regions.py`) already landed in `c7d567f` and is wired in here.

## Recon findings (verified against the primary fixture, not assumed)

Primary fixture: `/home/jflab/Analysis/wBA 1-3 2-1 072026/wBA_1-3_2-1_072026/` — 5 slices (s1..s5),
markers Fos (AF488-T3, nuclear) + TdT (AF568-T2, whole-cell), anchor DAPI/DAPI-T4, k_robust 3.0,
exclude_acronyms [DG-sg, VS].

Load-bearing discoveries that shape the design:

1. **`atlas_cells.tsv` is NOT usable for per-region density.** Its `region_label` column is
   `"DAPI-T4"` on every row — it carries the detection class, not an atlas region. Per-region
   work must use `percell_export.tsv` (bare acronyms in `region_label`) and `regions.tsv`.
2. **`regions.tsv` is the right source for the density gates.** Columns:
   `Image Name | Name | Classification | Area um^2 | Num Detections | Num <anchor channel>`.
   `Name` is the bare acronym, `Classification` is `"Left: <acr>"` / `"Right: <acr>"`, and counts
   are already hierarchically rolled up per named region by QuPath. Reading ONE named region's
   row gives count and area together — this structurally avoids the nested-annotation
   denominator bug (never sum sibling/nested rows).
3. **Anchor count column is config-derived**: `f"Num {anchor.channel}"` from `pipeline.yml`
   (`"Num DAPI-T4"` here). Falls back to `Num Detections` if absent. Never hardcoded.
4. **`region_area.tsv` joins on `acronym`**, not `region_label` (`region_label` is
   hemisphere-prefixed `"Left: CA1"`). Not needed for the gates given (2), but relevant to
   cockpit_regions.
5. **The fixture genuinely FLAGs.** Computed by hand from s1: cc = (2460+3135)/(0.5333+0.6386) =
   **4774/mm²** vs Isocortex = (32119+27936)/(7.3364+7.4993) = **4048/mm²** → ratio **1.18**,
   fails the 0.6 guard. VS = (516+414)/(0.3313+0.3744) = **1318/mm²**, fails the 500 guard.
   These are real detection-quality findings, not test failures — the gates must report them.

Reusable APIs confirmed present:
- `k_sweep_readout`: `robust_stats`, `robust_threshold`, `classifiable_mask`, `load_percell`,
  `markers_in_df`, `region_acronym`, `section_label`, `analyze_section`.
- `cockpit_regions`: `load_pipeline_config` → `Config`, `build_readout`, `write_csv`,
  `read_regions_file`, `coverage_report`.
- Groovy (per project `scripts/`): `run_braian_detection.groovy`, `02_detect_classify.groovy`,
  `03_export_region_table.groovy`, `find_threshold().groovy` (present in the M3 and tdt-only
  projects, NOT in the wBA fixture — the notebook must handle its absence gracefully).

## Tasks

1. **`scripts/cockpit_checks.py`** — importable, self-testable QC-gate module.
   - Config access: read `anchor.channel` from `pipeline.yml`; reuse
     `cockpit_regions.load_pipeline_config` for marker set / exclusions. No hardcoded
     marker, channel, or threshold values.
   - `GateThresholds` dataclass — every gate limit tunable, no magic numbers in gate bodies.
   - `GateResult` NamedTuple exposing `.value` and `.status` ("PASS"/"FLAG"), plus `.name`,
     `.detail`, `.advisory` for rendering.
   - Loaders: `find_slices()`, `load_regions_tsv()`, `load_percell_for_slice()`.
   - Gates: nucleus-area peak; white-matter over-detection (key gate); ventricle guard;
     grey-matter per-region density (advisory); total-count sanity (advisory); k-sweep
     stability of P(marker+|other marker+).
   - `run_all_gates(slice)` → list[GateResult]; `gate_table(project)` → one row per slice.
   - `--self-test` on synthetic data; `main()` CLI so it runs standalone.
2. **`notebooks/01_calibrate.ipynb`** — thin; one PARAMS dict at top. Config panel → threshold
   sweep (dry-run command) → EXPENSIVE detect-one-slice (dry-run) → cheap QC gates + area
   histogram → lock PARAMS into BraiAn.yml (backup first, explicit opt-in flag).
3. **`notebooks/02_batch.ipynb`** — thin; one PARAMS dict at top. Config panel → EXPENSIVE
   batch detect/classify/export (dry-run, skippable) → per-slice QC table → k-sweep →
   cockpit_regions region CSV → Fos-centric readout + plots + tidy CSV.
4. **Verify**: run both notebooks top-to-bottom in the `braian` env against the primary
   fixture; confirm the tdt-only secondary fixture does not crash (no Fos/Double).

## Constraints

- `braian` env only (`/home/jflab/miniforge3/envs/braian/bin/python3`); CPU-only.
- Every param read from `BraiAn.yml` / `pipeline.yml`; never hardcoded.
- Do NOT fork classification logic — import `k_sweep_readout` and `cockpit_regions`.
- Do NOT run a real detection pass. Expensive cells print the exact headless command
  (`DRY_RUN=True` default) rather than executing.
- Notebooks stay thin: logic lives in the modules.

## Out of scope

Speeding up detection; ABBA registration; changing Groovy logic; group/condition stats;
rebuilding animal-level rollup (that is cockpit_regions').
