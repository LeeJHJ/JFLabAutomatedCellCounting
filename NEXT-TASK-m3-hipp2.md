# Next task — run M3 Hipp2 072526 through the pipeline

**Written 2026-07-29** as a cold-start handoff. Assumes no memory of the session that
wrote it. This is the first run on the generalized pipeline, so it doubles as the
stress test: anything that needs hand-holding here is a generalization bug, not an
operator problem — record it rather than working around it.

---

## What this run is for

Two questions at once:

1. **Does the pipeline run on a new brain without being re-tuned?** Everything is now
   config-driven and the detection threshold self-calibrates per section. If M3 Hipp2
   needs manual intervention beyond editing `pipeline.yml` channel names, that is a
   finding.
2. **Are the M3 Hipp2 counts biologically plausible?** Hippocampus, so the v1.0 M3
   numbers are a rough comparison (see "Sanity anchors" below) — same region, same
   animal line, different acquisition.

**Do not re-tune detection parameters to make the numbers look better.** One global
config for the series is a hard project rule (`CLAUDE.md`). If the numbers look wrong,
that is the result.

---

## Starting state (verified 2026-07-29)

```
M3 Hipp2 072526/M3 Hippocampus 2 072526 scenes/
    -001-01.czi              74 GB   raw
    -001-01_processed.czi    47 GB   Airyscan-processed  <-- USE THIS ONE
```

No MIPs, no QuPath project yet. This run starts from scene extraction.

Read from the CZI metadata (do not re-derive, but do re-verify if anything looks off):

| Property | Value |
| --- | --- |
| Scenes | **6** (`S` 0–5), 154–180 mosaic tiles each, tiles 1512×1512 |
| Channels | **3**, metadata order `AF568-T2` (TdTomato), `AF488-T3` (Fos), `DAPI-T4` |
| Z-planes | **4** |
| Pixel size | **0.460357 µm/px** (`Scaling/Items/Distance[@Id="X"]` = 4.6035698784722189E-07 m) |
| Z-step | **2.0 µm** → imaged slab ~6–8 µm |
| Scene bboxes | **OVERLAP** — several pairs. Region-based isolation is unsafe here. |

The overlap matters: `czi_mip.py --isolate auto` will correctly resolve to `tiles`
(per-scene tile-stitch). Do not force `--isolate region`; it will refuse, and rightly.

---

## Step 1 — scenes to MIPs

Pre-flight first (cheap, no heavy read). Confirm 6 scenes and the pixel size:

```bash
cd /home/jflab/Analysis
conda run -n braian python3 czi_mip.py --check-scenes \
    --czi "M3 Hipp2 072526/M3 Hippocampus 2 072526 scenes/-001-01_processed.czi"
```

Then convert. Pixel size is read from the CZI — **do not pass `--pixel-um`**:

```bash
conda run -n braian python3 czi_mip.py \
    --czi "M3 Hipp2 072526/M3 Hippocampus 2 072526 scenes/-001-01_processed.czi" \
    --outdir "M3 Hipp2 072526/mips" \
    --channels "AF568-T2" "AF488-T3" "DAPI-T4" \
    --animal-prefix M3-hipp2
```

Output: `M3-hipp2_s1_MIP.ome.tiff` … `_s6_MIP.ome.tiff`. Projection is **hybrid** —
single sharpest DAPI plane, full-Z max projection for markers. This is deliberate and
load-bearing: plain MIP over-projects DAPI and fuses touching nuclei into blobs.

**This is slow** (47 GB, 6 scenes × 3 channels × 4 planes, tile-stitched). Expect a long
run; consider `run_in_background`.

### BLOCKING HUMAN CHECK — channel identity

`--channels` gives names in *physical read order*, and **aicspylibczi's read order does
not always match the metadata order** (known bug, memory `feedback-channel-order`). The
order above is what the other projects in this family use and matches this CZI's
metadata, but it has not been visually confirmed for *this* file.

Open one MIP in QuPath and confirm:
- `DAPI-T4` looks like nuclei (dense, uniform, every cell)
- `AF568-T2` looks like sparse cytoplasm-filling TdTomato
- `AF488-T3` looks like sparse nuclear Fos

If TdT and Fos are swapped, every downstream number is wrong in a way nothing
automated will catch. Do not proceed past this until it is checked.

Also confirm scene→section identity (which MIP is which physical section) — only the
operator can do this against the slide. AP order is *not* implied by the `sN` numbering.

---

## Step 2 — QuPath project + ABBA registration  [GUI, operator]

