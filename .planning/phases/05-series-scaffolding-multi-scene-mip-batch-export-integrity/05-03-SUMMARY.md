---
phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity
plan: 03
subsystem: imaging
tags: [czi, ome-tiff, deepslice, channel-identity, tissue-qc, human-verify]

# Dependency graph
requires:
  - phase: 05-01
    provides: 5 MIP OME-TIFFs + 5 identity thumbnails for the wBA1-3 series
provides:
  - Operator sign-off on channel identity (CONV-01, RESEARCH Assumption A1) — index 0=TdTomato, index 1=Fos confirmed correct on the new CZI
  - Operator sign-off on scene->section identity (CONV-02) — 5 distinct intact sections, consistent scene_key<->s{N} mapping
  - Two logged imaging-QC caveats (autofocus/focus banding, missing cortex tissue) carried to Phase 7
affects: [08-la-ba-classification-brain-wide-region-labeling-validation, 09-generalizable-area-based-density-readout, 07-imaging-re-validation]

# Tech tracking
tech-stack:
  added: []
  patterns: []

key-files:
  created:
    - .planning/todos/pending/2026-07-18-phase-7-imaging-qc-autofocus-banding-and-missing-cortex.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "Operator confirmed OME-TIFF physical channel index order is CORRECT: index 0=TdTomato-AF568, index 1=Fos-AF488, index 2=DAPI (the A1 sign-off Phase 8 depends on)"
  - "5-scene identity confirmed: distinct, intact single coronal sections with consistent scene_key<->s{N} mapping — no fusion/shuffle"
  - "s1 identity-thumbnail 'wrong channel' concern resolved as by-design: identity thumbnails are DAPI (physical index 2) for all 5 scenes (anatomical reference), not a channel bug — does not reopen 05-01"

patterns-established: []

requirements-completed: [CONV-01, CONV-02]

coverage:
  - id: D1
    description: "Operator confirms physical channel index identity (0=TdTomato, 1=Fos) on the wBA1-3 series before it is trusted for classification (CONV-01, RESEARCH Assumption A1)"
    requirement: "CONV-01"
    verification:
      - kind: manual_procedural
        ref: "Operator visual inspection of channel 0/1 marker distribution on wBA1-3_s1_MIP.ome.tiff; verbatim sign-off recorded below"
        status: pass
    human_judgment: true
    rationale: "No automated command substitutes for operator knowledge of expected TdTomato (cytosolic) vs Fos (nuclear) marker distribution on this animal — VALIDATION.md Manual-Only Verifications."
  - id: D2
    description: "Operator confirms all 5 scenes are distinct, intact single coronal sections with consistent scene_key<->s{N} mapping (CONV-02)"
    requirement: "CONV-02"
    verification:
      - kind: manual_procedural
        ref: "Operator visual inspection of wBA1-3_s{1..5}_identity.png thumbnails; verbatim sign-off recorded below"
        status: pass
    human_judgment: true
    rationale: "Scene fusion/shuffle is a visual/knowledge check no automated bbox assertion fully substitutes for (D-01/D-02/D-05)."

duration: 8min
completed: 2026-07-19
status: complete
---

# Phase 5 Plan 3: Human-Verify Gate — Channel Identity & Scene Identity Sign-Off Summary

**Operator approved channel-identity (index 0=TdTomato, 1=Fos) and scene-identity (5 distinct intact sections, consistent scene_key<->s{N}) for the wBA1-3 series, with two imaging-QC caveats logged for Phase 7.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-19T02:42:00Z
- **Completed:** 2026-07-19T02:43:08Z
- **Tasks:** 1 (checkpoint:human-verify, gate="blocking-human")
- **Files modified:** 0 source files (this plan writes no source files by design; only tracking docs updated)

## Accomplishments

