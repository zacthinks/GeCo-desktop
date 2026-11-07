"""Installed native GUI entry point; scientific libraries are not imported here."""

from __future__ import annotations

import sys
from pathlib import Path


def _set_app_icon(app) -> None:
    from PySide6.QtGui import QIcon

    if getattr(sys, "frozen", False):
        root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        icon = root / "icons" / "geco-app.png"
    else:
        icon = Path(__file__).resolve().parents[2] / "packaging" / "assets" / "geco-mark.svg"
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))


def main() -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print("GeCo Desktop requires its GUI dependencies. Install with [gui].", file=sys.stderr)
        return 2

    from .ui.main_window import MainWindow

    # Installer qualification checks the real frozen GUI and its app-owned
    # runtime resources, without creating projects or downloading science.
    if len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        from pathlib import Path

        from .environments import EnvironmentManager, installed_runner_path
        from .science_releases import RELEASES

        app = QApplication(sys.argv[:1])
        _set_app_icon(app)
        if app.windowIcon().isNull():
            raise RuntimeError("Missing GeCo app window icon in native distribution")
        window = MainWindow()
        runner = installed_runner_path()
        if not runner.with_name("workflow.py").is_file():
            raise RuntimeError("Missing app-owned scientific workflow resource")
        manager = EnvironmentManager()
        if not manager.uv or not Path(manager.uv).is_file():
            raise RuntimeError("Missing bundled uv provisioner")
        wheels = manager.wheelhouse
        if wheels is None or not all(
            any(file.name.startswith(prefix) for file in wheels.glob("*.whl"))
            for prefix in (release.wheel.rsplit("-", 3)[0] + "-" for release in RELEASES)
        ):
            raise RuntimeError("Missing verified bundled scientific packages")
        QTimer.singleShot(300, app.quit)
        app.exec()
        window.close()
        Path(sys.argv[2]).write_text("GeCo Desktop native self-check passed\\n", encoding="utf-8")
        return 0

    app = QApplication(sys.argv)
    _set_app_icon(app)
    window = MainWindow()
    window.show()
    # File associations send a project descriptor as the first launch argument.
    if len(sys.argv) > 1:
        project_path = sys.argv[1]
        QTimer.singleShot(0, lambda: window.open_project_path(project_path))
    return int(app.exec())
