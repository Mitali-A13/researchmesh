from sqlalchemy.orm import Session

from backend.db.models import ChatHistory, ReportCheck, ReportIteration


def save_report(db: Session, user_id: int, topic: str, result: dict) -> ChatHistory:
    """Save a finished report with its score history and citation-check numbers."""
    history = ChatHistory(
        user_id=user_id,
        topic=topic,
        report=result["report"],
        feedback=result["feedback"],
    )
    # the critic's score for every round
    history.iterations = [
        ReportIteration(round=number, score=score)
        for number, score in enumerate(result.get("scores", []), start=1)
    ]

    # the citation-check numbers
    verification = result.get("verification")
    if verification:
        history.check = ReportCheck(
            claims_total=verification["claims_total"],
            checked=verification["checked"],
            supported=verification["supported"],
            partial=verification["partial"],
            unsupported=verification["unsupported"],
            uncited_sentences=verification["uncited_sentences"],
            invalid_citations=len(verification["invalid_citations"]),
            unused_sources=len(verification["unused_sources"]),
            figures_not_found=verification["figures_not_found"],
            llm_used=verification["llm_used"],
        )

    db.add(history)
    db.commit()
    db.refresh(history)
    return history
