from pathlib import Path

import pytest

from app.agents.validator import format_issues_for_model, validate_files
from app.schemas.architecture import Architecture

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "calculator"


def contract_data():
    return {
        "element_ids": [
            {"name": "display", "purpose": "Shows the result"},
            {"name": "equals-btn", "purpose": "Calculates the result"},
        ],
        "css_classes": [
            {"name": "calculator", "purpose": "Calculator container"},
        ],
        "js_functions": [
            {"name": "calculateResult", "purpose": "Calculates the result"},
        ],
        "file_tasks": [
            {"filename": "index.html", "task": "Create HTML"},
            {"filename": "style.css", "task": "Style the app"},
            {"filename": "script.js", "task": "Implement behavior"},
        ],
    }


def good_files_dict():
    return {
        "index.html": (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            '  <link rel="stylesheet" href="style.css">\n'
            "</head>\n"
            "<body>\n"
            '  <div class="calculator">\n'
            '    <input id="display">\n'
            '    <button id="equals-btn">=</button>\n'
            "  </div>\n"
            '  <script src="script.js"></script>\n'
            "</body>\n"
            "</html>\n"
        ),
        "style.css": ".calculator { display: grid; }",
        "script.js": (
            "function calculateResult() {\n"
            '  const display = document.getElementById("display");\n'
            "  return display.value;\n"
            "}\n"
        ),
    }


def broken_files():
    """Several problems at once; also used by scripts/show_validator_output.py."""
    return {
        "index.html": (
            '<div class="calculator">\n'
            '  <input id="display">\n'
            "</div>\n"
        ),
        "style.css": "body { margin: 0; }",
        "script.js": 'fetch("/api");\ndocument.getElementById("equalsButton");\n',
    }


def contract_with_class(name):
    data = contract_data()
    data["css_classes"].append({"name": name, "purpose": "Added by JavaScript"})
    return Architecture.model_validate(data)


def codes(report):
    return [issue.code for issue in report.issues]


@pytest.fixture
def contract():
    return Architecture.model_validate(contract_data())


@pytest.fixture
def good_files():
    return good_files_dict()


def test_good_files_pass(contract, good_files):
    report = validate_files(good_files, contract)

    assert report.passed, format_issues_for_model(report)


def test_missing_html_file_is_reported(contract, good_files):
    del good_files["index.html"]

    report = validate_files(good_files, contract)

    assert any(
        issue.code == "missing_file" and issue.file == "index.html"
        for issue in report.issues
    )


def test_missing_html_does_not_flood_with_unknown_ids(contract, good_files):
    del good_files["index.html"]

    report = validate_files(good_files, contract)

    assert set(codes(report)) == {"missing_file"}


def test_missing_contract_id_is_reported(contract, good_files):
    good_files["index.html"] = good_files["index.html"].replace(
        '<button id="equals-btn">=</button>', ""
    )

    report = validate_files(good_files, contract)

    assert any(
        issue.code == "missing_id" and "equals-btn" in issue.message
        for issue in report.issues
    )


def test_duplicate_id_is_reported_once(contract, good_files):
    good_files["index.html"] += '<button id="display">Duplicate</button>'

    report = validate_files(good_files, contract)

    assert codes(report).count("duplicate_id") == 1
    assert any("display" in issue.message for issue in report.issues)


def test_missing_contract_function_is_reported(contract, good_files):
    good_files["script.js"] = "function somethingElse() {}"

    report = validate_files(good_files, contract)

    assert any(
        issue.code == "missing_function" and "calculateResult" in issue.message
        for issue in report.issues
    )


def test_unknown_id_in_script_is_reported(contract, good_files):
    good_files["script.js"] += '\ndocument.getElementById("equalsButton");'

    report = validate_files(good_files, contract)

    assert any(
        issue.code == "unknown_html_id" and "equalsButton" in issue.message
        for issue in report.issues
    )


def test_query_selector_with_descendant_is_not_a_false_positive(contract, good_files):
    good_files["script.js"] += "\ndocument.querySelector('#display .digit');"

    report = validate_files(good_files, contract)

    assert report.passed, format_issues_for_model(report)


def test_relative_dot_slash_links_are_accepted(contract, good_files):
    good_files["index.html"] = (
        good_files["index.html"]
        .replace('href="style.css"', 'href="./style.css"')
        .replace('src="script.js"', 'src="./script.js"')
    )

    report = validate_files(good_files, contract)

    assert report.passed, format_issues_for_model(report)


def test_class_added_by_script_is_accepted(good_files):
    contract = contract_with_class("active-operation")
    good_files["style.css"] += "\n.active-operation { color: red; }"
    good_files["script.js"] += '\ndocument.body.classList.add("active-operation");'

    report = validate_files(good_files, contract)

    assert report.passed, format_issues_for_model(report)


