import json
from types import SimpleNamespace

import pytest

import backend.evaluate as ev
from backend import agents
from backend.eval_summary import render, summarize

SOURCES = [
    {
        "id": 1,
        "title": "A",
        "url": "https://a.com",
        "read": "full",
        "text": "Solid-state batteries use a solid electrolyte. Costs remain high.",
    },
    {
        "id": 2,
        "title": "B",
        "url": "https://b.com",
        "read": "full",
        "text": "Several carmakers plan pilot production by 2027.",
    },
]

BODY = (
    "## Introduction\n\n"
    "Solid-state batteries use a solid electrolyte instead of a liquid one [1]. "
    "Costs remain high for now according to the sources [1].\n\n"
    "## Conclusion\n\nCarmakers plan pilot production soon [2]. This sentence has no citation at all."
)


class FakeVerifier:
    """Marks every claim as supported."""

    def invoke(self, inputs):
        count = inputs["claims"].count("\n") + 1
        checks = [
            SimpleNamespace(id=i, verdict="supported", reason="")
            for i in range(1, count + 1)
        ]
        return SimpleNamespace(checks=checks)


# ---------- text helpers ----------


def test_strip_for_judge_removes_markers_and_tidies():
    text = ev.strip_for_judge(
        "Batteries are costly [1][2]. Another point (see [3]) here."
    )
    assert "[" not in text
    assert "costly." in text
    assert "()" not in text


def test_strip_sources_section():
    report = "Body text [1].\n\n## Sources\n\n- **[1]** [A](https://a.com)"
    assert ev.strip_sources_section(report) == "Body text [1]."


def test_slugify_is_stable_and_safe():
    assert ev.slugify("RAG vs. Fine-tuning?!") == "rag-vs-fine-tuning"


def test_tag_every_sentence_lets_setup_a_be_fact_checked():
    plain = (
        "Solid-state batteries use a solid electrolyte instead of liquid ones today."
    )
    tagged = ev.tag_every_sentence(plain, SOURCES)
    assert tagged.endswith("[1][2]")
    result = ev.verify_report(tagged, SOURCES, FakeVerifier())
    assert result["claims_total"] == 1 and result["supported"] == 1


# ---------- retry ----------


def test_with_retry_waits_on_rate_limit_then_succeeds(monkeypatch):
    waits = []
    monkeypatch.setattr(ev, "_sleep", waits.append)
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("Error 429: rate limit reached")
        return "ok"

    assert ev.with_retry(flaky, "test") == "ok"
    assert calls["n"] == 3 and len(waits) == 2 and waits[1] > waits[0]


def test_with_retry_fails_fast_on_real_errors(monkeypatch):
    monkeypatch.setattr(ev, "_sleep", lambda s: None)
    calls = {"n": 0}

    def bad_key():
        calls["n"] += 1
        raise RuntimeError("Invalid API key")

    with pytest.raises(RuntimeError):
        ev.with_retry(bad_key, "test")
    assert calls["n"] == 1


# ---------- setup C sanity ----------


def test_c_problem_detects_half_runs():
    ok = {"status": "success", "scores": [6, 8], "warnings": []}
    assert ev.c_problem(ok) is None
    assert "failed" in ev.c_problem({"status": "failed", "error": "boom"})
    assert ev.c_problem({"status": "success", "scores": [], "warnings": []})
    critic = {
        "status": "success",
        "scores": [6],
        "warnings": ["The critic could not review this draft: 429"],
    }
    assert ev.c_problem(critic)
    revision = {
        "status": "success",
        "scores": [6],
        "warnings": ["Revision 1 failed, so the best earlier draft is used: x"],
    }
    assert ev.c_problem(revision)


def test_generate_c_rejects_incomplete_run_that_is_not_retryable(monkeypatch):
    bad = {
        "status": "success",
        "scores": [6],
        "report": "x",
        "warnings": ["The critic could not review this draft: bad request"],
        "revisions": 0,
    }
    monkeypatch.setattr(ev, "run_research_pipeline", lambda t, sources=None: bad)
    with pytest.raises(RuntimeError):
        ev.generate_c("t", SOURCES)


