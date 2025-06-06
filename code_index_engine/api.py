from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
from .scanner import WorkspaceScanner
from .watcher import WorkspaceWatcher

app = FastAPI()

scanner: WorkspaceScanner | None = None
watcher: WorkspaceWatcher | None = None


class StartRequest(BaseModel):
    path: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@app.post("/start")
def start(req: StartRequest):
    global scanner, watcher
    root = Path(req.path)
    if not root.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    scanner = WorkspaceScanner(root)
    scanner.scan()
    watcher = WorkspaceWatcher(scanner)
    watcher.start()
    return {"status": "started"}


@app.post("/stop")
def stop():
    global scanner, watcher
    if watcher:
        watcher.stop()
        watcher = None
    scanner = None
    return {"status": "stopped"}


@app.post("/search")
def search(req: SearchRequest):
    if not scanner:
        raise HTTPException(status_code=400, detail="not started")
    blocks = scanner.search(req.query, req.top_k)
    return [{"path": str(b.path), "content": b.content[:200]} for b in blocks]


@app.get("/status")
def status() -> dict:
    """Return running status for health checks."""
    return {"status": "running" if scanner else "not_started"}
