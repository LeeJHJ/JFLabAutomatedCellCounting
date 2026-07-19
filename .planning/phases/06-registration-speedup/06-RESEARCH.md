# Phase 6: Registration Speedup - Research

**Researched:** 2026-07-19
**Domain:** Atlas registration acceleration (DeepSlice batch CNN inference, ABBA/BigWarp landmark registration, elastix CLI masked registration) for a CPU-only, 5-section TRAP2 vibratome series
**Confidence:** MEDIUM-HIGH (DeepSlice Python API and elastix CLI verified directly from installed packages/binaries; ABBA-side integration verified from installed JAR bytecode + cross-checked against official ABBA docs; BigWarp effort/landmark specifics remain operator-judgment, as in prior phases)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**DeepSlice run mode (REG-03)**
- **D-01:** Run DeepSlice via a **local `deepslice`-conda-env script** (`scripts/run_deepslice.py`, does not exist yet — executor creates it), using the offline DeepSlice Python API (`predict()` + `propagate_angles()`). This is a **deliberate override** of CLAUDE.md's general "prefer DeepSlice online" guidance — rationale: the operator wants a **reproducible, offline, scriptable** batch run over all 5 sections, not a browser round-trip. CPU-bound is acceptable for 5 sections.
- **D-02:** The **operator supplies the known physical section order** (section numbers + approximate spacing) to DeepSlice so AP fit is constrained and angle-propagation is anchored to real geometry. This resolves the AP-ordering that Phase 5 deliberately deferred (05-CONTEXT D-03: raw scene index preserved, no AP claim at conversion time). AP order is established HERE.
- **D-03:** DeepSlice results reach ABBA via an **importable alignment file** — `run_deepslice.py` writes a QuickNII/JSON alignment output; the operator uses ABBA's "Import DeepSlice results" to stamp AP + angle onto the 5 loaded sections in one action (propagates the batch result, avoids per-section manual entry).
  - Name-matching gotcha to lock: ABBA import matches DeepSlice results to loaded slices **by image name**. The DeepSlice input images (likely downsampled proxies) MUST be named to match the ABBA slice names (`wBA1-3_s1..s5`), or the import silently fails to bind.
  - **Research finding this session (see Open Questions #1):** no distinct "Import DeepSlice results onto already-loaded slices" command was found as literally described; ABBA's native "DeepSlice Registration (Local)" command handles the whole export->predict->import loop in one action and may be the lower-risk mechanism. Presented as an option for the planner/operator, D-01/D-03 not overridden.

**Angle propagation (REG-03)**
- **D-04:** Shared-angle strategy is **belt-and-suspenders, not blind trust of DeepSlice**. Run `propagate_angles()` to derive a *candidate* single DV/ML angle (the same-animal / single-blade assumption), AND independently have the operator find a good DV/ML tilt manually on one well-fitting section in ABBA Review Mode. **Compare both overlays and adopt whichever fits better.** Rationale (operator, verbatim): "I've run into some trouble previously with fully trusting DeepSlice's DV/ML estimates." The propagated angle is a starting reference validated against real tissue, never adopted unseen.
- **D-05:** **Outlier rule** — the shared angle (whichever won D-04) is the default for all 5, but a **documented per-section DV/ML tilt override** is permitted in Review Mode for any section that fits poorly (folding, tissue damage, oblique cut). Record which sections deviated and why. Biology-honest: a single section can genuinely be cut differently.

**Masked-elastix prototype (REG-05)**
- **D-06:** Trial the masked-elastix prototype on the **worst-fitting section** — the one whose DeepSlice+angle+BigWarp overlay fits worst at the LA/BA boundary. Tests elastix precisely where an extra nonlinear step could earn its keep (strongest case for adoption). Scoped to this ONE section so it cannot balloon.
- **D-07 [A-PRIORI KEEP/REJECT RULE — locked now, applied after the trial]:** Keep elastix **only if the operator judges its LA/BA + ventral-edge atlas-tissue fit visibly better than DeepSlice+BigWarp on that section**. **Time is irrelevant** to the decision (quality-first: registration accuracy at the LA/BA boundary matters more than operator minutes for the amygdala engram readout). A merely-equal fit → reject (BigWarp stays default). If kept, the added time is an accepted tradeoff. **The decision is recorded either way** (a D-01-style findings record, keep or reject).
- **D-08:** `crop_to_tissue.py` (already built 2026-07-06, `braian` env) supplies the DAPI tissue mask/crop feeding the elastix trial. Pilot caveat to respect: on already-tight sections cropping trimmed only a few percent and may not by itself rescue elastix — hence trialing on the *worst-fitting* section (D-06), and quality-only acceptance (D-07).

### Claude's Discretion
- **BigWarp spec (REG-04) — user delegated to Claude. Planned defaults:**
  - **Reduced landmark set (~4)** on **amygdala-relevant features**, NOT v1.0's hippocampal CA1/CA3/DG set: candidate anchors = LA/BA lateral boundary, external capsule, optic tract, ventral brain edge. Researcher can adjust anchors at run time.
  - **Effort target:** documented per-section wall-clock at/below the low end of v1.0's 5-15 min baseline — **target ≈ ≤5 min/section**. Effort measured as **operator wall-clock per section**, recorded so REG-04's "materially less effort" claim is evidenced, not asserted.
  - BigWarp applied **across all 5** (REG-04 wording), escalated from the DeepSlice+angle state only where residual misalignment remains.
- **DeepSlice input-image prep** — channel representation (DAPI-only vs composite grayscale) and downsample factor for the DeepSlice proxy images. Pick sensible defaults; keep names matching ABBA slice names (D-03 gotcha).
- **DeepSlice ensemble flag** — enabling the ensemble model (higher accuracy, slower) is fine on CPU for only 5 sections; default to on unless it's prohibitively slow.
- **Channel index for the elastix/BigWarp dialog** — these 3-channel MIPs have **DAPI at index 2** (`AF568-T2`/`AF488-T3`/`DAPI-T4`); the moving-channel index is **2 here, not 0**. Do NOT carry over the single-channel `index 0` habit.

### Deferred Ideas (OUT OF SCOPE)
- None from the discussion — stayed within phase scope.
- Reviewed-but-not-folded todo: "Phase 7 imaging QC — autofocus banding and missing cortex tissue" — belongs to Phase 7, not this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REG-03 | DeepSlice batch `predict()` + angle propagation registers the 5-section series with materially less manual effort than per-section from scratch | Standard Stack, Architecture Patterns (Pattern 1 & 2), Common Pitfalls 1-3, Open Question 1 — verified `DSModel` API and ABBA's native "DeepSlice Registration (Local)" command as the two candidate implementation paths |
| REG-04 | A reduced-landmark BigWarp workflow with a documented per-section effort target, applied across all 5 sections | Architecture Patterns (system diagram), Validation Architecture (effort log schema), Claude's Discretion (locked defaults above) — landmark anchors and effort-logging convention specified |
| REG-05 | An experimental masked-elastix prototype trialed on one section, kept only if it demonstrably wins (a-priori accept/reject rule) | Standard Stack (elastix/transformix verified), Architecture Patterns (system diagram), Code Examples (verified CLI invocation), Don't Hand-Roll (parameter-file component standard), Assumptions Log A1/A2 |
</phase_requirements>

## Summary

This phase has three independent tracks (REG-03 DeepSlice, REG-04 BigWarp, REG-05 elastix), all downstream of the 5 identity-verified MIPs from Phase 5. The single most important finding this session: **ABBA's Fiji-side extension (`ImageToAtlasRegister-0.11.1.jar`, bundled inside the installed Fiji.app) already ships a native "DeepSlice Registration (Local)" command** that runs the *exact same* offline `DSModel.predict()` + `propagate_angles()` DeepSlice Python API the phase's `run_deepslice.py` was scoped to reimplement — as one menu action, on the already-loaded full-resolution slices, with zero manual file-naming or JSON-import steps. This is confirmed both by direct inspection of the installed jar's command classes/parameters and by ABBA's own official documentation (`abba-documentation.readthedocs.io`). It fulfills D-01's underlying goal (reproducible, offline, no browser round-trip), D-02 (post-processing "Keep order + set spacing" fields map directly onto "operator supplies known order + spacing"), and D-04 (an "Allow atlas slicing angle change" checkbox that adopts DeepSlice's *median* propagated angle, exactly the "candidate shared angle" D-04 describes comparing against a manual Review-Mode angle) largely out of the box. D-01 is a **locked decision** naming `scripts/run_deepslice.py` as something the executor authors — this research does not override that, but flags plainly that the native command is the lower-risk integration path and the standalone-script route carries a specific, non-obvious width/height/filename synchronization hazard documented below. The planner and operator should make this choice explicitly (see Open Questions).

