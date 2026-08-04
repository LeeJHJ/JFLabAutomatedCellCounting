#!/usr/bin/env python3
"""build_acronym_lookup.py -- a general Allen CCFv3 acronym lookup page.

This is the PROJECT-INDEPENDENT sibling of build_region_reference.py. That one
answers "which regions are in MY data"; this one answers "what is this acronym",
for anyone working in Allen CCFv3 — no experiment, no cell counts, no lab-specific
region sets.

Source is the vendored structure graph in docs/atlas/, which is byte-identical to
the copy every QuPath project here carries (see docs/atlas/README.md). Nothing on
the page is hardcoded: acronyms, names, numeric ids, colours and hierarchy are all
read from that file.

Optionally cross-references a local BrainGlobe atlas, if one is installed, to flag
the structures BrainGlobe's `allen_mouse` prunes -- an acronym can be valid CCFv3
and still not resolve in brainglobe-atlasapi or brainrender. Absent BrainGlobe the
column is simply omitted.

READ-ONLY on everything except its own output file.

Usage (from the Analysis root):
  ~/miniforge3/envs/braian/bin/python docs/build_acronym_lookup.py
  conda run -n braian python docs/build_acronym_lookup.py --out docs/assets/allen-acronyms.html
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
VENDORED = REPO / "docs" / "atlas" / "allen_mouse_10um_java-Ontology.json"
DEFAULT_OUT = REPO / "docs" / "assets" / "allen-acronyms.html"
BRAINGLOBE = Path.home() / ".brainglobe"

# Major divisions, in atlas order. Every structure is filed under the first of
# these that is an ancestor-or-self. Acronyms only -- names come from the atlas.
DIVISIONS = ["Isocortex", "OLF", "HPF", "CTXsp", "STR", "PAL", "TH", "HY",
             "MB", "P", "MY", "CB", "fiber tracts", "VS", "grv", "retina"]

# Confusable pairs worth calling out. Each entry is a list of acronyms that get
# mistaken for one another; the names are looked up in the atlas, never typed here,
# so a pair that stops existing disappears instead of going stale.
CONFUSABLES = [
    ["LH", "LHA"],
    ["PL", "PIR"],
    ["LA", "LP", "LD"],
    ["MO", "MOp", "MOs"],
    ["PA", "PAG", "PAA"],
    ["CA1", "CA2", "CA3"],
    ["AI", "AId", "AIv", "AIp"],
    ["SI", "SNr", "SNc"],
    ["RE", "RSP", "RT"],
]

# Terms the literature uses that the atlas does not. This is the one genuinely
# curated table on the page, and it is deliberately shallow: it stores only
# ALLEN acronyms as members, every one of which is validated against the graph at
# build time. Names, colours and hierarchy still come from the atlas -- an entry
# whose members stop resolving is dropped with a warning, never rendered stale.
#
#   alias       a different abbreviation or spelling for one atlas structure
#   composite   one literature term, several atlas structures
#   collision   the term IS a valid atlas acronym, for a DIFFERENT structure
#   positional  not expressible as acronyms at all -- a position, not a structure
#
# Where the field disagrees with itself, the note says so rather than picking a
# winner silently.
LITERATURE = [
    {"term": "mPFC", "kind": "composite", "also": ["medial prefrontal cortex"],
     "members": ["ACAd", "ACAv", "PL", "ILA"],
     "note": "Definitions differ between labs. Most rodent work means PL + ILA + ACA; some "
             "include MOs as dorsal mPFC, some drop ACA entirely. State which you used — the "
             "choice moves the numbers."},
    {"term": "vmPFC", "kind": "composite", "also": ["ventromedial prefrontal cortex"],
     "members": ["PL", "ILA"], "note": "Usually PL + ILA; occasionally ILA alone."},
    {"term": "dmPFC", "kind": "composite", "also": ["dorsomedial prefrontal cortex"],
     "members": ["ACAd", "ACAv", "PL"], "note": "Usually ACA + PL; occasionally ACA alone."},
    {"term": "PFC", "kind": "composite", "also": ["prefrontal cortex"],
     "members": ["ACA", "PL", "ILA", "ORB", "FRP", "AI"],
     "note": "The broadest reading. Whether rodents have a homologue of primate PFC is itself "
             "contested, so this one is a convenience, not a structure."},
    {"term": "OFC", "kind": "alias", "also": ["orbitofrontal cortex"], "members": ["ORB"],
     "note": "The atlas calls it the orbital area. ORBl / ORBm / ORBvl are its parts."},
    {"term": "amygdala", "kind": "composite", "also": ["Amyg", "amygdaloid complex"],
     "members": ["LA", "BLA", "BMA", "PA", "CEA", "MEA", "IA", "AAA", "COAa", "COAp"],
     "note": "Not one structure, and not even one division: the cortex-like nuclei sit under "
             "CTXsp, the striatum-like ones (CEA, MEA) under STR, and the cortical amygdalar "
             "areas under OLF. There is no single ancestor to roll up to."},
    {"term": "BLA complex", "kind": "composite",
     "also": ["basolateral amygdala complex", "BLAc"], "members": ["LA", "BLA", "BMA"],
     "note": "The trap: the atlas's BLA is ONE nucleus of this complex, not the complex."},
    {"term": "extended amygdala", "kind": "composite", "members": ["CEA", "BST", "IA"],
     "note": "Central extended amygdala. Some definitions add MEA and SI."},
    {"term": "hippocampus proper", "kind": "composite",
     "also": ["Ammon's horn", "cornu ammonis", "HPC"], "members": ["CA1", "CA2", "CA3"],
     "note": "The atlas's CA covers exactly these three. Add DG for the hippocampal region "
             "(HIP); add the retrohippocampal areas for the hippocampal formation (HPF)."},
    {"term": "ventral striatum", "kind": "composite", "members": ["ACB", "OT", "FS"],
     "note": "Some definitions add the ventral pallidum (PALv), which is pallidum, not striatum."},
    {"term": "dorsal striatum", "kind": "alias", "also": ["caudate putamen", "DMS", "DLS"],
     "members": ["CP"],
     "note": "One atlas structure. CCFv3 does not split CP — dorsomedial and dorsolateral "
             "striatum are positions inside CP, so separate them by coordinate, not by label."},
    {"term": "entorhinal cortex", "kind": "composite", "also": ["EC"],
     "members": ["ENTl", "ENTm"]},
    {"term": "insular cortex", "kind": "composite", "also": ["insula"],
     "members": ["AId", "AIv", "AIp"],
     "note": "Some definitions add the gustatory (GU) and visceral (VISC) areas. Do not "
             "abbreviate it IC here — see the collision below."},
    {"term": "septum", "kind": "composite", "members": ["MS", "NDB", "LSX", "TRS"]},
    {"term": "midbrain dopamine neurons", "kind": "composite", "also": ["VTA/SNc"],
     "members": ["VTA", "SNc"]},

    {"term": "BNST", "kind": "alias", "also": ["bed nucleus of the stria terminalis"],
     "members": ["BST"]},
    {"term": "NAc", "kind": "alias", "also": ["NAcc", "Acb", "nucleus accumbens"],
     "members": ["ACB"],
     "note": "CCFv3 does not subdivide the accumbens — there is no core or shell in this atlas."},
    {"term": "LHb", "kind": "alias", "also": ["lateral habenula"], "members": ["LH"],
     "note": "The atlas's acronym is LH — which is also what many papers write for lateral "
             "HYPOTHALAMUS. That one is LHA."},
    {"term": "MHb", "kind": "alias", "also": ["medial habenula"], "members": ["MH"]},
    {"term": "RSC", "kind": "alias", "also": ["retrosplenial cortex"], "members": ["RSP"]},
    {"term": "MEC", "kind": "alias", "also": ["medial entorhinal cortex"], "members": ["ENTm"]},
    {"term": "LEC", "kind": "alias", "also": ["lateral entorhinal cortex"], "members": ["ENTl"]},
    {"term": "PRh", "kind": "alias", "also": ["perirhinal cortex"], "members": ["PERI"]},
    {"term": "S1BF", "kind": "alias", "also": ["barrel cortex", "barrel field"],
     "members": ["SSp-bfd"]},
    {"term": "PVN", "kind": "alias", "also": ["paraventricular nucleus of the hypothalamus"],
     "members": ["PVH"],
     "note": "In the thalamus the paraventricular nucleus is PVT — a different structure in a "
             "different division."},
    {"term": "IL", "kind": "alias", "also": ["infralimbic cortex"], "members": ["ILA"]},
    {"term": "PrL", "kind": "alias", "also": ["prelimbic cortex"], "members": ["PL"]},
    {"term": "locus coeruleus", "kind": "alias", "members": ["LC"],
     "note": "The atlas spells it ceruleus, so a search for the oe spelling can come up empty."},

    {"term": "VP", "kind": "collision", "members": ["PALv"],
     "note": "In this atlas VP is the ventral posterior complex of the THALAMUS. If you mean "
             "ventral pallidum, that is PALv — substantia innominata (SI) plus the "
             "magnocellular nucleus (MA)."},
    {"term": "LH", "kind": "collision", "members": ["LHA"],
     "note": "In this atlas LH is the lateral HABENULA. If you mean the lateral hypothalamic "
             "area, that is LHA. Both readings are common in print."},
    {"term": "IC", "kind": "collision", "members": ["AId", "AIv", "AIp"],
     "note": "In this atlas IC is the inferior colliculus. Papers that abbreviate insular "
             "cortex as IC mean the agranular insular areas — AId, AIv, AIp."},

    {"term": "dHPC", "kind": "positional", "also": ["dorsal hippocampus"],
     "members": ["CA1", "CA2", "CA3", "DG", "SUB"],
     "note": "CCFv3 does not subdivide the hippocampus along the septotemporal axis. Dorsal "
             "and ventral hippocampus are the SAME acronyms at different anteroposterior "
             "positions — separate them by coordinate, never by region label."},
    {"term": "vHPC", "kind": "positional", "also": ["ventral hippocampus"],
     "members": ["CA1", "CA2", "CA3", "DG", "SUB"],
     "note": "Same acronyms as dHPC. The distinction is anteroposterior position, not "
             "structure — it cannot be made with a region label."},
    {"term": "dCA1", "kind": "positional", "also": ["vCA1"], "members": ["CA1"],
     "note": "One atlas structure. The dorsal/ventral split is a coordinate range within CA1."},
]


class Atlas:
    """The CCFv3 structure graph, keyed by acronym."""

    def __init__(self, path: Path):
        doc = json.loads(path.read_text(encoding="utf-8"))
        self.name = doc.get("name", path.stem)
        self.order: list[str] = []
        self.full: dict[str, str] = {}
        self.sid: dict[str, int] = {}
        self.parent: dict[str, str | None] = {}
        self.kids: dict[str, list[str]] = {}
        self.depth: dict[str, int] = {}
        self.color: dict[str, str] = {}
        self._walk(doc["root"], None, 0)

    def _walk(self, node: dict, parent: str | None, depth: int) -> None:
        d = node["data"]
        a = d["acronym"]
        self.order.append(a)
        self.full[a] = d.get("name", a)
        try:
            self.sid[a] = int(d.get("id", node.get("id", -1)))
        except (TypeError, ValueError):
            self.sid[a] = -1
        self.parent[a] = parent
        self.depth[a] = depth
        self.color[a] = "#" + str(d.get("color_hex_triplet", "888888")).lstrip("#")
        children = node.get("children") or []
        self.kids[a] = [c["data"]["acronym"] for c in children]
        for c in children:
            self._walk(c, a, depth + 1)

    def __contains__(self, a: str) -> bool:
        return a in self.full

    def ancestors_or_self(self, a: str) -> list[str]:
        out, cur = [], a
        while cur is not None:
            out.append(cur)
            cur = self.parent.get(cur)
        return out


def find_brainglobe() -> tuple[set[str], str] | None:
    """Acronyms in the newest locally installed BrainGlobe allen_mouse atlas."""
    if not BRAINGLOBE.is_dir():
        return None
    cands = sorted(BRAINGLOBE.glob("allen_mouse_*/structures.json"))
    if not cands:
        return None
    # Resolution does not change the structure list (10um and 25um carry the same
    # 840), but name the one this pipeline actually registers against.
    tenum = [c for c in cands if "10um" in c.parent.name]
    pick = tenum[-1] if tenum else cands[-1]
    try:
        data = json.loads(pick.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {s["acronym"] for s in data}, pick.parent.name


def build_payload(src: Path) -> dict:
    atlas = Atlas(src)
    n_leaf = sum(1 for a in atlas.order if not atlas.kids[a])
    print(f"  atlas: {src.relative_to(REPO) if src.is_relative_to(REPO) else src}")
    print(f"  {len(atlas.order)} structures, {n_leaf} leaves, "
          f"max depth {max(atlas.depth.values())}")

    bg = find_brainglobe()
    if bg:
        bg_set, bg_name = bg
        print(f"  brainglobe: {bg_name} — {len(bg_set)} structures, "
              f"{len(set(atlas.order) - bg_set)} pruned relative to this graph")
        if bg_set - set(atlas.order):
            print(f"  note: {len(bg_set - set(atlas.order))} brainglobe acronyms are NOT in "
                  f"this graph — the two atlases disagree, flag before trusting either",
                  file=sys.stderr)
    else:
        bg_set, bg_name = set(), ""
        print("  brainglobe: not installed locally — availability column omitted")

    idx = {a: i for i, a in enumerate(atlas.order)}

    div_of = []
    for a in atlas.order:
        found = -1
        for anc in atlas.ancestors_or_self(a):
            if anc in DIVISIONS:
                found = DIVISIONS.index(anc)
                break
        div_of.append(found)

    divisions = [{"acr": d, "name": atlas.full[d]} for d in DIVISIONS if d in atlas]
    for d in DIVISIONS:
        if d not in atlas:
            print(f"  note: division root '{d}' not in this graph, skipped", file=sys.stderr)

    confusables = []
    for group in CONFUSABLES:
        good = [a for a in group if a in atlas]
        if len(good) < 2:
            print(f"  note: confusable group {group} does not resolve, skipped", file=sys.stderr)
            continue
        confusables.append([{"acr": a, "name": atlas.full[a]} for a in good])

    # Literature terms: every member must resolve, or the entry does not ship.
    lit, by_kind = [], {}
    for entry in LITERATURE:
        good = [m for m in entry["members"] if m in atlas]
        bad = [m for m in entry["members"] if m not in atlas]
        if bad:
            print(f"  note: literature term '{entry['term']}' has unresolvable member(s) "
                  f"{bad} — dropped from the entry", file=sys.stderr)
        if not good:
            print(f"  note: literature term '{entry['term']}' resolves to nothing, skipped",
                  file=sys.stderr)
            continue
        # An alias that is itself a real acronym would make the page contradict the
        # index sitting next to it (IC is the inferior colliculus, whatever some
        # papers mean by it). Drop it and say so; a real one belongs in `collision`.
        also = []
        for a in entry.get("also", []):
            if a in atlas and entry["kind"] != "collision":
                print(f"  WARNING: alias '{a}' of '{entry['term']}' is itself a real acronym "
                      f"({atlas.full[a]}) — dropped; add a 'collision' entry instead",
                      file=sys.stderr)
                continue
            also.append(a)
        lit.append({
            "term": entry["term"],
            "kind": entry["kind"],
            "also": also,
            "note": entry.get("note", ""),
            "members": [idx[m] for m in good],
        })
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + 1
    print("  literature terms: " + ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())))

    # Same rule for the primary term.
    for e in lit:
        if e["term"] in atlas and e["kind"] != "collision":
            print(f"  WARNING: '{e['term']}' is a real atlas acronym ({atlas.full[e['term']]}) "
                  f"but is filed as '{e['kind']}' — it should be 'collision'", file=sys.stderr)

    # Two entries must never claim the same lookup key, or which one answers is
    # down to list order.
    keys: dict[str, str] = {}
    for e in lit:
        for key in [e["term"]] + e["also"]:
            k = key.lower().replace(" ", "")
            if k in keys and keys[k] != e["term"]:
                print(f"  WARNING: '{key}' is claimed by both '{keys[k]}' and '{e['term']}'",
                      file=sys.stderr)
            keys[k] = e["term"]

    return {
        "atlas": atlas.name,
        "source": str(src.relative_to(REPO)) if src.is_relative_to(REPO) else str(src),
        "built": date.today().isoformat(),
        "hasBG": bool(bg_set),
        "bgName": bg_name,
        "bgCount": len(bg_set),
        "acr": atlas.order,
        "name": [atlas.full[a] for a in atlas.order],
        "sid": [atlas.sid[a] for a in atlas.order],
        "par": [idx[atlas.parent[a]] if atlas.parent[a] is not None else -1 for a in atlas.order],
        "depth": [atlas.depth[a] for a in atlas.order],
        "color": [atlas.color[a] for a in atlas.order],
        "div": div_of,
        "bg": [1 if a in bg_set else 0 for a in atlas.order],
        "divisions": divisions,
        "confusables": confusables,
        "lit": lit,
    }


PAGE = r"""<title>Allen CCFv3 Acronym Lookup</title>
<style>
:root{
  --paper:#fbfbfc; --deck:#ffffff; --sunk:#f0f1f4; --rule:#dfe1e8; --rule-2:#ebedf2;
  --ink:#15161b; --ink-2:#4c5060; --ink-3:#828796;
  --accent:#8c2f39; --accent-soft:#f7e8e9;
  --ok:#1d6b4f; --ok-bg:#e2f2ea;
  --off:#8a8f9e; --off-bg:#edeef2;
  --flag:#8a5312; --flag-bg:#fbeedc; --flag-rule:#e6c79c;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --on-accent:#ffffff;
}
@media (prefers-color-scheme:dark){:root{
  --paper:#101216; --deck:#171a20; --sunk:#13161c; --rule:#262a33; --rule-2:#1d2028;
  --ink:#e9ebf1; --ink-2:#a5abbb; --ink-3:#7a8091;
  --accent:#e5919a; --accent-soft:#33191d;
  --ok:#5bc79a; --ok-bg:#0f2e23;
  --off:#7c8292; --off-bg:#1b1f27;
  --flag:#dfab6c; --flag-bg:#2b2113; --flag-rule:#584223;
  --on-accent:#1a1013;
}}
:root[data-theme="light"]{
  --paper:#fbfbfc; --deck:#ffffff; --sunk:#f0f1f4; --rule:#dfe1e8; --rule-2:#ebedf2;
  --ink:#15161b; --ink-2:#4c5060; --ink-3:#828796;
  --accent:#8c2f39; --accent-soft:#f7e8e9;
  --ok:#1d6b4f; --ok-bg:#e2f2ea; --off:#8a8f9e; --off-bg:#edeef2;
  --flag:#8a5312; --flag-bg:#fbeedc; --flag-rule:#e6c79c; --on-accent:#ffffff;
}
:root[data-theme="dark"]{
  --paper:#101216; --deck:#171a20; --sunk:#13161c; --rule:#262a33; --rule-2:#1d2028;
  --ink:#e9ebf1; --ink-2:#a5abbb; --ink-3:#7a8091;
  --accent:#e5919a; --accent-soft:#33191d;
  --ok:#5bc79a; --ok-bg:#0f2e23; --off:#7c8292; --off-bg:#1b1f27;
  --flag:#dfab6c; --flag-bg:#2b2113; --flag-rule:#584223; --on-accent:#1a1013;
}
*{box-sizing:border-box}
body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.page{max-width:1080px;margin:0 auto;padding:clamp(26px,4vw,52px) clamp(13px,3vw,30px) 90px;
  display:flex;flex-direction:column;gap:24px}
