# ROI Counting — count cells inside shapes you draw

A self-contained module. Everything it needs is in this folder; nothing outside it has to
change to use it.

**What it is for:** you have an image and you care about *one region* — LA, a hippocampal
subfield, a cortical column. You do not want to register a whole brain to get a number out
of it. So you draw the region by hand in QuPath and count inside it.

**No ABBA. No registration. No atlas. No `BraiAn.yml`.** It does not even require the image
to be a section.

**What it is not:** a different analysis. Detection, measurement, colocalization and the
positivity cut are the whole-brain pipeline's own machinery pointed at your shapes, so a
number from here means the same thing a number from there means.

```
ROI Counting/
  README.md                     <- you are here
  scripts/
    roi_count.groovy            the one button, run inside QuPath
    cockpit_roi.py              the readout, run without QuPath
  notebooks/
    04_roi.ipynb                set both cuts BY EYE, read the results
  docs/
    manual-roi.md               the long-form runbook
```

---

## The whole thing in one page

| # | where | what | cost |
|---|---|---|---|
| 1 | shell | make a QuPath project, deploy the pipeline into it | once, 2 min |
| 2 | text editor | point `pipeline.yml` at your image's channel names | once per slide-set |
| 3 | QuPath | draw ROIs, name them | minutes |
| 4 | QuPath | run `roi_count.groovy`, adjust the dialog, press OK | minutes |
| 5 | **QuPath** | **look at the overlay** | the important one |
| 6 | notebook | set the cuts by eye if step 5 looked wrong, re-run | seconds |
| 7 | notebook | read counts, check what is poolable, export a CSV | seconds |

---

## Step 1 — make a project

Use a **separate QuPath project** for manual counting. Not an unbreakable rule, but the
reason is real: a registered project already has whole-section detections on every entry,
and re-detecting inside an ROI there would overwrite them.

1. QuPath → `File > Project > Create project` → pick an empty directory.
2. Drag your images in.
3. From the Analysis root:

```bash
conda run -n braian python scripts/sync_project.py --project "<the project dir>"
```

That copies `roi_count.groovy` into the project (QuPath can only run scripts that live
inside a project) and scaffolds a `pipeline.yml` if there is not one.

## Step 2 — tell it your channel names

This is the only editing step, and the only one that reliably bites. Open
`<project>/pipeline.yml`:

```yaml
anchor:
  name: "DAPI"
  channel: "DAPI-T4"        # must match EXACTLY what QuPath shows for this image

markers:
  - name: "Fos"
    channel: "AF488-T3"
    compartment: "nuclear"      # measured on the nucleus
  - name: "TdT"
    channel: "AF568-T2"
    compartment: "whole-cell"   # measured on nucleus + cytoplasm, area-weighted
    k_robust: 2.0               # optional per-marker override
```

Channel names differ between acquisitions. The script checks them against the image and
stops with the real channel list before doing anything slow.

**One marker or five is fine.** With one, `Double+` never appears anywhere — no empty
column, no zero row. With two or more it appears automatically.

`roi_settings.yml` writes itself on the first run. You never create it.

## Step 3 — draw

Open the image. Draw ROIs with any area tool — rectangle, polygon, brush, wand.

**Name them** in the Annotations pane. The name becomes the row name in the CSV, and
several shapes sharing a name also pool into one extra row. Unnamed shapes become
`ROI_1`, `ROI_2`, … and the name is written back onto the annotation, so what QuPath shows
and what the CSV says can never drift apart.

Selecting some annotations before running restricts counting to the selection. Selecting
nothing counts every top-level area annotation on the image.

## Step 4 — run

`Automate > Script editor` → open `scripts/roi_count.groovy` → **Run**.

A dialog appears, seeded from whatever this image used last time. It has three passes,
each answering a different question:

