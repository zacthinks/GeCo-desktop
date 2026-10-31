"""Archive native application bundles without losing POSIX executable permissions."""
from __future__ import annotations

import argparse
import platform
import tarfile
import zipfile
from pathlib import Path


def archive(source: Path, destination: Path) -> Path:
    if not source.is_dir():
        raise FileNotFoundError(source)
    destination.mkdir(parents=True, exist_ok=True)
    if platform.system() == "Windows":
        result = destination / "geco-desktop-windows.zip"
        with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as file:
            for path in source.rglob("*"):
                if path.is_file():
                    file.write(path, arcname=path.relative_to(source))
    else:
        result = destination / "geco-desktop-macos.tar.gz"
        with tarfile.open(result, "w:gz", dereference=False) as file:
            for path in source.iterdir():
                file.add(path, arcname=path.name, recursive=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(archive(args.source, args.destination))
