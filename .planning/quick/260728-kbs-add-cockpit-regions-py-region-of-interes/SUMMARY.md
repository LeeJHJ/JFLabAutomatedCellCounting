---
gsd_quick: true
slug: add-cockpit-regions-py-region-of-interes
quick_id: 260728-kbs
date: 2026-07-28
status: complete
env: braian (CPU-only)
---

# Summary: cockpit_regions.py — region-of-interest readout CSV (cockpit increment 2 of 3)

## What shipped
`scripts/cockpit_regions.py` — a standalone, importable, unit-tested module that turns an
operator list of Allen acronyms into a tidy **per-slice** CSV of DAPI/marker counts +
densities + reactivation ratios, with **ontology-driven, exclusion-aware roll-up** and a
**Left/Right + pooled(both)** split. Marker/Double/ratio columns are generated dynamically
from `pipeline.yml`, so the TdT-only fixture emits DAPI+TdT columns only — no Fos, no Double,
no errors. Read-only: reuses `03_export_region_table.groovy`'s `*__region_table.tsv`, the
ontology JSON, and `pipeline.yml`; never re-runs QuPath/detection.

Also added `wBA/wBA1-2_2-1-tdt-only 072026 project/regions_of_interest.txt` (demo input:
LA, BLA, BMA, HPF, CA1).

## The load-bearing discovery (why the design is what it is)
The region_table's **parent-rollup rows follow QuPath's annotation hierarchy, which does NOT
match the Allen ontology.** Verified on real data: the `BMA` parent row reads DAPI=0 while its
child `BMAa` holds 1253 (BMAa isn't nested under BMA in QuPath). Trusting parent rows would
silently zero real regions.

So roll-up is computed from the **ontology tree**, summing the **data frontier** under each
requested acronym: `included_leaves(R)` = present acronyms that are ontology
descendants-or-self of R with no present ontology descendant, minus `exclude_acronyms` ∪
their descendants. Each frontier row's count == its own (finest-containing) bucket → the leaf
set is non-overlapping → count and area are summed over the **identical** leaf set (no
denominator drift). This also fixes the geometric-`is_leaf` trap: `LA` and `CA1` are
`is_leaf=False` rows with no finer child in the data, so a naive is_leaf sum would report them
as 0; frontier logic resolves LA→{LA}, CA1→{CA1} correctly.

## Verification (all passed)
- **Self-test** (`--self-test`, synthetic fixture): 21/21 checks — exclusion-aware roll-up,
  parent==Σ included leaves, LA/CA1 own-bucket (not 0), DG-sg contributes to no count/area,
  levels, L+R+both, pooled density/ratios recomputed from sums, unknown-acronym→warn, and the
  2-marker path (Fos+Double+ratio columns `P(Fos+|TdT+)`, `P(TdT+|Fos+)`).
- **Real tdt-only fixture** (5 slices → 57 rows): HPF(L)=8638 = sum of its 13 included
  frontier leaves (CA1,CA2,CA3,DG-mo,DG-po,ENTl*,POST,ProS,SUB); **DG-sg absent** (HPF area
  2.684 mm², not 2.84). BMA(both)=2245 sourced from BMAa — proves parent rows are never read.
  TdT-only → DAPI+TdT columns only. Unknown acronym `NOTAREGION` → warning + skip, no crash.
  Biologically plausible: DAPI ~3100–4700 /mm², TdT ~75–250 /mm².

## Known caveat (surfaced, not hidden)
Frontier summation omits cells whose finest-containing annotation is a **non-frontier
intermediate node**. Whole-brain coverage vs the region_table root rollup is 69–89% per
slice; for the focused engram regions requested here it is ~99–100%. This matches the GOAL's
`count = Σ over included_leaves` definition. `--coverage` prints the per-slice fraction so the
operator always sees it. If complete whole-brain totals are ever needed, that is an
`03_export` follow-up (attribute intermediate-bucket cells to a nearest present leaf).

## Files
- `scripts/cockpit_regions.py` (new, ~560 lines incl. self-test)
- `wBA/wBA1-2_2-1-tdt-only 072026 project/regions_of_interest.txt` (new, demo input)
- generated output `…/results/region_of_interest_readout.csv` is gitignored (`**/results/`)

## Out of scope (later increments)
Animal-level rollup across slices (increment 3); group/condition stats; wiring into the
cockpit notebook cell.
