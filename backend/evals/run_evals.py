"""Run the evaluation set through the real pipeline and report how it performs.

Run from the backend folder:
    python -m evals.run_evals --limit 3       quick smoke test
    python -m evals.run_evals                 every prompt
    python -m evals.run_evals --resume        skip prompts that already have a result
    python -m evals.run_evals --fresh         forget old results first
    python -m evals.run_evals --browser       also open each app in headless Chromium
    python -m evals.run_evals --report-only   rebuild the report from saved results
"""

import argparse
import json
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.agents.graph import stream_build
from app.services import runlog, tracing

EVALS_DIR = Path(__file__).resolve().parent
PROMPTS_PATH = EVALS_DIR / "prompts.json"
RESULTS_DIR = EVALS_DIR / "results"
RESULTS_FILE = RESULTS_DIR / "results.jsonl"
REPORT_FILE = RESULTS_DIR / "report.md"


def load_prompts() -> list[dict]:
    return json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))


def load_results() -> list[dict]:
    """Saved results, keeping only the latest one for each prompt."""
    if not RESULTS_FILE.exists():
        return []

    latest: dict[str, dict] = {}
    for line in RESULTS_FILE.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            latest[record["id"]] = record

    return list(latest.values())


def append_result(record: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with RESULTS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def browser_check(files: dict[str, str]) -> dict:
    """Load the app in headless Chromium and report script errors or a blank page."""
    from playwright.sync_api import sync_playwright

    errors: list[str] = []
    blank = True

    try:
        with tempfile.TemporaryDirectory() as folder:
            for name, content in files.items():
                (Path(folder) / name).write_text(content, encoding="utf-8")

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on(
                    "console",
                    lambda message: errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.goto((Path(folder) / "index.html").as_uri())
                page.wait_for_timeout(500)
                blank = not page.inner_text("body").strip()
                browser.close()
    except Exception as exc:
        errors.append(f"Browser check failed: {exc}")

    return {"errors": errors[:5], "blank": blank}


def run_one(case: dict, time_limit: float, browser: bool) -> dict:
    started = time.monotonic()
    timeline: list[dict] = []
    final: dict = {}
    first_issue_codes: list[str] | None = None

    def now() -> float:
        return time.monotonic() - started

    def emit(event: dict) -> None:
        timeline.append({**event, "type": event.get("kind"), "t": now()})

    with tracing.observation("span", f"eval-{case['id']}", input={"prompt": case["prompt"]}):
        tracing.tag_trace(tags=["eval"])

        try:
            for step, update in stream_build(
                case["prompt"], None, time_limit=time_limit, emit=emit
            ):
                final.update(update)
                timeline.append({"type": "step", "step": step, "t": now()})

                if step == "validator" and first_issue_codes is None:
                    report = update.get("report")
                    first_issue_codes = [issue.code for issue in report.issues] if report else []
        except Exception as exc:  # one bad prompt must never stop the whole run
            final.update({"status": "failed", "error": f"Harness error: {exc}"})

    summary = runlog.summarize(timeline, now())
    plan = final.get("plan")
    status = final.get("status", "failed")
    fix_rounds = final.get("fix_rounds", 0)

    result = {
        "id": case["id"],
        "category": case["category"],
        "expect_scope": case.get("expect_scope", "supported"),
        "status": "passed" if status == "passed" else "failed",
        "error": final.get("error"),
        "fix_rounds": fix_rounds,
        "first_pass": status == "passed" and fix_rounds == 0,
        "first_issue_codes": first_issue_codes or [],
        "scope_status": plan.scope_status if plan else None,
        "app_name": plan.app_name if plan else None,
        "duration_seconds": summary["duration_seconds"],
        "prompt_tokens": summary["prompt_tokens"],
        "completion_tokens": summary["completion_tokens"],
        "llm_calls": summary["llm_calls"],
        "wait_seconds": summary["wait_seconds"],
        "steps": summary["steps"],
        "browser": None,
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }

    if browser and result["status"] == "passed":
        result["browser"] = browser_check(final["files"])

    return result


def _median(values: list[float]) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _pct(part: int, whole: int) -> str:
    return f"{round(100 * part / whole)}%" if whole else "n/a"


def aggregate(results: list[dict]) -> dict:
    total = len(results)
    token_counts = [r["prompt_tokens"] + r["completion_tokens"] for r in results]
    total_seconds = sum(r["duration_seconds"] for r in results)
    total_wait = sum(r["wait_seconds"] for r in results)

    scope_cases = [r for r in results if r["expect_scope"] == "redirected"]
    browser_runs = [r for r in results if r["browser"] is not None]
    browser_ok = [
        r for r in browser_runs if not r["browser"]["errors"] and not r["browser"]["blank"]
    ]

    return {
        "total": total,
        "passed": sum(1 for r in results if r["status"] == "passed"),
        "first_pass": sum(1 for r in results if r["first_pass"]),
        "avg_fix_rounds": round(sum(r["fix_rounds"] for r in results) / total, 2) if total else 0.0,
        "median_seconds": round(_median([r["duration_seconds"] for r in results]), 1),
        "median_tokens": int(_median(token_counts)),
        "total_tokens": sum(token_counts),
        "wait_share": round(100 * total_wait / total_seconds) if total_seconds else 0,
        "scope_total": len(scope_cases),
        "scope_redirected": sum(1 for r in scope_cases if r["scope_status"] == "redirected"),
        "browser_total": len(browser_runs),
        "browser_ok": len(browser_ok),
        "issue_counts": Counter(code for r in results for code in r["first_issue_codes"]),
    }


def build_report(results: list[dict]) -> str:
    stats = aggregate(results)
    total = stats["total"]

    lines = [
        "# Promptly evaluation report",
        "",
        f"Model: `{config.GROQ_MODEL}` · {total} prompts · "
        f"generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Builds that passed validation | {stats['passed']} / {total} ({_pct(stats['passed'], total)}) |",
        f"| Passed with no repairs (first attempt) | {stats['first_pass']} / {total} ({_pct(stats['first_pass'], total)}) |",
        f"| Average fix rounds per build | {stats['avg_fix_rounds']} |",
        f"| Median build time | {stats['median_seconds']} s |",
        f"| Median tokens per build | {stats['median_tokens']:,} |",
        f"| Total tokens | {stats['total_tokens']:,} |",
        f"| Share of time spent waiting on rate limits | {stats['wait_share']}% |",
    ]

    if stats["scope_total"]:
        lines.append(
            f"| Out-of-scope requests redirected | {stats['scope_redirected']} / {stats['scope_total']} |"
        )
    if stats["browser_total"]:
        lines.append(
            f"| Apps that load without errors (browser check) | {stats['browser_ok']} / {stats['browser_total']} |"
        )

    lines += ["", "## Most common issues found on the first attempt", ""]

    if stats["issue_counts"]:
        lines += ["| Issue | Count |", "|---|---|"]
        lines += [f"| {code} | {count} |" for code, count in stats["issue_counts"].most_common()]
    else:
        lines.append("No issues were found on first attempts.")

    lines += [
        "",
        "## Per prompt",
        "",
        "| Prompt | Result | Fix rounds | Time | Tokens | First-attempt issues |",
        "|---|---|---|---|---|---|",
    ]

    for r in results:
        outcome = "PASS" if r["status"] == "passed" else "FAIL"
        tokens = r["prompt_tokens"] + r["completion_tokens"]
        issues = ", ".join(r["first_issue_codes"]) or "none"
        lines.append(
            f"| {r['id']} | {outcome} | {r['fix_rounds']} | {r['duration_seconds']:.0f} s | {tokens:,} | {issues} |"
        )

    failures = [r for r in results if r["status"] != "passed"]
    if failures:
        lines += ["", "## Failures", ""]
        for r in failures:
            first_line = (r["error"] or "No error recorded.").splitlines()[0]
            lines.append(f"- **{r['id']}**: {first_line}")

    return "\n".join(lines) + "\n"


def write_report() -> Path:
    order = {case["id"]: index for index, case in enumerate(load_prompts())}
    results = sorted(load_results(), key=lambda item: order.get(item["id"], len(order)))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_FILE.write_text(build_report(results), encoding="utf-8")
    return REPORT_FILE


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Promptly evaluation set.")
    parser.add_argument("--limit", type=int, help="run only the first N prompts")
    parser.add_argument("--only", help="comma-separated prompt ids to run")
    parser.add_argument("--resume", action="store_true", help="skip prompts that already have results")
    parser.add_argument("--fresh", action="store_true", help="delete saved results first")
    parser.add_argument("--browser", action="store_true", help="also load each app in headless Chromium")
    parser.add_argument("--report-only", action="store_true", help="rebuild the report and stop")
    parser.add_argument("--time-limit", type=float, default=600.0, help="seconds allowed per build")
    args = parser.parse_args()

    if args.report_only:
        print(f"Report written to {write_report()}")
        return

    if args.browser:
        try:
            import playwright  # noqa: F401
        except ImportError:
            raise SystemExit(
                "The browser check needs Playwright:\n"
                "  pip install playwright\n"
                "  python -m playwright install chromium"
            )

    if args.fresh and RESULTS_FILE.exists():
        RESULTS_FILE.unlink()

    cases = load_prompts()
    if args.only:
        wanted = {name.strip() for name in args.only.split(",")}
        cases = [case for case in cases if case["id"] in wanted]
    if args.resume:
        done = {result["id"] for result in load_results()}
        cases = [case for case in cases if case["id"] not in done]
    if args.limit:
        cases = cases[: args.limit]

    print(f"Running {len(cases)} prompt(s) with model {config.GROQ_MODEL}.\n")

    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']} ...", flush=True)
        result = run_one(case, args.time_limit, args.browser)
        append_result(result)

        outcome = "PASS" if result["status"] == "passed" else "FAIL"
        print(
            f"    {outcome} · {result['fix_rounds']} fix round(s) · "
            f"{result['duration_seconds']:.0f} s · "
            f"{result['prompt_tokens'] + result['completion_tokens']:,} tokens\n",
            flush=True,
        )

    tracing.flush()
    print(f"Report written to {write_report()}")


if __name__ == "__main__":
    main()