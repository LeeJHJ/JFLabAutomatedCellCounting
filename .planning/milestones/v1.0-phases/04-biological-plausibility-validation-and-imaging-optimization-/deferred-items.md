# Phase 4 — Deferred Items (out-of-scope discoveries)

Per the executor's scope boundary: issues found during Plan 04-03 Task 2 that are
**not** caused by this task's own changes (`scripts/val01_metrics.py`,
`04-VALIDATION-RECORD.md`) are logged here rather than fixed. Both items below live
in Phase 3's locked `scripts/02_detect_classify.groovy` and/or Plan 04-01's
`scripts/03_export_val01_metrics.groovy` region-labeling closures (`regionOf` /
`regionLabel`), which are out of this plan's file scope and out of Phase 4's
mandate (re-tuning/re-deriving detection or classification logic is explicitly
excluded by D-01).

## D-1: Per-cell region-label resolution appears hemisphere-asymmetric for at least one hemisphere (RESOLVED)

**Status: RESOLVED 2026-07-17.** Root-caused and fixed by Phase-4 code review CR-01
(`04-REVIEW.md`) — the `regionOf`/`is_leaf` closures used child-annotation topology to decide
"leaf region," which disagreed across hemispheres for rollups like `grey`, causing first-match
cell attribution to silently absorb 95,383 cells (44.8% of the section) into the `grey`
catch-all instead of their true finest subregion. Fixed in `scripts/03_export_val01_metrics.groovy`
(commit `29dbfdc`: `regionOf` now assigns each cell to the smallest-area containing region;
`is_leaf` is now computed geometrically, hemisphere-symmetric by construction) and
`scripts/val01_metrics.py` `compute_density()` (commit `1052bc6`: dropped the now-redundant/
harmful `is_leaf` density filter). CA1's bilateral cell count went from 3,567 (right-hemisphere-
only, the symptom described below) to 6,354 (true bilateral). See the "Post-review correction"
section at the top of `04-VALIDATION-RECORD.md` for the corrected numbers and full writeup. The
observation notes below are kept for historical/audit trail — they describe the bug accurately
as it was found, before the fix.

**Found during:** Plan 04-03 Task 2, while computing per-region DAPI density from
the real `val01_percell_export.tsv` / `val01_region_area.tsv` pair.

**Observation (measured):**
- `val01_region_area.tsv` correctly lists both `Left: <acronym>` and `Right:
  <acronym>` leaf rows for every hippocampal subfield (e.g. `Left: CA1` area
  0.794552 mm², `Right: CA1` area 1.086779 mm², both `is_leaf=true`) — the ABBA
  annotation hierarchy itself is symmetric and correctly loaded (141 Left leaf
  rows vs. 144 Right leaf rows).
- However, `val01_percell_export.tsv`'s per-cell `region_label` count for `CA1`
  is 3567 — which is numerically identical to the *Right-hemisphere-only* raw
  DAPI count recorded in Phase 2's `reference/dapi_region_reference.csv`
  (`"Right: CA1"` → `n_dapi=3567`). Phase 2's `"Left: CA1"` row shows a further
  2787 nuclei that do not appear to be reflected in the current `CA1`-labeled
  cell count.
- 95,383 of 213,106 per-cell rows (44.8%) carry `region_label="grey"` — a broad,
  non-leaf-in-the-usual-sense ancestor bucket. Cross-referencing
  `val01_region_area.tsv`: `Left: grey` is flagged `is_leaf=true` (area
  24.599842 mm², essentially the whole left-hemisphere gray-matter footprint),
  while `Right: grey` is correctly `is_leaf=false` (24.834326 mm², a true
  non-leaf ancestor with real leaf children). This asymmetry (`grey` appearing
  as a *leaf* only on one side) is consistent with — though not proven to be
  the sole cause of — cells on that hemisphere resolving to the broad `grey`
  ancestor label instead of their true leaf subregion.
- Spatial cross-check: median `centroid_x` for `CA1`-labeled cells is 5936.5,
  vs. 11167.9 for `grey`-labeled cells — a large, consistent offset, i.e. the
  two labels occupy spatially distinct clusters within the image, consistent
  with a hemisphere-linked resolution gap rather than random mislabeling.

**Why this was not fixed here:** the root cause (if confirmed) lives in the
`regionOf`/`regionLabel` centroid-in-ROI closures shared by
`scripts/02_detect_classify.groovy` (Phase 3, locked/verified) and
`scripts/03_export_val01_metrics.groovy` (Plan 04-01, locked/verified) — neither
file is in this task's `files` list, both are independently verified/locked
artifacts from prior phases, and per the Scope Boundary rule only issues
*directly caused by the current task's changes* are auto-fixed. Re-deriving or
patching region-hierarchy resolution logic is also explicitly out of Phase 4's
mandate (D-01: "Re-tuning detection is explicitly out of scope here").

**Impact on this plan's deliverable:** `04-VALIDATION-RECORD.md`'s per-region
density table (and the per-subfield ratio breakdown) are reported as measured
from the real export exactly as `val01_metrics.py` computes them (correctness
of the *Python* aggregation was fixed — see below), but the record explicitly
flags that leaf-region nuclei counts may be **right-hemisphere-dominated /
under-representing the left hemisphere** for at least CA1, pending confirmation
of this finding. This is not a Phase-4 scope violation to leave open: VAL-01 is
a findings record (D-01), and this is exactly the kind of flagged note for the
full series the phase's own framing anticipates.

**Recommendation for the full series (SERIES-01/02):** before batch-processing
additional sections, add a quick per-hemisphere leaf-count parity check (e.g.
compare `n_dapi` recovered per acronym against `reference/dapi_region_reference.csv`'s
per-hemisphere-split numbers, or add a hemisphere-qualified `region_label`
column to the export) to confirm or rule out this resolution gap before it
silently biases whole-brain density/ratio aggregates across many sections.

## D-2: `compute_density` in `scripts/val01_metrics.py` joined on the wrong key (FIXED, not deferred)

Not deferred — auto-fixed in this task per Rule 1 (bug: code doesn't work as
intended). Logged here only for cross-reference: the original `compute_density`
joined per-cell region counts to `val01_region_area.tsv` on the bare
`region_label` column, but the region-area export's `region_label` carries a
`"Left: "/"Right: "` hemisphere prefix while the per-cell export's
`region_label` is the bare acronym — the join matched **zero rows** and the
density table printed empty. Fixed by aggregating leaf-region areas across
hemispheres by `acronym` before joining (see `scripts/val01_metrics.py`
`compute_density`, commit in this task). See `04-VALIDATION-RECORD.md`
Methodology Note for the user-facing writeup.
