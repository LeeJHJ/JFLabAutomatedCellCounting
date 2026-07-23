# Runbook

The full operator tutorial for this pipeline (czi → MIP → ABBA registration →
BraiAnDetect → classify → export → per-region table) lives in
[`docs/`](docs/index.md), rendered as a searchable MkDocs Material site.

- **Preview locally:** `pip install -r requirements-docs.txt && mkdocs serve`,
  then open <http://127.0.0.1:8000>.
- **Read online:** once published (`mkdocs gh-deploy`, an opt-in manual step —
  see the "Publish this tutorial" section of `docs/index.md`), the tutorial is
  available at the GitHub Pages URL for this repo.

`docs/` is the single source of truth; this file is only a pointer so the
repo landing page finds a runbook.
