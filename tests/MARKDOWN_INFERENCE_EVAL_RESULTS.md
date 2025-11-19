# Markdown Search Inference Eval Results

**Date:** 2026-04-10
**Models:** haiku
**Questions:** 21
**Total LLM calls:** 42 (21 questions x 2 control/treatment)

## Per-Question Results

| # | Fixture | Query | haiku Ctrl | haiku Treat | Control Tok | Treat Tok | Savings |
|---|---------|-------|---------|----------|------------|-----------|---------|
| md_q1 | project_readme. | `authentication OAuth` | PASS | PASS | 2,730 | 442 | 84% |
| md_q2 | project_readme. | `testing TestClient` | PASS | PASS | 2,730 | 412 | 85% |
| md_q3 | project_readme. | `deployment docker` | PASS | PASS | 2,730 | 389 | 86% |
| md_q4 | project_readme. | `CORS middleware` | PASS | PASS | 2,730 | 215 | 92% |
| md_q5 | project_readme. | `changelog versions` | PASS | PASS | 2,730 | 139 | 95% |
| md_q6 | api_documentati | `secret key prefix te` | PASS | PASS | 2,386 | 564 | 76% |
| md_q7 | api_documentati | `error types` | PASS | PASS | 2,386 | 174 | 93% |
| md_q8 | api_documentati | `pagination parameter` | PASS | PASS | 2,386 | 324 | 86% |
| md_q9 | api_documentati | `webhook endpoint eve` | PASS | PASS | 2,386 | 299 | 87% |
| md_q10 | api_documentati | `error codes card_dec` | PASS | PASS | 2,386 | 266 | 89% |
| md_q11 | claude_md.md | `authentication provi` | PASS | PASS | 1,673 | 156 | 91% |
| md_q12 | claude_md.md | `rate limiting` | PASS | PASS | 1,673 | 110 | 93% |
| md_q13 | claude_md.md | `database ORM` | PASS | PASS | 1,673 | 231 | 86% |
| md_q14 | claude_md.md | `background jobs retr` | PASS | PASS | 1,673 | 109 | 93% |
| md_q15 | claude_md.md | `deployment environme` | PASS | PASS | 1,673 | 421 | 75% |
| md_q16 | api_documentati | `webhook signature ve` | PASS | PASS | 2,386 | 249 | 90% |
| md_q17 | project_readme. | `CORS middleware conf` | PASS | PASS | 2,730 | 344 | 87% |
| md_q18 | project_readme. | `async testing pytest` | PASS | PASS | 2,730 | 144 | 95% |
| md_q19 | claude_md.md | `e2e tests playwright` | PASS | PASS | 1,673 | 75 | 96% |
| md_q20 | claude_md.md | `background jobs retr` | PASS | PASS | 1,673 | 109 | 93% |
| md_q21 | claude_md.md | `e2e tests framework` | PASS | PASS | 1,673 | 75 | 96% |

## Token Savings Summary

| Metric | Value |
|--------|-------|
| Total control tokens | 46,810 |
| Total treatment tokens | 5,247 |
| Total savings | 88.8% |
| Ratio | 8.9x |

## Accuracy Summary

**haiku:** Control 21/21 (100%), Treatment 21/21 (100%)

## Methodology

**Control:** LLM receives the full markdown document + question.
**Treatment:** LLM receives `search_markdown(doc, query)` output + question.

Both paths use the same model, system prompt, and question. Gold answers are computed deterministically from the fixture text. Token counts are estimated as `len(context) / 4`.

The eval proves that `search_markdown` returns enough context for the LLM to answer correctly while using significantly fewer tokens.