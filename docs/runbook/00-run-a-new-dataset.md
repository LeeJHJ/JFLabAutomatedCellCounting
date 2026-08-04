# Run a new dataset, start to finish

**Written 2026-08-03** for the operator to run a fresh slice-set alone, using the new
M5 hippocampus set as the worked example. Substitute your own names throughout.

This is the *spine*. Two stages have their own detail docs and this file links to them
at the right moment: `01-registration.md` (ABBA) and `02-detection.md` (QuPath). Every
knob and which way to move it is in `03-tuning.md`.

**Time:** ~30 min of your attention spread over the day, plus ~1 h of ABBA clicking per
6 sections and an unattended detection batch (~20–40 min per section, run it overnight
or while you image).

---

## Conventions used below

```bash
cd ~/Analysis
PY=$HOME/miniforge3/envs/braian/bin/python
QP=$HOME/section-pipeline/tools/QuPath/bin/QuPath
```

**Use `$PY`, not `conda run -n braian`.** `conda run` buffers stdout, so a 20-minute
step looks frozen and you cannot tell progress from a hang. Calling the env's python
directly streams output live.

Every step is tagged **[SHELL]**, **[GUI]**, or **[NOTEBOOK]** so you know whether to
type or click.

---

## Step 0 — prove the machine is sane  [SHELL]

```bash
$PY scripts/smoke_test.py
```

Expect `24/24 checks passed`. This builds a throwaway project from nothing and runs the
chain against it, so a PASS means the pipeline works independent of whatever state the
workspace happens to be in. Run it after any pipeline change and on any new machine.
If it fails, stop — do not start a real run on a broken install.

---

## Step 1 — make the folder  [SHELL]

One directory per imaging session, at the repo root, named `<animal> <region> <date>`:

```bash
mkdir -p "M5 Hipp3 080326"/{raw,mips}
```

Drop the CZI(s) into `raw/`. The QuPath project will be created inside this folder in
step 4, giving the layout every other dataset uses:

```
M5 Hipp3 080326/
  raw/                          the CZI(s) as exported from ZEN
  mips/                         one OME-TIFF + one thumbnail PNG per scene
  M5 Hipp3 080326 QuPath/       the QuPath project (created in step 4)
```

---

## Step 2 — check the scenes before converting  [SHELL]

```bash
$PY czi_mip.py --check-scenes --czi "M5 Hipp3 080326/raw/M5_Hipp3.czi"
```

Read-only. It prints the channel count, Z-plane count, the pixel size **read from the
CZI's own metadata**, and one line per scene with its bounding box and tile count.
Check three things:

1. **Scene count matches the number of sections you imaged.** If it doesn't, the CZI is
   not what you think it is.
2. **Pixel size matches your other sections in this cohort.** M3 was 0.460357 and M5 was
   0.6905355 — 33 % apart, which made those two animals non-comparable on density.
   Either value works; *mixing within a comparison* does not.
3. **Z-plane count matches.** Markers are max-projected over Z, so 4 planes samples ~3×
   the cell volume of 2.

Write the pixel size down. You need it again in step 5.

---

## Step 3 — CZI → hybrid MIP  [SHELL]

```bash
$PY czi_mip.py \
  --czi "M5 Hipp3 080326/raw/M5_Hipp3.czi" \
  --outdir "M5 Hipp3 080326/mips" \
  --channels "AF568-T2" "AF488-T3" "DAPI-T4" \
  --animal-prefix M5-hipp3
```

`--channels` is in **physical read order**, which is not the metadata order —
aicspylibczi returns them differently. The order above is correct for our acquisitions;
`--check-scenes` prints what the file actually contains if you need to confirm.

`--animal-prefix` must be **unique per imaging session**. Three CZIs each numbering
scenes from `s1` will silently overwrite each other in one output directory. That
happened on M5.

Projection is **hybrid** and this matters: DAPI is a single auto-selected sharpest Z
plane, markers are a full-Z max projection. A plain MIP over-projects DAPI and fuses
touching nuclei into blobs.

Useful flags when something looks wrong (all documented in `03-tuning.md`):

| flag | when |
| --- | --- |
| `--scenes 1 3 5` | convert a subset while testing |
| `--dapi-z 2` | override the auto-picked DAPI plane |
| `--marker-z 0 1` | restrict marker projection depth — the **only** way to process a 4-plane acquisition at a 2-plane depth for comparability |
| `--no-flat-field` | if flat-field correction makes the tile seams worse rather than better |
| `--feather-margin N` | widen/narrow the tile-seam blend |

**Then look at the thumbnail PNGs in `mips/`.** They exist so you can confirm
scene → file identity before you spend an hour registering the wrong section. Check the
sections are the ones you meant, and that tile seams are not glaring.

