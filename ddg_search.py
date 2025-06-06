import requests
from bs4 import BeautifulSoup
from typing import List, Dict

def ddg_search(query: str, max_results: int = 5, region: str = "us-en") -> List[Dict[str, str]]:
    """Perform a DuckDuckGo search via the HTML endpoint."""
    url = "https://html.duckduckgo.com/html"
    data = {"q": query, "kl": region, "kp": "-2"}
    headers = {"User-Agent": "Mozilla/5.0 (Python) DevstralDDG/1.0"}
    resp = requests.post(url, data=data, headers=headers, timeout=10)
    resp.raise_for_status()
    return parse_ddg_html(resp.text, max_results)

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
        snippet_tag = div.find("a", class_="result__snippet") or div.find("p", class_="result__snippet")
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
    md = ddg_results_to_markdown(ddg_search(q, max_results=3))
    print(md)
