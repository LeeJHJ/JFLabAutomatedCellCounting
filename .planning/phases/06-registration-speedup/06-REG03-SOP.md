# REG-03 SOP: ABBA Native "DeepSlice Registration (Local)" — wBA1-3 Series

**Status:** Scaffold (parameters pinned) — per-section run record filled by plan 06-03.
**Context:** REG-03 registers the 5 wBA1-3 sections to Allen CCFv3 using ABBA's native Fiji
command `Plugins > BIOP > Atlas > Multi Image To Atlas > Align > ABBA - DeepSlice Registration
(Local)` (`RegisterSlicesDeepSliceLocalCommand`, confirmed present in the installed
`ImageToAtlasRegister-0.11.1.jar`). This is **NOT** a standalone `scripts/run_deepslice.py` —
06-CONTEXT.md's ⟳ RESOLUTION explicitly supersedes that earlier plan: the operator chose the
native command over authoring a script because it runs the identical offline `predict()` +
`propagate_angles()` DeepSlice API in one Fiji action, with zero proxy-image prep or
name-matching hazard. D-01's "scriptable/reproducible" goal is met by this committed,
parameter-pinned SOP record instead.

**Data:** `Automated Cell Counting/wBA Sungmo/wBA1-3_s1_MIP.ome.tiff` … `wBA1-3_s5_MIP.ome.tiff`
(0.69 µm/px, 3 channels `AF568-T2` / `AF488-T3` / `DAPI-T4`, **DAPI = channel index 2**). Do
**NOT** use the 32 GB `..._Merged.ome.tiff` (scenes fused into one canvas, Z not projected —
unusable for registration).

---

## Numbered Procedure

1. **One-time setup:** `Edit > Configuration > Set DeepSlice Env Path` →
   `/home/jflab/miniforge3/envs/deepslice`. Confirm once per Fiji install; skip if already set.

2. **Load the 5 MIPs** into ABBA's "Multi Image To Atlas" window as full-resolution slices.
   Filenames already contain `_s1`..`_s5` — no renaming needed.

3. **Before running DeepSlice**, set a **PERCENTILE-based Brightness & Contrast** (auto-contrast)
   on the DAPI channel (index 2) for each loaded slice. This avoids ABBA's documented failure
   mode: "almost 50% of images sent by ABBA users to DeepSlice are over-saturated" — a naive
   linear min/max rescale of raw 16-bit DAPI crushes tissue into a narrow band and degrades
   DeepSlice's AP/angle predictions (RESEARCH Pitfall 2).

4. **Select all 5 slices**, then run:
   `Plugins > BIOP > Atlas > Multi Image To Atlas > Align > ABBA - DeepSlice Registration (Local)`
   with these parameters **pinned verbatim** (dialog field values as a single string for quick
   copy-paste reference: `channels=2 model=mouse section_numbers=true
   post_processing=KEEP_ORDER_SET_SPACING propagate_angles=true ensemble=true`):

   | Parameter | Value | Why |
   |---|---|---|
   | `channels` | `2` | DAPI channel index. **NOT `0`** — index 0 throws ABBA's `"Missing channel in selected slice(s)"` error on these AF568-T2/AF488-T3/DAPI-T4 MIPs (RESEARCH Pitfall 3, [[feedback-abba-channel-index]]: channel index is per-dataset, this dataset's DAPI is index 2, do not carry over a single-channel-image `index 0` habit). |
   | `model` | `mouse` | Species. |
   | `section_numbers` | `true` | Parses trailing `_s\d+` from filename for ordering — the existing `wBA1-3_s1..s5` names already satisfy this regex, zero renaming required. |
   | `post_processing` | `KEEP_ORDER_SET_SPACING` | Plus the operator's known section spacing (**D-02** — record the spacing value used below; this is how the operator's known physical section order/spacing constrains AP fit and anchors angle-propagation to real geometry, resolving the AP-ordering Phase 5 deliberately deferred). |
   | `propagate_angles` | `true` | Produces the candidate shared DV/ML angle feeding the **D-04** compare-angle step below. |
   | `ensemble` | `true` | DeepSlice's own mouse default is already `True`; CPU-acceptable for only 5 sections. |
   | "Allow change of atlas slicing angle" | **UNCHECKED initially** | Per **D-04** — do not adopt the propagated angle unseen; compare it against a manual Review-Mode angle first (step 5). |

5. **D-04 belt-and-suspenders angle check.** Note the propagated candidate DV/ML angle from step
   4. Independently find a good DV/ML tilt manually in ABBA Review Mode on one well-fitting
   section. Compare both overlays (propagated vs. manual) against tissue anatomy and **ADOPT
   WHICHEVER FITS BETTER**. This is not blind trust of DeepSlice — see [[feedback-abba-tilt]]
   ("I've run into some trouble previously with fully trusting DeepSlice's DV/ML estimates").
   Record which source won in the run record below.

6. **D-05 outlier rule.** Apply the adopted shared angle (whichever won step 5) to all 5
   sections as the default. Permit a **documented per-section DV/ML override** in Review Mode
   for any section that fits poorly (fold, tissue damage, oblique cut) — a single section can
   genuinely be cut differently from the rest of the series. Record which sections deviated and
   why in the run record below.

7. **Confirm the atlas overlay tracks tissue** on each of the 5 sections before export (operator
   visual QC — no ground-truth registration metric exists for this pipeline, per established
   doctrine [[feedback-abba-tilt]]).

---

## Per-section run record (filled in plan 06-03)

| section | DeepSlice AP (mm) | shared angle source (propagated / manual) | per-section override? | overlay fit OK? | notes |
|---|---|---|---|---|---|
| wBA1-3_s1 |  |  |  |  |  |
| wBA1-3_s2 |  |  |  |  |  |
| wBA1-3_s3 |  |  |  |  |  |
| wBA1-3_s4 |  |  |  |  |  |
| wBA1-3_s5 |  |  |  |  |  |

**Section spacing used (D-02):** `<µm value — filled by operator>`

**Decision:** `<filled in plan 06-03 — D-04 angle-source outcome: propagated or manual, and why>`

---

## Cross-references

- [[feedback-abba-tilt]] — DeepSlice → Review-Mode DV/ML tilt → BigWarp escalation doctrine; do
  not trust DeepSlice's DV/ML estimate unseen; same-animal blade angle is consistent, note and
  reuse.
- [[feedback-abba-channel-index]] — channel index is per-dataset; this dataset's DAPI is index 2,
  not 0; the "missing channel" error is an index mismatch, not a metadata problem.
