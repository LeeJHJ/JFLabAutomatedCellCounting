#!/usr/bin/env python3
"""build_region_reference.py -- render a project's Allen ontology as a lookup page.

Every acronym on the page is RESOLVED FROM A PROJECT'S OWN
`allen_mouse_10um_java-Ontology.json`. There is no hardcoded acronym->name
table anywhere in this script, and there must never be one: the atlas the
sections were registered against is the only thing entitled to say what an
acronym means. Point `--project` at a different QuPath project and the page
re-derives itself.

The one piece of curation is the `FOCUS` sets below, and even those are stored
as a handful of ROOT acronyms; membership is expanded through the ontology at
build time. A root that does not resolve is dropped with a warning rather than
silently rendered.

Observed-in-data columns come from `*__percell_export.tsv` under each project's
`results/`. Those files are read, never written.

READ-ONLY on everything except its own output file.

Usage (from the Analysis root):
  ~/miniforge3/envs/braian/bin/python docs/build_region_reference.py
  conda run -n braian python docs/build_region_reference.py \
      --project "M5 072526/M5 073026 QuPath" --out docs/assets/region-acronyms.html
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ONTOLOGY_NAME = "allen_mouse_10um_java-Ontology.json"
DEFAULT_OUT = REPO / "docs" / "assets" / "region-acronyms.html"

# Major divisions, in atlas order. Each structure is filed under the first of
# these that is an ancestor-or-self. Acronyms only -- the names come from the
# ontology like everything else.
DIVISIONS = ["Isocortex", "OLF", "HPF", "CTXsp", "STR", "PAL", "TH", "HY",
             "MB", "P", "MY", "CB", "fiber tracts", "VS", "grv", "retina"]

# The curated layer: domain knowledge about WHICH corners of the atlas this lab
# cares about. Stored as roots and expanded through the ontology, so a focus set
# covers every subdivision the atlas defines without listing any of them here.
FOCUS = [
    {"key": "engram", "label": "Engram core",
     "note": "Context and episodic memory — where TRAP2 tagging is read out.",
     "roots": ["HPF", "RSP", "LA", "BLA", "BMA", "PL", "ILA", "ACA",
               "RE", "AM", "AV", "AD", "MS", "NDB"]},
    {"key": "fear", "label": "Fear & aversive",
     "note": "Aversive-valence engram and its output path.",
     "roots": ["LA", "BLA", "BMA", "CEA", "MEA", "PA", "BST", "PAG", "PVT"]},
    {"key": "reward", "label": "Reward & opioid",
     "note": "Canonical morphine targets and the mesolimbic path.",
     "roots": ["ACB", "CP", "OT", "FS", "VTA", "SNc", "LHA", "PVT",
               "CEA", "BST", "AI", "ORB", "ILA", "PL"]},
    {"key": "withdrawal", "label": "Withdrawal & stress",
     "note": "Stress axis and the withdrawal-associated brainstem nuclei.",
     "roots": ["PVH", "BST", "CEA", "LC", "PB", "DR", "PVT", "LHA", "AHN"]},
    {"key": "intero", "label": "Interoception & pain",
     "note": "Insular–parabrachial–PAG interoceptive and nociceptive chain.",
     "roots": ["AI", "PB", "PAG", "CEA", "VPM", "NTS", "LC"]},
    {"key": "sensory", "label": "Sensory & motor cortex",
     "note": "Useful mainly as comparison tissue — not an engram target.",
     "roots": ["SSp", "SSs", "VIS", "AUD", "MO", "GU", "VISC"]},
]


class Ontology:
    """The atlas tree, keyed by acronym. acronym/name live under node['data']."""

    def __init__(self, path: Path):
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.atlas = doc.get("name", path.stem)
        self.order: list[str] = []
        self.name: dict[str, str] = {}
        self.parent: dict[str, str | None] = {}
        self.kids: dict[str, list[str]] = {}
        self.depth: dict[str, int] = {}
        self.color: dict[str, str] = {}
        self._walk(doc["root"], None, 0)

    def _walk(self, node: dict, parent: str | None, depth: int) -> None:
        d = node["data"]
        a = d["acronym"]
        self.order.append(a)
        self.name[a] = d.get("name", a)
        self.parent[a] = parent
        self.depth[a] = depth
        self.color[a] = "#" + str(d.get("color_hex_triplet", "888888")).lstrip("#")
        children = node.get("children") or []
        self.kids[a] = [c["data"]["acronym"] for c in children]
        for c in children:
            self._walk(c, a, depth + 1)

    def __contains__(self, a: str) -> bool:
        return a in self.name

    def descendants_or_self(self, a: str) -> set[str]:
        out, stack = set(), [a]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(self.kids.get(cur, []))
        return out

    def ancestors_or_self(self, a: str) -> list[str]:
        out, cur = [], a
        while cur is not None:
            out.append(cur)
            cur = self.parent.get(cur)
        return out


def find_projects(root: Path) -> list[dict]:
    """QuPath projects that hold both an ontology and exported per-cell tables."""
    found = []
    for ont in sorted(root.glob("*/**/" + ONTOLOGY_NAME)):
        proj = ont.parent
        parts = proj.relative_to(root).parts
        if "_archive" in parts or "scratchpad" in parts:
            continue
        cells = sorted(proj.glob("results/*__percell_export.tsv"))
        if not cells:
            continue
        found.append({"dir": proj, "ontology": ont, "cells": cells})
    return found


def label_for(proj: Path, root: Path) -> str:
    """A short, human name for a project directory. Heuristic and harmless."""
    raw = proj.name
    out = re.sub(r"\b\d{6}\b", " ", raw)                       # date stamps
    out = re.sub(r"\b\d+\s*scenes?\b", " ", out, flags=re.I)   # "7 Scene" -- before bare "scene"
    out = re.sub(r"\b(QuPath|project|scenes?)\b", " ", out, flags=re.I)
    out = re.sub(r"[_]+", " ", out)
    out = re.sub(r"\s+", " ", out).strip(" -")
    return out or raw


def read_labels(cells: list[Path]) -> tuple[collections.Counter, int]:
    """Per-cell region labels across a project's exports, with cell counts.

    The counts are what make the roll-down rule concrete rather than assertable:
    a parent acronym's own count is the number of cells that would survive a
    literal string match, and it is typically a rounding error next to what
    sits below it.
    """
    labels: collections.Counter = collections.Counter()
    rows = 0
    for f in cells:
        with f.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh, delimiter="\t"):
                lab = (row.get("region_label") or "").strip()
                if lab:
                    labels[lab] += 1
                rows += 1
    return labels, rows


def build_payload(project: Path | None) -> dict:
    projects = find_projects(REPO)
    if not projects:
        sys.exit("No QuPath project with both an ontology and per-cell exports was found.")

    chosen = projects[0]
    if project is not None:
        want = (REPO / project).resolve()
        match = [p for p in projects if p["dir"].resolve() == want
                 or p["dir"].resolve().is_relative_to(want)]
        if not match:
            sys.exit(f"No ontology + per-cell exports under {project}")
        chosen = match[0]

    ont = Ontology(chosen["ontology"])
    print(f"  ontology: {chosen['ontology'].relative_to(REPO)}")
    print(f"  {len(ont.order)} structures, "
          f"{sum(1 for a in ont.order if not ont.kids[a])} leaves, "
          f"max depth {max(ont.depth.values())}")

    # ---- observed labels, per project ----
    series = []
    for p in projects:
        labels, rows = read_labels(p["cells"])
        unknown = sorted(l for l in labels if l not in ont)
        series.append({
            "label": label_for(p["dir"], REPO),
            "path": str(p["dir"].relative_to(REPO)),
            "sections": len(p["cells"]),
            "cells": rows,
            "labels": labels,
            "known": {l for l in labels if l in ont},
            "unknown": unknown,
        })
        print(f"  observed: {series[-1]['label']:16s} "
              f"{len(labels):4d} distinct labels over {len(p['cells'])} sections"
              + (f"  (not in ontology: {', '.join(unknown)})" if unknown else ""))

    idx = {a: i for i, a in enumerate(ont.order)}
    masks = []
    for a in ont.order:
        m = 0
        for bit, s in enumerate(series):
            if a in s["known"]:
                m |= 1 << bit
        masks.append(m)
    # per-series cell count for each structure, at the label itself (not rolled up)
    counts = [[s["labels"].get(a, 0) for a in ont.order] for s in series]

    # ---- division of each structure ----
    div_of = []
    for a in ont.order:
        chain = ont.ancestors_or_self(a)
        found = -1
        for anc in chain:
            if anc in DIVISIONS:
                found = DIVISIONS.index(anc)
                break
        div_of.append(found)

    divisions = [{"acr": d, "name": ont.name.get(d, d)} for d in DIVISIONS if d in ont]
    missing_div = [d for d in DIVISIONS if d not in ont]
    if missing_div:
        print(f"  note: division root(s) not in this ontology, skipped: {missing_div}",
              file=sys.stderr)

    # ---- focus sets, expanded through the ontology ----
    focus = []
    for f in FOCUS:
        good = [r for r in f["roots"] if r in ont]
        bad = [r for r in f["roots"] if r not in ont]
        if bad:
            print(f"  note: focus '{f['key']}' dropped unresolvable root(s): {bad}",
                  file=sys.stderr)
        members: set[str] = set()
        for r in good:
            members |= ont.descendants_or_self(r)
        focus.append({
            "key": f["key"], "label": f["label"], "note": f["note"],
            "roots": good,
            "members": sorted(idx[a] for a in members),
        })
        print(f"  focus: {f['label']:24s} {len(good)} roots -> {len(members)} structures")

    return {
        "atlas": ont.atlas,
        "sourceProject": str(chosen["dir"].relative_to(REPO)),
        "sourceFile": str(chosen["ontology"].relative_to(REPO)),
        "built": date.today().isoformat(),
        "acr": ont.order,
        "name": [ont.name[a] for a in ont.order],
        "par": [idx[ont.parent[a]] if ont.parent[a] is not None else -1 for a in ont.order],
        "depth": [ont.depth[a] for a in ont.order],
        "color": [ont.color[a] for a in ont.order],
        "div": div_of,
        "mask": masks,
        "count": counts,
        "divisions": divisions,
        "focus": focus,
        "series": [{"label": s["label"], "path": s["path"], "sections": s["sections"],
                    "cells": s["cells"], "distinct": len(s["labels"]),
                    "unknown": s["unknown"]} for s in series],
    }


PAGE = r"""<title>Allen CCFv3 Region Acronyms — resolved from the project ontology</title>
<style>
:root{
  --paper:#ffffff; --sunk:#f2f3f7; --rule:#e0e2ec; --rule-2:#eceef4;
  --ink:#161822; --ink-2:#4d5265; --ink-3:#82889c;
  --accent:#3d3a94; --accent-soft:#e8e7f7; --on-accent:#ffffff;
  --seen:#1c6b4d; --seen-bg:#e0f1e8;
  --unseen:#8b91a4; --unseen-bg:#eef0f5;
  --flag:#8c4a12; --flag-bg:#fbeedd; --flag-rule:#e7c69c;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#0f1116; --sunk:#171a22; --rule:#262a36; --rule-2:#1d212b;
  --ink:#e8eaf2; --ink-2:#a6acbe; --ink-3:#797f93;
  --accent:#9b96f0; --accent-soft:#1e1c3c; --on-accent:#14121f;
  --seen:#5cc79a; --seen-bg:#102e23;
  --unseen:#7e849a; --unseen-bg:#1b1f29;
  --flag:#e0ab6b; --flag-bg:#2b2113; --flag-rule:#584223;
}}
:root[data-theme="light"]{
  --paper:#ffffff; --sunk:#f2f3f7; --rule:#e0e2ec; --rule-2:#eceef4;
  --ink:#161822; --ink-2:#4d5265; --ink-3:#82889c;
  --accent:#3d3a94; --accent-soft:#e8e7f7; --on-accent:#ffffff;
  --seen:#1c6b4d; --seen-bg:#e0f1e8; --unseen:#8b91a4; --unseen-bg:#eef0f5;
  --flag:#8c4a12; --flag-bg:#fbeedd; --flag-rule:#e7c69c;
}
:root[data-theme="dark"]{
  --paper:#0f1116; --sunk:#171a22; --rule:#262a36; --rule-2:#1d212b;
  --ink:#e8eaf2; --ink-2:#a6acbe; --ink-3:#797f93;
  --accent:#9b96f0; --accent-soft:#1e1c3c; --on-accent:#14121f;
  --seen:#5cc79a; --seen-bg:#102e23; --unseen:#7e849a; --unseen-bg:#1b1f29;
  --flag:#e0ab6b; --flag-bg:#2b2113; --flag-rule:#584223;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.page{max-width:1080px;margin:0 auto;padding:clamp(26px,4vw,54px) clamp(13px,3vw,32px) 90px;
  display:flex;flex-direction:column;gap:24px}

