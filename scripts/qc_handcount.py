#!/usr/bin/env python3
"""qc_handcount.py -- read back the hand-count tally sheet and settle a QC gate.

THE OTHER HALF OF scripts/qc_handcount.groovy. The groovy lays boxes inside named
regions, counts the machine's detections in each, and writes

    <project>/results/<image>__handcount.tsv
        region  box  side_um  machine  machine_per_mm2  human

with `human` blank. A person fills that column in by eye. This script reads it back
and computes the one number the gates cannot: **machine / human**.

WHY THAT NUMBER AND NOT THE DENSITIES
  Two <anatomical> gates flag on every section ever run here -- white matter denser
  than cortex, and ventricles well above empty. <anatomical> means "true regardless
  of acquisition", so a violation is a real defect rather than a band to re-tune.
  But a gate compares the machine to an EXPECTATION. Hand counting compares the
  machine to the TISSUE, which is tier-1 evidence (SEEN) and outranks both.

  The distinction it buys is the one that decides what to do:

      machine/human ~ 1.0 everywhere    detection is sound; the gate's BAND is wrong
      machine/human >> 1 in white matter real over-detection -- tune the cut
      machine/human >> 1 in ventricle    haze segmented, or anchor bleed-through

  And the trap it avoids: the white-matter gate is a RATIO, wm density / cortex
  density. Raising the threshold to "fix" it can remove real cortical nuclei faster
  than it removes white-matter haze, making the ratio worse while improving the
  segmentation. Per-region machine/human is immune to that -- it is measured against
  the tissue in each region separately -- so it is reported FIRST here, and the
  ratio-of-ratios only after.

POOLING
  Per region, the aggregate is (sum machine) / (sum human) across boxes, not the mean
  of per-box ratios. A ratio of rates must be count-weighted; averaging per-box ratios
  lets a box with two nuclei in it swing the answer as hard as a box with forty.

Usage:
    python3 qc_handcount.py --project "<project dir>"
    python3 qc_handcount.py --project "<project dir>" --sheet <one tsv>
    python3 qc_handcount.py --self-test
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cockpit_checks as cc  # noqa: E402  gate constants -- do not fork them here

# Below this many pooled counts the ratio is too noisy to read as anything but a
# gross effect. Poisson relative SE on machine/human is ~sqrt(1/m + 1/h); at m=h=20
# that is 0.32, so a 2x over-count is unmistakable and a 10% one is invisible. That
# is exactly the resolution the harness claims, and this constant is where it lives.
MIN_POOLED_FOR_FINE = 20


@dataclass
class RegionCount:
    region: str
    boxes: int
    machine: int
    human: int
    area_mm2: float

    @property
    def ratio(self) -> float:
        """machine/human. Undefined when the eye found nothing -- that case is not a
        ratio, it is a categorical statement (see `verdict`), and reporting inf or 0
        here would launder it into a number someone could average."""
        if self.human <= 0:
            return float("nan")
        return self.machine / self.human

    @property
    def rel_se(self) -> float:
        """Poisson relative standard error on the ratio."""
        if self.machine <= 0 or self.human <= 0:
            return float("nan")
        return math.sqrt(1.0 / self.machine + 1.0 / self.human)

    @property
    def machine_per_mm2(self) -> float:
        return self.machine / self.area_mm2 if self.area_mm2 > 0 else float("nan")

    @property
    def human_per_mm2(self) -> float:
        # human == 0 is a MEASUREMENT (the eye looked and found none), not a missing
        # value -- only rows with a filled-in cell reach this object at all. Returning
        # nan for it would erase the single most informative ventricle result.
        return self.human / self.area_mm2 if self.area_mm2 > 0 else float("nan")


def find_sheets(project: Path) -> list[Path]:
    results = Path(project) / "results"
    if not results.is_dir():
        return []
    # The `.new.tsv` companions are machine-only re-runs; the sheet a human wrote in
    # is the plain one, and it is the only one worth reading back.
    return sorted(p for p in results.glob("*__handcount.tsv")
                  if not p.name.endswith("__handcount.new.tsv"))


def read_sheet(path: Path) -> list[RegionCount]:
    """Pool a tally sheet's boxes into one row per region.

    Rows with an empty `human` cell are dropped from BOTH sides of the ratio -- a box
    that was not counted must not contribute its machine count to the numerator, or a
    partially-counted region reads as a wild over-count.
    """
    lines = [ln.rstrip("\n") for ln in Path(path).read_text().splitlines() if ln.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    try:
        i_reg, i_side = header.index("region"), header.index("side_um")
        i_mach, i_hum = header.index("machine"), header.index("human")
    except ValueError as exc:
        raise ValueError(f"{path.name}: not a handcount sheet ({exc})") from exc

    pooled: dict[str, RegionCount] = {}
    for line in lines[1:]:
        f = line.split("\t")
        if len(f) <= i_hum or not f[i_hum].strip():
            continue
        region = f[i_reg].strip()
        side = float(f[i_side])
        rc = pooled.setdefault(region, RegionCount(region, 0, 0, 0, 0.0))
        rc.boxes += 1
        rc.machine += int(float(f[i_mach]))
        rc.human += int(float(f[i_hum].strip()))
        rc.area_mm2 += (side * side) / 1e6
    return list(pooled.values())


def uncounted_regions(path: Path) -> list[str]:
    """Regions present on the sheet with no human number anywhere."""
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    if not lines:
        return []
    header = lines[0].split("\t")
    i_reg, i_hum = header.index("region"), header.index("human")
    seen: dict[str, bool] = {}
    for line in lines[1:]:
        f = line.split("\t")
        region = f[i_reg].strip()
        has = len(f) > i_hum and bool(f[i_hum].strip())
        seen[region] = seen.get(region, False) or has
    return [r for r, has in seen.items() if not has]


def verdict(rc: RegionCount, th: cc.GateThresholds) -> str:
    """What this region's ratio means, in the vocabulary of the gates."""
    is_wm = rc.region in th.white_matter_acronyms
    is_vs = rc.region in th.ventricle_acronyms
    if rc.human == 0:
        # The eye found nothing. No ratio exists, but this is the strongest possible
        # result either way -- never report it as "not counted".
        if rc.machine == 0:
            return "both found none"
        return ("OVER-DETECTING -- the eye found none here"
                + (" (ventricle haze or anchor bleed)" if is_vs else ""))
    coarse = rc.machine + rc.human < 2 * MIN_POOLED_FOR_FINE

    if rc.ratio >= 1.5:
        if is_vs:
            return "OVER-DETECTING -- haze segmented, or anchor bleed into the ventricle"
        if is_wm:
            return "OVER-DETECTING in white matter -- the gate is right; tune the cut"
        return "OVER-DETECTING"
    if rc.ratio <= 0.67:
        return "UNDER-DETECTING -- real nuclei are being missed here"
    if coarse:
        return "agrees within the resolution of this many boxes"
    return "agrees -- detection is sound in this region"