---

## Step 4 — QuPath project + import  [GUI]

1. Open QuPath. **File → Project → Create project**, in
   `M5 Hipp3 080326/M5 Hipp3 080326 QuPath`.
2. **Add images** → the OME-TIFFs from `mips/`. Leave image type auto-detected.
3. **Verify the pixel size QuPath read** matches step 2 (hover an image, or check
   `data/<n>/server.json`). If it disagrees, stop — every micron-denominated detection
   parameter downstream is scaled by that number.

**Create the QuPath project FIRST, before touching ABBA.** ABBA must import *from the
QuPath project*. Importing into ABBA via Bio-Formats permanently blocks the registration
export back to QuPath, and the only fix is re-registering from scratch.

---

## Step 5 — deploy the pipeline into the project  [SHELL]

```bash
$PY scripts/sync_project.py --project "M5 Hipp3 080326/M5 Hipp3 080326 QuPath"
```

Repo `scripts/` is the **source**; `<project>/scripts/` is a **deployed copy** (QuPath
can only run Groovy that lives inside the project). Never hand-copy. Groovy is
overwritten wholesale; `pipeline.yml` is *merged*, never overwritten, so per-slice-set
tuning survives a re-sync. Re-run this any time the repo scripts change.

It will report `pipeline.yml CREATED from repo root`. **Now edit two files.** This is
where every config bug on the pilots lived.

### 5a. `<project>/pipeline.yml`

- **`animal:`** — set it if this brain was imaged across more than one session. Two
  sessions of the same brain without a matching `animal:` key roll up as **two animals**.
  That happened on M5. If this is a single-session animal, leave it out.
- **`markers:` channels** — must match `server.json` channel names exactly.
- **`k_robust:` per marker** — ⚠ **the repo template ships the global 3.0 and does NOT
  carry the TdT override.** The operator's own by-eye call on M3 Hipp2 s3 was that
  TdT+ cells were being missed at 3.0, and TdT was set to `k_robust: 2.0`. If this set
  is the same staining and prep, copy that block across:

  ```yaml
    - name: "TdT"
      channel: "AF568-T2"
      compartment: "whole-cell"
      k_robust: 2.0        # operator's by-eye call, M3 Hipp2 s3, 2026-07-30
  ```

  This was caught by hand right before the M5 launch. Check it every time until the
  template carries it.
- **`detection_threshold.span_frac`** — leave at 0.25 for now; you tune it in step 8.

### 5b. `<project>/BraiAn.yml`

`sync_project` does **not** deploy this — it is per-acquisition.

**Copy it from the project that shares this dataset's ACQUISITION REGIME — same pixel
size and same Z depth — not from whichever project you looked at last.** The existing
regimes:

| regime | pixel µm | Z | copy `BraiAn.yml` from |
| --- | --- | --- | --- |
| M3 family | 0.4603569878472219 | 4 | `M3 Hipp2 072526/M3 Hipp2 072526 QuPath/` |
| M5 family | 0.690535481770835 | 2 | `M5 072526/M5 073026 QuPath/` |

Step 2 told you which row you are in. Getting this wrong is the single most likely
mistake at this step — it happened on M5 Hipp3 (2026-08-04), where M3's config was
copied onto 0.69 µm/px images and the notebook refused at calibration.

Then set **`requestedPixelSizeMicrons`** to this project's exact pixel size. Read it
straight off the image rather than retyping it:

```bash
$PY -c "import tifffile,re,sys; print(re.findall(r'PhysicalSizeX=\"([^\"]+)\"',
  tifffile.TiffFile(sys.argv[1]).ome_metadata)[0])" \
  "M5 Hipp3 080326/mips/M5-hipp3_s1_MIP.ome.tiff"
```

Paste the **full-precision** value. If it does not match, BraiAnDetect resamples and
every nucleus area comes out wrong.

The micron-denominated seeds (`sigmaMicrons`, `minAreaMicrons`, `maxAreaMicrons`,
`cellExpansionMicrons`) are in microns and nominally transfer between regimes — but a
nucleus at 0.69 µm/px is **~2.25× fewer pixels** than at 0.46. If segmentation looks
wrong on the calibration section, `sigmaMicrons` is the first knob, not the threshold.

Leave `classifiers: []` empty. That is deliberate — there is **one** classification
path, in `02_detect_classify.groovy` driven by `pipeline.yml`. Repopulating it makes
classification happen twice by two different rules.

### 5c. Validate

```bash
$PY scripts/validate_pipeline_config.py \
  --config "M5 Hipp3 080326/M5 Hipp3 080326 QuPath/pipeline.yml"
```

