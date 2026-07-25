---
phase: quick-260725-npx
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - scripts/k_sweep_readout.py
autonomous: true
requirements: [KSWEEP-01]
must_haves:
  truths:
    - "Operator sees TdT+/marker+ counts across a swept k range (lenient k-min → strict k-max) per section, not a single k."
    - "Reported counts EXACTLY reproduce the real QuPath classifier: k=3.0 TdT+ = 9500 on wBA1-2_2-1 s1 (validated by PROTOTYPE_ksweep_laba.py)."
    - "Marker-agnostic: runs on a 1-marker (TdT-only) and a 2-marker (Fos+TdT) declared set (D-04/D-01); anchor/DAPI is the denominator, never a swept marker."
    - "Optional region-level readout (LA/BLA/BMA amygdala groups) reports anchor + marker+ counts per section; a region absent in a section reports 0, never errors."
    - "Tool is READ-ONLY: it globs exported TSVs and never re-runs QuPath, never touches pipeline.yml / 02_detect_classify.groovy / any image."
  artifacts:
    - scripts/k_sweep_readout.py
  key_links:
    - "threshold(k) = median(bgsub) + k*1.4826*MAD(bgsub), median linear-interpolated (numpy default), MAD = median(|x-median|) — matches Groovy medianOf/madOf/robustThreshold."
    - "positive iff bgsub >= threshold(k) (>=, matching Groovy `values.count { it >= threshold }`)."
    - "derivation/count population = detections with class != 'Excluded' AND finite (non-NaN, non-blank) <marker>_bgsub; threshold derived PER SECTION PER MARKER."
    - "region acronym = region_label.split(': ')[-1] if ': ' in region_label else region_label (handles both 'Left: LA' and bare 'LA')."
    - "k set always includes pipeline.yml k_robust, marked as the current setting."
---

<objective>
Create `scripts/k_sweep_readout.py` — a committed, marker-agnostic CLI that reads a QuPath
project's exported per-cell TSVs and reports TdT+/marker+ counts across a swept range of
k_robust values (the robust-cut multiplier), so the operator sees the detection RANGE
(k=2 lenient → k=3 strict) rather than a single k. It formalizes the validated exploratory
prototype (`PROTOTYPE_ksweep_laba.py`) into a reusable tool.

The tool must EXACTLY reproduce `scripts/02_detect_classify.groovy`'s robust cut: the
prototype already proved this (k=3 reproduced the real classifier's TdT+ counts
9500/9029/8742/9459/8180 cell-for-cell). Preserve that exactness.

Purpose: give the operator a self-calibration/tuning readout of the detection range without
re-running the pipeline; marker-agnostic per D-04/D-01 so it works on TdT-only or Fos+TdT sets.
Output: `scripts/k_sweep_readout.py` (additive; read-only analysis tool).
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/quick/260725-npx-k-sweep-readout/PROTOTYPE_ksweep_laba.py
@scripts/val01_metrics.py
@scripts/build_dapi_reference.py
@pipeline.yml

# Source of truth for the robust cut (already read into planning — do NOT re-read the whole file):
#   scripts/02_detect_classify.groovy lines ~416-472: isExcluded, medianOf, madOf,
#   robustThreshold (med + k*1.4826*MAD), positiveFraction (count { it >= threshold }).
# Real-data results (present on disk, used by the Task 2 bonus check):
#   "wBA/wBA1-2_2-1-tdt-only 072026 project/results/*__percell_export.tsv"
# Per-cell TSV schema (confirmed): columns = class, region_label, nucleus_area_um2,
#   centroid_x_px, centroid_y_px, <marker>_bgsub (e.g. TdT_bgsub). class values include
#   Excluded/Negative/TdT+ (and Fos+/Double+ on a 2-marker set). region_label here is a
#   bare acronym (e.g. VISp1) but MAY carry a "Left: "/"Right: " prefix in other exports.
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Core exact-reproduction k-sweep engine + CLI + section/region readouts + self-test</name>
  <files>scripts/k_sweep_readout.py</files>
  <behavior>
    Robust-cut math (the exact-reproduction contract — must match Groovy medianOf/madOf/robustThreshold):
    - median([1,2,3,4]) == 2.5 (numpy default linear interpolation, matching Groovy medianOf even-n 0.5*(a+b)).
    - mad(x) == median(|x - median(x)|); robust_sd == 1.4826*mad.
    - threshold(x, k) == median(x) + k*1.4826*mad(x), exactly.
    - positive count at k == count of (bgsub >= threshold(x, k)) — uses >=, not >.
    - As k increases (2.0 → 3.0), positive count is monotonically NON-INCREASING.
    Population/exclusion:
    - classifiable (derivation AND count population) = rows with class != "Excluded" AND finite <marker>_bgsub (non-NaN, non-blank). Excluded cells removed from BOTH threshold derivation AND every count.
    - threshold derived PER SECTION PER MARKER on that section's classifiable bgsub; applied to that section's cells.
    Marker-agnostic:
    - iterate the declared non-anchor markers from pipeline.yml; anchor (DAPI) is the denominator, never swept. Runs identically on a 1-marker and 2-marker declared set.
    Region readout:
    - acronym = region_label.split(": ")[-1] if ": " in region_label else region_label.
    - a requested region absent in a section yields count 0 (no error/crash).
  </behavior>
  <action>
