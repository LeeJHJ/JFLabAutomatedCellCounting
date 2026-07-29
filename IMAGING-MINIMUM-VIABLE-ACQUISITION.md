# Minimum Viable Acquisition — TRAP2 Section Pipeline

**Question this memo answers:** what is the cheapest acquisition that still supports (a) atlas
registration to Allen CCFv3 and (b) per-nucleus TdT+/Fos+/Double+ counting?

**Why it matters:** current acquisition is 20x/0.8 Airyscan at 0.460 µm/px, ~85 min/section
(operator-reported). That does not scale to a full series, let alone a cohort. We want to cut it
hard without invalidating the counts.

**Status of claims below:** `[measured]` = computed from our own exported data. `[optics]` =
derived from standard sampling theory with our objective/wavelengths. `[open]` = needs a test.
Prepared 2026-07-29 for discussion. Written to be read by someone who did not build the pipeline.

---

## TL;DR

1. **We are pixel-limited, not resolution-limited.** At 0.46–0.69 µm/px we sample 2.7–4.0×
   coarser than Nyquist for our objective. Airyscan's resolution advantage is mathematically
   unrecoverable at this sampling — **we are paying for Airyscan and throwing it away.**
2. **Magnification is the wrong lever.** Acquisition time scales with total pixels × dwell ×
   planes × channels, not with magnification. Dropping 20x → 10x at fixed pixel size saves
   tile overhead only. **10x at native sampling (~1.38 µm/px) breaks cell counting outright.**
3. **The real levers, in order:** Airyscan off (+ wider pinhole → shorter dwell), 0.46 → 0.69
   µm/px, fewer z-planes. Estimated combined ~6× → **~85 min/section to ~15 min/section.**
4. **Do not test lower laser power until the detection threshold is fixed.** Detection is
   currently pinned to an *absolute* intensity (`threshold: 700`). Any dimmer acquisition will
   silently under-detect, and the imaging will get blamed for a software problem.
5. **Registration is not the binding constraint.** It would survive 10–20 µm/px. Counting sets
   the floor, and the floor is **~1.0 µm/px**.

---

## 1. What the data says about our nuclei

From the v1.0 validation export, 213,106 detected nuclei on M3 hippocampus entry 1 `[measured]`:

| Property | Value |
| --- | --- |
| Nucleus area, modal 10 µm² bin | 40–50 µm² |
| Nucleus area, median | 47.88 µm² |
| Nucleus area, IQR | 36.6–65.4 µm² (skew 1.85, right-tailed) |
| **Equivalent nucleus diameter (median)** | **7.8 µm** |
| DAPI nucleus density, hippocampal subfields | 2,900–3,800 /mm² |
| DAPI nucleus density, brain-wide spread | 2,500–5,500 /mm² |

At ~3,400 nuclei/mm² the mean center-to-center spacing is ~17 µm, so a *typical* nucleus pair is
well separated. The hard cases are the dense laminae (CA pyramidal; DG granule is already
excluded from counting) where nuclei touch and segmentation has to resolve the waist between
them — roughly a 1–2 µm feature.

**7.8 µm is the number that sets the sampling floor.** Everything in §3 follows from it.

---

## 2. We are already far coarser than the optics

Plan-Apochromat 20x/0.8. Confocal lateral resolution ≈ 0.61 λ/NA `[optics]`:

| Channel | λ em | Resolution limit | Nyquist pixel (÷2.3) | Our pixel (0.46) | Our pixel (0.69) |
| --- | --- | --- | --- | --- | --- |
| DAPI | 461 nm | 0.35 µm | 0.15 µm | 3.0× coarser | 4.5× coarser |
| Fos / AF488 | 519 nm | 0.40 µm | 0.17 µm | 2.7× coarser | 4.0× coarser |
| TdT / AF568 | 603 nm | 0.46 µm | 0.20 µm | 2.3× coarser | 3.5× coarser |

Two consequences:

