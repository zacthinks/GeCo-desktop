"""Explicit cross-platform qualification for the candidate full TeAL profile.

Runs only in the optional heavyweight profile-qualification workflow.
It exercises a real, isolated locked environment, document preparation,
TeAL-linked GeCo creation and the supervised browser lifecycle.
"""
from __future__ import annotations

import csv
import json
import os
import platform
import shutil
import tempfile
from dataclasses import replace
from pathlib import Path

from geco_desktop.environments import EnvironmentManager, installed_runner_path, run_command
from geco_desktop.portable_project import resolve_project_files
from geco_desktop.project import ProjectDescriptor, RuntimeSpec, write_descriptor
from geco_desktop.science_releases import DEFAULT_PYTHON, GECO, TEAL
from geco_desktop.sessions import SessionError, SessionManager


def qualify() -> None:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("Install uv before qualifying a science profile")
    with tempfile.TemporaryDirectory(prefix="gecod-qualified-") as temporary:
        base = Path(temporary)
        manager = EnvironmentManager(base=base / "software", uv=uv)
        if platform.system() == "Windows":
            # Simulate a poisoned user roaming uv location, like WinError 448,
            # while actually resolving/installing the full scientific profile.
            os.environ["UV_DATA_DIR"] = str(base / "roaming-uv")
            os.environ["UV_PYTHON_INSTALL_DIR"] = str(
                base / "roaming-uv" / "python"
            )
            assert manager._uv_environment()["UV_PYTHON_INSTALL_DIR"] == str(
                manager.base / "uv-data" / "python"
            )
        spec = RuntimeSpec(
            DEFAULT_PYTHON, TEAL.version, GECO.version,
            locked_packages=(
                f"text-analysis-lab[all]=={TEAL.version}",
                f"geometric-coder=={GECO.version}",
            ),
        )
        files = resolve_project_files(manager, "Profile acceptance", spec)
        locked = replace(spec, resolved_requirements=files.requirements)
        python = manager.ensure(locked)
        assert manager.locate(locked) == python

        root = base / "Profile acceptance.gecod"
        root.mkdir()
        files.write(root)
        descriptor = ProjectDescriptor.new(
            "Profile acceptance", locked, project_lock_sha256=files.digest
        )
        write_descriptor(root, descriptor)
        runner = installed_runner_path()

        def command(action, **kwargs):
            return run_command(python, runner, action, path=str(root), timeout=1200, **kwargs)

        command("create_teal", name=descriptor.name)
        csv_file = base / "sentences.csv"
        with csv_file.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "text", "author"])
            for i in range(8):
                writer.writerow([
                    i, f"Example {i} sentence A|Example {i} sentence B",
                    "researcher",
                ])
        imported = command(
            "import_source", source_path=str(csv_file), kind="csv",
            text_fields=["text"], metadata_fields=["author"],
        )
        cleaned = command(
            "apply_step", artifact_id=imported["id"], kind="clean",
            field="text", options={"pattern": r"Example ", "replacement": ""},
            alias="cleaned",
        )["output"]
        units = command(
            "apply_step", artifact_id=cleaned["id"], kind="split",
            field="text", options={"delimiter": "|", "new_key": "unit_id"},
            alias="units",
        )["output"]
        assert units["rows"] == 16
        # The first GeCo workspace must open from texts without
        # computing a representation in Desktop.
        result = command(
            "finalize", documents_id=units["id"], text_id=units["id"],
            text_field="text", geometry_id=None,
            view_id=None, metadata_fields=["author"],
        )
        assert result["workspace"] == "desktop"
        assert any(row["name"] == "desktop" for row in command("project_info")["workspaces"])
        local = base / "custom-checkpoint.bin"
        local.write_bytes(b"researcher-supplied")
        run_command(
            python, runner, "teal_model_register_local",
            timeout=1200, name="test checkpoint", path=str(local),
        )
        resources = run_command(
            python, runner, "teal_model_catalog", timeout=1200,
        )["models"]
        assert any(
            row["key"] == "local:test checkpoint" and row["present"]
            for row in resources
        )

        sessions = SessionManager(base=base / "software")
        try:
            session = sessions.start(root, descriptor, python, wait_seconds=60.0)
        except SessionError:
            for log in (base / "software" / "logs").glob("*.log"):
                print(
                    f"GeCo browser diagnostic ({log.name}):\\n"
                    + log.read_text(encoding="utf-8", errors="replace")[-6000:],
                    flush=True,
                )
            raise
        assert session.url.startswith("http://127.0.0.1:")
        try:
            assert sessions.list()
        finally:
            sessions.stop(session.key)
        assert not sessions.list()
        manifest = {
            "format": 1,
            "python": spec.python,
            "teal": spec.teal,
            "geco": spec.geco,
            "pyproject": files.pyproject,
            "uv_lock": files.lock,
        }
        output = Path.cwd() / f"candidate-profile-{platform.system().lower()}.json"
        output.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print("PASS: full profile, text prep, GeCo link/browser, and close")


if __name__ == "__main__":
    qualify()
