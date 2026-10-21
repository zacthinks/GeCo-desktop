import json
import uuid
from dataclasses import replace

import pytest

from geco_desktop.project import (
    ProjectDescriptor,
    RuntimeSpec,
    read_descriptor,
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
