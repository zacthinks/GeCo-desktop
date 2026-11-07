# Contributing to GeCo Desktop

GeCo Desktop makes [geometric coding](https://github.com/zacthinks/GeCo) accessible without Python. Its role is to guide researchers through project preparation and launch the existing GeCo research workspace. [TeAL](https://github.com/zacthinks/text-analysis-lab) owns the scientific project, transformations and analytical history; GeCo owns coding and exploration. Desktop should not duplicate their scientific logic.

For researchers installing the application, start with the [README](README.md) and the [first-project guide](docs/getting-started.md). The instructions below are **only for contributors**.

## Development setup

Use Python 3.11 or newer:

```bash
python -m venv .venv
# Activate the development environment for your shell, then:
python -m pip install -e '.[gui,dev]'
python -m geco_desktop
```

Run the usual tests before opening a pull request:

```bash
ruff check src tests
pytest -q
```

The CI workflows also test the actual TeAL–GeCo integration, portable runtime reconstruction, and Windows/macOS application bundles.

## Building preview installers

Native building requires Git, uv, PyInstaller, and relevant platform packaging tools. The build system acquires the scientific packages specified in [science_releases.py](src/geco_desktop/science_releases.py); do not quietly replace their validated release versions with arbitrary repository heads.

```bash
python -m pip install -e '.[gui]' 'pyinstaller>=6.10,<7'
python packaging/build_science_wheels.py --output science-wheels
python packaging/build.py --output dist-native
```

The native CI workflow additionally builds a per-user Windows installer or an unsigned macOS DMG, installs or copies it, and exercises the actual application. Its download artifacts are development previews, not published releases.

When upstream [GeCo](https://github.com/zacthinks/GeCo/releases) or [TeAL](https://github.com/zacthinks/text-analysis-lab/releases) releases change, update the validated release catalog and run scientific integration and native installer checks. Existing projects retain their recorded scientific version and dependency lock instead of being silently upgraded.

## Contributions

Please open a pull request against `main` with a concise description, the tests actually run, and any known limitations. Avoid committing research datasets, project folders, caches, downloaded models, or credentials. Keep user-facing instructions approachable; place build details in contributor documentation rather than requiring researchers to understand them.

For security-sensitive issues, see [SECURITY.md](SECURITY.md).
