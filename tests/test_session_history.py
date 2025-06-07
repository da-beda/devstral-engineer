import importlib
import sys

import pytest
import conversation_store


def reload_devstral(tmp_path, monkeypatch):
    hist = tmp_path / "history.json"
    monkeypatch.setattr(conversation_store, "HISTORY_FILE", hist)
    sys.modules.pop("devstral_eng", None)
    import devstral_eng
    return importlib.reload(devstral_eng)


class DummySession:
    async def prompt_async(self, prompt):
        raise EOFError


@pytest.mark.asyncio
async def test_initial_history_messages(tmp_path, monkeypatch):
    eng = reload_devstral(tmp_path, monkeypatch)
    monkeypatch.setattr(eng.Config, "load", classmethod(lambda cls: cls()))
    monkeypatch.setattr(eng, "prompt_session", DummySession())
    class FakeAI:
        def __init__(self, *a, **k):
            self.chat = type("Chat", (), {"completions": type("Comp", (), {"create": lambda *a, **k: None})()})()

    monkeypatch.setattr(eng, "AsyncOpenAI", FakeAI)
    await eng.main(no_index=True)
    history = eng.conversation_history
    assert any(m["content"].startswith("Directory listing:") for m in history)
    assert any(m["content"].startswith("Git info:") for m in history)
    if eng.get_readme_content():
        assert any(m["content"].startswith("README:") for m in history)
