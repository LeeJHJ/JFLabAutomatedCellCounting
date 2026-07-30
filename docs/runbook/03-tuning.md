# 3. Tuning the pipeline

Every adjustable parameter in the pipeline, in one table, with the direction to move
it. Nothing here requires editing source code.

## The one command

```bash
conda run -n braian python3 scripts/cockpit_tune.py --project "<project dir>" --list
```

That prints the table below filled in with **this project's** current values. To
change something:

```bash
# change one or several knobs; each is routed to the correct config file
conda run -n braian python3 scripts/cockpit_tune.py --project "<dir>" \
    --set sigmaMicrons=2.5 --set span_frac=0.30

# same, and deploy into the QuPath project afterwards
conda run -n braian python3 scripts/cockpit_tune.py --project "<dir>" \
    --set span_frac=0.30 --deploy
```

After you have looked at the result, record the round so you can compare later:

```bash
conda run -n braian python3 scripts/cockpit_tune.py --project "<dir>" \
    --log --note "seams less visible, nuclei still a bit small"
```

This appends a row to `<project>/results/tuning_log.csv` holding the full parameter
set plus the resulting numbers (modal nucleus area, density, Fos+/TdT+ fractions),
so "the settings from two rounds ago looked better" is an answerable question.

!!! note "Why the settings live in two files"
    `BraiAn.yml` is BraiAnDetect's own detection-parameters file; `pipeline.yml` is
    the marker-set and classification config. They are deliberately kept separate
    (D-14) so classification cannot silently happen twice by two different rules.
    `cockpit_tune.py` reads and writes both, so you get one control surface without
    the files being merged. Your comments in those files are preserved on write.

---

## MIP / seams

These are **command-line arguments to `czi_mip.py`**, not stored settings — pass them
on the conversion call. They only apply to the tile-stitch path (`--isolate tiles`).

| Knob | Default | What it does | Which way to move it |
|---|---|---|---|
| `--feather-margin` | `130` px | Seam blend width for the per-scene tile stitch | **RAISE** to soften visible seams; **LOWER** to keep tile edges crisp |
| `--no-flat-field` | off (correction enabled) | Disables the per-channel retrospective shading correction | **USE** to test whether shading estimation is itself causing the banding you see |
| `--dapi-z N` | automatic | Forces the anchor focus plane to a 0-based Z index instead of the var-of-Laplacian pick | **SET** when the automatic pick disagrees with your eye. The log still prints what the automatic pick would have been |
| `--scenes N [N ...]` | all scenes | 1-based scene subset to convert | **SET to one scene** while tuning — one scene is ~5 min against ~30 min for a 6-scene series |

**Tuning seams in practice.** Re-cut a single scene, look at it, adjust, repeat:

```bash
conda run -n braian python3 czi_mip.py \
    --czi "<file>.czi" --outdir "<dir>/mips" --animal-prefix M3-hipp2 \
    --channels "AF568-T2" "AF488-T3" "DAPI-T4" \
    --scenes 3 --feather-margin 200
```

If widening the feather does not help, the seams may be a shading-estimation artifact
rather than a blending one — re-cut the same scene with `--no-flat-field` and compare.

---

## Detection — `BraiAn.yml`

| Knob | Default | What it does | Which way to move it |
|---|---|---|---|
| `sigmaMicrons` | `2.0` | Smoothing before watershed; the split-vs-merge control | **RAISE** to merge over-split nuclei; **LOWER** to separate touching nuclei |
| `minAreaMicrons` | `20.0` | Smallest accepted nucleus (µm²) | **RAISE** to reject debris; **LOWER** if real small nuclei are missing |
| `maxAreaMicrons` | `250.0` | Largest accepted nucleus (µm²) | **RAISE** if large nuclei are clipped; **LOWER** to reject merged blobs |
| `cellExpansionMicrons` | `5.0` | Nucleus → cell expansion; defines the whole-cell / cytoplasm compartment | **LOWER** to cut TdT contamination from passing axons; **RAISE** to capture more cytoplasm |
| `backgroundRadiusMicrons` | `10` | Background estimation radius | **RAISE** on broad uneven illumination; **LOWER** for local background |
| `requestedPixelSizeMicrons` | from the image | Must equal this project's `server.json` `PhysicalSizeX` | **DO NOT TUNE.** Match the image exactly, or every micron-denominated parameter mis-scales |

!!! warning "Over-splitting has a signature"
    Modal nucleus area *below* the expected band while density runs *above* it —
    smaller objects, more of them, total nuclear area roughly conserved — is the
    signature of watershed splitting single nuclei. `sigmaMicrons` is the knob.
    Judge it by looking at the outlines on a dense region, not by the numbers alone:
    the reference bands were imported from a different acquisition and have never
    been validated against hand counts on this data.

---

## Classification — `pipeline.yml`

