# Promptly evaluation report

Model: `openai/gpt-oss-120b` · 12 prompts · generated 2026-11-02 10:51 UTC

## Summary

| Metric | Result |
|---|---|
| Builds that passed validation | 7 / 12 (58%) |
| Passed with no repairs (first attempt) | 4 / 12 (33%) |
| Average fix rounds per build | 0.25 |
| Median build time | 53.5 s |
| Median tokens per build | 11,183 |
| Total tokens | 126,500 |
| Share of time spent waiting on rate limits | 79% |

## Most common issues found on the first attempt

| Issue | Count |
|---|---|
| missing_css_selector | 1 |
| missing_class | 1 |
| forbidden_api | 1 |

## Per prompt

| Prompt | Result | Fix rounds | Time | Tokens | First-attempt issues |
|---|---|---|---|---|---|
| pomodoro | PASS | 0 | 16 s | 10,908 | none |
| tip-calculator | PASS | 0 | 100 s | 13,100 | none |
| unit-converter | FAIL | 0 | 39 s | 6,356 | none |
| quiz | PASS | 0 | 103 s | 11,459 | none |
| tic-tac-toe | FAIL | 0 | 29 s | 5,629 | none |
| notes | FAIL | 0 | 27 s | 5,940 | none |
| expense-tracker | FAIL | 0 | 58 s | 6,266 | none |
| coffee-landing | PASS | 1 | 105 s | 18,349 | missing_css_selector |
| designer-portfolio | FAIL | 0 | 42 s | 6,964 | none |
| flashcards | PASS | 1 | 114 s | 14,848 | missing_class |
| calculator | PASS | 1 | 49 s | 14,624 | forbidden_api |
| todo | PASS | 0 | 99 s | 12,057 | none |

## Failures

- **unit-converter**: The Architect returned an architecture that does not match the schema: file_tasks: Field required
- **tic-tac-toe**: The Architect returned an architecture that does not match the schema: file_tasks.2.task: String should have at most 1000 characters
- **notes**: The Architect returned an architecture that does not match the schema: file_tasks.0.task: String should have at most 1000 characters; file_tasks.2.task: String should have at most 1000 characters
- **expense-tracker**: The Architect returned an architecture that does not match the schema: file_tasks.2.task: String should have at most 1000 characters
- **designer-portfolio**: The Architect returned an architecture that does not match the schema: file_tasks.0.task: String should have at most 1000 characters
