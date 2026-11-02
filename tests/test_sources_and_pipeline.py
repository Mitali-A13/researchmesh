import os, sys, time

os.environ.setdefault("MISTRAL_API_KEY", "dummy")
os.environ.setdefault("TAVILY_API_KEY", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import patch
import backend.sources as sources_mod
import backend.pipeline as pipeline_mod
import backend.custom_tools as tools
from backend.agents import Critique

FOUND = [
    {
        "title": f"Article {i}",
        "url": f"https://example.com/{i}",
        "snippet": f"snippet {i}",
    }
    for i in range(1, 6)
]


def fake_fetch(url, max_chars=6000):
    time.sleep(0.5)  # simulate a slow download
    if url.endswith("/3"):
        raise ValueError("HTTP 403")  # one page blocks us
    if url.endswith("/5"):
        raise ValueError("timeout")  # another fails too
    return f"Full text of {url} " * 20


def test_import_without_keys():
    # tools are created lazily, so importing never needs a key
    assert callable(tools.search_web) and callable(tools.fetch_page)


def test_gather_sources_numbers_parallel_and_fallback():
    with (
        patch.object(sources_mod, "search_web", return_value=FOUND),
        patch.object(sources_mod, "fetch_page", side_effect=fake_fetch),
    ):
        t = time.time()
        sources, warnings = sources_mod.gather_sources("topic")
        elapsed = time.time() - t
    assert [s["id"] for s in sources] == [1, 2, 3, 4, 5]  # stable numbering
    assert [s["read"] for s in sources] == [
        "full",
        "full",
        "snippet",
        "full",
        "snippet",
    ]
    assert sources[2]["text"] == "snippet 3"  # fallback used
    assert len(warnings) == 2
    assert elapsed < 1.5, f"not parallel: {elapsed:.1f}s"  # sequential would be 2.5s


def test_all_pages_unreadable_raises_only_if_no_text_at_all():
    nosnip = [{"title": "A", "url": "https://x.com/a", "snippet": ""}]
    with (
        patch.object(sources_mod, "search_web", return_value=nosnip),
        patch.object(sources_mod, "fetch_page", side_effect=ValueError("boom")),
    ):
        try:
            sources_mod.gather_sources("t")
            assert False
        except ValueError as e:
            assert "Could not read any" in str(e)


def test_no_results():
    with patch.object(sources_mod, "search_web", return_value=[]):
        try:
            sources_mod.gather_sources("t")
            assert False
        except ValueError as e:
            assert "No search results" in str(e)


class FakeChain:
    def __init__(self, out):
        self.out, self.seen, self.calls = out, None, 0

    def invoke(self, x):
        self.seen, self.calls = x, self.calls + 1
        return self.out


def make_critique(score):
    return Critique(
        score=score,
        strengths=["clear structure"],
        improvements=["add depth"],
        verdict="solid",
    )


def test_full_pipeline_with_fake_llm():
    writer = FakeChain("## Introduction\nClaim A [1]. Claim B [2][4].")
    reviser = FakeChain("## Introduction\nImproved claim [1]. Another [2].")
    critic_scores = iter([6, 9])

    class Critic:
        seen = None

        def invoke(self, x):
            Critic.seen = x
            return make_critique(next(critic_scores))

    with (
        patch.object(sources_mod, "search_web", return_value=FOUND),
        patch.object(sources_mod, "fetch_page", side_effect=fake_fetch),
        patch.object(pipeline_mod, "writer_chain", writer),
        patch.object(pipeline_mod, "reviser_chain", reviser),
        patch.object(pipeline_mod, "critic_chain", Critic()),
    ):
        state = pipeline_mod.run_research_pipeline("AI in healthcare")
    assert state["status"] == "success", state["error"]
    # writer received numbered sources with real URLs
    assert (
        "[1] Article 1" in writer.seen["research"]
        and "https://example.com/4" in writer.seen["research"]
    )
    # the loop ran once: first draft scored 6, revision scored 9
    assert reviser.calls == 1 and state["scores"] == [6, 9] and state["revisions"] == 1
    # the report is the improved draft, with a code-generated Sources section of real URLs
    assert "Improved claim" in state["report"] and "## Sources" in state["report"]
    for i in range(1, 6):
        assert f"https://example.com/{i}" in state["report"]
    assert "_(snippet only)_" in state["report"]
    # the critic could see the Sources list
    assert "## Sources" in Critic.seen["report"]
    # feedback card shows the real score path
    assert "Score: 9/10" in state["feedback"] and "6 → 9" in state["feedback"]
    # frontend payload: no giant text field
    assert all("text" not in s for s in state["sources"])
    assert len(state["warnings"]) == 2


def test_pipeline_failure_is_reported():
    with patch.object(sources_mod, "search_web", return_value=[]):
        state = pipeline_mod.run_research_pipeline("x")
    assert state["status"] == "failed" and "No search results" in state["error"]


def test_fetch_page_rules():
    import requests

    class R:
        def __init__(s, text, ctype="text/html", status=200):
            s.text, s.headers, s.status_code = text, {"Content-Type": ctype}, status

        def raise_for_status(s):
            if s.status_code >= 400:
                raise requests.HTTPError(f"HTTP {s.status_code}")

    html = (
        "<html><nav>MENU</nav><script>x()</script><body><p>"
        + ("Real content sentence. " * 40)
        + "</p></body></html>"
    )
    with patch.object(tools.requests, "get", return_value=R(html)):
        txt = tools.fetch_page("https://a.com")
        assert "Real content" in txt and "MENU" not in txt and "x()" not in txt
    with patch.object(tools.requests, "get", return_value=R("%PDF", "application/pdf")):
        try:
            tools.fetch_page("https://a.com/f.pdf")
            assert False
        except ValueError as e:
            assert "Not a readable" in str(e)
    with patch.object(tools.requests, "get", return_value=R("<p>tiny</p>")):
        try:
            tools.fetch_page("https://a.com")
            assert False
        except ValueError as e:
            assert "too little" in str(e)
    with patch.object(tools.requests, "get", return_value=R("", status=403)):
        try:
            tools.fetch_page("https://a.com")
            assert False
        except requests.HTTPError:
            pass