def test_generate_c_strips_sources_and_keeps_scores(monkeypatch):
    good = {
        "status": "success",
        "scores": [6, 9],
        "revisions": 1,
        "warnings": [],
        "report": BODY + "\n\n## Sources\n\n- **[1]** [A](https://a.com)",
    }
    monkeypatch.setattr(ev, "run_research_pipeline", lambda t, sources=None: good)
    made = ev.generate_c("t", SOURCES)
    assert "## Sources" not in made["body"]
    assert made["meta"] == {"scores": [6, 9], "revisions": 1}


# ---------- judge ----------


def test_judge_must_differ_from_writer(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setenv("JUDGE_PROVIDER", "groq")
    monkeypatch.delenv("JUDGE_MODEL", raising=False)
    with pytest.raises(SystemExit):
        ev.build_judge()


def test_judge_required(monkeypatch):
    monkeypatch.delenv("JUDGE_PROVIDER", raising=False)
    with pytest.raises(SystemExit):
        ev.build_judge()


def test_resolve_model_defaults_and_errors(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_MODEL", "m1")
    assert agents.resolve_model() == ("groq", "m1")
    assert agents.resolve_model("gemini", "g")[1] == "g"
    with pytest.raises(ValueError):
        agents.resolve_model("nope")


class FakeQuality:
    def invoke(self, inputs):
        assert "[" not in inputs["report"]  # the judge never sees markers
        return SimpleNamespace(
            depth=7, structure=8, balance=6, overall=7, comment="fine"
        )


def fake_judge():
    return {
        "id": ("gemini", "j"),
        "writer": ("groq", "w"),
        "quality": FakeQuality(),
        "verifier": FakeVerifier(),
    }


def test_judge_report_for_cited_and_plain_setups():
    b = ev.judge_report("B", BODY, SOURCES, fake_judge())
    assert b["quality"]["overall"] == 7
    assert b["citations"]["support_rate"] == 1.0
    assert b["uncited_sentences"] == 1
    a = ev.judge_report("A", ev.strip_for_judge(BODY), SOURCES, fake_judge())
    assert "pack" in a and a["pack"]["checked"] >= 1
    assert a["uncited_sentences"] >= 1 and "citations" not in a


def test_silent_factcheck_failure_is_an_error():
    class Broken:
        def invoke(self, inputs):
            raise RuntimeError("429 rate limit")

    with pytest.raises(RuntimeError):
        ev._fact_check(BODY, SOURCES, Broken())


# ---------- resume ----------


def test_run_topic_resumes_without_redoing_finished_work(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(ev, "_sleep", lambda s: None)
    counts = {"gather": 0, "A": 0, "B": 0, "C": 0}

    def gather(topic):
        counts["gather"] += 1
        return SOURCES, []

    def make(setup, fail_b_first=False):
        def generate(topic, sources):
            counts[setup] += 1
            if setup == "B" and fail_b_first and counts["B"] == 1:
                raise RuntimeError("boom")
            return {
                "body": BODY,
                "meta": {"scores": [6, 8], "revisions": 1} if setup == "C" else {},
            }

        return generate

    monkeypatch.setattr(ev, "gather_sources", gather)
    monkeypatch.setattr(
        ev, "GENERATORS", {"A": make("A"), "B": make("B", True), "C": make("C")}
    )

    ev.run_topic("Solid state batteries", fake_judge())  # B fails
    saved = json.loads((tmp_path / "solid-state-batteries.json").read_text())
    assert saved["setups"]["B"]["report"] is None
    assert saved["setups"]["A"]["judge"] and saved["setups"]["C"]["judge"]

    ev.run_topic("Solid state batteries", fake_judge())  # resume
    assert counts == {"gather": 1, "A": 1, "B": 2, "C": 1}
    saved = json.loads((tmp_path / "solid-state-batteries.json").read_text())
    assert all(saved["setups"][s]["judge"] for s in "ABC")


def test_config_change_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    ev.check_config({"writer": "x", "max_sources": 3})
    ev.check_config({"writer": "x", "max_sources": 3})  # same: fine
    with pytest.raises(SystemExit):
        ev.check_config({"writer": "x", "max_sources": 5})


# ---------- summary ----------


def _record(quality, support, scores=None):
    judge = {
        "quality": {
            "depth": quality,
            "structure": quality,
            "balance": quality,
            "overall": quality,
            "comment": "",
        },
        "words": 400,
        "uncited_sentences": 2,
        "cited_sentences": 8,
    }
    if support is not None:
        judge["citations"] = {
            "support_rate": support,
            "checked": 10,
            "supported": round(10 * support),
            "figures_not_found": 0,
        }
    else:
        judge["pack"] = {"support_rate": 0.5, "checked": 10, "supported": 5}
    return {
        "report": "x",
        "judge": judge,
        "meta": {"scores": scores, "revisions": len(scores) - 1} if scores else {},
    }


def test_summary_averages_and_head_to_head(tmp_path):
    for i, (qa, qb, qc, sb, sc) in enumerate(
        [(6, 7, 9, 0.8, 1.0), (6, 8, 8, 0.9, 0.9)]
    ):
        topic = {
            "topic": f"t{i}",
            "sources": [],
            "setups": {
                "A": _record(qa, None),
                "B": _record(qb, sb),
                "C": _record(qc, sc, [6, 9]),
            },
        }
        (tmp_path / f"t{i}.json").write_text(json.dumps(topic))
    # an incomplete topic must be left out of the averages
    (tmp_path / "bad.json").write_text(
        json.dumps({"topic": "bad", "sources": [], "setups": {"A": {"report": None}}})
    )

    s = summarize(tmp_path)
    assert s["topics_complete"] == 2 and s["topics_total"] == 3
    assert s["stats"]["A"]["quality"] == 6 and s["stats"]["C"]["quality"] == 8.5
    assert s["c_vs_b_quality"] == (1, 1, 0)
    assert s["c_vs_b_support"] == (1, 1, 0)
    text = render(s)
    assert "C: full ThinkMesh" in text and "Limitations" in text and "bad" in text


def test_clean_report_text_fixes_citation_styles_and_odd_characters():
    from backend.textclean import clean_report_text
    from backend.verify import CITATION

    text = "Costs fall【1】. Two sources【2, 3】. Tool style【1†L10-L12】. Both [4, 5] ok. A\u202fB\u2011C"
    cleaned = clean_report_text(text)
    assert "【" not in cleaned and "†" not in cleaned
    assert [int(n) for n in CITATION.findall(cleaned)] == [1, 2, 3, 1, 4, 5]
    assert "A B-C" in cleaned


def test_writer_and_reviser_chains_clean_their_output():
    from backend import agents

    assert "RunnableLambda" in repr(agents.writer_chain)
    assert "RunnableLambda" in repr(agents.reviser_chain)


def test_daily_limit_is_not_retried_and_raises_special_error(monkeypatch):
    waits = []
    monkeypatch.setattr(ev, "_sleep", waits.append)
    calls = {"n": 0}

    def quota():
        calls["n"] += 1
        raise RuntimeError("Error code: 429 - Rate limit exceeded: free-models-per-day")

    with pytest.raises(ev.DailyLimitReached):
        ev.with_retry(quota, "test")
    assert calls["n"] == 1 and waits == []
    # per-minute limits are still retried
    assert ev.is_retryable("429 rate limit per minute")
    assert not ev.is_retryable(
        "GenerateRequestsPerDayPerProjectPerModel-FreeTier quota"
    )


def test_run_topic_stops_on_daily_limit_and_keeps_the_written_report(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(ev, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(ev, "_sleep", lambda s: None)
    monkeypatch.setattr(ev, "gather_sources", lambda t: (SOURCES, []))
    monkeypatch.setattr(
        ev, "GENERATORS", {k: (lambda t, s: {"body": BODY, "meta": {}}) for k in "ABC"}
    )

    def limit(*args, **kwargs):
        raise ev.DailyLimitReached("free-models-per-day")

    monkeypatch.setattr(ev, "judge_report", limit)
    with pytest.raises(ev.DailyLimitReached):
        ev.run_topic("Daily limit topic", fake_judge())
    saved = json.loads((tmp_path / "daily-limit-topic.json").read_text())
    assert saved["setups"]["A"]["report"] and saved["setups"]["A"]["judge"] is None
    assert "B" not in saved["setups"]  # it stopped right away
