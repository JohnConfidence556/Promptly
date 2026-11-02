
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WriteFileArgs(BaseModel):
    """Validated arguments for the write_file tool."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    filename: Literal["index.html", "style.css", "script.js"] = Field(
        description="The exact name of the file to write."
    )

    content: str = Field(
        min_length=1,
        max_length=100 * 1024,
        description="The non-empty content to write to the file.",
    )
