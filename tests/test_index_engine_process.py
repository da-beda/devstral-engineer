import asyncio
import subprocess
import sys
import time
from code_index_engine.client import IndexClient


async def wait_for_status(client: IndexClient, timeout: float = 10.0) -> None:
    start = time.time()
    while time.time() - start < timeout:
        try:
            await client.status()
            return
        except Exception:
            await asyncio.sleep(0.2)
    raise RuntimeError("engine did not start")


def test_engine_process_starts_and_searches(tmp_path):
    file = tmp_path / "sample.py"
    file.write_text("def foo(): return 42")
    port = 8123
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "code_index_engine.api:app",
            "--port",
            str(port),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = IndexClient(f"http://127.0.0.1:{port}")
    try:
        asyncio.run(wait_for_status(client))
        asyncio.run(client.start(str(tmp_path)))
        results = asyncio.run(client.search("foo"))
        assert results
        assert "sample.py" in results[0]["path"]
    finally:
        asyncio.run(client.stop())
        proc.terminate()
        proc.wait(timeout=10)
