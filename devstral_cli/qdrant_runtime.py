from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional

_qdrant_proc: subprocess.Popen | None = None


def _bin_name() -> str:
    system = platform.system().lower()
    arch = platform.machine().lower()
    return f"qdrant-{system}-{arch}"


def find_qdrant_binary() -> Path:
    bin_dir = Path(__file__).parent / "bin"
    path = bin_dir / _bin_name()
    if not path.exists():
        raise FileNotFoundError(f"Bundled qdrant binary not found: {path}")
    return path


def start_qdrant(port: int = 6333, storage: Optional[Path] = None) -> Optional[subprocess.Popen]:
    global _qdrant_proc
    if _qdrant_proc and _qdrant_proc.poll() is None:
        return _qdrant_proc

    try:
        binary = find_qdrant_binary()
    except FileNotFoundError:
        return None
    env = os.environ.copy()
    env.setdefault("QDRANT__SERVICE__HTTP_PORT", str(port))
    if storage:
        env.setdefault("QDRANT__STORAGE__STORAGE_PATH", str(storage))
    _qdrant_proc = subprocess.Popen([str(binary)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return _qdrant_proc


def stop_qdrant() -> None:
    global _qdrant_proc
    if _qdrant_proc:
        _qdrant_proc.terminate()
        try:
            _qdrant_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:  # pragma: no cover - unlikely
            _qdrant_proc.kill()
        _qdrant_proc = None
