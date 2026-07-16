# Phase 4: Biological Plausibility Validation and Imaging Optimization Notes - Research

**Researched:** 2026-07-16
**Domain:** TRAP2 engram histology validation (literature grounding) + fluorescence microscopy optics (Airyscan/Nyquist) — a documentation/analysis phase, not a build phase
**Confidence:** MEDIUM (empirical/filesystem facts HIGH; literature-range provenance LOW-MEDIUM — primary source paper is access-blocked, see below)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Phase 4 is a findings record with interpretation, not a hard pass/fail gate. Each metric is documented with its target range, marked in/out of range, and out-of-range values are interpreted (n=1 caveat, biological explanation, threshold-sensitivity note). The phase completes even if a metric lands out of range. Re-tuning detection is explicitly out of scope here.
- **D-02:** The known Double+/TdT+ ≈ 0.45 (45%) is expected to be flagged OUT (target 10–40%) and must carry a written interpretation — candidate explanations to weigh: strong recall session, n=1 sampling, robust-threshold (k=3) sensitivity on the double-positive intersection, hippocampus-specific engram reactivation. Document; do not silently pass or silently fail.
- **D-03:** Groovy export → Python analysis. A QuPath (Groovy) script exports per-cell measurements (class, region label, nucleus area, centroid) plus per-region areas from `data.qpdata` to a CSV/TSV; a Python script in the `braian` env computes the four VAL-01 metrics and the area histogram, and writes `04-VALIDATION.md`.
- **D-04:** Density requires per-region area in mm² — the export must emit region annotation areas (µm² → mm²) so DAPI-nucleus density is computed per region, using the same pixel calibration path already used in `qc_detection_gates.groovy`.
- **D-05:** Two separate documents: `04-VALIDATION.md` (VAL-01 per-run scientific record) and `04-IMAGING-NOTES.md` (OPT-01/02/03 forward-looking acquisition recommendations).
- **D-06:** Empirical where possible, reasoned/literature elsewhere — label each claim `[measured]` vs `[inferred]`. OPT-02 file sizes and OPT-01 Z-plane counts are measured directly (Z-count via `aicspylibczi` CZI metadata; sizes via filesystem). OPT-01 should be grounded, where existing files support it, in a detection-count comparison across the MIP variants already generated (single-plane, 3-plane, hybrid) — does adding planes change the DAPI/marker count, or has it plateaued? OPT-03: compare per-subfield detection quality on the existing 20x MIP; fall back to reasoned optical argument for resolutions never captured.

### Claude's Discretion

- **Negative-control region (VAL-01 Fos+ 1–3%):** document the absence per VAL-01's explicit "or absence documented" allowance (hippocampus-only field, no clean negative-control region). Report a within-section low-signal reference if available; also report the SSp Fos+ rate as a corroboration point (post-fix SSp should read low, which is evidence the classifier is behaving even though SSp is not a designated control).
- **Export script boundary:** new/separate Groovy script vs. a block added to `02_detect_classify.groovy` is the planner's call — Phase-3 precedent (keep the fast re-classify loop clean) favors a separate export script.
- **Nucleus-area-peak method** (histogram binning / KDE / mode estimation) is analysis plumbing → researcher/planner's call; see `## Nucleus-Area-Peak Estimation Method` below for the recommendation.

### Deferred Ideas (OUT OF SCOPE)

- Re-tuning detection thresholds to bring Double+/TdT+ into 10–40% (D-01) — a series-phase decision with n>1 support, not Phase 4.
- Full per-cell Atlas_X/Y/Z micron export column + per-region TSV (v2 EXP-01/02/03).
- Whole-brain / full-series autofluorescence + Fos-drift validation (SERIES-01/02).
- PNN (perineuronal net / WFA) quantification (future phase).
- BraiAnalyse group stats / brainrender 3D (need full registered series).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| VAL-01 | Bioplausibility check documented: Double+ 10–40% of TdT+; DAPI density 500–2,000/mm²; nucleus-area peak 50–150 µm²; Fos+ 1–3% on negative-control (or absence documented) | See `## VAL-01 Published-Range Provenance` — literature grounding for each target, the known ≈0.45 ratio interpretation, and the internal Phase-2 finding that the density/area seeds were already flagged mis-calibrated for this imaging modality |
| OPT-01 | Z-plane count audit: acquired vs. minimum needed for a good MIP at 20x Airyscan, with a concrete target recommendation | See `## OPT-01 Plane-Count / Nyquist-for-MIP Framing` — measured CZI metadata (6 planes, 2 µm step, 20x/0.8 NA) + optical framing + the detection-count-plateau empirical test design |
| OPT-02 | Per-section file size recorded (CZI raw + MIP OME-TIFF); MIP-immediately vs. store-raw-Z tradeoff assessed | See `## OPT-02 File Size / Storage Tradeoff` — measured sizes, ratio, and full-series projection |
| OPT-03 | Resolution assessment: 20x Airyscan required throughout vs. lower-power survey per subfield; which subfields need Airyscan resolution | See `## OPT-03 Optical Resolution Argument` — NA/Nyquist/PSF grounding, subfield-specific density argument, TRAP2-paper acquisition comparison |
</phase_requirements>

## Summary

This is a documentation/analysis phase, not a build phase: the deliverables are two markdown records (`04-VALIDATION.md`, `04-IMAGING-NOTES.md`) computed from data that already exists on disk. The plumbing (Groovy export → Python metrics script in the `braian` env) is already fully specified in CONTEXT.md and does not need re-research. This research instead grounds the four numeric targets and the two forward-looking imaging questions in verifiable facts and literature, and is explicit about what is measured on this machine today vs. what is cited vs. what is inferred from general optics.

