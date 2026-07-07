---
phase: 02
slug: detection-parameter-lock
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-07
updated: 2026-07-07
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> This phase authors YAML/JSON config + Groovy helpers and is gated by GUI measurement QC — there is NO unit-test framework. Validation is (a) static file assertions on the config artifacts and (b) human-read D-05 measurement gates in QuPath.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — Groovy/QuPath + YAML/JSON authoring. No unit-test framework exists or is warranted. Validation = static file checks (`jq`, pyyaml parse, `check_classifier_compartment.py`) + measurement-gate visual QC in QuPath (`qc_detection_gates.groovy`). |
| **Config file** | none |
| **Quick run command (static, automatable)** | `jq`/`check_classifier_compartment.py` compartment asserts + `braian`-env pyyaml parse of `BraiAn.yml` |
| **Full suite command (measurement gate, manual)** | In QuPath: BraiAnDetect run on entry 1 → run `scripts/qc_detection_gates.groovy` → read nucleus-area peak + DAPI density vs the D-05 ranges on DG + CA1 |
| **Estimated runtime** | Static checks < 5 s; a QuPath detection + QC run on one section ~minutes (CPU-only) |

---

## Sampling Rate

- **After every classifier/BraiAn.yml edit (02-01, 02-02 Task 2):** run the static asserts (`jq` compartment, pyyaml parse, `check_classifier_compartment.py`) — sub-5-second automated feedback.
- **After the 02-01 authoring wave:** all three artifacts (BraiAn.yml + 2 classifiers) pass static asserts; both helper scripts exist and the static check exits 0 on the known-good source Fos classifier.
- **At the 02-02 human checkpoint:** full D-05 gate computation (nucleus-area peak + DAPI density) on entry 1, DG AND CA1, plus DG bleed / CA1 separability visual QC.
- **Phase gate:** both D-05 gates PASS (DG + CA1) before BraiAn.yml + both classifiers are LOCKED. D-06 (Double+ ratio) and D-07 (Fos+ negative-control) are reported but NOT gating.
- **Max feedback latency:** static checks < 5 s; measurement gate is bounded by a single-section QuPath run (human-initiated).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure/Correct Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|--------------------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | SCRI-02 (harness) | T-02-01/02 | QC helper reads real detections+annotations; static check catches wrong compartment | automatable (static) | `test -s scripts/qc_detection_gates.groovy && grep -q getDetectionObjects … && python3 scripts/check_classifier_compartment.py <known-good-Fos> "Nucleus: AF488-T3 mean"` | ✅ authored this task | ⬜ pending |
| 02-01-02 | 01 | 1 | CLASS-01 | T-02-01 | Fos nuclear, TdT cytoplasmic; no leftover `"Other"` class | automatable (static) | `jq -e '.function.measurement=="Nucleus: AF488-T3 mean"' Fos… && jq -e '.function.measurement=="Cytoplasm: AF568-T2 mean"' TdT…` | ✅ authored this task | ⬜ pending |
| 02-01-03 | 01 | 1 | SCRI-02 | T-02-02/03 | Single DAPI-T4 entry, histogramThreshold (not absolute), cellExpansion>0, exact channels | automatable (static) | `braian-python pyyaml parse-assert → "BraiAn.yml OK"` | ✅ authored this task | ⬜ pending |
| 02-02-01 | 02 | 2 | SCRI-02, CLASS-01 | T-02-01/05 | D-05 gates PASS on DG+CA1; non-zero Fos+/TdT+; Fos+ in nuclei; DG rings non-bleeding | **manual-only** (QuPath GUI) | N/A — human reads `qc_detection_gates.groovy` output + visual overlay | ❌ Wave 0 (summary/measurements written by QuPath at run time) | ⬜ pending |
| 02-02-02 | 02 | 2 | SCRI-02, CLASS-01 | T-02-06/07 | Tuned values written back without altering topology/compartment; lock recorded | automatable (static) | `pyyaml parse-assert + jq compartment/threshold asserts + lock-record greps` | ✅ authored this task | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `scripts/qc_detection_gates.groovy` — computes the two D-05 gate metrics (nucleus-area peak bin, DAPI density/mm²) + advisory D-06 ratio from a detection run. **Authored in Plan 02-01 Task 1** (was a RESEARCH Wave-0 gap; no such script existed in the repo).
- [x] `scripts/check_classifier_compartment.py` — static assert of classifier `function.measurement` compartment string, reusable for CLASS-01 (now) and CLASS-02 (v2). **Authored in Plan 02-01 Task 1.**
- [ ] Framework install: none needed — inherently GUI/measurement-based validation, no unit-test framework gap.

---

## Manual-Only Verifications

> These are the honestly-manual checks for this phase. Per CLAUDE.md, QuPath GUI parameter tuning and visual overlay QC cannot be automated and are handed to the researcher; the executor authors artifacts and records reported values.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Nucleus-area distribution peaks in 50–150 µm² (D-05 gate 1) | SCRI-02 | Requires a live WatershedCellDetection run on real 16-bit image data in QuPath | Run BraiAnDetect on entry 1 → run `qc_detection_gates.groovy` → read peak bin for DG and CA1 |
| DAPI nucleus density 500–2000/mm² (D-05 gate 2) | SCRI-02 | Needs detections + ABBA annotation areas in a live QuPath session | Same run; QC script prints DG + CA1 density/mm² |
| Detection produces non-zero Fos+ and TdT+ cells | SCRI-02 | Channel-name correctness only observable when detection runs on the actual image | Confirm both classes present in the QuPath detection output |
| Fos+ overlay lands only in nuclei | CLASS-01 | Visual overlay judgment on the viewer | Zoom DG/CA1; confirm Fos+ markers coincide with nuclei, not cytoplasm |
| DG cytoplasmic rings do not bleed into adjacent nuclei | SCRI-02 (success criterion 4) | Localized visual judgment on dense DG that a global histogram can mask (Pitfall 3) | Zoom dense DG; inspect expansion rings vs neighbouring nuclei |
| Classifier thresholds re-derived histogram-relative (D-02) | SCRI-02 | Requires inspecting entry-1's own measurement distributions in QuPath | Read `Nucleus: AF488-T3 mean` / `Cytoplasm: AF568-T2 mean` distributions; pick cutoffs by percentile or median+k·MAD |
| Double+/TdT+ ratio (D-06) — REPORTED, NOT A GATE | (advisory) | Biological outcome; deliberately excluded from lock to avoid circularity | QC script prints ratio; record advisory, do not gate |
| Fos+ negative-control rate (D-07) — SKIPPED this phase | (deferred) | No trustworthy low-activity control region on a single hippocampal section | Note deferral to full series in the lock record |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify OR are inherently-manual GUI checkpoints (02-02 Task 1) with reported-value acceptance.
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (only the single 02-02 human checkpoint is manual; it is flanked by automated static checks).
- [x] Wave 0 covers all MISSING references (both QC helper scripts authored in 02-01 Task 1).
- [x] No watch-mode flags.
- [x] Feedback latency: static checks < 5 s; measurement gate bounded by one single-section QuPath run.
- [x] `nyquist_compliant: true` set in frontmatter.

**Approval:** approved 2026-07-07
