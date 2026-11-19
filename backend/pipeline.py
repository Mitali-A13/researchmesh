import os

from dotenv import load_dotenv

from backend.agents import critic_chain, reviser_chain, verifier_chain, writer_chain
from backend.graph import build_graph, run_graph
from backend.sources import (
    format_sources_for_prompt,
    format_sources_section,
    gather_sources,
    public_view,
)
from backend.verify import format_verification, verify_report

load_dotenv()

# What the app shows while a report is being made
STAGE_SEARCH = "Searching the web and reading sources"
STAGE_WRITE = "Writing the report"
STAGE_REVIEW = "Reviewing the draft"
STAGE_REVISE = "Revising the report"
STAGE_VERIFY = "Checking citations"


class _Announce:
    """Wraps a chain so progress is reported just before it runs.
    The graph only ever calls .invoke(), so nothing else has to change."""

    def __init__(self, chain, announce, stage):
        self.chain = chain
        self.announce = announce
        self.stage = stage

    def invoke(self, *args, **kwargs):
        self.announce(self.stage)
        return self.chain.invoke(*args, **kwargs)


def _ai_fact_check_enabled() -> bool:
    return os.getenv("VERIFY_WITH_LLM", "true").lower() in ("1", "true", "yes", "on")


def _format_feedback(result: dict) -> str:
    """Turn the best critique into the text card shown in the UI."""
    critique = result.get("best_critique")
    if critique is None:
        return "The critic could not review this report, so there is no score."

    scores = result.get("scores", [])
    lines = [f"Score: {critique.score}/10", ""]

    if len(scores) > 1:
        path = " → ".join(str(s) for s in scores)
        lines += [f"Review rounds: {len(scores)} (scores: {path})", ""]

    lines += ["Strengths:", ""]
    lines += [f"- {point}" for point in critique.strengths]
    lines += ["", "Areas to Improve:", ""]
    lines += [f"- {point}" for point in critique.improvements]
    lines += ["", f"Verdict: {critique.verdict}"]
    return "\n".join(lines)


def run_research_pipeline(
    topic: str,
    sources: list[dict] | None = None,
    on_stage=None,
) -> dict:
    """Run the whole pipeline.

    `sources` is only for the evaluation: it hands in a ready-made source list so
    that every setup is compared on the same pages. The app never passes it.

    `on_stage(text)` is called as the work moves on (searching, writing, reviewing,
    revising, checking citations). It is for progress display only: if it raises,
    the pipeline carries on.
    """

    def announce(stage: str) -> None:
        if on_stage is None:
            return
        try:
            on_stage(stage)
        except Exception:
            pass

    state = {
        "topic": topic,
        "sources": [],
        "warnings": [],
        "scores": [],
        "revisions": 0,
        "verification": None,
        "report": "",
        "feedback": "",
        "error": None,
        "status": "started",
    }

    try:
        # 1. Search + read pages (plain code, pages are read in parallel)
        announce(STAGE_SEARCH)
        if sources is None:
            sources, warnings = gather_sources(topic)
        else:
            warnings = []
        state["sources"] = public_view(sources)
        state["warnings"] = list(warnings)

        # 2. Write -> critique -> revise loop (LangGraph)
        sources_section = format_sources_section(sources)
        if on_stage is None:
            writer, reviser, critic = writer_chain, reviser_chain, critic_chain
        else:
            writer = _Announce(writer_chain, announce, STAGE_WRITE)
            reviser = _Announce(reviser_chain, announce, STAGE_REVISE)
            critic = _Announce(critic_chain, announce, STAGE_REVIEW)
        graph = build_graph(writer, reviser, critic)
        result = run_graph(
            graph, topic, format_sources_for_prompt(sources), sources_section
        )

        # 3. Use the best draft; the Sources list is added by code (real URLs only)
        body = result.get("best_draft") or result["draft"]
        state["report"] = f"{body}\n\n{sources_section}"
        state["feedback"] = _format_feedback(result)
        state["scores"] = result.get("scores", [])
        state["revisions"] = result.get("revisions", 0)
        state["warnings"] += result.get("notes", [])

        # 4. Citation check (never allowed to break the report)
        announce(STAGE_VERIFY)
        try:
            chain = verifier_chain if _ai_fact_check_enabled() else None
            verification = verify_report(body, sources, chain)
            state["verification"] = verification
            state["feedback"] += "\n\n" + format_verification(verification)
        except Exception as exc:
            state["warnings"].append(f"Citation check failed: {str(exc)[:120]}")

        state["status"] = "success"
        return state

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        return state
