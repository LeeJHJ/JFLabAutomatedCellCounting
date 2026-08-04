# Finish M5 Hipp3, then run M3 Str1

**Written 2026-08-04**, end of a session that did QC tooling, not data. Assumes no
memory of it. The full procedure is `docs/runbook/00-run-a-new-dataset.md` — this file
only records what is *specific to these two datasets* and does not repeat the steps.

```bash
cd ~/Analysis
PY=$HOME/miniforge3/envs/braian/bin/python
QP=$HOME/section-pipeline/tools/QuPath/bin/QuPath
```

---

## 0. Do this first — M5 Hipp3 is missing the TdT k override

`M5 Hipp3 080326/…QuPath/pipeline.yml` declares TdT with **no per-marker `k_robust`**,
so it falls through to the global `3.0`. Every other project on this machine carries
`2.0`:

| project | TdT `k_robust` |
| --- | --- |
| M3 Hipp1 072326 | 2.0 — "set 2026-08-01 to MATCH M3 Hipp2" |
| M3 Hipp2 072526 | 2.0 — operator's by-eye call, s3, 2026-07-30 |
| M5 073026 | 2.0 — "MUST match the M3 arm" |
| **M5 Hipp3 080326** | **absent → 3.0** |

This is the exact omission `00-run-a-new-dataset.md` step 5a warns about: the repo
template ships the global 3.0 and does not carry the override, so it has to be added by
hand on every new project. Higher `k` is a stricter cut, so M5 Hipp3 currently
**under-calls TdT+ and Double+** relative to all three other datasets, and is not
comparable to them.

It is possible this was deliberate. Nothing here checked it against the image, and the
operator's eye outranks this table — but if it was deliberate, write the reason into the
file, because every other project says why it chose 2.0 and this one says nothing.

```yaml
  - name: "TdT"
    channel: "AF568-T2"
    compartment: "whole-cell"
    k_robust: 2.0        # operator's by-eye call, M3 Hipp2 s3, 2026-07-30
```

**Cost to fix: low.** `k_robust` is read by `02_detect_classify.groovy`, not by
detection. Re-run `02` then `03` per section; the expensive detection stays.

**Do not edit it mid-batch.** A batch was running when this was written; changing the
file part-way gives one `k` for the sections already done and another for the rest,
which is worse than a consistent wrong one. Let it finish, then edit, then re-run.

---

## 1. M5 Hipp3 080326 — where it stands

Two sections, `M5-hipp3_s1` and `s2`. Both **registered** (`ABBA-Transform-*.json` +
`ABBA-RoiSet-*.zip` present under `data/1/` and `data/2/`), so steps 1–7 of the runbook
are done. Acquisition: 3 channels, 2 Z-planes, **0.6905355 µm/px** — the M5 regime.

The thresholds were set **by eye**, per slice, and both are correct as written:

```yaml
threshold_overrides:
  M5-hipp3_s1: {span_frac: 0.50}          # -> cut 206  (floor 41, bright 370)
  M5-hipp3_s2: {mode: absolute, absolute: 2900}
```

`s1`'s histogram is trimodal and the span rule locks onto two *background* peaks
(41 → 370), which is why `s2` had to be written as an absolute: 2,900 sits far above
that section's "bright peak" of 346, so no fraction can express it. Both values were
verified this session against the groovy's own calibration JSONs.

**Remaining:** confirm the batch produced exports for both sections, apply §0, re-run
`02` + `03`, then the animal roll-up. Nothing else is outstanding.

---

## 2. M3 Str1 080426 — starts at zero

Only `raw/M3 Str1 080426.czi` (11.4 GB) exists; `mips/` is empty and there is no QuPath
project. Pre-flight already run this session, so step 2 of the runbook is done:

```
5 scenes · 3 channels · 2 Z-planes · 0.6905355 µm/px · z-step 2 µm
3 overlapping scene-bbox pairs -> isolation resolved to `tiles` (automatic, no flag)
```

