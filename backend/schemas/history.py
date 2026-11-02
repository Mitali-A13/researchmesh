from pydantic import BaseModel


class MessageResponse(BaseModel):
    success: bool
    message: str


class HistoryItem(BaseModel):
    id: int
    topic: str
    created_at: str


class HistoryResponse(BaseModel):
    success: bool
    history: list[HistoryItem]


class HistoryDetailItem(BaseModel):
    id: int
    topic: str
    report: str
    feedback: str | None = None
    created_at: str


class SingleHistoryResponse(BaseModel):
    success: bool
    history: HistoryDetailItem
