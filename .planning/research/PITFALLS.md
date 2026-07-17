# Domain Pitfalls: v1.1 First Full-Series Run (LA/BA Amygdala, wBA1-3)

**Domain:** Scaling a validated single-section TRAP2/Airyscan pipeline (QuPath + ABBA + BraiAn) to a
5-section series on a new animal, new region (amygdala LA/BA vs. v1.0 hippocampus), and new imaging
params (4 Z-planes, lower laser)
**Researched:** 2026-07-17
**Confidence:** MEDIUM — HIGH-confidence findings are drawn directly from this project's own commit
history, debug logs, and code review (`04-REVIEW.md` CR-01, `d05-threshold-all-negative.md`,
`02-LOCK-RECORD.md`); LOW-confidence findings are general domain knowledge from unverified web
search (Allen ontology structure, aicspylibczi scene-indexing behavior, general
imaging/quantification literature) and are flagged as such inline.

This file assumes the reader already has `.planning/research/PITFALLS.md`'s v1.0 predecessor content
in mind (TdT compartment, channel-name mismatch, duplicate ROI loads, proximity colocalization, etc.
— all still binding constraints, not repeated here). This document is additive: it covers what is
**new** at v1.1's scale-up and feature set. Ordered so **silent-count-corruption risks come first**.

---

## Critical Pitfalls

Mistakes that produce plausible-looking but wrong cell counts — and, at series scale, are much
harder to catch by eye than they were on one section.

---

### Pitfall 1: The CR-01 region-labeling fix (smallest-area leaf) was validated on laminar hippocampus — amygdala nuclei are not laminar and may defeat the same heuristic differently

**What goes wrong:** v1.0's Phase-4 code review found that QuPath/ABBA annotation nesting is not
reliable, and fixed per-cell region attribution to "smallest-area containing region" instead of
"first match" / "child-annotation emptiness" (`04-REVIEW.md` CR-01, `29dbfdc`). That fix was
validated against hippocampal subfields (CA1/CA3/DG-mo, etc.) — compact, well-nested, laminar
cyto-architecture where a smaller region genuinely nests inside a larger one almost everywhere. The
basolateral amygdala complex (BLA, containing LA/BA) is architecturally different: BLA principal
neurons are **not organized into layers** the way cortex/hippocampus is `[LOW confidence, web]`, and
LA/BA/BMA are adjacent nuclei of broadly comparable size rather than a small nucleus cleanly nested
inside a much larger parent. The smallest-area heuristic assumes area is a reliable proxy for
ontology depth; that assumption is untested outside hippocampus and could produce a *different*
mis-attribution pattern — e.g., LA and BA boundary cells flip-flopping between the two nuclei based
on tiny area differences rather than true tissue identity, or amygdala cells still being swept into
a `grey`/`BLA`/`CTXsp` rollup if the ABBA-exported ROI set does not include LA/BA at full ontology
depth for this section's AP level.

**Why it happens:** CR-01 was fixed and verified against one region family. Nothing about the fix
generalizes automatically; the milestone's own "Brain-wide region-labeling validation" requirement
exists precisely because this has not yet been checked outside hippocampus, and the amygdala is the
first genuinely different cyto-architecture to test it against.

**Consequences:** LA+/TdT+/Fos+/Double+ counts — the milestone's **primary readout** — could be
silently mis-attributed between LA and BA, or absorbed into a BLA/grey rollup, exactly the failure
mode that inflated `grey` to 95,383 cells in v1.0 before the fix. Because the fix already looks
correct in code, there is no obvious signal that it needs re-validation for a new region family.

**Prevention:**
- Do not assume CR-01 "generalizes because it's the smallest-area fix now." Re-run the same audit
  performed in `04-REVIEW.md` (inspect the region-area TSV for `is_leaf` flags that disagree across
  hemispheres or across LA/BA, and check whether any amygdala cells are landing in `BLA`, `CTXsp`,
  or `grey`) on the first amygdala section before trusting counts on the rest of the series.
- Print the actual `region_label` value distribution for cells inside the drawn amygdala ROI on
  section 1; confirm it resolves to `LA`/`BA` acronyms specifically, not a parent grouping.
- Verify the ABBA-RoiSet export depth includes LA/BA as distinct leaf polygons (check the atlas
  ontology depth setting used at export time) — if ABBA exported only to the `BLA` or `CTXsp` level,
  no downstream Groovy fix can recover finer subdivision that was never exported.

**Warning signs:** A single amygdala AP section reporting cell counts under `BLA`, `grey`, or
`CTXsp` instead of `LA`/`BA`; LA and BA counts that look implausibly similar in shape/area to each
other (suggesting boundary noise rather than a true anatomical split); the region-area TSV showing
`is_leaf` disagreeing between hemispheres for any amygdala acronym (the exact CR-01 symptom).

