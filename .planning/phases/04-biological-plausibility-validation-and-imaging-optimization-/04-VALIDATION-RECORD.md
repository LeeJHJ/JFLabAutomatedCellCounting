# VAL-01 Bioplausibility Validation Record — M3 Hippocampus Entry 1

**Section:** `M3 Hippocampus 20x 062926 3 plane`, entry 1 (`M3_20x_MIP_Z1-3.ome.tiff`)
**Data source:** Classified `data.qpdata` (Phase 3, human-confirmed 2026-07-16) exported by
`scripts/03_export_val01_metrics.groovy` (Plan 04-01) on 2026-07-17 (operator run, approved at
this plan's Task 1 checkpoint) → `M3 Hippocampus 20x 062926 3 plane/results/val01_percell_export.tsv`
(213,106 cells) and `.../results/val01_region_area.tsv` (450 region-area rows, 285 leaf / 165
non-leaf).
**Metrics computed by:** `scripts/val01_metrics.py` (Plan 04-01), run 2026-07-17 in the `braian`
conda env against the real export TSVs above.
**Register:** Findings record with interpretation, **not** a pass/fail gate (D-01, locked in
`04-CONTEXT.md`). Every metric below is reported with its target band, the measured value, an
in/out-of-range flag, and a written interpretation. Out-of-range values are interpreted, not
treated as failures — the phase completes with these findings recorded regardless of where each
value lands.

**Claim labels (D-06):** `[measured]` = computed directly from this section's real export data
this session; `[inferred]` = reasoned from measured facts plus general/domain knowledge, not
independently re-verified this session; `[ASSUMED]` = carried forward from an earlier phase or
literature recall that could not be confirmed against a directly-quoted primary source (the
seed paper, bioRxiv 2024.09.16.611953 / F1000Research 15:410, returned HTTP 403 again in Phase
4's own research pass — see `04-RESEARCH.md` §"Primary source access status").

---

## Methodology Note: a real bug found and fixed while computing these metrics

Running `scripts/val01_metrics.py` against the real (rather than synthetic-fixture) export TSVs
for the first time surfaced a genuine defect in `compute_density()`: the function joined
per-cell region counts to `val01_region_area.tsv` on the bare `region_label` column, but the
region-area export's `region_label` carries a `"Left: "` / `"Right: "` hemisphere prefix
(e.g. `"Right: CA1"`) while the per-cell export's `region_label` is the bare leaf acronym
(e.g. `"CA1"`) — the join matched **zero rows**, and metric #2 (DAPI density) printed an empty
table on the first run. **[measured, this session]**

**Fix (Rule 1, applied in this task):** `compute_density()` now aggregates leaf-region areas
(`is_leaf == True` rows only, to avoid double-counting area already covered by non-leaf
ancestor annotations) across both hemispheres by `acronym`, then joins per-cell region counts
on `acronym == region_label`. This is a bilateral-sum density (total nuclei for that acronym
across both hemispheres ÷ total leaf-region area for that acronym across both hemispheres),
which is the correct grain for the per-cell export's data (it does not carry a hemisphere
column). The fix was verified by re-running the script end-to-end and spot-checking the
whole-section `grey` aggregate (density 3877.4/mm²) against Phase 2's independently-measured
`root` density (~3866–3900/mm² per hemisphere, `reference/dapi_region_reference.csv`) — the two
land within noise of each other, corroborating the fix is computing a sane bilateral density.

A second, deeper finding surfaced while investigating this (per-cell region-label resolution
appears to under-represent one hemisphere for at least CA1 — see `deferred-items.md` §D-1) is
**not** fixed here: its root cause lives in Phase 3's/Plan 04-01's locked Groovy region-labeling
closures, out of this task's file scope and out of Phase 4's mandate (D-01 excludes re-tuning
detection/classification logic). It is logged and its impact on the density/ratio numbers below
is flagged explicitly where relevant.

---

## 1. Double+/TdT+ ratio

**Target:** 10–40% (10–40% band per `REQUIREMENTS.md`/`04-CONTEXT.md` D-02).

**Measured, whole section [measured]:**

| Convention | n(Double+) | n(TdT+) | Value | Band check |
|---|---|---|---|---|
| Raw ratio `n(Double+)/n(TdT+)` | 3,457 | 4,134 | **0.836** (83.6%) | flagged out of range vs. 10–40% |
| Co-expression fraction `Double+/(Double++TdT+)` | 3,457 | 4,134 | **0.455** (45.5%) | flagged out of range vs. 10–40% |

Both conventions the script prints are reported per the plan's instruction. The
co-expression-fraction convention (0.455) is the one directly comparable to Phase 2's own D-06
advisory measurement and to the phase's ≈0.45 working number cited at this plan's Task 1
checkpoint.

**Per-hippocampal-subfield breakdown [measured]** (the per-cell export carries a `region_label`
column, so subfield decomposition is free; the script prints all 146 populated regions — the
canonical hippocampal subfields are excerpted below, full breakdown reproducible via
`conda run -n braian python3 scripts/val01_metrics.py`):

| Subfield | n(Double+) | n(TdT+) | Raw ratio | Coexpr fraction | Band check (coexpr) |
|---|---|---|---|---|---|
| CA1 | 23 | 55 | 0.418 | **0.295** | **IN RANGE** (10–40%) |
| CA2 | 0 | 6 | 0.000 | 0.000 | below range (n=6, low count) |
| CA3 | 1 | 59 | 0.017 | 0.017 | below range |
| DG-mo | 12 | 107 | 0.112 | **0.101** | **IN RANGE** (borderline, at the 10% floor) |
| DG-po | 0 | 24 | 0.000 | 0.000 | below range |
| DG-sg | 0 | 0 | n/a | n/a | excluded from marker classification (Phase 2 D-05 lock: too dense for per-cell calls) |
| `grey` (broad ancestor bucket, not a hippocampal subfield) | 1,719 | 1,796 | 0.957 | 0.489 | flagged out of range |

**Interpretation (D-02: weigh all four candidates on paper, do not silently pass or fail):**

The most important observation from the per-subfield breakdown is that the two best-resolved,
classically recall-associated hippocampal subfields — **CA1 (0.295) and DG-mo (0.101) — actually
land inside or at the edge of the 10–40% target band** when isolated from the rest of the
section. The whole-section aggregate (0.455) is pulled upward substantially by (a) the `grey`
catch-all bucket, which alone contributes 1,719 of the 3,457 total Double+ cells (49.7%) and
1,796 of 4,134 total TdT+ cells (43.4%) at its own elevated 0.489 coexpr rate, and (b) numerous
small-n cortical/subcortical regions elsewhere in the field of view with noisy high ratios
(e.g. RSPagl2/3 13.0, AUDd2/3 9.0 — single-digit cell counts, not statistically meaningful on
their own). Per the deferred D-1 finding above, `grey` is disproportionately drawn from
whichever hemisphere's leaf-region resolution is incomplete — so a meaningful share of the
"elevated" aggregate ratio is attributable to a data-resolution artifact concentrated outside
the clean hippocampal subfield counts, not to CA1/CA3/DG reactivation biology directly.

Weighing the four D-02 candidates against this evidence:

1. **Strong recall session effect [inferred]** — CA1 landing inside the target band at 29.5% is
   consistent with (not contradicted by) a matched-context, strong-recall session per the
   broader engram literature's context-dependence pattern (`04-RESEARCH.md` §1) — a healthy,
   plausible reactivation rate in the subfield most classically associated with contextual
   recall, without needing to invoke an implausible response.
2. **n=1 sampling [inferred]** — still applies with full force: this is one section, one animal;
   subfield-level counts for CA2 (n(TdT+)=6) and CA3 (n(TdT+)=59, n(Double+)=1) are small enough
   that a single mis-called cell shifts the ratio by several percentage points.
3. **Robust-threshold (k=3) sensitivity [measured methodology-shift data point, see below;
   candidate not independently verified]** — the same globally-derived `median + 3·1.4826·MAD`
   cut (Phase 3 D-05) that classifies TdT+/Fos+ across the whole image is applied uniformly
   regardless of region; a region-agnostic global threshold can inflate or deflate a subfield's
   local positive rate relative to what a region-specific threshold would give. No k=4-vs-k=3
   comparison has been run, so this remains a **candidate, not a verified cause**, exactly as
   `04-RESEARCH.md` §1 flags it.
4. **Hippocampus-specific engram reactivation asymmetry [cited general pattern, inferred
   application to M3]** — the general engram literature documents CA1 showing more
   repeated/promiscuous cFos expression across sessions than DG neurons (`04-RESEARCH.md` §1,
   Nature Communications 2022 and related). This section's own DG-mo (0.101) sitting near the
   band floor while CA1 (0.295) sits mid-band is directionally consistent with that documented
   asymmetry, though it is a two-subfield, single-section comparison and should not be
   over-read.

**Methodology-shift data point [measured]:** Phase 2's own D-06 advisory measurement of this
same ratio (pre-Phase-3-redesign, sigma=2.5, interactive-UI absolute thresholds) was **≈0.40**
— inside the 10–40% advisory band (`02-LOCK-RECORD.md`). The subsequent Phase-3 background-
subtracted + robust-threshold (k=3) redesign shifted the whole-section co-expression fraction to
**0.455** — a real ~5.5-percentage-point shift attributable to a genuine measurement-methodology
change, not biological variation between runs (same section, same underlying detections). This
is direct evidence supporting candidate #3 above: the classification methodology itself is a
non-trivial contributor to where the ratio lands relative to the 10–40% band, on top of whatever
the true biological reactivation rate is.

**Conclusion for this metric:** flagged out of range at the whole-section aggregate level
(0.455 vs. 10–40%), but the two best-resolved hippocampal subfields individually land inside or
at the edge of the target band. The elevated aggregate is attributable to a mix of (a) a
data-resolution artifact in the broad `grey` bucket (D-1, deferred), (b) small-n noise in
peripheral cortical regions, and (c) the documented methodology-sensitivity of the k=3
robust-threshold redesign — with strong-recall biology and hippocampal-subfield asymmetry as
plausible, literature-consistent contributors to the CA1/DG-mo pattern specifically. Per D-01,
this is recorded as a flagged note for the full series, not a blocker.

---

## 2. Per-region DAPI nucleus density

**Target:** 500–2,000/mm².

**Whole-section cross-check [measured]:** the broad `grey` ancestor bucket (95,383 cells /
24.5998 mm², bilateral) reads **3,877.4/mm²** — within noise of Phase 2's independently-measured
`root` density (~3,866–3,900/mm² per hemisphere, `reference/dapi_region_reference.csv`).

**Hippocampal-subfield densities [measured]:**

| Subfield | n_nuclei | area (mm², bilateral) | density/mm² | Band check |
|---|---|---|---|---|
| CA1 | 3,567 | 1.8813 | 1,896.0 | **IN RANGE** |
| CA2 | 263 | 0.1297 | 2,028.2 | flagged out of range (marginal, low n) |
| CA3 | 2,250 | 1.2903 | 1,743.8 | **IN RANGE** |
| DG-mo | 1,402 | 0.9299 | 1,507.7 | **IN RANGE** |
| DG-po | 258 | 0.1104 | 2,336.2 | flagged out of range (marginal, low n) |
| DG-sg | 372 | 0.3621 | 1,027.2 | **IN RANGE** |

Across the full 146-region breakdown the script prints, roughly 60 of 146 regions (41%) land
inside the 500–2,000/mm² band and 86 (59%) read above it — a materially different picture from
Phase 2's own `dapi_region_reference.csv`, in which "nearly all regions... cluster in the
~2,500–5,500/mm² range" (`02-LOCK-RECORD.md`).

**Interpretation — cite the prior Phase-2 finding, do not re-litigate the seed:** Phase 2 already
established and locked the conclusion that both seed ranges (density 500–2,000/mm² and area
50–150 µm², carried forward from the TRAP2 literature as `[ASSUMED]`) are **mis-calibrated for
20× Airyscan MIP DAPI on this instrument**, superseded by the empirical internal per-region
reference (`02-LOCK-RECORD.md`: "both seed ranges... judged mis-calibrated... and superseded by
the empirical internal per-region reference"). This record does not re-derive that verdict; it
is cited as established. The whole-section `grey` cross-check above (3,877.4/mm² vs. Phase 2's
root ~3,866–3,900/mm²) directly corroborates that this section's overall density character is
consistent with Phase 2's prior finding.

The apparent improvement — several hippocampal subfields now landing inside the seed band, where
Phase 2's own per-hemisphere reference showed them well above it (e.g. `Left: CA1` 3,507.6/mm²,
`Right: CA1` 3,282.2/mm² per Phase 2 vs. 1,896.0/mm² bilateral here) — is **not** interpreted as a
genuine density decrease. Per the deferred D-1 finding (this plan's own investigation, logged in
`deferred-items.md`), this section's `CA1`-labeled per-cell count (3,567) is numerically
identical to Phase 2's *Right-hemisphere-only* raw count, suggesting the current bilateral
density figures for hippocampal subfields specifically may be **right-hemisphere-dominated**
(under-counting the left hemisphere's true contribution), which would mechanically deflate the
computed density relative to a true bilateral count. **[measured finding, inferred mechanism]**
This caveat is flagged rather than resolved here (out of this task's scope — the root cause is
in locked Groovy region-labeling code, not in this task's `val01_metrics.py`/record files); it is
logged for the full series in `deferred-items.md` §D-1.

**Conclusion for this metric:** several hippocampal subfields (CA1, CA3, DG-mo, DG-sg) read
inside the 500–2,000/mm² band on this run; CA2 and DG-po read marginally above it (low n).
Roughly 59% of all regions read above the band, consistent with — and explained by — Phase 2's
already-accepted mis-calibration finding for this imaging modality, not a new discrepancy. The
possible hemisphere-resolution artifact (D-1) means the hippocampal-subfield numbers specifically
should be treated as provisional pending confirmation for the full series, not as a precise
measurement of true bilateral density.

---

## 3. Nucleus-area distribution peak

**Target:** 50–150 µm².

**Measured [measured]:** modal 10 µm² bin = **[40.0, 50.0) µm²** (count 45,716 of 213,106 valid
cells — n_valid = n_total, no missing area values). Bin-independent cross-checks: median =
**47.88 µm²**, IQR = [36.61, 65.41] (width 28.80), skew = **1.848** (strongly right-skewed —
consistent with a long tail of larger, possibly partially-merged nuclei, per
`04-RESEARCH.md`'s pitfall note on skewed area distributions).

**Interpretation — accepted Phase-2 sigma=2.5 tradeoff, do not re-litigate:** this is the same
peak bin Phase 2 measured at the locked sigma=2.5 detection config ([40,50), mode ≈45 µm²,
`02-LOCK-RECORD.md` Gate 1), now reproduced independently from the real classified export. Phase
2 already documented and accepted this as a known tradeoff: sigma=3.0 landed the peak inside the
50–150 µm² seed band ([50,60)) but merged/missed larger cortical nuclei; sigma=2.5 was locked as
"compromise" favoring completeness in dense cortical clusters over exact seed-range compliance.
This record does not revisit that tradeoff — it is cited as an already-accepted, principled
decision, consistent with this plan's D-01 scope (re-tuning detection is explicitly out of
scope for Phase 4).

**Geometric sanity check [derived, area↔diameter for a circular cross-section]:** the median
(47.88 µm²) corresponds to a nucleus diameter of ≈7.81 µm; the peak bin midpoint (45 µm²)
corresponds to ≈7.57 µm. Both are modestly smaller than the commonly informally cited ~8–12 µm
mouse pyramidal/granule neuron nuclear diameter — consistent with either genuine biological
nucleus-size variation at this locked sigma, or (per `04-RESEARCH.md`'s pitfall discussion) mild
residual oversegmentation at sigma=2.5 even after the earlier sigma 2.0→2.5 adjustment.

**Conclusion for this metric:** the measured peak ([40,50), median 47.88 µm²) is marginally below
the 50–150 µm² seed lower bound, reproducing Phase 2's own finding on the same classified data.
Per D-01, this is a known, already-accepted tradeoff (not a new finding requiring action), flagged
as a note rather than a blocker.

---

## 4. Fos+ rate on a negative-control region

**Target:** 1–3%, or absence documented (VAL-01's explicit allowance).

**Negative-control absence [measured/documented]:** this is a hippocampus-only field of view with
no clean unstimulated or secondary-antibody-only negative-control region present in the section.
Per `04-CONTEXT.md`'s Claude's-Discretion allowance, this absence is documented rather than
worked around with a substitute region pretending to be a true control.

**SSp corroboration anchor [measured]:** n = 9,324 SSp-labeled cells (region_label starting
`SSp`, spanning `SSp-bfd`/`SSp-tr`/`SSp-un`/`SSp-ll`/`SSp-ul` layers), Fos+ (Fos+ and Double+
combined) = 4,393, rate = **0.471** (47.1%) — flagged out of range vs. the 1–3% target, and
notably more than double the whole-section Fos-expressing rate (20.1% — see below).

**Fiber-tract soft anchor [measured]:** n = 3,200 cells in fiber-tract-labeled regions (`fiber
tracts`, `cc`, `fx`, `or`, `ec`, `em`), Fos+ = 377, rate = **0.118** (11.8%) — also above the
1–3% target, but well below both SSp (47.1%) and the whole-section average (20.1%), consistent
with fiber tracts carrying largely non-neuronal, sparsely Fos-competent cells.

**Whole-section reference [measured]:** total classified cells 213,106 — Negative 163,967, Fos+
39,424, TdT+ 4,134, Double+ 3,457, Excluded (DG-sg/VS per Phase 2 lock) 2,124. Fos-expressing
(Fos+ + Double+) = 42,881/213,106 = **20.1%**.

**Interpretation:** SSp is explicitly *not* a true negative control (it was never designated as
such — it is somatosensory cortex, which can carry genuine Fos+ activity from ordinary sensory
experience during a TRAP2 recall/exploration session). This plan's Task 1 checkpoint carried
forward a qualitative Phase-3 attestation that SSp was "suppressed" post-fix; that qualitative
claim referred to the elimination of the specific pre-Phase-3 artifact documented in
`02-LOCK-RECORD.md` — under the *old*, global absolute Fos threshold (13,000.45), SSp's median
nuclear-488 intensity (15,072) itself exceeded the cutoff, driving a >50% false-positive rate
purely from regional autofluorescence. The Phase-3 background-subtracted, self-calibrated
robust-threshold (k=3) redesign was built specifically to remove that artifact, and did — SSp is
no longer being flagged by a threshold its own uncorrected autofluorescence exceeds by
construction.

This session's direct re-measurement shows SSp's rate under the *corrected* pipeline is still
elevated (47.1%) — well above the whole-section average (20.1%) and far above the 1–3% seed.
Two non-exclusive candidates, consistent with the D-02 threshold-sensitivity discussion above:
(a) **genuine regional sensory activation [inferred]** — SSp is real cortex that plausibly
experienced real tactile/sensory input during the behavioral session, so an elevated (if not
1–3%-range) rate is not on its face implausible for a region that was never meant to be a
negative control; (b) **residual global-threshold sensitivity [candidate, not verified]** — the
same region-agnostic k=3 robust cut discussed under metric #1 could still read SSp as
elevated relative to a hypothetical region-specific baseline, even after the local-background
subtraction removed the specific old autofluorescence artifact. Distinguishing these two
candidates would require either a true unstimulated control section or a region-specific
threshold comparison — both explicitly out of this plan's scope (D-01).

The fiber-tract anchor (11.8%), while still above the 1–3% seed, is meaningfully closer to it and
well below both SSp and the whole-section average — a soft, partial corroboration that the
classifier differentiates tissue types in the expected direction (sparse, largely non-neuronal
tissue reading lower than gray matter), even though it does not reach the seed's absolute range.

**Conclusion for this metric:** no true negative control exists in this section (documented, per
VAL-01's explicit allowance). SSp corroboration reads 47.1% Fos+ — flagged out of range against
the 1–3% seed and higher than this record's Task-1-checkpoint working assumption of "suppressed."
This measured, real number is reported as-is rather than reconciled toward the qualitative prior
attestation; the two are not in conflict once "suppressed" is read as "no longer driven by the
specific pre-fix autofluorescence artifact" rather than "reads near baseline." The fiber-tract
anchor (11.8%) offers softer, partial corroboration in the expected direction. Flagged as a note
for the full series — a true negative-control tissue (if one becomes available) would resolve
the ambiguity between the two candidate explanations above.

---

## Closing statement (D-01)

Per D-01, Phase 4's VAL-01 validation is a findings record with interpretation, not a hard
pass/fail gate. All four metrics above carry a measured value and a written interpretation; three
of four are flagged out of range at the whole-section aggregate level (ratio, density, Fos+
control), and the fourth (nucleus-area peak) is marginally below its band. **The phase completes
with these findings recorded as written.** None of the out-of-range values are treated as a
failure requiring rework: each is interpreted against n=1 sampling, prior Phase-2 findings, known
methodology tradeoffs, or documented data-resolution caveats (see `deferred-items.md`), and
becomes a flagged note carried forward to the full series (SERIES-01/02), not a blocker to this
phase's completion.