code{font-family:var(--mono);font-size:.88em;background:var(--sunk);border:1px solid var(--rule);
  border-radius:4px;padding:1px 5px}

.eyebrow{margin:0 0 10px;font-family:var(--mono);font-size:11px;letter-spacing:.16em;
  text-transform:uppercase;color:var(--accent)}
h1{margin:0;font-family:var(--serif);font-size:clamp(28px,4.4vw,42px);line-height:1.06;
  letter-spacing:-.016em;font-weight:600;text-wrap:balance;max-width:17ch}
.lede{margin:14px 0 0;font-family:var(--serif);font-size:17px;line-height:1.5;color:var(--ink-2);
  max-width:62ch}
.stat{margin-top:16px;display:flex;flex-wrap:wrap;gap:6px 26px;font-family:var(--mono);
  font-size:11.5px;color:var(--ink-3)}
.stat b{color:var(--ink-2);font-weight:500;font-variant-numeric:tabular-nums}

/* ---- search ---- */
.search{display:flex;flex-direction:column;gap:10px;position:sticky;top:0;z-index:8;
  background:var(--paper);padding:12px 0 11px;border-bottom:1px solid var(--rule)}
.srow{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
input[type=search]{flex:1 1 260px;min-width:0;font:inherit;font-size:15px;padding:11px 14px;
  border:1px solid var(--rule);border-radius:8px;background:var(--deck);color:var(--ink)}
input[type=search]:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
select{font:inherit;font-size:13.5px;padding:9px 10px;border:1px solid var(--rule);border-radius:8px;
  background:var(--deck);color:var(--ink);max-width:100%}
select:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.tgl{font:inherit;font-size:13px;cursor:pointer;padding:8px 13px;border-radius:20px;
  border:1px solid var(--rule);background:var(--deck);color:var(--ink-2)}
.tgl[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--on-accent)}
.tgl:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
#tally{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--ink-3);
  font-variant-numeric:tabular-nums;white-space:nowrap}

