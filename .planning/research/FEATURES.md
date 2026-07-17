# Feature Research

**Domain:** Neuroscience whole-brain mapping / TRAP2 engram quantification (mouse coronal sections, Allen CCFv3)
**Milestone:** v1.1 — First Full-Series Run, LA/BA Amygdala Engram (wBA1-3)
**Researched:** 2026-07-17
**Confidence:** LOW-MEDIUM (websearch-only sources this pass; no context7/exa/tavily/firecrawl available — treat quantitative bands as directional hypotheses, not locked gates, and re-verify against the seed paper bioRxiv 2024.09.16.611953 and the ABBA+BraiAn Cell Reports 2025 paper before finalizing thresholds)

**Note:** This file supersedes the v1.0 (single-section) FEATURES.md for the purposes of v1.1 planning. v1.0 features — CZI→MIP single-scene conversion, ABBA registration mechanics (DeepSlice + manual angle, no Affine/Spline), BraiAnDetect nucleus-anchored TdT+/Fos+/Double+ classification, per-region count/density rollup, CCFv3 micron export, VAL-01 bioplausibility methodology — are validated and NOT re-researched here. This file covers ONLY the 8 new v1.1 target features. The prior v1.0 hippocampal plausibility bands (TdT+ ~3.5% of DAPI+, Fos+ ~20%, Double+/TdT+ ~0.45; densities ~3,000/mm²; nucleus area peak 40-50 µm²) remain the project's own strongest same-pipeline precedent and should still be consulted alongside the new amygdala bands below.

---

## Feature Landscape

### Table Stakes (Expected for a Credible Full-Series / Amygdala-Engram Run)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Multi-scene MIP conversion (5 sections/animal) | A "full series" run is meaningless if ingestion still handles one section at a time; every whole-brain pipeline (ABBA, BraiAn, ClearMap) assumes N sections per animal as the base unit | LOW-MEDIUM | Pure extension of `czi_mip.py` — loop over CZI scenes, same channel-order fix (`--channels` override) applies per scene. Depends on v1.0 `czi_mip.py`. No new algorithm, just I/O looping + per-scene output naming. |
| Per-region nucleus-anchored TdT+/Fos+/Double+ counts in LA/BA | Direct continuation of the validated v1.0 colocalization method — the project's primary readout and core value proposition | MEDIUM | Depends fully on v1.0 `02_detect_classify.groovy`, locked detection params, and ABBA-RoiSet region labeling (with the CR-01 leaf-region fix). Only new work is ROI scoping to amygdala + running across 5 sections instead of 1. |
| Region-labeling correctness across all sections (brain-wide validation) | A single-section CR-01-style mislabeling bug (cells leaking into a `grey` rollup) silently corrupts every downstream region count; catching this before scaling is standard practice when a pipeline moves from n=1 to n=sections | LOW-MEDIUM | Direct re-application of the Phase-4 fix (`is_leaf` geometric containment) across 5 sections. Mostly a verification/QA pass, not new code. Depends on v1.0 Phase-4 CR-01 fix already being correct. |
| Section→animal aggregation (roll-up across sections into one animal-level table) | Aggregating to animal level BEFORE any group comparison is this project's own stats convention (CLAUDE.md) and standard practice in every whole-brain IEG paper (ABBA+BraiAn, ClearMap2-based papers) — sections are not independent replicates | MEDIUM | Depends on BraiAnalyse (`braian` conda env) being fed correctly-labeled per-section summary tables. First real use of BraiAnalyse in this project — integration risk even though the library itself is off-the-shelf and purpose-built. |
| Full per-region micron-coordinate export (brainrender-ready point cloud) | CCFv3-micron export was already a v1.0 hard rule; extending it across a full series so a 3D point cloud can be built is the natural conclusion of registration + classification — every whole-brain visualization pipeline (brainrender, BrainGlobe) requires micron CCFv3 coordinates as input | LOW-MEDIUM | Mechanical extension of the v1.0 micron-export step across all classified cells/sections. Depends on ABBA transform correctness per section and classification being complete first. |