def report(sheets: list[Path], th: cc.GateThresholds | None = None) -> int:
    th = th or cc.DEFAULT_THRESHOLDS
    any_counted = False
    for path in sheets:
        regions = read_sheet(path)
        pending = uncounted_regions(path)
        print("=" * 78)
        print(path.name.replace("__handcount.tsv", ""))
        print("=" * 78)
        if not regions:
            print("  no human counts recorded yet -- fill the 'human' column in")
            print(f"  {path}")
            if pending:
                print(f"  regions waiting: {', '.join(sorted(pending))}")
            print()
            continue
        any_counted = True

        print(f"  {'region':<12} {'boxes':>5} {'machine':>8} {'human':>7} "
              f"{'mach/human':>11} {'+-':>6}   verdict")
        by_name = {}
        for rc in sorted(regions, key=lambda r: r.region):
            by_name[rc.region] = rc
            se = rc.rel_se
            print(f"  {rc.region:<12} {rc.boxes:>5} {rc.machine:>8} {rc.human:>7} "
                  f"{rc.ratio:>11.2f} {se:>6.2f}   {verdict(rc, th)}")
        print()
        print("  +- is the Poisson relative SE on the ratio. Above ~0.2 the sheet can")
        print("  separate a 2x over-count from agreement, but not a 10% one.")

        if pending:
            print(f"  still uncounted: {', '.join(sorted(pending))}")

        # ── The gate, recomputed on the hand counts ──────────────────────────────
        cortex = [by_name[a] for a in th.cortex_acronyms if a in by_name]
        wm = [by_name[a] for a in th.white_matter_acronyms if a in by_name]
        print()
        print(f"  <anatomical> white-matter gate  (expects wm/cortex <= "
              f"{th.white_matter_ratio_max:g})")
        if not cortex or not wm:
            print("    needs a white-matter region AND a cortical reference, both counted.")
            print("    Counting white matter alone cannot settle a ratio gate.")
        else:
            cx = cortex[0]
            for w in wm:
                m_ratio = (w.machine_per_mm2 / cx.machine_per_mm2
                           if cx.machine_per_mm2 > 0 else float("nan"))
                h_ratio = (w.human_per_mm2 / cx.human_per_mm2
                           if cx.human_per_mm2 > 0 else float("nan"))
                print(f"    {w.region}/{cx.region}   machine {m_ratio:.2f}   "
                      f"BY EYE {h_ratio:.2f}")
                if not math.isfinite(h_ratio):
                    continue
                # These two questions are INDEPENDENT and both get answered. An
                # earlier version made them an either/or and reported "the band is
                # wrong" for a fixture where the machine was over-detecting 3x in cc
                # -- because the eye happened to also exceed the band. It can be true
                # both that the tissue breaks the band AND that detection is broken.
                over_detecting = math.isfinite(w.ratio) and w.ratio >= 1.5
                band_wrong = h_ratio > th.white_matter_ratio_max
                if over_detecting:
                    print(f"      Detection: machine/human is {w.ratio:.2f} in "
                          f"{w.region} -- real over-detection.")
                    print(f"      Tune, then re-count {cx.region} too: a stricter cut "
                          "that drops cortical")
                    print("      nuclei makes this RATIO worse while improving the "
                          "segmentation.")
                else:
                    print(f"      Detection: machine/human is {w.ratio:.2f} in "
                          f"{w.region} -- sound.")
                if band_wrong:
                    print(f"      Band: the TISSUE exceeds {th.white_matter_ratio_max:g} "
                          "by eye, so the gate's expectation")
                    print("      does not hold for this prep. Never tune to move this "
                          "number.")
                elif m_ratio > th.white_matter_ratio_max:
                    print("      Band: the eye stays inside it and the machine does "
                          "not -- the gate is")
                    print("      firing on something real.")
                else:
                    print("      Band: both inside it on this section.")

        vs = [by_name[a] for a in th.ventricle_acronyms if a in by_name]
        print()
        # ventricle_density_max is None while the gate is REPORT-ONLY (it was 500.0 and
        # flagged 16/16 slices, so the band was disarmed rather than left to fire on a
        # defect nobody had diagnosed). Formatting None with :g crashed here -- the
        # header must survive a disarmed gate, because a hand count is exactly the
        # evidence that would re-arm it.
        if th.ventricle_density_max is None:
            print("  <anatomical> ventricle gate  (REPORT-ONLY: no band set, because the "
                  "machine number")
            print("     flagged 16/16 slices and the cause was never diagnosed. Your eye "
                  "count is what")
            print("     would settle whether to re-arm it.)")
        else:
            print(f"  <anatomical> ventricle gate  (expects <= "
                  f"{th.ventricle_density_max:g}/mm^2)")
        if not vs:
            print("    no ventricle boxes counted.")
        else:
            for v in vs:
                print(f"    {v.region}   machine {v.machine_per_mm2:,.0f}/mm^2   "
                      f"BY EYE {v.human_per_mm2:,.0f}/mm^2  ({v.human} in "
                      f"{v.boxes} box(es))")
                if v.human > 0:
                    print("      The lumen is not empty by eye either -- the VS annotation")
                    print("      includes its own wall (ependyma, SVZ), which is genuinely")
                    print("      nucleated. That is a fact about the gate's premise.")
                elif v.machine > 0:
                    print("      Machine finds nuclei where the eye finds none: over-detection.")
                else:
                    print("      Both empty.")
        print()

    if not any_counted:
        print("Nothing to report until a human column is filled in.")
        return 1
    print("Ratios are tier-1 (SEEN). Where they disagree with a gate, the gate loses.")
    return 0