.eyebrow{margin:0 0 11px;font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent)}
h1{margin:0;font-family:var(--serif);font-size:clamp(27px,4.2vw,40px);line-height:1.08;
  letter-spacing:-.015em;font-weight:600;text-wrap:balance;max-width:20ch}
.lede{margin:14px 0 0;font-family:var(--serif);font-size:17px;line-height:1.5;
  color:var(--ink-2);max-width:60ch}
.prov{margin-top:15px;display:flex;flex-wrap:wrap;gap:5px 16px;font-family:var(--mono);
  font-size:11.5px;color:var(--ink-3)}
.prov b{color:var(--ink-2);font-weight:500}
code{font-family:var(--mono);font-size:.88em;background:var(--sunk);border:1px solid var(--rule);
  border-radius:4px;padding:1px 5px}

/* ---- the two rules that actually bite ---- */
.rules{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:13px}
.note{border:1px solid var(--flag-rule);background:var(--flag-bg);border-radius:8px;
  padding:14px 16px;display:flex;flex-direction:column;gap:7px}
.note h2{margin:0;font-size:14px;font-weight:650;color:var(--flag);letter-spacing:-.005em}
.note p{margin:0;font-size:13.8px;color:var(--ink-2)}
#rollProof{display:flex;flex-direction:column;gap:7px}
.measured{display:flex;flex-direction:column;gap:3px;font-size:13px;
  padding:9px 11px;border-radius:7px;background:color-mix(in srgb,var(--paper) 55%,transparent);
  border:1px solid var(--flag-rule)}
