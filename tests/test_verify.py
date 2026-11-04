import os, sys

os.environ.setdefault("MISTRAL_API_KEY", "dummy")
os.environ.setdefault("TAVILY_API_KEY", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from types import SimpleNamespace
from unittest.mock import patch

import backend.pipeline as pipeline_mod
import backend.sources as sources_mod
from backend.agents import Critique
from backend.verify import extract_sentences, format_verification, verify_report

SOURCES = [
    {
        "id": 1,
        "title": "A",
        "url": "https://a.com",
        "read": "full",
        "text": "Menlo Ventures found that 51 percent of enterprise AI deployments use RAG. GNoME predicted 380,000 stable materials.",
    },
    {
        "id": 2,
        "title": "B",
        "url": "https://b.com",
        "read": "full",
        "text": "Fine-tuning gives sub-second latency. RAG adds one to three seconds of latency.",
    },
    {
        "id": 3,
        "title": "C",
        "url": "https://c.com",
        "read": "snippet",
        "text": "Hybrid approaches such as RAFT combine retrieval with fine-tuning.",
    },
]

REPORT = """# Report title

## Introduction

Enterprises must choose between retrieval and fine-tuning for their models [1][2]. This is a sentence with no citation at all.

## Key Findings

### 1. Adoption

- **Adoption:** Menlo Ventures found that 51 percent of enterprise AI deployments use RAG [1].
- GNoME predicted 380000 stable materials for clean energy hardware [1].
- Teams in 2031 will save 77 percent of all their costs with this approach [2].
- RAG adds one to three seconds of latency to every request [7].

| Dimension | RAG | Fine-Tuning |
| :-- | :-- | :-- |
| **Latency** | One to three seconds [2] | Sub-second [2] |

Hybrid designs combine both methods in one pipeline. [3]
"""


class FakeChain:
    def __init__(self, checks=None, error=None):
        self.checks, self.error, self.seen = checks, error, None

    def invoke(self, payload):
        self.seen = payload
        if self.error:
            raise self.error
        return SimpleNamespace(checks=self.checks)


def check(i, verdict, reason=""):
    return SimpleNamespace(id=i, verdict=verdict, reason=reason)


def test_reading_the_report_skips_headings_and_handles_bullets_tables_and_stray_citations():
    sentences = extract_sentences(REPORT)
    text = " | ".join(sentences)
    assert "Report title" not in text and "Key Findings" not in text  # headings skipped
    assert "Dimension" not in text  # table header skipped
    assert (
        "Latency — One to three seconds [2] — Sub-second [2]" in text
    )  # table row kept
    assert any(s.endswith("[3]") for s in sentences)  # "pipeline. [3]" stays attached
    assert all("**" not in s for s in sentences)


def test_automatic_checks_find_real_problems():
    v = verify_report(REPORT, SOURCES)
    assert v["invalid_citations"] == [7]  # [7] does not exist
    assert v["unused_sources"] == []  # 1, 2 and 3 are all cited
    assert v["uncited_sentences"] == 1  # the "no citation at all" sentence
    assert v["llm_used"] is False and v["checked"] == 0
    verdicts = {f["verdict"] for f in v["flagged"]}
    assert {"invalid_citation", "figure_not_found"} <= verdicts
    figure_flags = " ".join(
        f["reason"] for f in v["flagged"] if f["verdict"] == "figure_not_found"
    )
    assert (
        "77" in figure_flags and "2031" in figure_flags
    )  # invented figures are caught
    assert (
        "51" not in figure_flags and "380000" not in figure_flags
    )  # real ones pass, commas ignored


def test_unused_sources_are_listed():
    v = verify_report(
        "Retrieval systems ground answers in external documents [1].", SOURCES
    )
    assert v["unused_sources"] == [2, 3]


def test_ai_fact_check_counts_verdicts_and_flags_the_bad_ones():
    body = (
        "Menlo Ventures found that 51 percent of enterprise AI deployments use RAG [1]. "
        "Fine-tuning gives sub-second latency for every single request [2]. "
        "Hybrid approaches always beat both methods on every benchmark [3]."
    )
    chain = FakeChain(
        [
            check(1, "Supported"),
            check(2, "supported"),
            check(3, "UNSUPPORTED", "sources never say always"),
        ]
    )
    v = verify_report(body, SOURCES, chain)
    assert v["llm_used"] and v["checked"] == 3
    assert (v["supported"], v["partial"], v["unsupported"]) == (2, 0, 1)
    assert v["support_rate"] == 0.667
    flagged = [f for f in v["flagged"] if f["verdict"] == "unsupported"]
    assert flagged and "always" in flagged[0]["reason"]
    assert (
        "[3]" in chain.seen["claims"] and "Hybrid approaches" in chain.seen["sources"]
    )


def test_unclear_or_missing_answers_are_never_counted_as_supported():
    body = "Menlo Ventures found that 51 percent of enterprise AI deployments use RAG [1]. Fine-tuning gives sub-second latency for every request [2]."
    v = verify_report(
        body, SOURCES, FakeChain([check(1, "maybe?"), check(99, "supported")])
    )
    assert v["checked"] == 1 and v["partial"] == 1 and v["supported"] == 0
    assert any("not returned" in n for n in v["notes"])


def test_a_failing_fact_checker_is_skipped_not_fatal():
    body = (
        "Menlo Ventures found that 51 percent of enterprise AI deployments use RAG [1]."
    )
    v = verify_report(body, SOURCES, FakeChain(error=RuntimeError("429 rate limit")))
    assert v["llm_used"] is False and any("skipped" in n for n in v["notes"])
    assert v["claims_total"] == 1


def test_feedback_text_is_readable():
    chain = FakeChain(
        [check(1, "supported"), check(2, "partial", "only part is stated")]
    )
    body = (
        "Menlo Ventures found that 51 percent of enterprise AI deployments use RAG [1]. "
        "Fine-tuning gives sub-second latency and also lower cost [2]."
    )
    text = format_verification(verify_report(body, SOURCES, chain))
    assert "1 of 2 cited claims are fully supported by their sources (50%)" in text
    assert "Partly supported: 1" in text and "Sources never cited: [3]" in text
    assert "(partly supported): only part is stated" in text
    assert 'lower cost." [2]' in text  # no stray space before the full stop
    assert text.startswith("---")


def test_pipeline_adds_the_citation_check_to_the_feedback_card(monkeypatch):
    monkeypatch.setenv("VERIFY_WITH_LLM", "true")
    found = [
        {"title": f"Art {i}", "url": f"https://x.com/{i}", "snippet": f"snippet {i}"}
        for i in (1, 2)
    ]

    class Writer:
        def invoke(self, _):
            return "RAG grounds answers in retrieved documents for enterprise users [1]. Fine-tuning changes model behaviour permanently [2]."

    class Critic:
        def invoke(self, _):
            return Critique(
                score=9, strengths=["clear"], improvements=["none"], verdict="good"
            )

    checker = FakeChain([check(1, "supported"), check(2, "supported")])
    with (
        patch.object(sources_mod, "search_web", return_value=found),
        patch.object(sources_mod, "fetch_page", return_value="Full text. " * 40),
        patch.object(pipeline_mod, "writer_chain", Writer()),
        patch.object(pipeline_mod, "critic_chain", Critic()),
        patch.object(pipeline_mod, "verifier_chain", checker),
    ):
        state = pipeline_mod.run_research_pipeline("topic")
    assert state["status"] == "success", state["error"]
    assert state["verification"]["supported"] == 2 and state["verification"]["llm_used"]
    assert (
        "Citation check" in state["feedback"]
        and "2 of 2 cited claims" in state["feedback"]
    )
    assert "Score: 9/10" in state["feedback"]


def test_pipeline_survives_a_crashing_checker(monkeypatch):
    found = [{"title": "Art", "url": "https://x.com/1", "snippet": "snippet"}]

    class Writer:
        def invoke(self, _):
            return (
                "RAG grounds answers in retrieved documents for enterprise users [1]."
            )

    class Critic:
        def invoke(self, _):
            return Critique(
                score=9, strengths=["clear"], improvements=["none"], verdict="good"
            )

    with (
        patch.object(sources_mod, "search_web", return_value=found),
        patch.object(sources_mod, "fetch_page", return_value="Full text. " * 40),
        patch.object(pipeline_mod, "writer_chain", Writer()),
        patch.object(pipeline_mod, "critic_chain", Critic()),
        patch.object(pipeline_mod, "verify_report", side_effect=RuntimeError("boom")),
    ):
        state = pipeline_mod.run_research_pipeline("topic")
    assert state["status"] == "success" and state["verification"] is None
    assert any("Citation check failed" in w for w in state["warnings"])
