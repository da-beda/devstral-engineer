import time
from code_index_engine.scanner import WorkspaceScanner
from code_index_engine.watcher import WorkspaceWatcher


def test_scanner_respects_gitignore(tmp_path):
    (tmp_path / ".gitignore").write_text("ignored.py\n")
    good = tmp_path / "good.py"
    ignored = tmp_path / "ignored.py"
    good.write_text('print("ok")')
    ignored.write_text('print("no")')
    scanner = WorkspaceScanner(tmp_path)
    scanner.scan()
    assert good in scanner.index
    assert ignored not in scanner.index


def test_watcher_updates_index(tmp_path):
    f = tmp_path / "file.py"
    f.write_text("a=1")
    scanner = WorkspaceScanner(tmp_path)
    scanner.scan()
    watcher = WorkspaceWatcher(scanner)
    watcher.start()
    try:
        f.write_text("a=2")
        time.sleep(0.5)
        assert scanner.index[f].content == "a=2"
    finally:
        watcher.stop()
