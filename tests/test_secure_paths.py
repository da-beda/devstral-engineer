import pytest
from devstral_eng import create_file, create_directory


def test_create_file_rejects_parent(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        create_file("../bad.txt", "data")


def test_create_file_rejects_tilde(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        create_file("~/bad.txt", "data")


def test_create_directory_rejects_parent(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = create_directory("../bad")
    assert result.startswith("Error")


def test_create_directory_rejects_tilde(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    result = create_directory("~/bad")
    assert result.startswith("Error")
