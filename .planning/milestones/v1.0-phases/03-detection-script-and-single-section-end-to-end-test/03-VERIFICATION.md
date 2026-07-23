---
phase: 03-detection-script-and-single-section-end-to-end-test
verified: 2026-07-16T20:00:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 3: Detection Script and Single-Section End-to-End Test Verification Report

**Phase Goal:** `02_detect_classify.groovy` runs successfully on the M3 section, producing classified TdT+, Fos+, Double+, and Negative cells with atlas region labels.
**Verified:** 2026-07-16
**Status:** passed
**Re-verification:** No — initial verification

## Context note on method

This is a GUI-mediated, CPU-only QuPath 0.6.0 pipeline with no automated test framework (`03-VALIDATION.md`, confirmed). QuPath cannot be launched in this environment. The phase gate (Plan 03-04, `checkpoint:human-verify`) was FIRST run 2026-07-10 and FAILED (100% Negative, root-caused via `/gsd-debug`), then FIXED, then human-CONFIRMED on 2026-07-16 against the final script. Per the launching agent's explicit instruction, SC1–SC4 are treated as **human-attested**, not re-derivable by grep alone. This report verifies (a) the on-disk artifacts implementing the attested fixes are actually present and correct, and (b) the attestation trail is internally coherent and corroborated by independent filesystem evidence (not just narrative).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | SC1 — script runs via "Run for project" without errors, writes classified `data.qpdata` for M3 entry 1 | ✓ VERIFIED | Human-attested pass in `03-04-SUMMARY.md` (D1) + `.planning/debug/resolved/d05-threshold-all-negative.md` (`verification:` field: "n≈207k population... biology plausible"). Corroborated independently: `M3 Hippocampus 20x 062926 3 plane/data/1/data.qpdata` mtime = 2026-07-16 10:28:52 (same session), `project.qpproj.backup` shows a real 8-line diff dated 2026-07-16 10:28:43 (QuPath's own autosave, not something an executor could fabricate without a live GUI session) |
| 2 | SC2 — all four classes (TdT+/Fos+/Double+/Negative) present and non-zero; each cell carries an atlas region label | ✓ VERIFIED | Human-attested: "Total Fos+ ~20%, TdT+ ~3.5%, Double+/TdT+ ~0.45, SSp suppressed, LA confirmed; atlas labels resolve (CA1/SSp-bfd/DG-mo)" (`03-04-SUMMARY.md` D2). Source-level support: compound classification loop (`scripts/02_detect_classify.groovy:400-413`) computes all four classes from the bg-sub measure; `regionOf`/`regionLabel` closures (lines 435-461) resolve every cell to a leaf ABBA annotation via centroid-in-ROI containment — this half was never broken even in the 2026-07-10 failed run (per `03-GATE-FAILURE-D05.md`: "Atlas labels themselves resolve correctly") |
| 3 | SC3 — printed Atlas_X values fall in 5,000–10,000 µm | ✓ VERIFIED | Human-attested on acceptance (`03-04-SUMMARY.md` D3); unblocked because SC2 now produces positive cells to sample (was blocked 2026-07-10 when 0 positives existed). Source: Atlas_X sanity-print block (lines 510-550) uses `AtlasTools.getAtlasToPixelTransform(imageData).inverse()`, samples ≤5 Fos+/TdT+/Double+ cells, documents the ×10 voxel-index fallback without hard-coding a conversion |
| 4 | SC4 — per-region `Count: *` table for CA1/CA2/CA3/DG readable in the QuPath annotation pane | ✓ VERIFIED | Human-attested (`03-04-SUMMARY.md` D4). Source: count-rollup block (lines 483-507) writes `Count: <class>` onto every leaf region annotation via `ann.getMeasurementList().put(...)`, iterating the same `regionAnnotations` set as SC2's labeling — mechanism was correct even during the 2026-07-10 failure ("SC4 mechanism OK, values all-Negative" per `03-GATE-FAILURE-D05.md`), now populated with non-zero classes |
| 5 | D-04 — compartment-agnostic local-background-subtracted measure exists and is correctly wired (write path bug fixed) | ✓ VERIFIED | `localBackgroundSubtractedMean` closure (lines 171-208) uses `RoiTools.buffer`/`subtract`, `hierarchy.getAllObjectsForRegion` (bounding-box, not centroid-only), a throwaway `PathObjects.createDetectionObject` + `ObjectMeasurements.addIntensityMeasurements`. Annulus key resolved via `keySet().find { it.startsWith(channelName) && ...endsWith("mean") }` (line 197) — the confirmed fix for the root-cause key-mismatch bug (`"Cell: <ch> mean"` assumed vs actual `"<ch>: Mean"`). Writes committed via `d.getMeasurements().put(...)` (lines 240-241) — the confirmed fix for the earlier legacy-buffered-list write bug (`getMeasurementList().put()` never flushed before reads) |
| 6 | D-05 — thresholds re-derived per-section via a self-calibrating robust cut, old absolute cutoffs superseded | ✓ VERIFIED | `robustThreshold` closure (lines 309-316): `median + k*1.4826*MAD`, k=3 (`K_ROBUST`, line 286). The old nth-histogram-peak `derivePeakThreshold`/`ChannelHistogram.findPeaks` logic is GONE from the operative script — `ChannelHistogram`/`findPeaks`/`zeroPhaseFilter` do not appear except in one historical comment (line 272) documenting why the redesign happened. Classification loop (lines 406-409) reads exclusively `fosBg.meas`/`tdtBg.meas` (bg-sub measurement names) and `fosBg.thr`/`tdtBg.thr` (re-derived), never the old absolute cutoffs (Pitfall 9 guard, confirmed by inspection) |
| 7 | Both bgsub classifier JSONs exist, parse, and hold real re-derived (non-placeholder) thresholds | ✓ VERIFIED | `M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json` → `measurement: "Nucleus: AF488-T3 mean (bg-sub)"`, `threshold: 3377.76`; `TdT_classifier_bgsub.json` → `measurement: "Cytoplasm: AF568-T2 mean (bg-sub)"`, `threshold: 1679.08`. Both parse cleanly via `json.load`. Both file mtimes = 2026-07-16 13:38 — i.e. written by the script's own `writeBgsubClassifierSpec` during the live run, NOT the placeholder raw-cutoff values (13000.4538/16766.4671) documented as superseded in the SUMMARY — this is strong independent corroboration that a real QuPath run executed the full script |

