---
phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity
verified: 2026-07-19T00:00:00Z
status: passed
score: 7/7 must-haves verified
behavior_unverified: 0
overrides_applied: 0
deferred:
  - truth: "03_export_val01_metrics.groovy 'Run for project' across all 5 real classified QuPath entries produces 10 non-empty, distinct TSVs with differing row counts (the full live exercise of EXP-02, beyond the mechanism check)"
    addressed_in: "Phase 8 / Phase 10"
    evidence: "05-02-PLAN.md sequencing note: 'the full 5-classified-section proof...naturally completes in Phase 8/10 when 5 registered+classified entries exist'; ROADMAP.md Phase 10 depends on 'Phase 8 (classified per-region series) and Phase 5 (fixed batch export, EXP-02)'. The 5 QuPath entries do not exist until Phase 6 registration + Phase 8 classification run; Phase 5 correctly proves the writer mechanism only."
---

# Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity Verification Report

**Phase Goal:** Establish data integrity at both ends of the series before it runs — the 16 GB processed CZI becomes 5 identity-verified section MIP OME-TIFFs (no scene fusion, each carrying physical pixel size in embedded OME-XML), and the export script writes correct per-entry output across all 5 sections without truncation.
**Verified:** 2026-07-19
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `czi_mip.py` emits exactly 5 MIP OME-TIFFs (one per scene) from the real `-001-07_processed.czi`, no scene fusion, each with embedded OME-XML pixel size (CONV-01) | ✓ VERIFIED | Re-ran the full conversion output is present on disk: `wBA1-3_s{1..5}_MIP.ome.tiff`, distinct sizes (775M/852M/908M/852M/990M — no two identical, ruling out duplication/fusion). Independently re-read all 5 with `tifffile`: shapes `(3,9295,13902)/(3,10216,13903)/(3,10216,14824)/(3,10216,13903)/(3,11138,14824)` each matching that scene's bbox `(h,w)` exactly; each `ome_metadata` contains `PhysicalSizeX="0.6905355"` and `PhysicalSizeXUnit="µm"`. |
| 2 | Each output MIP is identity-verified to its physical section via a printed scene bbox record + thumbnail the operator can visually confirm (CONV-02); AP order is explicitly out of scope at conversion time (D-03, documented decision) | ✓ VERIFIED | Re-ran `czi_mip.py --check-scenes` myself: prints 5 non-overlapping bboxes with 0-based keys, exits 0. Opened `wBA1-3_s1_identity.png` and `wBA1-3_s3_identity.png` directly — each shows one coherent, intact single coronal section (distinct anatomy: s1 shows a section without visible hippocampus, s3 clearly shows fimbria/hippocampal formation) — no double-brain ghosting or fusion. Operator sign-off recorded verbatim in 05-03-SUMMARY.md confirms all 5 + the scene_key<->s{N} mapping. D-03 (no AP claim at conversion time) is a pre-declared, documented scope decision in 05-CONTEXT.md, not a silent narrowing — AP ordering is explicitly assigned to Phase 6/DeepSlice. |
| 3 | A pre-flight smoke test asserts scene count == 5 and pairwise non-overlap BEFORE the heavy conversion loop (ROADMAP SC#4) | ✓ VERIFIED | `conda run -n braian python3 czi_mip.py --check-scenes --czi ".../-001-07_processed.czi"` run live during this verification: prints 5 scene bboxes, "All 5 scene bboxes pairwise non-overlapping -- PASS", exits 0 in seconds (no heavy read). |
| 4 | Channel identity (physical index 0=TdTomato, 1=Fos, 2=DAPI) is independently confirmed correct on this new CZI before the series is trusted for classification (CONV-01, Assumption A1) | ✓ VERIFIED | Blocking human-verify gate (plan 05-03) executed; operator's verbatim sign-off recorded in 05-03-SUMMARY.md: "index is correct in the ome-tiff (0-2)" — explicit approval, not auto-advanced. Two unrelated imaging-QC observations (autofocus banding, small missing cortex) were correctly triaged as non-blocking and logged to a Phase-7 todo rather than reopening plan 05-01. |
| 5 | `03_export_val01_metrics.groovy` derives both output filenames from the sanitized, collision-safe running QuPath entry identity so "Run for project" across N entries writes 2·N distinct files with no clobbering (EXP-02) | ✓ VERIFIED | Source inspected directly: `buildPathInProject("results", "${stem}__val01_percell_export.tsv"/"${stem}__val01_region_area.tsv")` (2 call sites), `getProjectEntry()` present, stem is `${safeName}__id${entryId}` anchored on the entry's stable unique `getID()` (the WR-03 code-review fix for name-sanitization collisions), with an empty-stem guard that throws rather than writing an unnamed file. Column headers (`percellHeader`/`regionHeader`, 7 and 5 cols) and all downstream row-building/write logic are byte-for-byte unchanged per `git diff` scope (confirmed by re-reading the full file — the edit is confined to the path-construction block). Both `scripts/03_export_val01_metrics.groovy` and the QuPath project's copy are byte-identical (`cmp` exits 0, re-verified live). |
| 6 | `scripts/verify_export_integrity.py` codifies the non-clobbering guarantee (pairing, even file count == 2·distinct stems, non-identical row counts across entries) and is read-only | ✓ VERIFIED | Independently constructed 4 synthetic fixtures (not reused from the executor's scratchpad) and ran the real checker against each: 2-stem differing-row-count case → PASS/exit 0; unpaired percell file → FAIL/exit 1 with correct message; 2-stem identical-row-count (clobber signature) → FAIL/exit 1 with the clobbering-guard message; single-stem case → PASS/exit 0 with the multi-entry assertion explicitly skipped. All 4 behaviors match the SUMMARY's claims exactly. |
| 7 | Code-review blocker + warnings (CR-01 crash/misattribution risk, WR-01 assert-strippable guards, WR-02 dimension-extent miscount, WR-03 stem-collision) are actually fixed in the shipped code, not just marked fixed in the review doc | ✓ VERIFIED | Read `czi_mip.py` directly: `_scene_tile_count()` (CR-01 fix) reconciles aggregate-vs-per-scene `get_dims_shape()` forms and returns `-1` rather than crashing/misattributing; `_extent()` helper (`hi - lo`, WR-02) used for `n_c`/`n_z`/`M`; all four integrity guards are `raise SystemExit(...)`, not bare `assert` (WR-01 — confirmed zero bare `assert` statements remain in the file, only a docstring mentions the word). `03_export_val01_metrics.groovy` stem is `getID()`-anchored (WR-03), confirmed above. All four fix commits (`cb11ce4`, `3da6124`, `1dd3445`, `775863a`) present in `git log`. |

**Score:** 7/7 truths verified (0 present-but-behavior-unverified)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | The full live 5-entry "Run for project" exercise (10 non-empty TSVs with differing row counts, produced by actually running the fixed Groovy script against 5 real classified QuPath entries) | Phase 8 / Phase 10 | 05-02-PLAN.md's own sequencing note states this proof "naturally completes in Phase 8/10 when 5 registered+classified entries exist"; ROADMAP.md's Phase 10 entry lists "Depends on: Phase 8 (classified per-region series) and Phase 5 (fixed batch export, EXP-02)". The 5 QuPath entries this script would run against do not exist until Phase 6 (registration) and Phase 8 (classification) complete — Phase 5 could not have produced this proof and correctly scoped itself to proving the writer mechanism (source inspection + byte-identical dual-copy + a synthetic-fixture-driven integrity checker), which this verification independently reproduced. |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `czi_mip.py` | Multi-scene CLI converter (argparse: `--czi`/`--outdir`/`--channels`/`--pixel-um`/`--animal-prefix`/`--check-scenes`) | ✓ VERIFIED | All flags present (parse_args lines 46-64); `_preflight_scenes`, `_scene_identity_record`, `_save_identity_thumbnail`, `_build_ome_xml`, `_scene_tile_count`, `_extent` all present and wired into `main()`. |
| `Automated Cell Counting/wBA Sungmo/wBA1-3_s{1..5}_MIP.ome.tiff` | 5 per-scene MIP OME-TIFFs (gitignored, on-disk only) | ✓ VERIFIED | All 5 present, distinct file sizes, correct shapes, correct pixel calibration (independently re-verified via `tifffile`, not just `ls`). |
| `Automated Cell Counting/wBA Sungmo/wBA1-3_s{1..5}_identity.png` | 5 scene-identity thumbnails | ✓ VERIFIED | All 5 present; 2 opened directly and visually confirmed as coherent single coronal sections, matching operator's independent sign-off. |
| `scripts/03_export_val01_metrics.groovy` | Fixed per-entry export path | ✓ VERIFIED | `buildPathInProject` ×2, `getProjectEntry()`, `getID()`-anchored stem, empty-stem guard, headers/row-logic unchanged. |
| `M3 Hippocampus 20x 062926 3 plane/scripts/03_export_val01_metrics.groovy` | Byte-identical dual-location copy | ✓ VERIFIED | `cmp` exits 0 (re-verified live). |
| `scripts/verify_export_integrity.py` | Read-only export-integrity checker | ✓ VERIFIED | `--help` shows `--results`; all 4 assertion code paths independently exercised against fresh synthetic fixtures and behave as documented; confirmed read-only design (no writes to `--results`). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `czi_mip.py` scene loop | `get_all_mosaic_scene_bounding_boxes()` | `region=(b.x,b.y,b.w,b.h)` passed verbatim, no `S=` kwarg | WIRED | Confirmed by direct read of `main()` (lines 219-244) — `read_mosaic(region=region, C=c, Z=z, scale_factor=1.0)`, no scene selector. |
| `czi_mip.py` identity record | `czi.get_dims_shape()` | `_scene_tile_count()` positional reconciliation, never crashes | WIRED | CR-01 fix present and used at line 249. |
| `03_export_val01_metrics.groovy` | `results/` output path | `getProjectEntry()` → sanitized `getID()` → `buildPathInProject` | WIRED | Confirmed 2 call sites building 2 distinct filenames per entry. |
| `verify_export_integrity.py` | `results/*.tsv` | glob + pairing/count/row-count assertions | WIRED | Exercised against 4 independent synthetic fixtures with all 4 expected outcomes reproduced. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Pre-flight smoke test (SC#4) | `conda run -n braian python3 czi_mip.py --check-scenes --czi ".../-001-07_processed.czi"` | 5 scenes, pairwise non-overlap PASS, exit 0 | ✓ PASS |
| Pixel-size + shape round-trip on real converter output | `tifffile.TiffFile(...).ome_metadata` + `.series[0].shape` for all 5 MIPs | `PhysicalSizeX="0.6905355"`, `PhysicalSizeXUnit="µm"`, shape==bbox(h,w) for all 5 | ✓ PASS |
| `verify_export_integrity.py` — PASS (multi-entry, differing rows) | run against synthetic 2-stem fixture | exit 0, "PASS" | ✓ PASS |
| `verify_export_integrity.py` — FAIL (unpaired file) | run against synthetic unpaired fixture | exit 1, correct pairing-failure message | ✓ PASS |
| `verify_export_integrity.py` — FAIL (clobber signature) | run against synthetic identical-row-count fixture | exit 1, correct clobbering-guard message | ✓ PASS |
| `verify_export_integrity.py` — PASS (single-entry, assertion skipped) | run against synthetic single-stem fixture | exit 0, multi-entry assertion explicitly skipped message | ✓ PASS |
| No bare `assert` remains in `czi_mip.py` (WR-01 regression check) | `grep -n "assert" czi_mip.py` | Only 1 hit, inside a docstring comment | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh`-style probes are declared or conventionally present for this phase; the phase's own verification commands (smoke test, integrity checker) are covered under Behavioral Spot-Checks above. Step 7c: SKIPPED (no probe scripts found).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| CONV-01 | 05-01, 05-03 | `czi_mip.py` emits one MIP OME-TIFF per scene, no fusion, region-based isolation | ✓ SATISFIED | 5 distinct-sized MIPs, correct calibration, operator channel-identity sign-off. |
| CONV-02 | 05-01, 05-03 | Each scene's output verified to correct physical section before entering registration | ✓ SATISFIED | Identity records + thumbnails + operator visual/consistency sign-off. |
| EXP-02 | 05-02 | Batch export fixed for multi-entry, no cross-entry TSV clobbering | ✓ SATISFIED | Mechanism fix (`getID()`-anchored stem), byte-identical dual copy, integrity checker independently exercised. Full 5-entry live proof correctly deferred to Phase 8/10 (see Deferred Items). |

No orphaned requirements: REQUIREMENTS.md's traceability table maps exactly CONV-01, CONV-02, EXP-02 to Phase 5, matching the union of all three plans' frontmatter `requirements:` fields exactly.

### Anti-Patterns Found

None. Scanned all 3 phase-modified files (`czi_mip.py`, `scripts/03_export_val01_metrics.groovy`, `scripts/verify_export_integrity.py`) for `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/placeholder wording — zero matches. No bare `assert` integrity guards remain (WR-01 fix confirmed). The 4 Info-level findings in `05-REVIEW.md` (IN-01 through IN-04) are explicitly deferred, documented, low-severity maintenance notes — not blockers, and correctly excluded from this phase's scope.

### Human Verification Required

None outstanding. The phase's one human-judgment item (channel identity, Assumption A1 — a swapped TdT/Fos channel would poison every downstream classifier) was a blocking-human-verify gate (plan 05-03) that has already been executed with an explicit, verbatim-recorded operator approval, not auto-advanced. This verification additionally independently opened 2 of the 5 identity thumbnails and confirmed they show distinct, coherent, intact single coronal sections, corroborating the operator's sign-off rather than merely trusting it.

### Gaps Summary

No gaps. Both halves of the phase's data-integrity gate are established and independently re-verified against the actual codebase and on-disk artifacts (not merely SUMMARY.md claims): the 16 GB CZI reliably converts to 5 identity-verified, pixel-calibrated section MIPs with a live-confirmed pre-flight smoke test, and the export script's per-entry mechanism is fixed, code-reviewed (1 blocker + 3 warnings all fixed with commits present in git log), byte-identical across both deploy locations, and covered by a read-only integrity checker whose 4 assertion paths were independently exercised against fresh synthetic fixtures during this verification (not just accepted from the SUMMARY). The one item not yet exercised live — the full 5-real-entry "Run for project" pass — is correctly and explicitly deferred to Phase 8/10, where the classified QuPath entries this script needs will first exist; this dependency chain is documented in both the plan and the roadmap, not silently skipped.

---

_Verified: 2026-07-19_
_Verifier: Claude (gsd-verifier)_
