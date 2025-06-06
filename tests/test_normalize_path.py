import sys
import os
from pathlib import Path
import pytest

# Ensure the project root is on sys.path for module imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure OpenAI client doesn't error out during module import
os.environ.setdefault("OPENAI_API_KEY", "test")


from devstral_eng import normalize_path


def test_normalize_path_returns_absolute(tmp_path):
    file = tmp_path / "example.txt"
    file.write_text("hi")
    normalized = normalize_path(str(file))
    assert Path(normalized).is_absolute()
    assert Path(normalized) == file.resolve()


def test_normalize_path_rejects_parent_refs():
    with pytest.raises(ValueError):
        normalize_path("../outside.txt")


def test_normalize_path_rejects_home_refs():
    with pytest.raises(ValueError):
        normalize_path("~/secrets.txt")
