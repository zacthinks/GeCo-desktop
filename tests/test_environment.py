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
