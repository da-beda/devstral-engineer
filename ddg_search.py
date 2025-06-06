import json
import time
from pathlib import Path
from typing import List, Dict

import aiohttp
import asyncio
from bs4 import BeautifulSoup

CACHE_DIR = Path.home() / ".cache" / "devstral-engineer"
CACHE_FILE = CACHE_DIR / "ddg_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60  # 24 hours


def _load_cache() -> Dict[str, Dict[str, object]]:
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache: Dict[str, Dict[str, object]]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with CACHE_FILE.open("w") as f:
        json.dump(cache, f)


def clear_ddg_cache() -> None:
    """Remove the stored DuckDuckGo cache file."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()


async def async_ddg_search(
    query: str, max_results: int = 5, region: str = "us-en"
) -> List[Dict[str, str]]:
    """Asynchronously perform a DuckDuckGo search via the HTML endpoint with caching."""
    cache = _load_cache()
    key = f"{query}|{region}"
    now = time.time()
    entry = cache.get(key)
    if entry and now - entry.get("timestamp", 0) < CACHE_TTL_SECONDS:
        results = entry.get("results", [])
    else:
        url = "https://html.duckduckgo.com/html"
        data = {"q": query, "kl": region, "kp": "-2"}
        headers = {"User-Agent": "Mozilla/5.0 (Python) DevstralDDG/1.0"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, data=data, headers=headers, timeout=10
            ) as resp:
                resp.raise_for_status()
                text = await resp.text()
        results = parse_ddg_html(text, max_results)
        cache[key] = {"timestamp": now, "results": results}
        _save_cache(cache)
    return results[:max_results]


def ddg_search(
    query: str, max_results: int = 5, region: str = "us-en"
) -> List[Dict[str, str]]:
    """Synchronous wrapper for :func:`async_ddg_search`."""
    return asyncio.run(async_ddg_search(query, max_results=max_results, region=region))


def parse_ddg_html(html: str, max_results: int) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, str]] = []
    for div in soup.find_all("div", class_="result"):
        if len(results) >= max_results:
            break
        a_title = div.find("a", class_="result__a")
        if not a_title or not a_title.get("href"):
            continue
        title = a_title.get_text(strip=True)
        url = a_title["href"]
        snippet_tag = div.find("a", class_="result__snippet") or div.find(
            "p", class_="result__snippet"
        )
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def ddg_results_to_markdown(results: List[Dict[str, str]]) -> str:
    lines = ["### DuckDuckGo Search Results", ""]
    for r in results:
        lines.append(f"- [{r['title']}]({r['url']}): {r['snippet']}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "python"
    results = asyncio.run(async_ddg_search(q, max_results=3))
    md = ddg_results_to_markdown(results)
    print(md)
