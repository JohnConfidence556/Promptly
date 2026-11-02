import re
from collections import Counter
from dataclasses import dataclass, field
from html.parser import HTMLParser

from app.schemas.architecture import Architecture

REQUIRED_FILES = ("index.html", "style.css", "script.js")

# Only these tags make the browser load something through src/href.
RESOURCE_TAGS = {
    "script", "link", "img", "iframe", "source", "video", "audio", "embed",
}

EXTERNAL_URL = re.compile(r"^(?:https?:)?//", re.IGNORECASE)

FORBIDDEN_JS_PATTERNS = {
    "fetch": r"\bfetch\s*\(",
    "XMLHttpRequest": r"\bXMLHttpRequest\b",
    "WebSocket": r"\bWebSocket\b",
    "eval": r"\beval\s*\(",
    "Function constructor": r"\bFunction\s*\(",
}

PLACEHOLDER_PATTERNS = [
    r"\brest of the code\b",
    r"\bexisting code\b",
    r"\bsame as before\b",
    r"\bcode continues here\b",
    r"\bimplementation goes here\b",
    r"\bto be implemented\b",
]

CSS_URL_PATTERNS = [
    re.compile(r"""url\(\s*["']?\s*((?:https?:)?//[^"')\s]+)""", re.IGNORECASE),
    re.compile(r"""@import\s+["']\s*((?:https?:)?//[^"'\s;]+)""", re.IGNORECASE),
]


@dataclass
class ValidationIssue:
    file: str
    code: str
    message: str


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.issues


class HTMLInspector(HTMLParser):
    """Collect IDs, classes, and resource links from HTML."""

    def __init__(self):
        super().__init__()
        self.ids: list[str] = []
        self.classes: list[str] = []
        self.resources: list[tuple[str, str, str]] = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)

        self.classes.extend((attributes.get("class") or "").split())

        for attribute in ("src", "href"):
            value = attributes.get(attribute)
            if value:
                self.resources.append((tag, attribute, value))


