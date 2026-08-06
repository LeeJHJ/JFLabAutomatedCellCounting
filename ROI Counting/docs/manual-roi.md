# Counting cells inside ROIs you draw by hand

**Written 2026-08-05.** A parallel route to the registered whole-brain pipeline, for when
you want counts inside a shape you drew rather than inside an Allen region.

**No atlas. No ABBA. No registration. No `BraiAn.yml`.** You open an image, draw ROIs,
press Run, and get counts. It works on images that would never survive registration —
a single field of view, an off-angle section, a crop.

What it does *not* skip is the science. Detection, measurement, colocalization and the
positivity cut are the registered route's own machinery, pointed at your shapes:

| | how |
|---|---|
| segmentation | BraiAnDetect's `ChannelDetections`, aimed at your annotations instead of the atlas Root — a supported constructor, the same watershed |
| anchor threshold | `floor + span_frac × (bright − floor)`, re-measured per image from its own histogram, using BraiAn's own peak finder |
| measurement | nucleus-anchored compartments (nuclear / cytoplasmic ring / whole-cell), each local-background-subtracted in an annulus with neighbouring cells geometrically removed |
| positivity | robust self-calibrating cut, `median + k × 1.4826 × MAD`, per marker |
| colocalization | nucleus-anchored only. `Double+` = **one** nucleus positive for two markers. Never proximity, never overlap |

The marker cut is held byte-identical to `02_detect_classify.groovy` by the smoke test
(`roi_math_pinned_to_02`), so the two routes cannot drift apart unnoticed.

---

## 1. Set up a project — five minutes, once

Use a **separate QuPath project** for manual counting. Not a rule you can't break, but
the reason is real: the registered route already put its own detections on every entry
of a registered project, and re-detecting inside an ROI there would overwrite them.

1. QuPath → `File > Project > Create project` → an empty directory.
2. Drag your images in.
3. Deploy the pipeline into it:

   ```bash
   python3 scripts/sync_project.py --project "<the project dir>"
   ```

4. Open the project's `pipeline.yml` and make the channel names match **your** image.
   This is the only editing step, and it is the one that actually matters:

   ```yaml
   anchor:
     name: "DAPI"
     channel: "DAPI-T4"        # must match the channel name QuPath shows
   markers:
     - name: "Fos"
       channel: "AF488-T3"
       compartment: "nuclear"
     - name: "TdT"
       channel: "AF568-T2"
       compartment: "whole-cell"
   ```

   Channel names differ between acquisitions. `roi_count.groovy` checks them against the
   image and stops with the actual channel list before doing anything expensive.

`roi_settings.yml` writes itself on the first run. You never create it.

**One marker, or three, is fine.** With a single marker there is no `Double+` anywhere —
no empty column, no zero row. With two or more, `Double+` appears automatically.

---

## 2. Count

1. Open the image. Draw ROIs — rectangle, polygon, brush, wand, whatever fits.
2. **Name them** in the Annotations pane (`LA`, `CA1`, …). Same name on several shapes ⇒
   they also pool into one row. Unnamed shapes become `ROI_1`, `ROI_2`, … and the name is
   written back to the annotation, so what QuPath shows and what the CSV says never differ.
3. `Automate > Script editor` → open `scripts/roi_count.groovy` → **Run**.
4. Adjust the settings dialog, press OK.
5. **Look at the overlay.**

Selecting annotations first restricts counting to the selection. Selecting nothing counts
every top-level area annotation on the image.

### The Stage control is the one to learn

| stage | cost | use when |
|---|---|---|
| `Detect + classify + export` | minutes | segmentation changed |
| `Classify + export only` | seconds | only `k` or a marker cut changed |
| `Export only` | instant | just rewriting the CSVs |

Tuning marker positivity therefore never costs a detection run. Re-running is always safe:
detections inside the target ROIs are cleared and rebuilt, and nothing outside them is
touched.

### Doing a whole folder at once

