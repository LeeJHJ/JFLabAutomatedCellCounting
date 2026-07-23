# Phase 4: Biological Plausibility Validation and Imaging Optimization Notes - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Produce two written records that close out the single-section validation run:

1. **VAL-01 bioplausibility validation** — check the M3 entry-1 classified counts against published TRAP2 ranges: Double+ is 10–40% of TdT+; DAPI nucleus density 500–2,000/mm²; nucleus-area distribution peaks 50–150 µm²; Fos+ rate ≈1–3% on a negative-control region (or documented absence).
2. **Imaging optimization notes** — forward-looking recommendations for the full series: Z-plane count audit (OPT-01), per-section file sizes + store-raw-Z vs MIP-now tradeoff (OPT-02), and a resolution assessment of whether 20x Airyscan is needed throughout vs. lower-power survey per hippocampal subfield (OPT-03).

This is predominantly a documentation/analysis phase. The inputs already exist on disk: the classified `data/1/data.qpdata`, the raw CZI (`Automated Cell Counting/M3 Hippocampus 20x 062026.czi`, ~9.0 GB), and multiple MIP OME-TIFF variants.

**In scope:** VAL-01, OPT-01, OPT-02, OPT-03 — the validation record, the metric computation pipeline that feeds it, and the imaging-notes record.

**Out of scope (own phases / v2):** full per-cell Atlas_X/Y/Z micron export column + per-region TSV (EXP-01/02/03); full-series batch run + Fos-drift plot (SERIES-01/02); PNN quantification; BraiAnalyse whole-brain stats; brainrender 3D; multi-animal comparison. Re-tuning detection thresholds is NOT a Phase-4 deliverable (see D-01).

Requirements: **VAL-01, OPT-01, OPT-02, OPT-03**.
</domain>

<decisions>
## Implementation Decisions

### What "validation" means (VAL-01 framing)
- **D-01:** **Phase 4 is a findings record with interpretation, not a hard pass/fail gate.** Each metric is documented with its target range, marked in/out of range, and out-of-range values are *interpreted* (n=1 caveat, biological explanation, threshold-sensitivity note). The phase **completes even if a metric lands out of range** — the deliverable is the honest record. Out-of-range items become flagged notes for the full series, not blockers. Rationale: this is a single section (n=1); the published ranges are population expectations, and treating them as acceptance criteria on one section would force premature threshold-chasing. Re-tuning detection is explicitly out of scope here.
- **D-02:** **The known Double+/TdT+ ≈ 0.45 (45%) is expected to be flagged OUT (target 10–40%) and must carry a written interpretation** — candidate explanations to weigh on paper: strong recall session, n=1 sampling, robust-threshold (k=3) sensitivity on the double-positive intersection, hippocampus-specific engram reactivation. Document; do not silently pass or silently fail.

### How the VAL-01 numbers are computed
- **D-03:** **Groovy export → Python analysis.** A QuPath (Groovy) script exports per-cell measurements (class, region label, nucleus area, centroid) plus per-region areas from `data.qpdata` to a CSV/TSV; a Python script in the `braian` env computes the four metrics (Double+/TdT+ ratio, DAPI density/mm², nucleus-area-distribution peak, Fos+ control rate) and the area histogram, and writes `04-VALIDATION.md`. Rationale: reproducible, re-runnable if thresholds ever change, and the histogram/density/stats math is far cleaner in Python than Groovy. Fits the project's established GUI-export / scriptable-analysis split (export is human-run "Run for project"; the analysis is Claude-scriptable).
- **D-04:** **Density requires per-region area in mm²** — the export must emit region annotation areas (µm² → mm²) so DAPI-nucleus density is computed per region, using the same pixel calibration path already used in `qc_detection_gates.groovy`.

### Imaging notes — evidence basis and format
- **D-05:** **Two separate documents.** `04-VALIDATION.md` (VAL-01 per-run scientific record) and `04-IMAGING-NOTES.md` (OPT-01/02/03 forward-looking acquisition recommendations). Different audiences and lifetimes — keep them separate.
- **D-06:** **Empirical where possible, reasoned/literature elsewhere — and label each claim `[measured]` vs `[inferred]`.** OPT-02 file sizes and OPT-01 Z-plane counts are measured directly from the CZI/MIP files on disk (Z-count via `aicspylibczi` CZI metadata; sizes via filesystem). Where existing files support it, ground OPT-01 ("planes actually needed") in a **detection-count comparison across the MIP variants already generated** (single-plane `M3_20x_Z2_single`, 3-plane `MIP_Z1-3`, `hybrid_dapiZ2_mipZ0-2`) — does adding planes change the DAPI/marker count, or has it plateaued? For OPT-03, compare per-subfield detection quality on the existing 20x MIP; fall back to reasoned optical argument (NA/section-thickness, Nyquist for nucleus size, TRAP2-paper acquisition) for resolutions never captured. Every claim tagged measured vs inferred.

