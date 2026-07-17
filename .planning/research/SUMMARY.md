# v1.1 Project Research Summary

**Milestone:** First Full-Series Run — LA/BA Amygdala Engram (wBA1-3)
**Project:** TRAP2/Airyscan Whole-Brain Section Pipeline
**Researched:** 2026-07-17
**Overall Confidence:** MEDIUM

## Executive Summary

v1.1 scales the validated single-section (M3 hippocampus, v1.0) TRAP2 pipeline to a 5-section series on a new animal (wBA1-3), new region (amygdala LA/BA), and new imaging parameters (4 Z-planes, lower laser power). The **majority of required work is low-risk extension of v1.0's already-verified machinery**: multi-scene MIP conversion (pure I/O looping), LA/BA nucleus-anchored classification (same detection/colocalization rules as hippocampus), section→animal BraiAnalyse aggregation (off-the-shelf library), and per-region micron-coordinate export (proven transform + output formatting).

**Two features are true differentiators** requiring their own research and validation phases: (1) generalizable area-based density readout for compact-nuclei regions (DG as in-section test case, novel v1.1 work), and (2) registration speedup via DeepSlice batch inference / tissue-mask-bounded elastix (optional, currently unproven at scale).

**Five critical silent-count-corruption risks** require careful phase ordering and explicit verification gates: (1) the CR-01 region-labeling fix (smallest-area leaf) was validated only on laminar hippocampus — amygdala's non-laminar architecture may defeat the heuristic differently; (2) the k=3 robust-threshold seed was tuned at v1.0's laser power/Z-plane count, new 4-plane/lower-laser could shift signal-to-noise without obvious error signals; (3) MIP over fewer Z-planes risks under-projection, systematically dimming nuclei; (4) multi-scene CZI scene indexing is untested — an off-by-one or shuffled scene mapping silently mislabels physical sections; (5) a 5-section series is the first time this pipeline encounters tissue damage (folds, tears, bubbles) that ABBA/BraiAnDetect silently fail on.

**Critical blocker:** Stage-4's export script has a multi-entry bug — running `03_export_val01_metrics.groovy` via "Run for project" across 5 entries truncates output files, leaving only the 5th entry's data on disk. This must be fixed first, blocking all downstream aggregation phases.

## Key Findings

### Recommended Stack

**NO new package installations needed.** v1.1 extends v1.0's pinned tools (QuPath 0.6.0, elastix 5.2.0, conda envs unchanged).

**Three APIs newly exercised at scale, requiring validation:**

1. **`aicspylibczi` scene iteration** (`get_all_mosaic_scene_bounding_boxes()` + `read_mosaic(region=bbox)`): Verified installed (3.3.1); method names from web-sourced GitHub. `read_mosaic()` otherwise ignores the S dimension and fuses all scenes (the exact bug behind the unusable 32 GB merged OME-TIFF). **Requires 5–10 min smoke test** on real 16 GB CZI file before writing the loop. Risk: LOW if test passes; HIGH if scene indexing/order doesn't match physical layout.

2. **`braian.SlicedBrain.from_qupath()` + `AnimalBrain.from_slices()`** (verified on-disk, 1.0.5): `BrainSlice.from_qupath()` → `SlicedBrain.from_qupath(animal_dir, ...)` → `AnimalBrain.from_slices(sliced_brain, metric=SliceMetrics.SUM, densities=...)`. HIGH confidence for method signatures; default file naming (`results/_regions.tsv`) already matches the detection export. **Gap**: exact aggregation math (missing-section handling, area-weighting defaults) not fully documented — plan 1–2 hours integration testing.

3. **`qupath.opencv.ml.pixel.PixelClassifiers.createThreshold()` + `PixelClassifierTools.addMeasurementsToSelectedObjects()`** (area-based density): From javadoc excerpts; BraiAnDetect has no area/density feature, so build on QuPath core applied to the existing ABBA region annotations. **Requires 2-min Script Editor autocomplete check** against installed `QuPath.jar` before coding.

**Core technologies unchanged:**
- `deepslice` 1.2.8 — batch `predict()` + `propagate_angles()` + `enforce_index_spacing()` for multi-section registration speedup (zero new install).
- `brainrender` 2.1.20 — `Points(data)` wants a plain Nx3 micron array in (AP, DV, ML) order matching `allen_mouse_10um` (export contract only; visualization deferred).

**Blocked / conditional:**
- Masked elastix Affine+Spline is possible at the elastix CLI (`-fMask`/`-mMask`) but **ABBA's Fiji GUI wrapper does not expose a mask parameter** — using it means bypassing ABBA's GUI and hand-building the transform JSON. CONDITIONAL/experimental, not a default. No CUDA anywhere.

