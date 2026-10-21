from geco_desktop.sessions import ActiveSession, SessionManager, _identity


def test_session_registry_discards_stale_entries(tmp_path):
    manager = SessionManager(base=tmp_path)
    root = tmp_path / "A.gecod"
    root.mkdir()
    key = _identity(root, "test-project")
    entry = ActiveSession(
        key=key, project_id="test-project", project_path=str(root),
        project_name="A", pid=999999999, process_created=0.0, port=8050,
        runner_path="/does/not/exist.py",
    )
    manager._write({key: entry})
    assert manager.list() == []
    assert manager._read() == {}
    assert manager.list() == []