### Claude's Discretion
- **Negative-control region (VAL-01 Fos+ 1–3%):** not selected for discussion — proceed with default. This is a hippocampus-only field with no clean negative-control region, so **document the absence per VAL-01's explicit "or absence documented" allowance.** If a within-section low-signal reference is available (e.g., a fiber/white-matter tract, or a non-engram structure at the field edge), report its Fos+ rate as a sanity anchor; also report the **SSp Fos+ rate as a corroboration point** — after the Phase-3 background-robust fix suppressed SSp autofluorescence, its Fos+ rate should now read low, which is itself evidence the classifier is behaving.
- **Export script boundary:** whether the D-03 export is a new numbered/named Groovy script or a block added to `02_detect_classify.groovy` is the planner's call — but the Phase-3 **D-01 precedent (keep the fast re-classify loop clean, detection/classify separated)** favors a *separate* export script following the dual-location deploy pattern, so the classify loop stays fast.
- **Nucleus-area-peak method** (histogram binning / KDE / mode estimation) is analysis plumbing → researcher/planner's call; the requirement only asks where the distribution peaks (target 50–150 µm²).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project rules & requirements
- `CLAUDE.md` — nucleus-anchored colocalization; DAPI-nuclear / TdTomato-cytoplasmic-ring / Fos-nuclear compartment mandate; CPU-only; export microns not pixels; **stats conventions** (aggregate to animal level, no pseudoreplication, Hedges' g + Welch's t — relevant framing even though this is n=1). Non-negotiable.
- `.claude/CLAUDE.md` — project-specific colocalization + coordinate-unit constraints; also carries the full stack/architecture map.
- `.planning/REQUIREMENTS.md` — **VAL-01, OPT-01, OPT-02, OPT-03** (this phase) with exact target ranges; CLASS-02, EXP-01/02/03, SERIES-01/02 (downstream — why export/series/PNN are excluded here).
- `.planning/ROADMAP.md` §"Phase 4" — goal + 4 success criteria (the operative acceptance text for VAL/OPT).

### Phase-3 outputs to validate against (MUST read — this is the data under validation)
- `.planning/phases/03-detection-script-and-single-section-end-to-end-test/03-VERIFICATION.md` — the human-attested counts (Fos+ ~20%, TdT+ ~3.5%, **Double+/TdT+ ~0.45**, SSp suppressed) and the on-disk artifact trail; the source of the numbers Phase 4 formalizes.
- `.planning/phases/03-detection-script-and-single-section-end-to-end-test/03-CONTEXT.md` — D-01..D-05 (detection/classify separation; compartment-agnostic local-background subtraction; self-calibrating robust threshold k=3). Explains what the measured intensities mean.
- `.planning/phases/02-detection-parameter-lock/02-LOCK-RECORD.md` — locked detection params + the SSp autofluorescence deviation that motivates the negative-control corroboration point.
- `M3 Hippocampus 20x 062926 3 plane/data/1/data.qpdata` — the classified objects (source of per-cell class/area/region for D-03 export).
- `M3 Hippocampus 20x 062926 3 plane/data/1/summary.json` and `.../results/*_regions.tsv` — existing count/region outputs (cross-check for the export; not authoritative per Phase-3 Pitfall 1).
- `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json` (thr 3377.76) / `TdT_classifier_bgsub.json` (thr 1679.08) — the operative re-derived thresholds behind the counts being validated.

### Existing code to build on (full paths)
- `scripts/02_detect_classify.groovy` — the classify script producing the data; its `regionOf`/`regionLabel` closures and pixel-calibration handling are the analog for the D-03 export.
- `scripts/qc_detection_gates.groovy` — region-annotation iteration + area/density computation pattern (lines ~132–146) and pixel-size resolution (lines ~53–65); direct template for the per-region mm² area export (D-04).
- `scripts/run_braian_detection.groovy` — `AtlasManager.saveResults` region-TSV path (reusable complement).
- `czi_mip.py` (`/home/jflab/Analysis/czi_mip.py`) — `aicspylibczi` CZI reading pattern; source of the Z-plane-count read for OPT-01 and the channel-order handling.

