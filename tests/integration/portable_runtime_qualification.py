"""Real scientific environment qualification, separate from mocked unit tests.

Resolve on Linux; install the same project descriptor on Windows/macOS/Linux.
All environments and diagnostics are in CI temp storage, never the .gecod folder.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from geco_desktop.environments import (
    EnvironmentManager,
    installed_runner_path,
    run_command,
    runtime_with_features,
)
from geco_desktop.project import ProjectDescriptor, read_descriptor, write_descriptor
from geco_desktop.science_releases import DEFAULT_PYTHON, GECO, TEAL


def resolve(output: Path, *, uv: str, pdf: bool, pinned_git: bool) -> None:
    manager = EnvironmentManager(base=output / "profiles", uv=uv)
    requested = runtime_with_features(
        DEFAULT_PYTHON, TEAL.version, GECO.version, pdf=pdf,
    )
    if pinned_git:
        # CI-only qualification of known tested sources until releases exist.
        # Never substitute these URLs for the normal user-facing defaults.
        requested = replace(requested, locked_packages=(
            f"text-analysis-lab[pdf] @ git+https://github.com/{TEAL.repository}.git@{TEAL.commit}",
            f"geometric-coder @ git+https://github.com/{GECO.repository}.git@{GECO.commit}",
        ))
    locked = manager.resolve(requested)
    assert locked.resolved_requirements, "Universal resolver did not return a lock"
    assert manager.resolve(locked) == locked, "Locked profile must not re-resolve"

    # A project carries a portable spec, never a copy of the environment.
    project = output / "Qualification.gecod"
    project.mkdir(parents=True, exist_ok=False)
    descriptor = ProjectDescriptor.new("Qualification", locked)
    write_descriptor(project, descriptor)

    loaded = read_descriptor(project)[1]
    assert loaded == descriptor
    assert ".venv" not in {p.name for p in project.iterdir()}
    digest = hashlib.sha256(locked.resolved_requirements.encode()).hexdigest()
    print(
        f"Resolved universal requirements: {len(locked.resolved_requirements.splitlines())} "
        f"lines, SHA256 {digest}",
        flush=True,
    )


def install(project: Path, *, uv: str, output: Path) -> None:
    source, descriptor = read_descriptor(project)
    assert descriptor.runtime.resolved_requirements, "Expected portable resolved lock"
    before = (source / "project.gecod").read_bytes()
    fingerprint_before = hashlib.sha256(before).hexdigest()

    manager = EnvironmentManager(base=output / "shared-runtime", uv=uv)
    interpreter = manager.ensure(descriptor.runtime)
    assert interpreter.is_file()
    assert manager.locate(descriptor.runtime) == interpreter
    # Reopening the project must reuse rather than alter a ready runtime.
    assert manager.ensure(descriptor.runtime) == interpreter

    ping = run_command(interpreter, installed_runner_path(), "ping")
    assert ping["runner_protocol"] == 1, ping
    supported = run_command(interpreter, installed_runner_path(), "capabilities", timeout=180)
    for name in ("clean", "count", "tfidf", "svd", "umap"):
        assert supported["operations"][name]["available"], (name, supported)

    script = (
        "from importlib.metadata import version;"
        "from text_analysis_lab import Project;"
        "assert Project is not None;"
        "print(version('text-analysis-lab'));"
        "print(version('geometric-coder'))"
    )
    probe = subprocess.run(
        [str(interpreter), "-c", script],
        capture_output=True, text=True, check=True, timeout=120,
    )
    versions = probe.stdout.splitlines()
    assert versions == [descriptor.runtime.teal, descriptor.runtime.geco], versions

    target = output / "relocated.gecod"
    shutil.move(str(source), str(target))
    moved, restored = read_descriptor(target / "project.gecod")
    assert moved == target.resolve() and restored == descriptor
    assert hashlib.sha256((moved / "project.gecod").read_bytes()).hexdigest() == fingerprint_before
    assert not (moved / ".venv").exists()
    assert manager.locate(restored.runtime) == interpreter
    print(
        f"PASS: {sys.platform}, locked TeAL {versions[0]}, GeCo {versions[1]}, "
        f"moved descriptor and reusable shared interpreter",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["resolve", "install"])
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--pdf", action="store_true")
    parser.add_argument("--pinned-git", action="store_true")
    args = parser.parse_args()
    args.output = args.output.absolute()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.step == "resolve":
        resolve(args.output, uv=args.uv, pdf=args.pdf, pinned_git=args.pinned_git)
    else:
        if args.project is None:
            parser.error("--project is required for install")
        install(args.project, uv=args.uv, output=args.output)


if __name__ == "__main__":
    main()
