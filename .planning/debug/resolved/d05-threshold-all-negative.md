---
slug: d05-threshold-all-negative
status: resolved
resolved: 2026-07-16
root_cause: >
  D-04 localBackgroundSubtractedMean looked up the annulus channel mean under
  "Cell: <channel> mean" but a plain detection object names it "<channel>: Mean"
  -> null -> NaN local background for every cell -> empty (n=0) D-05 population ->
  NaN threshold -> placeholder raw-scale JSON kept -> 100% Negative. (Two earlier
  hypotheses — sparse-marker unimodality, then buffered getMeasurementList writes —
  were both wrong; the A5 self-check print was the disproof all along.)
fix: >
  Resolve the annulus key by matching the channel name against the object's actual
  key set instead of assuming a "Cell:" compartment prefix. D-05 robust-threshold
  redesign (median + k*1.4826*MAD, k=3) kept — correct once population is non-empty.
verification: >
  Validated in QuPath on M3 entry 1 AND the single-plane/MIP hybrid: n≈207k population,
  finite thresholds, Total Fos+ ≈20%, Total TdT+ ≈3.5%, Double+/TdT+ ≈0.45, SSp
  autofluorescence suppressed, biology plausible (user visual-confirmed SSp + LA).
files_changed: >
  scripts/02_detect_classify.groovy (+ byte-identical M3 project copy)
trigger: |
  /gsd-debug 3 — Phase 3 (03-04) gate failure. After the human QuPath run on
  M3 entry 1, the detect+classify script runs end-to-end (213,106 detections,
  no crash) but classifies 100% of cells Negative (0 Fos+, 0 TdT+, 0 Double+).
created: 2026-07-10
updated: 2026-07-10
---

# Debug: D-05 threshold derivation yields 100% Negative cells

## Symptoms
- **Expected:** Non-zero Fos+/TdT+/Double+ counts, concentrated in TRAP2-expected
  regions (hippocampus CA/DG, amygdala BLA/LA), with SSp cortical
  autofluorescence suppressed relative to the Phase-2 raw-threshold run.
- **Actual:** 100% of 213,106 detected cells classified Negative. Atlas region
  labels resolve correctly (CA1/SSp-bfd/DG-mo), so SC2 label-half works; class-half fails.
  SC3 blocked (no positive cells to sample). SC4 rollup mechanism OK but all-Negative.
- **Errors:** No crash. Self-check tripwire fired (re-derivation returned NaN) as designed.
- **Timeline:** Surfaced on the 03-04 human QuPath validation run, 2026-07-10.
- **Reproduction:** Run `scripts/02_detect_classify.groovy` on M3 entry 1 in QuPath 0.6.0.

## Current Focus
- hypothesis: CONFIRMED (TRUE root cause, supersedes the earlier peak/unimodal theory) —
  D-04 wrote the bg-sub measures via `d.getMeasurementList().put(...)` (lines 218–219),
  the LEGACY array-backed list that buffers puts until `.close()`. The script never
  closed it (`fireHierarchyUpdate()` does NOT flush it), so the values never surfaced
  in the `getMeasurements()` Map view that D-05 derivation (297–298) and the classifier
  loop (376–377) read from. Every bg-sub read returned null → derivation population
  EMPTY (n=0) → NaN threshold → safe-write kept the placeholder raw-scale JSONs
  (13000.4538 / 16766.4671) on the bg-sub measure → classifier loop also read null →
  100% Negative.
  Proof it is the write path, not the key: the raw read at line 210
  (`getMeasurements().get("Nucleus: AF488-T3 mean")`) works (D-04 reported only 1/213106
  NaN). Keys write==read are byte-identical. Only difference: who committed the value —
  BraiAnDetect committed the raw measure; our uncommitted put() never surfaced.
- CORRECTION to the original diagnosis: the first run's "findPeaks returns 0 peaks →
  NaN" was NOT sparse-marker unimodality. The histogram had 0 peaks because it had
  0 data points (empty population, same bug). The D-05 robust-threshold redesign was
  therefore necessary-but-insufficient — it changed how the threshold is computed FROM
  the population, but the population was empty either way. Its virtue: it prints n=0
  explicitly, which exposed the true cause. Redesign is KEPT (correct for sparse markers
  once the population is non-empty).
