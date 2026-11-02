# Promptly evaluation report

Model: `openai/gpt-oss-120b` · 2 prompts · generated 2026-10-31 13:08 UTC

## Summary

| Metric | Result |
|---|---|
| Builds that passed validation | 2 / 2 (100%) |
| Passed with no repairs (first attempt) | 1 / 2 (50%) |
| Average fix rounds per build | 0.5 |
| Median build time | 73.9 s |
| Median tokens per build | 13,340 |
| Total tokens | 26,681 |
| Share of time spent waiting on rate limits | 78% |

## Most common issues found on the first attempt

| Issue | Count |
|---|---|
| forbidden_api | 1 |

## Per prompt

| Prompt | Result | Fix rounds | Time | Tokens | First-attempt issues |
|---|---|---|---|---|---|
| calculator | PASS | 1 | 49 s | 14,624 | forbidden_api |
| todo | PASS | 0 | 99 s | 12,057 | none |