- **Airyscan buys us nothing at this sampling.** Airyscan improves resolution ~1.4–1.7× *below*
  the confocal limit, which requires sampling at or finer than Nyquist. We sample 2.3–4.5×
  coarser. The extra resolution is discarded at the pixel grid. This is the strongest argument
  in this memo for turning Airyscan off — it is not a judgment call about image quality, it is
  that the information cannot survive the sampling we chose.
- **Optical resolution is not our limiting factor for segmentation — pixel size is.** So the
  question "will it still resolve nuclei?" is answered by pixels-per-nucleus, not by NA.

*Caveat:* Airyscan also improves SNR and optical sectioning, not just XY resolution. Those are
real and are the honest reasons to keep it. But sectioning is better addressed by the pinhole,
and SNR by dwell/laser — both cheaper than Airyscan's per-element light split.

---

## 3. The counting floor: pixels per nucleus

Our detection parameters are specified in **microns** (`sigmaMicrons: 2.0`, `minAreaMicrons: 20`,
`maxAreaMicrons: 250`, `cellExpansionMicrons: 5.0`), so they are nominally scale-free. But they
are rendered into **pixels** at detection time, and watershed behavior depends on the pixel
rendering. Using our 7.8 µm nucleus:

| Acquisition | µm/px | px across nucleus | `sigma` in px | `minArea` in px² | Verdict |
| --- | --- | --- | --- | --- | --- |
| 20x, 4-plane (current) | 0.460 | 17.0 | 4.3 | 94 | over-sampled for the task |
| 20x, 3-plane (v1.0, validated) | 0.691 | 11.3 | 2.9 | 42 | **proven good** |
| hypothetical | 1.00 | 7.8 | 2.0 | 20 | marginal — at the edge |
| 10x, native | ~1.38 | **5.7** | **1.45** | **10.5** | **breaks** |

Why 10x native fails, concretely:

- **`sigma` = 1.45 px.** A Gaussian smoothing kernel needs ≳2 px to be properly sampled. Below
  that it aliases instead of smoothing — it stops doing the job it exists to do.
- **`minArea` = 10.5 px².** A ten-pixel object is noise-scale. The minimum-area guard that
  suppresses spurious detections can no longer distinguish a nucleus from a speckle.
- **5.7 px across a nucleus.** The 1–2 µm waist between touching nuclei in dense laminae becomes
  ~1 px. Watershed cannot split what is not resolved; touching nuclei fuse.

**The floor is ~1.0 µm/px, and I would not go past 0.69 µm/px** — that is the value the v1.0
validation actually ran at, and 1.0 buys little extra time (2.1× fewer pixels than 0.69) for a
move into unvalidated territory.

### Known caveat, in the other direction

There is an **open** over-segmentation concern that argues against blindly trusting the current
setup either: measured density (2,500–5,500/mm²) runs above the 500–2,000/mm² literature seed
while nucleus area (40–50 µm²) runs *below* the 50–150 µm² seed. Smaller objects and more of
them, with total nuclear area roughly conserved, is the signature of watershed splitting single
nuclei in two. This has not been checked against hand counts. It is not a reason to change
imaging, but it means **"more pixels" has not been demonstrated to give better counts** — which
further weakens the case for 0.46 µm/px.

---

## 4. Registration needs far less than counting

Registration (DeepSlice for AP position, then ABBA/BigWarp/elastix for the warp) operates on
downsampled overviews — tissue outline, ventricles, major tract and laminar boundaries. Those are
100 µm–1 mm features. Registration would be comfortable at **10–20 µm/px**, one to two orders of
magnitude coarser than counting needs.

Practical notes from our own registration work:

- **DAPI is a poor registration channel.** Phase 06 (REG-05) found that registering on the
  structural/Nissl-like channel rather than DAPI markedly improved the LA/BA fit; the reference
  workflow (Cabrera et al., bioRxiv 2024.09.16.611953 / F1000Research 15:410) reports Dice ~0.30
  for DAPI vs ~0.49–0.55 for Fos/NeuN. If any channel is dropped to save time, **do not drop the
  one registration depends on.**
