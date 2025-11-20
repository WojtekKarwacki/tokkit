# Tokkit Markdown Search Token Savings Benchmark

**Fixtures:** 3 markdown documents (project README, API docs, CLAUDE.md)
**Date:** 2026-04-09

| # | Query | Tokkit (tokens) | Baseline (tokens) | Savings % | Ratio |
|---|-------|----------------:|------------------:|----------:|------:|
| 1 | Find auth-related sections (`authentication`) | 1,225 | 6,789 | 82.0% | 5.5x |
| 2 | Find testing documentation (`testing`) | 829 | 6,789 | 87.8% | 8.2x |
| 3 | Find deployment/Docker setup (`deployment docker`) | 1,024 | 6,789 | 84.9% | 6.6x |
| 4 | Find error handling docs (`error`) | 4,199 | 6,789 | 38.1% | 1.6x |
| 5 | Find WebSocket documentation (`websocket`) | 776 | 6,789 | 88.6% | 8.7x |
| | **Total** | **8,053** | **33,945** | **76.3%** | **4.2x** |

## Methodology

### What the baseline measures

The **Baseline** column is the total token cost of reading all 3 markdown documents in full for each query. This represents the cost when an agent reads entire files to find specific information.

The **Tokkit** column is the token cost of the `search_markdown` response, which returns only the matching sections with ranking metadata.

Each query is run against all 3 fixtures. Not every fixture will have matching content for every query — in those cases `search_markdown` returns the header tree (~50-100 tokens) instead of the full document.

*Token estimate: len(chars) / 4. Both paths use the same constant.*