### Differentiators (This Milestone's Actual Novel Work)

| Feature | Value Proposition | Complexity | Notes |
|---------|--------------------|------------|-------|
| Generalizable area-based density readout for compact-nuclei regions (DG test case) | Nucleus-anchored counting silently fails in the DG granule layer and potentially in dense amygdala sub-nuclei because adjacent nuclei visually overlap and defeat threshold/watershed segmentation — a known, documented problem in DG imaging. Building this as a reusable, brain-wide-ready module (not a one-off DG hack) is the differentiator: it's what lets the pipeline scale past hippocampus/amygdala to any dense nucleus later | HIGH | New algorithm, not an extension of v1.0 code. Depends on a DAPI+ region mask (from the existing detection step — no new detector needed) and must stay a **documented, additive/parallel exception**, never replacing nucleus-anchored counts (per the project's own recorded Key Decision). Accepted field methods, in order of precedent/simplicity: (1) **percent-area-above-threshold** — binarize each marker channel by intensity threshold, restrict to the DAPI+ ROI, report % area covered; the most commonly cited fallback for dense-region IEG quantification (e.g. dentate gyrus c-fos literature) and reuses the project's already-locked robust threshold logic (median + k·MAD, k=3); (2) **integrated optical density (IOD)** within the ROI — intensity-weighted variant of the same idea; (3) **pixel-level co-occurrence of two thresholded channel masks** (area of TdT+ mask ∩ Fos+ mask within the DAPI+ ROI) as the closest area-based analogue to "double-positive," but numerically distinct from a per-cell double-positive fraction and must be labeled as such. Manders' overlap coefficient specifically is now discouraged in the colocalization literature (interpretation ambiguity) in favor of the simpler %-area-above-threshold approach — prefer that over Manders for this use case. |
| Registration speedup for BigWarp (tissue-mask / reduced-landmark middle ground) | Directly targets the stated pain point — cutting 5–15 min/section of manual BigWarp landmark placement is the largest per-section labor cost in the pipeline and the main blocker to running full series routinely | MEDIUM-HIGH | ABBA's own automated affine+spline pass is not the bottleneck (completes in <1 min for 50-80 sections on an 8-core CPU); nearly all manual time is BigWarp landmark placement, which scales with the landmark-grid parameter (5-20 → 25-400 landmarks/section). Realistic middle ground per field practice: reduce landmark count on sections with strong anatomical contrast, and/or use a tissue-mask-cropped, *bounded* elastix pass to reduce background-pixel interference (the `crop_to_tissue.py` candidate already flagged in PROJECT.md) — general histology-registration literature confirms background/tissue masking as a standard speed technique. **Hard guardrail:** this must NOT reintroduce full unmasked Affine+Spline, which v1.0 already confirmed degrades results on this data (background pixels dominate the cost function) — any masked-elastix experiment needs the same per-section visual validation v1.0 used before being trusted across all 5 sections. |
| Imaging re-validation on new params (4 Z-planes, lower laser) | Confirms the v1.0 imaging-optimization notes actually transfer to a second acquisition session with different settings — protects against silently drifting detection quality when acquisition parameters change | MEDIUM | Depends on v1.0 `04-IMAGING-NOTES.md` (OPT-01/02/03) and the D-05 gate logic — re-lock detection ONLY if drift is actually detected, not by default. This is a validation gate, not new capability; scoped as a differentiator because it's the mechanism protecting the whole milestone's plausibility claims, not a routine step. |