REG-04 (BigWarp) and REG-05 (elastix) research confirms established project doctrine (see `[[feedback-abba-tilt]]`) and the elastix 5.2.0 CLI is verified working with `-f/-m/-out/-p/-fMask` flags exactly as needed for the masked single-section trial. No new packages are installed this phase — all dependencies (DeepSlice 1.2.8, brainglobe-atlasapi 2.3.1, elastix 5.2.0) are already installed and verified from prior setup.

**Primary recommendation:** For REG-03, prefer ABBA's native "DeepSlice Registration (Local)" Fiji command as the primary mechanism (channels=2 for DAPI, section_numbers=true — the existing `wBA1-3_s1..s5` filenames already satisfy DeepSlice's own `_s\d+` naming regex with zero renaming required, post_processing="Keep order + set spacing" with the operator's known spacing, ensemble=true (DeepSlice's own mouse default), propagate_angles checked). If the operator/planner insists on the literal `run_deepslice.py` standalone-script route from D-01, build it against the verified `DSModel` API below, but budget explicit handling for the results.json width/height/filename hazard documented in Common Pitfalls, and route its output through ABBA's Web-runner "paste results.json into the folder ABBA already exported to" mechanism (not the `ImportSlicesFromQuickNIICommand`, which creates new low-res slices — wrong for this pipeline).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| DeepSlice CNN inference (AP/angle prediction) | Local script/GUI (Fiji+conda, CPU) | — | Runs entirely on-machine; no client/server split in this pipeline — it's a scientific batch-processing tool, not a web app |
| Angle propagation / shared-angle decision | Fiji ABBA GUI (operator judgment) | `deepslice` conda env (candidate computation) | Final adoption is a human visual-QC decision (D-04); the env only supplies a candidate |
| BigWarp landmark placement | Fiji GUI (operator, manual) | — | Inherently interactive; no scriptable substitute exists in this pipeline |
| Masked elastix registration (REG-05) | CLI (`elastix`/`transformix` binaries, CPU) | `braian` conda env (mask prep via `crop_to_tissue.py`, atlas plate extraction via brainglobe-atlasapi) | elastix runs standalone outside any GUI per D-06/D-07 scope |
| Atlas coronal-plate extraction (elastix fixed image) | `braian` conda env (`brainglobe-atlasapi`) | — | Programmatic Allen CCFv3 volume access; no GUI needed |
| Registration QC / keep-reject judgment | Operator (visual, Fiji Review Mode / BigDataViewer) | — | No ground-truth metric exists for this pipeline (established doctrine) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| DeepSlice | 1.2.8 (already installed, `deepslice` conda env) | CNN-based AP position + DV/ML angle estimation per section | Already project-standard per CLAUDE.md; only the *run mode* (offline API vs. web) changes in this phase (D-01) |
| ABBA (`qupath-extension-abba-0.4.0` + Fiji `ImageToAtlasRegister-0.11.1.jar`) | 0.4.0 / 0.11.1 (already installed) | GUI-mediated slice registration, DeepSlice orchestration, BigWarp escalation, export to QuPath | Project's locked registration GUI; version pinned to the BIOP catalog install already done |
| elastix / transformix | 5.2.0 (already installed) | Direct CLI Affine+BSpline registration for the REG-05 masked prototype | Pinned per CLAUDE.md; ABBA requires exactly this version elsewhere in the pipeline |
| brainglobe-atlasapi | 2.3.1 (already installed, `braian` env) | Programmatic Allen CCFv3 volume/plate access for the elastix fixed image | Already a project dependency (via `brainrender`/`braian`); avoids hand-downloading atlas NIfTI files |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow (PIL) | already a DeepSlice dependency | Reading downsampled PNG proxy images (`get_image_size`) if the standalone-script route is taken | Only needed if `run_deepslice.py` is authored per D-01's literal instruction |
| tifffile / numpy | already installed (`braian` env) | Reading OME-TIFF MIPs, extracting the DAPI plane, building the DeepSlice proxy PNGs | Matches `czi_mip.py`/`crop_to_tissue.py` conventions already in the codebase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ABBA's native "DeepSlice Registration (Local)" command | Standalone `run_deepslice.py` + manual JSON hand-off | Script gives CLI reproducibility/logging outside Fiji, but reimplements bookkeeping ABBA already does correctly (see Common Pitfalls); higher implementation risk for a scientific-correctness-critical step |
| elastix CLI direct invocation (REG-05) | ABBA's internal `RegisterSlicesElastixAffineCommand`/`RegisterSlicesElastixSplineCommand` (confirmed present in the same jar, currently disabled project-wide) | D-06/D-07 explicitly scope REG-05 as "outside ABBA's GUI" — CLI keeps the trial isolated and inspectable, matching the a-priori experiment design |

