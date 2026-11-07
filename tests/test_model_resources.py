"""Model cache APIs stay in scientific runner and use public Hub helpers."""
from __future__ import annotations

import sys
import types

import pytest

from geco_desktop.backend import workflow


def test_model_inventory_only_reports_models(monkeypatch, tmp_path):
    first = types.SimpleNamespace(
        repo_type="model", repo_id="org/encoder",
        revisions=[types.SimpleNamespace(
            commit_hash="abcdef012345", size_on_disk=1048576,
            snapshot_path="/cache/snapshots/abc",
        )],
    )
    second = types.SimpleNamespace(repo_type="dataset", repo_id="org/data", revisions=[])
    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
        scan_cache_dir=lambda: types.SimpleNamespace(repos=[second, first], warnings=[]),
        constants=types.SimpleNamespace(HF_HUB_CACHE=str(tmp_path)),
    ))
    result = workflow.model_inventory()
    assert result["models"] == [{
        "model": "org/encoder", "revision": "abcdef012345",
        "size_bytes": 1048576, "snapshot_path": "/cache/snapshots/abc",
    }]


def test_model_download_uses_resolved_immutable_commit(monkeypatch):
    events = []

    class FakeAPI:
        def model_info(self, model, revision=None):
            events.append(("resolve", model, revision))
            return types.SimpleNamespace(sha="f" * 40)

    def download(**kwargs):
        events.append(("download", kwargs))
        return "/cached/snapshot"

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
        HfApi=FakeAPI, snapshot_download=download,
    ))
    result = workflow.download_model("org/encoder", "v1")
    assert result["revision"] == "f" * 40
    assert events == [
        ("resolve", "org/encoder", "v1"),
        ("download", {"repo_id": "org/encoder", "revision": "f" * 40, "repo_type": "model"}),
    ]
    with pytest.raises(ValueError, match="identifier"):
        workflow.download_model("")


def test_runner_model_actions_do_not_require_qt(monkeypatch, tmp_path):
    from geco_desktop.backend import runner
    from geco_desktop.protocol import request

    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
        scan_cache_dir=lambda: types.SimpleNamespace(repos=[], warnings=[]),
        constants=types.SimpleNamespace(HF_HUB_CACHE=str(tmp_path)),
    ))
    result = runner.dispatch(request("model_inventory"))
    assert result == {"models": [], "warnings": []}


def test_model_inventory_first_use_empty_cache(monkeypatch, tmp_path):
    cache = tmp_path / "never-created"
    monkeypatch.setitem(sys.modules, "huggingface_hub", types.SimpleNamespace(
        constants=types.SimpleNamespace(HF_HUB_CACHE=str(cache)),
        scan_cache_dir=lambda: (_ for _ in ()).throw(AssertionError("scanned absent cache")),
    ))
    assert workflow.model_inventory() == {"models": [], "warnings": []}