### Anti-Features (Do Not Build This Milestone)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Full per-nucleus segmentation algorithm for DG/dense amygdala nuclei (3D boundary-tracing reconstruction, Cellpose/StarDist retraining) | Seems like the "correct" fix to the segmentation-failure problem, and is what some published methods do | High implementation cost; GPU-oriented tools (Cellpose) conflict with the CPU-only hard constraint; would consume an entire phase or more on its own. The project has already decided (Key Decision, PROJECT.md) that area-based is the documented exception, not a segmentation arms race | Ship the area-based %-area/IOD readout as the accepted parallel metric for compact-nuclei regions; defer true per-nucleus dense-segmentation research to a future milestone if it's ever needed |
| Full elastix Affine+Spline registration re-enabled for speed | Faster nominal registration time, and it's the ABBA "textbook" path | Already confirmed to degrade results without a tissue mask (background pixels dominate the cost function) — re-enabling it to save time trades correctness for speed, violating the project's registration-quality bar | Use a tissue-masked, bounded elastix pass or reduced BigWarp landmark count instead — speed up the manual step, don't reintroduce the failed automated step |
| Multi-animal group statistics / brain-wide statistical comparison in this milestone | Natural "next step" once one animal is aggregated, and BraiAn's stats tools support it out of the box | This milestone is explicitly single-animal (n=1); running group comparisons now would produce meaningless or pseudoreplicated stats with no second animal, contradicting the project's own convention (aggregate to animal level before ANY group comparison — there is no group yet) | Defer group comparison + multiple-comparison correction to the milestone that adds a second animal; this milestone stops at animal-level aggregation + point-cloud export |
| Treating area-based readout as an authoritative replacement for nucleus counts in ANY region | Tempting simplification — one method everywhere is simpler to report | Loses the correctness of validated per-cell colocalization in every region where nuclei ARE separable (i.e., most of the brain); area-based is a known-lossy proxy that cannot itself confirm nucleus-anchored double-positivity | Keep area-based strictly additive/parallel per the project's own Key Decision — reported alongside, never substituting for, nucleus counts; scope it ONLY to regions where segmentation demonstrably fails (DG granule layer confirmed by literature; LA/BA sub-nuclei only if confirmed empirically on this data — see Gaps) |

---

## Feature Dependencies

```
Multi-scene MIP conversion (v1.1)
    └──requires──> v1.0 czi_mip.py (channel-order fix, OME-XML calibration)

Registration speedup (BigWarp/tissue-mask)
    └──requires──> v1.0 confirmed no-Affine+Spline-without-mask decision (must not violate it)
    └──enhances──> Multi-section throughput (makes 5-section registration practical time-wise)

LA/BA nucleus-anchored classification
    └──requires──> v1.0 locked detection params (02-LOCK-RECORD.md)
    └──requires──> v1.0 nucleus-anchored colocalization method (02_detect_classify.groovy)
    └──requires──> ABBA-RoiSet region labeling with CR-01 leaf-region fix

Area-based density readout (DG test case)
    └──requires──> DAPI+ region mask (from existing detection step, not a new detector)
    └──conflicts-if-misused──> nucleus-anchored colocalization rule (must stay additive, never substitute)
    └──enhances──> Brain-wide readiness (this milestone's DG test proves the reusable pattern before scaling)

Brain-wide region-labeling validation
    └──requires──> v1.0 Phase-4 CR-01 fix (is_leaf geometric containment)
    └──requires──> All 5 sections registered + classified first

Section→animal aggregation (BraiAnalyse)
    └──requires──> Correct per-section region-labeled summary tables (i.e., brain-wide validation passing)
    └──requires──> braian conda env + BraiAnalyse library (already installed, first real use)

Full per-region micron export → brainrender point cloud
    └──requires──> Section→animal aggregation OR at minimum all sections classified + region-labeled
    └──requires──> v1.0 micron-coordinate export convention (CCFv3 space, verified against OME-XML PhysicalSizeX)

Imaging re-validation (new params)
    └──requires──> v1.0 04-IMAGING-NOTES.md (OPT-01/02/03) as baseline for comparison
    └──gates──> Whether detection re-lock is needed before LA/BA classification proceeds
```

