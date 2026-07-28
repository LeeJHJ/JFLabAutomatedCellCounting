# Presentation Discussion Points
## TRAP2 Section Pipeline — Peer Presentation

*Points to discuss, clarify, or decide before/during building the slide deck.*  
*Imaging parameters to be filled in from separate Claude session.*

---

## Imaging Parameters (To Fill In)
*Source: separate Claude session — paste final values here*

| Parameter | Value |
|-----------|-------|
| Objective | |
| Zoom | |
| Pixel size | 0.69 µm/px (from metadata) |
| NA | |
| Z-step | 2 µm (from metadata) |
| Z-range | 12 µm / 6 planes (from metadata) |
| Tile overlap | |
| DAPI excitation | |
| DAPI emission | |
| DAPI laser power | |
| DAPI gain | |
| AF488 (Fos) excitation | |
| AF488 emission | |
| AF488 laser power | |
| AF488 gain | |
| AF568 (TdTomato) excitation | |
| AF568 emission | |
| AF568 laser power | |
| AF568 gain | |
| Airyscan mode | |

### Changes Made for Better DAPI Signal
*Fill in from other session:*
-
-
-

---

## Open Discussion Points

### Registration
- [ ] **BigWarp landmark strategy** — how many landmarks, where to place them, reproducibility across sections? Still being refined as of 2026-06-25
- [ ] **Blade angle consistency** — do DV/ML tilt angles need re-tuning for each section, or are they stable within an animal?
- [ ] **Why elastix fails** — worth including in the presentation to warn other labs? (root cause: no tissue mask, ~40% background sampling)

### Cell Detection
- [ ] **Threshold values** — TdT > 500 (cytoplasm), Fos > 200 (nucleus) are starting points. Have these been validated on this dataset?
- [ ] **Cytoplasmic expansion radius** — 4 µm was chosen as a starting point. Does this need to be tuned per section or per animal?
- [ ] **False positive rate** — have you spot-checked the TdT+ and Fos+ calls visually? Worth mentioning in the talk

### Biology Framing (Slide 2)
- [ ] Do you want to show the TRAP2 schematic from the original paper, or make a custom one?
- [ ] What comparison groups will you eventually have? (e.g., encoding vs home cage, different stimuli?)
- [ ] Is this for a specific brain region talk (amygdala) or whole-brain?

### Scope of the Talk
- [ ] Is this a methods talk or are you also showing preliminary data?
- [ ] Who is the audience — lab members only, or wider department?
- [ ] How long is the presentation slot?

### Pipeline Status
- [ ] BigWarp is still being refined — present as "current approach" or wait until finalized?
- [ ] BraiAn and brainrender steps not yet done — present as "planned" or skip for now?

---

## Slide-Specific Notes

**Slide 9 (Tilt Correction)** — This is the most visually striking result. Make sure to have a clear before/after. Consider annotating the LA position with an arrow to make the offset obvious.

**Slide 11 (Why Not Elastix)** — This is a good "lesson learned" for other labs. Explaining the root cause (no mask, background sampling) makes it more useful than just saying "it didn't work."

**Slide 12 (Cell Detection)** — Emphasize the cytoplasmic expansion ring — this is the correctness-critical step that many labs get wrong with TRAP2.

---

## Questions to Anticipate from the Audience

- Why not use ClearMap or other automated pipelines?
- How do you validate the atlas registration accuracy?
- How many animals/sections are planned?
- What is the expected double+ percentage?
- How long does the full pipeline take per animal?
