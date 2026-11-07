"""Portable uv project metadata, independent of machine-local scientific environments.

The project lock is the durable dependency authority. For the current
transition, an exported requirements snapshot is also returned so Desktop's
existing immutable environment installer can reuse its proven staging logic.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .science_releases import GECO, TEAL

if TYPE_CHECKING:
    from .environments import EnvironmentManager
    from .project import RuntimeSpec


PROJECT_FILE = "pyproject.toml"
LOCK_FILE = "uv.lock"


@dataclass(frozen=True)
class LockedProjectFiles:
    pyproject: str
    lock: str
    requirements: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.lock.encode("utf-8")).hexdigest()

    def write(self, root: Path) -> None:
        """Install two portable files in an existing, freshly created project."""
        if not root.is_dir():
            raise ValueError("Project root must exist")
        for name in (PROJECT_FILE, LOCK_FILE):
            if (root / name).exists():
                raise FileExistsError(f"Refusing to replace existing project file: {name}")
        (root / PROJECT_FILE).write_bytes(self.pyproject.encode("utf-8"))
        # Byte-preserving write: Windows newline conversion would otherwise
        # change the SHA256 recorded in the portable project descriptor.
        (root / LOCK_FILE).write_bytes(self.lock.encode("utf-8"))


def _portable_requirement(package: str) -> str:
    """Bind published science wheels to verifiable, transferable HTTPS sources.

    uv locks resolved from a local --find-links directory can contain a
    machine-local relative wheelhouse path. Such a lock is not portable.
    """
    match = re.fullmatch(
        r"(text-analysis-lab|geometric-coder)(\[[a-zA-Z0-9_,.-]+\])?==([0-9][a-zA-Z0-9.+-]*)",
        package,
    )
    if match is None:
        return package
    name, extras, version = match.groups()
    release = TEAL if name == "text-analysis-lab" else GECO
    if release.version != version:
        raise ValueError(f"Unsupported scientific profile requirement: {package}")
    if release.wheel_url is None:
        # Temporary test-profile source: immutable Git commit, not a mutable
        # branch name. This is portable but requires online Git access for
        # a researcher's own uv sync; the native installer bundles its wheel.
        if not re.fullmatch(r"[0-9a-f]{40}", release.commit):
            raise ValueError("Development scientific source must name an immutable commit")
        return (
            f"{name}{extras or ''} @ git+https://github.com/"
            f"{release.repository}.git@{release.commit}"
        )
    if not release.asset_sha256:
        raise ValueError(f"Unverified published scientific source for {package}")
    return f"{name}{extras or ''} @ {release.wheel_url}#sha256={release.asset_sha256}"


def project_metadata(name: str, spec: RuntimeSpec) -> str:
    """A non-installed uv project with reusable identity across research folders.

    The human research name lives in TeAL/GeCo metadata and Desktop launcher.
    A constant non-packaged uv root name makes compatible projects eligible
    to reuse one immutable validated lock rather than pinning each project
    name in its dependency graph.
    """
    packages = spec.locked_packages or (
        f"text-analysis-lab=={spec.teal}",
        f"geometric-coder=={spec.geco}",
    )
    # UV's project mode is an application dependency graph, not a Python package.
    # Restrict only the Python minor version chosen by this scientific profile.
    version = spec.python.split(".")
    if len(version) != 2 or not all(part.isdigit() for part in version):
        raise ValueError("Select a Python major.minor version for the scientific project")
    upper = f"{version[0]}.{int(version[1]) + 1}"
    lines = [
        "[project]",
        'name = "geco-research-project"',
        'version = "0.0.0"',
        f"requires-python = {json.dumps('>=' + spec.python + ',<' + upper)}",
        "dependencies = [",
        *(f"    {json.dumps(_portable_requirement(package))}," for package in packages),
        "]",
        "",
        "[tool.uv]",
        "package = false",
        "",
    ]
    return "\n".join(lines)


def project_files_from_profile(
    manager: EnvironmentManager, manifest: object,
) -> LockedProjectFiles:
    """Export a verified immutable profile lock without resolving it again."""
    if not manager.uv:
        raise RuntimeError("uv is required to use a software profile")
    pyproject = manifest.pyproject
    lock = manifest.uv_lock
    with tempfile.TemporaryDirectory(prefix="gecod-profile-lock-") as directory:
        scratch = Path(directory)
        (scratch / PROJECT_FILE).write_bytes(pyproject.encode("utf-8"))
        (scratch / LOCK_FILE).write_bytes(lock.encode("utf-8"))
        exported = scratch / "requirements.txt"
        manager._uv(
            "export", "--project", str(scratch), "--frozen", "--no-dev",
            "--no-emit-project", "--format", "requirements.txt",
            "--output-file", str(exported),
        )
        requirements = exported.read_text(encoding="utf-8") if exported.is_file() else ""
        if not requirements.strip():
            raise RuntimeError("Validated profile did not export install requirements")
        return LockedProjectFiles(pyproject, lock, requirements)


def resolve_project_files(manager: EnvironmentManager, name: str, spec: RuntimeSpec) -> LockedProjectFiles:
    """Resolve exactly once; never write a temporary venv into the project.

    Python resolution runs in an ephemeral external directory, not the research
    folder. Published HTTPS wheels with digests keep the resulting lock
    independent of the local native installer wheelhouse. uv's immutable lock
    is the source for the exported install list.
    """
    if not manager.uv:
        raise RuntimeError("uv is required to resolve a portable project")
    pyproject = project_metadata(name, spec)
    with tempfile.TemporaryDirectory(prefix="gecod-project-lock-") as directory:
        scratch = Path(directory)
        (scratch / PROJECT_FILE).write_text(pyproject, encoding="utf-8")
        manager._uv(
            "lock", "--project", str(scratch), "--python", spec.python,
        )
        lock_path = scratch / LOCK_FILE
        if not lock_path.is_file():
            raise RuntimeError("uv did not produce a project lock")
        lock = lock_path.read_text(encoding="utf-8")
        if str(scratch) in lock or 'source = { registry = "../' in lock:
            raise RuntimeError("uv produced a lock with machine-local scientific sources")
        exported = scratch / "requirements.txt"
        manager._uv(
            "export", "--project", str(scratch), "--frozen", "--no-dev",
            "--no-emit-project", "--format", "requirements.txt",
            "--output-file", str(exported),
        )
        requirements = exported.read_text(encoding="utf-8") if exported.is_file() else ""
        if not lock.strip() or not requirements.strip():
            raise RuntimeError("uv returned an empty project lock or dependency export")
        return LockedProjectFiles(pyproject, lock, requirements)
