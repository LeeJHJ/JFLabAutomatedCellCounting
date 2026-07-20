---
phase: 06-registration-speedup
plan: 01
subsystem: registration
tags: [brainglobe-atlasapi, elastix, subprocess, allen-ccfv3, python]

requires: []
provides:
  - "scripts/extract_atlas_plate.py — Allen CCFv3 coronal-plate + mask extractor with runtime-resolved AP axis (braian env, --self-test)"
  - "scripts/elastix_params/Par_Affine.txt, Par_BSpline.txt — standard elastix component set for masked 2D registration"
  - "scripts/elastix_trial_harness.py — shell=False elastix+transformix argv builder with path validation and dry-run self-test"
affects: [06-registration-speedup (plans 02-05, especially 06-05 the operator elastix trial)]

tech-stack:
  added: [brainglobe-atlasapi (already installed, first use in a project script)]
  patterns:
    - "AP axis resolved at runtime from atlas.orientation (never hardcoded) before any coronal-plate indexing"
    - "subprocess.run([...], shell=False) argv-list construction for external CLI tools, split into pure _build_*_argv helpers separate from _run's execution/env-setup"
    - "--self-test CLI flag with synthetic in-script assertions (project's only test framework), applied with a RED/GREEN TDD split via NotImplementedError stubs for tdd=true tasks"

key-files:
  created:
    - scripts/extract_atlas_plate.py
    - scripts/elastix_params/Par_Affine.txt
    - scripts/elastix_params/Par_BSpline.txt
    - scripts/elastix_trial_harness.py
  modified: []

key-decisions:
  - "AP axis resolution scans the orientation string for 'a' or 'p' rather than assuming axis 0 — direct mitigation for RESEARCH Assumption A1"
  - "elastix parameter files use only the standard elastix.dev component set (AdvancedMattesMutualInformation + AdaptiveStochasticGradientDescent + Affine/BSpline transforms) per Don't Hand-Roll guidance, with a leading comment flagging them as operator-retunable starting values (A2)"
  - "elastix_trial_harness.py authored as .py not .sh, matching the project's all-Python/Groovy script convention and reusing the --self-test idiom"

patterns-established:
  - "TDD RED/GREEN on single-file self-test scripts: helper stubs raise NotImplementedError so --self-test fails first (RED commit), then real logic is implemented so --self-test passes (GREEN commit) — reconciles the tdd=true task type with this codebase's single-file --self-test convention (no separate test files exist in this project)"

requirements-completed: [REG-05]

coverage:
  - id: D1
    description: "extract_atlas_plate.py resolves the AP axis from atlas.orientation and extracts a 2D coronal plate + mask via synthetic self-test (no atlas download)"
    requirement: "REG-05"
    verification:
      - kind: unit
        ref: "conda run -n braian python3 scripts/extract_atlas_plate.py --self-test"
        status: pass
    human_judgment: false
  - id: D2
    description: "Par_Affine.txt / Par_BSpline.txt use the standard elastix component set (no invented metric/optimizer combination)"
    requirement: "REG-05"
    verification:
      - kind: unit
        ref: "grep -c 'AdvancedMattesMutualInformation|AdaptiveStochasticGradientDescent|AffineTransform' scripts/elastix_params/Par_Affine.txt; grep -c 'BSplineTransform|FinalGridSpacingInPhysicalUnits' scripts/elastix_params/Par_BSpline.txt"
        status: pass
    human_judgment: false
  - id: D3
    description: "elastix_trial_harness.py builds shell=False argv lists for elastix (-f/-m/-fMask/-mMask, -p x2 Affine-then-BSpline, -out) and transformix (-in/-tp/-out), validates input paths before any subprocess call, and never invokes subprocess.run during --self-test"
    requirement: "REG-05"
    verification:
      - kind: unit
        ref: "conda run -n braian python3 scripts/elastix_trial_harness.py --self-test"
        status: pass
      - kind: unit
        ref: "manual dry-run with a missing --fixed path confirmed SystemExit before subprocess call"
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-20
status: complete
---

# Phase 6 Plan 1: REG-05 Scriptable Foundations Summary

**Allen CCFv3 coronal-plate/mask extractor, standard elastix Affine+BSpline parameter maps, and a shell=False elastix/transformix argv-building harness — all self-testable on synthetic data only, no atlas download and no real elastix invocation.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-07-20T15:37:36Z
- **Completed:** 2026-07-20T15:42:24Z
- **Tasks:** 3 completed
- **Files modified:** 4 created

