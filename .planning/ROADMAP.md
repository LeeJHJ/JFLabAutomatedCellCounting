# Roadmap: M3 Hippocampus Section Pipeline — First Run

**Project:** TRAP2 Section Pipeline, M3 Hippocampus Single-Section Validation
**Core Value:** Biologically plausible TdT+/Fos+/Double+ counts per atlas region with locked detection parameters ready for the full series.
**Created:** 2026-07-01
**Granularity:** Standard
**Phase convention:** Sequential

---

## Phases

- [x] **Phase 1: Atlas Registration and ROI Loading** - ABBA registers M3 sections in Fiji and atlas annotations are loaded into QuPath via Groovy script (completed 2026-07-02)
- [x] **Phase 2: Detection Parameter Lock** - BraiAn.yml authored with tuned parameters and Fos classifier compartment verified (completed 2026-07-09)
- [x] **Phase 3: Detection Script and Single-Section End-to-End Test** - `02_detect_classify.groovy` written, tested, and produces classified cell data on one section (completed 2026-07-16)
- [ ] **Phase 4: Biological Plausibility Validation and Imaging Optimization Notes** - Cell counts pass bioplausibility checks and imaging optimization recommendations are documented

---

## Phase Details

### Phase 1: Atlas Registration and ROI Loading

**Goal**: Atlas region annotations are loaded into the M3 QuPath project, visually verified to align with tissue, and the ROI loading script runs cleanly on all entries.
**Mode:** mvp
**Depends on**: Nothing (pipeline start)
**Requirements**: REG-01, REG-02, SCRI-01

**Success Criteria** (what must be TRUE):

  1. Fiji ABBA produces `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` for each M3 section entry
  2. A registration overlay QC image shows atlas region boundaries aligned to tissue (hippocampal subfields visible) — proceeding to detection is justified
  3. `01_load_abba_rois.groovy` runs via QuPath "Run for project" with no errors and atlas annotations populate the annotation list for each entry
  4. Re-running `01_load_abba_rois.groovy` on an already-annotated entry does not duplicate regions (clearAllObjects guard confirmed working)

**Plans**: 3/3 plans complete
**Wave 1**

- [x] 01-01-PLAN.md — Author and deploy 01_load_abba_rois.groovy (script + scripts dirs)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-02-PLAN.md — Register M3 entry 1 in Fiji ABBA and export ROI files (GUI)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 01-03-PLAN.md — Run script, confirm idempotent annotation load, capture QC overlay

---

### Phase 2: Detection Parameter Lock

**Goal**: A verified `BraiAn.yml` exists at project root with tuned detection parameters and the Fos classifier is confirmed to read from the nuclear compartment only.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: SCRI-02, CLASS-01

**Success Criteria** (what must be TRUE):

  1. `BraiAn.yml` contains locked values for sigma, min/max area, threshold (histogram-relative), and `cellExpansionMicrons > 0` for TdTomato channel, seeded from the TRAP2 paper (5 µm) and tuned visually on one M3 section
  2. Channel names in `BraiAn.yml` match the project exactly (`AF568-T2`, `AF488-T3`, `DAPI-T4`) — a detection run produces non-zero cells in the Fos and TdT channels
  3. `Fos_classifier.json` feature field reads `Nucleus: AF488-T3 mean` (not cytoplasm), confirmed by opening the JSON and by the detection overlay showing Fos+ only in nuclei
  4. Visual overlay on one representative dense region (e.g., DG) shows cytoplasmic expansion rings not bleeding into adjacent nuclei

**Plans**: 2/2 plans complete
**Wave 1**

- [x] 02-01-PLAN.md — Author BraiAn.yml (single DAPI-anchored entry, histogramThreshold, cellExpansion 5µm), both compartment-correct classifiers, and the D-05 QC harness

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 02-02-PLAN.md — Human-in-the-loop: tune detection on entry 1 (DG+CA1) to PASS the D-05 gates, re-derive classifier thresholds, and lock the values

---

### Phase 3: Detection Script and Single-Section End-to-End Test

**Goal**: `02_detect_classify.groovy` runs successfully on the M3 section, producing classified TdT+, Fos+, Double+, and Negative cells with atlas region labels.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: SCRI-03

