---
phase: 5
slug: series-scaffolding-multi-scene-mip-batch-export-integrity
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-18
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Seeded from `05-RESEARCH.md` § Validation Architecture. This project intentionally
> has **no** pytest/unit-test framework — verification is script-level printed assertions
> + human visual audit (per `.claude/CLAUDE.md` Error Handling). Do not introduce a new
> pytest layer; follow the established convention.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — script-level printed assertions + human visual audit (project convention; no pytest/conftest anywhere in repo) |
| **Config file** | none — no framework install needed (Wave 0 adds inline assertions to the scripts themselves) |
| **Quick run command** | `conda run -n braian python3 <conversion_script>.py --czi "Automated Cell Counting/wBA Sungmo/-001-07_processed.czi" --outdir <dir>` (prints per-scene assertions to stdout) |
| **Full suite command** | Same command over the full 5-scene series — this IS the full suite (5 scenes, no separate quick subset) |
| **Estimated runtime** | conversion bounded by 16 GB CZI read; per-scene streaming keeps memory bounded |

---

## Sampling Rate

- **After every task commit:** Run the conversion script against the real CZI (only one real input exists — no smaller fixture) and inspect stdout assertions
- **After every plan wave:** Re-run the full 5-scene conversion + a "Run for project" pass across all 5 resulting QuPath entries
- **Before `/gsd-verify-work`:** all 5 MIPs exist with correct OME-XML pixel size, all 5 identity thumbnails visually confirmed by operator, `results/` contains 10 non-clobbered TSVs
- **Max feedback latency:** single conversion run (no watch mode)

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command / Assertion | File Exists | Status |
|-----|----------|-----------|-------------------------------|-------------|--------|
| CONV-01 | Exactly 5 MIP OME-TIFFs, one per scene, no fusion | scripted assertion (inline in conversion script) | `assert len(list(outdir.glob("wBA1-3_s*_MIP.ome.tiff"))) == 5` + per-scene `assert mip.shape[1:] == (bbox.h, bbox.w)` | ❌ W0 | ⬜ pending |
| CONV-01 | Each output carries correct physical pixel size in OME-XML | scripted assertion | round-trip `tifffile.TiffFile(out).ome_metadata` → assert `PhysicalSizeX == 0.69` (calibrated value) | ❌ W0 | ⬜ pending |
| CONV-01 | Scene bboxes non-overlapping (guards region-based fusion) | scripted pre-flight assertion | pairwise rectangle-intersection over `get_all_mosaic_scene_bounding_boxes()`, assert no overlap, printed before conversion loop | ❌ W0 | ⬜ pending |
| CONV-02 | Scene→section identity confirmable by operator | manual (visual) | operator opens 5 `*_identity.png` thumbnails + reads printed text record (bbox, tile count M, dims, 0-based key + 1-based `s{N}` label) | manual (D-01) | ⬜ pending |
| EXP-02 | 5 distinct per-entry TSV pairs, no truncation / cross-section rows | scripted + manual | after "Run for project": `ls results/*.tsv \| wc -l` == 10; `wc -l results/*__val01_percell_export.tsv` row counts differ across entries (proves no clobbering) | ❌ W0 | ⬜ pending |
| EXP-02 | Column contract unchanged | already covered | `scripts/val01_metrics.py` `PERCELL_EXPECTED_COLS`/`REGION_EXPECTED_COLS` checks already `sys.exit` on header mismatch — no new test | ✅ existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Pre-flight bbox-overlap assertion — promote the ad hoc pairwise-rectangle check (run during research) into the conversion script
- [ ] Post-conversion assertion — exactly 5 output files, each shape-matched to its scene bbox
- [ ] Post-export integrity check — `scripts/verify_export_integrity.py` (or inline shell): file count == 10 and per-entry row counts non-identical (guards regression to the truncation bug)
- [ ] No pytest framework install — stays consistent with project's "printed assertion + human visual audit" convention

*No unit-test framework gap — this project intentionally does not use one.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Scene→physical-section identity | CONV-02 | Human eyeball verification is explicitly what D-01 asks for; not an automatable claim | Operator opens the 5 `*_identity.png` thumbnails and reads the paired text record; confirms morphology differs per scene and the 0-based key ↔ `s{N}` label mapping is correct |
| Channel identity (TdTomato vs Fos on indices 0/1) | CONV-01 | Research Assumption A1 — density alone could not independently re-derive which of index 0/1 is TdT vs Fos | `checkpoint:human-verify` — operator visually confirms channel assignment on one output MIP before the series is trusted |

---

## Validation Sign-Off

- [ ] All tasks have inline scripted assertions or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without an observable check
- [ ] Wave 0 covers all MISSING references (bbox-overlap, output-count, export-integrity)
- [ ] No watch-mode flags
- [ ] `nyquist_compliant: true` set in frontmatter once Wave 0 assertions land

**Approval:** pending
