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


def test_watcher_handles_rename(tmp_path):
    f = tmp_path / "file.py"
    f.write_text("a=1")
    scanner = WorkspaceScanner(tmp_path)
    scanner.scan()
    watcher = WorkspaceWatcher(scanner)
    watcher.start()
    try:
        new = tmp_path / "renamed.py"
        f.rename(new)
        time.sleep(0.5)
        assert new in scanner.index
        assert f not in scanner.index
    finally:
        watcher.stop()


def test_scanner_ignores_symlink_file(tmp_path):
    target = tmp_path / "real.py"
    target.write_text("print('hi')")
    link = tmp_path / "link.py"
    link.symlink_to(target)
    scanner = WorkspaceScanner(tmp_path)
    scanner.scan()
    assert target in scanner.index
    assert link not in scanner.index


def test_scanner_ignores_symlink_directory(tmp_path):
    real = tmp_path / "dir"
    real.mkdir()
    f = real / "a.py"
    f.write_text("x = 1")
    linkdir = tmp_path / "symdir"
    linkdir.symlink_to(real, target_is_directory=True)
    scanner = WorkspaceScanner(tmp_path)
    scanner.scan()
    assert f in scanner.index
    assert linkdir not in scanner.index
    assert not any(p.is_relative_to(linkdir) for p in scanner.index)


def test_watcher_ignores_symlink(tmp_path):
    target = tmp_path / "real.py"
    target.write_text("print('hi')")
    scanner = WorkspaceScanner(tmp_path)
    scanner.scan()
    watcher = WorkspaceWatcher(scanner)
    watcher.start()
    try:
        link = tmp_path / "link.py"
        link.symlink_to(target)
        time.sleep(0.5)
        assert link not in scanner.index
    finally:
        watcher.stop()