| pass | question | when |
|---|---|---|
| **Nucleus counting** | how many cells, and how many are marker+ | the default |
| **Independent marker detection** | how many marker objects, ignoring DAPI | dense fields, non-nuclear signal |
| **Area / intensity** | how much of the ROI does each channel occupy | DG-sg and anywhere counting is not defensible |

and a **Stage** control that decides how much gets recomputed:

| stage | cost | use when |
|---|---|---|
| `Detect + classify + export` | minutes | segmentation changed |
| `Classify + export only` | seconds | only a marker cut changed |
| `Export only` | instant | just rewriting the CSVs |

So tuning `k` never costs a detection run. Re-running is always safe — detections inside
the target ROIs are cleared and rebuilt, nothing outside them is touched.

## Step 5 — look

**This is the step that decides whether any of the numbers are worth anything.**

Toggle the detection overlay. Look at DAPI clean first, form an opinion, *then* turn
detections on — the other order anchors you to the machine's answer.

| what you see | what to change |
|---|---|
| detections in the gaps between nuclei | cut too low |
| obvious nuclei with no detection | cut too high |
| one nucleus wearing two detections | raise `sigma_um` — not the threshold |
| one detection spanning an obvious pair | lower `sigma_um` |
| cells called `TdT+` that plainly are not | raise `k for TdT`, or lower `cell_expansion_um` |

If the overlay looks wrong, it **is** wrong. No band, seed value or borrowed number
outranks it.

## Step 6 — set the cuts by eye

Two numbers decide everything, and both get a slider in `notebooks/04_roi.ipynb`:

- **§3 the anchor cut** — which pixels are nucleus
- **§4 the marker cut (`k`)** — which cells are positive

Launch it with `conda activate braian && jupyter lab` from the Analysis root.

The script offers three ways to get the anchor cut and **prints all three every run**, so
you see them disagree before committing to one:

| mode | measured on | right when |
|---|---|---|
| `image_span` | the whole image histogram | the frame is mostly tissue |
| `roi_span` | pixels inside your ROIs only | ROIs on tissue, most of the frame not |
| `absolute` | your eye | always available, often the right answer |

A cut you set while looking at the mask is **tier-1 evidence** by this project's own
hierarchy. The automatic rule is tier-3 — seeded from one operator call on one section,
never validated against hand counts, and it misfired on 5 of 16 sections in the registered
route under a *single* acquisition regime. At an unfamiliar magnification, expect worse.
**Setting it by eye per image is the primary method here, not a fallback.**

## Step 7 — read the results

```bash
conda run -n braian python "ROI Counting/scripts/cockpit_roi.py" --project "<project dir>"
```

or `notebooks/04_roi.ipynb` §5–7, which also plots it.

Files land in `<project>/results/roi/`:

| file | one row per |
|---|---|
| `<image>__percell_export.tsv` | cell |
| `<image>__roi_counts.tsv` | drawn shape, then each pooled name |
| `<image>__roi_area.tsv` | shape × channel (area pass) |
| `roi_counts_combined.csv` | image × ROI × class, with full settings provenance |
| `roi_area_combined.csv` | image × ROI × channel, same provenance |

---

## The three things worth understanding before you trust a number

### 1. Different magnifications are not automatically comparable

Settings are stored **per image** in `roi_settings.yml`, because images counted this way
vary in magnification, Z depth and intensity, and one locked parameter set cannot span
that.

Micron parameters are the right way to *write down* a setting and the wrong way to *judge*
one. Whether `sigma_um: 2.0` can separate two nuclei depends on how many **pixels** a
nucleus spans. So every run prints:

```
ACQUISITION CHECK — what these settings mean in pixels on THIS image
  a 10 um nucleus spans        21.7 px
  sigma 2.00 um                = 4.34 px
  min area 20.0 um^2           = 94 px  (>= 11.0 px across)
```

At 2.5 µm/px the same block reads `4.0 px` and flags `counting is PIXEL-LIMITED` —
touching nuclei cannot be split at any setting and the count is a lower bound.

