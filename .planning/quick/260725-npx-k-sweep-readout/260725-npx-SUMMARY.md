---
phase: quick-260725-npx
plan: 01
subsystem: analysis-tooling
tags: [k-sweep, robust-threshold, TdT, Fos, region-readout, read-only-cli]
dependency-graph:
  requires: [scripts/02_detect_classify.groovy (robust-cut source of truth, read-only), pipeline.yml (marker set / k_robust / anchor)]
  provides: [scripts/k_sweep_readout.py]
  affects: []
tech-stack:
  added: []
  patterns: [exact-reproduction of a Groovy robust-cut in numpy, marker-agnostic per-<marker>_bgsub iteration (D-04 idiom), --self-test synthetic-data gate before any real-data path]
key-files:
  created:
    - scripts/k_sweep_readout.py
  modified: []
decisions:
  - "Task 1/Task 2 split preserved as two atomic commits: Task 1 shipped the full engine/CLI/self-test with --out/--figure argparse accepted but bodies raising NotImplementedError; Task 2 filled in the two bodies without touching any Task 1 math."
  - "Region-level threshold is always the SECTION-level threshold (derived from the whole section's classifiable population per marker), applied to the region subset -- never re-derived per region. Matches the validated prototype and the plan's explicit contract."
  - "Figure plots exactly one marker (first pipeline.yml-declared marker actually present in the data) to keep --figure config-lite; prints a note when >1 marker is present."
metrics:
  duration: ~18min
  completed: 2026-07-25
status: complete
---

# Phase quick-260725-npx Plan 01: k-Sweep Readout CLI Summary

Generalized the validated exploratory prototype (`PROTOTYPE_ksweep_laba.py`) into a committed,
marker-agnostic, read-only CLI (`scripts/k_sweep_readout.py`) that reports TdT+/marker+ counts
across a swept k_robust range (lenient k=2 to strict k=3+) per section and per amygdala region
group, reproducing `02_detect_classify.groovy`'s robust cut cell-for-cell.

## What Was Built

`scripts/k_sweep_readout.py` — a standalone CLI (numpy/pandas/matplotlib/pyyaml, all already in
the `braian` env) that:

- Globs `*__percell_export.tsv` under `--results-dir`, derives each section's label from the
  filename (`basename.split(" - ")[-1].split("__")[0]`), and loads the per-cell TSV with pandas.
- Reproduces the exact robust-cut math from `02_detect_classify.groovy` (lines ~416-472):
  `threshold(k) = median(bgsub) + k * 1.4826 * MAD(bgsub)` (numpy's linear-interpolated median,
  matching Groovy's even-n `0.5*(a+b)`), positive iff `bgsub >= threshold` (`>=`, matching
  Groovy's `values.count { it >= threshold }`).
- Derives the classifiable population (used for BOTH threshold derivation AND every count) as
  rows with `class != "Excluded"` AND finite `<marker>_bgsub`, PER SECTION PER MARKER, reading
  exclusion from the already-written `class` column (never re-derived from region acronyms).
- Reads `pipeline.yml` for the declared non-anchor marker set, the anchor (DAPI) name, and
  `k_robust` — iterates whichever markers are actually present as a `<marker>_bgsub` column in a
  given section's export (D-01/D-04 marker-agnostic; skips-with-note on a section missing a
  declared marker).
- Builds a k-set from `--k-min/--k-max/--k-step` or an explicit `--k-values` list, always unioning
  in `pipeline.yml`'s `k_robust` and marking it `*current*`.
- Prints a section-level readout (median, robust_sd, threshold/count/%-of-classifiable at each k)
  and, when `--regions "LA,BLA,BMA"` (optionally `--amygdala-groups` to expand built-in amygdala
  nucleus groups) is given, a region-level readout (anchor denominator = classifiable-for-marker
  count in the region, marker+ count and % of anchor at each k) — an absent region reports 0 for
  every field, never an error.
- `--out <csv>` writes a tidy `section,region,marker,k,threshold,count,pct` table (whole-section
  rows use `region="__section__"`; region-group rows use the group name).
- `--figure <path.png>` writes a two-panel grouped-bar PNG (marker+ count; marker+ as % of
  anchor), bar height at the middle k of the swept set, whiskers spanning strict↔lenient k;
  requires `--regions`, exits cleanly with a usage error otherwise.
- `--self-test` runs entirely on synthetic per-cell TSVs (no real project needed) and proves five
  contracts before any real-data code path is touched.

## Verification

- `--self-test`: exit 0, all five proofs pass —
  (a) `robust_threshold == median + k*1.4826*MAD` against an independent calculation;
  (b) counts monotonically non-increasing as k increases;
  (c) injecting extra high-bgsub `Excluded` rows changes neither the derived median/MAD nor any
      count;
  (d) a present region reproduces a manual boolean-mask count, an absent region reports 0 with no
      exception;
  (e) the engine runs identically on a 1-marker (TdT-only) and a 2-marker (Fos+TdT) synthetic set.
- `--help`: renders the docstring epilog, exit 0.
- Real-data reproduction (bonus, present on disk): ran against
  `wBA/wBA1-2_2-1-tdt-only 072026 project/results` at `k=3.0` — section-level TdT+ counts
  reproduced the real QuPath classifier cell-for-cell: s1=9500, s2=9029, s3=8742, s4=9459,
  s5=8180. The `--out` tidy CSV round-trip was independently re-checked (`s1 TdT k=3.0 count =
  9500 -> REPRODUCTION OK`).
- `--figure` end-to-end smoke test on the same real project with `--regions "LA,BLA,BMA"
  --amygdala-groups`: wrote a 72 KB two-panel PNG; region-absent sections (s3/s5, which have no
  amygdala tissue in this series) correctly reported anchor=0 / count=0 / 0.0% at every k with no
  crash.
- `--figure` without `--regions`: exits with a clear `--figure requires --regions` usage error
  (exit code 2), not a stack trace.
- Additive-only: `git status` / `git diff --stat` confirm `scripts/02_detect_classify.groovy` and
  `pipeline.yml` are byte-unchanged across both commits; only `scripts/k_sweep_readout.py` was
  added/modified.

## Deviations from Plan

None — plan executed exactly as written, including the Task 1 (engine/CLI/self-test, `--out`/
`--figure` stubbed) → Task 2 (fill in `--out`/`--figure` bodies) commit boundary.

## Commits

- `5ee7510` — feat(quick-260725-npx): k-sweep exact-reproduction engine + CLI + section/region
  readouts + self-test
- `46f3262` — feat(quick-260725-npx): tidy CSV export (--out), grouped-bar figure (--figure),
  real-data reproduction

## Known Stubs

None. Both `--out` and `--figure` are fully implemented; no placeholder/mock data paths remain.

## Threat Flags

None. This tool only reads local per-cell TSVs already produced by the existing pipeline
(no network, no auth, no new write path into pipeline.yml/BraiAn.yml/QuPath project state);
matches the plan's `<threat_model>` exactly (T-quick-01/02/SC — all pre-declared, no new surface
introduced).

## Self-Check: PASSED

- FOUND: `scripts/k_sweep_readout.py`
- FOUND: commit `5ee7510`
- FOUND: commit `46f3262`