`Automate > Run for project` works and will show the dialog **once per image** — usually
what you want here, since per-image settings are the point. When settings are already
decided and saved, run it headless instead and skip the prompting:

```bash
# re-cut every image's markers with its saved settings, without re-detecting
~/section-pipeline/tools/QuPath/bin/QuPath script \
    -p "<project>/project.qpproj" -s \
    -a no-dialog -a stage=classify \
    "<project>/scripts/roi_count.groovy"
```

`stage=` takes `full`, `classify` or `export`; an unrecognised value aborts rather than
falling through to the expensive one. Without `no-dialog` a headless run uses each image's
saved block anyway — the flag only matters when a GUI is present.

---

## 3. The anchor threshold, and why three modes

Which pixels count as nucleus. The script computes **all three candidates and prints them
every run**, whichever you have selected:

```
ANCHOR THRESHOLD CANDIDATES on DAPI-T4 (span_frac 0.25)
  image_span  688         floor 162, bright 2268
  roi_span    1642        floor 410, bright 5338
  absolute    not set     set it in notebooks/04_roi.ipynb
  USING image_span -> 688
  NOTE: the two automatic rules disagree by 2.4x. ...
```

| mode | what it measures | when it is right |
|---|---|---|
| `image_span` | the **whole image** histogram | the frame is mostly tissue; keeps ROI counts comparable with atlas-route counts on the same image |
| `roi_span` | only pixels **inside your ROIs** | the ROIs are on tissue and most of the frame is not — a small field on a large canvas, a section with wide empty margins |
| `absolute` | a number you set by eye | always available, and often the right answer |

A large disagreement between the first two is information, not a fault: it usually means
the ROIs sit on much brighter material than the frame average.

### Set it by eye — this is the primary method, not a fallback

By this project's evidence hierarchy a cut you choose while looking at the mask is
**tier-1 (SEEN)**. `span_frac: 0.25` is **tier-3** — seeded from one operator call on one
section, never validated against hand counts. On the registered route it misfired or
looked suspect on 5 of 16 sections (31%), and that was a *single* acquisition regime. At
an unfamiliar magnification, expect worse.

`notebooks/04_roi.ipynb` §3 gives you the slider and the mask. Put what you settle on into
the dialog's *Absolute cut* with mode `absolute`.

**The one cost, and how to control it.** A mechanical rule has no operator variance;
twenty by-eye calls do. If your eye drifts across a session, that drift becomes a gradient
in the counts and reads as biology. So: judge against the same visual criterion every time
(mask covers nuclei, leaves the gaps between them alone), and where a group comparison
matters, set thresholds blind to condition. Every call is recorded in `roi_settings.yml`,
so the series is inspectable rather than recalled.

---

## 4. Different magnifications, and what does not carry

This is the part that separates the manual route from the registered one. The registered
route runs one acquisition regime with one locked parameter set. Here, images arrive at
whatever magnification, Z depth and exposure they were acquired at.

**Micron parameters are the right way to write a setting down and the wrong way to judge
it.** `sigmaMicrons: 2.0` describes a physical smoothing scale, but whether it can
separate two nuclei depends on how many *pixels* a nucleus spans. So every run prints:

```
ACQUISITION CHECK — what these settings mean in pixels on THIS image
  a 10 um nucleus spans        21.7 px
  sigma 2.00 um                = 4.34 px
  min area 20.0 um^2           = 94 px  (>= 11.0 px across)
  cell expansion 5.00 um       = 10.86 px
  no advisories — the settings sit in a workable range for this pixel size
```

At 2.5 µm/px the same block reads `a 10 um nucleus spans 4.0 px` and flags
`ADVISORY: counting is PIXEL-LIMITED here` — touching nuclei cannot be split at any
setting, and the count is a lower bound. That is the acquisition floor
(`IMAGING-MINIMUM-VIABLE-ACQUISITION.md`), surfaced before you spend the detection run.

