"""App-local GeCo browser session registry and independent process supervision."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from dataclasses import asdict, dataclass
from pathlib import Path

import psutil
from filelock import FileLock

from .environments import application_data, installed_runner_path
from .project import ProjectDescriptor


class SessionError(RuntimeError):
    """A GeCo session could not be started, recovered, or stopped safely."""


@dataclass
class ActiveSession:
    key: str
    project_id: str
    project_path: str
    project_name: str
    pid: int
    process_created: float
    port: int
    runner_path: str
    shutdown_file: str = ""
    status: str = "running"

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"


def _identity(project_root: Path, project_id: str) -> str:
    return hashlib.sha256(f"{project_root.resolve()}:{project_id}".encode()).hexdigest()[:24]


def _available_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _alive(session: ActiveSession) -> bool:
    """Validate our exact child process, independently of HTTP responsiveness."""
    try:
        process = psutil.Process(session.pid)
        if abs(process.create_time() - session.process_created) > 1.0:
            return False
        if not process.is_running() or process.status() == psutil.STATUS_ZOMBIE:
            return False
        cmdline = process.cmdline()
        return session.runner_path in cmdline and "--serve" in cmdline
    except (psutil.Error, OSError, ValueError):
        return False


def _ready(session: ActiveSession) -> bool:
    if not _alive(session):
        return False
    try:
        with urllib.request.urlopen(session.url, timeout=0.35) as response:
            return 200 <= response.status < 500
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return False


def _status(session: ActiveSession) -> str:
    if not _alive(session):
        return "stopped"
    return "running" if _ready(session) else "unresponsive"


class SessionManager:
    """One browser server per project; multiple different projects may run."""

    def __init__(self, base: Path | None = None) -> None:
        self.base = Path(base) if base is not None else application_data()
        self.registry = self.base / "sessions.json"
        self.lock = self.base / "sessions.lock"

    def _read(self) -> dict[str, ActiveSession]:
        if not self.registry.exists():
            return {}
        try:
            values = json.loads(self.registry.read_text(encoding="utf-8"))
            return {k: ActiveSession(**v) for k, v in values.items()}
        except (OSError, ValueError, TypeError):
            raise SessionError("Session registry is corrupt; inspect it before proceeding") from None

    def _write(self, sessions: dict[str, ActiveSession]) -> None:
        # Atomic JSON with no dependency on TeAL project files.
        import tempfile

        self.base.mkdir(parents=True, exist_ok=True)
        fd, staged = tempfile.mkstemp(prefix="sessions-", suffix=".tmp", dir=self.base)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({key: asdict(item) for key, item in sessions.items()}, stream, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(staged, self.registry)
        finally:
            if os.path.exists(staged):
                os.unlink(staged)

    def list(self) -> list[ActiveSession]:
        self.base.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.lock)):
            entries = self._read()
            clean = {key: item for key, item in entries.items() if _ready(item)}
            if len(clean) != len(entries):
                self._write(clean)
            return list(clean.values())

    def start(
        self, root: Path, descriptor: ProjectDescriptor, python: Path, *,
        runner: Path | None = None, wait_seconds: float = 20.0,
    ) -> ActiveSession:
        self.base.mkdir(parents=True, exist_ok=True)
        root = root.resolve()
        runner = (runner or installed_runner_path()).resolve()
        key = _identity(root, descriptor.project_id)
        with FileLock(str(self.lock)):
            sessions = self._read()
            existing = sessions.get(key)
            if existing and _alive(existing):
                return existing
            sessions.pop(key, None)
            port = _available_port()
            shutdown_file = self.base / ("stop-" + uuid.uuid4().hex)
            log_dir = self.base / "logs"
            log_dir.mkdir(exist_ok=True)
            flags = 0
            if os.name == "nt":
                flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            command = [
                str(python), str(runner), "--serve", "--project", str(root),
                "--workspace", descriptor.workspace_name, "--port", str(port),
                "--shutdown-file", str(shutdown_file),
            ]
            with (log_dir / f"{key}.log").open("ab") as output:
                process = subprocess.Popen(
                    command,
                    cwd=str(root), stdin=subprocess.DEVNULL,
                    stdout=output, stderr=subprocess.STDOUT,
                    start_new_session=(os.name != "nt"), creationflags=flags,
                )
            item = ActiveSession(
                key=key, project_id=descriptor.project_id, project_path=str(root),
                project_name=descriptor.name, pid=process.pid,
                process_created=psutil.Process(process.pid).create_time(),
                port=port, runner_path=str(runner), shutdown_file=str(shutdown_file),
            )
            sessions[key] = item
            self._write(sessions)
            # Hold the cross-process launch lock until ready. Otherwise a second
            # Desktop instance might see a not-yet-ready process as stale and
            # accidentally start a second writer against the same project.
            limit = time.monotonic() + wait_seconds
            while time.monotonic() < limit:
                if _ready(item):
                    return item
                if process.poll() is not None:
                    break
                time.sleep(0.15)
            if process.poll() is None:
                shutdown_file.touch()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            shutdown_file.unlink(missing_ok=True)
            sessions.pop(key, None)
            self._write(sessions)
            raise SessionError("GeCo server did not become ready; see the application log")

    def stop(self, key: str) -> None:
        """Ask the owned runner to close TeAL cleanly before forced fallback."""
        self.base.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.lock)):
            sessions = self._read()
            entry = sessions.get(key)
            if not entry:
                return
            if _alive(entry):
                proc = psutil.Process(entry.pid)
                if entry.shutdown_file:
                    Path(entry.shutdown_file).touch()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        pass
                if _alive(entry):
                    proc.terminate()
                    try:
                        proc.wait(timeout=4)
                    except psutil.TimeoutExpired:
                        proc.kill()
            if entry.shutdown_file:
                Path(entry.shutdown_file).unlink(missing_ok=True)
            del sessions[key]
            self._write(sessions)

    @staticmethod
    def open_browser(session: ActiveSession) -> None:
        webbrowser.open(session.url)