```bash
$PY czi_mip.py \
  --czi "M3 Str1 080426/raw/M3 Str1 080426.czi" \
  --outdir "M3 Str1 080426/mips" \
  --channels "AF568-T2" "AF488-T3" "DAPI-T4" \
  --animal-prefix M3-str1
```

Then runbook steps 4 onward. At step 5b, scaffold BraiAn.yml from the **M5 family**
regime — not M3's, despite the animal being M3:

```bash
$PY scripts/setup_braian_config.py --project "<project>" --scaffold --z-planes 2
```

### ⚠ M3 Str1 is in M5's acquisition regime, not M3's

| | pixel µm | Z |
| --- | --- | --- |
| M3 Hipp1 / M3 Hipp2 | 0.460357 | 4 |
| M5 073026, M5 Hipp3, **M3 Str1** | 0.6905355 | 2 |

Same animal as M3 Hipp1/Hipp2, different imaging. Per the standing rule — one
acquisition regime per comparison — **do not roll M3 Str1 up into animal `M3` with the
hippocampal sessions.** Pixel size and Z depth change what a cell physically *is*, so
area and expansion parameters do not carry across, and pooling would put the imaging
difference inside a single animal's number where nothing downstream can see it.

Striatum vs hippocampus are different regions, so no region-level comparison is directly
at risk. The exposure is the `animal:` key in `pipeline.yml`: leave it **unset** unless
someone decides otherwise and writes down why.

---

## 3. Hand-count QC — the harness is now complete, and unused

Built this session; **nobody has hand-counted anything yet.** Two `<anatomical>` gates
have flagged on every section ever run here (white matter denser than cortex; ventricles
far from empty), and until someone counts, "detection over-calls in white matter" stays
an inference from a ratio.

```
QuPath Script editor, slice open:   scripts/qc_handcount.groovy
                                    -> results/<image>__handcount.tsv
fill in the `human` column, then:   $PY scripts/qc_handcount.py --project "<project>"
```

Boxes are placed with a fixed seed, so a re-count samples the same places. A re-run will
not overwrite a sheet that already has human numbers in it.

Two things to know before spending the attention, both from `docs/runbook/04-qupath-gui.md`:

- The ventricle gate reads `regions.tsv`, written **before** `exclude_acronyms` drops
  `VS`. Measured on M5-hipp3_s1: 213 detections in VS per the gate, **0 cells** in
  `percell_export.tsv`. So that flag is true about detection and irrelevant to any
  number that gets reported.
- Three boxes inside VS held **zero** detections — the 213 are at the rim. The VS
  annotation includes its own wall (ependyma, SVZ), which is genuinely nucleated, so the
  gate's premise may be wrong as implemented.

The white-matter gate is the one worth settling, and `cc` + `Isocortex` must **both** be
counted — it is a ratio, and counting white matter alone cannot settle it.

---

## 4. Repo changes this session — one deploy still owed

Two commits, both green on `$PY scripts/smoke_test.py` (24/24):

- `ecdebcf` hand-count harness records human counts and computes machine/human
- `ea0f6bb` the threshold picker now emits cuts in the **pipeline's** endpoints

The second one matters if you use `notebooks/01_calibrate.ipynb` §3b. `span_frac` is a
number *plus the two endpoints it is measured against*, and the picker and the groovy
measure different ones on purpose (picker 256→5,632 on M5-hipp3_s1; groovy 41→370).
The picker used to write its own fraction into `pipeline.yml`, where the groovy
re-evaluated it against its peaks — an order-of-magnitude silent move. It now emits the
translated fraction, or an absolute when no fraction can express the cut.

M5 Hipp3's existing overrides are unaffected; they were already correct.

**Owed:** the new/changed Groovy has not been deployed into the two projects, because a
batch was reading from `<project>/scripts/` when the session ended.

```bash
$PY scripts/sync_project.py --project "M5 Hipp3 080326/M5 Hipp3 080326 QuPath"
```

Run it once nothing is in flight — check with `pgrep -af "QuPath script"` first.
