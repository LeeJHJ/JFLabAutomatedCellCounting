# Imaging Optimization Notes — TRAP2 / Airyscan 20x (M3 hippocampus, first run)

Evidence-based acquisition adjustments to try on the ZEN / Airyscan acquisition PC before
scaling to the full series. Derived from the M3 062026 CZI (6 Z-planes, 3 ch:
AF568-T2/TdT, AF488-T3/Fos, DAPI-T4) and the Phase-3 detection run.

**Do at the scope (GUI, ZEN Blue) — this box only ingests OME-TIFFs; ZEN is not installed here.**

---

## What we found in the current data (the "why")
- **DAPI is saturated.** Full-res read gave DAPI `p99 = 65535` (clipping at the 16-bit
  max), while Fos `p99 ≈ 36,500` and TdT `p99 ≈ 16,000` are fine. Saturated DAPI blooms
  and fuses touching nuclei → the "large blobs" that hurt segmentation.
- **3-plane MIP over-projects.** Focus survey (variance-of-Laplacian) across all 6 Z-planes
  was nearly flat (~5% variation) — every plane is near-focus. DAPI and Fos are BOTH
  sharpest at Z2 (axial chromatic offset ≈ 0 planes at the tested region). So MIP'ing more
  planes doesn't add focus, it just stacks axially-adjacent nuclei on top of each other.
  Nucleus separation degraded monotonically single-plane → 2-plane → 3-plane → 6-plane.
- **Implication:** a single well-focused plane (or 2) segments far cleaner AND keeps DAPI/Fos
  colocalization intact (they co-focus). See `plane_experiment_dapi.png` /
  `plane_experiment_overlay.png` in the phase-03 folder.

---

## Adjustments to try, in priority order

### 1. Fix DAPI exposure (highest impact — direct evidence of clipping)
- Lower DAPI **laser power** and/or **detector gain (Master Gain)** and/or **exposure/pixel
  dwell** until the brightest nuclei sit just below saturation.
- Use ZEN's **Range Indicator** (over/under-exposure display) in Live: red (saturated) pixels
  in nuclei should disappear. Aim for the brightest DAPI at ~80–90% of the display max, not
  clipped at 100%.
- Dim-but-separated nuclei segment better than bright-but-merged. Do not "expose for
  visibility" — expose for dynamic range.

### 2. Rethink the Z-stack / projection strategy
- The section is optically thin enough that all 6 planes are near-focus. Options:
  - **Acquire fewer, well-centered planes** (e.g., 2–3 tightly around best focus), OR
  - Keep a short stack but **project fewer planes for segmentation** (a single best-focus
    plane, or a 2-plane max) — over-projection is what merges nuclei.
- If you keep MIP for the marker channels (TdT is cytosolic and can benefit from a small
  MIP), you can still **segment nuclei on a single DAPI plane** and measure markers on the
  MIP — best of both. (We can wire this into the conversion script.)
- Set the **Z-step at Nyquist** for the objective (ZEN's "Optimal" button), don't over-slice.

### 3. Channel alignment / chromatic correction
- Apply ZEN **Channel Alignment** (chromatic-aberration correction) during/after Airyscan
  processing. Our tested region showed ~0 axial offset, but verify it holds across the
  whole section (edges/tile seams can drift).

### 4. Airyscan processing settings
- Use **Airyscan SR (2D)** processing at the **auto/recommended filter strength**. Avoid
  manually over-filtering (too-strong Wiener/deconvolution fuses adjacent structures and
  can create ringing that looks like extra objects).
- Keep the SAME Airyscan processing recipe for every section in the series.

### 5. Sampling / magnification for dense layers
- At 20x, `~0.69 µm/px` is coarse for the densest layers (CA pyramidal, DG granule —
  already the hardest to segment). Consider a **higher zoom** or **40x** for those layers,
  or accept that the tightest cell-body layers may need exclusion (DG-sg already excluded).
- Confirm **XY pixel size at/near Nyquist** for the objective NA (ZEN "Optimal").

### 6. Consistency across the series (for comparable thresholds/stats)
- **Lock laser power, gain, exposure, Z-range, and Airyscan recipe** once tuned, and reuse
  for every section. The D-05 threshold is self-calibrating per section, but consistent
  acquisition keeps the background model and detection params stable.
- Keep Fos and TdT **below saturation** too (currently OK) — a saturated marker channel
  destroys the intensity gradient the classifier relies on.

---

## Quick pre-flight checklist at the scope
- [ ] DAPI Range Indicator shows no saturated (clipped) nuclei
- [ ] Fos and TdT also unsaturated
- [ ] Z-step = Optimal/Nyquist; Z-range trimmed to the in-focus slab
- [ ] Channel alignment applied
- [ ] Airyscan SR, auto filter, same recipe as prior sections
- [ ] Laser/gain/exposure identical to the locked series settings