| Knob | Default | What it does | Which way to move it |
|---|---|---|---|
| `span_frac` | `0.25` | Anchor cut placement: `floor + span_frac × (bright_peak − floor)`, re-measured per section | **RAISE** for fewer, brighter nuclei; **LOWER** to catch dimmer nuclei |
| `peak_prominence` | `100` | Histogram peak-finding prominence for both threshold endpoints | **LOWER** if the bright-nuclei peak is not found on a section |
| `smooth_window` | `15` | Histogram smoothing window for peak finding | **RAISE** on noisy histograms |
| `k_robust` | `3.0` | Marker-positive cut: `median + k × 1.4826 × MAD` on background-subtracted signal | **RAISE** to cut TdT false positives from passing axons; **LOWER** if real positives are missed |
| `gap_um` | `1.0` | Gap between the nucleus boundary and the cytoplasmic measurement ring | **RAISE** to avoid nuclear bleed into the ring (cytoplasmic markers only) |
| `width_um` | `8.0` | Cytoplasmic measurement ring thickness | **RAISE** to capture more cytoplasm (cytoplasmic markers only) |

!!! danger "Never make the detection threshold absolute"
    `span_frac` is a *fraction of each section's own* intensity span, which is what
    makes sections and animals comparable. Switching `mode` to `absolute` pins the
    cut to one section's intensity scale and silently under-detects every dimmer
    section. See [`cockpit_threshold.py`](../index.md) and
    `notebooks/01_calibrate.ipynb` §3 to see where the cut actually lands before
    changing it.

---

## How much authority does a number have?

Gates print a tier next to their value. It says how much the gate's *own expected band*
is worth — never how much your eyes are worth.

| Tier | Meaning | What a FLAG means |
|---|---|---|
| `<anatomical>` | True regardless of acquisition, stain, or scope — ventricles are CSF-filled, white matter is sparsely nucleated vs cortex | **A real defect.** Something is being detected that is not there |
| `<internal>` | Measured from this dataset; checks self-consistency only (e.g. is the readout stable across `k`) | The result is fragile — treat the number as provisional |
| `<assumed>` | A band carried in from another acquisition or a paper, never checked against hand counts on our images | **Go and look.** It may be the band that is wrong |

**The operator's eye outranks all three.** If you can see that cells are being missed or
invented, that settles it — do not tune a parameter to move an `<assumed>` number into
its expected range. Tune to match the image.

---

## Marker+ cells are being missed (or over-called)

The symptom: cells you can see are clearly marker-positive are labelled `Negative`, or
are DAPI+/Fos+ but never called TdT+ / Double+.

First, work out which of two different failures it is:

- **Was the nucleus detected at all?** Classification is nucleus-anchored — a cell whose
  nucleus was never segmented can never be called positive for anything. If the cell has
  no outline, this is a *detection* problem: `span_frac` / `sigmaMicrons`.
- **Nucleus detected, marker not called?** A *classification* problem. Everything below.

### The levers, in the order worth trying

| # | Lever | Where | Effect |
|---|---|---|---|
| 1 | **`k_robust` for that marker** | `pipeline.yml`, inside the marker entry | LOWER catches dimmer positives. Per-marker, so loosening TdT does not touch Fos |
| 2 | `cellExpansionMicrons` | `BraiAn.yml` | Larger ring captures more cytoplasmic signal for dim whole-cell markers |
| 3 | `compartment` | `pipeline.yml` | `whole-cell` averages nucleus + ring by area. If a marker is bright in cytoplasm but absent from the nucleus, that average *dilutes* it — `cytoplasmic` (ring only) can be more sensitive |
| 4 | `backgroundRadiusMicrons` | `BraiAn.yml` | If background is estimated too locally, a cell sitting in marker-positive neuropil has its own signal subtracted away |

Sweep `k` before changing anything, straight off the per-cell export — no QuPath needed:

```python
import pandas as pd, numpy as np
df = pd.read_csv(percell_tsv, sep="\t")
v = pd.to_numeric(df["TdT_bgsub"], errors="coerce").dropna()
med, rsd = np.median(v), 1.4826 * np.median(np.abs(v - np.median(v)))
for k in (3.0, 2.5, 2.0, 1.5):
    print(k, round(med + k*rsd, 1), int((v > med + k*rsd).sum()))
```

Then set it per marker:

```yaml
markers:
  - name: "TdT"
    channel: "AF568-T2"
    compartment: "whole-cell"
    k_robust: 2.5          # this marker only; global k_robust still applies to the rest
```

!!! warning "The trade on whole-cell markers"
    Whole-cell TdTomato measurement picks up **passing axons**, which can mark a
    bystander nucleus as positive. Lowering `k` increases that. The counter-lever is
    `cellExpansionMicrons` **down**, not `k` back up — shrinking the ring keeps dim real
    cells while cutting the axon contribution. Which way to trade is a judgment call
    about your biology: over-calling inflates the tagged population, under-calling biases
    reactivation estimates conservative.

### What cannot be fixed after imaging

If a cell's marker signal is at or below the noise floor, no threshold recovers it —
lowering `k` far enough to catch it will pull in noise everywhere else. That is an
**acquisition** fix: longer exposure or higher gain on that channel, or more Z coverage
if the signal sits outside the imaged slab. Record it and change the protocol; do not
chase it with `k`.

---

## A tuning round, end to end

1. `--list` — see where everything currently sits
2. Change one thing (`--set`, or a `czi_mip.py` flag for a MIP knob)
3. Re-run the affected stage — one scene for MIP knobs, one slice for detection knobs
4. **Look at it.** Outlines on a dense region; seams on the stitched image
5. `--log --note "..."` — record what you saw
6. Repeat

Change **one knob at a time**. Two at once and the log cannot tell you which one
moved the numbers.