/* ---- panels ---- */
.panel{border:1px solid var(--rule);border-radius:10px;background:var(--deck);overflow:hidden}
.phead{padding:14px 16px;border-bottom:1px solid var(--rule-2);background:var(--sunk)}
.phead h2{margin:0;font-size:15.5px;font-weight:640;letter-spacing:-.008em}
.phead p{margin:5px 0 0;font-size:13.3px;color:var(--ink-2);max-width:76ch}
.pbody{padding:14px 16px;display:flex;flex-direction:column;gap:12px}

/* ---- check-a-list ---- */
.tabs{display:flex;gap:0;border:1px solid var(--rule);border-radius:8px;overflow:hidden;
  width:max-content;max-width:100%}
.tab{font:inherit;font-size:13.5px;cursor:pointer;padding:8px 15px;border:0;background:var(--deck);
  color:var(--ink-3);white-space:nowrap}
.tab+.tab{border-left:1px solid var(--rule)}
.tab[aria-pressed=true]{background:var(--accent);color:var(--on-accent);font-weight:600}
.tab:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
.tabhint{font-size:13px;color:var(--ink-2);margin:0}
textarea{width:100%;min-height:96px;font-family:var(--mono);font-size:13px;line-height:1.6;
  padding:11px 13px;border:1px solid var(--rule);border-radius:8px;background:var(--sunk);
  color:var(--ink);resize:vertical}
