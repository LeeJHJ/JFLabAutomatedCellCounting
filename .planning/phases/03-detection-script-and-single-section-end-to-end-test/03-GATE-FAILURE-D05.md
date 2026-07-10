# Phase 3 — 03-04 gate FAILED: D-05 threshold derivation broken (debug seed)

**Date:** 2026-07-10 · **Status:** gate failed on the science; needs a gap-closure / debug fix before Phase 3 can close.

## Outcome of the 03-04 human QuPath run
Script now runs **end-to-end** on M3 entry 1 (213,106 detections) with no crash, BUT:
- **SC1: PASS** — runs clean, writes classified `data.qpdata`.
- **SC2: FAIL** — 100% of cells classified **Negative** (0 Fos+, 0 TdT+, 0 Double+). Atlas labels themselves resolve correctly (CA1/SSp-bfd/DG-mo…), so the SC2 *label* half works; the *class* half fails.
- **SC3: FAIL (blocked)** — Atlas_X sanity print samples only positive cells; none exist, so it couldn't run.
- **SC4: mechanism OK, values all-Negative** — per-region `Count:` columns populate, but every region is Negative-only.

## Root cause (confirmed)
1. `derivePeakThreshold` (script lines ~250–266) takes the **nth (2nd) histogram peak** as the cutoff → assumes a **bimodal** distribution (background peak + positive peak).
2. TdT+/Fos+ are **sparse markers** (few % positive) → the intensity histogram is **unimodal**, background-dominated. There is no distinct 2nd peak. `ChannelHistogram.findPeaks(smoothed, 500)` correctly returns **0 peaks** → `derivePeakThreshold` returns **NaN**.
3. The built-in self-check (re-derive on the *raw* measure, compare to locked 13000.4538/16766.4671) **also** returned NaN — the tripwire fired as designed.
4. Because re-derivation returned NaN, the script safely **kept the placeholder** bgsub JSONs — whose thresholds are the **raw-scale** cutoffs (13000.4538 / 16766.4671) applied to the **bg-subtracted** measure. bg-sub ≪ raw, so nothing clears the bar → **100% Negative**.

## What already works (do NOT re-touch)
- Runs end-to-end; D-04 local-bg loop robust (try/catch; only **1/213,106** geometry-robustness failure — negligible).
- Groovy parse-clean (verified via QuPath's bundled Groovy, CONVERSION phase).
- Atlas region labeling + SC4 rollup mechanism + Excluded (DG-sg/VS) handling all correct.
- Prior fixes already committed this session: `n`→`cnt` closure param (parse error); D-04 annulus try/catch (batch-abort fix).

## Chosen fix direction (user decision, 2026-07-10): redesign D-05 for sparse markers
Replace the nth-peak logic with a **self-calibrating robust threshold** computed at runtime from each section's own bg-sub population:

```
threshold = background_mode + k * (1.4826 * MAD)
```
- `background_mode`: mode/peak of the bg-sub distribution (≈ 0, since a cell in its own local background has bg-sub ≈ 0). Median is an acceptable proxy.
- `MAD`: median absolute deviation of the bg-sub population; `1.4826 * MAD` ≈ robust SD.
- `k`: single tunable seed (start ~3, sweep 3–5). Higher k = stricter positive call.
- Rationale: for a background-subtracted, unimodal, sparse-marker measure, "a few robust SDs above the near-zero background band" is the correct cut. Auto-derives per section (D-01 series-scalability), robust to outliers, no bimodality assumption.

**Apply to both** `Nucleus: AF488-T3 mean (bg-sub)` (Fos) and `Cytoplasm: AF568-T2 mean (bg-sub)` (TdT). Keep the existing safe-write guard (only overwrite the bgsub JSON when the derived threshold is finite). Keep the self-check print but compare the *new* strategy's output to a sanity band, not the raw cutoffs.

## Validation gates for the redesign (what "fixed" looks like)
- Non-zero Fos+/TdT+/Double+ appear, concentrated where TRAP2 biology expects them (hippocampus CA/DG, amygdala BLA/LA, etc.), NOT uniformly.
- **SSp (cortical autofluorescence) stays suppressed** — its Fos+ fraction must be visibly lower than the Phase-2 raw-threshold run (the whole point of D-04/D-05).
- SC3 Atlas_X sample now lands in 5,000–10,000 µm.
- Counts are biologically plausible (Double+ a small subset of TdT+).
- `k` tuned on this one section, then locked as the series seed.

## Files
- `scripts/02_detect_classify.groovy` (canonical) + `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` (byte-identical copy)
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/{Fos_Classifier_20x_bgsub,TdT_classifier_bgsub}.json`
- Peak-finder to replace: `derivePeakThreshold` closure, lines ~250–266.
