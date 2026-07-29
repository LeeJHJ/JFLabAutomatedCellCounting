#!/usr/bin/env python3
"""validate_pipeline_config.py — fail-loud validator + contract printer for pipeline.yml.

Reads the sidecar pipeline config (D-14, `pipeline.yml`) and, from that config alone,
derives the SHARED CONTRACT every downstream groovy/python consumer must conform to:

  1. the per-marker background-subtracted measurement-key string
     (``"<compartment-label>: <channel> mean (bg-sub)"``) each classifier will write/read
     (compartment-label is Nucleus/Cytoplasm/Cell for nuclear/cytoplasmic/whole-cell);
  2. the PathClass vocabulary (``"<marker>+"`` per declared non-anchor marker, plus
     ``"Double+"`` ONLY when >=2 non-anchor markers are declared -- D-03);
  3. the per-slice table column set, built purely by iterating the declared markers
     (never a fixed Fos/TdT list -- D-04).

Fails loud (non-zero exit, clear message naming the offending key) on any missing,
mistyped, or invalid-value key -- so a malformed config is caught before any groovy/
python consumer runs against it (T-06.1-01/02).

Usage (from the Analysis root, braian env):
  conda run -n braian python scripts/validate_pipeline_config.py --config pipeline.yml
  conda run -n braian python scripts/validate_pipeline_config.py --self-test
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# D-14: BraiAnDetect detection params that MUST NOT appear in this sidecar config
# (they stay in BraiAn.yml). Checked defensively at the top level of the config.
_FORBIDDEN_DETECTION_KEYS = (
    "sigmaMicrons", "minAreaMicrons", "maxAreaMicrons",
    "histogramThreshold", "cellExpansionMicrons",
)

_VALID_COMPARTMENTS = ("nuclear", "cytoplasmic", "whole-cell")

# nuclear -> Nucleus, cytoplasmic -> Cytoplasm, whole-cell -> Cell (area-weighted
# whole-cell mean over nucleus + cytoplasm; added w88, 2026-07-25, operator
# domain call for TdTomato) -- D-01 spec.md compartment semantics.
_COMPARTMENT_LABELS = {"nuclear": "Nucleus", "cytoplasmic": "Cytoplasm", "whole-cell": "Cell"}


class ConfigError(SystemExit):
    """Raised (as a fail-loud exit) for any structural problem with the sidecar config."""


def _fail(msg: str) -> None:
    raise ConfigError(f"pipeline.yml INVALID: {msg}")


def load_config(path: Path) -> dict[str, Any]:
    """Load + structurally validate the sidecar pipeline config. Fail-loud on any problem."""
    if not path.exists():
        _fail(f"config file not found: {path}")

    with open(path) as f:
        try:
            config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            _fail(f"not valid YAML ({path}): {e}")

    if not isinstance(config, dict):
        _fail(f"top-level document must be a mapping, got {type(config).__name__}")

    # -- anchor --
    if "anchor" not in config:
        _fail("missing required top-level key 'anchor'")
    anchor = config["anchor"]
    if not isinstance(anchor, dict):
        _fail(f"'anchor' must be a mapping, got {type(anchor).__name__}")
    for key in ("name", "channel"):
        if key not in anchor:
            _fail(f"'anchor.{key}' is required")
        if not isinstance(anchor[key], str) or not anchor[key].strip():
            _fail(f"'anchor.{key}' must be a non-empty string")

    # -- markers --
    if "markers" not in config:
        _fail("missing required top-level key 'markers'")
    markers = config["markers"]
    if not isinstance(markers, list):
        _fail(f"'markers' must be a list, got {type(markers).__name__}")
    seen_names: set[str] = set()
    for i, m in enumerate(markers):
        if not isinstance(m, dict):
            _fail(f"'markers[{i}]' must be a mapping, got {type(m).__name__}")
        for key in ("name", "channel", "compartment"):
            if key not in m:
                _fail(f"'markers[{i}].{key}' is required")
        if not isinstance(m["name"], str) or not m["name"].strip():
            _fail(f"'markers[{i}].name' must be a non-empty string")
        if not isinstance(m["channel"], str) or not m["channel"].strip():
            _fail(f"'markers[{i}].channel' must be a non-empty string")
        if m["compartment"] not in _VALID_COMPARTMENTS:
            _fail(
                f"'markers[{i}].compartment' = {m['compartment']!r} is invalid; "
                f"must be one of {_VALID_COMPARTMENTS}"
            )
        if m["name"] in seen_names:
            _fail(f"duplicate marker name {m['name']!r} in 'markers'")
        seen_names.add(m["name"])

    # -- exclude_acronyms --
    if "exclude_acronyms" not in config:
        _fail("missing required top-level key 'exclude_acronyms'")
    exclude = config["exclude_acronyms"]
    if not isinstance(exclude, list) or not all(isinstance(x, str) for x in exclude):
        _fail("'exclude_acronyms' must be a list of strings")

    # -- k_robust --
    if "k_robust" not in config:
        _fail("missing required top-level key 'k_robust'")
    k_robust = config["k_robust"]
    if not isinstance(k_robust, (int, float)) or isinstance(k_robust, bool):
        _fail(f"'k_robust' must be numeric, got {type(k_robust).__name__}")

    # -- ring --
    if "ring" not in config:
        _fail("missing required top-level key 'ring'")
    ring = config["ring"]
    if not isinstance(ring, dict):
        _fail(f"'ring' must be a mapping, got {type(ring).__name__}")
    for key in ("gap_um", "width_um"):
        if key not in ring:
            _fail(f"'ring.{key}' is required")
        if not isinstance(ring[key], (int, float)) or isinstance(ring[key], bool):
            _fail(f"'ring.{key}' must be numeric, got {type(ring[key]).__name__}")

    # -- detection_threshold (anchor-channel intensity cut) --
    #
    # D-14 note: this does NOT violate "no BraiAnDetect detection params in
    # pipeline.yml". What lives here is the RULE (which mode, and the span
    # fraction) -- a pipeline policy that must be identical across a series.
    # The resolved per-section threshold VALUE is never written to either YAML;
    # run_braian_detection.groovy computes it from the section's own histogram and
    # injects it into the BraiAn config object at runtime. BraiAn.yml's own
    # `threshold` / `histogramThreshold` keys are consequently ignored for the
    # anchor channel.
    if "detection_threshold" not in config:
        _fail(
            "missing required top-level key 'detection_threshold' -- add the block "
            "from the repo-root pipeline.yml. Without it, detection would fall back "
            "to BraiAn.yml's absolute threshold, which does not transfer between "
            "sections or acquisitions."
        )
    dt = config["detection_threshold"]
    if not isinstance(dt, dict):
        _fail(f"'detection_threshold' must be a mapping, got {type(dt).__name__}")

    mode = dt.get("mode")
    if mode not in ("span_fraction", "absolute"):
        _fail(
            f"'detection_threshold.mode' must be \"span_fraction\" or \"absolute\", "
            f"got {mode!r}"
        )

    for key in ("resolution_level", "smooth_window"):
        if key not in dt:
            _fail(f"'detection_threshold.{key}' is required")
        if not isinstance(dt[key], int) or isinstance(dt[key], bool):
            _fail(f"'detection_threshold.{key}' must be an integer, got {type(dt[key]).__name__}")
    if dt["resolution_level"] != 0:
        _fail(
            f"'detection_threshold.resolution_level' must be 0, got {dt['resolution_level']} -- "
            "BraiAn's default of 4 is what produced the historical \"no valid peak\" failures"
        )

    if "peak_prominence" not in dt:
        _fail("'detection_threshold.peak_prominence' is required")
    if not isinstance(dt["peak_prominence"], (int, float)) or isinstance(dt["peak_prominence"], bool):
        _fail("'detection_threshold.peak_prominence' must be numeric")

    if mode == "span_fraction":
        if "span_frac" not in dt:
            _fail("'detection_threshold.span_frac' is required when mode is \"span_fraction\"")
        frac = dt["span_frac"]
        if not isinstance(frac, (int, float)) or isinstance(frac, bool):
            _fail(f"'detection_threshold.span_frac' must be numeric, got {type(frac).__name__}")
        if not 0.0 < frac < 1.0:
            _fail(
                f"'detection_threshold.span_frac' must be strictly between 0 and 1, got {frac} -- "
                "0 is the background floor (detects noise as nuclei) and 1 is the bright peak "
                "(drops every dim nucleus)"
            )
    else:
        if dt.get("absolute") is None:
            _fail(
                "'detection_threshold.absolute' is required when mode is \"absolute\" "
                "(and note that an absolute cut does not generalize across sections)"
            )
        if not isinstance(dt["absolute"], (int, float)) or isinstance(dt["absolute"], bool):
            _fail("'detection_threshold.absolute' must be numeric")

    # -- D-14 negative check: no BraiAnDetect detection params leaked in here --
    leaked = [k for k in _FORBIDDEN_DETECTION_KEYS if k in config]
    if leaked:
        _fail(
            f"BraiAnDetect detection param(s) {leaked} found at top level -- "
            f"these belong in BraiAn.yml, not pipeline.yml (D-14)"
        )

    return config


def derive_contract(config: dict[str, Any]) -> dict[str, Any]:
    """Derive the shared contract (measurement keys, class vocabulary, columns) from
    a config that has already passed `load_config`."""
    anchor_name = config["anchor"]["name"]
    markers = config["markers"]

    measurement_keys: dict[str, str] = {}
    compartment_labels: dict[str, str] = {}
    for m in markers:
        label = _COMPARTMENT_LABELS[m["compartment"]]
        compartment_labels[m["name"]] = label
        measurement_keys[m["name"]] = f"{label}: {m['channel']} mean (bg-sub)"

    marker_names = [m["name"] for m in markers]
    emit_double = len(marker_names) >= 2  # D-03: Double+ only when >=2 non-anchor markers declared

    class_vocabulary = [f"{name}+" for name in marker_names]
    if emit_double:
        class_vocabulary.append("Double+")
    class_vocabulary.append("Negative")
    class_vocabulary.append("Excluded")

    # D-04: per-slice table column set, built purely by iterating declared markers --
    # never a fixed Fos/TdT list. Anchor gets its own count/density pair; each declared
    # marker gets a "<name>+" count/density pair; Double+ count/density only if emitted.
    columns = ["region", "hemisphere", "is_leaf", "area_mm2",
               f"{anchor_name}_count", f"{anchor_name}_density"]
    for name in marker_names:
        columns.append(f"{name}+_count")
        columns.append(f"{name}+_density")
    if emit_double:
        columns.append("Double+_count")
        columns.append("Double+_density")

    return {
        "anchor_name": anchor_name,
        "anchor_channel": config["anchor"]["channel"],
        "marker_names": marker_names,
        "compartment_labels": compartment_labels,
        "measurement_keys": measurement_keys,
        "class_vocabulary": class_vocabulary,
        "emit_double": emit_double,
        "columns": columns,
    }


def _print_contract(config: dict[str, Any], contract: dict[str, Any]) -> None:
    print(f"anchor: {contract['anchor_name']!r} (channel {contract['anchor_channel']!r})")
    print(f"k_robust: {config['k_robust']}   (marker-positivity cut)")
    dt = config["detection_threshold"]
    if dt["mode"] == "span_fraction":
        print(f"detection_threshold: span_fraction, span_frac={dt['span_frac']}   "
              f"(anchor cut = floor + {dt['span_frac']} x (bright_peak - floor), per slice)")
    else:
        print(f"detection_threshold: ABSOLUTE {dt['absolute']}   "
              f"** does not transfer between sections/acquisitions **")
    print(f"ring: gap_um={config['ring']['gap_um']}, width_um={config['ring']['width_um']}")
    print(f"exclude_acronyms: {config['exclude_acronyms']}")
    print()
    print("Per-marker bg-sub measurement keys:")
    for name in contract["marker_names"]:
        print(f"  {name} ({contract['compartment_labels'][name]}): "
              f"{contract['measurement_keys'][name]!r}")
    print()
    print(f"PathClass vocabulary: {contract['class_vocabulary']}")
    print(f"Double+ emitted: {contract['emit_double']}")
    print()
    print(f"Per-slice table columns: {contract['columns']}")


def _build_synthetic_config(tmpdir: Path, marker_names_channels_compartments: list[tuple[str, str, str]]) -> Path:
    markers = [
        {"name": n, "channel": c, "compartment": comp}
        for n, c, comp in marker_names_channels_compartments
    ]
    config = {
        "anchor": {"name": "DAPI", "channel": "DAPI-T4"},
        "markers": markers,
        "exclude_acronyms": ["DG-sg", "VS"],
        "k_robust": 3.0,
        "ring": {"gap_um": 1.0, "width_um": 8.0},
        "detection_threshold": {
            "mode": "span_fraction",
            "span_frac": 0.25,
            "absolute": None,
            "resolution_level": 0,
            "smooth_window": 15,
            "peak_prominence": 100,
        },
    }
    path = tmpdir / f"synthetic_{'_'.join(n for n, _, _ in marker_names_channels_compartments)}.yml"
    with open(path, "w") as f:
        yaml.safe_dump(config, f)
    return path


def self_test() -> bool:
    """Construct synthetic configs and assert the D-03/D-04 variable-marker contract.

    (1) TdT-only (single non-anchor marker) -> Double+ NOT in vocabulary, no Fos column.
    (2) Fos+TdT (two non-anchor markers)     -> Double+ IS in vocabulary, both columns present.
    (3) TdT whole-cell (single non-anchor marker, compartment=whole-cell) -> measurement
        key resolves to "Cell: AF568-T2 mean (bg-sub)" (w88, 2026-07-25).

    Returns True if all assertions pass, False otherwise (never raises).
    """
    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        # (1) TdT-only
        tdt_only_path = _build_synthetic_config(tmpdir, [("TdT", "AF568-T2", "cytoplasmic")])
        tdt_only_config = load_config(tdt_only_path)
        tdt_only_contract = derive_contract(tdt_only_config)
        if "Double+" in tdt_only_contract["class_vocabulary"]:
            print("SELF-TEST FAIL: TdT-only config unexpectedly emits 'Double+'")
            ok = False
        if any(col.startswith("Fos") for col in tdt_only_contract["columns"]):
            print("SELF-TEST FAIL: TdT-only config unexpectedly has a Fos column: "
                  f"{tdt_only_contract['columns']}")
            ok = False
        if "TdT+_count" not in tdt_only_contract["columns"]:
            print("SELF-TEST FAIL: TdT-only config is missing its own TdT+_count column")
            ok = False

        # (2) Fos+TdT
        both_path = _build_synthetic_config(
            tmpdir, [("Fos", "AF488-T3", "nuclear"), ("TdT", "AF568-T2", "cytoplasmic")])
        both_config = load_config(both_path)
        both_contract = derive_contract(both_config)
        if "Double+" not in both_contract["class_vocabulary"]:
            print("SELF-TEST FAIL: Fos+TdT config is missing 'Double+' in vocabulary")
            ok = False
        if "Fos+_count" not in both_contract["columns"] or "TdT+_count" not in both_contract["columns"]:
            print("SELF-TEST FAIL: Fos+TdT config is missing an expected marker column: "
                  f"{both_contract['columns']}")
            ok = False

        # (3) TdT whole-cell -- w88, 2026-07-25: TdTomato fills the whole cell,
        # so the derived measurement key must resolve to the Cell-compartment
        # (area-weighted whole-cell) mean, not Cytoplasm.
        whole_cell_path = _build_synthetic_config(
            tmpdir, [("TdT", "AF568-T2", "whole-cell")])
        whole_cell_config = load_config(whole_cell_path)
        whole_cell_contract = derive_contract(whole_cell_config)
        expected_key = "Cell: AF568-T2 mean (bg-sub)"
        if whole_cell_contract["measurement_keys"].get("TdT") != expected_key:
            print("SELF-TEST FAIL: whole-cell TdT config measurement key = "
                  f"{whole_cell_contract['measurement_keys'].get('TdT')!r}, expected {expected_key!r}")
            ok = False

        if ok:
            print("SELF-TEST PASSED:")
            print("  TdT-only    -> vocabulary =", tdt_only_contract["class_vocabulary"],
                  "| columns =", tdt_only_contract["columns"])
            print("  Fos+TdT     -> vocabulary =", both_contract["class_vocabulary"],
                  "| columns =", both_contract["columns"])
            print("  TdT whole-cell -> measurement key =",
                  whole_cell_contract["measurement_keys"]["TdT"])

    return ok


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("--config", type=Path, default=Path("pipeline.yml"),
                     help="path to the sidecar pipeline config to validate (default: pipeline.yml)")
    ap.add_argument("--self-test", action="store_true",
                     help="run synthetic TdT-only vs Fos+TdT contract assertions instead of validating --config")
    args = ap.parse_args()

    if args.self_test:
        passed = self_test()
        sys.exit(0 if passed else 1)

    config = load_config(args.config)
    contract = derive_contract(config)
    _print_contract(config, contract)
    sys.exit(0)


if __name__ == "__main__":
    main()
