"""Installed native GUI entry point; scientific libraries are not imported here."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("GeCo Desktop requires its GUI dependencies. Install with [gui].", file=sys.stderr)
        return 2

    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    # File associations send a project descriptor as the first launch argument.
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
        QTimer.singleShot(0, lambda: window.open_project_path(project_path))
    return int(app.exec())
