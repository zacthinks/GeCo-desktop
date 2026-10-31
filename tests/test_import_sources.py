"""Multi-format inspection and TeAL-owned file extraction contracts."""
from __future__ import annotations

import sys
import types

import pytest

from geco_desktop.backend import workflow


def test_source_schema_csv_folder_is_bounded(tmp_path):
    folder = tmp_path / "corpus"
    folder.mkdir()
    for index in range(2):
        (folder / f"{index}.csv").write_text(
            "text,group\n" + "".join(f"example {i},g\n" for i in range(11)),
            encoding="utf-8",
        )
    result = workflow.source_schema(str(folder), "csv_folder")
    assert result["columns"] == ["text", "group"]
    assert result["file_count"] == 2
    assert len(result["sample"]) == 5


def test_source_schema_txt_pdf_only_inspects_files(tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.txt").write_text("more", encoding="utf-8")
    assert workflow.source_schema(str(tmp_path), "txt_folder", recursive=False)["file_count"] == 1
    result = workflow.source_schema(str(tmp_path), "txt_folder", recursive=True)
    assert result["columns"] == ["text"]
    assert result["file_count"] == 2
    with pytest.raises(ValueError, match="No .pdf"):
        workflow.source_schema(str(tmp_path), "pdf_folder")


def test_text_folder_import_delegates_inventory_and_translator(monkeypatch, tmp_path):
    (tmp_path / "a.txt").write_text("hello", encoding="utf-8")
    calls = []

    class Artifact:
        artifact_id = "result"
        artifact_type = types.SimpleNamespace(value="table")
        n_rows = 1
        primary_key = ("file_id",)

        def get_data_columns(self):
            return ["text"]

    class Project:
        @classmethod
        def open(cls, path):
            return cls()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def list_artifacts(self):
            return []

        def folder_inventory(self, root, *, patterns, recursive, alias):
            calls.append(("inventory", patterns, recursive, alias))
            return Artifact()

        def translate(self, translator, source, *, alias):
            calls.append(("translate", type(translator).__name__, alias))
            return {"output": Artifact()}

    class TextFileExtractor:
        pass

    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(
        Project=Project, translators=types.SimpleNamespace(TextFileExtractor=TextFileExtractor),
    ))
    result = workflow.import_source(
        "project", str(tmp_path), "txt_folder", [], [], recursive=False
    )
    assert result["id"] == "result"
    assert calls == [
        ("inventory", "*.txt", False, "file_inventory"),
        ("translate", "TextFileExtractor", "documents"),
    ]


def test_import_refuses_missing_text_selection_or_overlap():
    with pytest.raises(ValueError, match="text field"):
        workflow.import_source("x", "foo.csv", "csv", [], [])
    with pytest.raises(ValueError, match="both text and metadata"):
        workflow.import_source("x", "foo.csv", "csv", ["text"], ["text"])
