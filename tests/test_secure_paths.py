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


def test_create_file_symlink_escape(monkeypatch, tmp_path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    target = outside / "secret.txt"
    target.write_text("secret")
    link = tmp_path / "link.txt"
    link.symlink_to(target)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        create_file("link.txt", "data")


def test_create_directory_symlink_escape(monkeypatch, tmp_path, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside_dir")
    link = tmp_path / "linkdir"
    link.symlink_to(outside, target_is_directory=True)
    monkeypatch.chdir(tmp_path)
    result = create_directory("linkdir/sub")
    assert result.startswith("Error")
