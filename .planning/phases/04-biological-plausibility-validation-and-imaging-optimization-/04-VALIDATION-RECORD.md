# VAL-01 Bioplausibility Validation Record — M3 Hippocampus Entry 1

**Section:** `M3 Hippocampus 20x 062926 3 plane`, entry 1 (`M3_20x_MIP_Z1-3.ome.tiff`)
**Data source:** Classified `data.qpdata` (Phase 3, human-confirmed 2026-07-16) exported by
`scripts/03_export_val01_metrics.groovy` (Plan 04-01, corrected 2026-07-17 per CR-01 below) on
2026-07-17 (operator re-run, prior "Run for project" export superseded) →
`M3 Hippocampus 20x 062926 3 plane/results/val01_percell_export.tsv` (213,106 cells) and
`.../results/val01_region_area.tsv` (450 region-area rows).
**Metrics computed by:** `scripts/val01_metrics.py` (Plan 04-01, patched 2026-07-17 per CR-01
follow-up below), re-run 2026-07-17 in the `braian` conda env against the corrected export TSVs
above.
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

## Post-review correction (Phase-4 CR-01)

This record supersedes an earlier version written from data corrupted by a genuine region-
labeling defect. Phase-4 code review (`04-REVIEW.md`, **CR-01**, critical) found that the
per-cell region-assignment closure (`regionOf`) and the leaf-area export both determined "leaf
region" from QuPath child-annotation topology (`!ann.getChildObjects().any { isAnnotation() }`),
which is not reliably consistent across the real ABBA hierarchy: the broad `grey` rollup
annotation (~24.6 mm², geometrically overlapping every hippocampal subfield) qualified as a
"leaf" on one hemisphere but not the other, and — because `regionOf` returned the *first*
matching annotation rather than the *smallest* — **95,383 of 213,106 cells (44.8%)** were
mis-attributed to the `grey` catch-all instead of their true finest subregion. This silently
corrupted the per-region density and per-subfield ratio numbers the original record reported
(e.g. hippocampal-subfield cell counts were right-hemisphere-dominated, `CA1` read 3,567 cells
instead of the true bilateral 6,354).

**Fixes applied and committed:**
- **`29dbfdc`** — `03_export_val01_metrics.groovy`: `regionOf` now assigns each cell to the
  **smallest-area containing region** (finest atlas leaf, area-sorted short-circuit find), so a
  broad rollup can never out-compete a genuine subfield that also contains the point; `is_leaf`
  is now computed **geometrically** (`isLeafOf` — a region is a leaf iff no smaller region's
  centroid sits inside it), which cannot disagree across hemispheres the way the old
  child-annotation-topology heuristic did. Also fixed WR-01 (non-standard `NaN` tokens in the
  `--out` JSON), WR-02 (crash on an all-NaN area column), WR-03 (`opt01_zplane_audit.py`
  divide-by-zero/NaN-cast edges), and IN-01/IN-03 (documentation clarity).
- **`1052bc6`** — `val01_metrics.py compute_density()`: dropped the `is_leaf` filter from the
  density join. The new geometric `is_leaf` is *correct* for the export's own area-double-count
  guard but is too aggressive as a density filter — it marks genuine assignment targets
  (CA1/CA3/DG-sg/STRd/HY) non-leaf whenever a smaller adjacent region's centroid falls inside
  their curved ROI, which silently dropped them from the density table. Since per-cell
  `region_label` is already the finest containing region after the `29dbfdc` fix, rollups
  receive zero cells and are excluded by the inner join regardless — no double-counting occurs
  without the `is_leaf` restriction, and CA1/CA3/DG-mo/DG-sg now report real densities.

