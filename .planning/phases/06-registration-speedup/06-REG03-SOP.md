# REG-03 SOP: ABBA Native "DeepSlice Registration (Local)" — wBA1-3 Series

**Status:** Reconciled with the LIVE ABBA dialog 2026-07-20 (operator at the GUI). Field labels,
loading mechanism, post-processing choice, DAPI display range, and angle strategy below reflect what
is actually on screen — they supersede the JAR-bytecode/doc-derived values in the original scaffold
and in 06-RESEARCH.md. Per-section run record filled during plan 06-03.

**Context:** REG-03 registers the 5 wBA1-3 sections to Allen CCFv3 using ABBA's native Fiji
command `Plugins > BIOP > Atlas > Multi Image To Atlas > Align > ABBA - DeepSlice Registration
(Local)` (`RegisterSlicesDeepSliceLocalCommand`). This is **NOT** a standalone
`scripts/run_deepslice.py` — 06-CONTEXT.md's ⟳ RESOLUTION supersedes that earlier plan.

**Data:** `Automated Cell Counting/wBA Sungmo/wBA1-3_s1_MIP.ome.tiff` … `wBA1-3_s5_MIP.ome.tiff`
(0.69 µm/px, **16-bit**, 3 channels `AF568-T2` (Ch_0) / `AF488-T3` (Ch_1) / `DAPI-T4` (Ch_2), so
**DAPI = channel index 2**). Do **NOT** use the 32 GB `..._Merged.ome.tiff` (scenes fused, Z not
projected — unusable). These are **5 separate sections from ONE brain** (operator-confirmed
2026-07-20), but cut/mounted with variable quality (see the Angle section).

---

## Numbered Procedure

1. **One-time setup:** `Edit > Configuration > Set DeepSlice Env Path` →
   `/home/jflab/miniforge3/envs/deepslice`. Confirm once per Fiji install; skip if already set.

2. **Load the 5 MIPs — via the ABBA window's `Import` menu.** There is **no** "load into Multi
   Image To Atlas" action (the original scaffold was wrong). Use **`Import > Import With Bio-Formats`**
   and select the 5 `wBA1-3_s{1..5}_MIP.ome.tiff` files (or `Import QuPath Project` if going through
   a QuPath project). Filenames already contain `_s1`..`_s5` — no renaming needed. The loaded slices
   populate the MultiSlice Overlay + the right-hand "Slices Display" table automatically.