**Installation:** No new installs required — DeepSlice 1.2.8, brainglobe-atlasapi 2.3.1, and elastix 5.2.0 are already present and version-verified in this environment (see Package Legitimacy Audit and Environment Availability below).

**Version verification:**
```
$ deepslice conda env: pip show DeepSlice -> Version: 1.2.8
$ braian conda env: pip show brainglobe-atlasapi -> Version: 2.3.1
$ elastix --version -> elastix version: 5.2.0
$ transformix --version -> transformix version: 5.2.0
```
All four confirmed live in this session via direct tool invocation `[VERIFIED: local environment]`.

## Package Legitimacy Audit

No new external packages are installed in this phase. All dependencies used (DeepSlice 1.2.8, brainglobe-atlasapi 2.3.1, elastix/transformix 5.2.0, Pillow/numpy/tifffile already present in `deepslice`/`braian` envs) were installed and verified during prior setup phases (see CLAUDE.md Status log, 2026-06-19/2026-06-22). This gate is not applicable this phase.

**Packages removed due to [SLOP] verdict:** none (no new packages)
**Packages flagged as suspicious [SUS]:** none (no new packages)

## Architecture Patterns

### System Architecture Diagram

```
                         Phase 5 output
                              |
              wBA1-3_s1..s5_MIP.ome.tiff (5 files, 0.69 µm/px,
              channels [AF568-T2, AF488-T3, DAPI-T4], DAPI=index 2)
                              |
                              v
   +------------------------------------------------------------+
   |  ABBA (Fiji) -- "Multi Image To Atlas" window               |
   |  1. Load each of the 5 MIPs as a full-res SliceSources       |
   |     entry (names already contain "_s1".."_s5")               |
   +------------------------------------------------------------+
                              |
                 select all 5 loaded slices
                              v
   +------------------------------------------------------------+
   |  REG-03: Plugins > BIOP > Atlas > Multi Image To Atlas >    |
   |  Align > "ABBA - DeepSlice Registration (Local)"            |
   |    - channels=2 (DAPI), section_numbers=true (uses "_sN")   |
   |    - post_processing = Keep order + set spacing (D-02)      |
   |    - propagate_angles=true, ensemble=true                    |
   |    -- internally: exports downsampled proxy -> calls         |
   |       `deepslice` conda env DSModel.predict()+               |
   |       propagate_angles() -> results.json -> applies           |
   |       Affine transform to each of the 5 full-res slices      |
   +------------------------------------------------------------+
                              |
              operator inspects overlay fit per section
              (Fiji Review Mode) -- D-04: compare propagated
              shared angle vs. a manually-found angle on the
              best-fitting section; adopt whichever fits; D-05:
              per-section override allowed for outliers
                              v
   +------------------------------------------------------------+
   |  REG-04: BigWarp -- reduced landmark set (~4) per section    |
   |  Amygdala anchors: LA/BA lateral boundary, external capsule,  |
   |  optic tract, ventral brain edge (NOT hippocampal CA1/CA3/DG) |
   |  Operator wall-clock timed per section (target <=5 min)      |
   +------------------------------------------------------------+
                              |
                 identify worst-fitting section (D-06)
                              v
   +------------------------------------------------------------+
   |  REG-05 (single section only, outside ABBA's GUI):           |
   |  crop_to_tissue.py --dapi-channel 2 -> DAPI-masked crop       |
   |       |                                                       |
   |       v                                                       |
   |  brainglobe-atlasapi (braian env): extract Allen CCFv3        |
   |  coronal plate at DeepSlice-estimated AP -> fixed image       |
   |       |                                                       |
   |       v                                                       |
   |  elastix -f <atlas_plate> -m <cropped_dapi> -fMask <mask>     |
   |  -p affine.txt -p bspline.txt -out <dir>                      |
   |       |                                                       |
   |       v                                                       |
   |  transformix -tp <result.0.txt> ... (apply to full image)     |
   |       |                                                       |
   |       v                                                       |
   |  operator visually compares LA/BA + ventral-edge fit vs       |
   |  BigWarp-only result -> keep/reject per D-07 (quality only,   |
   |  time irrelevant) -> findings recorded either way             |
   +------------------------------------------------------------+
                              |
                              v
        ABBA export: ABBA-Transform-*.json + ABBA-RoiSet-*.zip
           per section, landing in QuPath project data/<N>/
        (consumed downstream by 01_load_abba_rois.groovy,
         Phase 8 classification)
```

