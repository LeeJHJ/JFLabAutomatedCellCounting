# Runbook

The full operator tutorial for this pipeline (czi → MIP → ABBA registration →
BraiAnDetect → classify → export → per-region table) lives in
[`docs/`](docs/index.md), rendered as a searchable MkDocs Material site.

- **Preview locally:** `pip install -r requirements-docs.txt && mkdocs serve`,
  then open <http://127.0.0.1:8000>.
- **Read online:** once published (`mkdocs gh-deploy`, an opt-in manual step —
  see the "Publish this tutorial" section of `docs/index.md`), the tutorial is
  available at the GitHub Pages URL for this repo.

`docs/` is the single source of truth; this file is only a pointer so the
repo landing page finds a runbook.

## Counting inside ROIs you draw, without an atlas

A parallel route for images you want counts from but would never register: draw
ROIs in QuPath, run one script, get CSVs. No ABBA, no registration, no
`BraiAn.yml`. It reuses the registered route's segmentation, threshold rule,
compartment measures and marker cut — so the numbers mean the same thing — and
stores settings **per image**, because images counted this way arrive at
different magnifications, Z depths and intensities.

Everything for it lives in [`ROI Counting/`](ROI%20Counting/README.md) — scripts,
notebook and runbook in one folder. Start at its `README.md`.

## Starting on a new brain / new slice-set

The two steps that are easy to miss, and that everything else depends on:

**1. Deploy the pipeline into the QuPath project.** QuPath can only run scripts that
live inside the project, so the repo's `scripts/` must be copied in. Do not do this by
hand — it also removes retired scripts and adds any config block the current scripts
require, without touching this project's own marker set:

```bash
conda run -n braian python3 scripts/sync_project.py --project "<project dir>"
conda run -n braian python3 scripts/sync_project.py --all --dry-run   # preview everything
```

Then edit `<project>/pipeline.yml` so `anchor.channel` and `markers[].channel` match
the channel names in that project's images **exactly** (they appear in `server.json`),
and verify:

```bash
conda run -n braian python3 scripts/validate_pipeline_config.py --config "<project>/pipeline.yml"
```

**2. Calibrate the detection threshold, looking at the histogram.** The anchor cut is
relative (`floor + span_frac × (bright_peak − floor)`, re-derived per section) so it
transfers across acquisitions — but confirm where it lands on a new slice-set before a
batch run. Run `scripts/calibrate_threshold.groovy` in QuPath on one slice (read-only,
safe to repeat), then plot it in `notebooks/01_calibrate.ipynb` §3, or:

```bash
conda run -n braian python3 scripts/cockpit_threshold.py --project "<project dir>" --plots
```

Raise `span_frac` for a stricter cut (fewer, brighter nuclei); lower it to catch dimmer
nuclei. Do **not** switch to `mode: "absolute"` for a series — it pins the cut to one
section's intensity scale.

