"""Portable GeCo Desktop project descriptor; TeAL remains the data authority."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DESCRIPTOR_NAME = "project.gecod"
SCHEMA_VERSION = 1
WORKSPACE_NAME = "desktop"


@dataclass(frozen=True)
class RuntimeSpec:
    python: str
    teal: str
    geco: str
    locked_packages: tuple[str, ...] = ()
    resolved_requirements: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("python", "teal", "geco"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Runtime {field_name} must be provided")
        if not isinstance(self.locked_packages, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.locked_packages
        ):
            raise ValueError("locked_packages must contain requirement strings")
        if self.resolved_requirements is not None and (
            not isinstance(self.resolved_requirements, str)
            or not self.resolved_requirements.strip()
        ):
            raise ValueError("resolved_requirements must be nonempty lock text")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RuntimeSpec:
        if not isinstance(data, dict):
            raise ValueError("Invalid runtime specification")
        return cls(
            python=data["python"],
            teal=data["teal"],
            geco=data["geco"],
            locked_packages=tuple(data.get("locked_packages", [])),
            resolved_requirements=data.get("resolved_requirements"),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "python": self.python,
            "teal": self.teal,
            "geco": self.geco,
            "locked_packages": list(self.locked_packages),
        }
        if self.resolved_requirements is not None:
            result["resolved_requirements"] = self.resolved_requirements
        return result


@dataclass(frozen=True)
class ProjectDescriptor:
    project_id: str
    name: str
    runtime: RuntimeSpec
    state: str = "preparing"
    workspace_name: str = WORKSPACE_NAME
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    created_with: str = "0.1.0.dev0"
    last_artifact_id: str | None = None
    project_lock_sha256: str | None = None
    profile_id: str | None = None

    def __post_init__(self) -> None:
        uuid.UUID(self.project_id)
        if not self.name.strip():
            raise ValueError("Project name cannot be blank")
        if self.state not in {"preparing", "finalized"}:
            raise ValueError("Invalid project state")
        if self.workspace_name != WORKSPACE_NAME:
            raise ValueError("Unrecognized Desktop-managed workspace name")
        if self.project_lock_sha256 is not None and (
            len(self.project_lock_sha256) != 64
            or any(char not in "0123456789abcdef" for char in self.project_lock_sha256)
        ):
            raise ValueError("Invalid project uv.lock SHA256")
        if self.profile_id is not None and (
            not self.profile_id.startswith("sha256:")
            or len(self.profile_id) != 71
            or any(char not in "0123456789abcdef" for char in self.profile_id[7:])
        ):
            raise ValueError("Invalid software profile identity")

    @classmethod
    def new(
        cls, name: str, runtime: RuntimeSpec, *,
        project_lock_sha256: str | None = None,
        profile_id: str | None = None,
    ) -> ProjectDescriptor:
        return cls(
            project_id=str(uuid.uuid4()), name=name, runtime=runtime,
            project_lock_sha256=project_lock_sha256,
            profile_id=profile_id,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectDescriptor:
        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("Unsupported GeCo Desktop project schema")
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            runtime=RuntimeSpec.from_dict(data["runtime"]),
            state=data.get("state", "preparing"),
            workspace_name=data.get("workspace_name", WORKSPACE_NAME),
            created_at=data["created_at"],
            created_with=data.get("created_with", "unknown"),
            last_artifact_id=data.get("last_artifact_id"),
            project_lock_sha256=data.get("project_lock_sha256"),
            profile_id=data.get("profile_id"),
        )

    def to_dict(self) -> dict[str, Any]:
        record = {
            "schema_version": SCHEMA_VERSION,
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
            "created_with": self.created_with,
            "state": self.state,
            "workspace_name": self.workspace_name,
            "runtime": self.runtime.to_dict(),
            "last_artifact_id": self.last_artifact_id,
        }
        if self.project_lock_sha256 is not None:
            record["project_lock_sha256"] = self.project_lock_sha256
        if self.profile_id is not None:
            record["profile_id"] = self.profile_id
        return record


def project_directory(path: str | Path) -> Path:
    """Resolve a project root from its folder or inner .gecod document."""
    selected = Path(path).expanduser().resolve()
    if selected.is_dir():
        return selected
    if selected.name == DESCRIPTOR_NAME:
        return selected.parent
    raise ValueError("Choose a GeCo project folder or project.gecod")


def read_descriptor(path: str | Path) -> tuple[Path, ProjectDescriptor]:
    root = project_directory(path)
    with (root / DESCRIPTOR_NAME).open("r", encoding="utf-8") as stream:
        descriptor = ProjectDescriptor.from_dict(json.load(stream))
    # Legacy descriptors have no project lock and retain their old opening path.
    # New descriptors must not silently reuse a profile after the portable lock
    # was edited, removed or replaced outside Desktop.
    if descriptor.project_lock_sha256 is not None:
        lock_file = root / "uv.lock"
        if not lock_file.is_file():
            raise FileNotFoundError(
                "The project's uv.lock is missing; restore it before opening in Desktop."
            )
        observed = hashlib.sha256(lock_file.read_bytes()).hexdigest()
        if observed != descriptor.project_lock_sha256:
            raise ValueError(
                "The project's uv.lock has changed. Desktop cannot safely reuse its "
                "original scientific environment; restore the original lock or use "
                "uv with this project until custom environment selection is available."
            )
    return root, descriptor


def write_descriptor(root: str | Path, descriptor: ProjectDescriptor, *, replace: bool = False) -> Path:
    """Atomically write only Desktop-owned metadata; never touch .teal state."""
    directory = Path(root).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("Project directory must already exist")
    target = directory / DESCRIPTOR_NAME
    if target.exists() and not replace:
        raise FileExistsError(f"Project descriptor already exists: {target}")
    fd, staged = tempfile.mkstemp(prefix=".gecod-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(descriptor.to_dict(), handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Never overwrite an existing descriptor on initial creation.
        if not replace and target.exists():
            raise FileExistsError(f"Project descriptor already exists: {target}")
        os.replace(staged, target)
    finally:
        if os.path.exists(staged):
            os.unlink(staged)
    return target


def reconcile_finalization(
    root: str | Path,
    descriptor: ProjectDescriptor,
    workspaces: list[dict[str, Any]],
) -> ProjectDescriptor:
    """Repair a stale descriptor only when TeAL already owns the linked workspace.

    TeAL's GeCo manifest is authoritative. This only repairs Desktop's small
    portable state marker after a crash between linking and the descriptor write.
    It never creates/replaces a GeCo workspace or mutates scientific artifacts.
    """
    if descriptor.state != "preparing":
        return descriptor
    if not any(
        isinstance(workspace, dict)
        and workspace.get("name") == descriptor.workspace_name
        for workspace in workspaces
    ):
        return descriptor
    recovered = ProjectDescriptor.from_dict({
        **descriptor.to_dict(),
        "state": "finalized",
    })
    write_descriptor(root, recovered, replace=True)
    return recovered