.measured b{color:var(--ink);font-variant-numeric:tabular-nums}
.aside{font-size:13px;color:var(--ink-2)}
.note code{background:color-mix(in srgb,var(--paper) 55%,transparent);border-color:var(--flag-rule)}

/* ---- controls ---- */
.controls{position:sticky;top:0;z-index:8;background:var(--paper);border-bottom:1px solid var(--rule);
  padding:12px 0 11px;display:flex;flex-direction:column;gap:10px}
.row{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search]{flex:1 1 240px;min-width:0;font:inherit;font-size:14.5px;padding:9px 13px;
  border:1px solid var(--rule);border-radius:7px;background:var(--sunk);color:var(--ink)}
input[type=search]:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
select{font:inherit;font-size:13.5px;padding:8px 10px;border:1px solid var(--rule);border-radius:7px;
  background:var(--sunk);color:var(--ink);max-width:100%}
select:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.tgl{font:inherit;font-size:13px;cursor:pointer;padding:7px 12px;border-radius:20px;
  border:1px solid var(--rule);background:var(--sunk);color:var(--ink-2)}
.tgl[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.tgl:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.focus-lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);flex:0 0 100%}
#tally{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--ink-3);
  font-variant-numeric:tabular-nums;white-space:nowrap}
.focus-note{font-size:12.5px;color:var(--ink-3);flex:0 0 100%;margin:0}
.focus-note[hidden]{display:none}

