---
task: cockpit-interpretation-plots
quick_id: 260729-gme
date: 2026-07-29
status: in-progress
env: braian (/home/jflab/miniforge3/envs/braian/bin/python3, CPU-only)
---

# Cockpit increment 3 follow-up — interpretation plots

Add a **plotting section** to `scripts/cockpit_animal.py` and a thin consuming section to
`notebooks/03_animal.ipynb`, so the operator can *see* the animal-level table alongside the CSV
export instead of reading raw numbers.

Operator's words: *"a better way to visualize data alongside the csv export — it'll help the user
better interpret vs. raw numbers before analysis."*

This is a **pre-analysis interpretation aid**. It is not publication figures and it is not
statistics. n=1 animal today; every figure must be useful at n=1 and degrade gracefully when a
second animal/group arrives.

Increment 1 = `scripts/cockpit_checks.py` (QC gates). Increment 2 = `scripts/cockpit_regions.py`
(per-slice region readout). Increment 3 = `scripts/cockpit_animal.py` (animal rollup, `c2e59a6`
… `5b9209b`). This is a follow-up to increment 3, not a fourth increment.

---

## Recon verified this session (read-only, on disk)

1. **The long table's columns** (verified against `scripts/cockpit_animal.py` as shipped):
   `group, animal, region_acronym, region_name, level, hemisphere, n_slices, projects, N_source,
   area_mm2, DAPI_count, Fos+_count, TdT+_count, Double+_count, N, DAPI_density, Fos+_density,
   TdT+_density, Double+_density, tagging_rate, activity_rate, reactivation_rate, reverse_rate,
   overlap_above_chance, log2_odds_ratio, log2_odds_ratio_hc, jaccard`.
   Marker columns are **config-derived** (`{M}+_count`) — never hardcode `Fos`/`TdT` anywhere in
   the plotting code. Resolve them through `config.marker_names` / `roles.tagged` /
   `roles.activity`, exactly as `add_metrics` already does.

2. **`hemisphere` ∈ {L, R, both}, and `both` is ALREADY L+R pooled** (`build_readout` appends a
   pooled row per region per slice; `rollup_animal` groups by `["animal", "region_acronym",
   "hemisphere"]`). Never sum across hemisphere; never plot all three as independent series.
   Figures 1-4 operate on `hemisphere == "both"`; figure 5 is the only one that touches `L`/`R`.

3. **TRAP — per-slice reactivation is NOT in `build_readout`'s output under that name.**
   `creg._row_for` emits `P({m1}+|{m0}+)` and `P({m0}+|{m1}+)` keyed on **marker declaration
   order**, not on resolved roles. M3's `pipeline.yml` declares `markers: [Fos, TdT]`, so
   `m0=Fos, m1=TdT` and the column `P(TdT+|Fos+)` is `Double/Fos` — the *reverse* rate.
   Figure 4 must compute per-slice reactivation as `Double+_count / {roles.tagged}+_count`
   directly from the per-slice counts. **Reading a `P(...)` column would silently plot the wrong
   quantity on M3.** A self-test check pins this (Task 2, check 6).

4. **Backend regression baseline is currently GREEN.** Verified this session:
   `matplotlib.use('pdf')` → `import cockpit_animal` → `get_backend()` still `'pdf'`.
   (`cockpit_animal` imports `k_sweep_readout`, whose `matplotlib.use("Agg")` is correctly guarded
   by `if __name__ == "__main__":` since `bd5d11f`.) matplotlib is **3.11.0** in the `braian` env
   — already installed, no new package is added by this task, so no package-legitimacy gate
   applies.

5. **`results/` is gitignored** (`**/results/` in `.gitignore`, which matches the top-level
   `results/` too). Default `--out-dir` is `results/animal`, so `<out_dir>/figures/*.png` are
   generated-not-committed by construction.

6. **Zero-cell regions are real and already loud.** `_warn_empty_regions` names them on stderr;
   on M3 `STRd` rolls up to 0 anchor cells with an all-NaN metric row (increment 2's
   frontier-coverage caveat). These must be **excluded from every figure with a visible note** —
   never drawn as a zero bar.

7. **The notebook idiom** (`notebooks/02_batch.ipynb`, cell 2): `%matplotlib inline` sits in the
   setup block with an explicit comment that ipykernel in this env does not auto-activate the
   inline backend. `notebooks/03_animal.ipynb` currently imports **no** matplotlib at all — its
   setup cell must gain `%matplotlib inline` + `import matplotlib.pyplot as plt` in the same
   place and the same style.

