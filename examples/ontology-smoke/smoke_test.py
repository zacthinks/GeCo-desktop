"""Genuine TeAL->GeCo Desktop process, reconnection and portability smoke."""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path
from geco_desktop.environments import installed_runner_path, run_command
from geco_desktop.project import ProjectDescriptor, RuntimeSpec, read_descriptor, write_descriptor
from geco_desktop.sessions import SessionManager

HERE = Path(__file__).resolve().parent

def smoke(science_python: Path, output: Path | None = None):
    output = output or Path(tempfile.mkdtemp(prefix="geco-real-smoke-"))
    output.mkdir(parents=True, exist_ok=True)
    csv = HERE / "data" / "documents.csv"
    root = output / "Ontology research.gecod"
    assert csv.is_file() and not root.exists()
    seed = subprocess.run([str(science_python), str(HERE / "seed_workspace.py"),
            "--root", str(root), "--csv", str(csv)],
            capture_output=True, text=True, timeout=240)
    if seed.returncode:
        raise RuntimeError(f"Real TeAL/GeCo creation failed:\n{seed.stdout}\n{seed.stderr}")
    data = json.loads(seed.stdout.strip().splitlines()[-1])
    assert data["rows"] == 84 and data["workspaces"] == ["desktop"], data
    runtime = RuntimeSpec(f"{sys.version_info.major}.{sys.version_info.minor}",
                          data["teal_version"], data["geco_version"])
    descriptor = replace(ProjectDescriptor.new("Ontology research", runtime),
                         state="finalized")
    write_descriptor(root, descriptor)
    runner = installed_runner_path()
    info = run_command(science_python, runner, "project_info", path=str(root))
    assert [w["name"] for w in info["workspaces"]] == ["desktop"]
    print("TeAL CSV, TF-IDF, SVD and linked GeCo creation passed", flush=True)
    registry = output / "app-local-sessions"
    manager = SessionManager(base=registry)
    active = manager.start(root, descriptor, science_python, wait_seconds=100)
    print("Real GeCo server responded:", active.url, flush=True)
    try:
        del manager
        manager = SessionManager(base=registry)
        assert len(manager.list()) == 1
        again = manager.start(root, descriptor, science_python, wait_seconds=15)
        assert again.pid == active.pid
        print("Desktop session-manager restart/reconnect passed", flush=True)
    finally:
        manager.stop(active.key)
    assert not manager.list()
    print("GeCo server stopped", flush=True)
    moved = output / "Relocated research.gecod"
    shutil.move(str(root), str(moved))
    actual, saved = read_descriptor(moved / "project.gecod")
    assert actual == moved.resolve() and saved == descriptor
    reopened = run_command(science_python, runner, "project_info", path=str(moved))
    assert [w["name"] for w in reopened["workspaces"]] == ["desktop"]
    print(json.dumps({"result": "PASS", "rows": 84, "project": str(moved)}))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--science-python", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    smoke(args.science_python.absolute(), args.output)
