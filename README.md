# GeCo Desktop

GeCo Desktop is a native Windows/macOS project preparation and launcher application for [Text Analysis Lab (TeAL)](https://github.com/zacthinks/text-analysis-lab) and [GeCo](https://github.com/zacthinks/GeCo). Researchers can create a portable project, import documents, preview and prepare text, choose representations and open the linked GeCo coding workspace in a local browser.

**Status: draft MVP, under integration and installer qualification.** Native installers and preparation tools are implemented but have not yet completed clean-machine/user acceptance. Do not treat draft CI artifacts as a supported release.

## How it works

- The PySide6 desktop application manages project creation, import/preparation steps, model resources and browser sessions.
- TeAL owns all durable scientific artifacts, transformations, fitted representations, lineage and interrupted operation resumption. GeCo owns interactive coding. The desktop GUI does not import either library directly.
- Each portable `.gecod/` folder contains a `project.gecod` descriptor and a regular `.teal/` project. Shared scientific Python environments are kept **outside** project folders.
- New projects record pinned scientific versions and a fully resolved, cross-platform requirements snapshot. The desktop application provisions/reuses a shared environment with `uv`, after the user authorizes installation.
- The native application packages verified pure-Python TeAL and GeCo wheels as install sources, while third-party dependencies are resolved from their normal package indexes. **Bundled science wheels do not mean all third-party dependencies are available offline.** The wheelhouse is needed for the default scientific packages that have not been published to the package registry.
- Browser sessions can continue after closing the Desktop window; reopening a project reconnects to an existing managed session where possible.

Optional PDF, embedding and spaCy features may require extra dependencies and model resources. Unavailable features are reported before execution; models are not downloaded automatically.

## Development

Python 3.11+ is required for development only. To work on the application source:

```bash
python -m pip install -e '.[gui,dev]'
python -m geco_desktop
pytest -q
ruff check src tests
```

Building the native app also requires Git, `uv`, PyInstaller and the application GUI dependencies. Produce the tested scientific wheels first, then build the native bundle:

```bash
python packaging/build_science_wheels.py --output science-wheels
python packaging/build.py --output dist-native
```

The science-wheel builder checks out explicit tested upstream revisions and requires cross-platform pure-Python wheels. These revisions are build inputs, not runtime Git dependencies for researchers.

## Qualification

The automated workflows separately validate unit/GUI behavior, the real TeAL–GeCo scientific pipeline, portable scientific environment reconstruction across Windows/macOS/Linux, and native application builds. Native builds additionally check that bundled wheels can resolve and install the default science environment. Passing these checks does not replace a clean-machine installation and hands-on real-data UX test.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for development checks and [SECURITY.md](SECURITY.md) for reporting security-sensitive issues.

## License

GeCo Desktop is licensed under the [MIT License](LICENSE). Copyright © 2026 Zachary Lim.