**Primary recommendation:** Treat VAL-01 as an interpretation exercise, not a gate — the empirical evidence already gathered in Phase 2 (`reference/dapi_region_reference.csv`, `02-LOCK-RECORD.md`) shows the DAPI-density and nucleus-area seed ranges were *already judged mis-calibrated* for 20x Airyscan MIP DAPI on this instrument (measured densities cluster 2,500–5,500/mm² across nearly all regions, well above the 500–2,000/mm² seed; nucleus-area peak at the locked sigma=2.5 landed at [40,50) µm², just below the 50–150 µm² seed). Phase 4 should present VAL-01 against the *literature-cited* ranges (their actual scientific provenance, documented below) while explicitly cross-referencing this prior internal finding, rather than re-deriving the ranges from scratch. For OPT-01/03, the CZI metadata read directly from the raw file (6 Z-planes, 2 µm step, Plan-Apochromat 20x/0.8 objective) plus standard confocal/Airyscan optical formulas show the acquired Z-stack (10–12 µm total range) covers only a fraction of typical vibratome section thickness (30–50 µm) — consistent with 20x-air penetration-depth limits, not deliberate undersampling — and is far coarser than true Nyquist axial sampling (~0.3–0.6 µm/step) would require for 3D reconstruction; but 3D reconstruction is explicitly out of scope (this project's own CLAUDE.md defines "3D" as atlas-space point cloud, not physical tissue reconstruction), so the operative question is the empirical detection-count-plateau test across the three existing MIP variants, which this research frames but does not itself execute (no live QuPath session in this research pass).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Per-cell measurement export (class, region, area, centroid) | QuPath/Groovy (GUI, human-run) | — | Only QuPath has live access to `data.qpdata`'s PathObjects; must be a "Run for project" script per project convention |
| Per-region area (mm²) export | QuPath/Groovy (GUI, human-run) | — | Same data source; reuses `qc_detection_gates.groovy`'s pixel-calibration + annotation-area pattern |
| VAL-01 metric computation (ratio, density, area-peak, Fos+ control rate) | Python / `braian` env | — | Histogram/stats math is materially easier and more auditable in Python (scipy/numpy) than Groovy; D-03 locks this split |
| VAL-01 interpretation record (`04-VALIDATION.md`) | Documentation (Claude-authored) | Python (feeds the numbers in) | Interpretation of out-of-range values requires literature/biological reasoning, not just arithmetic |
| CZI Z-plane-count / pixel-size read (OPT-01) | Python / `braian` env (`aicspylibczi`) | — | Same reader already used by `czi_mip.py`; metadata-only read, no new dependency |
| File-size measurement (OPT-02) | Filesystem (shell) | — | Trivial `ls -la` / `stat`; no library needed |
| Detection-count-plateau comparison (OPT-01) | QuPath project entries (existing MIP variants) + Python rollup | — | Requires the classify script (or its summary.json) already run per MIP variant; this research frames the comparison, execution is a plan task |
| Resolution/optics argument (OPT-03) | Documentation (Claude-authored, literature+formula grounded) | — | No new code; a reasoned record referencing NA/PSF/Nyquist and the TRAP2 paper's own acquisition choices |

## Standard Stack

No new external packages are required for this phase. All computation is either:
1. **QuPath/Groovy** (already installed, v0.6.0 pinned) — for the export script, following the `qc_detection_gates.groovy` pattern.
2. **Python in the existing `braian` conda env** — `numpy` 2.1.3, `scipy` 1.17.1, `scikit-image` 0.26.0, `pandas` 2.3.3 all already present and verified importable in this research session (`conda run -n braian python3 -c "import scipy, numpy, skimage"` succeeded; `scipy.stats.mode` is available).
3. **`aicspylibczi`** — already used by `czi_mip.py`; a metadata-only read (`czi.get_dims_shape()`) gives the Z-plane count directly, no new dependency.

### Package Legitimacy Audit

**Not applicable — this phase installs no new packages.** All libraries used (`numpy`, `scipy`, `pandas`, `scikit-image`, `aicspylibczi`) are pre-existing, already-verified dependencies of the `braian` conda env from prior phases. No `npm view` / `pip index versions` / registry check is needed; no Package Legitimacy Gate applies.

## VAL-01 Published-Range Provenance

### Primary source access status

The phase's cited primary seed — **bioRxiv 2024.09.16.611953 / F1000Research 15:410** (Cabrera et al., "Establishment of an optimized and automated workflow for whole brain probing of neuronal activity," published F1000Research March 2026) — returned **HTTP 403 Forbidden** on both the bioRxiv full-text/PDF URL and the F1000Research article URL in this research session, consistent with the same block documented in this project's own `.planning/STATE.md` from an earlier research pass ("Primary paper source returned HTTP 403 during research"). The paper's public GitHub scripts repository (`sebastien-cabrera/CABRERA-et-al-Scripts-for-quantification-and-analysis`) was checked and does **not** publish specific numeric thresholds for cell density, nucleus area, or double-positive ratio — its README states only that scripts use "fixed parameters (cell diameter, sphericity...)" as project-specific values to be set per experiment. **Conclusion: the exact numeric target ranges in VAL-01/REQUIREMENTS.md cannot be traced to a directly-quoted sentence in the seed paper this session** — they are carried forward from an earlier phase's research (Phase 2) as `[ASSUMED] TRAP2-paper seeds` (see `02-LOCK-RECORD.md`: "All BraiAn.yml sigma/area/threshold values are [ASSUMED] TRAP2-paper seeds; Primary paper source returned HTTP 403 during research; not load-bearing"). Phase 4 should preserve this same honesty rather than re-asserting these as directly-verified.

### 1. Double+ / TdT+ ratio (target 10–40%)

**What the broader TRAP/engram literature supports [CITED, cross-checked across multiple sources]:** Studies using cFos+/tdTomato+ (or equivalent activity-tag) double-labeling to quantify "engram reactivation" consistently report the overlap fraction as **context-dependent**: same-context re-exposure (recall of the encoding context) produces a materially higher overlap fraction than exposure to a different context, and the difference from chance-level overlap is formally tested with a hypergeometric-distribution comparison (observed overlap vs. expected overlap given population sizes) — e.g., the brain-wide engram-mapping literature (Nature Communications 2022, and related dentate-gyrus/CA1 studies) reports this pattern explicitly, with **CA1 neurons showing more repeated/promiscuous cFos expression across sessions than DG neurons** — a documented biological asymmetry between hippocampal subfields relevant to interpreting a hippocampus-only section.

**Specific numeric range for matched-context reactivation [ASSUMED — training-data recall, not verified against a retrieved quoted source this session]:** classic Tonegawa-lab engram papers (Liu et al. 2012 *Nature*; Ramirez et al. 2013 *Science*; Tanaka et al. 2014 *Science*) are broadly recalled as reporting matched-context/strong-recall double-labeling fractions in roughly the **15–40% range**, with chance/different-context overlap closer to **5–15%**. This specific numeric range could not be re-derived from a directly quoted sentence in this session's web searches and must be flagged `[ASSUMED]` in `04-VALIDATION.md`; it is nonetheless consistent with the requirement's own 10–40% seed band, and — if correct — places the M3 measured **≈0.45 (45%)** only modestly above the *upper* end of what a strong, matched-context recall session would be expected to produce, not in a biologically implausible regime.

**Interpretation for the M3 ≈0.45 value (per D-02, weigh all four candidates on paper):**
1. **Strong recall session effect** — if the behavioral paradigm used a highly salient/matched-context recall, a reactivation fraction at or above the top of typical published ranges (rather than a false result) is the single most literature-consistent explanation, per the context-dependence finding above.
2. **n=1 sampling** — a single section, single animal has no distributional evidence; 45% vs. a 40% seed boundary is a difference of one section's worth of noise, not evidence of a systematic miscalibration.
3. **Robust-threshold (k=3, median+k·MAD) sensitivity** — Phase 3's D-05 redesign (see `.planning/debug/resolved/d05-threshold-all-negative.md`) replaced a histogram-peak threshold with a `median + 3×1.4826×MAD` robust cut on the background-subtracted measure; this cut is intentionally conservative-permissive (k=3 rather than a stricter k=4–5), and a looser TdT+ cutoff mechanically inflates the *denominator*-adjacent double-positive rate less than it inflates raw TdT+ count — worth stating explicitly that k-sensitivity has NOT been quantified (e.g., no k=4 vs k=3 comparison run) and is a candidate but unverified explanation.
4. **Hippocampus-specific engram reactivation** — the CA1-vs-DG promiscuity asymmetry noted above ([CITED] general finding, not M3-specific) means a hippocampus-only section (mixing CA1, CA2, CA3, DG subfields with different intrinsic reactivation rates) could plausibly show a pooled ratio above a range seeded from whole-brain or cortex-weighted literature; this is a real biological candidate, not a technical artifact — but was not decomposed to per-subfield ratios in Phase 3's summary and should be reported per-subfield if the D-03 export supports it (it does: region label is a per-cell field).

**Phase 2 cross-reference (documented, not a re-derivation):** Phase 2's own D-06 measurement of this same ratio (pre-Phase-3-redesign, sigma=2.5, interactive-UI thresholds) was **≈0.40** — inside the advisory band. The subsequent Phase-3 bg-sub + robust-threshold redesign shifted it to **≈0.45**. This is itself a documented, `[measured]` methodology-sensitivity data point that belongs in the VAL-01 interpretation: the ratio moved by ~5 percentage points across a real measurement-methodology change (not just biological variation), which is direct evidence for candidate #3 above and should be stated as such.

### 2. DAPI nucleus density (target 500–2,000/mm²)

**Internal empirical finding (already established, Phase 2 — [measured]):** `reference/dapi_region_reference.csv` (452 rows, all 451 loaded ABBA region annotations at the locked sigma=2.5 config) shows nearly all regions — cortex, striatum, thalamus, and hippocampal subfields alike — cluster in the **~2,500–5,500 detections/mm²** range (e.g., CA1: 3,282–3,508/mm²; DG-mo: 2,886/mm²; DG-po: 3,828/mm²; DG-sg: 1,923–4,255/mm² across hemispheres; whole-brain `root`: ~3,700–3,900/mm²). This is **2–3x above** the 500–2,000/mm² seed almost uniformly, not a hippocampus-specific deviation. `02-LOCK-RECORD.md` already concluded: "both seed ranges (TRAP2 literature) judged mis-calibrated for 20× Airyscan MIP DAPI and superseded by the empirical internal per-region reference." **Recommendation for VAL-01:** report the measured M3-entry-1 hippocampal densities plainly, note they land above the literature-cited seed (as they did in every other region checked in Phase 2), and cite this exact prior internal finding rather than re-litigating whether the seed is "right" — the phase's own D-01 framing (findings record, not gate) already anticipates this outcome.

**General literature context [ASSUMED/LOW confidence — not verified this session]:** published mouse hippocampal/cortical DAPI+ nuclear density figures vary widely by imaging modality (widefield vs. confocal vs. super-resolution), section thickness (MIP over a thick optical stack inflates apparent 2D density vs. a thin single-plane count), and segmentation algorithm (watershed splitting behavior). A MIP-based 2D density measurement is *expected* to read higher than a true single-optical-plane density, because a projected image can contain nuclei from multiple depths that would be at different apparent 2D positions if imaged truly confocally thin — this is a plausible, literature-consistent (if not verified against Cabrera et al. specifically) explanation for why this pipeline's own density measurements uniformly exceed the seed.

### 3. Nucleus area distribution peak (target 50–150 µm²)

**Internal empirical finding (Phase 2, [measured]):** at the locked sigma=2.5 detection config, the nucleus-area histogram peak bin was **[40, 50) µm²** (mode ≈45 µm²) — *marginally below* the 50–150 µm² seed lower bound. `02-LOCK-RECORD.md` notes sigma=3.0 gave a peak of [50,60) (inside the seed range) but was rejected because it "merged/missed larger cortical nuclei"; sigma=2.5 was chosen as "compromise" favoring completeness in dense cortical clusters over exact seed-range compliance. This is a **known, already-accepted tradeoff**, not a new finding — VAL-01 should report it as such (measured value, prior rationale for accepting it, D-01 framing that a marginal near-miss on a single section is not a blocker).

**Geometric sanity check [derived, HIGH confidence — simple geometry, not literature]:** for a circular nucleus cross-section, area↔diameter conversion gives: 50 µm² ≈ 8.0 µm diameter, 100 µm² ≈ 11.3 µm diameter, 150 µm² ≈ 13.8 µm diameter. A peak at ~45 µm² corresponds to a ~7.6 µm diameter nucleus — smaller than the typical reported mouse pyramidal/granule neuron nuclear diameter (commonly cited informally as ~8–12 µm), consistent with either (a) genuine biological variation/undercounting at the sigma=2.5 setting, or (b) mild oversegmentation (splitting) still present even after the sigma=2.0→2.5 adjustment documented in Phase 2.

### 4. Fos+ rate on negative-control region (target 1–3%, or absence documented)

**Per CONTEXT.md's Claude's-Discretion allowance:** this hippocampus-only section has no clean negative-control region (no unstimulated tissue, no secondary-antibody-only region). VAL-01 explicitly permits documenting this absence. Two corroboration points, both already available from Phase 3 without new imaging:
- **SSp Fos+ rate (already measured, [measured]):** Phase 3's D-04/D-05 local-background-subtraction fix was specifically designed to suppress SSp (somatosensory cortex) autofluorescence, which in Phase 2 (pre-fix) drove a false Fos+ read (SSp median nuclear-488 = 15,072 > the then-Fos cutoff of 13,000, i.e. >50% false-positive). Phase 3's human-attested run confirmed "SSp suppressed" post-fix. **This is the single best available corroboration point for VAL-01's Fos+ control-rate criterion** — report SSp's actual post-fix Fos+ percentage (obtainable from the same per-cell export, filtered to SSp region label) as a sanity anchor, explicitly noting SSp is not a true "unstimulated" control (it is somatosensory cortex, which may have genuine low-level Fos+ activity from normal sensory experience) but its dramatic before/after change is itself evidence the classifier's background-subtraction step is functioning.
- **Any low-signal within-section reference** (fiber/white-matter tract or non-engram structure): the `dapi_region_reference.csv` reference includes fiber-tract-like regions (`fiber tracts`, `cc`, `fx`, `or`, `ec`, `em`) with real DAPI density but presumably minimal neuronal Fos+ signal — worth checking their Fos+ percentage as an additional soft anchor if the D-03 export includes them, though these were excluded from marker classification in Phase 2/3 for other reasons (sparse/non-neuronal) and may not have Fos-classified cells at all.

## OPT-01 Plane-Count / Nyquist-for-MIP Framing

**Measured CZI acquisition parameters [measured, this session, via `aicspylibczi` on the raw CZI]:**

```
Automated Cell Counting/M3 Hippocampus 20x 062026.czi  (9,004,830,144 bytes, ~9.00 GB)
  Dims: X=1024, Y=1024 (per tile), Z=6 planes, C=3 channels, M=187 mosaic tiles, S=1 scene
  Objective: Plan-Apochromat 20x/0.8 M27 (air, NA=0.8)
  Camera: LSM 980, pixel distance 13.81 µm (before magnification)
  Pixel size (X/Y): 6.90535E-7 m = 0.690535 µm/px  — matches PIXEL_SIZE_UM already hard-coded in czi_mip.py
  Z step: 2E-6 m = 2.0 µm/plane
  Total acquired Z range: 5 intervals × 2.0 µm = 10.0 µm (6 planes spanning a 10 µm depth)
```

This confirms and extends what CONTEXT.md already flags: the "3-plane" MIP variant (`M3_20x_MIP_Z1-3.ome.tiff`) uses planes 1–3 of the 6 acquired (a 4 µm sub-range), the "single-plane" variant uses one plane (Z2), and the hybrid variant uses DAPI from Z2 with markers MIP'd over Z0–2 — all three variants are sub-ranges of the same 6-plane, 10 µm-deep acquisition, not independently-acquired stacks.

**What governs "minimum Z-planes for a good MIP" [derived from standard optics, CITED formulas]:** two distinct, commonly-conflated questions:

1. **Nyquist sampling for 3D reconstruction/deconvolution** — requires z-step ≤ axial-resolution/2.3 (a standard oversampling convention; some sources use a stricter /2 Shannon minimum). Confocal axial resolution (FWHM) follows `FWHM_axial = 0.88·λ_em / (n − √(n²−NA²))`; at NA=0.8, air (n=1): `n−√(n²−NA²) = 1−√(1−0.64) = 1−0.6 = 0.4`, giving FWHM_axial ≈ 1.0–1.3 µm across this project's three emission channels (DAPI ~460nm → 1.01 µm; Fos-488 ~525nm em → 1.16 µm; TdTomato ~581nm em → 1.28 µm). Airyscan's marketed ~1.7× resolution gain over confocal (see OPT-03 below) would bring this to roughly **0.6–0.75 µm axial FWHM**, and Nyquist z-step would then be **~0.26–0.33 µm/plane** — this project's acquired step (2.0 µm) is roughly **6–8× coarser** than true Nyquist for 3D reconstruction at this NA.
   **This Nyquist-for-reconstruction framing is NOT the operative question here** — CLAUDE.md and this project's own `.claude/CLAUDE.md` both define "3D" scope as the atlas-space cell point cloud, explicitly NOT physical tissue reconstruction; sub-micron 3D reconstruction fidelity is out of scope by design.
2. **"Does the MIP capture all real signal without missing out-of-focus content?"** — the actually-relevant question, and it is an **empirical, not formula-derivable**, question: it depends on whether real nuclei/marker signal extends beyond the axial range already sampled (10 µm) and whether the coarse 2 µm step under-samples enough to miss dim, defocused signal between planes. This is exactly the **detection-count-plateau comparison** CONTEXT.md's D-06 already specifies: run (or read existing `summary.json`/count outputs for) the single-plane (Z2), 3-plane (Z1-3), and hybrid (dapiZ2+mipZ0-2) variants and compare DAPI/Fos+/TdT+/Double+ counts. If counts are within noise across variants, the extra planes buy nothing and a lower plane-count (e.g., a 3-plane MIP or even the single Z2 plane, if it holds up) is the concrete target recommendation for the next imaging session. **This research frames the comparison; it does not execute it** — no live QuPath session was available in this research pass, and the three MIP variants have not yet all been run through `02_detect_classify.groovy` (only entry 1, the 3-plane variant, has a confirmed classified `data.qpdata` per Phase 3's verification). The Phase 4 plan should include a task to run (or verify existing results for) all three variants and diff their counts.