### Expected Features

**Table stakes (low-risk extensions):**
1. Multi-scene MIP conversion (extend `czi_mip.py`, loop the S dimension)
2. LA/BA nucleus-anchored classification (run existing `02_detect_classify.groovy` across 5 entries)
3. Brain-wide region-labeling validation (automate the Phase-4 CR-01 check across 5 sections)
4. Section→animal aggregation (BraiAnalyse `SlicedBrain` + `AnimalBrain`)
5. Full per-region micron export (add Atlas_X/Y/Z columns to export TSVs)

**Differentiators (v1.1 novel work):**
1. Generalizable area-based density readout — **percent-area-above-threshold** within a DAPI+ mask (Manders overlap is discouraged in the literature); a fraction, never a per-cell count; additive/parallel to nucleus counts. DG test case, reusable brain-wide.
2. Registration speedup — DeepSlice batch + shared-angle propagation as primary; tissue-mask-bounded elastix as optional stretch.

**Plausibility anchor:** closest matched TRAP2 study (anterior BLA, fear conditioning + remote recall) reports **~20–30% reactivation fraction (Double+/TdT+)** — the best available LA/BA sanity band (LOW confidence; verify against seed paper bioRxiv 2024.09.16.611953 and use v1.0 hippocampus bands as same-pipeline precedent). A chance-overlap gate `(m1+/DAPI+)×(m2+/DAPI+)×DAPI+_count` vs observed double+ (chi-square/z-test) is the accepted "above-chance" statistical check.

**Defer to v2+:** per-nucleus dense-segmentation (GPU cost), multi-animal statistics (need n>1), 3D visualization rendering.

### Architecture Approach

**Pure integration milestone:** no new paradigms, only 5× scaling of v1.0's 4-stage architecture. Three of four Stage-3 Groovy scripts (`01_load_abba_rois`, `run_braian_detection`, `02_detect_classify`) already operate per-entry and are "Run for project"-safe — **zero code changes** to scale 1→5. `crop_to_tissue.py` already exists/self-tested and slots in as an optional **Stage 1.5**, strictly before QuPath/ABBA import (the ABBA transform is tied to the exact pixel canvas). The area-based readout has a natural home: `02_detect_classify.groovy` already marks `DG-sg`/`VS` as `"Excluded"` — a new separate script writes disjoint measurement keys onto the same region annotations, never touching `PathClass`.

**Modified components:**
- `czi_mip.py` (scene-loop extension, argparse adoption)
- `03_export_val01_metrics.groovy` (fix multi-entry truncation bug; add Atlas_X/Y/Z µm columns via the proven `AtlasTools.getAtlasToPixelTransform` path with mm→µm ×1000)

**New components:**
- `04_area_density.groovy` (area-based density, parameterized by region acronym)
- `validate_region_labels.py` (brain-wide CR-01 audit across 5 sections)
- `aggregate_animal.py` (BraiAnalyse section→animal roll-up)
- `render_pointcloud.py` (brainrender CCFv3-micron export)

### Critical Pitfalls (Silent-Count-Corruption Risks, ordered first)

**1. CR-01 fix may fail differently on amygdala:** smallest-area leaf heuristic validated only on laminar hippocampus; amygdala LA/BA are adjacent, comparable-size, non-nested nuclei. **Prevention**: re-run the CR-01 audit on the first amygdala section (inspect `region_label` distribution, `is_leaf` consistency across hemispheres, zero-cell rollup assertion) before trusting the series. Pull the rollup-acronym assertion list verbatim from `04-REVIEW.md`.

**2. k=3 threshold seed may drift at new laser power/Z-count:** lower laser changes photon statistics, not just brightness. **Prevention**: re-run D-05 gates AND compare background-subtraction histogram shape vs the v1.0 reference; if drift, re-sweep k (3–5) and re-lock — do not just confirm D-05 is non-empty.

**3. Under-projection at fewer Z-planes:** 4-plane MIP over a narrower range risks missing peak focus, systematically dimming nuclei / reintroducing DAPI blobs. **Prevention**: re-run an OPT-01-style plateau check; confirm the 4-plane range vs v1.0's stack; visually inspect DAPI quality.

**4. Multi-scene CZI scene→section mapping untested:** off-by-one/shuffle silently mislabels physical sections (project already hit this with the 32 GB merged file). **Prevention**: print + manually verify each scene's bounding box/morphology against known physical layout; name files with scene index verbatim.

