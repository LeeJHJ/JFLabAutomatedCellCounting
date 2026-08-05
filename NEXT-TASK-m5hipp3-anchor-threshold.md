# M5 Hipp3: why the anchor threshold is unusable, and the one-line fix

**Written 2026-08-04/05.** Investigation only — **no config was changed.** The anchor
cut is what the operator is actively setting by eye, so the decision below is theirs.

---

## Summary

`span_frac` is not broken. Its **endpoints** are. The peak-finder that supplies
`floor` and `bright_peak` is locking onto noise in the histogram's low tail instead of
onto the nuclei, because **`peak_prominence` is an absolute count** and 100 counts is
0.0001 % of a 161-million-pixel histogram. Every noise bump clears that bar.

Consequence: the whole `span_frac` 0→1 dial maps to cuts of **41→370** on s1, when the
nuclei population sits at **~5,670**. No fraction can reach the right answer, which is
why s2 had to be written as an absolute.

This is the same bug class the relative-threshold design was created to eliminate — a
parameter tuned on one image that silently misbehaves on another size or histogram.

---

## The measurements

DAPI channel (`DAPI-T4`, index 2, confirmed from OME-XML), full image, 161,474,560 px.

### In-tissue distribution (Otsu tissue mask, not brightest-crop sampling)

| | tissue % of frame | in-tissue p50 | dominant in-tissue mode |
| --- | --- | --- | --- |
| s1 | 55.6 % | 7,076 | **6,245** |
| s2 | 44.0 % | 5,305 | **4,537** |

`ACQUISITION-CHECKLIST.md` records M5's sibling sections at bright-nuclei peaks of
**3,700–6,600**. Both sections land inside that. **The acquisition is fine** — this is
not an exposure problem, and it is not the `M5a_s1` failure repeating.

### What the peak-finder returns, swept over both knobs

