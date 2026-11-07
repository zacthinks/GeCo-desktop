"""Read-only inventory of separately installed scientific runtime profiles."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from geco_desktop.environments import EnvironmentManager


class EnvironmentManagerDialog(QDialog):
    def __init__(self, manager: EnvironmentManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Software Profiles")
        self.resize(740, 420)
        layout = QVBoxLayout(self)
        description = QLabel(
            "Software profiles provide the tools your project needs. "
            "This development build shows locally installed runtimes; "
            "approved profile selection is not available until qualification is complete."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Software"]
        )
        layout.addWidget(self.table)
        buttons = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(refresh)
        buttons.addStretch()
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        profiles = self.manager.list_profiles()
        self.table.setRowCount(len(profiles))
        for index, record in enumerate(profiles):
            self.table.setItem(index, 0, QTableWidgetItem(str(record.get("state", "unknown"))))
            software = f"TeAL {record.get('teal', '?')} · GeCo {record.get('geco', '?')}"
            self.table.setItem(index, 1, QTableWidgetItem(software))
        self.table.resizeColumnsToContents()
