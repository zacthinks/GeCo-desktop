"""Build a native, self-contained GeCo Desktop application directory.

Requires PyInstaller and a locally available uv executable. Bundles the
current app-owned backend resources, not TeAL/GeCo science environments.
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def build(output: Path, *, uv: str | None = None) -> None:
    from geco_desktop.environments import installed_runner_path

    runner = installed_runner_path()
    workflow = runner.with_name("workflow.py")
    if not workflow.is_file():
        raise FileNotFoundError("App-owned workflow resource was not installed.")
    uv_path = shutil.which(uv or "uv")
    if uv_path is None:
        raise FileNotFoundError(
            "The builder needs a uv executable. Install uv before packaging the GUI."
        )
    entry = Path(__file__).resolve().parents[1] / "src" / "geco_desktop" / "__main__.py"
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--name", "GeCo Desktop",
        "--distpath", str(output), "--workpath", str(output / "build"),
        "--specpath", str(output / "spec"),
        "--add-data", f"{runner}{os.pathsep}backend",
        "--add-data", f"{workflow}{os.pathsep}backend",
        "--add-binary", f"{uv_path}{os.pathsep}.",
        str(entry),
    ]
    subprocess.run(command, check=True)
    print("Created native application in", output)
    print("Platform:", platform.system(), platform.machine())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist-native"))
    parser.add_argument("--uv", default=None)
    args = parser.parse_args()
    build(args.output.resolve(), uv=args.uv)
