from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .scanner import WorkspaceScanner, SUPPORTED_EXTENSIONS, IndexedBlock
from .embeddings import embed_text


class _Handler(FileSystemEventHandler):
    def __init__(self, scanner: WorkspaceScanner):
        self.scanner = scanner

    def on_created(self, event):
        self._handle(str(event.src_path))

    def on_modified(self, event):
        self._handle(str(event.src_path))

    def on_deleted(self, event):
        path = Path(str(event.src_path))
        if path in self.scanner.index:
            del self.scanner.index[path]
        if self.scanner.vector_store:
            self.scanner.vector_store.delete(str(path))

    def on_moved(self, event):
        src = Path(str(event.src_path))
        _dest = Path(str(event.dest_path))
        if src in self.scanner.index:
            del self.scanner.index[src]
        if self.scanner.vector_store:
            self.scanner.vector_store.delete(str(src))
        self._handle(str(event.dest_path))

    def _handle(self, path_str: str):
        path = Path(path_str)
        if path.is_symlink():
            return
        if path.suffix in SUPPORTED_EXTENSIONS and path.is_file():
            rel = path.relative_to(self.scanner.root)
            if self.scanner.spec.match_file(str(rel)):
                return
            text = path.read_text(errors="ignore")
            if (
                path not in self.scanner.index
                or self.scanner.index[path].content != text
            ):
                emb = embed_text(text)
                self.scanner.index[path] = IndexedBlock(path, text, emb)
                if self.scanner.vector_store:
                    self.scanner.vector_store.upsert(str(path), emb, {"path": str(path)})


class WorkspaceWatcher:
    def __init__(self, scanner: WorkspaceScanner):
        self.scanner = scanner
        self.observer = Observer()
        self.handler = _Handler(scanner)

    def start(self):
        self.observer.schedule(self.handler, str(self.scanner.root), recursive=True)
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
