"""GeCo 0.9's closeable listener must outlive launch() and its TeAL project."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from types import ModuleType, SimpleNamespace

from geco_desktop.backend import runner


def test_closeable_server_waits_until_shutdown_then_closes_teal(tmp_path, monkeypatch):
    events = []
    launched = threading.Event()
    stopped = threading.Event()
    project_path = tmp_path / "research.gecod"
    project_path.mkdir()
    shutdown = tmp_path / "stop-file"

    class Server:
        def wait(self, timeout=None):
            launched.set()
            return stopped.wait(timeout)

        def close(self):
            events.append("server.close")

    class Project:
        @staticmethod
        def open(path):
            assert path == str(project_path)
            return SimpleNamespace(
                geco=SimpleNamespace(
                    open=lambda workspace: SimpleNamespace(
                        launch=lambda **kwargs: Server()
                    )
                ),
                close=lambda: events.append("project.close"),
            )

    fake = ModuleType("text_analysis_lab")
    fake.Project = Project
    monkeypatch.setitem(sys.modules, "text_analysis_lab", fake)

    def run():
        events.append(runner.serve(str(project_path), "desktop", 40500, str(shutdown)))

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert launched.wait(5)
        assert not events, "GeCo server returned before shutdown"
        shutdown.touch()
        thread.join(5)
        assert not thread.is_alive()
        assert events == ["server.close", "project.close", 0]
    finally:
        stopped.set()
        thread.join(5)
