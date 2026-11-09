"""Build an unsigned macOS DMG from the native PyInstaller app bundle."""
from __future__ import annotations

import argparse
import platform
import subprocess
from pathlib import Path


def create_dmg(source: Path, output: Path) -> Path:
    if platform.system() != "Darwin":
        raise RuntimeError("DMG creation requires macOS.")
    application = source / "GeCo Desktop.app"
    if not application.is_dir():
        raise FileNotFoundError(f"Expected frozen application at {application}")
    output.mkdir(parents=True, exist_ok=True)
    disk = output / "GeCoDesktop-macOS.dmg"
    subprocess.run(
        [
            "hdiutil", "create", "-volname", "GeCo Desktop",
            "-srcfolder", str(application), "-ov", "-format", "UDZO", str(disk),
        ],
        check=True,
    )
    if not disk.is_file():
        raise RuntimeError(f"Missing DMG after successful hdiutil: {disk}")
    return disk


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(create_dmg(args.source.resolve(), args.output.resolve()))
