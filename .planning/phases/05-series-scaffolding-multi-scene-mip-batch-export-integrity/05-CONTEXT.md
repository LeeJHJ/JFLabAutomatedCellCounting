# Phase 5: Series Scaffolding — Multi-Scene MIP + Batch-Export Integrity - Context

**Gathered:** 2026-07-18
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish data integrity at both ends of the wBA1-3 series before it runs:

1. **CONV-01/CONV-02** — Convert `-001-07_processed.czi` into **5** identity-verified section MIP OME-TIFFs (one per scene), no scene fusion, each carrying physical pixel size in embedded OME-XML.
2. **EXP-02** — Fix `03_export_val01_metrics.groovy` so a "Run for project" across all 5 QuPath entries writes 5 distinct per-entry outputs with no cross-section TSV truncation.

**All work is scriptable — no GUI dependency.** This phase clarifies HOW to implement CONV-01/CONV-02/EXP-02; it does not add new capabilities. Requirements are locked in `.planning/REQUIREMENTS.md` (CONV-01, CONV-02, EXP-02).

**Grounded during discussion (metadata probe of the real CZI):** the processed CZI has **exactly 5 scenes** (S indices 0–4; per-scene tile counts M = 141/152/161/151/161; Z=4, C=3). The "6 Scenes" in the merged OME-TIFF filename is a red herring — that merged file is unusable and out of scope. `get_all_mosaic_scene_bounding_boxes()` was confirmed to work on the real file, so success-criterion #4's smoke test is effectively already green (re-run it inside the plan for the record).
</domain>

<decisions>
## Implementation Decisions

