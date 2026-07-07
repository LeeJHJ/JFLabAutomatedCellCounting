# Phase 2: Detection Parameter Lock - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Author a verified `BraiAn.yml` at project root with tuned WatershedCellDetection parameters (sigma, min/max nucleus area, detection threshold, TdTomato cytoplasmic expansion) and confirm the Fos classifier reads the **nuclear compartment only** — tuned visually on one M3 section.

**In scope:** BraiAn.yml authoring + one-section visual tuning; Fos classifier compartment verification (CLASS-01); channel-name correctness; parameter-lock acceptance gates.

**Out of scope (own phases):** the detection *script* `02_detect_classify.groovy` (Phase 3); the full-series batch run and Fos-drift plot (SERIES-01/02, later); per-region TSV export (EXP-02); 3D visualization (VIZ-01).

Requirements: **SCRI-02** (BraiAn.yml), **CLASS-01** (Fos classifier nuclear compartment).
</domain>

<decisions>
## Implementation Decisions

### Threshold strategy (series-scaling)
- **D-01:** Nucleus **detection** threshold in BraiAn.yml is **histogram-relative** (computed per-section from the DAPI histogram, e.g. percentile or median+k·MAD), NOT a fixed absolute value. Rationale: the same BraiAn.yml must work across the full series without re-tuning; absolute thresholds drift with staining/exposure (SERIES-02 risk). Note: prior M3 062226 classifiers used *absolute* (~10200 TdT / ~9341 Fos on 16-bit) — those are a starting reference for the relative calibration, not the locked approach.
- **D-02:** TdT+/Fos+ **classifier positive cutoffs** follow the **same histogram-relative philosophy** — derived from each section's measurement distribution, consistent with D-01. A globally dim/bright section must not fool the classifier.
- **D-03:** **One global BraiAn.yml** locked for every section. Do NOT re-tune per section. Instead use the Fos+-rate-vs-section-position plot (SERIES-02, later phase) to flag outlier sections for manual review. Maximizes cross-section consistency and statistical defensibility.

### Tuning reference + lock/accept bar
- **D-04:** Tune on **M3 062926 3 plane, entry 1** (the section registered in Phase 1). Use dense **DG** as the worst-case stress test (expansion-ring bleed, merged nuclei) and **CA1** as a cleaner separability check. Params must hold on both before locking.
- **D-05:** **Hard acceptance gates** to lock the params (both must PASS): (1) detected **nucleus area distribution peaks in 50–150 µm²**; (2) **DAPI nucleus density in 500–2000/mm²**. These validate sigma + min/max area + detection threshold are catching real nuclei.
- **D-06:** **Double+ = 10–40% of TdT+** is **advisory, NOT a hard gate.** Deliberately excluded from lock criteria: gating parameters on the expected biological result risks tuning toward the hypothesis (circularity). Report the ratio, don't lock on it.
- **D-07:** The **Fos+ ≈1–3% negative-control gate is SKIPPED for Phase 2** — a single hippocampal section has no trustworthy low-activity control region. Defer the strict negative-control check to the full series (where a proper control region exists). Do not block param-lock on it.

