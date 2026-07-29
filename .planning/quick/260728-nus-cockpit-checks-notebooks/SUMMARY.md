---
task: cockpit-checks-notebooks
quick_id: 260728-nus
date: 2026-07-28
status: complete
---

# SUMMARY — Cockpit increment 1: QC gates + thin calibrate/batch notebooks

## Delivered

| File | What |
|---|---|
| `scripts/cockpit_checks.py` | QC-gate module: 6 gates, headless QuPath command builder, BraiAn.yml param locking, `--self-test` |
| `notebooks/01_calibrate.ipynb` | Tune detection on ONE slice → inspect gates → lock into BraiAn.yml |
| `notebooks/02_batch.ipynb` | Apply locked params across all slices → QC table → k-sweep → region CSV → readout |

Notebooks are thin — all logic lives in `cockpit_checks` / `k_sweep_readout` / `cockpit_regions`.
Each opens with a single editable `PARAMS` dict.

## Gates (each reports its measured value AND a PASS/FLAG verdict)

| Gate | Blocking | Rule |
|---|---|---|
| `nucleus_area_peak_um2` | yes | modal nucleus area within 50–150 µm² |
| `white_matter_density` | yes | worst fiber tract ≤ 0.6× cortex and ≤ 1500/mm² |
| `ventricle_density` | yes | VS ≤ 500/mm² |
| `grey_density_median` | advisory | named grey regions within 500–2000/mm² |
| `total_density` | advisory | detections per registered mm² in a plausible band |
| `k_swing_pp` | yes | P(target+\|condition+) swings ≤ 10 pp across k |

## Recon findings that shaped the design

1. **`atlas_cells.tsv` cannot drive per-region work** — its `region_label` column holds the
   detection class (`"DAPI-T4"`) on every row, not an atlas region. Region work uses
   `percell_export.tsv` + `regions.tsv`.
2. **`regions.tsv` is the density source.** QuPath already rolls counts *and* area up per named
   region, so reading ONE region's row yields numerator and denominator together — this is how
   the nested-annotation denominator bug is avoided structurally rather than by convention.
   `region_density()` pools Left+Right of the *same* region and deliberately cannot sum
   different regions.
3. **White matter is measured per-acronym and the worst reported**, because `fiber tracts`
   already contains `cc` and `int` — summing them would double-count.
4. **Marker name ↔ column case mismatch (bug found and fixed).** Exports write `fos_bgsub` /
   `tdt_bgsub`; `pipeline.yml` declares `Fos` / `TdT`. Exact-match lookup silently found
   nothing and *every* marker-dependent gate degraded to N/A. `resolve_marker_tokens()`
   bridges it; the synthetic fixture now reproduces the lowercase columns so it stays covered.
5. **`lock_detection_params` edits values in place, not via `yaml.safe_dump`** — BraiAn.yml's
   comments record why each number is what it is (the `sigmaMicrons` comment alone documents
   the whole wBA-vs-M3 tuning call). A dump-based rewrite would silently delete all of it.
   Writes are verified by re-parsing before the file is touched; unknown keys raise.

## Verification

- `cockpit_checks.py --self-test`: **all pass**, 10 sections — both PASS and FLAG branches of
  every gate, threshold tunability, headless command construction, param locking + comment
  preservation + backup, single-marker path, missing-table degradation.
- **Primary fixture** (wBA1-3, Fos+TdT, 5 slices): both notebooks run top-to-bottom, 0 errors.
  Full Fos+/TdT+/Double+ columns. Totals at k=3: DAPI 999,711 · Fos+ 83,621 · TdT+ 68,071 ·
  Double+ 28,924. **P(Fos+|TdT+) = 42.4% (40.7–44.9%)** — reproduces the known wBA1 result
  (~36–42%), confirming classification logic is imported, not forked.
- **Secondary fixture** (tdt-only): both notebooks run, 0 errors. TdT+ only, no Fos/Double
  anywhere, k-sweep reports the single-marker path explicitly, region CSV built via
  `cockpit_regions` (57 rows over LA/BLA/BMA/HPF/CA1).
- **PARAMS drives behavior**: default thresholds → 5/5 FLAG; loosened thresholds → 5/5 PASS.

## Follow-up commits (operator calls made after the initial three)

| Commit | Change |
|---|---|
| `9618458` | `GateThresholds.advisory_gates` — park white-matter + ventricle as advisory. They still compute and still report FLAG (tagged `[demoted to advisory]`), but no longer drive the verdict. Not a deletion and not a threshold fudge. **Consequence: DAPI densities untrustworthy while parked**; ratio readouts (P(Fos+\|TdT+)) unaffected — no DAPI denominator. Remove the entry to re-arm. |
| `fee7a1a` | Nucleus-area band lower bound 50 → **25 µm²**, as the DEFAULT. Operator domain call: 50–150 was M3-derived (over-projected DAPI merged/inflated nuclei) and never matched what the images showed. Thin Z deblends, so 27–32 µm² peaks (~5.9–6.4 µm equiv. diameter) are real, not fragmentation. Floor still catches genuine over-splitting (over-split fixture peaks 17.5 µm² and still FLAGs). |

**Final QC state — both fixtures 5/5 PASS:** wBA1-3 peaks 27.5–32.5 µm², tdt-only 32.5 µm².
The table is now at a clean baseline, so the next FLAG means something actually changed
rather than being steady-state noise. Self-test still all-pass; both notebooks 0 errors.

## Findings for the operator (real, not test artifacts)

Both wBA fixtures FLAG the same three gates on every slice:

- **white matter over-detection** — cc ≈ 4,500–5,000/mm² vs Isocortex ≈ 4,000/mm² (ratio ~1.18).
  White matter should sit *below* cortex; this is the DAPI-haze signature the gate was built
  to catch, and it is the same failure noted on the recent M3 run (cc ~5100 vs cortex ~3900).
- **ventricle** — VS ≈ 1,200–2,300/mm² against a ≤500 guard.
- **nucleus area peak** — 27–32 µm² against a 50–150 band. This one is likely a *band* problem,
  not a detection problem: `BraiAn.yml` itself records that the 50–150 gate is M3-blob-calibrated
  and was re-baselined for wBA's cleaner imaging, which was validated visually as one-detection-
  per-nucleus. The gate reports the number; the threshold is tunable via `PARAMS["thresholds"]`.
  It was deliberately **not** silently retuned.

The white-matter and ventricle flags are worth acting on before these counts are used.

## Known gap (not fixed — would require an expensive re-export)

`cockpit_regions.build_readout()` consumes `*__region_table.tsv`. The primary wBA1-3 fixture
predates that consolidated export and carries only `*__region_area.tsv` (areas, no counts —
not a substitute), so section 5 of `02_batch` skips with an explanatory message and prints the
exact re-export command. The tdt-only fixture has the table and exercises the path fully.

## Deviations from spec

- Gates return a `GateResult` NamedTuple exposing `.value` and `.status` rather than a bare
  2-tuple, so the notebook can also render the gate's name and explanatory detail.
- `find_threshold().groovy` is absent from the wBA fixture (it exists in the M3 and tdt-only
  projects), so `01`'s sweep cell detects that and explains rather than failing.