**Phase to address:** Brain-wide region-labeling validation phase (extends Phase-4 CR-01 fix across
all 5 sections) — this must run and pass on an amygdala section specifically, not just re-confirm
the hippocampal result.

---

### Pitfall 2: The k=3 robust threshold seed (median + k·1.4826·MAD) was calibrated at the old laser power / Z-plane count — a 4-plane/lower-laser section is not guaranteed to reproduce the same separation

**What goes wrong:** v1.0's D-05 redesign (`d05-threshold-all-negative.md`) makes the Fos/TdT
positive threshold self-calibrating per section: `threshold = median + k·1.4826·MAD` on each
section's own local-background-subtracted measurement, k=3 locked as a series-ready seed. This
design is explicitly built to absorb **section-to-section brightness offset** drift (different
antibody penetration, position in cutting series, etc.) — it is *not* automatically proof against a
change in the underlying **signal-to-noise regime**. Lowering laser power reduces the number of
photons collected per pixel; by Poisson statistics, this widens the *relative* noise floor (shot
noise scales with √signal, not linearly), and it can also push more of the dim end of the
distribution down into camera read-noise/quantization territory. A median-and-MAD statistic
computed on a population with a fundamentally different noise character than the one k=3 was tuned
against is not guaranteed to reproduce the same effective sensitivity/specificity trade-off — it
could now call cells positive/negative at a different real intensity ratio than it did at the
original laser power, even though the *code* runs unchanged and produces a plausible-looking,
non-empty threshold.

**Why it happens:** Robust/histogram-relative thresholding schemes are designed to normalize away
*linear scale* differences (brightness, gain, section thickness) — they do not know anything about
*where the seed constant (k) was validated* and will silently apply it to a differently-shaped
distribution without complaint. There is no equivalent of the D-05 empty-population tripwire for
"this section's noise regime differs from the one the seed was tuned on."

**Consequences:** Series-wide Fos+/TdT+/Double+ rates could shift systematically relative to v1.0's
hippocampus numbers for reasons that are pure imaging-parameter artifact, not biology — and because
the pipeline no longer crashes or reports NaN (that specific bug is fixed), this would look like a
normal, successful run.

