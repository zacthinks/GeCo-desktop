"""Read-only inventory of separately installed scientific runtime profiles."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout,
)

from geco_desktop.environments import EnvironmentManager


class EnvironmentManagerDialog(QDialog):
    def __init__(self, manager: EnvironmentManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle("Scientific Environments")
        self.resize(740, 420)
        layout = QVBoxLayout(self)
        description = QLabel(
            "Scientific environments are stored outside your projects. "
            "Each project keeps its chosen versions, and opening it never updates them automatically."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Status", "Python", "TeAL", "GeCo", "Installed location"]
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
            for column, key in enumerate(("state", "python", "teal", "geco", "path")):
                self.table.setItem(
                    index, column, QTableWidgetItem(str(record.get(key, "—")))
                )
        self.table.resizeColumnsToContents()
