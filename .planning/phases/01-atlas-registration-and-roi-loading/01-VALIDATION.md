---
phase: 1
slug: atlas-registration-and-roi-loading
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-01
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (no automated test suite — GUI pipeline) |
| **Config file** | none — QuPath/Fiji GUI tools; validation via file-system checks and QuPath summary.json |
| **Quick run command** | `ls "M3 Hippocampus 20x 062926 3 plane/data/1/"` (check ABBA files present) |
| **Full suite command** | Manual QuPath + file check sequence (see Per-Task Verification Map) |
| **Estimated runtime** | ~5 minutes (manual) |

---

## Sampling Rate

- **After every task commit:** Check file system for expected outputs (ABBA JSON/zip, script files)
- **After every plan wave:** Full manual verification against success criteria
- **Before `/gsd-verify-work`:** All success criteria confirmed manually
- **Max feedback latency:** 5 minutes

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | REG-01 | — | N/A | manual | `ls "M3 Hippocampus 20x 062926 3 plane/data/1/ABBA-Transform-allen_mouse_10um_java.json"` | ⬜ W1 | ⬜ pending |
| 1-01-02 | 01 | 1 | REG-01 | — | N/A | manual | `ls "M3 Hippocampus 20x 062926 3 plane/data/1/ABBA-RoiSet-allen_mouse_10um_java.zip"` | ⬜ W1 | ⬜ pending |
| 1-01-03 | 01 | 1 | REG-02 | — | N/A | manual | Visual QC image present in `data/1/registration_QC.jpg` | ⬜ W1 | ⬜ pending |
| 1-02-01 | 02 | 2 | SCRI-01 | — | N/A | manual | `cat "Analysis/scripts/01_load_abba_rois.groovy"` exits 0 | ⬜ W2 | ⬜ pending |
| 1-02-02 | 02 | 2 | SCRI-01 | — | N/A | manual | QuPath "Run for project" completes with no errors; `summary.json` shows ~260 annotations | ⬜ W2 | ⬜ pending |
| 1-02-03 | 02 | 2 | SCRI-01 | — | N/A | manual | Re-run script; annotation count stays ~260 (no duplication) | ⬜ W2 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

None — this phase has no automated test suite. All verifications are manual (GUI pipeline: Fiji ABBA registration and QuPath script execution).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| ABBA registration quality | REG-01 | Fiji ABBA is a GUI-only tool; registration must be visually inspected | Open Fiji ABBA with M3 062926 project; run DeepSlice → adjust DV/ML tilt manually → export; confirm atlas outlines visible on tissue |
| QC image — CA1/CA3/DG + cortex + ventral edge aligned | REG-02 | Visual judgment required; no pixel-level automated check | Screenshot QuPath viewer with atlas overlay; verify CA1, CA3, DG subfield boundaries + cortex + ventral edge all align |
| ROI loading — no errors | SCRI-01 | QuPath script execution feedback is visual; no CLI runner | Open QuPath project; Extensions > BIOP > Run for project; check console for exceptions |
| No duplicate regions on re-run | SCRI-01 | Requires QuPath GUI to observe annotation count | Run script twice; annotation panel must show same count (~260) both times |

---

## Validation Sign-Off

- [ ] ABBA transform and ROI zip files present in `data/1/`
- [ ] QC image shows hippocampal subfields + cortex + ventral edge aligned
- [ ] Script runs via "Run for project" with no errors
- [ ] Re-run confirms no duplication (clearAllObjects guard working)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
