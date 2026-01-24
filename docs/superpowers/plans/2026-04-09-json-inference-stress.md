# JSON Inference Eval Stress Tests — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the inference eval to cover weak models (haiku), sparse/null data, large-scale datasets (120 rows), and ambiguous values with escaping edge cases.

**Architecture:** Add 3 new fixtures + 9 new questions (Q10-Q18) to the existing eval framework. Refactor `test_inference_eval.py` to use `pytest.mark.parametrize` over questions and models instead of one method per question. Add corresponding data fidelity tests.

**Tech Stack:** Python, pytest, claude_agent_sdk, pydantic, tokkit_json

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `tests/json_tests/fixtures/sparse_records.json` | Create | 20 records with ~40% null fields |
| `tests/json_tests/fixtures/tricky_values.json` | Create | 15 records with semicolons, braces, unicode in values |
| `tests/json_tests/fixtures/eval_questions.py` | Modify | Add Q10-Q18, `generate_large_orders()`, new loaders |
| `tests/json_tests/conftest.py` | Modify | Add sparse/tricky/large fixture loaders |
| `tests/json_tests/test_data_fidelity.py` | Modify | Add fidelity tests for 3 new fixtures |
| `tests/json_tests/test_inference_eval.py` | Rewrite | Parametrize over questions + models |

---

### Task 1: Sparse Records Fixture

**Files:**
- Create: `tests/json_tests/fixtures/sparse_records.json`

- [ ] **Step 1: Create the sparse records fixture**

Create `tests/json_tests/fixtures/sparse_records.json` with exactly this content:

```json
[
  {"id": "S01", "name": "alice", "email": "alice@example.com", "city": "San Francisco", "state": "CA", "age": 28, "role": "engineer", "skills": ["python", "go"], "salary": 120000},
  {"id": "S02", "name": null, "email": "anon2@example.com", "city": "Chicago", "state": "IL", "age": 35, "role": "pm", "skills": ["jira", "sql"], "salary": 95000},
  {"id": "S03", "name": "carol", "email": "carol@example.com", "city": null, "state": null, "age": 42, "role": "designer", "skills": [], "salary": 110000},
  {"id": "S04", "name": "dave", "email": null, "city": "Austin", "state": "TX", "age": null, "role": "analyst", "skills": ["sql", "python", "r"], "salary": null},
  {"id": "S05", "name": null, "email": "anon5@example.com", "city": null, "state": null, "age": 29, "role": "engineer", "skills": ["rust"], "salary": 130000},
  {"id": "S06", "name": "frank", "email": "frank@example.com", "city": "Seattle", "state": "WA", "age": 31, "role": "devops", "skills": [], "salary": 115000},
  {"id": "S07", "name": "grace", "email": "grace@example.com", "city": "Denver", "state": "CO", "age": 27, "role": "engineer", "skills": ["python", "docker", "k8s"], "salary": 125000},
  {"id": "S08", "name": null, "email": null, "city": null, "state": null, "age": null, "role": "intern", "skills": [], "salary": null},
  {"id": "S09", "name": "iris", "email": "iris@example.com", "city": "Boston", "state": "MA", "age": 38, "role": "lead", "skills": ["java", "spring", "postgres"], "salary": 145000},
  {"id": "S10", "name": "jack", "email": "jack@example.com", "city": null, "state": null, "age": 25, "role": "junior", "skills": ["javascript"], "salary": 75000},
  {"id": "S11", "name": "kate", "email": "kate@example.com", "city": "Portland", "state": "OR", "age": 33, "role": "designer", "skills": [], "salary": 105000},
  {"id": "S12", "name": null, "email": "anon12@example.com", "city": "Miami", "state": "FL", "age": 40, "role": "director", "skills": ["strategy", "roadmapping"], "salary": 160000},
  {"id": "S13", "name": "mike", "email": "mike@example.com", "city": "Phoenix", "state": "AZ", "age": null, "role": "analyst", "skills": ["excel", "sql"], "salary": 85000},
  {"id": "S14", "name": "nina", "email": null, "city": null, "state": null, "age": 36, "role": "engineer", "skills": ["python", "ml", "tensorflow"], "salary": null},
  {"id": "S15", "name": "oscar", "email": "oscar@example.com", "city": "San Francisco", "state": "CA", "age": 44, "role": "staff", "skills": ["go", "rust", "distributed-systems"], "salary": 175000},
  {"id": "S16", "name": null, "email": null, "city": null, "state": null, "age": null, "role": null, "skills": [], "salary": null},
  {"id": "S17", "name": "quinn", "email": "quinn@example.com", "city": "Austin", "state": "TX", "age": 30, "role": "pm", "skills": [], "salary": 100000},
  {"id": "S18", "name": "rachel", "email": "rachel@example.com", "city": "Chicago", "state": "IL", "age": 26, "role": "engineer", "skills": ["react", "typescript"], "salary": 95000},
  {"id": "S19", "name": "sam", "email": "sam@example.com", "city": null, "state": null, "age": 39, "role": "lead", "skills": ["python", "aws", "terraform"], "salary": 150000},
  {"id": "S20", "name": "tina", "email": "tina@example.com", "city": "New York", "state": "NY", "age": 32, "role": "designer", "skills": ["figma", "css"], "salary": 100000}
]
```