### Scene-identity verification artifact (CONV-02)
- **D-01:** Per scene, emit **both** a downsampled thumbnail PNG (for visual eyeball verification, in the spirit of v1.0's overlay PNGs) **and** a printed text record (bbox coords, tile count M, dims). Belt-and-suspenders against a silent scene→section shuffle.
- **D-02:** The identity artifact (text + thumbnail label) MUST print **both** the raw 0-based scene key (`0..4`) **and** the human-facing 1-based label (`s1..s5`) — see D-05. This keeps the 0/1-based off-by-one from ever hiding a shuffle.

### AP-order handling
- **D-03:** **Preserve raw scene index only; make NO anterior→posterior claim at conversion time.** Scene acquisition order is not assumed to equal anatomical AP order. DeepSlice sorts AP in Phase 6. CONV-02's job is scene→physical-section identity, not AP ordering.

### Output filename convention (the 5 MIP OME-TIFFs)
- **D-04:** Pattern: **`wBA1-3_s{N}_MIP.ome.tiff`** with **1-based** `N` (`s1`..`s5`). Animal prefix `wBA1-3`. This filename becomes each section's identity through the whole series (QuPath entries, downstream exports).
- **D-05:** ⚠ **Off-by-one guard.** The filename is 1-based (`s1..s5`) but the Python scene loop is 0-based (`0..4`): `s{N}` = scene loop index + 1. Because ROADMAP success-criterion #2 says "scene index written verbatim into the filename," the mapping must be unambiguous: the per-scene text/PNG record (D-01/D-02) prints the raw 0-based scene bbox key alongside the `s{N}` filename label, so `s1` is provably scene-0, `s5` is provably scene-4. Do not let the +1 translation live only implicitly in the loop.

### EXP-02 fix strategy
- **D-06:** Disambiguate the 5 entries' outputs by deriving the output filename **stem from the QuPath image/entry name** (sanitized), all files **flat in `results/`**. The entry name is already each section's identity, so outputs are self-describing. e.g. `results/wBA1-3_s1__val01_percell_export.tsv`, `results/wBA1-3_s1__val01_region_area.tsv`.
- **D-07:** Both TSVs (`val01_percell_export` and `val01_region_area`) get the per-entry stem. Preserve the exact column contract `scripts/val01_metrics.py` parses (do not rename columns). The per-run truncate/overwrite semantics stay, but now scoped to a unique per-entry filename so entries no longer clobber each other.

### Claude's Discretion
- Thumbnail channel/size (DAPI vs composite, downsample factor) and exact text-record fields beyond {bbox, M tile count, dims} — pick sensible defaults.
- Sanitization rule for turning an entry name into a filesystem-safe stem (whitespace/`:`/`/` handling).
- Per-scene MIP memory strategy (per-channel/per-Z streaming vs whole-scene) — implementation detail; keep memory bounded on the 16 GB input as the existing `czi_mip.py` already does.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Conversion (CONV-01 / CONV-02)
- `czi_mip.py` — current single-scene MIP converter to extend for per-scene output. Note the locked channel-order override (`--channels "TdTomato-AF568" "Fos-AF488" "DAPI"`) and the OME-XML pixel-size embedding idiom. Currently hardcodes M3 channel names in OME-XML (`DAPI`/`Fos-EGFP`/`TdTom-Cy3`) and single-file `F_IN`/`F_OUT` — both must generalize.
- `.planning/REQUIREMENTS.md` — CONV-01/CONV-02/EXP-02 exact wording; data spec for `-001-07_processed.czi` (5 scenes, Z=4, C=3, 0.69 µm/px, channels `AF568-T2`/`AF488-T3`/`DAPI-T4`).
- Data path: `Automated Cell Counting/wBA Sungmo/-001-07_processed.czi` (16 GB, use the **_processed** file — NOT the 32 GB `..._Merged.ome.tiff`, which fuses scenes and does not project Z).

### Export (EXP-02)
- `scripts/03_export_val01_metrics.groovy` — canonical export script to fix; the truncation bug is the fixed output filenames (`val01_percell_export.tsv` / `val01_region_area.tsv`) being overwritten per entry on "Run for project". Deploy convention: author in canonical `scripts/`, hard-copy byte-identically into `<QuPath project>/scripts/` (dual-location).
- `scripts/val01_metrics.py` — downstream consumer; the TSV **column names are the contract** — do not rename.

### Cross-cutting
- `CLAUDE.md` / `.claude/CLAUDE.md` — micron-export rule, channel-order fix, CPU-only + version pins.
- `.planning/STATE.md` §Critical Risks — "Multi-scene CZI scene→section mapping untested" (CR this phase mitigates) and "Multi-entry export truncation (EXP-02)".
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `czi_mip.py` MIP core (per-channel read → `np.max` over Z → `np.stack` (C,Y,X)) and the OME-XML builder are directly reusable; the change is wrapping them in a per-scene loop keyed on `get_all_mosaic_scene_bounding_boxes()` + `read_mosaic(region=bbox, C=, Z=)` so scenes are read separately instead of the whole fused mosaic.
- Pixel-calibration read idiom in `03_export_val01_metrics.groovy` (server `PixelCalibration` with hard-coded fallback) is the shared convention across scripts.

### Established Patterns
- Scene loop is **0-based** in Python; filenames are **1-based** (`s{N}`) per D-04 — the +1 must be explicit and logged (D-05).
- Export scripts are "Run for project" (human-run) and currently assume a single active entry — the EXP-02 fix must make the output path a function of the current entry, evaluated per-entry inside the project run.

### Integration Points
- The 5 MIP OME-TIFFs become QuPath project entries feeding Phase 6 (registration) and Phase 8 (classification).
- EXP-02 is sequenced here (not at aggregation) because per-entry non-truncated exports are a **blocking prerequisite for AGG-01 in Phase 10**.
</code_context>

<specifics>
## Specific Ideas

- Filename spec is concrete: `wBA1-3_s1_MIP.ome.tiff` … `wBA1-3_s5_MIP.ome.tiff` (1-based).
- Per-entry export example: `results/wBA1-3_s1__val01_percell_export.tsv` (entry-name stem, flat in `results/`).
- Scene→file mapping recorded verbatim: `s1`=scene-0 … `s5`=scene-4, printed in both the text record and PNG label.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope (AP ordering explicitly deferred to Phase 6 / DeepSlice per D-03; that is a sequencing decision, not new scope).
</deferred>

---

*Phase: 5-series-scaffolding-multi-scene-mip-batch-export-integrity*
*Context gathered: 2026-07-18*