textarea.names{font-family:var(--serif);font-size:14.5px}
textarea:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.btn{font:inherit;font-size:13.5px;font-weight:600;cursor:pointer;padding:9px 16px;border-radius:8px;
  border:1px solid var(--accent);background:var(--accent);color:var(--on-accent)}
.btn.ghost{background:var(--deck);color:var(--ink-2);border-color:var(--rule);font-weight:500}
.btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.res{display:flex;flex-direction:column;gap:11px}
.res[hidden]{display:none}
.bucket{border:1px solid var(--rule);border-radius:8px;padding:11px 13px;background:var(--sunk)}
.bucket h3{margin:0 0 7px;font-family:var(--mono);font-size:10.5px;letter-spacing:.11em;
  text-transform:uppercase;font-weight:700}
.bucket.good h3{color:var(--ok)}
.bucket.bad h3{color:var(--accent)}
.bucket.warn h3{color:var(--flag)}
.bucket ul{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:6px;
  font-size:13.4px}
.bucket li{display:flex;flex-wrap:wrap;gap:4px 8px;align-items:baseline}
.bucket .in{font-family:var(--mono);font-size:12.5px;color:var(--ink)}
.bucket.names .in{font-family:var(--serif);font-size:14px}
.bucket .arrow{color:var(--ink-3)}
.bucket .say{color:var(--ink-2)}
.bucket .bhead{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:7px}
.bucket .bhead h3{margin:0}
.acr.sm{font-size:12.5px;padding:2px 7px}
.loc{font-family:var(--mono);font-size:12px;background:var(--deck);border:1px solid var(--rule);
  border-radius:5px;padding:1px 6px;cursor:pointer;color:var(--ink-3);line-height:1.4}
.loc:hover{border-color:var(--accent);color:var(--accent)}
.loc:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.copyall{font:inherit;font-size:11.5px;font-family:var(--mono);cursor:pointer;padding:3px 9px;
  border-radius:20px;border:1px solid var(--rule);background:var(--deck);color:var(--ink-2);
  margin-left:auto}
.copyall:hover{border-color:var(--accent);color:var(--accent)}
.copyall:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.copyall.copied{color:var(--ok);border-color:var(--ok);background:var(--ok-bg)}
.fix{font-family:var(--mono);font-size:12.5px;background:none;border:0;padding:0;cursor:pointer;
  color:var(--accent);text-decoration:underline;text-underline-offset:2px}
.fix:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

/* ---- index ---- */
.tw{overflow-x:auto;border:1px solid var(--rule);border-radius:10px}
table{width:100%;border-collapse:collapse;font-size:14px}
thead th{background:var(--sunk);text-align:left;font-family:var(--mono);font-size:10px;
  letter-spacing:.11em;text-transform:uppercase;color:var(--ink-3);font-weight:700;padding:9px 12px;
  border-bottom:1px solid var(--rule);white-space:nowrap}
tbody td{padding:0;border-bottom:1px solid var(--rule-2);vertical-align:middle}
tbody tr:last-child td{border-bottom:none}
tbody tr.r:hover{background:var(--sunk)}
td>.cell{padding:6px 12px}
.sw{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none;
  box-shadow:inset 0 0 0 1px rgba(0,0,0,.16)}
.acr{font-family:var(--mono);font-size:13.5px;font-weight:640;line-height:1.3;color:var(--accent);
  background:var(--accent-soft);border:1px solid transparent;border-radius:5px;padding:3px 8px;
  cursor:pointer;white-space:nowrap}
.acr:hover{border-color:var(--accent)}
.acr:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.acr.copied{background:var(--ok-bg);color:var(--ok)}
.nm{font-family:var(--serif);font-size:14.5px;color:var(--ink-2);line-height:1.35}
.id{font-family:var(--mono);font-size:12.5px;color:var(--ink-3);font-variant-numeric:tabular-nums}
.lvl{display:flex;align-items:center;gap:2px}
.lvl i{width:3px;height:9px;background:var(--rule);border-radius:1px;display:block}
.lvl i.on{background:var(--ink-3)}
.lvl .d{font-family:var(--mono);font-size:10.5px;color:var(--ink-3);margin-left:5px;
  font-variant-numeric:tabular-nums}
.role{font-family:var(--mono);font-size:11px;color:var(--ink-3);white-space:nowrap}
.role.parent{color:var(--flag)}
.chip{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;padding:3px 7px;border-radius:20px;white-space:nowrap;
  color:var(--off);background:var(--off-bg)}
.chip.yes{color:var(--ok);background:var(--ok-bg)}
.exp{font-family:var(--mono);font-size:12px;background:none;border:0;cursor:pointer;
  color:var(--ink-3);padding:6px 10px;width:100%;text-align:left}
.exp:hover{color:var(--accent)}
.exp:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
tr.detail>td{padding:0;background:var(--sunk);border-bottom:1px solid var(--rule)}
tr.detail[hidden]{display:none}
.dwrap{padding:13px 14px;display:flex;flex-direction:column;gap:12px}
.dwrap h3{margin:0 0 5px;font-family:var(--mono);font-size:10.5px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);font-weight:700}
.crumb{display:flex;flex-wrap:wrap;gap:3px 5px;align-items:baseline;font-size:13px}
.jump{font-family:var(--mono);font-size:12px;background:var(--deck);border:1px solid var(--rule);
  border-radius:5px;padding:2px 7px;cursor:pointer;color:var(--ink-2)}
.jump:hover{border-color:var(--accent);color:var(--accent)}
.jump:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.jump.here{border-color:var(--accent);color:var(--accent);background:var(--accent-soft);font-weight:640}
.sep{color:var(--ink-3)}
.kidlist{display:flex;flex-wrap:wrap;gap:4px}
.none{color:var(--ink-3);font-style:italic;font-size:12.5px}
.warnrow{font-size:13px;color:var(--flag);background:var(--flag-bg);border:1px solid var(--flag-rule);
  border-radius:7px;padding:9px 11px}

.more{padding:13px;text-align:center;font-size:13px;color:var(--ink-3);background:var(--sunk);
  border-top:1px solid var(--rule)}
.more[hidden]{display:none}
.empty{border:1px dashed var(--rule);border-radius:9px;padding:30px;text-align:center;
  color:var(--ink-3)}
.empty[hidden]{display:none}

/* ---- literature terms ---- */
.lithit{border:1px solid var(--flag-rule);background:var(--flag-bg);border-radius:9px;
  padding:12px 14px;display:flex;flex-direction:column;gap:7px}
.lithit[hidden]{display:none}
.litrow{display:flex;flex-direction:column;gap:6px;padding:11px 12px;border:1px solid var(--rule);
  border-radius:8px;background:var(--sunk)}
.litrow .top{display:flex;flex-wrap:wrap;gap:7px;align-items:baseline}
.term{font-family:var(--mono);font-size:13.5px;font-weight:640;color:var(--ink)}
.kind{font-family:var(--mono);font-size:9.5px;font-weight:700;letter-spacing:.09em;
  text-transform:uppercase;padding:3px 7px;border-radius:20px;white-space:nowrap}
.kind.composite{color:var(--accent);background:var(--accent-soft)}
.kind.alias{color:var(--ok);background:var(--ok-bg)}
.kind.collision{color:var(--flag);background:var(--flag-bg)}
.kind.positional{color:var(--off);background:var(--off-bg)}
.also{font-size:12.5px;color:var(--ink-3);font-family:var(--serif)}
.litnote{font-size:13px;color:var(--ink-2);max-width:78ch}
.members{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.members .eq{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);margin-right:3px}
.litgrid{display:flex;flex-direction:column;gap:9px}
.kindhead{font-family:var(--mono);font-size:10.5px;letter-spacing:.11em;text-transform:uppercase;
  color:var(--ink-3);font-weight:700;margin:6px 0 0}
