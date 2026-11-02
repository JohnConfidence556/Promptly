
import pytest
from pydantic import ValidationError

from app.schemas.plan import Plan


VALID_PLAN = {
    "app_name": "Task Tracker",
    "summary": "A simple app for managing daily tasks.",
    "features": [
        "Add new tasks",
        "Mark tasks as complete",
        "Delete tasks",
    ],
    "visual_style_notes": "Clean blue-and-white layout with simple cards.",
    "scope_status": "supported",
    "scope_note": "The requested features fit the supported browser-only scope.",
}


def test_valid_plan_is_accepted():
    plan = Plan(**VALID_PLAN)

    assert plan.app_name == "Task Tracker"
    assert len(plan.features) == 3
    assert plan.scope_status == "supported"


def test_missing_required_field_is_rejected():
    data = VALID_PLAN.copy()
    data.pop("summary")

    with pytest.raises(ValidationError):
        Plan(**data)


def test_empty_features_list_is_rejected():
    data = {**VALID_PLAN, "features": []}

    with pytest.raises(ValidationError):
        Plan(**data)


def test_invalid_scope_status_is_rejected():
    data = {**VALID_PLAN, "scope_status": "unsupported"}

    with pytest.raises(ValidationError):
        Plan(**data)


def test_missing_scope_note_is_rejected():
    data = VALID_PLAN.copy()
    data.pop("scope_note")

    with pytest.raises(ValidationError):
        Plan(**data)