- Confirmed all 10 reviewed artifacts from plan 05-01 exist in `Automated Cell Counting/wBA Sungmo/`: `wBA1-3_s1_MIP.ome.tiff` through `wBA1-3_s5_MIP.ome.tiff`, and `wBA1-3_s1_identity.png` through `wBA1-3_s5_identity.png` (verified via `ls -la`, timestamps 2026-07-18 18:47).
- Recorded the operator's explicit channel-identity confirmation — the CONV-01 / Assumption A1 sign-off that Phase 8's classifiers depend on.
- Recorded the operator's explicit scene-identity confirmation — CONV-02.
- Resolved a raised concern (s1 identity-thumbnail "wrong channel") as by-design, not a defect — did not reopen plan 05-01.
- Logged two genuine imaging/tissue-QC findings (autofocus/focus banding; small missing cortex pieces) as a pending todo tagged for Phase 7 (Imaging Re-Validation), rather than treating them as converter defects.

## Operator Sign-Off (Verbatim) — A1 / CONV-01 / CONV-02 Gate

**Operator's raw words during the gate:**

> "s1 doesnt seem to be in the correct channel, can you confirm? (png), index is correct in the ome-tiff (0-2), i am noticing however that the autofocus for some of the slices didnt work well leding to differing contrast in rows (see s1 ome itff), im also noticing that some of the images have small sections of the cortex missing, would this lead to future registration issues"

**Resolution reached with the orchestrator (recorded at time of sign-off):**

- **s1 identity-PNG "wrong channel" concern — RESOLVED, by design, no defect.** The identity thumbnail is DAPI (physical index 2) for ALL 5 scenes (used as the anatomical reference for scene-identity confirmation, not for channel-order confirmation). Confirmed in code (`_dapi_index` resolves to index 2; the thumbnail is built from `mip_channels[dapi_idx]`) and visually (s1 and s3 thumbnails show classic DAPI coronal anatomy as distinct sections). This does **not** reopen plan 05-01.
- **CHANNEL IDENTITY (the A1 sign-off, CONV-01) — CONFIRMED / PASSES.** Operator explicitly confirmed the OME-TIFF physical channel index order is correct: index 0 = TdTomato-AF568, index 1 = Fos-AF488, index 2 = DAPI ("index is correct in the ome-tiff (0-2)"). This is the high-severity gate (T-05-03-01 in the threat register) and it passes. The `--channels "TdTomato-AF568" "Fos-AF488" "DAPI"` override inherited from the M3 acquisition is independently re-confirmed correct on this new CZI.
- **SCENE IDENTITY (CONV-02) — CONFIRMED / PASSES.** 5 scenes are distinct, intact, single coronal sections with a consistent `scene_key<->s{N}` mapping (s1<->0 … s5<->4); pre-flight showed 5 pairwise non-overlapping bounding boxes. No fusion or shuffle.
- **Operator's explicit decision via the checkpoint:** "Approve + log imaging QC."

**Gate status:** APPROVED. Both must-have truths in the plan frontmatter are satisfied. Plan 05-01 is NOT reopened.

## Imaging-QC Caveats (Logged, Not Blocking, Carried to Phase 7)

These two findings are genuine imaging/tissue-quality observations — **not** scene-fusion or channel defects, and they do not reopen the converter (plan 05-01):

1. **Autofocus failure on some slices -> row-to-row (tile-row) contrast/focus banding**, visible in `wBA1-3_s1_MIP.ome.tiff`. Primary risk is detection/classification quality: defocused tile rows blur/dim nuclei. `histogramThreshold` + robust median+k·MAD absorb brightness *drift* but do **not** correct for focus *blur*. Low risk to the DeepSlice -> manual-angle -> export registration workflow (no elastix, so local contrast banding does not feed a similarity-metric optimizer).
2. **Small missing cortex pieces on some sections.** Not a registration-breaker under the no-elastix workflow, but causes region-level under-count and under-area (a deflated density denominator) for the affected region on the affected section(s) — relevant to Phase 9 (Generalizable Area-Based Density Readout, AREA-01/AREA-02). Handle via per-section tissue-QC and a-priori, principled region exclusion, consistent with the existing "tissue damage undetected" risk already tracked in STATE.md and the CLAUDE.md stats convention that "any animal/section exclusion must be a priori and principled — document the rule, not the outcome."

