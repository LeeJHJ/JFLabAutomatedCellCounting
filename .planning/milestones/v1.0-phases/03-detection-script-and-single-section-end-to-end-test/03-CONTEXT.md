# Phase 3: Detection Script and Single-Section End-to-End Test - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Package the Phase-2 detection + nucleus-anchored classification work into the numbered pipeline so one section runs end-to-end and produces classified cell data. Specifically: author `02_detect_classify.groovy` that classifies BraiAnDetect-produced nuclei into TdT+/Fos+/Double+/Negative, attaches atlas region labels, confirms micron coordinate units, and surfaces a per-hippocampal-subfield count table — writing a classified `data.qpdata`.

**In scope:** SCRI-03 — the `02_detect_classify.groovy` classification script; nucleus-anchored compound classification; a **background-robust (autofluorescence-tolerant) Fos/TdT measure** (see D-04); atlas region labeling; an Atlas_X micron sanity check; a readable per-subfield count table.

**Out of scope (own phases):** the heavy BraiAnDetect **detection** pass itself (stays in `run_braian_detection.groovy` — D-01); full per-cell Atlas_X/Y/Z micron **export** column and per-region TSV export (EXP-01/02/03, v2); full-series batch run + Fos-drift plot (SERIES-01/02); PNN quantification (deferred — see below); biological-plausibility validation (Phase 4).

Requirement: **SCRI-03**.
</domain>

<decisions>
## Implementation Decisions

