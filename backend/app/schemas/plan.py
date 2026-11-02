
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

Feature = Annotated[str, Field(min_length=1, max_length=120)]


class Plan(BaseModel):
    """Structure description of a simple web application."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    app_name: str = Field(
        min_length=1,
        max_length=60,
        description="A short, descriptive name for the app.",
    )

    summary: str = Field(
        min_length=10,
        max_length=240,
        description="A one-sentence summary of the app.",
    )

    features: list[Feature] = Field(
        min_length=1,
        max_length=8,
        description="Between one and eight app features.",
    )

    visual_style_notes: str = Field(
        min_length=5,
        max_length=500,
        description="Notes on the app's colors, layout, and visual style.",
    )

    scope_status: Literal["supported", "redirected"]
    scope_note: str = Field(
        min_length=5,
        max_length=240,
        description="Explain the scope decision or the feasible alternative.",
)
