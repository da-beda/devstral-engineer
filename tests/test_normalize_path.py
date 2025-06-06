# tests/test_normalize_path.py

from pathlib import Path
import ast
import types
import pytest

# Load only the normalize_path function from devstral_eng.py without importing
source = Path(__file__).resolve().parents[1] / "devstral_eng.py"
mod_ast = ast.parse(source.read_text())
fn_node = next(
    n for n in mod_ast.body
    if isinstance(n, ast.FunctionDef) and n.name == "normalize_path"
)
module = types.ModuleType("_normalize")
module.__dict__["Path"] = Path
exec(
    compile(ast.Module([fn_node], []), filename=str(source), mode="exec"),
    module.__dict__,
)
normalize_path = module.normalize_path


def test_normalize_valid_relative(tmp_path, monkeypatch):
    # Create a subdirectory + file, cd into tmp_path
    monkeypatch.chdir(tmp_path)
    sub = tmp_path / "subdir"
    sub.mkdir()
    file = sub / "file.txt"
    file.write_text("content")
    rel = "subdir/file.txt"
    expected = str((tmp_path / rel).resolve())
    assert normalize_path(rel) == expected


def test_normalize_valid_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    abs_file = tmp_path / "absfile.txt"
    abs_file.write_text("hello")
    expected = str(abs_file.resolve())
    assert normalize_path(str(abs_file)) == expected


def test_reject_parent_directory(monkeypatch, tmp_path):
    # If we try to normalize "../outside.txt", it must raise
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        normalize_path("../outside.txt")


def test_reject_leading_tilde(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        normalize_path("~/secrets.txt")