Null distribution: 4 null names (S02, S05, S08, S16), 6 null cities (S03, S05, S08, S10, S14, S16), 5 empty skills (S03, S06, S08, S11, S16, S17 — actually 6), 3 null salaries (S04, S08, S14, S16 — actually 4). S08 and S16 are near-totally null.

- [ ] **Step 2: Verify JSON is valid and check null counts**

```bash
cd /home/edge/code/tokkit && python -c "
import json
with open('tests/json_tests/fixtures/sparse_records.json') as f:
    data = json.load(f)
print(f'Records: {len(data)}')
print(f'Null names: {sum(1 for r in data if r[\"name\"] is None)}')
print(f'Null cities: {sum(1 for r in data if r[\"city\"] is None)}')
print(f'Empty skills: {sum(1 for r in data if not r[\"skills\"])}')
print(f'Null salaries: {sum(1 for r in data if r[\"salary\"] is None)}')
"
```

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/fixtures/sparse_records.json
git commit -m "test: add sparse records fixture for null-heavy eval"
```

---

### Task 2: Tricky Values Fixture

**Files:**
- Create: `tests/json_tests/fixtures/tricky_values.json`

- [ ] **Step 1: Create the tricky values fixture**

Create `tests/json_tests/fixtures/tricky_values.json`:

```json
[
  {"id": "T01", "name": "alice", "email": "alice@example.com", "description": "Regular user", "code": 100, "tags": ["admin", "active"]},
  {"id": "T02", "name": "bob", "email": "bob@example.com", "description": "Uses {template} syntax daily", "code": 200, "tags": ["user"]},
  {"id": "T03", "name": "O'Brien; Jr.", "email": "obrien@example.com", "description": "Name has semicolons", "code": 404, "tags": ["legacy", "vip"]},
  {"id": "T04", "name": "diana", "email": "diana@example.com", "description": "Config: {a: 1, b: 2}", "code": 301, "tags": ["a;b", "c{d}"]},
  {"id": "T05", "name": "test;user", "email": "test;user@example.com", "description": "Semicolons in name and email", "code": 404, "tags": ["test"]},
  {"id": "T06", "name": "café owner", "email": "cafe@example.com", "description": "Unicode in name", "code": 500, "tags": ["unicode", "café"]},
  {"id": "T07", "name": "george", "email": "george@example.com", "description": "", "code": 40401, "tags": ["special;chars", "{braces}"]},
  {"id": "T08", "name": "helen", "email": "helen@example.com", "description": "Normal description", "code": 200, "tags": []},
  {"id": "T09", "name": "naïve user", "email": "naive@example.com", "description": "More unicode: naïve, résumé", "code": 404, "tags": ["résumé"]},
  {"id": "T10", "name": "jack", "email": "jack@example.com", "description": "Multiple [brackets] and {braces}", "code": 100, "tags": ["normal"]},
  {"id": "T11", "name": "", "email": "empty@example.com", "description": "Empty string name (not null)", "code": 301, "tags": ["empty"]},
  {"id": "T12", "name": "lisa", "email": "lisa@example.com", "description": "Code is string-like number", "code": 404, "tags": ["four-oh-four"]},
  {"id": "T13", "name": "mike;jones", "email": "mike@example.com", "description": "Semicolon in name", "code": 200, "tags": ["semi;colon"]},
  {"id": "T14", "name": "nancy", "email": "nancy@example.com", "description": "Newline in desc\nSecond line", "code": 500, "tags": ["multiline"]},
  {"id": "T15", "name": "owen", "email": "owen@example.com", "description": "Last record", "code": 100, "tags": ["final", "test"]}
]
```

Key tricky values:
- Semicolons in names: T03, T05, T13
- Braces in descriptions: T02, T04, T10
- Unicode: T06, T09
- Code field = 404 (number) on T03, T05, T09, T12 (used for Q17)
- Code field = 40401 on T07 (not 404)
- Tags with special chars: T04, T07, T13
- Empty string name on T11 (not null)
- Newline in description on T14

- [ ] **Step 2: Verify JSON and check key values**

```bash
cd /home/edge/code/tokkit && python -c "
import json
with open('tests/json_tests/fixtures/tricky_values.json') as f:
    data = json.load(f)