### Claude's Discretion
Two gray areas were surfaced but not selected for discussion — proceed with these defaults, flag in planning:
- **Cytoplasmic expansion radius / DG bleeding:** default to the TRAP2-paper seed of **5 µm** (`cellExpansionMicrons`), with rings constrained so they do not overlap adjacent nuclei (QuPath cell expansion clips at neighboring cell boundaries). Tune/verify visually on dense DG per D-04. This is where TdT over/under-count risk lives — planner should make the DG bleed-check explicit.
- **Reuse vs rebuild classifiers:** **reuse** `Fos_Classifier_20x.json` (062226 Redo) as the starting point — it already correctly reads `Nucleus: AF488-T3 mean` (satisfies CLASS-01) — but **re-derive its threshold as histogram-relative** per D-02. **Rebuild the TdT classifier** to read `Cytoplasm: AF568-T2 mean`: the existing `TRAP2TdT_Classifier_20x.json` wrongly reads `Nucleus: AF568-T2 mean`, violating the cytosolic-TdTomato rule. Discard the stale "Automated Cell Counting Test" classifiers (wrong channel names `Cy3-T1`/`EGFP-T2`, wrong compartments).
- **Sigma + min/max nucleus area:** seed from the TRAP2 paper, tune on the section; gated by D-05.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project rules & requirements
- `CLAUDE.md` — nucleus-anchored colocalization rule; DAPI-nuclear / TdTomato-cytoplasmic-ring / Fos-nuclear compartment mandate; BraiAnDetect over Cellpose/StarDist; CPU-only; channel-override convention. **Non-negotiable.**
- `.claude/CLAUDE.md` — project-specific colocalization + coordinate-units constraints.
- `.planning/REQUIREMENTS.md` — SCRI-02, CLASS-01 (Phase 2); CLASS-02, VAL-01, SERIES-02 (downstream, inform lock strategy).
- `.planning/ROADMAP.md` §"Phase 2: Detection Parameter Lock" — goal + 4 success criteria.

### Detection literature seed
- TRAP2 paper: **F1000Research 2026 / bioRxiv 2024.09.16.611953** — seed values for sigma, min/max area, threshold, and the 5 µm cytoplasmic expansion. Tune from these, don't invent.

### Existing classifiers (reference / reuse)
- `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/Fos_Classifier_20x.json` — reads `Nucleus: AF488-T3 mean` (thr ~9341); **correct compartment, reuse as base for CLASS-01**.
- `M3 Hippocampus 20x 062226/M3 Hippocampus 20x 062226 Redo/classifiers/object_classifiers/TRAP2TdT_Classifier_20x.json` — reads `Nucleus: AF568-T2 mean` (thr ~10200); **WRONG compartment — must rebuild to Cytoplasm**.
- `Automated Cell Counting Test/classifiers/object_classifiers/{TdT,Fos}_*.json` — stale (wrong channel names/compartments); do not reuse.
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Fos_Classifier_20x.json` (062226 Redo): already-correct nuclear Fos classifier — adapt threshold to histogram-relative, otherwise reuse.
- Channel names confirmed on the real M3 MIP: `['AF568-T2' (TdTomato), 'AF488-T3' (Fos), 'DAPI-T4' (DAPI)]` (verified via `crop_to_tissue.py` on `M3_20x_MIP_Z1-3.ome.tiff`). BraiAn.yml channel names MUST match these exactly.
- Phase-1 registered section (`M3 Hippocampus 20x 062926 3 plane`, entry 1, data/1/ populated with atlas annotations) is the tuning substrate.

### Established Patterns
- Groovy pipeline scripts live in canonical `scripts/` + hard-copied into each QuPath project's `scripts/` for "Run for project" (D-10/D-11 from Phase 1).
- 16-bit (uint16) MIP data — thresholds are in the ~10^4 range if expressed absolutely.

### Integration Points
- BraiAn.yml at project root is consumed by BraiAnDetect in the Phase-3 detection script.
- Classifier JSONs live under `<project>/classifiers/object_classifiers/`.
</code_context>

<specifics>
## Specific Ideas

- Tuning stress pair: dense DG (bleed/merge worst case) + CA1 (clean separability) — both must pass.
- Lock gates are detection-quality metrics (nucleus area peak, DAPI density), deliberately NOT the Double+ biological ratio.
</specifics>

<deferred>
## Deferred Ideas

- **Fos+ ≈1–3% negative-control validation** — deferred to the full-series phase where a proper low-activity control region exists (D-07).
- **Double+ 10–40% of TdT+ as a validation report** — computed and reported, but as an outcome, not a Phase-2 lock gate (D-06); revisit at series-stats time.
- **crop_to_tissue.py / masked-elastix registration pilot** — registration-domain (Phase 1 lineage), not detection; belongs to the series-scaling registration decision, not this phase.

### Reviewed Todos (not folded)
None — discussion stayed within phase scope.
</deferred>

---

*Phase: 2-detection-parameter-lock*
*Context gathered: 2026-07-07*
