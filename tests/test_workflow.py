"""Contract tests for Desktop-to-TeAL orchestration and bounded previews."""
from __future__ import annotations

import csv
import sys
import types

import pytest

from geco_desktop.backend import runner, workflow
from geco_desktop.protocol import request


def test_csv_schema_uses_only_selected_header_and_bounded_rows(tmp_path):
    path = tmp_path / "records.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["text", "speaker", "extra"])
        for i in range(100):
            writer.writerow([f"message {i}", f"s{i}", i])
    response = runner.dispatch(request("csv_schema", path=str(path)))
    assert response["columns"] == ["text", "speaker", "extra"]
    assert len(response["sample"]) == 5
    assert response["sample"][0]["text"] == "message 0"


def test_csv_schema_rejects_missing_and_duplicate_headers(tmp_path):
    with pytest.raises(FileNotFoundError):
        workflow.csv_schema(str(tmp_path / "missing.csv"))
    duplicate = tmp_path / "dupe.csv"
    duplicate.write_text("a,a\none,two\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        workflow.csv_schema(str(duplicate))


def test_preview_limit_is_bounded():
    assert workflow._positive_limit("12") == 12
    for value in [0, 101, -1]:
        with pytest.raises(ValueError):
            workflow._positive_limit(value)


def test_finalize_reuses_persisted_link_without_creating_another(monkeypatch):
    created = []
    closed = []

    class Linked:
        def list(self):
            return [{"name": "desktop"}]

        def create(self, *args, **kwargs):
            created.append((args, kwargs))
            raise AssertionError("Duplicate linked GeCo workspace")

    class FakeProject:
        geco = Linked()

        @classmethod
        def open(cls, path):
            return cls()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            closed.append(True)

    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FakeProject))
    result = workflow.finalize("anywhere", "docs", "docs", "text", "geom", None, [])
    assert result["already_exists"] is True
    assert created == []
    assert closed


def test_pattern_preview_is_not_committed(monkeypatch):
    calls = []

    class FakeArtifact:
        artifact_type = types.SimpleNamespace(value="table")
        n_rows = 1

        def sample(self, **kwargs):
            calls.append(("sample", kwargs))
            class Frame:
                def __getitem__(self, field):
                    assert field == "text"
                    return ["Speaker 1: Hello"]

                def to_json(self, *, orient):
                    assert orient == "records"
                    return '[{"text":"Speaker 1: Hello"}]'

            return Frame()

    class FakeProject:
        @classmethod
        def open(cls, path):
            return cls()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return None

        def get_artifact(self, artifact_id):
            return FakeArtifact()

        def translate(self, *args, **kwargs):
            raise AssertionError("Preview must never commit a durable artifact")

    class FakeExtractor:
        def __init__(self, pattern, **kwargs):
            calls.append(("constructor", pattern, kwargs))

        def translate(self, values):
            class Frame:
                def __init__(self, field, value):
                    self.field, self.value = field, value

                def to_json(self, *, orient):
                    import json
                    assert orient == "records"
                    return json.dumps([{self.field: self.value}])

            return {
                "data": Frame("utterance", "Hello"),
                "metadata": Frame("speaker", "Speaker 1"),
            }

    translators = types.SimpleNamespace(PatternExtractor=FakeExtractor)
    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FakeProject, translators=translators))
    result = workflow.preview_step(
        "workspace", "source", "pattern", "text",
        {"pattern": r"(?P<metadata_speaker>[^:]+): (?P<data_utterance>.*)"},
    )
    assert result["after"]["data"] == [{"utterance": "Hello"}]
    assert result["after"]["metadata"] == [{"speaker": "Speaker 1"}]
    assert calls[0][0] == "sample"
    assert calls[1][2]["metadata_mode"] == "full"


def test_package_contains_current_workflow_resource():
    from pathlib import Path
    assert Path(runner.__file__).with_name("workflow.py").is_file()


def test_preview_tables_preserve_source_alignment_and_split_lineage():
    original = [{"text": "A: hello"}, {"text": "B: hi"}]
    capture = workflow._preview_tables(
        "pattern", original,
        {"data": [{"utterance": "hello"}, {"utterance": "hi"}],
         "metadata": [{"speaker": "A"}, {"speaker": "B"}]},
        field="text", options={},
    )
    assert capture["after_columns"] == ["utterance", "metadata.speaker"]
    assert capture["after_rows"][1]["metadata.speaker"] == "B"
    assert capture["sample_only"] is True
    split = workflow._preview_tables(
        "split", original,
        {"source_positions": [0, 0, 1], "segment_ids": [0, 1, 0],
         "texts": ["A", "hello", "B: hi"]},
        field="text", options={"new_key": "segment"},
    )
    assert split["candidate_rows"] == 3
    assert split["after_rows"][1] == {
        "source_row": 1, "segment": 1, "text": "hello"
    }
    with pytest.raises(ValueError, match="aligned"):
        workflow._preview_tables(
            "split", original,
            {"source_positions": [0, 1], "segment_ids": [0], "texts": ["a"]},
            field="text", options={},
        )


def test_preview_tables_allow_empty_pattern_component():
    result = workflow._preview_tables(
        "pattern", [{"text": "nomatch"}], {"data": [], "metadata": []},
        field="text", options={},
    )
    assert result["source_rows"] == 1
    assert result["candidate_rows"] == 1

def test_catalog_preserves_true_matrix_dimensions_without_listing_all_features(monkeypatch):
    import sys
    import types
    from geco_desktop.backend import workflow

    class Matrix:
        artifact_id = "geom-id"
        artifact_type = types.SimpleNamespace(value="dense_matrix")
        n_rows = 5
        primary_key = ("row",)

        def get_data_columns(self):
            return [f"dim_{i}" for i in range(312)]

    class FakeProject:
        @classmethod
        def open(cls, path):
            return cls()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def list_artifacts(self):
            return [{
                "artifact_id": "geom-id", "aliases": ["projected"],
                "status": "complete", "lineage_mode": "preserved_key",
                "source_artifact_id": "source-id",
            }]

        def get_artifact(self, identifier):
            assert identifier == "geom-id"
            return Matrix()

        def list_operations(self):
            return []

        geco = types.SimpleNamespace(list=lambda: [])

    monkeypatch.setitem(
        sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FakeProject)
    )
    result = workflow.catalog("some-project")
    artifact = result["artifacts"][0]
    assert artifact["dimensions"] == 312
    assert len(artifact["data_fields"]) == 250
    assert artifact["source_artifact_id"] == "source-id"
    assert artifact["aliases"] == ["projected"]

def test_umap_for_geco_requests_teal_reusable_fitted_state(monkeypatch):
    import sys
    import types
    from geco_desktop.backend import workflow

    class FakeUMAP:
        def __init__(self, **params):
            self.params = params

    monkeypatch.setitem(
        sys.modules, "text_analysis_lab",
        types.SimpleNamespace(translators=types.SimpleNamespace(UMAP=FakeUMAP)),
    )
    result = workflow._translator(
        "umap", "not-used", {"n_components": "5", "n_neighbors": "12"}
    )
    assert result.params["n_components"] == 5
    assert result.params["reuse"] == "stored"
    assert result.params["storage"] == "compact"
    assert result.params["random_state"] == 42