Create `scripts/k_sweep_readout.py`, a standalone read-only CLI following the project idiom in
`val01_metrics.py`/`build_dapi_reference.py`: `from __future__ import annotations`; argparse with
`formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__`; a module docstring with a
"Usage (from the Analysis root, braian env)" block; `Path` objects; snake_case functions with
`_`-prefixed helpers; print-progress ("Step..." top-level, 2-space sub-steps); `def main()` + `if
__name__ == "__main__": main()`. Use numpy + pandas + matplotlib(Agg) + pyyaml (all in the braian env).

Implement the EXACT-reproduction robust cut (replicate `02_detect_classify.groovy` lines ~416-472
verbatim in numpy — this is the source of truth, do NOT invent a variant):
  - `robust_threshold(values, k)` returns `np.median(values) + k * 1.4826 * mad` where
    `mad = np.median(np.abs(values - np.median(values)))`. numpy's default median is linear-
    interpolated, matching Groovy medianOf's even-n `0.5*(a+b)`. Positive test uses `bgsub >= threshold`
    (matching Groovy `values.count { it >= threshold }`). Also expose `median` and `robust_sd`
    (=1.4826*mad) for the tuning readout.
  - The classifiable population (used for BOTH threshold derivation AND counts) = rows with
    `class != "Excluded"` AND finite `<marker>_bgsub`. The per-cell `class` column already carries
    "Excluded" for cells in exclude_acronyms regions (written by 02_detect_classify.groovy), so
    exclusion is read from the class column — do NOT re-derive it from region acronyms. This mirrors
    the validated prototype's `keep = (cls != "Excluded") & ~np.isnan(bg)`.
  - Derive the threshold PER SECTION PER MARKER on that section's classifiable bgsub; apply to that
    section's cells.

`--results-dir <dir>` (required): glob `*__percell_export.tsv`, one per section (sorted). Derive each
section label from the filename exactly as the prototype: `basename.split(" - ")[-1].split("__")[0]`
(e.g. `wBA1-2_2-1_s1`). Load each TSV with pandas; coerce every `<marker>_bgsub` column with
`pd.to_numeric(errors="coerce")`; parse the region acronym as
`region_label.split(": ")[-1] if ": " in region_label else region_label` (handles both a
"Left: <acronym>"/"Right: <acronym>" prefix and a bare acronym).

`--pipeline <pipeline.yml>` (default `pipeline.yml`): read via `yaml.safe_load`. Extract the declared
non-anchor marker names (`markers[].name`) and `k_robust` (the default sweep center), and the
`anchor.name` (the DAPI denominator). Marker-agnostic per D-04/D-01: iterate the declared markers;
never assume a fixed Fos/TdT pair. For each section only sweep markers whose `<marker>_bgsub` column
is actually present in that TSV (skip-with-note otherwise, per the val01_metrics D-04 idiom).

k range: `--k-min` (default 2.0), `--k-max` (default 3.0), `--k-step` (default 0.25) OR
`--k-values "2.0,2.5,3.0"` (explicit list overrides the min/max/step range). ALWAYS union the
pipeline.yml `k_robust` into the printed k set and mark it as the current setting (e.g. a "*current*"
annotation in the header/legend). Sort the k set ascending; de-duplicate to a stable float tolerance.

