from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.routes.deps import get_db, get_current_user, get_db_user

from backend.db.models import ChatHistory

from backend.schemas.history import (
    HistoryResponse,
    SingleHistoryResponse,
    MessageResponse,
)

router = APIRouter(tags=["History"])


@router.get("/history", response_model=HistoryResponse)
def get_history(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user(current_user, db)

    history = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
        .all()
    )

    output = []

    for item in history:
        output.append(
            {
                "id": item.id,
                "topic": item.topic,
                "created_at": item.created_at.isoformat(),
            }
        )

    return {"success": True, "history": output}


@router.get("/history/{history_id}", response_model=SingleHistoryResponse)
def get_single_history(
    history_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user(current_user, db)

    item = (
        db.query(ChatHistory)
        .filter(ChatHistory.id == history_id, ChatHistory.user_id == user.id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="History item not found.")

    return {
        "success": True,
        "history": {
            "id": item.id,
            "topic": item.topic,
            "report": item.report,
            "feedback": item.feedback,
            "created_at": item.created_at.isoformat(),
        },
    }


@router.delete("/history/{history_id}", response_model=MessageResponse)
def delete_history(
    history_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = get_db_user(current_user, db)

    item = (
        db.query(ChatHistory)
        .filter(ChatHistory.id == history_id, ChatHistory.user_id == user.id)
        .first()
    )

    if not item:
        raise HTTPException(status_code=404, detail="History item not found.")

    db.delete(item)
    db.commit()

    return {"success": True, "message": "History deleted successfully."}
