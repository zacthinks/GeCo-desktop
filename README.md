# GeCo Desktop

A small, local-first desktop launcher for TeAL-linked GeCo research workspaces.

GeCo Desktop helps researchers select an existing [Text Analysis Lab (TeAL)](https://github.com/zacthinks/text-analysis-lab) project, choose its keyed artifacts, create or reopen a linked [GeCo](https://github.com/zacthinks/GeCo) workspace, and launch the existing GeCo browser interface.

Scientific transformations and artifact storage remain in TeAL. Coding state and the interactive research interface remain in GeCo. GeCo Desktop does not create an independent analytics engine.

## Status

Early development. The desktop frontend and tested launcher workflow are being implemented. There is no packaged installer yet.

## Planned workflow

1. Select an existing TeAL project directory.
2. Select keyed documents, text and existing geometry/projection artifacts.
3. Create a named linked GeCo workspace or reopen one already on disk.
4. Launch its existing local GeCo browser UI.

The first release deliberately does not implement fitting, topic-model management, or a preprocessing workflow designer.

## Development

Python 3.11+ is required. The application will use the Python standard-library Tkinter GUI; some Linux distributions package Tkinter separately. Consult the project configuration once the package and entry point are added.

## License

A license has not yet been selected.