**Section-thickness cross-check [CITED, MEDIUM confidence]:** vibratome sections of mouse brain for immunohistochemistry are commonly cut at 30–50 µm thickness (40 µm particularly common), cross-checked across multiple independent vendor/protocol sources this session. The acquired 10 µm Z-range therefore covers only **~20–33%** of a typical vibratome section's physical thickness — this is consistent with normal 20x-air-objective imaging depth limits (light scattering/working-distance constraints prevent full-depth imaging of a 40 µm section at this NA without clearing or a longer-working-distance/higher-NA objective), not evidence that too few planes were acquired for the imaged depth. This is a useful, literature-grounded sentence for `04-IMAGING-NOTES.md`: the limiting factor on Z-range is imaging depth penetration at 20x/0.8 NA into a thick vibratome section, not the choice of Z-step.

## OPT-02 File Size / Storage Tradeoff

**Measured [measured, this session, filesystem]:**

| File | Size | Notes |
|------|------|-------|
| Raw CZI (`M3 Hippocampus 20x 062026.czi`) | 9,004,830,144 B (9.00 GB) | 6 Z × 3 C × 187 mosaic tiles × 1024×1024, uint16, mosaic (not yet stitched) |
| MIP OME-TIFF (`M3_20x_MIP_Z1-3.ome.tiff` and siblings) | ~968,910,236 B (0.97 GB) each | Stitched, single-plane-per-channel, uint16 |
| **Ratio (raw CZI : MIP)** | **~9.3×** | i.e. MIP-immediately reduces on-disk footprint to ~11% of raw |

