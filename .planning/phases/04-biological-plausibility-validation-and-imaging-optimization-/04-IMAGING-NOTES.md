# 04-IMAGING-NOTES.md — Imaging Optimization Notes (OPT-01/02/03)

**Phase:** 04-biological-plausibility-validation-and-imaging-optimization-
**Section under audit:** M3 hippocampus, 20x Airyscan (`Automated Cell Counting/M3 Hippocampus 20x 062026.czi`)
**Purpose:** Forward-looking acquisition recommendations for the next imaging session and the full-series run — Z-plane count, raw-vs-MIP storage policy, and per-subfield resolution requirement. This is a separate document from `04-VALIDATION.md` (per D-05 — different audience/lifetime: this record informs *acquisition*, not the current section's biological plausibility).

**Claim labeling convention (D-06):** every numeric claim below is tagged `[measured]` (read directly off the CZI metadata, filesystem, or an existing region-TSV this session — see `scripts/opt01_zplane_audit.py`) or `[inferred]` (derived from standard optics formulas, extrapolation, or reasoned argument, not a direct instrument/file read). No metric in this document is framed as a pass/fail gate.

---

## OPT-01 — Z-plane audit

### Measured acquisition facts

Read directly from `Automated Cell Counting/M3 Hippocampus 20x 062026.czi` via `scripts/opt01_zplane_audit.py` (metadata-only read, `aicspylibczi`):

- **Z-planes acquired: 6** `[measured]`
- **Z-step: 2.0 µm/plane** `[measured]`
- **Total acquired Z-range: 10.0 µm** (5 intervals × 2.0 µm) `[measured]`
- Pixel size (X/Y): 0.690535 µm/px `[measured]` — matches the value already hard-coded in `czi_mip.py`'s `PIXEL_SIZE_UM`
- Objective: Plan-Apochromat 20x/0.8 M27, air, NA=0.8 `[measured, from CZI metadata]`
- 3 channels, 187 mosaic tiles, 1 scene `[measured]`

All three existing MIP variants (`M3_20x_Z2_single.ome.tiff` — single plane, `M3_20x_MIP_Z1-3.ome.tiff` — 3-plane, `M3_20x_hybrid_dapiZ2_mipZ0-2.ome.tiff` — hybrid DAPI-Z2/markers-Z0-2) are all sub-ranges of this same 6-plane, 10 µm-deep acquisition, not independently acquired stacks.

### The plateau argument (empirical, 2-of-3)

Only the **3-plane variant** has a confirmed classified `data.qpdata` (Phase 3). The **hybrid variant** has a BraiAnDetect region-TSV from an earlier detection pass. The **single-plane (Z2) variant has never been detection-run** — no region-TSV or classified `data.qpdata` exists for it on disk.

Comparing the two available whole-section (`Root`) DAPI counts:

| Variant | Z-range used | Root `Num DAPI-T4` |
|---|---|---|
| 3-plane (`MIP_Z1-3`) | Z1–Z3 (4 µm sub-range) | **213,100** `[measured]` |
| hybrid (`dapiZ2_mipZ0-2`) | DAPI from Z2, markers MIP'd Z0–Z2 | **209,888** `[measured]` |
| **Percent difference** | | **1.51%** `[measured]` |

These two DAPI counts, taken from different sub-ranges of the same acquisition and different projection strategies, land within ~1.5% of each other. That is small enough to read as evidence the DAPI count is already near-plateaued across these sub-range variants at 20x — adding planes beyond a 3-plane MIP is not obviously buying additional detected nuclei.

**Scope limit (explicit, per RESEARCH.md Open Question 2 / this plan's resolution):** this is a **2-of-3, partial empirical comparison**. The single-plane (Z2) variant was never run through `02_detect_classify.groovy` or BraiAnDetect, so there is no third data point confirming whether a *single* plane alone would also plateau at the same count, or whether the 3-plane vs. hybrid agreement is itself coincidental (e.g., both variants happen to include Z2, the sharpest-focus plane). A full three-way empirical confirmation — running the single-plane variant through detection+classification — is **deferred as an optional GUI step**, not performed in this phase (Rule per CONTEXT.md: documentation/analysis phase, no new detection runs are in scope here beyond what Phase 3 already produced).

### Recommendation — concrete target plane count

**Target for the next imaging session: 3 Z-planes at the current 2.0 µm step (4 µm sub-range), anchored on the sharpest-focus mid-plane.** This is the variant with the confirmed classified run (Phase 3's verified biology) and the plateau comparison shows the hybrid single-DAPI-plane projection tracks it within 1.5%. Acquiring the full 6-plane stack is not shown to add meaningfully more detected nuclei at this NA/exposure, so trimming to 3 planes (or, pending the deferred single-plane confirmation, potentially fewer) would reduce acquisition time and file size for the full series without an established biological cost.

This recommendation should be treated as provisional until the deferred single-plane classification run closes the 2-of-3 gap — if a future check shows a single plane also plateaus at ~210k, the target could drop to 1 plane; if it diverges materially, 3 planes should be kept as the floor.

### Nyquist-for-3D-reconstruction — background only, NOT the operative question

Standard confocal axial-resolution formula (`FWHM_axial = 0.88·λ_em / (n − √(n²−NA²))`) at this project's NA=0.8, air (n=1): `n − √(n²−NA²) = 1 − √(1−0.64) = 0.4`, giving FWHM_axial ≈ 1.0–1.3 µm across the three emission channels `[inferred, formula]`. True Nyquist sampling for 3D reconstruction/deconvolution (z-step ≤ axial-resolution/2.3) would require **~0.26–0.33 µm/plane** `[inferred]` — this project's acquired step (2.0 µm) is roughly 6–8× coarser than that.

**This is explicitly NOT the operative question for OPT-01.** Per `CLAUDE.md` and `.claude/CLAUDE.md`, this project's own definition of "3D" is the **atlas-space cell point cloud**, not physical tissue reconstruction — sub-micron axial fidelity for deconvolution/reconstruction is out of scope by design. The operative question is only "does the MIP miss real signal," which is what the plateau comparison above addresses empirically. Cited here only so a future reader does not mistake the coarse 2 µm step for an acquisition error.

### Section-thickness cross-check

Vibratome sections of mouse brain for immunohistochemistry are commonly cut at **30–50 µm** thickness (40 µm particularly common), per multiple independent vendor/protocol sources `[inferred, cross-checked general practice — NOT confirmed against this project's own wet-lab protocol]`. The acquired 10 µm Z-range therefore covers only **~20–33%** of a typical vibratome section's physical thickness `[inferred]`.

This is consistent with the limiting factor being **imaging depth penetration at 20x/0.8 NA air into a thick vibratome section** (light scattering / working-distance constraints), not a deliberate choice to sample too little of the tissue with too few planes. In other words: the 6-plane, 10 µm acquisition likely already reflects how deep this objective can usefully image into the section, and the plane-count question (how many planes across that same 10 µm) is separable from the depth-coverage question (whether 10 µm is "enough" of the section).

**Open item:** this section's actual cut thickness has not been confirmed against wet-lab notes/protocol this session — the 30–50 µm figure is a general reference point, not a project-specific fact. Recommend checking the acquisition protocol or wet-lab notes before treating the ~20–33% coverage figure as more than an order-of-magnitude sanity check.

---

## OPT-02 — File-size / storage tradeoff

### Measured sizes

| File | Size | Notes |
|---|---|---|
| Raw CZI (`M3 Hippocampus 20x 062026.czi`) | 9,004,830,144 B ≈ **9.00 GB** `[measured]` | 6 Z × 3 C × 187 mosaic tiles × 1024×1024, uint16, not yet stitched |
| MIP OME-TIFF (`M3_20x_MIP_Z1-3.ome.tiff`) | 968,910,236 B ≈ **0.97 GB** `[measured]` | Stitched, single-plane-per-channel, uint16 |
| **Raw : MIP ratio** | **~9.29×** `[measured]` | MIP is ~10.8% of raw CZI size |

### Full-series projection

This machine has **854 GB free NVMe** (per `CLAUDE.md`). At the measured per-section sizes:

- **Raw-CZI-only storage:** ~9 GB/section → **~90 sections** storable before hitting capacity `[inferred projection]`
- **MIP-only storage:** ~1 GB/section → **~800+ sections** storable `[inferred projection]`

This project's `.gitignore` already excludes all microscopy data from git (`*.tif/*.tiff/*.czi/*.lif`), so the tradeoff is purely local-disk-capacity vs. reprocessing-flexibility, not a git-repo-size concern.

### Recommendation

**Keep the raw CZI** for the current single-section validation run and for any section where the OPT-01 plateau test above is inconclusive (i.e., where a different Z-sub-range might need to be re-derived later — keeping the raw stack preserves that option). **MIP-immediately-and-discard-raw** for the bulk of the full series once the OPT-01 plane-count target is locked (i.e., once the deferred single-plane confirmation closes the 2-of-3 gap and the target plane count is no longer provisional) — the ~9.3× storage multiplier is a meaningful capacity cost across ~90+ sections, and the section-thickness cross-check above suggests the acquired Z-range is already governed by imaging-depth limits at this NA rather than a deliberately generous margin, so little practical flexibility is being given up by discarding raw once the plane count is confirmed.

---

## OPT-03 — Resolution assessment (per-subfield Airyscan need)

### Measured optical parameters

- **Objective/NA:** Plan-Apochromat 20x/0.8, air `[measured, from CZI metadata]` — a mid-range NA for an air objective (20x air objectives commonly range NA 0.5–0.8; 0.8 is at the high end for air, but well below oil/water-immersion objectives at similar or higher magnification, e.g., NA 1.0–1.4).

### Estimated resolution at NA=0.8 (inferred, formula-derived)

Standard confocal-equivalent formulas, always paired with "at NA=0.8" per the extrapolation caveat below:

- **Confocal-equivalent lateral resolution** (`0.4·λ/NA`): **~230–290 nm** across the three emission channels (DAPI/Fos-488/TdTomato-568/581em) `[inferred, formula]`
- **Confocal-equivalent axial resolution** (FWHM, formula above): **~1.0–1.3 µm** `[inferred, formula]`
- **With the Airyscan ~1.7× relative gain extrapolated to NA=0.8:** lateral **~135–170 nm**, axial **~0.6–0.75 µm** `[inferred — extrapolation, NOT a verified Zeiss claim at this NA]`. Zeiss's marketed Airyscan 2 headline numbers (140 nm × 140 nm × 350 nm X/Y/Z) are demonstrated on high-NA objectives (typically NA ~1.4 oil) — applying the same *relative* 1.7× improvement factor to this project's NA=0.8 air objective is an extrapolation, not a verified figure for this NA (RESEARCH.md Pitfall 3, Assumptions Log A3).

### What actually drives classification

The nucleus-anchored classification pipeline (per `CLAUDE.md`'s non-negotiable rule) needs three measurements, none of which require Airyscan-grade lateral super-resolution:

1. **Nucleus segmentation** — DAPI nuclei are large (>7 µm diameter, 50–150 µm² target area) relative to even confocal-limited lateral resolution (~230–290 nm) — ordinary confocal-grade lateral resolution is more than adequate for segmenting objects this large.
2. **TdTomato cytoplasmic-ring intensity** — a compartment-mean measurement over a fixed-µm expansion ring, not a fine-structure measurement.
3. **Fos nuclear-mean intensity** — a compartment-mean measurement, not a fine-structure measurement.

**None of the three classification-relevant measurements require Airyscan-grade lateral super-resolution** — they are all compartment-mean intensity measurements on already-large (>7 µm) objects.

### Where resolution genuinely matters: nucleus separability in dense layers

The place resolution actually matters is **nucleus separability in dense cell layers** — and this is already empirically answered by Phase 2's locked finding (`02-LOCK-RECORD.md`, D-04): "CA1 nuclei cleanly separable (confirmed by researcher). DG granule layer not per-cell separable (expected) → density-only, `DG-sg` excluded from marker classification." `[measured]`

| Subfield | Nucleus packing | Per-cell separable at 20x/0.8 | Airyscan resolution need |
|---|---|---|---|
| **CA1** (pyramidal) | Moderate-dense, single layer | **Yes** — confirmed cleanly separable `[measured, Phase 2]` | Standard confocal likely sufficient; Airyscan is a comfortable margin, not clearly required |
| **CA2/CA3** (pyramidal) | Same cytoarchitecture family as CA1 | Not explicitly re-tested — reasonable to expect similar to CA1 `[inferred, extrapolated from CA1, not independently verified]` | Same expectation as CA1, unverified — flag for a quick visual QC in the full series |
| **DG-sg** (granule cell layer) | Very dense, tightly packed | **No** — not per-cell separable even at 20x Airyscan; excluded from marker classification (density-only) `[measured, Phase 2]` | Would need substantially higher NA/resolution (oil immersion) or a different modality — Airyscan at NA 0.8 does not solve this |
| **DG-mo / DG-po** (molecular/polymorph layers) | Sparser than DG-sg | Included in Phase 2/3 classification (not excluded) `[measured, Phase 2]` | Comparable to CA1 |
| **Cortex** (e.g. SSp, reference) | Moderate, layered | Density measured without issue in Phase 2 reference table `[measured, Phase 2]` | Comparable to CA1 |

### Recommendation

Airyscan at 20x/0.8 NA is **not required for successful classification** in any subfield except where nucleus *separability* (not marker-intensity measurement) is the bottleneck — and even Airyscan does not solve DG-sg's separability problem at this NA (already empirically excluded, not a new gap).

- **CA1, CA2/CA3, DG-mo, DG-po, and general cortical survey regions:** a lower-power confocal survey (non-Airyscan, same or lower NA) would plausibly suffice for cell-count/density purposes, since the limiting factor is nucleus packing density relative to lateral resolution, and Airyscan's gain here is a comfortable margin rather than a hard requirement. `[inferred]`
- **DG-sg:** stays density-only regardless of resolution tier chosen, unless a fundamentally different imaging strategy (oil immersion, higher NA, or accepting non-single-cell density) is adopted. `[inferred, grounded in the Phase-2 measured finding]`
- **CA2/CA3** are extrapolated from CA1's confirmed separability, not independently re-tested — flag for a quick visual QC in the full series before relying on this row. `[inferred, Assumptions Log A5]`

**This recommendation needs empirical confirmation before being treated as locked guidance:** a side-by-side same-region acquisition at Airyscan vs. non-Airyscan confocal settings has not been performed — no such paired acquisition exists on disk to compare. This document provides the optical reasoning, not a live comparison.

### TRAP2-paper acquisition-parameter provenance (honest hedge)

The phase's cited primary source — bioRxiv 2024.09.16.611953 / F1000Research 15:410 (Cabrera et al.) — returned **HTTP 403 Forbidden** on both the bioRxiv and F1000Research URLs this session, consistent with the same block from an earlier research pass. The paper's own objective/NA/Z-stack acquisition parameters could **not be verified** this session and are not cited as a direct comparison point above. If institutional/authenticated access to bioRxiv or F1000Research becomes available in a future session, re-attempt this fetch — the paper's own acquisition choices would be a strong, directly-comparable OPT-03 anchor.

---

*Phase: 04-biological-plausibility-validation-and-imaging-optimization-*
*Written: 2026-07-17*
