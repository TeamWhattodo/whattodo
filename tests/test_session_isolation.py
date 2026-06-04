import pytest


def test_sessions_isolated_between_users(tmp_path, monkeypatch):
    import backend.agents.sessions as sessions
    monkeypatch.setattr(sessions, "SESSION_ROOT", tmp_path / "sessions")

    sessions.save_session("userA_id", "s1", [{"role": "user", "content": "hi"}], [])

    # userA sees their session
    assert len(sessions.list_sessions("userA_id")) == 1
    # userB sees nothing
    assert sessions.list_sessions("userB_id") == []
    # userB cannot read userA's session by id
    assert sessions.load_session("userB_id", "s1") == ([], [])
    # userB deleting that id is a no-op; userA's session survives
    sessions.delete_session("userB_id", "s1")
    assert len(sessions.list_sessions("userA_id")) == 1


def test_session_id_rejects_path_traversal(tmp_path, monkeypatch):
    import backend.agents.sessions as sessions
    monkeypatch.setattr(sessions, "SESSION_ROOT", tmp_path / "sessions")
    with pytest.raises(ValueError):
        sessions.save_session("userA_id", "../evil", [], [])
    with pytest.raises(ValueError):
        sessions.load_session("userA_id", "../userA_id/s1")
