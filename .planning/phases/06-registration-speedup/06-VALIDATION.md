---
phase: 6
slug: registration-speedup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-19
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> **Character of this phase:** registration is GUI/operator-mediated with **no ground-truth metric** — fit quality is operator visual judgment against tissue anatomy (established doctrine, `[[feedback-abba-tilt]]`). Automated tests therefore cover only the **new REG-05 helper scripts' internal correctness** (file I/O, plate-indexing math, CLI-argument construction), never the registration outcome itself. REG-03 and REG-04 are manual-only.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | none — project convention is a `--self-test` CLI flag with synthetic in-script assertions (as in `scripts/crop_to_tissue.py`) |
| **Config file** | none |
| **Quick run command** | `conda run -n braian python3 scripts/<new_script>.py --self-test` |
| **Full suite command** | same per-script (no aggregate test runner exists in this project) |
| **Estimated runtime** | ~a few seconds per `--self-test` (synthetic data only; no real atlas download, no real elastix run) |

---

## Sampling Rate

- **After every task commit:** Run the touched script's `--self-test`.
- **After every plan wave:** Re-run all `--self-test` flags for scripts created/modified in the wave.
- **Before `/gsd-verify-work`:** All script `--self-test`s green; operator visual sign-offs recorded.
- **Max feedback latency:** < 30 seconds (synthetic self-tests only).

---

## Per-Task Verification Map

> Task IDs are assigned by the planner. Rows below are keyed by requirement and finalized once PLAN.md tasks exist.

| Task (req-keyed) | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|------------------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| REG-05 atlas plate extraction | early | REG-05 | T-06-01 (path/type validation before subprocess) | Reject non-existent / wrong-type input paths before use | unit (synthetic 3D array) | `conda run -n braian python3 scripts/extract_atlas_plate.py --self-test` | ❌ W0 | ⬜ pending |
| REG-05 elastix trial harness | mid | REG-05 | T-06-01 | Build elastix/transformix argv with `shell=False`; validate file args | unit (dry-run argv construction) | `scripts/elastix_trial_harness.sh --self-test` (or `.py` equivalent) | ❌ W0 | ⬜ pending |
| REG-03 DeepSlice batch (native ABBA command) | early | REG-03 | — | N/A (GUI operator action) | manual-only | n/a — operator visual overlay-fit per section | — | ⬜ pending |
| REG-04 reduced-landmark BigWarp | mid | REG-04 | — | N/A (GUI operator action) | manual-only | n/a — operator wall-clock effort log | — | ⬜ pending |
| REG-05 keep/reject decision | late | REG-05 | — | N/A (operator judgment) | manual-only | n/a — a-priori D-07 rule, recorded either way | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/extract_atlas_plate.py` — `--self-test` using a small **synthetic** 3D array (no real Allen atlas download) verifying coronal-plate indexing math (AP index from mm + resolution; expected 2D shape/dtype).
- [ ] `scripts/elastix_trial_harness.{sh,py}` — `--self-test` / dry-run verifying the constructed `elastix -f/-m/-fMask/-mMask/-p/-out` and `transformix -in/-tp/-out` command lines **without invoking elastix on real data**.
- [ ] `scripts/bigwarp_effort_log.csv` — no code gap; a file-convention artifact. Plan must pin its column schema: `section, start_time, end_time, elapsed_min, landmark_count, notes`.

*Note: REG-03 authors **no** proxy-generation script — the native ABBA "DeepSlice Registration (Local)" command handles proxy export internally (see CONTEXT ⟳ RESOLUTION). The previously-anticipated `run_deepslice.py --self-test` row is therefore removed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DeepSlice batch overlay fits tissue on each of the 5 sections | REG-03 | No ground-truth registration metric; ABBA overlay-vs-tissue is visual | Operator inspects atlas overlay in ABBA Review Mode per section; confirms region boundaries track tissue; records pass/deviation (D-05 outlier notes) |
| Propagated shared DV/ML angle vs. manual Review-Mode angle | REG-03 (D-04) | Operator distrust of unseen DeepSlice angles; visual comparison | Compare both overlays on a well-fitting section; adopt whichever fits better; record which won |
| Reduced-landmark BigWarp hits per-section effort target (≤ ~5 min, below v1.0 5–15 min) | REG-04 | Effort is recorded operator wall-clock, not asserted by a test | Log start/end wall-clock + landmark count per section in `bigwarp_effort_log.csv`; confirm target met |
| Masked-elastix LA/BA + ventral-edge fit vs. DeepSlice+BigWarp on the worst-fitting section | REG-05 (D-06/D-07) | Quality-only, a-priori visual keep/reject; time irrelevant | Operator visually compares elastix vs. BigWarp-only fit at LA/BA boundary + ventral edge; keep only if visibly better; **record decision either way** |

---

## Validation Sign-Off

- [ ] Every REG-05 script task has an `--self-test` (or an explicit Wave 0 dependency)
- [ ] Sampling continuity: manual-only tasks (REG-03/REG-04) are documented as such, not silent gaps
- [ ] Wave 0 covers the two new REG-05 scripts + the effort-log schema
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (synthetic self-tests)
- [ ] `nyquist_compliant: true` set in frontmatter once the above hold

**Approval:** pending
