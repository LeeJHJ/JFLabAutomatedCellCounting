---
phase: 4
slug: biological-plausibility-validation-and-imaging-optimization
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-16
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> This is a documentation/analysis phase (D-01: findings record, not a pass/fail gate).
> There is no automated unit-test suite — the "test" is each script's own printed/written
> output plus document completeness, consistent with the rest of this GUI-mediated pipeline.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | None (no automated test suite; QuPath/Groovy GUI-mediated export + Python metrics, human-attested — Phase 3 precedent) |
| **Config file** | none |
| **Quick run command** | `conda run -n braian python3 scripts/val01_metrics.py` — the Python metrics script is the fastest re-runnable check once the D-03 export TSV exists |
| **Full suite command** | Re-run the Groovy export ("Run for project" in QuPath, human-triggered) → then `conda run -n braian python3 scripts/val01_metrics.py` |
| **Estimated runtime** | ~10–30 seconds for the Python metrics pass (export TSV is small); Groovy export is human-in-the-loop |

---

## Sampling Rate

- **After every task commit:** Re-run the Python metrics script against the export TSV; diff computed numbers against the previous run if the export was regenerated
- **After every plan wave:** Confirm both `04-VALIDATION.md` and `04-IMAGING-NOTES.md` exist, are non-empty, and every VAL-01 / OPT-01..03 item has a documented finding (grep for section headers)
- **Before `/gsd-verify-work`:** All four VAL-01 metrics and all three OPT items must each carry both a value and a written interpretation (D-01: completeness gate, not a numeric pass)
- **Max feedback latency:** ~30 seconds (Python metrics re-run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-xx | 01 | 1 | (D-03 export) | — | N/A (local docs/analysis) | script output | Groovy "Run for project" writes export TSV with expected columns | ❌ W0 — export script needs authoring | ⬜ pending |
| 4-02-xx | 02 | 2 | VAL-01 | — | N/A | script output + record | `conda run -n braian python3 scripts/val01_metrics.py` writes the four metric values | ❌ W0 — metrics script needs authoring | ⬜ pending |
| 4-03-xx | 03 | 2/3 | OPT-01 | — | N/A | metadata read + record | `conda run -n braian python3 -c "import aicspylibczi; ..."` reads Z=6 / step 2.0 µm | ❌ W0 — inline snippet or folded into metrics script | ⬜ pending |
| 4-03-xx | 03 | 2/3 | OPT-02 | — | N/A | shell | `stat -c%s <file>` / `ls -la` (CZI ~9.0 GB, MIP ~0.97 GB) | ✅ trivial | ⬜ pending |
| 4-03-xx | 03 | 2/3 | OPT-03 | — | N/A | manual record (reasoned) | n/a — documentation only, grounded in NA/Nyquist + Phase-2 separability | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] D-03 Groovy export script (new file, e.g. `scripts/03_export_val01_metrics.groovy`, or a block appended per planner discretion) — does not yet exist; must read the exact measurement keys the classify script writes (`Nucleus: Area µm^2`, `Nucleus: AF488-T3 mean (bg-sub)`, `Cytoplasm: AF568-T2 mean (bg-sub)`, `getPathClass()`) plus per-region area (µm²→mm²) per D-04
- [ ] Python metrics script (new file, e.g. `scripts/val01_metrics.py`, `braian` env) — does not yet exist; implements the histogram-mode area-peak estimator (10 µm² bins, matching `qc_detection_gates.groovy` Gate 1), per-region density, and ratio/rate calculations
- [ ] No test framework install needed — this phase's "tests" are the scripts' printed output plus human/documentation review

*Existing infrastructure (the `braian` conda env: numpy/scipy/pandas/scikit-image/aicspylibczi) covers all computation; only the two scripts above are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| D-03 export runs on `data.qpdata` | VAL-01 | QuPath "Run for project" is GUI-only by project convention (needs live PathObjects + `DISPLAY=:0`) | Open the M3 QuPath project, run the export script for project, confirm a TSV appears with per-cell rows (class/region/area/centroid) and per-region area rows |
| OPT-01 plateau comparison across MIP variants | OPT-01 | Only the 3-plane variant has a confirmed classified `data.qpdata`; single-plane + hybrid may need a GUI detection run OR OPT-01 is scoped to "reasoned, not yet empirically confirmed across all three variants" | Check `data/*/summary.json` per variant project; if missing, run detection+classification (human) or document the scope-down |
| OPT-03 resolution argument | OPT-03 | Reasoned optical record; no on-disk paired Airyscan-vs-confocal acquisition exists to compare empirically | Confirm the record pairs every resolution number with "at NA=0.8" or `[inferred]`, and cites Phase-2 CA1-separable / DG-sg-not-separable finding |

---

## Validation Sign-Off

- [ ] All tasks have script-output verification, a documented finding, or a Wave 0 dependency
- [ ] Sampling continuity: every wave ends with a re-runnable metrics check or a document-completeness grep
- [ ] Wave 0 covers the two MISSING scripts (Groovy export + Python metrics)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter (set by planner once all VAL-01/OPT items map to a check or a documented rationale)

**Approval:** pending
