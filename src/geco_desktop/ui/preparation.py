"""Native project creation and TeAL preparation, without scientific imports in Qt.

A small workbench with explicit Apply and Preview: scientific state is always
owned by TeAL, and the only portable launcher file is project.gecod.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geco_desktop.environments import EnvironmentManager, installed_runner_path, run_command
from geco_desktop.project import ProjectDescriptor, RuntimeSpec, write_descriptor
from geco_desktop.sessions import SessionManager


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Work(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = _Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


def _row(*widgets: QWidget) -> QWidget:
    holder = QWidget()
    layout = QHBoxLayout(holder)
    layout.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        layout.addWidget(widget)
    return holder


def _button(label: str, callback) -> QPushButton:
    widget = QPushButton(label)
    widget.clicked.connect(callback)
    return widget


def _form_page() -> tuple[QWidget, QVBoxLayout, QFormLayout]:
    page = QWidget()
    layout = QVBoxLayout(page)
    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    layout.addLayout(form)
    return page, layout, form


def _fill_combo(combo: QComboBox, entries: list[dict], *, empty: str | None = None) -> None:
    selected = combo.currentData()
    combo.clear()
    if empty is not None:
        combo.addItem(empty, "")
    for entry in entries:
        combo.addItem(str(entry["name"]), str(entry["id"]))
    if selected is not None:
        index = combo.findData(selected)
        if index >= 0:
            combo.setCurrentIndex(index)


class PreparationWindow(QDialog):
    """Guided stateful interface; restart reopens TeAL artifacts, not a parallel DAG."""

    def __init__(
        self,
        environments: EnvironmentManager,
        sessions: SessionManager,
        *,
        root: Path | None = None,
        descriptor: ProjectDescriptor | None = None,
        interpreter: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prepare a GeCo project")
        self.resize(910, 700)
        self.environments = environments
        self.sessions = sessions
        self.root = root
        self.descriptor = descriptor
        self.interpreter = interpreter
        self.pool = QThreadPool.globalInstance()
        self._jobs: list[_Work] = []
        self.artifacts: list[dict] = []
        self.import_metadata: list[str] = []

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Create your project, prepare TeAL artifacts, then open GeCo."))
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self._setup_page()
        self._import_page()
        self._prepare_page()
        self._final_page()
        self.status = QLabel("Choose a destination and a supported scientific runtime.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        if root is not None and descriptor is not None:
            self.project_name.setText(descriptor.name)
            self.destination.setText(str(root.parent))
            self._set_existing()
            if (root / ".teal").is_dir():
                self.refresh_catalog()
            else:
                self.status.setText("Project was interrupted before TeAL initialization. Use Initialize missing TeAL state.")

    def _run(self, function, completed, *, message: str) -> None:
        self.status.setText(message)
        self.setEnabled(False)
        job = _Work(function)
        self._jobs.append(job)

        def finish(result: Any) -> None:
            self._jobs.remove(job)
            self.setEnabled(True)
            completed(result)

        def failed(error: str) -> None:
            self._jobs.remove(job)
            self.setEnabled(True)
            self.status.setText(f"Operation failed: {error}")
            QMessageBox.warning(self, "GeCo Desktop", error)

        job.signals.done.connect(finish)
        job.signals.failed.connect(failed)
        self.pool.start(job)

    def _command(self, action: str, *, timeout: int = 600, **arguments: Any) -> dict:
        if self.interpreter is None:
            raise ValueError("Create or open a project before running preparation operations.")
        return run_command(self.interpreter, installed_runner_path(), action, timeout=timeout, **arguments)

    def _setup_page(self) -> None:
        page, layout, form = _form_page()
        self.project_name = QLineEdit("My research")
        self.destination = QLineEdit(str(Path.home() / "Documents"))
        form.addRow("Project name", self.project_name)
        form.addRow("Parent folder", _row(self.destination, _button("Browse…", self.choose_destination)))
        self.python = QLineEdit("3.11")
        self.teal = QLineEdit("0.9.0")
        self.geco = QLineEdit("0.8.15")
        form.addRow("Scientific Python", self.python)
        form.addRow("TeAL version", self.teal)
        form.addRow("GeCo version", self.geco)
        layout.addWidget(QLabel("The scientific environment is installed/reused outside the project folder."))
        self.create_button = _button("Create project and provision environment", self.create_project)
        layout.addWidget(self.create_button)
        self.recover_button = _button("Initialize missing TeAL state", self.initialize_missing_teal)
        self.recover_button.setVisible(False)
        layout.addWidget(self.recover_button)
        layout.addStretch()
        self.tabs.addTab(page, "1 · Project")

    def choose_destination(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Choose parent folder", self.destination.text())
        if path:
            self.destination.setText(path)

    def create_project(self) -> None:
        name = self.project_name.text().strip()
        if not name or any(char in name for char in '\\/:*?"<>|'):
            QMessageBox.warning(self, "Project name", "Enter a valid folder name.")
            return
        parent = Path(self.destination.text()).expanduser()
        root = parent / (name if name.endswith(".gecod") else f"{name}.gecod")
        spec = RuntimeSpec(self.python.text().strip(), self.teal.text().strip(), self.geco.text().strip())

        def work():
            interpreter = self.environments.ensure(spec)
            # No replacement of a prior project or existing directory.
            root.mkdir(parents=True, exist_ok=False)
            descriptor = ProjectDescriptor.new(name, spec)
            write_descriptor(root, descriptor)
            run_command(interpreter, installed_runner_path(), "create_teal", timeout=120,
                        path=str(root), name=name)
            return root, descriptor, interpreter

        def finished(value):
            self.root, self.descriptor, self.interpreter = value
            self._set_existing()
            self.status.setText(f"Project created: {self.root}")
            self.tabs.setCurrentIndex(1)
            self.refresh_catalog()

        self._run(work, finished, message="Provisioning runtime and creating a TeAL project…")

    def _set_existing(self) -> None:
        self.create_button.setEnabled(False)
        self.recover_button.setVisible(self.root is not None and not (self.root / ".teal").exists())
        for widget in (self.project_name, self.destination, self.python, self.teal, self.geco):
            widget.setReadOnly(True)
        if self.descriptor:
            self.python.setText(self.descriptor.runtime.python)
            self.teal.setText(self.descriptor.runtime.teal)
            self.geco.setText(self.descriptor.runtime.geco)

    def initialize_missing_teal(self) -> None:
        """Recover a project interrupted after writing its portable descriptor."""
        if self.root is None or self.descriptor is None or self.interpreter is None:
            return
        if (self.root / ".teal").exists():
            self.recover_button.setVisible(False)
            self.refresh_catalog()
            return
        def done(_result):
            self.recover_button.setVisible(False)
            self.tabs.setCurrentIndex(1)
            self.refresh_catalog()
        self._run(lambda: self._command(
            "create_teal", path=str(self.root), name=self.descriptor.name
        ), done, message="Initializing missing TeAL project state…")

    def _import_page(self) -> None:
        page, layout, form = _form_page()
        self.source_kind = QComboBox()
        for title, kind in (
            ("CSV file", "csv"), ("CSV folder", "csv_folder"),
            ("Excel workbook", "excel"), ("Excel folder", "excel_folder"),
            ("JSONL file", "jsonl"), ("Parquet file", "parquet"),
            ("Text file", "txt"), ("Text folder", "txt_folder"),
            ("PDF file", "pdf"), ("PDF folder", "pdf_folder"),
        ):
            self.source_kind.addItem(title, kind)
        form.addRow("Source type", self.source_kind)
        self.csv_path = QLineEdit()
        form.addRow("Source file or folder", _row(self.csv_path, _button("Choose…", self.choose_csv)))
        self.recursive = QCheckBox("Include nested folders")
        self.recursive.setChecked(True)
        form.addRow("", self.recursive)
        self.text_columns = QListWidget()
        self.text_columns.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.metadata_columns = QListWidget()
        self.metadata_columns.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.text_label = QLabel("Text fields")
        self.metadata_label = QLabel("Metadata fields")
        form.addRow(self.text_label, self.text_columns)
        form.addRow(self.metadata_label, self.metadata_columns)
        self.import_button = _button("Import into TeAL", self.import_documents)
        layout.addWidget(self.import_button)
        self.csv_message = QLabel("Select a source to inspect the available columns or files.")
        self.csv_message.setWordWrap(True)
        layout.addWidget(self.csv_message)
        self.tabs.addTab(page, "2 · Import")
        self.source_kind.currentIndexChanged.connect(self._update_source_kind)
        self._update_source_kind()

    def _update_source_kind(self) -> None:
        kind = str(self.source_kind.currentData() or "csv")
        is_folder = kind.endswith("_folder")
        is_documents = kind in {"txt", "txt_folder", "pdf", "pdf_folder"}
        self.recursive.setVisible(is_folder)
        for widget in (self.text_columns, self.metadata_columns, self.text_label, self.metadata_label):
            widget.setVisible(not is_documents)
        self.csv_path.clear()
        self.text_columns.clear()
        self.metadata_columns.clear()
        self.csv_message.setText("Choose a source to inspect before importing.")

    def choose_csv(self) -> None:
        kind = str(self.source_kind.currentData())
        recursive = self.recursive.isChecked()
        if kind.endswith("_folder"):
            path = QFileDialog.getExistingDirectory(self, "Choose source folder")
        else:
            extension = {
                "csv": "CSV files (*.csv)", "excel": "Excel files (*.xlsx)",
                "jsonl": "JSON Lines (*.jsonl)", "parquet": "Parquet files (*.parquet)",
                "txt": "Text files (*.txt)", "pdf": "PDF files (*.pdf)",
            }[kind]
            path, _ = QFileDialog.getOpenFileName(self, "Choose source file", "", extension)
        if not path:
            return
        self.csv_path.setText(path)

        def finished(data):
            self.text_columns.clear()
            self.metadata_columns.clear()
            if kind not in {"txt", "txt_folder", "pdf", "pdf_folder"}:
                for name in data["columns"]:
                    self.text_columns.addItem(str(name))
                    self.metadata_columns.addItem(str(name))
                for i in range(self.text_columns.count()):
                    if self.text_columns.item(i).text().lower() in {"text", "content", "document"}:
                        self.text_columns.item(i).setSelected(True)
            self.csv_message.setText(
                f"{data['file_count']} source file(s); {len(data['columns'])} field(s) available."
            )

        self._run(lambda: self._command(
            "source_schema", source=path, kind=kind, recursive=recursive
        ), finished, message="Inspecting source structure…")

    def import_documents(self) -> None:
        kind = str(self.source_kind.currentData())
        text = [x.text() for x in self.text_columns.selectedItems()]
        metadata = [x.text() for x in self.metadata_columns.selectedItems()]
        if kind not in {"txt", "txt_folder", "pdf", "pdf_folder"} and not text:
            QMessageBox.warning(self, "Import", "Select at least one text field.")
            return
        if set(text) & set(metadata):
            QMessageBox.warning(self, "Import", "A field cannot be text and metadata simultaneously.")
            return
        source_path = self.csv_path.text()
        recursive = self.recursive.isChecked()
        root = str(self.root)

        def done(data):
            self.import_metadata = metadata
            self.status.setText(f"Imported {data['rows']} TeAL rows.")
            self.tabs.setCurrentIndex(2)
            self.refresh_catalog()

        self._run(lambda: self._command(
            "import_source", path=root, source_path=source_path, kind=kind,
            text_fields=text, metadata_fields=metadata, recursive=recursive,
        ), done, message="Importing source data through TeAL…")

    def _prepare_page(self) -> None:
        page, layout, form = _form_page()
        self.source = QComboBox()
        self.source.currentIndexChanged.connect(self._update_fields)
        form.addRow("Existing artifact", self.source)
        self.operation = QComboBox()
        for label, value in (
            ("Regex cleaning", "clean"), ("Pattern extraction", "pattern"),
            ("Split into units", "split"), ("CountVectorizer", "count"),
            ("TF-IDF", "tfidf"), ("SVD", "svd"), ("UMAP", "umap"),
        ):
            self.operation.addItem(label, value)
        self.operation.currentIndexChanged.connect(self._update_parameters)
        form.addRow("Operation", self.operation)
        self.field = QComboBox()
        form.addRow("Source text field", self.field)
        self.inputs: dict[str, QLineEdit] = {}
        for label, key, default in (
            ("Regex pattern", "pattern", r"(?P<metadata_speaker>[^:]+):\s*(?P<data_text>.*)"),
            ("Replacement", "replacement", ""),
            ("Output text field", "output_field", ""),
            ("Delimiter", "delimiter", r"\n"),
            ("New key", "new_key", "segment_id"),
            ("Max vocabulary", "max_features", "5000"),
            ("Components", "n_components", "2"),
            ("Neighbors", "n_neighbors", "15"),
            ("Minimum distance", "min_dist", "0.1"),
            ("Normalization (none, l1, l2)", "norm", "l2"),
        ):
            edit = QLineEdit(default)
            self.inputs[key] = edit
            form.addRow(label, edit)
        self._prepare_form = form
        self.output_alias = QLineEdit("prepared")
        form.addRow("Save as artifact", self.output_alias)
        layout.addWidget(_row(
            _button("First rows", lambda: self.show_preview(False)),
            _button("Random sample", lambda: self.show_preview(True)),
            _button("Try operation", self.try_operation),
            _button("Apply to all rows", self.apply_operation),
            _button("Refresh artifacts", self.refresh_catalog),
        ))
        self.table = QTableWidget()
        layout.addWidget(self.table)
        self.tabs.addTab(page, "3 · Prepare")
        self._update_parameters()

    def _update_fields(self) -> None:
        source = self._artifact(self.source.currentData())
        previous = self.field.currentText()
        self.field.clear()
        if source:
            self.field.addItems(source.get("data_fields", []))
        if previous:
            index = self.field.findText(previous)
            if index >= 0:
                self.field.setCurrentIndex(index)

    def _update_parameters(self) -> None:
        kind = self.operation.currentData()
        required = {
            "clean": {"pattern", "replacement", "output_field"},
            "pattern": {"pattern"},
            "split": {"delimiter", "new_key", "output_field"},
            "count": {"max_features"},
            "tfidf": {"norm"},
            "svd": {"n_components"},
            "umap": {"n_components", "n_neighbors", "min_dist"},
        }.get(kind, set())
        for key, edit in self.inputs.items():
            edit.setVisible(key in required)
            # QFormLayout labels are separate; explicitly hide them.
            form = self._prepare_form
            row, _role = form.getWidgetPosition(edit)
            if row >= 0:
                label_widget = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                if label_widget is not None and label_widget.widget():
                    label_widget.widget().setVisible(key in required)

    def _options(self) -> dict[str, Any]:
        kind = str(self.operation.currentData())
        values = {k: v.text().strip() for k, v in self.inputs.items()}
        if kind == "split":
            values["delimiter"] = values["delimiter"].replace(r"\n", "\n")
        return values

    def _artifact(self, identifier: Any) -> dict | None:
        return next((x for x in self.artifacts if x["id"] == str(identifier)), None)

    def _present_rows(self, columns: list[str], rows: list[dict]) -> None:
        self.table.clear()
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, column in enumerate(columns):
                self.table.setItem(i, j, QTableWidgetItem(str(row.get(column, ""))))
        self.table.resizeColumnsToContents()

    def show_preview(self, random: bool) -> None:
        identifier = str(self.source.currentData() or "")
        if not identifier:
            return
        def done(result):
            self._present_rows(result.get("columns", []), result.get("rows", []))
            self.status.setText(result.get("sampling", "Preview"))
        self._run(lambda: self._command(
            "preview", path=str(self.root), artifact_id=identifier, random=random,
        ), done, message="Sampling TeAL artifact without making a new one…")

    def try_operation(self) -> None:
        identifier = str(self.source.currentData() or "")
        if not identifier:
            return
        kind = str(self.operation.currentData())
        field = self.field.currentText()
        options = self._options()
        root = str(self.root)
        def done(result):
            rows = result.get("before", [])
            cols = list(rows[0]) if rows else []
            self._present_rows(cols, rows)
            self.status.setText(f"Try-only, no durable artifact created. {str(result.get('after'))[:900]}")
        self._run(lambda: self._command(
            "preview_step", path=root, artifact_id=identifier, kind=kind,
            field=field, options=options,
        ), done, message="Previewing the operation on a bounded sample…")

    def apply_operation(self) -> None:
        identifier = str(self.source.currentData() or "")
        if not identifier:
            return
        kind = str(self.operation.currentData())
        alias = self.output_alias.text().strip()
        field = self.field.currentText()
        options = self._options()
        root = str(self.root)
        if not alias:
            QMessageBox.warning(self, "Artifact name", "Provide an output artifact name.")
            return
        def done(result):
            self.status.setText(f"Saved {len(result)} TeAL output artifact(s): {alias}.")
            self.refresh_catalog()
        self._run(lambda: self._command(
            "apply_step", timeout=3600, path=root, artifact_id=identifier,
            kind=kind, field=field,
            options=options, alias=alias,
        ), done, message=f"Running {kind} on the full TeAL artifact…")

    def _final_page(self) -> None:
        page, layout, form = _form_page()
        self.documents = QComboBox()
        self.text_artifact = QComboBox()
        self.text_field = QComboBox()
        self.text_artifact.currentIndexChanged.connect(self._refresh_text_fields)
        self.geometry = QComboBox()
        self.projection = QComboBox()
        self.metadata_names = QLineEdit()
        for label, widget in (
            ("Documents (key universe)", self.documents),
            ("Prepared text artifact", self.text_artifact),
            ("Text field", self.text_field),
            ("Geometry", self.geometry),
            ("Optional 2D view", self.projection),
            ("Metadata fields, comma separated", self.metadata_names),
        ):
            form.addRow(label, widget)
        layout.addWidget(QLabel("Finalization links saved TeAL artifacts to a GeCo workspace. It never overwrites a workspace."))
        layout.addWidget(_row(
            _button("Refresh review", self.refresh_catalog),
            _button("Create GeCo workspace", self.finalize_project),
            _button("Open GeCo in browser", self.launch_browser),
        ))
        layout.addStretch()
        self.tabs.addTab(page, "4 · Finalize")

    def _refresh_text_fields(self) -> None:
        item = self._artifact(self.text_artifact.currentData())
        previous = self.text_field.currentText()
        self.text_field.clear()
        if item:
            self.text_field.addItems(item.get("data_fields", []))
        if previous:
            idx = self.text_field.findText(previous)
            if idx >= 0:
                self.text_field.setCurrentIndex(idx)

    def refresh_catalog(self) -> None:
        if self.root is None or self.interpreter is None:
            return

        def done(data):
            self.artifacts = data["artifacts"]
            self.status.setText(f"{len(self.artifacts)} saved TeAL artifacts. {len(data['workspaces'])} linked GeCo workspace(s).")
            table = [a for a in self.artifacts if a["type"] in {"table", "jsonl"}]
            matrices = [a for a in self.artifacts if a["type"] in {"dense_matrix", "sparse_matrix"}]
            for combo, entries, empty in (
                (self.source, self.artifacts, None),
                (self.documents, table, None),
                (self.text_artifact, table, None),
                (self.geometry, matrices, None),
                (self.projection, [a for a in matrices if len(a["data_fields"]) == 2], "No 2D view"),
            ):
                _fill_combo(combo, [{"id": a["id"], "name": ", ".join(a["aliases"]) or a["id"][:12]} for a in entries], empty=empty)
            self._update_fields()
            self._refresh_text_fields()
            if self.import_metadata and not self.metadata_names.text():
                self.metadata_names.setText(", ".join(self.import_metadata))

        self._run(lambda: self._command("catalog", path=str(self.root)),
                  done, message="Loading TeAL artifact catalog…")

    def finalize_project(self) -> None:
        if self.root is None or self.descriptor is None:
            return
        args = {
            "path": str(self.root),
            "documents_id": str(self.documents.currentData() or ""),
            "text_id": str(self.text_artifact.currentData() or ""),
            "text_field": self.text_field.currentText(),
            "geometry_id": str(self.geometry.currentData() or ""),
            "view_id": str(self.projection.currentData() or "") or None,
            "metadata_fields": [v.strip() for v in self.metadata_names.text().split(",") if v.strip()],
        }
        if not all((args["documents_id"], args["text_id"], args["text_field"], args["geometry_id"])):
            QMessageBox.warning(self, "Finalize", "Choose documents, text, text field and geometry.")
            return
        def done(result):
            self.descriptor = replace(self.descriptor, state="finalized", last_artifact_id=args["text_id"])
            write_descriptor(self.root, self.descriptor, replace=True)
            self.status.setText("Linked GeCo workspace is ready. Click Open GeCo in browser.")
        self._run(lambda: self._command("finalize", timeout=1200, **args),
                  done, message="Validating and creating the linked GeCo workspace…")

    def launch_browser(self) -> None:
        if self.root is None or self.interpreter is None or self.descriptor is None:
            return
        if self.descriptor.state != "finalized":
            QMessageBox.warning(self, "Open GeCo", "Finalize the linked GeCo workspace first.")
            return
        def done(session):
            self.sessions.open_browser(session)
            self.status.setText(f"GeCo is running: {session.url}")
        self._run(lambda: self.sessions.start(self.root, self.descriptor, self.interpreter),
                  done, message="Launching the GeCo browser server…")