**Full-series projection:** if the eventual full series has N sections at these per-section sizes, raw-CZI-only storage scales at ~9 GB/section vs. ~1 GB/section for MIP-only. This project's `.gitignore` already excludes all microscopy data from git (`*.tif/*.tiff/*.czi/*.lif`, ~23 GB currently on disk per `.planning/STATE.md`), so the tradeoff is purely local-disk-capacity vs. reprocessing-flexibility, not a git-repo-size concern. This machine has 854 GB NVMe free (per CLAUDE.md) — at 9 GB/section raw, ~90 sections of raw CZI would be storable; at 1 GB/section MIP-only, ~800+ sections. **No literature/domain convention search was needed here** (per the focus directive, this is a filesystem measurement + reasoned tradeoff) — the practical recommendation is: keep raw CZI for the current single-section validation run and any section where the OPT-01 plateau test is inconclusive (need to re-derive a different Z-range later), but plan to MIP-immediately-and-discard-raw for the bulk of the full series once OPT-01's plane-count recommendation is locked, given the ~9× storage multiplier and the finding above that the acquired Z-range is likely already governed by imaging-depth limits rather than a deliberately generous margin.

## OPT-03 Optical Resolution Argument

**NA and objective [measured, from CZI metadata]:** Plan-Apochromat 20x/0.8 M27, air, NA=0.8 — this is a **mid-range NA for an air objective** (20x air objectives commonly range NA 0.5–0.8; 0.8 is at the high end for air, but well below oil/water-immersion objectives at the same or higher magnification, e.g., 1.0–1.4 NA).