### Recommended Project Structure
```
scripts/
├── run_deepslice.py         # NEW (D-01) -- only if standalone-script route chosen; see Open Questions
├── crop_to_tissue.py         # EXISTS -- feeds REG-05 masked crop
├── extract_atlas_plate.py    # NEW -- brainglobe-atlasapi coronal plate extraction for REG-05 fixed image
├── elastix_trial_harness.sh  # NEW -- wraps elastix+transformix invocation for the single-section REG-05 trial
├── elastix_params/
│   ├── Par_Affine.txt        # NEW -- authored Affine parameter map
│   └── Par_BSpline.txt       # NEW -- authored BSpline parameter map
├── 01_load_abba_rois.groovy  # EXISTS -- unchanged, runs after this phase's export
└── bigwarp_effort_log.csv    # NEW -- operator-recorded per-section wall-clock (REG-04 evidence)
```

### Pattern 1: DeepSlice offline Python API (only if standalone-script route is chosen)
**What:** `DSModel(species).predict(image_directory=...)` then `.propagate_angles()` then `.save_predictions(filename)` — verified directly from the installed package source (`DeepSlice/main.py`).
**When to use:** Only if the planner/operator decides against ABBA's native Local command (see Open Questions) and wants a standalone, git-committable script per D-01's literal wording.
**Example:**
```python
# Source: verified from installed package
# /home/jflab/miniforge3/envs/deepslice/lib/python3.10/site-packages/DeepSlice/main.py
from DeepSlice import DSModel

Model = DSModel("mouse")
Model.predict(
    image_directory=str(proxy_dir),   # dir of .png/.jpg proxies named *_s{N}.png
    ensemble=True,                     # DeepSlice's own mouse default is already True
    section_numbers=True,              # parses "_s\d+" from filename -- matches wBA1-3_s{N} verbatim
)
Model.propagate_angles(method="weighted_mean")  # candidate shared DV/ML angle (D-04)
# D-02: enforce the operator-supplied known spacing before saving, if sections
# are known-adjacent at a fixed cut thickness:
Model.enforce_index_spacing(section_thickness=<known_um_thickness>)
Model.save_predictions(str(output_dir / "results"))  # writes results.json (QUINT schema) + results.csv
```
**Caveat (verified from source):** `predict()` only accepts `.jpg`/`.jpeg`/`.png` files (`neural_network.load_images_from_path`, hardcoded `valid_formats`) — OME-TIFFs cannot be fed directly; a proxy image (DAPI plane only, percentile-contrast-stretched to uint8, saved as PNG) must be generated first, reusing the exact pattern already in `czi_mip.py`'s `_save_identity_thumbnail` (1st/99.5th percentile clip -> uint8).

### Pattern 2: ABBA's native "DeepSlice Registration (Local)" command (recommended primary path)
**What:** A Fiji menu command (`Plugins > BIOP > Atlas > Multi Image To Atlas > Align > ABBA - DeepSlice Registration (Local)`, confirmed present in the installed `ImageToAtlasRegister-0.11.1.jar` as `ch.epfl.biop.atlas.aligner.command.RegisterSlicesDeepSliceLocalCommand`) that runs the identical offline API end-to-end on already-loaded, full-resolution ABBA slices in one action.
**When to use:** Primary recommendation for REG-03 (see Open Questions for the tradeoff against D-01's literal script requirement).
**Configuration (one-time):** `Edit > Configuration > Set DeepSlice Env Path` -> `/home/jflab/miniforge3/envs/deepslice` `[CITED: abba-documentation.readthedocs.io]`.
**Parameters (verified from installed jar bytecode field names, cross-checked against official docs):**
| Field | Meaning | Recommended value for wBA1-3 |
|---|---|---|
| `channels` | 0-based comma-separated slice channel(s) to export to DeepSlice | `2` (DAPI — NOT `0`, see Common Pitfalls) |
| `model` | species | `mouse` |
| `px_size_micron` | resampling resolution for the DeepSlice-facing proxy | 10 (project's atlas key is `allen_mouse_10um_java`) |
| `ensemble` | "Average of several models (slower)" | `true` — DeepSlice's own mouse default is already `True`, CPU-acceptable for 5 sections (Claude's Discretion, D-context) |
| `propagate_angles` | run DeepSlice's `propagate_angles()` for a candidate shared angle | `true` (feeds D-04's comparison) |
| `section_numbers` | parse trailing `_s\d+` from filename for ordering | `true` — `wBA1-3_s1..s5` filenames already satisfy this with zero renaming |
| `post_processing` | `KEEP_ORDER` / `KEEP_ORDER_REGULAR_SPACING` / `KEEP_ORDER_SET_SPACING` (+ `slices_spacing_micrometer`) / `NO_POST_PROCESSING` | `KEEP_ORDER_SET_SPACING` with the operator's known section spacing (D-02) |
| `allow_slicing_angle_change` ("Allow change of atlas slicing angle") | adopts DeepSlice's *median* angle across the selected slices onto the shared atlas cutting plane | Leave unchecked initially; compare against the manual Review-Mode angle per D-04 before deciding |

