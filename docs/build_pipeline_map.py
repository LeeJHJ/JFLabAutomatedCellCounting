#!/usr/bin/env python3
"""build_pipeline_map.py -- render docs/pipeline-stages.yml as a standalone HTML map.

The pipeline map is GENERATED, never hand-written, so the diagram and the
machine-readable stage list cannot drift apart. Edit `docs/pipeline-stages.yml`,
re-run this, re-publish the artifact.

READ-ONLY on everything except its own output file.

Built for change, in the same sense the YAML is:
  * statuses are discovered from the data -- an unknown status still renders,
    in neutral styling, with its literal name;
  * the status legend text is parsed OUT OF the YAML's own header comment, so
    the definitions on the page are the definitions in the file;
  * fields this script does not know about are still shown, as generic
    key/value detail rows. Adding a field to a stage does not require editing
    this script.

Usage (from the Analysis root):
  ~/miniforge3/envs/braian/bin/python docs/build_pipeline_map.py
  conda run -n braian python docs/build_pipeline_map.py --out docs/assets/pipeline-map.html
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = REPO / "docs" / "pipeline-stages.yml"
DEFAULT_OUT = REPO / "docs" / "assets" / "pipeline-map.html"

# Presentation only. The set of statuses that actually EXISTS comes from the
# YAML; anything not listed here falls back to `_default` and still renders.
STATUS_STYLE = {
    "active":     {"tone": "on",      "rank": 0},
    "optional":   {"tone": "aside",   "rank": 1},
    "standby":    {"tone": "parked",  "rank": 2},
    "diagnostic": {"tone": "probe",   "rank": 3},
    "unwired":    {"tone": "dark",    "rank": 4},
    "_default":   {"tone": "unknown", "rank": 9},
}

# Which statuses sit ON the default path (numbered, on the spine). Everything
# else is drawn parked beside the line at the point it attaches -- present, not
# deleted. `optional` is on the path but unnumbered: it runs when needed.
ON_SPINE = {"active"}

# Fields rendered by dedicated UI. Everything else on a stage becomes a
# generic detail row, so new YAML fields appear without a code change.
HANDLED = {"id", "name", "status", "kind", "environment", "entry",
           "inputs", "outputs", "knobs", "chain", "notes"}


def parse_status_legend(raw: str) -> dict[str, str]:
    """Pull the status definitions out of the YAML's own header comment.

    Recognises the two-column comment block:

        #   active      in the default path today
        #   standby     deliberately NOT in the default path, but kept working
        #               and expected to possibly return.

    Returns {} rather than raising if the block is reworded -- the legend then
    degrades to bare status names instead of the page failing to build.
    """
    legend: dict[str, str] = {}
    current: str | None = None
    for line in raw.splitlines():
        if not line.startswith("#"):
            if legend:
                break          # comment block ended, and we found something
            continue
        body = line[1:]
        m = re.match(r"^   (\w[\w-]*)\s\s+(\S.*)$", body)
        if m:
            current = m.group(1)
            legend[current] = m.group(2).strip()
            continue
        m = re.match(r"^ {8,}(\S.*)$", body)
        if m and current:
            legend[current] += " " + m.group(1).strip()
            continue
        if body.strip() and current:
            current = None     # a non-indented comment line closes the block
    return legend


def as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v]
    return [str(v)]


def clean(v) -> str:
    """YAML folded scalars arrive with hard newlines; reflow to one paragraph."""
    return re.sub(r"\s+", " ", str(v)).strip()


def humanize(key: str) -> str:
    return key.replace("_", " ")


def env_tokens(env: str) -> list[str]:
    """`"qupath + notebook"` -> ['qupath', 'notebook'] for filtering."""
    return [t.strip() for t in re.split(r"[+,/]", env or "") if t.strip()]


def build_payload(src: Path) -> dict:
    raw = src.read_text(encoding="utf-8")
    doc = yaml.safe_load(raw)
    legend = parse_status_legend(raw)

    stages = []
    step = 0
    for st in doc.get("stages", []):
        status = str(st.get("status", "")) or "unspecified"
        on_spine = status in ON_SPINE
        if on_spine:
            step += 1
        env = clean(st.get("environment", "")) if st.get("environment") else ""
        extras = [
            {"label": humanize(k), "value": clean(v)}
            for k, v in st.items()
            if k not in HANDLED and v is not None
        ]
        stages.append({
            "id": str(st.get("id", "")),
            "name": str(st.get("name", st.get("id", ""))),
            "status": status,
            "kind": clean(st.get("kind", "")),
            "env": env,
            "envTokens": env_tokens(env),
            "envNote": doc.get("environments", {}).get(env, ""),
            "entry": as_list(st.get("entry")),
            "inputs": as_list(st.get("inputs")),
            "outputs": as_list(st.get("outputs")),
            "knobs": as_list(st.get("knobs")),
            "chain": as_list(st.get("chain")),
            "notes": clean(st.get("notes", "")) if st.get("notes") else "",
            "extras": extras,
            "onSpine": on_spine,
            "step": step if on_spine else None,
        })

    used = []
    for s in stages:
        if s["status"] not in used:
            used.append(s["status"])
    used.sort(key=lambda s: STATUS_STYLE.get(s, STATUS_STYLE["_default"])["rank"])

    missing = [s for s in used if s not in legend]
    if missing:
        print(f"  note: no legend text in the YAML header for: {', '.join(missing)}",
              file=sys.stderr)

    statuses = [{
        "name": s,
        "tone": STATUS_STYLE.get(s, STATUS_STYLE["_default"])["tone"],
        "blurb": legend.get(s, ""),
        "count": sum(1 for x in stages if x["status"] == s),
        "onSpine": s in ON_SPINE,
    } for s in used]

    principles = [{"label": humanize(k), "text": clean(v)}
                  for k, v in (doc.get("principles") or {}).items()]

    return {
        "pipeline": doc.get("pipeline", ""),
        "readout": doc.get("readout", ""),
        "updated": str(doc.get("updated", "")),
        "schemaVersion": doc.get("schema_version", ""),
        "source": str(src.relative_to(REPO)) if src.is_relative_to(REPO) else str(src),
        "environments": doc.get("environments", {}),
        "statuses": statuses,
        "stages": stages,
        "principles": principles,
    }


PAGE = r"""<title>Section Pipeline Map — TRAP2 → Allen CCFv3</title>
<style>
:root{
  --ground:#eceef0; --deck:#ffffff; --sunk:#f3f5f7; --edge:#d8dde2; --edge-hi:#bcc5cd;
  --ink:#141a1f; --ink-2:#4b5761; --ink-3:#7b8791;
  --line:#9aa6b0;
  --on:#0b6f60;      --on-bg:#dcefe9;
  --aside:#245e9e;   --aside-bg:#dde9f6;
  --parked:#9a6207;  --parked-bg:#f7ead4;
  --probe:#6a4bb5;   --probe-bg:#e8e2f8;
  --dark:#6d7883;    --dark-bg:#e7eaee;
  --unknown:#6d7883; --unknown-bg:#e7eaee;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --shadow:0 1px 1px rgba(15,25,35,.04),0 4px 14px rgba(15,25,35,.06);
}
@media (prefers-color-scheme:dark){:root{
  --ground:#0d1216; --deck:#151c22; --sunk:#111820; --edge:#232d36; --edge-hi:#33404b;
  --ink:#e6ecf1; --ink-2:#a3b0bb; --ink-3:#71808c;
  --line:#3c4a55;
  --on:#3ec3ac;      --on-bg:#0e332e;
  --aside:#74a8e8;   --aside-bg:#132539;
  --parked:#dc9d3f;  --parked-bg:#33260f;
  --probe:#a58ceb;   --probe-bg:#231c3a;
  --dark:#8794a0;    --dark-bg:#1c242c;
  --unknown:#8794a0; --unknown-bg:#1c242c;
  --shadow:0 1px 1px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.34);
}}
:root[data-theme="light"]{
  --ground:#eceef0; --deck:#ffffff; --sunk:#f3f5f7; --edge:#d8dde2; --edge-hi:#bcc5cd;
  --ink:#141a1f; --ink-2:#4b5761; --ink-3:#7b8791; --line:#9aa6b0;
  --on:#0b6f60; --on-bg:#dcefe9; --aside:#245e9e; --aside-bg:#dde9f6;
  --parked:#9a6207; --parked-bg:#f7ead4; --probe:#6a4bb5; --probe-bg:#e8e2f8;
  --dark:#6d7883; --dark-bg:#e7eaee; --unknown:#6d7883; --unknown-bg:#e7eaee;
  --shadow:0 1px 1px rgba(15,25,35,.04),0 4px 14px rgba(15,25,35,.06);
}
:root[data-theme="dark"]{
  --ground:#0d1216; --deck:#151c22; --sunk:#111820; --edge:#232d36; --edge-hi:#33404b;
  --ink:#e6ecf1; --ink-2:#a3b0bb; --ink-3:#71808c; --line:#3c4a55;
  --on:#3ec3ac; --on-bg:#0e332e; --aside:#74a8e8; --aside-bg:#132539;
  --parked:#dc9d3f; --parked-bg:#33260f; --probe:#a58ceb; --probe-bg:#231c3a;
  --dark:#8794a0; --dark-bg:#1c242c; --unknown:#8794a0; --unknown-bg:#1c242c;
  --shadow:0 1px 1px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.34);
}
*{box-sizing:border-box}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
.page{max-width:1010px;margin:0 auto;padding:clamp(24px,4vw,52px) clamp(14px,3.5vw,34px) 80px;
  display:flex;flex-direction:column;gap:26px}