**Score:** 7/7 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/02_detect_classify.groovy` | Canonical classify/label/report script, D-01–D-05 fixes wired | ✓ VERIFIED | 551 lines; all required closures/imports present (see truths above); no `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found |
| `"M3 Hippocampus 20x 062926 3 plane/scripts/02_detect_classify.groovy"` | Byte-identical project-local deploy copy | ✓ VERIFIED | `cmp` exits 0 — byte-identical to canonical |
| `"M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/Fos_Classifier_20x_bgsub.json"` | Valid JSON, bg-sub measurement key, real re-derived threshold | ✓ VERIFIED | Parses; `measurement` ends in `(bg-sub)`; `threshold` = 3377.76 (not a placeholder) |
| `"M3 Hippocampus 20x 062926 3 plane/classifiers/object_classifiers/TdT_classifier_bgsub.json"` | Valid JSON, bg-sub measurement key, real re-derived threshold | ✓ VERIFIED | Parses; `measurement` ends in `(bg-sub)`; `threshold` = 1679.08 (not a placeholder) |
| `.planning/debug/resolved/d05-threshold-all-negative.md` | Complete root-cause trail, `status: resolved` | ✓ VERIFIED | Frontmatter `status: resolved`, `resolved: 2026-07-16`, `verification:` field records the passing run details |
| `.planning/phases/.../03-GATE-FAILURE-D05.md` | Header marks resolution, correction section supersedes the original (wrong) diagnosis | ✓ VERIFIED | Header: "✅ RESOLVED 2026-07-16"; correction block explicitly supersedes the original sparse-marker-unimodality theory with the true key-mismatch root cause |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| Compound classification loop | `Fos_Classifier_20x_bgsub.json` / `TdT_classifier_bgsub.json` | `readSpec` (Gson `JsonParser`) reading `fosBg`/`tdtBg` | WIRED | Lines 394-398, 406-409: `fosBg.meas`/`fosBg.thr` and `tdtBg.meas`/`tdtBg.thr` are the operative classification inputs; old `fos`/`tdt` (raw cutoffs) are printed for reference only (line 398), never applied |
| `localBackgroundSubtractedMean` closure | Compound classification | `bgsubFos`/`bgsubTdt` written via `getMeasurements().put(...)`, read back by the threshold-derivation and classification loop under the SAME keys | WIRED | Write (lines 240-241) and read (lines 327-328, 406-407) both use `getMeasurements()` (Map view) — confirmed self-consistent, closing the exact bug that caused the 2026-07-10 all-Negative failure |
| Annulus throwaway measurement object | `localBackgroundSubtractedMean`'s return value | `keySet().find { startsWith(channelName) && endsWith("mean") }` | WIRED | Line 197 resolves the actual measurement key empirically rather than assuming a `"Cell: ..."` prefix — the confirmed fix, with an A5 self-check println (line 188) that would have caught a regression |
| `02_detect_classify.groovy` (canonical) | `02_detect_classify.groovy` (M3 project copy) | Dual-location hard-copy deploy | WIRED | `cmp` confirms byte-identity |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|-------------|--------|----------|
| SCRI-03 | 03-01, 03-02, 03-03, 03-04 | `02_detect_classify.groovy` written and tested on one section; produces `data.qpdata` with classified cells | ✓ SATISFIED (substance) / ⚠️ STALE (bookkeeping) | Substance: all four SC human-confirmed 2026-07-16 with independent corroborating filesystem evidence (see Truths 1–7). **Bookkeeping gap:** `.planning/REQUIREMENTS.md` still shows SCRI-03 as `- [ ]` (unchecked) and the Traceability table lists it as `Pending`, even though `.planning/ROADMAP.md` (uncommitted working-tree edit, not yet applied) already marks Phase 3 `[x]` complete 2026-07-16. This is a documentation-sync gap, not a code/behavior gap — flagged for the orchestrator to reconcile `REQUIREMENTS.md` when it commits the phase-completion tracking update. Does not block the phase goal, which is about the script's behavior, not the requirements ledger's checkbox state. |

