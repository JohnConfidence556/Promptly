
import json

import pytest

from app.agents.planner import PlanError, parse_plan


VALID_PLAN = {
    "app_name": "Task Tracker",
    "summary": "A simple app for managing daily tasks.",
    "features": [
        "Add tasks",
        "Complete tasks",
    ],
    "visual_style_notes": "A clean blue-and-white interface.",
    "scope_status": "supported",
    "scope_note": "The requested features fit the browser-only scope.",
}


def test_parse_valid_json():
    plan = parse_plan(json.dumps(VALID_PLAN))

    assert plan.app_name == "Task Tracker"
    assert len(plan.features) == 2


def test_parse_invalid_json():
    with pytest.raises(PlanError, match="invalid JSON"):
        parse_plan('{"app_name":')


def test_parse_json_with_wrong_shape():
    incomplete_plan = {
        "app_name": "Task Tracker",
        "features": ["Add tasks"],
        "visual_style_notes": "A clean blue-and-white interface.",
    }

    with pytest.raises(PlanError, match="does not match the schema"):
        parse_plan(json.dumps(incomplete_plan))


def test_parse_json_array_instead_of_object():
    with pytest.raises(PlanError, match="not an object"):
        parse_plan(json.dumps([VALID_PLAN]))


def test_unexpected_fields_are_rejected():
    plan_with_extra_field = {
        **VALID_PLAN,
        "notes": "Unexpected field",
    }

    with pytest.raises(PlanError, match="does not match the schema"):
        parse_plan(json.dumps(plan_with_extra_field))