/* ---- masthead ---- */
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.17em;text-transform:uppercase;
  color:var(--ink-3);margin:0 0 10px}
h1{margin:0;font-size:clamp(24px,3.5vw,34px);line-height:1.1;letter-spacing:-.021em;
  font-weight:640;text-wrap:balance;max-width:19ch}
.readout{margin:12px 0 0;color:var(--ink-2);font-size:15.5px;max-width:64ch}
.stamp{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:15px;font-family:var(--mono);
  font-size:11.5px;color:var(--ink-3)}
.stamp b{color:var(--ink-2);font-weight:500}

/* ---- control deck ---- */
.deck{background:var(--deck);border:1px solid var(--edge);border-radius:10px;
  box-shadow:var(--shadow);padding:14px 15px;display:flex;flex-direction:column;gap:13px}
.deck-row{display:flex;flex-wrap:wrap;gap:9px;align-items:center}
.deck-lbl{font-family:var(--mono);font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--ink-3);flex:0 0 100%}
input[type=search]{flex:1 1 220px;min-width:0;font:inherit;font-size:14px;padding:8px 12px;
  border:1px solid var(--edge);border-radius:7px;background:var(--sunk);color:var(--ink)}
input[type=search]:focus-visible{outline:2px solid var(--on);outline-offset:1px}
select{font:inherit;font-size:13.5px;padding:8px 10px;border:1px solid var(--edge);
  border-radius:7px;background:var(--sunk);color:var(--ink)}
