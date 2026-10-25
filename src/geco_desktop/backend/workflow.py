"""User-selected TeAL operations for the Desktop preparation workbench.

This is an app-owned adapter, not an alternative science or artifact engine.
Every durable operation calls TeAL's public API within the pinned child Python.
"""
from __future__ import annotations

import csv
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _positive_limit(value: Any, *, maximum: int = 100) -> int:
    number = int(value)
    if number < 1 or number > maximum:
        raise ValueError(f"Preview size must be between 1 and {maximum}.")
    return number


def csv_schema(path: str) -> dict[str, Any]:
    """Read a bounded CSV header/sample to help a human select import fields."""
    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Choose an existing CSV file: {source}")
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream)
        columns = next(reader, [])
        if not columns or any(not name.strip() for name in columns):
            raise ValueError("The CSV must have a nonempty header row.")
        if len(set(columns)) != len(columns):
            raise ValueError("The CSV contains duplicate column names.")
        rows = []
        for _ in range(5):
            row = next(reader, None)
            if row is None:
                break
            rows.append({col: val for col, val in zip(columns, row, strict=False)})
    return {"columns": columns, "sample": rows}


def _artifact_details(artifact: Any) -> dict[str, Any]:
    return {
        "id": str(artifact.artifact_id),
        "type": str(getattr(artifact.artifact_type, "value", artifact.artifact_type)),
        "rows": int(artifact.n_rows or 0),
        "keys": list(artifact.primary_key),
        "data_fields": list(artifact.get_data_columns()),
    }


def catalog(path: str) -> dict[str, Any]:
    from text_analysis_lab import Project

    with Project.open(path) as project:
        rows = []
        for item in project.list_artifacts():
            if item.get("status") == "deleted":
                continue
            artifact = project.get_artifact(str(item["artifact_id"]))
            row = _artifact_details(artifact)
            row["aliases"] = list(item.get("aliases") or [])
            rows.append(row)
        return {
            "artifacts": rows,
            "workspaces": project.geco.list(),
        }


def import_csv(
    path: str,
    csv_path: str,
    text_fields: list[str],
    metadata_fields: list[str],
) -> dict[str, Any]:
    from text_analysis_lab import Project

    if not text_fields:
        raise ValueError("Select at least one text column.")
    if set(text_fields) & set(metadata_fields):
        raise ValueError("A CSV column cannot be both text and metadata.")
    with Project.open(path) as project:
        existing = project.list_artifacts()
        # A repeated click should not silently create an unrelated second import.
        if any("documents" in row.get("aliases", []) for row in existing):
            raise FileExistsError("Documents were already imported; select that artifact to continue.")
        result = project.read_csv(
            csv_path,
            text_fields=text_fields,
            metadata_fields=metadata_fields,
            alias="documents",
        )
        return _artifact_details(result)


def preview(path: str, artifact_id: str, *, n: int = 12, random: bool = False) -> dict:
    """Bounded, non-persistent source inspection; never use Project.sample()."""
    from text_analysis_lab import Project

    n = _positive_limit(n)
    with Project.open(path) as project:
        artifact = project.get_artifact(artifact_id)
        if artifact.artifact_type.value not in {"table", "jsonl"}:
            return {"artifact": _artifact_details(artifact), "rows": [], "columns": []}
        options: dict[str, Any] = {
            "key_columns": True,
            "data_columns": True,
            "metadata_columns": True,
            "metadata_mode": "full",
        }
        if random:
            frame = artifact.sample(n=min(n, int(artifact.n_rows or 0)), random_state=42, form="table", **options)
        else:
            frame = artifact.preview(n=n, **options)
        # Pandas JSON serialization handles NA, timestamps and numpy scalars.
        import json

        return {
            "artifact": _artifact_details(artifact),
            "columns": [str(col) for col in frame.columns],
            "rows": json.loads(frame.to_json(orient="records")),
            "sampling": "seeded random sample" if random else "first rows",
        }


