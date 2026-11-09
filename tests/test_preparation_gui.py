"""Offscreen construction contract for the real preparation workbench."""
import pytest


def test_native_wizard_can_construct_and_switch_parameter_sections(tmp_path):
    # Import Qt inside the test to preserve isolated stdlib-only runner checks.
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.preparation import PreparationWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    class Stub:
        pass

    wizard = PreparationWindow(Stub(), Stub())
    try:
        assert wizard.tabs.count() == 4
        assert wizard.operation.count() == 4
        for index in range(wizard.operation.count()):
            wizard.operation.setCurrentIndex(index)
            assert wizard.operation.currentData() in {
                "clean", "pattern", "split", "spacy"
            }
        assert wizard.windowTitle() == "Prepare observations for GeCo"
        assert not wizard.advanced_runtime.isChecked()
        assert wizard.create_button.text() == "Create research project"
    finally:
        wizard.close()



def test_create_new_project_never_runs_uv_before_first_open(tmp_path, monkeypatch):
    from types import SimpleNamespace

    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.project import read_descriptor
    from geco_desktop.ui import preparation

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    def forbidden(*_args, **_kwargs):
        raise AssertionError("Creating a project must not invoke uv")

    class DirectPool:
        @staticmethod
        def globalInstance():
            return SimpleNamespace(start=lambda job: job.run())

    monkeypatch.setattr(preparation, "QThreadPool", DirectPool)
    monkeypatch.setattr(preparation, "resolve_project_files", forbidden)
    dialog = preparation.NewProjectDialog(object())
    dialog.project_name.setText("Instant study")
    dialog.destination.setText(str(tmp_path))
    try:
        dialog.create_project()
        root = tmp_path / "Instant study.gecod"
        assert root.is_dir()
        assert (root / "project.gecod").is_file()
        assert not (root / "uv.lock").exists()
        assert not (root / "pyproject.toml").exists()
        assert not (root / ".teal").exists()
        assert read_descriptor(root)[1].state == "preparing"
    finally:
        dialog.close()


def test_new_project_dialog_only_asks_for_name_location_and_profile():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.preparation import NewProjectDialog

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    window = NewProjectDialog(object())
    try:
        assert window.windowTitle() == "New GeCo project"
        assert window.project_name.text()
        assert window.destination.text()
        assert not window.profile.isChecked()
        assert not hasattr(window, "pdf_feature")
        assert not hasattr(window, "embeddings_feature")
        assert not hasattr(window, "spacy_feature")
        assert not hasattr(window, "tabs")
    finally:
        window.close()

def test_model_manager_lists_ready_profiles_without_importing_teal():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.model_manager import ModelManagerDialog

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    class StubManager:
        def list_profiles(self):
            return [
                {"state": "ready", "spec": {
                    "python": "3.11", "teal": "0.9.0", "geco": "0.8.15",
                    "locked_packages": [],
                }},
                {"state": "incomplete"},
            ]

    window = ModelManagerDialog(StubManager())
    try:
        assert window.environment.count() == 1
        assert window.table.columnCount() == 3
        assert window.add_button.text() == "Add model…"
    finally:
        window.close()


def test_preview_tabs_show_candidate_data_without_saving():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.preparation import PreparationWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    class Stub:
        pass

    window = PreparationWindow(Stub(), Stub())
    try:
        assert window.preview_tabs.count() == 2
        window._present_rows(["text"], [{"text": "original"}])
        window._present_table(window.after_table, ["text"], [{"text": "cleaned"}])
        assert window.before_table.item(0, 0).text() == "original"
        assert window.after_table.item(0, 0).text() == "cleaned"
    finally:
        window.close()


