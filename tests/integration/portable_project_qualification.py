"""Opt-in real uv portability qualification for Desktop-created research files.

This requires network access to official TeAL/GeCo release assets and PyPI.
It is deliberately excluded from the default quick unit test suite.
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from geco_desktop.environments import EnvironmentManager
from geco_desktop.portable_project import resolve_project_files
from geco_desktop.project import RuntimeSpec
from geco_desktop.science_releases import DEFAULT_PYTHON, GECO, TEAL


def qualify(uv: str) -> None:
    with tempfile.TemporaryDirectory(prefix="gecod-uv-portability-") as directory:
        scratch = Path(directory)
        manager = EnvironmentManager(base=scratch / "local-profiles", uv=uv)
        runtime = RuntimeSpec(DEFAULT_PYTHON, TEAL.version, GECO.version)
        files = resolve_project_files(manager, "Portable interview analysis", runtime)
        assert "https://github.com/" in files.pyproject
        assert "file://" not in files.lock
        assert "gecod-project-lock-" not in files.lock
        project = scratch / "Research.gecod"
        project.mkdir()
        files.write(project)
        moved = scratch / "Moved Research.gecod"
        project.rename(moved)
        assert not (moved / ".venv").exists()
        subprocess.run([uv, "lock", "--check", "--project", str(moved)], check=True)
        frozen = subprocess.run(
            [uv, "export", "--frozen", "--project", str(moved),
             "--no-dev", "--no-emit-project", "--format", "requirements.txt"],
            check=True, capture_output=True, text=True,
        ).stdout
        assert "text-analysis-lab" in frozen
        assert "geometric-coder" in frozen
        assert "https://github.com/" in frozen
        assert str(scratch) not in frozen
        assert files.lock == (moved / "uv.lock").read_text(encoding="utf-8")
        print("PASS: official source lock, project move and frozen export")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--uv", default="uv")
    args = parser.parse_args()
    qualify(args.uv)