.kindhead:first-child{margin-top:0}
.kindhead span{font-weight:400;text-transform:none;letter-spacing:0;color:var(--ink-2);
  font-family:var(--sans);font-size:12.5px;margin-left:8px}

/* ---- confusables ---- */
.pairs{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:9px}
.pair{border:1px solid var(--rule);border-radius:8px;padding:10px 12px;background:var(--sunk);
  display:flex;flex-direction:column;gap:4px}
.pair .one{display:flex;gap:8px;align-items:baseline;font-size:13px}
.pair .one code{flex:none}
.pair .one span{color:var(--ink-2);font-family:var(--serif);font-size:13.5px}

footer{border-top:1px solid var(--rule);padding-top:16px;display:flex;flex-direction:column;gap:6px;
  font-family:var(--mono);font-size:11.5px;color:var(--ink-3)}
footer b{color:var(--ink-2);font-weight:500}
@media (max-width:760px){.hide-s{display:none}}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="page">
  <header>
    <p class="eyebrow" id="eyebrow"></p>
    <h1>Allen CCFv3 acronym lookup</h1>
    <p class="lede" id="lede"></p>
    <div class="stat" id="stat"></div>
  </header>

  <div class="search">
    <div class="srow">
      <input type="search" id="q" placeholder="Acronym, region name, or structure id…" aria-label="Search the atlas">
      <select id="div" aria-label="Filter by major division"></select>
      <button class="tgl" id="onlyLeaf" type="button" aria-pressed="false">Leaves only</button>
      <button class="tgl" id="onlyBG" type="button" aria-pressed="false">Missing from BrainGlobe</button>
      <span id="tally"></span>
    </div>
  </div>

  <div class="lithit" id="lithit" hidden></div>

  <section class="panel">
    <div class="phead">
      <h2>Look up a list</h2>
      <p>Paste what you have — acronyms from a config file, or region names from a paper,
      a figure legend, a collaborator's email — and get back what the atlas calls them.
      Nothing is uploaded; the lookup runs in this page.</p>
    </div>
    <div class="pbody">
      <div class="tabs" role="group" aria-label="What you are pasting">
        <button class="tab" id="tabAcr" type="button" aria-pressed="true"
          aria-controls="paste">I have acronyms</button>
        <button class="tab" id="tabName" type="button" aria-pressed="false"
          aria-controls="paste">I have region names</button>
      </div>
      <p class="tabhint" id="tabhint"></p>
      <textarea id="paste" spellcheck="false" aria-label="List to look up"></textarea>
      <div class="srow">
        <button class="btn" id="check" type="button">Look them up</button>
        <button class="btn ghost" id="clear" type="button">Clear</button>
      </div>
      <div class="res" id="res" hidden></div>
    </div>
  </section>

  <div class="tw">
    <table>
      <thead><tr>
        <th style="width:1%"></th>
        <th>Acronym</th>
        <th>Region name</th>
        <th class="hide-s">Id</th>
        <th class="hide-s">Level</th>
        <th class="hide-s">Role</th>
        <th id="bgHead">BrainGlobe</th>
        <th style="width:1%"></th>
      </tr></thead>
      <tbody id="rows"></tbody>
    </table>
    <div class="more" id="more" hidden></div>
  </div>
  <div class="empty" id="empty" hidden>No structure in this atlas matches that.</div>

  <section class="panel">
    <div class="phead">
      <h2>Terms the literature uses that the atlas does not</h2>
      <p>Papers are full of names that are not CCFv3 structures — mPFC, BNST, dorsal
      hippocampus. Each one below expands to the atlas acronyms it actually covers, so you can
      go from what a paper says to what your software will accept. These are <em>not</em> valid
      region labels; do not paste the term itself into a config.</p>
    </div>
    <div class="pbody"><div class="litgrid" id="litgrid"></div></div>
  </section>

  <section class="panel">
    <div class="phead">
      <h2>Acronyms that get mistaken for each other</h2>
      <p>Lookup is an exact, case-sensitive string match. A wrong-but-real acronym does not
      error — it silently returns a different part of the brain.</p>
    </div>
    <div class="pbody"><div class="pairs" id="pairs"></div></div>
  </section>

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
var fmt = function(n){ return n.toLocaleString("en-US"); };

var kids = []; for (var i = 0; i < N; i++) kids.push([]);
for (var i = 0; i < N; i++) if (D.par[i] >= 0) kids[D.par[i]].push(i);
var maxDepth = 0; for (var i = 0; i < N; i++) if (D.depth[i] > maxDepth) maxDepth = D.depth[i];
var byAcr = {}; for (var i = 0; i < N; i++) byAcr[D.acr[i]] = i;

var descCount = new Array(N);
for (var i = N - 1; i >= 0; i--){ var n = 0;
  for (var k = 0; k < kids[i].length; k++) n += 1 + descCount[kids[i][k]];
  descCount[i] = n; }

/* normalised index: lowercase, punctuation stripped -- catches ca1 / Ca-1 / CA_1 */
var norm = function(s){ return String(s).toLowerCase().replace(/[^a-z0-9]/g, ""); };
var byNorm = {};
for (var i = 0; i < N; i++){
  var k = norm(D.acr[i]);
  if (!byNorm[k]) byNorm[k] = [];
  byNorm[k].push(i);
}
var byId = {}; for (var i = 0; i < N; i++) byId[D.sid[i]] = i;

/* ---- masthead ---- */
var leaves = 0; for (var i = 0; i < N; i++) if (!kids[i].length) leaves++;
document.getElementById("eyebrow").textContent = D.atlas;
document.getElementById("lede").innerHTML =
  "Every structure in the Allen Mouse Brain Common Coordinate Framework v3 — acronym, " +
  "full name, numeric id, colour and place in the hierarchy. Read straight from the atlas's " +
  "own structure graph, so what you see is what your registration software sees. Search a " +
  "term the atlas does not use — <b>mPFC</b>, <b>BNST</b>, <b>dorsal hippocampus</b> — and it " +
  "answers with the acronyms that term actually covers.";
document.getElementById("stat").innerHTML =
  "<span><b>" + fmt(N) + "</b> structures</span>" +
  "<span><b>" + fmt(leaves) + "</b> leaves</span>" +
  "<span><b>" + maxDepth + "</b> levels deep</span>" +
  (D.hasBG ? "<span><b>" + fmt(D.bgCount) + "</b> of them in BrainGlobe " + esc(D.bgName) + "</span>" : "") +
  "<span><b>" + D.lit.length + "</b> literature terms mapped</span>";

if (!D.hasBG){
  document.getElementById("bgHead").remove();
}

/* ---- division filter ---- */
var divSel = document.getElementById("div");
divSel.innerHTML = '<option value="-1">Every division</option>' + D.divisions.map(function(d, k){
  return '<option value="' + k + '">' + esc(d.acr) + " — " + esc(d.name) + "</option>";
}).join("");

/* ---- index rows ---- */
var rowsEl = document.getElementById("rows");
var CAP = 400;