/* ---- index ---- */
.tw{overflow-x:auto;border:1px solid var(--rule);border-radius:9px}
table{width:100%;border-collapse:collapse;font-size:14px}
thead th{background:var(--sunk);text-align:left;font-family:var(--mono);
  font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3);font-weight:700;
  padding:9px 12px;border-bottom:1px solid var(--rule);white-space:nowrap}
tbody td{padding:0;border-bottom:1px solid var(--rule-2);vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr.r:hover{background:var(--sunk)}
td>.cell{padding:6px 12px}
.sw{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none;
  box-shadow:inset 0 0 0 1px rgba(0,0,0,.16)}
.acr{font-family:var(--mono);font-size:13.5px;font-weight:640;line-height:1.3;
  color:var(--accent);background:var(--accent-soft);border:1px solid transparent;
  border-radius:5px;padding:3px 8px;cursor:pointer;white-space:nowrap}
.acr:hover{border-color:var(--accent)}
.acr:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.acr.copied{background:var(--seen-bg);color:var(--seen)}
.nm{font-family:var(--serif);font-size:14.5px;color:var(--ink-2);line-height:1.35}
.lvl{display:flex;align-items:center;gap:2px}
.lvl i{width:3px;height:9px;background:var(--rule);border-radius:1px;display:block}
.lvl i.on{background:var(--ink-3)}
.lvl .d{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);margin-left:5px;
  font-variant-numeric:tabular-nums}
.role{font-family:var(--mono);font-size:11px;color:var(--ink-3);white-space:nowrap}
.role.parent{color:var(--flag)}
.seen{display:flex;gap:3px;flex-wrap:wrap}
.dotm{width:9px;height:9px;border-radius:50%;background:var(--unseen-bg);
  box-shadow:inset 0 0 0 1px var(--unseen);display:block}
.dotm.on{background:var(--seen);box-shadow:none}
.exp{font-family:var(--mono);font-size:12px;background:none;border:0;cursor:pointer;
  color:var(--ink-3);padding:6px 10px;width:100%;text-align:left}
.exp:hover{color:var(--accent)}
.exp:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
tr.detail>td{padding:0;background:var(--sunk);border-bottom:1px solid var(--rule)}
tr.detail[hidden]{display:none}
.dwrap{padding:13px 14px;display:flex;flex-direction:column;gap:11px}
.dwrap h3{margin:0;font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);font-weight:700}
.path{font-family:var(--mono);font-size:12px;color:var(--ink-2);word-break:break-word}
.path b{color:var(--ink);font-weight:600}
.roll{display:flex;flex-direction:column;gap:7px}
.roll .line{display:grid;grid-template-columns:130px 1fr;gap:4px 12px;font-size:13px;
  align-items:baseline}
