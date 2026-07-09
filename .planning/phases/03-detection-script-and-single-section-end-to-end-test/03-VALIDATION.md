---
phase: 3
slug: detection-script-and-single-section-end-to-end-test
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-09
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: `03-RESEARCH.md` §Validation Architecture. This is a GUI-driven scientific
> pipeline (QuPath/Groovy) with **no automated test framework** — consistent with Phases 1–2.
> Validation is measurement-based numeric/visual QC inside QuPath, not a unit-test suite.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None — no automated suite for this GUI-driven pipeline; QC is numeric/visual inside QuPath |
| **Config file** | none |
| **Quick run command** | Manual: in QuPath, "Run for project" (or single-entry run) `02_detect_classify.groovy` on entry 1; read console output |
| **Full suite command** | Same manual run; inspect annotation-pane measurement table for CA1/CA2/CA3/DG `Count: *` columns and `data.qpdata` mtime update |
| **Estimated runtime** | ~seconds–minutes per run (CPU-only; population-scale per-cell annulus loop is the cost driver — see RESEARCH Pitfall 7) |

Cheap static/CLI checks that CAN be automated (no GUI): classifier-JSON key ↔ new
background-subtracted measurement-name match (`python3 -c` / `jq`, mirrors Phase 2's
CLASS-01 static-file check) if new classifier JSON files are authored under D-05.

---

## Sampling Rate

- **After every task commit (each script edit):** re-run `02_detect_classify.groovy` on entry 1 — D-02 makes re-classification idempotent/safe — and inspect console output.
- **After every plan wave:** full run through all 4 success criteria on entry 1.
- **Phase gate:** all 4 success criteria pass on the M3 entry before Phase 3 is done. Biological-plausibility gates (VAL-01) are Phase 4 and out of scope here.
- **Max feedback latency:** one manual QuPath run (seconds–minutes).

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. The gsd-nyquist-auditor fills concrete task rows
> post-planning. Because this phase has no automated framework, most rows resolve to the
> Manual-Only table below rather than an `<automated>` command.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | SCRI-03 | — | N/A (local single-user script) | manual | — (GUI run) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `02_detect_classify.groovy` — does not exist yet; it is this phase's entire deliverable.
- [ ] Optional cheap static check: classifier-JSON measurement key matches the new background-subtracted measurement name (only if new classifier JSONs are authored under D-05).

*No test framework to install — existing manual-QC practice from Phases 1–2 covers this phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Script runs via "Run for project" without errors, writes classified `data.qpdata` | SCRI-03 / SC1 | Requires QuPath GUI + loaded project | Run `02_detect_classify.groovy` on entry 1; confirm no red error in QuPath log/console and `data.qpdata` mtime updates |
| All 4 classes present; each cell carries an atlas region label | SCRI-03 / SC2 | GUI detection state + console printout | Read the class-breakdown printout (TdT+/Fos+/Double+/Negative counts all > 0) plus the sample region-label printout (cells carry ABBA region acronyms) |
| Printed Atlas_X values fall in [5000, 10000] µm | SCRI-03 / SC3 | Numeric console check | Read the Atlas_X sanity-print for a sample of cells; confirm values are in µm range, not mm |
| Per-region count table for CA1/CA2/CA3/DG readable in annotation pane | SCRI-03 / SC4 | GUI measurement table | Open QuPath Annotations tab / measurement table; confirm `Count: *` columns populated for the four subfields |

---

## Validation Sign-Off

- [ ] Every task has a manual test instruction or an `<automated>` static check where feasible
- [ ] Sampling continuity: no plan wave without a defined SC re-check
- [ ] Wave 0 covers the missing `02_detect_classify.groovy` deliverable
- [ ] No watch-mode flags (N/A — no framework)
- [ ] Feedback latency = one manual QuPath run
- [ ] `nyquist_compliant: true` set in frontmatter (after nyquist-auditor pass)

**Approval:** pending
