"""Standalone PyInstaller entry point; scientific runtime stays external."""

from geco_desktop.app import main

if __name__ == "__main__":
    raise SystemExit(main())
