import logging

from conversation_store import (
    load_history,
    save_history,
    display_history,
    clear_history,
)


def test_load_missing(tmp_path, monkeypatch):
    file = tmp_path / "hist.json"
    monkeypatch.setattr("conversation_store.HISTORY_FILE", file)
    assert load_history() == []


def test_roundtrip(tmp_path, monkeypatch):
    file = tmp_path / "hist.json"
    monkeypatch.setattr("conversation_store.HISTORY_FILE", file)
    sample = [{"role": "user", "content": "hi"}]
    save_history(sample)
    assert file.exists()
    assert load_history() == sample


def test_display_and_clear(tmp_path, monkeypatch):
    file = tmp_path / "hist.json"
    monkeypatch.setattr("conversation_store.HISTORY_FILE", file)
    sample = [{"role": "assistant", "content": "hello"}]
    save_history(sample)
    text = display_history()
    assert "assistant" in text
    clear_history()
    assert not file.exists()


def test_corrupt_file_logs_warning(tmp_path, monkeypatch, caplog):
    file = tmp_path / "hist.json"
    file.write_text("{ bad json")
    monkeypatch.setattr("conversation_store.HISTORY_FILE", file)
    with caplog.at_level(logging.WARNING):
        assert load_history() == []
    assert any(
        "Failed to parse conversation history" in rec.message for rec in caplog.records
    )
