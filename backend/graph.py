"""The write -> critique -> revise loop, built with LangGraph.

        write --> critique --+--> (score is high enough, or no revisions left) --> END
                     ^       |
                     |       +--> revise
                     +-----------------+

Every round is scored, the best draft is kept, and a failure in the middle
of the loop never throws away a draft that already exists.
"""

import os
from typing import Any, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

load_dotenv()

TARGET_SCORE = int(
    os.getenv("TARGET_SCORE", "8")
)  # stop when the critic gives this or more
MAX_REVISIONS = int(os.getenv("MAX_REVISIONS", "2"))  # 0 = write once, critique once


class ResearchState(TypedDict, total=False):
    topic: str
    sources_text: str  # numbered sources handed to the writer
    sources_section: str  # the "## Sources" list (the critic can see it)
    draft: str  # latest draft
    critique: Any  # latest Critique, or None if the critic failed
    scores: list[int]  # one score per critique round
    revisions: int  # how many times we revised
    best_draft: str
    best_critique: Any
    best_score: int
    stop: bool
    notes: list[str]  # warnings for the user


def build_graph(
    writer_chain,
    reviser_chain,
    critic_chain,
    target_score: int | None = None,
    max_revisions: int | None = None,
):
    target = TARGET_SCORE if target_score is None else target_score
    limit = MAX_REVISIONS if max_revisions is None else max_revisions

    def write(state: ResearchState) -> dict:
        draft = writer_chain.invoke(
            {"topic": state["topic"], "research": state["sources_text"]}
        ).strip()
        if not draft:
            raise ValueError("Report generation failed.")
        return {
            "draft": draft,
            "revisions": 0,
            "scores": [],
            "notes": [],
            "stop": False,
        }

    def critique(state: ResearchState) -> dict:
        report = f"{state['draft']}\n\n{state.get('sources_section', '')}"
        try:
            result = critic_chain.invoke({"report": report})
            result.score
        except Exception as exc:
            notes = state.get("notes", []) + [
                f"The critic could not review this draft: {str(exc)[:120]}"
            ]
            return {"critique": None, "notes": notes}

        update = {
            "critique": result,
            "scores": state.get("scores", []) + [result.score],
        }
        # keep the best draft so a bad revision can never make the report worse
        if result.score > state.get("best_score", -1):
            update.update(
                best_draft=state["draft"], best_critique=result, best_score=result.score
            )
        return update

    def route_after_critique(state: ResearchState) -> str:
        result = state.get("critique")
        if result is None:
            return END
        if result.score >= target:
            return END
        if state.get("revisions", 0) >= limit:
            return END
        return "revise"

    def revise(state: ResearchState) -> dict:
        revisions = state.get("revisions", 0) + 1
        feedback = "\n".join(f"- {point}" for point in state["critique"].improvements)
        try:
            improved = reviser_chain.invoke(
                {
                    "topic": state["topic"],
                    "research": state["sources_text"],
                    "draft": state["draft"],
                    "feedback": feedback,
                }
            ).strip()
        except Exception as exc:
            notes = state.get("notes", []) + [
                f"Revision {revisions} failed, so the best earlier draft is used: {str(exc)[:120]}"
            ]
            return {"revisions": revisions, "notes": notes, "stop": True}

        if not improved:
            return {"revisions": revisions, "stop": True}
        return {"draft": improved, "revisions": revisions}

    def route_after_revise(state: ResearchState) -> str:
        return END if state.get("stop") else "critique"

    graph = StateGraph(ResearchState)
    graph.add_node("write", write)
    graph.add_node("critique", critique)
    graph.add_node("revise", revise)

    graph.add_edge(START, "write")
    graph.add_edge("write", "critique")
    graph.add_conditional_edges(
        "critique", route_after_critique, {"revise": "revise", END: END}
    )
    graph.add_conditional_edges(
        "revise", route_after_revise, {"critique": "critique", END: END}
    )

    app = graph.compile()
    app.max_revisions = limit  # used to size the recursion limit in run_graph
    return app


def run_graph(app, topic: str, sources_text: str, sources_section: str) -> dict:
    """Run the loop and return the final state."""
    limit = getattr(app, "max_revisions", MAX_REVISIONS)
    return app.invoke(
        {
            "topic": topic,
            "sources_text": sources_text,
            "sources_section": sources_section,
        },
        config={"recursion_limit": 10 + 4 * limit},
    )
