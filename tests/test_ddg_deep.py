import pytest
import ddg_deep
from ddg_deep import parse_ddg_results, RESULTS_PER_PAGE

SAMPLE_HTML = """
<div class="result">
  <a class="result__a" href="http://example1.com">One</a>
</div>
<div class="result">
  <a class="result__a" href="http://example2.com">Two</a>
</div>
"""


def test_parse_ddg_results_extracts_urls():
    urls = parse_ddg_results(SAMPLE_HTML)
    assert urls == ["http://example1.com", "http://example2.com"]


# Build an HTML snippet with more than RESULTS_PER_PAGE results to ensure we stop
# at the limit.
MANY_RESULTS_HTML = "".join(
    f'<div class="result"><a class="result__a" href="http://site{i}.com">{i}</a></div>'
    for i in range(RESULTS_PER_PAGE + 5)
)


def test_parse_ddg_results_respects_limit():
    urls = parse_ddg_results(MANY_RESULTS_HTML)
    assert len(urls) == RESULTS_PER_PAGE
    # Ensure the first and last URLs are as expected
    assert urls[0] == "http://site0.com"
    assert urls[-1] == f"http://site{RESULTS_PER_PAGE - 1}.com"


@pytest.mark.asyncio
async def test_to_markdown_formats(monkeypatch):
    async def fake_fetch(url):
        return f"Content from {url}"

    monkeypatch.setattr("ddg_deep.fetch_article_text_async", fake_fetch)

    async def noop(_):
        pass

    monkeypatch.setattr("ddg_deep.asyncio.sleep", noop)
    from ddg_deep import to_markdown

    md = await to_markdown(["http://a.com", "http://b.com"])
    assert md.startswith("### Deep Research Articles")
    assert "#### 1. [http://a.com](http://a.com)" in md
    assert "#### 2. [http://b.com](http://b.com)" in md
    assert "Content from http://a.com" in md
    assert "Content from http://b.com" in md


@pytest.mark.asyncio
async def test_deep_research_aggregates_pages(monkeypatch):
    PAGE1 = """
    <div class="result"><a class="result__a" href="http://a.com">A</a></div>
    <div class="result"><a class="result__a" href="http://b.com">B</a></div>
    <a class="result--more__btn" href="#">More</a>
    """
    PAGE2 = """
    <div class="result"><a class="result__a" href="http://b.com">B</a></div>
    <div class="result"><a class="result__a" href="http://c.com">C</a></div>
    """

    async def fake_page(query, start=0):
        if start == 0:
            return PAGE1
        elif start == RESULTS_PER_PAGE:
            return PAGE2
        return None

    monkeypatch.setattr("ddg_deep.fetch_ddg_page", fake_page)

    async def fake_article(url):
        return f"Article for {url}"

    monkeypatch.setattr("ddg_deep.fetch_article_text_async", fake_article)

    async def noop(_):
        pass

    monkeypatch.setattr("ddg_deep.asyncio.sleep", noop)
    from ddg_deep import deep_research

    md = await deep_research("test")
    assert md.count("<details>") == 3
    assert "http://a.com" in md
    assert "http://b.com" in md
    assert "http://c.com" in md


@pytest.mark.asyncio
async def test_to_markdown_throttles_before_fetch(monkeypatch):
    calls = []

    async def fake_fetch(url):
        calls.append(f"fetch:{url}")
        return "text"

    async def fake_sleep(delay):
        calls.append(f"sleep:{delay}")

    monkeypatch.setattr("ddg_deep.fetch_article_text_async", fake_fetch)
    monkeypatch.setattr("ddg_deep.asyncio.sleep", fake_sleep)
    from ddg_deep import to_markdown, REQUEST_DELAY

    await to_markdown(["u1", "u2"])
    assert calls == ["fetch:u1", f"sleep:{REQUEST_DELAY}", "fetch:u2"]


@pytest.mark.asyncio
async def test_fetch_ddg_page_returns_none_on_error(monkeypatch):
    class FailResponse:
        async def __aenter__(self):
            raise RuntimeError("boom")

        async def __aexit__(self, exc_type, exc, tb):
            pass

    class FailSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            pass

        def post(self, *args, **kwargs):
            return FailResponse()

    monkeypatch.setattr(ddg_deep.aiohttp, "ClientSession", lambda *a, **kw: FailSession())

    result = await ddg_deep.fetch_ddg_page("query")
    assert result is None
