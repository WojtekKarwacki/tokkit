# JSON Compaction Inference Eval Results

Evaluates whether `compact_json` output preserves enough information for an LLM to perform accurate inference — aggregation, cross-referencing, categorization, arithmetic, filtering, and path traversal on deeply nested data.

## Methodology

Each question is asked twice: once with **raw JSON** (control) and once with **compacted output** (treatment). Both answers are compared against a programmatically computed gold answer. If treatment fails but control passes, it's a compaction-caused accuracy loss.

- **Model:** Haiku (weakest Claude model — stress test for format readability)
- **Structured output:** JSON schema in system prompt, parsed from response
- **Comparison:** Typed (exact int match, float within 0.01, set equality for lists, ordered match for rankings/paths)

## Fixtures

| Fixture | Records | Nesting | Purpose |
|---------|---------|---------|---------|
| **org** | 1 org, 3 depts, 8 teams, 30+ members | 4 levels | Deeply nested objects with arrays |
| **ecommerce** | 15 orders | 4 levels | Heterogeneous (optional returns, varying items) |
| **sparse** | 20 records | 1 level | ~40% null fields — tests `;;;;;` runs |
| **large** | 120 orders (generated) | 4 levels | Scale — aggregation without key-name anchors |
| **tricky** | 15 records | 1 level | Semicolons, braces, unicode in values |

## Question Types

| Category | Questions | What it tests |
|----------|-----------|---------------|
| Cross-reference | Q2 | Comparing values across sibling nodes |
| Ranking + arithmetic | Q3, Q8 | Math across nesting levels |
| Categorization | Q4, Q9 | Inference from array contents |
| Path traversal | Q5 | Navigating parent-child nesting |
| Filtering | Q7, Q14 | Selecting records by nested field values |
| Null handling | Q10, Q11, Q12 | Aggregation/filtering with sparse data |
| Large-scale arithmetic | Q13 | Summing 120 orders x multiple line items |
| Large-scale cross-ref | Q15 | Filter + aggregate at scale |
| Escaping: semicolons | Q16, Q18 | Values containing the delimiter character |
| Escaping: numeric | Q17 | Distinguishing 404 from 40401 |

## Latest Results (2026-04-09)

| # | Fixture | Question | Control | Treatment | Savings |
|---|---------|----------|---------|-----------|---------|
| q2 | org | Team leads with fewer YOE than members | PASS | PASS | 81% |
| q3 | org | Rank departments by budget-per-person | PASS | PASS | 81% |
| q4 | org | Classify Engineering teams by stack | PASS | PASS | 81% |
| q5 | org | Trace carol's org path | FAIL | PASS | 81% |
| q7 | ecommerce | CA orders with no tracking events | PASS | PASS | 73% |
| q8 | ecommerce | Average order value | PASS | PASS | 73% |
| q9 | ecommerce | Classify orders by electronics content | PASS | PASS | 73% |
| q10 | sparse | Count records with non-null city | PASS | PASS | 72% |
| q11 | sparse | Records with at least one skill | PASS | PASS | 72% |
| q12 | sparse | Average salary (excluding nulls) | PASS | PASS | 72% |
| q13 | large | Total revenue across 120 orders | FAIL | FAIL | 76% |
| q14 | large | Count CA orders | PASS | PASS | 76% |
| q15 | large | Total CA refunds | PASS | PASS | 76% |
| q16 | tricky | Name with semicolons (T03) | PASS | PASS | 62% |
| q17 | tricky | Records where code == 404 (not 40401) | PASS | PASS | 62% |
| q18 | tricky | Tags with special chars (T07) | PASS | PASS | 62% |

### Summary

- **Control accuracy:** 14/16 (88%)
- **Treatment accuracy:** 15/16 (94%)
- **Accuracy delta:** +1 (treatment beat control)
- **Compaction-caused failures:** 0

### By Fixture Type

| Fixture | Control | Treatment | Token Savings |
|---------|---------|-----------|---------------|
| org | 3/4 | 4/4 | 81% |
| ecommerce | 3/3 | 3/3 | 73% |
| sparse | 3/3 | 3/3 | 72% |
| large | 2/3 | 2/3 | 76% |
| tricky | 3/3 | 3/3 | 62% |

### Notes on Failures

**Q13 (large-scale arithmetic):** Both control and treatment fail. Haiku cannot accurately sum `quantity * unit_price` across 120 orders with 1-5 line items each. This is a model arithmetic limitation, not a compaction issue. The gold answer is $491,889.15; haiku returns ~$490K-575K depending on the run.

**Q5 control failure:** Non-deterministic — haiku occasionally returns a slightly different path format. Treatment passed on this run.

## Bugs Found

**`_render_primitive` missing semicolon quoting (fixed in 3d3de08):** Scalar arrays containing strings with semicolons (e.g., `["special;chars", "{braces}"]`) were rendered without quoting: `[special;chars;{braces}]`. This made the output genuinely ambiguous — a parser (or LLM) couldn't distinguish 2 items from 3. Fixed by applying the same quoting logic from `_render_value` to `_render_primitive`.

## How to Run

```bash
# Deterministic data fidelity tests (no LLM, fast)
uv run pytest tests/json_tests/test_data_fidelity.py -v

# Full inference eval (requires Claude Code credentials)
uv run pytest -m inference tests/json_tests/test_inference_eval.py -v

# Override model (default: haiku)
TOKKIT_EVAL_MODEL=sonnet uv run pytest -m inference tests/json_tests/test_inference_eval.py -v
```
