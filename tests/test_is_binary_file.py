import os

os.environ.setdefault("OPENAI_API_KEY", "test")

from devstral_eng import is_binary_file


def test_utf16_not_binary(tmp_path):
    path = tmp_path / "utf16.txt"
    path.write_text("hello", encoding="utf-16")
    assert not is_binary_file(str(path))


def test_png_header_binary(tmp_path):
    path = tmp_path / "test.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n")
    assert is_binary_file(str(path))
