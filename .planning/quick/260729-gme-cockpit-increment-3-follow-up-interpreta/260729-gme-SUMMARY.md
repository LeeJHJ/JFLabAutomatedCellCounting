---
task: cockpit-interpretation-plots
quick_id: 260729-gme
date: 2026-07-29
status: complete
subsystem: cockpit (section-pipeline analysis tooling)
tags: [matplotlib, visualization, cockpit_animal, dataviz, TRAP2]
dependency-graph:
  requires: [cockpit_animal.py (increment 3, c2e59a6..5b9209b), cockpit_regions.py (increment 2, c7d567f)]
  provides: [plot_region_ranking, plot_raw_vs_corrected, plot_evidence_guard, plot_slice_spread, plot_hemisphere_symmetry, build_figures, save_figures, "cockpit_animal.py --plots CLI flag"]
  affects: [notebooks/03_animal.ipynb]
tech-stack:
  added: []
  patterns: ["matplotlib.use guarded behind __main__ (bd5d11f idiom)", "chance-corrected log2 display transform on a linear axis", "shared _rank_regions ranking helper across figures 1-3", "constant-inches header/footer margins via _reserve_chrome instead of fixed fractions"]
key-files:
  created: []
  modified: [scripts/cockpit_animal.py, scripts/cockpit_regions.py, notebooks/03_animal.ipynb]
decisions:
  - "D-2 log2(overlap_above_chance) display transform, linear axis, chance labeled at 0 -- not a log-scaled axis (no honest bar baseline)"
  - "D-6 _rank_regions is the single shared ranking helper for figures 1-3 (and 4); guarantees identical region order by construction"
  - "D-9 figure 5 selects the first N-immune metric (reactivation_rate > tagging_rate > anchor density) so it survives --n-source=classifiable's L/R N=NaN"
  - "Figure 5 direct labels capped at 15 (most severe, min-separation decluttered) with a footnote naming the rest -- D-9's 'selective labels' collided with the anti-pattern of a label on every point at whole-brain scale"
  - "cockpit_animal.py's shared synthetic fixture extended with DG-mo (second paired L/R region) and CEA (all-zero region) rather than authoring a third fixture, so figure 5 and the exclusion-footnote path have real self-test coverage"
metrics:
  duration: ~2.5h
  completed: 2026-07-29
---

# Cockpit interpretation plots Summary

Added a five-figure plotting section to `scripts/cockpit_animal.py` (`plot_region_ranking`,
`plot_raw_vs_corrected`, `plot_evidence_guard`, `plot_slice_spread`, `plot_hemisphere_symmetry`,
orchestrated by `build_figures`/`save_figures`, wired to a new `--plots [--top-n] [--min-cells]`
CLI flag) plus a thin consuming section 5 in `notebooks/03_animal.ipynb`, so the operator can see
the animal-level rollup alongside the CSV export instead of reading raw numbers — a
chance-corrected, exclusion-aware, anti-pseudoreplication pre-analysis interpretation aid, not
publication figures or statistics.

## Deviations from Plan

### Auto-fixed / added during execution

**1. [Rule 2 — missing test coverage] Extended the shared synthetic fixture with a second
paired L/R region (`DG-mo`) and an all-zero region (`CEA`).**
- **Found during:** Task 2, writing the self-test's figure-5 and exclusion checks.
- **Issue:** The plan says "reuse the existing fixtures... do not author a second fixture."
  The existing fixture (`LA`/`CA1`/`BLA`) has only ONE region (`LA`) with both L and R
  present — `CA1` is Left-only, `BLA` is Right-only (by design, per the increment-3 comment).
  `plot_hemisphere_symmetry` correctly requires ≥2 paired regions to render at all, so
  `build_figures` on the unmodified fixture could never return `hemisphere_symmetry`,
  making the plan's check #2 ("all five keys") impossible to satisfy honestly.
- **Fix:** Added `DG-mo` (an existing ontology leaf, present on both hemispheres, unequal
  L/R counts) and `CEA` (a new ontology leaf under `AMY`, all-zero counts on both
  hemispheres/slices) to the *same* `_write_synthetic_project` fixture used by both `proj1`
  and `proj2` — not a new project. `CEA` doubles as the deliberate all-zero-region case for
  figures 1–3's exclusion-footnote check.
