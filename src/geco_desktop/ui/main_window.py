"""Minimal branded native shell with project opening and Active Sessions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal
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
from geco_desktop.project import read_descriptor
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
        browse = QPushButton("Open project…")
        browse.setObjectName("primary")
        browse.clicked.connect(self.open_project)
        home_layout.addWidget(browse)
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

    def open_project(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open GeCo Desktop project", "", "GeCo projects (project.gecod *.gecod)"
        )
        if not path:
            return
        self.status.setText("Opening GeCo project…")

        def work():
            root, descriptor = read_descriptor(Path(path))
            interpreter = self.environments.locate(descriptor.runtime)
            session = self.sessions.start(root, descriptor, interpreter)
            return session

        def completed(session):
            self.status.setText(f"Running: {session.project_name}")
            self.sessions.open_browser(session)
            self.refresh_sessions()

        self._background(work, completed)

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

    def stop_session(self) -> None:
        key = self._selected_key()
        if key:
            self._background(lambda: self.sessions.stop(key), lambda _: self.refresh_sessions())