Note on REQUIREMENTS.md's SCRI-03 *description* text ("runs WatershedCellDetection, cytoplasmic expansion, ... via BraiAnDetect"): this describes the Phase-1-era intended architecture. Per D-01 (locked in `03-CONTEXT.md`, honored consistently across all four plans), detection was deliberately kept OUT of this script (it lives in `run_braian_detection.groovy`); `02_detect_classify.groovy` is the classify/label/report entry point that assumes detections already exist, and classification uses centroid-in-ROI compound logic, NOT BraiAn.yml's `OverlappingDetections`. This is a documented, deliberate architectural decision (not a shortfall), but the REQUIREMENTS.md prose has not been updated to reflect it — same bookkeeping gap as above, informational only.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | `grep -n -E "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER"` on `scripts/02_detect_classify.groovy` returned no matches. No debt markers, no stub returns (`return null`/`return {}`/`return []`), no empty handlers. |

### Cross-Reference: Plan SUMMARY Claims vs. On-Disk Artifacts

| Plan | Claim | On-disk verification |
|------|-------|----------------------|
| 03-01 | D-01/D-02 guard, compound classification, `regionOf`/`regionLabel` | Confirmed present in current script; matches described shape exactly |
| 03-02 | `Count: *` rollup via `MeasurementList.put`; Atlas_X sanity print via `AtlasTools` | Confirmed present (lines 483-550) |
| 03-03 | `localBackgroundSubtractedMean` (D-04); `ChannelHistogram.findPeaks`/`zeroPhaseFilter` threshold re-derivation (D-05, as originally designed) | D-04 half confirmed unchanged. **D-05 half is stale** as written in 03-03-SUMMARY.md — the `ChannelHistogram`-based nth-peak approach it describes was later REPLACED during the debug session (commit `89f4095`) with the robust `median + k*1.4826*MAD` cut. This supersession is explicitly and correctly documented in 03-04-SUMMARY.md's "Deviations from Plan" section ("Plan step 7 ... was stale and not applied ... redesigned during debugging"), so it is not a hidden discrepancy — it is the expected trail of a debug-session fix landing after the plan's own SUMMARY was written. |
| 03-04 | Human confirmed all 4 SC on the final bg-sub script (2026-07-16), gate cleared, k=3 locked | Confirmed: commits `89f4095`/`d6ea728`/`72decba` (the actual fix commits) exist in git log; `data.qpdata`/`.qpproj.backup`/bgsub-JSON mtimes on 2026-07-16 corroborate a real run happened on that date, independent of the SUMMARY's narrative |

### Human Verification Required

None. The phase gate's human-in-the-loop check (Plan 03-04) has already been executed and its outcome is recorded with a coherent, independently-corroborated evidence trail (git commits, file mtimes, non-placeholder JSON values). No further human action is needed to close this phase.

### Gaps Summary

No blocking gaps. One non-blocking bookkeeping item: `.planning/REQUIREMENTS.md`'s SCRI-03 checkbox and Traceability row still read `[ ]` / `Pending`; recommend the orchestrator update this alongside committing the phase-completion tracking changes (the `ROADMAP.md` edit marking Phase 3 complete is already staged in the working tree, uncommitted). This does not affect the phase-goal verdict — the underlying script behavior and artifacts are verified sound.

---

_Verified: 2026-07-16_
_Verifier: Claude (gsd-verifier)_
