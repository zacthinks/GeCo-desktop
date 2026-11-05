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
        (root / PROJECT_FILE).write_text(self.pyproject, encoding="utf-8")
        (root / LOCK_FILE).write_text(self.lock, encoding="utf-8")


def project_metadata(name: str, spec: RuntimeSpec) -> str:
    """A standards-compliant uv project with no package to install locally."""
    normalized = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "research"
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
        f"name = {json.dumps('geco-' + normalized)}",
        'version = "0.0.0"',
        f"requires-python = {json.dumps('>=' + spec.python + ',<' + upper)}",
        "dependencies = [",
        *(f"    {json.dumps(package)}," for package in packages),
        "]",
        "",
        "[tool.uv]",
        "package = false",
        "",
    ]
    return "\n".join(lines)


def resolve_project_files(manager: EnvironmentManager, name: str, spec: RuntimeSpec) -> LockedProjectFiles:
    """Resolve exactly once; never write a temporary venv into the project.

    Python resolution runs in an ephemeral external directory, not the research
    folder. Official wheelhouse entries can be used when packages are absent
    from PyPI. uv's immutable lock is the source for the exported install list.
    """
    if not manager.uv:
        raise RuntimeError("uv is required to resolve a portable project")
    pyproject = project_metadata(name, spec)
    with tempfile.TemporaryDirectory(prefix="gecod-project-lock-") as directory:
        scratch = Path(directory)
        (scratch / PROJECT_FILE).write_text(pyproject, encoding="utf-8")
        manager._uv(
            "lock", "--project", str(scratch), "--python", spec.python,
            *manager._wheel_links(),
        )
        lock_path = scratch / LOCK_FILE
        if not lock_path.is_file():
            raise RuntimeError("uv did not produce a project lock")
        lock = lock_path.read_text(encoding="utf-8")
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
