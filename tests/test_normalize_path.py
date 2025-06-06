from pathlib import Path
import ast
import types
import pytest

# Load only the normalize_path function from devstral_eng.py without importing
source = Path(__file__).resolve().parents[1] / "devstral_eng.py"
mod_ast = ast.parse(source.read_text())
fn_node = next(
    n for n in mod_ast.body if isinstance(n, ast.FunctionDef) and n.name == "normalize_path"
)
module = types.ModuleType("_normalize")
module.__dict__["Path"] = Path
exec(
    compile(ast.Module([fn_node], []), filename=str(source), mode="exec"),
    module.__dict__,
)
normalize_path = module.normalize_path


def test_normalize_valid_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = "subdir/file.txt"
    expected = str((tmp_path / p).resolve())
    assert normalize_path(p) == expected


def test_normalize_valid_absolute(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    abs_path = tmp_path / "absfile.txt"
    expected = str(abs_path.resolve())
    assert normalize_path(str(abs_path)) == expected


def test_reject_parent_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        normalize_path("../bad")


def test_reject_leading_tilde(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        normalize_path("~/bad")
