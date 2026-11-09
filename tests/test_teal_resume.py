"""Desktop delegates interrupted translation recovery to TeAL directly."""
from __future__ import annotations

import sys
import types

import pytest

from geco_desktop.backend import runner, workflow
from geco_desktop.protocol import request


class FakeArtifact:
    artifact_id = "recovered"
    artifact_type = types.SimpleNamespace(value="table")
    n_rows = 3
    primary_key = ("row_id",)

    def get_data_columns(self):
        return ["text"]


class FakeProject:
    seen = []

    @classmethod
    def open(cls, path):
        cls.seen.append(("open", path))
        return cls()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.seen.append(("closed",))

    def resume_operation(self, operation_id):
        self.seen.append(("resume", operation_id))
        return {"output": FakeArtifact()}

    def list_artifacts(self):
        return []

    def list_operations(self):
        return [
            {"operation_id": "op-1", "operation_type": "translate", "status": "failed"},
            {"operation_id": "op-2", "operation_type": "subset", "status": "incomplete"},
            {"operation_id": "op-3", "operation_type": "translate", "status": "complete"},
            {"operation_id": "op-4", "operation_type": "import", "status": "failed"},
        ]

    class geco:
        @staticmethod
        def list():
            return []


def test_resume_routes_exact_original_operation_id_to_teal(monkeypatch):
    FakeProject.seen = []
    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FakeProject))
    response = runner.dispatch(request("resume_operation", path="project", operation_id="op-1"))
    assert response["operation_id"] == "op-1"
    assert response["outputs"]["output"]["id"] == "recovered"
    assert FakeProject.seen == [("open", "project"), ("resume", "op-1"), ("closed",)]


def test_catalog_lists_only_teal_supported_incomplete_operations(monkeypatch):
    FakeProject.seen = []
    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FakeProject))
    result = workflow.catalog("project")
    assert [item["operation_id"] for item in result["interrupted_operations"]] == ["op-1", "op-2"]
    assert FakeProject.seen[-1] == ("closed",)


def test_empty_resume_identity_is_rejected_before_opening_science(monkeypatch):
    class FailOpen(FakeProject):
        @classmethod
        def open(cls, path):
            raise AssertionError("must not access TeAL for blank operation id")

    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FailOpen))
    with pytest.raises(ValueError, match="Select a recorded"):
        workflow.resume_operation("project", " ")
