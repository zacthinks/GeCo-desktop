# Development guidance for coding agents

This is a **public** Python repository for the GeCo Desktop application. Keep code changes small, testable, and compatible with the project boundaries described in README.md.

## Architecture invariants

- The desktop GUI uses PySide6. The GUI process must **not import TeAL or GeCo**.
- The lightweight, application-owned backend runner is updated with GeCo Desktop and invoked through the project's selected Python interpreter. **Do not install or freeze a separate runner into each project's scientific environment.**
- TeAL and GeCo own scientific artifacts, preprocessing, coding and their databases. Use their public APIs; do not duplicate algorithms or edit their internal catalogs.
- Research projects are portable directory-backed `.gecod` documents containing the small descriptor and real TeAL state, **not** virtual environments. Keep shared scientific environments and caches in per-user application data.
- Scientific environment profiles are immutable once shared. Do not silently update pinned dependencies, substitute model versions, or create hidden project-local environments.
- Keep the GeCo browser session separate from the Desktop GUI; localhost only, no debug server or duplicate writer for a project.
- Keep the UI consistent with the shipped GeCo visual identity while respecting native OS accessibility.

## Change and test discipline

- Work on a feature branch and submit a pull request to `main`. Do not bypass required checks, rewrite published history, or merge with failing/pending CI.
- For Python changes run `ruff check src tests` and `pytest -q`; run the Qt smoke test when changing the shell, and check Windows/macOS CI for OS-facing changes.
- Never report tests as passing unless they actually ran against the proposed commit. Include failures, skipped tests and environmental limitations in the PR.
- Add focused regression tests for bug fixes. Avoid placeholder modules, oversized abstractions or new services without a demonstrated need.
- Files that could contain research documents, tokens, scientific outputs, local environments or signing secrets must not be committed.
- PR titles and descriptions must stand alone for public readers. Do not include confidential notes, unpublished documents, credentials, personal data, non-public source links or implementation handoff details. Inspect the **first public PR description before creation**, not just after CI.
- Favor safe, reversible operations and preserve materialized TeAL data and GeCo judgments.

## Project scope

The initial release targets a native installer, model/environment management, an interactive TeAL preparation wizard, and handoff to GeCo's existing browser UI. An independent scientific engine, custom plugin runtime, unrestricted workflow editor and embedded GeCo browser are not part of the initial implementation.
