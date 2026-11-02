import json

import pytest
from pydantic import ValidationError

from app.agents.editor import EditError, apply_edit_plan, parse_edit_plan
from app.schemas.architecture import Architecture
from app.schemas.edit_plan import EditPlan
from tests.test_validator import contract_data


def architecture():
    return Architecture.model_validate(contract_data())


def edit_plan_data(**overrides):
    data = {
        "summary": "Make the buttons green",
        "edits": [{"filename": "style.css", "instruction": "Make buttons green"}],
    }
    data.update(overrides)
    return data


def test_valid_edit_plan_is_parsed():
    plan = parse_edit_plan(json.dumps(edit_plan_data()))

    assert plan.edits[0].filename == "style.css"
    assert plan.add_element_ids == []
    assert plan.remove_names == []


@pytest.mark.parametrize(
    "raw, message",
    [
        ("{broken", "invalid JSON"),
        ("[]", "not an object"),
        (json.dumps({"unexpected": 1}), "does not match"),
    ],
)
def test_bad_edit_plans_are_rejected(raw, message):
    with pytest.raises(EditError, match=message):
        parse_edit_plan(raw)


def test_duplicate_file_edits_are_rejected():
    data = edit_plan_data(
        edits=[
            {"filename": "style.css", "instruction": "a"},
            {"filename": "style.css", "instruction": "b"},
        ]
    )

    with pytest.raises(ValidationError):
        EditPlan.model_validate(data)


def test_empty_edit_list_is_rejected():
    with pytest.raises(ValidationError):
        EditPlan.model_validate(edit_plan_data(edits=[]))


def test_apply_adds_new_contract_items():
    edit_plan = EditPlan.model_validate(
        edit_plan_data(
            add_element_ids=[{"name": "history-panel", "purpose": "Past results"}],
            add_js_functions=[{"name": "renderHistory", "purpose": "Draws history"}],
        )
    )

    result = apply_edit_plan(architecture(), edit_plan)

    assert [item.name for item in result.element_ids] == [
        "display",
        "equals-btn",
        "history-panel",
    ]
    assert [item.name for item in result.js_functions] == [
        "calculateResult",
        "renderHistory",
    ]


def test_apply_removes_named_items():
    edit_plan = EditPlan.model_validate(edit_plan_data(remove_names=["equals-btn"]))

    result = apply_edit_plan(architecture(), edit_plan)

    assert [item.name for item in result.element_ids] == ["display"]


def test_adding_an_existing_name_is_ignored():
    edit_plan = EditPlan.model_validate(
        edit_plan_data(add_element_ids=[{"name": "display", "purpose": "again"}])
    )

    result = apply_edit_plan(architecture(), edit_plan)

    assert [item.name for item in result.element_ids] == ["display", "equals-btn"]


def test_removing_every_element_id_is_reported():
    edit_plan = EditPlan.model_validate(
        edit_plan_data(remove_names=["display", "equals-btn"])
    )

    with pytest.raises(EditError, match="contract"):
        apply_edit_plan(architecture(), edit_plan)


def test_id_and_class_may_not_share_a_name():
    edit_plan = EditPlan.model_validate(
        edit_plan_data(add_css_classes=[{"name": "display", "purpose": "clash"}])
    )

    with pytest.raises(EditError):
        apply_edit_plan(architecture(), edit_plan)