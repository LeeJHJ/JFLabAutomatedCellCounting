# M5 073026 — section exclusions

**Rule, stated before any M5 counts existed.** Per `CLAUDE.md` (stats conventions):
an exclusion must be a priori and principled — the RULE is documented, not the outcome.
Nothing in this file was decided after seeing a result.

## The rules

Two independent grounds for exclusion apply, both about the INPUT and both
applied before any count existed.

### Rule 1 — gross illumination gradient

> Exclude a section whose anchor (DAPI) channel carries a **gross within-section
> illumination gradient** — one region systematically brighter than another beyond
> the normal per-tile shading the flat-field correction handles.

**Mechanism, not preference.** The anchor detection threshold is derived per section as
`floor + span_frac × (bright_peak − floor)` from that section's own histogram. That rule
assumes the section has ONE background population. A section with two very different
illumination levels produces a histogram that represents neither half: a single cut
over-detects the bright side and under-detects the dark side simultaneously. No choice
of `span_frac` fixes it, because the defect is spatial and the threshold is global.

The same applies to the marker cuts (`median + k × 1.4826 × MAD`), which are likewise
computed over the whole section.

### Rule 2 — untrusted registration

> Exclude a section whose atlas registration the operator does not trust.

Every per-region number is produced by assigning cells to atlas regions through that
transform. A poor fit does not add noise evenly — it moves counts from one named
region into a neighbouring one, which is a systematic error dressed as a regional
difference. No downstream step can detect or correct it, so the operator's judgement of
the overlay is the only gate (`CLAUDE.md` evidence hierarchy: SEEN is tier 1).

## Excluded sections

| section | date excluded | reason | evidence |
| --- | --- | --- | --- |
| `M5c_s5` | 2026-07-31, before any M5 detection was run | autofocus failure during acquisition; right hemisphere markedly brighter than left, plus a saturated patch lower-right | `mips/M5c_s5_identity.png` (anchor-plane thumbnail) — operator-observed at acquisition and confirmed on the projection |
| `M5c_s2` | 2026-07-31, before any M5 detection was run | atlas registration judged unreliable by the operator — the section-to-atlas fit was not trusted | operator visual assessment of the ABBA overlay against Label Borders |

## Included

`M5a_s1`, `M5b_s1`–`M5b_s3`, `M5c_s1`, `M5c_s3`, `M5c_s4`, `M5c_s6`. **8 sections.**

## Notes

- This is an **acquisition** defect, not a pipeline one. It is distinct from the
  per-tile shading gradient present across the whole M3 Hipp2 dataset (recorded in
  `CLAUDE.md`), which is milder, uniform across sections, and partially corrected by
  `czi_mip.py`'s flat-field step.
- If this section is ever re-acquired with working autofocus it can be re-included
  without revisiting the rule — the rule is about the image, not about this section.
