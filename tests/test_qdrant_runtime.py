import devstral_cli.qdrant_runtime as qr


def test_start_qdrant_missing_binary(monkeypatch):
    monkeypatch.setattr(qr, "find_qdrant_binary", lambda: (_ for _ in ()).throw(FileNotFoundError()))
    assert qr.start_qdrant() is None


def test_start_qdrant_launch(monkeypatch, tmp_path):
    started = {}

    def fake_find():
        path = tmp_path / "qd"
        path.write_text("")
        return path

    class DummyProc:
        def poll(self):
            return None

    def fake_popen(args, env=None, stdout=None, stderr=None):
        started["args"] = args
        return DummyProc()

    monkeypatch.setattr(qr, "find_qdrant_binary", fake_find)
    monkeypatch.setattr(qr.subprocess, "Popen", fake_popen)
    proc = qr.start_qdrant(port=7000)
    assert isinstance(proc, DummyProc)
    assert started["args"] == [str(fake_find())]
