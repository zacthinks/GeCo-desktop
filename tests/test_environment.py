import json
import platform
import subprocess
import sys

import pytest

from geco_desktop.environments import (
    EnvironmentError,
    EnvironmentManager,
    installed_runner_path,
    run_command,
    runtime_with_features,
)
from geco_desktop.project import RuntimeSpec


def test_profile_reuse_and_exact_manifest(tmp_path):
    manager = EnvironmentManager(base=tmp_path, uv="uv")
    spec = RuntimeSpec("3.11", "0.9.0", "0.8.15")
    profile = manager.profile(spec)
    assert profile == manager.profile(spec)
    assert profile.path != manager.profile(RuntimeSpec("3.11", "1.0.0", "0.8.15")).path
    assert profile.path.is_relative_to(tmp_path)
    with pytest.raises(EnvironmentError, match="not installed"):
        manager.locate(spec)
    profile.python.parent.mkdir(parents=True)
    profile.python.touch()
    (profile.path / "profile.json").write_text(
        json.dumps({"fingerprint": profile.fingerprint, "spec": spec.to_dict()})
    )
    assert manager.locate(spec) == profile.python
    (profile.path / "profile.json").write_text("{}")
    with pytest.raises(EnvironmentError, match="does not match"):
        manager.locate(spec)


def test_current_app_owned_runner_ping_uses_selected_interpreter():
    runner = installed_runner_path()
    assert "geco_desktop" in str(runner)
    response = run_command(sys.executable, runner, "ping")
    assert response["python"] == platform.python_version()
    assert response["runner_protocol"] == 1


def test_no_scientific_or_qt_imports_for_ping():
    runner = installed_runner_path()
    result = subprocess.run(
        [sys.executable, "-I", str(runner)],
        input='{"version":1,"action":"ping","arguments":{}}\n',
        text=True,
        capture_output=True,
        check=True,
    )
    assert json.loads(result.stdout)["ok"] is True
    assert "PySide6" not in sys.modules


def test_optional_teal_features_are_part_of_project_runtime_identity(tmp_path):
    basic = runtime_with_features("3.11", "0.9.0", "0.8.15")
    richer = runtime_with_features(
        "3.11", "0.9.0", "0.8.15",
        pdf=True, embeddings=True, spacy=True,
    )
    assert basic.locked_packages == (
        "text-analysis-lab==0.9.0", "geometric-coder==0.8.15"
    )
    assert richer.locked_packages == (
        "text-analysis-lab[pdf,spacy,transformers]==0.9.0",
        "geometric-coder==0.8.15",
    )
    manager = EnvironmentManager(base=tmp_path)
    assert manager.profile(richer).fingerprint != manager.profile(basic).fingerprint
    assert manager.profile(richer).packages == richer.locked_packages


def test_repair_preserves_old_profile_when_staging_fails(tmp_path, monkeypatch):
    manager = EnvironmentManager(base=tmp_path, uv="uv")
    spec = RuntimeSpec("3.11", "0.9.0", "0.8.15")
    profile = manager.profile(spec)
    profile.path.mkdir(parents=True)
    marker = profile.path / "old-content"
    marker.write_text("preserved")

    def fail(*args):
        raise EnvironmentError("install failed")

    monkeypatch.setattr(manager, "_uv", fail)
    with pytest.raises(EnvironmentError, match="install failed"):
        manager.repair(spec)
    assert marker.read_text() == "preserved"
    assert not list(profile.path.parent.glob("gecod-env-*"))


def test_repair_rejects_ready_profile(tmp_path, monkeypatch):
    manager = EnvironmentManager(base=tmp_path, uv="uv")
    spec = RuntimeSpec("3.11", "0.9.0", "0.8.15")
    profile = manager.profile(spec)
    profile.python.parent.mkdir(parents=True)
    profile.python.touch()
    (profile.path / "profile.json").write_text(
        json.dumps({"fingerprint": profile.fingerprint, "spec": spec.to_dict()})
    )
    monkeypatch.setattr(manager, "_uv", lambda *args: pytest.fail("unexpected install"))
    with pytest.raises(EnvironmentError, match="already ready"):
        manager.repair(spec)


def test_repair_promotes_staged_profile_and_keeps_manifest(tmp_path, monkeypatch):
    manager = EnvironmentManager(base=tmp_path, uv="uv")
    spec = RuntimeSpec("3.11", "0.9.0", "0.8.15")
    profile = manager.profile(spec)
    profile.path.mkdir(parents=True)
    (profile.path / "old-content").write_text("damaged")

    def fake_uv(*args):
        if args[0] == "venv":
            env = __import__("pathlib").Path(args[-1])
            interpreter = (
                env / "Scripts" / "python.exe"
                if __import__("os").name == "nt" else env / "bin" / "python"
            )
            interpreter.parent.mkdir(parents=True, exist_ok=True)
            interpreter.touch()

    monkeypatch.setattr(manager, "_uv", fake_uv)
    assert manager.repair(spec) == profile.python
    assert not (profile.path / "old-content").exists()
    assert manager.locate(spec) == profile.python


def test_portable_resolution_is_persisted_and_reused(tmp_path, monkeypatch):
    manager = EnvironmentManager(base=tmp_path, uv="uv")
    spec = runtime_with_features("3.11", "0.9.0", "0.8.15", pdf=True)
    commands = []

    def fake_uv(*args):
        commands.append(args)
        if args[:2] == ("pip", "compile"):
            output = __import__("pathlib").Path(args[args.index("--output-file") + 1])
            output.write_text("geometric-coder==0.8.15\ntext-analysis-lab==0.9.0\n")

    monkeypatch.setattr(manager, "_uv", fake_uv)
    locked = manager.resolve(spec)
    assert "geometric-coder==0.8.15" in locked.resolved_requirements
    assert locked.to_dict()["resolved_requirements"] == locked.resolved_requirements
    assert RuntimeSpec.from_dict(locked.to_dict()) == locked
    assert manager.resolve(locked) == locked
    assert len(commands) == 1
    assert "--universal" in commands[0]
    assert manager.profile(locked).fingerprint != manager.profile(spec).fingerprint


def test_staged_install_uses_portable_lock_without_modifying_it(tmp_path, monkeypatch):
    manager = EnvironmentManager(base=tmp_path, uv="uv")
    spec = RuntimeSpec(
        "3.11", "0.9.0", "0.8.15",
        resolved_requirements="geometric-coder==0.8.15\ntext-analysis-lab==0.9.0\n",
    )
    calls = []

    def fake_uv(*args):
        calls.append(args)
        if args[:1] == ("venv",):
            from pathlib import Path

            from geco_desktop.environments import interpreter_path

            target = Path(args[-1])
            interpreter = interpreter_path(target)
            interpreter.parent.mkdir(parents=True, exist_ok=True)
            interpreter.touch()
        elif args[:2] == ("pip", "install"):
            lock = __import__("pathlib").Path(args[args.index("--requirement") + 1])
            assert lock.read_text() == spec.resolved_requirements

    monkeypatch.setattr(manager, "_uv", fake_uv)
    installed = manager.ensure(spec)
    assert installed == manager.profile(spec).python
    assert "--requirement" in calls[-1]
    assert manager.locate(spec) == installed
    assert not list(manager.profile(spec).path.parent.glob("*-requirements.txt"))
