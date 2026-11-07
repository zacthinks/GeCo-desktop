"""Minimal branded native shell with project opening and Active Sessions."""

from __future__ import annotations

import tomllib
import uuid
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from geco_desktop.environments import EnvironmentError, EnvironmentManager
from geco_desktop.project import (
    ProjectDescriptor,
    RuntimeSpec,
    read_descriptor,
    reconcile_finalization,
)
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


class ProjectDashboard(QDialog):
    """Small permanent entry point; all scientific inventory comes from TeAL."""

    def __init__(
        self, owner: MainWindow, root, descriptor, interpreter, *,
        external: bool = False, workspace_name: str | None = None,
    ):
        super().__init__(owner)
        self.owner = owner
        self.root = root
        self.descriptor = descriptor
        self.interpreter = interpreter
        self.external = external
        self.workspace_name = workspace_name
        self.setWindowTitle(f"{descriptor.name} — GeCo Desktop")
        self.resize(750, 540)
        layout = QVBoxLayout(self)
        title = QLabel(descriptor.name)
        title.setObjectName("title")
        layout.addWidget(title)
        self.summary = QLabel("Loading TeAL artifacts…")
        layout.addWidget(self.summary)
        self.artifacts = QTreeWidget()
        self.artifacts.setColumnCount(3)
        self.artifacts.setHeaderLabels(["Artifact", "Type", "Observations"])
        self.artifacts.setAlternatingRowColors(True)
        layout.addWidget(self.artifacts)
        actions = QHBoxLayout()
        self.preparation_button = QPushButton(
            "Set up GeCo…" if external else "Import and prepare observations…"
        )
        self.preparation_button.clicked.connect(self.open_preparation)
        self.preparation_button.setEnabled(
            workspace_name is None if external else descriptor.state != "finalized"
        )
        self.launch_button = QPushButton("Open GeCo")
        self.launch_button.setEnabled(
            (workspace_name is not None) if external
            else descriptor.state == "finalized"
        )
        self.launch_button.clicked.connect(self.open_geco)
        refresh = QPushButton("Refresh artifacts")
        refresh.clicked.connect(self.refresh)
        for button in (self.preparation_button, self.launch_button, refresh):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self):
        from geco_desktop.environments import installed_runner_path, run_command
        self.summary.setText("Loading saved TeAL artifacts…")
        def work():
            return run_command(
                self.interpreter, installed_runner_path(), "catalog",
                timeout=90, path=str(self.root)
            )
        def done(data):
            self.artifacts.clear()
            artifacts = data.get("artifacts", [])
            nodes = {}
            for artifact in artifacts:
                identifier = str(artifact["id"])
                name = ", ".join(artifact.get("aliases") or ()) or identifier[:12]
                node = QTreeWidgetItem([
                    name,
                    str(artifact.get("type", "artifact")).replace("_", " "),
                    f"{int(artifact.get('rows', 0)):,}",
                ])
                node.setToolTip(0, identifier)
                nodes[identifier] = node
            for artifact in artifacts:
                identifier = str(artifact["id"])
                parent = nodes.get(str(artifact.get("source_artifact_id") or ""))
                if parent is None or parent is nodes[identifier]:
                    self.artifacts.addTopLevelItem(nodes[identifier])
                else:
                    parent.addChild(nodes[identifier])
            self.artifacts.expandAll()
            self.artifacts.resizeColumnToContents(0)
            self.summary.setText(
                f"{len(artifacts)} TeAL artifacts · "
                f"{len(data.get('workspaces', []))} GeCo workspaces"
            )
            if self.external:
                names = [str(item["name"]) for item in data.get("workspaces", [])]
                if self.workspace_name is None and len(names) == 1:
                    self.workspace_name = names[0]
                self.preparation_button.setEnabled(not names)
                self.launch_button.setEnabled(
                    self.workspace_name is not None
                    and self.workspace_name in names
                )
            else:
                _root, current = read_descriptor(self.root)
                self.descriptor = current
                self.preparation_button.setEnabled(current.state != "finalized")
                self.launch_button.setEnabled(current.state == "finalized")
        self.owner._background(work, done)

    def open_preparation(self):
        from .preparation import PreparationWindow
        self.owner._preparation = PreparationWindow(
            self.owner.environments, self.owner.sessions,
            root=self.root,
            descriptor=(
                replace(self.descriptor, state="preparing")
                if self.external else self.descriptor
            ),
            interpreter=self.interpreter, external=self.external,
            parent=self.owner,
        )
        self.owner._preparation.finished.connect(lambda _result: self.refresh())
        self.owner._preparation.show()

    def open_geco(self):
        def done(session):
            self.owner.sessions.open_browser(session)
            self.owner.refresh_sessions()
        self.owner._background(
            lambda: self.owner.sessions.start(
                self.root, self.descriptor, self.interpreter,
                workspace=self.workspace_name,
            ),
            done,
        )


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
            if not (
                (Path(value) / "project.gecod").is_file()
                or (Path(value) / ".teal").is_dir()
            ):
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
        requested = Path(path).expanduser().resolve()
        root_path = requested.parent if requested.name == "project.gecod" else requested
        if (
            root_path.is_dir() and not (root_path / "project.gecod").is_file()
            and (root_path / ".teal").is_dir()
        ):
            self._open_external_teal(root_path)
            return
        self.status.setText("Opening GeCo project…")

        def work():
            root, descriptor = read_descriptor(Path(path))
            try:
                interpreter = self.environments.locate(descriptor.runtime)
            except EnvironmentError:
                # A moved/copied .gecod project does not carry a Python runtime.
                # Missing profiles can be explicitly provisioned by the user;
                # corrupt/partial profiles must not be silently overwritten.
                profile_path = self.environments.profile(descriptor.runtime).path
                if profile_path.exists():
                    return root, descriptor, None, "repair"
                return root, descriptor, None, "install"
            if descriptor.state == "preparing" and not (root / ".teal").exists():
                from geco_desktop.environments import installed_runner_path, run_command

                run_command(
                    interpreter, installed_runner_path(), "create_teal",
                    timeout=120, path=str(root), name=descriptor.name,
                )
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
            return root, descriptor, interpreter, None

        def completed(data):
            root, descriptor, interpreter, session = data
            self._remember_project(root)
            if interpreter is None:
                if session == "repair":
                    self._offer_runtime_repair(root, descriptor)
                else:
                    self._offer_runtime_install(root, descriptor)
                return
            self._dashboard = ProjectDashboard(self, root, descriptor, interpreter)
            self._dashboard.show()
            self.status.setText(f"Opened project: {descriptor.name}")

        self._background(work, completed)

    def _open_external_teal(self, root: Path) -> None:
        """Inspect a Python-created TeAL project without writing Desktop metadata."""
        from geco_desktop.environments import installed_runner_path, run_command

        required = {}
        lock = root / "uv.lock"
        if lock.is_file():
            try:
                for item in tomllib.loads(lock.read_text(encoding="utf-8")).get("package", []):
                    if item.get("name") in {"text-analysis-lab", "geometric-coder"}:
                        required[item["name"]] = item["version"]
            except (OSError, ValueError, KeyError, TypeError):
                QMessageBox.warning(
                    self, "Open project", "The project's uv.lock could not be inspected."
                )
                return
        candidates = []
        for record in self.environments.list_profiles():
            if record.get("state") != "ready" or not isinstance(record.get("spec"), dict):
                continue
            spec = RuntimeSpec.from_dict(record["spec"])
            if any((
                required.get("text-analysis-lab") not in {None, spec.teal},
                required.get("geometric-coder") not in {None, spec.geco},
            )):
                continue
            try:
                python = self.environments.locate(spec)
            except EnvironmentError:
                continue
            candidates.append((spec, python))
        if not candidates:
            QMessageBox.warning(
                self, "Software profile unavailable",
                "This TeAL project needs a compatible installed software profile. "
                "Its files have not been changed.",
            )
            return
        spec, interpreter = candidates[0]
        self.status.setText("Inspecting TeAL workspaces…")

        def completed(info):
            names = [str(item["name"]) for item in info["workspaces"]]
            chosen = None
            if len(names) == 1:
                chosen = names[0]
            elif len(names) > 1:
                settings_key = "preferred_geco_" + uuid.uuid5(
                    uuid.NAMESPACE_URL, str(root)
                ).hex
                default_name = str(self.settings.value(settings_key, names[0]))
                initial = names.index(default_name) if default_name in names else 0
                chosen, accepted = QInputDialog.getItem(
                    self, "Open GeCo", "Choose a coding workspace", names, initial, False
                )
                if not accepted:
                    return
                self.settings.setValue(settings_key, chosen)
            descriptor = replace(
                ProjectDescriptor.new(root.name, spec),
                project_id=str(uuid.uuid5(uuid.NAMESPACE_URL, str(root))),
                state="finalized",
            )
            self._dashboard = ProjectDashboard(
                self, root, descriptor, interpreter,
                external=True, workspace_name=chosen,
            )
            self._dashboard.show()
            self._remember_project(root)
            self.status.setText(f"Opened TeAL project: {root.name}")
        self._background(
            lambda: run_command(
                interpreter, installed_runner_path(), "project_info",
                timeout=90, path=str(root),
            ),
            completed,
        )

    def _offer_runtime_install(self, root, descriptor) -> None:
        """Ask before installing a missing runtime while opening a portable project."""
        profile = self.environments.profile(descriptor.runtime)
        packages = "\n".join(f"  • {requirement}" for requirement in profile.packages)
        answer = QMessageBox.question(
            self,
            "Install scientific environment?",
            f"The project {descriptor.name!r} needs a scientific Python environment "
            "that is not installed on this computer.\n\n"
            f"Python: {descriptor.runtime.python}\n"
            f"Declared packages:\n{packages}\n\n"
            f"Install location:\n{profile.path}\n\n"
            "Install these packages now? The project folder and TeAL data "
            "will not be modified.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText(
                f"Project {descriptor.name!r} was not opened: scientific environment "
                "installation was declined. Its files are unchanged."
            )
            return

        self.status.setText(f"Installing scientific environment for {descriptor.name}…")
        self._background(
            lambda: self.environments.ensure(descriptor.runtime),
            lambda _python: self.open_project_path(str(root)),
        )

    def _offer_runtime_repair(self, root, descriptor) -> None:
        """Explicit opt-in repair; never touch the portable project files."""
        profile = self.environments.profile(descriptor.runtime)
        answer = QMessageBox.question(
            self,
            "Repair scientific environment?",
            f"The environment for {descriptor.name!r} is incomplete or damaged.\n\n"
            f"Environment: {profile.path}\n\n"
            "Rebuild this shared scientific environment? The replacement is "
            "prepared separately before the old directory is replaced. "
            "Your .gecod project will not be modified.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.status.setText("Environment repair declined; project files unchanged.")
            return
        self.status.setText(f"Repairing scientific environment for {descriptor.name}…")
        self._background(
            lambda: self.environments.repair(descriptor.runtime),
            lambda _python: self.open_project_path(str(root)),
        )

    def _button_environment_manager(self) -> QPushButton:
        button = QPushButton("Software Profiles…")
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
        from .preparation import NewProjectDialog

        # Project creation ends here. Initial import lives in the opened project.
        self._new_project = NewProjectDialog(self.environments, parent=self)
        self._new_project.project_created.connect(self._remember_project)
        self._new_project.show()

    def open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Open GeCo or TeAL project folder"
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