**Airyscan 2 resolution claims [CITED, cross-checked across Zeiss/university-facility sources, but the headline number is NA-specific]:** Zeiss Airyscan 2 (32-channel area detector + pixel reassignment + linear deconvolution) is marketed as achieving **~1.7× lateral AND axial resolution improvement over standard confocal**, with representative published numbers of **140 nm × 140 nm × 350 nm (X/Y/Z)** — but these headline numbers are demonstrated on **high-NA (typically 1.4 oil) objectives**. Applying the same *relative* 1.7× improvement factor to this project's NA=0.8 air objective is an **extrapolation, flagged `[inferred]`, not a verified Zeiss claim for that specific NA** — the absolute resolution at NA 0.8 will be substantially coarser regardless of Airyscan's relative gain, because diffraction-limited resolution itself scales with NA (lateral ~λ/NA, axial ~λ/NA²).

**Estimated resolution at this project's actual NA=0.8 [derived, MEDIUM confidence — standard formulas, Airyscan factor extrapolated]:**
- Confocal-equivalent lateral resolution (`0.4·λ/NA`): ~230–290 nm across the three channels (DAPI/Fos-488/TdTomato-568/581em)
- Confocal-equivalent axial resolution (FWHM, formula above): ~1.0–1.3 µm
- With the extrapolated ~1.7× Airyscan gain: lateral ~135–170 nm, axial ~0.6–0.75 µm