- This also means a **cheap dedicated registration channel is viable** — a fast, coarse,
  single-plane structural scan could serve registration while the expensive sampling is reserved
  for the counting channels. Worth discussing as a longer-term option.

---

## 5. The software constraint that must be fixed first

**This is the most important operational point in this memo.**

Detection currently uses an **absolute** intensity threshold. In the newest project config
(`M3 Hipp1 072326`, set 2026-07-28):

```yaml
threshold: 700          # absolute
#histogramThreshold:    # ← the self-calibrating path, currently disabled
```

It was set deliberately and for a defensible reason: an intensity sweep on that section found
only two histogram peaks — background at 162 and bright nuclei at 2268 — with no distinct
dim-nuclei peak, so the self-calibrating method could only pick 162 (floods noise) or ~2268
(drops every dim nucleus). 700 cuts the valley between them. The config's own note records the
risk: *"700 is less sensitive than 400 → DIMMER slices are the under-detection risk on batch."*

**Implication for imaging tests:** lower laser power, shorter dwell, or Airyscan off all shift
the intensity histogram downward. Against a fixed threshold of 700, that shows up as *fewer
cells detected* — which is indistinguishable from "the cheaper imaging was inadequate." **We
would draw the wrong conclusion and over-buy acquisition quality for the rest of the study.**

The fix is not to revert to the histogram method (it genuinely failed on this data) but to use a
rule that self-calibrates without needing a dim peak — e.g. threshold at a fixed fraction of the
span between the background floor and the bright-nucleus peak, both of which *are* reliably
detectable. On this section that would have landed near 700 without being pinned to this
section's absolute scale.

**Sequence this before any laser/dwell test.** It is a software change, not an imaging one.

---

## 6. Z-planes and section thickness

Current strategy is a **hybrid projection**: DAPI from a single auto-selected sharpest plane
(avoids the over-projection that fused nuclei into blobs), markers max-projected over all planes
(catches axially spread signal). This was the right call and the evidence is solid `[measured]`:
across 6 planes the focus metric varied only ~5% (every plane near-focus), and nucleus separation
degraded monotonically from single-plane → 2 → 3 → 6 planes.

Two things to settle:

- **How many marker planes are actually needed?** `[open]` Going to a single plane total would be
  cheapest but risks losing axially-spread marker signal. It might also *help*: we have a known
  issue where whole-cell TdTomato measurement picks up passing axons and falsely marks bystander
  nuclei as TdT+, and fewer projected planes should reduce that. Genuinely two-sided — test 1 vs
  2 vs 4 marker planes on one section and compare both TdT+ fraction and the Double+/TdT+ ratio.
- **Section thickness vs imaged slab.** `[open]` These are vibratome sections; we image a thin
  slab of a much thicker section. Our "cells/mm²" is therefore cells per *imaged slab*, not per
  section. That is fine for comparisons — **as long as the z-range is identical across every
  section and animal.** If the z-range changes as part of this optimization, densities are no
  longer comparable to prior runs, and that break would be invisible in the numbers.

  The **z-step is 2.0 µm** `[measured]`, read from the CZI's own scaling metadata
  (`Scaling/Items/Distance[@Id="Z"]` = 2×10⁻⁶ m, confirmed on the M3 Hipp2 072526 acquisition,
  which is 4 planes × 3 channels). So the imaged slab is roughly **6–8 µm thick** — 4 planes at
  2 µm spacing. **Section thickness is still needed from whoever cut them**; if the sections are
  40–50 µm, we are sampling only ~15% of the tissue depth, which sets a hard ceiling on
  achievable counts and matters for any comparison against a literature density.

---

## 7. Recommended acquisition to test

Change one axis at a time so a regression is attributable. **Do §5 first.**