`scipy.signal.find_peaks` on the same histogram; reproduces BraiAn's configured result
(41 / 365 vs BraiAn's 41 / 370) closely enough to trust the sweep.

```
                                     first three peaks
smooth  prominence   % of n          s1                  s2
    15         100   0.0001%   [7, 41, 365]  <-cfg  [7, 9, 19]  <-cfg
    15       1,615   0.0010%   [7, 41, 365]         [7, 23, 347]
   401         100   0.0001%   [200, 215, 408]      [200, 370, 3821]
   801         100   0.0001%   [400, 5670]          [400, 3852]
  1601         100   0.0001%   [800, 5696]          [800, 3899]
```

At `smooth_window: 801` the second peak is the **real nuclei population** on both
sections — 5,670 and 3,852, in family with the checklist range and with each other.

Note s2 as configured: floor 7, bright 9, span **2**. Any `span_frac` yields a cut of 8.
That section could never have been thresholded by the span rule at all.

### Where the cut is consumed

`run_braian_detection.groovy:262-289` measures these peaks on the **raw** histogram and
passes the result to `parameters.setThreshold()`. QuPath's `WatershedCellDetector`
runs `Background estimate → Background subtracted → setThreshold`, and BraiAn.yml sets
`backgroundRadiusMicrons: 10`. So the number is measured in raw space and applied in
background-subtracted space. On a dark-background section those nearly coincide (M3:
floor 162, bright 2,268). Here they do not.

Both effects push the same way: the cut lands far too low. At s1's 238, essentially
the whole tissue passes — which is why s1 produced 276,889 "cells" and a grey-matter
density of 5,087/mm² against s2's 862/mm² on an identically-sized image.

---

## Proposed fix — one line, to be verified before adopting

```yaml
detection_threshold:
  smooth_window: 801        # was 15
```

Leave `peak_prominence: 100` alone; once the smoothing is right, 100 and 1,615 give
identical peaks, and raising it to 0.01 % of n makes the finder return a single peak
and abort. The stable plateau is `smooth_window` anywhere in ~801–1601.

Resulting cuts, with the endpoints above:

| span_frac | s1 cut | s2 cut |
| --- | --- | --- |
| 0.25 | 1,718 | 1,263 |
| 0.50 | 3,035 | 2,126 |
| 0.75 | 4,353 | 2,989 |

The operator's by-eye call on s2 was **2,900** (later 3,250). `span_frac ≈ 0.75`
reproduces it, and gives s1 a proportionally higher cut, which is the behaviour the
rule is supposed to have. Both sections then run on **one** `span_frac` with no
per-slice override — the thing the design exists for.

### Caveat, stated plainly

At `smooth_window: 801` the reported `floor` is **exactly w/2** (400 at 801, 800 at
1601). It is the box-convolution smearing the near-black spike, not a measurement.
`bright_peak` becomes a real measurement of the nuclei; `floor` becomes a constant.
The rule therefore degenerates to *"anchor the cut to the nuclei peak"* — which is
still the quantity that tracks staining and laser drift, and is still per-section, so
comparability holds. But it should be adopted understanding it as that, not as a span
between two measured populations.

**Verify before adopting.** The sweep above is a numpy reimplementation. Run BraiAn's
own implementation read-only first:

```bash
$QP script -p "M5 Hipp3 080326/M5 Hipp3 080326 QuPath/project.qpproj" \
   -s "…/scripts/calibrate_threshold.groovy"
```

with `smooth_window: 801`, and confirm it reports bright peaks near 5,670 / 3,852.

---

## RESOLVED 2026-08-05 — both cuts are wrong, in opposite directions

Operator reviewed overlays: **s2 too few detections; s1 "looked much better."** The s1
view was a dense cell layer, where a good cut and a flooding cut are indistinguishable
because there is no room to over-call. The s2 view was sparse tissue, where the
discrimination exists — and the judgement there was right.

Region-matched across every leaf region with ≥200 cells in **both** sections:

```
median s1/s2 density ratio, sparsest quartile of regions   6.33
median s1/s2 density ratio, densest  quartile of regions   2.32
Spearman(ratio, s2 density)                               -0.955
```

s1 returns ~5,000 cells/mm² in nearly every region regardless of region — LHA 5203,
RT 5752, PIR 4894, LA 5107, MEA 5153, VMH 5177, and white matter `scwm` 5226 / `alv`
5159. s2 varies 1,138→2,802 across the same regions, which is anatomically sensible.
A density that is flat across regions the other section says differ 2.5× is `<internal>`
evidence that s1 has stopped measuring tissue; white matter as dense as cortex is the
`<anatomical>` gate.

**Conclusion: s1's 238 floods, s2's 3,250 is too strict.** Neither observation was
wrong; the dense-layer view simply could not report on s1.

### Also: this was already diagnosed

`cockpit_threshold_gui.py`'s module docstring records the same finding from 2026-08-04
— trimodal histogram (canvas at 0, empty-field detector offset ~384, nuclei ~5,632),
BraiAn's peak rule locking onto the two background populations, cut at 123 instead of
~1,700 — and attributes it to **histogram bin width**. The independent measurement here
(nuclei at 5,670 / 3,852) agrees with it. `smooth_window` and bin width are two routes
to the same correction; the module's `find_peaks(bins=…)` table is the prior art.

That module also records the operator's standing decision that **per-slice by eye is a
first-class method, not a fallback**. Earlier wording in this file calling absolutes a
"stopgap" was wrong and is retracted.

---

## Open questions for the operator

1. ~~What looked wrong on s2?~~ **Answered above.**
2. **`k_robust` for TdT is unresolved, and cannot be settled yet.** `tuning_log.csv` at
   19:19 says *"Should increase k for tdt"*, written after the 2.0 change doubled TdT+
   (7,630 → 15,032). Operator reports the extra calls look like **noise, not axon
   contamination** — consistent with the anchor flooding. Left at 2.0; not re-tuned.

   Why it cannot be judged first: `k_robust` is `median + k·1.4826·MAD` **of whatever
   population it is handed**, so it rescales to a flooded population as happily as to a
   real one. Measured — TdT at k=2.0 calls **7.66 %** positive on s1 and **7.80 %** on
   s2, nearly identical, though s1's cut is 14× lower and most of its objects are noise.
   A sane-looking positive fraction is therefore no evidence that the anchor is sane.
   Fix the anchor, re-export, then set k on the overlay.
3. **Normalizing the MIPs** was raised as an idea. Argued against below.

---

## On normalizing MIP intensities across slices — recommend not

The idea is reasonable but it solves the problem in the wrong place, and it carries a
risk the current design deliberately avoids.

- **It is redundant.** Per-section rescaling is exactly what the relative cut already
  does. Fixing the endpoints restores it. Two mechanisms doing the same job makes the
  cut's behaviour much harder to reason about.
- **It changes stored pixel values.** Every downstream intensity measurement — the
  `Nucleus:`/`Cell:` per-channel means that `k_robust` thresholds on — shifts with it,
  and nothing in the export records that a scale factor was applied.
- **It folds biology into the scale factor.** Normalizing to a percentile or a mean
  assumes the reference quantity is constant across sections by construction. It is
  not: s1's nuclei peak is 5,670 and s2's is 3,852, and part of that gap may be real
  tissue difference (s1 is 55.6 % tissue, s2 44.0 %). Scaling it away would remove
  signal along with drift, invisibly.
- **It does not buy what is actually missing.** Per `CLAUDE.md`, relative cuts already
  absorb brightness drift; what they cannot absorb is SNR and geometry. Global
  normalization does not fix those either.

The safe version of this idea is already in the pipeline twice, and both operate on
**shape** rather than global scale: `czi_mip.py`'s retrospective flat-field correction
(within-section shading) and QuPath's `backgroundRadiusMicrons: 10` (local pedestal
removal). Those are the right places for it.

If cross-section intensity comparability ever does need to be enforced directly, the
defensible route is a **fixed imaging regime plus a recorded calibration standard**,
not a post-hoc rescale of the pixels.

---

## Scratch scripts (scratchpad, not repo)

```
dapi_hist.py     raw percentiles + saturation, both sections
bgsub_hist.py    raw vs background-subtracted, in-tissue crops
tissue_hist.py   Otsu tissue mask, in-tissue percentiles + modes
peakfind.py      the smooth_window x peak_prominence sweep above
```

`tissue_hist.py`'s peak list carried a de-duplication that forced ≥300-level spacing
and manufactured an apparent regular comb; that artifact is not in the data. Its
percentiles and its single high-smoothing mode are unaffected. `peakfind.py` supersedes
it for peak locations.
