"""Native CI gate: default project provisions from the application's verified wheels."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from geco_desktop.environments import EnvironmentManager, installed_runner_path, run_command
from geco_desktop.project import RuntimeSpec
from geco_desktop.science_releases import DEFAULT_PYTHON, GECO, TEAL


def qualify(wheels: Path, uv: str) -> None:
    with tempfile.TemporaryDirectory(prefix="gecod-native-science-") as folder:
        manager = EnvironmentManager(
            base=Path(folder) / "shared", uv=uv, wheelhouse=wheels.resolve()
        )
        spec = RuntimeSpec(DEFAULT_PYTHON, TEAL.version, GECO.version)
        locked = manager.resolve(spec)
        assert locked.resolved_requirements
        python = manager.ensure(locked)
        assert manager.locate(locked) == python
        assert manager.ensure(locked) == python
        result = run_command(python, installed_runner_path(), "capabilities", timeout=120)
        for name in ("clean", "count", "tfidf", "svd", "umap"):
            assert result["operations"][name]["available"], (name, result)
        version = subprocess.check_output(
            [str(python), "-c",
             "from importlib.metadata import version;"
             "print(version('geometric-coder'));"
             "print(version('text-analysis-lab'))"],
            text=True,
            timeout=60,
        ).splitlines()
        assert version == [GECO.version, TEAL.version], version
        print("PASS: native default scientific installation, version pins and reuse")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheels", type=Path, required=True)
    parser.add_argument("--uv", default="uv")
    a = parser.parse_args()
    qualify(a.wheels, a.uv)
