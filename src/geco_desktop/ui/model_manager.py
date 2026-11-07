"""Thin inventory-first frontend over TeAL's user-level ModelManager."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geco_desktop.environments import EnvironmentManager, installed_runner_path, run_command
from geco_desktop.project import RuntimeSpec


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Work(QRunnable):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.signals = _Signals()

    def run(self):
        try:
            self.signals.done.emit(self.callback())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class ModelManagerDialog(QDialog):
    """Show the model resources TeAL actually recognizes across shared caches."""

    def __init__(self, manager: EnvironmentManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self._jobs: list[_Work] = []
        self._models: list[dict] = []
        self.setWindowTitle("Models")
        self.resize(820, 530)
        layout = QVBoxLayout(self)
        self.status = QLabel("Models are shared across projects. Loading available resources…")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.environment = QComboBox()
        self.environment.setToolTip("Select a compatible installed software profile")
        for record in manager.list_profiles():
            if record.get("state") != "ready" or not isinstance(record.get("spec"), dict):
                continue
            try:
                runtime = RuntimeSpec.from_dict(record["spec"])
            except (ValueError, KeyError, TypeError):
                continue
            self.environment.addItem(
                f"TeAL {runtime.teal} · GeCo {runtime.geco}",
                record["spec"],
            )
        layout.addWidget(self.environment)
        self.environment.currentIndexChanged.connect(self.refresh)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Model", "Source", "Status"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.add_button = QPushButton("Add model…")
        self.add_button.clicked.connect(self.add_model)
        self.verify_button = QPushButton("Verify selection")
        self.verify_button.clicked.connect(self.verify)
        for button in (self.add_button, self.verify_button, self.refresh_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.refresh()

    def _python(self):
        spec = self.environment.currentData()
        if not spec:
            raise ValueError(
                "No compatible software profile is installed. "
                "Install an approved TeAL 0.11+ profile to inspect shared models."
            )
        return self.manager.locate(RuntimeSpec.from_dict(spec))

    def _run(self, action: str, completed, **arguments):
        try:
            python = self._python()
        except Exception as exc:
            self.status.setText(str(exc))
            return
        self.refresh_button.setEnabled(False)
        self.add_button.setEnabled(False)
        self.verify_button.setEnabled(False)
        job = _Work(lambda: run_command(
            python, installed_runner_path(), action, timeout=3600, **arguments
        ))
        self._jobs.append(job)

        def release():
            self._jobs.remove(job)
            self.refresh_button.setEnabled(True)
            self.add_button.setEnabled(True)
            self.verify_button.setEnabled(True)

        def success(result):
            release()
            completed(result)

        def failure(message):
            release()
            self.status.setText(message)
            QMessageBox.warning(self, "Models", message)

        job.signals.done.connect(success)
        job.signals.failed.connect(failure)
        QThreadPool.globalInstance().start(job)

    def refresh(self, *_):
        self.status.setText("Inspecting models and shared caches…")

        def completed(result):
            self._models = result["models"]
            self.table.setRowCount(len(self._models))
            for row, item in enumerate(self._models):
                status = "Found locally" if item["present"] else "Not downloaded"
                for col, value in enumerate((item["name"], item["provider"], status)):
                    self.table.setItem(row, col, QTableWidgetItem(str(value)))
            self.table.resizeColumnsToContents()
            self.status.setText(
                f"{sum(m['present'] for m in self._models)} model resources found "
                f"across {len(self._models)} supported resources. "
                "Presence does not guarantee compatibility."
            )

        self._run("teal_model_catalog", completed)

    def _selected(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self._models):
            return None
        return self._models[row]

    def add_model(self):
        # Provider support comes from TeAL. Do not invent a second downloader.
        choices = [item for item in self._models if not item["present"]]
        if not choices:
            QMessageBox.information(
                self, "Models", "All supported resources in this TeAL profile are present."
            )
            return
        from PySide6.QtWidgets import QInputDialog

        names = [f"{item['provider']} · {item['name']}" for item in choices]
        choice, ok = QInputDialog.getItem(
            self, "Add model", "Choose a supported model", names, 0, False
        )
        if not ok:
            return
        item = choices[names.index(choice)]
        answer = QMessageBox.question(
            self, "Download model",
            f"Download {item['name']} to the shared model cache? "
            "The model may be large and require an internet connection.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status.setText(f"Downloading {item['name']}…")
        self._run("teal_model_install", lambda _: self.refresh(), model_key=item["key"])

    def verify(self):
        item = self._selected()
        if item is None:
            QMessageBox.information(self, "Models", "Select a model to verify.")
            return

        def completed(info):
            messages = [f"{key}: {value}" for key, value in info.items()]
            QMessageBox.information(self, "Model check", "\\n".join(messages))
        self._run("teal_model_verify", completed, model_key=item["key"])
