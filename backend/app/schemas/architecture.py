from collections import Counter
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Naming rules live HERE, on the fields, so Pydantic both enforces them
# and publishes them in the JSON schema the model reads.
KEBAB_CASE = r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
CAMEL_CASE = r"^[a-z][A-Za-z0-9]*$"

Purpose = Annotated[str, Field(min_length=1, max_length=200)]


class ElementId(BaseModel):
    """An HTML element ID shared across the three files."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=50,
        pattern=KEBAB_CASE,
        description="Lowercase kebab-case ID, e.g. 'result-display'.",
    )
    purpose: Purpose


class CssClass(BaseModel):
    """A CSS class shared by the HTML and CSS files."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=50,
        pattern=KEBAB_CASE,
        description="Lowercase kebab-case class name, e.g. 'number-button'.",
    )
    purpose: Purpose


class JsFunction(BaseModel):
    """A JavaScript function the script file must define."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        max_length=50,
        pattern=CAMEL_CASE,
        description="camelCase function name, e.g. 'handleKeyPress'.",
    )
    purpose: Purpose


class FileTask(BaseModel):
    """Instructions for generating one application file."""
    model_config = ConfigDict(extra="forbid")

    filename: Literal["index.html", "style.css", "script.js"]
    task: str = Field(min_length=1, max_length=2000)


class Architecture(BaseModel):
    """Shared contract for the three files in a generated web app."""
    model_config = ConfigDict(extra="forbid")

    element_ids: list[ElementId] = Field(min_length=1, max_length=30)
    css_classes: list[CssClass] = Field(max_length=30)
    js_functions: list[JsFunction] = Field(max_length=20)
    file_tasks: list[FileTask] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_contract(self):
        id_names = [item.name for item in self.element_ids]
        class_names = [item.name for item in self.css_classes]
        function_names = [item.name for item in self.js_functions]

        # 1. No duplicates inside each list.
        for label, names in (
            ("element ID", id_names),
            ("CSS class", class_names),
            ("JavaScript function", function_names),
        ):
            duplicates = [
                name for name, count in Counter(names).items() if count > 1
            ]
            if duplicates:
                raise ValueError(
                    f"Duplicate {label}(s): {', '.join(sorted(duplicates))}"
                )

        # 2. An ID and a class may not share a name (avoids '#display' vs '.display').
        overlap = set(id_names) & set(class_names)
        if overlap:
            raise ValueError(
                "These names are used as both an element ID and a CSS class: "
                f"{', '.join(sorted(overlap))}. Give them different names."
            )

        # 3. Exactly one task per required file.
        expected = {"index.html", "style.css", "script.js"}
        filenames = [item.filename for item in self.file_tasks]

        duplicated = [
            name for name, count in Counter(filenames).items() if count > 1
        ]
        if duplicated:
            raise ValueError(
                f"Duplicate file task(s): {', '.join(sorted(duplicated))}"
            )

        missing = expected - set(filenames)
        if missing:
            raise ValueError(
                f"Missing file task(s): {', '.join(sorted(missing))}"
            )

        return self