"""Offscreen construction contract for the real preparation workbench."""
import pytest

qtwidgets = pytest.importorskip("PySide6.QtWidgets")


def test_native_wizard_can_construct_and_switch_parameter_sections(tmp_path):
    from geco_desktop.ui.preparation import PreparationWindow

    app = qtwidgets.QApplication.instance() or qtwidgets.QApplication([])
    assert app is not None
    class Stub:
        pass

    wizard = PreparationWindow(Stub(), Stub())
    try:
        assert wizard.tabs.count() == 4
        assert wizard.operation.count() == 7
        for index in range(wizard.operation.count()):
            wizard.operation.setCurrentIndex(index)
            assert wizard.operation.currentData() in {
                "clean", "pattern", "split", "count", "tfidf", "svd", "umap"
            }
        assert wizard.windowTitle() == "Prepare a GeCo project"
    finally:
        wizard.close()
