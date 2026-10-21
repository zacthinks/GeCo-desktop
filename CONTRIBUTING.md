# Contributing to GeCo Desktop

GeCo Desktop is at an early development stage. Contributions should be small, clearly scoped, and tested. The project integrates with the public [Text Analysis Lab](https://github.com/zacthinks/text-analysis-lab) and [GeCo](https://github.com/zacthinks/GeCo) APIs.

## Development setup

Developers need Python 3.11 or newer. The final user-facing installer is intended to manage its own Python runtime; these steps are **for contributors only**.

```bash
python -m venv .venv
# Activate the development environment for your shell, then:
python -m pip install -e '.[gui,dev]'
python -m geco_desktop
```

Run `ruff check src tests` and `pytest -q` before sending a PR. The GitHub Actions workflow checks these on Ubuntu, checks the Qt shell, runs Windows and macOS smoke tests, and builds a wheel.

Please open a PR against `main` with a concise description, a list of the actual tests run, and any known limitations. Do not add downloaded datasets, project folders, private files, package caches or credentials to the repository. Scientific transformations belong in TeAL; interactive coding belongs in GeCo. GeCo Desktop orchestrates the workflow.

For security-sensitive issues, see [SECURITY.md](SECURITY.md).
