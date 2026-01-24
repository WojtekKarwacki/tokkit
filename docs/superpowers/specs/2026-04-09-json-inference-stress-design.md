# JSON Compaction Inference Eval — Stress Tests

Extension of the inference eval to cover edge cases where compaction is most likely to degrade LLM accuracy: weak models, sparse data, large scale, and ambiguous values.

## Motivation

The initial eval (9/9 on Sonnet) tests the happy path. These stress tests target the format's weaknesses:

1. **Weaker model (Haiku)** — less reasoning budget to parse dense semicolon-delimited rows
2. **Sparse/null data** — many empty fields produce `;;;;;;` runs where positional tracking breaks
3. **Large row count (120 rows)** — aggregation/filtering without key-name anchors at scale
4. **Ambiguous values** — semicolons, braces, numeric strings that stress the escaping scheme

## New Fixtures

### Sparse records (`sparse_records.json`)

20 records, same schema: `{id, name, email, city, state, age, role, skills, salary}`. ~40% of fields are null across records. Specific patterns:

- 4 records with null name
- 6 records with null city
- 5 records with empty skills array `[]`
- 3 records with null salary
- 2 records where almost everything is null (just id + one field)
- All records have `id` (never null — needed for identification)

Gold answers must handle nulls explicitly (count non-null, filter by presence).

### Large orders (`large_orders.json`)

120 e-commerce orders. Same schema as existing `ecommerce_orders.json`. Generated programmatically by a `generate_large_orders()` function in `eval_questions.py` to avoid a 50KB fixture file in git. The function is deterministic (seeded random) so gold answers are stable.

Distribution:
- 40% delivered, 25% shipped, 20% processing, 15% cancelled
- 30% ship to CA, rest spread across 10 states
- 20% have returns
- Line items: 1-5 per order, categories from existing set
- Prices: $5.99-$999.99 range

### Tricky values (`tricky_values.json`)

15 records testing escaping edge cases:

```
{id, name, email, description, code, tags, metadata}
```

Specific tricky values:
- Names with semicolons: `"O'Brien; Jr."`, `"test;user"`
- Descriptions with curly braces: `"Use {template} syntax"`, `"Config: {a: 1, b: 2}"`
- `code` field: mix of numbers (`404`, `3.14`, `10001`) and longer strings containing those numbers (`"40401"`, `"ERR-3.14-B"`, `"CODE10001X"`)
- Tags arrays with special chars: `["a;b", "c{d}"]`
- Empty string `""` vs null for same field across rows
- Unicode: `"café"`, `"naïve"`

## New Questions

### Sparse fixture

| # | Category | Question | Model | Gold |
|---|----------|----------|-------|------|
| Q10 | Null aggregation | How many records have a non-null city? | CountAnswer | Programmatic: count where city is not None |
| Q11 | Null filtering | Which people (by id) have at least one skill in their skills list? | ListAnswer | Programmatic: filter where skills is non-empty list |
| Q12 | Null arithmetic | What is the average salary of records that have a non-null salary? | NumericAnswer | Programmatic: mean of non-null salaries |

### Large-scale fixture

| # | Category | Question | Model | Gold |
|---|----------|----------|-------|------|
| Q13 | Large aggregation | What is the total revenue (sum of qty * unit_price across all line items in all orders)? | NumericAnswer | Programmatic sum |
| Q14 | Large filtering | How many orders were shipped to California (state CA)? | CountAnswer | Programmatic count |
| Q15 | Large cross-ref | What is the total refund amount for orders that shipped to CA? | NumericAnswer | Programmatic: filter CA orders, sum refunds |

### Tricky values fixture

| # | Category | Question | Model | Gold |
|---|----------|----------|-------|------|
| Q16 | Semicolon in value | What is the name of the record with id "3"? | ListAnswer (single item) | Exact name with semicolons |
| Q17 | String vs number | List the ids of all records where the code field equals 404 (as a number, not as part of a longer string like "40401"). | ListAnswer | Programmatic: filter where code == 404 |
| Q18 | Special chars | What are the tags for the record with id "7"? | ListAnswer | Exact tags including special chars |

## Multi-Model Parameterization

The `TestInferenceEval` class runs against both `sonnet` and `haiku`. Implementation:

- Module-level `EVAL_MODEL` replaced by a `pytest.fixture(params=["sonnet", "haiku"])` 
- Each test method receives the model via fixture
- `_ask_llm` takes model as parameter
- Results collection keyed by `(question_id, model)`
- Report shows side-by-side: sonnet accuracy vs haiku accuracy per question

This doubles the LLM calls: 18 questions x 2 models x 2 (control + treatment) = 72 calls total. At ~2-3s per Haiku call and ~5-10s per Sonnet call, total runtime ~8-12 minutes.

## File Changes

| File | Action |
|------|--------|
| `tests/json_tests/fixtures/sparse_records.json` | Create |
| `tests/json_tests/fixtures/tricky_values.json` | Create |
| `tests/json_tests/fixtures/eval_questions.py` | Modify: add Q10-Q18 gold functions, `generate_large_orders()`, new QUESTIONS entries |
| `tests/json_tests/conftest.py` | Modify: add sparse/tricky/large fixture loaders |
| `tests/json_tests/test_data_fidelity.py` | Modify: add fidelity tests for 3 new fixtures |
| `tests/json_tests/test_inference_eval.py` | Modify: add Q10-Q18 tests, multi-model parameterization, updated report |

## Report Format

Updated to show per-model results:

```
| # | Question | Sonnet Ctrl | Sonnet Treat | Haiku Ctrl | Haiku Treat | Savings |
```

Plus summary section:
- Per-model accuracy breakdown
- Which questions Haiku fails that Sonnet passes (compaction-sensitive questions)
- Per-fixture-type accuracy (original vs sparse vs large vs tricky)