---

## Design decisions locked here

### D-1 — Colors: the validated palette, used unchanged; **no extension needed**

Already validated with the dataviz skill's `validate_palette.js` (reported by the orchestrator):

| Token | Hex | Role |
|-------|-----|------|
| `COLOR_ABOVE` | `#C0492B` | warm pole — above chance / flagged |
| `COLOR_BELOW` | `#2E5EAA` | cool pole — below chance |
| `COLOR_NEUTRAL` | `#8A8F98` | diverging **midpoint** + low-evidence de-emphasis |

Light mode: ALL CHECKS PASS (lightness band, chroma floor, CVD separation ΔE 20.1 protan /
29.5 tritan vs target ≥8, normal-vision ΔE 28.0, contrast ≥3:1). Dark mode: passes with a
**contrast WARN on `#2E5EAA` (2.74:1)**; relief is required and is satisfied by **direct region
labels on the y-axis** — every figure that uses the cool pole is a horizontal-bar or labeled
scatter form, so no region is identified by color alone. Keep it that way.

`#8A8F98` **FAILS the validator's chroma floor ("reads gray") and that is correct by design.**
That check is scoped to *categorical* palettes where every slot must carry identity; a diverging
**midpoint** is supposed to read neutral. Do not "fix" this into a hue. Recorded here so a future
reader does not.

**No new series color is introduced by this task**, so no re-validation is required. The two
figures that would naively have needed a third hue instead reuse the diverging encoding, which is
strictly better (see D-3, D-4). Text/axis ink is `#333333` and grid is `#8A8F98` at low alpha —
these are neutrals carrying no data identity, outside the series-palette contract.

**Status colors (good/warning/critical) are never reused as a series color.**

### D-2 — Figure 1 display transform: **plot `log2(overlap_above_chance)` on a linear axis**

`overlap_above_chance` is ratio data centered on 1.0: a 0.25× depletion and a 4× enrichment are
equal-magnitude opposites, and a linear axis makes depletion visually invisible (everything below
1.0 is squeezed into a 1.0-wide sliver while enrichment runs to 5×+).

Chosen: **transform for display**, `log2(oac)`, linear axis, bars emanating from **0** (= 1.0×,
chance), x-ticks relabeled as multiples (`0.25×, 0.5×, 1×, 2×, 4×, 8×`), reference line drawn at
0 and **labeled "1.0× (chance)"**.

Rejected: a log-scaled x-axis with `barh`, because bars on a log axis have no honest baseline
(a log axis has no zero, so the bar origin becomes arbitrary). The transform gets the symmetry
without the baseline lie.

This is a **display transform of `overlap_above_chance` only**. It is *not*
`log2_odds_ratio_hc` — that is a different metric with a different 2×2 construction; do not
substitute it. State the transform in the axis label.

Guard: `oac == 0` (D=0 with N,T,A > 0) → `log2` = `-inf`. Non-finite values after the transform go
through the same exclusion path as NaN (D-5).

### D-3 — Figure 2 layout: two panels, **one shared region order, one shared color encoding**

A dual-axis chart (two y-scales on one plot) is **FORBIDDEN** — it is the single worst chart
mistake and the skill names it explicitly. Do not create one under any circumstance.