Every count row carries a `settings_hash`. `cockpit_roi.py` groups by it and names what
differs, geometry breaks (pixel size, Z depth, channel) first. It **advises, never
blocks** — the call is yours, but a magnification difference should not get read as
biology by accident.

### 2. Independent marker detection is a weaker measurement, on purpose

Enabled by operator decision (2026-08-06), overriding this project's nucleus-anchored-only
rule. It detects each marker on its own channel with no reference to DAPI, and reports:

- `<M>_obj_count` — objects found on that marker's channel
- `Double_overlap_<A>_<B>_count` — pairs that overlap, matched **greedily one-to-one**
  (so one large blob cannot claim several partners)

These are **never** merged with the nucleus-anchored `Double+`. They live in their own
columns, and every row of the combined CSV carries `anchoring = nucleus-anchored` or
`independent-overlap` so filtering is a one-liner.

Why weaker: a blob on a marker channel is not necessarily a cell — it can be a process, a
speck, or two cells touching. And "two markers in the same place" is a different claim from
"one nucleus carrying both", systematically higher in dense fields. Use it where DAPI
genuinely cannot be segmented, or as a check on whether the anchored counts are missing a
population. Do not put the two side by side in a figure.

### 3. Area measures are for where counting is not defensible

For DG-sg and other densely packed layers, per-nucleus segmentation is not honest. The
area pass measures **occupancy** instead, with no segmentation at all: per channel, the
fraction of the ROI above cut, the positive area in mm², mean and integrated intensity,
and connected-blob counts with their size distribution.

The headline derived metric, computed by `cockpit_roi.py`:

```
<marker>+_per_<anchor>_area_mm2  =  marker+ count  /  area actually occupied by DAPI
```

That normalises a count to the tissue that could have carried it rather than to whatever
shape you happened to draw — which is what makes two hand-drawn ROIs of different size and
cellularity comparable at all. Also emitted: the pure-area analogue
`<marker>_area_per_<anchor>_area`, for fields where no count is trustworthy.

Measured on **raw** pixels by design: the cut comes from the same
`floor + frac × (bright − floor)` rule used everywhere else, and that rule's `floor` *is*
the background peak, so subtracting a background first would double-correct.

Watch the blob columns: a `blob_median_um2` equal to one pixel means the mask is speckle,
not objects. The script says so, and `area_min_blob_um2` filters the blob statistics
(never the area fraction, which is meant to stay raw).

---

## Doing a whole folder at once

`Automate > Run for project` works and shows the dialog once per image — usually what you
want, since per-image settings are the point. When settings are already decided:

```bash
~/section-pipeline/tools/QuPath/bin/QuPath script \
    -p "<project>/project.qpproj" -s \
    -a no-dialog -a stage=classify \
    "<project>/scripts/roi_count.groovy"
```

`stage=` takes `full`, `classify` or `export`; an unrecognised value aborts rather than
falling through to the expensive one.

---

## When it stops, and what it means

Every refusal names the fix.

| message | fix |
|---|---|
| `no pixel calibration` | set the pixel size (Image tab), or re-export with `PhysicalSizeX` in the OME-XML |
| `declares channel(s) absent from this image` | channel names differ per acquisition — the real list is printed |
| `NOTHING TO COUNT` | draw an area ROI |
| `image_span threshold unavailable` | histogram has no usable peak pair — try `roi_span`, or set the cut by eye. It will not silently substitute a different rule |
| `whole-cell marker … Cell-compartment measurement is missing` | `cell_expansion_um` is 0; a whole-cell marker needs the cell compartment to exist |
| `NO DETECTIONS inside the ROIs` | cut far too high, or min/max area excludes everything at this pixel size — check the acquisition block |
| `all three passes are switched off` | enable at least one of count / detect / area |

Long-form runbook with more detail: [`docs/manual-roi.md`](docs/manual-roi.md).
