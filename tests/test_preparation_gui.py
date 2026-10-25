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
