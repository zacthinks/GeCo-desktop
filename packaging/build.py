"""Build a native, self-contained GeCo Desktop application directory.

Requires PyInstaller and a locally available uv executable. Bundles the
current app-owned backend resources, not TeAL/GeCo science environments.
"""
from __future__ import annotations

import argparse
import os
import platform
import plistlib
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
    wheels = Path(__file__).resolve().parents[1] / "science-wheels"
    from geco_desktop.science_releases import RELEASES

    expected_wheels = {release.wheel for release in RELEASES}
    if not wheels.is_dir() or {wheel.name for wheel in wheels.glob("*.whl")} != expected_wheels:
        raise FileNotFoundError("Build the verified scientific wheelhouse before packaging.")
    entry = Path(__file__).resolve().parents[1] / "packaging" / "entry.py"
    output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onedir", "--windowed", "--name", "GeCo Desktop",
        "--distpath", str(output), "--workpath", str(output / "build"),
        "--specpath", str(output / "spec"),
        "--add-data", f"{runner}{os.pathsep}backend",
        "--add-data", f"{workflow}{os.pathsep}backend",
        "--add-data", f"{wheels}{os.pathsep}science-wheels",
        "--add-binary", f"{uv_path}{os.pathsep}.",
        str(entry),
    ]
    subprocess.run(command, check=True)
    # Some Windows PyInstaller versions classify the uv launcher as an external
    # executable and omit it from the bundle despite --add-binary. Explicitly
    # publish the exact binary at the frozen resource lookup path.
    if os.name == "nt":
        bundled = output / "GeCo Desktop" / "_internal"
        bundled.mkdir(parents=True, exist_ok=True)
        shutil.copy2(uv_path, bundled / "uv.exe")
        if not (bundled / "uv.exe").is_file():
            raise RuntimeError(f"Missing provisioner after Windows packaging: {bundled}")
        print("Windows provisioner:", bundled / "uv.exe", "size:", (bundled / "uv.exe").stat().st_size)
    if platform.system() == "Darwin":
        info_path = output / "GeCo Desktop.app" / "Contents" / "Info.plist"
        if not info_path.is_file():
            raise FileNotFoundError(f"Missing macOS application metadata: {info_path}")
        with info_path.open("rb") as stream:
            info = plistlib.load(stream)
        info["CFBundleIdentifier"] = "org.geco.desktop"
        info["CFBundleDocumentTypes"] = [{
            "CFBundleTypeName": "GeCo Desktop project",
            "CFBundleTypeExtensions": ["gecod"],
            "CFBundleTypeRole": "Editor",
            "LSHandlerRank": "Alternate",
        }]
        with info_path.open("wb") as stream:
            plistlib.dump(info, stream)
    print("Created native application in", output)
    print("Platform:", platform.system(), platform.machine())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist-native"))
    parser.add_argument("--uv", default=None)
    args = parser.parse_args()
    build(args.output.resolve(), uv=args.uv)
