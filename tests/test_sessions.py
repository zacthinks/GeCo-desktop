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

def test_live_but_unresponsive_process_stays_registered(tmp_path, monkeypatch):
    from geco_desktop import sessions
    manager = SessionManager(base=tmp_path)
    root = tmp_path / "A.gecod"
    root.mkdir()
    key = _identity(root, "test-project")
    entry = ActiveSession(
        key=key, project_id="test-project", project_path=str(root),
        project_name="A", pid=123, process_created=1.0, port=8050,
        runner_path="/runner.py",
    )
    monkeypatch.setattr(sessions, "_alive", lambda session: True)
    monkeypatch.setattr(sessions, "_ready", lambda session: False)
    manager._write({key: entry})
    result = manager.list()
    assert len(result) == 1
    assert result[0].status == "unresponsive"
    assert key in manager._read()


def test_live_managed_session_is_reused_even_when_not_http_ready(tmp_path, monkeypatch):
    from geco_desktop import sessions
    from geco_desktop.project import ProjectDescriptor, RuntimeSpec

    manager = SessionManager(base=tmp_path)
    root = tmp_path / "A.gecod"
    root.mkdir()
    descriptor = ProjectDescriptor.new("A", RuntimeSpec("3.11", "0.9.0", "0.8.15"))
    key = _identity(root, descriptor.project_id)
    entry = ActiveSession(
        key=key, project_id=descriptor.project_id, project_path=str(root),
        project_name="A", pid=123, process_created=1.0, port=8050,
        runner_path="/runner.py",
    )
    monkeypatch.setattr(sessions, "_alive", lambda session: True)
    monkeypatch.setattr(sessions, "_ready", lambda session: False)
    monkeypatch.setattr(sessions.subprocess, "Popen", lambda *args, **kwargs:
                        (_ for _ in ()).throw(AssertionError("duplicate launch")))
    manager._write({key: entry})
    assert manager.start(root, descriptor, tmp_path / "python") == entry
