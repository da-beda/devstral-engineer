from ddg_search import (
    parse_ddg_html,
    ddg_results_to_markdown,
    _save_cache,
    _load_cache,
)

SAMPLE_HTML = """
<div class="result">
  <a class="result__a" href="http://example.com">Example Domain</a>
  <a class="result__snippet">Example snippet.</a>
</div>
"""


def test_parse_ddg_html():
    results = parse_ddg_html(SAMPLE_HTML, max_results=1)
    assert results == [
        {
            "title": "Example Domain",
            "url": "http://example.com",
            "snippet": "Example snippet.",
        }
    ]


def test_ddg_results_to_markdown():
    md = ddg_results_to_markdown(
        [
            {
                "title": "Example Domain",
                "url": "http://example.com",
                "snippet": "Example snippet.",
            }
        ]
    )
    assert md.splitlines()[0] == "### DuckDuckGo Search Results"
    assert "- [Example Domain](http://example.com): Example snippet." in md


def test_cache_roundtrip_with_utf8(tmp_path, monkeypatch):
    file = tmp_path / "cache.json"
    monkeypatch.setattr("ddg_search.CACHE_DIR", tmp_path)
    monkeypatch.setattr("ddg_search.CACHE_FILE", file)
    data = {
        "ключ": {
            "timestamp": 1,
            "results": [
                {
                    "title": "Пример",
                    "url": "http://example.com",
                    "snippet": "Описание",
                }
            ],
        }
    }
    _save_cache(data)
    assert file.exists()
    loaded = _load_cache()
    assert loaded == data
