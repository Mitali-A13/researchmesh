from dotenv import load_dotenv

from backend.agents import critic_chain, writer_chain
from backend.sources import (
    format_sources_for_prompt,
    format_sources_section,
    gather_sources,
    public_view,
)

load_dotenv()


def run_research_pipeline(topic: str) -> dict:
    state = {
        "topic": topic,
        "sources": [],
        "warnings": [],
        "report": "",
        "feedback": "",
        "error": None,
        "status": "started",
    }

    try:
        # 1. Search + read pages (plain code, pages are read in parallel)
        sources, warnings = gather_sources(topic)
        state["sources"] = public_view(sources)
        state["warnings"] = warnings

        # 2. Writer: gets the numbered sources, must cite them as [1], [2] ...
        body = writer_chain.invoke(
            {"topic": topic, "research": format_sources_for_prompt(sources)}
        ).strip()

        if not body:
            raise ValueError("Report generation failed.")

        # 3. The Sources list is added by code, so URLs are always real
        state["report"] = f"{body}\n\n{format_sources_section(sources)}"

        # 4. Critic reviews the final report
        state["feedback"] = critic_chain.invoke({"report": state["report"]})
        state["status"] = "success"
        return state

    except Exception as e:
        state["error"] = str(e)
        state["status"] = "failed"
        return state
