"""Portable project lock tests without network or scientific imports."""

from __future__ import annotations

import hashlib
import tomllib
from pathlib import Path

import pytest

from geco_desktop.portable_project import (
    LockedProjectFiles,
    project_metadata,
    resolve_project_files,
)
from geco_desktop.project import RuntimeSpec


def test_project_metadata_is_ordinary_uv_project_with_exact_direct_versions():
    spec = RuntimeSpec(
        "3.11", "0.10.0", "0.9.0",
        locked_packages=(
            "text-analysis-lab[pdf,spacy]==0.10.0",
            "geometric-coder==0.9.0",
        ),
    )
    data = tomllib.loads(project_metadata("My Interview Study", spec))
    assert data["project"]["name"] == "geco-my-interview-study"
    assert data["project"]["requires-python"] == ">=3.11,<3.12"
    assert len(data["project"]["dependencies"]) == 2
    for package in data["project"]["dependencies"]:
        assert package.startswith(("text-analysis-lab", "geometric-coder"))
        assert "https://github.com/" in package
        assert "#sha256=" in package
    assert data["tool"]["uv"]["package"] is False


def test_raises_for_unrecognized_python_minor():
    with pytest.raises(ValueError, match="Python major.minor"):
        project_metadata("A", RuntimeSpec("python", "0.11.0", "0.10.0"))


def test_lock_and_export_use_one_uv_resolution_and_no_project_local_venv(tmp_path):
    calls = []

    class Manager:
        uv = "uv"

        def _uv(self, *args):
            calls.append(args)
            project_root = Path(args[args.index("--project") + 1])
            assert (project_root / "pyproject.toml").is_file()
            if args[0] == "lock":
                (project_root / "uv.lock").write_text('version = 1\n', encoding="utf-8")
            elif args[0] == "export":
                destination = Path(args[args.index("--output-file") + 1])
                destination.write_text(
                    "geometric-coder==0.10.0\ntext-analysis-lab==0.11.0\n",
                    encoding="utf-8",
                )

    spec = RuntimeSpec("3.11", "0.11.0", "0.10.0")
    result = resolve_project_files(Manager(), "Scientific project", spec)
    assert len(calls) == 2
    assert calls[0][:2] == ("lock", "--project")
    assert calls[1][0] == "export"
    assert "--find-links" not in calls[0]
    assert "--frozen" in calls[1]
    assert "--no-emit-project" in calls[1]
    assert result.digest == hashlib.sha256(result.lock.encode()).hexdigest()
    assert "geometric-coder==0.10.0" in result.requirements
    root = tmp_path / "study.gecod"
    root.mkdir()
    result.write(root)
    assert (root / "uv.lock").read_text() == result.lock
    assert (root / "pyproject.toml").read_text() == result.pyproject
    assert ".venv" not in {x.name for x in root.iterdir()}
    assert not (root / "requirements.txt").exists()


def test_portable_project_files_never_overwrite_old_research(tmp_path):
    files = LockedProjectFiles("[project]\n", "version = 1\n", "a==1\n")
    (tmp_path / "uv.lock").write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError, match="uv.lock"):
        files.write(tmp_path)
    assert (tmp_path / "uv.lock").read_text() == "original"
    assert not (tmp_path / "pyproject.toml").exists()


def test_empty_lock_or_dependency_export_is_rejected(tmp_path):
    class Manager:
        uv = "uv"

        def _uv(self, *args):
            root = Path(args[args.index("--project") + 1])
            if args[0] == "lock":
                (root / "uv.lock").write_text("version = 1\n")
            else:
                Path(args[args.index("--output-file") + 1]).write_text("")

    with pytest.raises(RuntimeError, match="empty"):
        resolve_project_files(Manager(), "Study", RuntimeSpec("3.11", "0.11.0", "0.10.0"))
