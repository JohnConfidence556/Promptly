from evals import run_evals


def make_result(**overrides):
    result = {
        "id": "a",
        "category": "utility",
        "expect_scope": "supported",
        "status": "passed",
        "error": None,
        "fix_rounds": 0,
        "first_pass": True,
        "first_issue_codes": [],
        "scope_status": "supported",
        "app_name": "App",
        "duration_seconds": 50.0,
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "llm_calls": 5,
        "wait_seconds": 10.0,
        "steps": [],
        "browser": None,
        "finished_at": "2026-01-01T00:00:00+00:00",
    }
    result.update(overrides)
    return result


def test_prompt_set_is_well_formed():
    cases = run_evals.load_prompts()
    ids = [case["id"] for case in cases]

    assert len(cases) >= 15
    assert len(ids) == len(set(ids))
    assert all(case["category"] and 10 <= len(case["prompt"]) <= 2000 for case in cases)
    assert any(case.get("expect_scope") == "redirected" for case in cases)


def test_aggregate_computes_the_headline_numbers():
    results = [
        make_result(id="a"),
        make_result(
            id="b", fix_rounds=2, first_pass=False, duration_seconds=80.0,
            wait_seconds=30.0, prompt_tokens=3000, completion_tokens=1500,
            first_issue_codes=["forbidden_api", "missing_id"],
        ),
        make_result(
            id="c", status="failed", fix_rounds=2, first_pass=False,
            duration_seconds=110.0, wait_seconds=20.0, prompt_tokens=2000,
            completion_tokens=1000, first_issue_codes=["forbidden_api"],
        ),
    ]

    stats = run_evals.aggregate(results)

    assert stats["total"] == 3
    assert stats["passed"] == 2
    assert stats["first_pass"] == 1
    assert stats["avg_fix_rounds"] == 1.33
    assert stats["median_seconds"] == 80.0
    assert stats["median_tokens"] == 3000
    assert stats["total_tokens"] == 9000
    assert stats["wait_share"] == 25
    assert stats["issue_counts"]["forbidden_api"] == 2


def test_scope_and_browser_checks_are_counted():
    results = [
        make_result(
            id="a", expect_scope="redirected", scope_status="redirected",
            browser={"errors": [], "blank": False},
        ),
        make_result(
            id="b", expect_scope="redirected", scope_status="supported",
            browser={"errors": ["boom"], "blank": False},
        ),
        make_result(id="c"),
    ]

    stats = run_evals.aggregate(results)

    assert (stats["scope_total"], stats["scope_redirected"]) == (2, 1)
    assert (stats["browser_total"], stats["browser_ok"]) == (2, 1)


def test_report_contains_the_key_sections():
    report = run_evals.build_report(
        [
            make_result(id="a"),
            make_result(
                id="b", status="failed", error="boom\nmore", first_pass=False,
                first_issue_codes=["missing_id"],
            ),
        ]
    )

    assert "# Promptly evaluation report" in report
    assert "Builds that passed validation | 1 / 2 (50%)" in report
    assert "| missing_id | 1 |" in report
    assert "| a | PASS |" in report
    assert "| b | FAIL |" in report
    assert "- **b**: boom" in report


def test_report_handles_no_results():
    assert "0 prompts" in run_evals.build_report([])


def test_results_file_keeps_the_latest_result_per_prompt(monkeypatch, tmp_path):
    monkeypatch.setattr(run_evals, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(run_evals, "RESULTS_FILE", tmp_path / "results.jsonl")

    run_evals.append_result(make_result(id="a", status="failed"))
    run_evals.append_result(make_result(id="a", status="passed"))
    run_evals.append_result(make_result(id="b"))

    results = run_evals.load_results()

    assert {item["id"]: item["status"] for item in results} == {"a": "passed", "b": "passed"}