def _issue(file: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(file=file, code=code, message=message)


def _token_pattern(name: str) -> str:
    """Regex matching `name` as a whole token (not part of a longer name)."""
    return r"(?<![\w-])" + re.escape(name) + r"(?![\w-])"


def _normalize_local_path(value: str) -> str:
    """'./style.css?v=2#top' -> 'style.css'."""
    path = value.strip().split("?", 1)[0].split("#", 1)[0]
    return path.removeprefix("./")


def find_js_function_definitions(script: str) -> set[str]:
    patterns = [
        r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(",
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=",
    ]

    names: set[str] = set()
    for pattern in patterns:
        names.update(re.findall(pattern, script))
    return names


def find_js_referenced_ids(script: str) -> set[str]:
    """Find IDs used in getElementById and querySelector(All) calls."""
    ids = set(
        re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", script)
    )

    # Take the whole selector string, then pull every #id token out of it,
    # so "#display .digit" yields "display" and not "display .digit".
    selector_calls = re.findall(
        r"""querySelector(?:All)?\(\s*(["'])(.*?)\1""", script
    )
    for _quote, selector in selector_calls:
        ids.update(re.findall(r"#([A-Za-z_][\w-]*)", selector))

    return ids


def find_forbidden_apis(script: str) -> set[str]:
    return {
        name
        for name, pattern in FORBIDDEN_JS_PATTERNS.items()
        if re.search(pattern, script)
    }


def find_external_resources(inspector: HTMLInspector) -> list[tuple[str, str, str]]:
    return [
        (tag, attribute, value)
        for tag, attribute, value in inspector.resources
        if tag in RESOURCE_TAGS and EXTERNAL_URL.match(value.strip())
    ]


def find_css_external_urls(css: str) -> list[str]:
    urls: list[str] = []
    for pattern in CSS_URL_PATTERNS:
        urls.extend(pattern.findall(css))
    return urls


def _links_local_file(
    inspector: HTMLInspector, tag_name: str, attribute_name: str, filename: str
) -> bool:
    return any(
        tag == tag_name
        and attribute == attribute_name
        and _normalize_local_path(value) == filename
        for tag, attribute, value in inspector.resources
    )


def _check_required_files(files: dict[str, str]) -> list[ValidationIssue]:
    issues = []
    for filename in REQUIRED_FILES:
        if filename not in files:
            issues.append(_issue(filename, "missing_file", f"{filename} is missing."))
        elif not isinstance(files[filename], str):
            issues.append(
                _issue(filename, "invalid_file_content", f"{filename} must contain text.")
            )
    return issues


def _check_html(inspector: HTMLInspector, contract: Architecture) -> list[ValidationIssue]:
    issues = []
    id_counts = Counter(inspector.ids)

    for item in contract.element_ids:
        if id_counts[item.name] == 0:
            issues.append(
                _issue(
                    "index.html",
                    "missing_id",
                    f"index.html has no element with id '{item.name}'.",
                )
            )

    for element_id, count in sorted(id_counts.items()):
        if count > 1:
            issues.append(
                _issue(
                    "index.html",
                    "duplicate_id",
                    f"index.html contains duplicate ID '{element_id}' "
                    f"({count} occurrences); each ID must appear exactly once.",
                )
            )

    for tag, attribute, url in find_external_resources(inspector):
        issues.append(
            _issue(
                "index.html",
                "external_url",
                f"index.html loads external URL '{url}' in <{tag}> {attribute}. "
                "Use only local files.",
            )
        )

    if not _links_local_file(inspector, "link", "href", "style.css"):
        issues.append(
            _issue("index.html", "missing_stylesheet_link", "index.html does not link to style.css.")
        )

    if not _links_local_file(inspector, "script", "src", "script.js"):
        issues.append(
            _issue("index.html", "missing_script_link", "index.html does not link to script.js.")
        )

    return issues


def _check_script(
    script: str, html_ids: set[str] | None, contract: Architecture
) -> list[ValidationIssue]:
    issues = []
    defined = find_js_function_definitions(script)

    for item in contract.js_functions:
        if item.name not in defined:
            issues.append(
                _issue(
                    "script.js",
                    "missing_function",
                    f"script.js does not define contract function '{item.name}'.",
                )
            )

    # Skip this check when there is no HTML to compare against,
    # otherwise one missing file would create a flood of unknown-ID issues.
    if html_ids is not None:
        for element_id in sorted(find_js_referenced_ids(script) - html_ids):
            issues.append(
                _issue(
                    "script.js",
                    "unknown_html_id",
                    f"script.js references ID '{element_id}', "
                    "but index.html does not contain it.",
                )
            )

    for api in sorted(find_forbidden_apis(script)):
        issues.append(
            _issue(
                "script.js",
                "forbidden_api",
                f"script.js uses forbidden API '{api}'. Use local, offline logic instead.",
            )
        )

    return issues


def _check_css(css: str, contract: Architecture) -> list[ValidationIssue]:
    issues = []

    for item in contract.css_classes:
        pattern = r"(?<![\w-])\." + re.escape(item.name) + r"(?![\w-])"
        if not re.search(pattern, css):
            issues.append(
                _issue(
                    "style.css",
                    "missing_css_selector",
                    f"style.css has no selector for contract class '{item.name}'.",
                )
            )

    for url in find_css_external_urls(css):
        issues.append(
            _issue(
                "style.css",
                "external_url",
                f"style.css loads external URL '{url}'. Use only local resources.",
            )
        )

    return issues


def _check_classes_used(
    inspector: HTMLInspector, script: str, contract: Architecture
) -> list[ValidationIssue]:
    """A contract class must appear in the HTML or be added by script.js."""
    issues = []
    html_classes = set(inspector.classes)

    for item in contract.css_classes:
        used_in_html = item.name in html_classes
        used_in_script = bool(re.search(_token_pattern(item.name), script))

        if not used_in_html and not used_in_script:
            issues.append(
                _issue(
                    "index.html",
                    "missing_class",
                    f"Contract CSS class '{item.name}' is not used in "
                    "index.html or script.js.",
                )
            )

    return issues


def _check_placeholders(files: dict[str, str]) -> list[ValidationIssue]:
    issues = []

    for filename in REQUIRED_FILES:
        content = files.get(filename)
        if not isinstance(content, str):
            continue

        for pattern in PLACEHOLDER_PATTERNS:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                issues.append(
                    _issue(
                        filename,
                        "placeholder_text",
                        f"{filename} contains placeholder text '{match.group(0)}'. "
                        "Provide the complete implementation.",
                    )
                )

    return issues


def validate_files(files: dict[str, str], contract: Architecture) -> ValidationReport:
    """Validate generated files against the architecture contract.

    Returns ALL issues found, not just the first, so one retry can fix them.

    Limitations: JavaScript checks use regex, not a real JS parser. Regex can
    be fooled by comments and strings and can miss unusual or obfuscated
    syntax. These are MVP safeguards, not a security boundary or a syntax
    validator.
    """
    report = ValidationReport()
    report.issues.extend(_check_required_files(files))

    html = files.get("index.html")
    css = files.get("style.css")
    script = files.get("script.js")

    inspector = None
    if isinstance(html, str):
        inspector = HTMLInspector()
        inspector.feed(html)
        report.issues.extend(_check_html(inspector, contract))

    if isinstance(script, str):
        html_ids = set(inspector.ids) if inspector is not None else None
        report.issues.extend(_check_script(script, html_ids, contract))

    if isinstance(css, str):
        report.issues.extend(_check_css(css, contract))

    if inspector is not None and isinstance(script, str):
        report.issues.extend(_check_classes_used(inspector, script, contract))

    report.issues.extend(_check_placeholders(files))

    return report


def format_issues_for_model(report: ValidationReport) -> str:
    """Format all validation issues as a numbered list for the Coder."""
    return "\n".join(
        f"{index}. [{issue.file}] ({issue.code}) {issue.message}"
        for index, issue in enumerate(report.issues, start=1)
    )