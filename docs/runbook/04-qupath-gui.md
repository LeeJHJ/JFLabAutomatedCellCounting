# Working in the QuPath GUI

**Written 2026-08-04.** The pipeline's *compute* is already headless — every stage runs
through `QuPath script`. The GUI is for two things the compute cannot do: **creating the
project**, and **looking at the result**. This guide is about the looking.

It is organised around questions rather than menus, because the menus are the easy part.
Exact menu paths shift between QuPath versions, so where a command is named here, find it
with QuPath's **searchable command list** rather than hunting a submenu.

> **Why not napari, or a web viewer?** Considered 2026-08-04 and rejected for now. The
> segmentation engine (BraiAnDetect's watershed, background-by-reconstruction, cell
> expansion, area-weighted whole-cell means) and the ABBA/Warpy transform integration are
> QuPath-specific. Reimplementing them is not a port — it is a *different segmenter*, and
> every number changes. A second viewer would duplicate what QuPath already does well
> without adding capability. Revisit if reviewing a whole series at once becomes the
> bottleneck.

---

## 1. Is this detection real?

The single most valuable thing the GUI does, and the top of the project's evidence
hierarchy: **what you see outranks any computed number.**

- **Toggle the detection overlay** (View menu). Look at the DAPI channel *clean* first,
  form an opinion, then turn detections on. Doing it the other way round anchors you.
- **Show one channel at a time** via the brightness/contrast dialog. TdT contamination
  from passing axons is invisible when three channels are composited.
- **Change the display range, not the data.** A dim section can be made to look bright;
  that tells you nothing about whether the threshold was right. Judge the *mask*, not
  the brightness.
- **Fill vs outline** for detections: outlines let you see the nucleus underneath, fills
  make density obvious at low zoom. Switch between them.

What you are looking for, in order:

1. **Flooding** — detections in the spaces *between* nuclei. Threshold too low.
2. **Missing dim nuclei** — visible DAPI blobs with no detection. Threshold too high.
3. **Over-segmentation** — one nucleus carrying two or three detections. That is
   `sigmaMicrons`, not the threshold: raise it to merge.
4. **Merged nuclei** — one detection spanning an obvious pair. Lower `sigmaMicrons`.

Directions for every knob: `docs/runbook/03-tuning.md`.

---

## 2. Hand counting — the one thing that settles a QC flag

Two `<anatomical>` gates have flagged on **every section ever run here**: white matter
denser than cortex (ratios 1.09–1.45 where ≤0.6 is expected), and ventricles at
872–3,605/mm² where CSF should be near-empty. `<anatomical>` is the tier that means *true
regardless of acquisition*, so a violation is a real defect — but **nobody has ever
counted by hand**, so "detection over-calls in white matter" has always been an inference
from a ratio, never an observation.

```
# QuPath Script editor, with the slice open
scripts/qc_handcount.groovy
```

It places boxes fully inside named regions (default `cc`, `VS`, `Isocortex`), reports the
machine count and implied density per box, and leaves the boxes named `handcount_*` in the
Annotations list. Double-click one to zoom to it. The RNG seed is fixed, so re-running
samples the same places and a re-count is comparable to the last one.

Box size is **adaptive** (150 → 40 µm, largest that fits). This matters: `cc` and `VS` are
long and thin, so a fixed 150 µm square does not fit inside them despite `cc` having over
500,000 µm² of area — the first version silently skipped exactly the two regions the gates
flag.

### Reading the result

| machine ÷ human | meaning |
| --- | --- |
| ≈ 1.0 | detection is sound; the gate's **band** is what is wrong |
| ≫ 1 in white matter | real over-detection — tune, then re-check cortex too |
| ≫ 1 in ventricle | haze is being segmented, or the anchor channel bleeds there |

**Count the ratio, not the absolute.** Two or three boxes per region is enough to tell a
2× over-count from a 10% one, and that is the distinction that changes what you do.

### Two things the first run already showed (M5-hipp3_s1, 2026-08-04)

**The ventricle gate may be measuring cells that never enter your analysis.**
`regions.tsv` — which the gate reads — is written by `run_braian_detection.groovy`, *before*
`02_detect_classify.groovy` applies `exclude_acronyms: ["DG-sg", "VS"]`. Measured:

```
regions.tsv          VS: 213 detections / 0.300 mm² = 709/mm²   ← what the gate reads
percell_export.tsv   VS: 0 cells                                 ← what analysis sees
```

So the flag is true about detection and irrelevant to any count, ratio or figure.

