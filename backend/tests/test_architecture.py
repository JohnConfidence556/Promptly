import json

import pytest
from pydantic import ValidationError

from app.schemas.architecture import Architecture


def valid_architecture():
    return {
        "element_ids": [
            {"name": "display", "purpose": "Shows the calculator result"},
            {"name": "equals-btn", "purpose": "Calculates the result"},
        ],
        "css_classes": [
            {"name": "is-active", "purpose": "Indicates an active control"},
        ],
        "js_functions": [
            {"name": "calculateResult", "purpose": "Evaluates the expression"},
        ],
        "file_tasks": [
            {"filename": "index.html", "task": "Create the calculator markup."},
            {"filename": "style.css", "task": "Style the calculator interface."},
            {"filename": "script.js", "task": "Implement calculator behavior."},
        ],
    }


def test_valid_architecture_is_accepted():
    architecture = Architecture.model_validate(valid_architecture())
    assert len(architecture.file_tasks) == 3


@pytest.mark.parametrize("bad_id", ["my button", "Equals", "1button"])
def test_invalid_element_ids_are_rejected(bad_id):
    data = valid_architecture()
    data["element_ids"][0]["name"] = bad_id

    with pytest.raises(ValidationError):
        Architecture.model_validate(data)


@pytest.mark.parametrize("bad_class", ["Big Button", "Active", "2col"])
def test_invalid_css_class_names_are_rejected(bad_class):
    data = valid_architecture()
    data["css_classes"][0]["name"] = bad_class

    with pytest.raises(ValidationError):
        Architecture.model_validate(data)


@pytest.mark.parametrize(
    "bad_function",
    ["calculate_result", "CalculateResult", "1calc", "calc result"],
)
def test_invalid_js_function_names_are_rejected(bad_function):
    data = valid_architecture()
    data["js_functions"][0]["name"] = bad_function

    with pytest.raises(ValidationError):
        Architecture.model_validate(data)


def test_duplicate_element_ids_are_rejected():
    data = valid_architecture()
    data["element_ids"][1]["name"] = "display"

    with pytest.raises(ValidationError, match="Duplicate element ID"):
        Architecture.model_validate(data)


def test_duplicate_css_classes_are_rejected():
    data = valid_architecture()
    data["css_classes"].append(
        {"name": "is-active", "purpose": "Same name again"}
    )

    with pytest.raises(ValidationError, match="Duplicate CSS class"):
        Architecture.model_validate(data)


def test_duplicate_js_functions_are_rejected():
    data = valid_architecture()
    data["js_functions"].append(
        {"name": "calculateResult", "purpose": "Same name again"}
    )

    with pytest.raises(ValidationError, match="Duplicate JavaScript function"):
        Architecture.model_validate(data)


def test_id_and_class_cannot_share_a_name():
    data = valid_architecture()
    data["css_classes"][0]["name"] = "display"

    with pytest.raises(ValidationError, match="both an element ID and a CSS class"):
        Architecture.model_validate(data)


def test_missing_file_task_is_rejected():
    data = valid_architecture()
    data["file_tasks"].pop()

    with pytest.raises(ValidationError):
        Architecture.model_validate(data)


def test_duplicate_file_task_is_rejected():
    data = valid_architecture()
    data["file_tasks"][2]["filename"] = "index.html"

    with pytest.raises(ValidationError, match="Duplicate file task"):
        Architecture.model_validate(data)


def test_extra_field_is_rejected():
    data = valid_architecture()
    data["unexpected"] = "not allowed"

    with pytest.raises(ValidationError):
        Architecture.model_validate(data)


def test_schema_publishes_naming_patterns():
    # The model reads the JSON schema, so the naming rules must appear in it.
    # Three name fields (ID, class, function) means at least three patterns.
    schema_text = json.dumps(Architecture.model_json_schema())

    assert schema_text.count('"pattern"') >= 3