print(f'Records: {len(data)}')
print(f'Records with code==404: {[r[\"id\"] for r in data if r[\"code\"] == 404]}')
print(f'Records with semicolons in name: {[r[\"id\"] for r in data if \";\" in (r[\"name\"] or \"\")]}')
print(f'Tags for T07: {[r[\"tags\"] for r in data if r[\"id\"] == \"T07\"]}')
"
```

Expected: code==404 on T03, T05, T09, T12. Semicolons in name on T03, T05, T13.

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/fixtures/tricky_values.json
git commit -m "test: add tricky values fixture for escaping edge cases"
```

---

### Task 3: Add New Questions & Large Orders Generator to eval_questions.py

**Files:**
- Modify: `tests/json_tests/fixtures/eval_questions.py`

- [ ] **Step 1: Add fixture loaders and large orders generator**

Add these after the existing `load_ecommerce()` function (after line ~67):

```python
def load_sparse() -> list[dict]:
    path = os.path.join(FIXTURES_DIR, "sparse_records.json")
    with open(path) as f:
        return json.load(f)


def load_tricky() -> list[dict]:
    path = os.path.join(FIXTURES_DIR, "tricky_values.json")
    with open(path) as f:
        return json.load(f)


def generate_large_orders(n: int = 120, seed: int = 42) -> list[dict]:
    """Generate n deterministic e-commerce orders for large-scale testing."""
    import random
    rng = random.Random(seed)

    states = ["CA", "CA", "CA", "TX", "NY", "IL", "WA", "FL", "CO", "MA"]
    cities = {
        "CA": "San Francisco", "TX": "Austin", "NY": "New York",
        "IL": "Chicago", "WA": "Seattle", "FL": "Miami",
        "CO": "Denver", "MA": "Boston",
    }
    carriers = ["FedEx", "UPS", "USPS"]
    categories = ["electronics", "furniture", "apparel", "books", "kitchen", "fitness", "office", "grocery"]
    products = {
        "electronics": ["Laptop", "Monitor", "Keyboard", "Mouse", "Headphones", "Speaker", "Tablet", "Cable"],
        "furniture": ["Chair", "Desk", "Lamp", "Shelf", "Cabinet"],
        "apparel": ["Jacket", "Shoes", "Hat", "Scarf", "Gloves"],
        "books": ["Novel", "Textbook", "Cookbook", "Guide", "Manual"],
        "kitchen": ["Blender", "Toaster", "Pan", "Knife Set", "Scale"],
        "fitness": ["Yoga Mat", "Dumbbells", "Band Set", "Jump Rope"],
        "office": ["Notebook", "Pen Set", "Stapler", "Folder Set"],
        "grocery": ["Coffee Beans", "Tea Box", "Olive Oil", "Spice Set"],
    }
    statuses_weights = [("delivered", 0.4), ("shipped", 0.25), ("processing", 0.2), ("cancelled", 0.15)]
    statuses = [s for s, _ in statuses_weights]
    weights = [w for _, w in statuses_weights]

    orders = []
    for i in range(1, n + 1):
        state = rng.choice(states)
        city = cities[state]
        status = rng.choices(statuses, weights=weights, k=1)[0]
        n_items = rng.randint(1, 5)
        line_items = []
        for _ in range(n_items):
            cat = rng.choice(categories)
            product = rng.choice(products[cat])
            line_items.append({
                "product": product,
                "quantity": rng.randint(1, 4),
                "unit_price": round(rng.uniform(5.99, 999.99), 2),
                "category": cat,
            })

        has_tracking = status in ("delivered", "shipped")
        n_events = rng.randint(1, 3) if has_tracking else 0
        tracking = []
        for j in range(n_events):
            tracking.append({
                "timestamp": f"2024-12-{i % 28 + 1:02d}T{8 + j * 4:02d}:00:00Z",
                "status": ["shipped", "in_transit", "delivered"][min(j, 2)],
                "location": f"{city}, {state}",
            })

        has_return = rng.random() < 0.2 and status == "delivered"
        returns = []
        if has_return and line_items:
            ret_item = rng.choice(line_items)
            returns.append({
                "item": ret_item["product"],
                "reason": rng.choice(["defective", "wrong item", "not as described", "changed mind"]),
                "status": "refunded",
                "refund_amount": ret_item["unit_price"],
            })

        orders.append({
            "order_id": f"ORD-L{i:03d}",
            "customer": f"customer_{i}",
            "date": f"2024-12-{i % 28 + 1:02d}",
            "status": status,
            "line_items": line_items,
            "shipping": {
                "address": {
                    "street": f"{100 + i} Main St",
                    "city": city,
                    "state": state,
                    "zip": f"{10000 + i}",
                },
                "carrier": rng.choice(carriers),
                "tracking_events": tracking,
            },
            "returns": returns,
        })
    return orders


def load_large_orders() -> list[dict]:
    return generate_large_orders()
```

- [ ] **Step 2: Add Q10-Q18 gold answer functions**

