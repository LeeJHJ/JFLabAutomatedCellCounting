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

## Trial record (filled in plan 06-05)

- **Worst-fitting section (D-06):** `<section id — e.g. wBA1-3_sN>`
- **Fixed image:** Allen CCFv3 coronal plate at `<AP mm>` via `extract_atlas_plate.py`
- **Moving image:** `crop_to_tissue.py` output, DAPI channel index 2
- **Elastix parameters:** `scripts/elastix_params/Par_Affine.txt` + `Par_BSpline.txt`, masked
  both sides (`-fMask` / `-mMask`)
- **Parameter retune tried (if any):** `<description, or "none — defaults used">`
- **Operator visual comparison at LA/BA boundary + ventral edge vs. BigWarp-only:**
  `<description>`

**Decision: KEEP / REJECT** — `<one-line justification tied to the D-07 quality-only rule, time
irrelevant>`

---

## Cross-references

- [[feedback-abba-tilt]] — BigWarp is the trusted default; unmasked elastix degrades without a
  tissue mask (confirmed 2026-06-23); crop-to-tissue pilot finding (D-08 caveat above).