| Setting | Current | Proposed | Rationale |
| --- | --- | --- | --- |
| Objective | 20x/0.8 | 20x/0.8 (unchanged) | 10x costs SNR and FOV-per-pixel with no time saving at fixed pixel size |
| Airyscan | on (SR 2D) | **off, confocal, ~1 AU pinhole** | resolution gain unrecoverable at our sampling (§2); wider pinhole → more photons → shorter dwell |
| XY pixel | 0.460 µm | **0.691 µm** | 2.25× fewer pixels; the v1.0-validated value; 11.3 px/nucleus |
| Z-planes | 4 | **2–3, tight around best focus** | all planes near-focus; over-projection is what fused nuclei |
| DAPI exposure | saturating | **below saturation** | DAPI p99 = 65,535 (clipped) vs Fos ~36,500, TdT ~16,000. Saturated DAPI blooms and fuses touching nuclei. Highest-impact single fix, and it is free. |
| Laser / dwell | locked | reduce **after** §5 | otherwise the threshold confounds the result |

**Estimated time:** 2.25× (pixels) × ~1.7× (planes) × ~1.5× (dwell, from the wider pinhole)
≈ **6×**, i.e. ~85 min → **~15 min/section**. This is an estimate from multipliers, not a
measurement — the dwell factor is the least certain. Turning Airyscan off additionally removes
the SR processing stage and the 16 GB intermediate CZI from the Windows workflow.

**Acceptance test.** Acquire one section — ideally a previously-imaged one — under both the
current and proposed settings, then compare on the same tissue:

1. Total DAPI nucleus count within a fixed atlas region (want: within ~10%)
2. Nucleus-area distribution (want: same modal bin, no shift toward smaller = no new splitting)
3. TdT+ / Fos+ / Double+ fractions (want: within noise)
4. Visual check for fused nuclei in CA pyramidal layer
5. Registration fit quality, operator visual

If 1–4 hold, the cheaper acquisition is validated and can be locked for the series. Lock every
setting including z-range, and keep them identical for every section and animal thereafter —
cross-section comparability depends on it more than on absolute quality.

---

## 8. Open questions for the group

1. **Section thickness** — z-step is 2.0 µm (from CZI metadata), so the imaged slab is ~6–8 µm.
   Cut thickness is still unknown and is needed to interpret density at all (§6).
2. **Is anyone relying on Airyscan resolution downstream?** Everything I can see needs nucleus
   *centroids* and *mean intensities*, not sub-diffraction morphology. If that is true for all
   planned analyses, Airyscan is pure cost. If someone plans a morphology or puncta analysis,
   that changes the answer.
3. **Over-segmentation (§3 caveat)** — worth spending one session on hand counts before locking
   detection parameters for a cohort. This is the one place where our counts could be wrong in a
   way that no amount of imaging quality fixes.
4. **Dedicated cheap registration channel (§4)** — decouples registration cost from counting
   cost. Attractive if we go brain-wide.
5. **10x** — I recommend against it at native sampling. If there is a throughput argument I am
   missing (stage/tile overhead dominating rather than pixel dwell), say so, because that would
   change the calculus and it is the one number I took from report rather than measurement.

---

## Appendix — where these numbers come from

| Claim | Source |
| --- | --- |
| Nucleus area, density, 213,106 cells | `.planning/milestones/v1.0-phases/04-.../04-VALIDATION-RECORD.md` |
| DAPI saturation p99 = 65,535; focus survey flat ~5%; monotonic separation loss | `IMAGING_OPTIMIZATION_NOTES.md` |
| Absolute `threshold: 700` and its sweep rationale | `M3 Hipp1 072326 7scene/.../BraiAn.yml` |
| Detection params in microns | same `BraiAn.yml`, `channelDetections.parameters` |
| Registration channel finding | `.planning/phases/06-registration-speedup/06-REG05-FINDINGS.md` |
| Hybrid DAPI-plane / marker-MIP strategy | `czi_mip.py` module docstring |
| ~85 min/section, 10x-not-better-than-20x | operator report — **not independently measured** |