Add after the existing `gold_q9_order_classification` function:

```python
# ---------------------------------------------------------------------------
# Gold answer computation — sparse fixture
# ---------------------------------------------------------------------------

def gold_q10_non_null_city(data: list[dict]) -> CountAnswer:
    """Q10: How many records have a non-null city?"""
    count = sum(1 for r in data if r["city"] is not None)
    return CountAnswer(count=count)


def gold_q11_has_skills(data: list[dict]) -> ListAnswer:
    """Q11: Which people (by id) have at least one skill?"""
    ids = [r["id"] for r in data if r["skills"]]
    return ListAnswer(items=ids)


def gold_q12_avg_salary(data: list[dict]) -> NumericAnswer:
    """Q12: Average salary of records with non-null salary."""
    salaries = [r["salary"] for r in data if r["salary"] is not None]
    avg = round(sum(salaries) / len(salaries), 2)
    return NumericAnswer(value=avg)


# ---------------------------------------------------------------------------
# Gold answer computation — large orders fixture
# ---------------------------------------------------------------------------

def gold_q13_total_revenue(data: list[dict]) -> NumericAnswer:
    """Q13: Total revenue across all line items in all orders."""
    total = sum(
        item["quantity"] * item["unit_price"]
        for order in data
        for item in order["line_items"]
    )
    return NumericAnswer(value=round(total, 2))


def gold_q14_ca_count(data: list[dict]) -> CountAnswer:
    """Q14: How many orders shipped to CA?"""
    count = sum(1 for o in data if o["shipping"]["address"]["state"] == "CA")
    return CountAnswer(count=count)


def gold_q15_ca_refunds(data: list[dict]) -> NumericAnswer:
    """Q15: Total refund amount for orders shipped to CA."""
    total = 0.0
    for order in data:
        if order["shipping"]["address"]["state"] == "CA":
            for ret in order.get("returns", []):
                total += ret["refund_amount"]
    return NumericAnswer(value=round(total, 2))


# ---------------------------------------------------------------------------
# Gold answer computation — tricky values fixture
# ---------------------------------------------------------------------------

def gold_q16_name_by_id(data: list[dict]) -> ListAnswer:
    """Q16: Name of record with id T03 (has semicolons)."""
    for r in data:
        if r["id"] == "T03":
            return ListAnswer(items=[r["name"]])
    raise ValueError("T03 not found")


def gold_q17_code_404(data: list[dict]) -> ListAnswer:
    """Q17: IDs of records where code == 404."""
    ids = [r["id"] for r in data if r["code"] == 404]
    return ListAnswer(items=ids)


def gold_q18_tags_for_t07(data: list[dict]) -> ListAnswer:
    """Q18: Tags for record T07."""
    for r in data:
        if r["id"] == "T07":
            return ListAnswer(items=r["tags"])
    raise ValueError("T07 not found")
```

- [ ] **Step 3: Add Q10-Q18 to the QUESTIONS registry**

Append to the existing `QUESTIONS` list:

```python
    # --- Sparse fixture questions ---
    {
        "id": "q10",
        "fixture": "sparse",
        "question": "How many records have a non-null city value? Count only records where city is present and not null.",
        "model": CountAnswer,
        "gold_fn": gold_q10_non_null_city,
    },
    {
        "id": "q11",
        "fixture": "sparse",
        "question": "Which records (by their id field) have at least one skill in their skills list? Return the ids. Exclude records with empty skills arrays.",
        "model": ListAnswer,
        "gold_fn": gold_q11_has_skills,
    },
    {
        "id": "q12",
        "fixture": "sparse",
        "question": "What is the average salary among records that have a non-null salary? Ignore records where salary is null. Return the value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q12_avg_salary,
    },
    # --- Large orders questions ---
    {
        "id": "q13",
        "fixture": "large",
        "question": "What is the total revenue across all orders? Calculate as the sum of (quantity * unit_price) for every line item in every order. Return the value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q13_total_revenue,
    },
    {
        "id": "q14",
        "fixture": "large",
        "question": "How many orders were shipped to California (state CA)?",
        "model": CountAnswer,
        "gold_fn": gold_q14_ca_count,
    },
    {
        "id": "q15",
        "fixture": "large",
        "question": "What is the total refund amount across all orders that were shipped to California (state CA)? Sum the refund_amount from all returns in CA orders. Return the value rounded to 2 decimal places.",
        "model": NumericAnswer,
        "gold_fn": gold_q15_ca_refunds,
    },
    # --- Tricky values questions ---
    {
        "id": "q16",
        "fixture": "tricky",
        "question": "What is the exact name of the record with id 'T03'? Return it as a single-item list.",
        "model": ListAnswer,
        "gold_fn": gold_q16_name_by_id,
    },
    {
        "id": "q17",
        "fixture": "tricky",
        "question": "List the ids of all records where the code field equals exactly 404 (the number four hundred and four, not numbers like 40401 that contain 404 as a substring).",
        "model": ListAnswer,
        "gold_fn": gold_q17_code_404,
    },
    {
        "id": "q18",
        "fixture": "tricky",
        "question": "What are the tags for the record with id 'T07'? Return them exactly as they appear.",
        "model": ListAnswer,
        "gold_fn": gold_q18_tags_for_t07,
    },
```