### Anti-Patterns to Avoid
- **Feeding OME-TIFFs directly to `DSModel.predict()`:** will silently find "no images" (only `.jpg/.jpeg/.png` are globbed) — always generate a downsampled, contrast-stretched proxy first.
- **Using ABBA's "Import QuickNII Project" command (`ImportSlicesFromQuickNIICommand`) to apply externally-computed DeepSlice results:** this command **creates new SliceSources by re-opening the image files named in the JSON via Bio-Formats** — if those files are the low-res DeepSlice proxies (not the full-res OME-TIFF MIPs), it produces duplicate, wrong-resolution slices, not a registration stamped onto the existing full-res entries. This command is for bootstrapping a *new* ABBA project from a pre-built QuickNII dataset, not for this pipeline's "already-loaded full-res slices get an AP/angle stamp" need.
- **Running the moving-channel index as `0` on this dataset:** these 3-channel MIPs have DAPI at index **2** (`AF568-T2`/`AF488-T3`/`DAPI-T4`); index `0` throws ABBA's `"Missing channel in selected slice(s)"` error `[VERIFIED: installed jar bytecode string]`, and reusing the single-channel-image habit from a different project (see `[[feedback-abba-channel-index]]`) is the documented root cause.
- **Re-enabling unmasked elastix Affine/Spline in ABBA's GUI:** out of scope this phase (`.planning/REQUIREMENTS.md` Out of Scope table) — REG-05 is a CLI-only, single-section, masked trial.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Applying a DeepSlice QuickNII anchoring vector to a QuPath/ABBA slice's pixel grid | A Python re-implementation of ABBA's `QuickNIISeries.getTransform()` affine math | ABBA's native Local/Web DeepSlice commands (they already do this transform internally, tested and maintained by BIOP) | Reimplementing this transform in Python risks a silent geometric error with no obvious symptom until region ROIs are visibly offset downstream |
| Allen CCFv3 coronal plate extraction for the elastix fixed image | Hand-downloading/parsing raw Allen NIfTI/MHD atlas files | `brainglobe-atlasapi`'s `BrainGlobeAtlas("allen_mouse_10um")` -> `.reference` volume, `.resolution`, `.orientation` (already installed, already project-standard via `brainrender`) `[VERIFIED: braian env import]` | Already the project's atlas-access library; avoids a second atlas-parsing code path with a different resolution/orientation convention than ABBA's |
| Elastix Affine/BSpline parameter files from scratch, untested | A custom transform/metric/optimizer combination invented ad hoc | Standard elastix component set (`AdvancedMattesMutualInformation` metric, `AdaptiveStochasticGradientDescent` optimizer, `AffineTransform` then `BSplineTransform`) documented at elastix.dev `[CITED: elastix.dev parameter documentation]` | This is exactly the component set ABBA's own (currently-disabled) internal elastix Affine/Spline commands use; deviating invites known elastix failure modes (metric/optimizer mismatches) this project has already hit once (2026-06-23) |

**Key insight:** Every "don't hand-roll" item above exists because ABBA/brainglobe already implement the tested version of the same operation this project needs — the risk in this phase is specifically re-deriving logic that already exists, correctly, one level down in the stack.

## Common Pitfalls

### Pitfall 1: DeepSlice results.json width/height mismatch if the standalone-script route bypasses ABBA's own export
**What goes wrong:** If `run_deepslice.py` builds its own downsampled proxy PNGs independently (rather than pointing at images ABBA itself exported), the `width`/`height` fields DeepSlice writes into `results.json` (via `get_image_size()` on the *proxy*, not the full-res OME-TIFF) describe the proxy's dimensions, not the real MIP's. QuickNII-style anchoring (`ox,oy,oz` + `ux,uy,uz` + `vx,vy,vz`) spans the *whole image* regardless of resolution, so the transform is still geometrically valid **only if** whatever consumes the JSON is told the correct real pixel dimensions of the image it's mapping the transform onto.
**Why it happens:** DeepSlice's CNN always resizes input to a fixed 299x299 square (`neural_network.load_images_from_path`, ignoring aspect ratio) — the metadata fields it separately records (`width`/`height`) are the *pre-resize* proxy dimensions, which only equal the real MIP's dimensions if the proxy was a simple, uncropped downsample of it.
**How to avoid:** Prefer ABBA's own DeepSlice-Local/Web commands, which export their own proxies and reconcile dimensions internally — this pitfall does not arise there. If the standalone-script route is used anyway, keep the proxy a simple uncropped downsample (no letterboxing/padding) of the full-res MIP, and route the resulting `results.json` through ABBA's Web-runner "paste results.json into folder" mechanism (which ABBA seeded with its own export of the *actual loaded slices*), not through `ImportSlicesFromQuickNIICommand`.
**Warning signs:** Registered atlas overlay is systematically stretched/skewed relative to tissue in a way that doesn't look like a simple angle/AP error.

### Pitfall 2: DAPI/proxy display saturation degrading DeepSlice accuracy
**What goes wrong:** ABBA's own documentation warns "Almost 50% of images sent by ABBA users to DeepSlice are over-saturated" `[CITED: installed jar bytecode string, cross-confirmed by abba-documentation.readthedocs.io]` — ABBA rescales intensities for the 8-bit RGB conversion it sends to DeepSlice based on the image's *display* min/max, not a fixed percentile.
**Why it happens:** Raw 16-bit DAPI planes have a much wider dynamic range than 8-bit; a naive linear rescale (min/max of the raw data, which may include a few hot pixels) crushes most tissue into a narrow band.
**How to avoid:** Use a percentile-based contrast stretch (1st/99.5th percentile, matching `czi_mip.py`'s existing `_save_identity_thumbnail` pattern) when building any DAPI proxy, whether for the native ABBA command (set Fiji's B&C dialog to a percentile-based auto-contrast before running) or a standalone script.
**Warning signs:** DeepSlice AP/angle predictions are wildly inconsistent between adjacent sections that look similar by eye.