**Settings are stored per image**, keyed by entry name in `roi_settings.yml`, so an image
you tuned keeps what you tuned and a re-run reproduces it. If a saved block was written at
a different pixel size, the script says so rather than silently applying it.

**Z-stacks.** Detection runs on the plane each ROI was drawn on — these are single-plane
counts, not a projection through the stack. The plane travels in every export. If you want
a projection, project first (`czi_mip.py`) and count the projection.

---

## 5. What is poolable

Every count row carries a `settings_hash`: a digest of the *rule* that produced it.

It deliberately **excludes** the resolved threshold under `image_span`/`roi_span` — each
image getting its own number is exactly what makes them comparable, so hashing it in would
mark every image as incompatible with every other. It **includes** pixel size, because a
different pixel size is a different measurement, not a rescaling.

```bash
conda run -n braian python scripts/cockpit_roi.py --project "<the project dir>"
```

or `notebooks/04_roi.ipynb` §5. One group ⇒ pool freely. More than one ⇒ you get the list
of what differs, geometry breaks first:

```
settings groups: 2
  MORE THAN ONE RULE produced these numbers. ...
  What differs:
    GEOMETRY  pixel_um: 0.460357, 2.5
    setting   sigma_um: 2.0, 3.0
```

**Nothing is blocked.** This project's tooling advises and ranks; it refuses only when
something cannot be computed at all. If the comparison is deliberate, say so alongside the
number. If it is not, re-count the odd images with matching settings.

---

## 6. Reading the counts

`notebooks/04_roi.ipynb` §6, or the CSVs directly. Three files land in `results/roi/`:

| file | one row per |
|---|---|
| `<image>__percell_export.tsv` | cell — class, ROI name, area, centroid, `<marker>_bgsub` |
| `<image>__roi_counts.tsv` | drawn shape, then each pooled name |
| `roi_counts_combined.csv` | (image × ROI × class), with full settings provenance |

The per-cell file uses the **same schema as the registered route**, which is why
`cockpit_marker_gui.py` — set `k` by looking at ringed cells on the marker channel — works
on ROI data unchanged (notebook §4).

**Report `overlap_above_chance`, not the raw `Double+/TdT+` ratio.** The raw ratio inflates
wherever the activity marker is dense: a region can be 69% `Fos+` among `TdT+` cells and
still be only 1.4× above chance, while a sparser region at a lower raw rate is 4×. The
metric family is imported from `cockpit_animal`, so these are the same definitions the
registered route reports.

---

## 7. When it refuses, and what it means

Every stop names the thing to fix.

| message | fix |
|---|---|
| `no pixel calibration` | Set the pixel size (`Image` tab) or re-export with `PhysicalSizeX` in the OME-XML. Micron parameters are meaningless without it. |
| `pipeline.yml declares channel(s) absent from this image` | Channel names differ per acquisition — the actual list is printed. |
| `NOTHING TO COUNT` | Draw an area ROI. |
| `image_span threshold unavailable` | The histogram gave no usable peak pair. Try `roi_span`, or set the cut by eye. It will not silently substitute a different rule. |
| `whole-cell marker … Cell-compartment measurement is missing` | `cell_expansion_um` is 0. A whole-cell marker needs the cell compartment to exist. |
| `NO DETECTIONS inside the ROIs` | Cut far too high, or min/max area excludes everything at this pixel size — check the acquisition block above it. |

---

## 8. The rule that outranks everything here

**If the overlay looks wrong, it is wrong.** Not "the numbers say otherwise", not "the
seed value came from a paper". Toggle the detection overlay, look at the DAPI channel
clean, form an opinion, then turn detections on and compare. Missing dim nuclei ⇒ the cut
is too high. Detections in the gaps between nuclei ⇒ too low. One nucleus wearing two
detections ⇒ raise `sigma_um`, not the threshold.

Directions for every knob: [`03-tuning.md`](03-tuning.md). What to look for in the GUI:
[`04-qupath-gui.md`](04-qupath-gui.md).