### Script composition
- **D-01:** **Detection stays separate.** `run_braian_detection.groovy` remains the standalone heavy BraiAnDetect pass. `02_detect_classify.groovy` performs classification + atlas labels + count table **only**, assuming detections already exist. Rationale: detection is CPU-heavy; keeping it out of the classify script lets the fast threshold-iteration loop re-run without re-detecting. (Note: the script name says "detect_classify" but the detection trigger lives elsewhere — the numbered script is the classify/label/report entry point.)
- **D-02:** **Guard on zero detections, re-classify in place idempotently.** If an entry has no detections, abort with a clear message telling the user to run `run_braian_detection.groovy` first (matches `classify_markers.groovy`'s existing "No detections — Aborting" guard). If detections exist, (re)classify them in place — `setPathClass` overwrites, so re-running just refreshes classes. Safe to run freely during threshold tuning. Under "Run for project", undetected entries (i.e. every entry except the registered/detected entry 1) simply abort cleanly rather than erroring the batch.

### SSp autofluorescence robustness
- **D-03:** **Fix now, not defer.** Even though the SSp (somatosensory cortex) false-positives land outside the CA1/CA2/CA3/DG subfields Phase 3 validates, build the background-robust measure this phase so the classifier is series-ready before the batch run. The problem (lock record Deviation #2): SSp reads ~2× AF488 uniformly (autofluorescence, not real Fos), so its median nuclear-488 ≈15072 clears the locked Fos cutoff 13000 → >50% false-positives in SSp.
- **D-04:** **Use local-background subtraction / background-normalized per-compartment intensity — NOT a nucleus:cytoplasm compartment-contrast ratio.** Rationale is forward-scaling to **PNN** (see deferred): PNNs are extracellular pericellular ECM, not nuclear or cytoplasmic, so a two-compartment *intracellular* ratio has nowhere to host a PNN signal and would not generalize. Local-background subtraction is **compartment-agnostic**: define whatever compartment the marker occupies (nucleus for Fos, cytoplasmic ring for TdT, a pericellular annulus for a future PNN channel) and subtract the local peri-cellular tissue background around each cell. Same robustness mechanism, extensible to new markers without a redesign. This design constraint is deliberate and locked.
- **D-05:** **Re-derive the positive thresholds on the new background-subtracted measure.** Fixing the measure means the locked absolute cutoffs (Fos ≥13000.4538 nuclear, TdT ≥16766.4671 cytoplasmic from `02-LOCK-RECORD.md`) are **superseded** for classification — new cutoffs are derived on the background-normalized measure (keeping the D-02 histogram-relative philosophy from Phase 2). The old absolute cutoffs remain a documented reference point, not the operative rule.

### Claude's Discretion
Two gray areas were surfaced but not selected — proceed with these defaults, flag in planning:
- **Atlas coordinate check (SC3):** satisfy the "printed Atlas_X in 5,000–10,000 µm" criterion with a **lightweight sanity-print** of a sample of classified cells' CCFv3 atlas X coordinates (enough to confirm CCFv3 micron units, not mm). Do **not** build a full per-cell Atlas_X/Y/Z measurement column here — that is v2 `EXP-01`/`EXP-03` export territory.
- **Per-region count table (SC4):** roll per-class counts **up onto the region annotations as measurements** so they render in the QuPath annotation-pane measurement table for CA1/CA2/CA3/DG (at minimum); a console-printed table is a fine complement, and BraiAn's `_regions.tsv` (written by the separate detection script) can be reused rather than reinvented.
- **Atlas-label mechanism** (resolveHierarchy / parent-annotation assignment so each cell carries its region label — SC2) is technical plumbing → researcher/planner's call.
- **Region exclusions** `DG-sg` + `VS` remain as locked in Phase 2 (`classify_markers.groovy` `EXCLUDE_ACRONYMS`). Whether the new background-robust measure reduces the need to exclude/flag SSp is an outcome to observe, not a Phase-3 exclusion decision to lock now.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project rules & requirements
- `CLAUDE.md` — nucleus-anchored colocalization (nucleus *contains* marker centroid, no proximity/overlap); DAPI-nuclear / TdTomato-cytoplasmic-ring / Fos-nuclear compartment mandate; BraiAnDetect over Cellpose/StarDist; CPU-only; export microns not pixels. **Non-negotiable.**
- `.claude/CLAUDE.md` — project-specific colocalization + coordinate-unit constraints.
- `.planning/REQUIREMENTS.md` — **SCRI-03** (this phase); CLASS-02, EXP-01/02/03, SERIES-01/02 (downstream — inform the background-robust measure + why export/series are excluded here).
- `.planning/ROADMAP.md` §"Phase 3: Detection Script and Single-Section End-to-End Test" — goal + 4 success criteria (data.qpdata written; 4 classes + atlas labels; Atlas_X 5,000–10,000 µm; per-subfield count table readable in annotation pane).

### Phase-2 lock (MUST read — carries the deviations that shape Phase 3)
- `.planning/phases/02-detection-parameter-lock/02-LOCK-RECORD.md` — locked `BraiAn.yml` params (sigma 2.5, area 20–250, histogram nPeak 2, 5 µm expansion, detection confined to `allen_mouse_10um_java` Root), locked classifier thresholds, and the **4 Phase-3 deviations**: (#1) classify via `classify_markers.groovy`, **not** BraiAn.yml `classifiers:`/OverlappingDetections; (#2) **SSp autofluorescence** breaks absolute thresholds — the exact bug this phase's D-03/D-04 fixes; (#3) `BraiAn.resolvePath` classifier-path resolution nuance; (#4) QuPath 0.6.0 API gotchas.
- `.planning/phases/02-detection-parameter-lock/02-CONTEXT.md` — D-01..D-07 threshold philosophy (histogram-relative D-01/D-02; one global BraiAn.yml D-03; hard gates D-05; Double+ advisory D-06; negative-control deferred D-07).

### Existing code to build on (full paths)
- `scripts/classify_markers.groovy` — **direct base for `02_detect_classify.groovy`**: nucleus-anchored compound Double+/Fos+/TdT+/Negative classification, reads thresholds from classifier JSON at runtime, handles DG-sg/VS exclusions, prints class breakdown. Extend with the background-subtracted measure (D-04), atlas labels, Atlas_X print, per-region rollup.
- `scripts/run_braian_detection.groovy` — the separate detection pass (D-01); also writes `results/<image>_regions.tsv` via `AtlasManager.saveResults` (reusable for the count table).
- `scripts/qc_detection_gates.groovy`, `scripts/export_region_dapi_reference.groovy`, `scripts/build_dapi_reference.py` — Phase-2 QC/reference harness (patterns for reading measurements, region iteration).
- `M3 Hippocampus 20x 062926 3 plane/BraiAn.yml` — locked detection config consumed by the detection pass.
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x.json` (Nucleus: AF488-T3 mean, thr 13000.4538) and `.../TdT_classifier.json` (Cytoplasm: AF568-T2 mean, thr 16766.4671) — the cutoffs superseded by D-05's background-normalized re-derivation.

### Detection literature seed
- TRAP2 paper: **F1000Research 2026 / bioRxiv 2024.09.16.611953** — parameter provenance (seeds now superseded by the empirical internal reference per `02-LOCK-RECORD.md`).
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `classify_markers.groovy` is the ready-made skeleton for `02_detect_classify.groovy` — runtime threshold read, per-nucleus compound classification, exclusion ROIs, class-count printout. The Phase-3 script extends it rather than starting fresh.
- `run_braian_detection.groovy`'s `AtlasManager.saveResults(...)` region-TSV path can back the SC4 count table.
- Channel names verified on the real M3 MIP: `AF568-T2` (TdTomato, cytosolic), `AF488-T3` (Fos, nuclear), `DAPI-T4`. Any new measurement must reference these exactly.

### Established Patterns
- Groovy pipeline scripts live in canonical `scripts/` and are **hard-copied** into each QuPath project's `scripts/` for "Run for project" (Phase 1 D-10/D-11). `02_detect_classify.groovy` follows the same dual-location deploy.
- 16-bit (uint16) MIP data — raw intensities are ~10^4; a background-subtracted measure lives on the same scale, minus the local floor.
- Deviation #3: `BraiAn.resolvePath` resolves classifier `<name>.json` against project base + parent (not `classifiers/object_classifiers/`); `name` fields carry the subpath.

### Integration Points
- Runs **after** `run_braian_detection.groovy` on the same entry; consumes the DAPI-T4 detection set + ABBA region annotations already in `data.qpdata`.
- Region labels come from the ABBA/BraiAn parent-annotation hierarchy already loaded by `01_load_abba_rois.groovy`.
</code_context>

<specifics>
## Specific Ideas

- The background-robust measure must be architected as a **compartment-agnostic local-background subtraction**, explicitly so the same machinery later hosts a **pericellular PNN (perineuronal net) annulus** compartment — this is a stated user goal that steers the design even though PNN is not built here.
- SSp is the concrete stress case for autofluorescence: uniform ~2× AF488 lift that a plain absolute threshold cannot distinguish from real nuclear Fos.
</specifics>

<deferred>
## Deferred Ideas

- **PNN (perineuronal net / WFA) quantification** — a future phase. Needs a new stain/channel and a pericellular-annulus detection compartment. Not built in Phase 3, but its extracellular nature is the deciding reason Phase 3's background-robust measure is local-background subtraction (D-04) rather than a nucleus:cytoplasm ratio.
- **Full per-cell Atlas_X/Y/Z micron export column + per-region TSV** — v2 `EXP-01`/`EXP-02`/`EXP-03`. Phase 3 does only a sanity-print of atlas coordinates.
- **Whole-brain / full-series autofluorescence validation** (SSp and other high-autofluorescence regions at scale) — series phase where cortex counts actually matter (SERIES-01/02).
- **Biological-plausibility gates** (Double+/TdT+ ratio, DAPI density, Fos negative-control) — Phase 4 (VAL-01).

### Reviewed Todos (not folded)
None — no matching pending todos for this phase.
</deferred>

---

*Phase: 3-detection-script-and-single-section-end-to-end-test*
*Context gathered: 2026-07-09*