1. Create a QuPath project, e.g. `M3 Hipp2 072526/M3 Hipp2 QuPath/`.
2. **Import the images FROM the QuPath project** — see the hard-won constraint below.
3. Register in ABBA (**fully manual after DeepSlice**, revised 2026-07-30): DeepSlice →
   Review/positioning mode for position + tilt → **Affine tab: match the slice to the
   overlay by hand** (angle, X, Y, scale) → **Spline tab: manual BigWarp** to finalize.
   Match against the **Label Borders** overlay. elastix is not used.
4. Export back to QuPath, then run `01_load_abba_rois.groovy` per entry.

Three things that will cost hours if forgotten:

- **Never Bio-Formats-import into ABBA.** Import FROM the QuPath project, or the
  registration export back to QuPath is blocked and the standalone `.abba` state
  cannot relink. Recovering means re-registering. (memory
  `feedback-abba-import-from-qupath-first`)
- **Adjust DV/ML tilt BEFORE Affine+Spline**, not more spline control points. Lateral
  structure misalignment is a tilt problem. (memory `feedback-abba-tilt`)
- **Match against the Label Borders overlay, by hand.** The registration is manual after
  DeepSlice (see step 3), so the overlay you want is the **region-outline drawing** — you
  are aligning boundaries to anatomy by eye. The section's own channel is **DAPI**, index
  **2** in these 3-channel MIPs (`AF568-T2`=0, `AF488-T3`=1, `DAPI-T4`=2); index 0
  presents as "missing channels" in BigWarp (memory `feedback-abba-channel-index`).

  If elastix is ever reintroduced, its *fixed* channel must be atlas **Nissl (Ch0)**, NOT
  Label Borders — an intensity-based optimizer needs intensity correspondence, and a line
  drawing gives it none. That is the same fact that makes Label Borders the *right*
  choice for a human. (`06-REG05-FINDINGS.md`; superseded as the standard chain
  2026-07-30.)

  > **Corrected 2026-07-30.** An earlier draft of this file said "do not register on
  > DAPI", conflating the atlas-side finding above with a separate *literature* claim —
  > Cabrera et al. (bioRxiv 2024.09.16.611953) report Dice ~0.30 for DAPI vs ~0.49–0.55
  > for Fos/NeuN. That comparison has never been tested on our data, and it probably does
  > not transfer: their alternative is **NeuN, a pan-neuronal stain**, whereas our 488 is
  > **Fos**, which is activity-sparse (2–28% of nuclei by region in the M3 Hipp1 readout;
  > TdT sparser still at ~1–5%). Neither of our marker channels gives continuous
  > structural texture. DAPI is the closest thing we have to their NeuN, not the thing
  > they warned against.

---

## Step 3 — deploy the pipeline into the new project

```bash
conda run -n braian python3 scripts/sync_project.py \
    --project "M3 Hipp2 072526/M3 Hipp2 QuPath"
```

This copies `scripts/*.groovy` in (QuPath can only run scripts inside the project),
removes retired ones, and creates `pipeline.yml` from the repo root.

