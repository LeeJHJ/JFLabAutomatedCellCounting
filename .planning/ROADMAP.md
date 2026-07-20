# Roadmap: M3 Section Pipeline — TRAP2 / Airyscan

**Project:** TRAP2 Section Pipeline (vibratome + Airyscan → Allen CCFv3)
**Core Value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region across a registered section series, with locked detection parameters and imaging-optimization notes ready to scale brain-wide.
**Created:** 2026-07-01 · v1.1 roadmap added 2026-07-17

---

## Milestones

- ✅ **v1.0 Single-Section Validation Run** — Phases 1-4 (shipped 2026-07-17)
- 🚧 **v1.1 First Full-Series Run — LA/BA Amygdala Engram (wBA1-3)** — Phases 5-10 (in progress)

Full v1.0 archive: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

---

## Phases

<details>
<summary>✅ v1.0 Single-Section Validation Run (Phases 1-4) — SHIPPED 2026-07-17</summary>

- [x] Phase 1: Atlas Registration and ROI Loading (3/3 plans) — completed 2026-07-02
- [x] Phase 2: Detection Parameter Lock (2/2 plans) — completed 2026-07-09
- [x] Phase 3: Detection Script and Single-Section End-to-End Test (4/4 plans) — completed 2026-07-16
- [x] Phase 4: Biological Plausibility Validation and Imaging Optimization Notes (3/3 plans) — completed 2026-07-17

Full phase details (goals, success criteria, plans) archived in [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md).

</details>

### 🚧 v1.1 First Full-Series Run — LA/BA Amygdala Engram (wBA1-3) (In Progress)

**Milestone Goal:** Run animal wBA1-3's full 5-section series end-to-end to quantify TRAP2/tdTomato engram tagging + Fos reactivation across the LA/BA amygdala — validating re-optimized imaging, cutting registration effort, standing up a generalizable area-based readout for compact-nuclei regions, and producing animal-level aggregated counts + a CCFv3 point cloud.

**Ordering principles (research-derived):** Scaffolding first (5 verified MIPs + fixed batch export gate everything and unblock aggregation) → registration speedup and imaging re-validation before classification (imaging re-validation is mandatory and gates whether detection params re-lock) → classification carries the amygdala-specific region-labeling re-audit → area-based readout and terminal aggregation/export are the downstream readouts. Registration + QuPath detection are human-in-the-loop GUI steps: the executor authors the scripts, the operator runs the GUI.

- [x] **Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity** - Convert the processed CZI to 5 identity-verified section MIPs and fix the multi-entry export blocker (completed 2026-07-19)
- [x] **Phase 6: Registration Speedup** - Register the 5-section series with materially less manual effort (DeepSlice batch + reduced-landmark BigWarp; masked-elastix prototype trialed under an a-priori accept/reject rule) (completed 2026-07-20)
- [ ] **Phase 7: Imaging Re-Validation (New 4-Plane / Lower-Laser Params)** - Re-run D-05 QC gates and re-lock the k threshold seed only on drift; confirm the 4-plane MIP is not under-projected
- [ ] **Phase 8: LA/BA Classification + Brain-Wide Region-Labeling Validation** - Nucleus-anchored TdT+/Fos+/Double+ across all 5 sections over the amygdala ROI, with the CR-01 fix re-audited on non-laminar LA/BA
- [ ] **Phase 9: Generalizable Area-Based Density Readout** - Region-parameterized percent-area-above-threshold within a DAPI+ mask; additive/parallel to nucleus counts; DG granule layer as the test case
- [ ] **Phase 10: Animal-Level Aggregation + Atlas-Space Export & Point Cloud** - Roll up 5 sections to one wBA1-3 animal table, persist per-cell CCFv3 micron coords, render the brainrender point cloud

## Phase Details

### Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity

**Goal**: Establish data integrity at both ends of the series before it runs — the 16 GB processed CZI becomes 5 identity-verified section MIP OME-TIFFs, and the export script writes correct per-entry output across all 5 sections without truncation.
**Depends on**: Phase 4 (v1.0 pipeline, shipped)
**Requirements**: CONV-01, CONV-02, EXP-02
**Success Criteria** (what must be TRUE):

  1. `czi_mip.py` emits exactly 5 MIP OME-TIFFs (one per scene) from `-001-07_processed.czi` with no scene fusion, each carrying its physical pixel size in embedded OME-XML.
  2. Each output MIP is confirmed to its correct physical section and AP order via a printed scene bounding-box / morphology check the operator can visually verify (scene index written verbatim into the filename).
  3. Running `03_export_val01_metrics.groovy` "for project" across all 5 QuPath entries produces 5 distinct per-entry output files with no cross-section TSV truncation — each file contains only its own section's rows.
  4. The multi-scene scene API (`get_all_mosaic_scene_bounding_boxes` + `read_mosaic(region=bbox)`) is smoke-tested on the real CZI before the conversion loop is trusted (verification spike, ~5-10 min).

**Plans**: 3/3 plans complete
Plans:
**Wave 1**

- [x] 05-01-PLAN.md — Wave 1: multi-scene MIP converter (czi_mip.py CLI + per-scene region= loop + pre-flight bbox assertion + scene-identity artifact) (CONV-01, CONV-02)
- [x] 05-02-PLAN.md — Wave 1: per-entry export fix (03_export_val01_metrics.groovy stem from entry name, dual-copy + verify_export_integrity.py) (EXP-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 05-03-PLAN.md — Wave 2: blocking human-verify of scene identity + TdT/Fos channel identity before the series is trusted (CONV-01, CONV-02)

**Notes**: EXP-02 is sequenced here (not at aggregation time) because it is a blocking prerequisite for AGG-01 in Phase 10. All work is scriptable — no GUI dependency.

### Phase 6: Registration Speedup

**Goal**: The 5-section series is atlas-registered to Allen CCFv3 with materially less manual effort than v1.0's per-section-from-scratch pass, via DeepSlice batch inference + shared-angle propagation, with an experimental masked-elastix prototype trialed under an a-priori accept/reject rule.
**Depends on**: Phase 5 (needs the 5 verified MIPs)
**Requirements**: REG-03, REG-04, REG-05
**Success Criteria** (what must be TRUE):

  1. DeepSlice batch `predict()` + angle propagation produces AP/angle estimates for all 5 sections in one pass, and the operator confirms the registered atlas overlay fits tissue on each section.
  2. A reduced-landmark BigWarp pass is applied across all 5 sections and hits a documented per-section effort target below the v1.0 5-15 min manual baseline.
  3. The masked-elastix prototype (`crop_to_tissue.py` DAPI mask → elastix Affine/Spline outside ABBA's GUI) is trialed on exactly one section, compared to DeepSlice-only on fit quality + time, and kept or rejected per the pre-declared rule — the decision is recorded either way.

**Plans**: 5/5 plans complete
Plans:

**Wave 1** *(executor-authored, autonomous)*

- [x] 06-01-PLAN.md — Wave 1: REG-05 elastix trial scripts + params (extract_atlas_plate.py, elastix_trial_harness.py, Par_Affine.txt/Par_BSpline.txt; all --self-test) (REG-05)
- [x] 06-02-PLAN.md — Wave 1: operator-record scaffolds (06-REG03-SOP.md native-DeepSlice params, bigwarp_effort_log.csv template, 06-REG05-FINDINGS.md a-priori rule) (REG-03, REG-04, REG-05)

**Wave 2** *(operator GUI, blocking-human)*

- [x] 06-03-PLAN.md — Wave 2: operator runs native ABBA DeepSlice-Local on the 5 sections, confirms per-section overlay fit, resolves D-04 angle + D-05 outliers (REG-03)

**Wave 3** *(operator GUI, blocking-human)*

- [x] 06-04-PLAN.md — Wave 3: operator reduced-landmark amygdala BigWarp across all 5, logs ≤~5 min/section wall-clock, identifies worst-fitting section D-06 (REG-04)

**Wave 4** *(elastix trial + operator judgment)*

- [x] 06-05-PLAN.md — Wave 4: masked-elastix trial on the one worst-fitting section, operator a-priori D-07 keep/reject recorded either way (REG-05)

**Notes**: Human-in-the-loop — executor authors the elastix/atlas-plate scripts + operator-record scaffolds; the operator runs the ABBA/BigWarp GUI. REG-03 uses ABBA's native "DeepSlice Registration (Local)" command (no run_deepslice.py — 06-CONTEXT ⟳ RESOLUTION). REG-05 is scoped as a single-section experiment so it cannot balloon.

### Phase 7: Imaging Re-Validation (New 4-Plane / Lower-Laser Params)

**Goal**: Detection and classification are confirmed valid on the new imaging parameters so classification runs on trustworthy signal — the D-05 QC gates are re-run and the k robust-threshold seed is re-locked only if it has drifted.
**Depends on**: Phase 5 (new-param MIPs); may proceed in parallel with Phase 6, which supplies a registered section for region-scoped QC
**Requirements**: IMG-01, IMG-02
**Success Criteria** (what must be TRUE):

  1. The D-05 detection-QC gates are re-run on the new-param MIPs and the background-subtraction distribution shape is compared against the v1.0 reference — the comparison is recorded, not merely confirmed non-empty.
  2. The k robust-threshold seed is either re-confirmed at k=3 or re-swept (3-5) and re-locked, with the drift decision documented.
  3. An OPT-01-style plateau check + visual DAPI-blob inspection confirms the 4-plane MIP is not under-projected, and the new Z-range vs v1.0's stack is documented.

**Plans**: TBD
**Notes**: Detection QC is a human-in-the-loop QuPath run — executor authors the QC harness; the operator runs BraiAnDetect. Gates Phase 8: if the seed drifted, it is re-locked here before classification.

### Phase 8: LA/BA Classification + Brain-Wide Region-Labeling Validation

**Goal**: Nucleus-anchored TdT+/Fos+/Double+ classification runs across all 5 sections over the LA/BA amygdala ROI producing per-region primary counts, and the CR-01 smallest-area-leaf region-labeling fix is re-audited on non-laminar amygdala to prove zero cells leak into parent rollups.
**Depends on**: Phase 6 (registered series) and Phase 7 (re-locked detection params)
**Requirements**: CLASS-02, LABEL-01
**Success Criteria** (what must be TRUE):

  1. `02_detect_classify.groovy` runs across all 5 sections producing non-zero TdT+/Fos+/Double+/Negative classes with atlas region labels over the LA/BA amygdala ROI (same detection + nucleus-anchored colocalization rules as v1.0).
  2. Per-region primary counts are produced for the amygdala subregions across the full series.
  3. The brain-wide region-labeling harness asserts zero cells leak into parent rollups across all 5 sections and all regions, re-audited specifically on non-laminar LA/BA, with rollup acronyms taken verbatim from `04-REVIEW.md`.
  4. The LA/BA Double+/TdT+ reactivation fraction is reported and interpreted against the ~20-30% TRAP2 BLA sanity band (a D-01-style findings record, not a pass/fail gate).

**Plans**: TBD
**Notes**: Classification is a human-in-the-loop QuPath run — executor authors the scripts; the operator runs BraiAnDetect + classify. LABEL-01 is paired with classification because the CR-01 heuristic was validated only on laminar hippocampus and must be re-proven on adjacent, comparable-size amygdala nuclei.

### Phase 9: Generalizable Area-Based Density Readout

**Goal**: A reusable, region-parameterized area-based density readout measures Fos+/TdT+ percent-area-above-threshold within a DAPI+ mask for compact-nuclei regions — additive/parallel to nucleus counts, governed by an explicit non-separability trigger, validated on the DG granule layer.
**Depends on**: Phase 8 (classified cells + ABBA region annotations present on the series)
**Requirements**: AREA-01, AREA-02
**Success Criteria** (what must be TRUE):

  1. `04_area_density.groovy` writes disjoint area-fraction measurement keys onto the existing region annotations — never touching `PathClass` — reported as a fraction and never a per-cell count.
  2. The readout is parameterized by region acronym and reusable brain-wide, not hard-coded to a single region.
  3. An explicit non-separability trigger rule governs when the area method applies — reserved for genuinely unsegmentable regions, not a general noise fallback.
  4. The method is validated on the DG granule layer as the in-section test case, with a crosswalk against nucleus-based counts on overlapping tissue.

**Plans**: TBD
**Notes**: Novel v1.1 work. Verification spike — QuPath `PixelClassifiers.createThreshold()` signatures via a ~2-min Script Editor autocomplete check against the installed JAR before coding. Area-based is a documented, generalizable exception to nucleus-anchored colocalization; it never replaces the primary counts.

### Phase 10: Animal-Level Aggregation + Atlas-Space Export & Point Cloud

**Goal**: The 5 sections' per-region counts roll up to a single wBA1-3 animal-level table via BraiAnalyse, and every classified cell's CCFv3 micron coordinates are persisted and rendered as a brainrender point cloud confirming cells land in the correct anatomy.
**Depends on**: Phase 8 (classified per-region series) and Phase 5 (fixed batch export, EXP-02)
**Requirements**: AGG-01, EXP-03, EXP-04
**Success Criteria** (what must be TRUE):

  1. `SlicedBrain.from_qupath` → `AnimalBrain.from_slices` produces one animal-level region table for wBA1-3, with per-region section-coverage documented and the aggregation math (sum/mean, missing-section handling) verified against the project stats conventions (animal-level, no pseudoreplication).
  2. Per-cell atlas coordinates are persisted as Atlas_X/Y/Z columns in microns (CCFv3) via the proven `AtlasTools.getAtlasToPixelTransform` path with the mm→µm ×1000 conversion applied.
  3. A brainrender 3D point cloud renders wBA1-3's classified cells colored by TdT+/Fos+/Double+ in CCFv3 micron space.
  4. The point cloud visually confirms the exported coordinates land in the correct anatomical location (LA/BA amygdala).

**Plans**: TBD
**Notes**: Terminal readout of the milestone. Verification spike — BraiAnalyse aggregation defaults (missing-section handling / area-weighting vs project stats conventions, ~1-2 h). brainrender rendering is a scriptable Python run, not a web/UI phase.

---

## Progress

**Execution Order:** Phases execute in numeric order: 5 → 6 → 7 → 8 → 9 → 10 (Phase 7 may run in parallel with Phase 6).

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Atlas Registration and ROI Loading | v1.0 | 3/3 | Complete | 2026-07-02 |
| 2. Detection Parameter Lock | v1.0 | 2/2 | Complete | 2026-07-09 |
| 3. Detection Script and Single-Section End-to-End Test | v1.0 | 4/4 | Complete | 2026-07-16 |
| 4. Biological Plausibility Validation and Imaging Optimization Notes | v1.0 | 3/3 | Complete | 2026-07-17 |
| 5. Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity | v1.1 | 3/3 | Complete    | 2026-07-19 |
| 6. Registration Speedup | v1.1 | 5/5 | Complete   | 2026-07-20 |
| 7. Imaging Re-Validation (New 4-Plane / Lower-Laser Params) | v1.1 | 0/TBD | Not started | - |
| 8. LA/BA Classification + Brain-Wide Region-Labeling Validation | v1.1 | 0/TBD | Not started | - |
| 9. Generalizable Area-Based Density Readout | v1.1 | 0/TBD | Not started | - |
| 10. Animal-Level Aggregation + Atlas-Space Export & Point Cloud | v1.1 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-01 · v1.0 milestone shipped 2026-07-17 · v1.1 roadmap added 2026-07-17*