**Success Criteria** (what must be TRUE):

  1. `02_detect_classify.groovy` runs via "Run for project" without errors and writes `data.qpdata` with classified cells for the M3 entry
  2. All four cell classes (TdT+, Fos+, Double+, Negative) are present in the detection output and each cell carries an atlas region label from the ABBA annotation hierarchy
  3. Printed Atlas_X values for detected cells fall in the range 5,000–10,000 µm (confirms CCFv3 micron units, not mm)
  4. Per-region count table for hippocampal subfields (CA1, CA2, CA3, DG, at minimum) is readable in the QuPath annotation pane

**Plans**: 4/4 plans complete
**Wave 1**

- [x] 03-01-PLAN.md — Runnable classify script + per-cell atlas region labels (SC1 + SC2)

**Wave 2** *(blocked on Wave 1)*

- [x] 03-02-PLAN.md — Per-region count rollup + Atlas_X micron sanity print (SC4 + SC3)

**Wave 3** *(blocked on Wave 2)*

- [x] 03-03-PLAN.md — Local-background-subtracted measure (D-04) + re-derived thresholds (D-05)

**Wave 4** *(blocked on Wave 3)*

- [x] 03-04-PLAN.md — Human-in-the-loop end-to-end verification of all four success criteria

---

### Phase 4: Biological Plausibility Validation and Imaging Optimization Notes

**Goal**: Cell counts are confirmed biologically plausible against published TRAP2 literature ranges, and imaging optimization recommendations are written for the full series.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: VAL-01, OPT-01, OPT-02, OPT-03

**Success Criteria** (what must be TRUE):

  1. Written validation record confirms: Double+ is 10–40% of TdT+; DAPI nucleus density is 500–2,000/mm²; nucleus area distribution peaks in 50–150 µm²; Fos+ rate on any negative-control region is 1–3% (or absence of control region documented)
  2. Z-plane count audit written: number of Z-planes acquired vs. minimum needed for a good MIP at 20x Airyscan, with a concrete target recommendation for the next imaging session
  3. Per-section file size recorded (CZI raw and MIP OME-TIFF); a written assessment of MIP-immediately vs. store-raw-Z tradeoff for the full series
  4. Resolution assessment written: whether 20x Airyscan is required throughout or a lower-power survey would suffice for non-DG hippocampal subfields; identifies which subfields actually require Airyscan resolution

**Plans**: 3 plans
**Wave 1** *(parallel — no file conflicts)*

- [ ] 04-01-PLAN.md — VAL-01 tooling: Groovy per-cell/per-region export + Python metrics script (VAL-01)
- [ ] 04-02-PLAN.md — Imaging optimization notes: Z-plane audit + file-size tradeoff + resolution assessment (OPT-01, OPT-02, OPT-03)

**Wave 2** *(blocked on 04-01)*

- [ ] 04-03-PLAN.md — VAL-01 record: human QuPath export run + metrics on real data + 04-VALIDATION-RECORD.md (VAL-01)

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Atlas Registration and ROI Loading | 3/3 | Complete    | 2026-07-02 |
| 2. Detection Parameter Lock | 2/2 | Complete   | 2026-07-09 |
| 3. Detection Script and Single-Section End-to-End Test | 4/4 | Complete    | 2026-07-16 |
| 4. Biological Plausibility Validation and Imaging Optimization Notes | 0/3 | Planned | - |

---

## Coverage

| Requirement | Phase | Category |
|-------------|-------|----------|
| REG-01 | Phase 1 | Registration |
| REG-02 | Phase 1 | Registration |
| SCRI-01 | Phase 1 | Scripting |
| SCRI-02 | Phase 2 | Scripting |
| CLASS-01 | Phase 2 | Classifiers |
| SCRI-03 | Phase 3 | Scripting |
| VAL-01 | Phase 4 | Validation |
| OPT-01 | Phase 4 | Imaging Optimization |
| OPT-02 | Phase 4 | Imaging Optimization |
| OPT-03 | Phase 4 | Imaging Optimization |

**v1 coverage:** 10/10 requirements mapped. No orphans.

---

## Human-in-the-Loop Notes

Phases 1 and 2 contain GUI steps (Fiji ABBA, QuPath parameter tuning) that cannot be automated. Claude Code writes scripts and documentation artifacts; the researcher performs the GUI interactions and reports results. Phase 3 and 4 are primarily scriptable.

---
*Roadmap created: 2026-07-01*