**And those 213 are at the rim, not in the lumen.** Three boxes placed inside `VS`
contained **zero** detections. Uniformly distributed, the ~22% of VS area they cover should
have held ~48. The ventricular lining (ependyma, subventricular zone) is genuinely
nucleated — so the gate's premise, *ventricle = CSF = empty*, may be wrong as implemented,
because the VS annotation includes its own wall.

Three boxes, one section, machine counts. A lead, not a verdict — but it tells you where
to point your eye.

---

## 3. Where did the threshold actually land?

```
scripts/calibrate_threshold.groovy      # read-only, changes no objects, safe to re-run
```

Prints the floor, the bright peak, a `span_frac` sweep, and the chosen cut, and writes the
JSON that `notebooks/01_calibrate.ipynb` §3 plots. If this slice has a per-slice override
in `pipeline.yml` (`threshold_overrides`), it says so and previews the overridden value —
so calibration and detection cannot disagree.

**Set the value in the notebook picker (§3b), not here.** This script tells you what the
rule *would* do; the picker shows you the mask on the image, which is the tier-1 evidence.
`span_frac 0.25` is tier-3 — seeded from one operator call on one section, never validated
against hand counts — and it misfired or looked suspect on 5 of the 16 sections run here.

---

## 4. Does the registration fit?

Judge against the **Label Borders** overlay: you are aligning boundaries by eye.

- **Check laterally first.** If LA / BA / cortex edges are off but the midline looks fine,
  that is a **tilt** problem, and it must be fixed in ABBA's positioning step *before* any
  warping. No number of spline control points will fix a tilt.
- **Check the section is where DeepSlice thinks it is.** Caudal sections past the
  cerebellum give DeepSlice little to work with; a confidently wrong AP position produces
  a registration that looks locally plausible and assigns every cell to the wrong region.
- **Unregistered entries are skipped loudly** by `01_load_abba_rois.groovy` — read its
  output rather than assuming everything went in.

Full click-path: `docs/runbook/01-registration.md`.

---

## 5. Running stages from the GUI

Any pipeline stage can be run from the **Script editor** on the open image, which is the
fast way to iterate on one slice.

| | Script editor | headless (`QuPath script …`) |
| --- | --- | --- |
| scope | the open image | `--image` one entry, or the whole project |
| saving | you control it | needs `-s`, or a 30-min run is discarded |
| use it for | tuning one slice, inspecting | batches, anything reproducible |

Two rules that have cost real time here:

- **`-s` is not optional headless.** Without it QuPath computes the detections and throws
  them away.
- **A stage that aborts must throw, not return.** A bare `return` exits with status 0, so
  a batch runner reads the abort as success and happily classifies and exports a section
  with no detections. This bit `M5c_s3`/`s4` on 2026-07-31 and is why
  `run_braian_detection.groovy` throws.

Deploy repo scripts into a project with `scripts/sync_project.py` — never hand-copy. QuPath
can only run Groovy that lives inside the project, so `<project>/scripts/` is a *deployed
copy*, and the repo is the source.

---

## 6. Practical

**Memory.** QuPath is set to `-Xmx32G` (`QuPath/lib/app/QuPath.cfg`). The GUI grows as you
pan around a large image — its tile cache is 25% of max heap, and it does not shrink.
Observed on this box, 2026-08-04: 5.9 GB after 45 min, **10.0 GB after 6 hours**. That is
normal, not a leak to chase, but:

- **Restart the GUI between sessions**, especially before a headless batch — two JVMs each
  holding tens of GB will start swapping on a 61 GB box.
- **Never kill QuPath by name while a headless run is going.** Match on the full command:
  `pgrep -af "QuPath script"` finds the batch, the bare GUI process is a different PID.
- Kill orphaned notebook kernels with `pkill -f ipykernel_launcher` — that pattern cannot
  match QuPath or Fiji.

**Project hygiene.** Create the QuPath project *first*, then import into ABBA **from the
project**. Importing into ABBA via Bio-Formats permanently blocks the registration export
back to QuPath, and the only fix is re-registering from scratch.

**When the GUI is the wrong tool.** Anything you want to be reproducible. If you found a
setting by clicking, put it in `pipeline.yml` or `BraiAn.yml` and re-run headless, or it
will not survive the session.

---

## Where to go next

| you want | read |
| --- | --- |
| run a dataset start to finish | `docs/runbook/00-run-a-new-dataset.md` |
| the ABBA click-path | `docs/runbook/01-registration.md` |
| detection detail | `docs/runbook/02-detection.md` |
| a knob and which way to turn it | `docs/runbook/03-tuning.md` |
| what the stages are | `docs/pipeline-stages.yml` |