### Dependency Notes

- **LA/BA classification and the area-based readout both require v1.0's locked detection + colocalization machinery** — neither is a from-scratch build; the risk is entirely in whether the amygdala's tissue characteristics (some sub-nuclei may pack more densely than hippocampal CA1/CA3) break the nucleus-anchored assumption, which is exactly what the area-based readout exists to catch and handle.
- **Section→animal aggregation strictly requires brain-wide region-labeling validation to have passed first** — feeding BraiAnalyse mislabeled per-section tables (e.g., a CR-01-style `grey`-rollup recurrence across 5 sections instead of 1) would corrupt the animal-level numbers in a way that's much harder to catch after aggregation than before it.
- **Registration speedup must not reintroduce the Affine+Spline-without-mask failure mode** — the speedup feature and the "no Affine+Spline" decision must be reconciled by scoping any masked-elastix experiment carefully and validating visually (as v1.0 did) before trusting it across 5 sections.
- **Area-based readout enhances future brain-wide scaling** but must remain parallel/additive to nucleus counts per the project's own recorded Key Decision — flag this explicitly everywhere it's reported.

---

## MVP Definition (for this milestone)

### Launch With (v1.1 core)

- [ ] Multi-scene MIP conversion — without this nothing else in the milestone can start
- [ ] LA/BA nucleus-anchored TdT+/Fos+/Double+ classification — the milestone's primary readout and core value
- [ ] Brain-wide region-labeling validation across all 5 sections — protects every downstream number
- [ ] Section→animal aggregation — the milestone's headline deliverable (first animal-level roll-up)
- [ ] Full per-region micron export — completes the pipeline to a brainrender-ready artifact

### Add After Validation (rest of v1.1)

- [ ] Area-based density readout for DG (and amygdala sub-nuclei if segmentation fails there too) — build once nucleus-anchored classification confirms where it's actually needed; don't build speculatively for regions that turn out to segment fine
- [ ] Registration speedup — nice-to-have efficiency win; if BigWarp effort proves acceptable on 5 sections, this can slip to a later milestone without blocking the amygdala-engram result
- [ ] Imaging re-validation — only re-lock detection params if D-05 drift is actually observed; otherwise this is a quick confirmatory pass, not a build

### Future Consideration (v1.2+)

- [ ] Brain-wide segmentation-failure catalog (which other regions besides DG need the area-based exception) — defer until more animals/regions are processed
- [ ] Multi-animal group statistics with multiple-comparison correction — needs a second animal
- [ ] brainrender 3D visualization / final figures — this milestone only produces the export the figure would consume

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|----------------------|----------|
| Multi-scene MIP conversion | HIGH | LOW | P1 |
| LA/BA nucleus-anchored classification | HIGH | MEDIUM | P1 |
| Brain-wide region-labeling validation | HIGH | LOW | P1 |
| Section→animal aggregation | HIGH | MEDIUM | P1 |
| Full per-region micron export | HIGH | LOW | P1 |
| Area-based density readout (DG) | MEDIUM-HIGH | HIGH | P2 |
| Registration speedup (BigWarp) | MEDIUM | MEDIUM-HIGH | P2 |
| Imaging re-validation | MEDIUM | MEDIUM | P2 |

---

## Domain-Specific Findings (Answers to Research Questions)

### 1. Area-based vs. nucleus-based quantification in dense regions

The field has no single standardized "double-positive area fraction" statistic; accepted approaches, in rough order of how commonly they appear in IEG/engram imaging papers:

1. **Percent area above threshold** — binarize each marker channel by intensity threshold, restrict to a region-of-interest mask (ideally a DAPI+ mask so background outside cells is excluded), report % of ROI area covered by signal. This is the most commonly cited fallback specifically for dentate gyrus c-fos quantification, and is the simplest to implement, reusing the project's existing threshold logic (robust median + k·MAD cut, already locked in v1.0).
2. **Integrated optical density (IOD)** — sum of pixel intensities within the ROI; used interchangeably with %area in some IHC literature, gives an intensity-weighted rather than binary-area readout.
3. **Pixel-level co-occurrence of two thresholded channels** ("area of TdT+ mask ∩ Fos+ mask" within the DAPI+ ROI) as a double-positive-area proxy — the closest area-based analogue to a "double-positive fraction," but it is fundamentally a different statistic from per-cell double-positive fraction and will not agree numerically with nucleus-anchored double+ counts even in regions where both can be computed.
4. **Manders' colocalization coefficients (M1/M2)** exist as a generic pixel-based co-localization metric but are increasingly discouraged in the colocalization literature (interpretation ambiguity, per a 2021 Cytometry Part A methods critique); prefer thresholded %-area methods over Manders overlap coefficient specifically if a single number is needed.

**Concrete recommendation for this milestone:** implement (1) percent-area-above-threshold, computed per-channel within a DAPI+ region mask, reused directly from the already-locked detection thresholds — lowest-risk, most literature-precedented, and cheapest to implement. Report it as a distinct output column (e.g. `pct_area_TdT`, `pct_area_Fos`, `pct_area_coexpr`) alongside, never merged into, the nucleus-anchored `%double+` column. State explicitly in output/report text that area-based double-positive is NOT equivalent to per-cell double-positive and is only valid as a relative/within-region comparison, not an absolute cell-count estimate.

**Segmentation-failure trigger — when to use area-based vs nucleus-based:** DG granule cell layer nuclei are densely packed enough to visually overlap in standard imaging, a widely acknowledged problem in the field (specialized 3D boundary-tracing reconstruction algorithms exist specifically because standard threshold/watershed segmentation fails there). This is exactly the failure mode the project's own Key Decision anticipates. Whether LA/BA amygdala sub-nuclei hit the same failure mode is NOT established in the literature surfaced this pass — treat it as an open empirical question to check visually/quantitatively on the actual wBA1-3 sections before assuming amygdala needs the area-based exception too (see Gaps below).

### 2. TRAP2 LA/BA amygdala engram plausibility bands

**Confidence: LOW** — only one closely-matched paper surfaced with hard numbers (anterior BLA, TRAP2×Ai14, fear conditioning + remote recall; Chen et al., PMC10174320), and it reports absolute counts per imaging field rather than %DAPI+ fractions, so it doesn't map cleanly onto this project's per-region-density style of reporting. Use these only as an order-of-magnitude sanity check, not a hard pass/fail gate — consistent with how the project already treats VAL-01 (a findings record, not a pass/fail gate).