**5. Tissue damage in a 5-section series undetected:** ABBA/BraiAnDetect don't error on folds/tears — they produce locally plausible wrong counts. **Prevention**: per-section visual tissue-QC checklist before registration; any exclusion must be a priori + principled (documented rule, not outcome-driven).

## Implications for Roadmap

**Suggested phase structure (dependency-ordered):**

| # | Phase | Rationale | Delivers | Spike? |
|---|-------|-----------|----------|--------|
| 0 | Stage-4 Export Fix | Blocking — truncation bug must be fixed before aggregation | Per-entry output filenames; Atlas_X/Y/Z µm columns | No |
| 1 | Multi-Scene MIP + scene-identity verification | Nothing starts without 5 verified MIPs | 5 MIP OME-TIFFs, verified AP order | Yes — aicspylibczi scene API (5–10 min) |
| 2 | Registration Speedup (optional) | De-risks manual BigWarp; parallel with Phase 3 | DeepSlice-batch flow; optional crop+elastix trial on one section | Conditional — masked-elastix/amygdala untested |
| 3 | Imaging Re-Validation | Gates whether k=3 needs re-locking at new params | D-05 gates + distribution-shape comparison; lock or re-sweep k | No |
| 4 | LA/BA Classification + Brain-wide Region Validation | Core deliverable; amygdala-specific CR-01 re-check | Classified cells + per-region tables + validation report | No |
| 5 | Area-Based Density Readout | Novel differentiator; reusable method + DG crosswalk | `04_area_density.groovy` + non-separability trigger rule + crosswalk check | Yes — QuPath PixelClassifiers (2 min) + crosswalk |
| 6 | Section→Animal Aggregation | First animal-level roll-up | Animal-level table + per-region section-coverage tally | Yes — BraiAnalyse aggregation defaults (1–2 h) |
| 7 | Micron Export + Point-Cloud | Complete pipeline; cells in CCFv3 µm space | Persisted Atlas_X/Y/Z µm + brainrender point cloud | No |

**Ordering principles:** Phase 0 first (blocks 5–6); Phase 1 next (hard dependency); Phases 2–3 parallel (speedup optional, re-validation mandatory); Phase 4 core (depends on 1–3, includes amygdala CR-01 re-check); Phase 5 novel (can defer if 6 is priority); Phase 6 depends on 4 + 0; Phase 7 parallel with 6.

## Confidence Assessment

| Area | Level | Rationale |
|------|-------|-----------|
| Stack | MEDIUM | HIGH for installed tools (braian/brainrender verified on-disk). LOW-MEDIUM for aicspylibczi scene API + QuPath PixelClassifiers (web/javadoc-sourced, not run against real file/jar). |
| Features | MEDIUM | HIGH for table-stakes (routine v1.0 extensions). LOW-MEDIUM for differentiators + amygdala plausibility bands (one matched paper, extrapolated). |
| Architecture | HIGH | Grounded in real v1.0 scripts on-disk; Stage-4 multi-entry bug concrete + documented. |
| Pitfalls | MEDIUM-HIGH | Pitfalls 1–3 well-motivated extrapolations to new region/params; 4–5 concrete from project history. |
| Overall | MEDIUM | Well-scoped integration milestone with proven machinery; limited by new APIs at scale + novel measurements requiring validation. All gaps have clear validation gates. |

### Gaps Requiring Resolution During Planning

1. aicspylibczi scene API — smoke test on real 16 GB CZI (Phase 1, 5–10 min, high priority).
2. QuPath PixelClassifiers signatures — Script Editor autocomplete check (Phase 5, 2 min).
3. BraiAnalyse aggregation math — missing-section handling + area-weighting vs project stats conventions (Phase 6, 1–2 h).
4. Amygdala tissue-mask / LA/BA boundary behavior — visual verification on one section (Phase 2/4, 1–2 h).
5. TRAP2 LA/BA plausibility bands — verify vs bioRxiv 2024.09.16.611953; fall back to v1.0 hippocampus bands.
6. Whether the 4-Z-plane acquisition covers the same total Z-range as v1.0's stack — determines OPT-01 plateau transfer.

## Sources

Synthesized from `.planning/research/STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md` (v1.1, 2026-07-17). API facts marked HIGH were verified by direct import/inspection of the installed `braian` 1.0.5 and `brainrender`/`brainglobe-atlasapi` packages and by reading the on-disk v1.0 scripts; quantitative bands and web-sourced API names are marked LOW-MEDIUM and gated by the spikes above.

---
*Research synthesized: 2026-07-17*
