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
        assert wizard.operation.count() == 9
        for index in range(wizard.operation.count()):
            wizard.operation.setCurrentIndex(index)
            assert wizard.operation.currentData() in {
                "clean", "pattern", "split", "count", "tfidf", "svd", "umap",
                "sentence_embeddings", "spacy"
            }
        assert wizard.windowTitle() == "Prepare a GeCo project"
    finally:
        wizard.close()


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
        assert window.profile.count() == 1
        assert window.table.columnCount() == 3
        assert window.download_button.text() == "Download model"
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