Section-level readout (always printed): per section, per marker — print `median`, `robust_sd` (tuning
aids), and at each k: `threshold`, positive `count`, and `% of classifiable`. Use a fixed-width
tabular print like the prototype's section block.

Region-level readout (only when `--regions` given): `--regions "LA,BLA,BMA"` is a comma list of
tokens. With `--amygdala-groups`, a token that matches a built-in amygdala group key expands to its
acronym set: LA={LA}, BLA={BLA,BLAa,BLAp,BLAv}, BMA={BMA,BMAa,BMAp} (LA is the amygdala nucleus, NOT
"LAT" thalamus). Without `--amygdala-groups`, or for a token not in the built-in map, treat the token
as an exact acronym (its own singleton group). Per (region-group, marker, section): L+R summed by
acronym (the default; `region_label.split(": ")[-1]` already collapses hemisphere prefixes to the
bare acronym) — report the anchor(DAPI) denominator = count of classifiable-for-that-marker cells in
the region, the marker+ count at each k, and % of anchor. A region absent from a section reports 0 for
every field and MUST NOT raise. (This is the prototype's LA/BA block, generalized per marker.)

Include stub hooks for `--figure` and `--out` argparse options here (accept the args) but leave their
bodies for Task 2 — do not implement figure/CSV writing in this task.

Wire `--self-test` as an early-return branch in `main()` (before any results-dir read), following the
`build_dapi_reference.py` `_self_test()` idiom (tempfile synthetic inputs, plain `assert`s, a final
"self-test PASSED" line). The self-test must prove, on SYNTHETIC per-cell arrays with a known bg-sub
distribution and known Excluded cells:
  (a) threshold(k) == median + k*1.4826*MAD exactly (assert against an independently computed value);
  (b) positive count is monotonically non-increasing as k increases across the swept set;
  (c) Excluded cells are removed from BOTH the derivation population AND the counts (build a synthetic
      set where injecting extra high-bgsub Excluded cells does not change any threshold or count);
  (d) region filtering works and an absent region → 0 (request a region acronym not present → count 0,
      no exception); and separately assert a present region returns the expected in-region count;
  (e) marker-agnostic: run the same engine on a 1-marker synthetic set AND a 2-marker synthetic set,
      asserting both produce per-marker thresholds/counts.
Build the synthetic per-cell data as small pandas DataFrames (or write temp TSVs with the real schema:
class, region_label, nucleus_area_um2, centroid_x_px, centroid_y_px, <marker>_bgsub) so the load path
is exercised too. Keep synthetic bgsub distributions fixed/seeded so the assertions are deterministic.

Constraints: CPU-only; no new deps; additive only — do NOT modify 02_detect_classify.groovy,
pipeline.yml, or any existing script. No deploy copies (runs from the Analysis root like
val01_metrics.py). Never read any image/CZI.
  </action>
  <verify>
    <automated>PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 scripts/k_sweep_readout.py --self-test; echo "exit=$?"; PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 scripts/k_sweep_readout.py --help >/dev/null && echo "help-ok"</automated>
  </verify>
  <done>`--self-test` exits 0 with all five proofs (a)-(e) printing PASS/asserting cleanly; `--help` renders the docstring epilog and exits 0. Section-level and region-level readouts are implemented; `--figure`/`--out` args are accepted (bodies stubbed for Task 2). No existing file modified.</done>
</task>

<task type="auto">
  <name>Task 2: Tidy CSV export (--out), grouped-bar figure (--figure), and real-data reproduction check</name>
  <files>scripts/k_sweep_readout.py</files>
  <action>
Implement the two output bodies stubbed in Task 1.

`--out <csv>`: write the long/tidy k-sweep table with columns
`section,region,marker,k,threshold,count,pct` — one row per (section × region × marker × k). Use the
literal `__section__` (or `ALL`) as the `region` value for the section-level (whole-section) rows so
section-level and region-level rows coexist in one tidy file for downstream use. Create parent dirs
(`args.out.parent.mkdir(parents=True, exist_ok=True)`), write via pandas `to_csv(index=False)`, and
print `wrote -> <path>`.

`--figure <path.png>`: reproduce the prototype's figure, cleaned up. matplotlib Agg backend
(`matplotlib.use("Agg")` at import, before pyplot). Two panels: (A) marker+ count, (B) marker+ as % of
anchor(DAPI). Grouped bars across sections for the requested `--regions` groups; bar height = count at
the MIDDLE k of the swept set; lower/upper whiskers span the extremes — strict end (largest k, fewest
positives) to lenient end (smallest k, most positives) — via asymmetric `yerr`. Title notes
"bar = k{mid}, whiskers = k{max}↔k{min}". Save with `fig.savefig(path, dpi=130, bbox_inches="tight")`
and print `figure -> <path>`. `--figure` requires `--regions`; if `--figure` is given without
`--regions`, exit with a clear message. Keep the figure code marker-aware but simple (one figure per
run; if multiple markers are declared, plot the first declared non-anchor marker, or add a small note —
keep it config-lite, do not overbuild).

Both `--out` and `--figure` remain OPTIONAL and read-only; when neither is given the tool only prints
the readouts. Do NOT change any Task 1 math.
  </action>
  <verify>
    <automated>cd "/home/jflab/Analysis" && PYTHONUNBUFFERED=1 /home/jflab/miniforge3/envs/braian/bin/python3 scripts/k_sweep_readout.py --results-dir "wBA/wBA1-2_2-1-tdt-only 072026 project/results" --k-values "3.0" --out /tmp/claude-1000/-home-jflab-Analysis/4f0301c6-cbad-4800-9eab-65bc51f40852/scratchpad/ksweep_check.csv >/dev/null && /home/jflab/miniforge3/envs/braian/bin/python3 -c "import pandas as pd; d=pd.read_csv('/tmp/claude-1000/-home-jflab-Analysis/4f0301c6-cbad-4800-9eab-65bc51f40852/scratchpad/ksweep_check.csv'); r=d[(d.section=='wBA1-2_2-1_s1')&(d.marker=='TdT')&(d.k==3.0)&(d.region.isin(['__section__','ALL']))]; c=int(r['count'].iloc[0]); print('s1 TdT k=3.0 count =', c); assert c==9500, f'expected 9500, got {c}'; print('REPRODUCTION OK')"</automated>
  </verify>
  <done>`--out` writes a tidy `section,region,marker,k,threshold,count,pct` CSV; the real wBA1-2_2-1 run reproduces the prototype's section-level count (s1 TdT+ at k=3.0 == 9500). `--figure` writes a two-panel grouped-bar PNG (count + %-of-anchor) with mid-k bars and k-range whiskers. `--self-test` still exits 0.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| local TSV files → parser | Operator-exported per-cell TSVs are the only untrusted input; parsed with pandas. No network, no auth, no code execution. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-quick-01 | Tampering | per-cell TSV parse | low | mitigate | fail-loud on missing required columns / empty results-dir; coerce numerics with `errors="coerce"`; absent region → 0 not crash. |
| T-quick-02 | Denial of Service | large TSV read | low | accept | TSVs are ~10 MB (200k rows); pandas handles in seconds; tool never touches the 33 GB CZI or any image (read-only, TSV-only). |
| T-quick-SC | Tampering | dependencies | low | accept | No package installs — numpy/pandas/matplotlib/pyyaml already in the braian env; additive tool adds no deps. |
</threat_model>

<verification>
- `--self-test` exits 0 with proofs (a)-(e) — the GATE (synthetic data, no real project needed).
- `--help` renders and exits 0.
- Bonus (data present on disk now): real wBA1-2_2-1 run reproduces s1 TdT+ @ k=3.0 == 9500.
- Additive-only: `git status` shows only `scripts/k_sweep_readout.py` added; 02_detect_classify.groovy / pipeline.yml unchanged.
</verification>

<success_criteria>
- `scripts/k_sweep_readout.py` exists, is read-only, marker-agnostic, and reproduces the QuPath robust cut exactly (validated by both the synthetic self-test and the 9500 real-data check).
- Section-level and region-level (amygdala-group) readouts print counts/%/threshold across the swept k set, with pipeline.yml k_robust marked as current.
- Optional `--out` (tidy CSV) and `--figure` (two-panel grouped bar) work; both optional and read-only.
</success_criteria>

<output>
Create `.planning/quick/260725-npx-k-sweep-readout/260725-npx-SUMMARY.md` when done.
</output>