def test_class_used_nowhere_is_reported(good_files):
    contract = contract_with_class("active-operation")
    good_files["style.css"] += "\n.active-operation { color: red; }"

    report = validate_files(good_files, contract)

    assert "missing_class" in codes(report)


@pytest.mark.parametrize(
    "snippet",
    [
        'fetch("/data")',
        "new XMLHttpRequest()",
        'new WebSocket("ws://example.com")',
        'eval("1+1")',
        'new Function("return 1")()',
    ],
)
def test_forbidden_apis_are_reported(contract, good_files, snippet):
    good_files["script.js"] += "\n" + snippet

    report = validate_files(good_files, contract)

    assert "forbidden_api" in codes(report)


def test_external_script_is_reported(contract, good_files):
    good_files["index.html"] += '<script src="https://cdn.example.com/lib.js"></script>'

    report = validate_files(good_files, contract)

    assert "external_url" in codes(report)


def test_plain_link_to_external_site_is_allowed(contract, good_files):
    good_files["index.html"] += '<a href="https://example.com">Docs</a>'

    report = validate_files(good_files, contract)

    assert report.passed, format_issues_for_model(report)


def test_css_import_from_external_site_is_reported(contract, good_files):
    good_files["style.css"] = (
        '@import url("https://fonts.googleapis.com/css?family=Roboto");\n'
        ".calculator { display: grid; }"
    )

    report = validate_files(good_files, contract)

    assert any(
        issue.code == "external_url" and issue.file == "style.css"
        for issue in report.issues
    )


def test_css_data_url_is_allowed(contract, good_files):
    good_files["style.css"] += "\n.calculator { background: url(data:image/png;base64,AAAA); }"

    report = validate_files(good_files, contract)

    assert report.passed, format_issues_for_model(report)


def test_placeholder_text_is_reported(contract, good_files):
    good_files["script.js"] += "\n// rest of the code stays the same"

    report = validate_files(good_files, contract)

    assert "placeholder_text" in codes(report)


def test_missing_stylesheet_link_is_reported(contract, good_files):
    good_files["index.html"] = good_files["index.html"].replace(
        '<link rel="stylesheet" href="style.css">', ""
    )

    report = validate_files(good_files, contract)

    assert "missing_stylesheet_link" in codes(report)


def test_missing_script_link_is_reported(contract, good_files):
    good_files["index.html"] = good_files["index.html"].replace(
        '<script src="script.js"></script>', ""
    )

    report = validate_files(good_files, contract)

    assert "missing_script_link" in codes(report)


def test_missing_css_selector_is_reported(contract, good_files):
    good_files["style.css"] = "body { margin: 0; }"

    report = validate_files(good_files, contract)

    assert "missing_css_selector" in codes(report)


def test_all_issues_are_reported_together(contract):
    report = validate_files(broken_files(), contract)

    assert {
        "missing_id",
        "missing_stylesheet_link",
        "missing_script_link",
        "missing_function",
        "unknown_html_id",
        "forbidden_api",
        "missing_css_selector",
    } <= set(codes(report))
    assert len(report.issues) == 7


def test_issues_are_formatted_as_numbered_list(contract):
    report = validate_files(broken_files(), contract)

    lines = format_issues_for_model(report).splitlines()

    assert len(lines) == len(report.issues)
    assert lines[0].startswith("1. [index.html] (missing_id)")


def test_realistic_app_passes():
    files = {
        name: (FIXTURE_DIR / name).read_text(encoding="utf-8")
        for name in ("index.html", "style.css", "script.js")
    }
    contract = Architecture.model_validate(
        {
            "element_ids": [
                {"name": "main-container", "purpose": "Main container"},
                {"name": "display-area", "purpose": "Shows input and result"},
                {"name": "clear-btn", "purpose": "Clears the input"},
                {"name": "equals-btn", "purpose": "Computes the result"},
            ],
            "css_classes": [
                {"name": "button", "purpose": "Base button style"},
                {"name": "number-button", "purpose": "Digit buttons"},
                {"name": "operation-button", "purpose": "Operator buttons"},
                {"name": "control-button", "purpose": "Clear and equals"},
                {"name": "keypad-grid", "purpose": "Keypad layout"},
                {"name": "calculator", "purpose": "Calculator wrapper"},
                {"name": "active-operation", "purpose": "Added by JavaScript"},
            ],
            "js_functions": [
                {"name": "handleButtonClick", "purpose": "Routes button clicks"},
                {"name": "updateDisplay", "purpose": "Refreshes the display"},
                {"name": "clearDisplay", "purpose": "Resets state"},
                {"name": "computeResult", "purpose": "Evaluates the expression"},
                {"name": "handleKeyPress", "purpose": "Keyboard support"},
            ],
            "file_tasks": [
                {"filename": "index.html", "task": "Create HTML"},
                {"filename": "style.css", "task": "Style the app"},
                {"filename": "script.js", "task": "Implement behavior"},
            ],
        }
    )

    report = validate_files(files, contract)

    assert report.passed, format_issues_for_model(report)