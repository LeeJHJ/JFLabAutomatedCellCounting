---
phase: 05-series-scaffolding-multi-scene-mip-batch-export-integrity
reviewed: 2026-07-19T14:38:23Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - czi_mip.py
  - scripts/03_export_val01_metrics.groovy
  - scripts/verify_export_integrity.py
findings:
  critical: 1
  warning: 3
  info: 4
  total: 8
status: issues_found
---

# Phase 05: Code Review Report

**Reviewed:** 2026-07-19T14:38:23Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the multi-scene CZI→MIP converter (`czi_mip.py`), the per-entry VAL-01 export Groovy script (`03_export_val01_metrics.groovy`), and the read-only export-integrity checker (`verify_export_integrity.py`). The code is generally careful — it carries explicit off-by-one guards, non-overlap assertions, a pixel-size round-trip check, and a final scene-count guard. However there is one data-integrity blocker in the scene identity path where `czi_mip.py` indexes `get_dims_shape()` by scene number in direct contradiction to its own documented warning about that call's behavior. Several warnings concern integrity guards implemented as `assert` (removable under `-O`), a latent dimension-extent miscount, and a filename-sanitization collision that can reintroduce the very cross-entry clobbering the export script was rewritten to fix.

Cross-file check: the `region_label` semantic asymmetry between the two Groovy TSV outputs (hemisphere-stripped per-cell vs. hemisphere-prefixed per-region) was traced into the downstream consumer `scripts/val01_metrics.py` (lines 135-154), which explicitly documents and compensates for it by joining on `acronym`. That is a handled contract, not a defect (noted as IN-02 for the maintenance trap only).

## Critical Issues

### CR-01: Scene identity record indexes `get_dims_shape()` by scene number, contradicting the file's own documented warning

**File:** `czi_mip.py:178,209`
**Issue:** `dims_by_scene = czi.get_dims_shape()` is indexed per scene at line 209: `M = dims_by_scene[scene_idx]["M"][1]`. This assumes `get_dims_shape()` returns one dict per scene, aligned to the bbox scene keys. But the module's own docstring (line 80) warns that `get_dims_shape()[0]['S']` is "silently wrong / returns 1 on multi-scene files with inconsistent per-scene shape," and line 163 treats the return value as a single aggregate dict (`dim0 = dims[0]`). These two usages are mutually contradictory:
- If `get_dims_shape()` returns a single aggregated dict (length 1) — the interpretation implied by line 80 and line 163 — then `dims_by_scene[scene_idx]` raises `IndexError` for every scene after scene 0. The crash occurs *after* scene 0's expensive MIP is written, leaving a partial output directory, and the final scene-count truncation guard (line 236) is never reached.
- If it returns a per-scene list, there is no guarantee its list index aligns with the bbox dict's scene keys, so `M` (tile count) can be reported for the wrong scene — silently corrupting the exact scene→file identity record (`_scene_identity_record`, the D-05 identity guard) this script exists to produce.

Either way the identity/tile-count metadata is unreliable, and the crash path halts the whole series conversion.
**Fix:** Do not re-index `get_dims_shape()` by scene. Derive the tile count from data actually read for this scene, or guard defensively:
```python
# Option A: count tiles per scene from the tile-info API instead of get_dims_shape()
# (aicspylibczi exposes per-region tile bounding boxes)
tile_bboxes = czi.get_mosaic_tile_bounding_boxes(S=scene_idx) if hasattr(
    czi, "get_mosaic_tile_bounding_boxes") else None
M = len(tile_bboxes) if tile_bboxes is not None else -1  # -1 = "unknown", never crash

# Option B: if the aggregate dict is the only reliable form, read M once, outside the loop
_agg = czi.get_dims_shape()
_agg0 = _agg[0] if isinstance(_agg, list) else _agg
M = _agg0.get("M", (0, -1))[1] - _agg0.get("M", (0, 0))[0]
```
Treat `M` as diagnostic-only and never let its retrieval crash the conversion of subsequent scenes.

## Warnings

### WR-01: Data-integrity guards implemented as bare `assert` — silently disabled under `python -O`

**File:** `czi_mip.py:99,202,230,236`
**Issue:** The scene-count truncation guard (line 236, "silent scene truncation"), the pixel-size round-trip check (line 230), the MIP-shape-vs-bbox check (line 202), and the multi-scene precondition (line 99) are all `assert` statements. Python run with `-O`/`-OO` strips every `assert`, so the very guards the docstring advertises as protecting against silent series corruption vanish, leaving corruption undetected. These are correctness invariants, not debug checks.
**Fix:** Convert integrity invariants to explicit raises:
```python
if len(written) != n_scenes:
    raise SystemExit(
        f"FATAL: expected {n_scenes} output MIPs, found {len(written)} "
        f"in {args.outdir} -- silent scene truncation")
```
Apply the same to the shape check and the OME-XML round-trip check.