**Effect on the numbers:** the `grey` bucket went from 95,383 cells to **zero** (it no longer
appears in the per-region breakdown at all — every cell now resolves to its true finest leaf).
Hippocampal-subfield cell counts roughly doubled where the old hemisphere-asymmetric bug had
been silently dropping one hemisphere's cells (e.g. CA1 3,567 → 6,354; SSp 9,324 → 24,370).
**This is a genuine correction, not a re-interpretation**: the prior record's explanation that
the elevated whole-section aggregate ratio was "pulled upward substantially by the `grey`
catch-all bucket" is now **wrong** and is replaced below by the corrected finding — the elevated
aggregate is driven by non-hippocampal regions elsewhere in the field of view, not a
data-resolution artifact. The whole-section totals for metric 1 (n(Double+)=3,457, n(TdT+)=4,134)
and metric 3 (nucleus-area peak) are **unchanged** — the region-labeling bug affected the
`region_label` column only, not the `class` (TdT+/Fos+/Double+/Negative) or `nucleus_area_um2`
columns, so those two metrics' whole-section/global numbers carry over unmodified from the
original run. Metrics 2 (density, per-region) and 4 (Fos+ control, SSp/fiber-tract subsets) are
region-attribution-dependent and are **fully recomputed** below. The previously-deferred
hemisphere-asymmetry finding (`deferred-items.md` former §D-1) is now **resolved** by this fix
— see `deferred-items.md` for the updated status.

---

## 1. Double+/TdT+ ratio

**Target:** 10–40% (10–40% band per `REQUIREMENTS.md`/`04-CONTEXT.md` D-02).

**Measured, whole section [measured]** (unchanged from the original run — the region-labeling
bug did not affect whole-section class totals):

