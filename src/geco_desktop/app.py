"""Installed native GUI entry point; scientific libraries are not imported here."""

from __future__ import annotations

import sys


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("GeCo Desktop requires its GUI dependencies. Install with [gui].", file=sys.stderr)
        return 2

    from .ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return int(app.exec())
