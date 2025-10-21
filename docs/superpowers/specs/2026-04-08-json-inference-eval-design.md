# JSON Compaction Inference Eval

Tests whether `compact_json` output preserves enough information for an LLM to perform accurate inference — aggregation, cross-referencing, categorization, arithmetic, and path traversal on deeply nested data.

## Approach: Hybrid

Two test layers:

1. **Deterministic data fidelity** (`test_data_fidelity.py`) — no LLM, runs in default pytest. Verifies compacted output preserves all values needed for inference.
2. **LLM inference eval** (`test_inference_eval.py`) — calls Claude via `claude_agent_sdk`, marked `@pytest.mark.inference`. Compares accuracy on raw JSON vs compacted JSON against gold answers.

## File Layout

```
tests/json_tests/
├── test_compact_json.py          # existing
├── test_data_fidelity.py          # NEW
├── test_inference_eval.py         # NEW
└── fixtures/
    ├── org_complex.json           # copy of nested_complex.json
    ├── ecommerce_orders.json      # NEW
    └── eval_questions.py          # questions, gold answers, Pydantic models
```

## Fixtures

### Org data (existing)

The `nested_complex.json` fixture: Acme Corp with 3 departments (Engineering, Product, Sales), each with 2-4 teams, each team with 3-6 members. Members have name, role, YOE, skills array, timezone. 4 nesting levels.

### E-commerce orders (new)

~15 orders with:
- Order metadata: id, customer name, date, status
- Line items array: product name, quantity, unit price, category
- Shipping: address (nested), carrier, tracking events array (timestamp, status, location)
- Returns array (optional): item, reason, status, refund amount

4 nesting levels. Heterogeneous — some orders have returns, some don't. Tests missing-key handling in compaction.

## Questions & Response Models

### Pydantic response models

```python
class CountAnswer(BaseModel):
    count: int

class NumericAnswer(BaseModel):
    value: float

class ListAnswer(BaseModel):
    items: list[str]

class RankEntry(BaseModel):
    name: str
    value: float

class RankedAnswer(BaseModel):
    rankings: list[RankEntry]

class Classification(BaseModel):
    name: str
    category: str

class ClassificationAnswer(BaseModel):
    classifications: list[Classification]

class PathAnswer(BaseModel):
    path: list[str]
```

### Org fixture questions

| # | Category | Question | Model | Gold derivation |
|---|----------|----------|-------|-----------------|
| Q1 | Aggregation | How many people across all teams have "python" as a skill? | CountAnswer | Programmatic count |
| Q2 | Cross-reference | Which team leads have fewer YOE than at least one of their members? | ListAnswer | Programmatic compute |
| Q3 | Filter + arithmetic | Rank departments by budget-per-person (budget/headcount). Return name and ratio. | RankedAnswer | Programmatic compute |
| Q4 | Categorization | Classify each Engineering team as "data", "infra", or "app" based on their stack. | ClassificationAnswer | Hand-labeled |
| Q5 | Path traversal | Trace carol's position: team, department, and org name. | PathAnswer | Programmatic extract |

### E-commerce fixture questions

| # | Category | Question | Model | Gold derivation |
|---|----------|----------|-------|-----------------|
| Q6 | Aggregation | What is the total refund amount across all returned orders? | NumericAnswer | Programmatic sum |
| Q7 | Filter + cross-ref | Which orders shipped to California but have no tracking events? | ListAnswer | Programmatic filter |
| Q8 | Arithmetic | What is the average order value (sum of line_item qty * unit_price) across all orders? | NumericAnswer | Programmatic compute |
| Q9 | Categorization | Classify each order as "electronics", "mixed", or "non-electronics" based on line item categories. | ClassificationAnswer | Programmatic from categories |

## Deterministic Data Fidelity Tests

`test_data_fidelity.py` — no LLM, default pytest run.

Per fixture:
- All member/customer names present in compacted output
- All numeric values preserved exactly (no rounding, no scientific notation)
- Nested list contents intact (every skill, tracking event, line item)
- Schema header correctly represents nesting structure
- Missing/null values don't corrupt adjacent fields
- Special characters properly escaped

~10-15 assertions per fixture.

## LLM Inference Eval Tests

`test_inference_eval.py` — `@pytest.mark.inference`, runs with `pytest -m inference`.

### Flow per question

1. Load fixture JSON
2. Compute gold answer programmatically (or load hand-labeled)
3. Run `compact_json()` on fixture
4. Two LLM calls via `claude_agent_sdk.query()`:
   - **Control:** raw JSON in prompt -> structured answer
   - **Treatment:** compacted JSON in prompt -> structured answer
5. Compare both against gold
6. Assert treatment matches gold. Log if control also fails (question too hard, not compaction problem).

### Prompt template

```
Given the following data:

{data}

Answer this question: {question}
```

Minimal — no format hints. Structured output constraint via Pydantic `output_format` handles extraction.

### Comparison logic

- `CountAnswer`: exact int match
- `NumericAnswer`: float within 0.01 tolerance
- `ListAnswer`: `set(items) == set(gold)` (order-independent)
- `RankedAnswer`: ordered list, floats within 0.01 tolerance
- `ClassificationAnswer`: set of (name, category) tuples match
- `PathAnswer`: ordered list exact match

### Report

After all questions, generate markdown report showing:
- Per-question: control correct, treatment correct, token savings %
- Summary: overall accuracy control vs treatment, total tokens saved

Written to `tests/INFERENCE_EVAL_RESULTS.md`.

## Configuration

- Model: env var `TOKKIT_EVAL_MODEL`, default `"sonnet"`
- Dependency: `claude-agent-sdk` in dev/test deps only
- Marker registration in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "inference: LLM-backed inference accuracy eval (requires API key)",
]
```

- ~18 LLM calls total (9 questions x 2). Sequential, no concurrency control needed.