- test: Re-run `scripts/02_detect_classify.groovy` on M3 entry 1 in QuPath 0.6.0.
- expecting: D-05 derivation population n≈210,981 (non-empty); finite Fos/TdT thresholds;
  non-zero, biologically-concentrated Fos+/TdT+/Double+; SSp suppressed; SC3 Atlas_X
  in 5,000–10,000 µm.
- next_action: DONE (code) — changed both bg-sub writes from `getMeasurementList().put()`
  to `getMeasurements().put()` (commits immediately, self-consistent with all reads) in
  both byte-identical copies (sha256 bb43f5c9…4316ac); parse-verified at CONVERSION phase
  via QuPath's bundled Groovy 4.0.23. REMAINING: human re-runs in QuPath 0.6.0 to confirm
  non-empty population + biologically plausible positives, then sweep/lock k (seed k=3).

## Confirmed root cause (THIRD and correct — on printed evidence)
`localBackgroundSubtractedMean` (line ~191) looked up the annulus channel mean under
`"Cell: ${channelName} mean"`, but `ObjectMeasurements.addIntensityMeasurements(...,
[Compartments.CELL])` on a PLAIN detection object (the annulus has no cell/nucleus
sub-ROIs) names the measurement `"<channel>: Mean"` (e.g. `AF488-T3: Mean`). The A5
self-check literally PRINTED the real keys `[AF568-T2: Mean, AF488-T3: Mean, DAPI-T4: Mean]`
— which never matched the assumed `"Cell: ... mean"` key. So the lookup returned null →
local background = NaN for EVERY cell → `rawFos - NaN = NaN` bg-sub for all 213,106 →
D-05 population filters out NaN → n=0 → NaN threshold → placeholder raw-scale JSON kept →
100% Negative. (The "1/213106 geometry failure" was a genuine JTS annulus failure; the
other 213,105 went NaN silently via the null-key path, NOT the catch, so weren't counted.)

Fix: resolve the annulus key by matching the channel name against the object's actual
key set (`keySet().find { it.startsWith(channelName) && ...endsWith("mean") }`) instead of
assuming a "Cell:" compartment prefix. Added an A5b print of the REAL detection key set
and per-stage finite-value counters so the next run confirms the raw compartment reads
(`Nucleus: AF488-T3 mean` / `Cytoplasm: AF568-T2 mean`) are also valid.

See `.planning/phases/03-detection-script-and-single-section-end-to-end-test/03-GATE-FAILURE-D05.md`
for the (now superseded) original write-up.

## Chosen fix (user decision, 2026-07-10) — redesign D-05 for sparse markers
Replace nth-peak logic with a self-calibrating robust threshold computed at runtime
from each section's own bg-sub population:

    threshold = background_mode + k * (1.4826 * MAD)

- background_mode: mode/peak of bg-sub distribution (≈0; median acceptable proxy).
- MAD: median absolute deviation; 1.4826*MAD ≈ robust SD.
- k: single tunable seed. **Default k=3** (sweep 3–5 on this section, then lock as series seed).
- Apply to BOTH `Nucleus: AF488-T3 mean (bg-sub)` (Fos) and
  `Cytoplasm: AF568-T2 mean (bg-sub)` (TdT).
- Keep the safe-write guard (only overwrite bgsub JSON when derived threshold is finite).
- Keep the self-check print but compare the NEW strategy's output to a sanity band,
  not the raw cutoffs.

## Do NOT re-touch (already working)
- End-to-end run; D-04 local-bg annulus loop (try/catch; 1/213,106 geometry failure — negligible).
- Groovy parse-clean (n→cnt closure rename; verified via QuPath's bundled Groovy).
- Atlas region labeling + SC4 rollup + Excluded (DG-sg/VS) handling.

## Files
- `scripts/02_detect_classify.groovy` (canonical)
- `M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy` (byte-identical copy)
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/{Fos_Classifier_20x_bgsub,TdT_classifier_bgsub}.json`
- Replace: `derivePeakThreshold` closure, lines ~250–266.

## Evidence
- timestamp: 2026-07-10 — Root cause confirmed and documented in 03-GATE-FAILURE-D05.md
  during the 03-04 human QuPath run; self-check tripwire fired (NaN), placeholder JSONs kept.
- timestamp: 2026-07-10 — FIX IMPLEMENTED. Replaced the nth-histogram-peak
  `derivePeakThreshold` closure with `robustThreshold` = median + k·(1.4826·MAD)
  (k=3 seed), applied to BOTH bg-sub measures (Nucleus AF488-T3 / Cytoplasm AF568-T2).
  Removed the now-unused `ChannelHistogram` import + histogram constants
  (BIN_WIDTH/SMOOTH_KERNEL/PEAK_PROMINENCE/N_PEAK). Safe-write guard kept as
  finite-only (writes bgsub JSON iff derived threshold is finite; NaN keeps
  last-known-good). Self-check redesigned to a scale-free sanity band on the NEW
  strategy's output (finite, >0, sparse-but-non-zero positive fraction; posFrac==0
  explicitly flagged as reproducing the all-Negative failure) instead of the raw
  cutoffs 13000.4538/16766.4671. Edited canonical `scripts/02_detect_classify.groovy`
  and copied byte-identical to the M3 project copy (sha256 match:
  dd0006d65b1f…788cba). Untouched: D-04 annulus loop, atlas labeling, SC4 rollup,
  Excluded handling, n→cnt rename.
- timestamp: 2026-07-10 — CODE VERIFIED (GUI validation still pending, human).
  Both copies PARSE OK at Groovy CONVERSION phase (QuPath-bundled groovy-4.0.26.jar,
  Fiji JDK 21) — same method prior fixes were verified this session. Robust-threshold
  arithmetic unit-checked on a synthetic sparse population (10k background N(0,50) +
  300 positives N(800,80)): median≈2.75, robustSD≈51.78 (recovers true σ), thr(k=3)≈158,
  posFrac≈3.0% (PASS band); empty→NaN and all-equal→value(mad=0) edge cases confirmed.

- timestamp: 2026-07-10 — SECOND QuPath run (post-redesign) STILL 100% Negative, but the
  failure mode changed and exposed the TRUE cause. Log showed "Background-subtracted
  measures written for 213106 (D-04)" yet D-05 self-check reported n=0 / median=NaN /
  threshold=NaN for BOTH markers → derivation population empty. Traced to a write/read
  measurement-API split: D-04 wrote via `getMeasurementList().put()` (legacy, buffered
  until close) while all reads use `getMeasurements().get()` (Map view) → uncommitted
  writes invisible. Raw read at line 210 via getMeasurements() works (only 1/213106 NaN),
  proving the bug is the write path, not the key.
- timestamp: 2026-07-10 — TRUE FIX IMPLEMENTED. Changed both D-04 bg-sub writes
  (lines 218–219) from `d.getMeasurementList().put(...)` to `d.getMeasurements().put(...)`
  (commits immediately; self-consistent with all reads). Added an explanatory comment.
  Applied to canonical + M3 copy, byte-identical (sha256 bb43f5c9…4316ac). Parse OK at
  Groovy CONVERSION phase (QuPath-bundled groovy-4.0.23.jar, Fiji JDK 21). D-05 redesign
  left intact (correct for sparse markers once the population is non-empty).

## Eliminated
- hypothesis: "Sparse-marker unimodality → findPeaks returns 0 peaks → NaN" (original
  03-04 diagnosis). ELIMINATED — the histogram had 0 peaks because it had 0 data points
  (empty population), not because the distribution was unimodal. Same underlying
  empty-population bug in both runs; the peak/unimodal framing was a misattribution.
- hypothesis: "bg-sub writes never committed: `getMeasurementList().put()` buffered until
  close, invisible to `getMeasurements()` reads." ELIMINATED by experiment — changed both
  writes to `getMeasurements().put()`; the re-run produced BYTE-IDENTICAL output (still
  n=0). If the write path were the bug, n would have changed. The values were already NaN
  before being written, so the write API was irrelevant. (Kept the `getMeasurements().put()`
  form anyway — it's correct and self-consistent with reads, just not the fix.)