.roll .who{font-family:var(--mono);font-size:11.5px;color:var(--ink-3)}
.roll .what{color:var(--ink-2)}
.tok{display:inline-flex;align-items:baseline;gap:5px;font-family:var(--mono);font-size:11.5px;
  background:var(--paper);border:1px solid var(--rule);border-radius:5px;padding:1px 6px;
  margin:0 3px 3px 0;color:var(--ink)}
.tok .cn{color:var(--ink-3);font-size:10.5px;font-variant-numeric:tabular-nums}
.tok.self .cn{color:var(--seen)}
.toll{display:flex;flex-wrap:wrap;gap:4px 20px;font-size:13px;color:var(--ink-2);
  padding:9px 11px;background:var(--paper);border:1px solid var(--rule);border-radius:7px}
.toll b{color:var(--ink);font-variant-numeric:tabular-nums}
.tok.self{border-color:var(--seen);color:var(--seen);background:var(--seen-bg)}
.none{color:var(--ink-3);font-style:italic;font-size:12.5px}

.more{padding:13px;text-align:center;font-size:13px;color:var(--ink-3);background:var(--sunk);
  border-top:1px solid var(--rule)}
.more[hidden]{display:none}
.empty{border:1px dashed var(--rule);border-radius:9px;padding:30px;text-align:center;
  color:var(--ink-3)}
.empty[hidden]{display:none}

/* ---- legend / footer ---- */
.legend{display:flex;flex-wrap:wrap;gap:8px 22px;font-size:12.5px;color:var(--ink-3);
  align-items:center}
.legend .k{display:inline-flex;align-items:center;gap:6px}
footer{border-top:1px solid var(--rule);padding-top:16px;display:flex;flex-direction:column;gap:6px;
  font-family:var(--mono);font-size:11.5px;color:var(--ink-3)}
