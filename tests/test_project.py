import hashlib
import json
import uuid
from dataclasses import replace

import pytest

from geco_desktop.project import (
    ProjectDescriptor,
    RuntimeSpec,
    read_descriptor,
    reconcile_finalization,
    write_descriptor,
)


def test_descriptor_round_trip_and_relative_root(tmp_path):
    original = ProjectDescriptor.new("Interview study", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    target = tmp_path / "Study.gecod"
    target.mkdir()
    (target / ".teal").mkdir()
    saved = write_descriptor(target, original)
    assert saved.name == "project.gecod"
    assert read_descriptor(target)[1] == original
    assert read_descriptor(saved)[1] == original
    assert ".venv" not in [p.name for p in target.iterdir()]
    assert set(x.name for x in target.iterdir()) == {"project.gecod", ".teal"}


def test_descriptor_can_move_without_absolute_paths(tmp_path):
    source = tmp_path / "old.gecod"
    source.mkdir()
    initial = ProjectDescriptor.new("Move me", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    write_descriptor(source, initial)
    destination = tmp_path / "new.gecod"
    source.rename(destination)
    root, restored = read_descriptor(destination / "project.gecod")
    assert root == destination.resolve()
    assert restored == initial
    assert str(source) not in json.dumps(restored.to_dict())


def test_never_overwrite_on_initial_creation(tmp_path):
    descriptor = ProjectDescriptor.new("A", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    write_descriptor(tmp_path, descriptor)
    with pytest.raises(FileExistsError):
        write_descriptor(tmp_path, replace(descriptor, name="B"))
    assert read_descriptor(tmp_path)[1].name == "A"
    write_descriptor(tmp_path, replace(descriptor, state="finalized"), replace=True)
    assert read_descriptor(tmp_path)[1].state == "finalized"


def test_reject_unknown_schema_or_workspace(tmp_path):
    descriptor = ProjectDescriptor.new("A", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    payload = descriptor.to_dict()
    payload["schema_version"] = 99
    (tmp_path / "project.gecod").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="schema"):
        read_descriptor(tmp_path)
    payload["schema_version"] = 1
    payload["workspace_name"] = "other"
    (tmp_path / "project.gecod").write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="workspace"):
        read_descriptor(tmp_path)
    assert uuid.UUID(descriptor.project_id)


def test_reconcile_interrupted_finalization_from_teal_workspace(tmp_path):
    root = tmp_path / "recovery.gecod"
    root.mkdir()
    original = ProjectDescriptor.new("Recover me", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    write_descriptor(root, original)
    assert reconcile_finalization(root, original, []) == original
    assert read_descriptor(root)[1].state == "preparing"
    assert reconcile_finalization(root, original, [{"name": "other"}]) == original
    recovered = reconcile_finalization(root, original, [{"name": "desktop"}])
    assert recovered.state == "finalized"
    assert recovered.project_id == original.project_id
    assert recovered.runtime == original.runtime
    assert read_descriptor(root)[1] == recovered
    assert reconcile_finalization(root, recovered, [{"name": "desktop"}]) == recovered


def test_portable_lock_identity_is_preserved_and_checked_on_open(tmp_path):
    root = tmp_path / "Research.gecod"
    root.mkdir()
    lock = 'version = 1\n'
    (root / "uv.lock").write_text(lock, encoding="utf-8")
    digest = hashlib.sha256(lock.encode("utf-8")).hexdigest()
    descriptor = ProjectDescriptor.new(
        "Research", RuntimeSpec("3.11", "0.10.0", "0.9.0"),
        project_lock_sha256=digest,
    )
    write_descriptor(root, descriptor)
    assert read_descriptor(root)[1] == descriptor

    (root / "uv.lock").write_text("version = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="uv.lock has changed"):
        read_descriptor(root)

    (root / "uv.lock").unlink()
    with pytest.raises(FileNotFoundError, match="uv.lock is missing"):
        read_descriptor(root)


def test_invalid_portable_lock_digest_is_rejected():
    with pytest.raises(ValueError, match="uv.lock SHA256"):
        ProjectDescriptor.new(
            "Research", RuntimeSpec("3.11", "0.10.0", "0.9.0"),
            project_lock_sha256="not-a-sha256",
        )
