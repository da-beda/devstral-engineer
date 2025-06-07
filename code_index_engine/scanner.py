from pathlib import Path
from typing import List, Dict, Optional
import pathspec
from .embeddings import embed_text
from .qdrant_store import QdrantStore

SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".rs",
    ".go",
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".cs",
    ".rb",
    ".php",
}


class IndexedBlock:
    def __init__(self, path: Path, content: str, embedding: List[float]):
        self.path = path
        self.content = content
        self.embedding = embedding


class WorkspaceScanner:
    def __init__(self, root: Path, vector_store: Optional[QdrantStore] = None):
        self.root = root
        self.index: Dict[Path, IndexedBlock] = {}
        self.vector_store = vector_store
        self._load_gitignore()

    def _load_gitignore(self):
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            patterns = gitignore.read_text().splitlines()
            self.spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        else:
            self.spec = pathspec.PathSpec.from_lines("gitwildmatch", [])

    def scan(self) -> None:
        for file in self.root.rglob("*"):
            if file.is_symlink():
                continue
            if file.is_file() and file.suffix in SUPPORTED_EXTENSIONS:
                rel = file.relative_to(self.root)
                if self.spec.match_file(str(rel)):
                    continue
                text = file.read_text(errors="ignore")
                embedding = embed_text(text)
                block = IndexedBlock(file, text, embedding)
                self.index[file] = block
                if self.vector_store:
                    self.vector_store.upsert(
                        str(file),
                        embedding,
                        {"path": str(file)},
                    )

    def search(self, query: str, top_k: int = 5) -> List[IndexedBlock]:
        """Search indexed files by query string."""
        q = embed_text(query)

        if self.vector_store:
            hits = self.vector_store.search(q, limit=top_k)
            blocks = []
            for hit in hits:
                p = Path(hit["path"])
                block = self.index.get(p)
                if block:
                    blocks.append(block)
            return blocks

        from numpy import dot
        from numpy.linalg import norm

        results = []
        for block in self.index.values():
            v = block.embedding
            score = dot(q, v) / (norm(q) * norm(v) + 1e-6)
            results.append((score, block))
        results.sort(key=lambda x: x[0], reverse=True)
        return [b for _, b in results[:top_k]]