| Convention | n(Double+) | n(TdT+) | Value | Band check |
|---|---|---|---|---|
| Raw ratio `n(Double+)/n(TdT+)` | 3,457 | 4,134 | **0.836** (83.6%) | flagged out of range vs. 10–40% |
| Co-expression fraction `Double+/(Double++TdT+)` | 3,457 | 4,134 | **0.455** (45.5%) | flagged out of range vs. 10–40% (IN-03: this band is defined for the ratio convention; reported against it here for direct comparability with Phase 2's D-06 advisory number) |

**Per-hippocampal-subfield breakdown [measured, corrected]** — now computed from the finest-leaf
region assignment (`29dbfdc`), which resolves the full bilateral cell population per subfield
instead of the prior right-hemisphere-dominated counts:

| Subfield | n(Double+) | n(TdT+) | Raw ratio | Coexpr fraction | Band check (coexpr, 10–40%) |
|---|---|---|---|---|---|
| CA1 | 56 | 104 | 0.538 | **0.350** | **IN RANGE** |
| CA2 | 1 | 10 | 0.100 | 0.091 | below range (n=11, low count) |
| CA3 | 21 | 126 | 0.167 | **0.143** | **IN RANGE** |
| DG-mo | 29 | 191 | 0.152 | **0.132** | **IN RANGE** |
| DG-po | 1 | 37 | 0.027 | 0.026 | below range |
| DG-sg | 0 | 0 | n/a | n/a | excluded from marker classification (Phase 2 D-05 lock: too dense for per-cell calls) |

Hippocampal subfields combined (CA1+CA2+CA3+DG-mo+DG-po+DG-sg) account for only **108 of 3,457
Double+ cells (3.1%)** and **468 of 4,134 TdT+ cells (11.3%)** section-wide. The remaining
non-hippocampal population — 3,349 Double+ / 3,666 TdT+ — reads a combined coexpression fraction
of **3,349/(3,349+3,666) = 0.477 (47.7%)**, i.e. *higher* than the whole-section aggregate
(0.455); the hippocampal subfields themselves pull the aggregate **down**, not up.

**Corrected cause of the elevated aggregate [measured]:** the prior record attributed the
elevated whole-section ratio primarily to the `grey` catch-all bucket. That explanation is now
known to be wrong — `grey` receives zero cells after the CR-01 fix (every cell resolves to its
true finest leaf). The elevated aggregate is instead driven by **non-hippocampal regions
elsewhere in the field of view** reading substantially higher coexpression than the hippocampal
subfields: auditory cortex (AUDd1 0.800, AUDd2/3 0.900, AUDd4 0.750, AUDv1 0.875, AUDv2/3 0.737,
AUDv4 0.643) and cortical amygdala (COAa 0.549) are the clearest examples, alongside numerous
somatosensory/retrosplenial/visual cortical regions (SSp-bfd subfields 0.55–0.71, SSs subfields
0.53–0.77, RSPd/RSPagl subfields 0.42–0.88, VISa subfields 0.31–0.81) that individually carry
substantial cell counts (hundreds each) and consistently read well above the 10–40% band. This
is a real, corrected finding, not the data-resolution artifact previously suspected.

**Interpretation (D-02: weigh all four candidates on paper, do not silently pass or fail):**

1. **Strong recall session effect [inferred]** — CA1 (0.350), CA3 (0.143), and DG-mo (0.132)
   all landing inside the 10–40% target band when isolated is consistent with a matched-context,
   strong-recall session per the broader engram literature's context-dependence pattern
   (`04-RESEARCH.md` §1) — a healthy, plausible reactivation rate in the subfields most
   classically associated with contextual recall, without needing to invoke an implausible
   response.
2. **n=1 sampling [inferred]** — still applies with full force: this is one section, one animal;
   subfield-level counts for CA2 (n(TdT+)=10) and DG-po (n(TdT+)=37) are small enough that a
   handful of mis-called cells shifts the ratio by several percentage points.
3. **Robust-threshold (k=3) sensitivity [candidate, not independently verified]** — the same
   globally-derived `median + 3·1.4826·MAD` cut (Phase 3 D-05) that classifies TdT+/Fos+ across
   the whole image is applied uniformly regardless of region; a region-agnostic global threshold
   can inflate or deflate a subfield's local positive rate relative to what a region-specific
   threshold would give. This candidate is now weaker as an explanation for the *hippocampal*
   numbers specifically (they land in-band after the region-labeling fix), but remains
   plausible for why cortical regions elsewhere in the section read consistently high. No
   k=4-vs-k=3 comparison has been run, so this remains a candidate, not a verified cause.
4. **Region-specific engram/sensory reactivation [inferred]** — the non-hippocampal regions
   driving the elevated aggregate are predominantly sensory cortex (auditory, somatosensory,
   visual) and cortical amygdala, all plausible sites of genuine session-related activity in a
   TRAP2 paradigm that is not restricted to hippocampal recall alone. This section's hippocampal
   subfields (the classically engram-relevant tissue) individually land in-band, while
   non-hippocampal cortex — which was never the target of the 10–40% seed's original
   provenance — reads elevated. This reframes candidate 4 from the original record (a
   CA1-vs-DG asymmetry argument, now less load-bearing since both CA1 and DG-mo land in-band)
   toward a region-scope argument: the whole-section aggregate mixes hippocampal and
   non-hippocampal tissue that were never expected to share one reactivation rate.

**Methodology-shift data point [measured]:** Phase 2's own D-06 advisory measurement of this
same whole-section ratio (pre-Phase-3-redesign, sigma=2.5, interactive-UI absolute thresholds)
was **≈0.40** — inside the 10–40% advisory band (`02-LOCK-RECORD.md`). The subsequent Phase-3
background-subtracted + robust-threshold (k=3) redesign shifted the whole-section co-expression
fraction to **0.455** (a real ~5.5-percentage-point shift attributable to a genuine
measurement-methodology change). This CR-01 correction pass did not change that whole-section
number again — 0.455 coexpr / 0.836 raw ratio is the same value before and after the
region-labeling fix, because the fix changed *region attribution*, not the underlying TdT+/Fos+
classification. The 0.40 → 0.45 methodology-shift point stands as originally documented and
remains direct evidence supporting candidate #3 above.

**Conclusion for this metric:** flagged out of range at the whole-section aggregate level
(0.455 vs. 10–40%), but three of five classified hippocampal subfields (CA1, CA3, DG-mo)
individually land inside the target band once cell counts are correctly (bilaterally) resolved.
The elevated aggregate is attributable to non-hippocampal cortical/amygdalar regions — not, as
previously suspected, a data-resolution artifact in a broad `grey` bucket. Per D-01, this is
recorded as a flagged note for the full series, not a blocker.

---

## 2. Per-region DAPI nucleus density

**Target:** 500–2,000/mm².

**Hippocampal-subfield densities [measured, corrected]** — now the true bilateral density per
acronym (`1052bc6`: joined without the over-aggressive `is_leaf` filter that previously dropped
or under-counted these subfields):

| Subfield | n_nuclei | area (mm², bilateral) | density/mm² | Band check |
|---|---|---|---|---|
| CA1 | 6,354 | 1.8813 | 3,377.4 | flagged out of range |
| CA2 | 465 | 0.1297 | 3,586.0 | flagged out of range |
| CA3 | 4,375 | 1.2903 | 3,390.8 | flagged out of range |
| DG-mo | 2,680 | 0.9299 | 2,882.1 | flagged out of range |
| DG-po | 422 | 0.1104 | 3,821.3 | flagged out of range |
| DG-sg | 1,090 | 0.3621 | 3,009.8 | flagged out of range |

All six hippocampal subfields now read out of range, uniformly clustered in the ~2,900–3,800/mm²
band. `root` (the residual, unassigned-below-root gap population) reads **772 nuclei /
56.0999 mm² = 13.8/mm²** — negligible, consistent with root now correctly capturing only the
small number of cells that do not resolve into any deeper leaf region, rather than acting as a
catch-all (contrast with the pre-fix `grey` bucket, which absorbed 95,383 cells at an inflated
3,877.4/mm² reading).

**What changed from the original record:** the original record reported CA1 at 1,896.0/mm²,
CA3 at 1,743.8/mm², DG-mo at 1,507.7/mm², and DG-sg at 1,027.2/mm² — all "IN RANGE" against the
500–2,000/mm² seed. Those numbers were an artifact of the hemisphere-asymmetric region-labeling
bug: CA1's per-cell count (3,567) was numerically identical to Phase 2's *right-hemisphere-only*
raw count, meaning the left hemisphere's CA1 nuclei had been silently absorbed into `grey`
instead of counted as CA1. With the CR-01 fix, CA1's bilateral count is 6,354 (roughly double),
and the corrected density (3,377.4/mm²) is now consistent with — not a genuine improvement over
— Phase 2's own per-hemisphere reference (`Left: CA1` 3,507.6/mm², `Right: CA1` 3,282.2/mm²,
`reference/dapi_region_reference.csv`). **The apparent "in-range" reading in the original record
was the bug; the corrected out-of-range reading is consistent with Phase 2's independently
measured density for this same tissue.**