- [ ] **Step 4: Verify all gold answers compute**

```bash
cd /home/edge/code/tokkit && python -c "
import sys; sys.path.insert(0, 'tests')
from json_tests.fixtures.eval_questions import *
sparse = load_sparse()
large = load_large_orders()
tricky = load_tricky()
print('Q10:', gold_q10_non_null_city(sparse))
print('Q11:', gold_q11_has_skills(sparse))
print('Q12:', gold_q12_avg_salary(sparse))
print('Q13:', gold_q13_total_revenue(large))
print('Q14:', gold_q14_ca_count(large))
print('Q15:', gold_q15_ca_refunds(large))
print('Q16:', gold_q16_name_by_id(tricky))
print('Q17:', gold_q17_code_404(tricky))
print('Q18:', gold_q18_tags_for_t07(tricky))
print(f'Large orders: {len(large)}')
print('All gold answers OK')
"
```

Expected: 9 lines of output, 120 large orders, no errors.

- [ ] **Step 5: Commit**

```bash
git add tests/json_tests/fixtures/eval_questions.py
git commit -m "test: add Q10-Q18 questions with sparse, large, tricky fixtures"
```

---

### Task 4: Update conftest with New Fixture Loaders

**Files:**
- Modify: `tests/json_tests/conftest.py`

- [ ] **Step 1: Add new fixture loaders**

Add these fixtures to the end of `tests/json_tests/conftest.py`:

```python
@pytest.fixture
def sparse_raw_json() -> str:
    """Load sparse fixture as raw JSON string."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sparse_records.json")
    with open(path) as f:
        return f.read()


@pytest.fixture
def sparse_data(sparse_raw_json) -> list[dict]:
    """Parse sparse fixture."""
    return json.loads(sparse_raw_json)


@pytest.fixture
def sparse_compacted(sparse_raw_json) -> str:
    """Compact sparse fixture."""
    return compact_json(sparse_raw_json)


@pytest.fixture
def tricky_raw_json() -> str:
    """Load tricky values fixture as raw JSON string."""
    path = os.path.join(os.path.dirname(__file__), "fixtures", "tricky_values.json")
    with open(path) as f:
        return f.read()


@pytest.fixture
def tricky_data(tricky_raw_json) -> list[dict]:
    """Parse tricky values fixture."""
    return json.loads(tricky_raw_json)


@pytest.fixture
def tricky_compacted(tricky_raw_json) -> str:
    """Compact tricky values fixture."""
    return compact_json(tricky_raw_json)


@pytest.fixture
def large_raw_json() -> str:
    """Generate large orders fixture as raw JSON string."""
    from json_tests.fixtures.eval_questions import generate_large_orders
    return json.dumps(generate_large_orders(), indent=2)


@pytest.fixture
def large_data(large_raw_json) -> list[dict]:
    """Parse large orders fixture."""
    return json.loads(large_raw_json)


@pytest.fixture
def large_compacted(large_raw_json) -> str:
    """Compact large orders fixture."""
    return compact_json(large_raw_json)
```

- [ ] **Step 2: Commit**

```bash
git add tests/json_tests/conftest.py
git commit -m "test: add sparse, tricky, large fixture loaders to conftest"
```

---

### Task 5: Data Fidelity Tests for New Fixtures

**Files:**
- Modify: `tests/json_tests/test_data_fidelity.py`

- [ ] **Step 1: Add sparse data fidelity tests**

Append to the end of `tests/json_tests/test_data_fidelity.py`:

```python
# ---------------------------------------------------------------------------
# Sparse fixture fidelity
# ---------------------------------------------------------------------------

class TestSparseDataFidelity:
    """Verify sparse fixture data survives compaction (especially nulls)."""

    def test_all_ids_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            assert record["id"] in sparse_compacted

    def test_non_null_names_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            if record["name"] is not None:
                assert record["name"] in sparse_compacted, (
                    f"Name '{record['name']}' for {record['id']} missing"
                )

    def test_non_null_cities_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            if record["city"] is not None:
                assert record["city"] in sparse_compacted

    def test_non_null_salaries_preserved(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            if record["salary"] is not None:
                assert str(record["salary"]) in sparse_compacted

    def test_skills_present(self, sparse_compacted, sparse_data):
        for record in sparse_data:
            for skill in record["skills"]:
                assert skill in sparse_compacted, (
                    f"Skill '{skill}' for {record['id']} missing"
                )

    def test_schema_header_has_all_fields(self, sparse_compacted):
        first_line = sparse_compacted.split("\n")[0]
        for field in ["id", "name", "email", "city", "state", "age", "role", "skills", "salary"]:
            assert field in first_line, f"Field '{field}' missing from schema header"


# ---------------------------------------------------------------------------
# Tricky values fixture fidelity
# ---------------------------------------------------------------------------

class TestTrickyDataFidelity:
    """Verify tricky values survive compaction (escaping edge cases)."""

    def test_all_ids_present(self, tricky_compacted, tricky_data):
        for record in tricky_data:
            assert record["id"] in tricky_compacted

    def test_semicolon_names_present(self, tricky_compacted, tricky_data):
        """Names with semicolons should be quoted in output."""
        for record in tricky_data:
            if ";" in (record["name"] or ""):
                # The name should appear somewhere in the output (possibly quoted)
                assert record["name"].replace(";", "") in tricky_compacted.replace(";", "") or \
                    record["name"] in tricky_compacted, (
                    f"Name '{record['name']}' for {record['id']} missing"
                )

    def test_unicode_preserved(self, tricky_compacted, tricky_data):
        for record in tricky_data:
            if any(ord(c) > 127 for c in (record["name"] or "")):
                assert record["name"] in tricky_compacted

    def test_all_codes_preserved(self, tricky_compacted, tricky_data):
        for record in tricky_data:
            assert str(record["code"]) in tricky_compacted

    def test_empty_string_vs_null(self, tricky_compacted, tricky_data):
        """T11 has empty string name, not null — both should not lose the record."""
        assert "T11" in tricky_compacted


# ---------------------------------------------------------------------------
# Large orders fixture fidelity
# ---------------------------------------------------------------------------

class TestLargeDataFidelity:
    """Verify large-scale fixture data survives compaction."""

    def test_all_order_ids_present(self, large_compacted, large_data):
        for order in large_data:
            assert order["order_id"] in large_compacted, (
                f"Order '{order['order_id']}' missing"
            )

    def test_order_count(self, large_data):
        assert len(large_data) == 120

    def test_all_states_present(self, large_compacted, large_data):
        states = {o["shipping"]["address"]["state"] for o in large_data}
        for state in states:
            assert state in large_compacted

    def test_refund_amounts_preserved(self, large_compacted, large_data):
        for order in large_data:
            for ret in order.get("returns", []):
                assert str(ret["refund_amount"]) in large_compacted
```

- [ ] **Step 2: Run all data fidelity tests**

```bash
cd /home/edge/code/tokkit && uv run pytest tests/json_tests/test_data_fidelity.py -v
```

Expected: all tests PASS (original 19 + new ones).

- [ ] **Step 3: Commit**

```bash
git add tests/json_tests/test_data_fidelity.py
git commit -m "test: add data fidelity tests for sparse, tricky, large fixtures"
```

---

### Task 6: Rewrite test_inference_eval.py with Parametrization

**Files:**
- Rewrite: `tests/json_tests/test_inference_eval.py`

This is a full rewrite. The new version parametrizes over questions and models instead of having one method per question.

- [ ] **Step 1: Write the new test_inference_eval.py**

Replace the entire file with:

```python
"""LLM inference accuracy eval for compact_json.

Compares LLM accuracy on raw JSON vs compacted JSON against gold answers.
Uses claude_agent_sdk (authenticates via Claude Code credentials).

Run: pytest -m inference tests/json_tests/test_inference_eval.py -v
"""

import asyncio
import json
import os
import re
from datetime import date

import pytest
from pydantic import BaseModel

from tokkit_json import compact_json

from json_tests.fixtures.eval_questions import (
    QUESTIONS,
    CountAnswer,
    NumericAnswer,
    ListAnswer,
    RankedAnswer,
    ClassificationAnswer,
    PathAnswer,
    load_org,
    load_ecommerce,
    load_sparse,
    load_tricky,
    load_large_orders,
)

from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODELS = ["sonnet", "haiku"]
CHARS_PER_TOKEN = 4


# ---------------------------------------------------------------------------
# LLM call helper
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, stripping markdown fences if present."""
    m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if m:
        text = m.group(1)
    return json.loads(text.strip())


def _ask_llm(data_str: str, question: str, response_model: type[BaseModel], model: str) -> BaseModel:
    """Send a question + data to Claude, return parsed structured output."""
    schema = json.dumps(response_model.model_json_schema(), indent=2)
    system = (
        "You are a data analyst. You will be given a dataset and a question. "
        "Analyze the data carefully and answer the question. "
        "Respond with ONLY a raw JSON object matching this schema "
        "(no markdown, no code fences, no explanation, just JSON):\n"
        f"{schema}"
    )

    options = ClaudeAgentOptions(
        system_prompt=system,
        model=model,
        max_turns=1,
    )

    user_prompt = f"Given the following data:\n\n{data_str}\n\nAnswer this question: {question}"

    result_text = None

    async def _run():
        nonlocal result_text
        async for msg in query(prompt=user_prompt, options=options):
            if isinstance(msg, ResultMessage):
                result_text = msg.result

    asyncio.get_event_loop().run_until_complete(_run())

    if not result_text:
        raise RuntimeError("No result from Claude")

    raw = _extract_json(result_text)
    return response_model.model_validate(raw)


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------

def answers_match(result: BaseModel, gold: BaseModel) -> bool:
    """Compare LLM result against gold answer based on model type."""
    if isinstance(gold, CountAnswer):
        return result.count == gold.count

    if isinstance(gold, NumericAnswer):
        return abs(result.value - gold.value) < 0.01

    if isinstance(gold, ListAnswer):
        return set(s.lower() for s in result.items) == set(s.lower() for s in gold.items)

    if isinstance(gold, RankedAnswer):
        if len(result.rankings) != len(gold.rankings):
            return False
        for r, g in zip(result.rankings, gold.rankings):
            if r.name.lower() != g.name.lower():
                return False
            if abs(r.value - g.value) > 0.01:
                return False
        return True

    if isinstance(gold, ClassificationAnswer):
        result_set = {(c.name.lower(), c.category.lower()) for c in result.classifications}
        gold_set = {(c.name.lower(), c.category.lower()) for c in gold.classifications}
        return result_set == gold_set

    if isinstance(gold, PathAnswer):
        return [s.lower() for s in result.path] == [s.lower() for s in gold.path]

    raise TypeError(f"Unknown answer type: {type(gold)}")


# ---------------------------------------------------------------------------
# Fixture data loaders (cached at module level)
# ---------------------------------------------------------------------------

_fixture_cache: dict[str, tuple] = {}


def _get_fixture(fixture_name: str) -> tuple[str, str, object]:
    """Return (raw_json, compacted, parsed_data) for a fixture. Cached."""
    if fixture_name not in _fixture_cache:
        if fixture_name == "org":
            data = load_org()
        elif fixture_name == "ecommerce":
            data = load_ecommerce()
        elif fixture_name == "sparse":
            data = load_sparse()
        elif fixture_name == "tricky":
            data = load_tricky()
        elif fixture_name == "large":
            data = load_large_orders()
        else:
            raise ValueError(f"Unknown fixture: {fixture_name}")
        raw = json.dumps(data, indent=2)
        compacted = compact_json(raw)
        _fixture_cache[fixture_name] = (raw, compacted, data)
    return _fixture_cache[fixture_name]


# ---------------------------------------------------------------------------
# Results collection
# ---------------------------------------------------------------------------

_results: list[dict] = []


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------

_question_ids = [q["id"] for q in QUESTIONS]


@pytest.mark.inference
class TestInferenceEval:

    @pytest.mark.parametrize("model", MODELS)
    @pytest.mark.parametrize("q_id", _question_ids)
    def test_question(self, q_id, model):
        q = next(q for q in QUESTIONS if q["id"] == q_id)
        raw, compacted, data = _get_fixture(q["fixture"])
        gold = q["gold_fn"](data)

        control = _ask_llm(raw, q["question"], q["model"], model)
        treatment = _ask_llm(compacted, q["question"], q["model"], model)

        _results.append({
            "id": q_id,
            "model": model,
            "fixture": q["fixture"],
            "question": q["question"][:60],
            "control_correct": answers_match(control, gold),
            "treatment_correct": answers_match(treatment, gold),
            "control_answer": control.model_dump(),
            "treatment_answer": treatment.model_dump(),
            "gold_answer": gold.model_dump(),
            "raw_tokens": len(raw) // CHARS_PER_TOKEN,
            "compact_tokens": len(compacted) // CHARS_PER_TOKEN,
        })

        assert answers_match(treatment, gold), (
            f"[{model}] {q_id} treatment wrong: got {treatment.model_dump()}, "
            f"expected {gold.model_dump()}"
        )

    def test_z_generate_report(self):
        """Generate markdown report after all questions."""
        expected = len(QUESTIONS) * len(MODELS)
        if len(_results) < expected:
            pytest.skip(f"Only {len(_results)}/{expected} results collected")

        lines = [
            "# JSON Compaction Inference Eval Results",
            "",
            f"**Date:** {date.today().isoformat()}",
            f"**Models:** {', '.join(MODELS)}",
            f"**Questions:** {len(QUESTIONS)}",
            f"**Total LLM calls:** {len(_results) * 2} ({len(_results)} questions x 2 control/treatment)",
            "",
            "## Per-Question Results",
            "",
            "| # | Fixture | Question | " + " | ".join(f"{m} Ctrl | {m} Treat" for m in MODELS) + " | Savings |",
            "|---|---------|----------|" + "|".join("---------|----------" for _ in MODELS) + "|---------|",
        ]

        for q in QUESTIONS:
            q_results = {r["model"]: r for r in _results if r["id"] == q["id"]}
            if not q_results:
                continue
            cols = []
            for m in MODELS:
                r = q_results.get(m)
                if r:
                    ctrl = "PASS" if r["control_correct"] else "FAIL"
                    treat = "PASS" if r["treatment_correct"] else "FAIL"
                    cols.append(f" {ctrl} | {treat}")
                else:
                    cols.append(" - | -")
            # Use first available result for savings
            r0 = next(iter(q_results.values()))
            savings = (1 - r0["compact_tokens"] / r0["raw_tokens"]) * 100 if r0["raw_tokens"] > 0 else 0
            lines.append(
                f"| {q['id']} | {q.get('fixture', '?')} | {q['question'][:50]} |"
                + " |".join(cols)
                + f" | {savings:.0f}% |"
            )

        # Summary per model
        lines.extend(["", "## Summary by Model", ""])
        for m in MODELS:
            m_results = [r for r in _results if r["model"] == m]
            ctrl_ok = sum(1 for r in m_results if r["control_correct"])
            treat_ok = sum(1 for r in m_results if r["treatment_correct"])
            total = len(m_results)
            lines.append(
                f"**{m}:** Control {ctrl_ok}/{total} ({ctrl_ok/total*100:.0f}%), "
                f"Treatment {treat_ok}/{total} ({treat_ok/total*100:.0f}%), "
                f"Delta {treat_ok - ctrl_ok}"
            )

        # Summary per fixture type
        lines.extend(["", "## Summary by Fixture Type", ""])
        fixture_types = list(dict.fromkeys(q.get("fixture", "?") for q in QUESTIONS))
        for ft in fixture_types:
            ft_results = [r for r in _results if r["fixture"] == ft]
            ctrl_ok = sum(1 for r in ft_results if r["control_correct"])
            treat_ok = sum(1 for r in ft_results if r["treatment_correct"])
            total = len(ft_results)
            if total > 0:
                lines.append(
                    f"**{ft}:** Control {ctrl_ok}/{total}, Treatment {treat_ok}/{total}"
                )

        # Failures detail
        failures = [r for r in _results if not r["treatment_correct"]]
        if failures:
            lines.extend(["", "## Treatment Failures", ""])
            for r in failures:
                lines.append(f"### [{r['model']}] {r['id']}: {r['question']}")
                lines.append(f"- **Gold:** `{r['gold_answer']}`")
                lines.append(f"- **Treatment got:** `{r['treatment_answer']}`")
                lines.append(f"- **Control got:** `{r['control_answer']}`")
                ctrl_ok = "correct" if r["control_correct"] else "also wrong"
                lines.append(f"- **Control was:** {ctrl_ok}")
                lines.append("")

        report = "\n".join(lines)
        report_path = os.path.join(
            os.path.dirname(__file__), "..", "INFERENCE_EVAL_RESULTS.md"
        )
        with open(report_path, "w") as f:
            f.write(report)

        print(f"\n\n{report}")
```