### WR-02: Dimension extent read as tuple end (`[1]`) instead of extent (`[1] - [0]`)

**File:** `czi_mip.py:164-165,209`
**Issue:** `n_c = dim0.get("C", (0, 1))[1]` and `n_z = dim0.get("Z", (0, 1))[1]` (and `M = ...["M"][1]`) take the tuple's end index as the count. `get_dims_shape()` returns `(start, end)` per dimension; the true extent is `end - start`. This is correct only when `start == 0`. If any dimension has a nonzero start, `n_c`/`n_z` overcount, and `range(n_c)`/`range(n_z)` then request channel/z indices that do not exist (read failure), while the channel-count guard at line 172 compares against an inflated `n_c`.
**Fix:**
```python
def _extent(d, key):
    lo, hi = d.get(key, (0, 1))
    return hi - lo
n_c = _extent(dim0, "C")
n_z = _extent(dim0, "Z")
```

### WR-03: Filename sanitization can collapse distinct entries to one stem, reintroducing cross-entry clobbering

**File:** `scripts/03_export_val01_metrics.groovy:158-167`
**Issue:** The per-entry output stem is `entry.getImageName()` with the set `< > : " / \ | ? *` stripped. Two distinct project entries whose names differ only in stripped characters map to the same stem — e.g. `s1:A` and `s1/A` both become `s1A` — so the second entry's `${stem}__val01_percell_export.tsv` overwrites the first. This is exactly the "Run for project" clobbering regression the script was rewritten (D-06/D-07) to eliminate, just triggered by sanitization collision rather than a fixed filename. `verify_export_integrity.py` would not necessarily catch it: pairing still holds for the survivor, and Assertion 3 only fires when *all* row counts are identical.
**Fix:** Make collisions impossible or loud. Prefer the stable, unique entry ID over the display name, or detect collisions before writing:
```groovy
// Use the entry's unique ID (collision-free) as the stem, or append it:
def stem = entry != null ? entry.getID().replaceAll(invalidChars, '') : ...
// Or: after building `stem`, assert the target file does not already exist this run
if (percellFile.exists()) {
    throw new RuntimeException("EXP-02: stem '${stem}' collides with an existing "
        + "export this run -- sanitization mapped two entries to one filename")
}
```

## Info

### IN-01: `verify_export_integrity.py` clobbering guard false-positives when all entries share a row count

**File:** `scripts/verify_export_integrity.py:129-137`
**Issue:** Assertion 3 fails whenever every paired stem has an identical percell row count. Distinct real sections can legitimately produce the same detection count (particularly small or sparsely populated sections), producing a false FAIL that blocks a correct run. The docstring acknowledges this is a heuristic, but the failure is hard (exit 1).
**Fix:** Downgrade the all-identical case to a loud warning unless corroborated (e.g. also compare file mtimes or a content hash), or require identical counts *and* identical file sizes before failing.

### IN-02: `region_label` column carries different semantics across the two export files (handled downstream, but a maintenance trap)

**File:** `scripts/03_export_val01_metrics.groovy:139,193`
**Issue:** In the per-cell export, `region_label` is hemisphere-stripped (`regionLabel` closure, line 106-112) — bare acronym. In the per-region export, `region_label` retains the `Left:`/`Right:` prefix (line 193). A column with the same name means two different things across the paired files. This is currently correct only because `scripts/val01_metrics.py` (lines 135-154) documents the asymmetry and joins on `acronym` instead of `region_label`; a future consumer that joins on `region_label` directly would match zero rows.
**Fix:** No functional change required. Consider renaming the per-region column to `region_label_hemi` (or emitting the bare acronym in both) so the shared name cannot mislead a future reader.

### IN-03: `assert n_scenes >= 2` rejects legitimate single-scene CZIs and is also stripped under `-O`

**File:** `czi_mip.py:99`
**Issue:** `_preflight_scenes` (used by `--check-scenes` too) hard-asserts at least two scenes. A single-scene mosaic — a valid input for a one-off section — fails preflight even though the rest of the pipeline (loop over `sorted(bboxes)`) would handle it. Combined with WR-01, under `-O` this precondition disappears entirely.
**Fix:** Make it a soft, explicit check with a clear message, or gate it behind a flag; do not block a valid single-scene conversion.

### IN-04: Inconsistent line terminators between header and data rows

**File:** `scripts/03_export_val01_metrics.groovy:172,174,206,208`
**Issue:** Headers are appended with a literal `"\n"` while data rows use `String.format('...%n', ...)` (platform line separator). Harmless on this Linux box (both `\n`), but if the script ever runs on a platform where `%n` is `\r\n`, the header and body would use mixed terminators.
**Fix:** Use `"\n"` explicitly for the data rows too (`.append("\n")` or replace `%n` with `\n`) to guarantee uniform Unix line endings that the Python consumer expects.

---

_Reviewed: 2026-07-19T14:38:23Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