### Imaging files to measure (OPT-01/02/03)
- `Automated Cell Counting/M3 Hippocampus 20x 062026.czi` — raw CZI, ~9.00 GB (OPT-02 raw size; OPT-01 acquired Z-plane count via metadata).
- MIP variants for the OPT-01 plane-count comparison (all under `M3 Hippocampus 20x 062226/`): `M3_20x_Z2_single.ome.tiff` (single plane), `M3_20x_MIP_Z1-3.ome.tiff` (3-plane MIP), `M3_20x_hybrid_dapiZ2_mipZ0-2.ome.tiff` (hybrid). See `[[hybrid_imaging_dapi]]` memory for why the hybrid exists (DAPI saturation + over-projection).

### Detection literature seed
- TRAP2 paper: **F1000Research 2026 / bioRxiv 2024.09.16.611953** — provenance for the VAL-01 target ranges and the OPT-03 acquisition-parameter reasoning.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `qc_detection_gates.groovy` already iterates region annotations and computes area/density with proper pixel calibration — the D-03/D-04 per-region mm² export is a near-copy of that loop plus a per-cell measurement dump.
- `02_detect_classify.groovy` already assigns each cell a class + region label; the export only needs to serialize what it computes (class, region, nucleus area, centroid) to TSV.
- `czi_mip.py`'s `aicspylibczi` reader already opens the CZI and knows its dimension layout — the OPT-01 Z-plane count is a metadata read on the same object; no new dependency.
- Filesystem sizes for OPT-02 are already enumerated in this session: CZI = 9,004,830,144 B (~9.00 GB); primary MIP OME-TIFFs ~0.97 GB each.

### Established Patterns
- Groovy pipeline scripts live in canonical `scripts/` and are hard-copied into each QuPath project's `scripts/` for "Run for project" (dual-location deploy). Any new export script follows this.
- Python analysis runs in the `braian` env (`conda run -n braian python3 ...`) — same env used for `czi_mip.py`.
- 16-bit (uint16) MIP intensities on the ~10^4 scale; background-subtracted measures are on the same scale minus the local floor.
- Claim-labeling `[measured]`/`[inferred]` (D-06) is a new documentation convention for the imaging notes — apply consistently.

### Integration Points
- The export consumes the same `data.qpdata` produced by Phase 3; the Python analysis consumes the export TSV(s) — no new state store.
- Region areas and labels come from the ABBA/BraiAn annotation hierarchy already loaded by `01_load_abba_rois.groovy`.
- The GUI/scriptable split holds: the QuPath export step is human-run ("Run for project"); everything downstream (Python metrics, both docs, CZI/size measurement) is Claude-scriptable.
</code_context>

<specifics>
## Specific Ideas

- Report the **SSp Fos+ rate** as an explicit corroboration line in `04-VALIDATION.md`: after the Phase-3 local-background-subtraction fix, SSp (the former autofluorescence stress case) should read low Fos+ — a passing SSp is evidence the classifier is trustworthy even though SSp is not a designated control.
- The OPT-01 recommendation should be framed as a **plateau argument**: if DAPI/marker counts on the single-plane vs 3-plane vs hybrid MIPs are within noise, the extra planes buy nothing at 20x and the next session can acquire fewer — state the concrete target plane count.
- OPT-02 should explicitly weigh the ~9 GB CZI vs ~1 GB MIP per section against the full-series count to make the store-raw-Z-vs-MIP-now tradeoff quantitative, not hand-wavy.
</specifics>

<deferred>
## Deferred Ideas

- **Re-tuning detection thresholds to bring Double+/TdT+ into 10–40%** — deliberately NOT done in Phase 4 (D-01). If the series confirms the ratio is genuinely high, threshold revision is a series-phase decision with n>1 support.
- **Full per-cell Atlas_X/Y/Z micron export column + per-region TSV** — v2 EXP-01/02/03. The D-03 export here is scoped to the VAL-01 metrics, not a general coordinate export.
- **Whole-brain / full-series autofluorescence + Fos-drift validation** — SERIES-01/02, where cortex counts and cross-section drift actually matter.
- **PNN (perineuronal net / WFA) quantification** — future phase; the Phase-3 compartment-agnostic background measure was designed to host it later.
- **BraiAnalyse group stats / brainrender 3D** — need the full registered series; out of scope for n=1.

### Reviewed Todos (not folded)
None — no matching pending todos for this phase.

</deferred>

---

*Phase: 4-biological-plausibility-validation-and-imaging-optimization-notes*
*Context gathered: 2026-07-16*
