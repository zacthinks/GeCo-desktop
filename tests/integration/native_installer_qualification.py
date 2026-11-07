"""Qualify the *installed* native application rather than its build tree.

Runs on ephemeral GitHub-hosted Windows/macOS runners after installers are built.
No TeAL projects, network model downloads, or pre-existing user app state needed.
"""

from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _run(command: list[str], *, timeout: int = 240) -> None:
    result = subprocess.run(
        command, text=True, capture_output=True, timeout=timeout, check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {command!r}\n"
            f"stdout: {result.stdout[-2500:]}\nstderr: {result.stderr[-2500:]}"
        )


def _self_check(executable: Path, directory: Path) -> None:
    assert executable.is_file(), f"Installed application executable missing: {executable}"
    marker = directory / "installed-app-check.txt"
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [str(executable), "--self-check", str(marker)],
        cwd=directory, env=env, capture_output=True, text=True, timeout=120,
        check=False,
    )
    if result.returncode or not marker.is_file():
        raise RuntimeError(
            f"Installed app did not pass self-check ({result.returncode}): "
            f"stdout={result.stdout[-1000:]!r} stderr={result.stderr[-1000:]!r}"
        )
    assert "self-check passed" in marker.read_text(encoding="utf-8")


def windows(installer: Path, directory: Path) -> None:
    import winreg

    installed = directory / "GeCo Desktop installation"
    executable = installed / "GeCo Desktop.exe"
    # Use the per-user default mode. Explicit file association exercises the
    # documented optional Inno task without touching system-wide registry.
    _run([
        str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
        "/TASKS=fileassoc", f"/DIR={installed}",
    ], timeout=360)
    _self_check(executable, directory)

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gecod") as key:
        association, _ = winreg.QueryValueEx(key, "")
        assert association == "GeCoDesktop.Project", association

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Classes\GeCoDesktop.Project\shell\open\command",
    ) as key:
        command, _ = winreg.QueryValueEx(key, "")
        assert str(executable).lower() in command.lower(), command
        assert '"%1"' in command, command

    uninstaller = installed / "unins000.exe"
    assert uninstaller.is_file(), "Windows installed app has no uninstaller"
    _run(
        [str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
        timeout=240,
    )
    assert not executable.exists(), "Windows uninstall left application executable"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.gecod") as key:
            remaining, _ = winreg.QueryValueEx(key, "")
            assert remaining != "GeCoDesktop.Project", remaining
    except FileNotFoundError:
        pass
    print("PASS: per-user Inno install, packaged app launch, association and uninstall")


def macos(dmg: Path, directory: Path) -> None:
    mount = directory / "GeCo Desktop mounted volume"
    mount.mkdir(parents=True)
    attached = False
    try:
        _run([
            "hdiutil", "attach", "-nobrowse", "-readonly",
            "-mountpoint", str(mount), str(dmg),
        ], timeout=120)
        attached = True
        source = mount / "GeCo Desktop.app"
        assert source.is_dir(), f"Missing application inside DMG: {source}"

        installed = directory / "GeCo Desktop.app"
        shutil.copytree(source, installed, symlinks=True)
    finally:
        if attached:
            _run(["hdiutil", "detach", str(mount)], timeout=120)

    with (installed / "Contents" / "Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    assert info["CFBundleIdentifier"] == "org.geco.desktop"
    document_types = info.get("CFBundleDocumentTypes", [])
    assert any(
        "gecod" in doc.get("CFBundleTypeExtensions", [])
        for doc in document_types
    ), "Copied app does not advertise .gecod project descriptor support"

    _self_check(installed / "Contents" / "MacOS" / "GeCo Desktop", directory)
    print("PASS: mount DMG, copy application, validate .gecod registration and launch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--installer", type=Path, required=True)
    args = parser.parse_args()
    installer = args.installer.resolve()
    assert installer.is_file(), installer
    with tempfile.TemporaryDirectory(prefix="gecod-installed-app-") as folder:
        directory = Path(folder)
        if sys.platform == "win32":
            windows(installer, directory)
        elif sys.platform == "darwin":
            macos(installer, directory)
        else:
            parser.error("Installer qualification runs only on Windows and macOS")


if __name__ == "__main__":
    main()