Left panel: `reactivation_rate` (%) — bar **length** encodes the raw rate.
Right panel: `log2(overlap_above_chance)` — bar length encodes chance-corrected enrichment.
Both panels share the y-axis region order (sorted by enrichment, desc) and share the y tick labels
(right panel's y ticks hidden; regions named once, on the left).

**Both panels use the same diverging color encoding** (colored by enrichment sign). This is the
PVH trap made visual: a region with a huge raw bar rendered in neutral/cool immediately reads as
"high raw rate, not actually enriched" — 69% raw but only 1.4× above chance. One shared legend
("above chance / below chance") for the figure; each panel is a single series so it gets no legend
of its own.

Additionally, each left-panel row carries a small `#k` rank annotation giving that region's rank by
**raw** rate, so a rank inversion is legible without a 20-line spaghetti slope chart. This is a
rank label, not the encoded value — it does not violate "never a number on every bar".

### D-4 — Figure 3 layout: two count panels, shared order, shared de-emphasis

Left: `Double+_count` (or `{roles.tagged}+_count` for a 1-marker project). Right: `N`.
Both on a log x-axis (counts span orders of magnitude; a log axis is honest for counts because they
are plotted as **dots/lollipops from a common left edge**, not as bars — no baseline problem).
Same y region order as figures 1 and 2, by construction (D-6).

Regions with the supporting count below `min_cells` (tunable, default **30**) are drawn in
`COLOR_NEUTRAL` at alpha 0.55 **and keep their label**, plus a footnote naming the rule.
**De-emphasise and label — never silently drop.** Every other region is colored by enrichment sign,
so "4× on 12 cells" is unmistakable: a warm, de-emphasised, tiny-count row.

### D-5 — Unusable regions are excluded with a visible note, never rendered as zero

A region is excluded from a figure when, for that figure's plotted column(s), the value is NaN or
non-finite, **or** the anchor count is 0. Each figure prints the excluded list to stdout **and**
carries a `fig.text` footnote: `N region(s) excluded (all-NaN / zero-count): STRd, … — see
cockpit_regions.coverage_report()`. This is increment 2's frontier-coverage caveat surfacing at
figure level; the exclusion note is the only thing standing between it and a fabricated zero bar.

### D-6 — One shared ranking helper

`_rank_regions(df, top_n)` returns the ordered region list ONCE, and figures 1, 2 and 3 all consume
it. Shared order is guaranteed **by construction**, not by three call sites agreeing. `top_n`
defaults to **20** — the M3 fixture has 275 regions and 138+ is a live y-tick-crowding risk.

### D-7 — Multi-animal: fail loud, do not guess

Every figure function takes `animal: str | None`. `None` + exactly one animal in the frame → that
animal. `None` + multiple animals → **raise `ValueError` naming the available animals and the
`animal=` argument**, matching the module's existing D-2/D-3 fail-loud ethos. Group-level
faceting is deliberately deferred (it edges into comparison, and statistics are out of scope).

### D-8 — Figure 4 must show pooled AND mean-of-slices, distinctly

The pooled animal value is `Σ Double+ / Σ {tagged}+` — **recomputed from sums, taken straight from
the animal long table**, never `np.mean` of the per-slice dots. The plot draws both:

- per-slice dots — `COLOR_NEUTRAL`, alpha 0.6 (raw supporting observations)
- **pooled** — filled `COLOR_ABOVE` diamond, legend `"pooled ΣD/ΣT (reported)"`
- **mean of slices** — hollow `COLOR_BELOW` circle, legend `"mean of slices — NOT reported"`

They differ, and that difference is the point: it is the anti-pseudoreplication rule made visual.

**No error bars, no CI, no p-value, anywhere.** At n=1 an error bar across slices is
pseudoreplication dressed as a CI — precisely what this module exists to prevent.

### D-9 — Figure 5 metric choice must survive `--n-source`

L/R rows have `N = NaN` when `n_source="classifiable"` (per-cell N is pooled-only), which NaNs
every N-dependent metric on L/R. So figure 5 selects the first **N-immune** metric available:
`reactivation_rate` → else `tagging_rate` → else `{anchor}_density`. Points within tolerance in
`COLOR_NEUTRAL`; points with `|L−R| / mean(L,R) > asym_tol` (default **0.25**) in `COLOR_ABOVE`
with a **direct region label** (selective labels only — flagged points, not all points). `y=x`
reference line. Skip the figure with a printed message if fewer than 2 regions have finite paired
L and R values.

### D-10 — 1-marker projects skip pair figures, never crash and never draw empty axes

| Figure | 2-marker | 1-marker (TdT-only) |
|--------|----------|---------------------|
| 1 region ranking | yes | **skip** (no `overlap_above_chance`) |
| 2 raw vs corrected | yes | **skip** |
| 3 evidence guard | yes (`Double+_count`) | **yes** (`{tagged}+_count`) |
| 4 per-slice spread | yes | **skip** |
| 5 L/R symmetry | yes | **yes** (`tagging_rate`) |

A skipped figure is simply **absent from the returned dict** with one printed explanatory line —
never a `Figure` with empty axes, never a NaN wall. Same discipline `add_metrics` already uses for
absent-vs-NaN columns.

---

## Tasks

### Task 1 — Plotting infrastructure + figures 1-3 in `scripts/cockpit_animal.py`

**Files:** `scripts/cockpit_animal.py`

**Action:**

Add a new section to the module, placed after `write_wide_pivots` and before the self-test
section, headed with the module's existing `# ---` banner comment style.

1. **Imports.** In the third-party import block (after `numpy`/`pandas`/`yaml`, **before** the
   `sys.path.insert` + sibling-module block) add:

   ```
   import matplotlib
   if __name__ == "__main__":
       matplotlib.use("Agg")
   import matplotlib.pyplot as plt
   ```

   with a comment mirroring `k_sweep_readout.py` lines 52-60: the headless backend is claimed
   **only** when this file is run as a CLI, because as an imported library it must leave the
   notebook's inline backend alone. Placing the guard before the sibling-module block keeps the
   `matplotlib.use` ahead of the transitive `k_sweep_readout` pyplot import. Also import
   `matplotlib.colors as mcolors` (needed by the self-test's facecolor assertions) and
   `from matplotlib.figure import Figure` for return annotations. Add `# noqa: E402` where the
   existing block already does.

   **Nothing outside that `if __name__ == "__main__":` guard may change the matplotlib backend.**
   This is the `bd5d11f` regression: an unconditional backend switch at import time silently
   blanked every notebook plot.

2. **Palette + style constants** (module level, D-1 table verbatim): `COLOR_ABOVE`, `COLOR_BELOW`,
   `COLOR_NEUTRAL`, `COLOR_INK = "#333333"`, `DEFAULT_TOP_N = 20`, `DEFAULT_MIN_CELLS = 30`,
   `DEFAULT_ASYM_TOL = 0.25`. Document in a comment: validated with the dataviz skill's palette
   validator; the neutral's chroma-floor FAIL is correct for a diverging midpoint and must not be
   "fixed" into a hue.

3. **`_select_animal(df, animal) -> tuple[pd.DataFrame, str]`** — D-7 fail-loud selection.

4. **`_style_axes(ax) -> None`** — recessive chrome, applied by every figure: hide top/right
   spines, remaining spines and tick labels in `COLOR_INK`, `ax.grid(axis=<value axis>,
   color=COLOR_NEUTRAL, alpha=0.25, lw=0.6)`, grid behind the marks (`ax.set_axisbelow(True)`),
   thin marks. No chartjunk, no bounding box.

5. **`_exclude_unusable(df, cols, anchor) -> tuple[pd.DataFrame, list[str]]`** — D-5. Drops rows
   where any of `cols` is non-finite or the anchor count is 0; returns the kept frame plus the
   sorted list of excluded acronyms.

6. **`_footnote(fig, excluded, extra=None) -> None`** — D-5 note text via `fig.text`, in
   `COLOR_INK` at small size, naming the excluded regions and pointing at
   `cockpit_regions.coverage_report()`. Never render the figure without this when exclusions exist.

7. **`_rank_regions(df, top_n) -> list[str]`** — D-6. Sorts by `overlap_above_chance` desc when
   present, else by the first available of `reactivation_rate` / `tagging_rate`; caps at `top_n`.
   The single source of region order for figures 1-3.

8. **`_enrichment_colors(values) -> list[str]`** — maps `log2(oac)` sign to `COLOR_ABOVE` /
   `COLOR_BELOW`, with values within ±0.05 (i.e. ~1.0×) mapped to `COLOR_NEUTRAL`. Shared by
   figures 1, 2 and 3 so the encoding is identical across the set.

9. **`_log2_ratio_axis(ax, values) -> None`** — D-2. Sets x-ticks at integer log2 positions inside
   the data range, relabels them as multiples (`0.25×`, `0.5×`, `1×`, `2×`, `4×`, `8×`), and draws
   the chance reference at 0 as a thin dashed `COLOR_NEUTRAL` line labeled `1.0× (chance)`.

10. **`plot_region_ranking(df, config, roles, animal=None, top_n=DEFAULT_TOP_N) -> Figure`** —
    figure 1 per D-2. Single diverging series → **no legend**; the title names the metric and the
    axis ends are annotated `depleted ←` / `→ enriched`. Horizontal bars, thin, sorted desc,
    `ax.invert_yaxis()` so rank 1 sits on top (matching the 02 notebook's existing idiom).

11. **`plot_raw_vs_corrected(df, config, roles, animal=None, top_n=DEFAULT_TOP_N) -> Figure`** —
    figure 2 per D-3. `plt.subplots(1, 2, sharey=True)`. Left = `reactivation_rate` as %, right =
    `log2(oac)` via `_log2_ratio_axis`. Region labels only on the left. `#k` raw-rank annotation
    per left-panel row. One shared figure-level legend with exactly two entries (above / below
    chance). **Under no circumstance create a second y-axis (`twinx`) on either panel.**

12. **`plot_evidence_guard(df, config, roles, animal=None, top_n=DEFAULT_TOP_N,
    min_cells=DEFAULT_MIN_CELLS) -> Figure`** — figure 3 per D-4. `plt.subplots(1, 2, sharey=True)`;
    horizontal lollipops (thin line + marker) on a log x-axis; left = `Double+_count` (2-marker) or
    `{roles.tagged}+_count` (1-marker), right = `N`. Rows below `min_cells` forced to
    `COLOR_NEUTRAL` at alpha 0.55 and kept labeled; footnote states the `min_cells` rule and names
    the de-emphasised regions.

All three take the **animal long table** (`stack_animals` / `rollup_animal` output) and filter to
`hemisphere == "both"` internally. All three call `_rank_regions` on the same filtered frame, so
their orders match by construction. None of them writes a file; each returns a `Figure`.

Docstrings follow the module's existing style: state the JOB the figure does, the encoding, and
the trap it defends against.

**Verify:**
```
/home/jflab/miniforge3/envs/braian/bin/python3 -u -c "
import matplotlib; matplotlib.use('pdf'); b0=matplotlib.get_backend()
import sys; sys.path.insert(0,'scripts'); import cockpit_animal as ca
assert matplotlib.get_backend()==b0, f'BACKEND CLOBBERED {b0} -> {matplotlib.get_backend()}'
for fn in ('plot_region_ranking','plot_raw_vs_corrected','plot_evidence_guard',
           '_rank_regions','_exclude_unusable','_select_animal','_enrichment_colors'):
    assert hasattr(ca, fn), fn
print('OK backend unchanged + figure-1/2/3 API present')
"
```
plus the existing suite still green:
```
/home/jflab/miniforge3/envs/braian/bin/python3 -u scripts/cockpit_animal.py --self-test
```

**Done:** Figures 1-3 exist as importable functions returning `Figure`; importing the module leaves
the matplotlib backend untouched; the pre-existing self-test still exits 0.

---

### Task 2 — Figures 4-5, the `--plots` CLI flag, and the self-test extension

**Files:** `scripts/cockpit_animal.py`

**Action:**

1. **`plot_slice_spread(df, per_slice, config, roles, animal=None, top_n=8) -> Figure`** —
   figure 4 per D-8. `per_slice` is `creg.build_readout(...)` output.
   **Compute each slice's reactivation as `Double+_count / {roles.tagged}+_count` from the
   per-slice counts** (recon 3 — the `P(...)` columns are keyed on declaration order and are the
   *reverse* rate on M3; using them would silently plot the wrong quantity). Filter `per_slice` to
   `hemisphere == "both"`. One row per region (top `top_n` by the shared ranking, kept small
   because each row carries `n_slices` dots), x = reactivation rate (%). Draw per-slice dots,
   the pooled value **read from the animal long table's `reactivation_rate`**, and the mean of the
   dots, with the three legend entries from D-8. Skip a region whose per-slice `{tagged}+_count`
   sums to 0.

2. **`plot_hemisphere_symmetry(df, config, roles, animal=None, asym_tol=DEFAULT_ASYM_TOL)
   -> Figure`** — figure 5 per D-9. Pivot the long table on `hemisphere` for `L` and `R`, inner
   join on region, drop non-finite pairs, scatter L (x) vs R (y), `y=x` reference across the data
   range in thin dashed `COLOR_NEUTRAL`, equal aspect. Flagged points warm + directly labeled;
   others neutral. Two-entry legend. Title states the QC job: large asymmetry flags registration or
   tissue damage, not biology.

3. **`build_figures(df, config, roles, per_slice=None, animal=None, top_n=DEFAULT_TOP_N,
   min_cells=DEFAULT_MIN_CELLS) -> dict[str, Figure]`** — orchestrator. Keys, in order:
   `region_ranking`, `raw_vs_corrected`, `evidence_guard`, `slice_spread`, `hemisphere_symmetry`.
   Applies D-10: a figure whose inputs are structurally absent (no `overlap_above_chance`; no
   `per_slice`; fewer than 2 finite L/R pairs) is **omitted from the dict** with one printed line
   explaining why. Never returns a `Figure` with empty axes.

4. **`save_figures(figs, out_dir) -> list[Path]`** — writes `Path(out_dir)/"figures"/f"{key}.png"`,
   `dpi=150`, `bbox_inches="tight"`, `facecolor="white"`; `mkdir(parents=True, exist_ok=True)`;
   returns the written paths. `<out_dir>` defaults to `results/animal`, which is gitignored —
   generated PNGs are never committed.

5. **CLI wiring** in `main()`: add `--plots` (store_true), `--top-n` (int, default
   `DEFAULT_TOP_N`), `--min-cells` (int, default `DEFAULT_MIN_CELLS`). When `--plots` is set,
   after the long/wide writes: resolve config+roles for the single selected project, build
   `per_slice` via `creg.build_readout(project, regions=regions)` **only when exactly one
   `--project` was given** (otherwise skip figure 4 with a printed line), call `build_figures` then
   `save_figures`, and print each written path in the module's existing `Wrote … -> …` style.
   Progress printing uses the repo's 0/2/4-space indentation convention.

6. **Extend `_self_test()`** with a `[self-test] interpretation plots` block. Reuse the existing
   synthetic fixtures (`proj2` 2-marker with percell, `proj1` 1-marker) — do not author a second
   fixture. Checks, each through the existing `check(...)` helper:

   1. **Backend unchanged (the `bd5d11f` regression guard).** Run in a **subprocess** (in-process
      the module is already `__main__` and has already claimed Agg):
      `subprocess.run([sys.executable, "-c", code], …)` where `code` does
      `import matplotlib; matplotlib.use("pdf"); b0=matplotlib.get_backend();
      sys.path.insert(0, <scripts dir>); import cockpit_animal;
      assert matplotlib.get_backend()==b0`. Assert `returncode == 0`.
   2. `build_figures` on the 2-marker fixture returns all five keys, every value an instance of
      `matplotlib.figure.Figure`.
   3. Axes counts: `region_ranking` → 1, `raw_vs_corrected` → 2, `evidence_guard` → 2. Assert
      **no axes anywhere has a twin** (`len(ax.get_shared_x_axes().get_siblings(ax))` sanity plus
      `ax.get_figure().axes` count matching the declared panel count) — the dual-axis prohibition,
      enforced not just documented.
   4. **No excluded region is rendered.** Add an all-zero region to the synthetic fixture (or reuse
      the existing zero-count path), then assert its acronym is absent from every figure's y tick
      labels, and that the exclusion footnote text naming it is present in `fig.texts`.
   5. **1-marker path:** `build_figures` on `proj1` returns exactly `{evidence_guard,
      hemisphere_symmetry}` — keys `region_ranking`, `raw_vs_corrected`, `slice_spread` absent —
      and raises nothing.
   6. **Role-correct per-slice reactivation (recon 3).** The synthetic fixture declares Fos first,
      so `Double/Fos != Double/TdT`. Assert figure 4's plotted per-slice values equal
      `Double+_count / TdT+_count` for those slices and **differ** from the declaration-order
      `P(TdT+|Fos+)` column. Read the values back off the axes' collections/lines.
   7. **Pooled marker != mean of dots.** Assert the pooled marker's x differs from
      `np.mean(dots)` by > 1e-6 on the LA fixture, and equals the long table's
      `reactivation_rate` to 1e-9.
   8. **`min_cells` de-emphasis count.** With `min_cells` set above some regions' counts, assert
      the number of marks whose facecolor is `COLOR_NEUTRAL`
      (`mcolors.to_hex(m.get_facecolor(), keep_alpha=False)`) equals the number of below-threshold
      regions — and that those regions are still present in the y tick labels (de-emphasised, not
      dropped).
   9. **`save_figures`** writes one PNG per returned figure under `<tmp>/figures/`, each
      `stat().st_size > 1000`.
   10. **Multi-animal fail-loud (D-7):** `plot_region_ranking(stacked_two_animal_frame, …,
       animal=None)` raises `ValueError` whose message names both animals.

   `plt.close(fig)` every figure after asserting, so the run does not trip matplotlib's
   >20-open-figures warning.

**Verify:**
```
/home/jflab/miniforge3/envs/braian/bin/python3 -u scripts/cockpit_animal.py --self-test
```
must exit 0 with every check PASS, then both real fixtures (READ-ONLY, `--out-dir` outside the
projects):
```
/home/jflab/miniforge3/envs/braian/bin/python3 -u scripts/cockpit_animal.py \
  --project "M3 Hipp1 072326 7scene/M3 Hipp1 072326 7 Scene QuPath" \
  --plots --out-dir results/animal/m3-plots
/home/jflab/miniforge3/envs/braian/bin/python3 -u scripts/cockpit_animal.py \
  --project "wBA/wBA1-2_2-1-tdt-only 072026 project" \
  --plots --out-dir results/animal/wba-tdt-plots
```
The M3 run deliberately omits `--regions` (275 regions) so the `top_n` cap is exercised against
real y-tick crowding. Both must exit 0; M3 must write 5 PNGs, wBA must write 2 and print the skip
lines for `region_ranking` / `raw_vs_corrected` / `slice_spread`.

**Then LOOK at the PNGs.** The palette validator checks color, not layout. `Read` each written PNG
as an image and confirm: no y-tick label collision or clipping, no overlapping direct labels, the
chance line is visible and labeled, the footnote is legible and not running off the canvas, panel
titles are not truncated by `bbox_inches="tight"`. Fix layout (figure height scaled to row count,
`constrained_layout` or `tight_layout`, label truncation for long acronyms) and re-render until
clean. Confirm the M3 `region_ranking` reproduces the project's known result shape — CA1 should
land near the top at roughly 4× (the recorded ~4.2× CA1 enrichment).

**Done:** All five figures implemented; `--plots` works headlessly on both fixtures; self-test
exits 0 including the backend, 1-marker, exclusion, role-correctness and anti-averaging checks;
every rendered PNG has been visually inspected and is free of collisions and clipping.

---

### Task 3 — Thin notebook section in `notebooks/03_animal.ipynb` + commit

**Files:** `notebooks/03_animal.ipynb`

**Action:**

1. **Setup cell (cell 2).** In the import block, immediately before `import numpy as np`, insert
   `%matplotlib inline` with the same explanatory comment `02_batch.ipynb` carries (ipykernel in
   this env does not auto-activate the inline backend, so plots silently render nothing), then
   `import matplotlib.pyplot as plt`. Add `from IPython.display import display` if not already
   implicitly available.

2. **PARAMS.** Add three keys with the surrounding comment style already in the cell:
   `"top_n": 20`, `"min_cells": 30`, `"save_figures": True` — each with a one-line comment saying
   what it does and that figures land in `<out_dir>/figures/` next to the CSV.

3. **New section, after section 4 (Export) and before section 5 (Caveat panel):**
   markdown header `## 5. Interpretation plots &nbsp;<sub>CHEAP</sub>` (renumber the existing
   caveat panel to 6), with prose stating: these are a **pre-analysis interpretation aid, not
   publication figures and not statistics**; every figure is chance-corrected or explicitly labeled
   raw; regions that rolled up to zero are excluded with a note rather than drawn as zero bars; and
   at n=1 no error bar is drawn because an error bar across slices would be pseudoreplication.

4. **One code cell.** THIN — it calls the module and displays, nothing else:

   - resolve `config` / `roles` for the single project
   - `per_slice = creg.build_readout(PROJECTS[0], regions=PARAMS["regions"])` (only when exactly
     one project)
   - `figs = ca.build_figures(combined, config, roles, per_slice=per_slice,
     top_n=PARAMS["top_n"], min_cells=PARAMS["min_cells"])`
   - `if PARAMS["save_figures"]: for p in ca.save_figures(figs, OUT_DIR): print(f"figure -> {p}")`
   - `for name, fig in figs.items(): display(fig); plt.close(fig)` — explicit `display` then
     `close`, so the figure renders exactly once and the inline backend does not flush a duplicate.

   **No plotting logic, no color, no axis handling in the notebook.** All of it lives in
   `cockpit_animal`, matching the locked 01/02 convention.

   Keep the markdown prose free of the literal non-interactive-canvas warning string, so the
   verification check below cannot be self-invalidated by the notebook's own text.

**Verify:**
```
/home/jflab/miniforge3/envs/braian/bin/jupyter nbconvert --to notebook --execute --inplace \
  notebooks/03_animal.ipynb
```
must exit 0. Then assert on the executed notebook's **outputs** (not its source):
```
/home/jflab/miniforge3/envs/braian/bin/python3 -u -c "
import json
d=json.load(open('notebooks/03_animal.ipynb'))
errs=[o for c in d['cells'] for o in c.get('outputs',[]) if o.get('output_type')=='error']
imgs=[o['data']['image/png'] for c in d['cells'] for o in c.get('outputs',[])
      if 'data' in o and 'image/png' in o.get('data',{})]
txt=''.join(t for c in d['cells'] for o in c.get('outputs',[]) for t in o.get('text',[]))
assert not errs, f'{len(errs)} error output(s)'
assert imgs, 'no rendered image outputs'
assert all(len(i)>1000 for i in imgs), 'a rendered image is empty'
assert 'non-interactive' not in txt, 'backend fell back to a non-interactive canvas'
print(f'OK 0 errors, {len(imgs)} non-empty rendered figure(s)')
"
```

Then `git status --short` must show **no** `.png` staged or untracked outside `results/`
(confirming the gitignore path holds), and commit:
`feat(cockpit): interpretation plots for the animal-level readout`.

**Done:** Notebook executes clean end to end with non-empty inline figures, figures also saved next
to the CSV under `<out_dir>/figures/`, no generated PNG is tracked by git, and the work is
committed.

---

## Constraints (apply to every task)

- **`braian` env only**, invoked **directly and unbuffered**:
  `/home/jflab/miniforge3/envs/braian/bin/python3 -u …`. Do **not** use `conda run` — it buffers
  stdout and hides progress. CPU-only; no GPU/CUDA anything.
- **READ-ONLY on all fixture projects.** Never write inside a QuPath project directory; all output
  goes to `--out-dir` (default `results/animal`, gitignored).
- **No new packages.** matplotlib 3.11.0 is already in the env.
- **Config-derived marker names throughout.** No literal `Fos` / `TdT` in plotting code — resolve
  via `config.marker_names` / `roles.tagged` / `roles.activity`.
- **Never sum across `hemisphere`.** `both` is already L+R pooled.
- **Nothing outside `if __name__ == "__main__":` may change the matplotlib backend.**
- **No dual-axis chart. No rainbow. No cycled categorical hues. No number on every bar.**
  Thin marks, recessive grid and axes, selective direct labels, legend only for ≥2 series.
- Repo Python conventions: `from __future__ import annotations` (already present), snake_case,
  `_`-prefixed private helpers, `Path` not `str`, PEP-604 unions, 0/2/4-space print-progress
  indentation, argparse with `RawDescriptionHelpFormatter` + `epilog=__doc__` (already present).
- Every new public function returns a `matplotlib.figure.Figure` (or a dict/list of them) — the
  notebook stays thin.
- Update the module docstring with a short PLOTTING section describing the five figures and the
  D-2 log2 display transform, so the figures' semantics are discoverable from `--help`.

## Out of scope

Statistics of any kind — t-tests, ANOVA, p-values, or error bars that imply inference (at n=1 an
error bar across slices is pseudoreplication dressed as a CI, which is exactly what this module
exists to prevent). brainrender 3D point clouds. Re-running detection, classification or export.
Changing any metric definition. Group-level faceting of the figures.

## Success criteria

- [ ] Five figure functions in `scripts/cockpit_animal.py`, each returning a `Figure`; the
      notebook contains zero plotting logic.
- [ ] Figure 1 is diverging about a labeled `1.0× (chance)` reference, on the D-2 log2 display
      transform, with the justification recorded in the docstring.
- [ ] Figure 2 is two panels sharing one region order and one color encoding — **no dual axis**,
      enforced by a self-test assertion.
- [ ] Figure 3 de-emphasises sub-`min_cells` regions in neutral grey **and keeps them labeled**.
- [ ] Figure 4's pooled marker is the recomputed-from-sums value, visually distinct from the
      mean of the per-slice dots, with per-slice reactivation computed role-correctly (not from a
      declaration-order `P(...)` column).
- [ ] Figure 5 scatters L vs R against `y=x` with flagged asymmetries directly labeled.
- [ ] Zero-cell / all-NaN regions are excluded from every figure with a visible footnote — never a
      zero bar.
- [ ] A 1-marker project returns only figures 3 and 5, with printed skip messages; no crash, no
      empty axes.
- [ ] `--plots` produces figures headlessly on both fixtures; PNGs land in `<out_dir>/figures/`
      alongside the CSV and are not tracked by git.
- [ ] `--self-test` exits 0 including the subprocess backend-unchanged assertion, the axes/series
      counts, the 1-marker skip path, the exclusion check, the role-correctness check and the
      anti-averaging check.
- [ ] Every rendered PNG was `Read` as an image and is free of label collisions, clipping and
      overlap.
- [ ] `jupyter nbconvert --to notebook --execute --inplace notebooks/03_animal.ipynb` exits 0 with
      0 error outputs, non-empty `image/png` outputs, and no non-interactive-canvas fallback.
- [ ] Work committed; `results/` PNGs remain untracked.