---

## Step 6 — ABBA atlas registration  [GUI]  ← the long one

Full click-path: **`docs/runbook/01-registration.md`**.

Short version — fully manual after DeepSlice, as of 2026-07-30:

1. Fiji → **Plugins → BIOP → Atlas → ABBA**. Import **from the QuPath project**.
2. **DeepSlice** for the initial AP position.
3. **Review/positioning mode** — fix position *and tilt*. Do tilt here, before any
   warping: lateral misalignment (LA, cortex edges) is a tilt problem, and no amount of
   spline control points fixes it.
4. **Affine tab** — match the slice to the overlay by hand: angle, X, Y, scale.
5. **Spline tab** — manual BigWarp to finalise.
6. Match against the **Label Borders** overlay. You are aligning boundaries by eye.
7. **Export registrations to the QuPath project.**

elastix is **standby, not retired** — it is out of the default path because manual
affine + BigWarp fit visibly better on M3 Hipp2, but on a cleanly mounted series the
automated chain may win again. If you reinstate it, the fixed channel must be atlas
**Nissl (Ch0)**, never Label Borders.

For caudal blocks (past the cerebellum) DeepSlice has little to work with. Image them in
**known cutting order** and use ABBA's "keep order + set spacing" so the easy sections
constrain the hard ones.

Registration is done when `ABBA-Transform-*.json` and `ABBA-RoiSet-*.zip` exist under
`<project>/data/<n>/`.

---

## Step 7 — load ABBA ROIs into QuPath  [SHELL]

```bash
$QP script -p "M5 Hipp3 080326/M5 Hipp3 080326 QuPath/project.qpproj" -s \
  "M5 Hipp3 080326/M5 Hipp3 080326 QuPath/scripts/01_load_abba_rois.groovy"
```

`-s` saves. Without it the work is discarded.

**This must run before detection.** Detection is confined to the atlas Root annotation;
without it, BraiAnDetect watersheds background across the whole image rectangle and
produces hundreds of thousands of spurious nuclei.

Unregistered entries are skipped loudly, by design — read the output rather than
assuming everything went in.

---

## Step 8 — calibrate the threshold on ONE section  [NOTEBOOK]

```bash
conda activate braian && jupyter lab
```

Open **`notebooks/01_calibrate.ipynb`**. Edit the `PARAMS` cell at the top:

```python
PARAMS = {
    "project": "M5 Hipp3 080326/M5 Hipp3 080326 QuPath",
    "slice": None,        # None -> first slice found; or the exact slice_id, e.g. "M5-hipp3_s3"
    "dry_run": True,      # expensive cells only PRINT their command until you flip this
    "detection": {},      # candidate BraiAn.yml overrides to try
    "lock": False,
}
```

`slice` is the **slice_id**, which is `<animal-prefix>_s<N>` from step 3 — not the scene
name and not the file name.

Then work down the notebook:

- **§3 plots the DAPI histogram with the cut drawn on it.** This is the thing to look at.
  The cut is `floor + span_frac × (bright_peak − floor)`, re-measured from *this
  section's own* histogram — never an absolute number. Raise `span_frac` for fewer,
  brighter nuclei; lower it to catch dimmer ones.
- Run the detection on that one slice (flip `dry_run` to `False`), then **open the slice
  in QuPath and look at the detections on the image.** This is the only step that
  actually validates anything. What you see outranks every expected band in the QC
  output.
- Iterate `sigmaMicrons` / `minAreaMicrons` / `maxAreaMicrons` / `span_frac` until the
  overlay looks right. `03-tuning.md` has each knob and its direction.

**Do not tune a parameter to move a number into an expected band.** The QC gates print
their evidence tier — `<anatomical>` (true regardless of acquisition), `<internal>`
(self-consistency), `<assumed>` (a band borrowed from elsewhere, never validated on our
data). Only the first two are grounds to change anything.

If calibration fails with *"single peak, no floor found"*, the section's histogram has
no separable background population. That is an acquisition problem, not a tuning
problem — a prominence sweep on M5c_s3/s4 gave thresholds from 1,073 to 6,328 with no
stable answer. Either re-image it or set that section by eye and record that you did.

---

## Step 9 — batch the whole set  [NOTEBOOK]

Open **`notebooks/02_batch.ipynb`**, set the same `"project"`, `"dry_run": False`,
`"skip_detection": False`. It runs, per section:

`run_braian_detection.groovy` → `02_detect_classify.groovy` → `03_export_region_table.groovy`

~20–40 min per section, CPU-bound. Start it and go image.

It writes to `<project>/results/`:

