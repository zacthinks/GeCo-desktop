"""Shared immutable scientific Python environments, never inside .gecod projects."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock
from platformdirs import user_data_path

from .project import RuntimeSpec


class EnvironmentError(RuntimeError):
    """A compatible scientific runtime is missing or failed to install."""


def application_data() -> Path:
    return Path(user_data_path("GeCo Desktop", appauthor=False))


def interpreter_path(environment: Path) -> Path:
    if os.name == "nt":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


@dataclass(frozen=True)
class RuntimeProfile:
    spec: RuntimeSpec
    base: Path

    @property
    def fingerprint(self) -> str:
        source = {
            **self.spec.to_dict(),
            "system": platform.system(),
            "machine": platform.machine(),
        }
        return hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest()[:20]

    @property
    def path(self) -> Path:
        return self.base / "environments" / self.fingerprint

    @property
    def python(self) -> Path:
        return interpreter_path(self.path)

    @property
    def packages(self) -> tuple[str, ...]:
        if self.spec.locked_packages:
            return self.spec.locked_packages
        return (
            f"text-analysis-lab=={self.spec.teal}",
            f"geometric-coder=={self.spec.geco}",
        )


class EnvironmentManager:
    def __init__(self, base: Path | None = None, uv: str | None = None) -> None:
        self.base = Path(base) if base is not None else application_data()
        self.uv = uv or os.environ.get("GECO_DESKTOP_UV") or shutil.which("uv")

    def profile(self, spec: RuntimeSpec) -> RuntimeProfile:
        return RuntimeProfile(spec, self.base)

    def locate(self, spec: RuntimeSpec) -> Path:
        profile = self.profile(spec)
        if not profile.python.is_file() or not (profile.path / "profile.json").is_file():
            raise EnvironmentError("Required scientific environment is not installed. Install it first.")
        with (profile.path / "profile.json").open(encoding="utf-8") as stream:
            stored = json.load(stream)
        if stored != {"fingerprint": profile.fingerprint, "spec": spec.to_dict()}:
            raise EnvironmentError("Scientific environment manifest does not match the project")
        return profile.python

    def ensure(self, spec: RuntimeSpec) -> Path:
        """Explicit opt-in provisioning; never silently modify an existing profile."""
        profile = self.profile(spec)
        self.base.mkdir(parents=True, exist_ok=True)
        with FileLock(str(self.base / "install.lock")):
            try:
                return self.locate(spec)
            except EnvironmentError:
                if profile.path.exists():
                    raise EnvironmentError(
                        "Scientific environment is incomplete; repair is needed, not an in-place upgrade"
                    ) from None
            if not self.uv:
                raise EnvironmentError("uv is needed to install a missing scientific environment")
            env_dir = profile.path.parent
            env_dir.mkdir(parents=True, exist_ok=True)
            staged = Path(tempfile.mkdtemp(prefix="gecod-env-", dir=env_dir))
            try:
                self._uv("venv", "--python", spec.python, str(staged))
                self._uv("pip", "install", "--python", str(interpreter_path(staged)), *profile.packages)
                manifest = {"fingerprint": profile.fingerprint, "spec": spec.to_dict()}
                (staged / "profile.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
                # Atomically publish only after the complete environment exists.
                staged.rename(profile.path)
            finally:
                if staged.exists():
                    shutil.rmtree(staged)
        return self.locate(spec)

    def _uv(self, *args: str) -> None:
        result = subprocess.run(
            [str(self.uv), *args], capture_output=True, text=True, check=False
        )
        if result.returncode:
            raise EnvironmentError(f"uv installation failed: {result.stderr.strip()[-2000:]}")


def run_command(python: Path, runner: Path, action: str, **kwargs: object) -> dict:
    """Invoke an app-owned runner with a scientific environment interpreter."""
    from .protocol import decode, encode, request

    result = subprocess.run(
        [str(python), str(runner)],
        input=encode(request(action, **kwargs)),
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    if result.returncode or len(lines) != 1:
        raise EnvironmentError(f"Runner failed: {result.stderr.strip()[-1000:]}")
    message = decode(lines[0])
    if not message.get("ok"):
        error = message.get("error", {})
        raise EnvironmentError(str(error.get("message", "Runner failed")))
    return message["result"]


def installed_runner_path() -> Path:
    """Resolve the current runner distributed alongside the installed GUI.

    A frozen PyInstaller bundle must include backend/runner.py as a data file.
    """
    if getattr(sys, "frozen", False):
        resource_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        result = resource_root / "backend" / "runner.py"
    else:
        result = Path(__file__).resolve().parent / "backend" / "runner.py"
    if not result.is_file():
        raise EnvironmentError(f"App-owned runner asset is missing: {result}")
    return result