3. **Set the DAPI display range BEFORE running DeepSlice** — this is the single biggest lever on fit.
   DeepSlice ingests the *rendered* DAPI at whatever display min/max is active, so a bad range =
   a bad prediction (ABBA's own "~50% of images are over-saturated" warning).
   - **Where:** right-hand **"Slices Display"** panel → the per-slice channel table
     (`Click table header to modify selected slices`). NOT inside the DeepSlice dialog.
   - **How:** select all 5 slices (click row 0, Shift-click row 4, or `Edit > Select All Slices`),
     then click the **`Ch_2` column header** to open the DAPI min/max editor.
   - **Values (measured from the actual data 2026-07-20):** DAPI is 16-bit and tops out at
     **~33 000** (not 65 535); median ~1 800–2 300, p99 ~19 000–21 000, consistent across all 5.
     Set **`min = 0`, `max ≈ 20 000`** (a 1st/99th-percentile stretch). If the section morphology
     still looks dark, push `max` down toward **~10 000–12 000** — DeepSlice keys on the section
     *shape/outline*, so over-brightening general tissue (and letting the brightest nuclei clip) is
     fine, even helpful. **Do NOT** use `0:255` (clips everything above 255 → over-saturated) or
     `0:65000` (data only reaches ~33 000 → half the range wasted, tissue dark).
   - `Ch_0`/`Ch_1` (TdTomato/Fos) display is **irrelevant** to registration — leave them.

4. **Select all 5 slices**, then run
   `Plugins > BIOP > Atlas > Multi Image To Atlas > Align > ABBA - DeepSlice Registration (Local)`
   with these **real dialog fields** (labels verbatim from the live dialog 2026-07-20):

   | Dialog field (verbatim) | Value | Why |
   |---|---|---|
   | `Mp` (MultiSlicePositioner instance) | leave default | Auto-populated. |
   | `('mouse', 'rat') Mouse or Rat ?` | `mouse` | Species. |
   | `Slices channels, 0-based, comma separated, '*' for all channels` | `2` | DAPI. **NOT `0`** — index 0 throws `"Missing channel in selected slice(s)"` on these AF568/AF488/DAPI MIPs (dialog literally says "0-based"; DAPI is index 2). See [[feedback-abba-channel-index]]. |
   | `Allow change of atlas slicing angle` | **UNCHECKED** | Checking it makes DeepSlice set the (single, global) atlas slicing angle to its *median* DV/ML estimate. Leave unchecked and set the global angle **manually** to a compromise (we distrust DeepSlice's DV/ML). NOTE: ABBA's slicing angle is **one global plane for all slices** — there is no per-section through-plane tilt (see Angle section); per-section residual is fixed with in-plane transforms + BigWarp. |
   | `Resampling pixel size (10 for mouse, 40 for rat)` | `10` | Mouse default; matches the `allen_mouse_10um` atlas. |
   | `Average of several models (slower)` | **CHECKED** | This is the "ensemble" option — CPU-acceptable for 5 sections. |
   | `Post_processing` | **`No post-processing`** | **NOT `Keep order + set spacing`.** `s1..s5` are scene/acquisition labels, NOT true anterior→posterior order (Phase 5 only verified the scene↔label mapping is *consistent*, never that it is AP-monotonic). Keep-order would force a false monotonic AP constraint and degrade the fit. `No post-processing` lets DeepSlice place each slice at its independently-predicted AP — which effectively discovers each section's true AP regardless of label. **This reverses D-02.** |
   | `Spacing (micrometer), used only when 'Keep order + set spacing' is selected` | `0.0` (N/A) | Only used with keep-order+spacing, which we are not using. |

5. **Angle strategy — ONE global slicing angle + per-section in-plane/BigWarp (corrected 2026-07-20).**
   ABBA's atlas **slicing angle is a single GLOBAL cutting plane** — changing it rotates the atlas for
   ALL slices at once (confirmed at the GUI 2026-07-20). This matches ABBA's one-brain-one-cut model;
   **there is no per-section through-plane tilt.** So "set each section's tilt in Review Mode" is wrong
   — do this instead:
   - **Set the global slicing angle ONCE** to the best compromise for the series (it IS one brain, so
     a real shared cut plane exists), prioritizing LA/BA + ventral-edge fit on the most representative
     sections. Set it manually (do not blindly adopt DeepSlice's median DV/ML).
   - **Fix each section's residual with the per-section tools that ARE per-section:** in-plane
     rotation/translation of the *individual* slice (select just that slice — mounting rotation/offset),
     then **BigWarp (Wave 3 / 06-04)** for the nonlinear residual — where LA/BA actually gets nailed.
   - **Diagnose** so you apply the right per-section fix:
     - **In-plane / mounting** (common here): section rotated/shifted on the slide but internally
       front-to-back symmetric → in-plane rotate/translate the slice; BigWarp finishes it.
     - **Through-plane / real cutting tilt**: one hemisphere/edge reads more anterior than the other
       within a section (asymmetric AP) → **cannot** be set as a per-section angle; BigWarp against the
       correct AP plate pulls the ROI into alignment (accept it is a 2D warp, not a true 3D re-cut).
   - Net: don't fight the global angle per-section — set it once, then BigWarp per section
     ([[feedback-abba-tilt]]).

6. **Atlas fixed channel — for the later elastix / manual-matching steps (NOT the DeepSlice run).**
   When ABBA matches your DAPI *against* the atlas (elastix Affine/Spline, or your eye judging the
   overlay), the atlas loads as **Ch 0 = Nissl**, **Ch 1 = Ara (average template)**, **Ch 2 = Label
   Borders**. Use **Ch 0 (Nissl)** as the fixed/target channel — it co-varies with DAPI
   (cell-body/nuclear density). **Never** use **Ch 2 (Label Borders)** as the registration target —
   it is a line-drawing of region outlines with no intensity correspondence to DAPI (this very likely
   compounded the 2026-06-23 "elastix degrades" result). Keep Label Borders *displayed* as a QC
   overlay — just not as the registration channel. (DeepSlice-Local itself takes no atlas-channel
   argument; this applies to elastix/BigWarp/manual matching.) See [[feedback-abba-channel-index]].

7. **A-priori tissue-quality exclusion.** If any single section is so badly mounted (folded, torn,
   genuinely warped beyond BigWarp) that the atlas cannot track tissue, flag it **now** for principled
   a-priori exclusion on tissue-quality grounds, documented — **not** dropped later because counts
   look off (CLAUDE.md; STATE risk register).

8. **Confirm the atlas overlay tracks tissue** on each of the 5 sections before export (operator
   visual QC — no ground-truth registration metric exists). No Affine/Spline in ABBA's GUI at this
   stage; export state is DeepSlice AP + per-section manual angle only. BigWarp is plan 06-04.

---

## Per-section run record (filled in plan 06-03)

| section | DeepSlice AP (mm) | angle: in-plane (mounting) / through-plane (tilt) | residual fix (in-plane / BigWarp) | overlay fit OK? (yes / needs-BigWarp) | notes |
|---|---|---|---|---|---|
| wBA1-3_s1 |  |  |  |  |  |
| wBA1-3_s2 |  |  |  |  |  |
| wBA1-3_s3 |  |  |  |  |  |
| wBA1-3_s4 |  |  |  |  |  |
| wBA1-3_s5 |  |  |  |  |  |

**Post_processing used:** `No post-processing` (D-02 reversed — `s1..s5` not true AP order).
**DAPI display range used:** `min 0 / max ______` (target ≈ 20 000).

**Decision (D-04):** `Shared/propagated angle REJECTED — sections inconsistently cut/mounted (cryostat
+ free-float variance); per-section manual angle adopted across the series (D-05 applied series-wide).`
_(Confirm/adjust after the pass.)_

**D-05 outliers / exclusions:** `<section id + reason, or "no outliers">`

---

## Cross-references

- [[feedback-abba-tilt]] — DeepSlice → Review-Mode DV/ML tilt → BigWarp escalation; **caveat added
  2026-07-20:** same-animal blade angle is NOT reliably consistent when cutting/mounting is
  inconsistent — treat angle per-section, lean on BigWarp for in-plane/warp.
- [[feedback-abba-channel-index]] — moving/slice channel index is per-dataset (DAPI = 2 here); **and
  the atlas FIXED channel must be Ch0 Nissl, never Ch2 Label Borders** (corrected 2026-07-20).