**Prevention:**
- This is exactly why the milestone requirement text says "re-lock detection only on drift" (D-05
  gates) — treat that as load-bearing, not optional. Re-run the D-05 quality gates (nucleus-area
  peak, DAPI density, and — new for v1.1 — a check on the bg-sub distribution's separability/shape)
  on the first 4-plane/lower-laser section before trusting k=3 for the rest of the series.
- Explicitly compare the bg-sub histogram shape (spread, bimodality) between a v1.0 hippocampus
  section and the first v1.1 amygdala section, independent of the region difference, to isolate
  whether any distribution change is attributable to the imaging-parameter change.
- If drift is detected, re-sweep k (the seed's own doc already flags k=3 as "sweep 3–5 on this
  section, then lock" — that sweep step should be repeated at the new imaging settings, not assumed
  still-valid from the hippocampus sweep).

**Warning signs:** Whole-series Fos+/TdT+ rates that differ from v1.0's ~20%/~3.5% by a large,
uniform-looking margin with no clear regional/biological story; bg-sub distributions across sections
showing markedly different spread (MAD) at the new imaging settings vs. the v1.0 reference; k=3
producing a threshold that sits implausibly close to zero or to the local maximum (loses
discriminating power at reduced signal).

**Phase to address:** Imaging re-validation phase (new 4-plane/lower-laser params, D-05 gates) —
must run before LA/BA classification, and must gate on distribution *shape*, not just "does it
produce a finite non-empty threshold."

---

### Pitfall 3: Fewer Z-planes changes what the MIP actually captures — under-projection can systematically dim exactly the cells the robust threshold is supposed to separate

**What goes wrong:** A maximum-intensity projection over fewer optical sections has a lower chance
of ever sampling a given nucleus's true peak-focus plane. If the new 4-plane acquisition covers a
narrower Z-range than the 6-plane/3-plane-MIP scheme validated in v1.0 (`04-IMAGING-NOTES.md`'s
OPT-01 plateau argument was explicitly scoped to "3 planes at the 2.0 µm step," not fewer, and even
that was flagged as a 2-of-3 partial confirmation, not a fully closed empirical result), some
in-focus signal for cells sitting near the edge of the sampled Z-range may simply not appear in any
of the 4 planes. Reducing planes also interacts with a real prior failure mode
(`hybrid_imaging_dapi.md`, memory): DAPI over-projection from MIP-ing too many/wrong planes produced
"blobs" from saturation — the fix there was a **single-plane DAPI + MIP-for-markers** hybrid
strategy. A naive "just MIP all 4 planes for every channel including DAPI" approach at the new
settings could reintroduce that exact artifact if the new acquisition's DAPI channel is close to
saturating on any plane.

**Why it happens:** Z-plane count and MIP strategy were tuned once (v1.0, hippocampus, 6-plane
acquisition) and are being changed for v1.1 (4-plane, lower laser) without the same plateau
comparison having been re-run at the new settings. The OPT-01 finding was explicitly provisional
("this recommendation needs empirical confirmation... a full three-way empirical confirmation...is
deferred") — treating 4-plane MIP as automatically safe repeats the same untested assumption at a
different plane count.

**Consequences:** Systematically dimmer apparent nuclei/markers in sections/regions where true focus
sits outside the narrower sampled range, which then interacts with Pitfall 2 (threshold
recalibration) in a way that is hard to separate from genuine biological signal.

**Prevention:**
- Re-apply the OPT-01-style plateau check (compare DAPI/marker counts across whatever
  sub-range/hybrid variants are actually acquired at the new 4-plane setting) before trusting the
  4-plane MIP as equivalent in information content to the previously-validated 3-plane variant.
- Explicitly re-confirm the DAPI-channel single-plane-vs-MIP choice (per `hybrid_imaging_dapi.md`)
  at the new laser power — lower overall laser power changes where saturation risk sits, it does not
  eliminate the need to check for it.
- Visually inspect DAPI nucleus quality (blob-vs-sharp) on the first converted section before running
  detection at scale.

**Warning signs:** Nucleus-area distribution shifting noticeably from v1.0's [40,50) µm² peak
without a principled reason; visually "fuzzy" or merged DAPI blobs in the overlay; detected nucleus
count lower than expected for a comparably-sized field of view.

**Phase to address:** Imaging re-validation phase, before LA/BA classification is trusted.

---

### Pitfall 4: Multi-scene CZI scene→section mapping is not guaranteed to preserve physical/AP order — an off-by-one or shuffled scene mapping silently mislabels which section is which

**What goes wrong:** `czi_mip.py` was written and validated for a **single-scene** CZI. The v1.1
source file has **5 mosaic scenes** in one processed CZI, and the milestone requires extending the
script for **per-scene** MIP output. Two related risks: (1) `aicspylibczi`'s scene indexing (0- vs
1-based, and how it enumerates scenes relative to the physical layout on the slide) is not something
this codebase has exercised before, and off-by-one scene selection would silently swap which
physical section becomes "entry 1" vs "entry 2" in the QuPath project `[LOW confidence, web:
aicspylibczi's own issue tracker documents split-scene-file scene-index confusion and
differently-shaped-scene ROI pitfalls]`; (2) the project's own known bad artifact — the "merged 32
GB OME-TIFF... all scenes fused into one canvas, Z not projected... do not use it" — is direct,
in-project evidence that this exact class of error (scenes mixed/merged incorrectly) has already
happened once with this data and file. A section-order mixup does not crash anything; it produces 5
perfectly valid-looking MIP OME-TIFFs that are simply attached to the wrong AP position when later
handed to DeepSlice/ABBA.

**Why it happens:** `generate_mip()` in the canonical script currently assumes a single scene; adding
a scene loop is new code with no prior test coverage on this project (`CONCERNS.md` already flags
"No automated tests for any pipeline component" as a standing gap, and the channel-order bug is the
direct historical precedent for a silent, plausible-looking mis-mapping of this same kind).

**Consequences:** If scene 3's tissue is actually the most posterior section but gets written as
`M3_..._MIP_scene1.ome.tiff` (or whatever naming convention is chosen), DeepSlice's AP-position
estimate for "section 1" would be computed against the wrong physical tissue, and every downstream
artifact (registration, region counts, section→animal aggregation) inherits a wrong section identity
that is not visually obvious unless someone specifically compares tissue morphology per scene against
expected AP order.

**Prevention:**
- Print (and manually verify against the original ZEN/CZI thumbnail or scene overview) the physical
  scene bounding-box position for every scene before committing to a scene→section-number mapping.
- Name output files with the scene index embedded verbatim (e.g., `_scene{N}_MIP.ome.tiff`) rather
  than renumbering to an assumed AP order — let ABBA/DeepSlice determine AP order from content, do
  not pre-bake an assumption into the filename.
- Add an explicit assertion/print step (per-scene channel min/max/mean, tile count, physical
  bounding box) immediately after conversion, mirroring the `CONCERNS.md`-recommended output
  validation that the single-scene script has always lacked.
- Keep the known-bad merged 32 GB canvas file physically out of any directory or glob pattern that
  downstream scripts might pick up by accident (rename/move it, don't just document "don't use it").

**Warning signs:** Section count in the QuPath project not matching the expected 5; any two "section"
entries showing implausibly similar or implausibly dissimilar tissue morphology; DeepSlice AP
estimates for consecutive "sections" not forming a monotonic series.

**Phase to address:** Multi-scene MIP conversion phase (the very first phase touching new code this
milestone) — must include a manual scene-identity verification step before any section proceeds to
registration.

---

### Pitfall 5: Damaged/folded tissue in a 5-section series is a new failure mode v1.0 never had to handle — registration and detection will not error on it, they will just quietly produce wrong local counts

**What goes wrong:** v1.0 validated exactly one hand-picked, visually-good section. A 5-section
series pulled from a real animal is far more likely to include at least one section with a fold,
tear, bubble, or partial tissue loss — common vibratome artifacts. Neither ABBA registration nor
BraiAnDetect nor the classification script has any built-in check for tissue integrity: a folded
region will register as if it were flat tissue (the fold's doubled/compressed thickness reads as an
intensity/area anomaly, not an error), producing locally implausible densities or spurious ROI
boundaries that are easy to miss if the operator only spot-checks the "clean" sections.

**Why it happens:** There is no automated tissue-QC step anywhere in this pipeline; every existing
quality gate (D-05 nucleus-area/density gates, VAL-01 bioplausibility checks) operates on
whole-section aggregates, which a single damaged local region can distort without moving the
aggregate very much (masking rather than surfacing the artifact) — or, conversely, can dominate the
aggregate metrics for a small section area.

**Consequences:** A folded region could locally double- or half-count nuclei, or attract a wildly
wrong ABBA-warped region boundary, contaminating that section's contribution to the animal-level
aggregate with no visible error anywhere in the pipeline's outputs.

**Prevention:**
- Visually screen all 5 sections for gross tissue damage (folds, tears, bubbles) before registration,
  as a discrete, documented step — not an implicit assumption folded into "ABBA registration quality
  is verified visually."
- Any section (or sub-region of a section) excluded for tissue-quality reasons must follow the
  project's existing rule: exclusion is **a priori and principled**, documented as a rule (e.g.,
  "exclude any section where >X% of the amygdala ROI area is visibly folded/torn"), not decided after
  seeing which sections give inconvenient numbers.
- If a section is partially usable (e.g., LA is fine but BA is folded), consider region-level rather
  than whole-section exclusion, explicitly documented per region per section.

**Warning signs:** A section's per-region nucleus density wildly outside the range of the other 4
sections for the same region; visibly doubled or compressed tissue thickness in the DAPI channel
overlay; ABBA region boundary snapping to an obviously wrong contour on one section only.

**Phase to address:** Registration speedup phase / LA/BA classification phase — tissue-quality
screening should be an explicit checklist item before registration begins on each of the 5 sections,
not an implicit assumption.

---

## Moderate Pitfalls

Mistakes that degrade counts or downstream comparability but are more likely to be caught before
they invalidate a finding.

---

### Pitfall 6: Area-based density readout, if not built on the same background-subtraction logic as the nucleus-anchored pipeline, will not be comparable to the counts it is meant to complement

**What goes wrong:** The milestone's generalizable area-based readout (DG as in-section test case,
designed to be reusable brain-wide for compact-nuclei regions where per-nucleus segmentation fails)
computes coexpression as **% positive area over a defined DAPI+ mask**, not per-cell classification.
If this area-based measurement uses a different intensity-normalization strategy than the
nucleus-anchored pipeline's local-background-subtracted, robust-threshold design (e.g., a fixed
global threshold, or raw un-subtracted channel means), the two readouts will not be on comparable
footing even when reported side by side for the same tissue — one will be far more sensitive to
regional autofluorescence, TdTomato bleed-through into the Fos channel, or section-to-section
brightness drift than the other. General fluorescence-quantification literature confirms this is a
known, generic risk: percentage-area measures are explicitly favored *because* they are less
sensitive to inter-experiment intensity variation than raw intensities `[LOW confidence, web]` — but
that only holds if the threshold defining "positive area" is itself derived consistently (e.g.,
per-section relative to local background), not fixed absolutely.