**Then edit `<project>/pipeline.yml`.** It arrives as a copy of the root config, so
confirm the channel names match this project's images exactly (they appear in
`server.json`). For M3 Hipp2 the root config should already be correct — multi-marker,
`DAPI-T4` anchor, `Fos`/`AF488-T3`/nuclear, `TdT`/`AF568-T2`/**whole-cell**.

Whole-cell TdT is an operator domain call from 2026-07-25 (TdTomato fills the whole cell
in this line; ring-only under-counts). Do not "fix" it to cytoplasmic — an external
review brief still says ring-only and is out of date on this point.

Verify:

```bash
conda run -n braian python3 scripts/validate_pipeline_config.py \
    --config "M3 Hipp2 072526/M3 Hipp2 QuPath/pipeline.yml"
```

Also create `BraiAn.yml` for the project. Copy from
`M3 Hipp1 072326 7scene/M3 Hipp1 072326 7 Scene QuPath/BraiAn.yml` — same acquisition
family (20x, 4-plane hybrid, 0.460357 µm/px) — and then:

- set `requestedPixelSizeMicrons: 0.460357` to match this project's `server.json`
  `PhysicalSizeX` exactly
- **delete the `threshold:` key and the commented `histogramThreshold:` block.** They
  are ignored for the anchor channel now: `run_braian_detection.groovy` computes the
  threshold per section from `pipeline.yml`'s `detection_threshold`. Leaving a stale
  `threshold: 700` in the file is confusing but harmless.
- leave `classifiers: []` — classification happens only in `02_detect_classify.groovy`

---

## Step 4 — calibrate the threshold on ONE slice, looking at it

This is the new step and the point of the generalization work. The cut is
`floor + span_frac × (bright_peak − floor)`, re-derived per section, so it should
transfer without tuning — but confirm where it lands on this slice-set.

In QuPath, on one slice: run `scripts/calibrate_threshold.groovy` (read-only, safe to
repeat). Then:

```bash
conda run -n braian python3 scripts/cockpit_threshold.py \
    --project "M3 Hipp2 072526/M3 Hipp2 QuPath" --plots
```

or use `notebooks/01_calibrate.ipynb` §3 (set `PARAMS["project"]`, `dry_run: False`).

**What to look for.** The reported `achieved_frac` should sit in 0.10–0.45; 0.25 is the
default. If the histogram has no bright-nuclei peak at `peak_prominence: 100`, lower it
and re-run — a missing second peak is the one case where this rule cannot be applied,
and it is worth recording as a finding rather than silently switching to
`mode: "absolute"`.

For reference, M3 Hipp1 gave floor 162 / bright 2268, so the cut landed at ~688.
M3 Hipp2 is the same acquisition family, so similar numbers are expected. **Very
different numbers are informative, not a problem to paper over.**

---

## Step 5 — batch detect → classify → export

`notebooks/02_batch.ipynb`, or the three Groovy stages "Run for project":

```
run_braian_detection.groovy    detection + per-channel measurements
02_detect_classify.groovy      per-marker robust cut, compartments, Double+
03_export_region_table.groovy  per-cell TSV + per-region counts/density + long CSV
```

Unregistered entries are now skipped loudly, so a stray import cannot silently enter
the batch. If you see a SKIP, that entry needs registering or removing.

Detection is the expensive stage (~30 min/slice at this pixel size × 6 slices).

---

## Step 6 — readout

`notebooks/03_animal.ipynb` for the animal-level rollup, and `cockpit_checks.py` gates.

Report **enrichment, not raw ratios**: `P(Fos+|TdT+) / baseline P(Fos+|DAPI)`. The raw
reactivation ratio inflates in dense-Fos regions (memory
`reactivation-enrichment-not-raw-ratio`). Field name is "above-chance ratio", not
"enrichment" (memory `engram-overlap-metrics`).

Aggregate to the animal level before any group comparison — never pseudoreplicate on
section- or cell-level n.

### Sanity anchors (hippocampus, from the v1.0 M3 run)

Comparison points, **not pass/fail gates**:

| Metric | v1.0 M3 value |
| --- | --- |
| Nucleus area, modal bin | 40–50 µm² (median 47.88) |
| DAPI density, hippocampal subfields | 2,900–3,800 /mm² |
| Fos+ fraction | ~20% |
| CA1 bilateral cells | 6,354 |
| Cells labelled `grey` | **must be ~0** |

**The `grey` count is a canary.** A non-trivial number means the CR-01 region-labelling
bug is back (geometric `is_leaf` + smallest-area-containing `regionOf`). An
all-`Negative` classification means the D-05 measurement-key bug is back. Check both.

TdT-derived v1.0 figures (TdT+ fraction ~3.5%, Double+/TdT+ ~0.45, per-subfield
coexpression) predate whole-cell TdT measurement and are **not** comparable.

---

## Known-open issues that may show up

- **Possible over-segmentation.** Measured density runs above the 500–2,000/mm²
  literature seed while nucleus area runs below the 50–150 µm² seed — smaller objects
  and more of them, total nuclear area roughly conserved, which is the signature of
  watershed splitting nuclei. Never checked against hand counts. If M3 Hipp2 shows the
  same pattern, that strengthens the case for spending a session on ground-truth counts
  before locking parameters for a cohort.
- **Whole-cell TdT picks up passing axons**, falsely marking bystander nuclei TdT+.
  Biases reactivation *conservative*. Levers: `k_robust` up, `cellExpansionMicrons`
  down. (memory `tdt-wholecell-axon-contamination`)
- **DAPI saturation.** The v1.0 acquisition clipped DAPI at 65,535. If M3 Hipp2 also
  clips, blob-like nuclei and over-segmentation both get worse. Check the histogram in
  step 4 — a hard spike at the top of the range is the tell.
- **DAPI density is not currently trustworthy** — the white-matter and ventricle gates
  are demoted to advisory (operator call 2026-07-28). Ratio readouts like P(Fos+|TdT+)
  are fine; absolute densities are not.

---

## Context you may want

- `IMAGING-MINIMUM-VIABLE-ACQUISITION.md` — the acquisition-cost memo; M3 Hipp2 is at
  the *current* expensive settings (0.46 µm/px, Airyscan on), so it is a baseline for
  any cheaper comparison, not the cheap arm.
- `RUNBOOK.md` "starting on a new brain" — the condensed version of steps 3–4.
- `docs/` — full operator tutorial (`mkdocs serve`).
- Branch `generalize-pipeline-260729` — the 7 commits this handoff follows from, not yet
  merged to `main`.