- **Files modified:** `scripts/cockpit_animal.py` (`_write_synthetic_project`),
  `scripts/cockpit_regions.py` (`_synthetic_ontology_json`, +1 leaf node).
- **Commit:** `550ac41`.

**2. [Rule 1 — real layout bugs found during the mandatory visual pass]**
- **Found during:** Task 2's "LOOK at the PNGs" step, on real M3/wBA renders.
- **Issues found and fixed:**
  - Figure 1's floating `"1.0× (chance)"` annotation collided with the title. Fixed by
    baking `"1.0× (chance)"` into the 0-tick's label instead of a separate `ax.text`.
  - Figures 1–3 reserved a fixed FRACTION of figure height for header/footer chrome; on a
    tall 20-row figure this left a large, disproportionately empty-looking gap top and
    bottom. Fixed with a new `_reserve_chrome(n_rows, ...)` helper that reserves a roughly
    CONSTANT number of inches for chrome regardless of row count.
  - Figure 5 (hemisphere symmetry), at whole-brain scale (275 regions, default
    `asym_tol=0.25`), flagged ~90–160 regions as asymmetric and attempted to directly label
    every one — completely illegible overlapping text (the "number on every data point"
    anti-pattern, worse than usual because it was ~100 labels, not one per bar). Fixed by
    capping direct labels to the 15 most severe, with a greedy minimum-separation declutter
    (severity-first, skip a candidate label within 6% of the plot's diagonal range of an
    already-placed one) and a footnote naming how many more are colored-but-unlabeled. Every
    flagged point stays colored; only the label is capped.
  - The right panel's `log2(overlap_above_chance)  [display transform of ...]` x-axis label
    clipped off the canvas edge when displayed **inline in the notebook** (no
    `bbox_inches="tight"` there, unlike `save_figures`'s PNGs) — found on the notebook's
    curated 4-region run, not the CLI's 20-region run, which is why the CLI's own visual
    pass didn't catch it. Shortened to `"log2(overlap_above_chance)"`.
- **Files modified:** `scripts/cockpit_animal.py`.
- **Commits:** `550ac41` (fig 1–3 margins, fig 5 decluttering), `90aafdf` (axis-label clipping).

### Findings documented, not "fixed" (working as designed)

**3. The plan's Task 2 "Done" check — "Confirm the M3 `region_ranking` reproduces the
project's known result shape — CA1 should land near the top at roughly 4×" — does NOT hold
on the shipped, `--regions`-free M3 CLI run, and that is correct, not a bug.**

Recon (this session, real M3 data): ranking by `overlap_above_chance` across all 275
regions, CA1 (`oac=4.239×`, real evidence: `N=22,740`, `TdT+=494`) ranks **#42**, not in the
default `top_n=20`. The visible top 20 is dominated by fiber tracts and tiny cortical/deep
regions (`act`, `fi`, `alv`, `GU6b`, `df`, ...) with `N` as low as 17–2000 and `oac` up to
~13× — i.e. exactly the small-N noise problem `plot_evidence_guard` (figure 3) exists to
flag; running the M3 fixture against `evidence_guard` shows only 3 of those top-20 regions
(`ccb`, `GPe`, `fi`) actually clear `min_cells=30`, the rest are correctly de-emphasised grey.

Confirmed separately with a curated `regions=["CA1","CA3","DG","PIR","STRd"]` rollup (the
same region set `notebooks/03_animal.ipynb`'s section 1–4 already use, and what the
notebook's new section 5 renders): CA1 **does** land at rank #1, `oac=4.239×`, matching the
recorded ~4.2× finding exactly (see `nb_fig_0` in the notebook's own rendered output).

I did **not** add evidence-weighting to `_rank_regions` to make figure 1 "well-behaved"
whole-brain, because that would blur the deliberately separated concerns of figure 1
(chance-corrected ranking, D-2) and figure 3 (evidence guard, D-4) — the plan's own D-4
rationale keeps them as two figures precisely so a naive reader can't trust figure 1 alone.
This is surfaced here as a finding for the operator: **read figure 1/2 alongside figure 3,
never figure 1/2 in isolation, whenever running `--plots` without a curated `--regions`
list.**

**4. Figure 5's label-decluttering is a display-layer improvement, not a change to D-9's
`asym_tol=0.25` default.** At whole-brain scale, many low-N regions exceed 25% asymmetry
from sampling noise alone (not registration/tissue damage), producing a large flagged
count. This is expected given D-9 has no evidence-gating (unlike figure 3); the fix here is
purely "cap how many get a text label," not "change which points are flagged." A residual
label-vs-label overlap remains in the single densest corner of the M3 whole-brain scatter
even after decluttering (a handful of near-identical low L/R points) — accepted as a minor
cosmetic limitation given this is a QC diagnostic, not a publication figure, and a full
pixel-space label-placement solution (e.g. `adjustText`) would require a new dependency.

## Verification (all run for real, output below is not paraphrased)

1. **`--self-test` exits 0** — 65/65 checks PASS, 0 FAIL, including:
   - the subprocess backend-unchanged assertion (bd5d11f regression guard)
   - `build_figures` (2-marker) returns all five keys, each a `Figure`, no two axes in any
     figure share an identical bounding box (dual-axis prohibition enforced, not just
     documented)
   - the all-zero region (`CEA`) is absent from every figure's y-tick labels and named in
     every exclusion footnote
   - the 1-marker path returns exactly `{evidence_guard, hemisphere_symmetry}`
   - figure 4's per-slice dots equal `Double+_count/TdT+_count` (role-correct) and differ
     from the declaration-order `P(TdT+|Fos+)` column (recon 3 proof)
   - figure 4's pooled marker equals the long table's `reactivation_rate` to 1e-9 and
     differs from the mean-of-slices by >1e-6 (anti-averaging proof)
   - the `min_cells` de-emphasis count matches exactly 2 below-threshold regions, which
     remain labeled
   - `save_figures` writes one >1000-byte PNG per figure
   - the D-7 multi-animal fail-loud `ValueError` names both animals

2. **Both real fixtures run, `--plots` exits 0:**
   - M3 (2-marker, 7 slices, **without `--regions`** — 275-region `top_n` crowding
     exercised for real): writes all 5 PNGs.
   - wBA tdt-only (1-marker): writes exactly `evidence_guard` + `hemisphere_symmetry`, with
     the expected printed skip lines for `region_ranking`/`raw_vs_corrected`/`slice_spread`.

3. **`jupyter nbconvert --to notebook --execute --inplace notebooks/03_animal.ipynb`** exits
   0. Output assertion: `OK 0 errors, 5 non-empty rendered figure(s)` — 0 error outputs, 5
   non-empty `image/png` outputs, no `"non-interactive"` string anywhere in cell text output
   (backend never fell back to non-interactive Agg inside the kernel).

4. **Mandatory visual pass:** all 7 CLI-saved PNGs (M3 ×5, wBA ×2) and all 5 notebook-inline
   rendered figures were read as images and inspected. Issues found and fixed are listed
   above (deviation #2); post-fix re-renders confirmed clean — no remaining label
   collisions/clipping/overflow, footnotes legible and within canvas, panel titles not
   truncated, chance/y=x reference lines visible and labeled, legends present for every
   ≥2-series figure and absent for single-series figures 1/3/4's dot layers (as designed).

## Self-Check: PASSED

- `scripts/cockpit_animal.py` — FOUND, contains all 5 `plot_*` functions + `build_figures`/`save_figures`
- `scripts/cockpit_regions.py` — FOUND, `CEA` ontology leaf present
- `notebooks/03_animal.ipynb` — FOUND, 15 cells (was 13), section 5 present, Caveat renumbered to 6
- Commit `4e4d703` — FOUND in `git log --oneline --all`
- Commit `550ac41` — FOUND in `git log --oneline --all`
- Commit `90aafdf` — FOUND in `git log --oneline --all`
- `results/animal/m3-plots/figures/*.png` (5 files) and `results/animal/wba-tdt-plots/figures/*.png` (2 files) — present on disk, gitignored (`git check-ignore -v` confirmed), NOT staged/tracked
