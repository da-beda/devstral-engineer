import sys
import importlib
import pytest

import cost_tracker
import conversation_store


def test_add_cost_accumulates(monkeypatch):
    monkeypatch.setattr(cost_tracker, "total_cost", 0.0)
    monkeypatch.setattr(cost_tracker, "total_api_duration", 0.0)
    cost_tracker.add_cost(0.5, 2.0)
    cost_tracker.add_cost(1.0, 3.0)
    assert cost_tracker.total_cost == 1.5
    assert cost_tracker.total_api_duration == 5.0


class DummySession:
    async def prompt_async(self, prompt):
        raise EOFError


def reload_devstral(tmp_path, monkeypatch):
    hist = tmp_path / "history.json"
    monkeypatch.setattr(conversation_store, "HISTORY_FILE", hist)
    sys.modules.pop("devstral_eng", None)
    import devstral_eng
    return importlib.reload(devstral_eng)


@pytest.mark.asyncio
async def test_session_prints_summary(tmp_path, monkeypatch):
    eng = reload_devstral(tmp_path, monkeypatch)
    monkeypatch.setattr(eng.Config, "load", classmethod(lambda cls: cls()))
    monkeypatch.setattr(eng, "prompt_session", DummySession())
    class FakeAI:
        def __init__(self, *a, **k):
            self.chat = type("Chat", (), {"completions": type("Comp", (), {"create": lambda *a, **k: None})()})()

    monkeypatch.setattr(eng, "AsyncOpenAI", FakeAI)
    printed = []
    monkeypatch.setattr(eng.console, "print", lambda *a, **k: printed.append(" ".join(str(x) for x in a)))
    monkeypatch.setattr(eng, "format_cost_summary", lambda: "SUMMARY")
    await eng.main(no_index=True)
    assert any("SUMMARY" in p for p in printed)

