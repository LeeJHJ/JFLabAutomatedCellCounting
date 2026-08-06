#!/usr/bin/env python3
"""marker_only_qa.py -- count Fos and TdT on their OWN channels, and their overlap.

THIS DELIBERATELY BREAKS THE NUCLEUS-ANCHORED RULE. Say so everywhere.

    Operator call, 2026-08-06: "override the nucleus anchored rule and also compute
    detections for tdtomato and fos+, just clearly stating that its not dapi-based,
    and also compute overlap stating that its not dapi based, this will primarily be
    for quality assurance, ensuring that we are getting similar amounts of doubles"

CLAUDE.md locks colocalization to nucleus-anchored: a cell is Fos+/TdT+/Double+ iff the
DETECTED NUCLEUS contains the marker signal, never a proximity or overlap heuristic.
That rule is not repealed. This module is a SECOND, INDEPENDENT measurement standing
beside it, for the specific job of checking it -- which is a normal and good thing to
have, and is only dangerous if the two are ever confused. So:

  * every output is prefixed `mo_` (marker-only) and lands in
    <project>/results/<image>__markeronly_QA.tsv, never in the region table
  * nothing here is per-region, per-animal, or aggregatable. It is a whole-section
    sanity number and it must not enter any group comparison or enrichment ratio
  * "mo_double" is NOT a double-positive CELL COUNT. It is co-located marker SIGNAL.
    There is no nucleus in this measurement, so there is no cell -- two adjacent cells
    and one double-labelled cell are indistinguishable to it

WHAT IT IS ACTUALLY GOOD FOR
    The DAPI-anchored counts can only be as good as the segmentation, and on
    M5-hipp3_s1 the segmentation is demonstrably losing nuclei that clear every
    threshold (see orphan_markers.py: 100% of orphan sites clear both the anchor cut
    and minArea by ~5x, so they are lost at the watershed). That opens a specific
    question this answers: is the double+ RATE distorted by those losses?

        mo_double / mo_tdt  ~=  DAPI-anchored Double+ / TdT+     segmentation loss is
                                                                 roughly unbiased
        the two diverge                                          the loss is selective,
                                                                 and by how much

    A ratio, not a count, is the comparable quantity -- the absolute numbers cannot
    match, because one counts cells and the other counts signal.

OVERLAP GEOMETRY
    Fos is nuclear and TdT fills the whole cell (CLAUDE.md, operator call 2026-07-25),
    so the containment test is asymmetric and matches that: a Fos blob counts as double
    when its CENTROID falls inside a TdT mask. Centroid-in-mask, not mask-intersects-
    mask -- a large TdT cell brushing a neighbouring Fos nucleus would satisfy the
    latter, which is exactly the proximity artifact the nucleus-anchored rule exists to
    avoid, and it would inflate mo_double.

Usage:
    python3 scripts/marker_only_qa.py --project "<dir>" --mip <file.ome.tiff>
    python3 scripts/marker_only_qa.py --project "<dir>" --mip <f> --k-fos 3.0 --k-tdt 2.0
    python3 scripts/marker_only_qa.py --self-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import orphan_markers as om   # noqa: E402  -- robust_cut / find_blobs / channel_index

BANNER = ("NOT DAPI-ANCHORED -- marker-channel detections and co-located signal, for "
          "QA only. Not cell counts. Never aggregate, never compare groups with these.")


def masks_and_blobs(plane: np.ndarray, k: float, pixel_um: float,
                    min_blob_um2: float, max_blob_um2: float | None = None
                    ) -> tuple[np.ndarray, np.ndarray, float]:
    """(mask, blob centroids, cut) for one marker channel."""
    cut = om.robust_cut(plane, k)
    blobs = om.find_blobs(plane, cut, pixel_um, min_blob_um2)
    if max_blob_um2 is not None and len(blobs):
        # A blob far larger than any cell is a sheet of autofluorescence or a fibre
        # bundle, not an object worth counting. Applied to the CENTROID list only --
        # the mask keeps everything, because for the containment test a big TdT region
        # is still legitimately TdT-positive territory.
        from scipy import ndimage
        lbl, _ = ndimage.label(plane >= cut)
        sizes = np.bincount(lbl.ravel()) * pixel_um * pixel_um
        keep = [i for i, (x, y) in enumerate(blobs)
                if sizes[lbl[min(int(y), lbl.shape[0] - 1),
                             min(int(x), lbl.shape[1] - 1)]] <= max_blob_um2]
        blobs = blobs[keep] if keep else np.empty((0, 2))
    return plane >= cut, blobs, cut


def double_by_containment(fos_blobs: np.ndarray, tdt_mask: np.ndarray) -> int:
    """Fos blobs whose centroid falls inside the TdT mask. See OVERLAP GEOMETRY."""
    if fos_blobs.size == 0:
        return 0
    h, w = tdt_mask.shape
    xs = np.clip(fos_blobs[:, 0].astype(int), 0, w - 1)
    ys = np.clip(fos_blobs[:, 1].astype(int), 0, h - 1)
    return int(tdt_mask[ys, xs].sum())


def compare_to_anchored(mo: dict, percell: Path | None) -> pd.DataFrame:
    """The only comparison that means anything: RATE against RATE."""
    rows = [{"quantity": "mo_double / mo_tdt (marker-only, signal)",
             "value": mo["mo_double"] / mo["mo_tdt"] if mo["mo_tdt"] else float("nan")}]
    if percell is not None and Path(percell).exists():
        df = pd.read_csv(percell, sep="\t")
        cls = df["class"].astype(str)
        tdt = int(cls.str.contains("TdT").sum() + cls.str.contains("Double").sum())
        dbl = int(cls.str.contains("Double").sum())
        rows.append({"quantity": "Double+ / TdT+ (DAPI-anchored, cells)",
                     "value": dbl / tdt if tdt else float("nan")})
        rows.append({"quantity": "  DAPI-anchored TdT+ (incl. Double+)", "value": float(tdt)})
        rows.append({"quantity": "  DAPI-anchored Double+", "value": float(dbl)})
    return pd.DataFrame(rows)


def _self_test() -> None:
    failures: list[str] = []

    def check(cond: bool, msg: str) -> None:
        print(("  ok    " if cond else "  FAIL  ") + msg)
        if not cond:
            failures.append(msg)

    px = 0.69
    rng = np.random.default_rng(5)
    fos = (rng.integers(90, 110, (600, 600))).astype(np.uint16)
    tdt = (rng.integers(90, 110, (600, 600))).astype(np.uint16)

    # 12 TdT cells; the first 5 also carry a Fos nucleus at their centre (true doubles),
    # and 4 further Fos nuclei sit well away from any TdT cell (Fos-only).
    tdt_centres = [(60 + 90 * i, 100) for i in range(6)] + [(60 + 90 * i, 300) for i in range(6)]
    for x, y in tdt_centres:
        tdt[y - 12:y + 13, x - 12:x + 13] = 6000
    for x, y in tdt_centres[:5]:
        fos[y - 4:y + 5, x - 4:x + 5] = 6000
    for i in range(4):
        fos[500 - 4:500 + 5, 60 + 90 * i - 4:60 + 90 * i + 5] = 6000

    tdt_mask, tdt_blobs, _ = masks_and_blobs(tdt, 3.0, px, 8.0)
    fos_mask, fos_blobs, _ = masks_and_blobs(fos, 3.0, px, 8.0)
    check(len(tdt_blobs) == 12, f"finds all 12 TdT objects ({len(tdt_blobs)})")
    check(len(fos_blobs) == 9, f"finds all 9 Fos objects ({len(fos_blobs)})")

    dbl = double_by_containment(fos_blobs, tdt_mask)
    check(dbl == 5, f"recovers exactly the 5 planted doubles (got {dbl})")

    far = double_by_containment(np.array([[500.0, 500.0]]), tdt_mask)
    check(far == 0, "a Fos blob outside every TdT cell is not a double")

    check(double_by_containment(np.empty((0, 2)), tdt_mask) == 0, "no Fos blobs -> 0")

    mo = {"mo_fos": 9, "mo_tdt": 12, "mo_double": 5}
    cmp = compare_to_anchored(mo, None)
    check(abs(cmp["value"].iloc[0] - 5 / 12) < 1e-9, "reports the RATE, not the count")

    print("\nALL SELF-TESTS PASSED" if not failures
          else f"\n{len(failures)} SELF-TEST FAILURE(S)")
    sys.exit(1 if failures else 0)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter,
                                epilog=__doc__)
    p.add_argument("--project", type=Path, default=None)
    p.add_argument("--mip", type=Path, default=None)
    p.add_argument("--percell", type=Path, default=None,
                   help="DAPI-anchored per-cell export, to compare RATES against")
    p.add_argument("--k-fos", type=float, default=3.0)
    p.add_argument("--k-tdt", type=float, default=2.0,
                   help="TdT separates less cleanly; the pipeline uses 2.0 for it too")
    p.add_argument("--min-blob-um2", type=float, default=8.0)
    p.add_argument("--max-blob-um2", type=float, default=400.0)
    p.add_argument("--pixel-um", type=float, default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--self-test", action="store_true")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.self_test:
        _self_test()
    if not args.mip:
        print("need --mip (or --self-test)")
        sys.exit(2)

    import tifffile
    import yaml

    pixel_um, channels = args.pixel_um, {"Fos": "AF488-T3", "TdT": "AF568-T2"}
    if args.project:
        doc = yaml.safe_load((args.project / "pipeline.yml").read_text())
        channels = {m["name"]: m["channel"] for m in doc.get("markers", [])} or channels
        if pixel_um is None:
            b = yaml.safe_load((args.project / "BraiAn.yml").read_text())
            pixel_um = b["channelDetections"][0]["parameters"]["requestedPixelSizeMicrons"]
    if pixel_um is None:
        print("need --pixel-um or --project")
        sys.exit(2)

    print("=" * 78)
    print(BANNER)
    print("=" * 78)
    print(f"{args.mip.name}   pixel {pixel_um} um   k_fos={args.k_fos} k_tdt={args.k_tdt}")

    out = {}
    masks = {}
    for name, k in (("TdT", args.k_tdt), ("Fos", args.k_fos)):
        idx = om.channel_index(args.mip, channels[name])
        if idx is None:
            print(f"  {name}: channel '{channels[name]}' absent -- aborting")
            sys.exit(1)
        plane = tifffile.imread(args.mip, key=idx)
        mask, blobs, cut = masks_and_blobs(plane, k, pixel_um,
                                           args.min_blob_um2, args.max_blob_um2)
        masks[name] = mask
        out[f"mo_{name.lower()}"] = len(blobs)
        out[f"mo_{name.lower()}_cut"] = cut
        if name == "Fos":
            out["mo_double"] = double_by_containment(blobs, masks["TdT"])
        print(f"  mo_{name.lower():4} cut={cut:9,.0f}  objects={len(blobs):7,}")
        del plane

    print(f"  mo_double (Fos centroid inside a TdT region) = {out['mo_double']:,}")
    print("\nRATE comparison -- the only comparable quantity (counts cannot match: "
          "one counts cells, the other signal)")
    print(compare_to_anchored(out, args.percell).to_string(index=False))

    dest = args.out
    if dest is None and args.project:
        dest = args.project / "results" / f"{args.mip.stem}__markeronly_QA.tsv"
    if dest:
        with open(dest, "w") as fh:
            fh.write(f"# {BANNER}\n")
            fh.write("\t".join(out) + "\n")
            fh.write("\t".join(str(v) for v in out.values()) + "\n")
        print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
