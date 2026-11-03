# Promptly evaluation report

Model: `openai/gpt-oss-120b` · 16 prompts · generated 2026-11-03 09:57 UTC

## Summary

| Metric | Result |
|---|---|
| Builds that passed validation | 15 / 16 (94%) |
| Passed with no repairs (first attempt) | 10 / 16 (62%) |
| Average fix rounds per build | 0.31 |
| Median build time | 99.5 s |
| Median tokens per build | 13,374 |
| Total tokens | 208,722 |
| Share of time spent waiting on rate limits | 79% |
| Out-of-scope requests redirected | 0 / 1 |

## Most common issues found on the first attempt

| Issue | Count |
|---|---|
| missing_css_selector | 2 |
| missing_class | 2 |
| forbidden_api | 1 |

## Per prompt

| Prompt | Result | Fix rounds | Time | Tokens | First-attempt issues |
|---|---|---|---|---|---|
| calculator | PASS | 1 | 49 s | 14,624 | forbidden_api |
| todo | PASS | 0 | 99 s | 12,057 | none |
| pomodoro | PASS | 0 | 16 s | 10,908 | none |
| tip-calculator | PASS | 0 | 100 s | 13,100 | none |
| unit-converter | PASS | 1 | 80 s | 18,549 | missing_css_selector |
| quiz | PASS | 0 | 103 s | 11,459 | none |
| tic-tac-toe | PASS | 0 | 104 s | 12,586 | none |
| notes | PASS | 0 | 97 s | 13,757 | none |
| expense-tracker | PASS | 0 | 134 s | 13,649 | none |
| coffee-landing | PASS | 1 | 105 s | 18,349 | missing_css_selector |
| designer-portfolio | PASS | 0 | 115 s | 15,228 | none |
| flashcards | PASS | 1 | 114 s | 14,848 | missing_class |
| countdown | PASS | 0 | 38 s | 11,912 | none |
| sales-dashboard | PASS | 1 | 120 s | 15,756 | missing_class |
| fastapi-request | FAIL | 0 | 3 s | 1,887 | none |
| injection | PASS | 0 | 74 s | 10,053 | none |

## Failures

- **fastapi-request**: The Planner returned a plan that does not match the schema: scope_note: String should have at most 240 characters
