import os

os.environ.setdefault("OPENAI_API_KEY", "test")
import devstral_eng


def test_apply_diff_edit_relative(monkeypatch, tmp_path):
    # create a file and cd into tmp_path
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "sample.txt"
    sample.write_text("hello world")

    # auto-confirm diff application
    class Dummy:
        def ask(self):
            return True

    monkeypatch.setattr(devstral_eng.questionary, "confirm", lambda *a, **k: Dummy())

    devstral_eng.apply_diff_edit("sample.txt", "hello", "goodbye")
    assert sample.read_text() == "goodbye world"
