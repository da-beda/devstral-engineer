from conversation_store import load_history, save_history, HISTORY_FILE


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