- **Reactivation fraction (Double+ / TdT+)**: ~20% in a context-only (non-fear) control condition, ~30% in a fear-conditioned condition, at a remote (3-week) recall timepoint. Single most citable number: **expect roughly 20-35% of TdT+ (TRAPed) cells to be Fos+ at recall in fear-relevant amygdala circuitry**, with fear/salient conditioning trending higher than neutral-context controls.
- TdT+ and Fos+ absolute counts scaled up ~40-45% comparing fear vs. context-only conditions in that study (110 vs 77 TdT+; 128 vs 83 Fos+) — i.e., a real behavioral effect produces a modest (30-50%) increase in ensemble size and overlap fraction, not a multi-fold jump. Sanity-check: if wBA1-3's TdT+ or Fos+ fraction in LA/BA is wildly higher (e.g., >2x this study's relative increase) or near-zero, suspect an imaging/threshold artifact before treating it as biology.
- ~70-80% of TRAPed BLA neurons are CaMKII+ (glutamatergic) in that study — not directly checkable in this pipeline (no CaMKII channel), but useful context: BLA/LA engram ensembles are expected to be excitatory-neuron-dominated, consistent with the hippocampal CA1/CA3 plausibility bands already validated in v1.0 (Phase 4).
- **No explicit chance-level statistical test was reported in the one paper found.** The broader engram-quantification literature (optogenetic reactivation studies) uses a standard chance-overlap formula: `expected_double+ = (marker1+/DAPI+) × (marker2+/DAPI+) × DAPI+_count`, then compares the observed double+ count to this expectation (chi-square or z-test) to claim above-chance overlap. **Recommend applying this same chance-level check to the wBA1-3 LA/BA numbers** as an additional plausibility gate beyond the raw %double+ figure — a cheap, standard, and well-precedented statistical sanity check that strengthens the milestone's "biologically plausible" claim.
- No independent TdT+/DAPI+ or Fos+/DAPI+ percentage-of-total-nuclei bands were found for LA/BA specifically (the source paper reports counts, not %DAPI+). **Gap:** cross-check against this project's own v1.0 hippocampal bands (TdT+ ~3.5%, Fos+ ~20%, Double+/TdT+ ~0.45 on M3 CA1/CA3/DG) as the nearest same-pipeline precedent, since amygdala-specific %DAPI+ bands were not found this pass. Given amygdala is a canonically fear-responsive structure and this design is fear-conditioning-adjacent, a TdT+ fraction of DAPI+ in the low single digits to ~10%, and a Double+/TdT+ ratio in the 0.2-0.35 range, is the best available first-pass expectation — treat as a working hypothesis, not a validated band, until the seed paper or additional literature is checked directly.

### 3. Registration workflow ergonomics

- ABBA's own automated stage (affine + spline concatenation) is not the bottleneck: **50-80 sections register in under 1 minute on an 8-core CPU** — this box's i9-9900K comfortably exceeds that reference hardware.
- The actual per-section manual-effort cost is **BigWarp landmark placement**, an explicitly tunable dial: ABBA's own guidance recommends a landmark-grid parameter between 5 and 20, producing 25 to 400 total landmarks per section, placed on white-matter boundaries and DAPI-density contrast. More landmarks = more precision but more manual time; this is the parameter to reduce against this project's stated "cut BigWarp from 5-15 min/section" goal.
- Semi-automated middle grounds labs actually use (per Image.sc community discussion on "how to reduce manual landmark work in ABBA"): reducing landmark density on sections with clear anatomical contrast (fewer, easier-to-place landmarks needed), and cropping/masking to tissue extent before any elastix-based refinement pass to reduce background-pixel interference — consistent with why this project's own tissue-mask + elastix candidate (`crop_to_tissue.py`) is reasonable, since general histology-registration literature separately confirms background/tissue masking as a standard technique for both speed and accuracy in elastix-based workflows.
- **Caveat carried forward from v1.0's own decision:** full Affine+Spline registration was already confirmed to degrade results on this project's data without a tissue mask (background pixels dominate the optimization). Any registration-speedup experiment this milestone must be validated visually per-section (as v1.0 did) before being trusted across all 5 sections — do not assume a masked-elastix pass is safe by default just because the general literature supports masking elsewhere.

### 4. Section→animal aggregation conventions