# ── self-test ───────────────────────────────────────────────────────────────────

def read_sheet_text(text: str, tmpdir) -> dict[str, RegionCount]:
    """Parse sheet content from a string. Test helper, kept next to the parser it
    exercises so a change to the format cannot silently pass the fixtures."""
    p = Path(tmpdir) / "_scratch__handcount.tsv"
    p.write_text(text)
    return {r.region: r for r in read_sheet(p)}


def _capture(fn) -> str:
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn()
    return buf.getvalue()


def _self_test() -> None:
    import tempfile

    failures = []

    def check(cond, label):
        print(("  ok   " if cond else "  FAIL ") + label)
        if not cond:
            failures.append(label)

    th = cc.DEFAULT_THRESHOLDS
    # The band-branch fixtures below are about BRANCH LOGIC -- "is a wrong band
    # reported alongside over-detection, or instead of it" -- not about whatever
    # white_matter_ratio_max happens to be today. Pinning it here decouples them from
    # the production value, which moved 0.6 -> 1.60 on 2026-08-05 and silently
    # falsified two checks that were testing something else entirely.
    th_band = replace(th, white_matter_ratio_max=0.6)
    print("qc_handcount self-test")
    print(f"  (band-branch fixtures pinned at white_matter_ratio_max="
          f"{th_band.white_matter_ratio_max:g}; production is "
          f"{th.white_matter_ratio_max:g})")

    with tempfile.TemporaryDirectory() as tmp:
        results = Path(tmp) / "results"
        results.mkdir()

        # (a) A sheet where the machine agrees with the eye everywhere, and white
        # matter is genuinely as dense as cortex. The gate flags; the eye says the
        # band is wrong. This is the case the harness exists to distinguish.
        sheet = results / "slice_a__handcount.tsv"
        sheet.write_text(
            "region\tbox\tside_um\tmachine\tmachine_per_mm2\thuman\n"
            "cc\t1\t100\t30\t3000\t29\n"
            "cc\t2\t100\t28\t2800\t27\n"
            "Isocortex\t1\t150\t60\t2666\t61\n"
            "Isocortex\t2\t150\t58\t2577\t57\n"
            "VS\t1\t40\t0\t0\t0\n"
        )
        regions = {r.region: r for r in read_sheet(sheet)}
        check(regions["cc"].machine == 58 and regions["cc"].human == 56,
              "boxes pool by region")
        check(abs(regions["cc"].ratio - 58 / 56) < 1e-9, "ratio is count-weighted, not box-mean")
        check(abs(regions["Isocortex"].area_mm2 - 2 * 0.0225) < 1e-9,
              "area sums from the side actually used per box")
        check("agrees" in verdict(regions["cc"], th), "1.04 reads as agreement")

        # The point of the fixture: wm/cortex by eye is ~1.05, over the pinned band,
        # while machine/human is ~1.0. Detection is sound, the band is not.
        hand_ratio = regions["cc"].human_per_mm2 / regions["Isocortex"].human_per_mm2
        check(hand_ratio > th_band.white_matter_ratio_max,
              f"fixture reproduces the real situation (eye says {hand_ratio:.2f}x cortex)")
        check(abs(regions["cc"].ratio - 1.0) < 0.1,
              "...while the machine matches the eye -- band wrong, detection fine")

        # (b) Genuine over-detection in white matter only.
        sheet_b = results / "slice_b__handcount.tsv"
        sheet_b.write_text(
            "region\tbox\tside_um\tmachine\tmachine_per_mm2\thuman\n"
            "cc\t1\t100\t60\t6000\t20\n"
            "Isocortex\t1\t150\t60\t2666\t59\n"
            "VS\t1\t40\t12\t7500\t0\n"
        )
        rb = {r.region: r for r in read_sheet(sheet_b)}
        check("OVER-DETECTING in white matter" in verdict(rb["cc"], th),
              "3x in cc reads as over-detection, named as white matter")
        check("agrees" in verdict(rb["Isocortex"], th),
              "cortex still agrees -- the defect is localised, which is the tunable case")
        check(not math.isfinite(rb["VS"].ratio),
              "human=0 gives no ratio rather than a division by zero")

        # REGRESSION (a): human == 0 is a measurement, not a missing value. The first
        # version reported "not counted" and nan/mm^2 for the ventricle box the eye
        # had actually looked at and found empty -- erasing the strongest result the
        # sheet can carry.
        check("OVER-DETECTING" in verdict(rb["VS"], th),
              "eye found none + machine found 12 reads as over-detection, not 'not counted'")
        check(rb["VS"].human_per_mm2 == 0.0,
              "...and an eye-counted zero is 0/mm^2, not nan")
        rb_empty = read_sheet_text(
            "region\tbox\tside_um\tmachine\tmachine_per_mm2\thuman\n"
            "VS\t1\t40\t0\t0\t0\n", tmp)["VS"]
        check(verdict(rb_empty, th) == "both found none",
              "machine 0 + eye 0 is agreement, not over-detection")

        # REGRESSION (b): over-detection and a wrong band are INDEPENDENT findings.
        # Fixture (b) has 3x over-detection in cc AND an eye ratio above 0.6; the
        # first version reported only "the band is wrong" and dropped the defect.
        out = _capture(lambda: report([sheet_b], th_band))
        check("real over-detection" in out,
              "3x in cc is reported even though the eye also exceeds the band")
        check("does not hold for this prep" in out,
              "...and the band finding is reported alongside it, not instead of it")

        # (c) Uncounted rows must not leak their machine counts into the numerator.
        sheet_c = results / "slice_c__handcount.tsv"
        sheet_c.write_text(
            "region\tbox\tside_um\tmachine\tmachine_per_mm2\thuman\n"
            "cc\t1\t100\t30\t3000\t29\n"
            "cc\t2\t100\t28\t2800\t\n"
            "Isocortex\t1\t150\t60\t2666\t\n"
        )
        rc = {r.region: r for r in read_sheet(sheet_c)}
        check(rc["cc"].machine == 30 and rc["cc"].boxes == 1,
              "a box with no human number is dropped from BOTH sides")
        check("Isocortex" not in rc, "a fully uncounted region does not appear")
        check(uncounted_regions(sheet_c) == ["Isocortex"],
              "...but is reported as still waiting")

        # (d) Small-N honesty: 3 vs 3 must not be read as agreement to 10%.
        sheet_d = results / "slice_d__handcount.tsv"
        sheet_d.write_text(
            "region\tbox\tside_um\tmachine\tmachine_per_mm2\thuman\n"
            "cc\t1\t40\t3\t1875\t3\n"
        )
        rd = read_sheet(sheet_d)[0]
        check("within the resolution" in verdict(rd, th),
              "tiny counts are called out as coarse rather than as agreement")
        check(rd.rel_se > 0.5, "...and carry a visible standard error")

        # (e) Discovery skips the machine-only .new companion.
        (results / "slice_a__handcount.new.tsv").write_text("region\tbox\n")
        found = [p.name for p in find_sheets(Path(tmp))]
        check("slice_a__handcount.new.tsv" not in found,
              "re-run companions are not mistaken for the human's sheet")
        check(len(found) == 4, "all four real sheets discovered")

        # (f) Gate constants come from cockpit_checks, not a fork.
        check(th.white_matter_ratio_max == cc.DEFAULT_THRESHOLDS.white_matter_ratio_max,
              "gate thresholds are imported, never redefined here")

        print("\n---- report on fixture (b) ----")
        report([sheet_b], th)

    print(f"\n{'FAILED: ' + '; '.join(failures) if failures else 'all checks passed'}")
    if failures:
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("--project", type=Path, default=None,
                   help="QuPath project directory (the one holding results/)")
    p.add_argument("--sheet", type=Path, default=None,
                   help="a single __handcount.tsv, instead of scanning the project")
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if not a.self_test and a.project is None and a.sheet is None:
        p.error("--project or --sheet is required unless --self-test is set")
    return a


def main() -> int:
    a = parse_args()
    if a.self_test:
        _self_test()
        return 0
    sheets = [a.sheet] if a.sheet else find_sheets(a.project)
    if not sheets:
        print(f"no __handcount.tsv found under {a.project}/results/")
        print("Run scripts/qc_handcount.groovy on a slice in QuPath first.")
        return 1
    return report(sheets)


if __name__ == "__main__":
    sys.exit(main())
