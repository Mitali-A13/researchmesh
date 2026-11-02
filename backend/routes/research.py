from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.db.models import ChatHistory, ReportIteration
from backend.routes.deps import get_current_user, get_db, get_db_user
from backend.schemas.research import ResearchRequest
from backend.services.pipeline_service import generate_research

router = APIRouter(tags=["Research"])


# Main pipeline route
@router.post("/research")
def research(
    data: ResearchRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    topic = data.topic.strip()

    result = generate_research(topic)

    if result["status"] == "failed":
        raise HTTPException(status_code=500, detail=result["error"])

    # Get current DB user
    user = get_db_user(current_user, db)

    # Save history (the report already contains its numbered Sources list)
    new_history = ChatHistory(
        user_id=user.id,
        topic=topic,
        report=result["report"],
        feedback=result["feedback"],
    )

    # Save the critic's score for every round
    new_history.iterations = [
        ReportIteration(round=number, score=score)
        for number, score in enumerate(result.get("scores", []), start=1)
    ]

    db.add(new_history)
    db.commit()
    db.refresh(new_history)

    return {"success": True, "data": result}
