# GeCo Desktop

GeCo Desktop is a cross-platform application for creating and opening [Text Analysis Lab (TeAL)](https://github.com/zacthinks/text-analysis-lab) projects linked to [GeCo](https://github.com/zacthinks/GeCo). It will guide non-programmers through document import, interactive preview, cleaning, representation selection, and handoff to GeCo's existing local browser interface.

**Status: initial application skeleton; not yet a distributable project factory.** The preprocessing wizard, Model Manager and OS installers have not been implemented.

## Architecture

- The desktop GUI is implemented with PySide6. It never imports TeAL or GeCo.
- TeAL and GeCo live in centrally managed Python environments, pinned per research project and never installed inside project directories.
- The installed application's **current** backend runner is executed by each project's selected Python interpreter. The runner invokes the public TeAL/GeCo APIs. It is not installed into or frozen with the project's scientific environment.
- A portable `.gecod` JSON descriptor lives next to an ordinary `.teal/` project directory. The researcher's GeCo state remains inside TeAL's linked workspace.
- Running GeCo browser sessions are independently supervised; closing the desktop window should not kill them.

## Development

Python 3.11+ is required **for development**; the intended finished installer will manage Python itself.

```bash
python -m pip install -e '.[gui,dev]'
python -m geco_desktop
pytest -q
ruff check src tests
```

The UI currently opens existing `.gecod` project descriptors and shows active sessions. Use of a linked GeCo workspace requires a separately installed compatible TeAL/GeCo scientific environment. The Environment Manager has an explicit `ensure()` method that uses `uv` when environment provisioning is requested; there is no automatic implicit download on project opening.

## Scope

The first technical milestone validates the application/runner boundary and session lifecycle. It does not claim to have built the scientific preparation wizard or a Windows/macOS installer. The product will retain GeCo's green visual identity and use the existing GeCo browser interface rather than embedding it.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for development and PR checks, and [SECURITY.md](SECURITY.md) for reporting security-sensitive issues.

## License

GeCo Desktop is licensed under the [MIT License](LICENSE). Copyright © 2026 Zachary Lim.