def test_open_missing_science_runtime_requires_explicit_consent(tmp_path, monkeypatch):
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.environments import EnvironmentError
    from geco_desktop.project import ProjectDescriptor, RuntimeSpec, write_descriptor
    from geco_desktop.ui.main_window import MainWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    root = tmp_path / "moved.gecod"
    root.mkdir()
    descriptor = ProjectDescriptor.new("Moved", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    write_descriptor(root, descriptor)
    window = MainWindow()
    installed = []
    prompts = []

    class MissingManager:
        def locate(self, runtime):
            raise EnvironmentError("Required scientific environment is not installed")

        def profile(self, runtime):
            from types import SimpleNamespace

            return SimpleNamespace(
                path=tmp_path / "shared-environments" / "missing",
                packages=("text-analysis-lab==0.9.0", "geometric-coder==0.8.15"),
            )

        def ensure(self, runtime):
            installed.append(runtime)
            return tmp_path / "python"

    window.environments = MissingManager()
    monkeypatch.setattr(window, "_remember_project", lambda path: None)

    def background(work, done):
        done(work())

    monkeypatch.setattr(window, "_background", background)
    monkeypatch.setattr(
        qtwidgets.QMessageBox,
        "question",
        lambda *args, **kwargs: (
            prompts.append(args[2]) or qtwidgets.QMessageBox.StandardButton.No
        ),
    )
    try:
        window.open_project_path(str(root))
        assert not installed
        assert len(prompts) == 1
        assert "text-analysis-lab==0.9.0" in prompts[0]
        assert "declined" in window.status.text()
        assert descriptor == __import__(
            "geco_desktop.project", fromlist=["read_descriptor"]
        ).read_descriptor(root)[1]
    finally:
        window.close()


def test_missing_science_runtime_install_reopens_project(tmp_path, monkeypatch):
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.project import ProjectDescriptor, RuntimeSpec, write_descriptor
    from geco_desktop.ui.main_window import MainWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    root = tmp_path / "moved.gecod"
    root.mkdir()
    descriptor = ProjectDescriptor.new("Moved", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    write_descriptor(root, descriptor)
    window = MainWindow()
    installed = []
    reopened = []

    class MissingManager:
        def profile(self, runtime):
            from types import SimpleNamespace

            return SimpleNamespace(
                path=tmp_path / "shared-environments" / "missing",
                packages=("text-analysis-lab==0.9.0", "geometric-coder==0.8.15"),
            )

        def ensure(self, runtime):
            installed.append(runtime)
            return tmp_path / "python"

    window.environments = MissingManager()
    monkeypatch.setattr(
        qtwidgets.QMessageBox, "question",
        lambda *args, **kwargs: qtwidgets.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(window, "_background", lambda work, done: done(work()))
    monkeypatch.setattr(window, "open_project_path", lambda path: reopened.append(path))
    try:
        window._offer_runtime_install(root, descriptor)
        assert installed == [descriptor.runtime]
        assert reopened == [str(root)]
    finally:
        window.close()


def test_incomplete_runtime_repair_requires_consent(tmp_path, monkeypatch):
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.project import ProjectDescriptor, RuntimeSpec
    from geco_desktop.ui.main_window import MainWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    window = MainWindow()
    descriptor = ProjectDescriptor.new("Repair", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    calls = []

    class Manager:
        def profile(self, runtime):
            from types import SimpleNamespace
            return SimpleNamespace(path=tmp_path / "incomplete")

        def repair(self, runtime):
            calls.append(runtime)
            return tmp_path / "python"

    window.environments = Manager()
    monkeypatch.setattr(window, "_background", lambda work, done: done(work()))
    monkeypatch.setattr(window, "open_project_path", lambda path: calls.append(path))
    monkeypatch.setattr(
        qtwidgets.QMessageBox, "question",
        lambda *args, **kwargs: qtwidgets.QMessageBox.StandardButton.No,
    )
    try:
        window._offer_runtime_repair(tmp_path, descriptor)
        assert calls == []
        monkeypatch.setattr(
            qtwidgets.QMessageBox, "question",
            lambda *args, **kwargs: qtwidgets.QMessageBox.StandardButton.Yes,
        )
        window._offer_runtime_repair(tmp_path, descriptor)
        assert calls == [descriptor.runtime, str(tmp_path)]
    finally:
        window.close()

def test_finalized_preparation_disables_writes_and_shows_open_workflow():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.project import ProjectDescriptor, RuntimeSpec
    from geco_desktop.ui.preparation import PreparationWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    class Stub:
        pass

    wizard = PreparationWindow(Stub(), Stub())
    try:
        from dataclasses import replace

        wizard.descriptor = replace(
            ProjectDescriptor.new("Study", RuntimeSpec("3.11", "0.9.0", "0.8.15")),
            state="finalized",
        )
        wizard._show_finalized()
        assert wizard.tabs.currentIndex() == 3
        assert not any(wizard.tabs.isTabEnabled(i) for i in (0, 1, 2))
        assert wizard.tabs.isTabEnabled(3)
        assert not wizard.resume_button.isEnabled()
        wizard.import_documents()
        wizard.apply_operation()
        wizard.finalize_project()
        assert wizard.tabs.currentIndex() == 3
    finally:
        wizard.close()


def test_capability_results_disable_unavailable_choices_without_removing_them():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.preparation import PreparationWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    class Stub:
        pass

    wizard = PreparationWindow(Stub(), Stub())
    try:
        supported = {
            str(wizard.operation.itemData(i)): {"available": True, "reason": ""}
            for i in range(wizard.operation.count())
        }
        supported["pattern"] = {"available": False, "reason": "Missing PatternExtractor"}
        supported["spacy"] = {
            "available": False, "reason": "spaCy model not available",
        }
        wizard._set_capabilities({
            "imports": {"pdf": {"available": False, "reason": "Missing pdfplumber"}},
            "operations": supported,
        })
        lookup = {
            wizard.operation.itemData(i): wizard.operation.model().item(i)
            for i in range(wizard.operation.count())
        }
        assert not lookup["pattern"].isEnabled()
        assert lookup["pattern"].toolTip() == "Missing PatternExtractor"
        assert not lookup["spacy"].isEnabled()
        assert lookup["clean"].isEnabled()
        pdf = next(
            i for i in range(wizard.source_kind.count())
            if wizard.source_kind.itemData(i) == "pdf"
        )
        assert not wizard.source_kind.model().item(pdf).isEnabled()
        assert wizard.source_kind.model().item(0).isEnabled()
    finally:
        wizard.close()


def test_changing_model_invalidates_capability_and_stale_probe_result():
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.preparation import PreparationWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None

    class Stub:
        pass

    wizard = PreparationWindow(Stub(), Stub())
    try:
        supported = {
            str(wizard.operation.itemData(i)): {"available": True, "reason": ""}
            for i in range(wizard.operation.count())
        }
        response = {"imports": {"pdf": {"available": True}}, "operations": supported}
        original = wizard._model_settings()
        wizard._set_capabilities(response, checked=original)
        spacy = next(
            i for i in range(wizard.operation.count())
            if wizard.operation.itemData(i) == "spacy"
        )
        assert wizard.operation.model().item(spacy).isEnabled()
        wizard.inputs["spacy_model"].setText("new_spacy_model")
        assert not wizard.operation.model().item(spacy).isEnabled()
        assert not wizard._capability_allowed(kind="spacy", operation=True)
        wizard._set_capabilities(response, checked=original)
        assert not wizard.operation.model().item(spacy).isEnabled()
        wizard._set_capabilities(response, checked=wizard._model_settings())
        assert wizard.operation.model().item(spacy).isEnabled()
    finally:
        wizard.close()


def test_first_open_resolves_new_project_lock_once_and_preserves_it(
    tmp_path, monkeypatch,
):
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    import geco_desktop.environments as env_module
    import geco_desktop.portable_project as portable
    from geco_desktop.portable_project import LockedProjectFiles
    from geco_desktop.project import (
        ProjectDescriptor,
        RuntimeSpec,
        read_descriptor,
        write_descriptor,
    )
    from geco_desktop.ui.main_window import MainWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    root = tmp_path / "Fresh.gecod"
    root.mkdir()
    spec = RuntimeSpec(
        "3.11", "0.11.1", "0.10.0",
        locked_packages=(
            "text-analysis-lab[all]==0.11.1",
            "geometric-coder==0.10.0",
        ),
    )
    write_descriptor(root, ProjectDescriptor.new("Fresh", spec))
    calls = []

    def lock(_manager, _name, _spec):
        calls.append("lock")
        return LockedProjectFiles(
            "[project]\\nname = 'study'\\n",
            "version = 1\\n",
            "science-dependency==1\\n",
        )

    class StubEnvironment:
        def locate(self, runtime):
            assert runtime.resolved_requirements is not None
            return tmp_path / "python"

    def science(_python, _runner, action, **_kwargs):
        if action == "create_teal":
            (root / ".teal").mkdir()
            return {}
        if action in {"catalog", "project_info"}:
            return {"artifacts": [], "workspaces": []}
        raise AssertionError(action)

    monkeypatch.setattr(portable, "resolve_project_files", lock)
    monkeypatch.setattr(env_module, "run_command", science)
    window = MainWindow()
    window.environments = StubEnvironment()
    monkeypatch.setattr(window, "_background", lambda work, done: done(work()))
    try:
        window.open_project_path(str(root))
        descriptor = read_descriptor(root)[1]
        assert descriptor.project_lock_sha256 is not None
        assert descriptor.runtime.resolved_requirements == "science-dependency==1\\n"
        assert (root / ".teal").is_dir()
        assert calls == ["lock"]
        window._dashboard.close()
        window.open_project_path(str(root))
        assert calls == ["lock"]
        window._dashboard.close()
    finally:
        window.close()


def test_open_python_created_teal_project_selects_workspace_without_descriptor(
    tmp_path, monkeypatch,
):
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.main_window import MainWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    root = tmp_path / "ordinary-teal"
    (root / ".teal").mkdir(parents=True)

    class Manager:
        def list_profiles(self):
            return [{"state": "ready", "spec": {
                "python": "3.11", "teal": "0.11.0", "geco": "0.10.0",
                "locked_packages": [],
            }}]

        def locate(self, runtime):
            return tmp_path / "python"

    def run_science(_python, _runner, action, **_kwargs):
        if action == "project_info":
            return {"workspaces": [{"name": "first"}, {"name": "second"}]}
        if action == "catalog":
            return {"artifacts": [], "workspaces": [
                {"name": "first"}, {"name": "second"}
            ]}
        raise AssertionError(action)

    monkeypatch.setattr("geco_desktop.environments.run_command", run_science)
    monkeypatch.setattr(
        qtwidgets.QInputDialog, "getItem",
        lambda *args, **kwargs: ("second", True),
    )
    window = MainWindow()
    window.environments = Manager()
    monkeypatch.setattr(window, "_background", lambda work, done: done(work()))
    try:
        window.open_project_path(str(root))
        dashboard = window._dashboard
        assert dashboard.external
        assert dashboard.workspace_name == "second"
        assert dashboard.launch_button.isEnabled()
        assert not dashboard.preparation_button.isEnabled()
        assert not (root / "project.gecod").exists()
        assert root in [root.__class__(name) for name in window._recent_paths()]
        dashboard.close()
    finally:
        window.close()


def test_python_created_teal_without_geco_offers_workspace_setup(tmp_path, monkeypatch):
    qtwidgets = pytest.importorskip("PySide6.QtWidgets")
    from geco_desktop.ui.main_window import MainWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    root = tmp_path / "teal-without-geco"
    (root / ".teal").mkdir(parents=True)

    class Manager:
        def list_profiles(self):
            return [{"state": "ready", "spec": {
                "python": "3.11", "teal": "0.11.1", "geco": "0.10.0",
                "locked_packages": [],
            }}]

        def locate(self, runtime):
            return tmp_path / "python"

    def run_science(_python, _runner, action, **_kwargs):
        assert action in {"project_info", "catalog"}
        return {"workspaces": [], "artifacts": []}

    monkeypatch.setattr("geco_desktop.environments.run_command", run_science)
    window = MainWindow()
    window.environments = Manager()
    monkeypatch.setattr(window, "_background", lambda work, done: done(work()))
    try:
        window.open_project_path(str(root))
        dashboard = window._dashboard
        assert dashboard.external
        assert dashboard.preparation_button.isEnabled()
        assert not dashboard.launch_button.isEnabled()
        assert not (root / "project.gecod").exists()
        dashboard.close()
    finally:
        window.close()
