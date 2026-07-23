# BraiAnDetect Detection — Detail Guide

**Screenshot to be captured during the 06.1-06 operator validation run.** The
image slots below are placeholders — they will be filled in the next time
this stage is run end-to-end.

`[GUI]` — this stage runs inside QuPath as a script you launch by hand, but
it is grouped with the other manual, judgment-requiring steps because tuning
it correctly requires visually inspecting the detected nuclei. This is the
seam the **D-15 "detections present" and "config-declared channels match the
image" boundary asserts** guard: `02_detect_classify.groovy` and
`03_export_region_table.groovy` both check `getDetectionObjects()` is
non-empty and that every channel named in `pipeline.yml` exists on the
image's channel metadata, aborting cleanly with the missing item named if
either check fails.

## The two config files: `BraiAn.yml` vs `pipeline.yml`

This is the single most important thing to understand about this stage —
detection parameters and marker/region parameters live in **two separate
files with a hard responsibility split**:

| File | Lives in | Owns |
|---|---|---|
| `BraiAn.yml` | QuPath project base dir | **How cells are found**: `sigmaMicrons`, `minAreaMicrons`/`maxAreaMicrons`, `histogramThreshold` (resolution level, smoothing window, peak prominence, which histogram peak), `cellExpansionMicrons` (cytoplasmic expansion ring width for the *detection* step). |
| `pipeline.yml` | Repo root (copy alongside `BraiAn.yml`) | **What the found cells are**: the marker list (name/channel/compartment), the anchor channel, `exclude_acronyms`, `k_robust`, and the ring geometry used for the *classification* bg-sub measure. |

`BraiAn.yml` also declares the detection **topology**: a single
`channelDetections` entry rooted at the DAPI anchor channel, with both
marker classifiers (e.g. Fos, TdT) nested underneath it — not one
`channelDetections` entry per marker with a separate overlap-merge step.
This is deliberate: per the project's nucleus-anchored colocalization rule,
applying both classifiers sequentially to the *same* DAPI-derived detection
set is how `Double+` arises, with no geometric-overlap heuristic involved.

`scripts/validate_pipeline_config.py` defensively checks that no
`BraiAn.yml`-only key (`sigmaMicrons`, `minAreaMicrons`, `maxAreaMicrons`,
`histogramThreshold`, `cellExpansionMicrons`) has leaked into `pipeline.yml`
— if you see that error, move the offending key back to `BraiAn.yml`.

**Classification is a separate step.** Detection (`run_braian_detection.groovy`,
this doc) only finds nuclei and measures raw per-channel intensities.
Assigning `<marker>+`/`Double+`/`Negative` classes is
`02_detect_classify.groovy` (see the "Classify" section of
[docs/index.md](../index.md)) — keeping them apart is what makes the
re-classify-without-re-detect tuning loop below fast.

## Running detection

In QuPath, with the entry's ABBA ROIs already loaded (previous stage):

```
Automate > Script editor > Run   (run_braian_detection.groovy)
```

This runs BraiAnDetect's built-in QuPath cell detector (CPU-only — no
Cellpose/StarDist) against the region(s) declared in `BraiAn.yml`'s
`classForDetections`, using the parameters under `channelDetections`.

![Detected nuclei overlay](../assets/det-01-overlay.png)

## Tuning loop (delete → edit → re-run)

Detection parameters are tuned by eye, watching for one-nucleus-per-detected-blob
without over-splitting or missing faint nuclei:

1. **Delete the previous detections:** in QuPath,
   `Objects > Delete > Delete all detections`.
2. **Edit `BraiAn.yml`** — the parameter most often adjusted is `sigmaMicrons`
   (blob-splitting sensitivity: too low under-splits touching nuclei, too
   high over-splits a single nucleus into several); also watch
   `minAreaMicrons`/`maxAreaMicrons` (nucleus-area band) and
   `histogramThreshold.nPeak`/`peakProminence` (which histogram peak counts
   as the tissue/nuclear signal vs. background).
3. **Re-run** `run_braian_detection.groovy`.
4. Repeat until the overlay looks right, then move on to
   `02_detect_classify.groovy` (classification reads whichever detections
   exist right now — no need to re-run classification until detection itself
   is settled).

![Sigma too low — under-split](../assets/det-02-undersplit.png)
![Sigma too high — over-split](../assets/det-03-oversplit.png)

## A known extension bug (already patched in this repo's copy)

`run_braian_detection.groovy` is a corrected copy of the BraiAnDetect
extension's own bundled example script. The bundled version constructs
`new ImageChannelTools(name, server)`, but in the installed extension version
that `(String, ImageServer)` constructor leaves `ImageChannelTools.imageData`
null, causing a null-pointer exception inside `findNChannel()`. This repo's
copy passes `imageData` (the `(String, ImageData)` constructor) instead — if
you ever re-copy the extension's original example script over this file,
you will reintroduce that crash.