```
*__percell_export.tsv          one row per cell: class, LEAF region, area, centroid, anchor_mean
*__region_table.tsv            per-region counts
*__detection_threshold.tsv     the cut actually used, per section
```

Detection **aborts loudly and non-zero** if the threshold cannot be calibrated, rather
than falling back to a hardcoded value. An abort is information — read it.

---

## Step 10 — QC, then look again  [NOTEBOOK + GUI]

`02_batch.ipynb` runs the gates (`scripts/cockpit_checks.py`). They **advise, they never
block** — nothing is dropped for you.

Then open two or three sections in QuPath and look at the classified overlay. If you
want to see exactly which cells a `k_robust` change would flip:

```bash
$QP script -p "<project>/project.qpproj" -s "<project>/scripts/inspect_marker_band.groovy"
```

It tags the borderline cells with a *derived* class, so your existing classification
survives. (It used to overwrite classes and corrupted 27,632 cells on M3 Hipp2 before
that was fixed — if counts ever drop inexplicably, grep for stray `InspectBand` classes
first.)

---

## Step 11 — roll up to the animal  [NOTEBOOK or SHELL]

**`notebooks/03_animal.ipynb`**, or directly:

```bash
$PY scripts/cockpit_animal.py \
  --project "M5 Hipp3 080326/M5 Hipp3 080326 QuPath" \
  --regions "LA,BLA,CA1,CA3,SSp,MOp" \
  --out-dir results/animal
```

Add `--pool-same-animal` when several projects declare the same `animal:` key.
Add `--project` again for each additional project.

Counts are **pooled first, then every ratio recomputed** — never a mean of per-section
ratios.

Region names resolve through the project's **own** ontology JSON. Per-cell labels are
**leaf** regions, so a parent acronym like `STR` or `HY` matches nothing until it is
rolled down — `cockpit_regions.py` does that for you. Never hardcode an acronym list.

Chance baselines, if you want them:

```bash
$PY scripts/chance_methods.py --project "<project>" --plot results/chance_methods.png
```

Five definitions of chance side by side, so you can show a conclusion does not depend on
which one you picked.

---

## Step 12 — figures  [SHELL]

```bash
$PY scripts/figure_region_panels.py \
  --long results/animal/animal_region_long.csv \
  --out results/figures/M5_hipp3 --separate \
  --ontology "M5 Hipp3 080326/M5 Hipp3 080326 QuPath/allen_mouse_10um_java-Ontology.json" \
  --group-label "M5" --subtitle "6 sections · preliminary" \
  --ymax "overlap_above_chance=8,frac_tdt=0.15"
```

`--long` is `cockpit_animal.py`'s long table from step 11 — the figure script never
recomputes a metric, so the definitions live in one place. `--separate` writes one PNG
per panel into `--out` (treated as a directory) so every graph carries its own region
labels rather than only the bottom one. `--ontology` supplies the full region name
printed under each acronym.

`--ymax` takes `metric=value` pairs and locks that panel's y-limit. **Use the same
values across groups** — without it a lower-valued group's bars fill its own panel and
read as equal to a higher group's.

---

## The five things that cost the most time on the pilots

1. **Bio-Formats import into ABBA** → registration export permanently blocked. Always
   import *from the QuPath project*.
2. **Scene-prefix collision** → three CZIs each writing `s1` into one directory. Unique
   `--animal-prefix` per session.
3. **Missing `animal:` key** → one brain counted as three animals.
4. **Template `k_robust` not carrying the TdT override** → caught by hand, twice.
5. **A section imaged far outside the family** → `M5a_s1` at a bright peak of 253 vs
   ~5,000 for its siblings, which drove an apparent group effect that vanished on
   exclusion.

Number 5 is prevented at the scope, in 30 seconds, and nowhere else. Before you leave
each section: **is this section's DAPI bright-nuclei peak in family with the ones you
already imaged?** Target ≈ 2,000–4,000 (16-bit), background floor ≈ 150–250, ratio
≥ 12×, never clipping at 65,535. Full rationale and the per-section measured table are
in `ACQUISITION-CHECKLIST.md`.

---

## If you get stuck

| symptom | look at |
| --- | --- |
| a knob and which way to turn it | `docs/runbook/03-tuning.md` |
| ABBA click-path detail | `docs/runbook/01-registration.md` |
| QuPath detection detail | `docs/runbook/02-detection.md` |
| what the stages are and their status | `docs/pipeline-stages.yml` |
| acquisition targets and failure modes | `ACQUISITION-CHECKLIST.md` |
| where the data currently stands | `NEXT-SESSION.md` |

Every Python script here takes `--self-test` and `-h`. The self-test asserts what the
code actually does — if you doubt a script, run it.