**What actually drives classification vs. what needs resolving:** the nucleus-anchored classification pipeline (per CLAUDE.md's non-negotiable rule) needs to (a) segment nuclei as discrete objects (DAPI, ~8–14 µm diameter per the 50–150 µm² target, i.e. **large relative to even the confocal-limited lateral resolution of ~230–290 nm** — nucleus segmentation itself does not require super-resolution, ordinary confocal-grade lateral resolution is more than adequate), (b) measure a cytoplasmic-ring intensity (TdTomato, a compartment defined by a fixed-µm expansion, not by resolving fine substructure), and (c) measure nuclear-mean intensity (Fos, again a compartment mean, not a fine-structure measurement). **None of the three classification-relevant measurements actually require Airyscan-grade lateral super-resolution** — they are all compartment-mean intensity measurements on already-large (>7 µm) objects. The place resolution genuinely matters is **nucleus *separability* in dense cell layers** — exactly what Phase 2 already found empirically: "CA1 nuclei cleanly separable (confirmed by researcher). DG granule layer not per-cell separable (expected) → density-only, DG-sg excluded from marker classification" (`02-LOCK-RECORD.md`). This is the load-bearing, already-empirically-validated answer to OPT-03's subfield question:

| Subfield | Nucleus packing | Per-cell separable at 20x/0.8 (measured, Phase 2) | Airyscan resolution need |
|----------|-----------------|----------------------------------------------------|---------------------------|
| CA1 (pyramidal) | Moderate-dense, single layer | Yes — confirmed cleanly separable | Standard confocal likely sufficient; Airyscan is a comfortable margin, not clearly required |
| CA2/CA3 (pyramidal) | Similar to CA1 (not explicitly re-checked in Phase 2, but same cytoarchitecture family) | Not explicitly re-tested — reasonable to expect similar to CA1 | Same expectation as CA1, unverified — flag for a quick visual QC in the full series |
| DG-sg (granule cell layer) | Very dense, tightly packed | **No** — not per-cell separable even with Airyscan at this NA/exposure; excluded from marker classification (density-only) | Would need substantially higher NA/resolution (oil immersion) or a different modality (e.g., STED, or accepting density-only quantification permanently) — Airyscan at NA 0.8 does not solve this |
| DG-mo / DG-po (molecular/polymorph layers) | Sparser than DG-sg | Included in Phase 2/3 classification (not excluded) | Comparable to CA1 |
| Cortex (e.g. SSp, used as reference) | Moderate, layered | Density measured without issue in Phase 2 reference table | Comparable to CA1 |

**Recommendation for `04-IMAGING-NOTES.md`:** Airyscan at 20x/0.8 NA is **not required for successful classification** in any subfield except where nucleus *separability* (not marker-intensity measurement) is the bottleneck — and even Airyscan does not solve DG-sg's separability problem at this NA (already empirically excluded). This suggests: (a) for CA1/CA2/CA3/DG-mo/DG-po and general cortical survey regions, a lower-power confocal survey (non-Airyscan, same or lower NA) would very plausibly suffice for cell-count/density purposes, since the limiting factor is nucleus packing density relative to lateral resolution, and Airyscan's gain here is a comfortable margin rather than a hard requirement; (b) DG-sg will remain density-only regardless of resolution tier chosen, unless a fundamentally different imaging strategy (oil immersion, higher NA, or accepting non-single-cell density) is adopted — this is an existing, already-accepted limitation, not a new gap. **This recommendation should be flagged for empirical confirmation** (side-by-side same-region imaging at Airyscan vs. non-Airyscan confocal) before being treated as locked guidance — this research provides the optical reasoning, not a live comparison (no such paired acquisition exists on disk to compare).

**TRAP2 paper's own acquisition parameters [not verified — 403-blocked, see VAL-01 section]:** could not be confirmed this session due to the same access block; if accessible in a future session, the Cabrera et al. paper's stated objective/NA/Z-stack choices would be a directly relevant comparison point and should be added then.

## Nucleus-Area-Peak Estimation Method

**Recommendation: histogram-mode as primary, matching the codebase's existing convention, with a percentile/IQR spread reported alongside; KDE mode as an optional cross-check.**

The codebase already implements a histogram-mode peak estimator in Groovy (`qc_detection_gates.groovy`, Gate 1): 10 µm² bins, `argmax` over bin counts. For consistency and auditability, the Python D-03 script should use the **same bin width (10 µm²)** so the two independently-computed peak values (Groovy's ephemeral QC print vs. the Python VAL-01 record) are directly comparable, not artifacts of different binning choices.

```python
# Source: matches qc_detection_gates.groovy's Gate-1 binning (AREA_BIN_WIDTH_UM2 = 10.0)
# scipy 1.17.1 / numpy 2.1.3 confirmed present in braian env (verified this session)
import numpy as np

def area_histogram_mode(areas_um2: np.ndarray, bin_width: float = 10.0) -> tuple[float, float, int]:
    """Returns (bin_start, bin_end, count) of the modal 10 um^2 bin."""
    areas_um2 = areas_um2[~np.isnan(areas_um2)]
    bin_starts = np.floor(areas_um2 / bin_width) * bin_width
    values, counts = np.unique(bin_starts, return_counts=True)
    peak_idx = np.argmax(counts)
    return values[peak_idx], values[peak_idx] + bin_width, int(counts[peak_idx])
```

**Pitfalls to guard against (document these in `04-VALIDATION.md` methodology notes):**
- **Bin-width sensitivity:** a 10 µm² bin at a peak near 45 µm² can shift the reported peak bin by one bin-width depending on bin edge alignment (e.g., floor-based bins starting at 0 vs. bins centered on the data). Report the bin edges explicitly, and consider also reporting the **median** and **IQR** of the area distribution as a bin-independent cross-check (scipy has no binning ambiguity for median/IQR).
- **Log-scale consideration:** cell/nucleus area distributions are frequently right-skewed (a long tail of larger, possibly-merged or oversegmented objects); if the histogram looks strongly skewed rather than roughly unimodal, computing the mode on `log(area)` and converting back can give a more stable central estimate than a linear-scale histogram mode — recommend checking a quick skewness statistic (`scipy.stats.skew`) before deciding.
- **Outlier tails:** the locked `maxAreaMicrons=250` cap (Phase 2) already bounds the upper tail at detection time, but very small fragments near `minAreaMicrons=20` can still pull a linear histogram's low-end bins; the min/max area gate already constrains this to a bounded [20,250] µm² domain, so extreme-outlier handling is less of a concern here than in an uncapped dataset.
- **KDE mode as an optional cross-check, not primary:** `scipy.stats.gaussian_kde` can give a continuous-density mode estimate immune to bin-edge artifacts, but requires a bandwidth choice (default Scott's/Silverman's rule is usually adequate for ~10³–10⁴ points) and is more opaque to a non-statistician reader of the record than "which 10 µm² bin has the most cells." Recommend using it only as a stated cross-check ("KDE mode = X µm², consistent with histogram mode Y µm²") rather than the primary reported number.

## Common Pitfalls

### Pitfall 1: Treating literature-seeded ranges as ground truth rather than population expectations
**What goes wrong:** re-tuning detection parameters or writing an "out of range = broken" verdict based on a single n=1 section against ranges whose exact literature provenance could not be confirmed this session (403-blocked primary source).
**Why it happens:** the ranges look precise (500–2,000/mm², 50–150 µm², 10–40%) and invite treating them as hard acceptance criteria.
**How to avoid:** D-01 already locks this — report, interpret, do not gate. Cite the *actual* provenance status honestly (literature-grounded broad pattern for the double+ ratio's context-dependence; unverifiable exact numbers for density/area; Phase 2's own prior finding that density/area seeds were already judged mis-calibrated for this modality).
**Warning signs:** phrasing like "FAILED" or "must fix" anywhere in `04-VALIDATION.md` for a metric — the correct register is "flagged out of range, interpreted as follows."

### Pitfall 2: Conflating Nyquist-for-3D-reconstruction with "enough planes for a good MIP"
**What goes wrong:** computing a formal Nyquist z-step (~0.3 µm) and concluding the current 2 µm step is "wrong," when the project's actual 3D scope (atlas-space point cloud, not tissue reconstruction) never required that sampling density in the first place.
**Why it happens:** Nyquist/PSF formulas are the standard, well-documented answer to "how should I sample Z," but they answer a different question (faithful 3D reconstruction) than the one OPT-01 is actually asking (does the 2D MIP miss real signal).
**How to avoid:** frame OPT-01's answer around the empirical detection-count-plateau comparison across the three existing MIP variants, using the Nyquist formula only as background context for *why* the current step is coarse, not as the basis for the actual recommendation.
**Warning signs:** a recommendation that says "should be N µm/step per Nyquist" without reference to the plateau test.

### Pitfall 3: Assuming Airyscan's marketed resolution figures apply unchanged at this project's NA
**What goes wrong:** citing "140nm/350nm" as this project's actual resolution without noting those figures are typically demonstrated at NA ~1.4 (oil), not this project's NA 0.8 (air).
**Why it happens:** the marketed numbers are the most commonly retrieved search result and are easy to misapply.
**How to avoid:** always requalify with the actual objective NA and recompute via the standard confocal formula, extrapolating the *relative* Airyscan gain rather than reusing the *absolute* headline number.
**Warning signs:** any resolution number in `04-IMAGING-NOTES.md` not paired with "at NA=0.8" or explicitly marked `[inferred]`.

### Pitfall 4: Using export-script measurement key names that don't match what `02_detect_classify.groovy` actually writes
**What goes wrong:** the D-03 export script assumes generic QuPath measurement names (e.g., `"Cell: AF568 mean"`) instead of the project's actual bg-sub-suffixed keys.
**Why it happens:** QuPath's measurement key naming is compartment- and channel-name-dependent and was itself the root cause of the Phase-3 D-04/D-05 all-Negative bug.
**How to avoid:** the export script must read the exact same keys the classify script already resolved and wrote: `"Nucleus: Area µm^2"` (area), `"Nucleus: AF488-T3 mean (bg-sub)"` (Fos), `"Cytoplasm: AF568-T2 mean (bg-sub)"` (TdT), plus `getPathClass()` for the four classes (Double+/Fos+/TdT+/Negative, and Excluded for DG-sg/VS) and the `regionOf`/`regionLabel` closures' output for atlas region.
**Warning signs:** an export that reads `null` for area/intensity on most cells — the exact symptom of the D-04 bug from Phase 3.

## Code Examples

### Reading Z-plane count and pixel calibration from the raw CZI (OPT-01)
```python
# Source: verified this session against the actual project CZI file
# (Automated Cell Counting/M3 Hippocampus 20x 062026.czi), using the same
# aicspylibczi API already used by czi_mip.py — no new dependency.
import aicspylibczi

czi = aicspylibczi.CziFile(CZI_PATH)
dims = czi.get_dims_shape()[0]   # list of dicts for multi-scene; [0] for single-scene S=1
n_z = dims['Z'][1]                # 6 for this file
n_c = dims['C'][1]                # 3
n_tiles = dims['M'][1]            # 187 (mosaic tiles)

# Z step and pixel size come from the Scaling/Items block in czi.meta (OME-adjacent
# metadata), not from get_dims_shape():
scaling = czi.meta.find('.//Scaling/Items')
z_step_m = float(scaling.find("./Distance[@Id='Z']/Value").text)   # 2e-6 -> 2.0 um
xy_um    = float(scaling.find("./Distance[@Id='X']/Value").text) * 1e6  # 0.690535 um/px
```

### Histogram-mode nucleus-area peak (matches Groovy's existing Gate 1 binning)
See `## Nucleus-Area-Peak Estimation Method` above.

## State of the Art

Not applicable in the "old vs. current library version" sense — this is a scientific-methodology and optics question, not a software-dependency question. The one relevant "state of the art" note: this pipeline's own methodology evolved mid-project (Phase 2's histogram-relative interactive threshold → Phase 3's background-subtracted + robust median/MAD threshold), and that evolution measurably shifted the Double+/TdT+ ratio (0.40 → 0.45) — this is documented above as direct evidence for the D-02 interpretation, not a generic industry trend.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | VAL-01's exact numeric target ranges (500–2,000/mm², 50–150 µm², 10–40%, 1–3%) trace directly to the Cabrera et al. TRAP2 paper | VAL-01 Published-Range Provenance | LOW — already flagged `[ASSUMED]` since Phase 2; paper is 403-blocked again this session; does not change Phase 4's D-01 findings-record framing, but means the record should not claim these are "the paper's numbers" without hedging |
| A2 | Matched-context/strong-recall double-labeling fractions in the general engram literature are ~15–40%, chance/different-context ~5–15% | VAL-01 §1 (Double+/TdT+ ratio) | MEDIUM — this specific range is training-data recall, not confirmed via a directly-quoted source this session; if wrong, the "45% is only modestly above typical strong-recall ranges" framing in the Summary would need softening to "45% cannot be benchmarked against a verified literature range" |
| A3 | Airyscan's ~1.7× resolution gain over confocal (demonstrated at NA~1.4 oil) extrapolates proportionally to this project's NA=0.8 air objective | OPT-03 | MEDIUM — if Airyscan's relative gain is NA-dependent (plausible, since the underlying pixel-reassignment SNR gain may interact differently with a lower-NA PSF), the estimated 0.6–0.75 µm axial figure could be off; the qualitative conclusion (classification doesn't need this resolution; DG-sg separability is NA-limited, not Airyscan-limited) is robust to this uncertainty |
| A4 | Vibratome sections in this project are 30–50 µm thick (no project-specific confirmation found) | OPT-01 (section-thickness cross-check) | LOW-MEDIUM — this is a general-practice figure, cross-checked across independent sources, but not confirmed against this specific lab's actual protocol; if this project's sections are thinner (e.g., 20 µm) or thicker (e.g., 60 µm+), the "10 µm acquired range covers ~20–33% of section thickness" estimate would need updating — recommend the planner add a quick check (ask the wet-lab protocol or measure directly) rather than treating 30–50 µm as locked |
| A5 | CA2/CA3 pyramidal layers have separability comparable to CA1 (extrapolated, not independently re-tested in Phase 2) | OPT-03 table | LOW — CA1/CA2/CA3 share cytoarchitecture family; if CA2/CA3 turn out denser/less separable than CA1 in practice, only the OPT-03 subfield table's CA2/CA3 row needs revision, not the overall conclusion |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Exact TRAP2-paper acquisition parameters (objective, NA, Z-stack depth) for direct comparison**
   - What we know: paper identity, title, and workflow description confirmed via search; QuPath/ABBA-based pipeline confirmed as directly analogous to this project's own tooling.
   - What's unclear: the paper's own imaging parameters (403-blocked full text) — would be a strong, directly-comparable OPT-03 anchor if retrievable.
   - Recommendation: if the planner or a future session gets authenticated/institutional access to bioRxiv or F1000Research, re-attempt this fetch; otherwise proceed with the general-optics-formula argument documented above, clearly labeled as not paper-verified.

2. **Has the detection-count-plateau comparison (single-plane vs 3-plane vs hybrid) actually been run?**
   - What we know: all three MIP variant files exist on disk; only the 3-plane variant (entry 1 in the "M3 Hippocampus 20x 062926 3 plane" project) has a confirmed classified `data.qpdata` per Phase 3's verification.
   - What's unclear: whether the single-plane and hybrid variants have been run through `01_load_abba_rois.groovy` + `02_detect_classify.groovy` in any QuPath project, or only MIP'd (file exists) but never registered/detected/classified.
   - Recommendation: the Phase 4 plan should include an explicit task to check `data/*/summary.json` existence for each variant's QuPath project entry, and — if missing — either run detection+classification on them (adds a GUI-human-in-the-loop step) or explicitly scope OPT-01's plateau argument down to "reasoned, not yet empirically confirmed across all three variants" if that GUI step is out of budget for this phase.

3. **What is the M3-section-specific vibratome thickness?**
   - What we know: general practice is 30–50 µm (A4 above).
   - What's unclear: this specific animal/protocol's actual cut thickness.
   - Recommendation: check wet-lab notes/protocol if available; otherwise state the 30–50 µm figure as a general reference point, not a project-specific fact, in `04-IMAGING-NOTES.md`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `braian` conda env (numpy/scipy/pandas/scikit-image) | VAL-01 Python metrics script | ✓ | numpy 2.1.3, scipy 1.17.1, pandas 2.3.3, scikit-image 0.26.0 (all verified importable this session) | — |
| `aicspylibczi` (in `braian` env) | OPT-01 Z-plane-count read | ✓ | 3.3.1 (per project docs; import not re-verified this session but already load-bearing in `czi_mip.py`) | — |
| QuPath v0.6.0 | D-03 Groovy export script (human-run) | Not verifiable from this shell session (GUI-only, requires `DISPLAY=:0`) | v0.6.0 (per CLAUDE.md status log) | None — this step is GUI-only by project convention; no scriptable fallback |
| Internet access to bioRxiv/F1000Research | Primary literature confirmation | ✗ (403 Forbidden on both endpoints, this session) | — | Proceed with general-literature/formula grounding, clearly labeled `[ASSUMED]`/`[inferred]` per D-06's convention; re-attempt in a future session if institutional access becomes available |

**Missing dependencies with no fallback:** none blocking — the 403 block only affects citation precision, not the phase's ability to produce its two documents.

**Missing dependencies with fallback:** bioRxiv/F1000Research primary-source access (fallback: general engram/optics literature via web search, explicitly labeled by confidence tier, per this document).

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None (no automated test suite in this project; QuPath/Groovy GUI-mediated pipeline with human-attested verification, per Phase 3's precedent) |
| Config file | none |
| Quick run command | `conda run -n braian python3 <val01_metrics_script>.py` — the Python metrics script itself is the fastest re-runnable check once the D-03 export TSV exists |
| Full suite command | Re-run the Groovy export ("Run for project" in QuPath, human-triggered) + the Python metrics script |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VAL-01 | Four metrics computed and documented with interpretation | script output + manual record | `conda run -n braian python3 <val01_script>.py` (writes `04-VALIDATION.md` sections/values) | ❌ Wave 0 — export script + Python metrics script both need authoring |
| OPT-01 | Z-plane count read + plateau comparison documented | script output (metadata read) + manual record | `conda run -n braian python3 -c "import aicspylibczi; ..."` (see Code Examples) | ❌ Wave 0 — no standalone script yet; inline snippet suffices, or fold into the VAL-01 script |
| OPT-02 | File sizes measured | shell command | `stat -c%s <file>` / `ls -la` | ✓ — trivial, no script needed |
| OPT-03 | Optical/resolution argument documented | manual record (reasoned, no automated check) | n/a | n/a — documentation only |

### Sampling Rate
- **Per task commit:** re-run the Python metrics script against the export TSV; diff the computed numbers against the previous run if the export was regenerated.
- **Per wave merge:** confirm both `04-VALIDATION.md` and `04-IMAGING-NOTES.md` exist, are non-empty, and every VAL-01/OPT-01..03 requirement has a corresponding documented finding (grep for section headers).
- **Phase gate:** since this phase has no pass/fail acceptance criteria (D-01), the "gate" is document completeness, not a numeric pass — verify all four VAL-01 metrics and all three OPT items have both a value and a written interpretation before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] D-03 Groovy export script (new file, e.g. `scripts/03_export_val01_metrics.groovy`, or a block appended to an existing script per the planner's discretion) — does not yet exist.
- [ ] Python metrics script (new file, e.g. `scripts/val01_metrics.py`, in the `braian` env) — does not yet exist; should implement the histogram-mode area-peak estimator documented above, the density-per-region calculation reading the D-04 area export, and the ratio/rate calculations.
- [ ] No test framework install needed — this phase's "tests" are the scripts' own printed output plus human/documentation review, consistent with the rest of this GUI-mediated pipeline.

## Security Domain

**ASVS categories: not applicable.** This phase produces two local markdown documents and reads existing local microscopy files and QuPath project state; there is no network-facing service, no authentication, no user-supplied input beyond files already trusted within this single-operator local pipeline, and no cryptography or session management surface. The project's `security_enforcement: true` / `security_asvs_level: 1` config setting is not meaningfully engaged by a documentation/analysis phase with no new code paths handling untrusted input — noting this explicitly rather than fabricating applicable ASVS rows.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | N/A — single-operator local machine, no auth surface |
| V3 Session Management | No | N/A |
| V4 Access Control | No | N/A |
| V5 Input Validation | No (weak sense only) | The export TSV read by the Python script should be validated for expected columns/row count before computing metrics (defensive coding, not a security control) |
| V6 Cryptography | No | N/A — no secrets, no crypto surface in this phase |

### Known Threat Patterns for this stack
None identified — no injection surface, no network exposure, no untrusted-input parsing beyond a locally-generated TSV file from a script this project itself authors and controls.

## Sources

### Primary (attempted, blocked)
- bioRxiv 2024.09.16.611953 (full text and PDF) — HTTP 403, this session
- F1000Research 15:410 (`f1000research.com/articles/15-410`) — HTTP 403, this session
- [GitHub — sebastien-cabrera/CABRERA-et-al-Scripts-for-quantification-and-analysis](https://github.com/sebastien-cabrera/CABRERA-et-al-Scripts-for-quantification-and-analysis) — checked; no specific numeric parameters published

### Secondary (MEDIUM confidence — cross-checked web sources)
- [Vibratome sections for IHC — thickness ranges](https://www.vibrotome.com/post/70%C2%B5m-mouse-brain-sections-for-immunohistochemistry-cur-with-5100mz-vibrotome), [ResearchGate Q&A on IHC section thickness](https://www.researchgate.net/post/What-can-be-the-ideal-thickness-of-the-tissue-section-for-IHC), [Precisionary — vibratomes vs microtomes](https://precisionary.com/applications-vibratomes-vs-microtomes/)
- [Zeiss Airyscan detector / resolution](https://www.zeiss.com/microscopy/en/products/light-microscopes/confocal-microscopes/airyscan.html), [Cellular Imaging Facility (unil.ch) — Airyscan system](https://cif.unil.ch/the-airyscan-system-for-improved-confocal-resolution/), [ZEISS LSM 980 with Airyscan 2 brochure](https://pages.zeiss.com/rs/896-XMS-794/images/ZEISS-Microscopy_Product-Brochure_ZEISS-LSM-980.pdf)
- [ConductScience Nyquist Sampling & PSF Calculator](https://conductscience.com/tools/nyquist-sampling-psf-calculator), [microscopist.co.uk — Collecting Data: Nyquist Sampling](https://microscopist.co.uk/collecting-data-nyquist-sampling/), [UQ IMB — Nyquist Conditions](https://imb.uq.edu.au/research/facilities/microscopy/training-manuals/microscopy-online-resources/image-capture/nyquist-conditions)
- [Brain-wide mapping reveals that engrams for a single memory are distributed across multiple brain regions — Nature Communications 2022](https://www.nature.com/articles/s41467-022-29384-4)

### Tertiary (LOW confidence — training-data recall, flagged ASSUMED)
- Classic Tonegawa-lab engram papers (Liu et al. 2012 *Nature*; Ramirez et al. 2013 *Science*; Tanaka et al. 2014 *Science*) — specific reactivation-percentage ranges recalled from training data, not independently re-confirmed via a directly quoted source this session

### Internal (this project, HIGH confidence — already-verified prior-phase artifacts)
- `.planning/phases/02-detection-parameter-lock/02-LOCK-RECORD.md`
- `reference/dapi_region_reference.csv` (452 rows, whole-section per-region density reference at locked sigma=2.5)
- `.planning/phases/03-detection-script-and-single-section-end-to-end-test/03-VERIFICATION.md`
- `.planning/debug/resolved/d05-threshold-all-negative.md`
- `scripts/qc_detection_gates.groovy`, `scripts/02_detect_classify.groovy`
- Direct CZI metadata read (this session): `Automated Cell Counting/M3 Hippocampus 20x 062026.czi`

## Metadata

**Confidence breakdown:**
- VAL-01 numeric-range provenance: LOW — primary source 403-blocked both this session and in a prior session; ranges carried forward as `[ASSUMED]` since Phase 2
- VAL-01 interpretation reasoning (context-dependence, CA1-vs-DG asymmetry, chance-overlap statistics): MEDIUM — cross-checked web sources, general literature pattern confirmed, exact M3-applicable numbers not
- OPT-01/OPT-02 measured facts (Z-count, Z-step, pixel size, file sizes): HIGH — directly measured this session against the actual project files
- OPT-03 optical/Nyquist formulas and Airyscan headline figures: MEDIUM — formulas are standard/well-established (CITED), but the Airyscan-at-NA-0.8 extrapolation is explicitly flagged inferred
- Nucleus-area-peak estimation method: HIGH — standard scipy/numpy techniques, consistent with the codebase's own existing Groovy convention

**Research date:** 2026-07-16
**Valid until:** Literature-grounding sections (VAL-01, OPT-03 Airyscan figures) — 90 days (stable domain, but re-attempt bioRxiv/F1000 access if this phase is revisited); measured-fact sections (OPT-01/02) — valid indefinitely for this specific CZI file, but must be re-measured per-section for the full series (SERIES-01/02, out of scope here).