**Why it happens:** Building a second, parallel quantification method is easy to treat as
independent scope from the first — but for the two numbers to ever be placed in the same table (the
milestone's stated goal: "additive/parallel to nucleus counts"), they need a shared normalization
philosophy, or an explicit crosswalk/validation step showing they agree in overlapping test regions.

**Consequences:** A brain-wide reader comparing "DG area-based Fos+% " to "CA1 nucleus-based Fos+%"
in a later milestone could draw a false conclusion about a real regional difference that is actually
a methodology artifact between the two readout types.

**Prevention:**
- Reuse the same local-background-subtraction closure (or an area-equivalent of it — e.g., a
  per-section local-background estimate over the same DAPI+ mask) for the area-based readout, rather
  than inventing an independent normalization.
- Explicitly define "DAPI+ area" with a documented, reproducible rule (e.g., Otsu on the DAPI channel
  within the ROI, or a relative-to-local-background cutoff consistent with the nuclear detection
  pipeline's own DAPI channel handling) — not an arbitrary fixed intensity cutoff.
- Run a sanity crosswalk on the one region where both methods can be computed (e.g., compare DG-mo's
  nucleus-based Fos+ rate against an area-based readout computed on the same DG-mo tissue) to confirm
  the two methods land in the same ballpark before trusting the area-based numbers elsewhere.

**Warning signs:** Area-based Fos+/TdT+ percentages that look wildly different in scale or direction
from the nucleus-based rate in an adjacent, comparably-classified subregion; area-based readout
tracking known autofluorescent regions (e.g., SSp, per v1.0's VAL-01 finding) the same way the
nucleus-based pipeline was shown to (before its own background-subtraction fix suppressed it).

**Phase to address:** Generalizable area-based density readout phase.

---

### Pitfall 7: The compact-nuclei exception is scoped to genuinely inseparable regions (DG-sg) — treating it as a fallback whenever per-nucleus detection "looks noisy" anywhere else quietly abandons the nucleus-anchored rule this project treats as non-negotiable

**What goes wrong:** The project's own key-decisions log frames the area-based readout as "a
documented, generalizable exception to nucleus-anchored colocalization" specifically because DG-mo/
DG-sg-style granule packing defeats per-nucleus segmentation (v1.0's own D-04 visual gate: "DG
granule layer not per-cell separable (expected) → density-only"). If the area-based method is
available and "reusable brain-wide," there is a real risk in later use (this milestone or beyond)
that it gets reached for whenever a region's detection *looks* messy for some other reason (e.g.,
sigma mistuned, imaging drift, folded tissue) rather than because that region is genuinely,
structurally non-separable at this NA/resolution the way DG-sg is.

**Why it happens:** Having a documented, sanctioned fallback method makes it tempting to use it as a
patch for any detection-quality problem, which quietly erodes the nucleus-anchored-only constraint
this project has treated as a hard rule since v1.0.

**Prevention:**
- Require an explicit, visually-confirmed trigger before applying the area-based method to any new
  region — the same kind of confirmation DG-sg received in Phase 2 (D-04: "confirmed by researcher"
  visual check that nuclei genuinely cannot be separated), not "the threshold looked off."
- Document each region's designation (nucleus-anchored vs. area-based) as a locked decision with its
  own rationale, the same way DG-sg's exclusion is documented, rather than leaving it as an
  ad-hoc per-run choice.

**Warning signs:** Area-based readout being invoked for a region where per-nucleus separability was
never explicitly visually checked; the set of "area-based" regions growing without a corresponding
documented visual-confirmation entry for each one.

**Phase to address:** Generalizable area-based density readout phase; carried forward as a standing
rule for any future brain-wide application.

---

### Pitfall 8: A single global BraiAn.yml / k=3 seed applied across 5 sections can mask a bad section instead of flagging it

**What goes wrong:** v1.0 locked one global `BraiAn.yml` (histogram-relative detection config) and
one global robust-threshold seed (k=3), explicitly chosen to be "series-scalable" and
"drift-monitored via SERIES-02." That monitoring step (SERIES-02) is referenced but was never
exercised against a real multi-section series before v1.1 — it existed only as a name in the v1.0
decision log. Applying one global config uniformly across 5 sections is the right default, but
without an actual per-section drift check running and being inspected, a section that is genuinely
different (badly registered, damaged tissue, atypical laser drift) will simply get the same
threshold as everyone else and produce a number that looks superficially fine.

**Why it happens:** "One global config, monitored for drift" was designed and named in v1.0 but the
monitoring mechanism itself is unbuilt/unexercised — it's easy to carry forward the *decision*
("global config is right") without carrying forward the *monitoring obligation* that decision was
conditioned on.

**Prevention:**
- Actually run and inspect a per-section drift comparison (e.g., bg-sub distribution shape, median,
  MAD for each of the 5 sections plotted or tabulated side by side) before accepting all 5 sections'
  classifications as comparable.
- Treat SERIES-02 as a concrete deliverable of this milestone (its own review step), not an inherited
  assumption.

**Warning signs:** One section's Fos+/TdT+ rate is an outlier relative to the other four with no
corresponding regional/biological story; bg-sub median/MAD for one section differing sharply from
the rest.

**Phase to address:** Imaging re-validation phase / LA/BA classification phase (whichever owns
running detection across all 5 sections).

---

### Pitfall 9: Section→animal aggregation with only 5 sections and uneven per-region representation risks a different flavor of pseudoreplication than the classic "sections as independent n" mistake

**What goes wrong:** The standing rule (aggregate to animal level, never treat sections as
independent n) is already documented and understood for *between-animal* comparisons. This milestone
is the **first real exercise** of that aggregation step (BraiAnalyse roll-up, 5 sections → 1 animal),
and a new, more subtle risk appears even within a single animal: if LA/BA (or specific subnuclei) are
only clearly present/well-registered in 3 of the 5 sections (a realistic scenario at a 5-section
AP span), a naive mean-of-sections aggregate implicitly treats "region present or absent" the same
as "region present with zero cells," or silently drops sections from the average without recording
why — either way distorting the animal-level number in a way that is not visible unless someone
checks per-section region coverage.

**Why it happens:** BraiAn's aggregation tooling is being exercised for the first time on real data
this milestone; there is no established local pattern yet for how this project handles
partial-region-coverage across a short series.

**Prevention:**
- Before aggregating, tabulate which of the 5 sections actually contain each amygdala subregion (LA,
  BA) with a valid ROI area — do not assume all 5 contribute equally.
- Use BraiAn's area-weighted aggregation (density-weighted by region area per section) rather than a
  flat per-section mean, and document explicitly which sections contributed to each region's
  animal-level number.
- Any section dropped from a given region's aggregate (e.g., because that AP level does not contain
  LA) must be dropped for a documented anatomical reason, not a convenience/outlier reason.

**Warning signs:** Animal-level region density that swings drastically depending on which sections
are included; a region's "n sections contributing" count not matching the expectation for its known
AP extent.

**Phase to address:** Section→animal aggregation phase (BraiAnalyse roll-up).

---

### Pitfall 10: Micron-coordinate sanity range from v1.0 (hippocampus) does not transfer to amygdala sections — a wrong-but-plausible-looking range check would miss a real mm/µm bug

**What goes wrong:** v1.0's coordinate-export sanity check printed a handful of `Atlas_X` values and
confirmed they fell in a hippocampus-specific expected range (~5,000–10,000 µm). The amygdala sits at
a different AP/DV/ML position in the CCFv3 volume. If this milestone's export step reuses the same
hard-coded expected-range comment/check without recomputing it for the amygdala's actual coordinate
neighborhood, a genuine mm-vs-µm scaling bug (the same class of error already catalogued in the v1.0
pitfalls doc, Pitfall 8) could produce numbers that fail a stale hippocampus-shaped sanity check
non-obviously, or — worse — pass a check that was never actually recalibrated for the new region and
therefore isn't checking anything meaningful.

**Why it happens:** Copy-forward of a validated sanity check without re-deriving its expected bounds
for a genuinely different anatomical location is an easy shortcut that looks like reuse of
already-validated code.

**Prevention:**
- Recompute the expected micron-range for the amygdala's CCFv3 position specifically (from the Allen
  atlas reference, not copied from the hippocampus check) before relying on the sanity print.
- Keep the "multiply by 1000 if values look like mm" check itself (that part is location-independent),
  but do not reuse the hippocampus's specific numeric bounds as if they generalize.

**Warning signs:** Sanity-check comment/range in the export script still reading the v1.0
hippocampus-specific numbers; brainrender point cloud for amygdala cells landing outside the expected
CCFv3 amygdala neighborhood.

**Phase to address:** Full per-atlas-region micron export phase.

---

## Minor Pitfalls

Issues that are easy to detect and fix but worth flagging so they are checked deliberately rather
than assumed.

---

### Pitfall 11: LA/BA boundary precision under the locked DeepSlice-only (no Affine/Spline) registration workflow may be coarser than hippocampal subfield boundaries could tolerate

**What goes wrong:** v1.0 locked "DeepSlice → manual angle → export, no Affine/Spline" because
elastix degrades without a tissue mask. That workflow's residual registration error was acceptable
for hippocampal subfields, which are relatively large, distinctively shaped structures. LA and BA are
smaller, adjacent nuclei with a less visually distinctive boundary between them; the same residual
registration error that was fine for CA1-vs-DG might land closer to the LA/BA border, increasing the
chance that this milestone's own registration-speedup research (tissue-mask elastix as a candidate)
is worth prioritizing specifically because the new region is more boundary-sensitive, not just for
speed.

**Prevention:** Visually confirm the ABBA-warped LA/BA boundary against a recognizable anatomical
landmark (e.g., the external capsule separating BLA from the overlying cortex) on at least one
section before trusting per-nucleus LA-vs-BA assignment; if the tissue-mask-elastix candidate is
adopted, validate it improves boundary precision specifically at the LA/BA border, not just overall
registration speed.

**Phase to address:** Registration speedup phase.

---

### Pitfall 12: `crop_to_tissue.py` (tissue-mask candidate) was built for hippocampal tissue framing — verify it behaves the same on amygdala-containing fields of view before relying on it for elastix

**What goes wrong:** The quick-task tissue-mask auto-crop tool referenced as a registration-speedup
candidate was authored against hippocampus data. Amygdala-containing sections may have a different
tissue-to-background ratio, shape, or ventricle/fiber-tract proximity that the crop heuristic was
never tested against.

**Prevention:** Run and visually verify the crop output on an amygdala section before adopting it as
the mask source for any elastix step in this milestone.

**Phase to address:** Registration speedup phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Reusing v1.0's hippocampus-specific micron sanity-check numbers for amygdala export | Saves a few minutes of re-deriving expected ranges | A real unit bug could pass/fail the check for the wrong reason (Pitfall 10) | Never — re-derive per region, it's cheap |
| Applying k=3 threshold seed to the new imaging params without re-sweeping | Faster path to a working classification run | Silent, systematic shift in Fos+/TdT+ rates attributable to imaging change, not biology (Pitfall 2) | Only if the D-05 gates are re-run and shown stable at the new settings first |
| Treating the area-based readout as available for any "noisy" region | Quick workaround when nucleus detection looks messy | Erodes the nucleus-anchored-only rule project-wide (Pitfall 7) | Never without an explicit, documented visual non-separability confirmation |
| Skipping a manual scene-identity check on the multi-scene CZI conversion | Faster conversion | Section identity swap silently corrupts AP order for the whole series (Pitfall 4) | Never — this project has already hit exactly this class of bug once (merged-canvas file) |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|-------------------|
| aicspylibczi multi-scene read | Assuming scene index order matches physical/AP order on the slide `[LOW confidence, web]` | Verify each scene's bounding box/thumbnail against the known physical layout before assigning section numbers |
| ABBA ROI export depth for amygdala | Exporting only to a `BLA`/`CTXsp` ontology depth, expecting Groovy region-labeling to recover LA/BA later | Confirm export depth includes LA/BA as distinct leaf polygons before running any detection |
| BraiAn aggregation across 5 sections | Flat mean-of-sections ignoring per-region area coverage | Use area-weighted aggregation; document which sections contribute to each region |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all 5 scenes' full-resolution mosaics into RAM at once for MIP generation | OOM or severe slowdown during multi-scene conversion | Process one scene at a time, release arrays between scenes (extends the existing running-max/tile-by-tile improvement already flagged in `CONCERNS.md`) | At 5 scenes × 4 Z × 3 channels, this is a larger single-run memory footprint than any prior single-scene conversion on this machine |

## "Looks Done But Isn't" Checklist

- [ ] **Multi-scene MIP conversion:** Often missing a manual scene-identity/AP-order verification —
      verify each scene's tissue morphology and bounding box against the expected physical layout,
      not just that 5 files were written.
- [ ] **Imaging re-validation:** Often missing a distribution-*shape* comparison (not just "threshold
      is finite and non-zero") — verify bg-sub spread/separability at the new settings, not only that
      D-05's old area/density gates still pass.
- [ ] **Brain-wide region-labeling validation:** Often missing an amygdala-specific re-check of the
      CR-01 fix — verify LA/BA resolve correctly, not just that hippocampus still does.
- [ ] **Area-based density readout:** Often missing a documented visual non-separability
      confirmation and a cross-method sanity comparison against the nucleus-based numbers on
      overlapping tissue — verify both before calling the readout "generalizable."
- [ ] **Section→animal aggregation:** Often missing an explicit per-region section-coverage tally —
      verify which of the 5 sections actually contribute to each region before trusting the
      animal-level number.
- [ ] **Micron export:** Often missing a region-specific (not copy-forwarded) sanity range — verify
      the expected coordinate neighborhood for amygdala, not hippocampus.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| CR-01-style mis-labeling recurs on amygdala (Pitfall 1) | MEDIUM | Re-run the Groovy export with an explicit LA/BA-only region filter and re-verify `is_leaf`/area-sort behavior; re-derive VAL-style metrics from the corrected export (same recovery pattern already exercised once in v1.0) |
| Scene mis-mapping discovered after registration (Pitfall 4) | HIGH | Re-derive the correct scene→section mapping from tissue morphology, re-run MIP conversion for affected scenes, and re-do registration for any section whose identity changed — cannot be patched downstream without re-registering |
| k=3 seed found invalid at new imaging settings (Pitfall 2) | MEDIUM | Re-sweep k on the bg-sub distribution at the new settings, re-lock, re-run classification (classification is fast relative to detection, per the Phase-3 design decision to keep detection and classification separate) |
| Area-based readout found inconsistent with nucleus-based counts (Pitfall 6) | LOW–MEDIUM | Recompute the area-based normalization to reuse the nucleus pipeline's local-background-subtraction logic; re-run the crosswalk check |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Amygdala CR-01 recurrence | Brain-wide region-labeling validation | `region_label` distribution for amygdala ROI resolves to LA/BA, not BLA/grey/CTXsp; `is_leaf` agrees across hemispheres |
| 2. k=3 seed drift at new imaging params | Imaging re-validation (4-plane/lower-laser) | Re-run D-05 gates + bg-sub distribution-shape comparison against v1.0 reference before locking |
| 3. Under-projection at fewer Z-planes | Imaging re-validation | Re-run OPT-01-style plateau check at the new plane count; visually confirm no DAPI blob/saturation artifact |
| 4. Multi-scene index/AP-order mixup | Multi-scene MIP conversion | Manual scene bounding-box/morphology check against expected physical layout before any registration |
| 5. Damaged/folded tissue undetected | Registration speedup / LA/BA classification | Explicit visual tissue-QC checklist item per section before registration |
| 6. Area-based readout not comparable to nucleus counts | Generalizable area-based density readout | Crosswalk check on one shared-tissue region; confirm shared background-subtraction logic |
| 7. Area-based method over-generalized as detection-quality fallback | Generalizable area-based density readout | Each area-based region has a documented, visually-confirmed non-separability rationale, not an ad hoc trigger |
| 8. Global BraiAn.yml/k seed masking a bad section | Imaging re-validation / LA/BA classification | Per-section bg-sub median/MAD comparison across all 5 sections, not just entry 1 |
| 9. Aggregation pseudoreplication via uneven region coverage | Section→animal aggregation | Per-region section-coverage tally documented before computing animal-level numbers |
| 10. Stale micron sanity range for amygdala | Full per-atlas-region micron export | Region-specific expected coordinate range re-derived, not copy-forwarded from hippocampus |
| 11. LA/BA boundary precision under DeepSlice-only registration | Registration speedup | Visual boundary check against external capsule landmark |
| 12. Tissue-mask crop tool unverified on amygdala FOV | Registration speedup | Visual crop-output check on an amygdala section before adopting for elastix |

---

## Sources

**HIGH confidence — this project's own artifacts (measured/observed):**
- `.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-REVIEW.md` —
  CR-01 critical finding (region-labeling defect, smallest-area leaf fix)
- `.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-VALIDATION-RECORD.md`
  — corrected per-region findings post-CR-01
- `.planning/phases/04-biological-plausibility-validation-and-imaging-optimization-/04-IMAGING-NOTES.md`
  — OPT-01 Z-plane plateau argument (explicitly provisional, 2-of-3)
- `.planning/debug/resolved/d05-threshold-all-negative.md` — robust-threshold (k·MAD) redesign root
  cause and design intent
- `.planning/phases/02-detection-parameter-lock/02-LOCK-RECORD.md` — locked BraiAn.yml, k=3 seed,
  SERIES-02 drift-monitoring reference
- `.planning/codebase/CONCERNS.md` — no-automated-tests gap, channel-order bug precedent, missing
  output validation
- `.planning/PROJECT.md` — v1.1 scope, merged-32GB-canvas known-bad-file warning
- User memory: `hybrid_imaging_dapi.md` (DAPI saturation/blob fix precedent)

**LOW confidence — general web search, not project-verified:**
- BLA principal-neuron non-laminar organization: Nature Scientific Reports / bioRxiv (biorxiv.org/content/10.1101/2023.12.29.573684) — https://www.nature.com/articles/s41598-025-18411-1
- aicspylibczi multi-scene/split-scene indexing issues — https://github.com/AllenCellModeling/aicspylibczi/issues/87 , https://forum.image.sc/t/finding-bounding-box-of-a-scene-in-a-czi-file/31606
- Area/percentage-based immunofluorescence quantification vs. raw intensity — https://pmc.ncbi.nlm.nih.gov/articles/PMC6410121/ , https://pmc.ncbi.nlm.nih.gov/articles/PMC6616976/
- MIP/Z-projection distortion of downstream analysis — https://analyticalscience.wiley.com/content/article-do/flattened-truth-z-projections-distort-image-analysis
- Laser power / SNR / background-subtraction tradeoffs — https://evidentscientific.com/en/microscope-resource/knowledge-hub/techniques/confocal/signaltonoise , https://www.sciencedirect.com/science/article/abs/pii/S1074742725000164

---
*Pitfalls research for: v1.1 First Full-Series Run — LA/BA Amygdala Engram (wBA1-3)*
*Researched: 2026-07-17*
