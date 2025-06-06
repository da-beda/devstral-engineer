import asyncio
import time
import os

os.environ.setdefault("OPENAI_API_KEY", "test")

import devstral_eng


async def wait_for_status(client, timeout=10.0):
    start = time.time()
    while time.time() - start < timeout:
        try:
            await client.status()
            return
        except Exception:
            await asyncio.sleep(0.2)
    raise RuntimeError("engine did not start")


def test_search_code_returns_matches(tmp_path):
    sample = tmp_path / "match.py"
    sample.write_text("def foo(): pass")
    port = 8600
    devstral_eng.launch_engine(port, debug=False)
    asyncio.run(wait_for_status(devstral_eng.index_client))
    asyncio.run(devstral_eng.index_client.start(str(tmp_path)))
    try:
        output = asyncio.run(devstral_eng.search_code("foo"))
        assert "match.py" in output
        assert "foo" in output
    finally:
        asyncio.run(devstral_eng.index_client.stop())
        devstral_eng.engine_proc.terminate()
        devstral_eng.engine_proc.wait(timeout=5)


def test_search_code_directory_filter(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    f1 = d / "one.py"
    f2 = tmp_path / "two.py"
    f1.write_text("def bar(): pass")
    f2.write_text("def bar(): pass")
    port = 8601
    devstral_eng.launch_engine(port, debug=False)
    asyncio.run(wait_for_status(devstral_eng.index_client))
    asyncio.run(devstral_eng.index_client.start(str(tmp_path)))
    try:
        output = asyncio.run(devstral_eng.search_code("bar", directory_prefix=str(d)))
        assert str(f1) in output
        assert str(f2) not in output
    finally:
        asyncio.run(devstral_eng.index_client.stop())
        devstral_eng.engine_proc.terminate()
        devstral_eng.engine_proc.wait(timeout=5)