footer b{color:var(--ink-2);font-weight:500}
@media (max-width:720px){
  .roll .line{grid-template-columns:1fr}
  .hide-s{display:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="page">
  <header>
    <p class="eyebrow" id="eyebrow"></p>
    <h1>Region acronyms, straight from the atlas you registered against</h1>
    <p class="lede" id="lede"></p>
    <div class="prov" id="prov"></div>
  </header>

  <div class="rules">
    <div class="note">
      <h2>An acronym is an exact string match — a typo returns nothing, not an error</h2>
      <p><code>Ca1</code>, <code>ca1</code> and <code>CA-1</code> all yield an empty region
      rather than failing. Click any acronym below to copy it exactly.</p>
      <p>Watch the collisions: <code>LH</code> is the lateral <em>habenula</em>; the lateral
      hypothalamic area is <code>LHA</code>. <code>PL</code> is prelimbic cortex.
      <code>LA</code> is the lateral amygdalar nucleus, not a thalamic nucleus.</p>
    </div>
    <div class="note">
      <h2>A parent acronym matches almost nothing until you roll it down</h2>
      <p>Per-cell rows are labelled with the <em>finest</em> annotation containing the cell —
      usually an ontology leaf, sometimes a mid-level node where the registration carried no
      finer child. Either way the label is at the frontier, not at the parent.</p>
      <p id="rollProof">Roll down over descendants-or-self ∩ what is actually present, then keep
      only the nodes with no present descendant. That frontier is non-overlapping, so it is safe
      to sum. Expand any row below to see its frontier, per series.</p>
    </div>
  </div>

  <div class="controls">
    <div class="row">
      <input type="search" id="q" placeholder="Search acronym or region name…" aria-label="Search regions">
      <select id="div" aria-label="Filter by major division"></select>
      <button class="tgl" id="onlySeen" type="button" aria-pressed="false">Only regions in the data</button>
      <button class="tgl" id="onlyLeaf" type="button" aria-pressed="false">Frontier only</button>
      <span id="tally"></span>
    </div>
    <div class="row" id="focusRow">
      <span class="focus-lbl">Focus</span>
    </div>
    <p class="focus-note" id="focusNote" hidden></p>
  </div>

  <div class="tw">
    <table>
      <thead><tr>
        <th style="width:1%"></th>
        <th>Acronym</th>
        <th>Region name (atlas verbatim)</th>
        <th class="hide-s">Level</th>
        <th class="hide-s">Role</th>
        <th>In the data</th>
        <th style="width:1%"></th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="more" id="more" hidden></div>
  </div>
  <div class="empty" id="empty" hidden>Nothing in this atlas matches that.</div>

  <div class="legend" id="legend"></div>

  <footer id="foot"></footer>
</div>

<script id="data" type="application/json">__PAYLOAD__</script>
<script>
(function(){
"use strict";
var D = JSON.parse(document.getElementById("data").textContent);
var N = D.acr.length;
var esc = function(s){ return String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); };

/* children index, derived -- the payload only carries parents */
var kids = []; for (var i = 0; i < N; i++) kids.push([]);
for (var i = 0; i < N; i++) if (D.par[i] >= 0) kids[D.par[i]].push(i);
var maxDepth = 0; for (var i = 0; i < N; i++) if (D.depth[i] > maxDepth) maxDepth = D.depth[i];

function descendants(i){                   /* descendants-or-self */
  var out = [], stack = [i];
  while (stack.length){ var c = stack.pop(); out.push(c);
    for (var k = 0; k < kids[c].length; k++) stack.push(kids[c][k]); }
  return out;
}
/* the data frontier under i for series bit b: present nodes with no present descendant */
function frontier(i, bit){
  var d = descendants(i), present = {}, out = [];
  for (var k = 0; k < d.length; k++) if (D.mask[d[k]] & (1 << bit)) present[d[k]] = 1;
  for (var k = 0; k < d.length; k++){
    if (!present[d[k]]) continue;
    var sub = descendants(d[k]), covered = false;
    for (var j = 0; j < sub.length; j++) if (sub[j] !== d[k] && present[sub[j]]) { covered = true; break; }
    if (!covered) out.push(d[k]);
  }
  return out;
}
function cellsAt(i){ var n = 0;
  for (var b = 0; b < D.count.length; b++) n += D.count[b][i]; return n; }
function cellsUnder(i){ var d = descendants(i), n = 0;
  for (var k = 0; k < d.length; k++) n += cellsAt(d[k]); return n; }
var fmt = function(n){ return n.toLocaleString("en-US"); };

var descCount = new Array(N);
(function(){ for (var i = N - 1; i >= 0; i--){ var n = 0;
  for (var k = 0; k < kids[i].length; k++) n += 1 + descCount[kids[i][k]];
  descCount[i] = n; } })();

/* ---- masthead ---- */
var totalSeen = 0; for (var i = 0; i < N; i++) if (D.mask[i]) totalSeen++;
document.getElementById("eyebrow").textContent = D.atlas + " · region lookup";
document.getElementById("lede").innerHTML =
  "Every acronym and name on this page was resolved from <code>" + esc(D.sourceFile.split("/").pop()) +
  "</code> in your own QuPath project — all <b>" + N + "</b> structures the atlas defines, not a " +
  "curated list. <b>" + totalSeen + "</b> of them have actually carried a cell in the " +
  D.series.length + " registered series on this machine.";
document.getElementById("prov").innerHTML =
    "<span><b>atlas</b> " + esc(D.atlas) + "</span>" +
    "<span><b>ontology from</b> " + esc(D.sourceProject) + "</span>" +
    "<span><b>structures</b> " + N + "</span>" +
    "<span><b>built</b> " + esc(D.built) + "</span>";

/* ---- the roll-down rule, stated in this dataset's own numbers ---- */
var byAcr = {}; for (var i = 0; i < N; i++) byAcr[D.acr[i]] = i;
(function(){
  var rows = [];
  ["HPF","TH","CTXsp","STR","HY","MB"].forEach(function(a){
    var i = byAcr[a]; if (i == null) return;
    var under = cellsUnder(i); if (under <= 0) return;
    rows.push({acr:a, under:under, self:cellsAt(i)});
  });
  rows.sort(function(x, y){ return y.under - x.under; });
  rows = rows.slice(0, 4);
  if (!rows.length) return;

  /* a mid-level node that IS the frontier here: has children in the atlas, none in the data */
  var mid = null;
  for (var i = 0; i < N; i++){
    if (!kids[i].length) continue;
    var self = cellsAt(i); if (!self) continue;
    if (self !== cellsUnder(i)) continue;          /* nothing below it was ever labelled */
    if (!mid || self > mid.self) mid = {acr:D.acr[i], self:self, kidsN:descCount[i]};
  }

  var el = document.getElementById("rollProof");
  el.innerHTML =
    "<span class=\"measured\">" + rows.map(function(r){
      return "<span><code>" + esc(r.acr) + "</code> holds <b>" + fmt(r.under) +
             "</b> cells; <b>" + (100 * r.self / r.under).toFixed(1) +
             "%</b> carry it as their literal label</span>"; }).join("") + "</span>" +
    (mid ? "<span class=\"aside\">The reverse also happens: <code>" + esc(mid.acr) +
      "</code> has " + mid.kidsN + " subdivisions in the atlas but the registration carried none " +
      "of them, so <code>" + esc(mid.acr) + "</code> is itself the frontier here and holds all " +
      fmt(mid.self) + " of its cells directly.</span>" : "") +
    "<span>" + el.innerHTML + "</span>";
})();

/* ---- division filter ---- */
var divSel = document.getElementById("div");
divSel.innerHTML = '<option value="-1">Every division</option>' + D.divisions.map(function(d, k){
  return '<option value="' + k + '">' + esc(d.acr) + " — " + esc(d.name) + "</option>";
}).join("");

/* ---- focus chips ---- */
var focusRow = document.getElementById("focusRow");
var focusNote = document.getElementById("focusNote");
var activeFocus = null, focusSet = null;
D.focus.forEach(function(f){
  var b = document.createElement("button");
  b.type = "button"; b.className = "tgl"; b.setAttribute("aria-pressed","false");
  b.textContent = f.label;
  b.addEventListener("click", function(){
    var on = activeFocus === f.key;
    Array.prototype.forEach.call(focusRow.querySelectorAll(".tgl"), function(x){
      x.setAttribute("aria-pressed","false"); });
    if (on){ activeFocus = null; focusSet = null; focusNote.hidden = true; }
    else {
      activeFocus = f.key; b.setAttribute("aria-pressed","true");
      focusSet = {}; f.members.forEach(function(m){ focusSet[m] = 1; });
      focusNote.hidden = false;
      focusNote.innerHTML = esc(f.note) + " Expanded from " + f.roots.length +
        " root acronym" + (f.roots.length === 1 ? "" : "s") + " (" +
        f.roots.map(function(r){ return "<code>" + esc(r) + "</code>"; }).join(" ") +
        ") through the ontology — " + f.members.length + " structures.";
    }
    apply();
  });
  focusRow.appendChild(b);
});

/* ---- row rendering ---- */
var rowsEl = document.getElementById("rows");
var CAP = 400;

function levelCell(i){
  var s = '<span class="lvl">';
  for (var d = 0; d <= maxDepth; d++)
    s += '<i class="' + (d <= D.depth[i] ? "on" : "") + '"></i>';
  return s + '<span class="d">' + D.depth[i] + "</span></span>";
}
function roleCell(i){
  var n = descCount[i];
  if (n === 0) return '<span class="role">leaf</span>';
  return '<span class="role parent">parent · ' + n + " below</span>";
}
function seenCell(i){
  var s = '<span class="seen">';
  for (var b = 0; b < D.series.length; b++)
    s += '<span class="dotm ' + ((D.mask[i] & (1 << b)) ? "on" : "") + '" title="' +
         esc(D.series[b].label) + ((D.mask[i] & (1 << b)) ? ": labelled directly" : ": not a label here") +
         '"></span>';
  return s + "</span>";
}
function rowHTML(i){
  return '<tr class="r" data-i="' + i + '">' +
    '<td><span class="cell"><span class="sw" style="background:' + esc(D.color[i]) + '"></span></span></td>' +
    '<td><span class="cell"><button class="acr" type="button" data-c="' + esc(D.acr[i]) +
        '" title="Copy">' + esc(D.acr[i]) + "</button></span></td>" +
    '<td><span class="cell nm">' + esc(D.name[i]) + "</span></td>" +
    '<td class="hide-s"><span class="cell">' + levelCell(i) + "</span></td>" +
    '<td class="hide-s"><span class="cell">' + roleCell(i) + "</span></td>" +
    '<td><span class="cell">' + seenCell(i) + "</span></td>" +
    '<td><button class="exp" type="button" aria-expanded="false" title="Show hierarchy and roll-down">+</button></td>' +
  "</tr>" +
  '<tr class="detail" hidden><td colspan="7"></td></tr>';
}
function detailHTML(i){
  var chain = [], c = i;
  while (c >= 0){ chain.unshift(c); c = D.par[c]; }
  var path = chain.map(function(x, k){
    var t = "<code>" + esc(D.acr[x]) + "</code>";
    return k === chain.length - 1 ? "<b>" + t + "</b>" : t;
  }).join(" › ");

  var roll = D.series.map(function(s, b){
    var f = frontier(i, b);
    var body;
    if (!f.length) body = '<span class="none">no cell in this series was labelled anywhere under ' +
        esc(D.acr[i]) + "</span>";
    else body = f.map(function(x){
        return '<span class="tok' + (x === i ? " self" : "") + '">' + esc(D.acr[x]) +
               '<span class="cn">' + fmt(D.count[b][x]) + "</span></span>"; }).join("");
    return '<div class="line"><span class="who">' + esc(s.label) + '</span><span class="what">' +
           body + "</span></div>";
  }).join("");

  var self = cellsAt(i), under = cellsUnder(i);
  var toll = '<div class="toll">' +
    "<span><b>" + fmt(under) + "</b> cells sit under <code>" + esc(D.acr[i]) + "</code></span>" +
    "<span><b>" + fmt(self) + "</b> carry it as their literal label" +
    (under ? " (" + (100 * self / under).toFixed(2) + "%)" : "") + "</span>" +
    "</div>";

  return '<div class="dwrap">' +
      '<div><h3>Where it sits</h3><div class="path">' + path + "</div></div>" +
      toll +
      '<div><h3>Rolls down to — per-cell labels actually present under ' + esc(D.acr[i]) +
        ', with cells at each</h3><div class="roll">' + roll + "</div></div>" +
    "</div>";
}

var tally = document.getElementById("tally");
var moreEl = document.getElementById("more");
var emptyEl = document.getElementById("empty");
var q = document.getElementById("q");
var onlySeen = document.getElementById("onlySeen");
var onlyLeaf = document.getElementById("onlyLeaf");
[onlySeen, onlyLeaf].forEach(function(b){
  b.addEventListener("click", function(){
    b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
    apply();
  });
});

var hay = new Array(N);
for (var i = 0; i < N; i++) hay[i] = (D.acr[i] + " " + D.name[i]).toLowerCase();

function apply(){
  var term = q.value.trim().toLowerCase();
  var wantDiv = parseInt(divSel.value, 10);
  var seenOnly = onlySeen.getAttribute("aria-pressed") === "true";
  var leafOnly = onlyLeaf.getAttribute("aria-pressed") === "true";
  var hits = [];
  for (var i = 0; i < N; i++){
    if (seenOnly && !D.mask[i]) continue;
    if (leafOnly && descCount[i] !== 0) continue;
    if (wantDiv >= 0 && D.div[i] !== wantDiv) continue;
    if (focusSet && !focusSet[i]) continue;
    if (term && hay[i].indexOf(term) < 0) continue;
    hits.push(i);
  }
  var show = hits.slice(0, CAP);
  rowsEl.innerHTML = show.map(rowHTML).join("");
  tally.textContent = hits.length + " / " + N + " structures";
  moreEl.hidden = hits.length <= CAP;
  moreEl.textContent = hits.length <= CAP ? "" :
    (hits.length - CAP) + " more match — narrow the search to see them.";
  emptyEl.hidden = hits.length > 0;
}

/* delegated: copy + expand */
rowsEl.addEventListener("click", function(ev){
  var copy = ev.target.closest(".acr");
  if (copy){
    var text = copy.dataset.c;
    var done = function(){
      var old = copy.textContent;
      copy.classList.add("copied"); copy.textContent = "copied";
      setTimeout(function(){ copy.classList.remove("copied"); copy.textContent = old; }, 850);
    };
    if (navigator.clipboard && navigator.clipboard.writeText)
      navigator.clipboard.writeText(text).then(done, function(){});
    else {
      var ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); done(); } catch(e){}
      document.body.removeChild(ta);
    }
    return;
  }
  var exp = ev.target.closest(".exp");
  if (exp){
    var tr = exp.closest("tr.r");
    var det = tr.nextElementSibling;
    var open = exp.getAttribute("aria-expanded") === "true";
    if (!open && !det.dataset.filled){
      det.firstElementChild.innerHTML = detailHTML(parseInt(tr.dataset.i, 10));
      det.dataset.filled = "1";
    }
    exp.setAttribute("aria-expanded", String(!open));
    exp.textContent = open ? "+" : "−";
    det.hidden = open;
  }
});

q.addEventListener("input", apply);
divSel.addEventListener("change", apply);

/* ---- legend + footer ---- */
document.getElementById("legend").innerHTML =
  '<span class="k"><span class="sw" style="background:#8fbcd4"></span> the atlas\'s own colour for that structure</span>' +
  D.series.map(function(s, b){
    return '<span class="k"><span class="dotm on"></span> ' + esc(s.label) + " — " + s.sections +
           " sections, " + s.distinct + " distinct labels</span>";
  }).join("");

var unknownNote = D.series.filter(function(s){ return s.unknown.length; })
  .map(function(s){ return s.label + ": " + s.unknown.join(", "); }).join("; ");
document.getElementById("foot").innerHTML =
  "<span>Generated from <b>" + esc(D.sourceFile) + "</b> by docs/build_region_reference.py. " +
    "No acronym on this page is hardcoded — point the script at another project and it re-derives.</span>" +
  "<span>&quot;In the data&quot; is a snapshot of per-cell exports on " + esc(D.built) +
    ", read from each project's results/. It says a label was written, not that the count is trustworthy.</span>" +
  (unknownNote ? "<span>Labels seen in exports that are not atlas structures — " +
    esc(unknownNote) + " — cells outside every registered annotation.</span>" : "");

apply();
})();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", type=Path, default=None,
                    help="QuPath project to take the ontology from "
                         "(default: first project found with per-cell exports)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="HTML to write")
    args = ap.parse_args()

    print("Resolving acronyms from the project ontology...")
    payload = build_payload(args.project)

    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    blob = blob.replace("</", "<\\/")          # never break out of <script>
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(PAGE.replace("__PAYLOAD__", blob), encoding="utf-8")
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
