---
gsd_quick: true
slug: add-cockpit-regions-py-region-of-interes
quick_id: 260728-kbs
date: 2026-07-28
env: braian (CPU-only)
---

# Quick Task: cockpit_regions.py — region-of-interest readout CSV (cockpit increment 2 of 3)

## Goal
Standalone importable module `scripts/cockpit_regions.py` that, given an operator list of
Allen acronyms, emits a tidy **per-slice** CSV of DAPI/marker counts + densities +
reactivation ratios per region, with **ontology-driven, exclusion-aware roll-up** and a
**hemisphere split (L/R) + pooled (both)** row. Marker columns are generated dynamically
from `pipeline.yml` so a TdT-only config emits DAPI+TdT only (no Fos/Double), no errors.

## Load-bearing design decisions (verified against the tdt-only fixture, 2026-07-28)
1. **Roll up from the ONTOLOGY, never from the region_table's parent rows.** Verified: the
   region_table's parent-rollup rows follow QuPath's *annotation* hierarchy, which does NOT
   match the Allen ontology — e.g. `BMA` parent row shows DAPI=0 while its child `BMAa` holds
   1253 (BMAa is not nested under BMA in QuPath). Trusting parent rows would silently zero
   real regions.
2. **"included_leaves(R)" = ontology-frontier present acronyms.** A requested acronym's leaf
   set = present acronyms that are ontology descendants-or-self of R AND have no present
   ontology descendant (the data frontier), minus `exclude_acronyms` ∪ their descendants.
   This makes LA→{LA}, CA1→{CA1} (both are `is_leaf=False` geometric rows but have no finer
   region in the data — pure geometric-`is_leaf` summation would report them as 0). Each
   frontier row's count == its own bucket → the leaf set is non-overlapping, safe to sum.
3. **count(R,hemi,cat) & area(R,hemi) summed over the IDENTICAL frontier-leaf set** → no
   denominator drift. Excluding DG-sg drops both its count (already 0) and its area from every
   roll-up (HPF area 2.835→2.684 mm² L; DG 0.588→0.445).
4. **Coverage caveat, surfaced not hidden:** frontier summation omits cells whose finest
   containing annotation is a non-frontier intermediate node (whole-brain ~16%; focused
   engram regions ~0–0.3%). The module reports per-region coverage; this matches the GOAL's
   `count = Σ over included_leaves` definition and is documented, not swallowed.
5. **Pooled "both" = L+R summed counts/areas; densities & ratios RECOMPUTED from pooled sums**
   (never averaged).

## Data sources (reused, read-only — no QuPath / detection re-run)
- `<project>/pipeline.yml` — markers (name/channel/compartment), `exclude_acronyms`. Parsed
  with PyYAML (valid YAML; sibling `k_sweep_readout.py` does the same).
- `<project>/allen_mouse_10um_java-Ontology.json` — authoritative tree; acronyms under
  `node.data.acronym`, name under `node.data.name`. Fallback to brainglobe atlas only if absent.
- `<project>/results/*__region_table.tsv` — per-slice, per-annotation rows:
  `region_label, hemisphere, acronym, is_leaf, area_mm2, <cat>_count, <cat>_density`.
  Anchor column prefix has no `+` (`DAPI_count`); markers do (`TdT+_count`); `Double+_count`
  only when ≥2 markers. Density is recomputed by us (count/area), not read.
- `<project>/regions_of_interest.txt` — one acronym/line, `#` comments ok; absent → all
  included leaves.

## Output
`<project>/results/region_of_interest_readout.csv`, one row per (slice_id, region, hemisphere∈{L,R,both}):
`project, animal, slice_id, hemisphere, region_acronym, region_name, level(leaf|summary),
area_mm2, DAPI_count, DAPI_density, <M>+_count, <M>+_density…, [Double+_count, Double+_density
if ≥2 markers], [P(<m1>+|<m0>+), P(<m0>+|<m1>+) if Double emitted]`.
Density = count/area_mm2 (/mm²); ratios = Double/marker, NaN if denom 0. animal/slice parsed
from the region_table filename (`…_sN` → animal prefix + `sN`), or a declared `animal:` field.

## Tasks
1. Write `scripts/cockpit_regions.py`: PyYAML config loader, Ontology (parent/desc/ancestors),
   region_table loader (filename→project/animal/slice), `included_leaves`, `rollup`,
   `build_readout`→DataFrame, `write_csv`, argparse `main`, `--self-test`.
2. Create `<fixture>/regions_of_interest.txt` mixing summary+leaf (LA, BLA, BMA, HPF, CA1).
3. Self-test (synthetic fixture): exclusion-aware roll-up, parent==Σ leaves, TdT-only→no
   Fos/Double, unknown-acronym→warn-not-crash, L+R+both, pooled ratios from sums.
4. Run against the real tdt-only fixture; eyeball LA/BLA/BMA/HPF/CA1 roll-up + coverage.
5. Atomic commit.

## Acceptance (against tdt-only fixture)
- Roll-up correct: parent row == Σ its included leaves; excluded DG-sg contributes to no
  count/area.
- TdT-only → DAPI+TdT columns only, no Fos/Double, no errors.
- Unknown acronym → warning, not a crash.
- Left + Right + pooled rows all present; pooled counts = L+R, ratios recomputed from sums.

## Out of scope
Animal-level rollup across slices (increment 3); group/condition stats; re-running detection.
