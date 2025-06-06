import pytest
from ddg_deep import parse_ddg_results, RESULTS_PER_PAGE

SAMPLE_HTML = '''
<div class="result">
  <a class="result__a" href="http://example1.com">One</a>
</div>
<div class="result">
  <a class="result__a" href="http://example2.com">Two</a>
</div>
'''


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

