# Phase 1: Atlas Registration and ROI Loading - Context

**Gathered:** 2026-07-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 1 delivers ABBA atlas registration of the M3 hippocampus section in Fiji (GUI), followed by a Groovy script (`01_load_abba_rois.groovy`) that loads the resulting atlas ROIs into the QuPath project. The output is a QuPath project entry with Allen CCFv3 annotation hierarchy present, visually verified against tissue, ready for BraiAnDetect cell detection in Phase 2.

**In scope:**
- ABBA registration of one M3 hippocampus section in Fiji (DeepSlice → manual angle adjust → export)
- Writing and testing `01_load_abba_rois.groovy` (clearAllObjects + loadWarpedAtlasAnnotations)
- Registration overlay QC image (manual QuPath screenshot)

**Out of scope:**
- Detection parameter tuning (Phase 2)
- Writing detection or classification scripts (Phase 2–3)
- Multi-section batch registration (deferred to full series run)
- Elastix Affine+Spline registration (confirmed to degrade without tissue mask; excluded permanently)

</domain>

<decisions>
## Implementation Decisions

### Target Project and Scope
- **D-01:** Target QuPath project is `M3 Hippocampus 20x 062926 3 plane/`. This project has correct channel names (`AF568-T2`, `AF488-T3`, `DAPI-T4`) matching the canonical czi_to_mip output and BraiAn.yml requirements.
- **D-02:** The two entries in the project are duplicates (`M3_20x_MIP_Z1-3.ome.tiff` and `M3_20x_MIP_Z1-3_MIP.ome.tiff`). The canonical entry to register is **entry 1: `M3_20x_MIP_Z1-3.ome.tiff`**.
- **D-03 [informational]:** Scope is one section for this validation run. Multi-section batch registration is deferred to the full series.
- **D-04:** The older `M3 Hippocampus 20x 062226/` project (old channel names: DAPI / Fos-EGFP / TdTom-Cy3) is not the target — do not register or write scripts for it.

### ROI Loading Script Behavior
- **D-05:** The script calls `clearAllObjects()` before reloading atlas annotations. This is acceptable for Phase 1 — detection has not run yet. A comment in the script should note that re-running after Phase 3 detection will wipe cell data.
- **D-06:** Atlas name is a configurable variable at the top of the script: `def atlasName = 'allen_mouse_10um_java'`. This matches the key used in existing ABBA transform files on this project.

### QC Image Capture
- **D-07:** QC is a manual screenshot taken from the QuPath viewer by the researcher. No programmatic export needed.
- **D-08:** The QC image must show all of: CA1, CA3, DG hippocampal subfield boundaries + surrounding cortex + the ventral brain edge — all aligned to atlas region outlines. If the ventral edge or subfield boundaries are off, the registration must be redone before proceeding to Phase 2.
- **D-09:** Screenshot is saved in the QuPath project's `data/1/` directory alongside the ABBA transform and ROI files (e.g., `data/1/registration_QC.jpg`).

### Script Location and Project Structure
- **D-10:** Central canonical location for all pipeline Groovy scripts: `/home/jflab/Analysis/scripts/`. This directory needs to be created; it does not exist yet.
- **D-11:** Scripts are hard-copied into each QuPath project's `scripts/` folder for "Run for project" access. Workflow: author in `Analysis/scripts/`, copy into `M3 Hippocampus 20x 062926 3 plane/scripts/`.

### Claude's Discretion
- **resolveHierarchy():** Include a `resolveHierarchy()` call after `loadWarpedAtlasAnnotations`. This is the standard BIOP/BraiAnDetect pattern and ensures parent-child atlas region nesting is correct before detection runs. The user deferred this choice to Claude.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/ROADMAP.md` — Phase 1 success criteria (authoritative); Phase 2–4 depend on Phase 1 output
- `.planning/REQUIREMENTS.md` — Requirements REG-01, REG-02, SCRI-01 are Phase 1's requirements
- `.planning/PROJECT.md` — Locked decisions table, constraint list, pipeline overview
- `CLAUDE.md` — Hard constraints (CPU-only, version pins, colocalization rules, coordinate units)

### Existing ABBA Artifacts (reference structure)
- `Automated Cell Counting Test/data/1/ABBA-Transform-allen_mouse_10um_java.json` — existing ABBA transform JSON from the June test; use as structural reference for what a correct transform looks like
- `Automated Cell Counting Test/data/1/ABBA-RoiSet-allen_mouse_10um_java.zip` — existing ROI set; reference for what the output of ABBA export produces

### Target Project Files
- `M3 Hippocampus 20x 062926 3 plane/project.qpproj` — the QuPath project being registered; contains 2 entries (use entry 1)
- `M3 Hippocampus 20x 062926 3 plane/data/1/server.json` — confirms channel names: `['AF568-T2', 'AF488-T3', 'DAPI-T4']`

### Existing Scripts (context only — not the ROI loading mechanism)
- `Automated Cell Counting Test/scripts/Test 062026 1.groovy` — Warpy object transfer script; NOT ABBA ROI loading; do not use as template for `01_load_abba_rois.groovy`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None directly reusable for `01_load_abba_rois.groovy` — the existing Warpy scripts use a different mechanism (RealTransform object transfer, not ABBA atlas annotation loading)
- Existing classifiers in `Automated Cell Counting Test/classifiers/` exist but use wrong channel names for the M3 project; they need to be rebuilt in Phase 2

### Established Patterns
- Groovy header convention from existing scripts: Javadoc-style `/** ... */` block with `@author` tags and logical step comments
- `println` for output (not `print`) — matches existing scripts
- `def` for variable declarations
- Atlas key established: `allen_mouse_10um_java` — used in both the Automated Cell Counting Test and M3 062226 projects

### Integration Points
- ABBA outputs (`ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip`) must be present in `data/1/` before `01_load_abba_rois.groovy` can run — ABBA Fiji export writes these files
- The `loadWarpedAtlasAnnotations` QuPath API call (from `qupath.ext.biop.abba.AtlasTools`) reads these files from the project entry's data directory
- Channel names in `data/1/server.json` (`AF568-T2`, `AF488-T3`, `DAPI-T4`) are the names that all downstream scripts and classifiers must use

### Known Gotchas
- The two existing Groovy scripts (`Test 062026.groovy`, `Test 062026 1.groovy`) are identical Warpy transfer scripts — they are not ABBA ROI loading scripts; researcher should not confuse them
- The `M3 Hippocampus 20x 062226/` project has ABBA already done but wrong channel names — do not use as the pipeline target
- `resolveHierarchy()` must follow `loadWarpedAtlasAnnotations` or BraiAnDetect cell-to-region assignment will be incorrect

</code_context>

<specifics>
## Specific Ideas

- The registration QC image specifically needs to show all four of: CA1, CA3, DG hippocampal subfields + surrounding cortex + ventral brain edge, all aligned to atlas region outlines. The researcher sets a high accuracy bar here — if anything looks off, the registration should be redone.
- The script's `clearAllObjects()` should include a prominent comment warning that re-running the script after Phase 3 detection will wipe all cell data.
- The `Analysis/scripts/` directory needs to be created as part of Phase 1 deliverables.

</specifics>

<deferred>
## Deferred Ideas

- Multi-section batch registration — when the full M3 series is ready, all sections will be imported into a project and registered in one ABBA session. Deferred until this single-section validation is confirmed.
- The duplicate second entry (`M3_20x_MIP_Z1-3_MIP.ome.tiff`) in the project — can be removed or ignored; no action required in Phase 1.

</deferred>

---

*Phase: 1-Atlas Registration and ROI Loading*
*Context gathered: 2026-07-01*
