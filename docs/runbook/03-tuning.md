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

## A tuning round, end to end

1. `--list` — see where everything currently sits
2. Change one thing (`--set`, or a `czi_mip.py` flag for a MIP knob)
3. Re-run the affected stage — one scene for MIP knobs, one slice for detection knobs
4. **Look at it.** Outlines on a dense region; seams on the stitched image
5. `--log --note "..."` — record what you saw
6. Repeat

Change **one knob at a time**. Two at once and the log cannot tell you which one
moved the numbers.
