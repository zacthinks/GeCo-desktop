"""Shared on-demand Hugging Face model resources; never mutate pinned profiles."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geco_desktop.environments import EnvironmentManager, installed_runner_path, run_command
from geco_desktop.project import RuntimeSpec


class _Signals(QObject):
    finished = Signal(object)
    failed = Signal(str)


class _Job(QRunnable):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.signals = _Signals()

    def run(self):
        try:
            self.signals.finished.emit(self.callback())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ModelManagerDialog(QDialog):
    """Explicit opt-in model download into the shared revision-aware Hub cache."""

    def __init__(self, manager: EnvironmentManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Model Manager")
        self.resize(850, 500)
        self._jobs: list[_Job] = []
        layout = QVBoxLayout(self)
        message = QLabel(
            "Download exact Hugging Face model snapshots to the shared cache. "
            "Choose a compatible installed scientific environment; downloads "
            "do not alter its packages or automatically select a model for a project."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        form = QFormLayout()
        self.profile = QComboBox()
        for record in self.manager.list_profiles():
            if record.get("state") != "ready":
                continue
            spec = record.get("spec")
            if not isinstance(spec, dict):
                continue
            runtime = RuntimeSpec.from_dict(spec)
            label = f"Python {runtime.python} · TeAL {runtime.teal} · GeCo {runtime.geco}"
            self.profile.addItem(label, spec)
        form.addRow("Installed environment", self.profile)
        self.model = QLineEdit("sentence-transformers/all-MiniLM-L6-v2")
        form.addRow("Model repository", self.model)
        self.revision = QLineEdit()
        self.revision.setPlaceholderText("Optional release revision or commit SHA")
        form.addRow("Requested revision", self.revision)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("Inspect downloaded models")
        self.refresh_button.clicked.connect(self.refresh)
        self.download_button = QPushButton("Download model")
        self.download_button.clicked.connect(self.download)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.download_button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Model", "Exact revision", "Disk size (MB)"])
        layout.addWidget(self.table)
        self.status = QLabel("Select a scientific environment to inspect its shared model cache.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)

    def _interpreter(self):
        spec = self.profile.currentData()
        if not spec:
            raise ValueError("Install a compatible scientific environment first.")
        return self.manager.locate(RuntimeSpec.from_dict(spec))

    def _background(self, command: str, *, success, **params):
        # Snapshot all Qt values before worker dispatch; workers never access Qt.
        try:
            python = self._interpreter()
        except Exception as exc:
            QMessageBox.warning(self, "Model Manager", str(exc))
            return
        self.status.setText("Checking the shared model cache…" if command == "model_inventory"
                            else "Downloading requested model revision…")
        self.refresh_button.setEnabled(False)
        self.download_button.setEnabled(False)
        job = _Job(lambda: run_command(
            python, installed_runner_path(), command, timeout=3600, **params
        ))
        self._jobs.append(job)

        def clear():
            self._jobs.remove(job)
            self.refresh_button.setEnabled(True)
            self.download_button.setEnabled(True)

        def completed(data):
            clear()
            success(data)

        def failed(message):
            clear()
            self.status.setText(message)
            QMessageBox.warning(self, "Model Manager", message)

        job.signals.finished.connect(completed)
        job.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(job)

    def refresh(self):
        def completed(result):
            models = result["models"]
            self.table.setRowCount(len(models))
            for i, model in enumerate(models):
                for j, value in enumerate((
                    model["model"], model["revision"][:12],
                    f"{model['size_bytes'] / (1024 * 1024):.1f}",
                )):
                    self.table.setItem(i, j, QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents()
            warnings = result.get("warnings", [])
            self.status.setText(
                f"{len(models)} cached model revision(s)." +
                (f" Cache warning: {warnings[0]}" if warnings else "")
            )

        self._background("model_inventory", success=completed)

    def download(self):
        model = self.model.text().strip()
        revision = self.revision.text().strip()
        if not model:
            QMessageBox.warning(self, "Model Manager", "Enter a model repository.")
            return
        choice = QMessageBox.question(
            self, "Download model",
            f"Download {model} ({revision or 'latest revision'}) into the shared model cache? "
            "This may require substantial disk space and internet access.",
        )
        if choice != QMessageBox.StandardButton.Yes:
            return

        def completed(info):
            # Show resolved immutable revision, which can be used in TeAL settings.
            self.revision.setText(info["revision"])
            self.status.setText(
                f"Downloaded {info['model']} @ {info['revision']}."
            )
            self.refresh()

        self._background(
            "download_model", success=completed,
            model=model, revision=revision or None,
        )
