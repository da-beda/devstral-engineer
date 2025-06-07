from pathlib import Path
from typing import List, Dict
import pathspec
from .embeddings import embed_text

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
    def __init__(self, root: Path):
        self.root = root
        self.index: Dict[Path, IndexedBlock] = {}
        self._load_gitignore()

    def _load_gitignore(self):
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            patterns = gitignore.read_text().splitlines()
            self.spec = pathspec.PathSpec.from_lines("gitwildmatch", patterns)
        else:
            self.spec = pathspec.PathSpec.from_lines("gitwildmatch", [])

    def scan(self):
        for file in self.root.rglob("*"):
            if file.is_symlink():
                continue
            if file.is_file() and file.suffix in SUPPORTED_EXTENSIONS:
                rel = file.relative_to(self.root)
                if self.spec.match_file(str(rel)):
                    continue
                text = file.read_text(errors="ignore")
                embedding = embed_text(text)
                self.index[file] = IndexedBlock(file, text, embedding)

    def search(self, query: str, top_k: int = 5) -> List[IndexedBlock]:
        from numpy import dot
        from numpy.linalg import norm

        q = embed_text(query)
        results = []
        for block in self.index.values():
            v = block.embedding
            score = dot(q, v) / (norm(q) * norm(v) + 1e-6)
            results.append((score, block))
        results.sort(key=lambda x: x[0], reverse=True)
        return [b for _, b in results[:top_k]]