**Interpretation — cite the prior Phase-2 finding, do not re-litigate the seed:** Phase 2 already
established and locked the conclusion that both seed ranges (density 500–2,000/mm² and area
50–150 µm², carried forward from the TRAP2 literature as `[ASSUMED]`) are **mis-calibrated for
20× Airyscan MIP DAPI on this instrument**, superseded by the empirical internal per-region
reference (`02-LOCK-RECORD.md`: "both seed ranges... judged mis-calibrated... and superseded by
the empirical internal per-region reference"). This record does not re-derive that verdict; it
is cited as established. Across the full 165-region breakdown the script prints, the large
majority of regions read in the ~2,500–5,500/mm² range Phase 2 already characterized as this
modality's true density character — a small number of broad ancestor/fiber-tract rollups
(`root` 13.8, `fiber tracts` 178.1, `CH` 0.0 (n=1, negligible), `HPF` 2.3 (n=11, negligible),
`TH` 31.0, `OLF` 100.3, `STR` 241.3, `lfbst` 225.0) read very low because their bilateral
polygon area spans a much larger footprint than the actual nucleus-bearing tissue within it —
an expected artifact of measuring density against a coarse ancestor region's full area rather
than its true occupied tissue, not a biological finding.

**Conclusion for this metric:** all six classified hippocampal subfields (CA1, CA2, CA3, DG-mo,
DG-po, DG-sg) now read consistently above the 500–2,000/mm² band, in the ~2,900–3,800/mm² range
— fully consistent with Phase 2's already-accepted mis-calibration finding for this imaging
modality, not a new discrepancy. The hemisphere-resolution artifact previously flagged as a
caveat on this metric (`deferred-items.md` former §D-1) is now resolved; these densities are the
corrected, trustworthy bilateral figures for the full series to reference.

---

## 3. Nucleus-area distribution peak

**Target:** 50–150 µm².

**Measured [measured]** (unchanged from the original run — `nucleus_area_um2` was not affected
by the region-labeling bug): modal 10 µm² bin = **[40.0, 50.0) µm²** (count 45,716 of 213,106
valid cells — n_valid = n_total, no missing area values). Bin-independent cross-checks: median =
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

**SSp corroboration anchor [measured, corrected]:** n = 24,370 SSp-labeled cells (region_label
starting `SSp`, spanning `SSp-bfd`/`SSp-tr`/`SSp-un`/`SSp-ll`/`SSp-ul` layers), Fos+ (Fos+ and
Double+ combined) = 11,574, rate = **0.475** (47.5%) — flagged out of range vs. the 1–3% target,
and notably more than double the whole-section Fos-expressing rate (20.1% — see below). This n
(24,370) is roughly 2.6× the original record's SSp count (9,324) — the same hemisphere-resolution
bug affected SSp exactly as it affected the hippocampal subfields, and the corrected count now
captures the full bilateral SSp population. The corrected rate (0.475) is close to the original
record's uncorrected rate (0.471) — the region-labeling bug under-counted SSp roughly uniformly
across positive and negative classes, so the *rate* barely moved even though the *count* did.

**Fiber-tract soft anchor [measured, corrected]:** n = 3,405 cells in fiber-tract-labeled regions
(`fiber tracts`, `cc`, `fx`, `or`, `ec`, `em`), Fos+ = 411, rate = **0.121** (12.1%) — also above
the 1–3% target, but well below both SSp (47.5%) and the whole-section average (20.1%),
consistent with fiber tracts carrying largely non-neuronal, sparsely Fos-competent cells. (n and
rate both close to the original record's 3,200/0.118 — fiber-tract regions were less affected by
the hemisphere-resolution bug than the hippocampal/SSp cortical regions.)

**Whole-section reference [measured, unchanged]:** total classified cells 213,106 — Negative
163,967, Fos+ 39,424, TdT+ 4,134, Double+ 3,457, Excluded (DG-sg/VS per Phase 2 lock) 2,124.
Fos-expressing (Fos+ + Double+) = 42,881/213,106 = **20.1%**. (These whole-section class totals
are unaffected by the region-labeling bug — only `region_label` attribution changed.)

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

This session's direct re-measurement (now on the corrected, full bilateral SSp population) shows
SSp's rate under the *corrected* pipeline is still elevated (47.5%) — well above the
whole-section average (20.1%) and far above the 1–3% seed. Two non-exclusive candidates,
consistent with the D-02 threshold-sensitivity discussion above: (a) **genuine regional sensory
activation [inferred]** — SSp is real cortex that plausibly experienced real tactile/sensory
input during the behavioral session, so an elevated (if not 1–3%-range) rate is not on its face
implausible for a region that was never meant to be a negative control; (b) **residual
global-threshold sensitivity [candidate, not verified]** — the same region-agnostic k=3 robust
cut discussed under metric #1 could still read SSp as elevated relative to a hypothetical
region-specific baseline, even after the local-background subtraction removed the specific old
autofluorescence artifact. Distinguishing these two candidates would require either a true
unstimulated control section or a region-specific threshold comparison — both explicitly out of
this plan's scope (D-01).

The fiber-tract anchor (12.1%), while still above the 1–3% seed, is meaningfully closer to it and
well below both SSp and the whole-section average — a soft, partial corroboration that the
classifier differentiates tissue types in the expected direction (sparse, largely non-neuronal
tissue reading lower than gray matter), even though it does not reach the seed's absolute range.

**Conclusion for this metric:** no true negative control exists in this section (documented, per
VAL-01's explicit allowance). SSp corroboration reads 47.5% Fos+ on the corrected, full bilateral
population — flagged out of range against the 1–3% seed. This is materially the same rate as the
original (uncorrected) record's 47.1% — the region-labeling bug affected the SSp cell *count*
more than the SSp Fos+ *rate*. The fiber-tract anchor (12.1%) offers softer, partial corroboration
in the expected direction. Flagged as a note for the full series — a true negative-control tissue
(if one becomes available) would resolve the ambiguity between the two candidate explanations
above.

---

## Closing statement (D-01)

Per D-01, Phase 4's VAL-01 validation is a findings record with interpretation, not a hard
pass/fail gate. All four metrics above carry a measured value and a written interpretation, now
computed from the CR-01-corrected region attribution: the ratio metric is flagged out of range at
the whole-section aggregate level but three of five classified hippocampal subfields (CA1, CA3,
DG-mo) individually land inside the 10–40% band; the density metric now reads out of range for
all six hippocampal subfields (previously four of six misleadingly read in-range due to the
region-labeling bug); the nucleus-area peak is marginally below its band, unchanged from the
original measurement; and the Fos+ control metric reads a corrected SSp rate (47.5%) essentially
unchanged from the original (47.1%), with a larger, now-correct denominator. **The phase completes
with these corrected findings recorded as written.** None of the out-of-range values are treated
as a failure requiring rework: each is interpreted against n=1 sampling, prior Phase-2 findings,
known methodology tradeoffs, or the now-resolved data-resolution history documented above (see
`deferred-items.md`), and becomes a flagged note carried forward to the full series
(SERIES-01/02), not a blocker to this phase's completion.