**Disposition:** Both are logged as a pending todo tagged for Phase 7 (Imaging Re-Validation, IMG-01/IMG-02):
`.planning/todos/pending/2026-07-18-phase-7-imaging-qc-autofocus-banding-and-missing-cortex.md`

## Task Commits

This plan performs no source-file changes (checkpoint-only gate, `files_modified: []` per frontmatter). No per-task feat/fix commit was made.

**Plan metadata:** recorded in the final tracking commit (SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md, and the new todo file).

## Files Created/Modified

- `.planning/todos/pending/2026-07-18-phase-7-imaging-qc-autofocus-banding-and-missing-cortex.md` - Pending todo logging the two imaging-QC caveats for Phase 7
- `.planning/phases/05-series-scaffolding-multi-scene-mip-batch-export-integrity/05-03-SUMMARY.md` - This summary
- `.planning/STATE.md` - Plan 3/3 marked done, A1 channel sign-off recorded as locked decision/context
- `.planning/ROADMAP.md` - Phase 5 plan-progress table updated (05-03 complete)
- `.planning/REQUIREMENTS.md` - CONV-01, CONV-02 marked operator-verified

## Decisions Made

- Channel index assignment (0=TdTomato, 1=Fos, 2=DAPI) is now operator-verified on the wBA1-3 series, not just inherited from M3 — added as a locked decision distinct from the pre-existing M3-derived `--channels` override decision.
- The s1 identity-PNG concern was resolved as a by-design DAPI reference thumbnail, not investigated further as a potential channel bug, based on direct code inspection (`_dapi_index`) plus visual confirmation.
- Imaging-QC findings (autofocus banding, missing cortex) are tracked as a Phase 7 todo rather than blocking Phase 5 completion or reopening plan 05-01, since neither affects channel identity or scene-fusion/shuffle (the two things this gate exists to catch).

## Deviations from Plan

None - plan executed exactly as written. This plan's sole task was the blocking human-verify checkpoint; the operator had already completed the visual inspection and given explicit sign-off (including the "Approve + log imaging QC" decision) prior to this recording pass. This executor run recorded that sign-off, confirmed the underlying artifacts exist, logged the imaging-QC caveats as a Phase 7 todo, and updated tracking docs — no re-presentation of the gate and no additional input was solicited, per the operator's explicit instruction.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 5 is now complete (3/3 plans): 05-01 (multi-scene MIP converter), 05-02 (EXP-02 export-integrity fix), 05-03 (this human-verify gate).
- CONV-01 and CONV-02 requirements are satisfied and operator-verified — the series is unblocked for Phase 6 (Registration Speedup) and, transitively, Phase 8 (LA/BA Classification), which depends on the A1 channel sign-off recorded here.
- Two imaging-QC caveats (autofocus/focus banding, missing cortex) are carried forward as an explicit pending todo for Phase 7 (Imaging Re-Validation, IMG-01/IMG-02) — not blockers for Phase 6/8, but should be addressed before the series' area-based readout (Phase 9) and classification quality are finalized.
- No blockers to starting Phase 6.

## Self-Check

- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s1_MIP.ome.tiff" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s2_MIP.ome.tiff" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s3_MIP.ome.tiff" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s4_MIP.ome.tiff" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s5_MIP.ome.tiff" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s1_identity.png" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s2_identity.png" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s3_identity.png" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s4_identity.png" ]` -> FOUND
- `[ -f "Automated Cell Counting/wBA Sungmo/wBA1-3_s5_identity.png" ]` -> FOUND
- `[ -f ".planning/todos/pending/2026-07-18-phase-7-imaging-qc-autofocus-banding-and-missing-cortex.md" ]` -> FOUND

## Self-Check: PASSED

---
*Phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity*
*Completed: 2026-07-19*
