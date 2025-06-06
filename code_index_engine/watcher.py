from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .scanner import WorkspaceScanner, SUPPORTED_EXTENSIONS, IndexedBlock


class _Handler(FileSystemEventHandler):
    def __init__(self, scanner: WorkspaceScanner):
        self.scanner = scanner

    def on_created(self, event):
        self._handle(event.src_path)

    def on_modified(self, event):
        self._handle(event.src_path)

    def on_deleted(self, event):
        path = Path(event.src_path)
        if path in self.scanner.index:
            del self.scanner.index[path]

    def on_moved(self, event):
        src = Path(event.src_path)
        dest = Path(event.dest_path)
        if src in self.scanner.index:
            del self.scanner.index[src]
        self._handle(dest)

    def _handle(self, path_str: str):
        path = Path(path_str)
        if path.suffix in SUPPORTED_EXTENSIONS and path.is_file():
            rel = path.relative_to(self.scanner.root)
            if self.scanner.spec.match_file(str(rel)):
                return
            text = path.read_text(errors="ignore")
            embedding = (
                self.scanner.index[path].embedding
                if path in self.scanner.index
                else None
            )
            if embedding is None or self.scanner.index[path].content != text:
                from .embeddings import embed_text

                self.scanner.index[path] = IndexedBlock(path, text, embed_text(text))


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
