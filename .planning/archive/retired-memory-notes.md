# Retired Claude memory notes

These two notes were removed from Claude's live memory (`~/.claude/projects/-home-jflab-Analysis/memory/`) on 2026-07-10 to reduce per-session token load. They are archived here verbatim so they can be restored as memories later if the TRACR / LIF work resumes. Both relate to a side task (a registration-only favor for another lab), not the core M3 pipeline.

---

## 1. tracr-side-registration (was `project_tracr_registration.md`, type: project)

> Side task — quick Allen-CCF registration of another lab's Ai63TRACR LIF sections (registration-only, no detection)

Running in parallel with the main M3 section pipeline: a **quick registration favor for another lab**. Source files in `/home/jflab/Analysis/TRACR/` are Leica **LIF** (not CZI): `..._DAPI_wholebrain.lif` (5 whole coronal DAPI sections at 1.44 µm/px, single plane, + 160 unstitched 512² tiles Bio-Formats explodes into separate series) and `..._GFP.lif` (4 high-mag Alexa488+DAPI z-stacks of the LA region only, ~0.72 µm/px, with per-series-inconsistent channel order).

**Scope decided (2026-07-03): registration only** — register the 5 DAPI whole sections to Allen CCFv3, hand back ABBA transforms + RoiSet region annotations to the other lab. No cell detection, so channel-order and MIP issues are moot.

Purpose of the registration: a **viral-targeting anatomical reference** for the other lab (region outlines per section), not quantification.

**Done:** (1) extracted the 5 clean DAPI whole sections to `/home/jflab/Analysis/TRACR/registration_input/*.ome.tiff` (LZW, ~20 MB each, calibration verified) via bundled Bio-Formats; (2) **prebuilt the QuPath project headless** at `/home/jflab/Analysis/TRACR/TRACR_LA_Registration_070326/` — 5 entries, all type=Fluorescence, BioFormatsImageServer, 1.4444 µm/px verified. Built via `QuPath script` (v0.6.0); note `Project.getImageList()` not `imageList()`. The GFP file was left alone.

**Next (GUI, human):** open Fiji ▸ ABBA ▸ import from this QuPath project → DeepSlice → manual DV/ML tilt → export regions to QuPath. Caveat: the 5 sections are single slices from ~3 different animals (3-4, 1-2, 2-2), not one ordered brain — do NOT enforce even AP spacing in DeepSlice; take per-section predictions.

**Registration in progress (2026-07-06):** Hit ABBA "missing channels" errors at the BigWarp step — root cause was the registration dialog's moving-channel index; these DAPI sections are single-channel (index 0 only), so any carried-over M3 index (M3 DAPI = index 2) fails. Fix = set moving/slice channel to `0`, atlas channel to `0`. Registration was completed manually but was "rough"; quality per-section may need a second pass before final handoff.

---

## 2. lif-bioformats-extraction (was `reference_lif_bioformats.md`, type: reference)

> How to inspect/convert Leica LIF (or any proprietary microscopy file) into calibrated OME-TIFFs headlessly via Fiji's bundled Bio-Formats

Fiji at `$HOME/section-pipeline/tools/Fiji.app` bundles **Bio-Formats 8.5** (in `jars/`, plus a `jars/bio-formats/bio-formats-tools-8.0.1.jar`) and a JDK21 at `java/linux64/.../bin/java`. This is the same reader QuPath/ABBA use, so pixel calibration round-trips exactly.

**Slice a specific series → calibrated OME-TIFF** (e.g. one whole section out of a multi-series LIF):
```
JAVA=$FIJI/java/linux64/zulu*/bin/java
CP=$(find $FIJI/jars -name '*.jar' | tr '\n' ':')
$JAVA -cp "$CP" loci.formats.tools.ImageConverter -series N -overwrite -compression LZW in.lif out.ome.tiff
```
Convert class is `ImageConverter` (not `ImageConvert`). LZW is lossless; without it the OME-TIFF is written uncompressed (~4× bloat).

**Gotcha:** `loci.formats.tools.ImageInfo`'s metadata dump goes through SLF4J, which is NOP'd in this classpath, so it prints *nothing* to stdout. To inspect structure (series count, dims, Z/C/T, pixel size, channel names) instead run a Groovy script through `ImageJ-linux64 --headless` using `ImageReader` + `MetadataTools.createOMEXMLMetadata()` — kept at `scratchpad/lif_info.groovy`, driven by `-Dlif.path=...`.

Relevant when ingesting non-CZI formats; complements `czi_mip.py`. LIFs can also have per-series-inconsistent channel order (see the channel-order memory).