function levelCell(i){
  var s = '<span class="lvl">';
  for (var d = 0; d <= maxDepth; d++) s += '<i class="' + (d <= D.depth[i] ? "on" : "") + '"></i>';
  return s + '<span class="d">' + D.depth[i] + "</span></span>";
}
function rowHTML(i){
  return '<tr class="r" data-i="' + i + '" id="s-' + esc(D.acr[i]) + '">' +
    '<td><span class="cell"><span class="sw" style="background:' + esc(D.color[i]) + '"></span></span></td>' +
    '<td><span class="cell"><button class="acr" type="button" data-c="' + esc(D.acr[i]) +
        '" title="Copy">' + esc(D.acr[i]) + "</button></span></td>" +
    '<td><span class="cell nm">' + esc(D.name[i]) + "</span></td>" +
    '<td class="hide-s"><span class="cell id">' + D.sid[i] + "</span></td>" +
    '<td class="hide-s"><span class="cell">' + levelCell(i) + "</span></td>" +
    '<td class="hide-s"><span class="cell">' + (descCount[i]
        ? '<span class="role parent">parent · ' + descCount[i] + " below</span>"
        : '<span class="role">leaf</span>') + "</span></td>" +
    (D.hasBG ? '<td><span class="cell"><span class="chip ' + (D.bg[i] ? "yes" : "") + '">' +
        (D.bg[i] ? "present" : "pruned") + "</span></span></td>" : "") +
    '<td><button class="exp" type="button" aria-expanded="false" title="Show hierarchy">+</button></td>' +
  "</tr>" +
  '<tr class="detail" hidden><td colspan="' + (D.hasBG ? 8 : 7) + '"></td></tr>';
}
function jump(i, here){
  return '<button class="jump' + (here ? " here" : "") + '" type="button" data-j="' + i + '">' +
         esc(D.acr[i]) + "</button>";
}
function detailHTML(i){
  var chain = [], c = i;
  while (c >= 0){ chain.unshift(c); c = D.par[c]; }
  var crumb = chain.map(function(x, k){
    return jump(x, k === chain.length - 1); }).join('<span class="sep">›</span>');

  var kidHTML = kids[i].length
    ? '<div class="kidlist">' + kids[i].map(function(k){ return jump(k, false); }).join("") + "</div>"
    : '<span class="none">none — this is a leaf of the atlas</span>';

  var warn = "";
  if (D.hasBG && !D.bg[i]) warn = '<div class="warnrow"><b>' + esc(D.acr[i]) +
    "</b> is a valid CCFv3 structure but is not in BrainGlobe's " + esc(D.bgName) +
    ". It will resolve in ABBA and QuPath and fail in brainglobe-atlasapi or brainrender — " +
    "roll up to an ancestor that is present if you need it there.";

  return '<div class="dwrap">' +
    warn +
    '<div><h3>Path from the root</h3><div class="crumb">' + crumb + "</div></div>" +
    '<div><h3>Direct children (' + kids[i].length + " · " + descCount[i] +
      " in the whole subtree)</h3>" + kidHTML + "</div>" +
    '<div><h3>Full name</h3><div class="nm">' + esc(D.name[i]) + "</div></div>" +
  "</div>";
}

var tally = document.getElementById("tally");
var moreEl = document.getElementById("more");
var emptyEl = document.getElementById("empty");
var litHit = document.getElementById("lithit");
var q = document.getElementById("q");
var onlyLeaf = document.getElementById("onlyLeaf");
var onlyBG = document.getElementById("onlyBG");
if (!D.hasBG) onlyBG.remove();

[onlyLeaf, onlyBG].forEach(function(b){
  if (!b || !b.isConnected) return;
  b.addEventListener("click", function(){
    b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") === "true" ? "false" : "true");
    apply();
  });
});

var hay = new Array(N);
for (var i = 0; i < N; i++) hay[i] = (D.acr[i] + " " + D.name[i] + " " + D.sid[i]).toLowerCase();

function apply(keep){
  var term = q.value.trim().toLowerCase();
  var wantDiv = parseInt(divSel.value, 10);
  var leafOnly = onlyLeaf.getAttribute("aria-pressed") === "true";
  var bgOnly = onlyBG.isConnected && onlyBG.getAttribute("aria-pressed") === "true";
  var hits = [];
  for (var i = 0; i < N; i++){
    if (leafOnly && descCount[i] !== 0) continue;
    if (bgOnly && D.bg[i]) continue;
    if (wantDiv >= 0 && D.div[i] !== wantDiv) continue;
    if (term && hay[i].indexOf(term) < 0) continue;
    hits.push(i);
  }
  rowsEl.innerHTML = hits.slice(0, CAP).map(rowHTML).join("");
  tally.textContent = fmt(hits.length) + " / " + fmt(N) + " structures";
  moreEl.hidden = hits.length <= CAP;
  moreEl.textContent = hits.length <= CAP ? "" :
    fmt(hits.length - CAP) + " more match — narrow the search to see them.";
  emptyEl.hidden = hits.length > 0;

  /* searching a literature term should answer, not come up empty */
  var e = q.value.trim() ? litFor(q.value) : null;
  litHit.hidden = !e;
  if (e) litHit.innerHTML =
    '<div class="top" style="display:flex;flex-wrap:wrap;gap:7px;align-items:baseline">' +
      '<span class="term">' + esc(e.term) + "</span>" +
      '<span class="kind ' + esc(e.kind) + '">' + esc(e.kind) + "</span>" +
      '<span class="also">' + esc(KINDSAY[e.kind] || "") + "</span></div>" +
    memberHTML(e) +
    (e.note ? '<p class="litnote">' + esc(e.note) + "</p>" : "");
  return hits;
}
q.addEventListener("input", function(){ apply(); });
divSel.addEventListener("change", function(){ apply(); });

/* focus one structure in the index, wherever it is */
function reveal(i){
  q.value = D.acr[i]; divSel.value = "-1";
  onlyLeaf.setAttribute("aria-pressed", "false");
  if (onlyBG.isConnected) onlyBG.setAttribute("aria-pressed", "false");
  apply();
  var tr = document.getElementById("s-" + D.acr[i]);
  if (tr){
    var exp = tr.querySelector(".exp");
    if (exp && exp.getAttribute("aria-expanded") !== "true") exp.click();
    tr.scrollIntoView({block:"center"});
  }
}

function writeClipboard(text, done){
  if (navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(text).then(done, function(){});
    return;
  }
  var ta = document.createElement("textarea");
  ta.value = text; document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); done(); } catch(e){}
  document.body.removeChild(ta);
}
/* every acronym anywhere on the page copies on click */
function copyFrom(ev){
  var el = ev.target.closest(".acr");
  if (!el) return false;
  var old = el.textContent;
  writeClipboard(el.dataset.c, function(){
    el.classList.add("copied"); el.textContent = "copied";
    setTimeout(function(){ el.classList.remove("copied"); el.textContent = old; }, 850);
  });
  return true;
}

