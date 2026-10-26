"""Minimal branded native shell with project opening and Active Sessions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from geco_desktop.environments import EnvironmentManager
from geco_desktop.project import read_descriptor, reconcile_finalization
from geco_desktop.sessions import SessionManager

THEME = """
QMainWindow, QWidget { background: #f4f6f3; color: #171b18; font-size: 13px; }
QLabel#title { font-size: 24px; font-weight: 700; color: #255c3b; }
QPushButton { background: #ffffff; border: 1px solid #dfe3e6; border-radius: 8px; padding: 8px 12px; }
QPushButton:hover { background: #e7f1ea; border-color: #3f8d5d; }
QPushButton#primary { background: #3f8d5d; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #255c3b; }
QListWidget, QTabWidget::pane { background: #ffffff; border: 1px solid #dfe3e6; border-radius: 8px; }
QListWidget::item { padding: 9px; }
QListWidget::item:selected { background: #e7f1ea; color: #173a27; }
"""


class _Signals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback
        self.signals = _Signals()

    def run(self) -> None:
        try:
            self.signals.succeeded.emit(self.callback())
        except Exception as exc:
            self.signals.failed.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("GeCo Desktop")
        self.resize(800, 550)
        self.setStyleSheet(THEME)
        self.environments = EnvironmentManager()
        self.sessions = SessionManager()
        self.pool = QThreadPool.globalInstance()
        self._tasks: list[_Task] = []
        self._preparation = None
        self.settings = QSettings("GeCo Desktop", "GeCo Desktop")

        holder = QWidget()
        layout = QVBoxLayout(holder)
        layout.setContentsMargins(24, 20, 24, 24)
        heading = QLabel("🦎 GeCo Desktop")
        heading.setObjectName("title")
        layout.addWidget(heading)
        layout.addWidget(QLabel("Prepare a TeAL project and open it in GeCo."))
        tabs = QTabWidget()
        layout.addWidget(tabs)
        home = QWidget()
        home_layout = QVBoxLayout(home)
        self.status = QLabel("Open a GeCo Desktop project to launch its coding workspace.")
        home_layout.addWidget(self.status)
        create = QPushButton("New project…")
        create.setObjectName("primary")
        create.clicked.connect(self.new_project)
        home_layout.addWidget(create)
        browse = QPushButton("Open project…")
        browse.setObjectName("primary")
        browse.clicked.connect(self.open_project)
        home_layout.addWidget(browse)
        home_layout.addWidget(self._button_environment_manager())
        home_layout.addWidget(self._button_model_manager())
        home_layout.addWidget(QLabel("Recent projects"))
        self.recent_list = QListWidget()
        self.recent_list.setMaximumHeight(160)
        self.recent_list.itemDoubleClicked.connect(
            lambda item: self.open_project_path(str(item.data(Qt.ItemDataRole.UserRole)))
        )
        home_layout.addWidget(self.recent_list)
        self._load_recent_projects()
        home_layout.addStretch()
        tabs.addTab(home, "Home")

        active = QWidget()
        active_layout = QVBoxLayout(active)
        self.session_list = QListWidget()
        active_layout.addWidget(self.session_list)
        actions = QHBoxLayout()
        for text, handler in (
            ("Refresh", self.refresh_sessions),
            ("Open in browser", self.open_session_browser),
            ("Details", self.session_details),
            ("Stop", self.stop_session),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            actions.addWidget(button)
        active_layout.addLayout(actions)
        tabs.addTab(active, "Active Sessions")
        tabs.currentChanged.connect(lambda _: self.refresh_sessions())
        self.setCentralWidget(holder)
        self.refresh_sessions()

    def _background(self, work, success) -> None:
        task = _Task(work)
        self._tasks.append(task)
        task.signals.succeeded.connect(lambda value: self._complete(task, success, value))
        task.signals.failed.connect(lambda error: self._failed(task, error))
        self.pool.start(task)

    def _complete(self, task, success, value) -> None:
        self._tasks.remove(task)
        success(value)

    def _failed(self, task, message: str) -> None:
        self._tasks.remove(task)
        self.status.setText("Could not open project.")
        QMessageBox.warning(self, "GeCo Desktop", message)

    def _recent_paths(self) -> list[str]:
        saved = self.settings.value("recent_projects", [])
        if isinstance(saved, str):
            return [saved]
        return [str(value) for value in saved] if isinstance(saved, list) else []

    def _load_recent_projects(self) -> None:
        self.recent_list.clear()
        for value in self._recent_paths():
            if not (Path(value) / "project.gecod").is_file():
                continue
            self.recent_list.addItem(value)
            self.recent_list.item(self.recent_list.count() - 1).setData(
                Qt.ItemDataRole.UserRole, value
            )

    def _remember_project(self, root: str | Path) -> None:
        resolved = str(Path(root).expanduser().resolve())
        recent = [resolved] + [name for name in self._recent_paths() if name != resolved]
        self.settings.setValue("recent_projects", recent[:10])
        self._load_recent_projects()

    def open_project_path(self, path: str) -> None:
        self.status.setText("Opening GeCo project…")

        def work():
            root, descriptor = read_descriptor(Path(path))
            interpreter = self.environments.locate(descriptor.runtime)
            if descriptor.state == "preparing" and (root / ".teal").is_dir():
                # A crash can occur after TeAL creates the linked workspace but
                # before Desktop commits its portable finalized-state marker.
                from geco_desktop.environments import installed_runner_path, run_command

                info = run_command(
                    interpreter, installed_runner_path(), "project_info",
                    timeout=90, path=str(root),
                )
                descriptor = reconcile_finalization(
                    root, descriptor, info["workspaces"],
                )
            if descriptor.state == "preparing":
                return root, descriptor, interpreter, None
            session = self.sessions.start(root, descriptor, interpreter)
            return root, descriptor, interpreter, session

        def completed(data):
            root, descriptor, interpreter, session = data
            self._remember_project(root)
            if session is None:
                from .preparation import PreparationWindow

                self._preparation = PreparationWindow(
                    self.environments, self.sessions,
                    root=root, descriptor=descriptor,
                    interpreter=interpreter, parent=self,
                )
                self._preparation.show()
                self.status.setText(f"Resumed preparation: {descriptor.name}")
                return
            self.status.setText(f"Running: {session.project_name}")
            self.sessions.open_browser(session)
            self.refresh_sessions()

        self._background(work, completed)

    def _button_environment_manager(self) -> QPushButton:
        button = QPushButton("Scientific Environments…")
        button.clicked.connect(self.open_environment_manager)
        return button

    def open_environment_manager(self) -> None:
        from .environment_manager import EnvironmentManagerDialog

        dialog = EnvironmentManagerDialog(self.environments, self)
        dialog.exec()

    def _button_model_manager(self) -> QPushButton:
        button = QPushButton("Model Manager…")
        button.clicked.connect(self.open_model_manager)
        return button

    def open_model_manager(self) -> None:
        from .model_manager import ModelManagerDialog

        dialog = ModelManagerDialog(self.environments, self)
        dialog.exec()

    def new_project(self) -> None:
        from .preparation import PreparationWindow

        # Keep the window alive when opening it non-modally.
        self._preparation = PreparationWindow(self.environments, self.sessions, parent=self)
        self._preparation.project_created.connect(self._remember_project)
        self._preparation.show()

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open GeCo Desktop project", "", "GeCo project (project.gecod)"
        )
        if path:
            self.open_project_path(path)

    def refresh_sessions(self) -> None:
        self._background(self.sessions.list, self._show_sessions)

    def _show_sessions(self, sessions) -> None:
        self._latest_sessions = sessions
        self.session_list.clear()
        for session in sessions:
            self.session_list.addItem(f"{session.project_name} ({session.status})  —  {session.project_path}")
            self.session_list.item(self.session_list.count() - 1).setData(256, session.key)

    def _selected_key(self) -> str | None:
        item = self.session_list.currentItem()
        return str(item.data(256)) if item else None

    def open_session_browser(self) -> None:
        key = self._selected_key()
        for session in getattr(self, "_latest_sessions", []):
            if session.key == key:
                if session.status == "running":
                    self.sessions.open_browser(session)
                else:
                    self.status.setText("GeCo session is alive but not responding yet.")
                return

    def session_details(self) -> None:
        """Keep technical process details out of the main session list."""
        key = self._selected_key()
        for session in getattr(self, "_latest_sessions", []):
            if session.key != key:
                continue
            from PySide6.QtWidgets import QDialog, QFormLayout

            dialog = QDialog(self)
            dialog.setWindowTitle("GeCo Session Details")
            dialog.resize(440, 230)
            form = QFormLayout(dialog)
            for label, value in (
                ("Project", session.project_name),
                ("Location", session.project_path),
                ("Status", session.status),
                ("Server", session.url),
                ("Process ID", str(session.pid)),
                ("App-owned runner", session.runner_path),
            ):
                detail = QLabel(value)
                detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                detail.setWordWrap(True)
                form.addRow(label, detail)
            dialog.exec()
            return

    def stop_session(self) -> None:
        key = self._selected_key()
        if key:
            self._background(lambda: self.sessions.stop(key), lambda _: self.refresh_sessions())
