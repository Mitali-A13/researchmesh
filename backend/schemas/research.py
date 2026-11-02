from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="Research topic entered by the user",
    )


class ResearchResponse(BaseModel):
    success: bool
    data: dict