rowsEl.addEventListener("click", function(ev){
  if (copyFrom(ev)) return;
  var j = ev.target.closest(".jump");
  if (j){ reveal(parseInt(j.dataset.j, 10)); return; }
  var exp = ev.target.closest(".exp");
  if (exp){
    var tr = exp.closest("tr.r"), det = tr.nextElementSibling;
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

/* ---- check a list ---- */
function editDistance(a, b){
  if (Math.abs(a.length - b.length) > 2) return 3;
  var prev = [], cur = [];
  for (var j = 0; j <= b.length; j++) prev[j] = j;
  for (var i = 1; i <= a.length; i++){
    cur[0] = i;
    for (var j = 1; j <= b.length; j++){
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1,
                        prev[j - 1] + (a.charAt(i - 1) === b.charAt(j - 1) ? 0 : 1));
    }
    for (var j = 0; j <= b.length; j++) prev[j] = cur[j];
  }
  return prev[b.length];
}
function sharedPrefix(a, b){
  var n = Math.min(a.length, b.length), i = 0;
  while (i < n && a.charAt(i) === b.charAt(i)) i++;
  return i;
}
function suggest(raw){
  var k = norm(raw);
  if (byNorm[k]) return byNorm[k].slice(0, 4);        /* case / punctuation only */
  var out = [];
  for (var i = 0; i < N; i++){
    if (editDistance(k, norm(D.acr[i])) <= 1) out.push(i);
    if (out.length >= 4) break;
  }
  if (out.length || k.length < 4) return out;
  /* Someone pasted a name, not an acronym -- answer that too rather than
     calling it unknown. Match a whole word of the region name, allowing a
     different ending ("hippocampus" -> "Hippocampal formation"). */
  var scored = [];
  for (var i = 0; i < N; i++){
    var words = D.name[i].toLowerCase().split(/[^a-z0-9]+/);
    var best = 0;
    for (var w = 0; w < words.length; w++){
      if (words[w].length < 4) continue;
      var sp = sharedPrefix(k, words[w]);
      if (sp >= 5 && sp > best) best = sp;
    }
    if (best) scored.push({i: i, sp: best, len: D.name[i].length});
  }
  scored.sort(function(x, y){ return y.sp - x.sp || x.len - y.len; });
  return scored.slice(0, 4).map(function(x){ return x.i; });
}

/* ---- literature terms: one lookup key per term and per alias ---- */
var litByKey = {};
D.lit.forEach(function(e, k){
  litByKey[norm(e.term)] = k;
  e.also.forEach(function(a){ if (litByKey[norm(a)] == null) litByKey[norm(a)] = k; });
});
function litFor(raw){
  var k = litByKey[norm(raw)];
  return k == null ? null : D.lit[k];
}
var KINDSAY = {
  composite:  "covers several atlas structures",
  alias:      "the atlas's name for it is",
  collision:  "means something else in this atlas",
  positional: "is a position, not a structure"
};
function memberHTML(e){
  return '<div class="members"><span class="eq">' +
    (e.kind === "collision" ? "you probably mean" :
     e.kind === "positional" ? "structures involved" :
     e.kind === "alias" ? "=" : "=") + "</span>" +
    e.members.map(function(i){
      return '<button class="acr sm" type="button" data-c="' + esc(D.acr[i]) +
        '" title="Copy ' + esc(D.acr[i]) + '">' + esc(D.acr[i]) + "</button>"; }).join("") +
    (e.members.length > 1 ? '<button class="copyall" type="button" data-all="' +
      esc(e.members.map(function(i){ return D.acr[i]; }).join(", ")) +
      '">Copy all ' + e.members.length + "</button>" : "") +
    "</div>";
}
function litRowHTML(e){
  return '<div class="litrow"><div class="top"><span class="term">' + esc(e.term) + "</span>" +
    '<span class="kind ' + esc(e.kind) + '">' + esc(e.kind) + "</span>" +
    (e.also.length ? '<span class="also">also written ' +
      e.also.map(function(a){ return esc(a); }).join(", ") + "</span>" : "") +
    "</div>" +
    memberHTML(e) +
    (e.note ? '<p class="litnote">' + esc(e.note) + "</p>" : "") +
  "</div>";
}

/* ---- name -> acronym, the direction you usually need ---- */
var nameTok = new Array(N), byNameExact = {};
for (var i = 0; i < N; i++){
  var t = D.name[i].toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  nameTok[i] = t.split(" ").filter(function(x){ return x.length; });
  byNameExact[t] = i;
}
var STOP = {the:1, of:1, and:1};
/* "amygdala" should reach "amygdalar", "hippocampus" should reach "hippocampal" */
function tokenHit(qt, nt){
  if (qt === nt) return true;
  if (qt.length >= 4 && nt.indexOf(qt) === 0) return true;
  if (nt.length >= 4 && qt.indexOf(nt) === 0) return true;
  return sharedPrefix(qt, nt) >= 5;
}
function matchName(raw){
  var qn = raw.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  if (!qn) return [];
  if (byNameExact[qn] != null) return [{i: byNameExact[qn], sure: true}];
  if (byAcr[raw.trim()] != null) return [{i: byAcr[raw.trim()], sure: true}];
  var qt = qn.split(" ").filter(function(x){ return x.length && !STOP[x]; });
  if (!qt.length) return [];
  /* Word order carries information in both directions: people write the
     distinguishing word first ("retrosplenial cortex"), and so does the atlas
     ("Retrosplenial area"). Without this, "cortex" alone matches Cerebral cortex
     and outranks the region actually being asked for. */
  var w = [], wsum = 0;
  for (var a = 0; a < qt.length; a++){ w[a] = 1 / (1 + a); wsum += w[a]; }

  var scored = [];
  for (var i = 0; i < N; i++){
    var nt = nameTok[i], got = 0;
    for (var a = 0; a < qt.length; a++){
      for (var b = 0; b < nt.length; b++){ if (tokenHit(qt[a], nt[b])) { got += w[a]; break; } }
    }
    var cov = got / wsum;
    if (cov < 0.5) continue;
    scored.push({i: i, cov: cov, extra: Math.abs(nt.length - qt.length), len: D.name[i].length});
  }
  scored.sort(function(x, y){ return y.cov - x.cov || x.extra - y.extra || x.len - y.len; });
  var top = scored.slice(0, 4);
  if (!top.length) return [];
  /* Call it an answer only when every word is accounted for AND the runner-up is
     strictly worse. Informal names ("lateral amygdala" vs "Lateral amygdalar
     nucleus") legitimately leave spare words in the atlas name, so extra words
     are a tie-breaker, not a disqualifier. */
  var sure = top[0].cov === 1 &&
             (top.length === 1 || top[1].cov < 1 || top[1].extra > top[0].extra);
  return top.map(function(x, k){ return {i: x.i, sure: sure && k === 0}; })
            .slice(0, sure ? 1 : 4);
}

/* ---- mode ---- */
var MODE = "acr";
var pasteEl = document.getElementById("paste");
var tabAcr = document.getElementById("tabAcr"), tabName = document.getElementById("tabName");
var tabhint = document.getElementById("tabhint");
var PLACEHOLDER = {
  acr: "CA1\ndg-mo\nLHA\nBLA\nCa-3\nVISp1",
  name: "Field CA1\nlateral hypothalamic area\nDentate gyrus, molecular layer\nnucleus accumbens\nbasolateral amygdala"
};
var HINT = {
  acr: "One acronym per line, or separated by spaces and commas. Numeric structure ids work too.",
  name: "One name per line — Allen names contain commas, so line breaks are the only separator. " +
        "Informal names are fine: “basolateral amygdala” finds the nucleus."
};
function setMode(m){
  MODE = m;
  tabAcr.setAttribute("aria-pressed", String(m === "acr"));
  tabName.setAttribute("aria-pressed", String(m === "name"));
  pasteEl.placeholder = PLACEHOLDER[m];
  pasteEl.classList.toggle("names", m === "name");
  tabhint.textContent = HINT[m];
  resEl.hidden = true; resEl.innerHTML = "";
}
tabAcr.addEventListener("click", function(){ setMode("acr"); });
tabName.addEventListener("click", function(){ setMode("name"); });

/* ---- results ---- */
var resEl = document.getElementById("res");

function hitHTML(i){
  return '<button class="acr sm" type="button" data-c="' + esc(D.acr[i]) +
      '" title="Copy ' + esc(D.acr[i]) + '">' + esc(D.acr[i]) + "</button>" +
    '<span class="say">' + esc(D.name[i]) + "</span>" +
    (D.hasBG && !D.bg[i] ? ' <span class="chip">not in BrainGlobe</span>' : "") +
    '<button class="loc" type="button" data-j="' + i + '" title="Show in the index"' +
      ' aria-label="Show ' + esc(D.acr[i]) + ' in the index">↗</button>';
}
function bucket(cls, title, items, all){
  return '<div class="bucket ' + cls + '"><div class="bhead"><h3>' + esc(title) + "</h3>" +
    (all && all.length > 1 ? '<button class="copyall" type="button" data-all="' +
        esc(all.join(", ")) + '">Copy all ' + all.length + "</button>" : "") +
    "</div><ul>" + items.join("") + "</ul></div>";
}

document.getElementById("check").addEventListener("click", function(){
  var raw = pasteEl.value;
  var items = (MODE === "name"
      ? raw.split(/[\n\r;|\t]+/)               /* names carry commas — lines only */
      : raw.split(/[\s,;|]+/))
    .map(function(s){ return s.trim(); }).filter(function(s){ return s.length; });
  if (!items.length){ resEl.hidden = true; return; }

  var sure = [], maybe = [], unknown = [], parents = [], lits = [], seen = {};
  items.forEach(function(it){
    if (seen[it]) return; seen[it] = 1;
    var e = litFor(it);

    /* A real acronym always wins the lookup. But if the literature also uses that
       exact string for something else, say so instead of letting it pass. */
    var i = byAcr[it];
    if (i == null && MODE === "acr" && /^\d+$/.test(it) && byId[parseInt(it, 10)] != null)
      i = byId[parseInt(it, 10)];
    if (i != null){
      sure.push({in: it, i: i});
      if (descCount[i]) parents.push({in: it, i: i});
      if (e && e.kind === "collision") lits.push({in: it, e: e});
      return;
    }
    if (e){ lits.push({in: it, e: e}); return; }

    if (MODE === "name"){
      var m = matchName(it);
      if (!m.length){ unknown.push(it); return; }
      if (m[0].sure){
        sure.push({in: it, i: m[0].i});
        if (descCount[m[0].i]) parents.push({in: it, i: m[0].i});
      } else maybe.push({in: it, s: m.map(function(x){ return x.i; })});
      return;
    }
    var s = suggest(it);
    if (s.length) maybe.push({in: it, s: s});
    else unknown.push(it);
  });

  var html = "";
  if (sure.length) html += bucket("good" + (MODE === "name" ? " names" : ""),
    sure.length + (MODE === "name" ? " resolved to an acronym" : " recognised"),
    sure.map(function(e){
      return '<li><span class="in">' + esc(e.in) + '</span><span class="arrow">→</span>' +
             hitHTML(e.i) + "</li>"; }),
    sure.map(function(e){ return D.acr[e.i]; }));

  if (maybe.length) html += bucket("bad" + (MODE === "name" ? " names" : ""),
    maybe.length + (MODE === "name" ? " matched more than one — pick the right one"
                                    : " not an exact match — did you mean"),
    maybe.map(function(f){
      return '<li><span class="in">' + esc(f.in) + '</span><span class="arrow">→</span>' +
        f.s.map(function(i){ return hitHTML(i); }).join('<span class="sep">·</span>') + "</li>"; }));

  if (unknown.length) html += bucket("bad" + (MODE === "name" ? " names" : ""),
    unknown.length + " not in this atlas at all",
    unknown.map(function(u){ return '<li><span class="in">' + esc(u) +
      '</span><span class="say">' + (MODE === "name" ? "no region name is close to this"
                                                     : "no structure with a close acronym") +
      "</span></li>"; }));

  if (lits.length) html += bucket("warn",
    lits.length + " are terms from the literature, not atlas acronyms",
    lits.map(function(L){
      return '<li style="display:block"><span class="in">' + esc(L.in) + "</span> " +
        '<span class="kind ' + esc(L.e.kind) + '">' + esc(L.e.kind) + "</span> " +
        '<span class="say">' + esc(KINDSAY[L.e.kind] || "") + "</span>" +
        memberHTML(L.e) +
        (L.e.note ? '<p class="litnote">' + esc(L.e.note) + "</p>" : "") + "</li>"; }));

  if (parents.length) html += bucket("warn",
    parents.length + " of these are parents, not leaves",
    parents.map(function(p){
      return '<li><span class="in">' + esc(D.acr[p.i]) + '</span><span class="say">covers ' +
        descCount[p.i] + " structures below it (" +
        kids[p.i].slice(0, 5).map(function(k){ return esc(D.acr[k]); }).join(", ") +
        (kids[p.i].length > 5 ? ", …" : "") +
        "). If your per-region labels are leaves, this matches nothing until you roll it down." +
        "</span></li>"; }));

  resEl.innerHTML = html;
  resEl.hidden = false;
});
document.getElementById("clear").addEventListener("click", function(){
  pasteEl.value = ""; resEl.hidden = true; resEl.innerHTML = "";
});
function panelClick(ev){
  if (copyFrom(ev)) return;
  var all = ev.target.closest(".copyall");
  if (all){
    var old = all.textContent;
    writeClipboard(all.dataset.all, function(){
      all.classList.add("copied"); all.textContent = "copied";
      setTimeout(function(){ all.classList.remove("copied"); all.textContent = old; }, 900);
    });
    return;
  }
  var loc = ev.target.closest(".loc");
  if (loc){ reveal(parseInt(loc.dataset.j, 10)); return; }
  var f = ev.target.closest(".fix");
  if (f) reveal(parseInt(f.dataset.j, 10));
}
resEl.addEventListener("click", panelClick);
litHit.addEventListener("click", panelClick);

/* ---- the literature panel ---- */
var KINDINTRO = {
  composite:  "One term, several atlas structures. Sum them — there is no single acronym.",
  alias:      "The same structure under a different abbreviation or spelling.",
  collision:  "The term is a real atlas acronym, for a DIFFERENT structure. Read carefully.",
  positional: "Not a structure at all. No set of acronyms expresses it."
};
var litGrid = document.getElementById("litgrid");
var order = ["composite", "alias", "collision", "positional"];
var seenKinds = {};
D.lit.forEach(function(e){ seenKinds[e.kind] = 1; });
order.forEach(function(k){ if (!seenKinds[k]) delete seenKinds[k]; });
Object.keys(seenKinds).forEach(function(k){ if (order.indexOf(k) < 0) order.push(k); });

litGrid.innerHTML = order.filter(function(k){ return seenKinds[k]; }).map(function(k){
  var rows = D.lit.filter(function(e){ return e.kind === k; });
  return '<p class="kindhead">' + esc(k) + " <span>" + esc(KINDINTRO[k] || "") + "</span></p>" +
         rows.map(litRowHTML).join("");
}).join("");
litGrid.addEventListener("click", panelClick);

setMode("acr");

/* ---- confusables ---- */
document.getElementById("pairs").innerHTML = D.confusables.map(function(g){
  return '<div class="pair">' + g.map(function(m){
    return '<div class="one"><code>' + esc(m.acr) + "</code><span>" + esc(m.name) + "</span></div>";
  }).join("") + "</div>";
}).join("");

/* ---- footer ---- */
document.getElementById("foot").innerHTML =
  "<span>Generated from <b>" + esc(D.source) + "</b> by docs/build_acronym_lookup.py on " +
    esc(D.built) + ". Acronyms, names, ids and colours are the atlas's own — none are hardcoded.</span>" +
  (D.hasBG ? "<span>BrainGlobe column compares against <b>" + esc(D.bgName) + "</b> installed on this " +
    "machine. Where the two overlap they agree exactly; BrainGlobe simply carries fewer structures.</span>" : "") +
  "<span>Lookup is exact and case-sensitive wherever you use it — this page is lenient so your tools " +
    "do not have to be.</span>";

apply();
if (location.hash){
  var t = byAcr[decodeURIComponent(location.hash.slice(1))];
  if (t != null) reveal(t);
}
})();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=VENDORED,
                    help="atlas structure graph (default: the vendored copy in docs/atlas/)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="HTML to write")
    args = ap.parse_args()

    if not args.src.exists():
        sys.exit(f"Atlas not found: {args.src}\nSee docs/atlas/README.md.")

    print("Building the Allen CCFv3 acronym lookup...")
    payload = build_payload(args.src)

    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    blob = blob.replace("</", "<\\/")          # never break out of <script>
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(PAGE.replace("__PAYLOAD__", blob), encoding="utf-8")
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