### Pitfall 3: Moving-channel index reuse across datasets
**What goes wrong:** ABBA's registration dialogs (BigWarp, elastix, DeepSlice-Local/Web) all ask for a 0-based channel index. This project's 3-channel MIPs have DAPI at index 2; a different, single-channel dataset in this same project (TRACR) has DAPI at index 0.
**Why it happens:** The index is per-dataset, not a pipeline-wide constant.
**How to avoid:** Always confirm channel count/order for the *specific* dataset before setting the index; for `wBA1-3_s1..s5_MIP.ome.tiff`, index is **2** `[VERIFIED: OME-XML channel order confirmed operator sign-off, STATE.md Phase 5]`.
**Warning signs:** ABBA's `"Missing channel in selected slice(s)"` error.

### Pitfall 4: Unmasked elastix reproducing the 2026-06-23 failure
**What goes wrong:** Running elastix Affine/Spline without a tissue mask degrades registration (confirmed project history, `[[feedback-abba-tilt]]`).
**Why it happens:** elastix's similarity metric samples background/black-border pixels as if they were informative signal.
**How to avoid:** REG-05 is explicitly masked (`crop_to_tissue.py` output + `-fMask`/`-mMask` elastix flags); never run the CLI trial without the mask.
**Warning signs:** elastix log shows most sampled points landing outside the tissue bounding box; result looks warped relative to the DeepSlice+BigWarp baseline in an unphysical way.

### Pitfall 5: Crop-to-tissue may not rescue an already-tight section
**What goes wrong:** the project's own pilot (2026-07-06, documented in `[[feedback-abba-tilt]]`) found that on an already-tight section, `crop_to_tissue.py` only trims a few percent — cropping alone may not fix an elastix failure whose root cause is a genuine tissue-vs-atlas shape mismatch.
**Why it happens:** the original "black-border sampling" theory came from a downsampled 327x229 px preview, not the full-res MIP, where tissue already nearly fills the frame.
**How to avoid:** D-06/D-08 already account for this — trial elastix on the *worst-fitting* section specifically (where any real gain is most plausible), and apply the quality-only a-priori accept/reject rule (D-07) rather than assuming the crop alone guarantees improvement.
**Warning signs:** `crop_to_tissue.py`'s printed "tissue-fill fraction" is already >0.9 before cropping — expect a marginal, not dramatic, change from cropping alone.

## Code Examples

### Atlas coronal-plate extraction for the REG-05 fixed image
```python
# Source: verified from installed brainglobe-atlasapi 2.3.1 (braian conda env)
from brainglobe_atlasapi import BrainGlobeAtlas

atlas = BrainGlobeAtlas("allen_mouse_10um")   # matches ABBA's atlas key allen_mouse_10um_java
res_um = atlas.resolution                      # (z, y, x) voxel size in microns, e.g. (10, 10, 10)
volume = atlas.reference                       # 3D numpy array
# AP axis convention: confirm atlas.orientation and .shape before indexing;
# for the standard "asr"-style CCFv3 volume, AP is typically axis 0.
ap_index = round(ap_position_mm * 1000 / res_um[0])
fixed_plate = volume[ap_index, :, :]           # 2D coronal plate at the DeepSlice-estimated AP
```
**Caveat:** confirm `atlas.orientation` on the actual downloaded atlas before assuming axis order — do not hardcode axis 0 = AP without checking, since brainglobe atlas orientation strings vary by atlas source `[ASSUMED — verify atlas.orientation value empirically before use; not fetched this session to avoid a large atlas download]`.

