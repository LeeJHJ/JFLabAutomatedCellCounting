# docs/assets/ — screenshot placeholders

The `.png` files in this directory are **1x1 stub images**, not real
screenshots. They exist only so `mkdocs build --strict` resolves every
`![...](assets/*.png)` link in `docs/runbook/01-registration.md` and
`docs/runbook/02-detection.md` without a broken-link warning (D-18a).

Each stub is referenced from a runbook doc that also carries a bold
**"Screenshot to be captured during the 06.1-06 operator validation run"**
note near the top. Replace the stub files with real annotated screenshots
captured during that run — same filenames, so the runbook links keep
working with no further edits.

This file (and `.gitkeep`) can be deleted once every `*.png` here is a real
screenshot.
