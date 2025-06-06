import asyncio
import os
import time
import threading

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


def test_engine_restarts_on_crash(tmp_path):
    port = 9000 + int(time.time()) % 1000
    devstral_eng.launch_engine(port)
    asyncio.run(wait_for_status(devstral_eng.index_client))
    assert devstral_eng.engine_proc.poll() is None

    # Simulate crash
    devstral_eng.engine_proc.terminate()
    devstral_eng.engine_proc.wait(timeout=5)

    # Start polling thread which should restart the engine
    devstral_eng.status_stop_event.clear()
    t = threading.Thread(target=devstral_eng.poll_engine_status, daemon=True)
    t.start()
    try:
        asyncio.run(wait_for_status(devstral_eng.index_client, timeout=15))
        assert devstral_eng.engine_proc.poll() is None
    finally:
        devstral_eng.status_stop_event.set()
        t.join(timeout=5)
        asyncio.run(devstral_eng.index_client.stop())
        devstral_eng.engine_proc.terminate()
        devstral_eng.engine_proc.wait(timeout=5)
