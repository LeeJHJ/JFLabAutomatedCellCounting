# Phase 6: Registration Speedup - Context

**Gathered:** 2026-07-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Register the 5-section wBA1-3 series (`wBA1-3_s1..s5_MIP.ome.tiff`) to Allen CCFv3 with **materially less manual effort** than v1.0's per-section-from-scratch pass. Three requirements (locked in `.planning/REQUIREMENTS.md`):

- **REG-03** — DeepSlice batch `predict()` + angle propagation produces AP/angle for all 5 sections in one pass; operator confirms the atlas overlay fits tissue on each.
- **REG-04** — A reduced-landmark BigWarp pass across all 5 sections, hitting a documented per-section effort target below v1.0's 5–15 min manual baseline.
- **REG-05** — A masked-elastix prototype (`crop_to_tissue.py` DAPI mask → elastix Affine/Spline outside ABBA's GUI) trialed on **exactly one** section under an a-priori keep/reject rule; the decision is recorded either way.

**Human-in-the-loop.** The executor authors the scripts (`run_deepslice.py`, elastix trial harness; `crop_to_tissue.py` already exists); the **operator runs the ABBA / BigWarp / Review-Mode GUI**. This phase clarifies HOW to implement REG-03/04/05 — it does not add new capabilities.

**Established registration doctrine carried forward (NOT re-litigated here):** BigWarp is the trusted default; unmasked elastix Affine/Spline stays excluded (degrades without a tissue mask); the normal path is DeepSlice → Review-Mode manual angle → export. See [[feedback-abba-tilt]].

</domain>

<decisions>
## Implementation Decisions

### DeepSlice run mode (REG-03)
- **D-01:** Run DeepSlice via a **local `deepslice`-conda-env script** (`scripts/run_deepslice.py`, does not exist yet — executor creates it), using the offline DeepSlice Python API (`predict()` + `propagate_angles()`). This is a **deliberate override** of CLAUDE.md's general "prefer DeepSlice online" guidance — rationale: the operator wants a **reproducible, offline, scriptable** batch run over all 5 sections, not a browser round-trip. CPU-bound is acceptable for 5 sections. **[MECHANISM UPDATED 2026-07-19 post-research — see ⟳ RESOLUTION below: `run_deepslice.py` is NOT authored for REG-03; ABBA's native "DeepSlice Registration (Local)" command is used instead.]**
- **D-02:** The **operator supplies the known physical section order** (section numbers + approximate spacing) to DeepSlice so AP fit is constrained and angle-propagation is anchored to real geometry. This resolves the AP-ordering that Phase 5 deliberately deferred (05-CONTEXT D-03: raw scene index preserved, no AP claim at conversion time). AP order is established HERE.
- **D-03 [informational]:** **SUPERSEDED by the ⟳ RESOLUTION below** — the native ABBA "DeepSlice Registration (Local)" command replaces this mechanism, so no plan implements the run_deepslice.py QuickNII-import path. _(Original decision, retained for history:)_ DeepSlice results reach ABBA via an **importable alignment file** — `run_deepslice.py` writes a QuickNII/JSON alignment output; the operator uses ABBA's "Import DeepSlice results" to stamp AP + angle onto the 5 loaded sections in one action (propagates the batch result, avoids per-section manual entry).
  - ⚠ **Name-matching gotcha to lock:** ABBA import matches DeepSlice results to loaded slices **by image name**. The DeepSlice input images (likely downsampled proxies) MUST be named to match the ABBA slice names (`wBA1-3_s1..s5`), or the import silently fails to bind. **[SUPERSEDED — see ⟳ RESOLUTION below: ABBA's native Local command does the export→predict→apply round-trip internally, so this manual name-matching/import path no longer applies to REG-03.]**

- **⟳ RESOLUTION (2026-07-19, post-research + operator decision) — REG-03 mechanism finalized:** Research (`06-RESEARCH.md`, Open Question 1) found ABBA's already-installed Fiji extension (`ImageToAtlasRegister-0.11.1.jar`) ships a native **"DeepSlice Registration (Local)"** command (`RegisterSlicesDeepSliceLocalCommand`) that runs the *identical* offline `predict()` + `propagate_angles()` API end-to-end on the loaded full-resolution slices in one action. **The operator chose this native command over authoring `scripts/run_deepslice.py`.** It satisfies D-01's real intent (offline, batch, no browser round-trip) and D-02's known-order/spacing control with materially lower risk — no proxy-image prep, no name-matching silent-failure, no `results.json` width/height hazard, no QuickNII import path.
  - **`scripts/run_deepslice.py` is NOT authored for REG-03.** D-01's "scriptable/reproducible" goal is met by a **precise, parameter-pinned operator SOP** (a committed markdown/CSV run record), not a CLI script.
  - **Command config for wBA1-3** (menu: `Plugins > BIOP > Atlas > Multi Image To Atlas > Align > ABBA - DeepSlice Registration (Local)`): `channels=2` (DAPI — **NOT 0**), `model=mouse`, `section_numbers=true` (filenames `wBA1-3_s1..s5` already satisfy DeepSlice's `_s\d+` regex — zero renaming), `post_processing=KEEP_ORDER_SET_SPACING` with the operator's known section spacing (**D-02**), `propagate_angles=true` (feeds **D-04**'s compare-against-manual step), `ensemble=true`. One-time setup: `Edit > Configuration > Set DeepSlice Env Path` → `/home/jflab/miniforge3/envs/deepslice`. Apply a **percentile-based B&C** contrast on the DAPI channel before running (avoids ABBA's documented ~50% over-saturation failure mode).
  - **Downstream decisions unchanged (D-02 / D-04 / D-05):** the native command produces the AP + candidate shared angle; the operator still compares the propagated angle vs. a manual Review-Mode angle (per D-04) and may override per-section outliers (per D-05). Downstream ABBA export is unchanged.
  - **Future-atlas note:** this choice does not constrain future non-Allen (e.g. P14) work — DeepSlice ships **adult mouse (Allen CCFv3) + rat (Waxholm) weights only** (verified in the installed `config.json`), so P14 would need ABBA **Method 3** (abba-python) + a non-DeepSlice initial alignment regardless. The atlas-agnostic REG-04 (BigWarp) and REG-05 (elastix) work is what carries forward. See [[abba-method2-deepslice-adult-only]].

### Angle propagation (REG-03)
- **D-04:** Shared-angle strategy is **belt-and-suspenders, not blind trust of DeepSlice**. Run `propagate_angles()` to derive a *candidate* single DV/ML angle (the same-animal / single-blade assumption), AND independently have the operator find a good DV/ML tilt manually on one well-fitting section in ABBA Review Mode. **Compare both overlays and adopt whichever fits better.** Rationale (operator, verbatim): "I've run into some trouble previously with fully trusting DeepSlice's DV/ML estimates." The propagated angle is a starting reference validated against real tissue, never adopted unseen.
- **D-05:** **Outlier rule** — the shared angle (whichever won D-04) is the default for all 5, but a **documented per-section DV/ML tilt override** is permitted in Review Mode for any section that fits poorly (folding, tissue damage, oblique cut). Record which sections deviated and why. Biology-honest: a single section can genuinely be cut differently.

### Masked-elastix prototype (REG-05)
- **D-06:** Trial the masked-elastix prototype on the **worst-fitting section** — the one whose DeepSlice+angle+BigWarp overlay fits worst at the LA/BA boundary. Tests elastix precisely where an extra nonlinear step could earn its keep (strongest case for adoption). Scoped to this ONE section so it cannot balloon.
- **D-07 [A-PRIORI KEEP/REJECT RULE — locked now, applied after the trial]:** Keep elastix **only if the operator judges its LA/BA + ventral-edge atlas-tissue fit visibly better than DeepSlice+BigWarp on that section**. **Time is irrelevant** to the decision (quality-first: registration accuracy at the LA/BA boundary matters more than operator minutes for the amygdala engram readout). A merely-equal fit → reject (BigWarp stays default). If kept, the added time is an accepted tradeoff. **The decision is recorded either way** (a D-01-style findings record, keep or reject).
- **D-08:** `crop_to_tissue.py` (already built 2026-07-06, `braian` env) supplies the DAPI tissue mask/crop feeding the elastix trial. Pilot caveat to respect: on already-tight sections cropping trimmed only a few percent and may not by itself rescue elastix — hence trialing on the *worst-fitting* section (D-06), and quality-only acceptance (D-07).

### Claude's Discretion
- **BigWarp spec (REG-04) — user delegated to Claude. Planned defaults:**
  - **Reduced landmark set (~4)** on **amygdala-relevant features**, NOT v1.0's hippocampal CA1/CA3/DG set (those subfields aren't the ROI here): candidate anchors = LA/BA lateral boundary, external capsule, optic tract, ventral brain edge. Researcher can adjust anchors at run time.
  - **Effort target:** documented per-section wall-clock at/below the low end of v1.0's 5–15 min baseline — **target ≈ ≤5 min/section**. Effort measured as **operator wall-clock per section**, recorded so REG-04's "materially less effort" claim is evidenced, not asserted.
  - BigWarp applied **across all 5** (REG-04 wording), escalated from the DeepSlice+angle state only where residual misalignment remains.
- **DeepSlice input-image prep** — ~~channel representation (DAPI-only vs composite grayscale) and downsample factor for the DeepSlice proxy images~~ **[MOOT per ⟳ RESOLUTION — ABBA's native Local command exports its own proxy from the loaded slices internally; no separate proxy-image prep script is built. Residual operator step: set a percentile-based B&C on the DAPI channel (index 2) before running the command.]**
- **DeepSlice ensemble flag** — enabling the ensemble model (higher accuracy, slower) is fine on CPU for only 5 sections; default to on unless it's prohibitively slow.
- **Channel index for the elastix/BigWarp dialog** — these 3-channel MIPs have **DAPI at index 2** (`AF568-T2`/`AF488-T3`/`DAPI-T4`); the moving-channel index is **2 here, not 0**. Do NOT carry over the single-channel `index 0` habit. See [[feedback-abba-channel-index]].

### ⟳ GUI RECONCILIATION (2026-07-20, operator at the live ABBA dialog)

Several REG-03 values were researched from JAR bytecode / ABBA docs and proved wrong against the live
GUI. **Operator GUI observation supersedes the researched value in every conflict below.** The
corrected operative procedure is `06-REG03-SOP.md` (rewritten 2026-07-20).

- **[LOADING] "Multi Image To Atlas" is not a load target.** MIPs are imported via the ABBA window's
  `Import > Import With Bio-Formats` (or `Import QuPath Project`). RESEARCH's system diagram and the
  original SOP step 2 were wrong.
- **[DIALOG FIELDS] Real DeepSlice-Local dialog labels** (not the researched param names): `Slices
  channels, 0-based` (=2), `Allow change of atlas slicing angle` (checkbox), `Resampling pixel size`
  (=10), `Average of several models (slower)` (=ensemble, checked), `Post_processing` (dropdown),
  `Spacing (micrometer)`. There are **no** `section_numbers` or `propagate_angles` named fields.
- **[D-02 REVERSED] `Post_processing = No post-processing`, NOT `Keep order + set spacing`.** D-02
  assumed "the operator supplies the known physical section order" — **false**: `s1..s5` are scene/
  acquisition labels, not true anterior→posterior order (Phase 5 CONV-02 verified only that the
  scene↔label mapping is *consistent*). Keep-order would impose a false monotonic AP constraint and
  degrade the fit. Each slice's AP is found independently. The `Spacing` field is therefore N/A.
- **[D-04 REVERSED] Shared/propagated cutting angle rejected for this series.** "One brain → one
  cutting angle" holds only for the true blade plane; inconsistent cryostat cutting + poor free-float
  mounting break it. `Allow change of atlas slicing angle` is left **unchecked**; angle is set
  **per-section** in Review Mode (D-05 applied series-wide), with BigWarp (06-04) absorbing the
  in-plane rotation/warp mounting introduces. Diagnostic recorded in the SOP: in-plane (mounting) vs
  through-plane (asymmetric-AP = real tilt).
- **[DAPI B&C — concrete] `min 0 / max ≈ 20 000`.** DAPI is 16-bit but tops out at ~33 000
  (median ~1 800–2 300, p99 ~19–21 k, consistent across all 5). ABBA's auto `0:255` clips →
  over-saturated; `0:65000` leaves it dark. Set in the "Slices Display" table's `Ch_2` header, not in
  the DeepSlice dialog.
- **[ATLAS FIXED CHANNEL] Use Ch 0 (Nissl), never Ch 2 (Label Borders), for elastix/manual matching.**
  Atlas loads Ch0=Nissl / Ch1=Ara / Ch2=Label Borders. Nissl co-varies with DAPI; Label Borders is a
  region-outline line-drawing with no intensity correspondence — using it as the elastix fixed channel
  very likely **compounded the 2026-06-23 "elastix degrades" result** (recorded then as a mask problem
  only). `extract_atlas_plate.py` correctly uses `.reference` (the Ara average template), so the
  Wave-4 script is unaffected; this correction applies to the ABBA-GUI elastix/BigWarp/manual path and
  to [[feedback-abba-channel-index]] (whose "any valid atlas index works" claim was wrong).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase requirements & roadmap
- `.planning/ROADMAP.md` §"Phase 6: Registration Speedup" — authoritative success criteria (3 criteria: DeepSlice batch+propagation overlay fit; reduced-landmark BigWarp effort target; one-section masked-elastix under a-priori rule).
- `.planning/REQUIREMENTS.md` — REG-03 / REG-04 / REG-05 exact wording; the a-priori accept/reject language for REG-05.

### Registration doctrine (memory — treat as constraints, verify against current code)
- `~/.claude/.../memory/feedback_abba_tilt.md` [[feedback-abba-tilt]] — DeepSlice → Review-Mode DV/ML tilt → BigWarp escalation; same-animal consistent blade angle → note-and-reuse; NO Affine/Spline in the normal path; crop-to-tissue pilot finding (tight sections barely benefit).
- `~/.claude/.../memory/feedback_abba_channel_index.md` [[feedback-abba-channel-index]] — moving-channel index is per-dataset; DAPI = index **2** on these 3-channel MIPs (not 0).
- `~/.claude/.../memory/abba_registration_reuse.md` [[abba-registration-reuse]] — `01_load_abba_rois.groovy` is the path that loads ABBA ROIs into QuPath after registration/export (relevant for the downstream ROI-loading, not for cross-section reuse — each of the 5 is a distinct physical section).

### Existing scripts / assets
- `scripts/crop_to_tissue.py` — EXISTS (2026-07-06, `braian` env); DAPI-name-selected tissue crop, preserves µm calibration + channel order, has `--self-test`. Feeds the REG-05 elastix trial (D-08).
- `scripts/01_load_abba_rois.groovy` — EXISTS; loads warped atlas annotations into QuPath from the ABBA export (`AtlasTools.loadWarpedAtlasAnnotations`, atlas key `allen_mouse_10um_java`). Runs AFTER this phase's registration/export.
- `scripts/run_deepslice.py` — **DOES NOT EXIST**; executor creates it (D-01/D-02/D-03). CLAUDE.md cites `run_deepslice.py` as the DeepSlice-env naming convention.

### Data (the 5 MIPs to register)
- `Automated Cell Counting/wBA Sungmo/wBA1-3_s1_MIP.ome.tiff` … `wBA1-3_s5_MIP.ome.tiff` — the 5 identity-verified Phase-5 outputs (0.69 µm/px, 3 channels `AF568-T2`/`AF488-T3`/`DAPI-T4`). Do NOT use the 32 GB `..._Merged.ome.tiff` (scenes fused, Z not projected).

### Cross-cutting
- `CLAUDE.md` / `.claude/CLAUDE.md` — CPU-only; version pins (QuPath 0.6.0, elastix 5.2.0); elastix needs `LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib`; DeepSlice env prefix `/home/jflab/miniforge3/envs/deepslice`. NOTE: D-01 overrides the "prefer DeepSlice online" line for this phase (local script chosen deliberately).
- `.planning/phases/01-atlas-registration-and-roi-loading/01-CONTEXT.md` — v1.0 single-section registration decisions (atlas key, script deploy convention: author in `Analysis/scripts/`, hard-copy into the QuPath project's `scripts/`).
- `.planning/phases/05-.../05-CONTEXT.md` — D-03 (raw scene index, no AP claim) — AP order is resolved in THIS phase via D-02.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`scripts/crop_to_tissue.py`** — ready to drive the REG-05 masked-elastix DAPI crop; selects DAPI by name, preserves calibration/channel order, `--self-test`, `braian` env.
- **`scripts/01_load_abba_rois.groovy`** — the ROI-into-QuPath loader; unchanged mechanism (`loadWarpedAtlasAnnotations`, atlas key `allen_mouse_10um_java`), consumes this phase's ABBA export.
- **elastix 5.2.0** at `$HOME/section-pipeline/tools/elastix/bin/{elastix,transformix}` — invoked directly for REG-05 (outside ABBA's GUI); requires `LD_LIBRARY_PATH` set.

### Established Patterns
- Python script conventions: `snake_case`, `Path` objects, argparse with `type=Path`, `RawDescriptionHelpFormatter`, indented step/sub-step prints. `run_deepslice.py` should match (see `czi_mip.py`).
- Script deploy convention (from Phase 1): author in canonical `/home/jflab/Analysis/scripts/`, hard-copy into the QuPath project's `scripts/` for GUI "Run for project" access.
- Registration QC is **operator visual judgment** against tissue anatomy (atlas region boundaries fit tissue) — no ground-truth metric; consistent with feedback-abba-tilt.

### Integration Points
- Output of this phase = ABBA export per section (`ABBA-Transform-allen_mouse_10um_java.json` + `ABBA-RoiSet-allen_mouse_10um_java.zip`) landing in each section's QuPath `data/<entry>/`, consumed by `01_load_abba_rois.groovy` then Phase 8 classification.
- `run_deepslice.py` proxy-image names MUST equal ABBA slice names for "Import DeepSlice results" to bind (D-03 gotcha).
- Phase 7 (Imaging Re-Validation) may run in parallel and needs one registered section for region-scoped QC — this phase supplies it.

### Known Gotchas
- DeepSlice DV/ML angle estimates are NOT to be trusted unseen (operator history) — always validate against a manual angle (D-04).
- Moving-channel index in ABBA/elastix dialogs = **2** (DAPI) on these MIPs, not 0.
- Unmasked elastix Affine/Spline degrades without a tissue mask — only the masked (`crop_to_tissue.py`) prototype is in scope, on one section only.

</code_context>

<specifics>
## Specific Ideas

- REG-05 is a **quality-only experiment**: keep elastix iff visibly better LA/BA + ventral-edge fit than BigWarp, on the worst-fitting section, time no object (D-06/D-07). Record keep-or-reject as a findings note regardless.
- Angle handling is explicitly a **compare-two-candidates** step: `propagate_angles()` output vs a hand-set Review-Mode angle; pick the better overlay (D-04).
- BigWarp landmark set is **amygdala-relevant** (LA/BA boundary, external capsule, optic tract, ventral edge), NOT the hippocampal CA1/CA3/DG set from v1.0.

</specifics>

<deferred>
## Deferred Ideas

- None from the discussion — stayed within phase scope.

### Reviewed Todos (not folded)
- **"Phase 7 imaging QC — autofocus banding and missing cortex tissue"** (`.planning/... 2026-07-18-phase-7-imaging-qc-autofocus-banding-and-missing-cortex.md`) — matched on generic keywords (phase/tissue/operator) but is explicitly **Phase 7 (Imaging Re-Validation)** scope, not registration. Not folded; belongs to Phase 7.

</deferred>

---

*Phase: 6-Registration Speedup*
*Context gathered: 2026-07-19*