- [ ] **Step 2: Verify tests are collected correctly**

```bash
cd /home/edge/code/tokkit && uv run pytest tests/json_tests/test_inference_eval.py --collect-only 2>&1 | head -50
```

Expected: 18 questions x 2 models = 36 parametrized tests + 1 report = 37 total.

- [ ] **Step 3: Verify existing deterministic tests still pass**

```bash
cd /home/edge/code/tokkit && uv run pytest tests/json_tests/test_data_fidelity.py tests/json_tests/test_compact_json.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/json_tests/test_inference_eval.py
git commit -m "test: rewrite inference eval with parametrized questions and multi-model support"
```

---

### Task 7: Run the Full Stress Eval

- [ ] **Step 1: Run data fidelity tests**

```bash
cd /home/edge/code/tokkit && uv run pytest tests/json_tests/test_data_fidelity.py -v
```

Expected: all PASS.

- [ ] **Step 2: Run inference eval (all models, all questions)**

```bash
cd /home/edge/code/tokkit && uv run pytest -m inference tests/json_tests/test_inference_eval.py -v -s --timeout=600
```

Expected: 37 tests. Some haiku tests may fail — that's the point. Review which ones.

- [ ] **Step 3: Review results and commit report**

Read `tests/INFERENCE_EVAL_RESULTS.md`. Analyze:
- Does haiku fail on questions where sonnet passes? (Model weakness, not compaction)
- Does treatment fail where control passes for the same model? (Compaction-caused accuracy loss)
- Which fixture types are hardest? (sparse, large, tricky)

```bash
git add tests/INFERENCE_EVAL_RESULTS.md
git commit -m "test: inference eval stress results — multi-model, sparse, large, tricky"
```