### elastix masked Affine + BSpline invocation (REG-05)
```bash
# Source: verified from local elastix 5.2.0 --help output
export LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib:$LD_LIBRARY_PATH
$HOME/section-pipeline/tools/elastix/bin/elastix \
  -f  atlas_plate_10um.tif \
  -m  worst_section_dapi_cropped.tif \
  -fMask atlas_plate_mask.tif \
  -mMask tissue_mask_from_crop_to_tissue.tif \
  -p  Par_Affine.txt \
  -p  Par_BSpline.txt \
  -out elastix_trial_out/

# Apply the resulting transform stack to the full-resolution section:
$HOME/section-pipeline/tools/elastix/bin/transformix \
  -in  worst_section_full_res.tif \
  -tp  elastix_trial_out/TransformParameters.1.txt \
  -out elastix_trial_out/
```
`[VERIFIED: elastix --help / transformix --help output this session]` for flag names; parameter *file contents* (metric/optimizer/transform component choices) are `[CITED: elastix.dev parameter documentation]` standard components, not verified against a live registration run this session — validate on the one D-06 trial section before drawing the D-07 keep/reject conclusion.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Per-section manual DeepSlice web upload + manual AP/angle entry (v1.0, Phase 1) | Batch offline `predict()` + `propagate_angles()`, ideally via ABBA's native Local command | This phase (REG-03) | One action registers all 5 sections' initial AP/angle instead of 5 separate manual passes |
| Full hippocampal 4-6 landmark BigWarp set (v1.0) | Reduced ~4-landmark, amygdala-specific anchor set (LA/BA boundary, external capsule, optic tract, ventral edge) | This phase (REG-04, Claude's Discretion) | Landmarks re-targeted to the actual ROI (LA/BA) rather than reusing hippocampal anchors that aren't relevant here |
| No elastix trial (elastix confirmed to degrade unmasked, 2026-06-23) | One-section masked-elastix CLI trial under an a-priori keep/reject rule | This phase (REG-05) | First controlled re-test of elastix now that a tissue mask exists; scoped to avoid re-litigating the original rejection broadly |

**Deprecated/outdated:** DeepSlice web upload as the *sole* run mode for this project is superseded this phase by the offline API (D-01) — CLAUDE.md's general "prefer DeepSlice online" guidance is deliberately overridden for Phase 6 only.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `brainglobe_atlasapi`'s `allen_mouse_10um` atlas has AP as axis 0 of `.reference` | Code Examples | Wrong axis indexing silently extracts a sagittal or horizontal plate instead of coronal — would be visually obvious immediately (plate shape wrong), low residual risk but must be checked before scripting the extraction |
| A2 | elastix Affine+BSpline parameter file component choices (AdvancedMattesMutualInformation, AdaptiveStochasticGradientDescent, standard resolution pyramid) are adequate defaults for this trial without further tuning | Code Examples, Don't Hand-Roll | If defaults underperform, the D-07 "merely-equal fit -> reject" outcome could reflect an under-tuned elastix run rather than a genuine elastix-vs-BigWarp comparison; mitigate by giving the operator freedom to retune registration parameters (not just accept/reject the first attempt) before finalizing the D-07 decision |
| A3 | ABBA's "DeepSlice Registration (Local)" internal export/import round-trip correctly reconciles the DeepSlice 25µm-atlas-space anchoring output with ABBA's own 10µm `allen_mouse_10um_java` atlas key without manual rescaling | Summary, Pattern 2 | If this reconciliation is imperfect, the registered overlay would show a a systematic scale offset immediately visible in Review Mode — low residual risk given this is a heavily-used, documented BIOP feature, but not independently verified by re-deriving the math this session |

**If this table is empty:** N/A — see above.

## Open Questions

1. **Standalone `run_deepslice.py` (D-01 literal wording) vs. ABBA's native "DeepSlice Registration (Local)" command**
   - What we know: ABBA's native command runs the identical offline DeepSlice API, requires zero custom naming/import logic, and satisfies D-01/D-02/D-04's functional intent (offline, batch, order/spacing control, propagate-angles candidate) directly through its own dialog fields. This was not known to be available when D-01 was decided (CONTEXT.md's rationale focuses on avoiding the *web* round-trip, not on GUI-vs-script per se).
   - What's unclear: whether the operator's underlying goal — "reproducible, scriptable" — specifically requires a git-committable CLI script (for logging/reproducibility/automation reasons beyond just "not a browser"), in which case the native command's GUI-only nature would not satisfy the intent even though it is equally offline.
   - Recommendation: surface this explicitly to the operator before planning locks in an implementation. If CLI reproducibility is the true priority, build `run_deepslice.py` per the API in Pattern 1, but route its output through ABBA's Web-runner "paste results.json" mechanism (Pitfall 1) rather than a from-scratch JSON-import path, to avoid the width/height/filename hazard. If offline-ness (not GUI-vs-CLI) was the real priority, use the native Local command and skip authoring a new script entirely for REG-03.

2. **Exact axis convention of `brainglobe_atlasapi`'s `allen_mouse_10um` volume**
   - What we know: `.reference`, `.resolution`, `.orientation`, `.shape` are all confirmed-present attributes on the installed `BrainGlobeAtlas` class.
   - What's unclear: the precise axis order (AP/DV/ML mapping to array axes 0/1/2) was not verified this session (would have required downloading the ~1GB atlas, out of scope for a dry research pass).
   - Recommendation: the executor should print `atlas.orientation` and `atlas.shape` and sanity-check one extracted plate visually against the DeepSlice-estimated AP before scripting the full REG-05 harness.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| DeepSlice (Python pkg) | REG-03 | ✓ | 1.2.8 | — |
| `deepslice` conda env | REG-03 | ✓ | Python 3.10 | — |
| ABBA (Fiji `ImageToAtlasRegister-0.11.1.jar` + QuPath extension 0.4.0) | REG-03, REG-04 | ✓ | 0.11.1 / 0.4.0 | — |
| elastix / transformix CLI | REG-05 | ✓ | 5.2.0 | — |
| brainglobe-atlasapi | REG-05 (fixed-image extraction) | ✓ | 2.3.1 | — |
| Fiji.app (`fiji-linux-x64`) | REG-03, REG-04 | ✓ | present | — |
| QuPath | downstream (post-registration) | ✓ | v0.6.0 | — |
| Real X display (`DISPLAY=:0`) | REG-03/04 GUI steps | ✓ | — | — |
| Internet access (for Allen CCFv3 atlas download if not already cached) | REG-05 atlas plate extraction | not verified this session | — | if `allen_mouse_10um` is not yet cached locally, brainglobe-atlasapi will attempt a ~1GB download on first use — confirm cache presence before the operator's REG-05 session to avoid a mid-trial download delay |

**Missing dependencies with no fallback:** none identified.
**Missing dependencies with fallback:** Allen CCFv3 atlas cache — if absent, brainglobe-atlasapi downloads it automatically on first `BrainGlobeAtlas("allen_mouse_10um")` call; no action needed beyond expecting a one-time delay.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | none (project convention: a `--self-test` CLI flag with synthetic in-script assertions, as in `scripts/crop_to_tissue.py`) |
| Config file | none |
| Quick run command | `conda run -n braian python3 <new_script>.py --self-test` |
| Full suite command | same (no aggregate test runner exists in this project) |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REG-03 | DeepSlice batch predict+propagate produces AP/angle for all 5 sections | manual-only (operator visual overlay-fit confirmation per section) | n/a — no automated ground truth for registration fit | — |
| REG-03 | Any new proxy-generation script (if D-01's standalone route is taken) correctly extracts/contrast-stretches the DAPI plane and names outputs `*_s{N}.png` | unit (synthetic) | `conda run -n braian python3 scripts/run_deepslice_proxy.py --self-test` | ❌ Wave 0 (script does not exist yet) |
| REG-04 | Reduced-landmark BigWarp hits a documented per-section effort target | manual-only (operator wall-clock log) | n/a — effort is recorded, not asserted by a test | — |
| REG-05 | elastix trial harness correctly invokes `-f/-m/-fMask/-p/-out` with the right files for the one worst-fitting section | unit (dry-run / argument-construction self-test, not a real registration run) | `bash scripts/elastix_trial_harness.sh --self-test` (or equivalent python self-test) | ❌ Wave 0 (harness does not exist yet) |
| REG-05 | Atlas plate extraction returns a 2D plate of expected shape/dtype at a given AP | unit (synthetic, using a small dummy volume, no real atlas download) | `conda run -n braian python3 scripts/extract_atlas_plate.py --self-test` | ❌ Wave 0 (script does not exist yet) |

### Sampling Rate
- **Per task commit:** run each new script's `--self-test` flag.
- **Per wave merge:** re-run all `--self-test` flags for scripts touched in the wave.
- **Phase gate:** all three success criteria are ultimately operator visual/manual sign-offs (registration fit, effort log, keep/reject decision) — no automated full-suite gate exists for the registration outcome itself, only for the scripts' internal correctness (file I/O, argument construction, naming conventions).

### Wave 0 Gaps
- [ ] `scripts/run_deepslice.py` (or a proxy-generation helper, depending on which Open Question 1 path the planner chooses) — needs a `--self-test` covering DAPI-plane extraction, percentile contrast stretch, and `_s{N}` filename construction.
- [ ] `scripts/extract_atlas_plate.py` — needs a `--self-test` using a small synthetic 3D array (not the real Allen atlas) to verify plate indexing math.
- [ ] `scripts/elastix_trial_harness.sh` (or `.py`) — needs a `--self-test`/dry-run mode verifying the constructed elastix/transformix command lines, without actually invoking elastix on real data.
- [ ] `bigwarp_effort_log.csv` template — no code gap, just a file convention the operator fills in; the plan should specify its exact column schema (section, start_time, end_time, landmark_count, notes) so REG-04's "documented effort target" claim has a concrete artifact.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | local, offline, single-operator scientific pipeline — no auth surface |
| V3 Session Management | no | no sessions |
| V4 Access Control | no | no multi-user access model |
| V5 Input Validation | yes (narrow) | file-path arguments in new scripts (`run_deepslice.py`, `extract_atlas_plate.py`, elastix harness) should validate that input paths exist and are the expected file type before invoking subprocess/CLI tools, matching the existing `crop_to_tissue.py`/`czi_mip.py` argparse + explicit error pattern |
| V6 Cryptography | no | no cryptographic operations in this phase |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Shell-injection via unsanitized filenames passed to `elastix`/`transformix` subprocess calls | Tampering | Use `subprocess.run([...], shell=False)` with an argument list (never a shell string), matching how existing scripts in this codebase invoke external tools |
| Silent misregistration presented as correct (a data-integrity concern more than a security one, but high-impact here) | Tampering (data integrity) | Operator visual QC at every stage (already established doctrine); D-07's a-priori keep/reject rule prevents a "looks fine" post-hoc rationalization |

## Sources

### Primary (HIGH confidence)
- Direct inspection of installed `DeepSlice` 1.2.8 package source (`main.py`, `neural_network/neural_network.py`, `coord_post_processing/spacing_and_indexing.py`, `coord_post_processing/angle_methods.py`, `read_and_write/QuickNII_functions.py`) — `$HOME/miniforge3/envs/deepslice/lib/python3.10/site-packages/DeepSlice/`
- Direct inspection of installed ABBA jars: `qupath-extension-abba-0.4.0.jar` and `ImageToAtlasRegister-0.11.1.jar` (class list + string constants) — `$HOME/section-pipeline/tools/`
- `elastix --help` / `transformix --help` output, elastix 5.2.0, this session
- Existing project scripts read as pattern references: `scripts/crop_to_tissue.py`, `scripts/01_load_abba_rois.groovy`, `czi_mip.py`

### Secondary (MEDIUM confidence)
- [ABBA DeepSlice registration tutorial](https://abba-documentation.readthedocs.io/en/latest/tutorial/2_registration.html) — confirms menu paths, parameter semantics, saturation warning, single-animal-angle caveat, cross-checked against jar bytecode
- [ABBA installation docs](https://abba-documentation.readthedocs.io/en/latest/installation/installation.html) — DeepSlice local conda env setup
- [elastix parameter documentation](https://elastix.dev/doxygen/parameter.html) and [elastix transform parameters](https://elastix.dev/doxygen/transformparameter.html) — standard Affine/BSpline component conventions

### Tertiary (LOW confidence)
- Axis-order assumption for `brainglobe_atlasapi`'s `allen_mouse_10um` volume (A1 in Assumptions Log) — not independently verified this session; flagged for operator/executor check before use

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all four core dependencies version-confirmed live this session
- Architecture (DeepSlice/ABBA integration): MEDIUM-HIGH — native command's existence/parameters verified from installed bytecode AND cross-confirmed by official docs; some internal reconciliation details (atlas-resolution handling) not independently re-derived
- Pitfalls: MEDIUM-HIGH — width/height/filename hazard and saturation warning both grounded in source/doc evidence, not hypothetical
- elastix parameter file contents: MEDIUM — CLI flags verified live; parameter *component* choices are standard/documented but not validated against a live registration run this session

**Research date:** 2026-07-19
**Valid until:** 30 days (stable, pinned toolchain; re-verify if QuPath/elastix/ABBA versions change)
