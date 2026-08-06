#!/usr/bin/env python3
"""orphan_markers.py -- count marker-positive cells the anchor channel MISSED.

WHY THIS EXISTS
    Every other check on the anchor cut is a proxy. Total density asks whether a
    slice resembles our accepted ones; grey contrast asks whether structures still
    differ; both are `<internal>` and neither knows what a cell is. The operator's
    actual criterion is narrower and much more consequential (2026-08-06, looking at
    M5-hipp3_s1 at span_frac 0.25):

        a bright Fos or TdT cell with NO nucleus contour around it is a positive
        deleted outright, and engrams are sparse enough that those are the
        observations we can least afford to lose

    This module measures exactly that. It finds marker blobs on the marker channels
    themselves, independently of any nucleus detection, and reports what fraction have
    no detected nucleus under them. That number is the one honest tuning target we
    have for the anchor cut, because it is the only one that does not reduce to
    "does this run look like our other runs".

WHY IT IS NOT A CLASSIFIER, AND MUST NOT BECOME ONE
    Nothing here may feed back into counts. The project rule is nucleus-anchored
    colocalization only (CLAUDE.md, locked): a cell is Fos+/TdT+ iff the DETECTED
    NUCLEUS contains the marker signal. Rescuing an orphan blob into the counts would
    be exactly the proximity heuristic that rule forbids, and it would bias the
    numerator of every enrichment ratio upward. An orphan is a DIAGNOSTIC that the
    anchor cut is too strict -- the fix is to move the anchor cut and re-detect, so
    the nucleus is found properly and the normal classification path picks it up.

THE ASYMMETRY THIS IS MEANT TO ARBITRATE
    Under-detection deletes positives -- unrecoverable, and biased toward dim cells.
    Over-detection adds marker-NEGATIVE objects, which inflate the denominator of
    P(marker+|anchor) and therefore INFLATE every enrichment ratio -- recoverable in
    principle, but silently wrong if unnoticed. So neither direction is free, and the
    orphan rate is what lets the two be traded off against something measured rather
    than assumed.

METHOD, and its limits stated plainly
    1. Marker blobs: per-channel robust cut (median + k*1.4826*MAD over the whole
       channel, the same robust statistic the pipeline uses for marker positivity),
       then connected components at or above `--min-blob-um2`.
    2. A blob is MATCHED if any detected nucleus centroid lies within `--match-um` of
       the blob centroid, else ORPHAN.
    3. `--match-um` defaults to 6.0 um, roughly one nucleus radius (nuclei here run
       27-32 um^2, i.e. ~3.0 um radius) plus slack for a whole-cell TdT blob whose
       centroid sits off the nucleus. Sweep it with --match-sweep before trusting a
       single value.

    Limits: this uses nucleus CENTROIDS, not nucleus ROIs, because the per-cell export
    carries centroids only -- so matching is a distance test, not containment. A blob
    on a nucleus whose centroid is more than --match-um away reads as an orphan. That
    makes the orphan count an UPPER bound. Treat differences between configs as the
    signal, not the absolute number.

Usage:
    python3 scripts/orphan_markers.py --mip <file.ome.tiff> --percell <export.tsv>
    python3 scripts/orphan_markers.py --project "<dir>" --run-dir <archived results>
    python3 scripts/orphan_markers.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_MATCH_UM = 6.0
DEFAULT_MIN_BLOB_UM2 = 8.0
DEFAULT_K = 3.0


def robust_cut(plane: np.ndarray, k: float = DEFAULT_K,
               sample: int = 4_000_000) -> float:
    """median + k * 1.4826 * MAD, the same robust statistic the pipeline's marker
    positivity uses. Sampled, because a 161-megapixel channel does not need every
    pixel to estimate a median and the full sort is the slow step."""
    flat = plane.ravel()
    if flat.size > sample:
        idx = np.linspace(0, flat.size - 1, sample).astype(np.int64)
        flat = flat[idx]
    med = float(np.median(flat))
    mad = float(np.median(np.abs(flat - med)))
    return med + k * 1.4826 * mad


def find_blobs(plane: np.ndarray, cut: float, pixel_um: float,
               min_blob_um2: float = DEFAULT_MIN_BLOB_UM2) -> np.ndarray:
    """Centroids (x_px, y_px) of connected components at or above `cut`.

    scipy.ndimage rather than skimage: it is present in the `braian` env, it labels
    in one pass, and center_of_mass over the label set is enough -- shape statistics
    are not needed for a presence/absence test.
    """
    from scipy import ndimage

    mask = plane >= cut
    if not mask.any():
        return np.empty((0, 2), dtype=float)
    lbl, n = ndimage.label(mask)
    if n == 0:
        return np.empty((0, 2), dtype=float)
    min_px = max(1, int(round(min_blob_um2 / (pixel_um ** 2))))
    sizes = np.bincount(lbl.ravel())
    keep = np.nonzero(sizes >= min_px)[0]
    keep = keep[keep != 0]                      # label 0 is background
    if keep.size == 0:
        return np.empty((0, 2), dtype=float)
    cen = ndimage.center_of_mass(mask, lbl, keep)
    return np.array([(c[1], c[0]) for c in cen], dtype=float)   # (x, y)


def orphan_rate(blobs: np.ndarray, nuclei_xy: np.ndarray, pixel_um: float,
                match_um: float = DEFAULT_MATCH_UM) -> tuple[int, int]:
    """(orphans, total) -- blobs with no nucleus centroid within `match_um`."""
    if blobs.size == 0:
        return 0, 0
    if nuclei_xy.size == 0:
        return len(blobs), len(blobs)
    from scipy.spatial import cKDTree

    tree = cKDTree(nuclei_xy)
    dist, _ = tree.query(blobs, k=1)
    return int((dist * pixel_um > match_um).sum()), int(len(blobs))


def channel_index(mip: Path, want: str) -> int | None:
    """Index of a named channel in the OME-XML, or None. Channel ORDER in the file is
    authoritative -- never the order the names appear in pipeline.yml (see
    feedback_channel_order: aicspylibczi's read order differs from the metadata's)."""
    import tifffile

    with tifffile.TiffFile(mip) as tf:
        desc = tf.pages[0].description or ""
    names = []
    for chunk in desc.split("<Channel")[1:]:
        if 'Name="' in chunk:
            names.append(chunk.split('Name="')[1].split('"')[0])
    for i, n in enumerate(names):
        if n.strip().lower() == want.strip().lower():
            return i
    return None


def analyse(mip: Path, percell: Path, markers: dict[str, str], pixel_um: float,
            k: float = DEFAULT_K, match_um: float = DEFAULT_MATCH_UM,
            min_blob_um2: float = DEFAULT_MIN_BLOB_UM2,
            match_sweep: bool = False) -> pd.DataFrame:
    import tifffile

    cells = pd.read_csv(percell, sep="\t")
    nuclei = cells[["centroid_x_px", "centroid_y_px"]].to_numpy(dtype=float)
    print(f"  {len(nuclei):,} detected nuclei")

    rows = []
    for name, chan in markers.items():
        idx = channel_index(mip, chan)
        if idx is None:
            print(f"  {name}: channel '{chan}' not in OME-XML -- skipped")
            continue
        plane = tifffile.imread(mip, key=idx)
        cut = robust_cut(plane, k)
        blobs = find_blobs(plane, cut, pixel_um, min_blob_um2)
        orph, tot = orphan_rate(blobs, nuclei, pixel_um, match_um)
        pct = 100.0 * orph / tot if tot else float("nan")
        print(f"  {name:5} ch{idx} cut={cut:8,.0f}  blobs={tot:7,}  "
              f"orphan={orph:6,} ({pct:5.1f}%)")
        row = {"marker": name, "channel": chan, "cut": cut,
               "blobs": tot, "orphans": orph, "orphan_pct": pct}
        if match_sweep:
            for m in (3.0, 4.5, 6.0, 8.0, 12.0):
                o, t = orphan_rate(blobs, nuclei, pixel_um, m)
                row[f"orphan_pct@{m:g}um"] = 100.0 * o / t if t else float("nan")
        rows.append(row)
        del plane
    return pd.DataFrame(rows)


def _self_test() -> None:
    """Synthetic: nuclei on a grid, marker blobs on a known subset plus a known number
    placed deliberately far from any nucleus. The orphan count must recover them."""
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + msg)
        if not cond:
            failures.append(msg)

    pixel_um = 0.69
    rng = np.random.default_rng(3)
    nuclei = np.array([(x, y) for x in range(50, 950, 40) for y in range(50, 950, 40)],
                      dtype=float)

    plane = np.zeros((1000, 1000), dtype=np.uint16)
    plane += rng.integers(90, 110, plane.shape).astype(np.uint16)

    on_nucleus = nuclei[:30]
    for x, y in on_nucleus:                       # blobs sitting ON a nucleus
        plane[int(y) - 3:int(y) + 4, int(x) - 3:int(x) + 4] = 5000
    far = np.array([(x, y) for x, y in zip(range(70, 190, 20), [990] * 6)], dtype=float)
    for x, y in far:                              # blobs far from every nucleus
        plane[int(y) - 3:int(y), int(x) - 3:int(x) + 4] = 5000

    cut = robust_cut(plane, k=3.0)
    # background is uniform 90-110 (MAD ~5), so the cut lands just above it -- the
    # point is that it separates background from the 5,000 signal, not that it is large
    check(110 < cut < 5000, f"robust cut separates background from signal ({cut:,.0f})")

    blobs = find_blobs(plane, cut, pixel_um, min_blob_um2=8.0)
    check(len(blobs) == 36, f"finds every blob and no background ({len(blobs)} of 36)")

    orph, tot = orphan_rate(blobs, nuclei, pixel_um, match_um=6.0)
    check(tot == 36, f"total blobs reported ({tot})")
    check(orph == 6, f"recovers exactly the 6 planted orphans (got {orph})")

    # the planted orphans sit ~41 um from the nearest nucleus, so the radius has to
    # clear that before they match -- monotonic, but not at any arbitrary radius
    check(orphan_rate(blobs, nuclei, pixel_um, 40.0)[0] <= orph,
          "orphan count is monotonic non-increasing in the match radius")
    check(orphan_rate(blobs, nuclei, pixel_um, 60.0)[0] < orph,
          "a radius clearing the planted distance matches them")

    o_none, t_none = orphan_rate(blobs, np.empty((0, 2)), pixel_um)
    check(o_none == t_none == 36, "no nuclei at all -> every blob is an orphan")

    e_o, e_t = orphan_rate(np.empty((0, 2)), nuclei, pixel_um)
    check((e_o, e_t) == (0, 0), "no blobs -> (0, 0), not a divide-by-zero")

    print("\nALL SELF-TESTS PASSED" if not failures
          else f"\n{len(failures)} SELF-TEST FAILURE(S)")
    sys.exit(1 if failures else 0)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--mip", type=Path, default=None, help="MIP OME-TIFF for one slice")
    p.add_argument("--percell", type=Path, default=None,
                   help="that slice's __percell_export.tsv")
    p.add_argument("--pixel-um", type=float, default=None,
                   help="pixel size; read from BraiAn.yml when --project is given")
    p.add_argument("--project", type=Path, default=None,
                   help="QuPath project dir (for pipeline.yml markers + pixel size)")
    p.add_argument("--k", type=float, default=DEFAULT_K,
                   help=f"robust multiplier for the blob cut (default {DEFAULT_K})")
    p.add_argument("--match-um", type=float, default=DEFAULT_MATCH_UM,
                   help=f"blob-to-nucleus match radius (default {DEFAULT_MATCH_UM})")
    p.add_argument("--min-blob-um2", type=float, default=DEFAULT_MIN_BLOB_UM2,
                   help=f"smallest accepted blob (default {DEFAULT_MIN_BLOB_UM2})")
    p.add_argument("--match-sweep", action="store_true",
                   help="also report the orphan rate at several match radii")
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
    if not args.mip or not args.percell:
        print("need --mip and --percell (or --self-test)")
        sys.exit(2)

    markers = {"Fos": "AF488-T3", "TdT": "AF568-T2"}
    pixel_um = args.pixel_um
    if args.project:
        import yaml
        doc = yaml.safe_load((Path(args.project) / "pipeline.yml").read_text())
        markers = {m["name"]: m["channel"] for m in doc.get("markers", [])} or markers
        if pixel_um is None:
            b = yaml.safe_load((Path(args.project) / "BraiAn.yml").read_text())
            pixel_um = (b["channelDetections"][0]["parameters"]
                        ["requestedPixelSizeMicrons"])
    if pixel_um is None:
        print("need --pixel-um or --project (pixel size must never be defaulted)")
        sys.exit(2)

    print(f"orphan markers -- {args.mip.name}")
    print(f"  pixel {pixel_um} um  k={args.k}  match {args.match_um} um  "
          f"min blob {args.min_blob_um2} um^2")
    df = analyse(args.mip, args.percell, markers, pixel_um, args.k,
                 args.match_um, args.min_blob_um2, args.match_sweep)
    if args.match_sweep and not df.empty:
        print()
        print(df.filter(regex="marker|@").to_string(index=False))


if __name__ == "__main__":
    main()
