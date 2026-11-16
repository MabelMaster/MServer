import pytest

from server.static import read_asset, resolve


def test_root_path_reads_index(tmp_path):
    (tmp_path / "index.html").write_text("hello", encoding="utf-8")
    assert resolve(tmp_path, "/") == (tmp_path / "index.html").resolve()
    body, content_type = read_asset(tmp_path, "/")
    assert body == b"hello"
    assert content_type.startswith("text/html")


def test_parent_path_is_rejected(tmp_path):
    (tmp_path / "index.html").write_text("hello", encoding="utf-8")
    with pytest.raises(PermissionError):
        resolve(tmp_path, "/../secrets.txt")


def test_missing_file_is_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        resolve(tmp_path, "/missing.js")