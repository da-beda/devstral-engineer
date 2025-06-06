import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import time

MAX_DDG_PAGES = 3
RESULTS_PER_PAGE = 10
MAX_ARTICLE_LENGTH = 50000
SUMMARIZE_THRESHOLD = 10000
REQUEST_DELAY = 1.0


def fetch_ddg_page(query: str, start: int = 0) -> Optional[str]:
    """Fetch one DuckDuckGo results page as HTML."""
    url = "https://html.duckduckgo.com/html"
    data = {"q": query, "kl": "us-en", "kp": "-2", "s": str(start)}
    headers = {"User-Agent": "Mozilla/5.0 (Python) DevstralDeep/1.0"}
    try:
        resp = requests.post(url, data=data, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"[ddg_deep] Error fetching page {start}: {e}")
        return None


def parse_ddg_results(html: str) -> List[str]:
    """Parse DDG HTML and return result URLs."""
    soup = BeautifulSoup(html, "html.parser")
    urls: List[str] = []
    for div in soup.find_all("div", class_="result"):
        if len(urls) >= RESULTS_PER_PAGE:
            break
        a_tag = div.find("a", class_="result__a")
        if a_tag and a_tag.get("href"):
            urls.append(a_tag["href"])
    return urls


def fetch_article_text(url: str) -> str:
    """Fetch the given URL and try to extract main textual content."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Python) DevstralDeep/1.0"}, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        art = soup.find("article")
        if art:
            txt = art.get_text("\n", strip=True)
            return txt[:MAX_ARTICLE_LENGTH]
        best = ""
        for d in soup.find_all("div"):
            t = d.get_text("\n", strip=True)
            if len(t) > len(best):
                best = t
        return best[:MAX_ARTICLE_LENGTH]
    except Exception:
        return ""


def to_markdown(urls: List[str]) -> str:
    """Convert URLs to a Markdown document with snippets."""
    lines = ["### Deep Research Articles", ""]
    for idx, link in enumerate(urls, start=1):
        text = fetch_article_text(link)
        if not text:
            lines.append(f"#### {idx}. [Failed to fetch {link}]")
            lines.append("")
            continue
        snippet = text[:200].replace("\n", " ")
        lines.append(f"#### {idx}. [{link}]({link})")
        lines.append(f"> {snippet}...")
        lines.append("")
        lines.append("<details>")
        lines.append("<summary>Read more</summary>")
        lines.append("")
        lines.append(text)
        lines.append("")
        lines.append("</details>")
        lines.append("")
        time.sleep(REQUEST_DELAY)
    return "\n".join(lines)


def deep_research(query: str) -> str:
    """Perform multi-page DuckDuckGo scraping and return Markdown."""
    collected: List[str] = []
    for page in range(MAX_DDG_PAGES):
        start_idx = page * RESULTS_PER_PAGE
        html = fetch_ddg_page(query, start=start_idx)
        if not html:
            break
        page_urls = parse_ddg_results(html)
        if not page_urls:
            break
        collected.extend(page_urls)
        soup = BeautifulSoup(html, "html.parser")
        more = soup.find("a", class_="result--more__btn")
        if not more:
            break
        time.sleep(REQUEST_DELAY)

    unique_urls: List[str] = []
    seen = set()
    for u in collected:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    md = to_markdown(unique_urls)
    if len(md) > SUMMARIZE_THRESHOLD:
        return f"*Deep research results exceed {SUMMARIZE_THRESHOLD} chars; please summarize below:*\n\n{md}"
    return md


if __name__ == "__main__":
    q = "python web scraping"
    result = deep_research(q)
    print(result[:2000])
