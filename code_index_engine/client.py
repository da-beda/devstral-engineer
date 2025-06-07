import aiohttp
from typing import Any, List


class IndexClient:
    """Asynchronous client for the indexing engine API."""

    def __init__(self, base_url: str = "http://127.0.0.1:8001"):
        self.base_url = base_url.rstrip("/")

    async def start(self, path: str) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/start", json={"path": path}
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def stop(self) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/stop") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def clear(self) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/clear") as resp:
                resp.raise_for_status()
                return await resp.json()

    async def search(self, query: str, top_k: int = 5) -> List[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/search",
                json={"query": query, "top_k": top_k},
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def status(self) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/status") as resp:
                resp.raise_for_status()
                return await resp.json()