- The standard, purpose-built tool for this in the ABBA/QuPath ecosystem is **BraiAnalyse** (Python, already installed in this project's `braian` conda env) — this is the field's de facto answer for "how do labs aggregate whole-brain section data to the animal level," not a bespoke script the project needs to invent.
- BraiAnalyse's `braian.stats` submodule is explicitly described as providing prebuilt **density calculations, percentage metrics, fold-change, and marker-overlap indices**, and is designed to chain aggregation from single sections → single animals → single groups while keeping every value attributed to the atlas region hierarchy (i.e., aggregation is done per-region, not by flattening all cells together first).
- **Gap:** the exact aggregation math (sum vs. mean across sections, whether region volume/area is used to normalize density, how missing/excluded sections are handled) was not resolvable from the public docs excerpt available this pass — this needs a direct read of the BraiAnalyse API reference (`braian.stats` module docs) or a short example notebook before implementation, since the project's own stats convention (no pseudoreplication, principled a priori exclusion) must be reconciled with however BraiAnalyse defaults handle these cases. Do not assume BraiAnalyse's defaults already satisfy the project's stats conventions — verify explicitly during implementation.
- This is the first real (non-installation-test) use of BraiAnalyse in the project, so budget for this being an integration-risk item even though the library itself is mature and purpose-built (it's the same library used in the ABBA+BraiAn Cell Reports 2025 paper this pipeline is modeled on).

---

## Sources

- [Anterior basolateral amygdala neurons comprise a remote fear memory engram (PMC10174320)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10174320/) — LOW confidence (websearch/webfetch synthesis, not a first-party PDF read); primary quantitative source for LA/BA reactivation fractions
- [ABBA+BraiAn, an integrated suite for whole-brain mapping (Cell Reports, 2025)](https://www.cell.com/cell-reports/fulltext/S2211-1247(25)00647-3) — LOW confidence; registration timing and BraiAn architecture
- [ABBA Documentation — registration tutorial](https://abba-documentation.readthedocs.io/en/latest/tutorial/2_registration.html) — LOW confidence; BigWarp landmark-count guidance
- [How to reduce manual landmark work in ABBA registration — Image.sc Forum](https://forum.image.sc/t/how-to-reduce-manual-landmark-work-in-abba-registration-of-whole-mouse-brain-sections/121085) — LOW confidence; community practice on landmark reduction
- [BraiAn for QuPath — Codeberg Pages](https://silvalab.codeberg.page/BraiAn/braian-qupath/) and [BraiAnalyse (braian-python)](https://silvalab.codeberg.page/BraiAn/braian-python/) — LOW confidence; aggregation feature list (exact math not resolved, flagged as gap)
- [Efficient cytoplasmic cell quantification using a semi-automated FIJI-based tool (Sci Reports / PMC12304148)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12304148/) — LOW confidence; area/semi-automated dense-tissue quantification precedent
- [Quantifying colocalization: the case for discarding the Manders overlap coefficient (Cytometry Part A, 2021)](https://onlinelibrary.wiley.com/doi/full/10.1002/cyto.a.24336) — LOW-MEDIUM confidence (peer-reviewed methods critique); basis for preferring %-area-above-threshold over the Manders overlap coefficient
- [Colocalization metrics — scikit-image docs](https://scikit-image.org/docs/stable/auto_examples/applications/plot_colocalization_metrics.html) — LOW confidence; general colocalization-metric background
- Dentate gyrus segmentation-difficulty and c-fos %-area quantification: synthesized from multiple websearch results (eLife 101428 / PMC11370351 series on DG granule cell segmentation challenges; general c-fos %-area IHC quantification literature) — LOW confidence, no single authoritative source read in full
- bioRxiv 2024.09.16.611953 (seed paper for this project's detection parameters, per CLAUDE.md) — NOT re-read directly this pass; recommended as a first stop for amygdala-specific plausibility bands before locking thresholds, since it was not surfaced with new detail beyond what's already in the project's v1.0 record

**Overall confidence caveat:** This research pass used built-in WebSearch/WebFetch only (no context7, exa, tavily, or firecrawl available in this environment/config this run) — treat every quantitative band above as LOW confidence and a starting hypothesis. Before locking any plausibility gate or aggregation implementation for v1.1, prioritize a direct read of (a) the bioRxiv 2024.09.16.611953 seed paper's amygdala-relevant supplementary data if present, and (b) the BraiAnalyse API reference / example notebooks for exact aggregation math.

---
*Feature research for: Neuroscience whole-brain mapping / TRAP2 engram quantification*
*Researched: 2026-07-17*