select:focus-visible{outline:2px solid var(--on);outline-offset:1px}
.sbtn{font:inherit;font-size:12.5px;cursor:pointer;padding:6px 11px 6px 9px;border-radius:20px;
  border:1px solid var(--edge);background:var(--sunk);color:var(--ink-3);
  display:inline-flex;align-items:center;gap:7px;line-height:1.3}
.sbtn .dot{width:9px;height:9px;border-radius:50%;background:currentColor;flex:none;opacity:.35}
.sbtn[aria-pressed=true]{color:var(--tone);background:var(--tone-bg);border-color:var(--tone)}
.sbtn[aria-pressed=true] .dot{opacity:1}
.sbtn .n{font-family:var(--mono);font-size:11px;opacity:.75;font-variant-numeric:tabular-nums}
.sbtn:focus-visible{outline:2px solid var(--on);outline-offset:2px}
.tone-on{--tone:var(--on);--tone-bg:var(--on-bg)}
.tone-aside{--tone:var(--aside);--tone-bg:var(--aside-bg)}
.tone-parked{--tone:var(--parked);--tone-bg:var(--parked-bg)}
.tone-probe{--tone:var(--probe);--tone-bg:var(--probe-bg)}
.tone-dark{--tone:var(--dark);--tone-bg:var(--dark-bg)}
.tone-unknown{--tone:var(--unknown);--tone-bg:var(--unknown-bg)}
.tbtn{font:inherit;font-size:12.5px;cursor:pointer;padding:6px 11px;border-radius:7px;
  border:1px solid var(--edge);background:var(--sunk);color:var(--ink-2)}