def _translator(kind: str, field: str, options: Mapping[str, Any]) -> Any:
    """A curated adapter to *public* translators, not arbitrary Python execution."""
    from text_analysis_lab import translators as tr

    if kind == "pattern":
        return tr.PatternExtractor(
            str(options["pattern"]),
            field=field,
            metadata_mode="full",
            on_unmatched=str(options.get("on_unmatched", "fill")),
            fill_value=options.get("fill_value", ""),
        )
    if kind == "clean":
        return tr.RegexCleaner(
            text_field=field,
            output_field=str(options.get("output_field") or field),
            rules=[{"pattern": str(options["pattern"]), "replacement": str(options.get("replacement", ""))}],
            strip=bool(options.get("strip", True)),
        )
    if kind == "split":
        return tr.DelimiterDecomposer(
            text_field=field,
            output_text_field=str(options.get("output_field") or field),
            delimiter=str(options.get("delimiter", "\n")),
            new_key=str(options.get("new_key", "segment_id")),
            strip=bool(options.get("strip", True)),
            drop_empty=bool(options.get("drop_empty", True)),
        )
    if kind == "count":
        return tr.CountVectorizer(
            text_field=field,
            max_features=int(options.get("max_features", 5000)),
            stop_words=options.get("stop_words") or None,
        )
    if kind == "tfidf":
        return tr.TfidfTransformer(norm=options.get("norm") or None)
    if kind == "svd":
        return tr.SVD(
            n_components=int(options.get("n_components", 2)),
            random_state=int(options.get("random_state", 42)),
        )
    if kind == "umap":
        return tr.UMAP(
            n_components=int(options.get("n_components", 2)),
            n_neighbors=int(options.get("n_neighbors", 15)),
            min_dist=float(options.get("min_dist", 0.1)),
            random_state=int(options.get("random_state", 42)),
        )
    raise ValueError(f"Unsupported preparation operation {kind!r}")


def preview_step(
    path: str,
    artifact_id: str,
    kind: str,
    field: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    """Show a small *standalone* operation; do not write a scientific artifact."""
    from text_analysis_lab import Project

    if kind not in {"clean", "pattern", "split"}:
        raise ValueError("Preview is only available for cleaning, extraction and splitting.")
    with Project.open(path) as project:
        artifact = project.get_artifact(artifact_id)
        if artifact.artifact_type.value not in {"table", "jsonl"}:
            raise ValueError("Text-operation previews require a table artifact.")
        frame = artifact.sample(
            n=min(12, int(artifact.n_rows or 0)), random_state=42,
            key_columns=False, data_columns=[field], metadata_columns=False,
            form="table",
        )
        source = frame[field]
        translator = _translator(kind, field, options)
        result = translator.translate(source)
        # Each standalone translator has a public but distinct output shape.
        import json

        if kind == "pattern":
            after = {
                key: json.loads(values.to_json(orient="records"))
                for key, values in result.items()
            }
        elif kind == "clean":
            after = {"texts": [None if x is None else str(x) for x in result.tolist()]}
        else:
            after = {
                "source_positions": result["source_positions"].tolist(),
                "segment_ids": result["segment_ids"].tolist(),
                "texts": result["texts"].fillna("").tolist(),
            }
        return {
            "sampling": "12 seeded sample rows (not exhaustive)",
            "before": json.loads(frame.to_json(orient="records")),
            "after": after,
        }


def apply_step(
    path: str,
    artifact_id: str,
    kind: str,
    field: str,
    options: dict[str, Any],
    alias: str,
) -> dict[str, Any]:
    """Commit one immutable TeAL translation with full lineage."""
    from text_analysis_lab import Project

    if not alias.strip():
        raise ValueError("Name this operation's output artifact.")
    with Project.open(path) as project:
        source = project.get_artifact(artifact_id)
        translator = _translator(kind, field, options)
        # SVD and UMAP may emit multiple outputs: TeAL requires one alias per output.
        if kind == "svd":
            aliases: str | dict[str, str] = {
                "output": alias,
                "components": f"{alias}_components",
            }
        else:
            aliases = alias
        result = project.translate(translator, source, alias=aliases)
        return {label: _artifact_details(artifact) for label, artifact in result.items()}


def finalize(
    path: str,
    documents_id: str,
    text_id: str,
    text_field: str,
    geometry_id: str,
    view_id: str | None,
    metadata_fields: list[str],
) -> dict[str, Any]:
    """Create the reserved GeCo workspace only after checking existing manifests."""
    from text_analysis_lab import Project

    with Project.open(path) as project:
        workspaces = [row for row in project.geco.list() if row["name"] == "desktop"]
        if workspaces:
            return {"workspace": "desktop", "already_exists": True}
        documents = project.get_artifact(documents_id)
        text = project.get_artifact(text_id)
        geometry = project.get_artifact(geometry_id)
        projections = {"default": project.get_artifact(view_id)} if view_id else {}
        handle = project.geco.create(
            "desktop",
            documents=documents,
            text=text,
            display_text=text,
            text_field=text_field,
            geometry=geometry,
            projections=projections,
            metadata_fields=metadata_fields,
            overwrite=False,
        )
        handle.close()
        return {"workspace": "desktop", "already_exists": False}
