# Acquisition checklist — what the M3/M5 pilots taught us

**Written 2026-08-03**, before a fresh set of brains is cut and imaged.

M3 and M5 were **proof-of-concept runs**. They validated the pipeline end to end and
produced no defensible biology — one animal per group, and a group direction that flips
depending on a normalisation choice. Their real value is this list: every item below is
a problem that cost real time on those runs, with the measured number that revealed it.

The single most important sentence in this file: **lock one acquisition regime across
every animal in a comparison, and do not change it mid-cohort.** Almost everything else
here is a consequence of that.

---

## Before the first section

### Lock these, write them down, do not vary them

| parameter | pilot values | note |
| --- | --- | --- |
| pixel size | 0.460357 (M3) vs 0.6905355 (M5) | **33% apart — made the two animals non-comparable on density and any DAPI-normalised metric.** 0.69 produced perfectly usable data and is ~2.25× fewer pixels, so faster. Either is fine; mixing is not. |
| Z-planes | 4 (M3) vs 2 (M5) | Markers are max-projected over Z, so 4 planes samples ~3× the cell volume of 2. Biases marker calls between animals. 2-plane cut imaging from ~12 h to ~3 h per brain — a real win, but only if it is used for *everything*. |
| DAPI exposure | see below | the failure that cost the most |
| laser / gain per channel | — | record them; they set the SNR, which relative thresholds do NOT absorb |
| tile overlap / shading | fixed after M3 | keep it fixed |

Relative thresholds absorb **brightness drift**. They do not absorb **geometry**
(pixel size, Z depth) or **separability** (SNR). That is why the table above matters
and why "it looked the same on screen" is not sufficient.

### DAPI exposure — both failure directions are real

- **Too bright:** M3's v1.0 acquisition clipped at 65,535. Clipping fuses touching
  nuclei and makes over-segmentation worse.
- **Too dim:** `M5a_s1` had a bright-nuclei peak of **253** where its sibling sections
  were **3,700–6,600**. It used ~0.4% of the 16-bit range. The threshold rule scaled
  correctly to that histogram, but at that signal level noise dominates, so detection
  ran at a cut of 104 and produced 5,119 cells/mm² against ~3,400 for its siblings.
  That one section then drove an apparent group effect that evaporated once it was
  excluded.

Aim for the bright-nuclei population well inside the range, not clipped and not
compressed into the bottom few percent.

---

## At the scope, per section — a 30-second check that would have saved days

**Look at the DAPI histogram and check the bright-nuclei peak is in family with the
sections you already imaged.** If one section's peak is an order of magnitude off its
siblings, re-image it now rather than discovering it in analysis a week later.

That single check would have caught `M5a_s1`.

Also check, per section:

- **autofocus held across the whole tile grid.** `M5c_s5` had one hemisphere markedly
  brighter than the other and had to be excluded — a global threshold cannot serve two
  illumination levels within one section, because the rule assumes one background
  population.
- **no gross illumination gradient** left/right or top/bottom.
- **the section is intact** where your regions of interest are.

---

## Coverage — decide before cutting, not after

The current shortlist spans **+2.9 to −7.8 mm from bregma**, essentially the whole
brain. No section holds more than a handful of these. Rough AP blocks:

| block | AP (mm) | regions |
| --- | --- | --- |
| 1 | +2.9 → +0.4 | ACA, ACB |
| 2 | +0.7 → −1.0 | BST, PVH, SSp |
| 3 | −0.4 → −2.5 | LHA, MH, LH, CA3, BLA, SSp |
| 4 | −2.4 → −3.7 | SNr, SNc, VTA |
| 5 | −2.8 → −4.8 | SCs, SCm, PERI |
| 6 | −4.4 → −5.6 | PB |
| 7 | −6.8 → −7.8 | CU (and preBötzinger, which CCFv3 does not delineate) |

**Every animal in a comparison needs sections at the same AP levels.** M3 was
hippocampal and M5 striatal/brainstem, so after quality exclusions they shared only
**two** regions — which is why the comparison could not be made regardless of how good
the data was.

**Include the control regions in every animal.** `SSp` and `MOp` are the nominated
controls. MOp was absent from M3 Hipp2 entirely, so that dataset had only one control.
Two independent controls agreeing is much stronger evidence of a stable floor than one.

Caudal blocks are hard to register — sections past the cerebellum give DeepSlice little
to work with. Image them **in known cutting order** and use ABBA's "keep order + set
spacing" so the easy sections constrain the hard ones, instead of solving each alone.

---

## Bookkeeping that saves hours later

- **Record the acquisition regime alongside every dataset.** Any reported number needs
  its pixel size, Z depth, and the `k` it was measured at.
- **One brain imaged across several sessions** must declare the same `animal:` in each
  project's `pipeline.yml`, or the rollup treats the sessions as separate animals.
  M5's three sessions did exactly that until it was caught.
- **Name files so scene numbering cannot collide.** Three CZIs each numbering scenes
  from `s1` will silently overwrite each other in one output directory — use a distinct
  `--animal-prefix` per session.
- **Write exclusions down as a RULE, before looking at any counts.** See
  `M5 072526/EXCLUSIONS.md` for the pattern: state the mechanism, not the outcome. An
  exclusion decided after seeing results is not defensible; the same decision made
  before is.

---

## What the pilots could not answer, and what would fix it

- **The technical floor differs between animals** (M3 1.46–1.48, M5 1.25–2.13 depending
  on estimator) and the group direction flips with the choice. A settled acquisition
  regime across all animals is what makes floors comparable.
- **n=1 per group.** No statistics were possible. Whatever the new cohort size is,
  aggregate to the animal level before any group comparison — never to section or cell
  level.
- **Detection over-calls in ventricles and white matter** (ventricle 1,116–5,019/mm²
  where it should be near zero). Never checked against hand counts. One session of
  ground-truth counting on a couple of crops would settle whether the absolute numbers
  can be trusted at all, and it needs no new imaging.
