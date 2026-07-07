# External Integrations

**Analysis Date:** 2026-06-30

## Reference Atlases

**Allen Mouse Brain Common Coordinate Framework v3 (CCFv3):**
- Provider: Allen Institute for Brain Science
- Role: the authoritative atlas for all region assignments and coordinate mapping
- Access: downloaded automatically on first use via `brainglobe-atlasapi` 2.3.1
- Atlas identifiers used: `allen_mouse_10um_java` (QuPath/ABBA), `allen_mouse_25um` (brainrender)
- Local cache: `~/` (brainglobe default atlas storage, downloaded once, then offline)
- Ontology file present: `allen_mouse_10um_java-Ontology.json` (checked into QuPath project dirs)
- Both ABBA and brainrender reference CCFv3 — coordinates must be exported in microns (not pixels) to ensure point clouds land correctly

**ABBA Transform Format:**
- File: `ABBA-Transform-allen_mouse_10um_java.json` (per-image, stored in QuPath project `data/<n>/`)
- File: `ABBA-RoiSet-allen_mouse_10um_java.zip` (atlas region ROIs for a registered section)
- These are produced by ABBA in Fiji and consumed by the ABBA QuPath extension

## External Web Services

**DeepSlice Online (primary, no local setup required):**
- URL: `https://www.deepslice.com.au` (web UI)
- Role: predicts anatomical Z-position (bregma coordinate) and DV/ML tilt angles from section images
- Used as: upload section MIP → download JSON prediction → import into ABBA for initial registration
- No API key required; manual upload/download workflow
- Local fallback: `deepslice` conda env (DeepSlice 1.2.8 / TensorFlow 2.21.0) exists but DeepSlice online is preferred for speed on this CPU-only machine

**GitHub Releases (install-time only):**
- QuPath releases: `https://api.github.com/repos/qupath/qupath/releases/tags/v0.6.0`
- elastix releases: `https://api.github.com/repos/SuperElastix/elastix/releases/tags/5.2.0`
- Used only during initial `SECTION_PIPELINE_SETUP (1).md` install; not a runtime dependency

**Fiji Update Sites (install-time only):**
- PTBIOP update site: provides ABBA plugin and BigWarp for Fiji
- Activated once via `Help > Update... > Manage update sites` in the Fiji GUI

**QuPath Extension Catalogs (install-time only):**
- `https://github.com/BIOP/qupath-biop-catalog` — provides ABBA, Warpy, Image Combiner Warpy
- `https://github.com/carlocastoldi/qupath-extension-braian-catalog` — provides BraiAnDetect

## Data Storage

**Local Filesystem (all primary storage):**
- Raw input: CZI mosaic files, e.g., `Automated Cell Counting/M3 Hippocampus 20x 062026.czi`
- Processed MIPs: OME-TIFF files, e.g., `Automated Cell Counting/M3_20x_MIP.ome.tiff`
- QuPath projects: `*.qpproj` JSON files with per-image data in `data/<n>/` subdirectories
- Registration outputs: `ABBA-Transform-*.json`, `ABBA-RoiSet-*.zip`, `landmarks.csv`
- Classifiers: `classifiers/object_classifiers/*.json` (threshold-based, single measurement)
- Elastix registration logs: `elastix_spline_backup/` directories (debugging artifacts)

**No cloud storage, databases, or OMERO server** — all data is local NVMe storage.

## Acquisition Hardware Integration

**Zeiss ZEN (Windows microscope PC — separate machine, not installed here):**
- Produces: Airyscan-processed, tile-stitched, z-projected OME-TIFF or CZI files
- Transfer: manual file copy to this Linux analysis desktop
- No network API; transfer is offline file handoff
- Channel order note: `aicspylibczi` reads CZI channels in a different order than the ZEN metadata declares — always pass explicit channel names when calling `czi_mip.py` (see `feedback_channel_order.md`)
- Standard channel order as acquired: DAPI (Ch0), Fos-AF488 (Ch1), TdTomato-AF568 (Ch2)

## Authentication & Identity

- No authentication systems in use; all tools are local or public web services without login (DeepSlice online requires no account)

## Monitoring & Observability

**Error Tracking:** None — debugging via manual inspection of terminal output and QuPath/Fiji logs.

**Logs:**
- QuPath: internal log visible in the QuPath log panel
- elastix: writes `elastix.log` and `IterationInfo.*.txt` files to the working directory (examples in `elastix_spline_backup/`)
- Python scripts: stdout/stderr to terminal; `czi_mip.py` uses `print(..., flush=True)` for progress

## CI/CD & Deployment

**No CI/CD pipeline.** This is a single-workstation research analysis environment. There is no automated testing, container build, or deployment process.

## Webhooks & Callbacks

**Incoming:** None

**Outgoing:** None

## Environment Configuration

**Required env vars (set in `~/.bashrc`):**
- `LD_LIBRARY_PATH=$HOME/section-pipeline/tools/elastix/lib` — must be set or elastix fails to load shared libraries

**No `.env` files** — environment configuration is embedded in `~/.bashrc` and conda activation.

**Tool paths (hardcoded in scripts or configured once via GUI):**
- `$HOME/section-pipeline/tools/QuPath/bin/QuPath`
- `$HOME/section-pipeline/tools/Fiji.app/ImageJ-linux64`
- `$HOME/section-pipeline/tools/elastix/bin/elastix`
- `$HOME/section-pipeline/tools/elastix/bin/transformix`
- DeepSlice conda env prefix: `/home/jflab/miniforge3/envs/deepslice` (configured in Fiji ABBA GUI)

---

*Integration audit: 2026-06-30*