.tbtn:hover{border-color:var(--edge-hi)}
.tbtn:focus-visible{outline:2px solid var(--on);outline-offset:2px}
#tally{margin-left:auto;font-family:var(--mono);font-size:11.5px;color:var(--ink-3);
  font-variant-numeric:tabular-nums}
.keydefs{display:flex;flex-direction:column;gap:5px;border-top:1px solid var(--edge);padding-top:11px}
.keydef{display:flex;gap:10px;font-size:13px;color:var(--ink-2);align-items:baseline}
.keydef .k{font-family:var(--mono);font-size:11.5px;font-weight:600;letter-spacing:.03em;
  text-transform:uppercase;color:var(--tone);flex:0 0 88px}

/* ---- the line ---- */
.flow{display:flex;flex-direction:column}
.stage{display:grid;grid-template-columns:30px 1fr;gap:0 16px;position:relative}
.rail{position:relative;display:flex;justify-content:center}
.rail::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:2px;
  transform:translateX(-50%);background:var(--line);opacity:.5}
.stage:first-child .rail::before{top:17px}
.stage:last-child .rail::before{bottom:calc(100% - 17px)}
.stage[hidden]{display:none}
.pip{position:relative;z-index:1;margin-top:4px;width:26px;height:26px;border-radius:50%;
  display:grid;place-items:center;font-family:var(--mono);font-size:12px;font-weight:600;
  background:var(--deck);color:var(--tone);border:2px solid var(--tone);
  font-variant-numeric:tabular-nums}