## Accomplishments
- `scripts/extract_atlas_plate.py` resolves the AP axis dynamically from `atlas.orientation` (never hardcodes axis 0), converts an AP-mm position to a bounds-checked plate index, and extracts a 2D coronal plate + `(plate > 0)` mask — synthetic self-test passes with zero atlas download.
- `scripts/elastix_params/Par_Affine.txt` + `Par_BSpline.txt` encode the standard elastix.dev component set (same set ABBA's own internal elastix commands use), avoiding the metric/optimizer mismatch that caused the 2026-06-23 failure.
- `scripts/elastix_trial_harness.py` builds `subprocess.run([...], shell=False)` argv lists for both elastix (masked Affine→BSpline) and transformix (consuming `TransformParameters.1.txt`, the BSpline-stage output), validates all input paths exist before any subprocess call, and its `--self-test` never touches the filesystem or calls `subprocess.run`.

## Task Commits

Each task was committed atomically (Tasks 1 and 3 used TDD RED/GREEN commits):

1. **Task 1: extract_atlas_plate.py**
   - `a26f429` (test) — failing self-test, helper stubs raise `NotImplementedError`
   - `810be16` (feat) — real `_resolve_ap_axis`/`_ap_mm_to_index`/`_extract_plate` implementation, self-test green
2. **Task 2: elastix parameter files**
   - `72488a9` (feat) — `Par_Affine.txt` + `Par_BSpline.txt`, standard component set
3. **Task 3: elastix_trial_harness.py**
   - `cf47cdb` (test) — failing self-test, argv-builder stubs raise `NotImplementedError`
   - `5859ec5` (feat) — real `_build_elastix_argv`/`_build_transformix_argv`/`_validate_paths` implementation, self-test green

_TDD tasks: RED commit precedes GREEN commit in both cases, verified in git log._

## Files Created/Modified
- `scripts/extract_atlas_plate.py` — Allen CCFv3 coronal-plate + mask extractor (braian env, `--self-test`)
- `scripts/elastix_params/Par_Affine.txt` — standard elastix Affine parameter map (2D, masked)
- `scripts/elastix_params/Par_BSpline.txt` — standard elastix BSpline parameter map (2D, masked, initialized by Affine)
- `scripts/elastix_trial_harness.py` — elastix + transformix `shell=False` argv wrapper (`--dry-run`/`--self-test`)

## Decisions Made
- AP axis resolution: scan `orientation[i]` for `'a'`/`'p'` rather than assume axis 0 — directly implements RESEARCH Assumption A1's mitigation and is exercised by the self-test against both `"asr"` (AP=0) and `"srp"` (AP=2) to prove the logic is not accidentally axis-0-only.
- Elastix parameter files carry a leading comment flagging them as retunable starting values (grid spacing, iterations, spatial samples) per Assumption A2, so a future under-tuned run isn't mistaken for a genuine elastix-vs-BigWarp loss at the D-07 keep/reject gate.
- TDD gate reconciliation: this codebase's only test framework is a `--self-test` flag embedded in the same file as the implementation (no separate test files exist anywhere in the project). For the two `tdd="true"` tasks, RED was achieved by committing helper stubs that `raise NotImplementedError` (self-test fails), then GREEN by implementing the real logic in the same file (self-test passes) — this satisfies the `test(...)` → `feat(...)` gate sequence without inventing a project-inconsistent separate-test-file pattern.

## Deviations from Plan

None — plan executed exactly as written. All four artifacts exist with the exact helper/CLI-flag names specified in `<artifacts_this_phase_produces>`, and all acceptance-criteria greps pass.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required. This plan is scriptable-only; the real elastix trial itself (on the one worst-fitting section, using these tools) is operator-run in plan 06-05.

## Next Phase Readiness

All three REG-05 tooling artifacts are self-test-green and ready for the operator's single-section masked-elastix trial in plan 06-05. No blockers. Plans 06-02 through 06-05 (REG-03 SOP scaffolding, REG-04 BigWarp effort log, and the operator-driven registration/trial plans) can proceed independently — this plan had no dependencies (`wave: 1`, `depends_on: []`).

---
*Phase: 06-registration-speedup*
*Completed: 2026-07-20*

## Self-Check: PASSED

All created files and all task commit hashes verified present on disk / in `git log --oneline --all`.
