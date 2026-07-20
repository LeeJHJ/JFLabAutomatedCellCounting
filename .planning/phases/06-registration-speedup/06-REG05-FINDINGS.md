# REG-05 Findings: Masked-Elastix Keep/Reject Decision

**Status:** Scaffold (a-priori rule locked) — trial record filled by plan 06-05.

## A-priori keep/reject rule (locked now, BEFORE the trial — D-06/D-07)

Trial the masked-elastix prototype on the **worst-fitting section** (D-06) — the one whose
DeepSlice+angle+BigWarp overlay fits worst at the LA/BA boundary. This tests elastix precisely
where an extra nonlinear step could earn its keep, and is scoped to exactly one section so it
cannot balloon.

**KEEP elastix ONLY IF** the operator judges its LA/BA + ventral-edge atlas-tissue fit **VISIBLY
BETTER** than DeepSlice+BigWarp on that section (D-07). **Time is IRRELEVANT to the decision**
(quality-first: registration accuracy at the LA/BA boundary matters more than operator minutes
for the amygdala engram readout — if kept, the added time is an accepted tradeoff). A
merely-equal fit → **REJECT** (BigWarp stays the trusted default, per established doctrine
[[feedback-abba-tilt]]).

**The decision is recorded EITHER WAY** below — this is not a pass/fail gate that can be silently
skipped; a REJECT is as valid an outcome as a KEEP.

**D-08 caveat to respect:** on already-tight sections `crop_to_tissue.py`'s crop trims only a few
percent (2026-07-06 pilot finding, [[feedback-abba-tilt]]) and may not by itself rescue elastix —
a REJECT outcome may reflect a genuine tissue-vs-atlas shape mismatch that only BigWarp landmarks
resolve, not a flaw in the masking approach itself.

**Under-tuning caveat (RESEARCH A2):** if a first elastix run underperforms, the operator should
retune the elastix parameters (`scripts/elastix_params/Par_Affine.txt` /
`Par_BSpline.txt` — standard `AdvancedMattesMutualInformation` /
`AdaptiveStochasticGradientDescent` component set) before finalizing a REJECT, so the decision
reflects a genuine elastix-vs-BigWarp comparison rather than an under-tuned first attempt. Any
retune tried should be recorded in the trial record below.

---

## ⟳ REG-05 answered IN-GUI (2026-07-20) — the separate CLI trial was not needed

The a-priori rule above was written for a *separate out-of-ABBA masked-elastix CLI trial* on the
one worst-fitting section. In practice the operator answered REG-05's real question — **does elastix
earn its keep?** — directly **inside ABBA**, on all 5 sections, using ABBA's built-in `Elastix 2D
Affine` + `Elastix 2D Spline` with the **atlas Nissl channel (Ch0)** as fixed and section DAPI (Ch2)
as moving. Per operator decision (2026-07-20) this in-GUI result **is** the REG-05 finding; the
redundant CLI trial is skipped and the Wave-1 scripts (`extract_atlas_plate.py`,
`elastix_trial_harness.py`, `Par_Affine/BSpline.txt`) are retained as tested tools for future use.

## Trial record (in-GUI, all 5 sections)

- **Mechanism:** ABBA built-in `Elastix 2D Affine` then `Elastix 2D Spline (15 control pts)`, run
  after DeepSlice + a single global slicing angle (X=−8.6°, Y=3.9°, locked), then **BigWarp refine**
  via "Edit last registration" (nudge the 15 pts + add more).
- **Fixed image:** atlas **Nissl (Ch0)** — NOT Label Borders (Ch2). This was the decisive fix.
- **Moving image:** section DAPI (Ch2).
- **Masking:** in-GUI elastix masking status **TBC** — resolve when annotations are checked in QuPath
  (operator to confirm whether the fit was carried by the mask, the Nissl channel, or both).
- **Comparison vs. DeepSlice+BigWarp-only:** elastix Affine(Nissl)+Spline visibly improved the fit;
  it is now part of the operator's best-in-hand pipeline.

**Root cause of the 2026-06-23 "elastix degrades" failure (now understood):** substantially the
**wrong atlas fixed channel** (Label Borders Ch2 = region outlines, no DAPI-intensity correspondence),
not only the missing tissue mask. With Nissl (Ch0), in-GUI elastix Affine+Spline works. This
**overturns the locked "No Affine+Spline in ABBA" decision** (see STATE.md Key Decisions).

**Decision: KEEP** — elastix Affine(Nissl Ch0)+Spline(15pts) demonstrably improves the LA/BA-region
fit and is retained as part of the standard registration pipeline (D-07 quality-only rule; time
irrelevant). BigWarp remains the final per-section refinement on top.

---

## Cross-references

- [[feedback-abba-tilt]] — BigWarp is the trusted default; unmasked elastix degrades without a
  tissue mask (confirmed 2026-06-23); crop-to-tissue pilot finding (D-08 caveat above).
