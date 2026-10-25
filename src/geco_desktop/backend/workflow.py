"""User-selected TeAL operations for the Desktop preparation workbench.

This is an app-owned adapter, not an alternative science or artifact engine.
Every durable operation calls TeAL's public API within the pinned child Python.
"""
from __future__ import annotations

import csv
import json
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



SOURCE_TYPES = frozenset({
    "csv", "csv_folder", "excel", "excel_folder", "jsonl", "parquet",
    "txt", "txt_folder", "pdf", "pdf_folder",
})


def _source_files(source: Path, extension: str, *, recursive: bool) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() != extension:
            raise ValueError(f"Expected a {extension} source file.")
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(f"Source folder does not exist: {source}")
    files = sorted(
        file for file in (source.rglob("*") if recursive else source.iterdir())
        if file.is_file() and file.suffix.lower() == extension
    )
    if not files:
        raise ValueError(f"No {extension} files found under {source}.")
    return files


def source_schema(source: str, kind: str, recursive: bool = True) -> dict[str, Any]:
    """Display a small source sample, without importing research data into TeAL.

    TeAL remains responsible for the actual import, extraction and data typing.
    """
    if kind not in SOURCE_TYPES:
        raise ValueError(f"Unsupported import type: {kind!r}")
    path = Path(source).expanduser()
    ext = {
        "csv": ".csv", "csv_folder": ".csv",
        "excel": ".xlsx", "excel_folder": ".xlsx",
        "jsonl": ".jsonl", "parquet": ".parquet",
        "txt": ".txt", "txt_folder": ".txt",
        "pdf": ".pdf", "pdf_folder": ".pdf",
    }[kind]
    files = _source_files(path, ext, recursive=recursive)
    if kind in {"txt", "txt_folder", "pdf", "pdf_folder"}:
        sample = [
            {"source_file": str(file.relative_to(path)) if path.is_dir() else file.name}
            for file in files[:5]
        ]
        return {"columns": ["text"], "sample": sample, "file_count": len(files)}
    file = files[0]
    if kind in {"csv", "csv_folder"}:
        result = csv_schema(str(file))
    elif kind == "excel" or kind == "excel_folder":
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("Excel preview requires openpyxl in the selected scientific environment.") from exc
        book = load_workbook(file, read_only=True, data_only=True)
        try:
            sheet = book.active
            it = sheet.iter_rows(values_only=True)
            columns = [str(v) if v is not None else "" for v in next(it, ())]
            rows = [
                {col: value for col, value in zip(columns, record, strict=False)}
                for _, record in zip(range(5), it, strict=False)
            ]
            result = {"columns": columns, "sample": rows}
        finally:
            book.close()
    elif kind == "jsonl":
        rows: list[dict[str, Any]] = []
        with file.open("r", encoding="utf-8-sig") as stream:
            for line in stream:
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError("JSONL observations must be JSON objects.")
                rows.append(record)
                if len(rows) >= 5:
                    break
        result = {"columns": list(dict.fromkeys(key for row in rows for key in row)), "sample": rows}
    else:
        try:
            import duckdb
        except ImportError as exc:
            raise RuntimeError("Parquet preview requires DuckDB in the selected scientific environment.") from exc
        con = duckdb.connect(database=":memory:")
        try:
            relation = con.read_parquet(str(file))
            columns = [str(x) for x in relation.columns]
            rows = [dict(zip(columns, values, strict=False)) for values in relation.limit(5).fetchall()]
        finally:
            con.close()
        result = {"columns": columns, "sample": rows}
    columns = result["columns"]
    if not columns or any(not str(name).strip() for name in columns):
        raise ValueError("The source requires nonempty field names.")
    if len(set(columns)) != len(columns):
        raise ValueError("The source has duplicate field names.")
    result["file_count"] = len(files)
    return result


def import_source(
    path: str,
    source_path: str,
    kind: str,
    text_fields: list[str],
    metadata_fields: list[str],
    recursive: bool = True,
) -> dict[str, Any]:
    """Commit one import into the ordinary TeAL project with a stable alias."""
    if kind not in SOURCE_TYPES:
        raise ValueError(f"Unsupported import type: {kind!r}")
    folder_kind = kind.endswith("_folder")
    file_kind = kind in {"txt", "pdf"}
    text_file_kind = kind in {"txt", "txt_folder", "pdf", "pdf_folder"}
    if not text_file_kind and not text_fields:
        raise ValueError("Choose at least one text field.")
    if set(text_fields) & set(metadata_fields):
        raise ValueError("A field cannot be both text and metadata.")
    from text_analysis_lab import Project
    from text_analysis_lab import translators as tr

    input_path = Path(source_path).expanduser()
    extension = ".pdf" if kind.startswith("pdf") else ".txt" if kind.startswith("txt") else None
    if extension:
        files = _source_files(input_path, extension, recursive=recursive)
        if file_kind and len(files) != 1:
            raise ValueError("Choose exactly one file for single-file import.")
    with Project.open(path) as project:
        if any("documents" in row.get("aliases", []) for row in project.list_artifacts()):
            raise FileExistsError("Documents were already imported. Reopen them in the Prepare tab.")
        if text_file_kind:
            root = input_path.parent if file_kind else input_path
            pattern = input_path.name if file_kind else f"*{extension}"
            inventory = project.folder_inventory(
                root, patterns=pattern, recursive=recursive if not file_kind else False,
                alias="file_inventory",
            )
            extractor = tr.PdfTextExtractor() if kind.startswith("pdf") else tr.TextFileExtractor()
            result = project.translate(extractor, inventory, alias="documents")["output"]
        else:
            method = {
                "csv": project.read_csv,
                "csv_folder": project.read_csv_folder,
                "excel": project.read_excel,
                "excel_folder": project.read_excel_folder,
                "jsonl": project.read_jsonl,
                "parquet": project.read_parquet,
            }[kind]
            options: dict[str, Any] = {
                "text_fields": text_fields,
                "metadata_fields": metadata_fields,
                "alias": "documents",
            }
            if folder_kind:
                options["recursive"] = recursive
            result = method(input_path, **options)
        return _artifact_details(result)

def _artifact_details(artifact: Any) -> dict[str, Any]:
    return {
        "id": str(artifact.artifact_id),
        "type": str(getattr(artifact.artifact_type, "value", artifact.artifact_type)),
        "rows": int(artifact.n_rows or 0),
        "keys": list(artifact.primary_key),
        "data_fields": list(artifact.get_data_columns())[:250],
        "dimensions": len(artifact.get_data_columns()),
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
    if kind == "sentence_embeddings":
        if not str(options.get("model") or "").strip():
            raise ValueError("Specify a SentenceTransformers model identifier.")
        return tr.SentenceTransformerEncoder(
            model=str(options["model"]).strip(),
            text_field=field,
            revision=str(options.get("revision") or "").strip() or None,
            normalize=str(options.get("normalize", "false")).lower() == "true",
            truncation=str(options.get("truncation") or "error"),
            max_length=int(options["max_length"]) if str(options.get("max_length") or "").strip() else None,
            trust_remote_code=False,
            save_model=False,
        )
    if kind == "spacy":
        return tr.SpacyTranslator(
            model=str(options.get("spacy_model") or "en_core_web_sm"),
            text_field=field,
            save_model=False,
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
        elif kind == "spacy":
            aliases = {"sentences": f"{alias}_sentences", "tokens": f"{alias}_tokens"}
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
