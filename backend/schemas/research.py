from pydantic import BaseModel, Field, field_validator


class ResearchRequest(BaseModel):
    topic: str = Field(
        ...,
        min_length=3,
        max_length=300,
        description="Research topic entered by the user",
    )

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        value = " ".join(value.split())

        if len(value) < 3:
            raise ValueError("Topic must have at least 3 characters.")

        return value


class ResearchResponse(BaseModel):
    success: bool
    data: dict
