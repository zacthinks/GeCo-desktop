"""Optional real TeAL -> GeCo Desktop backend smoke, not a mocked unit test.

Use only public TeAL/GeCo operations through Desktop's app-owned runner.
Synthetic data is generated in a temporary location and is not product data.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from dataclasses import replace
from pathlib import Path

from geco_desktop.environments import installed_runner_path, run_command
from geco_desktop.project import (
    ProjectDescriptor,
    RuntimeSpec,
    read_descriptor,
    reconcile_finalization,
    write_descriptor,
)
from geco_desktop.science_releases import DEFAULT_PYTHON, GECO, TEAL
from geco_desktop.sessions import SessionManager


def smoke(science_python: Path, output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    root = output_root / "Scientific backend.gecod"
    moved = output_root / "Moved scientific backend.gecod"
    if root.exists() or moved.exists():
        raise FileExistsError("Choose a fresh output directory for the integration smoke.")

    source = output_root / "temporary-input.csv"
    with source.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["text", "category"])
        for i in range(36):
            animal, tail = (
                ("cat", "feline whiskers purring kittens")
                if i % 2 == 0 else ("dog", "canine barking puppies walking")
            )
            writer.writerow([f"Document {i}  describes  a {animal}. {tail}.", animal])

    runner = installed_runner_path()

    def command(action: str, **kwargs):
        print(f"Desktop runner: {action}", flush=True)
        if action not in {"source_schema", "csv_schema"}:
            kwargs.setdefault("path", str(root))
        return run_command(science_python, runner, action, timeout=480, **kwargs)

    root.mkdir()
    command("create_teal", name="Scientific backend")
    schema = command("source_schema", source=str(source), kind="csv")
    assert "text" in schema["columns"], schema
    documents = command(
        "import_source", source_path=str(source), kind="csv",
        text_fields=["text"], metadata_fields=["category"],
    )
    assert documents["rows"] == 36, documents
    documents_id = documents["id"]

    baseline = command("catalog")
    assert len(baseline["artifacts"]) == 1, baseline
    preview = command("preview", artifact_id=documents_id, n=6, random=True)
    assert len(preview["rows"]) == 6, preview
    candidate = command(
        "preview_step", artifact_id=documents_id, kind="clean", field="text",
        options={"pattern": r"\s+", "replacement": " ", "output_field": "text"},
    )
    assert candidate["sample_only"] is True
    assert candidate["source_rows"] == 12
    assert len(command("catalog")["artifacts"]) == 1, "Preview persisted an artifact"

    def apply(kind: str, artifact_id: str, alias: str, *, field: str = "", **options):
        outputs = command(
            "apply_step", artifact_id=artifact_id, kind=kind, field=field,
            options=options, alias=alias,
        )
        assert "output" in outputs, (kind, outputs)
        return outputs["output"]

    cleaned = apply(
        "clean", documents_id, "cleaned", field="text",
        pattern=r"\s+", replacement=" ", output_field="text",
    )
    assert cleaned["rows"] == 36, cleaned
    # Exercise TeAL's released PatternExtractor through the real Desktop
    # runner. Capture data and metadata, with no preview persistence.
    pattern = r"Document (?P<metadata_document_number>\\d+)\\s+describes\\s+a (?P<data_animal>\\w+)\\. (?P<data_details>.*)"
    pattern_options = {"pattern": pattern, "on_unmatched": "fail"}
    pattern_preview = command(
        "preview_step", artifact_id=cleaned["id"], kind="pattern",
        field="text", options=pattern_options,
    )
    assert pattern_preview["sample_only"] is True
    assert pattern_preview["candidate_rows"] == 12
    assert "animal" in pattern_preview["after_columns"]
    assert "metadata.document_number" in pattern_preview["after_columns"]
    assert len(command("catalog")["artifacts"]) == 2, "Pattern preview wrote artifacts"
    extracted = apply(
        "pattern", cleaned["id"], "extracted", field="text", **pattern_options
    )
    assert extracted["rows"] == 36, extracted
    extracted_preview = command("preview", artifact_id=extracted["id"], n=4)
    assert "animal" in extracted_preview["columns"]
    assert any("document_number" in name for name in extracted_preview["columns"])
    counts = apply("count", cleaned["id"], "counts", field="text", max_features=100)
    tfidf = apply("tfidf", counts["id"], "tfidf", norm="l2")
    svd = apply("svd", tfidf["id"], "svd", n_components=2)
    assert svd["dimensions"] == 2, svd
    umap = apply(
        "umap", tfidf["id"], "umap", n_components=2, n_neighbors=8,
        min_dist=0.1,
    )
    assert umap["dimensions"] == 2, umap

    linked_args = {
        "documents_id": documents_id, "text_id": cleaned["id"],
        "text_field": "text", "geometry_id": umap["id"], "view_id": svd["id"],
        "metadata_fields": ["category"],
    }
    first = command("finalize", **linked_args)
    assert first == {"workspace": "desktop", "already_exists": False}, first
    second = command("finalize", **linked_args)
    assert second == {"workspace": "desktop", "already_exists": True}, second

    descriptor = replace(
        ProjectDescriptor.new(
            "Scientific backend",
            RuntimeSpec(python=DEFAULT_PYTHON, teal=TEAL.version, geco=GECO.version),
        ),
        state="finalized", last_artifact_id=cleaned["id"],
    )
    # Simulate a crash after TeAL created the linked workspace but before
    # Desktop recorded finalized state in its portable descriptor.
    write_descriptor(root, replace(descriptor, state="preparing"))
    saved = read_descriptor(root)[1]
    recovered = reconcile_finalization(root, saved, command("project_info")["workspaces"])
    assert recovered == descriptor
    assert read_descriptor(root)[1].state == "finalized"
    sessions = SessionManager(base=output_root / "desktop-session-registry")
    print("Desktop runner: start browser session", flush=True)
    active = sessions.start(root, descriptor, science_python, wait_seconds=120)
    try:
        assert active.url.startswith("http://127.0.0.1:")
        recovered = SessionManager(base=output_root / "desktop-session-registry")
        current = recovered.start(root, descriptor, science_python, wait_seconds=15)
        assert current.pid == active.pid, (current.pid, active.pid)
    finally:
        sessions.stop(active.key)

    source.unlink()  # Reopening computed artifacts must not need original source files.
    shutil.move(str(root), str(moved))
    resolved, saved = read_descriptor(moved / "project.gecod")
    assert resolved == moved.resolve() and saved == descriptor
    reopened = run_command(science_python, runner, "project_info", path=str(moved))
    assert [item["name"] for item in reopened["workspaces"]] == ["desktop"], reopened
    after_move = run_command(science_python, runner, "catalog", path=str(moved))
    assert len(after_move["artifacts"]) >= 7, after_move
    print("PASS: real runner, TeAL artifacts, GeCo, session and moved project", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--science-python", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    smoke(arguments.science_python.absolute(), arguments.output_root.resolve())
