from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.architecture import CssClass, ElementId, JsFunction


class FileEdit(BaseModel):
    """What to change in one file."""
    model_config = ConfigDict(extra="forbid")

    filename: Literal["index.html", "style.css", "script.js"]
    instruction: str = Field(min_length=1, max_length=600)


class EditPlan(BaseModel):
    """Which files an edit touches, and how the shared contract changes."""
    model_config = ConfigDict(extra="forbid")

    summary: str = Field(
        min_length=3,
        max_length=200,
        description="One short sentence describing the change.",
    )
    edits: list[FileEdit] = Field(
        min_length=1,
        max_length=3,
        description=(
            "Every file that may need to change. "
            "Include index.html and style.css for visual changes."
        ),
    )
    add_element_ids: list[ElementId] = Field(default_factory=list, max_length=10)
    add_css_classes: list[CssClass] = Field(default_factory=list, max_length=10)
    add_js_functions: list[JsFunction] = Field(default_factory=list, max_length=10)
    remove_names: list[str] = Field(
        default_factory=list,
        max_length=20,
        description="Names of existing IDs, classes or functions this change removes.",
    )

    @model_validator(mode="after")
    def each_file_at_most_once(self):
        counts = Counter(edit.filename for edit in self.edits)
        duplicated = sorted(name for name, count in counts.items() if count > 1)

        if duplicated:
            raise ValueError(f"Duplicate file edit(s): {', '.join(duplicated)}")

        return self