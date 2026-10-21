import subprocess
import sys
import types

import pytest

from geco_desktop.backend import runner
from geco_desktop.environments import installed_runner_path
from geco_desktop.protocol import ProtocolError, decode, encode, request


def test_protocol_validates_version():
    decoded = decode(encode(request("ping")))
    assert decoded["action"] == "ping"
    with pytest.raises(ProtocolError):
        decode('{"version":2,"ok":true}')
    with pytest.raises(ProtocolError):
        decode("not json")


def test_runner_handles_invalid_action_without_killing_stream():
    result = subprocess.run(
        [sys.executable, str(installed_runner_path())],
        input=encode(request("not-supported")) + encode(request("ping")),
        text=True,
        capture_output=True,
        check=True,
    )
    outputs = [decode(line) for line in result.stdout.splitlines()]
    assert [x["ok"] for x in outputs] == [False, True]
    assert outputs[0]["error"]["type"] == "ValueError"


def test_project_commands_close_teal_even_after_errors(monkeypatch, tmp_path):
    projects = []

    class FakeManager:
        def list(self):
            return [{"name": "desktop"}]

    class FakeProject:
        def __init__(self, path):
            self.path = path
            self.geco = FakeManager()
            self.closed = False
            projects.append(self)

        @classmethod
        def open(cls, path):
            return cls(path)

        @classmethod
        def create(cls, path, name, delete_existing=False):
            assert delete_existing is False
            return cls(path)

        def close(self):
            self.closed = True

    monkeypatch.setitem(sys.modules, "text_analysis_lab", types.SimpleNamespace(Project=FakeProject))
    result = runner.dispatch(request("project_info", path=str(tmp_path)))
    assert result["workspaces"] == [{"name": "desktop"}]
    assert projects[-1].closed
    result = runner.dispatch(request("create_teal", path=str(tmp_path), name="Test"))
    assert result["project_path"] == str(tmp_path)
    assert projects[-1].closed
    (tmp_path / ".teal").mkdir()
    with pytest.raises(FileExistsError):
        runner.dispatch(request("create_teal", path=str(tmp_path), name="Test"))

def test_serve_shutdown_marker_closes_project(tmp_path):
    """Exercise the real detached-runner cooperative shutdown seam."""
    import os
    import time
    from pathlib import Path

    from geco_desktop.environments import installed_runner_path

    fake_package = tmp_path / "text_analysis_lab.py"
    closed = tmp_path / "closed.txt"
    running = tmp_path / "running.txt"
    fake_package.write_text(
        "import time\n"
        "from pathlib import Path\n"
        "class Linked:\n"
        "    def launch(self, **kwargs):\n"
        f"        Path({str(running)!r}).write_text('ready')\n"
        "        while True: time.sleep(0.1)\n"
        "class Manager:\n"
        "    def open(self, name): return Linked()\n"
        "class Project:\n"
        "    @classmethod\n"
        "    def open(cls, path): return cls()\n"
        "    def __init__(self): self.geco = Manager()\n"
        f"    def close(self): Path({str(closed)!r}).write_text('closed')\n"
    )
    marker = tmp_path / "stop.marker"
    env = {**os.environ, "PYTHONPATH": str(tmp_path)}
    process = subprocess.Popen(
        [sys.executable, str(installed_runner_path()), "--serve",
         "--project", str(tmp_path), "--port", "8050", "--shutdown-file", str(marker)],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 6
        while not running.exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(0.05)
        assert running.exists(), "mock GeCo server never started"
        marker.touch()
        assert process.wait(timeout=6) == 0
        assert closed.read_text() == "closed"
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=3)