.stage.off .pip{border-style:dashed;width:20px;height:20px;margin-top:8px}
.stage.off{margin-left:26px}
.stage.off .rail::before{background:var(--tone);opacity:.32;
  -webkit-mask-image:repeating-linear-gradient(180deg,#000 0 5px,transparent 5px 10px);
  mask-image:repeating-linear-gradient(180deg,#000 0 5px,transparent 5px 10px)}
.stage.off::before{content:"";position:absolute;left:-26px;top:17px;width:26px;height:2px;
  background:var(--tone);opacity:.32}

.card{background:var(--deck);border:1px solid var(--edge);border-radius:9px;
  box-shadow:var(--shadow);margin-bottom:10px;border-left:3px solid var(--tone);overflow:hidden}
.stage.off .card{background:var(--sunk);border-left-style:dashed}
.head{width:100%;text-align:left;font:inherit;background:none;border:0;cursor:pointer;
  padding:11px 14px;display:flex;flex-wrap:wrap;align-items:baseline;gap:5px 11px;color:inherit}
.head:hover{background:var(--sunk)}
.stage.off .head:hover{background:var(--deck)}
.head:focus-visible{outline:2px solid var(--tone);outline-offset:-2px}
.nm{font-size:15px;font-weight:600;letter-spacing:-.01em}
.ent{font-family:var(--mono);font-size:12px;color:var(--ink-3);word-break:break-all}
.badges{margin-left:auto;display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
.badge{font-family:var(--mono);font-size:10px;font-weight:700;letter-spacing:.08em;
  text-transform:uppercase;padding:3px 8px;border-radius:20px;white-space:nowrap;
  color:var(--tone);background:var(--tone-bg)}
.badge.env{color:var(--ink-3);background:var(--sunk);border:1px solid var(--edge);font-weight:600}
.stage.off .badge.env{background:var(--deck)}
.caret{font-family:var(--mono);font-size:12px;color:var(--ink-3);transition:transform .16s ease}
.head[aria-expanded=true] .caret{transform:rotate(90deg)}
.body{padding:0 14px 14px;display:flex;flex-direction:column;gap:12px;
  border-top:1px solid var(--edge)}
.body[hidden]{display:none}
.body p{margin:12px 0 0;font-size:14px;color:var(--ink-2);max-width:70ch}
.body p:first-child{margin-top:12px}
dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:5px 16px;font-size:13.5px}
dt{font-family:var(--mono);font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--ink-3);padding-top:2px}
dd{margin:0;color:var(--ink-2)}
dd code,.ent code{font-family:var(--mono)}
.pill{display:inline-block;font-family:var(--mono);font-size:11.5px;background:var(--sunk);
  border:1px solid var(--edge);border-radius:5px;padding:1px 6px;margin:0 4px 4px 0;color:var(--ink)}
.stage.off .pill{background:var(--deck)}
ol.chain{margin:0;padding-left:0;list-style:none;counter-reset:c;
  display:flex;flex-direction:column;gap:5px}
ol.chain li{counter-increment:c;font-size:13.5px;color:var(--ink-2);
  display:grid;grid-template-columns:20px 1fr;gap:9px}
ol.chain li::before{content:counter(c);font-family:var(--mono);font-size:10.5px;color:var(--tone);
  background:var(--tone-bg);border-radius:4px;height:17px;display:grid;place-items:center;
  font-weight:700;margin-top:1px}

.empty{border:1px dashed var(--edge-hi);border-radius:9px;padding:26px;text-align:center;
  color:var(--ink-3);font-size:14px}
.empty[hidden]{display:none}

/* ---- principles ---- */
.rules{background:var(--deck);border:1px solid var(--edge);border-radius:10px;
  box-shadow:var(--shadow);padding:16px 18px;display:flex;flex-direction:column;gap:12px}
.rules h2{margin:0;font-size:13px;font-family:var(--mono);letter-spacing:.12em;
  text-transform:uppercase;color:var(--ink-3);font-weight:700}
.rule{display:grid;grid-template-columns:170px 1fr;gap:4px 18px;font-size:13.5px}
.rule b{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--on);letter-spacing:-.01em}
.rule span{color:var(--ink-2);max-width:72ch}
footer{border-top:1px solid var(--edge);padding-top:16px;font-family:var(--mono);font-size:11.5px;
  color:var(--ink-3);display:flex;flex-direction:column;gap:5px}
@media (max-width:660px){
  .stage{grid-template-columns:24px 1fr;gap:0 11px}
  .stage.off{margin-left:14px}
  .stage.off::before{left:-14px;width:14px}
  .rule{grid-template-columns:1fr;gap:2px}
  .keydef{flex-direction:column;gap:1px}
  .keydef .k{flex:none}
  dl{grid-template-columns:1fr;gap:2px 0}
  dd{margin-bottom:7px}
  .badges{margin-left:0;width:100%}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="page">
  <header>
    <p class="eyebrow" id="eyebrow"></p>
    <h1>The section pipeline, stage by stage</h1>
    <p class="readout" id="readout"></p>
    <div class="stamp" id="stamp"></div>
  </header>

  <div class="deck">
    <div class="deck-row">
      <input type="search" id="q" placeholder="Search stages, scripts, notes…" aria-label="Search stages">
      <select id="env" aria-label="Filter by where the stage runs"></select>
      <button class="tbtn" id="expand" type="button">Expand all</button>
      <span id="tally"></span>
    </div>
    <div class="deck-row" id="chips">
      <span class="deck-lbl">Show status</span>
    </div>
    <div class="keydefs" id="keydefs"></div>
  </div>

  <div class="flow" id="flow"></div>
  <div class="empty" id="empty" hidden>No stage matches that filter.</div>

  <section class="rules" id="rules"></section>

  <footer id="prov"></footer>
</div>

<script id="data" type="application/json">__PAYLOAD__</script>
<script>
(function(){
"use strict";
var D = JSON.parse(document.getElementById("data").textContent);
var esc = function(s){ return String(s == null ? "" : s)
  .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); };
var toneOf = {};
D.statuses.forEach(function(s){ toneOf[s.name] = s.tone; });

/* ---- masthead ---- */
document.getElementById("eyebrow").textContent = D.pipeline;
document.getElementById("readout").textContent = "Readout: " + D.readout + ".";
document.getElementById("stamp").innerHTML =
    "<span><b>generated from</b> " + esc(D.source) + "</span>" +
  "<span><b>stage list updated</b> " + esc(D.updated) + "</span>" +
  "<span><b>schema</b> v" + esc(D.schemaVersion) + "</span>" +
  "<span><b>" + D.stages.length + "</b> stages</span>";

/* ---- status chips + their definitions, both straight from the file ---- */
var chips = document.getElementById("chips");
var shown = {};
D.statuses.forEach(function(s){
  shown[s.name] = true;
  var b = document.createElement("button");
  b.type = "button"; b.className = "sbtn tone-" + s.tone;
  b.setAttribute("aria-pressed","true");
  b.dataset.status = s.name;
  b.innerHTML = '<span class="dot"></span>' + esc(s.name) + ' <span class="n">' + s.count + "</span>";
  b.addEventListener("click", function(){
    shown[s.name] = !shown[s.name];
    b.setAttribute("aria-pressed", String(shown[s.name]));
    apply();
  });
  chips.appendChild(b);
});
document.getElementById("keydefs").innerHTML = D.statuses.map(function(s){
  return '<div class="keydef tone-' + s.tone + '"><span class="k">' + esc(s.name) + "</span>" +
         "<span>" + esc(s.blurb || "—") + "</span></div>";
}).join("");

/* ---- environment filter ---- */
var envSel = document.getElementById("env");
var envs = [];
D.stages.forEach(function(s){
  s.envTokens.forEach(function(t){ if (envs.indexOf(t) < 0) envs.push(t); });
});
envs.sort();
envSel.innerHTML = '<option value="">Anywhere it runs</option>' + envs.map(function(e){
  var note = D.environments[e];
  var label = e.replace(/`/g, "");
  return '<option value="' + esc(e) + '">' + esc(label) + (note ? " — " + esc(note) : "") + "</option>";
}).join("");

/* ---- stage cards ---- */
function detailRows(s){
  var rows = "";
  function row(label, value){ rows += "<dt>" + esc(label) + "</dt><dd>" + value + "</dd>"; }
  function pills(list){ return list.map(function(x){
    return '<span class="pill">' + esc(x) + "</span>"; }).join(""); }
  if (s.entry.length)   row(s.entry.length > 1 ? "entry points" : "entry point", pills(s.entry));
  row("runs in", esc(s.env || "—") + (s.envNote ? ' <span style="color:var(--ink-3)">— ' +
      esc(s.envNote) + "</span>" : ""));
  if (s.kind)           row("kind", esc(s.kind));
  if (s.inputs.length)  row("takes", pills(s.inputs));
  if (s.outputs.length) row("writes", pills(s.outputs));
  if (s.knobs.length)   row("knobs", pills(s.knobs));
  s.extras.forEach(function(x){ row(x.label, esc(x.value)); });
  return rows ? "<dl>" + rows + "</dl>" : "";
}

var flow = document.getElementById("flow");
flow.innerHTML = D.stages.map(function(s, i){
  var tone = toneOf[s.status] || "unknown";
  var chain = s.chain.length
    ? "<ol class=\"chain\">" + s.chain.map(function(c){ return "<li><span>" + esc(c) + "</span></li>"; }).join("") + "</ol>"
    : "";
  return '<div class="stage tone-' + tone + (s.onSpine ? "" : " off") + '" id="stage-' + esc(s.id) +
      '" data-i="' + i + '">' +
      '<div class="rail"><div class="pip">' + (s.step == null ? "·" : s.step) + "</div></div>" +
      '<div class="card">' +
        '<button class="head" type="button" aria-expanded="false" aria-controls="body-' + esc(s.id) + '">' +
          '<span class="nm">' + esc(s.name) + "</span>" +
          (s.entry.length ? '<span class="ent">' + esc(s.entry[0]) +
              (s.entry.length > 1 ? " +" + (s.entry.length - 1) : "") + "</span>" : "") +
          '<span class="badges">' +
            (s.env ? '<span class="badge env">' + esc(s.env) + "</span>" : "") +
            '<span class="badge">' + esc(s.status) + "</span>" +
            '<span class="caret">›</span>' +
          "</span>" +
        "</button>" +
        '<div class="body" id="body-' + esc(s.id) + '" hidden>' +
          (s.notes ? "<p>" + esc(s.notes) + "</p>" : "") +
          chain +
          detailRows(s) +
        "</div>" +
      "</div></div>";
}).join("");

/* ---- expand / collapse ---- */
var heads = Array.prototype.slice.call(flow.querySelectorAll(".head"));
function setOpen(head, open){
  head.setAttribute("aria-expanded", String(open));
  document.getElementById(head.getAttribute("aria-controls")).hidden = !open;
}
heads.forEach(function(h){
  h.addEventListener("click", function(){
    setOpen(h, h.getAttribute("aria-expanded") !== "true");
    syncExpandBtn();
  });
});
var expandBtn = document.getElementById("expand");
function visibleHeads(){
  return heads.filter(function(h){ return !h.closest(".stage").hidden; });
}
function syncExpandBtn(){
  var vis = visibleHeads();
  var allOpen = vis.length > 0 && vis.every(function(h){
    return h.getAttribute("aria-expanded") === "true"; });
  expandBtn.textContent = allOpen ? "Collapse all" : "Expand all";
  expandBtn.dataset.mode = allOpen ? "collapse" : "expand";
}
expandBtn.addEventListener("click", function(){
  var open = expandBtn.dataset.mode !== "collapse";
  visibleHeads().forEach(function(h){ setOpen(h, open); });
  syncExpandBtn();
});

/* ---- filtering ---- */
var haystacks = D.stages.map(function(s){
  return [s.id, s.name, s.status, s.kind, s.env, s.notes,
          s.entry.join(" "), s.inputs.join(" "), s.outputs.join(" "),
          s.knobs.join(" "), s.chain.join(" "),
          s.extras.map(function(x){ return x.label + " " + x.value; }).join(" ")
         ].join(" ").toLowerCase();
});
var cards = Array.prototype.slice.call(flow.querySelectorAll(".stage"));
var q = document.getElementById("q");
var tally = document.getElementById("tally");
var empty = document.getElementById("empty");

function apply(){
  var term = q.value.trim().toLowerCase();
  var wantEnv = envSel.value;
  var n = 0;
  cards.forEach(function(card, i){
    var s = D.stages[i];
    var ok = shown[s.status] !== false
      && (!term || haystacks[i].indexOf(term) >= 0)
      && (!wantEnv || s.envTokens.indexOf(wantEnv) >= 0);
    card.hidden = !ok;
    if (ok) n++;
  });
  tally.textContent = n + " / " + D.stages.length + " shown";
  empty.hidden = n > 0;
  syncExpandBtn();
}
q.addEventListener("input", apply);
envSel.addEventListener("change", apply);

/* ---- principles ---- */
document.getElementById("rules").innerHTML =
  "<h2>Rules that hold across every stage</h2>" +
  D.principles.map(function(p){
    return '<div class="rule"><b>' + esc(p.label) + "</b><span>" + esc(p.text) + "</span></div>";
  }).join("");

/* ---- provenance ---- */
document.getElementById("prov").innerHTML =
  "<span>Generated from " + esc(D.source) + " by docs/build_pipeline_map.py — edit the YAML, re-run, re-publish.</span>" +
  "<span>Numbered pips are the default path. Dashed, indented cards are off it: parked beside the line at the point they attach, not removed from it.</span>";

/* ---- deep link ---- */
apply();
if (location.hash) {
  var t = document.getElementById(location.hash.slice(1));
  if (t) {
    var h = t.querySelector(".head");
    if (h) { setOpen(h, true); syncExpandBtn(); }
    t.scrollIntoView({block:"center"});
  }
}
})();
</script>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC, help="pipeline-stages.yml")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="HTML to write")
    args = ap.parse_args()

    print(f"Reading {args.src}...")
    payload = build_payload(args.src)
    counts = ", ".join(f"{s['name']}={s['count']}" for s in payload["statuses"])
    print(f"  {len(payload['stages'])} stages ({counts})")

    blob = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    blob = blob.replace("</", "<\\/")          # never break out of <script>
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(PAGE.replace("__PAYLOAD__", blob), encoding="utf-8")
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
