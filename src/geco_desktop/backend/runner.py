"""Application-owned runner. Execute this file with a project's pinned Python.

This module intentionally imports only Python standard library at startup. It is
not installed into each immutable scientific environment and never imports Qt.
"""

from __future__ import annotations

import _thread
import argparse
import importlib.util
import json
import sys
import threading
import traceback
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = 1


def dispatch(message: dict[str, Any]) -> dict[str, Any]:
    if message.get("version") != PROTOCOL_VERSION:
        raise ValueError("Unsupported runner protocol")
    action = message.get("action")
    args = message.get("arguments", {})
    if not isinstance(args, dict):
        raise ValueError("Expected command arguments object")
    if action == "ping":
        return {"python": sys.version.split()[0], "runner_protocol": PROTOCOL_VERSION}
    if action == "project_info":
        from text_analysis_lab import Project

        project = Project.open(args["path"])
        try:
            workspaces = project.geco.list()
            return {"project_path": str(project.path), "workspaces": workspaces}
        finally:
            project.close()
    if action in {"csv_schema", "source_schema", "import_source", "catalog", "import_csv", "preview", "preview_step", "apply_step", "finalize"}:
        # This sibling resource ships with the current installed Desktop runner,
        # not as a package added to an immutable TeAL scientific environment.
        resource = Path(__file__).with_name("workflow.py")
        if not resource.is_file():
            raise FileNotFoundError(f"Desktop workflow resource missing: {resource}")
        module_spec = importlib.util.spec_from_file_location("_geco_desktop_workflow", resource)
        if module_spec is None or module_spec.loader is None:
            raise RuntimeError("Unable to load Desktop workflow resource.")
        workflow = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(workflow)
        return getattr(workflow, action)(**args)
    if action == "create_teal":
        from text_analysis_lab import Project

        root = Path(args["path"])
        if (root / ".teal").exists():
            raise FileExistsError("TeAL state already exists; refusing to replace it")
        project = Project.create(root, name=args["name"], delete_existing=False)
        try:
            return {"project_path": str(project.path)}
        finally:
            project.close()
    raise ValueError(f"Unsupported runner action: {action!r}")


def run_lines() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = {"version": PROTOCOL_VERSION, "ok": True, "result": dispatch(json.loads(line))}
        except Exception as exc:
            response = {
                "version": PROTOCOL_VERSION,
                "ok": False,
                "error": {"type": type(exc).__name__, "message": str(exc)},
            }
            traceback.print_exc(file=sys.stderr)
        print(json.dumps(response, default=str, allow_nan=False), flush=True)
    return 0


def serve(path: str, workspace: str, port: int, shutdown_file: str | None = None) -> int:
    from text_analysis_lab import Project

    project = Project.open(path)
    complete = threading.Event()

    def watch_shutdown() -> None:
        if not shutdown_file:
            return
        marker = Path(shutdown_file)
        while not complete.wait(0.15):
            if marker.is_file():
                _thread.interrupt_main()
                return

    watcher = threading.Thread(target=watch_shutdown, daemon=True)
    watcher.start()
    try:
        linked = project.geco.open(workspace)
        linked.launch(host="127.0.0.1", port=port, debug=False, use_reloader=False)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        complete.set()
        watcher.join(timeout=1)
        project.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--project")
    parser.add_argument("--workspace", default="desktop")
    parser.add_argument("--port", type=int)
    parser.add_argument("--shutdown-file")
    args = parser.parse_args()
    if args.serve:
        if not args.project or not args.port:
            parser.error("--serve requires --project and --port")
        return serve(args.project, args.workspace, args.port, args.shutdown_file)
    return run_lines()


if __name__ == "__main__":
    raise SystemExit(main())
